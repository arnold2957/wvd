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