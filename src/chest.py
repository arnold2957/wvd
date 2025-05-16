from ppadb.client import Client as AdbClient
import numpy as np
import cv2
import time
from win10toast import ToastNotifier
import numpy as np
from scipy.optimize import curve_fit
from scipy.signal import find_peaks

toaster = ToastNotifier()

client = AdbClient(host="127.0.0.1", port=5037)
device = client.device("emulator-5554")
def Sleep(t=1):
    time.sleep(t)
def ScreenShot():
    print('ScreenShot')
    screenshot = device.screencap()

    screenshot_np = np.frombuffer(screenshot, dtype=np.uint8)
    image = cv2.imdecode(screenshot_np, cv2.IMREAD_COLOR)

    #cv2.imwrite('screen.png', image)

    return image

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

    cv2.imwrite("Matched Result.png",cropped)

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

def triangular_wave(t, p, c):
    t_mod = np.mod(t-c, p)
    return np.where(t_mod < p/2, (2/p)*t_mod, 2 - (2/p)*t_mod)

def CalculSpd(t,x):
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
        triangular_wave,
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
def CheckIf(pathOfScreen, pathOfTarget):
    print('check',pathOfTarget)
    pathOfTarget = f'.\\{pathOfTarget}.png'
    template = cv2.imread(pathOfTarget, cv2.IMREAD_COLOR)
    screenshot = pathOfScreen
    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)

    threshold = 0.8
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    pos = None
    if max_val >= threshold:
        cv2.rectangle(screenshot, max_loc, (max_loc[0] + template.shape[1], max_loc[1] + template.shape[0]), (0, 255, 0), 2)
        cv2.imwrite("Matched Result.png", screenshot)

        pos=[max_loc[0] + template.shape[1]//2, max_loc[1] + template.shape[0]//2]
    return pos

def chestOpen():
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
                cv2.imwrite("Matched Result.png",s)
            if len(ts)>=20:
                break
        p, c = CalculSpd(ts,xs)
        spd = 2/p*900
        print('速度 spd =',2/p*900)

        t = float(device.shell("date +%s.%N").strip())
        s = ScreenShot()
        x = getCursorCoordinates(s,'cursor.png')
        target = findWidestRectMid(s)
        print('理论点',triangular_wave(t-t0,p,c)*900)
        print('起始点', x)
        print('目标点 ',target)

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
        # s = ScreenShot()
        # cv2.imwrite("press!!!.png",s)
        device.shell(f"input tap 430 1000")
        Sleep(2)
        if not CheckIf(ScreenShot(), 'chestCancel'):
            break



chestOpen()


    





