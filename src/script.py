from ppadb.client import Client as AdbClient
import numpy as np
from win10toast import ToastNotifier
from scipy.optimize import curve_fit
from scipy.signal import find_peaks
from enum import Enum
from datetime import datetime
import os
import subprocess
import socket
from utils import *
import random
from threading import Thread,Event
from pathlib import Path

CC_SKILLS = ["KANTIOS"]
SECRET_AOE_SKILLS = ["SAoLABADIOS","SAoLAERLIK","SAoLAFOROS"]
FULL_AOE_SKILLS = ["LAERLIK", "LAMIGAL","LAZELOS", "LACONES", "LAFOROS","LAHALITO", "LAFERU"]
ROW_AOE_SKILLS = ["maerlik", "mahalito", "mamigal","mazelos","maferu", "macones","maforos"]
PHYSICAL_SKILLS = ["FPS","tzalik","QS","PS","DTS","AP","AB","BCS","HA","FS","SB",]

ALL_SKILLS = CC_SKILLS + SECRET_AOE_SKILLS + FULL_AOE_SKILLS + ROW_AOE_SKILLS +  PHYSICAL_SKILLS
ALL_SKILLS = [s for s in ALL_SKILLS if s in list(set(ALL_SKILLS))]

SPELLSEKILL_TABLE = [
            ["btn_enable_all","所有技能",ALL_SKILLS,0,0],
            ["btn_enable_horizontal_aoe","横排AOE",ROW_AOE_SKILLS,0,1],
            ["btn_enable_full_aoe","全体AOE",FULL_AOE_SKILLS,1,0],
            ["btn_enable_secret_aoe","秘术AOE",SECRET_AOE_SKILLS,1,1],
            ["btn_enable_physical","强力单体",PHYSICAL_SKILLS,2,0],
            ["btn_enable_cc","群体控制",CC_SKILLS,2,1]
            ]

DUNGEON_TARGETS = BuildQuestReflection()

####################################
CONFIG_VAR_LIST = [
            #var_name,                      type,          config_name,                  default_value
            ["farm_target_text_var",        tk.StringVar,  "_FARMTARGET_TEXT",           list(DUNGEON_TARGETS.keys())[0] if DUNGEON_TARGETS else ""],
            ["farm_target_var",             tk.StringVar,  "_FARMTARGET",                ""],
            ["randomly_open_chest_var",     tk.BooleanVar, "_RANDOMLYOPENCHEST",         False],
            ["who_will_open_it_var",        tk.IntVar,     "_WHOWILLOPENIT",             0],
            ["skip_recover_var",            tk.BooleanVar, "_SKIPCOMBATRECOVER",         False],
            ["skip_chest_recover_var",      tk.BooleanVar, "_SKIPCHESTRECOVER",          False],
            ["system_auto_combat_var",      tk.BooleanVar, "_SYSTEMAUTOCOMBAT",          False],
            ["aoe_once_var",                tk.BooleanVar, "_AOE_ONCE",                  False],
            ["auto_after_aoe_var",          tk.BooleanVar, "_AUTO_AFTER_AOE",            False],
            ["active_rest_var",             tk.BooleanVar, "_ACTIVE_REST",               True],
            ["rest_intervel_var",           tk.IntVar,     "_RESTINTERVEL",              0],
            ["karma_adjust_var",            tk.StringVar,  "_KARMAADJUST",               "+0"],
            ["emu_path_var",                tk.StringVar,  "_EMUPATH",                   ""],
            ["adb_port_var",                tk.StringVar,  "_ADBPORT",                   5555],
            ["last_version",                tk.StringVar,  "LAST_VERSION",               ""],
            ["latest_version",              tk.StringVar,  "LATEST_VERSION",             None],
            ["_spell_skill_config_internal",list,          "_SPELLSKILLCONFIG",          []]
            ]

class FarmConfig:
    for attr_name, var_type, var_config_name, var_default_value in CONFIG_VAR_LIST:
        locals()[var_config_name] = var_default_value
    def __init__(self):
        #### 统计信息
        self._LAPTIME = 0
        self._TOTALTIME = 0
        self._COUNTERDUNG = 0
        self._COUNTERCOMBAT = 0
        self._COUNTERCHEST = 0
        self._TIME_COMBAT= 0
        self._TIME_COMBAT_TOTAL = 0
        self._TIME_CHEST = 0
        self._TIME_CHEST_TOTAL = 0
        #### 面板配置其他
        self._FORCESTOPING = None
        self._FINISHINGCALLBACK = None
        self._MSGQUEUE = None
        #### 临时参数
        self._MEET_CHEST_OR_COMBAT = False
        self._ENOUGH_AOE = False
        self._COMBATSPD = False
        self._SUICIDE = False # 当有两个人死亡的时候(multipeopledead), 在战斗中尝试自杀.
        self._MAXRETRYLIMIT = 20
        #### 底层接口
        self._ADBDEVICE = None
    def __getattr__(self, name):
        # 当访问不存在的属性时，抛出AttributeError
        raise AttributeError(f"FarmConfig对象没有属性'{name}'")
class FarmQuest:
    _DUNGWAITTIMEOUT = 0
    _TARGETINFOLIST = None
    _EOT = None
    _preEOTcheck = None
    _SPECIALDIALOGOPTION = None
    _SPECIALFORCESTOPINGSYMBOL = None
    _TYPE = None
    def __getattr__(self, name):
        # 当访问不存在的属性时，抛出AttributeError
        raise AttributeError(f"FarmQuest对象没有属性'{name}'")
class TargetInfo:
    def __init__(self, target: str, swipeDir: list = None, roi=None):
        self.target = target
        self.swipeDir = swipeDir
        # 注意 roi校验需要target的值. 请严格保证roi在最后.
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
                value = [[100,100,700,1200]]
            case "右上":
                value = [[700,100,100,1200]]
            case "右下":
                value = [[700,1200,100,100]]
            case "左下":
                value = [[100,1200,700,100]]
            case _:
                value = inputValue
        
        self._swipeDir = value

    @property
    def roi(self):
        return self._roi

    @roi.setter
    def roi(self, value):
        if value == 'default':
            value = [[0,0,900,1600],[0,0,900,208],[0,1265,900,335],[0,636,137,222],[763,636,137,222], [336,208,228,77],[336,1168,228,97]]
        if self.target == 'chest':
            if value == None:
                value = [[0,0,900,1600]]
            value += [[0,0,900,208],[0,1265,900,335],[0,636,137,222],[763,636,137,222], [336,208,228,77],[336,1168,228,97]]

        self._roi = value

##################################################################

