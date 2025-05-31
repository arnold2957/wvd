import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import json
import os
import logging
from script import *
from threading import Thread,Event
import subprocess
import socket
import time
import shutil

VERSION = '0.5.2.2'
CONFIG_FILE = 'config.json'
LOG_FILE_NAME = "log.txt"
if os.path.exists(LOG_FILE_NAME):
    os.remove(LOG_FILE_NAME)
with open(LOG_FILE_NAME, 'w', encoding='utf-8') as f:
    pass
RESTART_SCREENSHOT_FOLDER_NAME = "screenshotwhenrestart"
if os.path.exists(RESTART_SCREENSHOT_FOLDER_NAME):
    shutil.rmtree(RESTART_SCREENSHOT_FOLDER_NAME)
os.makedirs(RESTART_SCREENSHOT_FOLDER_NAME, exist_ok=True)

# --- 预定义的技能和目标 ---
DUNGEON_TARGETS = ["[刷图]水路一号街",
                   "[刷图]水路船一 shiphold",
                   "[刷图]水路船二 lounge",
                   "[刷图]鸟洞三层 fordraig B3F",
                   "[刷图]卢比肯的洞窟",
                   "[刷图]土洞(5-9)",
                   "[刷图]火洞(10-14)", 
                   "[刷图]光洞(15-19)",
                   "[任务]7000G",
                   "[任务]角鹫之剑 fordraig",
                   "[任务]击退敌势力",
                   ]

ESOTERIC_AOE_SKILLS = ["SAoLABADIOS","SAoLAERLIK","SAoLAFOROS"]
FULL_AOE_SKILLS = ["LAERLIK", "LAMIGAL","LAZELOS", "LACONES", "LAFOROS"]
ROW_AOE_SKILLS = ["maerlik", "mahalito", "mamigal","mazelos","maferu", "macones","maforos"]
PHYSICAL_SKILLS = ["FPS","tzalik","PS","AB","HA","SB",]

ALL_SKILLS = ESOTERIC_AOE_SKILLS + FULL_AOE_SKILLS + ROW_AOE_SKILLS +  PHYSICAL_SKILLS
ALL_SKILLS = [s for s in ALL_SKILLS if s in list(set(ALL_SKILLS))]

############################################
logger = logging.getLogger('WvDLogger')
logger.setLevel(logging.DEBUG)
# 文件句柄
file_handler = logging.FileHandler(LOG_FILE_NAME, mode='a', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)
# tk组件句柄
scrolled_text_formatter = logging.Formatter(
    '%(message)s'
)
class ScrolledTextHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.text_widget.config(state=tk.DISABLED)

    def emit(self, record):
        msg = self.format(record)
        try:
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.see(tk.END)
            self.text_widget.config(state=tk.DISABLED)
        except Exception:
            self.handleError(record)
