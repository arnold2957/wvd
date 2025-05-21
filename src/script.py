from ppadb.client import Client as AdbClient
import numpy as np
import cv2
import time
from win10toast import ToastNotifier
from scipy.optimize import curve_fit
from scipy.signal import find_peaks
from enum import Enum
import random
import sys
import os

class FarmSetting:
    _FARMTARGET = "shiphold"
    _DUNGTARGET = 'chest' # 'chest or marker'
    _DUNGWAITTIMEOUT = 0
    _LAPTIME = 0
    _DUNGCOUNTER = 0
    _CHESTCOUNTER = 0
    _SPELLSKILLCONFIG = [
        'LAERLIK',
        'LAMIGAL',
        'LAZELOS',
        "LAFOROS",
        "LACONES",
        'SAoLABADIOS',
        'SAoLAERLIK',
        'SAoLAFOROS',
        'maerlik',
        'macones',
        'maferu',
        'mahalito',
        'mazelos',
        'mamigal',
        "maforos",
        'PS',
        'HA',
        'SB',
        ]
    _SYSTEMAUTOCOMBAT = False
    _RANDOMLYOPENCHEST = True
    _FORCESTOPING = None
    _FINISHINGCALLBACK = None
    _COMBATSPD = False
    _RESTINTERVEL = 0
    _SKIPRECOVER = False
    _ADBDEVICE = None
    _LOGGER = None

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