def StartAdbServer(setting: FarmConfig):
    def check_adb_connection():
        try:
            # 创建socket检测端口连接
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)  # 设置超时时间
            result = sock.connect_ex(("127.0.0.1", 5037))
            return result == 0  # 返回0表示连接成功
        except Exception as e:
            logger.info(f"连接检测异常: {str(e)}")
            return False
        finally:
            sock.close()
    try:
        if not check_adb_connection():
            adb_path = setting._EMUPATH.replace("HD-Player.exe", "HD-Adb.exe")
            logger.info(f"开始启动ADB服务, 路径:{adb_path}")
            # 启动adb服务（非阻塞模式）
            subprocess.Popen(
                [adb_path, "start-server"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False
            )
            logger.info("ADB 服务启动中...")

            # 循环检测连接（最多重试5次）
            for _ in range(5):
                if check_adb_connection():
                    logger.info("ADB 连接成功")
                    return True
                time.sleep(1)  # 每次检测间隔1秒

            logger.info("ADB 连接超时")
            return False
        else:
            return True
    except Exception as e:
        logger.info(f"启动ADB失败: {str(e)}")
        return False
def CreateAdbDevice(setting: FarmConfig):
    client = AdbClient(host="127.0.0.1", port=5037)

    target_device = f"127.0.0.1:{setting._ADBPORT}"
    connected_devices = [d.serial for d in client.devices()]
    if target_device in connected_devices:
        # 设备已连接时才断开
        client.remote_disconnect("127.0.0.1", int(setting._ADBPORT))
        time.sleep(0.5)

    logger.info(f"尝试创建adb连接 127.0.0.1:{setting._ADBPORT}...")
    client.remote_connect("127.0.0.1", int(setting._ADBPORT))
    devices = client.devices()
    if (not devices) or not (devices[0]):
        logger.info("创建adb链接失败.尝试启动模拟器.")
        if StartEmulator(setting):
            return CreateAdbDevice(setting)
        else:
            return
    return devices[0]

def StartEmulator(setting):
    hd_player_path = setting._EMUPATH
    if not os.path.exists(hd_player_path):
        logger.error(f"模拟器启动程序不存在: {hd_player_path}")
        return False
    
    try:
        logger.info(f"启动模拟器: {hd_player_path}")
        subprocess.Popen(
            hd_player_path, 
            shell=True,
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            cwd=os.path.dirname(hd_player_path))
    except Exception as e:
        logger.error(f"启动模拟器失败: {str(e)}")
        return False
    
    logger.info("等待模拟器启动...")
    time.sleep(15)

def Factory():
    toaster = ToastNotifier()
    setting =  None
    quest = None
    def LoadQuest(farmtarget):
        # 构建文件路径
        data = LoadJson(ResourcePath(QUEST_FILE))[setting._FARMTARGET]
        

        
        # 创建 Quest 实例并填充属性
        quest = FarmQuest()
        for key, value in data.items():
            if key == '_TARGETINFOLIST':
                setattr(quest, key, [TargetInfo(*args) for args in value])
            elif hasattr(FarmQuest, key):
                setattr(quest, key, value)
            elif key in ["type","questName","questId",'extraConfig']:
                pass
            else:
                logger.info(f"'{key}'并不存在于FarmQuest中.")
        
        if 'extraConfig' in data and isinstance(data['extraConfig'], dict):
            for key, value in data['extraConfig'].items():
                if hasattr(setting, key):
                    setattr(setting, key, value)
                else:
                    logger.info(f"Warning: Config has no attribute '{key}' to override")
        return quest
    ##################################################################
    def DeviceShell(cmdStr):
        while True:
            # 使用共享变量存储结果
            exception = None
            result = None
            completed = Event()
            
            def adb_command_thread():
                nonlocal exception,result
                try:
                    result = setting._ADBDEVICE.shell(cmdStr, timeout=5)
                except Exception as e:
                    exception = e
                finally:
                    completed.set()
            
            # 创建并启动线程
            thread = Thread(target=adb_command_thread)
            thread.daemon = True
            thread.start()
            
            # 等待线程完成，设置总超时时间
            completed.wait(timeout=7)  # 比ADB命令超时稍长
            
            if not completed.is_set():
                # 线程超时未完成
                logger.debug("外部检测: ADB命令执行超时")
                exception = TimeoutError("外部检测: ADB命令执行超时")
            
            if exception is None:
                return result
            
            # 处理异常情况
            logger.debug(f"{exception}")
            if isinstance(exception, (RuntimeError, ConnectionResetError, TimeoutError, cv2.error)):
                logger.debug(f"ADB操作失败. {exception}")
                logger.info(f"ADB异常({type(exception).__name__})，尝试重启服务...")
                
                while True:
                    if StartAdbServer(setting):
                        if device := CreateAdbDevice(setting):
                            setting._ADBDEVICE = device
                            logger.info("ADB服务重启成功，设备重新连接")
                            break
                    logger.warning("ADB重启失败，5秒后重试...")
                    time.sleep(5)
            else:
                raise exception  # 非预期异常直接抛出
    
    def Sleep(t=1):
        time.sleep(t)
    def ScreenShot():
        while True:
            try:
                # logger.debug('ScreenShot')
                screenshot = setting._ADBDEVICE.screencap()
                screenshot_np = np.frombuffer(screenshot, dtype=np.uint8)

                if screenshot_np.size == 0:
                    logger.error("截图数据为空！")
                    raise RuntimeError("截图数据为空")

                image = cv2.imdecode(screenshot_np, cv2.IMREAD_COLOR)

                if image is None:
                    logger.error("OpenCV解码失败：图像数据损坏")
                    raise RuntimeError("图像解码失败")

                if image.shape != (1600, 900, 3):  # OpenCV格式为(高, 宽, 通道)
                    if image.shape == (900, 1600, 3):
                        logger.error(f"截图尺寸错误: 当前{image.shape}, 为横屏.")
                        image = cv2.transpose(image)
                        restartGame(skipScreenShot = True) # 这里直接重启, 会被外部接收到重启的exception
                    else:
                        logger.error(f"截图尺寸错误: 期望(1600,900,3), 实际{image.shape}.")
                        raise RuntimeError("截图尺寸异常")

                #cv2.imwrite('screen.png', image)
                return image
            except Exception as e:
                logger.debug(f"{e}")
                if isinstance(e, (AttributeError,RuntimeError, ConnectionResetError, cv2.error)):
                    logger.info("adb重启中...")
                    while True:
                        if StartAdbServer(setting):
                            if device := CreateAdbDevice(setting):
                                setting._ADBDEVICE = device
                                logger.info("ADB服务重启成功，设备重新连接")
                                break
                        logger.warning("ADB重启失败，5秒后重试...")
                        time.sleep(5)
                    continue
    def CheckIf(screenImage, shortPathOfTarget, roi = None, outputMatchResult = False):
        def cutRoI(screenshot,roi):
            if roi is None:
                return screenshot

            img_height, img_width = screenshot.shape[:2]
            roi_copy = roi.copy()
            roi1_rect = roi_copy.pop(0)  # 第一个矩形 (x, y, width, height)

            x1, y1, w1, h1 = roi1_rect

            roi1_y_start_clipped = max(0, y1)
            roi1_y_end_clipped = min(img_height, y1 + h1)
            roi1_x_start_clipped = max(0, x1)
            roi1_x_end_clipped = min(img_width, x1 + w1)

            pixels_not_in_roi1_mask = np.ones((img_height, img_width), dtype=bool)
            if roi1_x_start_clipped < roi1_x_end_clipped and roi1_y_start_clipped < roi1_y_end_clipped:
                pixels_not_in_roi1_mask[roi1_y_start_clipped:roi1_y_end_clipped, roi1_x_start_clipped:roi1_x_end_clipped] = False

            screenshot[pixels_not_in_roi1_mask] = 0

            if (roi is not []):
                for roi2_rect in roi_copy:
                    x2, y2, w2, h2 = roi2_rect

                    roi2_y_start_clipped = max(0, y2)
                    roi2_y_end_clipped = min(img_height, y2 + h2)
                    roi2_x_start_clipped = max(0, x2)
                    roi2_x_end_clipped = min(img_width, x2 + w2)

                    if roi2_x_start_clipped < roi2_x_end_clipped and roi2_y_start_clipped < roi2_y_end_clipped:
                        pixels_in_roi2_mask_for_current_op = np.zeros((img_height, img_width), dtype=bool)
                        pixels_in_roi2_mask_for_current_op[roi2_y_start_clipped:roi2_y_end_clipped, roi2_x_start_clipped:roi2_x_end_clipped] = True

                        # 将位于 roi2 中的像素设置为0
                        # (如果这些像素之前因为不在roi1中已经被设为0，则此操作无额外效果)
                        screenshot[pixels_in_roi2_mask_for_current_op] = 0

            # cv2.imwrite(f'cutRoI_{time.time()}.png', screenshot)
            return screenshot

        nonlocal setting
        template = LoadTemplateImage(shortPathOfTarget)
        screenshot = screenImage
        threshold = 0.80
        pos = None
        search_area = cutRoI(screenshot, roi)
        result = cv2.matchTemplate(search_area, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        logger.debug(f"搜索到疑似{shortPathOfTarget}, 匹配程度:{max_val*100:.2f}%")
        if max_val < threshold:
            logger.debug("匹配程度不足阈值.")
            return None
        if max_val<=0.9:
            logger.debug(f"警告: {shortPathOfTarget}的匹配程度超过了{threshold*100:.0f}%但不足90%")

        pos=[max_loc[0] + template.shape[1]//2, max_loc[1] + template.shape[0]//2]

        if outputMatchResult:
            cv2.rectangle(screenshot, max_loc, (max_loc[0] + template.shape[1], max_loc[1] + template.shape[0]), (0, 255, 0), 2)
            cv2.imwrite("Matched Result.png", screenshot)
        return pos
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
        rectangles, _ = cv2.groupRectangles(rectangles, groupThreshold=1, eps=0.5)
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
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        logger.debug(f"搜索到疑似{shortPathOfTarget}, 匹配程度:{max_val*100:.2f}%")
        if max_val >= threshold:
            if max_val<=0.9:
                logger.debug(f"警告: {shortPathOfTarget}的匹配程度超过了80%但不足90%")

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
            logger.debug(f"中心匹配检查:{mean_diff:.2f}")

            if mean_diff<0.2:
                return True
        return False
    def CheckIf_ReachPosition(screenImage,targetInfo : TargetInfo):
        screenshot = screenImage
        position = targetInfo.roi
        cropped = screenshot[position[1]-33:position[1]+33, position[0]-33:position[0]+33]

        for i in range(4):
            template = LoadTemplateImage(f"cursor_{i}")
        
            result = cv2.matchTemplate(cropped, template, cv2.TM_CCOEFF_NORMED)
            threshold = 0.80
            _, max_val, _, _ = cv2.minMaxLoc(result)

            logger.debug(f"目标格搜素{position}, 匹配程度:{max_val*100:.2f}%")
            if max_val > threshold:
                logger.debug("已达到检测阈值.")
                return None 
        return position
    def CheckIf_throughStair(screenImage,targetInfo : TargetInfo):
        stair_img = ["stair_up","stair_down","stair_teleport"]
        screenshot = screenImage
        position = targetInfo.roi
        cropped = screenshot[position[1]-33:position[1]+33, position[0]-33:position[0]+33]
        
        if (targetInfo.target not in stair_img):
            # 验证楼层
            template = LoadTemplateImage(targetInfo.target)
            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            threshold = 0.80
            _, max_val, _, _ = cv2.minMaxLoc(result)

            logger.debug(f"搜索楼层标识{targetInfo.target}, 匹配程度:{max_val*100:.2f}%")
            if max_val > threshold:
                logger.info("楼层正确, 判定为已通过")
                return None
            return position
            
        else: #equal: targetInfo.target IN stair_img
            template = LoadTemplateImage(targetInfo.target)
            result = cv2.matchTemplate(cropped, template, cv2.TM_CCOEFF_NORMED)
            threshold = 0.80
            _, max_val, _, _ = cv2.minMaxLoc(result)

            logger.debug(f"搜索楼梯{targetInfo.target}, 匹配程度:{max_val*100:.2f}%")
            if max_val > threshold:
                logger.info("判定为楼梯存在, 尚未通过.")
                return position
            return None
    def CheckIf_fastForwardOff(screenImage):
        position = [240,1490]
        template =  LoadTemplateImage(f"fastforward_off")
        screenshot =  screenImage
        cropped = screenshot[position[1]-50:position[1]+50, position[0]-50:position[0]+50]
        
        result = cv2.matchTemplate(cropped, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        threshold = 0.80
        pos=[position[0]+max_loc[0] - cropped.shape[1]//2, position[1]+max_loc[1] -cropped.shape[0]//2]

        if max_val > threshold:
            logger.info(f"快进未开启, 即将开启.{pos}")
            return pos
        return None
    def Press(pos):
        if pos!=None:
            logger.debug(f'按了{pos[0]} {pos[1]}')
            DeviceShell(f"input tap {pos[0]} {pos[1]}")
            return True
        return False
    def PressReturn():
        logger.debug("按了返回.")
        DeviceShell('input keyevent KEYCODE_BACK')
    ##################################################################
    def FindCoordsOrElseExecuteFallbackAndWait(targetPattern, fallback,waitTime):
        # fallback可以是坐标[x,y]或者字符串. 当为字符串的时候, 视为图片地址
        while True:
            for _ in range(setting._MAXRETRYLIMIT):
                if setting._FORCESTOPING.is_set():
                    return None
                scn = ScreenShot()
                if isinstance(targetPattern, (list, tuple)):
                    for pattern in targetPattern:
                        p = CheckIf(scn,pattern)
                        if p:
                            return p
                else:
                    pos = CheckIf(scn,targetPattern)
                    if pos:
                        return pos # FindCoords
                # OrElse
                if Press(CheckIf(scn,'retry')):
                    logger.info("发现并点击了\"重试\". 你遇到了网络波动.")
                    Sleep(1)
                    continue
                if Press(CheckIf_fastForwardOff(scn)):
                    Sleep(1)
                    continue
                def pressTarget(target):
                    if target.lower() == 'return':
                        PressReturn()
                    elif target.startswith("input swipe"):
                        DeviceShell(target)
                    else:
                        Press(CheckIf(scn, target))
                if fallback: # Execute
                    if isinstance(fallback, (list, tuple)):
                        if (len(fallback) == 2) and all(isinstance(x, (int, float)) for x in fallback):
                            Press(fallback)
                        else:
                            for p in fallback:
                                if isinstance(p, str):
                                    pressTarget(p)
                                elif isinstance(p, (list, tuple)) and len(p) == 2:
                                    Press(p)
                                else:
                                    logger.debug(f"错误: 非法的目标{p}.")
                                    setting._FORCESTOPING.set()
                                    return None
                    else:
                        if isinstance(fallback, str):
                            pressTarget(fallback)
                        else:
                            logger.debug("错误: 非法的目标.")
                            setting._FORCESTOPING.set()
                            return None
                Sleep(waitTime) # and wait

            logger.info(f"{setting._MAXRETRYLIMIT}次截图依旧没有找到目标{targetPattern}, 疑似卡死. 重启游戏.")
            Sleep()
            restartGame()
            return None # restartGame会抛出异常 所以直接返回none就行了
    def restartGame(skipScreenShot = False):
        nonlocal setting
        setting._COMBATSPD = False # 重启会重置2倍速, 所以重置标识符以便重新打开.
        setting._MAXRETRYLIMIT = min(50, setting._MAXRETRYLIMIT + 5) # 每次重启后都会增加5次尝试次数, 以避免不同电脑导致的反复重启问题.
        setting._TIME_CHEST = 0
        setting._TIME_COMBAT = 0 # 因为重启了, 所以清空战斗和宝箱计时器.

        if not skipScreenShot:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # 格式：20230825_153045
            file_path = os.path.join("screenshotwhenrestart", f"{timestamp}.png")
            cv2.imwrite(file_path, ScreenShot())
            logger.info(f"重启前截图已保存在{file_path}中.")
        else:
            logger.info(f"因为外部设置, 跳过了重启前截图.")

        package_name = "jp.co.drecom.wizardry.daphne"
        mainAct = DeviceShell(f"cmd package resolve-activity --brief {package_name}").strip().split('\n')[-1]
        DeviceShell(f"am force-stop {package_name}")
        Sleep(2)
        logger.info("巫术, 启动!")
        logger.debug(DeviceShell(f"am start -n {mainAct}"))
        Sleep(10)
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
                logger.info("任务进度重置中...")
                continue
    ##################################################################
    def getCursorCoordinates(input, threshold=0.8):
        """在本地图片中查找模板位置"""
        template = LoadTemplateImage('cursor')
        if template is None:
            raise ValueError("无法加载模板图片！")

        h, w = template.shape[:2]  # 获取模板尺寸
        coordinates = []

        # 按指定顺序读取截图文件
        img = input

        # 执行模板匹配
        result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val > threshold:
            # 返回中心坐标（相对于截图左上角）
            center_x = max_loc[0] + w // 2
            coordinates = center_x
        else:
            coordinates = None
        return coordinates
    def findWidestRectMid(input):
        crop_area = (30,62),(880,115)
        # 转换为灰度图
        gray = cv2.cvtColor(input, cv2.COLOR_BGR2GRAY)

        # 裁剪图像 (y1:y2, x1:x2)
        (x1, y1), (x2, y2) = crop_area
        cropped = gray[y1:y2, x1:x2]

        # cv2.imwrite("Matched Result.png",cropped)

        # 返回结果
        column_means = np.mean(cropped, axis=0)
        aver = np.average(column_means)
        binary = column_means > aver

        # 离散化
        rect_range = []
        startIndex = None
        for i, val in enumerate(binary):
            if val and startIndex is None:
                startIndex = i
            elif not val and startIndex is not None:
                rect_range.append([startIndex,i-1])
                startIndex = None
        if startIndex is not None:
            rect_range.append([startIndex,i-1])

        logger.debug(rect_range)

        widest = 0
        widest_rect = []
        for rect in rect_range:
            if rect[1]-rect[0]>widest:
                widest = rect[1]-rect[0]
                widest_rect = rect


        return int((widest_rect[1]+widest_rect[0])/2)+x1
    def triangularWave(t, p, c):
        t_mod = np.mod(t-c, p)
        return np.where(t_mod < p/2, (2/p)*t_mod, 2 - (2/p)*t_mod)
    def calculSpd(t,x):
        t_data = np.array(t)
        x_data = np.array(x)
        peaks, _ = find_peaks(x_data)
        if len(peaks) >= 2:
            t_peaks = t_data[peaks]
            p0 = np.mean(np.diff(t_peaks))
        else:
            # 备选方法：傅里叶变换或手动设置初值
            p0 = 1.0  # 根据数据调整

        # 非线性最小二乘拟合
        p_opt, _ = curve_fit(
            triangularWave,
            t_data,
            x_data,
            p0=[p0,0],
            bounds=(0, np.inf)  # 确保周期为正
        )
        estimated_p = p_opt[0]
        logger.debug(f"周期 p = {estimated_p:.4f}")
        estimated_c = p_opt[1]
        logger.debug(f"初始偏移 c = {estimated_c:.4f}")

        return p_opt[0], p_opt[1]
    def ChestOpen():
        logger.info("开始智能开箱(?)...")
        ts = []
        xs = []
        t0 = float(DeviceShell("date +%s.%N").strip())
        while 1:
            while 1:
                Sleep(0.2)
                t = float(DeviceShell("date +%s.%N").strip())
                s = ScreenShot()
                x = getCursorCoordinates(s)
                if x != None:
                    ts.append(t-t0)
                    xs.append(x/900)
                    logger.debug(f"t={t-t0}, x={x}")
                else:
                    # cv2.imwrite("Matched Result.png",s)
                    None
                if len(ts)>=20:
                    break
            p, c = calculSpd(ts,xs)
            spd = 2/p*900
            logger.debug(f"s = {2/p*900}")

            t = float(DeviceShell("date +%s.%N").strip())
            s = ScreenShot()
            x = getCursorCoordinates(s)
            target = findWidestRectMid(s)
            logger.debug(f"理论点: {triangularWave(t-t0,p,c)*900}")
            logger.debug(f"起始点: {x}")
            logger.debug(f"目标点: {target}")

            if x!=None:
                waittime = 0
                t_mod = np.mod(t-c, p)
                if t_mod<p/2:
                    # 正向移动, 向右
                    waittime = ((900-x)+(900-target))/spd
                    logger.debug("先向右再向左")
                else:
                    waittime = (x+target)/spd
                    logger.debug("先向左再向右")

                if waittime > 0.270 :
                    logger.debug(f"预计等待 {waittime}")
                    Sleep(waittime-0.270)
                    DeviceShell(f"input tap 450 900") # 这里和retry重合 可以按.
                    Sleep(3)
                else:
                    logger.debug(f"等待时间过短: {waittime}")

            if not CheckIf(ScreenShot(), 'chestOpening'):
                break
    ##################################################################
    class State(Enum):
        Dungeon = 'dungeon'
        Inn = 'inn'
        EoT = 'edge of Town'
        Quit = 'quit'
    class DungeonState(Enum):
        Dungeon = 'dungeon'
        Map = 'map'
        Chest = 'chest'
        Combat = 'combat'
        Quit = 'quit'

    def IdentifyState():
        counter = 0
        while 1:
            screen = ScreenShot()
            logger.info(f'状态机检查中...(第{counter+1}次)')

            if setting._FORCESTOPING.is_set():
                return State.Quit, DungeonState.Quit, screen

            if Press(CheckIf(screen,'retry')):
                    logger.info("发现并点击了\"重试\". 你遇到了网络波动.")
                    # logger.info("ka le.")
                    Sleep(2)

            identifyConfig = [
                ('combatActive',  DungeonState.Combat),
                ('dungFlag',      DungeonState.Dungeon),
                ('chestFlag',     DungeonState.Chest),
                ('whowillopenit', DungeonState.Chest),
                ('mapFlag',       DungeonState.Map),
                ('combatActive_2',DungeonState.Combat),
                ]
            for pattern, state in identifyConfig:
                if CheckIf(screen, pattern):
                    return State.Dungeon, state, screen

            while CheckIf(screen,'someonedead'):
                Press([400,800])
                Sleep(1)
                screen = ScreenShot()

            if Press(CheckIf(screen, "returnText")):
                Sleep(2)
                return IdentifyState()

            if CheckIf(screen,"returntoTown"):
                FindCoordsOrElseExecuteFallbackAndWait('Inn',['return',[1,1]],1)
                return State.Inn,DungeonState.Quit, screen

            if Press(CheckIf(screen,"openworldmap")):
                return IdentifyState()

            if CheckIf(screen,"RoyalCityLuknalia"):
                FindCoordsOrElseExecuteFallbackAndWait(['Inn','dungFlag'],['RoyalCityLuknalia',[1,1]],1)
                if CheckIf(scn:=ScreenShot(),'Inn'):
                    return State.Inn,DungeonState.Quit, screen
                elif CheckIf(scn,'dungFlag'):
                    return State.Dungeon,None, screen

            if CheckIf(screen,"fortressworldmap"):
                FindCoordsOrElseExecuteFallbackAndWait(['Inn','dungFlag'],['fortressworldmap',[1,1]],1)
                if CheckIf(scn:=ScreenShot(),'Inn'):
                    return State.Inn,DungeonState.Quit, screen
                elif CheckIf(scn,'dungFlag'):
                    return State.Dungeon,None, screen

            if (CheckIf(screen,'Inn')):
                return State.Inn, None, screen

            if quest._SPECIALFORCESTOPINGSYMBOL != None:
                for symbol in quest._SPECIALFORCESTOPINGSYMBOL:
                        if CheckIf(screen,symbol):
                            return State.Quit,DungeonState.Quit,None

            if counter>=4:
                logger.info("看起来遇到了一些不太寻常的情况...")
                if quest._SPECIALDIALOGOPTION != None:
                    for option in quest._SPECIALDIALOGOPTION:
                        if Press(CheckIf(screen,option)):
                            return IdentifyState()
                if (CheckIf(screen,'RiseAgain')):
                    setting._SUICIDE = False # 死了 自杀成功 设置为false
                    logger.info("快快请起.")
                    # logger.info("REZ.")
                    Press([450,750])
                    Sleep(10)
                    return IdentifyState()
                if (CheckIf(screen,'cursedWheel_timeLeap')):
                    setting._MSGQUEUE.put(('turn_to_7000G',""))
                    raise SystemExit
                if (pos:=CheckIf(screen,'ambush')) and setting._KARMAADJUST.startswith('-'):
                    new_str = None
                    num_str = setting._KARMAADJUST[1:]
                    if num_str.isdigit():
                        num = int(num_str)
                        if num != 0:
                            new_str = f"-{num - 1}"
                        else:
                            new_str = f"+0"
                    if new_str is not None:
                        logger.info(f"即将进行善恶值调整. 剩余次数:{new_str}")
                        setting._KARMAADJUST = new_str
                        SetOneVarInConfig("_KARMAADJUST",setting._KARMAADJUST)
                        Press(pos)
                        logger.info("伏击起手!")
                        # logger.info("Ambush! Always starts with Ambush.")
                        Sleep(2)
                if (pos:=CheckIf(screen,'ignore')) and setting._KARMAADJUST.startswith('+'):
                    new_str = None
                    num_str = setting._KARMAADJUST[1:]
                    if num_str.isdigit():
                        num = int(num_str)
                        if num != 0:
                            new_str = f"+{num - 1}"
                        else:
                            new_str = f"-0"
                    if new_str is not None:
                        logger.info(f"即将进行善恶值调整. 剩余次数:{new_str}")
                        setting._KARMAADJUST = new_str
                        SetOneVarInConfig("_KARMAADJUST",setting._KARMAADJUST)
                        Press(pos)
                        logger.info("积善行德!")
                        # logger.info("")
                        Sleep(2)
                if Press(CheckIf(screen,'blessing')):
                    logger.info("我要选安戈拉的祝福!...好吧随便选一个吧.")
                    # logger.info("Blessing of... of course Angora! Fine, anything.")
                    Sleep(2)
                if Press(CheckIf(screen,'DontBuyIt')):
                    logger.info("等我买? 你白等了, 我不买.")
                    # logger.info("wait for paurch? Wait for someone else.")
                    Sleep(2)
                if Press(CheckIf(screen,'donthelp')):
                    logger.info("不帮你了.")
                    # logger.info("")
                    Sleep(2)
                if Press(CheckIf(screen,'adventurersbones')):
                    logger.info("是骨头!")
                    # logger.info("")
                    Sleep(2)
                if Press(CheckIf(screen,'buyNothing')):
                    logger.info("有骨头的话我会买的.")
                    # logger.info("No Bones No Buy.")
                    Sleep(2)
                if Press(CheckIf(screen,'Nope')):
                    logger.info("但是, 我拒绝.")
                    # logger.info("And what, must we give in return?")
                    Sleep(2)
                if Press(CheckIf(screen,'dontGiveAntitoxin')):
                    logger.info("但是, 我拒绝.")
                    # logger.info("")
                    Sleep(2)
                if (CheckIf(screen,'multipeopledead')):
                    setting._SUICIDE = True # 准备尝试自杀
                    logger.info("死了好几个, 惨哦")
                    # logger.info("Corpses strew the screen")
                    Press(CheckIf(screen,'skull'))
                    Sleep(2)
                if Press(CheckIf(screen,'startdownload')):
                    logger.info("确认, 下载, 确认.")
                    # logger.info("")
                    Sleep(2)
                if Press(CheckIf(screen,'totitle')):
                    logger.info("网络故障警报! 网络故障警报! 返回标题, 重复, 返回标题!")
                    return IdentifyState()
                PressReturn()
                PressReturn()
            if counter>15:
                black = LoadTemplateImage("blackScreen")
                mean_diff = cv2.absdiff(black, screen).mean()/255
                if mean_diff<0.02:
                    logger.info(f"警告: 游戏画面长时间处于黑屏中, 即将重启({25-counter})")
            if counter>= 25:
                logger.info("看起来遇到了一些非同寻常的情况...重启游戏.")
                restartGame()
                counter = 0

            Press([1,1])
            Press([1,1])
            Press([1,1])
            Sleep(1)
            counter += 1
        return None, None, screen
    def GameFrozenCheck(queue, scn):
        logger.info("卡死检测截图")
        LENGTH = 10
        if len(queue) > LENGTH:
            queue = []
        queue.append(scn)
        totalDiff = 0
        t = time.time()
        if len(queue)==LENGTH:
            for i in range(1,LENGTH):
                grayThis = cv2.cvtColor(queue[i], cv2.COLOR_BGR2GRAY)
                grayLast = cv2.cvtColor(queue[i-1], cv2.COLOR_BGR2GRAY)
                mean_diff = cv2.absdiff(grayThis, grayLast).mean()/255
                totalDiff += mean_diff
            logger.info(f"卡死检测耗时: {time.time()-t:.5f}秒")
            logger.info(f"卡死检测结果: {totalDiff:.5f}")
            if totalDiff<=0.15:
                return queue, True
        return queue, False
    def StateInn():
        FindCoordsOrElseExecuteFallbackAndWait('OK',['Inn','Stay','Economy',[1,1]],2)
        FindCoordsOrElseExecuteFallbackAndWait('Stay',['OK',[299,1464]],2)
        PressReturn()
    def StateEoT():
        if quest._preEOTcheck:
            if Press(CheckIf(ScreenShot(),quest._preEOTcheck)):
                pass
        for info in quest._EOT:
            pos = FindCoordsOrElseExecuteFallbackAndWait(info[1],info[2],info[3])
            if info[0]=="press":
                Press(pos)
        Sleep(1)
        Press(CheckIf(ScreenShot(), 'GotoDung'))
    def StateCombat():
        nonlocal setting
        if setting._TIME_COMBAT==0:
            setting._TIME_COMBAT = time.time()

        screen = ScreenShot()
        if not setting._COMBATSPD:
            if Press(CheckIf(screen,'combatSpd')):
                setting._COMBATSPD = True

        if setting._SYSTEMAUTOCOMBAT:
            Press(CheckIf(screen,'combatAuto'))
            Sleep(5)
            return

        if setting._ENOUGH_AOE and setting._AUTO_AFTER_AOE:
            Press(CheckIf(screen,'combatAuto'))
            Sleep(5)
            return

        if not CheckIf(screen,'flee'):
            return
        if setting._SUICIDE:
            Press(CheckIf(screen,'defend'))
        else:
            castSpellSkill = False
            castAndPressOK = False
            for skillspell in setting._SPELLSKILLCONFIG:
                if setting._ENOUGH_AOE and ((skillspell in SECRET_AOE_SKILLS) or (skillspell in FULL_AOE_SKILLS)):
                    #logger.info(f"本次战斗已经释放全体aoe, 由于面板配置, 不进行更多的技能释放.")
                    continue
                elif Press((CheckIf(screen, 'spellskill/'+skillspell))):
                    logger.info(f"使用技能 {skillspell}")
                    Sleep(1)
                    scn = ScreenShot()
                    if Press(CheckIf(scn,'OK')):
                        castAndPressOK = True
                        Sleep(2)
                    elif pos:=(CheckIf(scn,'next')):
                        Press([pos[0]-15+random.randint(0,30),pos[1]+150+random.randint(0,30)])
                        Sleep(1)
                        if CheckIf(ScreenShot(),'notenoughsp') or CheckIf(ScreenShot(),'notenoughmp'):
                            PressReturn()
                            Press(CheckIf(ScreenShot(),'spellskill/lv1'))
                            Press([pos[0]-15+random.randint(0,30),pos[1]+150+random.randint(0,30)])
                            Sleep(1)
                    else:
                        Press([150,750])
                        Press([300,750])
                        Press([450,750])
                        Press([550,750])
                        Press([650,750])
                        Press([750,750])
                        Sleep(2)
                    Sleep(1)
                    castSpellSkill = True
                    if castAndPressOK and setting._AOE_ONCE and ((skillspell in SECRET_AOE_SKILLS) or (skillspell in FULL_AOE_SKILLS)):
                        setting._ENOUGH_AOE = True
                        logger.info(f"已经释放了首次全体aoe.")
                    break
            if not castSpellSkill:
                Press(CheckIf(ScreenShot(),'combatClose'))
                Press([850,1100])
                Press([850,1100])
                Sleep(3)
    def StateMap_FindSwipeClick(targetInfo : TargetInfo):
        ### return = None: 视为没找到, 大约等于目标点结束.
        ### return = [x,y]: 视为找到, [x,y]是坐标.
        target = targetInfo.target
        roi = targetInfo.roi
        for i in range(len(targetInfo.swipeDir)):
            scn = ScreenShot()
            if not CheckIf(scn,'mapFlag'):
                raise KeyError("地图不可用.")

            swipeDir = targetInfo.swipeDir[i]
            if swipeDir!=None:
                logger.debug(f"拖动地图:{swipeDir[0]} {swipeDir[1]} {swipeDir[2]} {swipeDir[3]}")
                DeviceShell(f"input swipe {swipeDir[0]} {swipeDir[1]} {swipeDir[2]} {swipeDir[3]}")
                Sleep(2)
                scn = ScreenShot()
            
            targetPos = None
            if target == 'position':
                logger.info(f"当前目标: 地点{roi}")
                targetPos = CheckIf_ReachPosition(scn,targetInfo)
            elif target.startswith("stair"):
                logger.info(f"当前目标: 楼梯{target}")
                targetPos = CheckIf_throughStair(scn,targetInfo)
            else:
                logger.info(f"搜索{target}...")
                if targetPos:=CheckIf(scn,target,roi):
                    logger.info(f'找到了 {target}! {targetPos}')
                    if (target == 'chest') and (swipeDir!= None):
                        logger.debug(f"宝箱热力图: 地图:{setting._FARMTARGET} 方向:{swipeDir} 位置:{targetPos}")
                    if not roi:
                        # 如果没有指定roi 我们使用二次确认
                        logger.debug(f"拖动: {targetPos[0]},{targetPos[1]} -> 450,800")
                        DeviceShell(f"input swipe {targetPos[0]} {targetPos[1]} {(targetPos[0]+450)//2} {(targetPos[1]+800)//2}")
                        Sleep(2)
                        Press([1,1255])
                        targetPos = CheckIf(ScreenShot(),target,roi)
                    break
        return targetPos
    def StateMoving_CheckFrozen():
        lastscreen = None
        dungState = None
        logger.info("面具男, 移动.")
        while 1:
            Sleep(3)
            _, dungState,screen = IdentifyState()
            if dungState == DungeonState.Map:
                logger.info(f"开始移动失败. 不要停下来啊面具男!")
                FindCoordsOrElseExecuteFallbackAndWait("dungFlag",([280,1433],[1,1]),1)
                dungState = dungState.Dungeon
                break
            if dungState != DungeonState.Dungeon:
                logger.info(f"已退出移动状态. 当前状态: {dungState}.")
                break
            if lastscreen is not None:
                gray1 = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
                gray2 = cv2.cvtColor(lastscreen, cv2.COLOR_BGR2GRAY)
                mean_diff = cv2.absdiff(gray1, gray2).mean()/255
                logger.debug(f"移动停止检查:{mean_diff:.2f}")
                if mean_diff < 0.1:
                    dungState = None
                    logger.info("已退出移动状态.进行状态检查...")
                    break
            lastscreen = screen
        return dungState
    def StateSearch(waitTimer, targetInfoList : list[TargetInfo]):
        normalPlace = ['harken','chest','leaveDung','position']
        targetInfo = targetInfoList[0]
        target = targetInfo.target
        # 地图已经打开.
        map = ScreenShot()
        if not CheckIf(map,'mapFlag'):
                return None,targetInfoList # 发生了错误

        try:
            searchResult = StateMap_FindSwipeClick(targetInfo)
        except KeyError as e:
            logger.info(f"错误: {e}") # 一般来说这里只会返回"地图不可用"
            return None,  targetInfoList

        if searchResult == None:
            if target == 'chest':
                # 结束, 弹出.
                targetInfoList.pop(0)
                logger.info(f"没有找到宝箱.\n停止检索宝箱.")
            elif (target == 'position' or target.startswith('stair')):
                # 结束, 弹出.
                targetInfoList.pop(0)
                logger.info(f"已经抵达目标地点或目标楼层.")
            else:
                # 这种时候我们认为真正失败了. 所以不弹出.
                # 当然, 更好的做法时传递finish标识()
                logger.info(f"未找到目标{target}.")

            return DungeonState.Map,  targetInfoList
        else:
            if target in normalPlace or target.endswith("_quit") or target.startswith('stair'):
                Press(searchResult)
                Press([280,1433]) # automove
                return StateMoving_CheckFrozen(),targetInfoList
            else:
                if (CheckIf_FocusCursor(ScreenShot(),target)): #注意 这里通过二次确认 我们可以看到目标地点 而且是未选中的状态
                    logger.info("经过对比中心区域, 确认没有抵达.")
                    Press(searchResult)
                    Press([280,1433]) # automove
                    return StateMoving_CheckFrozen(),targetInfoList
                else:
                    if setting._DUNGWAITTIMEOUT == 0:
                        logger.info("经过对比中心区域, 判断为抵达目标地点.")
                        logger.info("无需等待, 当前目标已完成.")
                        targetInfoList.pop(0)
                        return DungeonState.Map,  targetInfoList
                    else:
                        logger.info("经过对比中心区域, 判断为抵达目标地点.")
                        logger.info('开始等待...等待...')
                        PressReturn()
                        PressReturn()
                        while 1:
                            if setting._DUNGWAITTIMEOUT-time.time()+waitTimer<0:
                                logger.info("等得够久了. 目标地点完成.")
                                targetInfoList.pop(0)
                                Sleep(1)
                                Press([777,150])
                                return None,  targetInfoList
                            logger.info(f'还需要等待{setting._DUNGWAITTIMEOUT-time.time()+waitTimer}秒.')
                            if CheckIf(ScreenShot(),'combatActive'):
                                return DungeonState.Combat,targetInfoList
        return DungeonState.Map,  targetInfoList
    def StateChest():
        nonlocal setting
        if setting._TIME_CHEST==0:
            setting._TIME_CHEST = time.time()
        FindCoordsOrElseExecuteFallbackAndWait('whowillopenit', ['chestFlag',[1,1]],1)
        tryOpenCounter = 0
        MAXTRYOPEN = 2
        MAXERROROPEN = 50
        while 1:
            scn = ScreenShot()
            Press(CheckIf(scn,'chestFlag'))
            if CheckIf(scn,'whowillopenit'):
                if (tryOpenCounter<=MAXTRYOPEN) and (setting._WHOWILLOPENIT != 0):
                    whowillopenit = setting._WHOWILLOPENIT - 1 # 如果指定了人选且次数没超过尝试次数, 使用指定的序号
                else:
                    # 其他时候都使用随机
                    others = [num for num in [1, 2, 3, 4, 5, 6] if num != setting._WHOWILLOPENIT] # setting._WHOWILLOPENIT可以等于0, 这种情况就是完全随机
                    whowillopenit = random.choice(others) # 如果超过了尝试次数, 那么排除指定的人选后随机
                Press([200+(whowillopenit%3)*200, 1200+((whowillopenit)//3)%2*150])
                Sleep(1)
            Press([1,1])
            if CheckIf(ScreenShot(),'chestOpening'):
                Sleep(1)
                if not setting._RANDOMLYOPENCHEST:
                    FindCoordsOrElseExecuteFallbackAndWait(['dungFlag','combatActive'],[450,900],1)
                    break
                else:
                    if CheckIf(ScreenShot(),'chestOpening'):
                        ChestOpen()
                return None
            if CheckIf(ScreenShot(),'dungFlag'):
                return DungeonState.Dungeon
            if CheckIf(ScreenShot(),'combatActive'):
                return DungeonState.Combat
            if Press(CheckIf(ScreenShot(),'retry')):
                logger.info("发现并点击了\"重试\". 你遇到了网络波动.")
                continue
            tryOpenCounter += 1
            logger.info(f"似乎选择人物失败了,当前已经尝次数:{tryOpenCounter}.")
            if tryOpenCounter <=MAXTRYOPEN:
                logger.info(f"尝试{MAXTRYOPEN}次后若失败则会变为随机开箱.")
            else:
                logger.info(f"随机开箱已经启用.")
            if tryOpenCounter > MAXERROROPEN:
                logger.info(f"错误: 尝试次数过多. 疑似卡死.")
                return None
    def StateDungeon(targetInfoList : list[TargetInfo]):
        gameFrozen_none = []
        gameFrozen_map = 0
        dungState = None
        shouldRecover = False
        waitTimer = time.time()
        needRecoverBecauseCombat = False
        needRecoverBecauseChest = False
        while 1:
            logger.info("----------------------")
            if setting._FORCESTOPING.is_set():
                logger.info("即将停止脚本...")
                dungState = DungeonState.Quit
            logger.info(f"当前状态(地下城): {dungState}")

            match dungState:
                case None:
                    s, dungState,scn = IdentifyState()
                    if (s == State.Inn)or(s == DungeonState.Quit):
                        break
                    gameFrozen_none, result = GameFrozenCheck(gameFrozen_none,scn)
                    if result:
                        logger.info("由于画面卡死, 在state:None中重启.")
                        restartGame()
                    MAXTIMEOUT = 300
                    if (setting._TIME_CHEST != 0 ) and (time.time()-setting._TIME_CHEST > MAXTIMEOUT):
                        logger.info("由于宝箱用时过久, 在state:None中重启.")
                        restartGame()
                    if (setting._TIME_COMBAT != 0) and (time.time()-setting._TIME_COMBAT > MAXTIMEOUT):
                        logger.info("由于战斗用时过久, 在state:None中重启.")
                        restartGame()
                case DungeonState.Quit:
                    break
                case DungeonState.Dungeon:
                    Press([1,1])
                    ########### RESUME
                    shouldResume = False # 我们假定不需要resume, 但是如果检测到战斗或宝箱, 那么尝试resume.
                    if (setting._TIME_CHEST !=0) or (setting._TIME_COMBAT!=0):
                        shouldResume = True
                    ########### COMBAT RESET
                    # 战斗结束了, 我们将一些设置复位
                    if setting._AOE_ONCE:
                        setting._ENOUGH_AOE = False
                    ########### TIMER
                    if (setting._TIME_CHEST !=0) or (setting._TIME_COMBAT!=0):
                        spend_on_chest = 0
                        if setting._TIME_CHEST !=0:
                            spend_on_chest = time.time()-setting._TIME_CHEST
                            setting._TIME_CHEST = 0
                        spend_on_combat = 0
                        if setting._TIME_COMBAT !=0:
                            spend_on_combat = time.time()-setting._TIME_COMBAT
                            setting._TIME_COMBAT = 0
                        logger.info(f"粗略统计: 宝箱{spend_on_chest:.2f}秒, 战斗{spend_on_combat:.2f}秒.")
                        if (spend_on_chest!=0) and (spend_on_combat!=0):
                            if spend_on_combat>spend_on_chest:
                                setting._TIME_COMBAT_TOTAL = setting._TIME_COMBAT_TOTAL + spend_on_combat-spend_on_chest
                                setting._TIME_CHEST_TOTAL = setting._TIME_CHEST_TOTAL + spend_on_chest
                            else:
                                setting._TIME_CHEST_TOTAL = setting._TIME_CHEST_TOTAL + spend_on_chest-spend_on_combat
                                setting._TIME_COMBAT_TOTAL = setting._TIME_COMBAT_TOTAL + spend_on_combat
                        else:
                            setting._TIME_COMBAT_TOTAL = setting._TIME_COMBAT_TOTAL + spend_on_combat
                            setting._TIME_CHEST_TOTAL = setting._TIME_CHEST_TOTAL + spend_on_chest
                    ########### RECOVER
                    if needRecoverBecauseChest:
                        logger.info("进行开启宝箱后的恢复.")
                        setting._COUNTERCHEST+=1
                        needRecoverBecauseChest = False
                        setting._MEET_CHEST_OR_COMBAT = True
                        if not setting._SKIPCHESTRECOVER:
                            logger.info("由于面板配置, 进行开启宝箱后恢复.")
                            shouldRecover = True
                        else:
                            logger.info("由于面板配置, 跳过了开启宝箱后恢复.")
                    if needRecoverBecauseCombat:
                        setting._COUNTERCOMBAT+=1
                        needRecoverBecauseCombat = False
                        setting._MEET_CHEST_OR_COMBAT = True
                        if (not setting._SKIPCOMBATRECOVER):
                            logger.info("由于面板配置, 进行战后恢复.")
                            shouldRecover = True
                        else:
                            logger.info("由于面板配置, 跳过了战后后恢复.")
                    if shouldRecover:
                        Press([1,1])
                        Press([150,1300])
                        Sleep(1)
                        if CheckIf(ScreenShot(),'trait'):
                            for _ in range(3):
                                Press([833,843])
                                if CheckIf(ScreenShot(),'recover'):
                                    Sleep(1)
                                    Press([600,1200])
                                    PressReturn()
                                    Sleep(0.5)
                                    PressReturn()
                                    PressReturn()
                                    shouldRecover = False
                                    break
                    ########### REUSME
                    Sleep(1)
                    if shouldResume:
                        Press(CheckIf(ScreenShot(), 'resume'))
                        StateMoving_CheckFrozen()
                    ########### OPEN MAP
                    Press([777,150])
                    dungState = DungeonState.Map
                case DungeonState.Map:
                    dungState, newTargetInfoList = StateSearch(waitTimer,targetInfoList)
                    
                    if newTargetInfoList == targetInfoList:
                        gameFrozen_map +=1
                        logger.info(f"地图卡死检测:{gameFrozen_map}")
                    else:
                        gameFrozen_map = 0
                    if gameFrozen_map > 50:
                        gameFrozen_map = 0
                        restartGame()

                    if (targetInfoList==None) or (targetInfoList == []):
                        logger.info("地下城目标完成. 地下城状态结束.(仅限任务模式.)")
                        break
                case DungeonState.Chest:
                    needRecoverBecauseChest = True
                    dungState = StateChest()
                case DungeonState.Combat:
                    needRecoverBecauseCombat =True
                    StateCombat()
                    dungState = None
    def StateAcceptRequest(request: str, pressbias:list = [0,0]):
        FindCoordsOrElseExecuteFallbackAndWait('Inn',[1,1],1)
        StateInn()
        Press(FindCoordsOrElseExecuteFallbackAndWait('guildRequest',['guild',[1,1]],1))
        Press(FindCoordsOrElseExecuteFallbackAndWait('guildFeatured',['guildRequest',[1,1]],1))
        Sleep(2)
        DeviceShell(f"input swipe 150 1000 150 200")
        Sleep(2)
        pos = FindCoordsOrElseExecuteFallbackAndWait(request,['input swipe 150 200 150 250',[1,1]],1)
        if not CheckIf(ScreenShot(),'request_accepted',[[0,pos[1]-200,900,pos[1]+200]]):
            FindCoordsOrElseExecuteFallbackAndWait(['Inn','guildRequest'],[[pos[0]+pressbias[0],pos[1]+pressbias[1]],'return',[1,1]],1)
            FindCoordsOrElseExecuteFallbackAndWait('Inn',['return',[1,1]],1)
        else:
            logger.info("奇怪, 任务怎么已经接了.")
            FindCoordsOrElseExecuteFallbackAndWait('Inn',['return',[1,1]],1)

    def DungeonFarm():
        nonlocal setting
        state = None
        while 1:
            logger.info("======================")
            Sleep(1)
            if setting._FORCESTOPING.is_set():
                logger.info("即将停止脚本...")
                break
            logger.info(f"当前状态: {state}")
            match state:
                case None:
                    def _identifyState():
                        nonlocal state
                        state=IdentifyState()[0]
                    RestartableSequenceExecution(
                        lambda: _identifyState()
                        )
                    logger.info(f"下一状态: {state}")
                    if state ==State.Quit:
                        logger.info("即将停止脚本...")
                        break
                case State.Inn:
                    if setting._LAPTIME!= 0:
                        setting._TOTALTIME = setting._TOTALTIME + time.time() - setting._LAPTIME
                        logger.info(f"已完成{setting._COUNTERDUNG}次{setting._FARMTARGET_TEXT}地下城. 最后一次用时:{round(time.time()-setting._LAPTIME,2)}秒.\n累计开箱子{setting._COUNTERCHEST}次.累计战斗{setting._COUNTERCOMBAT}次.\n累计用时{round(setting._TOTALTIME,2)}秒.战斗{round(setting._TIME_COMBAT_TOTAL*100/setting._TOTALTIME,2)}%,宝箱{round(setting._TIME_CHEST_TOTAL*100/setting._TOTALTIME,2)}%.",
                                    extra={"summary": True})
                    setting._LAPTIME = time.time()
                    setting._COUNTERDUNG+=1
                    if not setting._MEET_CHEST_OR_COMBAT:
                        logger.info("因为没有遇到战斗或宝箱, 跳过恢复")
                    elif not setting._ACTIVE_REST:
                        logger.info("因为面板设置, 跳过恢复")
                    elif ((setting._COUNTERDUNG-1) % (setting._RESTINTERVEL+1) != 0):
                        logger.info("还有许多地下城要刷. 面具男, 现在还不能休息哦.")
                    else:
                        logger.info("休息时间到!")
                        setting._MEET_CHEST_OR_COMBAT = False
                        RestartableSequenceExecution(
                        lambda:StateInn()
                        )
                    state = State.EoT
                case State.EoT:
                    RestartableSequenceExecution(
                        lambda:StateEoT()
                        )
                    state = State.Dungeon
                case State.Dungeon:
                    targetInfoList = quest._TARGETINFOLIST.copy()
                    RestartableSequenceExecution(
                        lambda: StateDungeon(targetInfoList)
                        )
                    state = None
        setting._FINISHINGCALLBACK()
    def QuestFarm():
        nonlocal setting
        match setting._FARMTARGET:
            case '7000G':
                stepNo = 1
                while 1:
                    if setting._FORCESTOPING.is_set():
                        break

                    starttime = time.time()
                    setting._COUNTERDUNG += 1
                    def stepMain():
                        logger.info("第一步: 开始诅咒之旅...")
                        Press(FindCoordsOrElseExecuteFallbackAndWait('cursedWheel_timeLeap',['ruins','cursedWheel',[1,1]],1))
                        Press(FindCoordsOrElseExecuteFallbackAndWait('cursedwheel_impregnableFortress',['cursedWheelTapRight',[1,1]],1))

                        if not Press(CheckIf(ScreenShot(),'FortressArrival')):
                            DeviceShell(f"input swipe 450 1200 450 200")
                            Press(FindCoordsOrElseExecuteFallbackAndWait('FortressArrival','input swipe 50 1200 50 1300',1))

                        while pos:= CheckIf(ScreenShot(), 'leap'):
                            Press(pos)
                            Sleep(2)
                            Press(CheckIf(ScreenShot(),'FortressArrival'))
                    RestartableSequenceExecution(
                        lambda: stepMain()
                        )

                    Sleep(10)
                    logger.info("第二步: 返回要塞...")
                    RestartableSequenceExecution(
                        lambda: FindCoordsOrElseExecuteFallbackAndWait('Inn',['returntotown','returnText','leaveDung','blessing',[1,1]],2)
                        )

                    logger.info("第三步: 前往王城...")
                    RestartableSequenceExecution(
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait('intoWorldMap',[40, 1184],2)),
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait('RoyalCityLuknalia','input swipe 450 150 500 150',1)),
                        lambda:FindCoordsOrElseExecuteFallbackAndWait('guild',['RoyalCityLuknalia',[1,1]],1),
                        )

                    logger.info("第四步: 给我!(伸手)")
                    stepMark = -1
                    def stepMain():
                        nonlocal stepMark
                        if stepMark == -1:
                            Press(FindCoordsOrElseExecuteFallbackAndWait('guild',[1,1],1))
                            Press(FindCoordsOrElseExecuteFallbackAndWait('7000G/illgonow',[1,1],1))
                            Sleep(15)
                            FindCoordsOrElseExecuteFallbackAndWait(['7000G/olddist','7000G/iminhungry'],[1,1],2)
                            if pos:=CheckIf(scn:=ScreenShot(),'7000G/olddist'):
                                Press(pos)
                            else:
                                Press(CheckIf(scn,'7000G/iminhungry'))
                                Press(FindCoordsOrElseExecuteFallbackAndWait('7000G/olddist',[1,1],2))
                            stepMark = 0
                        if stepMark == 0:
                            Sleep(4)
                            Press([1,1])
                            Press([1,1])
                            Sleep(8)
                            Press(FindCoordsOrElseExecuteFallbackAndWait('7000G/royalcapital',[1,1],2))
                            FindCoordsOrElseExecuteFallbackAndWait('intoWorldMap',[1,1],2)
                            stepMark = 1
                        if stepMark == 1:
                            FindCoordsOrElseExecuteFallbackAndWait('fastforward',[450,1111],0)
                            FindCoordsOrElseExecuteFallbackAndWait('intoWorldMap',['7000G/why',[1,1]],2)
                            stepMark = 2
                        if stepMark == 2:
                            FindCoordsOrElseExecuteFallbackAndWait('fastforward',[200,1180],0)
                            FindCoordsOrElseExecuteFallbackAndWait('intoWorldMap',['7000G/why',[1,1]],2)
                            stepMark = 3
                        if stepMark == 3:
                            FindCoordsOrElseExecuteFallbackAndWait('fastforward',[680,1200],0)
                            Press(FindCoordsOrElseExecuteFallbackAndWait('7000G/leavethechild',['7000G/why',[1,1]],2))
                            stepMark = 4
                        if stepMark == 4:
                            Press(FindCoordsOrElseExecuteFallbackAndWait('7000G/icantagreewithU',[1,1],1))
                            stepMark = 5
                        if stepMark == 5:
                            Press(FindCoordsOrElseExecuteFallbackAndWait('7000G/illgo',[[1,1],'7000G/olddist'],1))
                            stepMark = 6
                        if stepMark == 6:
                            Press(FindCoordsOrElseExecuteFallbackAndWait('7000G/noeasytask',[1,1],1))
                            stepMark = 7
                        FindCoordsOrElseExecuteFallbackAndWait('ruins',[1,1],1)
                    RestartableSequenceExecution(
                        lambda: stepMain()
                        )
                    costtime = time.time()-starttime
                    logger.info(f"第{setting._COUNTERDUNG}次\"7000G\"完成. 该次花费时间{costtime:.2f}, 每秒收益:{7000/costtime:.2f}Gps.",
                                extra={"summary": True})

            case 'fordraig':
                quest._SPECIALDIALOGOPTION = ['fordraig/thedagger','fordraig/InsertTheDagger']
                while 1:
                    if setting._FORCESTOPING.is_set():
                        break
                    setting._COUNTERDUNG += 1
                    setting._SYSTEMAUTOCOMBAT = True
                    starttime = time.time()
                    logger.info('第一步: 诅咒之旅...')
                    RestartableSequenceExecution(
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait('cursedWheel',['ruins',[1,1]],1)),
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait('Fordraig/Leap',['specialRequest',[1,1]],1)),
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait('OK','leap',1)),
                        )
                    Sleep(15)

                    RestartableSequenceExecution(
                        lambda: logger.info('第二步: 领取任务.'),
                        lambda: StateAcceptRequest('fordraig/RequestAccept',[350,180])
                        )

                    logger.info('第三步: 进入地下城.')
                    Press(FindCoordsOrElseExecuteFallbackAndWait('intoWorldMap',[40, 1184],2))
                    Press(FindCoordsOrElseExecuteFallbackAndWait('labyrinthOfFordraig','input swipe 450 150 500 150',1))
                    Press(FindCoordsOrElseExecuteFallbackAndWait('fordraig/Entrance',['labyrinthOfFordraig',[1,1]],1))
                    FindCoordsOrElseExecuteFallbackAndWait('dungFlag',['fordraig/Entrance','GotoDung',[1,1]],1)

                    logger.info('第四步: 陷阱.')
                    RestartableSequenceExecution(
                        lambda:StateDungeon([
                            TargetInfo('position',"左上",[721,448]),
                            TargetInfo('position',"左上",[720,608])]), # 前往第一个陷阱
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("dungFlag","return",1), # 关闭地图
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("fordraig/TryPushingIt",["input swipe 100 250 800 250",[400,800],[400,800],[400,800]],1)), # 转向来开启机关
                        )
                    logger.info('已完成第一个陷阱.')

                    RestartableSequenceExecution(
                        lambda:StateDungeon([
                            TargetInfo('stair_down',"左上",[721,236]),
                            TargetInfo('position',"左下", [240,921])]), #前往第二个陷阱
                        lambda:FindCoordsOrElseExecuteFallbackAndWait("dungFlag","return",1), # 关闭地图
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("fordraig/TryPushingIt",["input swipe 100 250 800 250",[400,800],[400,800],[400,800]],1)), # 转向来开启机关
                        )
                    logger.info('已完成第二个陷阱.')

                    RestartableSequenceExecution(
                        lambda:StateDungeon([
                            TargetInfo("position","左下",[33,1238]),
                            TargetInfo("stair_down","左下",[453,1027]),
                            TargetInfo("position","左下",[187,1027]),
                            TargetInfo("stair_teleport","左下",[80,1026])
                            ]), #前往第三个陷阱
                        )
                    logger.info('已完成第三个陷阱.')

                    StateDungeon([TargetInfo('position','左下',[508,1025])]) # 前往boss战门前
                    setting._SYSTEMAUTOCOMBAT = False
                    StateDungeon([TargetInfo('position','左下',[720,1025])]) # 前往boss战斗
                    setting._SYSTEMAUTOCOMBAT = True
                    StateDungeon([TargetInfo('stair_teleport','左上',[665,395])]) # 第四层出口
                    FindCoordsOrElseExecuteFallbackAndWait("dungFlag","return",1)
                    Press(FindCoordsOrElseExecuteFallbackAndWait("ReturnText",["leaveDung",[455,1200]],3.75)) # 回城
                    # 3.75什么意思 正常循环是3秒 有4次尝试机会 因此3.75秒按一次刚刚好.
                    Press(FindCoordsOrElseExecuteFallbackAndWait("RoyalCityLuknalia",['return',[1,1]],1)) # 回城
                    FindCoordsOrElseExecuteFallbackAndWait("Inn",[1,1],1)

                    costtime = time.time()-starttime
                    logger.info(f"第{setting._COUNTERDUNG}次\"鸟剑\"完成. 该次花费时间{costtime:.2f}.",
                            extra={"summary": True})
            case 'repelEnemyForces':
                if not setting._ACTIVE_REST:
                    logger.info("注意, \"休息间隔\"控制连续战斗多少次后回城. 当前未启用休息, 强制设置为1.")
                    setting._RESTINTERVEL = 1
                if setting._RESTINTERVEL == 0:
                    logger.info("注意, \"休息间隔\"控制连续战斗多少次后回城. 当前值0为无效值, 最低为1.")
                    setting._RESTINTERVEL = 1
                logger.info("注意, 该流程不包括时间跳跃和接取任务, 请确保接取任务后再开启!")
                counter = 0
                while 1:
                    if setting._FORCESTOPING.is_set():
                        break
                    t = time.time()
                    RestartableSequenceExecution(
                        lambda : StateInn()
                    )
                    RestartableSequenceExecution(
                        lambda : Press(FindCoordsOrElseExecuteFallbackAndWait('TradeWaterway','EdgeOfTown',1)),
                        lambda : FindCoordsOrElseExecuteFallbackAndWait('7thDist',[1,1],1),
                        lambda : FindCoordsOrElseExecuteFallbackAndWait('dungFlag',['7thDist','GotoDung',[1,1]],1),
                    )
                    RestartableSequenceExecution(
                        lambda : StateDungeon([TargetInfo('position','左下',[559,599]),
                                               TargetInfo('position','左下',[186,813])])
                    )
                    logger.info('已抵达目标地点, 开始战斗.')
                    FindCoordsOrElseExecuteFallbackAndWait('dungFlag',['return',[1,1]],1)
                    for i in range(setting._RESTINTERVEL):
                        logger.info(f"第{i+1}轮开始.")
                        secondcombat = False
                        while 1:
                            Press(FindCoordsOrElseExecuteFallbackAndWait(['icanstillgo','combatActive'],['input swipe 400 400 400 100',[1,1]],1))
                            Sleep(1)
                            if setting._AOE_ONCE:
                                setting._ENOUGH_AOE = False
                            while 1:
                                scn=ScreenShot()
                                if Press(CheckIf(scn,'retry')):
                                    continue
                                if CheckIf(scn,'icanstillgo'):
                                    break
                                if CheckIf(scn,'combatActive'):
                                    StateCombat()
                                else:
                                    Press([1,1])
                            if not secondcombat:
                                logger.info(f"第1场战斗结束.")
                                secondcombat = True
                                Press(CheckIf(ScreenShot(),'icanstillgo'))
                            else:
                                logger.info(f"第2场战斗结束.")
                                Press(CheckIf(ScreenShot(),'letswithdraw'))
                                break
                        logger.info(f"第{i+1}轮结束.")
                    RestartableSequenceExecution(
                        lambda:StateDungeon([TargetInfo('position','左上',[612,448])])
                    )
                    RestartableSequenceExecution(
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait('returnText',[[1,1],'leaveDung','return'],3))
                    )
                    RestartableSequenceExecution(
                        lambda:FindCoordsOrElseExecuteFallbackAndWait('Inn',['return',[1,1]],1)
                    )
                    counter+=1
                    logger.info(f"第{counter}x{setting._RESTINTERVEL}轮\"击退敌势力\"完成, 共计{counter*setting._RESTINTERVEL*2}场战斗. 该次花费时间{(time.time()-t):.2f}秒.",
                                    extra={"summary": True})
            case 'LBC-oneGorgon':
                checkCSC = False
                while 1:
                    if setting._FORCESTOPING.is_set():
                        break
                    if setting._LAPTIME!= 0:
                        setting._TOTALTIME = setting._TOTALTIME + time.time() - setting._LAPTIME
                        logger.info(f"第{setting._COUNTERDUNG}次三牛完成. 本次用时:{round(time.time()-setting._LAPTIME,2)}秒. 累计开箱子{setting._COUNTERCHEST}, 累计战斗{setting._COUNTERCOMBAT}, 累计用时{round(setting._TOTALTIME,2)}秒.",
                                    extra={"summary": True})
                    setting._LAPTIME = time.time()
                    setting._COUNTERDUNG+=1
                    def stepOne():
                        nonlocal checkCSC
                        Press(FindCoordsOrElseExecuteFallbackAndWait('cursedWheel',['ruins',[1,1]],1))
                        Press(FindCoordsOrElseExecuteFallbackAndWait('cursedwheel_impregnableFortress',['cursedWheelTapRight',[1,1]],1))

                        if not Press(CheckIf(ScreenShot(),'LBC/GhostsOfYore')):
                            DeviceShell(f"input swipe 450 1200 450 200")
                            Press(FindCoordsOrElseExecuteFallbackAndWait('LBC/GhostsOfYore','input swipe 50 1200 50 1300',1))

                        while CheckIf(ScreenShot(), 'leap'):
                            if not checkCSC:
                                FindCoordsOrElseExecuteFallbackAndWait('LBC/symbolofalliance','CSC',1)
                                while 1:
                                    scn_b = ScreenShot() *np.array([0, 1, 2])
                                    scaled_image = np.clip(scn_b, 0, 255).astype(np.uint8)
                                    if Press(CheckIf(scaled_image,'LBC/didnottakethequest')):
                                        continue
                                    else:
                                        break
                                Press(CheckIf(ScreenShot(),"LBC/EnaWasSaved"))
                                PressReturn()
                                checkCSC = True
                            Press(CheckIf(ScreenShot(),'leap'))
                            Sleep(2)
                            Press(CheckIf(ScreenShot(),'LBC/GhostsOfYore'))
                    RestartableSequenceExecution(
                        lambda: logger.info('第一步: 重置因果'),
                        lambda: stepOne()
                        )
                    Sleep(10)
                    RestartableSequenceExecution(
                        lambda: logger.info("第二步: 返回要塞"),
                        lambda: FindCoordsOrElseExecuteFallbackAndWait('Inn',['returntotown','returnText','leaveDung','blessing',[1,1]],2)
                        )
                    RestartableSequenceExecution(
                        lambda: logger.info("第三步: 前往王城"),
                        lambda: Press(FindCoordsOrElseExecuteFallbackAndWait('intoWorldMap',[40, 1184],2)),
                        lambda: Press(FindCoordsOrElseExecuteFallbackAndWait('RoyalCityLuknalia','input swipe 450 150 500 150',1)),
                        lambda: FindCoordsOrElseExecuteFallbackAndWait('guild',['RoyalCityLuknalia',[1,1]],1),
                        )
                    
                    def stepFive():
                        scn = ScreenShot()
                        if Press(CheckIf(scn,'LBC/LBC')) or CheckIf(scn,"dungFlag"):
                            pass
                        else:
                            Press(FindCoordsOrElseExecuteFallbackAndWait('intoWorldMap',['closePartyInfo','closePartyInfo_fortress',[1,1]],1))
                            Press(FindCoordsOrElseExecuteFallbackAndWait('LBC/LBC','input swipe 100 100 700 1500',1))
                                           
                    RestartableSequenceExecution(
                        lambda: logger.info('第四步: 领取任务'),
                        lambda: StateAcceptRequest('LBC/Request',[266,257]),
                        lambda: logger.info('第五步: 进入牛洞'),
                        lambda: stepFive()
                        )

                    Gorgon1 = TargetInfo('position','左上',[134,342])
                    Gorgon2 = TargetInfo('position','右上',[500,395])
                    Gorgon3 = TargetInfo('position','右下',[340,1027])
                    LBC_quit = TargetInfo('LBC/LBC_quit')
                    if setting._ACTIVE_REST:
                        RestartableSequenceExecution(
                            lambda: logger.info('第六步: 击杀一牛'),
                            lambda: StateDungeon([Gorgon1,LBC_quit])
                            )
                        RestartableSequenceExecution(
                            lambda: logger.info('第七步: 回去睡觉'),
                            lambda: StateInn()
                            )
                        RestartableSequenceExecution(
                            lambda: logger.info('第八步: 再入牛洞'),
                            lambda: stepFive()
                            )
                        RestartableSequenceExecution(
                            lambda: logger.info('第九步: 击杀二牛'),
                            lambda: StateDungeon([Gorgon2,Gorgon3,LBC_quit])
                            )
                    else:
                        logger.info('跳过回城休息.')
                        RestartableSequenceExecution(
                            lambda: logger.info('第六步: 连杀三牛'),
                            lambda: StateDungeon([Gorgon1,Gorgon2,Gorgon3,LBC_quit])
                            )
            case 'SSC-goldenchest':
                while 1:
                    quest._SPECIALDIALOGOPTION = ['SSC/dotdotdot','SSC/shadow']
                    if setting._FORCESTOPING.is_set():
                        break
                    if setting._LAPTIME!= 0:
                        setting._TOTALTIME = setting._TOTALTIME + time.time() - setting._LAPTIME
                        logger.info(f"第{setting._COUNTERDUNG}次忍洞完成. 本次用时:{round(time.time()-setting._LAPTIME,2)}秒. 累计开箱子{setting._COUNTERCHEST}, 累计战斗{setting._COUNTERCOMBAT}, 累计用时{round(setting._TOTALTIME,2)}秒.",
                                    extra={"summary": True})
                    setting._LAPTIME = time.time()
                    setting._COUNTERDUNG+=1
                    RestartableSequenceExecution(
                        lambda: logger.info('第一步: 重置因果'),
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait('cursedWheel',['ruins',[1,1]],1)),
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait('SSC/Leap',['specialRequest',[1,1]],1)),
                        lambda:Press(FindCoordsOrElseExecuteFallbackAndWait('OK','leap',1)),
                        )
                    Sleep(10)
                    RestartableSequenceExecution(
                        lambda: logger.info("第二步: 前往王城"),
                        lambda: Press(FindCoordsOrElseExecuteFallbackAndWait('intoWorldMap',[40, 1184],2)),
                        lambda: Press(FindCoordsOrElseExecuteFallbackAndWait('RoyalCityLuknalia','input swipe 450 150 500 150',1)),
                        lambda: FindCoordsOrElseExecuteFallbackAndWait('guild',['RoyalCityLuknalia',[1,1]],1),
                        )
                    def stepThree():
                        FindCoordsOrElseExecuteFallbackAndWait('Inn',[1,1],1)
                        StateInn()
                        Press(FindCoordsOrElseExecuteFallbackAndWait('guildRequest',['guild',[1,1]],1))
                        Press(FindCoordsOrElseExecuteFallbackAndWait('guildFeatured',['guildRequest',[1,1]],1))
                        Sleep(1)
                        DeviceShell(f"input swipe 150 1300 150 200")
                        Sleep(2)
                        while 1:
                            pos = CheckIf(ScreenShot(),'SSC/Request')
                            if not pos:
                                DeviceShell(f"input swipe 150 200 150 250")
                                Sleep(1)
                            else:
                                Press([pos[0]+300,pos[1]+150])
                                break
                        FindCoordsOrElseExecuteFallbackAndWait('guildRequest',[1,1],1)
                        PressReturn()
                    RestartableSequenceExecution(
                        lambda: logger.info('第三步: 领取任务'),
                        lambda: stepThree()
                        )
                    def stepFour():
                        scn = ScreenShot()
                        if Press(CheckIf(scn,'SSC/SSC')) or CheckIf(scn,"dungFlag"):
                            pass
                        else:
                            Press(FindCoordsOrElseExecuteFallbackAndWait('intoWorldMap',['closePartyInfo','closePartyInfo_fortress',[1,1]],1))
                            Press(FindCoordsOrElseExecuteFallbackAndWait('SSC/SSC','input swipe 700 100 100 100',1))
                            FindCoordsOrElseExecuteFallbackAndWait('dungFlag',['SSC/SSC',[1,1]],1)
                    RestartableSequenceExecution(
                        lambda: logger.info('第四步: 进入忍洞'),
                        lambda: stepFour()
                        )
                    RestartableSequenceExecution(
                        lambda: logger.info('第五步: 关闭陷阱'),
                        lambda:FindCoordsOrElseExecuteFallbackAndWait('SSC/trapdeactived',['input swipe 450 1050 450 850',[445,721]],4),
                        lambda:FindCoordsOrElseExecuteFallbackAndWait('dungFlag',[1,1],1)
                    )
                    quest._SPECIALDIALOGOPTION = ['SSC/dotdotdot','SSC/shadow']
                    RestartableSequenceExecution(
                        lambda: logger.info('第六步: 第一个箱子'),
                        lambda: StateDungeon([
                                TargetInfo('position',     '左上', [719,1088]),
                                TargetInfo('position',     '左上', [346,874]),
                                TargetInfo('chest',        '左上', [[0,0,900,1600],[640,0,260,1600],[506,0,200,700]]),
                                TargetInfo('chest',        '右上', [[0,0,900,1600],[0,0,407,1600]]),
                                TargetInfo('chest',        '右下', [[0,0,900,1600],[0,0,900,800]]),
                                TargetInfo('chest',        '左下', [[0,0,900,1600],[650,0,250,811],[507,166,179,165]]),
                                TargetInfo('SSC/SSC_quit', '右下', None)
                            ])
                        )
            case 'CaveOfSeperation':
                while 1:
                    if setting._FORCESTOPING.is_set():
                        break
                    if setting._LAPTIME!= 0:
                        setting._TOTALTIME = setting._TOTALTIME + time.time() - setting._LAPTIME
                        logger.info(f"第{setting._COUNTERDUNG}次约定之剑完成. 本次用时:{round(time.time()-setting._LAPTIME,2)}秒. 累计开箱子{setting._COUNTERCHEST}, 累计战斗{setting._COUNTERCOMBAT}, 累计用时{round(setting._TOTALTIME,2)}秒.",
                                    extra={"summary": True})
                    setting._LAPTIME = time.time()
                    setting._COUNTERDUNG+=1
                    def stepOne():
                        Press(FindCoordsOrElseExecuteFallbackAndWait('cursedWheel',['ruins',[1,1]],1))
                        Press(FindCoordsOrElseExecuteFallbackAndWait('cursedwheel_impregnableFortress',['cursedWheelTapRight',[1,1]],1))

                        if not Press(CheckIf(ScreenShot(),'COS/GhostsOfYore')):
                            DeviceShell(f"input swipe 450 1200 450 200")
                            Press(FindCoordsOrElseExecuteFallbackAndWait('COS/GhostsOfYore','input swipe 50 1200 50 1300',1))

                        while CheckIf(ScreenShot(), 'leap'):
                            FindCoordsOrElseExecuteFallbackAndWait('COS/ArnasPast','CSC',1)
                            while 1:
                                scn_b = ScreenShot() *np.array([0, 1, 2])
                                scaled_image = np.clip(scn_b, 0, 255).astype(np.uint8)
                                if Press(CheckIf(scaled_image,'COS/didnottakethequest')):
                                    continue
                                else:
                                    break
                            PressReturn()
                            Press(CheckIf(ScreenShot(),'leap'))
                            Sleep(2)
                            Press(CheckIf(ScreenShot(),'COS/GhostsOfYore'))
                    RestartableSequenceExecution(
                        lambda: logger.info('第一步: 重置因果'),
                        lambda: stepOne()
                        )
                    Sleep(10)
                    RestartableSequenceExecution(
                        lambda: logger.info("第二步: 返回要塞"),
                        lambda: FindCoordsOrElseExecuteFallbackAndWait('Inn',['returntotown','returnText','leaveDung','blessing',[1,1]],2)
                        )
                    RestartableSequenceExecution(
                        lambda: logger.info("第三步: 前往王城"),
                        lambda: Press(FindCoordsOrElseExecuteFallbackAndWait('intoWorldMap',[40, 1184],2)),
                        lambda: Press(FindCoordsOrElseExecuteFallbackAndWait('RoyalCityLuknalia','input swipe 450 150 500 150',1)),
                        lambda: FindCoordsOrElseExecuteFallbackAndWait('guild',['RoyalCityLuknalia',[1,1]],1),
                        )
                    
                    RestartableSequenceExecution(
                        lambda: logger.info('第四步: 领取任务'),
                        lambda: FindCoordsOrElseExecuteFallbackAndWait(['COS/Okay','guildRequest'],['guild',[1,1]],1),
                        lambda: FindCoordsOrElseExecuteFallbackAndWait('Inn',['COS/Okay','return',[1,1]],1),
                        lambda: StateInn(),
                        )
                    
                    RestartableSequenceExecution(
                        lambda: logger.info('第五步: 进入洞窟'),
                        lambda: Press(FindCoordsOrElseExecuteFallbackAndWait('COS/COS',['EdgeOfTown',[1,1]],1)),
                        lambda: Press(FindCoordsOrElseExecuteFallbackAndWait('COS/COSENT',[1,1],1))
                        )
                    quest._SPECIALDIALOGOPTION = ['COS/takehimwithyou']
                    cosb1f = [TargetInfo('position',"右下",[286-54,440]),
                              TargetInfo('position',"右下",[819,653+54]),
                              TargetInfo('position',"右上",[659-54,501]),
                              TargetInfo('stair_down',"右上",[126-54,342]),
                        ]
                    RestartableSequenceExecution(
                        lambda: logger.info('第六步: 1层找人'),
                        lambda: StateDungeon(cosb1f)
                        )

                    quest._SPECIALFORCESTOPINGSYMBOL = ['COS/EnaTheAdventurer']
                    cosb2f = [TargetInfo('position',"右上",[340+54,448]),
                              TargetInfo('position',"右上",[500-54,1088]),
                              TargetInfo('position',"左上",[398+54,766]),
                        ]
                    RestartableSequenceExecution(
                        lambda: logger.info('第七步: 2层找人'),
                        lambda: StateDungeon(cosb2f)
                        )

                    quest._SPECIALFORCESTOPINGSYMBOL = ['COS/requestwasfor'] 
                    cosb3f = [TargetInfo('stair_down',"左上",[720,822]),
                              TargetInfo('position',"左下",[239,600]),
                              TargetInfo('position',"左下",[185,1185]),
                              TargetInfo('position',"左下",[560,652]),
                              ]
                    RestartableSequenceExecution(
                        lambda: logger.info('第八步: 3层找人'),
                        lambda: StateDungeon(cosb3f)
                        )

                    quest._SPECIALFORCESTOPINGSYMBOL = None
                    quest._SPECIALDIALOGOPTION = ['COS/requestwasfor'] 
                    cosback2f = [TargetInfo('stair_up',"左下",[827,547]),
                                 TargetInfo('position',"右上",[340+54,448]),
                                 TargetInfo('position',"右上",[500-54,1088]),
                                 TargetInfo('position',"左上",[398+54,766]),
                                 TargetInfo('position',"左上",[559,1087])
                        ]
                    RestartableSequenceExecution(
                        lambda: logger.info('第九步: 回2楼'),
                        lambda: StateDungeon(cosback2f)
                        )
                    FindCoordsOrElseExecuteFallbackAndWait('dungFlag',['return',[1,1]],1),
                    Press(FindCoordsOrElseExecuteFallbackAndWait("ReturnText",["leaveDung",[455,1200]],3.75)) # 回城
                    # 3.75什么意思 正常循环是3秒 有4次尝试机会 因此3.75秒按一次刚刚好.
                    Press(FindCoordsOrElseExecuteFallbackAndWait("guild",['return',[1,1]],1)) # 回城
                    FindCoordsOrElseExecuteFallbackAndWait("Inn",['return',[1,1]],1)
                    
                pass
        setting._FINISHINGCALLBACK()
        return
    def Farm(set:FarmConfig):
        nonlocal setting
        nonlocal quest
        setting = set

        if not StartAdbServer(setting):
            setting._FINISHINGCALLBACK()
            return
        setting._ADBDEVICE = CreateAdbDevice(setting)

        quest = LoadQuest(setting._FARMTARGET)
        if quest._TYPE =="dungeon":
            DungeonFarm()
        else:
            QuestFarm()
    return Farm