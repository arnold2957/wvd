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
def StateCombat_DetectArrow(screenshot):
    """
    边缘分数采用膨胀-腐蚀边界卷积，并在归一化图上应用阈值。
    """
    # ---------- 0. 参数设定 ----------
    mask1 = LoadTemplateImage("spellskill/arrow/mask1") # 箭头内部区域
    if mask1.ndim == 3:
        mask1 = cv2.cvtColor(mask1, cv2.COLOR_BGR2GRAY)
    mask2 = LoadTemplateImage("spellskill/arrow/mask2") # 非箭头区域, 近似看作背景
    if mask2.ndim == 3:
        mask2 = cv2.cvtColor(mask2, cv2.COLOR_BGR2GRAY)
    mask3 = LoadTemplateImage("spellskill/arrow/mask3") # 边缘
    if mask3.ndim == 3:
        mask3 = cv2.cvtColor(mask3, cv2.COLOR_BGR2GRAY)

    edge_thresh_norm=200     # 归一化后阈值（0~255）
    color_score_thresh=0.6
    iou_thresh=0.3

    # ---------- 1. 计算梯度幅度 ----------
    if screenshot.ndim == 3:
        gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
    else:
        gray = screenshot
    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad_mag = cv2.magnitude(grad_x, grad_y)

    # ---------- 2. 构建膨胀-腐蚀边界核 ----------
    kernel = np.ones((3, 3), np.uint8)
    # 注意：这里对 mask3 进行膨胀-腐蚀，而不是直接用 mask3
    boundary = (cv2.dilate(mask3, kernel) - cv2.erode(mask3, kernel)) > 0
    boundary = boundary.astype(np.float32)
    boundary_count = boundary.sum()
    if boundary_count == 0:
        raise ValueError("膨胀-腐蚀后边界为空，请检查 mask3")

    # ---------- 3. 计算边缘强度图 ----------
    edge_sum = cv2.filter2D(grad_mag, cv2.CV_32F, boundary,
                            borderType=cv2.BORDER_REPLICATE)
    edge_map = edge_sum / boundary_count   # 原始平均梯度

    # ---------- 4. 归一化并阈值化 ----------
    edge_norm = cv2.normalize(edge_map, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    _, high_edge_mask = cv2.threshold(edge_norm, edge_thresh_norm, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(high_edge_mask, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)

    # ---------- 5. 提取候选中心（质心） ----------
    candidate_centers = []
    for cnt in contours:
        M = cv2.moments(cnt)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
        else:
            x, y, w, h = cv2.boundingRect(cnt)
            cx, cy = x + w // 2, y + h // 2
        # 从原始边缘强度图中获取该点的分数
        edge_score = float(edge_map[cy, cx])
        candidate_centers.append((cx, cy, edge_score))

    # ---------- 6. 颜色匹配验证 ----------
    m1 = (mask1 > 127).astype(np.float32)
    m2 = (mask2 > 127).astype(np.float32)
    # N1, N2 = m1.sum(), m2.sum()
    H_k, W_k = mask1.shape
    half_h, half_w = H_k // 2, W_k // 2
    img_float = screenshot.astype(np.float32)
    H_img, W_img = img_float.shape[:2]

    candidates = []
    for cx, cy, edge_score in candidate_centers:
        x0 = cx - half_w
        y0 = cy - half_h
        if x0 < 0 or y0 < 0 or x0 + W_k > W_img or y0 + H_k > H_img:
            continue

        roi = img_float[y0:y0+H_k, x0:x0+W_k]
        bg_mean = roi[m2 > 0.5].mean(axis=0)
        pred_mean = 0.7 * bg_mean + 100.0 # 该公式是由数据拟合而来
        actual_mean = roi[m1 > 0.5].mean(axis=0)
        mae = float(np.mean(np.abs(actual_mean - pred_mean)))
        color_score = 1.0 / (1.0 + mae / 50.0)

        if color_score >= color_score_thresh:
            edge_norm = min(edge_score / 300.0, 1.0)
            total = edge_norm + color_score
            candidates.append((x0, y0, W_k, H_k, edge_score, color_score,
                            edge_norm, total))

    # ---------- 7. 非极大值抑制 ----------
    if iou_thresh > 0 and candidates:
        candidates.sort(key=lambda c: c[7], reverse=True)
        keep = []
        while candidates:
            best = candidates.pop(0)
            keep.append(best)
            bx, by, bw, bh = best[0], best[1], best[2], best[3]
            filtered = []
            for c in candidates:
                x, y, w_, h_ = c[0], c[1], c[2], c[3]
                ix1, iy1 = max(bx, x), max(by, y)
                ix2, iy2 = min(bx+bw, x+w_), min(by+bh, y+h_)
                if ix2 <= ix1 or iy2 <= iy1:
                    filtered.append(c)
                else:
                    inter = (ix2-ix1)*(iy2-iy1)
                    union = bw*bh + w_*h_ - inter
                    if inter/union < iou_thresh:
                        filtered.append(c)
            candidates = filtered
        final_candidates = keep
    else:
        final_candidates = candidates
    
    final_candidates = sorted(final_candidates, key=lambda c: c[7], reverse=True)

    # ---------- 8. 绘制结果 ----------
    result_img = screenshot.copy()
    for x0, y0, w, h, edge_score, color_score, edge_norm, total in final_candidates:
        cv2.rectangle(result_img, (x0, y0), (x0 + w, y0 + h), (0, 255, 0), 2)
        cv2.putText(result_img, f"En:{edge_norm:.2f}", (x0, y0 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        cv2.putText(result_img, f"C:{color_score:.2f}", (x0, y0 + h + 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    return result_img, final_candidates