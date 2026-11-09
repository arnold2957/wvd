"""pywebview 版图形界面.

界面直接使用同目录下的 ``ui.html``. 本模块负责:

* 读取 / 保存配置 (沿用 config.json 的原有结构)
* 启动 / 停止脚本任务
* 把日志与后台事件放进一个线程安全队列, 由前端定时 ``poll`` 取走
* 暴露给 JavaScript 的 API (``WebBridge``)

窗口本身由 pywebview 创建, 因此不再依赖 tkinter 的主循环.
"""

import copy
import ctypes
import os
import platform
import queue
import re
import sys
import threading
import webbrowser
from datetime import date, datetime

import tkinter as tk
import webview

from script import *
from auto_updater import *
from utils import *


# ============================================================
# 与原 Tk 版本保持一致的配置读写函数
# ============================================================
def LoadSettingFromDict(input_dict):
    setting = FarmConfig()

    for category, attr_name, var_type, default_value in CONFIG_VAR_LIST:
        if attr_name not in input_dict:
            setattr(setting, attr_name, default_value)
        else:
            setattr(setting, attr_name, input_dict[attr_name])

    return setting


def LoadConfig(specific='ALL'):
    raw_config = LoadRawConfigFromFile() or {}
    general_config = raw_config.get("GENERAL", {})

    # 兼容旧字段名: KARMA_ADJUST 已重命名为 KARMA_ADJUST_REMAINING.
    if "KARMA_ADJUST_REMAINING" not in general_config and "KARMA_ADJUST" in general_config:
        general_config = dict(general_config)
        general_config["KARMA_ADJUST_REMAINING"] = general_config["KARMA_ADJUST"]

    # 旧配置没有 KARMA_MAINTAIN 时, 按剩余点数推断.
    if "KARMA_MAINTAIN" not in general_config:
        general_config = dict(general_config)
        try:
            karma_remaining = int(str(general_config.get("KARMA_ADJUST_REMAINING") or "0").strip() or 0)
        except (TypeError, ValueError):
            karma_remaining = 0
        general_config["KARMA_MAINTAIN"] = karma_remaining == 0

    task_specific = general_config.get("TASK_SPECIFIC_CONFIG", False)
    farm_target = general_config.get("FARM_TARGET")

    if task_specific and farm_target and farm_target in raw_config:
        task_config = raw_config.get(farm_target, {})
    else:
        task_config = raw_config.get("DEFAULT", {})

    if specific == "ALL":
        result_config = {}
        result_config.update(general_config)
        result_config.update(task_config)
    elif specific == "general":
        result_config = general_config
    elif specific == "specific":
        result_config = raw_config.get(farm_target, {})
    elif specific == "default":
        result_config = raw_config.get("DEFAULT", {})

    return result_config


# ============================================================
# 工具函数
# ============================================================
def _is_bool_var(var_type):
    return var_type is tk.BooleanVar


def _is_int_var(var_type):
    return var_type is tk.IntVar


def _to_bool(value):
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _to_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _display_of(value, canon):
    """把规范中文值转成当前语言下的显示文本.

    无法识别的旧值原样保留, 避免保存时悄悄改掉用户的配置.
    """
    if value in canon:
        return _(value)
    displayed = [_(c) for c in canon]
    if value in displayed:
        return value
    return value if value else _(canon[0])


def _canonical_of(value, canon):
    """把当前语言下的显示文本转回规范中文值."""
    if value in canon:
        return value
    for c in canon:
        if value == _(c):
            return c
    return value if value else canon[0]


def _kill_webview_children():
    """结束本进程创建的 WebView2 子进程树.

    pywebview 退出后, msedgewebview2.exe 往往还会在后台存活一两秒.
    关闭 UI 时主动结束它, 避免用户看到"程序已关但后台还在".
    """
    if os.name != "nt":
        return
    try:
        from ctypes import wintypes
        TH32CS_SNAPPROCESS = 0x00000002
        invalid_handle = ctypes.c_void_p(-1).value

        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_char * 260),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel32.Process32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
        kernel32.Process32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snapshot in (None, 0, invalid_handle):
            return

        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        children = {}
        if kernel32.Process32First(snapshot, ctypes.byref(entry)):
            while True:
                pid = entry.th32ProcessID
                ppid = entry.th32ParentProcessID
                name = entry.szExeFile.decode(errors="ignore").lower()
                children.setdefault(ppid, []).append((pid, name))
                if not kernel32.Process32Next(snapshot, ctypes.byref(entry)):
                    break
        kernel32.CloseHandle(snapshot)

        # 从本进程向下的 WebView2 子树 (browser / gpu / renderer ...).
        targets = set()
        stack = [pid for pid, name in children.get(os.getpid(), [])
                 if name == "msedgewebview2.exe"]
        while stack:
            pid = stack.pop()
            if pid in targets:
                continue
            targets.add(pid)
            for child_pid, _child_name in children.get(pid, []):
                stack.append(child_pid)

        PROCESS_TERMINATE = 0x0001
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel32.TerminateProcess.restype = wintypes.BOOL
        for pid in targets:
            try:
                handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
                if handle:
                    kernel32.TerminateProcess(handle, 1)
                    kernel32.CloseHandle(handle)
            except Exception:
                pass
    except Exception:
        pass


# ============================================================
# 启动前环境检查
# ============================================================
# pywebview 的 edgechromium 后端依赖三样东西, 任何一样缺失都会在
# webview.start() 时直接崩溃 (通常是 Windows 弹窗后进程消失):
#   1. pythonnet 的 Python.Runtime.dll (.NET Framework 4.6.2+)
#   2. webview/lib 下的 WebView2 托管 DLL 与 WebView2Loader.dll
#   3. 系统已安装 WebView2 Runtime
# 这里在创建窗口之前先把它们查一遍, 失败时用原生 MessageBox 说明原因,
# 而不是让用户面对一个没有任何提示的闪退.

WEBVIEW2_CLIENT_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
WEBVIEW2_DOWNLOAD_URL = "https://developer.microsoft.com/microsoft-edge/webview2/"
NETFX_DOWNLOAD_URL = "https://dotnet.microsoft.com/download/dotnet-framework/net48"
MIN_NETFX_RELEASE = 394802  # .NET Framework 4.6.2

_RUNTIME_FILE_INDEX = None


def _read_reg_value(root, subkey, name):
    """读取注册表值; 不存在或平台不支持时返回 None."""
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return value
    except OSError:
        return None


def _runtime_roots():
    """返回打包后可能存放运行库文件的目录, 按优先级排序."""
    roots = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(meipass)
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        roots.append(exe_dir)
        roots.append(os.path.join(exe_dir, "_internal"))
    return list(dict.fromkeys(p for p in roots if p and os.path.isdir(p)))


def _runtime_file_index():
    """一次性索引打包目录中的文件名 -> 路径, 避免反复遍历."""
    global _RUNTIME_FILE_INDEX
    if _RUNTIME_FILE_INDEX is not None:
        return _RUNTIME_FILE_INDEX
    index = {}
    for root in _runtime_roots():
        for dirpath, dirnames, filenames in os.walk(root):
            depth = dirpath[len(root):].count(os.sep)
            if depth >= 6:
                # WebView2Loader.dll 位于 webview/lib/runtimes/<arch>/native,
                # 深度约为 5 层, 这里只停止继续下钻, 仍然索引当前目录.
                dirnames[:] = []
            for name in filenames:
                index.setdefault(name.lower(), []).append(
                    os.path.join(dirpath, name))
    _RUNTIME_FILE_INDEX = index
    return index


