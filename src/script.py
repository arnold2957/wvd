from ppadb.client import Client as AdbClient
from win10toast import ToastNotifier
from scipy.optimize import curve_fit
from scipy.signal import find_peaks
from enum import Enum
from datetime import datetime
import os
import subprocess
from utils import *
import random
from threading import Thread,Event
from pathlib import Path
import numpy as np
import copy
import struct

DUNGEON_TARGETS = BuildQuestReflection()

##################################################################
        
CONFIG_VAR_LIST = [
            #categor      var_name,                   type,          default_value
            ["GENERAL",   "EMU_PATH",                 tk.StringVar,  None],
            ["GENERAL",   "EMU_INDEX",                tk.IntVar,     0],
            ["GENERAL",   "ADB_ADRESS",               tk.StringVar,  "127.0.0.1:16384"],
            ["GENERAL",   "LAST_VERSION",             tk.StringVar,  None],
            ["GENERAL",   "LATEST_VERSION",           tk.StringVar,  None],
            ["GENERAL",   "FARM_TARGET_TEXT",         tk.StringVar,  list(DUNGEON_TARGETS.keys())[0] if DUNGEON_TARGETS else ""],
            ["GENERAL",   "FARM_TARGET",              tk.StringVar,  None],
            ["GENERAL",   "KARMA_ADJUST",             tk.StringVar,  "+0"],
            ["GENERAL",   "TASK_SPECIFIC_CONFIG",     tk.BooleanVar, False],
            ["GENERAL",   "STRATEGY",                 list         , [{
                                                                        "group_name": _("柚子"),
                                                                        "skill_settings": [
                                                                            {
                                                                                "role_var": _("F 柚奈壬姬"),
                                                                                "skill_var": _("左上技能"),
                                                                                "target_var": _("不可用"),
                                                                                "freq_var": _("每次启动仅一次"),
                                                                                "skill_lvl": 1
                                                                            }
                                                                        ]
                                                                    },
                                                                    {
                                                                        "group_name": _("全自动战斗"),
                                                                        "skill_settings": []
                                                                    },]],
            ["GENERAL",   "DEFAULT_OVERALL_STRATEGY", tk.StringVar, _("全自动战斗")],        
            ["GENERAL",   "LANGUAGE",                 tk.StringVar, "zh_CN"],
            ["GENERAL",   "WEBSITE_ORG_TIME",         tk.StringVar, None],
            ["GENERAL",   "AM_REFRESH_TIME",          tk.StringVar, None],

            ["TEMPLATE",   "TASK_POINT_STRATEGY",     dict,          {}],
            ["TEMPLATE",   "QUICK_DISARM_CHEST",      tk.BooleanVar, False],
            ["TEMPLATE",   "WHO_WILL_OPEN_IT",        tk.IntVar,     0],
            ["TEMPLATE",   "SKIP_COMBAT_RECOVER",     tk.BooleanVar, False],
            ["TEMPLATE",   "SKIP_CHEST_RECOVER",      tk.BooleanVar, False],
            ["TEMPLATE",   "RECOVER_WHEN_BEGINNING",  tk.BooleanVar, False],
            ["TEMPLATE",   "ACTIVE_REST",             tk.BooleanVar, True],
            ["TEMPLATE",   "ACTIVE_ROYALSUITE_REST",  tk.BooleanVar, False],
            ["TEMPLATE",   "ACTIVE_TRIUMPH",          tk.BooleanVar, False],
            ["TEMPLATE",   "ACTIVE_BEAUTIFUL_ORE",    tk.BooleanVar, False],
            ["TEMPLATE",   "ACTIVE_BEG_MONEY",        tk.BooleanVar, True],
            ["TEMPLATE",   "MAX_TRY_LIMIT",           tk.IntVar,     25],
            ["TEMPLATE",   "REST_INTERVEL",           tk.IntVar,     1],
            ["TEMPLATE",   "ACTIVE_CSC",              tk.BooleanVar, True],
            ]
class FarmConfig:
    for attr_name, var_type, var_config_name, var_default_value in CONFIG_VAR_LIST:
        locals()[var_config_name] = var_default_value
    def __init__(self):
        #### 面板配置其他
        self._FORCESTOPING = None
        self._FINISHINGCALLBACK = None
        self._MSGQUEUE = None
        #### 底层接口
        self._ADBDEVICE = None
    def __getitem__(self, key):
        return getattr(self, key)
    def __getattr__(self, name):
        # 当访问不存在的属性时，抛出AttributeError
        raise AttributeError(_("FarmConfig对象没有属性'%s'") % name)
class RuntimeContext:
    #### 模拟器信息
    _RUNNING_EMU_PID = None # 全局变量
    #### 统计信息
    _LAPTIME = 0
    _TOTALTIME = 0
    _COUNTERDUNG = 0
    _COUNTERCOMBAT = 0
    _COUNTERCHEST = 0
    _TIME_COMBAT= 0
    _TIME_COMBAT_TOTAL = 0
    _TIME_CHEST = 0
    _TIME_CHEST_TOTAL = 0
    #### 其他临时参数
    _MEET_CHEST_OR_COMBAT = False
    _COMBATSPD = False
    _SUICIDE = False # 当有两个人死亡的时候(multipeopledead), 在战斗中尝试自杀.
    _MAXRETRYLIMIT = 20
    _ACTIVESPELLSEQUENCE = None
    _RECOVERAFTERREZ = False
    _ZOOMWORLDMAP = False
    _CRASHCOUNTER = 0
    _IMPORTANTINFO = ""
    _RESUMEAVAILABLE = False
    _STEPAFTERRESTART = True
    STRATEGY_RESET_EACH_RESTART = {}
    STRATEGY_RESET_EACH_DUNGEON = {}
    COMBAT_RESET = True
    CURRENT_STRATEGY = {}
    NEED_RECOVER_WHEN_BEGINNING = True
    TASK_STEP_INDEX = 0
class FarmQuest:
    _TARGETINFOLIST = None
    _EOT = None
    _preEOTcheck = None
    _SPECIALDIALOGOPTION = None
    _SPECIALFORCESTOPINGSYMBOL = None
    _SPELLSEQUENCE = None
    _TYPE = None
    _RTT = None
    def __getattr__(self, name):
        # 当访问不存在的属性时，抛出AttributeError
        raise AttributeError(_("FarmQuest对象没有属性'%s'") % name)
class TargetInfo:
    def __init__(self, target: str, swipeDir: list = None, roi=None):
        self.target = target
        self.swipeDir = swipeDir
        self.roi = roi
    @property
    def swipeDir(self):
        return self._swipeDir

    @swipeDir.setter
    def swipeDir(self, inputValue):
        value = None
        match inputValue:
            case None:
                value = [None,
                        [100,100,700,1200],
                        [400,1200,400,100],
                        [700,800,100,800],
                        [400,100,400,1200],
                        [100,800,700,800],
                        ]
            case "左上":
                value = [[100,250,700,1200]]
            case "右上":
                value = [[700,250,100,1200]]
            case "右下":
                value = [[700,1200,100,250]]
            case "左下":
                value = [[100,1200,700,250]]
            case _:
                value = inputValue
        
        self._swipeDir = value

    @property
    def roi(self):
        return self._roi

    @roi.setter
    def roi(self, value):
        if value == "default":
            value = [[0,0,900,1600],[0,0,900,208],[0,1265,900,335],[0,636,137,222],[763,636,137,222], [336,208,228,77],[336,1168,228,97]]
        if self.target == "chest":
            if value == None:
                value = [[0,0,900,1600]]
            value += [[0,0,900,208],[0,1265,900,335],[0,636,137,222],[763,636,137,222], [336,208,228,77],[336,1168,228,97]]

        self._roi = value
##################################################################
def LoadQuest(farmtarget):
    # 构建文件路径
    jsondict = LoadJson(ResourcePath(QUEST_FILE))
    logger.info(farmtarget)
    if farmtarget in jsondict:
        data = jsondict[farmtarget]
    else:
        logger.error(_("任务列表已更新.请重新手动选择地下城任务."))
        return None
    
    # 创建 Quest 实例并填充属性
    quest = FarmQuest()
    for key, value in data.items():
        if key == "_TARGETINFOLIST":
            setattr(quest, key, [TargetInfo(*args) for args in value])
        elif hasattr(FarmQuest, key):
            setattr(quest, key, value)
        elif key in ["type","questName","questId"]:
            pass
        else:
            logger.info(_("'%s'并不存在于FarmQuest中.") % key)
    
    return quest
##################################################################
def CMDLine(cmd):
    logger.debug(_("执行cmd命令: %s") % cmd)
    result = subprocess.run(cmd,shell=True, capture_output=True, text=True, timeout=10,encoding="utf-8")
    logger.debug(_("cmd命令返回:{a}\n cmd命令错误:{b}").format(a=result.stdout, b=result.stderr))
    return result
def GetADBPathFromEmuPath(emu_path):
        adb_path = emu_path
        adb_path = adb_path.replace("HD-Player.exe", "HD-Adb.exe") # 蓝叠
        adb_path = adb_path.replace("MuMuPlayer.exe", "adb.exe") # mumu
        adb_path = adb_path.replace("MuMuNxDevice.exe", "adb.exe") # mumu
        if not os.path.exists(adb_path):
            logger.error(_("adb程序序不存在: {a}").format(a=adb_path))
            return None
    
        return adb_path
def CheckAndRecoverDevice(setting : FarmConfig, runtimeContext: RuntimeContext, FORCE_RESTART_EMU = False, FORCE_RESTART_ADB = False):
    def CheckEmulator():
        result = subprocess.run(
            "tasklist /FO CSV /NH | findstr \"MuMuNxDevice.exe MuMuPlayer.exe\"",
            shell=True,
            capture_output=True, 
            text=True
        )
        result_str = result.stdout.strip()
        logger.debug(result_str)
        split_results_list = result_str.split("\n")
        check_results_list = []
        for task in split_results_list:
            if not task:
                continue
            parts = task.split("\",\"")
            if len(parts) >= 2:
                try:
                    pid = int(parts[1])
                    check_results_list.append(pid)
                except ValueError:
                    pass
        return check_results_list
    def KillAdb():
        adb_path = GetADBPathFromEmuPath(setting.EMU_PATH)
        try:
            logger.info(_("正在检查并关闭adb..."))
            # Windows 系统使用 taskkill 命令
            if os.name == "nt":
                subprocess.run(
                    f"taskkill /f /im adb.exe", 
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False  # 不检查命令是否成功（进程可能不存在）
                )
                time.sleep(1)
                subprocess.run(
                    f"taskkill /f /im HD-Adb.exe", 
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False  # 不检查命令是否成功（进程可能不存在）
                )
            else:
                subprocess.run(
                    f"pkill -f {adb_path}", 
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False
                )
            logger.info(_("已尝试终止adb"))
        except Exception as e:
            logger.error(_("终止模拟器进程时出错: {a}").format(a=str(e)))
    def KillEmulator():
        emulator_name = os.path.basename(setting.EMU_PATH)
        emulator_SVC = "MuMuVMMSVC.exe"
        try:
            logger.info(_("正在检查并关闭已运行的模拟器实例{a}...").format(a=emulator_name))
            # Windows 系统使用 taskkill 命令
            if os.name == "nt":
                if runtimeContext._RUNNING_EMU_PID:
                    logger.info(_("使用已知进程号{a}关闭模拟器...").format(a=runtimeContext._RUNNING_EMU_PID))
                    subprocess.run(
                        f"taskkill /IM /pid {runtimeContext._RUNNING_EMU_PID}", 
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False  # 不检查命令是否成功（进程可能不存在）
                    )
                    time.sleep(1)
                    subprocess.run(
                        f"taskkill /F /IM MuMuVMMHeadless.exe", 
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False  # 不检查命令是否成功（进程可能不存在）
                    )
                    time.sleep(1)
                else:
                    logger.info(_("模拟器uid未知, 全杀了."))
                    subprocess.run(
                        f"taskkill /f /im {emulator_name}", 
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False  # 不检查命令是否成功（进程可能不存在）
                    )
                    time.sleep(1)
                    subprocess.run(
                        f"taskkill /f /im {emulator_SVC}", 
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False  # 不检查命令是否成功（进程可能不存在）
                    )
                    time.sleep(1)

            # Unix/Linux 系统使用 pkill 命令
            else:
                subprocess.run(
                    f"pkill -f {emulator_name}", 
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False
                )
                subprocess.run(
                    f"pkill -f {emulator_headless}", 
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False
                )
            logger.info(_("已尝试终止模拟器进程: {a}".format(a=emulator_name)))
        except Exception as e:
            logger.error(_("终止模拟器进程时出错: {a}".format(a=str(e))))
        finally:
            # 重置进程号
            runtimeContext._RUNNING_EMU_PID = None

    def StartEmulator():
        hd_player_path = setting.EMU_PATH
        if not os.path.exists(hd_player_path):
            logger.error(_("模拟器启动程序不存在: {a}".format(a=hd_player_path)))
            return False
        
        cmd = ("\"{hd}\" control -v {a}").format(hd=hd_player_path, a=setting.EMU_INDEX)
        try:
            logger.info(_("启动模拟器: {a}".format(a=cmd)))

            # 启动前检查进程
            pre_result_list = CheckEmulator()

            subprocess.Popen(
                cmd, 
                shell=True,
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                cwd=os.path.dirname(hd_player_path))

            # 延时
            time.sleep(5)

            # 启动后检查进程
            aft_results_list = CheckEmulator()

            logger.info(aft_results_list)
            new_tasks = [task for task in aft_results_list if task not in pre_result_list]
            if new_tasks:
                # 模拟器启动成功，pid捕获成功
                runtimeContext._RUNNING_EMU_PID = int(new_tasks[0])
                logger.info(_("模拟器启动开始，进程号为{a}".format(a=runtimeContext._RUNNING_EMU_PID)))

        except Exception as e:
            logger.error(_("启动模拟器失败: {a}".format(a=str(e))))
            return False
        
        logger.info(_("等待模拟器启动..."))
        time.sleep(15)

    # 以上是内部函数
    ####################################
    # 功能实现

    if FORCE_RESTART_EMU:
        KillEmulator()
        time.sleep(1)
    
    if FORCE_RESTART_ADB:
        KillAdb()
        time.sleep(1)

    MAXRETRIES = 20

    adb_path = GetADBPathFromEmuPath(setting.EMU_PATH)

    for attempt in range(MAXRETRIES):
        logger.info(_("-----------------------\n开始尝试连接adb. 次数:{a}/{b}...").format(a=attempt + 1, b=MAXRETRIES))

        if attempt == 3:
            logger.info(_("失败次数过多, 尝试关闭adb."))
            KillAdb()

            # 我们不起手就关, 但是如果2次链接还是尝试失败, 那就触发一次强制重启.
        
        try:
            logger.info(_("检查adb服务..."))
            result = CMDLine(f"\"{adb_path}\" devices")
            if ("daemon not running" in result.stderr) or ("offline" in result.stdout):
                time.sleep(2)
                result = CMDLine(f"\"{adb_path}\" devices")
                if ("daemon not running" in result.stderr) or ("offline" in result.stdout):
                    logger.info("adb服务未启动!\n启动adb服务...")
                    CMDLine(f"\"{adb_path}\" kill-server")
                    CMDLine(f"\"{adb_path}\" start-server")
                    time.sleep(2)

            logger.debug(_("尝试连接到adb..."))
            result = CMDLine(f"\"{adb_path}\" connect {setting.ADB_ADRESS}")

            result = CMDLine(f"\"{adb_path}\" devices")
            if ("{a}").format(a=setting.ADB_ADRESS) in result.stdout:
                logger.info(_("成功连接到模拟器!"))
                results_list = CheckEmulator()
                logger.debug("{a}".format(a=results_list))
                if len(results_list)==1:
                    runtimeContext._RUNNING_EMU_PID = int(results_list[0])
                    logger.info(_("模拟器进程号为{a}.".format(a=runtimeContext._RUNNING_EMU_PID)))
                else:
                    logger.info(_("\n\n***********\n有多个模拟器已经启动, 无法识别进程号. 当需要重启模拟器的时候, 会重启所有模拟器.\n为了避免本问题, 请关闭目标模拟器, 并使用本脚本自动启动模拟器.\n\n"))
                break

            if (not runtimeContext._RUNNING_EMU_PID) or (runtimeContext._RUNNING_EMU_PID not in CheckEmulator()):
                logger.info(_("模拟器未运行，尝试启动..."))
                StartEmulator()
                logger.info(_("模拟器(应该)启动完毕.\n 尝试连接到模拟器..."))
                result = CMDLine(f"\"{adb_path}\" connect {setting.ADB_ADRESS}")
                if result.returncode == 0 and ("connected" in result.stdout or "already" in result.stdout):
                    logger.info(_("成功连接到模拟器"))
                    break
                logger.info(_("无法连接. 检查adb端口."))

            logger.info(_("连接失败: {a}".format(a=result.stderr.strip())))
            time.sleep(2)
            KillEmulator()
            KillAdb()
            time.sleep(2)
        except Exception as e:
            logger.error(_("重启ADB服务时出错: {a}".format(a=e)))
            time.sleep(2)
            KillEmulator()
            KillAdb()
            time.sleep(2)
            return None
    else:
        logger.info(_("达到最大重试次数，连接失败"))
        return None

    try:
        client = AdbClient(host="127.0.0.1", port=5037)
        devices = client.devices()
        
        # 查找匹配的设备
        target_device = "{a}".format(a=setting.ADB_ADRESS)
        for device in devices:
            if device.serial == target_device:
                logger.info(_("成功创建设备对象: {a}".format(a=device.serial)))
                return device
    except Exception as e:
        logger.error(_("创建ADB设备时出错: {a}".format(a=e)))
    
    return None
