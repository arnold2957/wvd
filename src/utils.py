import tkinter as tk
from tkinter import ttk, scrolledtext
import json
import os
import copy
import sys
import cv2
import time
import numpy as np
import glob
import gettext
from loguru import logger
from datetime import datetime

# 基础模块包括:
# LOGGER. 将输入写入到logger.txt文件中.
# CONFIG. 保存和写入设置.
# CHANGES LOG. 弹窗展示更新文档.
# TOOLTIP. 鼠标悬停时的提示.

############################################
LOGS_FOLDER_NAME = "logs"
os.makedirs(LOGS_FOLDER_NAME, exist_ok=True)

# 移除 loguru 默认 handler，配置自定义 sinks
logger.remove()

# 文件日志：自动轮转（每天），保留 3 天，多进程安全（enqueue=True）
logger.add(
    os.path.join(LOGS_FOLDER_NAME, "log_{time:YYMMDD-HHMMSS}.txt"),
    rotation="1 day",
    retention="3 days",
    enqueue=True,
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} - {level} - [{module}:{function}:{line}] - {message}",
    encoding="utf-8",
)

# 控制台输出（INFO 级别），可通过函数动态添加/移除
_console_handler_id = None

def RegisterConsoleHandler():
    """添加控制台日志输出（避免重复添加）"""
    global _console_handler_id
    if _console_handler_id is not None:
        return
    _console_handler_id = logger.add(
        sys.stdout,
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} - {level} - {message}",
        enqueue=True,
    )

def RemoveConsoleHandler():
    """移除控制台日志输出"""
    global _console_handler_id
    if _console_handler_id is not None:
        logger.remove(_console_handler_id)
        _console_handler_id = None

# 重定向标准输出/错误到 loguru
class LoggerStream:
    """自定义流，将输出重定向到 loguru"""
    def __init__(self, level):
        self.level = level
        self.buffer = ''

    def write(self, message):
        self.buffer += message
        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            if line:
                logger.log(self.level, line)

    def flush(self):
        if self.buffer:
            logger.log(self.level, self.buffer)
            self.buffer = ''

# 默认将 stdout/stderr 重定向到 loguru（可根据需要调用）
sys.stdout = LoggerStream("DEBUG")
sys.stderr = LoggerStream("ERROR")

# GUI 文本框输出 sink（用于 Tkinter 界面）
class ScrolledTextHandler:
    """将日志输出到 Tkinter ScrolledText 组件"""
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.text_widget.config(state=tk.DISABLED)

    def write(self, message):
        # loguru 传入的 message 是已格式化的字符串（可能含换行）
        try:
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.insert(tk.END, message)
            self.text_widget.see(tk.END)
            self.text_widget.config(state=tk.DISABLED)
        except Exception:
            pass  # 忽略 GUI 销毁等异常

# 为 GUI 添加日志 sink 的辅助函数
_gui_handler_id = None
def AddGuiLogHandler(text_widget, level="INFO", filter_func=None):
    """添加 GUI 日志输出，返回 handler id"""
    global _gui_handler_id
    if _gui_handler_id is not None:
        RemoveGuiLogHandler()
    sink = ScrolledTextHandler(text_widget)
    _gui_handler_id = logger.add(
        sink.write,
        level=level,
        format="{time:HH:mm:ss} - {level} - {message}",
        filter=filter_func,
        enqueue=True,  # 确保线程安全
    )
    return _gui_handler_id

def RemoveGuiLogHandler():
    """移除 GUI 日志输出"""
    global _gui_handler_id
    if _gui_handler_id is not None:
        logger.remove(_gui_handler_id)
        _gui_handler_id = None

# 自定义过滤器示例：只显示 summary 为 True 的记录
def summary_filter(record):
    return record["extra"].get("summary", False)

############################################
def ResourcePath(relative_path):
    """ 获取资源的绝对路径，适用于开发环境和 PyInstaller 打包环境 """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_path, relative_path)

def LoadJson(path):
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                return loaded_config
        else:
            return {}   
    except json.JSONDecodeError:
        logger.error(f"错误: 无法解析 {path}。将使用默认配置。")
        return {}
    except Exception as e:
        logger.error(f"错误: 加载配置时发生错误: {e}。将使用默认配置。")
        return {}

