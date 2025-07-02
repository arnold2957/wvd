from ppadb.client import Client as AdbClient
import numpy as np
import cv2
import time
from win10toast import ToastNotifier
from scipy.optimize import curve_fit
from scipy.signal import find_peaks
from enum import Enum
from datetime import datetime
import sys
import os
import subprocess
import socket
import time
from utils import *

class FarmSetting:
    _FARMTARGET = "shiphold"
    _DUNGWAITTIMEOUT = 0
    _LAPTIME = 0
    _COUNTERDUNG = 0
    _COUNTERCOMBAT = 0
    _COUNTERCHEST = 0
    _SPELLSKILLCONFIG = None
    _SYSTEMAUTOCOMBAT = False
    _RANDOMLYOPENCHEST = True
    _WHOWILLOPENIT = 0
    _FORCESTOPING = None
    _FINISHINGCALLBACK = None
    _COMBATSPD = False
    _RESTINTERVEL = 0
    _SKIPCOMBATRECOVER = False
    _ADBDEVICE = None
    _LOGGER = None
    _TARGETLIST = None
    _TARGETSEARCHDIR = None
    _TARGETROI = None
    _SPECIALDIALOGOPTION = None
    _SUICIDE = False # 当有两个人死亡的时候(multipeopledead), 在战斗中尝试自杀.
    _ADBPATH = None
    _ADBPORT = None
    _MAXRETRYLIMIT = 20
    _KARMAADJUST = "+0"