def _runtime_files(name):
    return _runtime_file_index().get(name.lower(), [])


def _find_runtime_file(name):
    paths = _runtime_files(name)
    return paths[0] if paths else None


def _clear_runtime_motw():
    """递归清除程序目录中可执行模块的 MOTW.

    手动下载/解压的安装包不会经过更新器, 这里在加载 CLR 前统一处理.
    不在白名单里区分原生 DLL: 任何 .dll/.exe/.pyd 带上 MOTW 都可能被
    Windows 阻止加载, 因此整个目录树都要扫一遍.
    """
    roots = list(_runtime_roots())
    if not getattr(sys, "frozen", False):
        # 源码运行时 _runtime_roots() 为空, 退回到脚本所在目录.
        roots.append(os.path.dirname(os.path.abspath(__file__)))

    # 去掉被上层目录包含的根, 避免同一批文件被遍历多次 (如 _MEIPASS 与 _internal).
    scan_roots = []
    for root in sorted(dict.fromkeys(os.path.abspath(r) for r in roots), key=len):
        if not any(root == other or root.startswith(other + os.sep)
                   for other in scan_roots):
            scan_roots.append(root)

    paths = []
    for root in scan_roots:
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in filenames:
                if name.lower().endswith((".dll", ".exe", ".pyd")):
                    paths.append(os.path.join(dirpath, name))
    return ClearMotw(paths)


def _load_changelog():
    """读取版本更新说明 (CHANGES_LOG.md) 中最新版本的一段, 用于启动弹窗.

    与发布通报 (notify.py) 保持一致: 取第一个 "###" 标题到第一个空行
    之间的内容, 而不是整份更新日志.
    """
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    candidates = [
        os.path.join(base_dir, "CHANGES_LOG.md"),
        os.path.join(os.getcwd(), "CHANGES_LOG.md"),
    ]
    text = ""
    for path in dict.fromkeys(os.path.abspath(p) for p in candidates):
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                text = f.read()
            break
        except OSError:
            continue
    if not text:
        return ""

    header = re.search(r"^###[ \t]*(.+?)[ \t]*$", text, re.MULTILINE)
    if not header:
        return ""
    end = re.search(r"\r?\n\r?\n", text[header.end():])
    body = text[header.end():header.end() + end.start()] if end else text[header.end():]
    lines = [line.rstrip() for line in body.splitlines() if line.strip()]
    return "\n".join([header.group(1).strip(), *lines])


def _netfx_release():
    """返回已安装的 .NET Framework 4.x Release 值 (4.6.2 = 394802)."""
    try:
        import winreg
    except ImportError:
        return None
    releases = []
    for subkey in (
        r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full",
        r"SOFTWARE\WOW6432Node\Microsoft\NET Framework Setup\NDP\v4\Full",
    ):
        value = _read_reg_value(winreg.HKEY_LOCAL_MACHINE, subkey, "Release")
        if isinstance(value, int):
            releases.append(value)
    return max(releases) if releases else None


def _webview2_version():
    """返回已安装的 WebView2 Runtime 版本号, 未安装时返回 None."""
    try:
        import winreg
    except ImportError:
        return None
    for root, subkey in (
        (winreg.HKEY_LOCAL_MACHINE,
         rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_CLIENT_GUID}"),
        (winreg.HKEY_LOCAL_MACHINE,
         rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_CLIENT_GUID}"),
        (winreg.HKEY_CURRENT_USER,
         rf"Software\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_CLIENT_GUID}"),
    ):
        value = _read_reg_value(root, subkey, "pv")
        if value and str(value) not in ("", "0.0.0.0"):
            return str(value)

    # 注册表被清理时, 再按安装目录兜底检测.
    base = os.path.join(
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        "Microsoft", "EdgeWebView", "Application")
    try:
        for name in os.listdir(base):
            if re.match(r"^\d+\.\d+\.\d+\.\d+$", name):
                return name
    except OSError:
        pass
    return None


def _try_load_clr():
    """尝试加载 pythonnet, 返回 (错误信息, 是否回退到 coreclr)."""
    try:
        import clr  # noqa: F401
        return None, False
    except BaseException as first_error:
        first_msg = f"{type(first_error).__name__}: {first_error}"

    # 与 pywebview 的 edgechromium 后端一致: netfx 失败时回退 coreclr.
    old_runtime = os.environ.get("PYTHONNET_RUNTIME")
    os.environ["PYTHONNET_RUNTIME"] = "coreclr"
    try:
        import clr  # noqa: F401
        return None, True
    except BaseException as second_error:
        if old_runtime is None:
            os.environ.pop("PYTHONNET_RUNTIME", None)
        else:
            os.environ["PYTHONNET_RUNTIME"] = old_runtime
        return (f"{first_msg}; coreclr 回退失败: "
                f"{type(second_error).__name__}: {second_error}"), False


def _fit_window_size(width=1158, height=820, margin=24):
    """按显示器工作区收缩初始窗口, 避免高 DPI / 小屏幕下窗口超出屏幕.

    返回 (宽, 高, 系统缩放比例). 尺寸使用 pywebview/WinForms 的逻辑像素.
    """
    if os.name != "nt":
        return width, height, 1.0
    try:
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

        scale = 1.0
        try:
            dpi = user32.GetDpiForSystem()
            if dpi:
                scale = dpi / 96.0
        except Exception:
            try:
                hdc = user32.GetDC(0)
                dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
                user32.ReleaseDC(0, hdc)
                if dpi:
                    scale = dpi / 96.0
            except Exception:
                pass

        rect = wintypes.RECT()
        # SPI_GETWORKAREA: 主显示器去掉任务栏后的可用区域 (物理像素).
        if user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
            avail_w = (rect.right - rect.left) / scale
            avail_h = (rect.bottom - rect.top) / scale
            fitted_w = max(640, min(int(width), int(avail_w) - margin))
            fitted_h = max(200, min(int(height), int(avail_h) - margin))
            return fitted_w, fitted_h, scale
    except Exception:
        logger.exception("计算窗口尺寸失败, 使用默认尺寸")
    return width, height, 1.0


