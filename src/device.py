from pathlib import Path, PureWindowsPath
import os
import re
import subprocess
import time

from ppadb.client import Client as AdbClient

from utils import logger


PACKAGE_NAME = "jp.co.drecom.wizardry.daphne"


def device_path(value):
    text = str(value or "")
    if os.name == "nt":
        return Path(text)
    if "\\" in text or (len(text) >= 2 and text[1] == ":"):
        return PureWindowsPath(text)
    return Path(text)


def path_exists(path):
    return hasattr(path, "exists") and path.exists()


class Device:
    device_type = "physical"
    display_name = _("实体设备")
    can_restart_emulator = False
    visible_config_fields = ["adb_path", "adb_address"]
    address_label = _("ADB连接地址:")
    visible_path_rows = ["adb"]
    default_adb_address = ""
    default_adb_paths = []
    setup_display_after_connect = False
    display_size = "900x1600"
    display_density = "240"
    restore_display_on_stop = False
    close_game_on_stop = False

    def __init__(self, setting, runtime_context):
        self.setting = setting
        self.runtime_context = runtime_context

    @property
    def serial(self):
        return self.setting.ADB_ADRESS

    @property
    def adb_path(self):
        adb_path = getattr(self.setting, "ADB_PATH", None)
        if adb_path:
            return device_path(adb_path)
        default_path = self.first_existing_default_adb_path()
        if default_path:
            return default_path
        return Path("adb")

    @classmethod
    def iter_default_adb_paths(cls):
        for path in cls.default_adb_paths:
            yield path
        if os.name == "nt":
            yield str(Path.home() / "Documents" / "platform-tools" / "adb.exe")

    @classmethod
    def first_existing_default_adb_path(cls):
        for adb_path in cls.iter_default_adb_paths():
            path = device_path(adb_path)
            if path_exists(path):
                return path
        return None

    def _run_adb(self, *args, timeout=10):
        cmd = [str(self.adb_path), *[str(arg) for arg in args]]
        logger.debug(_("执行adb命令: {a}").format(a=" ".join(cmd)))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="ignore",
        )
        logger.debug(_("adb命令返回:{a}").format(a=result.stdout))
        if result.stderr:
            logger.debug(_("adb命令错误:{a}").format(a=result.stderr))
        if result.returncode != 0:
            logger.error(_("adb命令执行失败(exit={a}): {b}").format(a=result.returncode, b=result.stderr or result.stdout))
        return result

    def _adb_command_failed(self, result):
        return getattr(result, "returncode", 0) != 0

    def _adb_device_state(self, devices_output):
        for line in str(devices_output or "").splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0] == str(self.serial):
                return parts[1]
        return None

    def validate_adb_path(self):
        if str(self.adb_path) == "adb":
            return True
        if not path_exists(self.adb_path):
            logger.error(_("adb程序不存在: {a}").format(a=self.adb_path))
            return False
        return True

    def kill_adb(self):
        self._kill_processes([self.adb_path.name])

    def recover_adb(self):
        logger.info(_("正在检查并关闭adb..."))
        self.kill_adb()
        logger.info(_("已尝试终止adb"))

    def setup_display(self):
        logger.info(_("设置设备分辨率为{a}, DPI为{b}.").format(a=self.display_size, b=self.display_density))
        size_result = self._run_adb("-s", self.serial, "shell", "wm", "size", self.display_size)
        density_result = self._run_adb("-s", self.serial, "shell", "wm", "density", self.display_density)
        if size_result.returncode != 0 or density_result.returncode != 0:
            logger.error(
                _("设置设备分辨率或DPI失败: size={a}, density={b}").format(
                    a=size_result.stderr or size_result.stdout,
                    b=density_result.stderr or density_result.stdout,
                )
            )

    def restore_display(self):
        if not self.restore_display_on_stop:
            return True
        logger.info(_("恢复设备分辨率与DPI设置."))
        size_result = self._run_adb("-s", self.serial, "shell", "wm", "size", "reset")
        density_result = self._run_adb("-s", self.serial, "shell", "wm", "density", "reset")
        if size_result.returncode != 0 or density_result.returncode != 0:
            logger.error(
                _("恢复设备分辨率或DPI失败: size={a}, density={b}").format(
                    a=size_result.stderr or size_result.stdout,
                    b=density_result.stderr or density_result.stdout,
                )
            )
            return False
        return True

    def close_game(self, package_name=PACKAGE_NAME):
        if not getattr(self.setting, "_ADBDEVICE", None):
            logger.warning(_("ADB设备尚未连接，跳过关闭游戏."))
            return False
        logger.info(_("关闭游戏: {a}").format(a=package_name))
        self.shell(f"am force-stop {package_name}")
        return True

    def cleanup_after_stop(self):
        close_ok = True
        if self.close_game_on_stop:
            try:
                close_ok = self.close_game()
            except Exception as e:
                close_ok = False
                logger.error(_("关闭游戏时出错: {a}").format(a=e))
        display_ok = self.restore_display()
        return close_ok and display_ok

    def after_connect(self):
        if self.setup_display_after_connect:
            self.setup_display()

    def connect(self, force_restart_emu=False, force_restart_adb=False):
        if force_restart_emu:
            self.restart_target()
            time.sleep(1)
        if force_restart_adb:
            self.recover_adb()
            time.sleep(1)
        return self._connect_adb()

    def _connect_adb(self):
        if not self.validate_adb_path():
            return None

        max_retries = 20
        for attempt in range(max_retries):
            logger.info(_("-----------------------\n开始尝试连接adb. 次数:{a}/{b}...").format(a=attempt + 1, b=max_retries))
            if attempt == 3:
                logger.info(_("失败次数过多, 尝试关闭adb."))
                self.recover_adb()

            try:
                result = self._run_adb("devices")
                if self._adb_command_failed(result):
                    time.sleep(2)
                    continue
                state = self._adb_device_state(result.stdout)
                if ("daemon not running" in result.stderr) or state == "offline":
                    time.sleep(2)
                    result = self._run_adb("devices")
                    if self._adb_command_failed(result):
                        time.sleep(2)
                        continue
                    state = self._adb_device_state(result.stdout)
                    if ("daemon not running" in result.stderr) or state == "offline":
                        logger.info(_("adb服务未启动!\n启动adb服务..."))
                        self._run_adb("kill-server")
                        self._run_adb("start-server")
                        time.sleep(2)

                state = self._adb_device_state(result.stdout)
                if self._should_adb_connect() and state != "device":
                    logger.debug(_("尝试连接到adb..."))
                    connect_result = self._run_adb("connect", self.serial)
                    if self._adb_command_failed(connect_result):
                        time.sleep(2)
                        continue

                result = self._run_adb("devices")
                if self._adb_command_failed(result):
                    time.sleep(2)
                    continue
                state = self._adb_device_state(result.stdout)
                if state == "device":
                    logger.info(_("成功连接到设备: {a}").format(a=self.serial))
                    self.capture_running_pid()
                    device = self._create_ppadb_device()
                    if device:
                        self.after_connect()
                        return device
                if state == "offline":
                    logger.info(_("设备处于offline状态，尝试重启ADB服务: {a}").format(a=self.serial))
                    self.recover_adb()
                    time.sleep(2)
                    continue

                if isinstance(self, EmulatorDevice) and not self.is_running():
                    logger.info(_("模拟器未运行，尝试启动..."))
                    if self.start_emulator():
                        logger.info(_("模拟器(应该)启动完毕.\n 尝试连接到模拟器..."))
                        if self._should_adb_connect():
                            self._run_adb("connect", self.serial)
                        continue

                logger.info(_("连接失败: {a}").format(a=result.stderr.strip()))
                time.sleep(2)
                if isinstance(self, EmulatorDevice) and self.restart_on_connect_failure:
                    self.kill_emulator()
                    self.recover_adb()
                time.sleep(2)
            except Exception as e:
                logger.error(_("重启ADB服务时出错: {a}").format(a=e))
                time.sleep(2)
                if isinstance(self, EmulatorDevice) and self.restart_on_connect_failure:
                    self.kill_emulator()
                    self.recover_adb()
                time.sleep(2)
                return None

        logger.info(_("达到最大重试次数，连接失败"))
        return None

    def _should_adb_connect(self):
        return ":" in str(self.serial)

    def _create_ppadb_device(self):
        try:
            client = AdbClient(host="127.0.0.1", port=5037)
            for device in client.devices():
                if device.serial == str(self.serial):
                    logger.info(_("成功创建设备对象: {a}").format(a=device.serial))
                    self.setting._ADBDEVICE = device
                    return device
        except Exception as e:
            logger.error(_("创建ADB设备时出错: {a}").format(a=e))
        return None

    def capture_running_pid(self):
        pass

    def shell(self, cmd, timeout=5):
        if not getattr(self.setting, "_ADBDEVICE", None):
            raise RuntimeError(_("ADB设备尚未连接."))
        return self.setting._ADBDEVICE.shell(cmd, timeout=timeout)

    def screencap(self):
        serial = self.setting._ADBDEVICE.serial
        return subprocess.run(
            [str(self.adb_path), "-s", serial, "exec-out", "screencap"],
            capture_output=True,
            timeout=5,
        )

    def clear_logcat(self):
        result = self._run_adb("-s", self.serial, "shell", "logcat", "-b", "all", "-c")
        if self._adb_command_failed(result):
            logger.warning(_("清除全部logcat缓冲区失败，尝试清除默认缓冲区."))
            self._run_adb("-s", self.serial, "shell", "logcat", "-c")

    def find_graphics_api_crash_log(self):
        result = self._run_adb("-s", self.serial, "shell", "logcat", "-b", "all", "-d", timeout=10)
        if self._adb_command_failed(result):
            logger.warning(_("读取logcat失败，跳过图形API崩溃检测."))
            return ""
        matched_lines = [
            line
            for line in str(result.stdout or "").splitlines()
            if re.search(r"unable to initialize.*graphics api", line, re.IGNORECASE)
        ]
        return "\n".join(matched_lines[-20:])

    def restart_target(self):
        logger.info(_("当前设备类型不支持重启模拟器/设备, 将仅重启游戏."))
        return False

    def restart_game(self, package_name=PACKAGE_NAME):
        if not getattr(self.setting, "_ADBDEVICE", None):
            raise RuntimeError(_("ADB设备尚未连接."))
        self.clear_logcat()
        main_act = self.shell(f"cmd package resolve-activity --brief {package_name}").strip().split("\n")[-1]
        if not main_act or "/" not in main_act:
            logger.error(_("无法解析游戏启动Activity: {a}").format(a=main_act))
            return False
        self.shell(f"am force-stop {package_name}")
        logger.info(_("巫术, 启动!"))
        logger.debug(self.shell(f"am start -n {main_act}"))
        return True

    def _kill_processes(self, process_names):
        for name in process_names:
            if not name:
                continue
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/f", "/im", name],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                else:
                    subprocess.run(
                        ["pkill", "-f", name],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
            except Exception as e:
                logger.error(_("终止进程{a}时出错: {b}").format(a=name, b=e))


class EmulatorDevice(Device):
    can_restart_emulator = True
    visible_config_fields = ["emu_path", "adb_address"]
    address_label = _("ADB连接地址:")
    visible_path_rows = ["install", "emulator", "adb", "cleanup_processes"]
    process_names = []
    adb_process_names = []
    cleanup_process_names = []
    default_install_roots = []
    tracks_single_emulator_process = True
    restart_on_connect_failure = True

    @property
    def install_root(self):
        configured = getattr(self.setting, "EMU_PATH", None)
        if configured:
            return self.normalize_install_root(device_path(configured))
        default_root = self.first_existing_default_root()
        if default_root:
            return default_root
        if self.default_install_roots:
            return device_path(self.default_install_roots[0])
        return device_path("")

    def normalize_install_root(self, path):
        return path

    def first_existing_default_root(self):
        for root in self.default_install_roots:
            path = device_path(root)
            if path_exists(path):
                return path
        return None

    @property
    def emu_path(self):
        return self.install_root

    def validate_adb_path(self):
        if not str(self.install_root):
            logger.error(_("未设置模拟器路径."))
            return False
        return super().validate_adb_path()

    def start_emulator(self):
        raise NotImplementedError

    def detect_running_pids(self):
        if os.name != "nt":
            return []
        names = " ".join(self.process_names)
        if not names:
            return []
        result = subprocess.run(
            f'tasklist /FO CSV /NH | findstr "{names}"',
            shell=True,
            capture_output=True,
            text=True,
        )
        check_results = []
        for task in result.stdout.strip().split("\n"):
            if not task:
                continue
            parts = task.split("\",\"")
            if len(parts) >= 2:
                try:
                    check_results.append(int(parts[1]))
                except ValueError:
                    pass
        return check_results

    def is_running(self):
        pid = getattr(self.runtime_context, "_RUNNING_EMU_PID", None)
        pids = self.detect_running_pids()
        return bool(pid and pid in pids) or bool(pids)

    def capture_running_pid(self):
        if not self.tracks_single_emulator_process:
            logger.debug(_("当前设备类型不追踪单一模拟器进程: {a}").format(a=self.device_type))
            self.runtime_context._RUNNING_EMU_PID = None
            return

        pids = self.detect_running_pids()
        logger.debug("{a}".format(a=pids))
        if len(pids) == 1:
            self.runtime_context._RUNNING_EMU_PID = int(pids[0])
            logger.info(_("模拟器进程号为{a}.").format(a=self.runtime_context._RUNNING_EMU_PID))
        elif len(pids) > 1:
            logger.info(_("\n\n***********\n有多个模拟器已经启动, 无法识别进程号. 当需要重启模拟器的时候, 会重启所有模拟器.\n为了避免此问题, 请关闭目标模拟器, 并使用本脚本自动启动模拟器.\n\n"))

    def kill_adb(self):
        self._kill_processes(self.adb_process_names or [self.adb_path.name])

    def kill_emulator(self):
        emulator_name = self.emu_path.name if self.emu_path.name else None
        try:
            logger.info(_("正在检查并关闭已运行的模拟器实例{a}...").format(a=emulator_name or self.display_name))
            pid = getattr(self.runtime_context, "_RUNNING_EMU_PID", None)
            if os.name == "nt" and pid:
                logger.info(_("使用已知进程号{a}关闭模拟器...").format(a=pid))
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                time.sleep(1)
            else:
                names = list(self.process_names)
                if emulator_name and emulator_name not in names:
                    names.append(emulator_name)
                self._kill_processes(names)
                time.sleep(1)
            self._kill_processes(self.cleanup_process_names)
            logger.info(_("已尝试终止模拟器进程: {a}").format(a=emulator_name or self.display_name))
        except Exception as e:
            logger.error(_("终止模拟器进程时出错: {a}").format(a=str(e)))
        finally:
            self.runtime_context._RUNNING_EMU_PID = None

    def restart_target(self):
        self.kill_emulator()
        time.sleep(1)
        self.start_emulator()
        return True


class MuMuEmulatorDevice(EmulatorDevice):
    device_type = "mumu"
    display_name = "MuMu"
    visible_config_fields = ["emu_path", "adb_address", "emu_index"]
    process_names = ["MuMuNxDevice.exe", "MuMuPlayer.exe"]
    adb_process_names = ["adb.exe"]
    cleanup_process_names = ["MuMuVMMSVC.exe", "MuMuVMMHeadless.exe"]
    default_install_roots = [
        r"C:\Program Files\Netease\MuMuPlayer",
        r"C:\Program Files (x86)\MuMuPlayer",
    ]

    @property
    def shell_dir(self):
        root = self.install_root
        if root.name.lower() == "shell":
            return root
        return root / "nx_device" / "12.0" / "shell"

    def normalize_install_root(self, path):
        if path.name.lower() in ["mumunxdevice.exe", "mumuplayer.exe", "adb.exe"]:
            path = path.parent
        if path.name.lower() == "shell":
            return path.parent.parent.parent
        return path

    @property
    def emu_path(self):
        shell_dir = self.shell_dir
        nx_device = shell_dir / "MuMuNxDevice.exe"
        if path_exists(nx_device):
            return nx_device
        return shell_dir / "MuMuPlayer.exe"

    @property
    def adb_path(self):
        return self.shell_dir / "adb.exe"

    def start_emulator(self):
        if not path_exists(self.emu_path):
            logger.error(_("模拟器启动程序不存在: {a}").format(a=self.emu_path))
            return False
        cmd = [str(self.emu_path), "control", "-v", str(self.setting.EMU_INDEX)]
        try:
            logger.info(_("启动模拟器: {a}").format(a=" ".join(cmd)))
            pre_pids = self.detect_running_pids()
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(self.shell_dir),
            )
            time.sleep(5)
            aft_pids = self.detect_running_pids()
            new_tasks = [pid for pid in aft_pids if pid not in pre_pids]
            if new_tasks:
                self.runtime_context._RUNNING_EMU_PID = int(new_tasks[0])
                logger.info(_("模拟器启动开始，进程号为{a}").format(a=self.runtime_context._RUNNING_EMU_PID))
        except Exception as e:
            logger.error(_("启动模拟器失败: {a}").format(a=str(e)))
            return False
        logger.info(_("等待模拟器启动..."))
        time.sleep(15)
        return True