def resource_path(relative_path):
    """ 获取资源的绝对路径，适用于开发环境和 PyInstaller 打包环境 """
    try:
        # PyInstaller 创建一个临时文件夹并将路径存储在 _MEIPASS 中
        base_path = sys._MEIPASS
    except Exception:
        # 未打包状态 (开发环境)
        # 假设 script.py 位于 C:\Users\Arnold\Desktop\andsimscripts\src\
        # 并且 resources 位于 C:\Users\Arnold\Desktop\andsimscripts\resources\
        # 我们需要从 script.py 的目录 (src) 回到上一级 (andsimscripts)
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        # 如果你的 script.py 和 resources 文件夹都在项目根目录，则 base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)
def StartAdbServer(setting: FarmSetting):
    def check_adb_connection():
        try:
            # 创建socket检测端口连接
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)  # 设置超时时间
            result = sock.connect_ex(("127.0.0.1", 5037))
            return result == 0  # 返回0表示连接成功
        except Exception as e:
            setting._LOGGER.info(f"连接检测异常: {str(e)}")
            return False
        finally:
            sock.close()
    try:
        if not check_adb_connection():
            setting._LOGGER.info(f"开始启动ADB服务, 路径:{setting._ADBPATH}")
            # 启动adb服务（非阻塞模式）
            subprocess.Popen(
                [setting._ADBPATH, "start-server"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True
            )
            setting._LOGGER.info("ADB 服务启动中...")
            
            # 循环检测连接（最多重试5次）
            for _ in range(5):
                if check_adb_connection():
                    setting._LOGGER.info("ADB 连接成功")
                    return True
                time.sleep(1)  # 每次检测间隔1秒
            
            setting._LOGGER.info("ADB 连接超时")
            return False
        else:
            return True
    except Exception as e:
        setting._LOGGER.info(f"启动ADB失败: {str(e)}")
        return False
def CreateAdbDevice(setting: FarmSetting):
    client = AdbClient(host="127.0.0.1", port=5037)

    target_device = f"127.0.0.1:{setting._ADBPORT}"
    connected_devices = [d.serial for d in client.devices()]
    if target_device in connected_devices:
        # 设备已连接时才断开
        client.remote_disconnect("127.0.0.1", int(setting._ADBPORT))
        time.sleep(0.5)

    setting._LOGGER.info(f"尝试创建adb连接 127.0.0.1:{setting._ADBPORT}...")
    client.remote_connect("127.0.0.1", int(setting._ADBPORT))
    devices = client.devices()
    if (not devices) or not (devices[0]):
        setting._LOGGER.info("创建adb链接失败.")
        setting._FINISHINGCALLBACK()
        return
    return devices[0]

def Factory():
    toaster = ToastNotifier()
    device = None
    logger = None
    setting =  None
    ##################################################################
    def Sleep(t=1):
        time.sleep(t)
    def ScreenShot():
        while True:
            try:
                logger.debug('ScreenShot')
                screenshot = device.screencap()
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
            except (RuntimeError, ConnectionResetError, cv2.error) as e:
                logger.debug(f"{e}")
                logger.info("adb重启中...")
                while 1:
                    if StartAdbServer(setting):
                        setting._ADBDEVICE = CreateAdbDevice(setting)
                        break
                continue
    def _CheckIfLoadImage(shortPathOfTarget):
        logger.debug(f"加载{shortPathOfTarget}")
        pathOfTarget = resource_path(fr'resources/images/{shortPathOfTarget}.png')
        try:
            # 尝试读取图片
            template = cv2.imread(pathOfTarget, cv2.IMREAD_COLOR)
            if template is None:
            # 手动抛出异常
                raise ValueError(f"[OpenCV 错误] 图片加载失败，路径可能不存在或图片损坏: {pathOfTarget}(注意: 路径中不能包含中文.)")
        except Exception as e:
            setting._FORCESTOPING.set()
            logger.info(f"加载图片失败: {str(e)}")
            return None
        return template
    def CheckIf(pathOfScreen, shortPathOfTarget, roi = None, outputMatchResult = False):
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
            
            # cv2.imwrite('cutRoI.png', screenshot)
            return screenshot
        
        nonlocal setting
        template = _CheckIfLoadImage(shortPathOfTarget)
        screenshot = pathOfScreen
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
    def CheckIf_MultiRect(pathOfScreen, shortPathOfTarget):
        template = _CheckIfLoadImage(shortPathOfTarget)
        screenshot = pathOfScreen
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
    def CheckIf_FocusCursor(pathOfScreen, shortPathOfTarget):
        template = _CheckIfLoadImage(shortPathOfTarget)
        screenshot = pathOfScreen
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
    def Press(pos):
        if pos!=None:
            logger.debug(f'按了{pos[0]} {pos[1]}')
            device.shell(f"input tap {pos[0]} {pos[1]}")
            return True
        return False
    def PressReturn():
        logger.debug("按了返回.")
        device.shell('input keyevent KEYCODE_BACK')
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
                def pressTarget(target):
                    if target.lower() == 'return':
                        PressReturn()
                    elif target.startswith("input swipe"):
                        device.shell(target)
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
            
            logger.info(f"{setting._MAXRETRYLIMIT}次截图依旧没有找到目标, 疑似卡死. 重启游戏.")
            Sleep()
            restartGame()
            return None # restartGame会抛出异常 所以直接返回none就行了
    def restartGame(skipScreenShot = False):
        nonlocal setting
        setting._COMBATSPD = False # 重启会重置2倍速, 所以重置标识符以便重新打开.
        setting._MAXRETRYLIMIT = min(50, setting._MAXRETRYLIMIT + 5) # 每次重启后都会增加5次尝试次数, 以避免不同电脑导致的反复重启问题.

        if not skipScreenShot:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # 格式：20230825_153045
            file_path = os.path.join("screenshotwhenrestart", f"{timestamp}.png")
            cv2.imwrite(file_path, ScreenShot())
            logger.info(f"重启前截图已保存在{file_path}中.")
        else:
            logger.info(f"因为外部设置, 跳过了重启前截图.")

        package_name = "jp.co.drecom.wizardry.daphne"
        mainAct = device.shell(f"cmd package resolve-activity --brief {package_name}").strip().split('\n')[-1]
        device.shell(f"am force-stop {package_name}")
        Sleep(2)
        logger.info("巫术, 启动!")
        logger.debug(device.shell(f"am start -n {mainAct}"))
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
    def getCursorCoordinates(input, template_path, threshold=0.8):
        """在本地图片中查找模板位置"""
        template = cv2.imread(resource_path(fr'resources/images/{template_path}.png'))
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
        t0 = float(device.shell("date +%s.%N").strip())
        while 1:
            while 1:
                Sleep(0.2)
                t = float(device.shell("date +%s.%N").strip())
                s = ScreenShot()
                x = getCursorCoordinates(s,'cursor')
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

            t = float(device.shell("date +%s.%N").strip())
            s = ScreenShot()
            x = getCursorCoordinates(s,'cursor')
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
                    device.shell(f"input tap 450 900") # 这里和retry重合 可以按.
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
                ('flee',          DungeonState.Combat),
                ('dungFlag',      DungeonState.Dungeon),
                ('chestFlag',     DungeonState.Chest),
                ('whowillopenit', DungeonState.Chest),
                ('mapFlag',       DungeonState.Map)
                ]
            for pattern, state in identifyConfig:
                if CheckIf(screen, pattern):
                    return State.Dungeon, state, screen

            while CheckIf(screen,'someonedead'):
                Press([400,800])
                Sleep(1)
                screen = ScreenShot()

            if Press(CheckIf(screen, "Return")):
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

            if counter>=4:
                logger.info("看起来遇到了一些不太寻常的情况...")
                if setting._SPECIALDIALOGOPTION != None:
                    for option in setting._SPECIALDIALOGOPTION:
                        if Press(CheckIf(ScreenShot(),option)):
                            return IdentifyState()
                if (CheckIf(screen,'RiseAgain')):
                    setting._SUICIDE = False # 死了 自杀成功 设置为false
                    logger.info("快快请起.")
                    # logger.info("REZ.")
                    Press([450,750])
                    Sleep(10)
                    return IdentifyState()
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
                    logger.info("有骨头的话我会买的. 但是现在我没有骨头的识别图片啊.")
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
                black = _CheckIfLoadImage("blackScreen")
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
            if totalDiff<=0.1:
                return queue, True
        return queue, False
    def StateInn():
        Press(FindCoordsOrElseExecuteFallbackAndWait('Inn',[1,1],1))
        Press(FindCoordsOrElseExecuteFallbackAndWait('Stay',['Inn',[1,1]],2))
        Press(FindCoordsOrElseExecuteFallbackAndWait('Economy',['Stay',[1,1]],2))
        Press(FindCoordsOrElseExecuteFallbackAndWait('OK',['Economy',[1,1]],2))
        FindCoordsOrElseExecuteFallbackAndWait('Stay',['OK',[299,1464]],2)
        PressReturn()
    def StateEoT():
        match setting._FARMTARGET:
            case "shiphold":
                Press(FindCoordsOrElseExecuteFallbackAndWait('TradeWaterway',['EdgeOfTown',[1,1]],1))
                Press(FindCoordsOrElseExecuteFallbackAndWait('shiphold',[1,1],1))
            case "lounge":
                Press(FindCoordsOrElseExecuteFallbackAndWait('TradeWaterway',['EdgeOfTown',[1,1]],1))
                Press(FindCoordsOrElseExecuteFallbackAndWait('lounge',[1,1],1))
            case "LBC":
                if Press(CheckIf(ScreenShot(),'LBC')):
                    pass
                else:
                    Press(FindCoordsOrElseExecuteFallbackAndWait('intoWorldMap',['closePartyInfo',[1,1]],1))
                    Press(FindCoordsOrElseExecuteFallbackAndWait('LBC','input swipe 100 100 700 1500',1))
            case "SSC":
                if Press(CheckIf(ScreenShot(),'SSC')):
                    pass
                else:
                    Press(FindCoordsOrElseExecuteFallbackAndWait('intoWorldMap',['closePartyInfo',[1,1]],1))
                    Press(FindCoordsOrElseExecuteFallbackAndWait('SSC','input swipe 700 100 100 100',1))
            case "fordraig-B3F":
                if Press(CheckIf(ScreenShot(),'fordraig/B3F')):
                    pass
                else:
                    Press(FindCoordsOrElseExecuteFallbackAndWait('intoWorldMap',[40, 1184],2))
                    Press(FindCoordsOrElseExecuteFallbackAndWait('labyrinthOfFordraig','input swipe 450 150 500 150',1))               
                    Press(FindCoordsOrElseExecuteFallbackAndWait('fordraig/B3F',['labyrinthOfFordraig',[1,1]],1))
            case 'fortress-B3F':
                Press(FindCoordsOrElseExecuteFallbackAndWait('impregnableFortress',['EdgeOfTown',[1,1]],1))
                Press(FindCoordsOrElseExecuteFallbackAndWait('fortressb3f', 'input swipe 650 250 650 900',1))
            case "Dist":
                Press(FindCoordsOrElseExecuteFallbackAndWait('TradeWaterway',['EdgeOfTown',[1,1]],1))
                Press(FindCoordsOrElseExecuteFallbackAndWait('Dist', 'input swipe 650 250 650 900',1))
            case "DOE":
                Press(FindCoordsOrElseExecuteFallbackAndWait('DOE',['EdgeOfTown',[1,1]],1))
                Press(FindCoordsOrElseExecuteFallbackAndWait('DOEB1F',[1,1],1))
            case "DOL":
                Press(FindCoordsOrElseExecuteFallbackAndWait('DOL',['EdgeOfTown',[1,1]],1))
                Press(FindCoordsOrElseExecuteFallbackAndWait('DOLB1F',[1,1],1))
            case "DOF":
                Press(FindCoordsOrElseExecuteFallbackAndWait('DOF',['EdgeOfTown',[1,1]],1))
                Press(FindCoordsOrElseExecuteFallbackAndWait('DOFB1F',[1,1],1))
            case "DOW":
                Press(FindCoordsOrElseExecuteFallbackAndWait('DOW',['EdgeOfTown',[1,1]],1))
                Press(FindCoordsOrElseExecuteFallbackAndWait('DOWB1F',[1,1],1))
        Sleep(1)
        Press(CheckIf(ScreenShot(), 'GotoDung'))
    def StateCombat():
        nonlocal setting
        screen = ScreenShot()
        if not setting._COMBATSPD:
            if Press(CheckIf(screen,'combatSpd')):
                setting._COMBATSPD = True

        if setting._SUICIDE:
            Press(CheckIf(screen,'defend'))
        elif setting._SYSTEMAUTOCOMBAT:
            Press(CheckIf(screen,'combatAuto'))
            Sleep(5)
        else:
            castSpellSkill = False
            for skillspell in setting._SPELLSKILLCONFIG:
                if Press(CheckIf(screen, 'spellskill/'+skillspell)):
                    logger.info(f"使用了技能 {skillspell}")
                    Sleep(1)
                    Press([150,750])
                    Press([300,750])
                    Press([450,750])
                    Press([550,750])
                    Press([650,750])
                    Press([750,750])
                    Press(CheckIf(ScreenShot(),'OK'))
                    Sleep(3)
                    castSpellSkill = True
                    break
            if not castSpellSkill:
                Press([850,1100])
                Press([850,1100])
                Sleep(3)
    def StateMap_FindSwipeClick(target,searchDir = None, roi = None):
        if searchDir == None:
            searchDir = [None,
                        [100,100,700,1200],
                        [400,1200,400,100],
                        [700,800,100,800],
                        [400,100,400,1200],
                        [100,800,700,800],
                        ]
        targetPos = None
        for i in range(len(searchDir)):
            if searchDir[i]!=None:
                device.shell(f"input swipe {searchDir[i][0]} {searchDir[i][1]} {searchDir[i][2]} {searchDir[i][3]}")
                Sleep(2)

            map = ScreenShot()
            if not CheckIf(map,'mapFlag'):
                return None # 发生了错误
            
            targetPos = None
            if (target == 'chest'):
                if roi==None:
                    roi = [[0,0,900,1600]]
                roi += [[0,0,900,208],[0,1265,900,335],[0,636,137,222],[763,636,137,222], [336,208,228,77],[336,1168,228,97]]
            if targetPos:=CheckIf(map,target,roi):
                logger.info(f'找到了 {target}! {targetPos}')
                if not roi:
                    # 固定视角的情况下, 跳过二次确认
                    logger.debug(f"拖动: {targetPos[0]},{targetPos[1]} -> 450,800")
                    device.shell(f"input swipe {targetPos[0]} {targetPos[1]} 450 800")
                    Sleep(2)
                    Press([1,230])
                    targetPos = CheckIf(ScreenShot(),target,roi)
                break # return targetPos
        return targetPos
    def StateMoving_CheckFrozen(): # return current DungeonState
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
    def StateSearch(targetList:list[str],waitTimer,searchDirList=None, roiList = None):
        normalPlace = ['harken','chest','leaveDung']
        target = targetList[0]
        roi = roiList[len(roiList)-len(targetList)] if roiList is not None else None
        searchDir = searchDirList[len(searchDirList)-len(targetList)] if searchDirList is not None else None
        if target == None:
            logger.debug("当前目标为空, 跳过.")
            targetList.pop(0)
            return None,targetList
        logger.info(f"当前目标:{target}")
        # 地图已经打开.
        map = ScreenShot()
        if not CheckIf(map,'mapFlag'):
                return None,targetList # 发生了错误
        if not (pos:=StateMap_FindSwipeClick(target,searchDir,roi)):
            logger.info(f"没有找到{target}.")
            if target == 'chest' or target.endswith('_once'):
                targetList.pop(0)
                logger.info(f"不再搜索{target}") 
            return DungeonState.Map,  targetList
        else:
            if target in normalPlace or target.endswith("_quit"):
                Press(pos)
                Press([280,1433]) # automove
                return StateMoving_CheckFrozen(),targetList
            else:
                if (CheckIf_FocusCursor(ScreenShot(),target)): #注意 这里通过二次确认 我们可以看到目标地点 而且是未选中的状态
                    logger.info("经过对比中心区域, 确认没有抵达.")
                    Press(pos)
                    Press([280,1433]) # automove
                    return StateMoving_CheckFrozen(),targetList
                else:
                    logger.info("经过对比中心区域, 判断为抵达目标地点.")
                    logger.info('开始等待...等待...')
                    PressReturn()
                    PressReturn()
                    while 1:
                        if setting._DUNGWAITTIMEOUT-time.time()+waitTimer<0:
                            logger.info("等得够久了. 目标地点完成.")
                            targetList.pop(0)
                            Sleep(1)
                            Press([777,150])
                            return None,  targetList
                        logger.info(f'还需要等待{setting._DUNGWAITTIMEOUT-time.time()+waitTimer}秒.')
                        if CheckIf(ScreenShot(),'flee'):
                            return DungeonState.Combat,targetList                
        return DungeonState.Map,  targetList
    def StateChest():
        FindCoordsOrElseExecuteFallbackAndWait('whowillopenit', ['chestFlag',[1,1]],1)
        tryOpenCounter = 0
        MSXTRYOPEN = 5
        MAXERROROPEN = 50
        while 1:
            scn = ScreenShot()
            Press(CheckIf(scn,'chestFlag'))
            if CheckIf(scn,'whowillopenit'):
                if tryOpenCounter>MSXTRYOPEN or setting._WHOWILLOPENIT == 0:
                    whowillopenit = tryOpenCounter # 如果超过尝试次数或者根本就是设置了随机开箱, 那么用尝试次数作为序号
                else:
                    whowillopenit = setting._WHOWILLOPENIT - 1 # 否则, 使用指定的序号
                Press([200+(whowillopenit%3)*200, 1200+((whowillopenit)//3)%2*150])
                Sleep(1)
            Press([1,1])
            if CheckIf(ScreenShot(),'chestOpening'):
                Sleep(1)
                if not setting._RANDOMLYOPENCHEST:
                    while 1:
                        screen = ScreenShot()
                        if Press(CheckIf(screen,'retry')):
                            logger.info("发现并点击了\"重试\". 你遇到了网络波动.")
                            Sleep(1)
                            screen = ScreenShot()
                        if CheckIf(screen, 'chestOpening'):
                            Press([450,900])
                        else:
                            break
                else:
                    if CheckIf(ScreenShot(),'chestOpening'):
                        ChestOpen()
                return None
            if CheckIf(ScreenShot(),'dungFlag'):
                return DungeonState.Dungeon
            if CheckIf(ScreenShot(),'flee'):
                return DungeonState.Combat
            if Press(CheckIf(ScreenShot(),'retry')):
                logger.info("发现并点击了\"重试\". 你遇到了网络波动.")
                continue
            tryOpenCounter += 1
            logger.info(f"似乎选择人物失败了,当前已经尝次数:{tryOpenCounter}.")
            if tryOpenCounter <=MSXTRYOPEN:
                logger.info(f"尝试{MSXTRYOPEN}次后若失败则会变为随机开箱.")
            else:
                logger.info(f"随机开箱已经启用.")
            if tryOpenCounter > MAXERROROPEN:
                logger.info(f"错误: 尝试次数过多. 疑似卡死.")
                return None
            
    def StateDungeon(specialTargetList = None):
        gameFrozen_none = []
        gameFrozen_map = []
        dungState = None
        shouldRecover = False
        waitTimer = time.time()
        if specialTargetList == None:
            targetList = setting._TARGETLIST.copy() # copy()很重要 不然就是引用传进去了
        else:
            targetList = specialTargetList
        needRecoverBecauseCombat = False
        needRecoverBecauseChest = False
        while 1:
            logger.info("----------------------")
            if setting._FORCESTOPING.is_set():
                logger.info("即将中断脚本...")
                dungState = DungeonState.Quit
            logger.info(f"当前状态(地下城): {dungState}")

            match dungState:
                case None:
                    gameFrozen_none, result = GameFrozenCheck(gameFrozen_none,ScreenShot())
                    if result:
                        restartGame()
                    s, dungState,_ = IdentifyState()
                    if (s == State.Inn)or(s == DungeonState.Quit):
                        break
                case DungeonState.Quit:
                    break
                case DungeonState.Dungeon:
                    Press([1,1]) # interrupt auto moving
                    if needRecoverBecauseChest:
                        logger.info("进行开启宝箱后的恢复.")
                        setting._COUNTERCHEST+=1
                        needRecoverBecauseChest = False
                        shouldRecover = True
                    if needRecoverBecauseCombat:
                        setting._COUNTERCOMBAT+=1
                        needRecoverBecauseCombat = False
                        if (not setting._SKIPCOMBATRECOVER):
                            logger.info("由于面板配置, 进行战后恢复.")
                            shouldRecover = True
                    if shouldRecover:
                        Press([1,1])
                        Press([450,1300])
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
                    Sleep(1)
                    Press([777,150])
                    Sleep(1)
                    dungState = DungeonState.Map
                case DungeonState.Map:
                    gameFrozen_map, result = GameFrozenCheck(gameFrozen_map,ScreenShot())
                    if result:
                        restartGame()
                    dungState, targetList = StateSearch(targetList,waitTimer, setting._TARGETSEARCHDIR, setting._TARGETROI)
                    if (targetList==None) or (targetList == []):
                        logger.info("地下城目标完成. 地下城状态结束.(仅限任务模式.)")
                        break
                case DungeonState.Chest:
                    needRecoverBecauseChest = True
                    dungState = StateChest()
                case DungeonState.Combat:
                    needRecoverBecauseCombat =True
                    StateCombat()
                    dungState = None

    def StreetFarm(set:FarmSetting):
        nonlocal setting
        nonlocal device
        nonlocal logger
        setting = set
        device = setting._ADBDEVICE
        logger = setting._LOGGER
        if setting._TARGETSEARCHDIR and setting._TARGETROI:
            if len(setting._TARGETLIST)!=len(setting._TARGETSEARCHDIR) or len(setting._TARGETLIST)!= len(setting._TARGETROI):
                logger.info("警告: 数据的长度不一致")
                return 
        state = None
        while 1:
            logger.info("======================")
            Sleep(1)
            if setting._FORCESTOPING.is_set():
                logger.info("即将中断脚本...")
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
                        logger.info("即将中断脚本...")
                        break
                case State.Inn:
                    if setting._LAPTIME!= 0:
                        logger.info(f"第{setting._COUNTERDUNG}次地下城完成. 用时:{time.time()-setting._LAPTIME}. 累计开箱子{setting._COUNTERCHEST}, 累计战斗{setting._COUNTERCOMBAT}")
                    setting._LAPTIME = time.time()
                    setting._COUNTERDUNG+=1

                    if (setting._COUNTERDUNG-1) % (setting._RESTINTERVEL+1) == 0:
                        logger.info("休息时间到!")
                        RestartableSequenceExecution(
                        lambda:StateInn()
                        )
                    else:
                        logger.info("还有许多地下城要刷. 面具男, 现在还不能休息哦.")
                    state = State.EoT
                case State.EoT:
                    RestartableSequenceExecution(
                        lambda:StateEoT()
                        )
                    state = State.Dungeon
                case State.Dungeon:
                    RestartableSequenceExecution(
                        lambda: StateDungeon()
                        )
                    state = None
        setting._FINISHINGCALLBACK()
    def QuestFarm(set:FarmSetting):
        nonlocal setting
        nonlocal device
        nonlocal logger
        setting = set
        device = setting._ADBDEVICE
        logger = setting._LOGGER
        match setting._FARMTARGET:
            case '7000G':                    
                stepNo = 1
                while 1:
                    match stepNo:
                        case 1:
                            starttime = time.time()
                            setting._COUNTERDUNG += 1
                            def stepMain():
                                logger.info("第一步: 开始诅咒之旅...")
                                Press(FindCoordsOrElseExecuteFallbackAndWait('cursedWheel',['ruins',[1,1]],1))
                                Press(FindCoordsOrElseExecuteFallbackAndWait('cursedwheel_impregnableFortress',['cursedWheelTapRight',[1,1]],1))

                                if not Press(CheckIf(ScreenShot(),'FortressArrival')):
                                    device.shell(f"input swipe 450 1200 450 200")
                                    Press(FindCoordsOrElseExecuteFallbackAndWait('FortressArrival','input swipe 50 1200 50 1300',1))
                                
                                while pos:= CheckIf(ScreenShot(), 'leap'):
                                    Press(pos)
                                    Sleep(2)
                                    Press(CheckIf(ScreenShot(),'FortressArrival'))
                            RestartableSequenceExecution(
                                lambda: stepMain()
                                )
                            stepNo = 2
                        case 2:
                            Sleep(10)
                            logger.info("第二步: 从要塞返回王城...")                                
                            RestartableSequenceExecution(
                                lambda: FindCoordsOrElseExecuteFallbackAndWait('Inn',['returntotown','returnText','leaveDung','blessing',[1,1]],2)
                                )
                            stepNo = 3
                        case 3:
                            logger.info("第三步: 前往王城...")
                            RestartableSequenceExecution(
                                lambda:Press(FindCoordsOrElseExecuteFallbackAndWait('intoWorldMap',[40, 1184],2)),
                                lambda:Press(FindCoordsOrElseExecuteFallbackAndWait('RoyalCityLuknalia','input swipe 450 150 500 150',1)),
                                lambda:FindCoordsOrElseExecuteFallbackAndWait('guild',['RoyalCityLuknalia',[1,1]],1),
                                )
                            stepNo = 4
                        case 4:
                            logger.info("第四步: 给我!(伸手)")
                            Press(FindCoordsOrElseExecuteFallbackAndWait('guild',[1,1],1))
                            Press(FindCoordsOrElseExecuteFallbackAndWait('7000G/illgonow',[1,1],1))
                            Sleep(15)
                            stepMark = 0
                            def stepMain():
                                nonlocal stepMark
                                if stepMark <= 3:
                                    FindCoordsOrElseExecuteFallbackAndWait(['7000G/olddist','7000G/iminhungry'],[1,1],2)
                                    if pos:=CheckIf(scn:=ScreenShot(),'7000G/olddist'):
                                        Press(pos)
                                    else:
                                        Press(CheckIf(scn,'7000G/iminhungry'))
                                        Press(FindCoordsOrElseExecuteFallbackAndWait('7000G/olddist',[1,1],2))
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
                            logger.info(f"第{setting._COUNTERDUNG}次\"7000G\"完成. 该次花费时间{costtime:.2f}, 每秒收益:{7000/costtime:.2f}Gps.")
                            if not setting._FORCESTOPING.is_set():
                                stepNo = 1
                            else:
                                break
            case 'fordraig':
                stepNo = 1
                setting._SYSTEMAUTOCOMBAT = True
                setting._SPECIALDIALOGOPTION = ['fordraig/thedagger']
                while 1:
                    match stepNo:
                        case 1:
                            setting._COUNTERDUNG += 1
                            logger.info(setting._COUNTERDUNG)
                            starttime = time.time()
                            logger.info('第一步: 诅咒之旅...')
                            RestartableSequenceExecution(
                                lambda:Press(FindCoordsOrElseExecuteFallbackAndWait('cursedWheel',['ruins',[1,1]],1)),
                                lambda:Press(FindCoordsOrElseExecuteFallbackAndWait('Fordraig/Leap',['specialRequest',[1,1]],1)),
                                lambda:Press(FindCoordsOrElseExecuteFallbackAndWait('OK','leap',1)),
                                )
                            Sleep(15)
                            stepNo = 2
                        case 2:
                            logger.info('第二步: 领取任务.')
                            FindCoordsOrElseExecuteFallbackAndWait('Inn',[1,1],1)
                            StateInn()
                            Press(FindCoordsOrElseExecuteFallbackAndWait('guildRequest',['guild',[1,1]],1))
                            Press(FindCoordsOrElseExecuteFallbackAndWait('guildFeatured',['guildRequest',[1,1]],1))
                            Sleep(1)
                            device.shell(f"input swipe 450 1000 450 200")
                            while 1:
                                pos = CheckIf(ScreenShot(),'fordraig/RequestAccept')
                                if not pos:
                                    device.shell(f"input swipe 50 1200 50 1300")
                                else:
                                    Press([pos[0]+350,pos[1]+180])
                                    break
                            FindCoordsOrElseExecuteFallbackAndWait('guildRequest',[1,1],1)
                            PressReturn()
                            stepNo = 3
                        case 3:
                            logger.info('第三步: 进入地下城.')
                            Press(FindCoordsOrElseExecuteFallbackAndWait('intoWorldMap',[40, 1184],2))
                            Press(FindCoordsOrElseExecuteFallbackAndWait('labyrinthOfFordraig','input swipe 450 150 500 150',1))                            
                            Press(FindCoordsOrElseExecuteFallbackAndWait('fordraig/Entrance',['labyrinthOfFordraig',[1,1]],1))
                            stepNo = 4
                        case 4:
                            logger.info('第四步: 陷阱.')
                            RestartableSequenceExecution(
                                lambda:StateDungeon(['fordraig/b1fquit','fordraig/firstTrap',None]), # 前往第一个陷阱
                                lambda:FindCoordsOrElseExecuteFallbackAndWait("dungFlag","return",1), # 关闭地图
                                lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("fordraig/TryPushingIt",["input swipe 100 250 800 250",[400,800],[400,800],[400,800]],1)), # 转向来开启机关
                                
                                )
                            logger.info('已完成第一个陷阱.')
                            FindCoordsOrElseExecuteFallbackAndWait(["fordraig/B2Fentrance","fordraig/thedagger"],[50,950],1) # 移动到下一层
                            RestartableSequenceExecution(
                                lambda:StateDungeon(['fordraig/SecondTrap',None]), #前往第二个陷阱, 这个有几率中断啊
                                lambda:FindCoordsOrElseExecuteFallbackAndWait("dungFlag","return",1), # 关闭地图
                                lambda:Press(FindCoordsOrElseExecuteFallbackAndWait("fordraig/TryPushingIt",["input swipe 100 250 800 250",[400,800],[400,800],[400,800]],1)), # 转向来开启机关
                                )
                            logger.info('已完成第二个陷阱.')
                            FindCoordsOrElseExecuteFallbackAndWait("mapFlag",[777,150],1) # 开启地图
                            FindCoordsOrElseExecuteFallbackAndWait("dungFlag",([35,1241],[280,1433]),1) # 前往左下角
                            FindCoordsOrElseExecuteFallbackAndWait("mapFlag",[777,150],1) # 开启地图
                            StateDungeon(['fordraig/B2Fquit',None])
                            FindCoordsOrElseExecuteFallbackAndWait("dungFlag","return",1)
                            FindCoordsOrElseExecuteFallbackAndWait("fordraig/B3fentrance","input swipe 400 1200 400 200",1)
                            StateDungeon(['fordraig/thirdMach',None]) #前往boss战
                            FindCoordsOrElseExecuteFallbackAndWait("dungFlag","return",1) # 关闭地图
                            Press(FindCoordsOrElseExecuteFallbackAndWait("fordraig/InsertTheDagger",[850,950],1)) # 第三个机关
                            logger.info('已完成第三个机关.')
                            FindCoordsOrElseExecuteFallbackAndWait("fordraig/B4F","input swipe 400 1200 400 200",1) # 前往下一层
                            StateDungeon(['fordraig/readytoBoss',None])
                            setting._SYSTEMAUTOCOMBAT = False
                            StateDungeon(['fordraig/SecondBoss',None]) # 前往boss战斗
                            setting._SYSTEMAUTOCOMBAT = True
                            StateDungeon(['fordraig/B4Fquit',None]) # 第四层出口
                            FindCoordsOrElseExecuteFallbackAndWait("dungFlag","return",1) 
                            Press(FindCoordsOrElseExecuteFallbackAndWait("return",["leaveDung",[455,1200]],3.75)) # 回城
                            # 3.75什么意思 正常循环是3秒 有4次尝试机会 因此3.75秒按一次刚刚好.
                            Press(FindCoordsOrElseExecuteFallbackAndWait("RoyalCityLuknalia",['return',[1,1]],1)) # 回城
                            FindCoordsOrElseExecuteFallbackAndWait("Inn",[1,1],1)

                            costtime = time.time()-starttime
                            logger.info(f"第{setting._COUNTERDUNG}次\"鸟剑\"完成. 该次花费时间{costtime:.2f}.")
                            if not setting._FORCESTOPING.is_set():
                                stepNo = 1
                            else:
                                break
            case 'repelEnemyForces':
                if setting._RESTINTERVEL == 0:
                    logger.info("注意, \"休息间隔\"控制连续战斗多少次后回城. 当前值0为无效值, 最低为1.")
                    setting._RESTINTERVEL = 1
                logger.info("注意, 该流程不包括时间跳跃和接取任务, 请确保接取任务后再开启!")
                counter = 0
                while 1:
                    t = time.time()

                    StateInn()
                    Press(FindCoordsOrElseExecuteFallbackAndWait('TradeWaterway','EdgeOfTown',1))
                    FindCoordsOrElseExecuteFallbackAndWait('7thDist',[1,1],1)
                    FindCoordsOrElseExecuteFallbackAndWait('dungFlag',['7thDist','GotoDung',[1,1]],1)
                    StateDungeon(['repelEnemyForcesMid','repelEnemyForces',None])
                    logger.info('已抵达目标地点, 开始战斗.')
                    FindCoordsOrElseExecuteFallbackAndWait('dungFlag',['return',[1,1]],1)
                    for i in range(setting._RESTINTERVEL):
                        logger.info(f"第{i+1}轮开始.")
                        secondcombat = False
                        while 1:
                            FindCoordsOrElseExecuteFallbackAndWait(['flee','icanstillgo'],['input swipe 400 400 400 100',[1,1]],1)
                            if CheckIf(scn:=ScreenShot(),'flee'):
                                StateCombat()
                            elif pos:=CheckIf(scn,'icanstillgo'):
                                if secondcombat:
                                    logger.info(f"第2场战斗结束.")
                                    Press(CheckIf(scn,'letswithdraw'))
                                    break
                                logger.info(f"第1场战斗结束.")
                                secondcombat = True
                                Press(pos)
                        logger.info(f"第{i+1}轮结束.")
                    Press(FindCoordsOrElseExecuteFallbackAndWait('returnText',[[1,1],'leaveDung'],3))
                    FindCoordsOrElseExecuteFallbackAndWait('Inn',['return',[1,1]],1)
                    counter+=1
                    logger.info(f"第{counter}x{setting._RESTINTERVEL}轮\"击退敌势力\"完成, 共计{counter*setting._RESTINTERVEL*2}场战斗. 该次花费时间{(time.time()-t):.2f}秒.")

        setting._FINISHINGCALLBACK()
        return
                        
                        
    return StreetFarm, QuestFarm