def PreflightCheck(version_changed=False):
    """在创建窗口之前检查运行环境.

    version_changed 为 True 表示本次启动的版本与上次运行不同 (刚更新过),
    此时才需要清理整个目录的 MOTW.

    返回 dict: ok / fatal / warnings / actions / details / window_size.
    """
    report = {
        "ok": True,
        "fatal": [],
        "warnings": [],
        "actions": [],   # [(说明, 下载地址), ...]
        "details": {},
        "window_size": (1158, 820),
    }

    # 布局适配: 高 DPI 或小屏幕时缩小初始窗口.
    fitted_w, fitted_h, scale = _fit_window_size()
    report["details"]["dpi_scale"] = scale
    report["window_size"] = (fitted_w, fitted_h)
    if fitted_w != 1158 or fitted_h != 820:
        report["warnings"].append(
            f"屏幕可用区域较小或缩放为 {int(scale * 100)}%, "
            f"窗口已自动调整为 {fitted_w}x{fitted_h}.")

    if os.name != "nt":
        return report

    frozen = bool(getattr(sys, "frozen", False))

    # ---- 1. 打包文件是否完整 ----
    if frozen:
        required = (
            ("Python.Runtime.dll", "pythonnet 的 .NET 运行时库"),
            ("Microsoft.Web.WebView2.Core.dll", "WebView2 托管库"),
            ("Microsoft.Web.WebView2.WinForms.dll", "WebView2 WinForms 绑定"),
        )
        for name, desc in required:
            if not _find_runtime_file(name):
                report["fatal"].append(
                    f"缺少 {name}（{desc}）。程序打包不完整，或被安全软件隔离/删除。")

        is_64 = (sys.maxsize > 2 ** 32)
        machine = platform.machine().lower()
        if machine in ("arm64", "aarch64"):
            arch_dir = "win-arm64"
        else:
            arch_dir = "win-x64" if is_64 else "win-x86"
        loader_paths = _runtime_files("WebView2Loader.dll")
        if not loader_paths:
            report["fatal"].append(
                "缺少 WebView2Loader.dll（WebView2 加载器），程序无法创建 WebView2 窗口。")
        elif not any(f"\\{arch_dir}\\" in path.replace("/", "\\").lower()
                     for path in loader_paths):
            report["warnings"].append(
                f"WebView2Loader.dll 的架构目录不是 {arch_dir}，"
                "可能无法在当前 Python 上加载。")

    # ---- 2. WebView2 Runtime ----
    webview2 = _webview2_version()
    report["details"]["webview2"] = webview2
    if not webview2:
        report["fatal"].append(
            "未安装 Microsoft Edge WebView2 Runtime，界面引擎无法启动。")
        report["actions"].append(("安装 WebView2 Runtime", WEBVIEW2_DOWNLOAD_URL))

    # ---- 3. .NET Framework ----
    netfx = _netfx_release()
    report["details"]["netfx_release"] = netfx
    if netfx is None:
        report["warnings"].append("未检测到 .NET Framework 4.x，将尝试使用 .NET Core 运行时。")
    elif netfx < MIN_NETFX_RELEASE:
        report["warnings"].append(
            f".NET Framework 版本过低（Release={netfx}，需要 4.6.2 及以上）。")

    # ---- 4. 实际加载 pythonnet ----
    # 前面的文件检查已经失败时不再尝试, 避免在已知缺失的环境里触发底层崩溃.
    if not report["fatal"]:
        # 只有版本发生变化 (刚更新过) 时才清理: 手动下载/解压的新包会带 MOTW,
        # 而平时启动不需要重复扫描整个目录.
        if version_changed:
            motw_cleared = _clear_runtime_motw()
            if motw_cleared:
                report["details"]["motw_cleared"] = motw_cleared
                logger.info(f"已清除 {motw_cleared} 个可执行模块的 MOTW.")
        clr_error, used_coreclr = _try_load_clr()
        report["details"]["clr_coreclr"] = used_coreclr
        if clr_error:
            report["fatal"].append(
                "无法初始化 .NET 运行时（Python.Runtime.dll / CLR 加载失败）：" + clr_error)
            report["actions"].append(("安装 .NET Framework 4.8", NETFX_DOWNLOAD_URL))
        elif used_coreclr:
            report["warnings"].append("已回退到 .NET Core 运行时。")

    report["ok"] = not report["fatal"]
    return report


def _native_message(title, text, flags):
    """不依赖 WebView 的原生消息框, 界面引擎坏掉时也能显示."""
    try:
        return ctypes.windll.user32.MessageBoxW(0, text, title, flags)
    except Exception:
        return 0


