import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import os
import logging
from script import *
from auto_updater import *
from utils import *

############################################
class ScrollableFrame(ttk.Frame):
    def __init__(self, container, height=None, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        
        # 接收 height 参数并传递给 Canvas
        # 注意: height 单位是像素
        self.canvas = tk.Canvas(self, height=height, borderwidth=0, highlightthickness=0)
        
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        self.scrollable_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    # ... (其余方法 _on_frame_configure, _on_canvas_configure, _check_scroll_necessity, _on_mousewheel 保持不变) ...
    def _on_frame_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._check_scroll_necessity()

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_frame, width=event.width)
        self._check_scroll_necessity()

    def _check_scroll_necessity(self):
        canvas_height = self.canvas.winfo_height()
        content_height = self.scrollable_frame.winfo_reqheight()
        if content_height <= canvas_height:
            self.canvas.yview_moveto(0)
        else:
            self.scrollbar.pack(side="right", fill="y")

    def _on_mousewheel(self, event):
        canvas_height = self.canvas.winfo_height()
        content_height = self.scrollable_frame.winfo_reqheight()
        if content_height > canvas_height:
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

class CollapsibleSection(ttk.Frame):
    def __init__(self, parent, title="", expanded=False, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.columnconfigure(0, weight=1)
        
        # 1. 接收外部传入的状态
        self.is_expanded = expanded
        
        # 顶部标题栏
        self.header_frame = ttk.Frame(self, style="Header.TFrame")
        self.header_frame.pack(fill="x", pady=2)
        
        self.label = ttk.Label(self.header_frame, text=title, font=("微软雅黑", 11, "bold"))
        self.label.pack(side="left", padx=5)
        
        # 2. 根据初始状态决定图标
        icon_text = "❌" if self.is_expanded else "➕"
        self.toggle_btn = ttk.Button(self.header_frame, text=icon_text, width=3, command=self.toggle)
        self.toggle_btn.pack(side="right", padx=5)
        
        self.content_frame = ttk.Frame(self)
        self.spacer = ttk.Frame(self, height=5)
        self.spacer.pack(fill='x')

        # 3. 如果初始是展开的，立即显示内容
        if self.is_expanded:
            self.content_frame.pack(fill="x", expand=True, padx=5, pady=2, before=self.spacer)

    def toggle(self):
        if self.is_expanded:
            self.content_frame.pack_forget()
            self.toggle_btn.configure(text="➕")
            self.is_expanded = False
        else:
            self.content_frame.pack(fill="x", expand=True, padx=5, pady=2, before=self.spacer)
            self.toggle_btn.configure(text="❌")
            self.is_expanded = True

    def toggle(self):
        if self.is_expanded:
            # 当前是展开的 -> 执行折叠
            self.content_frame.pack_forget()     # 隐藏内容
            self.toggle_btn.configure(text="➕")  # 按钮变回"折叠态"图标
            self.is_expanded = False
        else:
            # 当前是折叠的 -> 执行展开
            # 注意: before=self.spacer 保证内容在底部分隔线之上
            self.content_frame.pack(fill="x", expand=True, padx=5, pady=2, before=self.spacer)
            self.toggle_btn.configure(text="❌")  # 按钮变为"展开态"图标
            self.is_expanded = True

############################################
class ConfigPanelApp(tk.Toplevel):
    def __init__(self, master_controller, version, msg_queue):
        self.URL = "https://github.com/arnold2957/wvd"
        self.TITLE = f"WvDAS 巫术daphne自动刷怪 v{version} @德德Dellyla(B站)"
        self.INTRODUCTION = f"遇到问题? 请访问:\n{self.URL} \n或加入Q群: 922497356."

        RegisterQueueHandler()
        StartLogListener()

        super().__init__(master_controller)
        self.controller = master_controller
        self.msg_queue = msg_queue
        self.geometry('560x750')
        
        self.title(self.TITLE)

        self.adb_active = False

        # 关闭时退出整个程序
        self.protocol("WM_DELETE_WINDOW", self.controller.destroy)

        # --- 任务状态 ---
        self.quest_active = False

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
        

        logger.info("**********************************")
        logger.info(f"当前版本: {version}")
        logger.info(self.INTRODUCTION, extra={"summary": True})
        logger.info("**********************************")
        
        if self.last_version.get() != version:
            ShowChangesLogWindow()
            self.last_version.set(version)
            self.save_config()

    def save_config(self):
        def standardize_karma_input():
          if self.karma_adjust_var.get().isdigit():
              valuestr = self.karma_adjust_var.get()
              self.karma_adjust_var.set('+' + valuestr)
        standardize_karma_input()

        emu_path = self.emu_path_var.get()
        emu_path = emu_path.replace("HD-Adb.exe", "HD-Player.exe")
        self.emu_path_var.set(emu_path)

        for attr_name, var_type, var_config_name, _ in CONFIG_VAR_LIST:
            if issubclass(var_type, tk.Variable):
                self.config[var_config_name] = getattr(self, attr_name).get()
        if self.system_auto_combat_var.get():
            self.config["_SPELLSKILLCONFIG"] = []
        else:
            self.config["_SPELLSKILLCONFIG"] = [s for s in ALL_SKILLS if s in list(set(self._spell_skill_config_internal))]

        if self.farm_target_text_var.get() in DUNGEON_TARGETS:
            self.farm_target_var.set(DUNGEON_TARGETS[self.farm_target_text_var.get()])
        else:
            self.farm_target_var.set(None)
        
        SaveConfigToFile(self.config)

    def updata_config(self):
        config = LoadConfigFromFile()
        if '_KARMAADJUST' in config:
            self.karma_adjust_var.set(config['_KARMAADJUST'])

    def create_widgets(self):
        scrolled_text_formatter = logging.Formatter('%(message)s')
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

        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.main_frame.rowconfigure(0, weight=1) 
        self.main_frame.columnconfigure(0, weight=1)

        self.scroll_view = ScrollableFrame(self.main_frame, height=620)
        self.scroll_view.grid(row=0, column=0, sticky="nsew")
        content_root = self.scroll_view.scrollable_frame

        # ==========================================
        # 分组 1: 基础设置 & 模拟器
        # ==========================================
        self.section_emu = CollapsibleSection(content_root, title="模拟器", expanded= False if self.emu_path_var.get() else True,)
        self.section_emu.pack(fill="x", pady=(0, 5)) # 使用pack垂直堆叠
        
        # 获取折叠板的内容容器
        container = self.section_emu.content_frame 

        # --- 原有逻辑 (微调父容器为 container) ---
        row_counter = 0 
        frame_row = ttk.Frame(container)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=2)
        
        self.adb_status_label = ttk.Label(frame_row)
        self.adb_status_label.grid(row=0, column=0)
        
        adb_entry = ttk.Entry(frame_row, textvariable=self.emu_path_var)
        adb_entry.grid_remove()
        
        def selectADB_PATH():
            path = filedialog.askopenfilename(
                title="选择ADB执行文件",
                filetypes=[("Executable", "*.exe"), ("All files", "*.*")]
            )
            if path:
                self.emu_path_var.set(path)
                self.save_config()

        self.adb_path_change_button = ttk.Button(
            frame_row, text="修改", command=selectADB_PATH, width=5
        )
        self.adb_path_change_button.grid(row=0, column=1)
        
        def update_adb_status(*args):
            if self.emu_path_var.get():
                self.adb_status_label.config(text="已设置模拟器", foreground="green")
            else:
                self.adb_status_label.config(text="未设置模拟器", foreground="red")
        
        self.emu_path_var.trace_add("write", lambda *args: update_adb_status())
        update_adb_status()

        # 端口和编号
        row_counter += 1
        frame_row = ttk.Frame(container)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=2)
        ttk.Label(frame_row, text="端口:").grid(row=0, column=2, sticky=tk.W, pady=5)
        vcmd_non_neg = self.register(lambda x: ((x=="")or(x.isdigit())))
        self.adb_port_entry = ttk.Entry(frame_row, textvariable=self.adb_port_var, validate="key",
                                        validatecommand=(vcmd_non_neg, '%P'), width=7)
        self.adb_port_entry.grid(row=0, column=3)
        ttk.Label(frame_row, text=" 编号:").grid(row=0, column=4, sticky=tk.W, pady=5)
        self.emu_index_entry = ttk.Entry(frame_row, textvariable=self.emu_index_var, validate="key",
                                         validatecommand=(vcmd_non_neg, '%P'), width=5)
        self.emu_index_entry.grid(row=0, column=5)
        self.button_save_adb_port = ttk.Button(frame_row, text="保存", command=self.save_config, width=5)
        self.button_save_adb_port.grid(row=0, column=6)


        # ==========================================
        # 分组 2: 目标
        # ==========================================
        self.section_farm = CollapsibleSection(content_root, title="目标",expanded=True)
        self.section_farm.pack(fill="x", pady=5)
        container = self.section_farm.content_frame
        row_counter = 0

        # 地下城目标
        frame_row = ttk.Frame(container)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=2)
        ttk.Label(frame_row, text="任务目标:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.farm_target_combo = ttk.Combobox(frame_row, textvariable=self.farm_target_text_var, 
                                              values=list(DUNGEON_TARGETS.keys()), state="readonly")
        self.farm_target_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)
        self.farm_target_combo.bind("<<ComboboxSelected>>", lambda e: self.save_config())


        # ==========================================
        # 分组 3: 探索
        # ==========================================
        self.section_karma = CollapsibleSection(content_root, title="探索")
        self.section_karma.pack(fill="x", pady=5)
        container = self.section_karma.content_frame
        row_counter = 0

        # 开箱设置
        row_counter += 1
        frame_row = ttk.Frame(container)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=2)
        self.random_chest_check = ttk.Checkbutton(frame_row, text="快速开箱", variable=self.randomly_open_chest_var,
                                                  command=self.save_config, style="Custom.TCheckbutton")
        self.random_chest_check.grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Label(frame_row, text="| 开箱人选:").grid(row=0, column=1, sticky=tk.W, pady=5)
        
        self.open_chest_mapping = {0:"随机", 1:"左上", 2:"中上", 3:"右上", 4:"左下", 5:"中下", 6:"右下"}
        self.who_will_open_text_var = tk.StringVar(value=self.open_chest_mapping.get(self.who_will_open_it_var.get(), "随机"))
        self.who_will_open_combobox = ttk.Combobox(frame_row, textvariable=self.who_will_open_text_var, 
                                                   values=list(self.open_chest_mapping.values()), state="readonly", width=4)
        self.who_will_open_combobox.grid(row=0, column=2, sticky=tk.W, pady=5)
        
        def handle_open_chest_selection(event=None):
            open_chest_reverse_mapping = {v: k for k, v in self.open_chest_mapping.items()}
            self.who_will_open_it_var.set(open_chest_reverse_mapping[self.who_will_open_text_var.get()])
            self.save_config()
        self.who_will_open_combobox.bind("<<ComboboxSelected>>", handle_open_chest_selection)

        # 跳过恢复
        row_counter += 1
        row_recover = tk.Frame(container)
        row_recover.grid(row=row_counter, column=0, columnspan=2, sticky=tk.W, pady=2)
        self.skip_recover_check = ttk.Checkbutton(row_recover, text="跳过战后恢复", variable=self.skip_recover_var,
                                                  command=self.save_config, style="Custom.TCheckbutton")
        self.skip_recover_check.grid(row=0, column=0)
        self.skip_chest_recover_check = ttk.Checkbutton(row_recover, text="跳过开箱后恢复", variable=self.skip_chest_recover_var,
                                                        command=self.save_config, style="Custom.TCheckbutton")
        self.skip_chest_recover_check.grid(row=0, column=1)

        # 休息设置
        row_counter += 1
        frame_row = ttk.Frame(container)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=2)
        def checkcommand():
            self.update_active_rest_state()
            self.save_config()
        self.active_rest_check = ttk.Checkbutton(frame_row, variable=self.active_rest_var, text="启用旅店休息",
                                                 command=checkcommand, style="Custom.TCheckbutton")
        self.active_rest_check.grid(row=0, column=0)
        ttk.Label(frame_row, text=" | 间隔:").grid(row=0, column=1, sticky=tk.W, pady=5)
        self.rest_intervel_entry = ttk.Entry(frame_row, textvariable=self.rest_intervel_var, validate="key",
                                             validatecommand=(vcmd_non_neg, '%P'), width=5)
        self.rest_intervel_entry.grid(row=0, column=2)
        self.button_save_rest_intervel = ttk.Button(frame_row, text="保存", command=self.save_config, width=4)
        self.button_save_rest_intervel.grid(row=0, column=3)

        frame_row = ttk.Frame(container)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=2)
        ttk.Label(frame_row, text=f"善恶:").grid(row=0, column=0, sticky=tk.W, pady=5)
        
        # 善恶值逻辑保持不变
        self.karma_adjust_mapping = {"维持现状": "+0", "恶→中立,中立→善": "+17", "善→中立,中立→恶": "-17"}
        times = int(self.karma_adjust_var.get())
        if times == 0: self.karma_adjust_text_var = tk.StringVar(value="维持现状")
        elif times > 0: self.karma_adjust_text_var = tk.StringVar(value="恶→中立,中立→善")
        elif times < 0: self.karma_adjust_text_var = tk.StringVar(value="善→中立,中立→恶")
            
        self.karma_adjust_combobox = ttk.Combobox(frame_row, textvariable=self.karma_adjust_text_var,
                                                  values=list(self.karma_adjust_mapping.keys()), state="readonly", width=14)
        self.karma_adjust_combobox.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        def handle_karma_adjust_selection(event=None):
            karma_adjust_left = int(self.karma_adjust_var.get())
            karma_adjust_want = int(self.karma_adjust_mapping[self.karma_adjust_text_var.get()])
            if (karma_adjust_left == 0 and karma_adjust_want == 0) or (karma_adjust_left*karma_adjust_want > 0):
                return
            self.karma_adjust_var.set(self.karma_adjust_mapping[self.karma_adjust_text_var.get()])
            self.save_config()
        self.karma_adjust_combobox.bind("<<ComboboxSelected>>", handle_karma_adjust_selection)
        
        ttk.Label(frame_row, text="还需").grid(row=0, column=2, sticky=tk.W, pady=5)
        ttk.Label(frame_row, textvariable=self.karma_adjust_var).grid(row=0, column=3, sticky=tk.W, pady=5)
        ttk.Label(frame_row, text="点").grid(row=0, column=4, sticky=tk.W, pady=5)


        # ==========================================
        # 分组 4: 战斗
        # ==========================================
        self.section_combat = CollapsibleSection(content_root, title="战斗")
        self.section_combat.pack(fill="x", pady=5)
        container = self.section_combat.content_frame
        row_counter = 0

        # 自动战斗
        self.system_auto_check = ttk.Checkbutton(container, text="启用自动战斗", variable=self.system_auto_combat_var,
                                                 command=self.update_system_auto_combat, style="LargeFont.TCheckbutton")
        self.system_auto_check.grid(row=row_counter, column=0, columnspan=2, sticky=tk.W, pady=5)

        # 仅释放一次AOE
        row_counter += 1
        def aoe_once_command():
            if self.aoe_once_var.get():
                if self.btn_enable_full_aoe_var.get() != True: self.btn_enable_full_aoe.invoke()
                if self.btn_enable_secret_aoe_var.get() != True: self.btn_enable_secret_aoe.invoke()
            self.update_change_aoe_once_check()
            self.save_config()
            
        frame_row = ttk.Frame(container)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=2)
        self.aoe_once_check = ttk.Checkbutton(frame_row, text="一场战斗中仅释放", variable=self.aoe_once_var,
                                              command=aoe_once_command, style="BoldFont.TCheckbutton")
        self.aoe_once_check.grid(row=0, column=0)
        self.aoe_custom_time_entry = ttk.Entry(frame_row, textvariable=self.custom_aoe_time_var, validate="key",
                                               validatecommand=(vcmd_non_neg,'%P'), width=1)
        self.aoe_custom_time_entry.grid(row=0, column=1)
        self.aoe_custom_time_label = ttk.Label(frame_row, text="次AOE.", font=("微软雅黑", 9, "bold"))
        self.aoe_custom_time_label.grid(row=0, column=2)
        self.button_save_custom_aoe = ttk.Button(frame_row, text="保存", command=self.save_config, width=4)
        self.button_save_custom_aoe.grid(row=0, column=3)

        # AOE后自动
        row_counter += 1
        self.auto_after_aoe_check = ttk.Checkbutton(container, text="全体AOE后开启自动战斗", variable=self.auto_after_aoe_var,
                                                    command=self.save_config, style="BoldFont.TCheckbutton")
        self.auto_after_aoe_check.grid(row=row_counter, column=0, columnspan=2, sticky=tk.W, pady=5)

        # 技能按钮
        row_counter += 1
        self.skills_button_frame = ttk.Frame(container)
        self.skills_button_frame.grid(row=row_counter, column=0, columnspan=2, sticky=tk.W)
        
        for buttonName, buttonText, buttonSpell, s_row, s_col in SPELLSEKILL_TABLE:
            setattr(self, buttonName, ttk.Checkbutton(
                self.skills_button_frame,
                text=f"启用{buttonText}",
                variable=getattr(self, f"{buttonName}_var"),
                command=lambda spell=buttonSpell, btnN=buttonName, btnT=buttonText: self.update_spell_config(spell, btnN, btnT),
                style="Custom.TCheckbutton"
            ))
            getattr(self, buttonName).grid(row=s_row, column=s_col, padx=2, pady=2)

        # ==========================================
        # 分组 5: 高级
        # ==========================================
        self.section_advanced = CollapsibleSection(content_root, title="高级")
        self.section_advanced.pack(fill="x", pady=5)
        
        # 获取容器
        container = self.section_advanced.content_frame
        row_counter = 0

        # 1. 自动要钱
        frame_row = ttk.Frame(container)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=2)
        self.active_beg_money = ttk.Checkbutton(
            frame_row,
            variable=self.active_beg_money_var,
            text="没有火的时候自动找王女要钱",
            command=self.save_config, # 如果这里需要特定逻辑，可以改回 checkcommand
            style="Custom.TCheckbutton"
        )
        self.active_beg_money.grid(row=0, column=0, sticky=tk.W)

        # 2. 豪华房
        row_counter += 1
        frame_row = ttk.Frame(container)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=2)
        self.active_royalsuite_rest = ttk.Checkbutton(
            frame_row,
            variable=self.active_royalsuite_rest_var,
            text="住豪华房",
            command=self.save_config,
            style="Custom.TCheckbutton"
        )
        self.active_royalsuite_rest.grid(row=0, column=0, sticky=tk.W)

        # 3. 凯旋
        row_counter += 1
        frame_row = ttk.Frame(container)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=2)
        self.active_triumph = ttk.Checkbutton(
            frame_row,
            variable=self.active_triumph_var,
            text="跳跃到\"凯旋\"",
            command=self.save_config,
            style="Custom.TCheckbutton"
        )
        self.active_triumph.grid(row=0, column=0, sticky=tk.W)

        # 3. 第四章
        row_counter += 1
        frame_row = ttk.Frame(container)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=2)
        self.active_beautiful_ore = ttk.Checkbutton(
            frame_row,
            variable=self.active_beautiful_ore_var,
            text="跳跃到\"美丽矿石的真相\"",
            command=self.save_config,
            style="Custom.TCheckbutton"
        )
        self.active_beautiful_ore.grid(row=0, column=0, sticky=tk.W)

        # 4. 因果调整
        row_counter += 1
        frame_row = ttk.Frame(container)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=2)
        self.active_csc = ttk.Checkbutton(
            frame_row,
            variable=self.active_csc_var,
            text="尝试调整因果",
            command=self.save_config,
            style="Custom.TCheckbutton"
        )
        self.active_csc.grid(row=0, column=0, sticky=tk.W)
        
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
        self.update_sep = ttk.Separator(self.main_frame, orient='horizontal')
        self.update_sep.grid(row=row_counter, column=0, columnspan=3, sticky='ew', pady=10)

        #更新按钮
        row_counter += 1
        frame_row_update = tk.Frame(self.main_frame)
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
            url = os.path.join(self.URL, "releases")
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
            self.button_save_custom_aoe.config(state="disable")
            self.aoe_custom_time_entry.config(state="disable")
            self.aoe_custom_time_label.config(state="disable")
        if self.aoe_once_var.get():
            self.auto_after_aoe_check.config(state="normal")
            self.button_save_custom_aoe.config(state="normal")
            self.aoe_custom_time_entry.config(state="normal")
            self.aoe_custom_time_label.config(state="normal")

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
        self.button_save_custom_aoe.config(state=button_state)
        self.aoe_custom_time_entry.config(state=button_state)
        self.aoe_custom_time_label.config(state=button_state)
        if is_system_auto:
            self.auto_after_aoe_check.config(state = button_state)
        else:
            self.update_change_aoe_once_check()
        
        # 更新按钮颜色并保存
        self.save_config()

    def update_spell_config(self, skills_to_process, buttonName, buttonText):
        if self.system_auto_combat_var.get():
            return

        skills_to_process_set = set(skills_to_process)

        if buttonName == "btn_enable_all":
            if getattr(self,f"{buttonName}_var").get():
                self._spell_skill_config_internal = sorted(list(skills_to_process_set))
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
            self.button_save_custom_aoe,
            self.aoe_custom_time_entry,
            self.aoe_custom_time_label,
            self.auto_after_aoe_check,
            self.skip_recover_check,
            self.skip_chest_recover_check,
            self.active_rest_check,
            self.rest_intervel_entry,
            self.button_save_rest_intervel,
            self.karma_adjust_combobox,
            self.adb_port_entry,
            self.emu_index_entry,
            self.active_triumph,
            self.active_beautiful_ore,
            self.active_royalsuite_rest,
            self.active_beg_money,
            self.button_save_adb_port,
            self.active_csc
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
        if not self.quest_active:
            self.start_stop_btn.config(text="停止")
            self.set_controls_state(tk.DISABLED)
            setting = FarmConfig()
            config = LoadConfigFromFile()
            for attr_name, var_type, var_config_name, var_default_value in CONFIG_VAR_LIST:
                setattr(setting, var_config_name, config[var_config_name])
            setting._FINISHINGCALLBACK = self.finishingcallback
            self.msg_queue.put(('start_quest', setting))
            self.quest_active = True
        else:
            self.msg_queue.put(('stop_quest', None))

    def finishingcallback(self):
        logger.info("已停止.")
        self.start_stop_btn.config(text="脚本, 启动!")
        self.set_controls_state(tk.NORMAL)
        self.updata_config()
        self.quest_active = False

    def turn_to_7000G(self):
        self.summary_log_display.config(bg="#F4C6DB" )
        self.main_frame.grid_remove()
        summary = self.summary_log_display.get("1.0", "end-1c")
        if self.INTRODUCTION in summary:
            summary = "唔, 看起来一次成功的地下城都没有完成."
        text = f"你的队伍已经耗尽了所有的再起之火.\n在耗尽再起之火前,\n你的队伍已经完成了如下了不起的壮举:\n\n{summary}\n\n不过没关系, 至少, 你还可以找公主要钱.\n\n赞美公主殿下!\n"
        turn_to_7000G_label = ttk.Label(self, text = text)
        turn_to_7000G_label.grid(row=0, column=0,)