##################################################################
def CutRoI(screenshot, roi):
    """
    screenshot: 输入图像
    roi: 列表，第一个元素是 (x, y, w, h) 作为main_rect，后续元素是需要涂黑的矩形
    返回: 只包含 main_rect 区域的图像，其中与其他 RoI 重叠的部分已被涂黑
    """
    if roi is None or len(roi) == 0:
        return screenshot

    # 第一个是 main_rect，其余是需要涂黑的区域
    main_rect = roi[0]
    other_rects = roi[1:] if len(roi) > 1 else []

    img_h, img_w = screenshot.shape[:2]

    # 在原图上直接涂黑其他 RoI（注意边界裁剪）
    for rect in other_rects:
        x, y, w, h = rect
        x_start = max(0, x)
        y_start = max(0, y)
        x_end = min(img_w, x + w)
        y_end = min(img_h, y + h)

        if x_start < x_end and y_start < y_end:
            screenshot[y_start:y_end, x_start:x_end] = 0

    # 裁剪出 roi1 区域
    x1, y1, w1, h1 = main_rect
    x1_start = max(0, x1)
    y1_start = max(0, y1)
    x1_end = min(img_w, x1 + w1)
    y1_end = min(img_h, y1 + h1)

    if x1_start >= x1_end or y1_start >= y1_end:
        logger.error("错误:roi1范围无效.")
        return screenshot  # 无效 roi1，返回原图

    main_img = screenshot[y1_start:y1_end, x1_start:x1_end].copy()
    return main_img