def LoadImage(path):
    try:
        img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"[OpenCV 错误] 图片加载失败，路径可能不存在或图片损坏: {path}")
    except Exception as e:
        logger.error(f"加载图片失败: {str(e)}")
        return None
    return img

def SaveImage(scn, name=None):
    if not name:
        name = datetime.now().strftime('%H%M%S.%f')[:-3]
    if not name.endswith(".png"):
        name = f"{name}.png"
    file_path = os.path.join(LOGS_FOLDER_NAME, name)
    logger.info(f"截图已保存在{file_path}中.")
    cv2.imwrite(file_path, scn)

def CleanupOldImages(days=3):
    """删除 logs 文件夹中超过指定天数的截图（.png）"""
    import time
    import glob

    now = time.time()
    cutoff = now - days * 86400  # 3 天前的秒数

    pattern = os.path.join(LOGS_FOLDER_NAME, "*.png")
    for filepath in glob.glob(pattern):
        try:
            mtime = os.path.getmtime(filepath)
            if mtime < cutoff:
                os.remove(filepath)
                logger.debug(f"已删除过期截图: {filepath}")
        except Exception as e:
            logger.error(f"删除过期截图失败 {filepath}: {e}")

CleanupOldImages()
############################################
CONFIG_FILE = 'config.json'
def SaveConfigToFile(config_data):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        logger.info(_("配置已保存。"))
        return True
    except Exception as e:
        logger.error(f"保存配置时发生错误: {e}")
        return False

def LoadRawConfigFromFile(config_file_path = CONFIG_FILE):
    if config_file_path == None:
        config_file_path = CONFIG_FILE
    return LoadJson((config_file_path))

def SetOneVarInGeneralConfig(var, value):
    data = LoadRawConfigFromFile()
    data['GENERAL'][var] = value
    SaveConfigToFile(data)

def GetOneVarInGeneralConfig(var, default_value):
    data = LoadRawConfigFromFile()
    if 'GENERAL' in data:
        if var in data['GENERAL']:
            return data['GENERAL'][var]
    return default_value

############################################
localedir = ResourcePath("locale")
LANGUAGE = GetOneVarInGeneralConfig('LANGUAGE', "zh_CN")
trans = gettext.translation('messages', localedir, languages=[LANGUAGE], fallback=True)
trans.install()
_ = trans.gettext

###########################################
CHANGES_LOG = "CHANGES_LOG.md"
def ShowChangesLogWindow():
    log_window = tk.Toplevel()
    log_window.title(_("更新日志"))
    log_window.geometry("700x500")

    log_window.lift()
    log_window.attributes('-topmost', True)
    log_window.after(100, lambda: log_window.attributes('-topmost', False))
    
    text_area = scrolledtext.ScrolledText(
        log_window, 
        wrap=tk.WORD,
        font=("Segoe UI", 10),
        padx=10,
        pady=10
    )
    text_area.pack(fill=tk.BOTH, expand=True)
    text_area.configure(state='disabled')
    
    try:
        with open(CHANGES_LOG, "r", encoding="utf-8") as file:
            markdown_content = file.read()
        text_area.configure(state='normal')
        text_area.delete(1.0, tk.END)
        text_area.insert(tk.INSERT, markdown_content)
        text_area.configure(state='disabled')
    except FileNotFoundError:
        text_area.configure(state='normal')
        text_area.insert(tk.INSERT, f"错误：未找到{CHANGES_LOG}文件")
        text_area.configure(state='disabled')
    except Exception as e:
        text_area.configure(state='normal')
        text_area.insert(tk.INSERT, f"读取文件时出错: {str(e)}")
        text_area.configure(state='disabled')