def Factory():
    toaster = ToastNotifier()
    device = None
    logger = None
    setting = None
    ##################################################################
    def Sleep(t=1):
        time.sleep(t)
    def ScreenShot():
        logger.debug('ScreenShot')
        screenshot = device.screencap()

        screenshot_np = np.frombuffer(screenshot, dtype=np.uint8)
        image = cv2.imdecode(screenshot_np, cv2.IMREAD_COLOR)

        #cv2.imwrite('screen.png', image)

        return image
    def _CheckIfLoadImage(shortPathOfTarget):
        logger.debug(f"检查{shortPathOfTarget}")
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
    def CheckIf(pathOfScreen, shortPathOfTarget, outputMatchResult = False):
        nonlocal setting

        template = _CheckIfLoadImage(shortPathOfTarget)
        screenshot = pathOfScreen
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)

        threshold = 0.80
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        pos = None
        logger.debug(f"搜索到疑似{shortPathOfTarget}, 匹配程度:{max_val*100:.2f}%")
        if max_val >= threshold:
            pos=[max_loc[0] + template.shape[1]//2, max_loc[1] + template.shape[0]//2]
            if max_val<=0.9:
                logger.debug(f"警告: {shortPathOfTarget}的匹配程度超过了80%但不足90%")
        
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
            gray1 = cv2.cvtColor(midimg_scn, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(miding_ptn, cv2.COLOR_BGR2GRAY)
            mean_diff = cv2.absdiff(gray1, gray2).mean()/255
            logger.debug(f"中心匹配检查:{mean_diff:.2f}")

            if mean_diff<0.1:
                return True
        return False
    def Press(pos):
        if pos!=None:
            logger.debug(f'按了{pos[0]} {pos[1]}')
            device.shell(f"input tap {pos[0]} {pos[1]}")
            return True
        return False
    def PressReturn():
        device.shell('input keyevent KEYCODE_BACK')
    def FindItOtherwisePressAndWait(targetPattern, pressPos,waitTime):
        # PressPos可以是坐标[x,y]或者字符串. 当为字符串的时候, 视为图片地址.

        for _ in range(25):
            if setting._FORCESTOPING.is_set():
                return None
            scn = ScreenShot()
            pos = CheckIf(scn,targetPattern)
            if pos:
                return pos # findit 
            else: # otherwise
                if Press(CheckIf(scn,'retry')):
                    Sleep(1)
                    continue
                if pressPos: # press
                    if isinstance(pressPos, str):
                        Press(CheckIf(scn, pressPos))
                    elif isinstance(pressPos, (list, tuple)) and len(pressPos) == 2:
                        Press(pressPos)
                    else:
                        logger.debug("错误: 非法的目标.")
                        setting._FORCESTOPING.set()
                        return None
                Sleep(waitTime) # and wait
        
        logger.info("25次截图依旧没有找到目标, 疑似卡死. 重启游戏.")
        restartGame()
        return FindItOtherwisePressAndWait(targetPattern, pressPos,waitTime) #???能这么些吗?
    ##################################################################
    class RestartException(Exception):
        pass
    def restartThisWhenRetartGame(func):
        def wrapper(*args, **kwargs):
            while True:
                try:
                    return func(*args, **kwargs)
                except RestartException:
                    continue
        return wrapper
    def restartGame():
        nonlocal setting
        setting._COMBATSPD = False
        package_name = "jp.co.drecom.wizardry.daphne"
        mainAct = device.shell(f"cmd package resolve-activity --brief {package_name}").strip().split('\n')[-1]
        device.shell(f"am force-stop {package_name}")
        Sleep(2)
        logger.info("巫术, 启动!")
        logger.debug(device.shell(f"am start -n {mainAct}"))
        Sleep(5)
        raise RestartException()
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
                logger.debug(f"预计等待 {waittime}")
                Sleep(waittime-0.270)
                device.shell(f"input tap 430 1000")
                Sleep(3)
            if not CheckIf(ScreenShot(), 'chestOpening'):
                break
    ##################################################################
    class State(Enum):
        Dungeon = 'dungeon'
        Inn = 'inn'
        EoT = 'edge of Town'
        NearTown = 'nearTown'
        Quit = 'quit'
    class DungeonState(Enum):
        Dungeon = 'dungeon'
        Map = 'map'
        Chest = 'chest'
        Combat = 'combat'
        Quit = 'quit'
    ##################################################################
    def IdentifyState():
        counter = 0
        while 1:
            screen = ScreenShot()
            logger.info(f'状态机检查中...(第{counter+1}次)')

            if setting._FORCESTOPING.is_set():
                return State.Quit, DungeonState.Quit, screen

            if Press(CheckIf(screen,'retry')):
                    logger.info("网络不太给力啊.")
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
                return State.NearTown,DungeonState.Quit, screen
            if Press(CheckIf(screen,"openworldmap")):
                PressReturn()
                Sleep(2)
                return IdentifyState()
            
            if Press(CheckIf(screen,"RoyalCityLuknalia")):
                Sleep(2)
                return IdentifyState()
            

            if (CheckIf(screen,'Inn')):
                return State.Inn, None, screen

            if counter>5:
                logger.info("看起来遇到了一些不太寻常的情况...")
                if (CheckIf(screen,'RiseAgain')):
                    logger.info("这就把你拉起来.")
                    # logger.info("REZ.")
                    Press([450,750])
                    Sleep(10)
                    return IdentifyState()
                if Press(CheckIf(screen,'ambush')):
                    logger.info("伏击起手!")
                    # logger.info("Ambush! Always starts with Ambush.")
                    Sleep(2)
                if Press(CheckIf(screen,'blessing')):
                    logger.info("我要选安戈拉的祝福!...好吧随便选一个吧.")
                    # logger.info("Blessing of... of course Angora! Fine, anything.")
                    Sleep(2)
                if Press(CheckIf(screen,'DontBuyIt')):
                    logger.info("等我买? 你白等了, 我不买.")
                    # logger.info("wait for paurch? Wait for someone else.")
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
                    logger.info("死了好几个, 惨哦")
                    # logger.info("Corpses strew the screen")
                    Press(CheckIf(screen,'skull'))
                    Sleep(2)
                PressReturn()
                PressReturn()
            if counter>= 20:
                logger.info("看起来遇到了一些非同寻常的情况...重启游戏吧")
                restartGame()
                counter = 0

            Press([1,1])
            Press([1,1])
            Press([1,1])
            Sleep(1)
            counter += 1
        return None, None, screen
    def StateNone_CheckFrozen(queue, scn):
        if len(queue) > 5:
            queue = []
        queue.append(scn)
        totalDiff = 0
        t = time.time()
        if len(queue)==5:
            for i in range(1,5):
                grayThis = cv2.cvtColor(queue[i], cv2.COLOR_BGR2GRAY)
                grayLast = cv2.cvtColor(queue[i-1], cv2.COLOR_BGR2GRAY)
                mean_diff = cv2.absdiff(grayThis, grayLast).mean()/255
                totalDiff+=mean_diff
            logger.debug(f"卡死检测耗时: {time.time()-t:.5f}秒")
            logger.debug(f"卡死检测结果: {totalDiff:.5f}")
            if totalDiff<=0.08:
                return queue, True
        return queue, False
    @restartThisWhenRetartGame
    def StateInn():
        Press(FindItOtherwisePressAndWait('Inn',[1,1],1))
        Press(FindItOtherwisePressAndWait('Stay',[1,1],2))
        Press(FindItOtherwisePressAndWait('Economy',[1,1],2))
        Press(FindItOtherwisePressAndWait('OK',[1,1],2))
        FindItOtherwisePressAndWait('Stay',[299,1464],2)
        PressReturn()
    @restartThisWhenRetartGame
    def StateEoT():
        match setting._FARMTARGET:
            case "shiphold":
                Press(FindItOtherwisePressAndWait('TradeWaterway','EdgeOfTown',1))
                Press(FindItOtherwisePressAndWait('shiphold',[1,1],1))
            case "lounge":
                Press(FindItOtherwisePressAndWait('TradeWaterway','EdgeOfTown',1))
                Press(FindItOtherwisePressAndWait('lounge',[1,1],1))
            case "LBC":
                Press(FindItOtherwisePressAndWait('intoWorldMap','closePartyInfo',1))
                
                while not Press(CheckIf(ScreenShot(),'LBC')):
                    device.shell(f"input swipe 100 100 700 1500")
                    Sleep(1)
            case "fordraig-B3F":
                Press(FindItOtherwisePressAndWait('intoWorldMap',[40, 1184],2))

                while not Press(CheckIf(ScreenShot(),'labyrinthOfFordraig')):
                    device.shell(f"input swipe 450 150 500 150")
                
                Press(FindItOtherwisePressAndWait('fordraig/B3F','labyrinthOfFordraig',1))
            case "Dist":
                Press(FindItOtherwisePressAndWait('TradeWaterway','EdgeOfTown',1))

                while not Press(CheckIf(ScreenShot(), 'Dist')):
                    device.shell(f"input swipe 650 250 650 900")
                    Sleep(1)
            case "DOE":
                Press(FindItOtherwisePressAndWait('DOE','EdgeOfTown',1))
                Press(FindItOtherwisePressAndWait('DOEB1F',[1,1],1))
            case "DOL":
                Press(FindItOtherwisePressAndWait('DOL','EdgeOfTown',1))
                Press(FindItOtherwisePressAndWait('DOLB1F',[1,1],1))
            case "DOF":
                Press(FindItOtherwisePressAndWait('DOF','EdgeOfTown',1))
                Press(FindItOtherwisePressAndWait('DOFB1F',[1,1],1))
        Sleep(1)
        Press(CheckIf(ScreenShot(), 'GotoDung'))
    def StateCombat():
        nonlocal setting
        screen = ScreenShot()
        if not setting._COMBATSPD:
            if Press(CheckIf(screen,'combatSpd')):
                setting._COMBATSPD = True

        if setting._SYSTEMAUTOCOMBAT:
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
    def StateMap_FindSwipeClick(target,searchDir = None):
        if searchDir == None:
            searchDir = [None,
                        [100,100,700,1500],
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
            if target == 'marker':
                points = CheckIf_MultiRect(ScreenShot(),target)
                if len(points)>1:
                    targetPos = sorted(points, key=lambda p: p[1], reverse=False)[0]
                    logger.info(f'找到了 {target}! {targetPos}')
                    device.shell(f"input swipe {targetPos[0]} {targetPos[1]} 450 800")
                    Sleep(2)
                    Press([1,230])
                    points = CheckIf_MultiRect(ScreenShot(),target)
                    targetPos = sorted(points, key=lambda p: p[1], reverse=False)[0]
                    Sleep(1)
                    return targetPos
            else:
                if targetPos:=CheckIf(map,target):
                    logger.info(f'找到了 {target}! {targetPos}')
                    device.shell(f"input swipe {targetPos[0]} {targetPos[1]} 450 800")
                    Sleep(2)
                    Press([1,230])
                    targetPos = CheckIf(ScreenShot(),target)
                    return targetPos
        return targetPos
    def StateMoving_CheckFrozen(): # return current DungeonState
        lastscreen = None
        dungState = None
        logger.info("面具男, 移动.")
        while 1:
            Sleep(3)
            _, dungState,screen = IdentifyState()
            if dungState == DungeonState.Map:
                logger.info(f"疑似移动失败.")
                FindItOtherwisePressAndWait("dungFlag",[280,1433],1)
                dungState = dungState.Dungeon
                break
            if dungState != DungeonState.Dungeon:
                logger.info(f"退出移动状态. 当前状态: {dungState}.")
                break
            if lastscreen is not None:
                gray1 = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
                gray2 = cv2.cvtColor(lastscreen, cv2.COLOR_BGR2GRAY)
                mean_diff = cv2.absdiff(gray1, gray2).mean()/255
                logger.debug(f"移动冻结检查:{mean_diff:.2f}")
                if mean_diff < 0.02:
                    dungState = None
                    logger.info("退出移动状态. 疑似游戏卡死.")
                    break
            lastscreen = screen
        return dungState
    def StateSearch(targetComplete,waitTimer, targetList = None):
        normalPlace = ['harken','chest','leaveDung']
        target = setting._DUNGTARGET
        # 地图已经打开.
        map = ScreenShot()
        if not CheckIf(map,'mapFlag'):
                return None,targetComplete # 发生了错误
        if target in normalPlace:
            if pos:=StateMap_FindSwipeClick(target):
                Press(pos)
                Press([280,1433]) # automove
                return StateMoving_CheckFrozen(),targetComplete
            else:
                logger.info("没有找到目标, 地下城完成, 准备离开.")
                targetComplete = True
        else:
            if (pos:=StateMap_FindSwipeClick(target)):
                if (CheckIf_FocusCursor(ScreenShot(),target)): #注意 这里通过二次确认 我们可以看到目标地点 而且是未选中的状态
                    logger.info("经过对比中心区域, 确认没有抵达.")
                    Press(pos)
                    Press([280,1433]) # automove
                    return StateMoving_CheckFrozen(),targetComplete
                else:
                    logger.info("经过对比中心区域, 判断为抵达目标地点.")
                    logger.info('开始等待...等待...')
                    PressReturn()
                    PressReturn()
                    while 1:
                        if setting._DUNGWAITTIMEOUT-time.time()+waitTimer<0:
                            logger.info("等得够久了.")
                            targetComplete = True
                            Sleep(1)
                            Press([777,150])
                            return None,  targetComplete
                        logger.info(f'还需要等待{setting._DUNGWAITTIMEOUT-time.time()+waitTimer}秒.')
                        if CheckIf(ScreenShot(),'flee'):
                            return DungeonState.Combat,targetComplete
            else:
                logger.info("错误: 地图中未找到目标地点.")
                return DungeonState.Map,  targetComplete
        return DungeonState.Map,  targetComplete
    def StateQuit():
        logger.info("地下城已经完成, 返回中...")
        # if not alreadyPressReturnTarget:
        targetSpecialQuit = [
            "DOE",
            "DOF",
            "DOL",
            "LBC",
            ]
        targetQuit = None
        if setting._FARMTARGET in targetSpecialQuit:
            targetQuit = setting._FARMTARGET+"_quit"
        else:
            targetQuit = 'harken'
        if targetQuit:
            if pos:=StateMap_FindSwipeClick(targetQuit):
                Press(pos)
                Press([280,1433])
                return StateMoving_CheckFrozen()
        return StateMoving_CheckFrozen()
    def StateChest():
        FindItOtherwisePressAndWait('whowillopenit', 'chestFlag',1)
        tryOpenCounter = 0
        MAXtryOpen = 5
        while 1:
            if CheckIf(ScreenShot(),'whowillopenit'):
                if setting._RANDOMLYPERSONOPENCHEST or tryOpenCounter>=MAXtryOpen:
                    Press([200+(setting._CHESTCOUNTER%3)*200, 1200+((setting._CHESTCOUNTER)//3)%2*150])
                else:
                    Press([200,1200])
                setting._CHESTCOUNTER += 1
                Sleep(1)
            Press([1,1])
            if CheckIf(ScreenShot(),'chestOpening'):
                Sleep(1)
                if setting._RANDOMLYOPENCHEST:
                    while 1:
                        screen = ScreenShot()
                        if Press(CheckIf(screen,'retry')):
                            Sleep(1)
                            screen = ScreenShot()
                        if CheckIf(screen, 'chestOpening'):
                            Press([430,1000])
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
            if CheckIf(ScreenShot(),'retry'):
                return None
            ## todo: 换个简易版本的identify
            tryOpenCounter += 1
            logger.info(f"似乎选择人物失败了,当前尝试次数:{tryOpenCounter}. 尝试{MAXtryOpen}次后若失败则会变为随机开箱.")

    def StreetFarm(set):
        nonlocal setting
        nonlocal device
        nonlocal logger
        setting = set
        device = setting._ADBDEVICE
        logger = setting._LOGGER
        screenFrozen = []
        
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
                    state,_,_ = IdentifyState()
                    logger.info(f"下一状态: {state}")
                    if state ==State.Quit:
                        logger.info("即将中断脚本...")
                        break
                case State.NearTown:
                    if setting._LAPTIME!= 0:
                        logger.info(f"第{setting._DUNGCOUNTER}次地下城完成. 用时:{time.time()-setting._LAPTIME}")
                    setting._LAPTIME = time.time()
                    setting._DUNGCOUNTER+=1
                    if (setting._DUNGCOUNTER-1) % (setting._RESTINTERVEL+1) == 0:
                        PressReturn()
                        state = State.Inn
                    else:
                        logger.info("还有许多地下城要刷. 现在还不能休息...稍微休息一下好了.")
                        Press([1,1])
                        FindItOtherwisePressAndWait('gradeup',[450,1300],2)
                        Press(FindItOtherwisePressAndWait('recover',[833,750],1))
                        PressReturn()
                        Sleep(0.5)
                        PressReturn()
                        PressReturn()
                        #Press([600,1200])
                        state = State.EoT
                case State.Inn:
                    StateInn()
                    state = State.EoT
                case State.EoT:
                    StateEoT()
                    state = State.Dungeon
                case State.Dungeon:
                    dungState = None
                    inDung = True
                    targetComplete = False
                    waitTimer = time.time()
                    while inDung:
                        logger.info("----------------------")
                        if setting._FORCESTOPING.is_set():
                            logger.info("即将中断脚本...")
                            dungState = DungeonState.Quit
                        logger.info(f"当前状态(地下城): {dungState}")

                        match dungState:
                            case None:
                                screenFrozen, result = StateNone_CheckFrozen(screenFrozen,ScreenShot())
                                if result:
                                    restartGame()
                                s, dungState,_ = IdentifyState()
                                if (s == State.Inn)or(s == DungeonState.Quit):
                                    inDung = False
                            case DungeonState.Quit:
                                inDung = False
                            case DungeonState.Dungeon:
                                Press([1,1]) # interrupt auto moving
                                if not setting._SKIPRECOVER:
                                    Press([1,1])
                                    Press([450,1300])
                                    Sleep(1)
                                    if CheckIf(ScreenShot(), 'trait'):
                                        logger.info("治疗队伍.")
                                        Press([833,843])
                                        Sleep(1)
                                        if CheckIf(ScreenShot(),'recover'):
                                            Press([600,1200])
                                            PressReturn()
                                            Sleep(0.5)
                                            PressReturn()
                                        PressReturn()
                                Sleep(1)
                                Press([777,150])
                                Sleep(1)
                                dungState = DungeonState.Map
                            case DungeonState.Map:
                                if not targetComplete:
                                    dungState, targetComplete = StateSearch(targetComplete,waitTimer)
                                else:
                                    dungState = StateQuit()
                            case DungeonState.Chest:
                                dungState = StateChest()
                            case DungeonState.Combat:
                                StateCombat()
                                dungState = None
                    state = None
        setting._FINISHINGCALLBACK()
    def QuestFarm(set):
        nonlocal setting
        nonlocal device
        nonlocal logger
        setting = set
        device = setting._ADBDEVICE
        logger = setting._LOGGER
        match setting._FARMTARGET:
            case '7000G':                    
                stepNo = 1 #IdentifyStep(stepNo)
                while 1:
                    setting._DUNGCOUNTER += 1
                    starttime = time.time()
                    match stepNo:
                        case 1:
                            @restartThisWhenRetartGame
                            def step_1():
                                logger.info("第一步: 开始诅咒之旅...")
                                Press(FindItOtherwisePressAndWait('cursedWheel','ruins',1))
                                Press(FindItOtherwisePressAndWait('impregnableFortress','cursedWheelTapRight',1))

                                if not Press(CheckIf(ScreenShot(),'FortressArrival')):
                                    device.shell(f"input swipe 450 1200 450 200")
                                    while not Press(CheckIf(ScreenShot(),'FortressArrival')):
                                        device.shell(f"input swipe 50 1200 50 1300")
                                
                                while pos:= CheckIf(ScreenShot(), 'leap'):
                                    Press(pos)
                                    Sleep(2)
                                    Press(CheckIf(ScreenShot(),'FortressArrival'))
                            step_1()
                            stepNo = 2
                        case 2:
                            logger.info("第二步: 从要塞返回主城...")
                            leapSuccess = False
                            Sleep(10)
                            while 1:
                                Sleep(15)
                                for i in range(50):
                                    if (CheckIf(ScreenShot(),'leaveDung')):
                                        logger.info("跳跃成功!")
                                        leapSuccess = True
                                        break
                                    else:
                                        Press([1,1])
                                if not leapSuccess:
                                    restartGame()
                                    logger.info("跳跃失败, 重启游戏")
                                else:
                                    break
                            Press(FindItOtherwisePressAndWait('return','leaveDung',2))
                            Press(FindItOtherwisePressAndWait('returntotown',[1,1],2))
                            FindItOtherwisePressAndWait('Inn',[1,1],2)
                            stepNo = 3
                        case 3:
                            logger.info("第三步: 前往王城...")
                            Press(FindItOtherwisePressAndWait('intoWorldMap',[40, 1184],2))

                            while not Press(CheckIf(ScreenShot(),'RoyalCityLuknalia')):
                                device.shell(f"input swipe 450 150 500 150")
                            stepNo = 4
                        case 4:
                            logger.info("第四步: 给我!(伸手)")
                            Press(FindItOtherwisePressAndWait('guild',[1,1],1))
                            Press(FindItOtherwisePressAndWait('7000G/illgonow',[1,1],1))
                            Sleep(15)
                            Press(FindItOtherwisePressAndWait('7000G/olddist',[1,1],2))
                            Sleep(4)
                            Press([1,1])
                            Press([1,1])
                            Sleep(8)
                            Press(FindItOtherwisePressAndWait('7000G/royalcapital',[1,1],2))
                            FindItOtherwisePressAndWait('intoWorldMap',[1,1],2)
                            FindItOtherwisePressAndWait('fastforward',[450,1111],0)
                            while not CheckIf(scn:=ScreenShot(),'intoWorldMap'):
                                Press(CheckIf(scn,'7000G/why'))
                                Press([1,1])
                                Sleep(2)
                            FindItOtherwisePressAndWait('fastforward',[200,1180],0)
                            while not CheckIf(scn:=ScreenShot(),'intoWorldMap'):
                                Press(CheckIf(scn,'7000G/why'))
                                Press([1,1])
                                Sleep(2)
                            FindItOtherwisePressAndWait('fastforward',[680,1200],0)
                            while not Press(CheckIf(scn:=ScreenShot(),'7000G/leavethechild')):
                                Press(CheckIf(scn,'7000G/why'))
                                Press([1,1])
                                Sleep(1)
                            Press(FindItOtherwisePressAndWait('7000G/icantagreewithU',[1,1],1))
                            Press(FindItOtherwisePressAndWait('7000G/olddist',[1,1],1))
                            Press(FindItOtherwisePressAndWait('7000G/illgo',[1,1],1))
                            Press(FindItOtherwisePressAndWait('7000G/noeasytask',[1,1],1))
                            FindItOtherwisePressAndWait('ruins',[1,1],1)
                            costtime = time.time()-starttime
                            logger.info(f"第{setting._DUNGCOUNTER}次\"7000G\"完成. 该次花费时间{costtime:.2f}, 每秒收益:{7000/costtime:.2f}Gps.")
                            if not setting._FORCESTOPING.is_set():
                                stepNo = 1
                            else:
                                break
            case 'fordraig':
                stepNo = 3
                while 1:
                    setting._DUNGCOUNTER += 1
                    logger.info(setting._DUNGCOUNTER)
                    starttime = time.time()
                    match stepNo:
                        case 1:
                            @restartThisWhenRetartGame
                            def step_1():
                                logger.info('第一步: 诅咒之旅...')
                                Press(FindItOtherwisePressAndWait('cursedWheel','ruins',1))
                                Press(FindItOtherwisePressAndWait('Fordraig/Leap','specialRequest',1))
                                Press(FindItOtherwisePressAndWait('OK','leap',1))
                                Sleep(15)
                            step_1()
                            stepNo = 2
                        case 2:
                            logger.info('第二步: 领取任务.')
                            FindItOtherwisePressAndWait('Inn',[1,1],1)
                            StateInn()
                            Press(FindItOtherwisePressAndWait('guildRequest','guild',1))
                            Press(FindItOtherwisePressAndWait('guildFeatured','guildRequest',1))
                            Sleep(1)
                            device.shell(f"input swipe 450 1000 450 200")
                            while 1:
                                pos = CheckIf(ScreenShot(),'fordraig/RequestAccept')
                                if not pos:
                                    device.shell(f"input swipe 50 1200 50 1300")
                                else:
                                    Press([pos[0]+350,pos[1]+180])
                                    break
                            FindItOtherwisePressAndWait('guildRequest',[1,1],1)
                            PressReturn()
                            stepNo = 3
                        case 3:
                            logger.info('第三步: 进入地下城.')
                            Press(FindItOtherwisePressAndWait('intoWorldMap',[40, 1184],2))

                            while not Press(CheckIf(ScreenShot(),'labyrinthOfFordraig')):
                                device.shell(f"input swipe 450 150 500 150")
                            
                            Press(FindItOtherwisePressAndWait('fordraig/Entrance','labyrinthOfFordraig',1))
                            stepNo = 4
                        case 4:
                            
                            break
                            

        setting._FINISHINGCALLBACK()
        return
                        
                        
    return StreetFarm, QuestFarm



# Press(CheckIf(ScreenShot(),'ruins'))
# Press(CheckIf(ScreenShot(),'cursedWheel'))
# Press(CheckIf(ScreenShot(),'specialRequest'))
# Press(CheckIf(ScreenShot(),'FordraigLeap'))
# Press(CheckIf(ScreenShot(),'leap'))
# Press(CheckIf(ScreenShot(),'OK'))
# Sleep(15)
# KeepPress([1,1]) until Inn
# StateInn()
# Press(CheckIf(ScreenShot(),'guild'))
# Press(CheckIf(ScreenShot(),'guildRequest'))
# Press(CheckIf(ScreenShot(),'guildFeatured'))
# pos=CheckIf(ScreenShot(),'fordraigRequestAccept')
# Press([pos[0]+350,pos[1]+180])
# KeepPress([1,1]) until guildRequest
# PressReturn()
# Press(CheckIf(ScreenShot(),'closePartyInfo'))
# Press(CheckIf(ScreenShot(),'intoWorldMap'))
# Press(CheckIf(ScreenShot(),'labyrinthOfFordraig'))
# Press(CheckIf(ScreenShot(),'fordraigEntrance'))
# pos = CheckIf(ScreenShot(),'fordraigFirstTrap')
# Press([pos[0], pos[1]+90])
# device.shell(f"input swipe 100 250 800 250")
# Sleep(1)
# Press([450,900])
# Press(CheckIf(ScreenShot(),'fordraigTryPushingIt'))
# Sleep(2)
# downstair
# Press(CheckIf(ScreenShot(),'fordraigAskDagger'))
# Sleep(2)
# Press(CheckIf(ScreenShot(),'fordraigSecondTrap'))
# device.shell(f"input swipe 100 250 800 250")
# Sleep(1)
# Press([450,900])
# Press(CheckIf(ScreenShot(),'fordraigTryPushingIt'))
# device.shell(f"input swipe 30 1234 800 250")
# Sleep(2)
# Press([30,1234])
# Press(CheckIf(ScreenShot(),'downstair2'))
# Press(CheckIf(ScreenShot(),'fordraigFirstBoss'))
# input()
# Press(CheckIf(ScreenShot(),'harken'))
# Press(CheckIf(ScreenShot(),'fordraigReachHarken'))
# Press([450,1100])
# Press([450,1200]) # 找一个固定位置? 这是return
# if CheckIf('fordraigEntrance') then Return
# Press(CheckIf(ScreenShot(),'RoyalCityLuknalia'))
# StateInn()
# Press(CheckIf(ScreenShot(),'closePartyInfo'))
# Press(CheckIf(ScreenShot(),'intoWorldMap'))
# Press(CheckIf(ScreenShot(),'labyrinthOfFordraig')) # 这3步相同
# Press(CheckIf(ScreenShot(),'fordraigB3F'))
# device.shell(f"input swipe 30 1234 800 250")
# Sleep(2) # 这2步相同
# Press([100,1000])
# Press(CheckIf(ScreenShot(),'fordraigInsertTheDagger'))
# Press(Resume)
# Press(CheckIf(ScreenShot(),'fordraigSecondBoss'))
# 'chest'
#  keep 'quit' until return
# if CheckIf('fordraigEntrance') then Return
# Press(CheckIf(ScreenShot(),'RoyalCityLuknalia'))
# 不交任务了直接结束吧