class BlueStacksEmulatorDevice(EmulatorDevice):
    device_type = "bluestacks"
    display_name = "BlueStacks Legacy"
    process_names = ["HD-Player.exe"]
    adb_process_names = ["HD-Adb.exe"]
    default_install_roots = [
        r"C:\Program Files\BlueStacks_nxt",
        r"C:\Program Files\BlueStacks",
    ]

    def normalize_install_root(self, path):
        if path.name.lower() in ["hd-adb.exe", "hd-player.exe"]:
            return path.parent
        return path

    @property
    def emu_path(self):
        return self.install_root / "HD-Player.exe"

    @property
    def adb_path(self):
        return self.install_root / "HD-Adb.exe"

    def start_emulator(self):
        if not path_exists(self.emu_path):
            logger.error(_("模拟器启动程序不存在: {a}").format(a=self.emu_path))
            return False
        try:
            logger.info(_("启动模拟器: {a}").format(a=self.emu_path))
            subprocess.Popen(
                [str(self.emu_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(self.install_root),
            )
            time.sleep(15)
            return True
        except Exception as e:
            logger.error(_("启动模拟器失败: {a}").format(a=str(e)))
            return False


class GooglePlayGamesDevEmulatorDevice(EmulatorDevice):
    device_type = "gpg_dev"
    display_name = "Google Play Games Developer Emulator"
    visible_path_rows = ["install", "emulator", "adb"]
    process_names = ["Service.exe"]
    adb_process_names = ["adb.exe"]
    default_adb_address = "localhost:6520"
    tracks_single_emulator_process = False
    restart_on_connect_failure = False
    setup_display_after_connect = True
    default_install_roots = [
        r"C:\Program Files\Google\Play Games Developer Emulator",
    ]

    @property
    def base_dir(self):
        path = self.install_root
        if path.name.lower() == "emulator":
            return path
        return path / "current" / "emulator"

    def normalize_install_root(self, path):
        if path.name.lower() in ["adb.exe", "crosvm.exe", "service.exe"]:
            path = path.parent
        if path.name.lower() == "service":
            return path.parent.parent
        if path.name.lower() == "emulator":
            return path.parent.parent
        return path

    @property
    def startup_bin(self):
        return self.install_root / "Bootstrapper.exe"

    @property
    def emu_path(self):
        return self.install_root / "current" / "service" / "Service.exe"

    @property
    def adb_path(self):
        return self.base_dir / "adb.exe"

    def detect_running_pids(self):
        if os.name != "nt":
            return []
        root = str(self.install_root).rstrip("\\/").replace("'", "''")
        root_prefix = f"{root}\\"
        script = (
            "Get-CimInstance Win32_Process -Filter \"Name = 'Service.exe'\" | "
            f"Where-Object {{ $_.ExecutablePath -and $_.ExecutablePath.StartsWith('{root_prefix}', "
            "[System.StringComparison]::OrdinalIgnoreCase) }} | "
            "ForEach-Object { $_.ProcessId }"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stderr:
            logger.debug(_("GPG服务进程查询错误:{a}").format(a=result.stderr))
        pids = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.isdigit():
                pids.append(int(line))
        logger.info(_("找到GPG模拟器服务进程: {a}").format(a=pids))
        return pids

    def kill_emulator(self):
        try:
            logger.info(_("正在检查并关闭GPG模拟器服务: {a}...").format(a=self.emu_path))
            pids = self.detect_running_pids()
            if not pids:
                logger.info(_("未找到正在运行的GPG模拟器服务."))
                return
            for pid in pids:
                logger.info(_("使用进程号{a}关闭GPG模拟器服务...").format(a=pid))
                result = subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode != 0:
                    logger.error(
                        _("关闭GPG模拟器服务失败(pid={a}, exit={b}): {c}").format(
                            a=pid,
                            b=result.returncode,
                            c=result.stderr or result.stdout,
                        )
                    )
            time.sleep(1)
            logger.info(_("已尝试终止GPG模拟器服务."))
        except Exception as e:
            logger.error(_("终止GPG模拟器服务时出错: {a}").format(a=str(e)))
        finally:
            self.runtime_context._RUNNING_EMU_PID = None

    def start_emulator(self):
        if not path_exists(self.startup_bin):
            logger.error(_("模拟器启动程序不存在: {a}").format(a=self.startup_bin))
            return False
        try:
            logger.info(_("启动模拟器: {a}").format(a=self.startup_bin))
            subprocess.Popen(
                [str(self.startup_bin)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(self.startup_bin.parent),
            )
            time.sleep(15)
            return True
        except Exception as e:
            logger.error(_("启动模拟器失败: {a}").format(a=str(e)))
            return False


class PhysicalAndroidDevice(Device):
    device_type = "physical"
    display_name = _("实体设备")
    setup_display_after_connect = True
    restore_display_on_stop = True
    close_game_on_stop = True
    default_adb_paths = [
        r"C:\Android\platform-tools\adb.exe",
    ]

    def validate_adb_path(self):
        if not getattr(self.setting, "ADB_PATH", None) and str(self.adb_path) == "adb":
            logger.error(_("实体设备需要设置ADB执行文件."))
            return False
        return super().validate_adb_path()


DEVICE_REGISTRY = {
    "mumu": MuMuEmulatorDevice,
    "bluestacks": BlueStacksEmulatorDevice,
    "gpg_dev": GooglePlayGamesDevEmulatorDevice,
    "physical": PhysicalAndroidDevice,
}


def infer_device_type(setting):
    explicit = getattr(setting, "DEVICE_TYPE", None)
    if explicit:
        return explicit
    emu_path = getattr(setting, "EMU_PATH", "") or ""
    lowered = str(emu_path).lower()
    if "hd-player.exe" in lowered or "hd-adb.exe" in lowered:
        return "bluestacks"
    if "google\\play games developer emulator" in lowered or "crosvm.exe" in lowered or "service.exe" in lowered:
        return "gpg_dev"
    return "mumu"


def create_device(setting, runtime_context):
    device_type = infer_device_type(setting)
    device_cls = DEVICE_REGISTRY.get(device_type, MuMuEmulatorDevice)
    return device_cls(setting, runtime_context)
