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
    _DUNGTARGETMARKED = False
    _DUNGWAITTIMEOUT = 0
    _LAPTIME = 0
    _DUNGCOUNTER = 0
    _CHESTCOUNTER = 0
    _SPELLSKILLCONFIG = [
        ('LAERLIK','OK'),
        ('LAMIGAL','OK'),
        ('LAZELOS','OK'),
        ('SAoLABADIOS','OK'),
        ('SAoLAERLIK','OK'),
        ('maerlik','left2right'),
        ('maferu','left2right'),
        ('mahalito','left2right'),
        ('mazelos','left2right'),
        ('mamigal','left2right'),
        ('PS','left2right'),
        ('HA','left2right'),
        ('BS','left2right')
        ]
    _SYSTEMAUTOCOMBAT = False
    _RANDOMLYOPENCHEST = True
    _FORCESTOPING = None
    _FINISHINGCALLBACK = None
    _COMBATSPD = False
    _RESTINTERVEL = 0
    _SKIPRECOVER = False

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
    client = AdbClient(host="127.0.0.1", port=5037)
    device = client.device("emulator-5554")
    setting = None
    ##################################################################
    def Sleep(t=1):
        time.sleep(t)
    def ScreenShot():
        # print('ScreenShot')
        screenshot = device.screencap()

        screenshot_np = np.frombuffer(screenshot, dtype=np.uint8)
        image = cv2.imdecode(screenshot_np, cv2.IMREAD_COLOR)

        #cv2.imwrite('screen.png', image)

        return image
    def CheckIf(pathOfScreen, shortPathOfTarget):
        print('检查',shortPathOfTarget)
        pathOfTarget = resource_path(fr'resources/images/{shortPathOfTarget}.png')
        template = cv2.imread(pathOfTarget, cv2.IMREAD_COLOR)
        screenshot = pathOfScreen
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)

        threshold = 0.80
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        pos = None
        if max_val >= threshold:
            pos=[max_loc[0] + template.shape[1]//2, max_loc[1] + template.shape[0]//2]

        #print(max_val)
            if max_val<=0.9:
                print(f"警告: {shortPathOfTarget}的匹配程度超过了80%但不足90%, 当前为{max_val*100:.2f}%")
        # cv2.rectangle(screenshot, max_loc, (max_loc[0] + template.shape[1], max_loc[1] + template.shape[0]), (0, 255, 0), 2)
        # cv2.imwrite("Matched Result.png", screenshot)
        return pos
    def CheckIf_MultiRect(pathOfScreen, pathOfTarget):
        print('检查', pathOfTarget)
        pathOfTarget = resource_path(fr'resources/images/{pathOfTarget}.png')
        template = cv2.imread(pathOfTarget, cv2.IMREAD_COLOR)
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
    def Press(pos):
        if pos!=None:
            # print(f'按了{pos[0]} {pos[1]}')
            device.shell(f"input tap {pos[0]} {pos[1]}")
            return True
        return False
    def PressReturn():
        device.shell('input keyevent KEYCODE_BACK')
    ##################################################################
    def getCursorCoordinates(input, template_path, threshold=0.8):
        """在本地图片中查找模板位置"""
        template = cv2.imread(template_path)
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

        print(rect_range)

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
        print(f"周期 p = {estimated_p:.4f}")
        estimated_c = p_opt[1]
        print(f"初始偏移 c = {estimated_c:.4f}")

        return p_opt[0], p_opt[1]
    def ChestOpen():
        ts = []
        xs = []
        t0 = float(device.shell("date +%s.%N").strip())
        while 1:
            while 1:
                Sleep(0.2)
                t = float(device.shell("date +%s.%N").strip())
                s = ScreenShot()
                x = getCursorCoordinates(s,'cursor.png')
                if x != None:
                    ts.append(t-t0)
                    xs.append(x/900)
                    print(t-t0,x)
                else:
                    # cv2.imwrite("Matched Result.png",s)
                    None
                if len(ts)>=20:
                    break
            p, c = calculSpd(ts,xs)
            spd = 2/p*900
            print('速度 spd =',2/p*900)

            t = float(device.shell("date +%s.%N").strip())
            s = ScreenShot()
            x = getCursorCoordinates(s,'cursor.png')
            target = findWidestRectMid(s)
            print('理论点',triangularWave(t-t0,p,c)*900)
            print('起始点', x)
            print('目标点 ',target)

            if x!=None:
                waittime = 0
                t_mod = np.mod(t-c, p)
                if t_mod<p/2:
                    # 正向移动, 向右
                    waittime = ((900-x)+(900-target))/spd
                    print("先向右再向左")
                else:
                    waittime = (x+target)/spd
                    print("先向左再向右")
                print("预计等待", waittime)
                Sleep(waittime-0.270)
                device.shell(f"input tap 430 1000")
                Sleep(3)
            if not CheckIf(ScreenShot(), 'chestOpening'):
                break

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
            print(f'状态机检查中...(第{counter+1}次)')

            if setting._FORCESTOPING.is_set():
                return State.Quit, DungeonState.Quit, screen

            if Press(CheckIf(screen,'retry')):
                    print("网络不太给力啊.")
                    # print("ka le.")
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

            if Press(CheckIf(screen,"returntoTown")) or Press(CheckIf(screen,"openworldmap")):
                PressReturn()
                Sleep(2)
                return IdentifyState()
            
            if Press(CheckIf(screen,"RoyalCityLuknalia")):
                Sleep(2)
                return IdentifyState()
            

            if (CheckIf(screen,'Inn')):
                return State.Inn, None, screen

            if counter>5:
                print("看起来遇到了一些不太寻常的情况...")
                if (CheckIf(screen,'RiseAgain')):
                    print("这就把你拉起来.")
                    # print("REZ.")
                    Press([450,750])
                    Sleep(10)
                    return IdentifyState()
                if Press(CheckIf(screen,'ambush')):
                    print("伏击起手!")
                    # print("Ambush! Always starts with Ambush.")
                    Sleep(2)
                if Press(CheckIf(screen,'blessing')):
                    print("我要选安戈拉的祝福!...好吧随便选一个吧.")
                    # print("Blessing of... of course Angora! Fine, anything.")
                    Sleep(2)
                if Press(CheckIf(screen,'DontBuyIt')):
                    print("等我买? 你白等了, 我不买.")
                    # print("wait for paurch? Wait for someone else.")
                    Sleep(2)
                if Press(CheckIf(screen,'buyNothing')):
                    print("有骨头的话我会买的. 但是现在我没有骨头的识别图片啊.")
                    # print("No Bones No Buy.")
                    Sleep(2)
                if Press(CheckIf(screen,'Nope')):
                    print("但是, 我拒绝.")
                    # print("And what, must we give in return?")
                    Sleep(2)
                if (CheckIf(screen,'multipeopledead')):
                    print("死了好几个, 惨哦")
                    # print("Corpses strew the screen")
                    Press(CheckIf(screen,'skull'))
                    Sleep(2)
                PressReturn()
                PressReturn()
            if counter>= 20:
                print("看起来遇到了一些非同寻常的情况...重启游戏吧")
                package_name = "jp.co.drecom.wizardry.daphne"
                mainAct = device.shell(f"cmd package resolve-activity --brief {package_name}").strip().split('\n')[-1]
                device.shell(f"am force-stop {package_name}")
                Sleep(2)
                print("DvW, 启动!")
                print(device.shell(f"am start -n {mainAct}"))
                Sleep(5)
                setting._DUNGTARGETMARKED = False
                counter = 0

            Press([1,1])
            Press([1,1])
            Press([1,1])
            Sleep(1)
            counter += 1
        return None, None, screen
    def StateInn():
        while not Press(CheckIf(ScreenShot(), 'Inn')):
            Sleep(1)
        while not Press(CheckIf(ScreenShot(), 'Stay')):
            Sleep(2)
        while not Press(CheckIf(ScreenShot(), 'Economy')):
            Sleep(2)
        while not Press(CheckIf(ScreenShot(), 'OK')):
            Sleep(2)
        while not CheckIf(ScreenShot(), 'Stay'):
            Press([183,1467]) # 点击两个按钮中间的地方不会在常规情况下打断正常的跳过逻辑, 反而能在升级的时候正确的关闭页面
            Sleep(1)
        PressReturn()
    def StateEoT():
        match setting._FARMTARGET:
            case "shiphold":
                while not Press(CheckIf(ScreenShot(), 'EdgeOfTown')):
                    Sleep(1)
                while not Press(CheckIf(ScreenShot(), 'TradeWaterway')):
                    Sleep(1)
                while not Press(CheckIf(ScreenShot(), 'shiphold')):
                    Sleep(1)
            case "lounge":
                while not Press(CheckIf(ScreenShot(), 'EdgeOfTown')):
                    Sleep(1)
                while not Press(CheckIf(ScreenShot(), 'TradeWaterway')):
                    Sleep(1)
                while not Press(CheckIf(ScreenShot(), 'lounge')):
                    Sleep(1)
            case "LBC":
                while not Press(CheckIf(screen:=ScreenShot(),'intoWorldMap')):
                    Press(CheckIf(screen,'closePartyInfo'))
                    Sleep(1)
                while not Press(CheckIf(ScreenShot(),'LBC')):
                    Sleep(1)
            case "Dist":
                while not Press(CheckIf(ScreenShot(), 'EdgeOfTown')):
                    Sleep(1)
                while not Press(CheckIf(ScreenShot(), 'TradeWaterway')):
                    Sleep(1)
                while not Press(CheckIf(ScreenShot(), 'Dist')):
                    device.shell(f"input swipe 650 250 650 900")
                    Sleep(1)
            case "DOE":
                while not Press(CheckIf(ScreenShot(), 'EdgeOfTown')):
                    Sleep(1)
                while not Press(CheckIf(ScreenShot(), 'DOE')):
                    Sleep(1)
                while not Press(CheckIf(ScreenShot(), 'DOEB1F')):
                    Sleep(1)
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
            for skillspell, doubleCheck in setting._SPELLSKILLCONFIG:
                if Press(CheckIf(screen, 'spellskill/'+skillspell)):
                    print('使用了技能', skillspell)
                    Sleep(1)
                    Press(CheckIf(ScreenShot(),'OK'))
                    Press([150,750])
                    Press([300,750])
                    Press([450,750])
                    Press([550,750])
                    Press([650,750])
                    Press([750,750])
                    Sleep(3)
                    castSpellSkill = True
                    break
            if not castSpellSkill:
                Press([850,1100])
                Press([850,1100])
                Sleep(3)
    def StateMap_FindSwipeClick(target,operation):
        searchDir = [
            [100,100,700,1500],
            [400,1200,400,100],
            [700,800,100,800],
            [400,100,400,1200],
            [100,800,700,800],
            ]
        targetPos = None
        for i in range(5):
            map = ScreenShot()
            if not CheckIf(map,'mapFlag'):
                return None # 发生了错误
            targetPos = None

            if target == 'marker':
                points = CheckIf_MultiRect(ScreenShot(),target)
                if len(points)>1:
                    targetPos = sorted(points, key=lambda p: p[1], reverse=False)[0]
                    print(f'找到了 {target}! {targetPos}')
                    device.shell(f"input swipe {targetPos[0]} {targetPos[1]} 450 800")
                    Sleep(2)
                    Press([1,230])
                    points = CheckIf_MultiRect(ScreenShot(),target)
                    targetPos = sorted(points, key=lambda p: p[1], reverse=False)[0]
                    Press(targetPos)
                    Sleep(1)
            else:
                if targetPos:=CheckIf(map,target):
                    print(f'找到了 {target}! {targetPos}')
                    device.shell(f"input swipe {targetPos[0]} {targetPos[1]} 450 800")
                    Sleep(2)
                    Press([1,230])
                    targetPos = CheckIf(ScreenShot(),target)
                    Press(targetPos)
            if targetPos:
                if operation == 'MarkSpot':
                    Press(CheckIf(ScreenShot(),'markspot'))
                    return True
                elif operation == 'AutoMove':
                    Press([280,1433])
                    return True

            device.shell(f"input swipe {searchDir[i][0]} {searchDir[i][1]} {searchDir[i][2]} {searchDir[i][3]}")
            Sleep(2)
        return False
    def StateMoving_CheckFrozen(): # return current DungeonState
        lastscreen = None
        dungState = None
        print("进入移动状态. 将不断进行自检.")
        while 1:
            Sleep(3)
            _, dungState,screen = IdentifyState()
            if dungState != DungeonState.Dungeon:
                print(f"退出移动状态. 当前状态: {dungState}.")
                break
            if lastscreen is not None:
                gray1 = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
                gray2 = cv2.cvtColor(lastscreen, cv2.COLOR_BGR2GRAY)
                mean_diff = cv2.absdiff(gray1, gray2).mean()/255
                # print(mean_diff)
                if mean_diff < 0.02:
                    dungState = None
                    print("退出移动状态. 疑似游戏卡死.")
                    break
            lastscreen = screen
        return dungState
    def StateMap(targetComplete,waitTimer):
        normalPlace = ['harken','chest','marker','leaveDung']
        target = setting._DUNGTARGET
        alreadyPressReturnTarget = True # 假设
        # 地图已经打开.
        map = ScreenShot()
        if not CheckIf(map,'mapFlag'):
                return None,targetComplete # 发生了错误
        if not targetComplete:
            if target not in normalPlace:
                if not setting._DUNGTARGETMARKED:
                    StateMap_FindSwipeClick(target, 'MarkSpot')
                    setting._DUNGTARGETMARKED=True
                target = 'marker'
            # 然后所有都是常规target 断开这个if-else可以体现最新的情况.
            if target in normalPlace:
                if StateMap_FindSwipeClick(target, 'AutoMove'):
                    return StateMoving_CheckFrozen(),targetComplete
                else:
                    print("没有找到目标或已经抵达目标地点.")
                    if target!='marker':
                        targetComplete = True
                    else:
                        print('开始等待...等待...')
                        PressReturn()
                        PressReturn()
                        while 1:
                            if setting._DUNGWAITTIMEOUT-time.time()+waitTimer<0:
                                print("等得够久了.")
                                targetComplete = True
                                # alreadyPressReturnTarget = False
                                break
                            print(f'还需要等待{setting._DUNGWAITTIMEOUT-time.time()+waitTimer}秒.')
                            if CheckIf(ScreenShot(),'flee'):
                                return DungeonState.Combat,targetComplete
        if targetComplete:
            print("地下城已经完成, 返回中...")
            # if not alreadyPressReturnTarget:
            targetSpecialQuit = [
                "DOE",
                "LBC",
                ]
            if setting._FARMTARGET in targetSpecialQuit:
                targetQuit = setting._FARMTARGET+"_quit"
            else:
                targetQuit = 'harken'
            if targetQuit:
                if StateMap_FindSwipeClick(targetQuit,'AutoMove'):
                    return StateMoving_CheckFrozen(),targetComplete
            #    alreadyPressReturnTarget = True
            # else:
            #     PressReturn()
            #     Press(CheckIf(ScreenShot(),'resume'))
        return StateMoving_CheckFrozen(),targetComplete
    def StateChest():
        Press(CheckIf(ScreenShot(),'chestFlag'))
        tryOpenCounter = 0
        while 1:
            if CheckIf(ScreenShot(),'whowillopenit'):
                if setting._RANDOMLYPERSONOPENCHEST or tryOpenCounter>10:
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
                        if Press(CheckIf(screen,'Retry')):
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

    def StreetFarm(set):
        nonlocal setting
        setting = set
        state = None
        while 1:
            print("======================")
            Sleep(1)
            if setting._FORCESTOPING.is_set():
                print("即将中断脚本...")
                break
            print('当前状态: ', state)
            match state:
                case None:
                    state,_,_ = IdentifyState()
                    print('下一状态: ', state)
                    if state ==State.Quit:
                        print("即将中断脚本...")
                        break
                case State.Inn:
                    if setting._LAPTIME!= 0:
                        print(f"第{setting._DUNGCOUNTER}次地下城完成. 用时:",time.time()-setting._LAPTIME)
                    setting._LAPTIME = time.time()
                    setting._DUNGCOUNTER+=1
                    if (setting._DUNGCOUNTER-1) % (setting._RESTINTERVEL+1) == 0:
                        StateInn()
                    else:
                        print("还有许多地下城要刷. 现在还不能休息哦.")
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
                        print("----------------------")
                        if setting._FORCESTOPING.is_set():
                            print("即将中断脚本...")
                            dungState = DungeonState.Quit
                        print("当前状态(地下城): ", dungState)

                        match dungState:
                            case None:
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
                                        print("治疗队伍.")
                                        Press([833,843])
                                        Sleep(1)
                                        if CheckIf(ScreenShot(),'recover'):
                                            Press([600,1200])
                                            PressReturn()
                                            Sleep(0.5)
                                            PressReturn()
                                        PressReturn()
                                Press([777,150])
                                Sleep(1)
                                dungState = DungeonState.Map
                            case DungeonState.Map:
                                dungState, targetComplete = StateMap(targetComplete,waitTimer)
                            case DungeonState.Chest:
                                dungState = StateChest()
                            case DungeonState.Combat:
                                StateCombat()
                                dungState = None
                    state = None
        setting._FINISHINGCALLBACK()
    return StreetFarm

# client = AdbClient(host="127.0.0.1", port=5037)
# device = client.device("emulator-5554")
# setting = None
# ##################################################################
# def Sleep(t=1):
#     time.sleep(t)
# def ScreenShot():
#     # print('ScreenShot')
#     screenshot = device.screencap()

#     screenshot_np = np.frombuffer(screenshot, dtype=np.uint8)
#     image = cv2.imdecode(screenshot_np, cv2.IMREAD_COLOR)

#     #cv2.imwrite('screen.png', image)

#     return image
# def CheckIf(pathOfScreen, pathOfTarget):
#     print('检查',pathOfTarget)
#     pathOfTarget = resource_path(fr'resources/images/{pathOfTarget}.png')
#     template = cv2.imread(pathOfTarget, cv2.IMREAD_COLOR)
#     screenshot = pathOfScreen
#     result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)

#     threshold = 0.8
#     _, max_val, _, max_loc = cv2.minMaxLoc(result)
#     pos = None
#     print(max_val)
#     if max_val >= threshold:
#         cv2.rectangle(screenshot, max_loc, (max_loc[0] + template.shape[1], max_loc[1] + template.shape[0]), (0, 255, 0), 2)
#         # cv2.imwrite("Matched Result.png", screenshot)

#         pos=[max_loc[0] + template.shape[1]//2, max_loc[1] + template.shape[0]//2]
#     return pos
# def CheckIf_MultiRect(pathOfScreen, pathOfTarget):
#     print('检查', pathOfTarget)
#     pathOfTarget = resource_path(fr'resources/images/{pathOfTarget}.png')
#     template = cv2.imread(pathOfTarget, cv2.IMREAD_COLOR)
#     screenshot = pathOfScreen
#     result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)

#     threshold = 0.8
#     ys, xs = np.where(result >= threshold)
#     h, w = template.shape[:2]
#     rectangles = list([])

#     for (x, y) in zip(xs, ys):
#         rectangles.append([x, y, w, h])
#         rectangles.append([x, y, w, h]) # 复制两次, 这样groupRectangles可以保留那些单独的矩形.
#     rectangles, _ = cv2.groupRectangles(rectangles, groupThreshold=1, eps=0.5)
#     pos_list = []
#     for rect in rectangles:
#         x, y, rw, rh = rect
#         center_x = x + rw // 2
#         center_y = y + rh // 2
#         pos_list.append([center_x, center_y])
#         # cv2.rectangle(screenshot, (x, y), (x + w, y + h), (0, 255, 0), 2)
#     # cv2.imwrite("Matched_Result.png", screenshot)
#     return pos_list
# def Press(pos):
#     if pos!=None:
#         print(f'按了{pos[0]} {pos[1]}')
#         device.shell(f"input tap {pos[0]} {pos[1]}")
#         return True
#     return False
# def PressReturn():
#     device.shell('input keyevent KEYCODE_BACK')

# Press([1,230])


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