###########################################
QUEST_FILE_BASE = 'resources/quest/quest.json'
QUEST_FILE_MOD = 'mod/quest.json'
def _build_quest_data():
    try:
        base_data = LoadJson(ResourcePath(QUEST_FILE_BASE))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"无法读取通用任务列表: {e}")
        raise

    merged = copy.deepcopy(base_data)

    if os.path.exists(QUEST_FILE_MOD):
        try:
            mod_data = LoadJson(QUEST_FILE_MOD)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"无法读取自定义任务列表: {e}, 跳过合并.")
            mod_data = {}

        for mod_key, mod_info in mod_data.items():
            if "_TYPE" not in mod_info or mod_info["_TYPE"] not in ("dungeon", "quest"):
                logger.error(f"自定义任务 '{mod_key}' 具有不合法的_TYPE值, 跳过.")
                continue

            has_local_name = "questName" in mod_info
            has_en_name = "questName_en_US" in mod_info
            if not has_local_name and not has_en_name:
                logger.error(f"自定义任务 '{mod_key}' 缺少任务名或者英文任务名, 跳过.")
                continue

            if has_local_name and not has_en_name:
                mod_info["questName_en_US"] = mod_info["questName"]
            elif has_en_name and not has_local_name:
                mod_info["questName"] = mod_info["questName_en_US"]

            mod_info["questCategory"] = "自定义"
            mod_info["questCategory_en_US"] = "Custom Requests"

            final_key = mod_key
            while final_key in merged:
                final_key += "_mod"
                mod_info["questName"] += "_自定义"
                mod_info["questName_en_US"] += "_mod"
            merged[final_key] = mod_info
            if final_key != mod_key:
                logger.info(f"自定义任务的内部代号 '{mod_key}' 和现有任务冲突, 修改为 '{final_key}'.")

    return merged

QUEST_DATA = _build_quest_data()

QUEST_CATEGORY_ORDER = {
    "最新任务": 0,
    "WHATS NEW": 0,
    "主线前三章" : 3,
    "Chapter 1,2 and 3":3,
    "主线第四章": 4,
    "Chapter 4": 4,
    "任务洞窟": 10,
    "Request Caves": 10,
    "矿石" : 20,
    "Ore": 20,
    "月常": 30,
    "Monthly Requests": 30,
    "FFXI联动": 11,
    "FFXI Cave": 11,
    "其他": 999,
    "Other": 999
    }

def BuildQuestReflection():
    try:
        data = QUEST_DATA
        quest_reflect_map = {}
        seen_names = set()
        
        for quest_code, quest_info in data.items():
            quest_name = quest_info.get(f"questName_{LANGUAGE}", quest_info["questName"])
            if quest_name in seen_names:
                raise ValueError(f"Duplicate questName found: '{quest_name}'")
            seen_names.add(quest_name)
            category = quest_info.get(f"questCategory_{LANGUAGE}", quest_info["questCategory"])
            quest_reflect_map.setdefault(category, {})[quest_name] = quest_code

        sorted_categories = sorted(
            quest_reflect_map.keys(),
            key=lambda c: (QUEST_CATEGORY_ORDER.get(c, float('inf')), c)
        )
        quest_reflect_map = {cat: quest_reflect_map[cat] for cat in sorted_categories}
        
        return quest_reflect_map
    except KeyError as e:
        raise KeyError(f"不存在'questName'属性: {e}.")
    except json.JSONDecodeError as e:
        logger.info(f"Error at line {e.lineno}, column {e.colno}: {e.msg}")
        logger.info(f"Problematic text: {e.doc[e.pos-30:e.pos+30]}")
        exit()
    except FileNotFoundError as e:
        raise FileNotFoundError(f"{e}")

###########################################
IMAGE_FOLDER = fr'resources/images/'
def LoadTemplateImage(shortPathOfTarget):
    logger.debug(f"加载图片: {shortPathOfTarget}")
    image_filename = f"{shortPathOfTarget}.png"

    resource_path = ResourcePath(os.path.join(IMAGE_FOLDER, image_filename))
    try:
        return LoadImage(resource_path)
    except (FileNotFoundError, OSError, Exception) as e:
        logger.debug(f"资源路径未找到 {image_filename}: {e}，尝试 mod 目录")

    mod_path = os.path.join('mod', image_filename)
    if os.path.isfile(mod_path):
        return LoadImage(mod_path)

    raise FileNotFoundError(f"图片 {shortPathOfTarget} 不可用")

def reflectImage(folder):
    pattern = os.path.join(IMAGE_FOLDER, folder, '*.png')
    full_pattern = ResourcePath(pattern)
    png_files = glob.glob(full_pattern)
    img = sorted([os.path.splitext(os.path.basename(f))[0] for f in png_files])
    return img

DIALOG_OPTION_IMAGE_LIST = reflectImage('dialogueChoices')
CHAR_LIST = sorted(list({img.split('_')[0] for img in reflectImage(os.path.join('spellskill', 'char'))}))