def ShowPreflightErrorAndExit(report):
    """显示环境检查结果并退出进程."""
    title = "wvdas 启动失败"
    lines = ["程序运行环境检查未通过，界面无法启动。", ""]
    for index, message in enumerate(report["fatal"], 1):
        lines.append(f"{index}. {message}")
    if report["warnings"]:
        lines.append("")
        lines.append("其他提示：")
        lines.extend(f"· {w}" for w in report["warnings"])

    actions = report.get("actions") or []
    if actions:
        lines.append("")
        lines.append("可以安装以下组件后重试：")
        lines.extend(f"· {label}：{url}" for label, url in actions)

    lines.append("")
    lines.append("详细诊断信息已写入 logs\\preflight_error.log。")

    # 写一份独立诊断日志, 方便用户直接发出来排查.
    try:
        os.makedirs("logs", exist_ok=True)
        with open(os.path.join("logs", "preflight_error.log"), "a", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
            f.write(f"fatal: {report['fatal']}\n")
            f.write(f"warnings: {report['warnings']}\n")
            f.write(f"details: {report['details']}\n")
    except Exception:
        pass
    logger.error("启动前环境检查失败: " + "; ".join(report["fatal"]))

    MB_ICONERROR = 0x10
    MB_TOPMOST = 0x40000
    if actions:
        lines.append("")
        lines.append(f"是否现在打开下载页面（{actions[0][0]}）？")
        answer = _native_message(title, "\n".join(lines),
                                 MB_ICONERROR | MB_TOPMOST | 0x4)  # MB_YESNO
        if answer == 6:  # IDYES
            try:
                webbrowser.open(actions[0][1])
            except Exception:
                pass
    else:
        _native_message(title, "\n".join(lines), MB_ICONERROR | MB_TOPMOST)

    HardExit(1)


# ============================================================
# 前端可调用的 API
# ============================================================
class WebBridge:
    """pywebview 会把这里的公开方法暴露为 window.pywebview.api."""

    def __init__(self, app):
        self._app = app

    # ---- 初始化 / 轮询 ----
    def bootstrap(self):
        return self._app.bootstrap()

    def poll(self):
        return self._app.poll()

    # ---- 窗口 ----
    def minimize_window(self):
        return self._app.minimize_window()

    def toggle_maximize(self):
        return self._app.toggle_maximize()

    def close_window(self):
        self._app.close_window()
        return {"ok": True}

    def set_compact(self, enabled, height=None):
        return self._app.set_compact(enabled, height)

    # ---- 配置 ----
    def save(self, patch):
        return self._app.save(patch or {})

    def set_language(self, kind, value):
        return self._app.set_language(kind, value)

    def choose_emu_path(self):
        return self._app.choose_emu_path()

    # ---- 任务 / 战斗 ----
    def select_target(self, text):
        return self._app.select_target(text)

    def set_task_specific(self, enabled):
        return self._app.set_task_specific(enabled)

    def clear_task_specific(self):
        return self._app.clear_task_specific()

    def set_overall_strategy(self, value, enable_custom=False):
        return self._app.set_overall_strategy(value, enable_custom)

    def set_task_point_strategy(self, index, value):
        return self._app.set_task_point_strategy(index, value)

    def save_plans(self, plans):
        return self._app.save_plans(plans)

    # ---- 日常 ----
    def claim_gem(self, url):
        return self._app.claim_gem(url)

    def switch_monthly(self):
        return self._app.switch_monthly()

    # ---- 其他 ----
    def open_url(self, url):
        return self._app.open_url(url)

    def download_update(self):
        return self._app.download_update()

    def start_quest(self):
        return self._app.start_quest()

    def stop_quest(self):
        return self._app.stop_quest()

    def set_stop_after(self, enabled):
        return self._app.set_stop_after(enabled)


# ============================================================
# 主窗口控制器
# ============================================================
class ConfigPanelApp:
    SKILL_CANON = ["左上技能", "右上技能", "左下技能", "右下技能", "防御"]
    TARGET_CANON = ["左上角色", "中上角色", "右上角色", "左下角色",
                    "右下角色", "中下角色", "不可用"]
    SKILL_LEVELS = [1, 2, 3, 4, 5, 6, 7]
    LANGUAGES = [("zh_CN", "简体中文"), ("en_US", "English")]
    CUSTOM_STRATEGY = "自定义任务点策略"
    FULL_AUTO = "全自动战斗"
    CONFIG_KEYS = {row[1] for row in CONFIG_VAR_LIST}
    # 任务运行期间由脚本线程直接写入配置文件的字段:
    # GUI 保存其他设置时不能用旧的内存值覆盖它们.
    _RUNTIME_OWNED_KEYS = ("KARMA_ADJUST_REMAINING", "KARMA_MAINTAIN")

    def __init__(self, version, msg_queue):
        # 与上次运行的版本不同, 说明刚刚更新过, 这时才需要清理 MOTW.
        # 这里直接读原始配置, 以便在加载 CLR 之前就知道是否发生过版本更新.
        try:
            last_version = (LoadRawConfigFromFile() or {}).get(
                "GENERAL", {}).get("LAST_VERSION")
        except Exception:
            last_version = None
        version_changed = last_version != version

        # 版本真正变过 (刚更新过) 时才需要展示更新说明;
        # MOTW 清理也复用同一个判断, 与弹窗在同一时间点触发.
        # 下载通知 (发现新版本可下载) 不会走到这里, 也不会触发清理.
        self._changelog_text = _load_changelog() if version_changed else ""

        # 先确认 .NET / WebView2 可用, 否则 create_window 会直接让进程崩溃.
        try:
            self._preflight = PreflightCheck(version_changed=version_changed)
        except Exception:
            # 检查本身出错时不应阻止程序启动.
            logger.exception("启动前环境检查出错, 已跳过")
            self._preflight = {"ok": True, "warnings": [],
                               "window_size": (1158, 820)}
        if not self._preflight["ok"]:
            ShowPreflightErrorAndExit(self._preflight)
        for warning in self._preflight["warnings"]:
            logger.warning(warning)

        self.URL = "https://github.com/arnold2957/wvd"
        self.version = version
        self.TITLE = _("wvdas v%s") % version
        self.INTRODUCTION = _("遇到问题? 请访问:\n%s \n或加入Q群: 922497356.") % self.URL

        self.msg_queue = msg_queue

        self._lock = threading.RLock()
        self._events = queue.Queue()
        self._closing = False
        self._log_handler_id = None
        self._summary_handler_id = None
        self._summary_text = ""
        self._window = None
        self._maximized = False
        self._compact = False
        self._compact_saved_size = None
        self._compact_was_maximized = False
        self._download_cb = None
        self._quest_active = False
        self._run_started = None
        self._latest_version = ""
        self._latest_notes = ""

        self.values = {}
        self._load_values()
        self._install_log_sinks()

        # 记录本次运行版本, 避免旧版 LAST_VERSION 一直残留.
        if self.values.get("LAST_VERSION") != version:
            self.values["LAST_VERSION"] = version
            try:
                self._save_internal()
            except Exception:
                pass

        html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        window_width, window_height = self._preflight["window_size"]
        self._window = webview.create_window(
            self.TITLE,
            html=html,
            js_api=WebBridge(self),
            width=window_width,
            height=window_height,
            min_size=(min(700, window_width), 160),
            resizable=True,
            frameless=True,
            easy_drag=True,
            hidden=True,
            background_color="#ffffff",
        )
        self._window.events.closed += self._on_window_closed
        # 页面加载完成后再显示窗口, 避免先出现约 0.4 秒的空白窗口.
        self._window.events.loaded += lambda: self._window.show()

        logger.info("**********************************")
        logger.info(_("当前版本: %s") % version)
        logger.info(_("当前游戏语言: {0}").format(LANGUAGE_GAME))
        logger.info(self.INTRODUCTION, summary=True)
        logger.info("**********************************")

    # ------------------------------------------------------------------
    # 运行
    # ------------------------------------------------------------------
    def run(self):
        # 只允许标题栏作为拖拽区域, 避免在输入框/按钮上拖动窗口.
        webview.settings["DRAG_REGION_DIRECT_TARGET_ONLY"] = True
        # 使用临时 profile: 启动速度与持久 profile 基本一致, 但关闭时不会
        # 长时间等待 WebView2 把用户数据刷回磁盘.
        try:
            webview.start(debug=False)
        except Exception:
            # 启动前检查通过, 但界面引擎仍可能初始化失败 (例如 WebView2 文件损坏).
            logger.exception("界面引擎启动失败")
            _native_message(
                "wvdas 启动失败",
                "界面引擎（pywebview / WebView2）启动失败。\n\n"
                "请查看 logs\\preflight_error.log 或 logs\\ 目录中最新的日志文件。\n"
                "也可以尝试重新安装 Microsoft Edge WebView2 Runtime。\n\n"
                f"下载地址：{WEBVIEW2_DOWNLOAD_URL}",
                0x10 | 0x40000,  # MB_ICONERROR | MB_TOPMOST
            )
            HardExit(1)

    def shutdown(self):
        if self._closing:
            return
        self._closing = True
        try:
            self.save_config()
        except Exception:
            pass
        self._remove_log_sinks()

    def _on_window_closed(self):
        # 原生关闭(Alt+F4等): 保存配置后立刻结束进程.
        self.shutdown()
        _kill_webview_children()
        HardExit(0)

    def close_window(self):
        # 保存配置后直接结束进程: 不等待 WebView2 / Chromium 的异步清理.
        self.shutdown()
        _kill_webview_children()
        HardExit(0)

    def minimize_window(self):
        try:
            self._window.minimize()
        except Exception:
            pass
        return {"ok": True}

    def set_compact(self, enabled, height=None):
        if enabled:
            if not self._compact:
                self._compact_saved_size = (self._window.width, self._window.height)
                self._compact_was_maximized = self._maximized
                self._compact = True
                if self._compact_was_maximized:
                    self._window.restore()
                    self._maximized = False
            self._window.resize(711, max(160, int(height or 180)))
        elif self._compact:
            width, height = self._compact_saved_size
            self._window.resize(width, height)
            if self._compact_was_maximized:
                self._window.maximize()
                self._maximized = True
            self._compact = False
        return {"ok": True}

    def toggle_maximize(self):
        try:
            if self._maximized:
                self._window.restore()
                self._maximized = False
            else:
                self._window.maximize()
                self._maximized = True
        except Exception:
            pass
        return {"ok": True, "maximized": self._maximized}

    # ------------------------------------------------------------------
    # 配置
    # ------------------------------------------------------------------
    def _load_values(self):
        config_dict = LoadConfig()
        self.values = {}
        for category, attr_name, var_type, default_value in CONFIG_VAR_LIST:
            if attr_name in config_dict and config_dict[attr_name] is not None:
                value = config_dict[attr_name]
            else:
                value = default_value
            self.values[attr_name] = self._coerce(var_type, value, default_value)

        # 配置里保存的是显示文本; 语言切换后用任务 ID 反查当前语言的显示名.
        target_id = self.values.get("FARM_TARGET")
        if target_id:
            for items in DUNGEON_TARGETS.values():
                matched = next((text for text, qid in items.items() if qid == target_id), None)
                if matched:
                    self.values["FARM_TARGET_TEXT"] = matched
                    break

        self.values["TASK_POINT_STRATEGY"] = self._normalize_task_point_strategy(
            self.values.get("TASK_POINT_STRATEGY"))
        self.values["STRATEGY"] = self.values.get("STRATEGY") or []
        if not isinstance(self.values["STRATEGY"], list):
            self.values["STRATEGY"] = []

    @staticmethod
    def _coerce(var_type, value, default):
        if _is_bool_var(var_type):
            return _to_bool(value)
        if _is_int_var(var_type):
            return _to_int(value, _to_int(default, 0))
        if var_type is list:
            return copy.deepcopy(value if isinstance(value, list) else default)
        if var_type is dict:
            return copy.deepcopy(value if isinstance(value, dict) else default)
        if value is None:
            return None
        return str(value) if not isinstance(value, str) else value

    @classmethod
    def _normalize_task_point_strategy(cls, value):
        if not isinstance(value, dict):
            return {"overall_strategy": _(cls.FULL_AUTO), "task_point": {}}
        result = dict(value)
        result.setdefault("overall_strategy", _(cls.FULL_AUTO))
        if not isinstance(result.get("task_point"), dict):
            result["task_point"] = {}
        return result

    def _coerce_key(self, key, value):
        for category, attr_name, var_type, default_value in CONFIG_VAR_LIST:
            if attr_name == key:
                return self._coerce(var_type, value, default_value)
        return value

    def save(self, patch):
        with self._lock:
            for key, value in patch.items():
                if key not in self.CONFIG_KEYS:
                    continue
                if key == "TASK_SPECIFIC_CONFIG":
                    continue
                self.values[key] = self._coerce_key(key, value)
            self._normalize_values()
            self._save_internal(changed_keys=tuple(patch.keys()))
        return self._snapshot_with_ok()

    def save_config(self):
        with self._lock:
            self._normalize_values()
            self._save_internal()

    def _normalize_values(self):
        # KARMA_ADJUST_REMAINING: 正值补 '+'; 空值视作 +0.
        karma = self.values.get("KARMA_ADJUST_REMAINING")
        karma = "" if karma is None else str(karma).strip()
        if karma in ("", "0"):
            karma = "+0"
        elif karma.isdigit():
            karma = "+" + karma
        self.values["KARMA_ADJUST_REMAINING"] = karma

        # ADB 地址: 只填端口 / 逗号分隔多个端口时自动补全.
        adb = "" if self.values.get("ADB_ADRESS") is None else str(self.values["ADB_ADRESS"]).strip()
        if adb.isdigit():
            adb = "127.0.0.1:%s" % adb
        elif "," in adb:
            ports = [_to_int(p.strip(), 0) for p in adb.split(",") if p.strip().isdigit()]
            if ports:
                adb = "127.0.0.1:%s" % max(ports)
        self.values["ADB_ADRESS"] = adb

        emu_path = self.values.get("EMU_PATH") or ""
        self.values["EMU_PATH"] = str(emu_path).replace("HD-Adb.exe", "HD-Player.exe")

        self.values["EMU_INDEX"] = max(0, _to_int(self.values.get("EMU_INDEX"), 0))
        self.values["REST_INTERVEL"] = max(0, _to_int(self.values.get("REST_INTERVEL"), 1))
        self.values["RE_ASSEMBLE_PARTY_INTERVAL"] = max(
            1, min(12, _to_int(self.values.get("RE_ASSEMBLE_PARTY_INTERVAL"), 6)))
        self.values["MAXIMUM_TIME_INTERVALS_BETWEEN_RESTARTING_EMU"] = max(
            1, min(12, _to_int(
                self.values.get("MAXIMUM_TIME_INTERVALS_BETWEEN_RESTARTING_EMU"), 6)))
        self.values["MAX_TRY_LIMIT"] = max(25, _to_int(self.values.get("MAX_TRY_LIMIT"), 25))
        self.values["MAX_CRASH_LIMIT"] = max(10, _to_int(self.values.get("MAX_CRASH_LIMIT"), 10))
        self.values["STARTUP_WAIT_TIME"] = max(
            1, min(120, _to_int(self.values.get("STARTUP_WAIT_TIME"), 10)))

        # 显示文本 -> 任务 ID. 找不到时保持 None, 与旧界面一致.
        target_text = self.values.get("FARM_TARGET_TEXT") or ""
        self.values["FARM_TARGET_TEXT"] = target_text
        farm_target = None
        for items in DUNGEON_TARGETS.values():
            if target_text in items:
                farm_target = items[target_text]
                break
        self.values["FARM_TARGET"] = farm_target

    def _save_internal(self, changed_keys=()):
        existing_config = LoadRawConfigFromFile() or {}
        # 脚本运行时会直接写入 config.json 的字段, GUI 内存中的副本可能过期.
        # 未在本次操作中显式修改时, 以磁盘上的最新值为准, 避免覆盖脚本的写入.
        disk_general = existing_config.get("GENERAL") or {}
        for key in self._RUNTIME_OWNED_KEYS:
            if key in changed_keys:
                continue
            if key in disk_general:
                self.values[key] = disk_general[key]

        other_task_spec_config = {
            k: v for k, v in existing_config.items()
            if k not in ["GENERAL"] and isinstance(v, dict)
        }

        new_general = {}
        other_items = {}
        for category, attr_name, var_type, default_value in CONFIG_VAR_LIST:
            value = copy.deepcopy(self.values.get(attr_name, default_value))
            if category == "GENERAL":
                new_general[attr_name] = value
            else:
                other_items[attr_name] = value

        new_config = {"GENERAL": new_general}
        new_config.update(other_task_spec_config)

        task_specific = bool(new_general.get("TASK_SPECIFIC_CONFIG", False))
        farm_target = new_general.get("FARM_TARGET")
        if task_specific and farm_target:
            new_config[farm_target] = other_items
        else:
            new_config["DEFAULT"] = other_items

        SaveConfigToFile(new_config)

    def set_language(self, kind, value):
        if value not in ("zh_CN", "en_US"):
            return {"ok": False, "error": "unsupported language"}
        with self._lock:
            key = "LANGUAGE_SCRIPT" if kind in ("script", "gui") else "LANGUAGE_GAME"
            self.values[key] = value
            self._save_internal()
        message = (_("GUI语言设置已保存，请重启脚本后生效。")
                   if key == "LANGUAGE_SCRIPT" else
                   _("游戏语言设置已保存。\n请确保模拟器内的游戏语言与此设置一致，建议重启脚本以加载对应的识别库。"))
        return self._snapshot_with_ok(message=message)

    def choose_emu_path(self):
        try:
            result = self._window.create_file_dialog(
                webview.FileDialog.OPEN,
                allow_multiple=False,
                file_types=("可执行文件 (*.exe)", "所有文件 (*.*)"),
            )
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        if not result:
            return {"ok": True, "cancelled": True}

        path = result[0] if isinstance(result, (list, tuple)) else result
        with self._lock:
            self.values["EMU_PATH"] = str(path)
            self._normalize_values()
            self._save_internal()

        warning = None
        normal = str(path).replace("\\", "/")
        valid_suffixes = (
            "nx_device/12.0/shell/MuMuNxDevice.exe",
            "nx_device/15.0/shell/MuMuNxDevice.exe",
            "MuMu Player 12/shell/MuMuPlayer.exe",
        )
        if not any(normal.endswith(s) for s in valid_suffixes):
            warning = _("设置的模拟器路径可能不正确。\n如果你遇到无法启动模拟器，请尝试重新设置路径。")
        return self._snapshot_with_ok(warning=warning)

    # ------------------------------------------------------------------
    # 快照
    # ------------------------------------------------------------------
    def _snapshot_with_ok(self, **extra):
        snap = self._snapshot()
        snap["ok"] = True
        snap.update(extra)
        return snap

    def _snapshot(self):
        with self._lock:
            values = copy.deepcopy(self.values)
            target_text = values.get("FARM_TARGET_TEXT") or ""
            return {
                "version": self.version,
                "url": self.URL,
                "values": values,
                "targetText": target_text,
                "targetId": values.get("FARM_TARGET"),
                "category": self._find_category(target_text),
                "taskSpecific": bool(values.get("TASK_SPECIFIC_CONFIG")),
                "taskPoints": self._task_points_state(values),
                "plans": self._plans_for_js(values.get("STRATEGY") or []),
                "options": self._options(),
                "daily": self._daily_state(values),
                "update": {"latest": self._latest_version, "notes": self._latest_notes}
                          if self._latest_version else None,
                "running": self._quest_active,
                "startedAt": self._run_started.timestamp() if self._run_started else None,
                "stopAfter": StopAfterRunEvent.is_set(),
            }

    def bootstrap(self):
        with self._lock:
            snap = self._snapshot()
            snap["categories"] = [
                {"name": cat, "targets": [{"text": text, "id": qid}
                                          for text, qid in items.items()]}
                for cat, items in DUNGEON_TARGETS.items()
            ]
            snap["languages"] = [{"value": v, "label": label} for v, label in self.LANGUAGES]
            snap["autoGroupName"] = _(self.FULL_AUTO)
            snap["customStrategy"] = _(self.CUSTOM_STRATEGY)
            snap["canonSkills"] = [_(c) for c in self.SKILL_CANON]
            snap["canonTargets"] = [_(c) for c in self.TARGET_CANON]
            snap["levels"] = list(self.SKILL_LEVELS)
            # 仅在启动时的 bootstrap 里带一次, 用于版本更新说明弹窗.
            snap["changelog"] = self._changelog_text
            snap["ok"] = True
            return snap

    @staticmethod
    def _find_category(target_text):
        if not target_text:
            return ""
        for category, items in DUNGEON_TARGETS.items():
            if target_text in items:
                return category
        return ""

    def _options(self):
        return {
            "roles": list(CHAR_DISPLAY_TO_ID.keys()),
            "skills": [_(_c) for _c in self.SKILL_CANON],
            "targets": [_(_c) for _c in self.TARGET_CANON],
            "levels": list(self.SKILL_LEVELS),
            "lockSkills": [_("防御"), _("双击自动")],
        }

    # ------------------------------------------------------------------
    # 战斗方案
    # ------------------------------------------------------------------
    @classmethod
    def _normalize_group_name(cls, name):
        if name in (cls.FULL_AUTO, _(cls.FULL_AUTO)):
            return _(cls.FULL_AUTO)
        return name or _(cls.FULL_AUTO)

    def _plans_for_js(self, plans):
        result = []
        for plan in plans:
            if not isinstance(plan, dict):
                continue
            settings = []
            for setting in plan.get("skill_settings", []) or []:
                if not isinstance(setting, dict):
                    continue
                role = setting.get("role_var", "")
                if role in CHAR_LIST:
                    role = _(role)
                elif role not in CHAR_DISPLAY_TO_ID:
                    role = next(iter(CHAR_DISPLAY_TO_ID), "")

                skill = setting.get("skill_var", self.SKILL_CANON[0])
                target = setting.get("target_var", self.TARGET_CANON[-1])

                settings.append({
                    "role_var": role,
                    "skill_var": _display_of(skill, self.SKILL_CANON),
                    "target_var": _display_of(target, self.TARGET_CANON),
                    "freq_var": setting.get("freq_var", ""),
                    "skill_lvl": _to_int(setting.get("skill_lvl"), 1),
                })
            result.append({
                "group_name": self._normalize_group_name(plan.get("group_name")),
                "need_reload_when_dungeon_begins": bool(
                    plan.get("need_reload_when_dungeon_begins", False)),
                "need_reload_when_combat_begins": bool(
                    plan.get("need_reload_when_combat_begins", False)),
                "complete_one_as_all": bool(plan.get("complete_one_as_all", False)),
                "skill_settings": settings,
            })
        return result

    def _plans_to_store(self, plans):
        stored = []
        for plan in plans:
            if not isinstance(plan, dict):
                continue
            settings = []
            for setting in plan.get("skill_settings", []) or []:
                if not isinstance(setting, dict):
                    continue
                role = setting.get("role_var", "")
                role = CHAR_DISPLAY_TO_ID.get(role, role)
                settings.append({
                    "role_var": role,
                    "skill_var": _canonical_of(setting.get("skill_var", ""), self.SKILL_CANON),
                    "target_var": _canonical_of(setting.get("target_var", ""), self.TARGET_CANON),
                    "freq_var": setting.get("freq_var", ""),
                    "skill_lvl": _to_int(setting.get("skill_lvl"), 1),
                })
            stored.append({
                "group_name": self._normalize_group_name(plan.get("group_name")),
                "need_reload_when_dungeon_begins": _to_bool(
                    plan.get("need_reload_when_dungeon_begins", False)),
                "need_reload_when_combat_begins": _to_bool(
                    plan.get("need_reload_when_combat_begins", False)),
                "complete_one_as_all": _to_bool(plan.get("complete_one_as_all", False)),
                "skill_settings": settings,
            })
        return stored

    def save_plans(self, plans):
        if not isinstance(plans, list):
            return {"ok": False, "error": "invalid plans"}

        names = [self._normalize_group_name(p.get("group_name")) for p in plans
                 if isinstance(p, dict)]
        duplicates = [name for name in names if names.count(name) > 1]
        if duplicates:
            return {"ok": False,
                    "error": _("名称 '%s' 已存在，请使用其他名称") % duplicates[0]}

        with self._lock:
            self.values["STRATEGY"] = self._plans_to_store(plans)
            self._save_internal()
        return self._snapshot_with_ok()

    # ------------------------------------------------------------------
    # 任务点 / 战斗策略
    # ------------------------------------------------------------------
    def _strategy_names(self, values=None):
        values = values or self.values
        return [self._normalize_group_name(p.get("group_name"))
                for p in values.get("STRATEGY", []) if isinstance(p, dict)]

    def _task_points_state(self, values):
        target_id = values.get("FARM_TARGET")
        quest = None
        if target_id:
            try:
                quest = LoadQuest(target_id)
            except Exception:
                quest = None

        is_dungeon = bool(quest and getattr(quest, "_TYPE", None) == "dungeon")
        strategies = self._strategy_names(values)
        custom_label = _(self.CUSTOM_STRATEGY)
        full_auto_label = _(self.FULL_AUTO)

        tps = self._normalize_task_point_strategy(values.get("TASK_POINT_STRATEGY"))
        if values.get("TASK_SPECIFIC_CONFIG"):
            overall = tps.get("overall_strategy") or full_auto_label
        else:
            overall = values.get("DEFAULT_OVERALL_STRATEGY") or full_auto_label

        if is_dungeon:
            overall_values = (strategies + [custom_label]) if strategies else [custom_label]
        else:
            overall_values = strategies if strategies else [full_auto_label]
        if overall not in overall_values:
            overall = full_auto_label if full_auto_label in overall_values else overall_values[0]

        points = []
        if is_dungeon and quest and getattr(quest, "_TARGETINFOLIST", None):
            saved_points = tps.get("task_point", {})
            if not isinstance(saved_points, dict):
                saved_points = {}
            for idx, point in enumerate(quest._TARGETINFOLIST):
                label = "%s · %s" % (idx + 1, point.target)
                if point.target == "position":
                    label += " " + str(point.roi)
                saved = saved_points.get(str(idx))
                if saved is None:
                    saved = saved_points.get(idx)
                if saved not in strategies:
                    saved = full_auto_label if full_auto_label in strategies else (
                        strategies[0] if strategies else full_auto_label)
                points.append({"index": idx, "label": label, "strategy": saved})

        return {
            "isDungeon": is_dungeon,
            "points": points,
            "strategies": strategies,
            "overall": overall,
            "overallValues": overall_values,
            "customMode": overall == custom_label,
            "customLabel": custom_label,
            "fullAutoLabel": full_auto_label,
        }

    def _save_task_point_strategy(self):
        tps = self._normalize_task_point_strategy(self.values.get("TASK_POINT_STRATEGY"))
        self.values["TASK_POINT_STRATEGY"] = tps
        if not self.values.get("TASK_SPECIFIC_CONFIG"):
            self.values["DEFAULT_OVERALL_STRATEGY"] = tps.get(
                "overall_strategy", _(self.FULL_AUTO))
        self._save_internal()

    def set_overall_strategy(self, value, enable_custom=False):
        with self._lock:
            if value == _(self.CUSTOM_STRATEGY) and not self.values.get("TASK_SPECIFIC_CONFIG"):
                if not enable_custom:
                    return {"ok": False, "cancelled": True}
                self._save_internal()
                self._switch_task_specific(True, save_at_end=False)

            tps = self._normalize_task_point_strategy(self.values.get("TASK_POINT_STRATEGY"))
            tps["overall_strategy"] = value
            self.values["TASK_POINT_STRATEGY"] = tps
            self._save_task_point_strategy()
        return self._snapshot_with_ok()

    def set_task_point_strategy(self, index, value):
        with self._lock:
            tps = self._normalize_task_point_strategy(self.values.get("TASK_POINT_STRATEGY"))
            tps.setdefault("task_point", {})[str(index)] = value
            self.values["TASK_POINT_STRATEGY"] = tps
            self._save_task_point_strategy()
        return self._snapshot_with_ok()

    # ------------------------------------------------------------------
    # 任务定制配置
    # ------------------------------------------------------------------
    def set_task_specific(self, enabled):
        with self._lock:
            self._save_internal()
            self._switch_task_specific(bool(enabled))
        return self._snapshot_with_ok()

    def _switch_task_specific(self, enabled, save_at_end=True):
        """切换默认 / 任务专用配置, 并把对应值载入当前界面状态."""
        self._save_internal()

        if enabled:
            task_config = LoadConfig("specific")
        else:
            task_config = LoadConfig("default")

        for category, attr_name, var_type, default_value in CONFIG_VAR_LIST:
            if attr_name not in task_config:
                continue
            self.values[attr_name] = self._coerce(
                var_type, task_config[attr_name], default_value)

        specific_config = LoadConfig("specific")
        if specific_config.get("TASK_POINT_STRATEGY") is not None:
            self.values["TASK_POINT_STRATEGY"] = self._normalize_task_point_strategy(
                specific_config["TASK_POINT_STRATEGY"])
        else:
            self.values["TASK_POINT_STRATEGY"] = {
                "overall_strategy": _(self.FULL_AUTO), "task_point": {}}

        tps = self._normalize_task_point_strategy(self.values.get("TASK_POINT_STRATEGY"))
        if tps.get("overall_strategy") == self.FULL_AUTO:
            tps["overall_strategy"] = _(self.FULL_AUTO)
        self.values["TASK_POINT_STRATEGY"] = tps

        self.values["TASK_SPECIFIC_CONFIG"] = bool(enabled)
        self._normalize_values()
        if save_at_end:
            self._save_internal()

    def clear_task_specific(self):
        with self._lock:
            self._switch_task_specific(False)

            raw_config = LoadRawConfigFromFile() or {}
            general_config = raw_config.get("GENERAL", {})
            farm_target = general_config.get("FARM_TARGET")
            if farm_target and farm_target in raw_config:
                logger.info(_("删除任务定制的配置文件, 任务为 %s.") % farm_target)
                del raw_config[farm_target]
                SaveConfigToFile(raw_config)
        return self._snapshot_with_ok()

    def select_target(self, text):
        text = "" if text is None else str(text)
        with self._lock:
            self.values["FARM_TARGET_TEXT"] = text
            self._normalize_values()
            self._save_internal()
            # 选择新任务时, 与旧界面一致: 关闭任务专用配置并载入默认配置.
            self._switch_task_specific(False)
            tip = None
            target_id = self.values.get("FARM_TARGET")
            if target_id:
                try:
                    quest = LoadQuest(target_id)
                    tip = getattr(quest, "_TIPS", None) if quest else None
                except Exception:
                    tip = None
            if tip:
                logger.info("\n\n########### TIPS #############\n\n%s\n\n##############################"
                            % tip)
        snap = self._snapshot_with_ok()
        snap["tip"] = tip
        return snap

    # ------------------------------------------------------------------
    # 日常 / 周常
    # ------------------------------------------------------------------
    DATE_FORMAT = "%Y-%m-%d"

    def _is_same_week(self, date_str):
        try:
            input_date = datetime.strptime(date_str, self.DATE_FORMAT).date()
        except (ValueError, TypeError):
            return False
        current_date = datetime.now().date()
        iy, iw, _ = input_date.isocalendar()
        cy, cw, _ = current_date.isocalendar()
        return iy == cy and iw == cw

    def _is_same_fortnight(self, date_str):
        first_double_saturday = date(1970, 1, 11)
        try:
            input_date = datetime.strptime(date_str, self.DATE_FORMAT).date()
        except (ValueError, TypeError):
            return False
        current_date = datetime.now().date()
        input_period = (input_date - first_double_saturday).days // 14
        current_period = (current_date - first_double_saturday).days // 14
        return input_period == current_period

    def _daily_state(self, values):
        last_new = values.get("WEBSITE_ORG_TIME") or ""
        new_done = bool(last_new) and self._is_same_week(last_new)
        last_old = values.get("WEBSITE_ORG_TIME_OLD") or ""
        old_done = bool(last_old) and self._is_same_week(last_old)
        all_done = new_done and old_done

        last_am = values.get("AM_REFRESH_TIME") or ""
        am_done = bool(last_am) and self._is_same_fortnight(last_am)
        return {
            # 新/旧官网分开记录, 点击一个只会消除对应的提醒.
            "gemNewDone": new_done,
            "gemOldDone": old_done,
            "gemDone": all_done,
            "gemStatus": _("本周已领取") if all_done else _("本周待领取"),
            "gemTone": "green" if all_done else "amber",
            "gemRecord": last_new or "—",
            "gemRecordNew": last_new or "—",
            "gemRecordOld": last_old or "—",
            "gemDesc": (_("本周宝石已领取 · 点击可再次打开官网") if all_done
                        else _("本周 50 钻待领取 · 点击直接打开官网")),
            "amDone": am_done,
            "amStatus": _("本期已切换") if am_done else _("本期待切换"),
            "amTone": "green" if am_done else "amber",
            "amRecord": last_am or "—",
        }

    def claim_gem(self, url):
        if url:
            webbrowser.open(str(url))
        url_text = str(url or "")
        if "webstore.wizardry.info" in url_text:
            key = "WEBSITE_ORG_TIME"
        elif "store.wizardry.info" in url_text:
            key = "WEBSITE_ORG_TIME_OLD"
        else:
            key = "WEBSITE_ORG_TIME"
        with self._lock:
            self.values[key] = datetime.now().strftime(self.DATE_FORMAT)
            self._save_internal()
        return self._snapshot_with_ok()

    def switch_monthly(self):
        found_text = None
        for category, items in DUNGEON_TARGETS.items():
            for text, target_id in items.items():
                if target_id == "LMG-GT":
                    found_text = text
                    break
            if found_text:
                break
        if not found_text:
            found_text = "[骨头]炉壶灵庙(王都出发)"

        with self._lock:
            self.values["AM_REFRESH_TIME"] = datetime.now().strftime(self.DATE_FORMAT)
            self._save_internal()

        snap = self.select_target(found_text)
        snap["message"] = _("已切换到月常任务：%s") % found_text
        return snap

    # ------------------------------------------------------------------
    # 其他
    # ------------------------------------------------------------------
    def open_url(self, url):
        if not url:
            return {"ok": False, "error": "empty url"}
        webbrowser.open(str(url))
        return {"ok": True}

    def download_update(self):
        if self._download_cb is None:
            return {"ok": False, "error": _("没有可用的更新")}
        threading.Thread(target=self._download_cb, daemon=True).start()
        return {"ok": True}

    # ------------------------------------------------------------------
    # 任务运行
    # ------------------------------------------------------------------
    def start_quest(self):
        with self._lock:
            if self._quest_active:
                return {"ok": True, "running": True,
                        "startedAt": self._run_started.timestamp() if self._run_started else None}
            self._normalize_values()
            self._save_internal()

        setting = LoadSettingFromDict(LoadConfig())
        setting._FINISHINGCALLBACK = self.finishingcallback
        self.msg_queue.put(('start_quest', setting))

        with self._lock:
            self._quest_active = True
            self._run_started = datetime.now()
            started_at = self._run_started.timestamp()
        logger.info(_("启动任务\"%s\"...") % (getattr(setting, "FARM_TARGET_TEXT", "") or ""))
        return {"ok": True, "running": True, "startedAt": started_at}

    def stop_quest(self):
        self.msg_queue.put(('stop_quest', None))
        return {"ok": True}

    def set_stop_after(self, enabled):
        if enabled:
            StopAfterRunEvent.set()
        else:
            StopAfterRunEvent.clear()
        return {"ok": True, "armed": bool(enabled)}

    def finishingcallback(self):
        """由任务线程调用, 因此只能推事件, 不能直接操作界面."""
        logger.info(_("已停止."))
        config = LoadConfig()
        StopAfterRunEvent.clear()
        with self._lock:
            self._quest_active = False
            self._run_started = None
            if 'KARMA_ADJUST_REMAINING' in config:
                self.values['KARMA_ADJUST_REMAINING'] = config['KARMA_ADJUST_REMAINING']
            if 'KARMA_MAINTAIN' in config:
                self.values['KARMA_MAINTAIN'] = _to_bool(config['KARMA_MAINTAIN'])
        self.push_event({"type": "run_finished", "state": self._snapshot()})

    # ------------------------------------------------------------------
    # 后台事件 / 日志
    # ------------------------------------------------------------------
    def push_event(self, event):
        if not self._closing:
            self._events.put(event)

    def poll(self):
        events = []
        for underscore in range(200):
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                break
        return events

    def _install_log_sinks(self):
        def log_sink(message):
            if self._closing:
                return
            record = message.record
            self.push_event({
                "type": "log",
                "time": record["time"].strftime("%H:%M:%S"),
                "level": record["level"].name,
                "message": record["message"].rstrip("\n"),
            })

        def summary_sink(message):
            if self._closing:
                return
            record = message.record
            self._summary_text = record["message"]
            summary_data = record["extra"].get("summary_data")
            if summary_data is not None:
                self.push_event({
                    "type": "summary",
                    "data": summary_data,
                    "events": record["extra"].get("summary_events") or {},
                })

        # 不使用 enqueue, 避免关闭窗口时 loguru 的工作线程卡住.
        self._log_handler_id = logger.add(log_sink, level="INFO", enqueue=False)
        self._summary_handler_id = logger.add(
            summary_sink, level="INFO", filter=summary_filter, enqueue=False)

    def _remove_log_sinks(self):
        for handler_id in (self._log_handler_id, self._summary_handler_id):
            if handler_id is None:
                continue
            try:
                logger.remove(handler_id)
            except Exception:
                pass
        self._log_handler_id = None
        self._summary_handler_id = None

    # ------------------------------------------------------------------
    # 控制器回调
    # ------------------------------------------------------------------
    def show_update_notice(self, version, download_cb=None, notes=""):
        if self._closing:
            return
        with self._lock:
            self.values["LATEST_VERSION"] = version
            self._latest_version = str(version)
            self._latest_notes = str(notes or "")
            self._download_cb = download_cb
            self._save_internal()
        self.push_event({
            "type": "update_available",
            "version": str(version),
            "current": self.version,
            "notes": self._latest_notes,
        })

    def turn_to_quest(self, target):
        if self._closing:
            return

        display_text = None
        for items in DUNGEON_TARGETS.values():
            for text, target_id in items.items():
                if target_id == target or str(target_id).lower() == str(target).lower():
                    display_text = text
                    break
            if display_text:
                break

        switch_notice = {
            "7000G": _("你的队伍已经耗尽了所有的再起之火.\n在耗尽再起之火前,\n你的队伍已经完成了如下了不起的壮举:\n\n%s\n\n不过没关系, 至少, 你还可以找公主要钱.\n\n赞美公主殿下!\n"),
            "fishing": _("你的队伍已经耗尽了所有的再起之火.\n在耗尽再起之火前,\n你的队伍已经完成了如下了不起的壮举:\n\n%s\n\n不过没关系, 至少, 你还可以去钓鱼.\n\n事已至此, 先钓鱼吧.\n"),
            "ffxi-org": _("你的队伍已经耗尽了所有的再起之火.\n在耗尽再起之火前,\n你的队伍已经完成了如下了不起的壮举:\n\n%s\n\n不过没关系, 至少, 你还可以去挖矿.\n\n只要能有全改, 管他什么方法呢.\n"),
        }
        template = switch_notice.get(str(target).lower()) or switch_notice.get(str(target))
        summary = (self._summary_text or "").strip()
        if not summary or self.INTRODUCTION in summary:
            summary = _("唔, 看起来一次成功的地下城都没有完成.")
        if template:
            logger.info(template % summary)

        self.push_event({
            "type": "task_switched",
            "text": display_text or self.values.get("FARM_TARGET_TEXT") or "",
            "target": target,
            "message": _("已切换到任务：%s") % (display_text or self.values.get("FARM_TARGET_TEXT") or ""),
        })
