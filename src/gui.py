import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import os
import logging
from script import *
from auto_updater import *
from utils import *
from threading import Thread,Event
import shutil

__version__ = '1.4.7-beta3'

OWNER = "arnold2957"
REPO = "wvd"

TITLE = f"WvDAS 巫术daphne自动刷怪 v{__version__} @德德Dellyla(B站)"
INTRODUCTION = "遇到问题? 请访问:\nhttps://github.com/arnold2957/wvd \n或加入Q群: 922497356."

############################################
RESTART_SCREENSHOT_FOLDER_NAME = "screenshotwhenrestart"
if os.path.exists(RESTART_SCREENSHOT_FOLDER_NAME):
    shutil.rmtree(RESTART_SCREENSHOT_FOLDER_NAME)
os.makedirs(RESTART_SCREENSHOT_FOLDER_NAME, exist_ok=True)
############################################
class ConfigPanelApp(tk.Toplevel):
    def __init__(self, master_controller):
        super().__init__(master_controller)
        self.controller = master_controller
        self.geometry('550x608')
        # self.root.resizable(False, False)
        self.title(TITLE)

        self.adb_active = False

        # 关闭时退出整个程序
        self.protocol("WM_DELETE_WINDOW", self.controller.destroy)

        # --- 后台线程 ---
        self.thread = None
        self.stop_event = Event()

        # --- ttk Style ---
        #
        self.style = ttk.Style()
        self.style.configure("custom.TCheckbutton")
        self.style.map("Custom.TCheckbutton",
            foreground=[("disabled selected", "#8CB7DF"),("disabled", "#A0A0A0"), ("selected", "#196FBF")])
        self.style.configure("BoldFont.TCheckbutton", font=("微软雅黑", 9,"bold"))
        self.style.configure("LargeFont.TCheckbutton", font=("微软雅黑", 12,"bold"))

        # --- UI 变量 ---
        self.config = LoadConfigFromFile()
        for attr_name, var_type, var_config_name, var_default_value in CONFIG_VAR_LIST:
            if issubclass(var_type, tk.Variable):
                setattr(self, attr_name, var_type(value = self.config.get(var_config_name,var_default_value)))
            else:
                setattr(self, attr_name, var_type(self.config.get(var_config_name,var_default_value)))
        
        for btn,_,spellskillList,_,_ in SPELLSEKILL_TABLE:
            for item in spellskillList:
                if item not in self._spell_skill_config_internal:
                    setattr(self,f"{btn}_var",tk.BooleanVar(value = False))
                    break
                setattr(self,f"{btn}_var",tk.BooleanVar(value = True))             

        self.create_widgets()
        self.update_system_auto_combat()
        self.update_active_rest_state() # 初始化时更新旅店住宿entry.
        self.update_change_aoe_once_check() #

        logger.info("**********************************")
        logger.info(f"当前版本: {__version__}")
        logger.info(INTRODUCTION, extra={"summary": True})
        logger.info("**********************************")
        
        if self.last_version.get() != __version__:
            ShowChangesLogWindow()
            self.last_version.set(__version__)
            self.save_config()

    def save_config(self):
        def standardize_karma_input():
          if self.karma_adjust_var.get().isdigit():
              valuestr = self.karma_adjust_var.get()
              self.karma_adjust_var.set('+' + valuestr)
        standardize_karma_input()

        for attr_name, var_type, var_config_name, _ in CONFIG_VAR_LIST:
            if issubclass(var_type, tk.Variable):
                self.config[var_config_name] = getattr(self, attr_name).get()
        if self.system_auto_combat_var.get():
            self.config["_SPELLSKILLCONFIG"] = []
        else:
            self.config["_SPELLSKILLCONFIG"] = [s for s in ALL_SKILLS if s in list(set(self._spell_skill_config_internal))]

        self.farm_target_var.set(DUNGEON_TARGETS[self.farm_target_text_var.get()])
        
        SaveConfigToFile(self.config)

    def updata_config(self):
        config = LoadConfigFromFile()
        if '_KARMAADJUST' in config:
            self.karma_adjust_var.set(config['_KARMAADJUST'])

    def create_widgets(self):
        self.log_display = scrolledtext.ScrolledText(self, wrap=tk.WORD, state=tk.DISABLED, bg='#ffffff',bd=2,relief=tk.FLAT, width = 34, height = 30)
        self.log_display.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.scrolled_text_handler = ScrolledTextHandler(self.log_display)
        self.scrolled_text_handler.setLevel(logging.INFO)
        self.scrolled_text_handler.setFormatter(scrolled_text_formatter)
        logger.addHandler(self.scrolled_text_handler)


        self.summary_log_display = scrolledtext.ScrolledText(self, wrap=tk.WORD, state=tk.DISABLED, bg="#C6DBF4",bd=2, width = 34, )
        self.summary_log_display.grid(row=1, column=1, pady=5)
        self.summary_text_handler = ScrolledTextHandler(self.summary_log_display)
        self.summary_text_handler.setLevel(logging.INFO)
        self.summary_text_handler.setFormatter(scrolled_text_formatter)
        self.summary_text_handler.addFilter(SummaryLogFilter())
        original_emit = self.summary_text_handler.emit
        def new_emit(record):
            self.summary_log_display.configure(state='normal')
            self.summary_log_display.delete(1.0, tk.END)
            self.summary_log_display.configure(state='disabled')
            original_emit(record)
        self.summary_text_handler.emit = new_emit
        logger.addHandler(self.summary_text_handler)

        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        #设定adb
        row_counter = 0
        frame_row0 = ttk.Frame(main_frame)
        frame_row0.grid(row=row_counter, column=0, sticky="ew", pady=5)  # 首行框架
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
        vcmd_non_neg = self.register(lambda x: ((x=="")or(x.isdigit())))
        self.adb_port_entry = ttk.Entry(frame_row0,
                                        textvariable=self.adb_port_var,
                                        validate="key",
                                        validatecommand=(vcmd_non_neg, '%P'),
                                        width=5)
        self.adb_port_entry.grid(row=0, column=3)
        self.button_save_adb_port = ttk.Button(
            frame_row0,
            text="保存",
            command = self.save_config,
            width=5
            )
        self.button_save_adb_port.grid(row=0, column=4)

        # 分割线.
        row_counter += 1
        ttk.Separator(main_frame, orient='horizontal').grid(row=row_counter, column=0, columnspan=3, sticky='ew', pady=10)

        # 地下城目标
        row_counter += 1
        frame_row2 = ttk.Frame(main_frame)
        frame_row2.grid(row=row_counter, column=0, sticky="ew", pady=5)  # 第二行框架
        ttk.Label(frame_row2, text="地下城目标:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.farm_target_combo = ttk.Combobox(frame_row2, textvariable=self.farm_target_text_var, values=list(DUNGEON_TARGETS.keys()), state="readonly")
        self.farm_target_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)
        self.farm_target_combo.bind("<<ComboboxSelected>>", lambda e: self.save_config())

        # 开箱子设置
        row_counter += 1
        frame_row3 = ttk.Frame(main_frame)
        frame_row3.grid(row=row_counter, column=0, sticky="ew", pady=5)  # 第二行框架
        self.random_chest_check = ttk.Checkbutton(
            frame_row3,
            text="智能开箱(测试版)",
            variable=self.randomly_open_chest_var,
            command=self.save_config,
            style="Custom.TCheckbutton"
        )
        self.random_chest_check.grid(row=0, column=0,  sticky=tk.W, pady=5)
        ttk.Label(frame_row3, text="| 开箱人选:").grid(row=0, column=1, sticky=tk.W, pady=5)
        self.open_chest_mapping = {
            0:"随机",
            1:"左上",
            2:"中上",
            3:"右上",
            4:"左下",
            5:"中下",
            6:"右下",
        }
        self.who_will_open_text_var = tk.StringVar(value=self.open_chest_mapping[self.who_will_open_it_var.get()])
        self.who_will_open_combobox = ttk.Combobox(
            frame_row3,
            textvariable=self.who_will_open_text_var,  # 绑定变量
            values=list(self.open_chest_mapping.values()),  # 使用中文选项
            state="readonly",  # 设置为只读（只能选择）
            width=4
        )
        self.who_will_open_combobox.grid(row=0, column=2, sticky=tk.W, pady=5)
        def handle_open_chest_selection(event = None):
            open_chest_reverse_mapping = {v: k for k, v in self.open_chest_mapping.items()}
            self.who_will_open_it_var.set(open_chest_reverse_mapping[self.who_will_open_text_var.get()])
            self.save_config()
        self.who_will_open_combobox.bind("<<ComboboxSelected>>", handle_open_chest_selection)

        # 跳过恢复
        row_counter += 1
        row_recover = tk.Frame(main_frame)
        row_recover.grid(row = row_counter,column=0, columnspan=2, sticky=tk.W, pady=5)
        self.skip_recover_check = ttk.Checkbutton(
            row_recover,
            text="跳过战后恢复",
            variable=self.skip_recover_var,
            command=self.save_config,
            style="Custom.TCheckbutton"
        )
        self.skip_recover_check.grid(row=0, column=0)
        self.skip_chest_recover_check = ttk.Checkbutton(
            row_recover,
            text="跳过开箱后恢复",
            variable=self.skip_chest_recover_var,
            command=self.save_config,
            style="Custom.TCheckbutton"
        )
        self.skip_chest_recover_check.grid(row=0, column=1)

        # 休息设置
        row_counter += 1
        frame_row5 = ttk.Frame(main_frame)
        frame_row5.grid(row=row_counter, column=0, sticky="ew", pady=5)

        def checkcommand():
            self.update_active_rest_state()
            self.save_config()
        self.active_rest_check = ttk.Checkbutton(
            frame_row5,
            variable=self.active_rest_var,
            text="启用旅店休息",
            command=checkcommand,
            style="Custom.TCheckbutton"
            )
        self.active_rest_check.grid(row=0, column=0)
        ttk.Label(frame_row5, text=" | 间隔:").grid(row=0, column=1, sticky=tk.W, pady=5)
        self.rest_intervel_entry = ttk.Entry(frame_row5,
                                             textvariable=self.rest_intervel_var,
                                             validate="key",
                                             validatecommand=(vcmd_non_neg, '%P'),
                                             width=5)
        self.rest_intervel_entry.grid(row=0, column=2)
        self.button_save_rest_intervel = ttk.Button(
            frame_row5,
            text="保存",
            command = self.save_config,
            width=4
            )
        self.button_save_rest_intervel.grid(row=0, column=3)

        # 善恶设置
        row_counter += 1
        frame_row6 = ttk.Frame(main_frame)
        frame_row6.grid(row=row_counter, column=0, sticky="ew", pady=5)
        ttk.Label(frame_row6, text=f"善恶:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.karma_adjust_mapping = {
            "维持现状": "+0",
            "恶→中立,中立→善": "+17",
            "善→中立,中立→恶": "-17",
            }
        times = int(self.karma_adjust_var.get())
        if times == 0:
            self.karma_adjust_text_var = tk.StringVar(value = "维持现状")
        elif times > 0:
            self.karma_adjust_text_var = tk.StringVar(value = "恶→中立,中立→善")
        elif times < 0:
            self.karma_adjust_text_var = tk.StringVar(value = "善→中立,中立→恶")
        self.karma_adjust_combobox = ttk.Combobox(
            frame_row6,
            textvariable=self.karma_adjust_text_var,  # 绑定变量
            values=list(self.karma_adjust_mapping.keys()),  # 使用中文选项
            state="readonly",  # 设置为只读（只能选择）
            width=14
        )
        self.karma_adjust_combobox.grid(row=0, column=1, sticky=tk.W, pady=5)
        def handle_karma_adjust_selection(event = None):
            karma_adjust_left = int(self.karma_adjust_var.get())
            karma_adjust_want = int(self.karma_adjust_mapping[self.karma_adjust_text_var.get()])
            if (karma_adjust_left == 0 and karma_adjust_want == 0) or (karma_adjust_left*karma_adjust_want > 0):
                return
            self.karma_adjust_var.set(self.karma_adjust_mapping[self.karma_adjust_text_var.get()])
            self.save_config()
        self.karma_adjust_combobox.bind("<<ComboboxSelected>>", handle_karma_adjust_selection)
        ttk.Label(frame_row6, text="还需").grid(row=0, column=2, sticky=tk.W, pady=5)
        ttk.Label(frame_row6, textvariable=self.karma_adjust_var).grid(row=0, column=3, sticky=tk.W, pady=5)
        ttk.Label(frame_row6, text="点").grid(row=0, column=4, sticky=tk.W, pady=5)

        # 分割线
        row_counter += 1
        ttk.Separator(main_frame, orient='horizontal').grid(row=row_counter, column=0, columnspan=3, sticky='ew', pady=10)

        # 系统自动战斗
        row_counter += 1
        self.system_auto_check = ttk.Checkbutton(
            main_frame,
            text="启用自动战斗",
            variable=self.system_auto_combat_var,
            command=self.update_system_auto_combat,
            style="LargeFont.TCheckbutton"
        )
        self.system_auto_check.grid(row=row_counter, column=0, columnspan=2, sticky=tk.W, pady=5)

        #仅释放一次aoe
        def aoe_once_command():
            if self.aoe_once_var.get():
                if self.btn_enable_full_aoe_var.get() != True:
                    self.btn_enable_full_aoe.invoke()
                if self.btn_enable_secret_aoe_var.get() != True:
                    self.btn_enable_secret_aoe.invoke()
            self.update_change_aoe_once_check()
            self.save_config()
        row_counter += 1
        self.aoe_once_check = ttk.Checkbutton(
            main_frame,
            text="一场战斗中仅释放一次全体AOE",
            variable=self.aoe_once_var,
            command= aoe_once_command,
            style="BoldFont.TCheckbutton"
        )
        self.aoe_once_check.grid(row=row_counter, column=0, columnspan=2, sticky=tk.W, pady=5)

        #任何aoe后自动战斗
        row_counter += 1
        self.auto_after_aoe_check = ttk.Checkbutton(
            main_frame,
            text="全体AOE后开启自动战斗",
            variable=self.auto_after_aoe_var,
            command= self.save_config,
            style="BoldFont.TCheckbutton"
        )
        self.auto_after_aoe_check.grid(row=row_counter, column=0, columnspan=2, sticky=tk.W, pady=5)

        # 技能按钮框架
        row_counter += 1
        self.skills_button_frame = ttk.Frame(main_frame)
        self.skills_button_frame.grid(row=row_counter, column=0, columnspan=2, sticky=tk.W)
        for buttonName,buttonText,buttonSpell, row, col in SPELLSEKILL_TABLE:
            setattr(self,buttonName,ttk.Checkbutton(
                self.skills_button_frame,
                text=f"启用{buttonText}",
                variable= getattr(self,f"{buttonName}_var"),
                command=lambda spell=buttonSpell, btnN = buttonName,btnT = buttonText:self.update_spell_config(spell,btnN,btnT),
                style="Custom.TCheckbutton"
                )
                )
            getattr(self, buttonName).grid(row=row,column=col,padx=2, pady=2)
        
        # 分割线
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        start_frame = ttk.Frame(self)
        start_frame.grid(row=1, column=0, sticky="nsew")
        start_frame.columnconfigure(0, weight=1)
        start_frame.rowconfigure(1, weight=1)

        ttk.Separator(start_frame, orient='horizontal').grid(row=0, column=0, columnspan=3, sticky="ew", padx=10)

        button_frame = ttk.Frame(start_frame)
        button_frame.grid(row=1, column=0, columnspan=3, pady=5, sticky="nsew")
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        button_frame.columnconfigure(2, weight=1)

        label1 = ttk.Label(button_frame, text="",  anchor='center')
        label1.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

        label3 = ttk.Label(button_frame, text="",  anchor='center')
        label3.grid(row=0, column=2, sticky='nsew', padx=5, pady=5)

        s = ttk.Style()
        s.configure('start.TButton', font=('微软雅黑', 15), padding = (0,5))
        def btn_command():
            self.save_config()
            self.toggle_start_stop()
        self.start_stop_btn = ttk.Button(
            button_frame,
            text="脚本, 启动!",
            command=btn_command,
            style='start.TButton',
        )
        self.start_stop_btn.grid(row=0, column=1, sticky='nsew', padx=5, pady= 26)

        # 分割线
        row_counter += 1
        self.update_sep = ttk.Separator(main_frame, orient='horizontal')
        self.update_sep.grid(row=row_counter, column=0, columnspan=3, sticky='ew', pady=10)

        #更新按钮
        row_counter += 1
        frame_row_update = tk.Frame(main_frame)
        frame_row_update.grid(row=row_counter, column=0, sticky=tk.W)

        self.find_update = ttk.Label(frame_row_update, text="发现新版本:",foreground="red")
        self.find_update.grid(row=0, column=0, sticky=tk.W)

        self.update_text = ttk.Label(frame_row_update, textvariable=self.latest_version,foreground="red")
        self.update_text.grid(row=0, column=1, sticky=tk.W)

        self.button_auto_download = ttk.Button(
            frame_row_update,
            text="自动下载",
            width=7
            )
        self.button_auto_download.grid(row=0, column=2, sticky=tk.W, padx= 5)

        def open_url():
            url = f"https://github.com/{OWNER}/{REPO}/releases"
            if sys.platform == "win32":
                os.startfile(url)
            elif sys.platform == "darwin":
                os.system(f"open {url}")
            else:
                os.system(f"xdg-open {url}")
        self.button_manual_download = ttk.Button(
            frame_row_update,
            text="手动下载最新版",
            command=open_url,
            width=7
            )
        self.button_manual_download.grid(row=0, column=3, sticky=tk.W)

        self.update_sep.grid_remove()
        self.find_update.grid_remove()
        self.update_text.grid_remove()
        self.button_auto_download.grid_remove()
        self.button_manual_download.grid_remove()

    def update_active_rest_state(self):
        if self.active_rest_var.get():
            self.rest_intervel_entry.config(state="normal")
            self.button_save_rest_intervel.config(state="normal")
        else:
            self.rest_intervel_entry.config(state="disable")
            self.button_save_rest_intervel.config(state="disable")

    def update_change_aoe_once_check(self):
        if self.aoe_once_var.get()==False:
            self.auto_after_aoe_var.set(False)
            self.auto_after_aoe_check.config(state="disabled")
        if self.aoe_once_var.get():
            self.auto_after_aoe_check.config(state="normal")

    def update_system_auto_combat(self):
        is_system_auto = self.system_auto_combat_var.get()

        # 更新技能列表
        if is_system_auto:
            self._spell_skill_config_internal = ["systemAuto"]
        else:
            if self._spell_skill_config_internal == ["systemAuto"]:
                self._spell_skill_config_internal = []
                for buttonName,buttonText,buttonSpell, row, col in SPELLSEKILL_TABLE:
                    if getattr(self,f"{buttonName}_var").get():
                        self._spell_skill_config_internal += buttonSpell
        
        # 更新其他按钮信息
        button_state = tk.DISABLED if is_system_auto else tk.NORMAL
        for buttonName,_,_, _, _ in SPELLSEKILL_TABLE:
            getattr(self,buttonName).config(state=button_state)
        self.aoe_once_check.config(state = button_state)
        self.auto_after_aoe_check.config(state = button_state)
        
        # 更新按钮颜色并保存
        self.save_config()

    def update_spell_config(self, skills_to_process, buttonName, buttonText):
        if self.system_auto_combat_var.get():
            return

        skills_to_process_set = set(skills_to_process)

        if buttonName == "btn_enable_all":
            if getattr(self,f"{buttonName}_var").get():
                self._spell_skill_config_internal = list(skills_to_process_set)
                logger.info(f"已启用所有技能: {self._spell_skill_config_internal}")
                for btn,_,_,_,_ in SPELLSEKILL_TABLE:
                    if btn!=buttonName:
                        getattr(self,f"{btn}_var").set(True)
            else:
                self._spell_skill_config_internal = []
                for btn,_,_,_,_ in SPELLSEKILL_TABLE:
                    if btn!=buttonName:
                        getattr(self,f"{btn}_var").set(False)
                logger.info("已取消所有技能。")
        else:
            if getattr(self,f"{buttonName}_var").get():
                for skill in skills_to_process:
                    if skill not in self._spell_skill_config_internal:
                        self._spell_skill_config_internal.append(skill)
                logger.info(f"已启用{buttonText}技能. 当前技能: {self._spell_skill_config_internal}")
            else:
                self._spell_skill_config_internal = [s for s in self._spell_skill_config_internal if s not in skills_to_process_set]
                logger.info(f"已禁用{buttonText}技能. 当前技能: {self._spell_skill_config_internal}")

        # 保证唯一性，但保留顺序
        self._spell_skill_config_internal = list(dict.fromkeys(self._spell_skill_config_internal))

        self.save_config()

    def set_controls_state(self, state):
        self.button_and_entry = [
            self.adb_path_change_button,
            self.random_chest_check,
            self.who_will_open_combobox,
            self.system_auto_check,
            self.aoe_once_check,
            self.auto_after_aoe_check,
            self.skip_recover_check,
            self.skip_chest_recover_check,
            self.active_rest_check,
            self.rest_intervel_entry,
            self.button_save_rest_intervel,
            self.karma_adjust_combobox,
            self.adb_port_entry,
            self.button_save_adb_port,
            ]

        if state == tk.DISABLED:
            self.farm_target_combo.configure(state="disabled")
            for widget in self.button_and_entry:
                widget.configure(state="disabled")
        else:
            self.farm_target_combo.configure(state="readonly")
            for widget in self.button_and_entry:
                widget.configure(state="normal")
            self.update_active_rest_state()
            self.update_change_aoe_once_check()

        if not self.system_auto_combat_var.get():
            widgets = [
                *[getattr(self,buttonName) for buttonName,_,_,_,_ in SPELLSEKILL_TABLE]
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
            self.dungeonLoop()
        else: # self.thread is NOT None
            if self.thread.is_alive():
                logger.info("等待当前步骤执行完毕, 执行完毕后将中断脚本. 这可能需要一些时间...")
                self.stop_event.set()

    def finishingcallback(self):
        logger.info("已中断.")
        self.start_stop_btn.config(text="脚本, 启动!")
        self.set_controls_state(tk.NORMAL)
        self.updata_config()

    def dungeonLoop(self):
        setting = FarmConfig()
        config = LoadConfigFromFile()
        for attr_name, var_type, var_config_name, var_default_value in CONFIG_VAR_LIST:
            setattr(setting, var_config_name, config[var_config_name])
        logger.info(f"目标地下城:{setting._FARMTARGET_TEXT}")

        setting._FINISHINGCALLBACK = self.finishingcallback
        setting._FORCESTOPING = self.stop_event

        Farm = Factory()
        self.thread = Thread(target=Farm,args=(setting,))
        self.thread.start()
             
class AppController(tk.Tk):
    def __init__(self):
        super().__init__()
        # 关键：立即隐藏根窗口
        self.withdraw()
        self.main_window = None
        if not self.main_window:
            self.main_window = ConfigPanelApp(self)

        self.msg_queue = queue.Queue()
        
        self.is_checking_for_update = False 
        self.updater = AutoUpdater(
            msg_queue=self.msg_queue,
            github_user=OWNER,
            github_repo=REPO,
            current_version=__version__
        )
        self.schedule_periodic_update_check()
        self.check_queue()

    def run_in_thread(self, target_func, *args):
        thread = threading.Thread(target=target_func, args=args, daemon=True)
        thread.start()
    def schedule_periodic_update_check(self):
        # 如果当前没有在检查或下载，则启动一个新的检查
        if not self.is_checking_for_update:
            # print("调度器：正在启动一小时一次的后台更新检查...")
            self.is_checking_for_update = True  # 设置标志，防止重复
            self.run_in_thread(self.updater.check_for_updates)
            self.is_checking_for_update = False
        else:
            # print("调度器：上一个检查/下载任务尚未完成，跳过本次检查。")
            None
        self.after(3600000, self.schedule_periodic_update_check)

    def check_queue(self):
        """处理来自AutoUpdater和其他服务的消息"""
        try:
            message = self.msg_queue.get_nowait()
            command, value = message
            
            # --- 这是处理更新逻辑的核心部分 ---
            if command == 'update_available':
                # 在面板上显示提示
                update_data = value
                version = update_data['version']
                
                self.main_window.find_update.grid()
                self.main_window.update_text.grid()
                self.main_window.latest_version.set(version)
                self.main_window.button_auto_download.grid()
                self.main_window.button_manual_download.grid()
                self.main_window.update_sep.grid()
                self.main_window.save_config()
                width, height = map(int, self.main_window.geometry().split('+')[0].split('x'))
                self.main_window.geometry(f'{width}x{height+50}')

                self.main_window.button_auto_download.config(command=lambda:self.run_in_thread(self.updater.download))          
            elif command == 'download_started':
                # 控制器决定创建并显示进度条窗口
                if not hasattr(self, 'progress_window') or not self.progress_window.winfo_exists():
                    self.progress_window = Progressbar(self.main_window,title="下载中...",max_size = value)

            elif command == 'progress':
                # 控制器更新进度条UI
                if hasattr(self, 'progress_window') and self.progress_window.winfo_exists():
                    self.progress_window.update_progress(value)
                    self.update()
                    None

            elif command == 'download_complete':
                # 控制器关闭进度条并显示成功信息
                if hasattr(self, 'progress_window') and self.progress_window.winfo_exists():
                    self.progress_window.destroy()

            elif command == 'error':
                 # 控制器处理错误显示
                if hasattr(self, 'progress_window') and self.progress_window.winfo_exists():
                    self.progress_window.destroy()
                messagebox.showerror("错误", value, parent=self.main_window)

            elif command == 'restart_ready':
                script_path = value
                messagebox.showinfo(
                    "更新完成",
                    "新版本已准备就绪，应用程序即将重启！",
                    parent=self.main_window
                )
                
                if sys.platform == "win32":
                    subprocess.Popen([script_path], shell=True)
                else:
                    os.system(script_path)
                
                self.destroy()
                
            elif command == 'no_update_found':
                # （可选）可以给个安静的提示，或什么都不做
                print("UI: 未发现更新。")

        except queue.Empty:
            pass
        finally:
            # 持续监听
            self.after(100, self.check_queue)

if __name__ == "__main__":
    # 程序的入口点是创建控制器
    controller = AppController()
    # 控制器自己运行事件循环
    controller.mainloop()