############################################
class ConfigPanelApp:
    def __init__(self, root):
        self.root = root
        self.root.geometry('450x470')
        # self.root.resizable(False, False)
        self.root.title(f"WvD 巫术daphne自动刷怪 v{VERSION} @德德Dellyla(B站)")

        self.adb_active = False

        self.thread = None
        self.continue_trigger = Event()
        self.stop_event = Event()

        # --- ttk Style ---
        self.style = ttk.Style()
        # 你可以尝试不同的主题, 如 'clam', 'alt', 'default', 'classic'
        # self.style.theme_use('clam')
        self.style.configure("Active.TButton", foreground="green")
        # "Inactive.TButton" 可以不特别定义，恢复到默认的 "TButton" 即可
        # 或者显式定义: self.style.configure("Inactive.TButton", foreground="black") # 或其他默认颜色

        self.config = self.load_config()

        # --- UI 变量 ---
        self.farm_target_var = tk.StringVar(value=self.config.get("_FARMTARGET", DUNGEON_TARGETS[0] if DUNGEON_TARGETS else ""))
        self.randomly_open_chest_var = tk.BooleanVar(value=self.config.get("_RANDOMLYOPENCHEST", False))
        self.randomly_people_open_chest_var = tk.BooleanVar(value=self.config.get("_RANDOMLYPERSONOPENCHEST", False))
        self.skip_recover_var = tk.BooleanVar(value=self.config.get("_SKIPCOMBATRECOVER", False))
        self.system_auto_combat_var = tk.BooleanVar(value=self.config.get("SYSTEM_AUTO_COMBAT_ENABLED", False))
        self.rest_intervel_var = tk.StringVar(value=self.config.get("_RESTINTERVEL", 0))
        self.adb_path_var = tk.StringVar(value=self.config.get("ADB_PATH", ""))
        self.adb_port_var = tk.StringVar(value=self.config.get("ADB_PORT", 5555))

        self._spell_skill_config_internal = list(self.config.get("_SPELLSKILLCONFIG", []))

        self.skill_buttons_map = [] # 用于存储按钮和它们关联的技能列表

        self.create_widgets()
        self.update_combat_buttons_state() # 初始化时更新按钮状态 (包括启用/禁用)
        self.update_skill_button_visuals() # 初始化时更新技能按钮颜色
        self.update_current_skills_display() # 初始化时更新技能显示

        logger.info("**********************\n" \
                    f"当前版本: {VERSION}\n"\
        "使用前请确保以下模拟器设置:\n" \
        "1 模拟器已经允许adb调试. 位于\"设置\"-\"高级\"-\"adb调试\"的设置已经打开.\n" \
        "2 模拟器分辨率为 1600x900, 240 dpi.\n" \
        "3 多开模拟器时, 请确保运行巫术的模拟器为第一个启动的模拟器.\n" \
        "**********************\n" \
        "如果没有勾选\"开箱子时随机人选\", 那么固定使用左上角的人开箱. 多次选人失败后会临时变为随机人选开箱.\n" \
        "**********************\n"\
        "旅店休息间隔是间隔多少次地下城休息. 0代表一直休息, 1代表间隔一次休息, 以此类推.\n" \
        "**********************\n"\
        "现在可用的强力单体技能包括 精密攻击, 眩晕突袭, 浑身一击 扎兹里克 以及 强袭.\n" \
        "**********************\n"\
        "每次进入地下城必定会恢复. 开宝箱后必定会恢复. 界面按钮控制战斗后是否恢复.\n"\
        "**********************\n"\
        "击退敌势力流程不包括时间跳跃和接取任务, 请确保接取任务后再开启!\n"\
        "**********************\n")
        
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 确保关键字段存在
                    defaults = self.get_default_config()
                    for key, value in defaults.items():
                        loaded_config.setdefault(key, value)
                    return loaded_config
            except json.JSONDecodeError:
                messagebox.showerror("错误", f"无法解析 {CONFIG_FILE}。将使用默认配置。")
                return self.get_default_config()
            except Exception as e:
                messagebox.showerror("错误", f"加载配置时发生错误: {e}。将使用默认配置。")
                return self.get_default_config()
        else:
            return self.get_default_config()

    def get_default_config(self):
        return {
            "ADB_PATH": "",
            "_FARMTARGET": DUNGEON_TARGETS[0] if DUNGEON_TARGETS else "默认地牢",
            "_RANDOMLYOPENCHEST": False,
            "_SPELLSKILLCONFIG": [],
            "SYSTEM_AUTO_COMBAT_ENABLED": False
        }

    def save_config(self):
        self.config["ADB_PATH"] = self.adb_path_var.get()
        self.config["ADB_PORT"] = self.adb_port_var.get()
        self.config["_FARMTARGET"] = self.farm_target_var.get()
        self.config["_RANDOMLYOPENCHEST"] = self.randomly_open_chest_var.get()
        self.config["_RANDOMLYPERSONOPENCHEST"] = self.randomly_people_open_chest_var.get()
        self.config["SYSTEM_AUTO_COMBAT_ENABLED"] = self.system_auto_combat_var.get()
        self.config["_RESTINTERVEL"] = self.rest_intervel_var.get()
        self.config["_SKIPCOMBATRECOVER"] = self.skip_recover_var.get()

        if self.system_auto_combat_var.get():
            self.config["_SPELLSKILLCONFIG"] = []
        else:
            self.config["_SPELLSKILLCONFIG"] = list(set(self._spell_skill_config_internal))

        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            logger.info("配置已保存。")
        except Exception as e:
            messagebox.showerror("错误", f"保存配置时发生错误: {e}")

    def create_widgets(self):
        self.log_display = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, state=tk.DISABLED, bg='white', width = 22, height = 1)
        self.log_display.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.scrolled_text_handler = ScrolledTextHandler(self.log_display)
        self.scrolled_text_handler.setLevel(logging.INFO)
        self.scrolled_text_handler.setFormatter(scrolled_text_formatter)
        logger.addHandler(self.scrolled_text_handler)

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 第0行 设定adb
        frame_row0 = ttk.Frame(main_frame)
        frame_row0.grid(row=0, column=0, sticky="ew", pady=5)  # 首行框架
        self.adb_status_label = ttk.Label(frame_row0)
        self.adb_status_label.grid(row=0, column=0,)
        # 隐藏的Entry用于存储变量
        adb_entry = ttk.Entry(frame_row0, textvariable=self.adb_path_var)
        adb_entry.grid_remove()
        def selectADB_PATH():
            path = filedialog.askopenfilename(
                title="选择ADB执行文件",
                filetypes=[("Executable", "*.exe"), ("All files", "*.*")]
            )
            if path:
                self.adb_path_var.set(path)
                self.save_config()
        # 浏览按钮
        self.adb_path_change_button = ttk.Button(
            frame_row0,
            text="修改",
            command=selectADB_PATH,
            width = 5,
        )
        self.adb_path_change_button.grid(row=0,column=1)
        # 初始化标签状态
        def update_adb_status(*args):
            if self.adb_path_var.get():
                self.adb_status_label.config(text="已设定ADB", foreground="green")
            else:
                self.adb_status_label.config(text="未设定ADB", foreground="red")
        
        self.adb_path_var.trace_add("write", lambda *args: update_adb_status())
        update_adb_status()  # 初始调用

        ttk.Label(frame_row0, text="端口:").grid(row=0, column=2, sticky=tk.W, pady=5)
        vcmd = root.register(lambda x: ((x=="")or(x.isdigit())))
        self.adb_port_entry = ttk.Entry(frame_row0,
                                        textvariable=self.adb_port_var,
                                        validate="key",
                                        validatecommand=(vcmd, '%P'),
                                        width=5)
        self.adb_port_entry.grid(row=0, column=3)
        self.button_save_adb_port = ttk.Button(
            frame_row0,
            text="保存",
            command = self.save_config,
            width=5
            )
        self.button_save_adb_port.grid(row=0, column=4)

        # 第1行 分割线.
        ttk.Separator(main_frame, orient='horizontal').grid(row=1, column=0, columnspan=3, sticky='ew', pady=10)

        # 第2行 地下城目标
        frame_row2 = ttk.Frame(main_frame)
        frame_row2.grid(row=2, column=0, sticky="ew", pady=5)  # 第二行框架
        ttk.Label(frame_row2, text="地下城目标:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.farm_target_combo = ttk.Combobox(frame_row2, textvariable=self.farm_target_var, values=DUNGEON_TARGETS, state="readonly")
        self.farm_target_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)
        self.farm_target_combo.bind("<<ComboboxSelected>>", lambda e: self.save_config())

        # 第3行 开箱子设置
        frame_row3 = ttk.Frame(main_frame)
        frame_row3.grid(row=3, column=0, sticky="ew", pady=5)  # 第二行框架
        self.random_chest_check = ttk.Checkbutton(
            frame_row3,
            text="智能开箱(测试版)",
            variable=self.randomly_open_chest_var,
            command=self.save_config
        )
        self.random_chest_check.grid(row=0, column=0,  sticky=tk.W, pady=5)
        self.random_people_open_check = ttk.Checkbutton(
            frame_row3,
            text="开箱时随机人选",
            variable=self.randomly_people_open_chest_var,
            command=self.save_config
        )
        self.random_people_open_check.grid(row=0, column=1,  sticky=tk.W, pady=5)



        # 第4行 跳过恢复
        self.skip_recover_check = ttk.Checkbutton(
            main_frame,
            text="不进行战后恢复",
            variable=self.skip_recover_var,
            command=self.save_config
        )
        self.skip_recover_check.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=5)

        # 第5行 休息设置
        frame_row5 = ttk.Frame(main_frame)
        frame_row5.grid(row=5, column=0, sticky="ew", pady=5)
        ttk.Label(frame_row5, text="旅店休息间隔:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.rest_intervel_entry = ttk.Entry(frame_row5,
                                             textvariable=self.rest_intervel_var,
                                             validate="key",
                                             validatecommand=(vcmd, '%P'),
                                             width=8)
        self.rest_intervel_entry.grid(row=0, column=1)
        self.button_save_rest_intervel = ttk.Button(
            frame_row5,
            text="保存",
            command = self.save_config,
            width=5
            )
        self.button_save_rest_intervel.grid(row=0, column=2)

        # 第6行 启动! 以及继续
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=5, sticky=tk.W)
        
        s = ttk.Style()
        s.configure('start.TButton', font=('微软雅黑', 15))
        self.start_stop_btn = ttk.Button(
            button_frame,
            text="脚本, 启动!",
            command=self.toggle_start_stop,
            style='start.TButton'
        )
        self.start_stop_btn.grid(row=0, column=0, padx=2)

        self.continue_btn = ttk.Button(
            button_frame,
            text="继续",
            command=self.continue_execution,
        )
        self.continue_btn.grid(row=0, column=1, padx=2)
        self.continue_btn.grid_remove()

        # 第7行 分割线
        ttk.Separator(main_frame, orient='horizontal').grid(row=7, column=0, columnspan=3, sticky='ew', pady=10)

        # 第8行 技能配置 文本
        ttk.Label(main_frame, text="技能配置:", font=('Arial', 10, 'bold')).grid(row=8, column=0, sticky=tk.W, pady=5)

        # 第9行 系统自动战斗
        self.system_auto_check = ttk.Checkbutton(
            main_frame,
            text="启用系统自动战斗",
            variable=self.system_auto_combat_var,
            command=self.toggle_system_auto_combat
        )
        self.system_auto_check.grid(row=9, column=0, columnspan=2, sticky=tk.W, pady=5)

        # 第10行 技能按钮框架
        self.skills_button_frame = ttk.Frame(main_frame)
        self.skills_button_frame.grid(row=10, column=0, columnspan=2, sticky=tk.W)

        self.btn_enable_all = ttk.Button(self.skills_button_frame, text="启用所有技能", command=lambda: self.update_spell_config(ALL_SKILLS, "all"))
        self.btn_enable_all.grid(row=0, column=0, padx=2, pady=2)
        self.skill_buttons_map.append({"button": self.btn_enable_all, "skills": ALL_SKILLS, "name": "all"})

        self.btn_enable_horizontal_aoe = ttk.Button(self.skills_button_frame, text="启用所有横排AOE", command=lambda: self.update_spell_config(ROW_AOE_SKILLS, "horizontal_aoe"))
        self.btn_enable_horizontal_aoe.grid(row=0, column=1, padx=2, pady=2)
        self.skill_buttons_map.append({"button": self.btn_enable_horizontal_aoe, "skills": ROW_AOE_SKILLS, "name": "horizontal_aoe"})

        self.btn_enable_full_aoe = ttk.Button(self.skills_button_frame, text="启用所有全体AOE", command=lambda: self.update_spell_config(FULL_AOE_SKILLS, "full_aoe"))
        self.btn_enable_full_aoe.grid(row=1, column=0, padx=2, pady=2)
        self.skill_buttons_map.append({"button": self.btn_enable_full_aoe, "skills": FULL_AOE_SKILLS, "name": "full_aoe"})

        self.btn_enable_esoteric_aoe = ttk.Button(self.skills_button_frame, text="启用秘术AOE", command=lambda: self.update_spell_config(ESOTERIC_AOE_SKILLS, "esoteric_aoe"))
        self.btn_enable_esoteric_aoe.grid(row=1, column=1, padx=2, pady=2)
        self.skill_buttons_map.append({"button": self.btn_enable_esoteric_aoe, "skills": ESOTERIC_AOE_SKILLS, "name": "esoteric_aoe"})

        self.btn_enable_physical = ttk.Button(self.skills_button_frame, text="启用强力单体", command=lambda: self.update_spell_config(PHYSICAL_SKILLS, "physical_skills"))
        self.btn_enable_physical.grid(row=2, column=0, padx=2, pady=2)
        self.skill_buttons_map.append({"button": self.btn_enable_physical, "skills": PHYSICAL_SKILLS, "name": "physical_skills"})

        # 第11行 技能选择结果展示
        self.current_skills_label_var = tk.StringVar()
        current_skills_display = ttk.Label(main_frame, textvariable=self.current_skills_label_var, wraplength=230)
        # current_skills_display.grid(row=11, column=0, columnspan=2, sticky=tk.W+tk.E, pady=5)

    def update_current_skills_display(self):
        if self.system_auto_combat_var.get():
            self.current_skills_label_var.set(f"启用系统自动战斗")
        else:
            # 显示去重后的技能列表
            unique_skills = list(dict.fromkeys(self._spell_skill_config_internal))
            self.current_skills_label_var.set(f"当前技能: {unique_skills}")

    def toggle_system_auto_combat(self):
        is_system_auto = self.system_auto_combat_var.get()
        if is_system_auto:
            self._spell_skill_config_internal = ["systemAuto"]
        else:
            # 确保不是 ['systemAuto']，如果是，则清空
            if self._spell_skill_config_internal == ["systemAuto"]:
                 self._spell_skill_config_internal = []
        self.update_combat_buttons_state() # 会调用 update_skill_button_visuals 和 update_current_skills_display
        self.save_config()


    def update_combat_buttons_state(self):
        is_system_auto = self.system_auto_combat_var.get()
        button_state = tk.DISABLED if is_system_auto else tk.NORMAL

        for item in self.skill_buttons_map:
            item["button"].config(state=button_state)

        # 如果是从 "systemAuto" 切换回来，并且 _spell_skill_config_internal 还是 ['systemAuto']
        # 则清空它，因为此时用户可以手动选择技能了。
        if not is_system_auto and self._spell_skill_config_internal == ["systemAuto"]:
            self._spell_skill_config_internal = []

        self.update_skill_button_visuals() # 更新按钮颜色
        self.update_current_skills_display() # 更新技能显示


    def update_spell_config(self, skills_to_process, category_name):
        if self.system_auto_combat_var.get():
            return

        current_skill_set = set(self._spell_skill_config_internal)
        skills_to_process_set = set(skills_to_process)

        if category_name == "all":
            # "启用所有技能" 按钮：如果当前所有技能都已启用，再次点击则清空所有技能。否则，启用所有技能。
            if skills_to_process_set.issubset(current_skill_set) and len(skills_to_process_set) == len(current_skill_set) and len(current_skill_set) > 0 : # 确保不是空集对空集
                self._spell_skill_config_internal = []
                logger.info("已取消所有技能。")
            else:
                self._spell_skill_config_internal = list(skills_to_process_set)
                logger.info(f"已启用所有技能: {self._spell_skill_config_internal}")
        else:
            # 其他技能按钮：如果该类别的所有技能都已启用，则移除这些技能。否则，添加这些技能。
            is_fully_active = skills_to_process_set.issubset(current_skill_set)

            if is_fully_active:
                self._spell_skill_config_internal = [s for s in self._spell_skill_config_internal if s not in skills_to_process_set]
                logger.info(f"已禁用 {category_name} 技能. 当前技能: {self._spell_skill_config_internal}")
            else:
                for skill in skills_to_process:
                    if skill not in self._spell_skill_config_internal:
                        self._spell_skill_config_internal.append(skill)
                logger.info(f"已启用/添加 {category_name} 技能. 当前技能: {self._spell_skill_config_internal}")

        # 保证唯一性，但保留顺序（如果重要的话，使用 dict.fromkeys）
        self._spell_skill_config_internal = list(dict.fromkeys(self._spell_skill_config_internal))

        self.update_current_skills_display()
        self.update_skill_button_visuals()
        self.save_config()

    def update_skill_button_visuals(self):
        """根据当前 _spell_skill_config_internal 更新技能按钮的样式"""
        if self.system_auto_combat_var.get():
            # 如果是系统自动战斗，所有按钮都应该是默认样式（因为它们被禁用了）
            for item in self.skill_buttons_map:
                item["button"].configure(style="TButton") # 恢复默认样式
            return

        current_skill_set = set(self._spell_skill_config_internal)

        for item in self.skill_buttons_map:
            button = item["button"]
            skills_for_button = set(item["skills"])
            category_name = item["name"]

            # 特殊处理 "all" 按钮
            if category_name == "all":
                # 如果 ALL_SKILLS 中的所有技能都在 current_skill_set 中，并且数量一致
                if skills_for_button and skills_for_button.issubset(current_skill_set) and len(skills_for_button) == len(current_skill_set) and len(current_skill_set) > 0:
                    button.configure(style="Active.TButton")
                else:
                    button.configure(style="TButton")
            else:
                # 检查该按钮对应的所有技能是否都在当前配置中
                if skills_for_button and skills_for_button.issubset(current_skill_set):
                    button.configure(style="Active.TButton")
                else:
                    button.configure(style="TButton") # 恢复默认样式
    def set_controls_state(self, state):
        if state == tk.DISABLED:
            self.adb_path_change_button.configure(state="disabled")
            self.farm_target_combo.configure(state="disabled")
            self.random_chest_check.configure(state="disabled")
            self.random_people_open_check.configure(state="disabled")
            self.system_auto_check.configure(state="disabled")
            self.skip_recover_check.configure(state="disabled")
            self.rest_intervel_entry.configure(state="disabled")
            self.button_save_rest_intervel.configure(state="disabled")
            self.adb_port_entry.configure(state='disabled')
            self.button_save_adb_port.configure(state='disabled')
        else:
            self.adb_path_change_button.configure(state="normal")
            self.farm_target_combo.configure(state="readonly") 
            self.random_chest_check.configure(state="normal")
            self.random_people_open_check.configure(state="normal")
            self.system_auto_check.configure(state="normal")
            self.skip_recover_check.configure(state="normal")
            self.rest_intervel_entry.configure(state="normal")
            self.button_save_rest_intervel.configure(state="normal")
            self.adb_port_entry.configure(state='normal')
            self.button_save_adb_port.configure(state='normal')
        """设置所有控件的状态"""
        if not self.system_auto_combat_var.get():
            widgets = [
                *[item["button"] for item in self.skill_buttons_map]
            ]
            for widget in widgets:
                if isinstance(widget, ttk.Widget):
                    widget.state([state.lower()] if state != tk.NORMAL else ['!disabled'])

    def toggle_start_stop(self):
        if self.thread and (not self.thread.is_alive()):
            self.thread.join()
            self.thread = None
            self.stop_event.clear()
        if self.thread is None:
            self.start_stop_btn.config(text="中断")
            self.set_controls_state(tk.DISABLED)
            self.thread = Thread(target=self.dungeonLoop)
            self.thread.start()
        else: # self.thread is NOT None
            if self.thread.is_alive():
                logger.info("等待当前步骤执行完毕, 执行完毕后将中断脚本. 这可能需要一些时间...")
                self.stop_event.set()

    def finishingcallback(self):
        logger.info("已中断.")
        self.start_stop_btn.config(text="脚本, 启动!")
        self.set_controls_state(tk.NORMAL)
        self.continue_btn.grid_remove()

    def continue_execution(self):
        self.continue_btn.grid_remove()
        self.continue_trigger.set()

    def start_adb_server(self):
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
                logger.info(f"开始启动ADB服务, 路径:{self.adb_path_var.get()}")
                # 启动adb服务（非阻塞模式）
                subprocess.Popen(
                    [self.adb_path_var.get(), "start-server"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    shell=True
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

    def dungeonLoop(self):
        if not self.adb_active:
            self.adb_active = self.start_adb_server()
            if not self.adb_active:
                self.finishingcallback()
                return

        client = AdbClient(host="127.0.0.1", port=5037)
        client.remote_connect("127.0.0.1", int(self.adb_port_var.get()))
        devices = client.devices()
        if (not devices) or not (devices[0]):
            logger.info("创建adb链接失败.")
            self.finishingcallback()
            return
        device = devices[0]

        logger.info(f"目标地下城:{self.farm_target_var.get()}")
        setting = FarmSetting()
        setting._SYSTEMAUTOCOMBAT = self.system_auto_combat_var.get()
        setting._RANDOMLYOPENCHEST = self.randomly_open_chest_var.get()
        setting._RANDOMLYPERSONOPENCHEST = self.randomly_people_open_chest_var.get()
        setting._SKIPCOMBATRECOVER = self.skip_recover_var.get()
        setting._FORCESTOPING = self.stop_event
        setting._SPELLSKILLCONFIG = [s for s in ALL_SKILLS if s in list(set(self._spell_skill_config_internal))]
        setting._FINISHINGCALLBACK = self.finishingcallback
        setting._RESTINTERVEL = int(self.rest_intervel_var.get())
        setting._ADBDEVICE = device
        setting._LOGGER = logger
        StreetFarm,QuestFarm = Factory()
        match self.farm_target_var.get():
            case "[刷图]水路船一 shiphold":
                setting._FARMTARGET = 'shiphold'
                setting._TARGETLIST = ['chest','harken']
                StreetFarm(setting)
            case "[刷图]水路船二 lounge":
                setting._FARMTARGET = 'shiphold'
                setting._TARGETLIST = ['shiphold_upstair_once','chest','lounge_downstair_once','harken']
                setting._TARGETSEARCHDIR = [[[1,1,1,1]],[[100,100,700,1500]],[[100,100,700,1500]],None]
                setting._TARGETROI = [[0,0,900,800],[0,0,900,800],[0,0,900,800],None]
                StreetFarm(setting)
            case "[刷图]水路一号街":
                setting._FARMTARGET = 'Dist'
                setting._TARGETLIST = ['chest','harken']
                StreetFarm(setting)
            case "[刷图]土洞(5-9)":
                setting._FARMTARGET = 'DOE'
                setting._TARGETLIST = ['DOEtarget','DOE_quit']
                setting._DUNGWAITTIMEOUT = 0
                StreetFarm(setting)
            case "[刷图]光洞(15-19)":
                setting._FARMTARGET = 'DOL'
                setting._TARGETLIST = ['DOLtarget1','DOLtarget2','DOL_quit']
                setting._DUNGWAITTIMEOUT = 0
                StreetFarm(setting)
            case "[刷图]火洞(10-14)":
                setting._FARMTARGET = 'DOF'
                setting._TARGETLIST = ['DOFtarget1','DOFtarget2','DOF_quit']
                setting._DUNGWAITTIMEOUT = 0
                StreetFarm(setting)
            case "[刷图]卢比肯的洞窟":
                setting._FARMTARGET = 'LBC'
                setting._TARGETLIST = ['chest','LBC_quit']
                StreetFarm(setting)
            case "[任务]7000G":
                setting._FARMTARGET = '7000G'
                QuestFarm(setting)
            case "[刷图]鸟洞三层 fordraig B3F":
                setting._FARMTARGET = 'fordraig-B3F'
                setting._TARGETLIST = ['chest','harken']
                setting._TARGETSEARCHDIR = [None,[[100,1200,700,100],[700,800,100,800],[400,100,400,1200],[100,800,700,800],[400,1200,400,100],]]
                StreetFarm(setting)
            case "[任务]角鹫之剑 fordraig":
                setting._FARMTARGET = 'fordraig'
                QuestFarm(setting)
            case "[任务]击退敌势力":
                setting._FARMTARGET = 'repelEnemyForces'
                QuestFarm(setting)
            case _:
                logger.info(f"无效的任务名:{self.farm_target_var.get()}")
                self.finishingcallback()
                

        
        # self.continue_btn.grid()
        # self.continue_trigger.clear()
        # print('wait!')
        # self.continue_trigger.wait()
        # print("got!")

if __name__ == '__main__':
    root = tk.Tk()
    app = ConfigPanelApp(root)
    root.mainloop()