##################################################################
def Factory():
    toaster = ToastNotifier()
    setting =  None
    quest = None
    runtimeContext = RuntimeContext()
    runtimeContext = None
    ##################################################################
    def ResetDevice(force_restart_emu=False, force_restart_adb = False):
        nonlocal setting # 修改device
        nonlocal runtimeContext
        if device := CheckAndRecoverDevice(setting, runtimeContext, force_restart_emu, force_restart_adb):
            setting._ADBDEVICE = device
            logger.info(_("ADB服务成功启动，设备已连接."))
    def DeviceShell(cmdStr):
        while True:
            logger.debug(_("DeviceShell {a}".format(a=cmdStr)))
            exception = None
            result = None
            completed = Event()
            
            def adb_command_thread():
                nonlocal exception, result
                try:
                    result = setting._ADBDEVICE.shell(cmdStr, timeout=5)
                except Exception as e:
                    exception = e
                finally:
                    completed.set()
            
            thread = Thread(target=adb_command_thread)
            thread.daemon = True
            thread.start()
            
            try:
                if not completed.wait(timeout=7):
                    # 线程超时未完成
                    logger.warning(_("ADB命令执行超时: {a}".format(a=cmdStr)))
                    raise TimeoutError(_("ADB命令在7秒内未完成"))
                
                if exception is not None:
                    raise exception
                    
                return result
            except ( RuntimeError, ConnectionResetError, cv2.error) as e:
                logger.warning(_("ADB操作失败 ({a}): {b}").format(a=type(e).__name__, b=e))
                logger.info(_("ADB操作失败, 尝试重启ADB或模拟器程序..."))
                ResetDevice()
                time.sleep(1)

                continue
            except TimeoutError as e:
                logger.info(_("ADB超时, 尝试重启ADB或模拟器程序..."))             
                ResetDevice(force_restart_adb=True)
                time.sleep(1)

                continue
            except Exception as e:
                # 非预期异常直接抛出
                logger.error(_("非预期的ADB异常({a}): {b}").format(a=type(e).__name__, b=e))
                raise
    
    def Sleep(t=1):
        time.sleep(t)
    def ScreenShot():
        t = time.time()

        
        while True:
            try:
                # 获取设备序列号，用于构造 adb 命令
                serial = setting._ADBDEVICE.serial 

                process_result = subprocess.run(
                    [GetADBPathFromEmuPath(setting.EMU_PATH), "-s", serial, "exec-out", "screencap"],
                    capture_output=True, # 捕获输出
                    timeout=5            # 设置超时
                )
                
                if process_result.stderr:
                    logger.error(_("截图命令报错: {a}".format(a=process_result.stderr.decode('utf-8', errors='ignore'))))
                    raise RuntimeError(_("截图命令报错"))

                raw_data = process_result.stdout
                
                # 解析头部信息 (前12个字节)
                if len(raw_data) < 12:
                    logger.error(_("截图数据不足12字节(无头信息)"))
                    raise RuntimeError(_("截图数据异常"))
                
                # struct.unpack 解析二进制: "<"小端序, "I"无符号整型(4字节)
                # 前三个整数分别是: 宽度, 高度, 像素格式
                w, h, fmt = struct.unpack("<III", raw_data[:12])
                expected_pixels = w * h * 4
                pixels_data = raw_data[12:]

                if len(pixels_data) == expected_pixels:
                    pass
                elif len(pixels_data) > expected_pixels:
                    # 通常是多了4个字节的结束符，直接切掉尾部多余的
                    pixels_data = pixels_data[:expected_pixels]
                else:
                    logger.error(_("数据长度校验失败: 头部声明 {a}x{b}, 实际收到 {c}, 期望 {d}".format(a=w,b=h,c=len(pixels_data), d=expected_pixels)))
                    raise RuntimeError(_("截图数据不完整"))

                image = np.frombuffer(pixels_data, dtype=np.uint8)
                image = image.reshape((h, w, 4))
                image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)

                # 注意：现在的 image.shape 已经是 (h, w, 3)
                current_h, current_w = image.shape[:2]
               
                if (current_h, current_w) != (1600, 900):
                    if (current_h, current_w) == (900, 1600):
                        logger.error(_("截图尺寸错误: 当前{a}, 检测为横屏.".format(a=image.shape)))  
                        # 不能截图, 截图就爆栈了.
                        restartGame(skip_screenshot=True)
                    else:
                        logger.error(_("截图尺寸错误: 期望(1600,900), 实际({a},{b}).".format(a=current_h,b=current_w)))
                        raise RuntimeError(_("分辨率异常: {a}x{b}".format(a=current_w, b=current_h)))

                # logger.info(f"{time.time()-t}")

                return image

            except subprocess.TimeoutExpired:
                logger.warning(_("截图超时 (Subprocess)"))
                logger.info(_("ADB操作失败, 尝试重启ADB或模拟器程序..."))
                ResetDevice(force_restart_adb=True)
                
            except Exception as e:
                logger.debug(_("截图发生异常: {a}".format(a=e)))
                if isinstance(e, (AttributeError, RuntimeError, ConnectionResetError, cv2.error)):
                    logger.info(_("ADB操作失败/数据错误, 尝试重启ADB或模拟器程序..."))
                    ResetDevice()
                time.sleep(1)
    def _check(screenImage, template, roi = None, outputMatchResult = False):
        screenshot = screenImage.copy()
        pos = None
        search_area = CutRoI(screenshot, roi)
        try:
            result = cv2.matchTemplate(search_area, template, cv2.TM_CCOEFF_NORMED)
        except Exception as e:
                logger.error("{a}".format(a=e))
                logger.info("{a}".format(a=e))
                if isinstance(e, (cv2.error)):
                    logger.info(_("cv2异常."))
                    # timestamp = datetime.now().strftime("cv2_%Y%m%d_%H%M%S")  # 格式：20230825_153045
                    # file_path = os.path.join(LOGS_FOLDER_NAME, f"{timestamp}.png")
                    # cv2.imwrite(file_path, ScreenShot())
                    return None

        underscore, max_val, underscore, max_loc = cv2.minMaxLoc(result)

        if outputMatchResult:
            cv2.imwrite("origin.png", search_area)
            cv2.rectangle(search_area, max_loc, (max_loc[0] + template.shape[1], max_loc[1] + template.shape[0]), (0, 255, 0), 2)
            cv2.imwrite("matched.png", search_area)

        if roi is None or len(roi) == 0:
            pos=[max_loc[0] + template.shape[1]//2,
                 max_loc[1] + template.shape[0]//2]
        else:
            pos=[roi[0][0] + max_loc[0] + template.shape[1]//2,
                 roi[0][1] + max_loc[1] + template.shape[0]//2]
        return pos,max_val
    def CheckIf(screenImage, shortPathOfTarget, roi = None, outputMatchResult = False):
        pos, max_val = _check(screenImage, LoadTemplateImage(shortPathOfTarget), roi, outputMatchResult)

        if max_val < 0.8:
            logger.debug(_("匹配失败: {a}的匹配程度为{b:.2f}%, 不足阈值.".format(a=shortPathOfTarget, b=max_val*100)))
            return None
        else:
            logger.debug(_("匹配成功: {a}的匹配程度为{b:.2f}%, 位于{c}.".format(a=shortPathOfTarget, b=max_val*100,c=pos)))
            return pos
    def CheckHow(screenImage, shortPathOfTarget, roi = None, outputMatchResult = False):
        pos, max_val = _check(screenImage, LoadTemplateImage(shortPathOfTarget), roi, outputMatchResult)

        logger.debug(_("匹配检测: {a}的匹配程度为{b:.2f}%, 位于{c}.".format(a=shortPathOfTarget,b=max_val*100, c=pos)))
        return max_val
    def CheckIf_MultiRect(screenImage, shortPathOfTarget):
        template = LoadTemplateImage(shortPathOfTarget)
        screenshot = screenImage
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)

        threshold = 0.8
        ys, xs = np.where(result >= threshold)
        h, w = template.shape[:2]
        rectangles = list([])

        for (x, y) in zip(xs, ys):
            rectangles.append([x, y, w, h])
            rectangles.append([x, y, w, h]) # 复制两次, 这样groupRectangles可以保留那些单独的矩形.
        rectangles, underscore = cv2.groupRectangles(rectangles, groupThreshold=1, eps=0.5)
        pos_list = []
        for rect in rectangles:
            x, y, rw, rh = rect
            center_x = x + rw // 2
            center_y = y + rh // 2
            pos_list.append([center_x, center_y])
            # cv2.rectangle(screenshot, (x, y), (x + w, y + h), (0, 255, 0), 2)
        # cv2.imwrite("Matched_Result.png", screenshot)
        return pos_list
    def CheckIf_FocusCursor(screenImage, shortPathOfTarget):
        template = LoadTemplateImage(shortPathOfTarget)
        screenshot = screenImage
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)

        threshold = 0.80
        underscore, max_val, underscore, max_loc = cv2.minMaxLoc(result)
        logger.debug(_("搜索到疑似{a}, 匹配程度:{b:.2f}%".format(a=shortPathOfTarget, b=max_val*100)))
        if max_val >= threshold:
            if max_val<=0.9:
                logger.debug(_("警告: {a}的匹配程度超过了80%但不足90%".format(a=shortPathOfTarget)))

            cropped = screenshot[max_loc[1]:max_loc[1]+template.shape[0], max_loc[0]:max_loc[0]+template.shape[1]]
            SIZE = 15 # size of cursor 光标就是这么大
            left = (template.shape[1] - SIZE) // 2
            right =  left+ SIZE
            top = (template.shape[0] - SIZE) // 2
            bottom =  top + SIZE
            midimg_scn = cropped[top:bottom, left:right]
            miding_ptn = template[top:bottom, left:right]
            # cv2.imwrite("miding_scn.png", midimg_scn)
            # cv2.imwrite("miding_ptn.png", miding_ptn)
            gray1 = cv2.cvtColor(midimg_scn, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(miding_ptn, cv2.COLOR_BGR2GRAY)
            mean_diff = cv2.absdiff(gray1, gray2).mean()/255
            logger.debug(_("中心匹配检查:{a:.2f}".format(a=mean_diff)))

            if mean_diff<0.2:
                return True
        return False
    def CheckIf_ReachPosition(screenImage,targetInfo : TargetInfo):
        screenshot = screenImage
        position = targetInfo.roi
        cropped = screenshot[position[1]-33:position[1]+33, position[0]-33:position[0]+33]

        for i in range(4):
            pos, max_val = _check(cropped, LoadTemplateImage(f"cursor_{i}"))

            logger.debug(_("目标格搜索{a}, 匹配程度:{b:.2f}%".format(a=position, b=max_val*100)))
            if max_val > 0.8:
                logger.debug(_("已达到检测阈值."))
                return None 
        return position
    def CheckIf_throughStair(screenImage,targetInfo : TargetInfo):
        stair_img = ["stair_up","stair_down","stair_teleport"]
        screenshot = screenImage
        position = targetInfo.roi
        cropped = screenshot[position[1]-33:position[1]+33, position[0]-33:position[0]+33]
        threshold = 0.8
        
        if (targetInfo.target not in stair_img):
            # 验证楼层
            pos, max_val = _check(screenshot, LoadTemplateImage(targetInfo.target))

            logger.debug(_("搜索楼层标识{a}, 匹配程度:{b:.2f}%".format(a=targetInfo.target,b=max_val*100)))
            if max_val > threshold:
                logger.info(_("楼层正确, 判定为已通过"))
                return None
            return position
            
        else: #equal: targetInfo.target IN stair_img
            pos, max_val = _check(cropped, LoadTemplateImage(targetInfo.target))

            logger.debug(_("搜索楼梯{a}, 匹配程度:{b:.2f}%".format(a=targetInfo.target, b=max_val*100)))
            if max_val > threshold:
                logger.info(_("判定为楼梯存在, 尚未通过."))
                return position
            return None
    def CheckIf_harkenStair(screenImage,targetInfo: TargetInfo):
        screenshot = screenImage
        target = targetInfo.target
        correctStair = targetInfo.roi
        threshold = 0.80

        isInCorrectStair = True

        if (correctStair != None) and isinstance(correctStair, str) and correctStair.startswith('stair_'):
            pos, max_val = _check(screenshot, LoadTemplateImage(correctStair))

            logger.debug(_("楼层验证中, 目标楼层标识{a}, 匹配程度:{b:.2f}%".format(a=correctStair,b=max_val*100)))
            if max_val > threshold:
                logger.info(_("楼层验证判定通过, 当前处于正确楼层."))
                isInCorrectStair = True
            else:
                isInCorrectStair = False
        
        if not isInCorrectStair:
            logger.info(_("目前处于错误的楼层中, 可能是由于错误点击导致的, 开始全地图搜索哈肯."))
            pos = StateMap_FindSwipeClick(TargetInfo('harken', None, None))
            if pos == None:
                pos = StateMap_FindSwipeClick(TargetInfo('Bharken', None, None))
            return pos
        if isInCorrectStair:
            pos, max_val = _check(screenshot, LoadTemplateImage(target))

            logger.debug(_("哈肯搜索, 目标{a}, 匹配程度:{b:.2f}%".format(a=target,b=max_val*100)))
            if max_val > threshold:
                logger.info(_("哈肯搜索, 已找到哈肯."))
                return pos
            return None
            
    def CheckIf_fastForwardOff(screenImage):
        position = [240,1490]
        template =  LoadTemplateImage(f"fastforward_off")
        screenshot =  screenImage
        cropped = screenshot[position[1]-50:position[1]+50, position[0]-50:position[0]+50]
        
        result = cv2.matchTemplate(cropped, template, cv2.TM_CCOEFF_NORMED)
        underscore, max_val, underscore, max_loc = cv2.minMaxLoc(result)
        threshold = 0.80
        pos=[position[0]+max_loc[0] - cropped.shape[1]//2, position[1]+max_loc[1] -cropped.shape[0]//2]

        if max_val > threshold:
            logger.info(_("快进未开启, 即将开启.{a}".format(a=pos)))
            return pos
        return None
    def Press(pos):
        if pos!=None:
            DeviceShell(f"input tap {pos[0]} {pos[1]}")
            return True
        return False
    def PressReturn():
        DeviceShell("input keyevent KEYCODE_BACK")
    def WrapImage(image,r,g,b):
        scn_b = image * np.array([b, g, r])
        return np.clip(scn_b, 0, 255).astype(np.uint8)
    def MinusImage(image,r,g,b):
        scn_b = image - np.array([b, g, r])
        return np.clip(scn_b, 0, 255).astype(np.uint8)
    def TryPressRetry(scn):
        if Press(CheckIf(scn,"startdownload")):
            logger.info(_("开始下载……"))
            return True
        if Press(CheckIf(scn,"retry")):
            logger.info(_("发现并点击了\"重试\". 你遇到了网络波动."))
            return True
        if pos:=(CheckIf(scn,"retry_blank")):
            Press([pos[0], pos[1]+103])
            logger.info(_("发现并点击了\"重试\". 你遇到了网络波动."))
            return True
        return False
    def AddImportantInfo(str):
        nonlocal runtimeContext
        if runtimeContext._IMPORTANTINFO == "":
            runtimeContext._IMPORTANTINFO = _("👆向上滑动查看重要信息👆\n")
        time_str = datetime.now().strftime("%Y%m%d-%H%M%S") 
        runtimeContext._IMPORTANTINFO = " {a} {b}\n{c}".format(a = time_str, b=str, c=runtimeContext._IMPORTANTINFO)
    ##################################################################
    def FindCoordsOrElseExecuteFallbackAndWait(targetPattern, fallback,waitTime):
        # fallback可以是坐标[x,y]或者字符串. 当为字符串的时候, 视为图片地址
        def pressTarget(target):
            if target.lower() == "return":
                PressReturn()
            elif target.startswith("input swipe"):
                DeviceShell(target)
            else:
                Press(CheckIf(scn, target))
        def checkPattern(scn, pattern):
            if pattern.startswith("combatActive"):
                return StateCombatCheck(scn)
            else:
                return CheckIf(scn,pattern)

        while True:
            for underscore in range(setting.MAX_TRY_LIMIT):
                if setting._FORCESTOPING.is_set():
                    return None
                scn = ScreenShot()
                if isinstance(targetPattern, (list, tuple)):
                    for pattern in targetPattern:
                        if p:=checkPattern(scn, pattern):
                            return p
                else:
                    if p:=checkPattern(scn,targetPattern):
                        return p # FindCoords
                # OrElse
                if TryPressRetry(scn):
                    Sleep(1)
                    continue
                if Press(CheckIf_fastForwardOff(scn)):
                    Sleep(1)
                    continue
                
                if fallback: # Execute
                    if isinstance(fallback, (list, tuple)):
                        if (len(fallback) == 2) and all(isinstance(x, (int, float)) for x in fallback):
                            Press(fallback)
                        else:
                            for p in fallback:
                                if isinstance(p, str):
                                    pressTarget(p)
                                elif isinstance(p, (list, tuple)) and len(p) == 2:
                                    t = time.time()
                                    Press(p)
                                    if (waittime:=(time.time()-t)) < 0.1:
                                        Sleep(0.1-waittime)
                                else:
                                    logger.debug(_("错误: 非法的目标{a}.".format(a=p)))
                                    setting._FORCESTOPING.set()
                                    return None
                    else:
                        if isinstance(fallback, str):
                            pressTarget(fallback)
                        else:
                            logger.debug(_("错误: 非法的目标."))
                            setting._FORCESTOPING.set()
                            return None
                Sleep(waitTime) # and wait

            logger.info(_("{a}次截图依旧没有找到目标{b}, 疑似卡死. 重启游戏.".format(a=setting.MAX_TRY_LIMIT, b=targetPattern)))
            Sleep()
            restartGame()
            return None # restartGame会抛出异常 所以直接返回none就行了
    def restartGame(skip_screenshot = False, force_restart_EMU = False):
        nonlocal runtimeContext
        runtimeContext._COMBATSPD = False # 重启会重置2倍速, 所以重置标识符以便重新打开.
        runtimeContext._TIME_CHEST = 0
        runtimeContext._TIME_COMBAT = 0 # 因为重启了, 所以清空战斗和宝箱计时器.
        runtimeContext._ZOOMWORLDMAP = False
        runtimeContext._STEPAFTERRESTART = False
        runtimeContext.STRATEGY_RESET_EACH_RESTART = copy.deepcopy(setting.STRATEGY)

        # 保存重启前截图作为备份
        if not skip_screenshot:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # 格式：20230825_153045
            file_path = os.path.join(LOGS_FOLDER_NAME, f"{timestamp}.png")
            cv2.imwrite(file_path, ScreenShot())
            logger.info(_("重启前截图已保存在{a}中.".format(a=file_path)))

        package_name = "jp.co.drecom.wizardry.daphne"

        runtimeContext._CRASHCOUNTER +=1
        logger.info(_("崩溃计数: {a}\n崩溃计数超过10次后会重启模拟器.".format(a=runtimeContext._CRASHCOUNTER)))
        if runtimeContext._CRASHCOUNTER > 10:
            runtimeContext._CRASHCOUNTER = 0
            force_restart_EMU = True

        if force_restart_EMU:
            CheckAndRecoverDevice(setting, runtimeContext, FORCE_RESTART_EMU=True)
            Sleep(5)

        DeviceShell("logcat -c")
        mainAct = DeviceShell(f"cmd package resolve-activity --brief {package_name}").strip().split("\n")[-1]
        DeviceShell(f"am force-stop {package_name}")
        logger.info(_("巫术, 启动!"))
        logger.debug(DeviceShell(f"am start -n {mainAct}"))
        Sleep(10)
        logs = DeviceShell("logcat -d | grep -i \"unable to initialize.*graphics api\"")
        if logs.strip():
            logger.error(_("检测到崩溃日志, 关闭模拟器重启.{a}".format(a=logs)))
            restartGame(skip_screenshot = False, force_restart_EMU = True)
        raise RestartSignal()
    class RestartSignal(Exception):
        pass
    def RestartableSequenceExecution(*operations):
        while True:
            try:
                for op in operations:
                    op()
                return
            except RestartSignal:
                logger.info(_("任务进度重置中..."))
                continue
    ##################################################################
    # def getCursorCoordinates(input, threshold=0.8):
    #     """在本地图片中查找模板位置"""
    #     template = LoadTemplateImage("cursor")
    #     if template is None:
    #         raise ValueError(_("无法加载模板图片！"))

    #     h, w = template.shape[:2]  # 获取模板尺寸
    #     coordinates = []

    #     # 按指定顺序读取截图文件
    #     img = input

    #     # 执行模板匹配
    #     result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    #     underscore, max_val, underscore, max_loc = cv2.minMaxLoc(result)

    #     if max_val > threshold:
    #         # 返回中心坐标（相对于截图左上角）
    #         center_x = max_loc[0] + w // 2
    #         coordinates = center_x
    #     else:
    #         coordinates = None
    #     return coordinates
    # def findWidestRectMid(input):
    #     crop_area = (30,62),(880,115)
    #     # 转换为灰度图
    #     gray = cv2.cvtColor(input, cv2.COLOR_BGR2GRAY)

    #     # 裁剪图像 (y1:y2, x1:x2)
    #     (x1, y1), (x2, y2) = crop_area
    #     cropped = gray[y1:y2, x1:x2]

    #     # cv2.imwrite("Matched Result.png",cropped)

    #     # 返回结果
    #     column_means = np.mean(cropped, axis=0)
    #     aver = np.average(column_means)
    #     binary = column_means > aver

    #     # 离散化
    #     rect_range = []
    #     startIndex = None
    #     for i, val in enumerate(binary):
    #         if val and startIndex is None:
    #             startIndex = i
    #         elif not val and startIndex is not None:
    #             rect_range.append([startIndex,i-1])
    #             startIndex = None
    #     if startIndex is not None:
    #         rect_range.append([startIndex,i-1])

    #     logger.debug(rect_range)

    #     widest = 0
    #     widest_rect = []
    #     for rect in rect_range:
    #         if rect[1]-rect[0]>widest:
    #             widest = rect[1]-rect[0]
    #             widest_rect = rect


    #     return int((widest_rect[1]+widest_rect[0])/2)+x1
    # def triangularWave(t, p, c):
    #     t_mod = np.mod(t-c, p)
    #     return np.where(t_mod < p/2, (2/p)*t_mod, 2 - (2/p)*t_mod)
    # def calculSpd(t,x):
    #     t_data = np.array(t)
    #     x_data = np.array(x)
    #     peaks, underscore = find_peaks(x_data)
    #     if len(peaks) >= 2:
    #         t_peaks = t_data[peaks]
    #         p0 = np.mean(np.diff(t_peaks))
    #     else:
    #         # 备选方法：傅里叶变换或手动设置初值
    #         p0 = 1.0  # 根据数据调整

    #     # 非线性最小二乘拟合
    #     p_opt, underscore = curve_fit(
    #         triangularWave,
    #         t_data,
    #         x_data,
    #         p0=[p0,0],
    #         bounds=(0, np.inf)  # 确保周期为正
    #     )
    #     estimated_p = p_opt[0]
    #     logger.debug(f"周期 p = {estimated_p:.4f}")
    #     estimated_c = p_opt[1]
    #     logger.debug(f"初始偏移 c = {estimated_c:.4f}")

    #     return p_opt[0], p_opt[1]
    # def ChestOpen():
    #     logger.info(("开始智能开箱(?)..."))
    #     ts = []
    #     xs = []
    #     t0 = float(DeviceShell("date +%s.%N").strip())
    #     while 1:
    #         while 1:
    #             Sleep(0.2)
    #             t = float(DeviceShell("date +%s.%N").strip())
    #             s = ScreenShot()
    #             x = getCursorCoordinates(s)
    #             if x != None:
    #                 ts.append(t-t0)
    #                 xs.append(x/900)
    #                 logger.debug(f"t={t-t0}, x={x}")
    #             else:
    #                 # cv2.imwrite("Matched Result.png",s)
    #                 None
    #             if len(ts)>=20:
    #                 break
    #         p, c = calculSpd(ts,xs)
    #         spd = 2/p*900
    #         logger.debug(f"s = {2/p*900}")

    #         t = float(DeviceShell("date +%s.%N").strip())
    #         s = ScreenShot()
    #         x = getCursorCoordinates(s)
    #         target = findWidestRectMid(s)
    #         logger.debug(f"理论点: {triangularWave(t-t0,p,c)*900}")
    #         logger.debug(f"起始点: {x}")
    #         logger.debug(f"目标点: {target}")

    #         if x!=None:
    #             waittime = 0
    #             t_mod = np.mod(t-c, p)
    #             if t_mod<p/2:
    #                 # 正向移动, 向右
    #                 waittime = ((900-x)+(900-target))/spd
    #                 logger.debug("先向右再向左")
    #             else:
    #                 waittime = (x+target)/spd
    #                 logger.debug("先向左再向右")

    #             if waittime > 0.270 :
    #                 logger.debug(f"预计等待 {waittime}")
    #                 Sleep(waittime-0.270)
    #                 DeviceShell(f"input tap 527 920") # 这里和retry重合, 也和to_title+retry重合.
    #                 Sleep(3)
    #             else:
    #                 logger.debug(f"等待时间过短: {waittime}")

    #         if not CheckIf(ScreenShot(), "chestOpening"):
    #             break
    ##################################################################
    class State(Enum):
        Dungeon = "dungeon"
        Inn = "inn"
        EoT = "edge of Town"
        Quit = "quit"
    class DungeonState(Enum):
        Dungeon = "dungeon"
        Map = "map"
        Chest = "chest"
        Combat = "combat"
        Quit = "quit"

    def DungeonCompletionCounter():
        nonlocal runtimeContext
        if runtimeContext._LAPTIME!= 0:
            runtimeContext._TOTALTIME = runtimeContext._TOTALTIME + time.time() - runtimeContext._LAPTIME
            summary_text = _("已完成{a}次\"{b}\"地下城.\n总计{c}秒.上次用时:{d}秒.\n".format(a=runtimeContext._COUNTERDUNG, b=setting.FARM_TARGET_TEXT, c=round(runtimeContext._TOTALTIME,2), d=round(time.time()-runtimeContext._LAPTIME,2)))
            if runtimeContext._COUNTERCHEST > 0:
                summary_text += f"箱子效率{round(runtimeContext._TOTALTIME/runtimeContext._COUNTERCHEST,2)}秒/箱.\n累计开箱{runtimeContext._COUNTERCHEST}次,开箱平均耗时{round(runtimeContext._TIME_CHEST_TOTAL/runtimeContext._COUNTERCHEST,2)}秒.\n"
            if runtimeContext._COUNTERCOMBAT > 0:
                summary_text += _("累计战斗{a}次.战斗平均用时{b}秒.".format(a=runtimeContext._COUNTERCOMBAT, b=round(runtimeContext._TIME_COMBAT_TOTAL/runtimeContext._COUNTERCOMBAT,2)))
            logger.info("{a}{b}".format(a=runtimeContext._IMPORTANTINFO, b=summary_text),extra={"summary": True})
        # 圈数计时器
        runtimeContext._LAPTIME = time.time()
        # 开箱或战斗标识
        if runtimeContext._MEET_CHEST_OR_COMBAT:
            runtimeContext._MEET_CHEST_OR_COMBAT = False
            runtimeContext._COUNTERDUNG+=1

    def TeleportFromCityToWorldLocation(target, swipe, press_any_key = [550,1]):
        nonlocal runtimeContext
        FindCoordsOrElseExecuteFallbackAndWait(["intoWorldMap","dungFlag","worldmapflag","openworldmap","startdownload"],["closePartyInfo","closePartyInfo_fortress","closePartyInfo_waterway",[1,1]],1)
        
        if CheckIf(scn:=ScreenShot(), "dungflag"):
            # 如果已经在副本里了 直接结束.
            # 因为该函数预设了是从城市开始的.
            return
        
        if CheckIf(scn, "openworldmap"):
            # 如果已经进入了洞窟, 直接结束.
            # 因为这是无战斗无宝箱然后重新尝试的情况.
            return
        
        if Press(CheckIf(scn,"intoWorldMap")):
            # 如果在城市, 尝试进入世界地图
            Sleep(0.5)
            FindCoordsOrElseExecuteFallbackAndWait("worldmapflag","intoWorldMap",1)
        elif CheckIf(scn,"worldmapflag"):
            # 如果在世界地图, 下一步.
            pass

        # 往下都是确保了现在能看见"worldmapflag", 并尝试看见"target"
        Sleep(0.5)
        if not runtimeContext._ZOOMWORLDMAP:
            for underscore in range(3):
                Press([100,1500])
                Sleep(0.5)
            Press([250,1500])
            runtimeContext._ZOOMWORLDMAP = True
        pos = FindCoordsOrElseExecuteFallbackAndWait(target,[swipe,press_any_key],1)

        # 现在已经确保了可以看见target, 那么确保可以点击成功
        Sleep(1)
        Press(pos)
        Sleep(1)
        FindCoordsOrElseExecuteFallbackAndWait(["Inn","openworldmap","dungFlag"],[target,press_any_key],1)
    
    def TeleportFromDungeonToCity(target, swipe, press_any_key = [550,1]):
        nonlocal runtimeContext
        FindCoordsOrElseExecuteFallbackAndWait(["dungFlag","worldmapflag","openworldmap","startdownload"],"openworldmap",1)
        scn = ScreenShot()

        if Press(CheckIf(scn, "openworldmap")):
            pass
        elif CheckIf(scn,"worldmapflag"):
            # 如果在世界地图, 下一步.
            pass

        # 往下都是确保了现在能看见"worldmapflag", 并尝试看见"target"
        Sleep(0.5)
        if not runtimeContext._ZOOMWORLDMAP:
            for underscore in range(3):
                Press([100,1500])
                Sleep(0.5)
            Press([250,1500])
            runtimeContext._ZOOMWORLDMAP = True
        pos = FindCoordsOrElseExecuteFallbackAndWait(target,[swipe,press_any_key],1)

        # 现在已经确保了可以看见target, 那么确保可以点击成功
        Sleep(1)
        Press(pos)
        Sleep(1)
        FindCoordsOrElseExecuteFallbackAndWait(["Inn","openworldmap","dungFlag"],[target,press_any_key],1)
        
    def CursedWheelTimeLeap(target="GhostsOfYore", CSC_symbol=None,CSC_setting = None, chapter = "cursedwheel_impregnableFortress"):
        # CSC_symbol: 是否开启因果? 如果开启因果, 将用这个作为是否点开ui的检查标识
        # CSC_setting: 默认会先选择不接所有任务. 这个列表中储存的是想要打开的因果.
        # 其中的RGB用于缩放颜色维度, 以增加识别的可靠性.
        if setting.ACTIVE_CSC == False:
            logger.info(_("因为面板设置, 跳过了调整因果."))
            CSC_symbol = None

        logger.info(_("开始时间跳跃, 本次跳跃目标:{a}".format(a=target)))

        # 调整条目以找到跳跃目标
        Press(FindCoordsOrElseExecuteFallbackAndWait("cursedWheel",["ruins","startdownload",[1,1]],1))
        for underscore in range(10):
            Press([105,230])
            Sleep(0.5)
        Press(FindCoordsOrElseExecuteFallbackAndWait(chapter,["cursedWheelTapRight","cursedWheel",[1,1]],1))
        if not Press(CheckIf(ScreenShot(),target)):
            DeviceShell(f"input swipe 450 1200 450 200")
            Sleep(2)
            DeviceShell(f"input swipe 450 1200 450 200")
            Sleep(2)
            Press(FindCoordsOrElseExecuteFallbackAndWait(target,"input swipe 50 1200 50 1300",1))
        Sleep(1)

        # 跳跃前尝试调整因果
        while CheckIf(ScreenShot(), "leap"):
            if CSC_symbol != None:
                FindCoordsOrElseExecuteFallbackAndWait(CSC_symbol,"CSC",1)
                last_scn = CutRoI(ScreenShot(), [[77,349,757,1068]])
                # 先关闭所有因果
                while 1:
                    Press(CheckIf(WrapImage(ScreenShot(),2,0,0),"didnottakethequest"))
                    DeviceShell(f"input swipe 150 500 150 400")
                    Sleep(1)
                    scn = CutRoI(ScreenShot(), [[77,349,757,1068]])
                    logger.debug(f"因果: 滑动后的截图误差={cv2.absdiff(scn, last_scn).mean()/255:.6f}")
                    if cv2.absdiff(scn, last_scn).mean()/255 < 0.006:
                        break
                    else:
                        last_scn = scn
                # 然后调整每个因果
                if CSC_setting!=None:
                    last_scn = CutRoI(ScreenShot(), [[77,349,757,1068]])
                    while 1:
                        for option, r, g, b in CSC_setting:
                            Press(CheckIf(WrapImage(ScreenShot(),r,g,b),option))
                            Sleep(1)
                        DeviceShell(f"input swipe 150 400 150 500")
                        Sleep(1)
                        scn = CutRoI(ScreenShot(), [[77,349,757,1068]])
                        logger.debug(f"因果: 滑动后的截图误差={cv2.absdiff(scn, last_scn).mean()/255:.6f}")
                        if cv2.absdiff(scn, last_scn).mean()/255 < 0.006:
                            break
                        else:
                            last_scn = scn
                PressReturn()
                Sleep(0.5)
            Press(CheckIf(ScreenShot(),"leap"))
            Sleep(2)
            Press(CheckIf(ScreenShot(),target))

    def RiseAgainReset(reason):
        nonlocal runtimeContext
        runtimeContext._SUICIDE = False # 死了 自杀成功 设置为false
        runtimeContext._RECOVERAFTERREZ = True
        if reason == "chest":
            runtimeContext._COUNTERCHEST -=1
        else:
            runtimeContext._COUNTERCOMBAT -=1
        logger.info(_("快快请起."))
        AddImportantInfo(_("面具死了, 但是再起."))
        Press([450,750])
        Sleep(10)
    def IdentifyState():
        nonlocal setting # 修改因果
        counter = 0
        while 1:
            screen = ScreenShot()
            logger.info(_("状态检查中...(第{a}次)".format(a=counter+1)))

            if setting._FORCESTOPING.is_set():
                return State.Quit, DungeonState.Quit, screen

            if TryPressRetry(screen):
                    Sleep(2)

            if Press(CheckIf(screen,"startdownload",[[222,901,465,84]])):
                logger.info(_("确认, 下载, 确认."))
                Sleep(2)

            identifyConfig = [
                ("dungFlag",      DungeonState.Dungeon),
                ("chestFlag",     DungeonState.Chest),
                ("whowillopenit", DungeonState.Chest),
                ("mapFlag",       DungeonState.Map),
                ]
            for pattern, state in identifyConfig:
                if CheckIf(screen, pattern):
                    return State.Dungeon, state, screen
                
            if StateCombatCheck(screen):
                return State.Dungeon, DungeonState.Combat, screen

            if CheckIf(screen,"someonedead"):
                AddImportantInfo(_("尝试复活队友..."))
                Sleep(1)
                for underscore in range(5):
                    Press([400+random.randint(0,100),750+random.randint(0,100)])
                    Sleep(1)

            if Press(CheckIf(screen, "returnText")):
                Sleep(2)
                return IdentifyState()

            if CheckIf(screen,"returntoTown"):
                if setting.ACTIVE_REST and runtimeContext._MEET_CHEST_OR_COMBAT and ((runtimeContext._COUNTERDUNG-1) % (max(setting.REST_INTERVEL,1)) == 0):
                    FindCoordsOrElseExecuteFallbackAndWait("Inn",["return",[1,1]],1)
                    return State.Inn,DungeonState.Quit, screen
                else:
                    
                    logger.info(_("不满足回城条件, 跳过回城."))
                    return State.EoT,DungeonState.Quit,screen

            if CheckIf(screen, "worldmapflag"):
                for underscore in range(3):
                    Press([100,1500])
                    Sleep(0.5)
                Press([250,1500])
                # 由于定位流程包含了返回键, 有时会退出到大地图, 因此强制执行RTT流程, 不管是否需要住宿.
                # if setting.ACTIVE_REST and runtimeContext._MEET_CHEST_OR_COMBAT and ((runtimeContext._COUNTERDUNG-1) % (max(setting.REST_INTERVEL,1)) == 0):
                if quest._RTT:
                    for info in quest._RTT:
                        TeleportFromDungeonToCity(*info[2])
                    return IdentifyState()
                       
            if pos:=(CheckIf(screen,"openworldmap")):
                if setting.ACTIVE_REST and runtimeContext._MEET_CHEST_OR_COMBAT and ((runtimeContext._COUNTERDUNG-1) % (max(setting.REST_INTERVEL,1)) == 0):
                    Press(pos)
                    if quest._RTT:
                        for info in quest._RTT:
                            TeleportFromDungeonToCity(*info[2])
                    return IdentifyState()
                else:
                    logger.info(_("不满足回城条件, 跳过回城."))
                    return State.EoT,DungeonState.Quit,screen

            for city in ["City_RoyalCityLuknalia","City_fortress", "City_DHI","City_portTownGrandLegion"]:
                if CheckIf(screen,city):
                    FindCoordsOrElseExecuteFallbackAndWait(["Inn","dungFlag"],[city,[1,1]],1)
                    if CheckIf(scn:=ScreenShot(),"Inn"):
                        return State.Inn,DungeonState.Quit, screen
                    elif CheckIf(scn,"dungFlag"):
                        return State.Dungeon,None, screen

            if (CheckIf(screen,"Inn")):
                return State.Inn, None, screen

            if quest._SPECIALFORCESTOPINGSYMBOL != None:
                for symbol in quest._SPECIALFORCESTOPINGSYMBOL:
                        if CheckIf(screen,symbol):
                            return State.Quit,DungeonState.Quit,screen
                        
            if quest._SPECIALDIALOGOPTION != None:
                for option in quest._SPECIALDIALOGOPTION:
                    if Press(CheckIf(screen,option)):
                        return IdentifyState()

            if counter>=4:
                logger.info(_("看起来遇到了一些不太寻常的情况..."))
                if Press(CheckIf(screen,"RiseAgain")):
                    RiseAgainReset(reason = "combat")
                    return IdentifyState()
                if Press(CheckIf(screen, "sandman_recover")):
                    return IdentifyState()
                if (CheckIf(screen,"cursedWheel_timeLeap")):
                    if (setting.ACTIVE_BEG_MONEY):
                        setting._MSGQUEUE.put(("turn_to_7000G",""))
                        raise SystemExit
                    else:
                        logger.info(_("看起来你没有选择找王女要钱. 那么就等两个小时吧."), extra={"summary": True})
                        Sleep(7300)
                        restartGame()
                if CheckIf(screen,"ambush") or CheckIf(screen,"ignore"):
                    if int(setting.KARMA_ADJUST) == 0:
                        Press(CheckIf(screen,"ambush"))
                        new_str = "+2"
                    elif setting.KARMA_ADJUST.startswith("-"):
                        Press(CheckIf(screen,"ambush"))
                        num = int(setting.KARMA_ADJUST)
                        num = num + 2
                        new_str = "{a}".format(a=num)
                    else:
                        Press(CheckIf(screen,"ignore"))
                        num = int(setting.KARMA_ADJUST)
                        num = num - 1
                        new_str = f"+{num}"

                    logger.info(_("即将进行善恶值调整. 剩余次数:{a}".format(a=new_str)))
                    AddImportantInfo(_("新的善恶:{a}".format(a=new_str)))
                    setting.KARMA_ADJUST = new_str
                    SetOneVarInGeneralConfig("KARMA_ADJUST",setting.KARMA_ADJUST)
                    Sleep(2)

                for op in DIALOG_OPTION_IMAGE_LIST:
                    if Press(CheckIf(screen, "dialogueChoices/"+op)):
                        Sleep(2)
                        if op == "adventurersbones":
                            AddImportantInfo(_("购买了骨头."))
                        if op == "halfBone":
                            AddImportantInfo(_("购买了尸油."))
                        return IdentifyState()
                    
                if pos_b:=CheckIf(screen,"blessing"):
                    if pos:=CheckIf(screen, "combatClose"): # 如果因为某些原因点到了切换哈肯祝福, 进入了二次确认界面
                        Press(pos) # 我们把二次确认的界面关了, 无事发生
                    else:
                        Press(pos_b)
                
                if (CheckIf(screen,"multipeopledead")):
                    runtimeContext._SUICIDE = True # 准备尝试自杀
                    logger.info(_("死了好几个, 惨哦"))
                    # logger.info("Corpses strew the screen")
                    Press(CheckIf(screen,"skull"))
                    Sleep(2)

                if Press(CheckIf(screen,"totitle")):
                    logger.info(_("网络故障警报! 网络故障警报! 返回标题, 重复, 返回标题!"))
                    return IdentifyState()
                PressReturn()
                Sleep(0.5)
                PressReturn()
            if counter>= setting.MAX_TRY_LIMIT:
                logger.info(_("看起来遇到了一些非同寻常的情况...重启游戏."))
                restartGame()
                counter = 0
            if counter>=4:
                Press([1,1])
                Sleep(0.25)
                Press([1,1])
                Sleep(0.25)
                Press([1,1])

            Sleep(1)
            counter += 1
        return None, None, screen
    def GameFrozenCheck(queue, scn,  tick= 10, threshold = 0.15):
        LENGTH = tick
        if scn is None:
            raise ValueError(_("GameFrozenCheck被传入了一个空值."))

        while len(queue) >= LENGTH:
            queue.pop(0)
        queue.append(scn)

        if not hasattr(GameFrozenCheck, "call_counter"):
            GameFrozenCheck.call_counter = 0
        GameFrozenCheck.call_counter += 1

        logger.debug(_("卡死检测截图 counter={a} length={b}".format(a=GameFrozenCheck.call_counter, b=len(queue))))

        if (GameFrozenCheck.call_counter % tick == 0) and (len(queue)==LENGTH):
            totalDiff = 0
            t = time.time()
            for i in range(1,LENGTH):
                grayThis = cv2.cvtColor(queue[i], cv2.COLOR_BGR2GRAY)
                grayLast = cv2.cvtColor(queue[i-1], cv2.COLOR_BGR2GRAY)
                mean_diff = cv2.absdiff(grayThis, grayLast).mean()/255
                totalDiff += mean_diff
            logger.info(f"卡死检测耗时: {time.time()-t:.5f}秒")
            logger.info(f"卡死检测结果: {totalDiff:.5f}")
            if totalDiff<=threshold:
                return queue, True
        return queue, False
    def StateCombatCheck(screen):
        combatActiveFlag = [
            "combatActive",
            "combatActive_2",
            "combatActive_3",
            "combatActive_4",
            ]
        for combat in combatActiveFlag:
            if pos:=CheckIf(screen,combat, [[0,0,150,80]]):
                return pos
        return None
    def StateInn():
        if not setting.ACTIVE_ROYALSUITE_REST:
            FindCoordsOrElseExecuteFallbackAndWait("OK",["Inn","Stay","Economy",[1,1]],2)
        else:
            FindCoordsOrElseExecuteFallbackAndWait("OK",["Inn","Stay","royalsuite",[1,1]],2)
        FindCoordsOrElseExecuteFallbackAndWait("Stay",["OK",[299,1464]],2)
        PressReturn()
    def StateEoT():
        runtimeContext._RESUMEAVAILABLE = False
        if quest._preEOTcheck:
            if Press(CheckIf(ScreenShot(),quest._preEOTcheck)):
                pass
        for info in quest._EOT:
            if info[1]=="intoWorldMap":
                TeleportFromCityToWorldLocation(*info[2])
            else:
                pos = FindCoordsOrElseExecuteFallbackAndWait(info[1], info[2], info[3])
                if info[0]=="press":
                    Press(pos)
        RestartableSequenceExecution(
            lambda: FindCoordsOrElseExecuteFallbackAndWait(["dungFlag","GotoDung"], [quest._EOT[-1][1],[1,1]], 1)
            )
        Sleep(1)
        Press(CheckIf(ScreenShot(), "GotoDung"))
    def StateCombat():
        if runtimeContext._TIME_COMBAT==0:
            runtimeContext._TIME_COMBAT = time.time()
        # 内部函数：复制策略到 runtime.CURRENT_STRATEGY
        def CopyStrategy():
            if not setting.TASK_SPECIFIC_CONFIG:
                strategy_key = setting.DEFAULT_OVERALL_STRATEGY
            else:
                overall = setting.TASK_POINT_STRATEGY["overall_strategy"]
                if overall == _("自定义任务点策略"):
                    # 使用当前任务步骤索引获取具体策略
                    task_step_idx = runtimeContext.TASK_STEP_INDEX
                    strategy_key = setting.TASK_POINT_STRATEGY["task_point"][str(task_step_idx)]
                else:
                    strategy_key = overall

            # 在对应列表中查找 group_name 匹配的字典
            target_dict = None
            for d in runtimeContext.STRATEGY_RESET_EACH_DUNGEON:
                if d.get("group_name") == strategy_key:
                    target_dict = d
                    break

            if target_dict is not None:
                # 拷贝该字典到 CURRENT_STRATEGY
                runtimeContext.CURRENT_STRATEGY = copy.deepcopy(target_dict)
            else:
                # 如果未找到，可考虑默认策略或报错，这里简单置空
                runtimeContext.CURRENT_STRATEGY = {}
                logger.error(_("无法获取当前策略."))
            return
        def AutoThisChar():
            Press([850,1100])
            Sleep(0.5)
            Press([850,1100])
            Sleep(2)
            return
        def ActiveAutoCombat():
            scn = ScreenShot()
            if CheckIf(scn,"spellskill/CombatAutoDisable",[[842, 1124-42, 35, 13]]):
                Press([850,1100])
            Sleep(5)
            return
        def SkillLvlSelectAndDoubleCheck(skillPos,skilllvl, supportTarget):
            skillPosDict = { "左上技能":[266,965],"右上技能":[640,965],"左下技能":[266,1054],"右下技能":[640,1054]}
            supportTargetDict = {"左上角色": [200,1200], "中上角色": [450,1200], "右上角色": [700,1200], "左下角色":[200,1400], "中下角色":[450,1400], "右下角色":[700,1400]}
            
            # 打开详情界面
            into_detail = False
            for underscore in range(3):
                Press(skillPosDict[skillPos])
                Sleep(1)
                if CheckIf(ScreenShot(),"spellskill/skillDetail"):
                    into_detail = True
                    break
            if not into_detail:
                logger.info("没有检测到任务详情界面. 疑似法力不足, 使用自动战斗.")
                for underscore in range(3):
                    PressReturn()
                    Sleep(0.2)

                AutoThisChar()
                return

            # 设置等级
            Sleep(1)
            scn = ScreenShot()
            has_lv_1 = (CheckIf(scn,f"spellskill\skillLvl\lv1")) or (CheckIf(scn,f"spellskill\skillLvl\s_lv1"))
            if (not has_lv_1):
                if (skilllvl>=2):
                    logger.error("错误: 设定了高于1级的技能, 但并未检测到技能等级.\n 使用默认技能.")
            else:
                if skilllvl!=1:
                    has_lv_x = (CheckIf(scn,f"spellskill\skillLvl\lv{skilllvl}")) or (CheckIf(scn,f"spellskill\skillLvl\s_lv{skilllvl}"))
                else:
                    has_lv_x = has_lv_1

                if not has_lv_x:
                    skilllvl = 1
                    logger.error("错误: 未检测到目标等级\n 使用1级技能.")
                if not Press(CheckIf(scn,f"spellskill\skillLvl\lv{skilllvl}")):
                    if not Press(CheckIf(scn,f"spellskill\skillLvl\s_lv{skilllvl}")):
                        logger.error("错误: 我认为不可能发生这种情况. 请务必告诉我.")

            # 辅助技能
            if CheckIf(ScreenShot(),"supportSkillCheck",[[677,1475,189,80]]):
                if supportTarget in supportTargetDict.keys():
                    Press(supportTargetDict[supportTarget])
                    logger.info(_("释放了位于\"{a}\"的辅助技能, 技能等级为{b}, 释放对象为{c}".format(a=skillPos, b=skilllvl, c=supportTarget)))

            # 确认
            scn = ScreenShot()
            if Press(CheckIf(scn,"OK")):
                logger.info(_("释放了位于\"{a}\"的全体技能, 技能等级为{b}.".format(a=skillPos, b=skilllvl)))
                Sleep(2)
            elif pos:=(CheckIf(scn,"next")):
                Press([pos[0]-15+random.randint(0,30),pos[1]+150+random.randint(0,30)])
                logger.info(_("释放了位于\"{a}\"的单体技能, 技能等级为{b}. 选择next作为敌方目标.".format(a=skillPos, b=skilllvl)))
            else:
                for i in range(6):
                    Press([150*i-150,750])
                    Sleep(0.1)
                logger.info(_("释放了位于\"{a}\"的单体技能, 技能等级为{b}. 随机选择敌方目标.".format(a=skillPos, b=skilllvl)))
                Sleep(2)

            # 资源不足
            Sleep(1)
            scn = ScreenShot()
            if CheckIf(scn,"notenoughsp") or CheckIf(scn,"notenoughmp"):
                for underscore in range(3):
                    PressReturn()
                    Sleep(0.2)

                SkillLvlSelectAndDoubleCheck(skillPos,1,supportTarget)
                return

        ###################################################################################
        # 主逻辑开始
        # 0. 开启二倍速
        screen = ScreenShot()
        if Press(CheckIf(screen,"combatSpd")) or Press(CheckIf(screen,"combatSpd_DHI")):
            runtimeContext._COMBATSPD = True
            Sleep(1)
        # 1. 检查重置标识
        if runtimeContext.COMBAT_RESET:
            CopyStrategy()
            runtimeContext.COMBAT_RESET = False

        # 2. 获取当前策略中的技能设置列表
        skill_settings = runtimeContext.CURRENT_STRATEGY.get("skill_settings", [])
        aac = False
        if runtimeContext.CURRENT_STRATEGY == {}:
            logger.error(_("错误: 当前战斗策略内容为空. 使用全自动战斗."))
            aac = True
        elif runtimeContext.CURRENT_STRATEGY.get("group_name","") ==_("全自动战斗"):
            logger.info(_("当前战斗为\"全自动战斗\", 因此使用全自动战斗."))
            aac = True
        elif skill_settings == []:
            logger.info(_("当前战斗技能列表内容为空, 因此使用全自动战斗."))
            aac = True
        
        if aac:
            ActiveAutoCombat()
            return

        # 检查是否所有技能都是“重复”且“双击自动”
        all_repeat_and_auto = all(
            item.get("freq_var") == _("重复") and item.get("skill_var") == _("双击自动")
            for item in skill_settings
        )

        if all_repeat_and_auto:
            ActiveAutoCombat()
            return

        # 3. 非全自动模式：点击任意键直到出现“flee”图片
        [pos_x, pos_y] = FindCoordsOrElseExecuteFallbackAndWait(["flee","chestFlag","dungFlag", "someonedead","RiseAgain"],[1,1],1)
        if (pos_x>=735)and(pos_x<=735+126)and(pos_y>=1158)and(pos_y<=1158+68):
            pass
        else:
            logger.debug(_("战斗已结束."))
            return

        # 4. 进行匹配
        highest_match_rate = 0
        target_skill = None
        scn = ScreenShot()
        t = time.time()
        for skill in skill_settings:
            role_var = skill.get("role_var")
            if not role_var:  # 如果 role_var 为空则跳过
                continue
            for candidate in [role_var, role_var + "_sp", role_var + "_alt"]:
                # 构造图片完整路径并检查是否存在
                img_path = os.path.join(IMAGE_FOLDER, "spellskill", "char", f"{candidate}.png")
                full_path = ResourcePath(img_path)
                if os.path.exists(full_path):
                    match_rate = CheckHow(scn, f"spellskill/char/{candidate}", [[85, 57, 100, 48]])
                    if match_rate > highest_match_rate:
                        highest_match_rate = match_rate
                        target_skill = skill
                        logger.debug(_("最佳 {a}, {b}".format(a=candidate, b=highest_match_rate)))
        logger.debug(f"匹配时间 {time.time() - t}")

        # 5. 判断匹配率是否达标
        if highest_match_rate < 0.80:
            logger.info(_("并未设定该角色的行为, 使用自动战斗."))
            AutoThisChar()
            return

        # 6. 按照技能等级释放技能
        if target_skill.get("skill_var") == _("双击自动"):
            if target_skill.get("freq_var") == _("重复"):
                logger.info(_("不需要同时设置为\"双击自动\"且\"重复\", 因为这是未设置角色时的默认行为."))
            # 双击自动
            AutoThisChar()
        elif target_skill.get("skill_var") == _("防御"):
            Press([513,1200])
            Sleep(0.1)
            Press([513,1200])
            Sleep(0.1)
        else:
            SkillLvlSelectAndDoubleCheck(target_skill.get("skill_var"), target_skill.get("skill_lvl"), target_skill.get("target_var"))

        # 9. 根据频次设置删除对应字典
        freq = target_skill.get("freq_var")
        if (freq == _("每次启动仅一次")) or (freq == _("每次副本仅一次")) or (freq == _("每场战斗仅一次")):
            runtimeContext.CURRENT_STRATEGY["skill_settings"].remove(target_skill)
            logger.info(_("在当前战斗的策略中删除了该技能."))
        if (freq == _("每次启动仅一次")) or (freq == _("每次副本仅一次")):
            group = runtimeContext.CURRENT_STRATEGY.get("group_name")
            if group:
                for d in runtimeContext.STRATEGY_RESET_EACH_DUNGEON:
                    if d.get("group_name") == group:
                        # 在对应的 skill_settings 中删除相同内容的字典
                        d["skill_settings"].remove(target_skill)
                        logger.info(_("在每次地下城的策略中删除了该技能."))
                        break
        if freq == _("每次启动仅一次"):
            group = runtimeContext.CURRENT_STRATEGY.get("group_name")
            if group:
                for d in runtimeContext.STRATEGY_RESET_EACH_RESTART:
                    if d.get("group_name") == group:
                        # 在对应的 skill_settings 中删除相同内容的字典
                        d["skill_settings"].remove(target_skill)
                        logger.info(_("在每次启动中使用的策略里删除了该技能."))
                        break
        return
    def StateMap_FindSwipeClick(targetInfo : TargetInfo):
        ### return = None: 视为没找到, 大约等于目标点结束.
        ### return = [x,y]: 视为找到, [x,y]是坐标.
        target = targetInfo.target
        roi = targetInfo.roi
        for i in range(len(targetInfo.swipeDir)):
            scn = ScreenShot()
            if not CheckIf(scn,"mapFlag"):
                raise KeyError(_("地图不可用."))

            swipeDir = targetInfo.swipeDir[i]
            if swipeDir!=None:
                logger.debug(f"拖动地图:{swipeDir[0]} {swipeDir[1]} {swipeDir[2]} {swipeDir[3]}")
                DeviceShell(f"input swipe {swipeDir[0]} {swipeDir[1]} {swipeDir[2]} {swipeDir[3]}")
                Sleep(2)
                scn = ScreenShot()
            
            targetPos = None
            if target == "position":
                logger.info(_("当前目标: 地点{a}".format(a=roi)))
                targetPos = CheckIf_ReachPosition(scn,targetInfo)
            elif target in ['harken','Bharken']:
                targetPos = CheckIf_harkenStair(scn,targetInfo)
            elif target.startswith("stair"):
                logger.info(_("当前目标: 楼梯{a}".format(a=target)))
                targetPos = CheckIf_throughStair(scn,targetInfo)
            else:
                logger.info(_("搜索{a}...".format(a=target)))
                if targetPos:=CheckIf(scn,target,roi):
                    logger.info(_("找到了 {a}! {b}".format(a=target, b=targetPos)))
                    if (target == "chest") and (swipeDir!= None):
                        logger.debug(_("宝箱热力图: 地图:{a} 方向:{b} 位置:{c}".format(a=setting.FARM_TARGET, b=swipeDir, c=targetPos)))
                    Sleep(1)
                    break
            if targetPos!=None:
                return targetPos
        return targetPos
    def StateMoving_CheckFrozen():
        runtimeContext._RESUMEAVAILABLE = True
        lastscreen = None
        dungState = None
        logger.info(_("面具男, 移动."))
        while 1:
            Sleep(3)
            underscore, dungState,screen = IdentifyState()
            if dungState == DungeonState.Map:
                logger.info(_("开始移动失败. 不要停下来啊面具男!"))
                FindCoordsOrElseExecuteFallbackAndWait("dungFlag",[[280,1433],[1,1]],1)
                dungState = dungState.Dungeon
                break
            if dungState != DungeonState.Dungeon:
                logger.info(_("已退出移动状态. 当前状态: {a}.".format(a=dungState)))
                break
            if lastscreen is not None:
                gray1 = cv2.cvtColor(CutRoI(screen,[[650,25,225,225]]), cv2.COLOR_BGR2GRAY)
                gray2 = cv2.cvtColor(CutRoI(lastscreen,[[650,25,225,225]]), cv2.COLOR_BGR2GRAY)
                mean_diff = cv2.absdiff(gray1, gray2).mean()/255
                logger.debug(f"移动停止检查:{mean_diff:.2f}")
                if mean_diff < 0.1:
                    dungState = None
                    logger.info(_("已退出移动状态. 进行状态检查..."))
                    break
            lastscreen = screen
        return dungState
    def StateSearch(waitTimer, targetInfo):
        normalPlace = ["harken","chest","leaveDung","position","Bharken"]
        target = targetInfo.target
        # 地图已经打开.
        map = ScreenShot()

        if CheckIf(map,"tooPoorToReadTheMap"):
            logger.info(_("在暴风雪中."))
            Press(CheckIf(map,"dungFlag"))
            return StateMoving_CheckFrozen(),False
    
        if not CheckIf(map,"mapFlag"):
            logger.info(_("没有检测到地图."))
            return None,False # 发生了其他错误

        try:
            searchResult = StateMap_FindSwipeClick(targetInfo)
        except KeyError as e:
            logger.info(_("错误: {a}".format(a=e))) # 一般来说这里只会返回"地图不可用
            return None, False
    
        if not CheckIf(map,"mapFlag"):
                return None, False # 发生了错误, 应该是进战斗了

        if searchResult == None:
            if target == "chest":
                logger.info(_("没有找到宝箱.\n停止检索宝箱."))
                return DungeonState.Map,  True
            elif (target == "position" or target.startswith("stair")):
                logger.info(_("已经抵达目标地点或目标楼层."))
                return DungeonState.Map,  True
            else:
                # 这种时候我们认为真正失败了. 所以不弹出.
                # 当然, 更好的做法时传递finish标识()
                logger.info(_("未找到目标{a}.".format(a=target)))
                return DungeonState.Map,  False
        else:
            if target in normalPlace or target.endswith("_quit") or target.startswith("stair"):
                Press(searchResult)
                Press([136,1431]) # automove
                return StateMoving_CheckFrozen(),False
            else:
                if (CheckIf_FocusCursor(ScreenShot(),target)): #注意 这里通过二次确认 我们可以看到目标地点 而且是未选中的状态
                    logger.info(_("经过对比中心区域, 确认没有抵达."))
                    Press(searchResult)
                    Press([136,1431]) # automove
                    return StateMoving_CheckFrozen(), False
                else:
                    # if setting._DUNGWAITTIMEOUT == 0:
                        logger.info(_("经过对比中心区域, 判断为抵达目标地点."))
                        logger.info(_("无需等待, 当前目标已完成."))
                        return DungeonState.Map, True
                    # else:
                    #     logger.info(_("经过对比中心区域, 判断为抵达目标地点."))
                    #     logger.info(_("开始等待...等待..."))
                    #     PressReturn()
                    #     Sleep(0.5)
                    #     PressReturn()
                    #     while 1:
                    #         if setting._DUNGWAITTIMEOUT-time.time()+waitTimer<0:
                    #             logger.info(_("等得够久了. 目标地点完成."))
                    #             Sleep(1)
                    #             Press([777,150])
                    #             return None, True
                    #         logger.info(_("还需要等待{a}秒.".foramt(a=setting._DUNGWAITTIMEOUT-time.time()+waitTimer)))
                    #         if StateCombatCheck(ScreenShot()):
                    #             return DungeonState.Combat, False
        return DungeonState.Map, False
    def StateChest():
        nonlocal runtimeContext
        availableChar = [0, 1, 2, 3, 4, 5]
        disarm = [515,934]  # 527,920会按到接受死亡 450 1000会按到技能 445,1050还是会按到技能
        haveBeenTried = False

        if runtimeContext._TIME_CHEST==0:
            runtimeContext._TIME_CHEST = time.time()
        
        if setting.QUICK_DISARM_CHEST:
            if Press(CheckIf(ScreenShot(),"chestFlag")):
                Sleep(1)
                whowillopenit = setting.WHO_WILL_OPEN_IT - 1
                pos = [258+(whowillopenit%3)*258, 1161+((whowillopenit)//3)%2*184]
                Press(pos)
                Sleep(0.2)
                Press(pos)
                Sleep(0.2)
                Press(pos)
                Sleep(1)
                for underscore in range(30):
                    Press(disarm)
                    Sleep(0.2)
                for underscore in range(3):
                    Press([1,1])
                    Press(disarm)

        while 1:
            FindCoordsOrElseExecuteFallbackAndWait(
                ["dungFlag","combatActive","chestOpening","whowillopenit","RiseAgain", "ambush"],
                [[1,1],[1,1],"chestFlag"],
                1)
            scn = ScreenShot()

            if CheckIf(scn,"whowillopenit"):
                while 1:
                    pointSomeone = setting.WHO_WILL_OPEN_IT - 1
                    if (pointSomeone != -1) and (pointSomeone in availableChar) and (not haveBeenTried):
                        whowillopenit = pointSomeone # 如果指定了一个角色并且该角色可用并且没尝试过, 使用它
                    else:
                        whowillopenit = random.choice(availableChar) # 否则从列表里随机选一个
                    pos = [258+(whowillopenit%3)*258, 1161+((whowillopenit)//3)%2*184]
                    # logger.info(f"{availableChar},{pos}")
                    if CheckIf(scn,"chestfear",[[pos[0]-125,pos[1]-82,250,164]]):
                        if whowillopenit in availableChar:
                            availableChar.remove(whowillopenit) # 如果发现了恐惧, 删除这个角色.
                    else:
                        Press(pos)
                        Sleep(1.5)
                        # if not setting._SMARTDISARMCHEST:
                        for underscore in range(8):
                            t = time.time()
                            Press(disarm)
                            if time.time()-t<0.3:
                                Sleep(0.3-(time.time()-t))
                                
                        break
                if not haveBeenTried:
                    haveBeenTried = True

            if CheckIf(scn,"chestOpening"):
                Sleep(1)
                # if setting._SMARTDISARMCHEST:
                #     ChestOpen()
                FindCoordsOrElseExecuteFallbackAndWait(
                    ["dungFlag","combatActive","chestFlag","RiseAgain"], # 如果这个fallback重启了, 战斗箱子会直接消失, 固有箱子会是chestFlag
                    [disarm,disarm,disarm,disarm,disarm,disarm,disarm,disarm],
                    1)
            
            if CheckIf(scn,"RiseAgain"):
                RiseAgainReset(reason = "chest")
                return None
            if CheckIf(scn,"dungFlag"):
                return DungeonState.Dungeon
            if CheckIf(scn, "ambush"):
                logger.info("开箱子然后遇到怪物还是善恶, 你这什么运气啊.")
                return None
            if StateCombatCheck(scn):
                return DungeonState.Combat
            
            TryPressRetry(scn)
    def StateDungeon(targetInfoList : list[TargetInfo]):
        gameFrozen_none = []
        gameFrozen_map = 0
        dungState = None
        shouldRecover = False
        waitTimer = time.time()
        needRecoverBecauseCombat = False
        needRecoverBecauseChest = False

        nonlocal runtimeContext
        runtimeContext.TASK_STEP_INDEX = 0
        def TargetPointComplete():
            logger.info(f"任务点完成: {targetInfoList[0].target} {targetInfoList[0].roi}")
            targetInfoList.pop(0)
            runtimeContext.TASK_STEP_INDEX += 1
            return
        
        runtimeContext.NEED_RECOVER_WHEN_BEGINNING = True
        runtimeContext.STRATEGY_RESET_EACH_DUNGEON = copy.deepcopy(runtimeContext.STRATEGY_RESET_EACH_RESTART)
        
        ##############################################
        while 1:
            logger.info("----------------------")
            if setting._FORCESTOPING.is_set():
                logger.info(_("即将停止脚本..."))
                dungState = DungeonState.Quit
            logger.info(_("当前状态(地下城): {a}".format(a=dungState)))

            match dungState:
                case None:
                    s, dungState,scn = IdentifyState()
                    if (s == State.Inn) or (dungState == DungeonState.Quit):
                        break
                    gameFrozen_none, result = GameFrozenCheck(gameFrozen_none,scn)
                    if result:
                        logger.info(_("由于画面卡死, 在state:None中重启."))
                        restartGame()
                    MAXTIMEOUT = 400
                    if (runtimeContext._TIME_CHEST != 0 ) and (time.time()-runtimeContext._TIME_CHEST > MAXTIMEOUT):
                        logger.info(_("由于宝箱用时过久, 在state:None中重启."))
                        restartGame()
                    if (runtimeContext._TIME_COMBAT != 0) and (time.time()-runtimeContext._TIME_COMBAT > MAXTIMEOUT):
                        logger.info(_("由于战斗用时过久, 在state:None中重启."))
                        restartGame()
                case DungeonState.Quit:
                    break
                case DungeonState.Dungeon:
                    Press([1,1])
                    ########### COMBAT RESET
                    # 战斗结束了, 我们将一些设置复位
                    runtimeContext.COMBAT_RESET = True
                    ########### TIMER
                    if (runtimeContext._TIME_CHEST !=0) or (runtimeContext._TIME_COMBAT!=0):
                        spend_on_chest = 0
                        if runtimeContext._TIME_CHEST !=0:
                            spend_on_chest = time.time()-runtimeContext._TIME_CHEST
                            runtimeContext._TIME_CHEST = 0
                        spend_on_combat = 0
                        if runtimeContext._TIME_COMBAT !=0:
                            spend_on_combat = time.time()-runtimeContext._TIME_COMBAT
                            runtimeContext._TIME_COMBAT = 0
                        logger.info(f"粗略统计: 宝箱{spend_on_chest:.2f}秒, 战斗{spend_on_combat:.2f}秒.")
                        if (spend_on_chest!=0) and (spend_on_combat!=0):
                            if spend_on_combat>spend_on_chest:
                                runtimeContext._TIME_COMBAT_TOTAL = runtimeContext._TIME_COMBAT_TOTAL + spend_on_combat-spend_on_chest
                                runtimeContext._TIME_CHEST_TOTAL = runtimeContext._TIME_CHEST_TOTAL + spend_on_chest
                            else:
                                runtimeContext._TIME_CHEST_TOTAL = runtimeContext._TIME_CHEST_TOTAL + spend_on_chest-spend_on_combat
                                runtimeContext._TIME_COMBAT_TOTAL = runtimeContext._TIME_COMBAT_TOTAL + spend_on_combat
                        else:
                            runtimeContext._TIME_COMBAT_TOTAL = runtimeContext._TIME_COMBAT_TOTAL + spend_on_combat
                            runtimeContext._TIME_CHEST_TOTAL = runtimeContext._TIME_CHEST_TOTAL + spend_on_chest
                    ########### RECOVER
                    if needRecoverBecauseChest:
                        logger.info(_("进行开启宝箱后的恢复."))
                        runtimeContext._COUNTERCHEST+=1
                        needRecoverBecauseChest = False
                        runtimeContext._MEET_CHEST_OR_COMBAT = True
                        if not setting.SKIP_CHEST_RECOVER:
                            logger.info(_("由于面板配置, 进行开启宝箱后恢复."))
                            shouldRecover = True
                        else:
                            logger.info(_("由于面板配置, 跳过了开启宝箱后恢复."))
                    if needRecoverBecauseCombat:
                        runtimeContext._COUNTERCOMBAT+=1
                        needRecoverBecauseCombat = False
                        runtimeContext._MEET_CHEST_OR_COMBAT = True
                        if (not setting.SKIP_COMBAT_RECOVER):
                            logger.info(_("由于面板配置, 进行战后恢复."))
                            shouldRecover = True
                        else:
                            logger.info(_("由于面板配置, 跳过了战后后恢复."))
                    if setting.RECOVER_WHEN_BEGINNING and runtimeContext.NEED_RECOVER_WHEN_BEGINNING:
                        shouldRecover = True
                        runtimeContext.NEED_RECOVER_WHEN_BEGINNING = False
                        logger.info(_("由于面板配置, 在刚进入地下城时进行恢复."))
                    if runtimeContext._RECOVERAFTERREZ == True:
                        shouldRecover = True
                        runtimeContext._RECOVERAFTERREZ = False
                    if shouldRecover:
                        Press([1,1])
                        counter_trychar = -1
                        while 1:
                            counter_trychar += 1
                            scn=ScreenShot()
                            if (CheckIf(scn,"dungflag") and not CheckIf(scn,"mapFlag")) and (counter_trychar <=30):
                                Press([36+(counter_trychar%3)*286,1425])
                                Sleep(2)
                                continue
                            elif CheckIf(scn:=ScreenShot(),"trait"):
                                if CheckIf(scn,"story", [[676,800,220,108]]):
                                    Press([725,850])
                                else:
                                    Press([830,850])
                                Sleep(1)
                                FindCoordsOrElseExecuteFallbackAndWait(["recover","combatActive",],[833,843],1)
                                if CheckIf(ScreenShot(),"recover"):
                                    Sleep(1.5)
                                    Press([600,1200])
                                    Sleep(1)
                                    for underscore in range(5):
                                        t = time.time()
                                        PressReturn()
                                        if time.time()-t<0.3:
                                            Sleep(0.3-(time.time()-t))
                                    shouldRecover = False
                                    break
                            else:
                                logger.info(_("自动回复异常, 中止本次回复."))
                                break
                    ########### 防止卡空气墙
                    if not runtimeContext._STEPAFTERRESTART:
                        logger.info("防止卡空气墙, 右转后左右走.")
                        DeviceShell(f"input swipe 300 950 600 950")
                        Sleep(1)
                        Press([27,950])
                        Sleep(1)
                        Press([853,950])

                        runtimeContext._STEPAFTERRESTART = True
                    ########### 尝试resume
                    not_moving = False
                    if runtimeContext._RESUMEAVAILABLE and Press(CheckIf(ScreenShot(),"resume")):
                        logger.info(_("resume可用. 使用resume."))
                        lastscreen = ScreenShot()
                        for counter in range(30):
                            Sleep(3)
                            underscore, dungState,screen = IdentifyState()
                            if dungState != DungeonState.Dungeon:
                                logger.info(_("已退出移动状态. 当前状态为{a}.".format(a=dungState)))
                                not_moving = True
                            elif lastscreen is not None:
                                gray1 = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
                                gray2 = cv2.cvtColor(lastscreen, cv2.COLOR_BGR2GRAY)
                                mean_diff = cv2.absdiff(gray1, gray2).mean()/255
                                logger.debug(f"移动停止检查:{mean_diff:.2f}")
                                if mean_diff < 0.1:
                                    runtimeContext._RESUMEAVAILABLE = False
                                    logger.info(_("已退出移动状态. 当前状态为{a}.".format(a=dungState)))
                                    not_moving = True
                                lastscreen = screen
                            if counter == 29:
                                # 转圈可能 重启.
                                restartGame()
                            if not_moving:
                                break
                    ########### 如果resume失败且为退出:
                    if dungState == DungeonState.Quit:
                        break
                    ########### 如果resume失败且为地下城
                    if dungState == DungeonState.Dungeon:
                        dungState = DungeonState.Map
                case DungeonState.Map:
                    ########### 不打开地图, 执行自动任务
                    def startAuto():
                        for tar in ["chest_auto","mark_auto"]:
                            if targetInfoList[0] and (targetInfoList[0].target == tar):                        
                                lastscreen = ScreenShot()
                                if not Press(CheckIf(lastscreen,tar,[[720,250,150,180]])):
                                    Press(CheckIf(lastscreen,"mapflag"))
                                    Press([762,346]) # 认为是没有展开菜单
                                    Sleep(1)
                                    lastscreen = ScreenShot()
                                    if not Press(CheckIf(lastscreen,tar,[[720,250,150,180]])):
                                        return None # 如果我们两次检测失败, 认为发生了异常
                                
                                if tar == "chest_auto":
                                    if not CheckIf(MinusImage(lastscreen,90,90,90),"chest_auto_minus",[[811,340, 41, 30]]): # 精确匹配按钮是否可用
                                        logger.info('宝箱按钮不可用.')
                                        return DungeonState.Dungeon
                                    lastscreen = ScreenShot()
                                    if CheckIf(lastscreen,"NoChestCanBeFound") or CheckIf(lastscreen,"theRouteToTheDestinationCannotBeFound"):
                                        TargetPointComplete()
                                        logger.info(_("退出宝箱搜索."))
                                        return DungeonState.Dungeon
                                    lastscreen = ScreenShot()
                                    if CheckIf(lastscreen,"NoChestCanBeFound") or CheckIf(lastscreen,"theRouteToTheDestinationCannotBeFound"):
                                        TargetPointComplete()
                                        logger.info(_("退出宝箱搜索."))
                                        return DungeonState.Dungeon

                                Sleep(1)
                                Press(CheckIf(lastscreen,"resume")) # 立刻按一次resume 以兼容暴风雪场景.
                                return StateMoving_CheckFrozen()
                            
                        return DungeonState.Dungeon

                    dungState = startAuto()
                    if dungState == None:
                        # 如果状态无效, 直接进入下一轮.
                        continue
                    ########### 不是自动任务, 开始搜索

                    Sleep(1)
                    Press([777,150])
                    Sleep(1)

                    dungState, ifTargetPointComplete = StateSearch(waitTimer,targetInfoList[0])

                    if ifTargetPointComplete:
                        TargetPointComplete()
                    
                    if not ifTargetPointComplete:
                        gameFrozen_map +=1
                        logger.info(_("地图卡死检测:{a}".format(a=gameFrozen_map)))
                    else:
                        gameFrozen_map = 0
                    if gameFrozen_map > 50:
                        gameFrozen_map = 0
                        restartGame()

                    if (targetInfoList==None) or (targetInfoList == []):
                        logger.info(_("地下城目标完成. 地下城状态结束.(仅限任务模式.)"))
                        break

                case DungeonState.Chest:
                    needRecoverBecauseChest = True
                    dungState = StateChest()
                case DungeonState.Combat:
                    needRecoverBecauseCombat =True
                    StateCombat()
                    dungState = None
    def StateAcceptRequest(request: str, pressbias:list = [0,0]):
        FindCoordsOrElseExecuteFallbackAndWait("Inn",[1,1],1)
        StateInn()
        Press(FindCoordsOrElseExecuteFallbackAndWait("guildRequest",["guild",[1,1]],1))
        Press(FindCoordsOrElseExecuteFallbackAndWait("guildFeatured",["guildRequest",[1,1]],1))
        for underscore in range(3):
            Sleep(1)
            DeviceShell(f"input swipe 150 1000 150 200")
        Sleep(2)
        pos = FindCoordsOrElseExecuteFallbackAndWait(request,["input swipe 150 200 150 250",[1,1]],1)
        if not CheckIf(ScreenShot(),"request_accepted",[[0,pos[1]-200,900,pos[1]+200]]):
            FindCoordsOrElseExecuteFallbackAndWait(["Inn","guildRequest"],[[pos[0]+pressbias[0],pos[1]+pressbias[1]],"return",[1,1]],1)
            FindCoordsOrElseExecuteFallbackAndWait("Inn",["return",[1,1]],1)
        else:
            logger.info(_("奇怪, 任务怎么已经接了."))
            FindCoordsOrElseExecuteFallbackAndWait("Inn",["return",[1,1]],1)

    def DungeonFarm():
        nonlocal runtimeContext
        state = None
        while 1:
            logger.info("======================")
            Sleep(1)
            if setting._FORCESTOPING.is_set():
                logger.info(_("即将停止脚本..."))
                break
            logger.info(_("当前状态: {a}".format(a=state)))
            match state:
                case None:
                    def _identifyState():
                        nonlocal state
                        state=IdentifyState()[0]
                    RestartableSequenceExecution(
                        lambda: _identifyState()
                        )
                    logger.info(_("下一状态: {a}".format(a=state)))
                    if state ==State.Quit:
                        logger.info(_("即将停止脚本..."))
                        break
                case State.Inn:
                    if not runtimeContext._MEET_CHEST_OR_COMBAT:
                        logger.info(_("因为没有遇到战斗或宝箱, 跳过住宿."))
                    elif not setting.ACTIVE_REST:
                        logger.info(_("因为面板设置, 跳过住宿."))
                    elif ((runtimeContext._COUNTERDUNG-1) % (max(setting.REST_INTERVEL,1)) != 0):
                        logger.info(_("还有许多地下城要刷. 面具男, 现在还不能休息哦."))
                    else:
                        logger.info(_("休息时间到!"))
                        RestartableSequenceExecution(
                        lambda:StateInn()
                        )
                    state = State.EoT
                case State.EoT:
                    DungeonCompletionCounter()
                    RestartableSequenceExecution(
                        lambda:StateEoT()
                        )
                    state = State.Dungeon
                case State.Dungeon:
                    # 首次进入地下城
                    targetInfoList = quest._TARGETINFOLIST.copy()
                    RestartableSequenceExecution(
                        lambda: StateDungeon(targetInfoList)
                        )
                    state = None
        setting._FINISHINGCALLBACK()
    def QuestFarm():
        nonlocal setting # 强制自动战斗 等等.
        nonlocal runtimeContext
        match setting.FARM_TARGET:
            case "7000G":
                while 1:
                    if setting._FORCESTOPING.is_set():
                        break

                    starttime = time.time()
                    runtimeContext._COUNTERDUNG += 1

                    logger.info(_("第一步: 时间跳跃..."))
                    RestartableSequenceExecution(    
                        lambda: CursedWheelTimeLeap(target="FortressArrival",chapter = "cursedwheel_impregnableFortress")
                        )

                    Sleep(10)
                    logger.info(_("第二步: 返回要塞..."))
                    RestartableSequenceExecution(
                        lambda: FindCoordsOrElseExecuteFallbackAndWait("Inn",["returntotown","returnText","leaveDung","blessing",[1,1]],2)
                        )

                    logger.info(_("第三步: 前往王城..."))
                    RestartableSequenceExecution(
                        lambda:TeleportFromCityToWorldLocation("City_RoyalCityLuknalia", "input swipe 450 150 500 150"),
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("guild",["City_RoyalCityLuknalia",[1,1]],1),
                        )

                    logger.info(_("第四步: 给我!(伸手)"))
                    stepMark = -1
                    def stepMain():
                        nonlocal stepMark
                        if stepMark == -1:
                            Press(FindCoordsOrElseExecuteFallbackAndWait("guild",[1,1],1))
                            Press(FindCoordsOrElseExecuteFallbackAndWait("7000G/illgonow",[1,1],1))
                            Sleep(15)
                            FindCoordsOrElseExecuteFallbackAndWait(["7000G/olddist","7000G/iminhungry"],[1,1],2)
                            if pos:=CheckIf(scn:=ScreenShot(),"7000G/olddist"):
                                Press(pos)
                            else:
                                Press(CheckIf(scn,"7000G/iminhungry"))
                                Press(FindCoordsOrElseExecuteFallbackAndWait("7000G/olddist",[1,1],2))
                            stepMark = 0
                        if stepMark == 0:
                            Sleep(4)
                            Press([1,1])
                            Press([1,1])
                            Sleep(8)
                            Press(FindCoordsOrElseExecuteFallbackAndWait("7000G/royalcapital",[1,1],2))
                            FindCoordsOrElseExecuteFallbackAndWait("intoWorldMap",[1,1],2)
                            stepMark = 1
                        if stepMark == 1:
                            FindCoordsOrElseExecuteFallbackAndWait("fastforward",[450,1111],0)
                            FindCoordsOrElseExecuteFallbackAndWait("intoWorldMap",["7000G/why",[1,1]],2)
                            stepMark = 2
                        if stepMark == 2:
                            FindCoordsOrElseExecuteFallbackAndWait("fastforward",[200,1180],0)
                            FindCoordsOrElseExecuteFallbackAndWait("intoWorldMap",["7000G/why",[1,1]],2)
                            stepMark = 3
                        if stepMark == 3:
                            FindCoordsOrElseExecuteFallbackAndWait("fastforward",[680,1200],0)
                            Press(FindCoordsOrElseExecuteFallbackAndWait("7000G/leavethechild",["7000G/why",[1,1]],2))
                            stepMark = 4
                        if stepMark == 4:
                            Press(FindCoordsOrElseExecuteFallbackAndWait("7000G/icantagreewithU",[1,1],1))
                            stepMark = 5
                        if stepMark == 5:
                            Press(FindCoordsOrElseExecuteFallbackAndWait("7000G/illgo",[[1,1],"7000G/olddist"],1))
                            Press(FindCoordsOrElseExecuteFallbackAndWait("7000G/noeasytask",[1,1],1))
                            FindCoordsOrElseExecuteFallbackAndWait("ruins",[1,1],1)
                    RestartableSequenceExecution(
                        lambda: stepMain()
                        )
                    costtime = time.time()-starttime
                    logger.info(_("第{a}次\"7000G\"完成. 该次花费时间{b:.2f}, 每秒收益:{c:.2f}Gps.".format(a=runtimeContext._COUNTERDUNG, b=costtime, c=7000/costtime)),
                                extra={"summary": True})
            case "fordraig":
                quest._SPECIALDIALOGOPTION = ["fordraig/thedagger","fordraig/InsertTheDagger"]
                while 1:
                    if setting._FORCESTOPING.is_set():
                        break
                    runtimeContext._COUNTERDUNG += 1
                    setting._SYSTEMAUTOCOMBAT = True
                    starttime = time.time()
                    logger.info(_("第一步: 诅咒之旅..."))
                    RestartableSequenceExecution(
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("cursedWheel",["ruins",[1,1]],1)),
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("Fordraig/Leap",["specialRequest",[1,1]],1)),
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("OK","leap",1)),
                        )
                    Sleep(15)

                    RestartableSequenceExecution(
                        lambda: logger.info(_("第二步: 领取任务.")),
                        lambda: StateAcceptRequest("fordraig/RequestAccept",[350,180])
                        )

                    logger.info(_("第三步: 进入地下城."))
                    TeleportFromCityToWorldLocation("fordraig/labyrinthOfFordraig","input swipe 450 150 500 150")
                    Press(FindCoordsOrElseExecuteFallbackAndWait("fordraig/Entrance",["fordraig/labyrinthOfFordraig",[1,1]],1))
                    FindCoordsOrElseExecuteFallbackAndWait("dungFlag",["fordraig/Entrance","GotoDung",[1,1]],1)

                    logger.info(_("第四步: 陷阱."))
                    RestartableSequenceExecution(
                        lambda:StateDungeon([
                            TargetInfo("position","左上",[721,448]),
                            TargetInfo("position","左上",[720,608])]), # 前往第一个陷阱
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("dungFlag","return",1), # 关闭地图
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("fordraig/TryPushingIt",["input swipe 100 250 800 250",[400,800],[400,800],[400,800]],1)), # 转向来开启机关
                        )
                    logger.info("已完成第一个陷阱.")

                    RestartableSequenceExecution(
                        lambda:StateDungeon([
                            TargetInfo("stair_down","左上",[721,236]),
                            TargetInfo("position","左下", [240,921])]), #前往第二个陷阱
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("dungFlag","return",1), # 关闭地图
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("fordraig/TryPushingIt",["input swipe 100 250 800 250",[400,800],[400,800],[400,800]],1)), # 转向来开启机关
                        )
                    logger.info(_("已完成第二个陷阱."))

                    RestartableSequenceExecution(
                        lambda:StateDungeon([
                            TargetInfo("position","左下",[33,1238]),
                            TargetInfo("stair_down","左下",[453,1027]),
                            TargetInfo("position","左下",[187,1027]),
                            TargetInfo("stair_teleport","左下",[80,1026])
                            ]), #前往第三个陷阱
                        )
                    logger.info(_("已完成第三个陷阱."))

                    StateDungeon([TargetInfo("position","左下",[508,1025])]) # 前往boss战门前
                    setting._SYSTEMAUTOCOMBAT = False
                    StateDungeon([TargetInfo("position","左下",[720,1025])]) # 前往boss战斗
                    setting._SYSTEMAUTOCOMBAT = True
                    StateDungeon([TargetInfo("stair_teleport","左上",[665,395])]) # 第四层出口
                    FindCoordsOrElseExecuteFallbackAndWait("dungFlag","return",1)
                    Press(FindCoordsOrElseExecuteFallbackAndWait("ReturnText",["leaveDung",[455,1200]],3.75)) # 回城
                    # 3.75什么意思 正常循环是3秒 有4次尝试机会 因此3.75秒按一次刚刚好.
                    Press(FindCoordsOrElseExecuteFallbackAndWait("City_RoyalCityLuknalia",["return",[1,1]],1)) # 回城
                    FindCoordsOrElseExecuteFallbackAndWait("Inn",[1,1],1)

                    costtime = time.time()-starttime
                    logger.info(_("第{a}次\"鸟剑\"完成. 该次花费时间{b:.2f}.".format(a=runtimeContext._COUNTERDUNG, b=costtime)),
                            extra={"summary": True})
            case "repelEnemyForces":
                if not setting.ACTIVE_REST:
                    logger.info(_("注意, \"休息间隔\"控制连续战斗多少次后回城. 当前未启用休息, 强制设置为1."))
                    setting.REST_INTERVEL = 1
                if setting.REST_INTERVEL == 0:
                    logger.info(_("注意, \"休息间隔\"控制连续战斗多少次后回城. 当前值0为无效值, 最低为1."))
                    setting.REST_INTERVEL = 1
                logger.info(_("注意, 该流程不包括时间跳跃和接取任务, 请确保接取任务后再开启!"))
                counter = 0
                while 1:
                    if setting._FORCESTOPING.is_set():
                        break
                    t = time.time()
                    RestartableSequenceExecution(
                        lambda : StateInn()
                    )
                    RestartableSequenceExecution(
                        lambda : Press(FindCoordsOrElseExecuteFallbackAndWait("TradeWaterway","EdgeOfTown",1)),
                        lambda : FindCoordsOrElseExecuteFallbackAndWait("7thDist",[1,1],1),
                        lambda : FindCoordsOrElseExecuteFallbackAndWait("dungFlag",["7thDist","GotoDung",[1,1]],1),
                    )
                    RestartableSequenceExecution(
                        lambda : StateDungeon([TargetInfo("position","左下",[559,599]),
                                               TargetInfo("position","左下",[186,813])])
                    )
                    logger.info(_("已抵达目标地点, 开始战斗."))
                    FindCoordsOrElseExecuteFallbackAndWait("dungFlag",["return",[1,1]],1)
                    for i in range(setting.REST_INTERVEL):
                        logger.info(_("第{a}轮开始.".format(a=i+1)))
                        secondcombat = False
                        while 1:
                            Press(FindCoordsOrElseExecuteFallbackAndWait(["icanstillgo","combatActive"],["input swipe 400 400 400 100",[1,1]],1))
                            Sleep(1)
                            if setting._AOE_ONCE:
                                runtimeContext._ENOUGH_AOE = False
                                runtimeContext._AOE_CAST_TIME = 0
                            while 1:
                                scn=ScreenShot()
                                if TryPressRetry(scn):
                                    continue
                                if CheckIf(scn,"icanstillgo"):
                                    break
                                if StateCombatCheck(scn):
                                    StateCombat()
                                else:
                                    Press([1,1])
                            if not secondcombat:
                                logger.info(_("第1场战斗结束."))
                                secondcombat = True
                                Press(CheckIf(ScreenShot(),"icanstillgo"))
                            else:
                                logger.info(_("第2场战斗结束."))
                                Press(CheckIf(ScreenShot(),"letswithdraw"))
                                Sleep(1)
                                break
                        logger.info(_("第{a}轮结束.".format(a=i+1)))
                    RestartableSequenceExecution(
                        lambda:StateDungeon([TargetInfo("position","左上",[612,448])])
                    )
                    RestartableSequenceExecution(
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("returnText",[[1,1],"leaveDung","return"],3))
                    )
                    RestartableSequenceExecution(
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("Inn",["return",[1,1]],1)
                    )
                    counter+=1
                    logger.info(_("第{a}x{b}轮\"击退敌势力\"完成, 共计{c}场战斗. 该次花费时间{c:.2f}秒.".format(a=counter, b=setting.REST_INTERVEL, c=counter*setting.REST_INTERVEL*2), c=(time.time()-t)),
                                    extra={"summary": True})
            case "darkLight":
                gameFrozen_none = []
                dungState = None
                shouldRecover = False
                needRecoverBecauseCombat = False
                needRecoverBecauseChest = False
                while 1:
                    underscore, dungState,underscore = IdentifyState()
                    logger.info(dungState)
                    match dungState:
                        case None:
                            s, dungState,scn = IdentifyState()
                            if (s == State.Inn) or (dungState == DungeonState.Quit):
                                break
                            gameFrozen_none, result = GameFrozenCheck(gameFrozen_none,scn)
                            if result:
                                logger.info(_("由于画面卡死, 在state:None中重启."))
                                restartGame()
                            MAXTIMEOUT = 400
                            if (runtimeContext._TIME_CHEST != 0 ) and (time.time()-runtimeContext._TIME_CHEST > MAXTIMEOUT):
                                logger.info(_("由于宝箱用时过久, 在state:None中重启."))
                                restartGame()
                            if (runtimeContext._TIME_COMBAT != 0) and (time.time()-runtimeContext._TIME_COMBAT > MAXTIMEOUT):
                                logger.info(_("由于战斗用时过久, 在state:None中重启."))
                                restartGame()
                        case DungeonState.Dungeon:
                            Press([1,1])
                            ########### COMBAT RESET
                            # 战斗结束了, 我们将一些设置复位
                            if setting._AOE_ONCE:
                                runtimeContext._ENOUGH_AOE = False
                                runtimeContext._AOE_CAST_TIME = 0
                            ########### TIMER
                            if (runtimeContext._TIME_CHEST !=0) or (runtimeContext._TIME_COMBAT!=0):
                                spend_on_chest = 0
                                if runtimeContext._TIME_CHEST !=0:
                                    spend_on_chest = time.time()-runtimeContext._TIME_CHEST
                                    runtimeContext._TIME_CHEST = 0
                                spend_on_combat = 0
                                if runtimeContext._TIME_COMBAT !=0:
                                    spend_on_combat = time.time()-runtimeContext._TIME_COMBAT
                                    runtimeContext._TIME_COMBAT = 0
                                logger.info(f"粗略统计: 宝箱{spend_on_chest:.2f}秒, 战斗{spend_on_combat:.2f}秒.")
                                if (spend_on_chest!=0) and (spend_on_combat!=0):
                                    if spend_on_combat>spend_on_chest:
                                        runtimeContext._TIME_COMBAT_TOTAL = runtimeContext._TIME_COMBAT_TOTAL + spend_on_combat-spend_on_chest
                                        runtimeContext._TIME_CHEST_TOTAL = runtimeContext._TIME_CHEST_TOTAL + spend_on_chest
                                    else:
                                        runtimeContext._TIME_CHEST_TOTAL = runtimeContext._TIME_CHEST_TOTAL + spend_on_chest-spend_on_combat
                                        runtimeContext._TIME_COMBAT_TOTAL = runtimeContext._TIME_COMBAT_TOTAL + spend_on_combat
                                else:
                                    runtimeContext._TIME_COMBAT_TOTAL = runtimeContext._TIME_COMBAT_TOTAL + spend_on_combat
                                    runtimeContext._TIME_CHEST_TOTAL = runtimeContext._TIME_CHEST_TOTAL + spend_on_chest
                            ########### RECOVER
                            if needRecoverBecauseChest:
                                logger.info(_("进行开启宝箱后的恢复."))
                                runtimeContext._COUNTERCHEST+=1
                                needRecoverBecauseChest = False
                                runtimeContext._MEET_CHEST_OR_COMBAT = True
                                if not setting.SKIP_CHEST_RECOVER:
                                    logger.info(_("由于面板配置, 进行开启宝箱后恢复."))
                                    shouldRecover = True
                                else:
                                    logger.info(_("由于面板配置, 跳过了开启宝箱后恢复."))
                            if needRecoverBecauseCombat:
                                runtimeContext._COUNTERCOMBAT+=1
                                needRecoverBecauseCombat = False
                                runtimeContext._MEET_CHEST_OR_COMBAT = True
                                if (not setting.SKIP_COMBAT_RECOVER):
                                    logger.info(_("由于面板配置, 进行战后恢复."))
                                    shouldRecover = True
                                else:
                                    logger.info(_("由于面板配置, 跳过了战后后恢复."))
                            if shouldRecover:
                                Press([1,1])
                                FindCoordsOrElseExecuteFallbackAndWait( # 点击打开人物面板有可能会被战斗打断
                                    ["trait","combatActive","chestFlag","combatClose"],
                                    [[36,1425],[322,1425],[606,1425]],
                                    1
                                    )
                                if CheckIf(ScreenShot(),"trait"):
                                    Press([833,843])
                                    Sleep(1)
                                    FindCoordsOrElseExecuteFallbackAndWait(
                                        ["recover","combatActive"],
                                        [833,843],
                                        1
                                        )
                                    if CheckIf(ScreenShot(),"recover"):
                                        Sleep(1)
                                        Press([600,1200])
                                        for underscore in range(5):
                                            t = time.time()
                                            PressReturn()
                                            if time.time()-t<0.3:
                                                Sleep(0.3-(time.time()-t))
                                        shouldRecover = False
                            ########### light the dark light
                            Press(FindCoordsOrElseExecuteFallbackAndWait("darklight_lightIt","darkLight",1))
                        case DungeonState.Chest:
                            needRecoverBecauseChest = True
                            dungState = StateChest()
                        case DungeonState.Combat:
                            needRecoverBecauseCombat =True
                            StateCombat()
                            dungState = None
            case "LBC-oneGorgon":
                while 1:
                    if setting._FORCESTOPING.is_set():
                        break
                    if runtimeContext._LAPTIME!= 0:
                        runtimeContext._TOTALTIME = runtimeContext._TOTALTIME + time.time() - runtimeContext._LAPTIME
                        logger.info(_("第{a}次三牛完成. 本次用时:{b}秒. 累计开箱子{c}, 累计战斗{d}, 累计用时{e}秒.".format(a=runtimeContext._COUNTERDUNG, b=round(time.time()-runtimeContext._LAPTIME,2),c=runtimeContext._COUNTERCHEST, d=runtimeContext._COUNTERCOMBAT, e=round(runtimeContext._TOTALTIME,2))),
                                    extra={"summary": True})
                    runtimeContext._LAPTIME = time.time()
                    runtimeContext._COUNTERDUNG+=1

                    RestartableSequenceExecution(
                        lambda: logger.info(_("第一步: 重置因果")),
                        lambda: CursedWheelTimeLeap("GhostsOfYore","LBC/symbolofalliance",[["LBC/EnaWasSaved",2,1,0]])
                        )
                    Sleep(10)
                    RestartableSequenceExecution(
                        lambda: logger.info(_("第二步: 返回要塞")),
                        lambda: FindCoordsOrElseExecuteFallbackAndWait("Inn",["returntotown","returnText","leaveDung","blessing",[1,1]],2)
                        )
                    RestartableSequenceExecution(
                        lambda: logger.info(_("第三步: 前往王城")),
                        lambda: TeleportFromCityToWorldLocation("City_RoyalCityLuknalia","input swipe 450 150 500 150"),
                        lambda: FindCoordsOrElseExecuteFallbackAndWait("guild",["City_RoyalCityLuknalia",[1,1]],1),
                        )
               
                    RestartableSequenceExecution(
                        lambda: logger.info(_("第四步: 领取任务")),
                        lambda: StateAcceptRequest("LBC/Request",[266,257]),
                    )
                    RestartableSequenceExecution(
                        lambda: logger.info(_("第五步: 进入牛洞")),
                        lambda: TeleportFromCityToWorldLocation("LBC/LBC","input swipe 400 400 400 500")
                        )

                    Gorgon1 = TargetInfo("position","左上",[134,342])
                    Gorgon2 = TargetInfo("position","右上",[500,395])
                    Gorgon3 = TargetInfo("position","右下",[340,1027])
                    LBC_quit = TargetInfo("LBC/LBC_quit")
                    if setting.ACTIVE_REST:
                        RestartableSequenceExecution(
                            lambda: logger.info(_("第六步: 击杀一牛")),
                            lambda: StateDungeon([Gorgon1,LBC_quit])
                            )
                        RestartableSequenceExecution(
                            lambda: logger.info(_("第七步: 回去睡觉")),
                            lambda: StateInn()
                            )
                        RestartableSequenceExecution(
                            lambda: logger.info(_("第八步: 再入牛洞")),
                            lambda: TeleportFromCityToWorldLocation("LBC/LBC","input swipe 400 400 400 500")
                            )
                        RestartableSequenceExecution(
                            lambda: logger.info(_("第九步: 击杀二牛")),
                            lambda: StateDungeon([Gorgon2,Gorgon3,LBC_quit])
                            )
                    else:
                        logger.info("跳过回城休息.")
                        RestartableSequenceExecution(
                            lambda: logger.info(_("第六步: 连杀三牛")),
                            lambda: StateDungeon([Gorgon1,Gorgon2,Gorgon3,LBC_quit])
                            )
            case "SSC-goldenchest":
                while 1:
                    quest._SPECIALDIALOGOPTION = ["SSC/dotdotdot","SSC/shadow"]
                    if setting._FORCESTOPING.is_set():
                        break
                    if runtimeContext._LAPTIME!= 0:
                        runtimeContext._TOTALTIME = runtimeContext._TOTALTIME + time.time() - runtimeContext._LAPTIME
                        logger.info(_("第{a}次忍洞完成. 本次用时:{b}秒. 累计开箱子{c}, 累计战斗{d}, 累计用时{e}秒.".format(a=runtimeContext._COUNTERDUNG, b=round(time.time()-runtimeContext._LAPTIME,2),c=runtimeContext._COUNTERCHEST, d=runtimeContext._COUNTERCOMBAT, e=round(runtimeContext._TOTALTIME,2))),
                                    extra={"summary": True})
                    runtimeContext._LAPTIME = time.time()
                    runtimeContext._COUNTERDUNG+=1
                    RestartableSequenceExecution(
                        lambda: logger.info(_("第一步: 重置因果")),
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("cursedWheel",["ruins",[1,1]],1)),
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("SSC/Leap",["specialRequest",[1,1]],1)),
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("OK","leap",1)),
                        )
                    Sleep(10)
                    RestartableSequenceExecution(
                        lambda: logger.info(_("第二步: 前往王城")),
                        lambda: TeleportFromCityToWorldLocation("City_RoyalCityLuknalia","input swipe 450 150 500 150"),
                        lambda: FindCoordsOrElseExecuteFallbackAndWait("guild",["City_RoyalCityLuknalia",[1,1]],1),
                        )
                    def stepThree():
                        FindCoordsOrElseExecuteFallbackAndWait("Inn",[1,1],1)
                        StateInn()
                        Press(FindCoordsOrElseExecuteFallbackAndWait("guildRequest",["guild",[1,1]],1))
                        Press(FindCoordsOrElseExecuteFallbackAndWait("guildFeatured",["guildRequest",[1,1]],1))
                        Sleep(1)
                        DeviceShell(f"input swipe 150 1300 150 200")
                        Sleep(2)
                        while 1:
                            pos = CheckIf(ScreenShot(),"SSC/Request")
                            if not pos:
                                DeviceShell(f"input swipe 150 200 150 250")
                                Sleep(1)
                            else:
                                Press([pos[0]+300,pos[1]+150])
                                break
                        FindCoordsOrElseExecuteFallbackAndWait("guildRequest",[1,1],1)
                        PressReturn()
                    RestartableSequenceExecution(
                        lambda: logger.info(_("第三步: 领取任务")),
                        lambda: stepThree()
                        )

                    RestartableSequenceExecution(
                        lambda: logger.info(_("第四步: 进入忍洞")),
                        lambda: TeleportFromCityToWorldLocation("SSC/SSC","input swipe 700 500 600 600")
                        )
                    RestartableSequenceExecution(
                        lambda: logger.info(_("第五步: 关闭陷阱")),
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("SSC/trapdeactived",["input swipe 450 1050 450 850",[445,721]],4),
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("dungFlag",[1,1],1)
                    )
                    quest._SPECIALDIALOGOPTION = ["SSC/dotdotdot","SSC/shadow"]
                    RestartableSequenceExecution(
                        lambda: logger.info(_("第六步: 第一个箱子")),
                        lambda: StateDungeon([
                                TargetInfo("position",     "左上", [719,1088]),
                                TargetInfo("position",     "左上", [346,874]),
                                TargetInfo("chest",        "左上", [[0,0,900,1600],[640,0,260,1600],[506,0,200,700]]),
                                TargetInfo("chest",        "右上", [[0,0,900,1600],[0,0,407,1600]]),
                                TargetInfo("chest",        "右下", [[0,0,900,1600],[0,0,900,800]]),
                                TargetInfo("chest",        "左下", [[0,0,900,1600],[650,0,250,811],[507,166,179,165]]),
                                TargetInfo("SSC/SSC_quit", "右下", None)
                            ])
                        )
            case "CaveOfSeperation":
                while 1:
                    if setting._FORCESTOPING.is_set():
                        break
                    if runtimeContext._LAPTIME!= 0:
                        runtimeContext._TOTALTIME = runtimeContext._TOTALTIME + time.time() - runtimeContext._LAPTIME
                        logger.info(_("第{a}次约定之剑完成. 本次用时:{b}秒. 累计开箱子{c}, 累计战斗{d}, 累计用时{e}秒.".format(a=runtimeContext._COUNTERDUNG, b=round(time.time()-runtimeContext._LAPTIME,2),c=runtimeContext._COUNTERCHEST, d=runtimeContext._COUNTERCOMBAT, e=round(runtimeContext._TOTALTIME,2))),
                                    extra={"summary": True})
                    runtimeContext._LAPTIME = time.time()
                    runtimeContext._COUNTERDUNG+=1
                    RestartableSequenceExecution(
                        lambda: logger.info(_("第一步: 重置因果")),
                        lambda: CursedWheelTimeLeap("GhostsOfYore","COS/ArnasPast")
                        )
                    Sleep(10)
                    RestartableSequenceExecution(
                        lambda: logger.info(_("第二步: 返回要塞")),
                        lambda: FindCoordsOrElseExecuteFallbackAndWait("Inn",["returntotown","returnText","leaveDung","blessing",[1,1]],2)
                        )
                    RestartableSequenceExecution(
                        lambda: logger.info(_("第三步: 前往王城)")),
                        lambda: TeleportFromCityToWorldLocation("City_RoyalCityLuknalia","input swipe 450 150 500 150"),
                        lambda: FindCoordsOrElseExecuteFallbackAndWait("guild",["City_RoyalCityLuknalia",[1,1]],1),
                        )
                    
                    RestartableSequenceExecution(
                        lambda: logger.info(_("第四步: 领取任务")),
                        lambda: FindCoordsOrElseExecuteFallbackAndWait(["COS/Okay","guildRequest"],["guild",[1,1]],1),
                        lambda: FindCoordsOrElseExecuteFallbackAndWait("Inn",["COS/Okay","return",[1,1]],1),
                        lambda: StateInn(),
                        )
                    
                    RestartableSequenceExecution(
                        lambda: logger.info(_("第五步: 进入洞窟")),
                        lambda: Press(FindCoordsOrElseExecuteFallbackAndWait("COS/COS",["EdgeOfTown",[1,1]],1)),
                        lambda: Press(FindCoordsOrElseExecuteFallbackAndWait("COS/COSENT",[1,1],1))
                        )
                    quest._SPECIALDIALOGOPTION = ["COS/takehimwithyou"]
                    cosb1f = [TargetInfo("position","右下",[286-54,440]),
                              TargetInfo("position","右下",[819,653+54]),
                              TargetInfo("position","右上",[659-54,501]),
                              TargetInfo("stair_2","右上",[126-54,342]),
                        ]
                    RestartableSequenceExecution(
                        lambda: logger.info(_("第六步: 1层找人")),
                        lambda: StateDungeon(cosb1f)
                        )

                    quest._SPECIALFORCESTOPINGSYMBOL = ["COS/EnaTheAdventurer"]
                    cosb2f = [TargetInfo("position","右上",[340+54,448]),
                              TargetInfo("position","右上",[500-54,1088]),
                              TargetInfo("position","左上",[398+54,766]),
                        ]
                    RestartableSequenceExecution(
                        lambda: logger.info(_("第七步: 2层找人")),
                        lambda: StateDungeon(cosb2f)
                        )

                    quest._SPECIALFORCESTOPINGSYMBOL = ["COS/requestwasfor"] 
                    cosb3f = [TargetInfo("stair_3","左上",[720,822]),
                              TargetInfo("position","左下",[239,600]),
                              TargetInfo("position","左下",[185,1185]),
                              TargetInfo("position","左下",[560,652]),
                              ]
                    RestartableSequenceExecution(
                        lambda: logger.info(_("第八步: 3层找人")),
                        lambda: StateDungeon(cosb3f)
                        )

                    quest._SPECIALFORCESTOPINGSYMBOL = None
                    quest._SPECIALDIALOGOPTION = ["COS/requestwasfor"] 
                    cosback2f = [
                                 TargetInfo("stair_2","左下",[827,547]),
                                 TargetInfo("position","右上",[340+54,448]),
                                 TargetInfo("position","右上",[500-54,1088]),
                                 TargetInfo("position","左上",[398+54,766]),
                                 TargetInfo("position","左上",[559,1087]),
                                 TargetInfo("stair_1","左上",[666,448]),
                                 TargetInfo("position", "右下",[660,919])
                        ]
                    RestartableSequenceExecution(
                        lambda: logger.info(_("第九步: 离开洞穴")),
                        lambda: StateDungeon(cosback2f)
                        )
                    Press(FindCoordsOrElseExecuteFallbackAndWait("guild",["return",[1,1]],1)) # 回城
                    FindCoordsOrElseExecuteFallbackAndWait("Inn",["return",[1,1]],1)
                    
                pass
            case "gaintKiller":
                while 1:
                    if setting._FORCESTOPING.is_set():
                        break
                    if runtimeContext._LAPTIME!= 0:
                        runtimeContext._TOTALTIME = runtimeContext._TOTALTIME + time.time() - runtimeContext._LAPTIME
                        logger.info(_("第{a}次巨人完成. 本次用时:{b}秒. 累计开箱子{c}, 累计战斗{d}, 累计用时{e}秒.".format(a=runtimeContext._COUNTERDUNG, b=round(time.time()-runtimeContext._LAPTIME,2),c=runtimeContext._COUNTERCHEST, d=runtimeContext._COUNTERCOMBAT, e=round(runtimeContext._TOTALTIME,2))),
                                    extra={"summary": True})
                    runtimeContext._LAPTIME = time.time()
                    runtimeContext._COUNTERDUNG+=1

                    quest._EOT = [
                        ["press","impregnableFortress",["EdgeOfTown",[1,1]],1],
                        ["press","fortressb7f",[1,1],1]]
                    RestartableSequenceExecution(
                        lambda: StateEoT()
                        )
                    
                    logger.info(_("跳过了巨人检测环节. 现在默认总是击杀灯怪."))
                    RestartableSequenceExecution(
                        lambda: StateDungeon([TargetInfo("position","左上",[560,928+54]),
                                              TargetInfo("harken2","左上")]),
                        lambda: FindCoordsOrElseExecuteFallbackAndWait("Inn",["returntotown","returnText","leaveDung","blessing",[1,1]],2)
                    )

                    if ((runtimeContext._COUNTERDUNG-1) % (setting.REST_INTERVEL+1) == 0):
                        RestartableSequenceExecution(
                            lambda: StateInn()
                        )
            case "Scorpionesses":
                total_time = 0
                while 1:
                    if setting._FORCESTOPING.is_set():
                        break

                    starttime = time.time()
                    runtimeContext._COUNTERDUNG += 1

                    if not setting.ACTIVE_BEAUTIFUL_ORE:
                        if not setting.ACTIVE_TRIUMPH:                            
                            logger.info(_("第一步: 时空跳跃..."))
                            RestartableSequenceExecution(
                                lambda: CursedWheelTimeLeap()
                            )
                            Sleep(10)
                            logger.info(_("第二步: 返回要塞..."))
                            RestartableSequenceExecution(
                                lambda: FindCoordsOrElseExecuteFallbackAndWait("Inn",["returntotown","returnText","leaveDung","blessing",[1,1]],2)
                                )
                                
                            logger.info(_("第三步: 前往王城..."))
                            RestartableSequenceExecution(
                                lambda:TeleportFromCityToWorldLocation("City_RoyalCityLuknalia","input swipe 450 150 500 150"),
                                )
                        else:
                            logger.info(_("第一步: 时空跳跃..."))
                            RestartableSequenceExecution(
                                lambda: CursedWheelTimeLeap(chapter="cursedwheel_impregnableFortress", target="Triumph")
                            )
                            Sleep(10)
                                
                            logger.info(_("第三步: 前往王城..."))
                            RestartableSequenceExecution(
                                lambda:TeleportFromCityToWorldLocation("City_RoyalCityLuknalia","input swipe 450 150 500 150"),
                                )

                    elif setting.ACTIVE_BEAUTIFUL_ORE:
                        logger.info(_("第一步: 时空跳跃..."))
                        RestartableSequenceExecution(
                            lambda: CursedWheelTimeLeap(chapter="cursedwheel_dhi", target="BeautifulOre")
                        )
                        Sleep(10)

                    logger.info(_("第四步: 悬赏揭榜"))
                    RestartableSequenceExecution(
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("guildRequest",["guild",[1,1]],1)),
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("Bounties",["guild","guildRequest","input swipe 600 1400 300 1400",[1,1]],1)),
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("EdgeOfTown",["return",[1,1]],1)
                        )

                    logger.info(_("第五步: 击杀蝎女"))
                    RestartableSequenceExecution(
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("dungFlag",["EdgeOfTown","beginningAbyss","B2FTemple","GotoDung",[1,1]],1),
                    )
                    RestartableSequenceExecution(
                        lambda:StateDungeon([TargetInfo("position","左下",[505,760]),
                                             TargetInfo("position","左上",[506,821])]),
                        )
                    
                    logger.info(_("第六步: 提交悬赏"))
                    RestartableSequenceExecution(
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("guild",["return",[1,1]],1),
                    )
                    RestartableSequenceExecution(
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("CompletionReported",["guild","guildRequest","input swipe 600 1400 300 1400","Bounties",[1,1]],1))
                        )
                    RestartableSequenceExecution(
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("EdgeOfTown",["return",[1,1]],1)
                        )
                    
                    logger.info(_("第七步: 休息"))
                    if ((runtimeContext._COUNTERDUNG-1) % (setting.REST_INTERVEL+1) == 0):
                        RestartableSequenceExecution(
                            lambda:StateInn()
                            )
                        
                    costtime = time.time()-starttime
                    total_time = total_time + costtime
                    logger.info(_("第{a}次\"悬赏:蝎女\"完成. \n该次花费时间{b:.2f}s.\n总计用时{c:.2f}s.\n平均用时{d:.2f}".format(a=runtimeContext._COUNTERDUNG,b=costtime, c=total_time, d=total_time/runtimeContext._COUNTERDUNG)),
                            extra={"summary": True})
            case "Scorpionesses_plus_6_hands":
                total_time = 0
                while 1:
                    if setting._FORCESTOPING.is_set():
                        break

                    starttime = time.time()
                    runtimeContext._COUNTERDUNG += 1

                    if not setting.ACTIVE_BEAUTIFUL_ORE:
                        if not setting.ACTIVE_TRIUMPH:                            
                            logger.info(_("第一步: 时空跳跃..."))
                            RestartableSequenceExecution(
                                lambda: CursedWheelTimeLeap()
                            )
                            Sleep(10)
                            logger.info(_("第二步: 返回要塞..."))
                            RestartableSequenceExecution(
                                lambda: FindCoordsOrElseExecuteFallbackAndWait("Inn",["returntotown","returnText","leaveDung","blessing",[1,1]],2)
                                )
                                
                            logger.info(_("第三步: 前往王城..."))
                            RestartableSequenceExecution(
                                lambda:TeleportFromCityToWorldLocation("City_RoyalCityLuknalia","input swipe 450 150 500 150"),
                                )
                        else:
                            logger.info(_("第一步: 时空跳跃..."))
                            RestartableSequenceExecution(
                                lambda: CursedWheelTimeLeap(chapter="cursedwheel_impregnableFortress", target="Triumph")
                            )
                            Sleep(10)
                                
                            logger.info(_("第三步: 前往王城..."))
                            RestartableSequenceExecution(
                                lambda:TeleportFromCityToWorldLocation("City_RoyalCityLuknalia","input swipe 450 150 500 150"),
                                )

                    elif setting.ACTIVE_BEAUTIFUL_ORE:
                        logger.info(_("第一步: 时空跳跃..."))
                        RestartableSequenceExecution(
                            lambda: CursedWheelTimeLeap(chapter="cursedwheel_dhi", target="BeautifulOre")
                        )
                        Sleep(10)

                    logger.info(_("第四步: 悬赏揭榜"))
                    RestartableSequenceExecution(
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("guildRequest",["guild",[1,1]],1)),
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("Bounties",["guild","guildRequest","input swipe 600 1400 300 1400",[1,1]],1)),
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("EdgeOfTown",["return",[1,1]],1)
                        )

                    logger.info(_("第五步: 击杀蝎女"))
                    RestartableSequenceExecution(
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("dungFlag",["EdgeOfTown","beginningAbyss","B2FTemple","GotoDung",[1,1]],1),
                    )
                    RestartableSequenceExecution(
                        lambda:StateDungeon([TargetInfo("position","左下",[505,760]),
                                             TargetInfo("position","左上",[506,821])]),
                        )
                    RestartableSequenceExecution(
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("guild",["return",[1,1]],1),
                    )

                    logger.info(_("第5.5步: 击杀风暴六手"))
                    RestartableSequenceExecution(
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("dungFlag",["EdgeOfTown","beginningAbyss","B5FWarpedOnesNest","GotoDung",[1,1]],1),
                    )
                    RestartableSequenceExecution(
                        lambda:StateDungeon([TargetInfo("position","左上",[454,662]),
                                             TargetInfo("position","左上",[135,714])]),
                        )
                    RestartableSequenceExecution(
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("guild",["return",[1,1]],1),
                    )
                    
                    logger.info(_("第六步: 提交悬赏"))
                    RestartableSequenceExecution(
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("CompletionReported",["guild","guildRequest","input swipe 600 1400 300 1400","Bounties",[1,1]],1))
                        )
                    RestartableSequenceExecution(
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("EdgeOfTown",["return",[1,1]],1)
                        )
                    
                    RestartableSequenceExecution(
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("CompletionReported",["guild","guildRequest","input swipe 600 1400 300 1400","Bounties",[1,1]],1))
                        )
                    RestartableSequenceExecution(
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("EdgeOfTown",["return",[1,1]],1)
                        )
                    
                    logger.info(_("第七步: 休息"))
                    if ((runtimeContext._COUNTERDUNG-1) % (setting.REST_INTERVEL+1) == 0):
                        RestartableSequenceExecution(
                            lambda:StateInn()
                            )
                        
                    costtime = time.time()-starttime
                    total_time = total_time + costtime
                    logger.info(_("第{a}次\"悬赏:蝎女\"完成. \n该次花费时间{b:.2f}s.\n总计用时{c:.2f}s.\n平均用时{d:.2f}".format(a=runtimeContext._COUNTERDUNG,b=costtime, c=total_time, d=total_time/runtimeContext._COUNTERDUNG)),
                            extra={"summary": True})
            case "steeltrail":
                total_time = 0
                while 1:
                    if setting._FORCESTOPING.is_set():
                        break

                    starttime = time.time()
                    runtimeContext._COUNTERDUNG += 1

                    RestartableSequenceExecution(
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("guildRequest",["guild",[1,1]],1)),
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("gradeexam",["guild","guildRequest","input swipe 600 1400 300 1400",[1,1]],1)),
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("Steel","gradeexam",1)
                    )

                    pos = CheckIf(ScreenShot(),"Steel")
                    Press([pos[0]+306,pos[1]+258])
                    
                    quest._SPECIALDIALOGOPTION = ["ready","noneed", "quit"]
                    RestartableSequenceExecution(
                        lambda:StateDungeon([TargetInfo("position","左上",[131,769]),
                                    TargetInfo("position","左上",[827,447]),
                                    TargetInfo("position","左上",[131,769]),
                                    TargetInfo("position","左下",[719,1080]),
                                    ])
                                  )
                    
                    if ((runtimeContext._COUNTERDUNG-1) % (setting.REST_INTERVEL+1) == 0):
                        RestartableSequenceExecution(
                            lambda:StateInn()
                            )
                    costtime = time.time()-starttime
                    total_time = total_time + costtime
                    logger.info(_("第{a}次\"钢试炼\"完成. \n该次花费时间{b:.2f}s.\n总计用时{c:.2f}s.\n平均用时{d:.2f}".format(a=runtimeContext._COUNTERDUNG,b=costtime, c=total_time, d=total_time/runtimeContext._COUNTERDUNG)),
                            extra={"summary": True})

            case "jier":
                total_time = 0
                while 1:
                    quest._SPECIALDIALOGOPTION = ["bounty/cuthimdown"]

                    if setting._FORCESTOPING.is_set():
                        break

                    starttime = time.time()
                    runtimeContext._COUNTERDUNG += 1

                    RestartableSequenceExecution(
                        lambda: CursedWheelTimeLeap("requestToRescueTheDuke")
                        )

                    Sleep(10)
                    logger.info(_("第二步: 返回要塞..."))
                    RestartableSequenceExecution(
                        lambda: FindCoordsOrElseExecuteFallbackAndWait("Inn",["returntotown","returnText","leaveDung","blessing",[1,1]],2)
                        )

                    logger.info(_("第三步: 前往王城..."))
                    RestartableSequenceExecution(
                        lambda:TeleportFromCityToWorldLocation("City_RoyalCityLuknalia","input swipe 450 150 500 150"),
                        )

                    logger.info(_("第四步: 悬赏揭榜"))
                    RestartableSequenceExecution(
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("guildRequest",["guild",[1,1]],1)),
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("Bounties",["guild","guildRequest","input swipe 600 1400 300 1400",[1,1]],1)),
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("EdgeOfTown",["return",[1,1]],1)
                        )

                    logger.info(_("第五步: 和吉尔说再见吧"))
                    RestartableSequenceExecution(
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("dungFlag",["EdgeOfTown","beginningAbyss","B4FLabyrinth","GotoDung",[1,1]],1)
                        )
                    RestartableSequenceExecution( 
                        lambda:StateDungeon([TargetInfo("position","左下",[452,545]),
                                             TargetInfo("position","左下",[452,1026]),
                                             TargetInfo("harken","左上",None)]),
                        )
                    
                    logger.info(_("第六步: 提交悬赏"))
                    RestartableSequenceExecution(
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("guild",["return",[1,1]],1),
                    )
                    RestartableSequenceExecution(
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("CompletionReported",["guild","guildRequest","input swipe 600 1400 300 1400","Bounties",[1,1]],1))
                        )
                    RestartableSequenceExecution(
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("EdgeOfTown",["return",[1,1]],1)
                        )
                    
                    logger.info(_("第七步: 休息"))
                    if ((runtimeContext._COUNTERDUNG-1) % (setting.REST_INTERVEL+1) == 0):
                        RestartableSequenceExecution(
                            lambda:StateInn()
                            )
                        
                    costtime = time.time()-starttime
                    total_time = total_time + costtime
                    logger.info(_("第{a}次\"悬赏:吉尔\"完成. \n该次花费时间{b:.2f}s.\n总计用时{c:.2f}s.\n平均用时{d:.2f}".format(a=runtimeContext._COUNTERDUNG,b=costtime, c=total_time, d=total_time/runtimeContext._COUNTERDUNG)),
                            extra={"summary": True})
            case "lovesleep":
                logger.info(_("开始睡觉."))
                t = time.time()
                for counter in range(9999):
                    RestartableSequenceExecution(
                            lambda:StateInn()
                            )
                    logger.info(_("完成了{a}次旅店休息.\n总计用时{c:.2f}s.\n平均用时{d:.2f}s.").format(a=counter+1, c=time.time()-t, d=(time.time()-t)/(counter+1)),extra={"summary": True})
            case "retard_tapjoy":
                def split_image(img):
                    img_analyze = {}
                    for i in range(5):
                        for j in range(7):
                            cropped = img[(274+114*j):(368+114*j),(174+114*i):(268+114*i)]
                            img_analyze[i*10+j] = cropped
                    return img_analyze
                def smallgame_check(a,b):
                    result = cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)
                    underscore, max_val, underscore, max_loc = cv2.minMaxLoc(result)
                    return max_val
                def shoot(i):
                    Press([221+114*i,321])
                ############
                screen_queue = []
                empty_img = LoadTemplateImage('smallgame/smallgame_empty')
                merge_counter = 0
                start_time = time.time()
                while 1:
                    Sleep(1)
                    img = ScreenShot()
                    if Press(CheckIf(img,"smallgame/nothanks")):
                        Sleep(1)
                        continue
                    if Press(CheckIf(img,"smallgame/nothanks_y")):
                        Sleep(1)
                        continue
                    if Press(CheckIf(img,"smallgame/nothanks_s")):
                        Sleep(1)
                        continue
                    if Press(CheckIf(img,"smallgame/yes")):
                        Sleep(1)
                        continue
                    if Press(CheckIf(img,"smallgame/play")):
                        Sleep(1)
                        continue
                    screen_queue, if_frozen = GameFrozenCheck(screen_queue,img[274:(274+114*7),174:(174+114*5)],3,0.002)
                    if if_frozen:
                        if smallgame_check(img[1150-50:1150+50,800-50:800+50],empty_img[1150-50:1150+50,800-50:800+50]) > 0.9:
                            Press([800,1150])
                            Sleep(2)
                            Press([315,1037])
                            Sleep(0.5)
                            shoot(0)
                            continue
                    img_analyze = split_image(img)

                    empty_img = LoadTemplateImage('smallgame/smallgame_empty')
                    img_analyze_empty = split_image(empty_img)

                    depth = [7,7,7,7,7]
                    for k in img_analyze.keys():
                        r = smallgame_check(img_analyze[k],img_analyze_empty[k])
                        if r>0.98:
                            if k%10 < depth[k//10]:
                                depth[k//10] = k % 10
                    
                    # logger.info(depth)

                    next = img[1178-40:1178+40,450-40:450+40,]

                    send = False
                    for i in range(5):
                        if depth[i]!=0:
                            k = i*10+depth[i]-1
                            if k in img_analyze:
                                r = smallgame_check(img_analyze[k],next)
                                if r >0.95:
                                    send = True
                                    break
                    if send:
                        logger.info(f"合成{i}")
                        shoot(i)
                        merge_counter+=1
                        cost_time = time.time()-start_time
                        if merge_counter %20 ==0:
                            logger.info(f"完成最多{merge_counter}次合并, 用时{cost_time:.2f}s. 平均{cost_time/merge_counter:.2f}秒一次合并.", extra={"summary": True})
                        continue
                    for i in range(5):
                        if depth[i]==0:
                            logger.info(f"空白{i}")
                            shoot(i)
                            continue
                    
                    mindeep = depth.index(min(depth))
                    logger.info(f"摆烂{mindeep}")
                    shoot(mindeep)
                    continue
        ##########################
        setting._FINISHINGCALLBACK()
        return
    def Farm(set:FarmConfig):
        nonlocal quest
        nonlocal setting # 初始化
        nonlocal runtimeContext
        

        setting = set
        runtimeContext = RuntimeContext()

        runtimeContext.STRATEGY_RESET_EACH_RESTART = copy.deepcopy(setting.STRATEGY)

        Sleep(1) # 没有等utils初始化完成
        
        ResetDevice()

        quest = LoadQuest(setting.FARM_TARGET)
        if quest:
            if quest._TYPE =="dungeon":
                DungeonFarm()
            else:
                QuestFarm()
        else:
            setting._FINISHINGCALLBACK()
    return Farm