###########################################
class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window:
            return
            
        widget_x = self.widget.winfo_rootx()
        widget_y = self.widget.winfo_rooty()
        widget_width = self.widget.winfo_width()
        widget_height = self.widget.winfo_height()
        
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.attributes("-alpha", 0.95)
        
        label = ttk.Label(
            self.tooltip_window, 
            text=self.text, 
            background="#ffffe0", 
            relief="solid", 
            borderwidth=1,
            padding=(8, 4),
            font=("Arial", 10),
            justify="left",
            wraplength=300
        )
        label.pack()
        
        x = widget_x + widget_width + 2
        y = widget_y + widget_height//2
        
        self.tooltip_window.wm_geometry(f"+{int(x)}+{int(y)}")
        self.tooltip_window.deiconify()

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
###########################################
MASK3 = LoadTemplateImage("spellskill/arrow/mask3") # 边缘
if MASK3.ndim == 3:
    MASK3 = cv2.cvtColor(MASK3, cv2.COLOR_BGR2GRAY)
    MASK3 = MASK3.astype(np.float32) / 255.0
    
def StateCombat_DetectArrow(screenshot):
    """
    使用手绘三角形模板匹配检测图像中的三角形区域。

    参数:
        mask3: 灰度模板图像（白色内部，黑色外部），用于提取边缘方向场
        screenshot: BGR彩色测试图像
        threshold: 归一化响应的阈值，范围[0,1]，默认0.5

    返回:
        results: 去重后的检测结果列表，每个元素为 (center_x, center_y, score, channel_label)
        marked_img: 在原图上标记了所有检测框的图像
    """

    threshold = 0.5

    # ---------- 模板方向场 ----------
    gx_t = cv2.Sobel(MASK3, cv2.CV_32F, 1, 0, ksize=3)
    gy_t = cv2.Sobel(MASK3, cv2.CV_32F, 0, 1, ksize=3)
    mag_t = np.sqrt(gx_t**2 + gy_t**2) + 1e-6
    gx_t /= mag_t
    gy_t /= mag_t

    mask_h, mask_w = MASK3.shape[:2]
    dedup_dist = 0.5 * min(mask_h, mask_w)   # 去重距离阈值（模板短边一半）

    # ---------- 准备测试通道：灰度和R通道 ----------
    gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
    _, _, r_channel = cv2.split(screenshot)   # BGR顺序，R是第三个
    channel_data = [('Grey', gray), ('R', r_channel)]

    all_detections = []   # 存储所有通道的检测结果（字典形式）

    for label, ch in channel_data:
        # 高斯模糊（抑制噪声，使梯度方向稳定）
        blurred = cv2.GaussianBlur(ch, (5, 5), 0)

        # 计算梯度
        gx = cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(blurred, cv2.CV_32F, 0, 1, ksize=3)

        # 方向内积响应
        resp_x = cv2.filter2D(gx, -1, gx_t, borderType=cv2.BORDER_CONSTANT)
        resp_y = cv2.filter2D(gy, -1, gy_t, borderType=cv2.BORDER_CONSTANT)
        response = resp_x + resp_y

        # 按该通道最大响应归一化
        max_val = response.max()
        if max_val <= 0:
            continue
        norm_response = response / max_val

        # 阈值过滤
        binary = (norm_response >= threshold).astype(np.uint8) * 255

        # 查找轮廓
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 10:   # 过滤小面积噪声
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            center_x = x + w // 2
            center_y = y + h // 2

            # 取该矩形区域内最大归一化响应作为得分
            roi = norm_response[y:y+h, x:x+w]
            score = roi.max()

            # 用字典保存检测信息
            all_detections.append({
                'center': (center_x, center_y),
                'score': score,
                'label': label,
                'bbox': (x, y, w, h)
            })

    # 按得分降序排序
    all_detections.sort(key=lambda d: d['score'], reverse=True)

    # 去重（基于中心距离的非极大值抑制）
    kept_detections = []
    for det in all_detections:
        cx, cy = det['center']
        duplicate = False
        for kept in kept_detections:
            kx, ky = kept['center']
            if (cx - kx) ** 2 + (cy - ky) ** 2 < dedup_dist ** 2:
                duplicate = True
                break
        if not duplicate:
            kept_detections.append(det)

    # ---------- 在原图上标记结果 ----------
    marked_img = screenshot.copy()
    for det in kept_detections:
        x, y, w, h = det['bbox']
        score = det['score']
        label = det['label']
        cv2.rectangle(marked_img, (x, y), (x + w, y + h), (0, 255, 0), 2)
        text = f'{label}:{score:.2f}'
        cv2.putText(marked_img, text, (x, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    # 转换为要求的输出格式（元组列表）
    results = [(det['center'][0], det['center'][1], det['score'], det['label']) for det in kept_detections]

    return results, marked_img

##############
BOBBER = LoadTemplateImage("fishing/bobber") # 边缘
if BOBBER.ndim == 3:
    BOBBER = cv2.cvtColor(BOBBER, cv2.COLOR_BGR2GRAY)

def Fishing_DetectBobber(screenshot):
    # 参数
    threshold=0.5

    # 模板方向场
    mask_float = BOBBER.astype(np.float32) / 255.0
    gx_t = cv2.Sobel(mask_float, cv2.CV_32F, 1, 0, ksize=3)
    gy_t = cv2.Sobel(mask_float, cv2.CV_32F, 0, 1, ksize=3)
    mag_t = np.sqrt(gx_t**2 + gy_t**2) + 1e-6
    gx_t, gy_t = gx_t / mag_t, gy_t / mag_t

    side = min(BOBBER.shape[:2])
    dedup_dist = 0.5 * side

    # R通道缩放
    r_channel = screenshot[:, :, 2].astype(np.float32)
    r_scaled = np.clip((r_channel - 14.0) * (255.0 / 86.0), 0, 255).astype(np.uint8)

    # 方向场响应
    blurred = cv2.GaussianBlur(r_scaled, (5, 5), 0)
    gx = cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(blurred, cv2.CV_32F, 0, 1, ksize=3)
    resp = (cv2.filter2D(gx, -1, gx_t, borderType=cv2.BORDER_CONSTANT) +
            cv2.filter2D(gy, -1, gy_t, borderType=cv2.BORDER_CONSTANT))

    max_resp = resp.max()
    if max_resp <= 0:
        return [], r_scaled.copy()

    norm_resp = resp / max_resp
    binary = (norm_resp >= threshold).astype(np.uint8) * 255

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    detections = []
    for cnt in contours:
        if cv2.contourArea(cnt) < 10:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        cx, cy = x + w // 2, y + h // 2
        score = norm_resp[y:y+h, x:x+w].max()
        detections.append({'center': (cx, cy), 'score': float(score), 'bbox': (x, y, w, h)})

    detections.sort(key=lambda d: d['score'], reverse=True)
    kept = []
    for det in detections:
        if not any((det['center'][0]-k['center'][0])**2 + (det['center'][1]-k['center'][1])**2 < dedup_dist**2 for k in kept):
            kept.append(det)

    # 模板匹配得分与过滤
    final = []
    for det in kept:
        cx, cy = det['center']
        x1, y1 = max(cx - side//2, 0), max(cy - side//2, 0)
        x2 = min(cx + side//2, screenshot.shape[1]-1)
        y2 = min(cy + side//2, screenshot.shape[0]-1)
        roi = r_scaled[y1:y2, x1:x2]
        tmpl = cv2.resize(BOBBER, (roi.shape[1], roi.shape[0]))
        match_score = float((cv2.matchTemplate(roi, tmpl, cv2.TM_CCOEFF_NORMED)[0][0] + 1.0) / 2.0)
        det['match_score'] = match_score
        if det['score'] >= 0.9 and match_score >= 0.8:
            final.append(det)

    # 标记
    marked = r_scaled.copy()
    for det in final:
        cx, cy = det['center']
        x1, y1 = max(cx - side//2, 0), max(cy - side//2, 0)
        x2 = min(cx + side//2, marked.shape[1]-1)
        y2 = min(cy + side//2, marked.shape[0]-1)
        cv2.rectangle(marked, (x1, y1), (x2, y2), 255, 2)
        cv2.putText(marked, f'DF:{det["score"]:.2f}', (x1, y1-5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, 255, 1)
        cv2.putText(marked, f'MA:{det["match_score"]:.2f}', (x1, y1-20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, 255, 1)

    return [(d['center'][0], d['center'][1], d['score'], d['match_score']) for d in final], marked

# EOF