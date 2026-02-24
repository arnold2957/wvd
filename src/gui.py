import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox,simpledialog
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

class CollapsibleSection(tk.Frame):
    def __init__(self, parent, title="", expanded=True,bg_color=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.columnconfigure(0, weight=1)
        
        self.is_expanded = expanded
        self.bg_color = bg_color
        self.close_emoji = "➖"
        self.showmore_emoji = "➕"
        self.config(bg=self.bg_color)
        
        # 顶部标题栏
        self.header_frame = tk.Frame(self, bg=self.bg_color)
        self.header_frame.pack(fill="x", pady=2)
        
        self.label = tk.Label(self.header_frame, text=title, font=("微软雅黑", 13, "bold"),bg=self.bg_color)
        self.label.pack(side="left", padx=5)
        
        # 2. 根据初始状态决定图标
        icon_text = self.close_emoji if self.is_expanded else self.showmore_emoji
        self.toggle_btn = ttk.Button(self.header_frame, text=icon_text, width=3, command=self.toggle)
        self.toggle_btn.pack(side="right", padx=5)
        
        self.content_frame = tk.Frame(self, bg=self.bg_color)
        self.spacer = tk.Frame(self, height=5, bg = self.bg_color)
        self.spacer.pack(fill='x')

        # 3. 如果初始是展开的，立即显示内容
        if self.is_expanded:
            self.content_frame.pack(fill="x", expand=True, padx=5, pady=2, before=self.spacer)

    def toggle(self):
        if self.is_expanded:
            self.content_frame.pack_forget()
            self.toggle_btn.configure(text=self.showmore_emoji)
            self.is_expanded = False
        else:
            self.content_frame.pack(fill="x", expand=True, padx=5, pady=2, before=self.spacer)
            self.toggle_btn.configure(text=self.close_emoji)
            self.is_expanded = True

    def toggle(self):
        if self.is_expanded:
            # 当前是展开的 -> 执行折叠
            self.content_frame.pack_forget()     # 隐藏内容
            self.toggle_btn.configure(text=self.showmore_emoji)  # 按钮变回"折叠态"图标
            self.is_expanded = False
        else:
            # 当前是折叠的 -> 执行展开
            # 注意: before=self.spacer 保证内容在底部分隔线之上
            self.content_frame.pack(fill="x", expand=True, padx=5, pady=2, before=self.spacer)
            self.toggle_btn.configure(text=self.close_emoji)  # 按钮变为"展开态"图标
            self.is_expanded = True

class SkillConfigPanel(CollapsibleSection):
    def __init__(self,
                 parent,
                 title="技能配置组",
                 on_delete=None,
                 init_config=None,
                 on_name_change=None,
                 on_config_change = None,
                 **kwargs):
        self.bg_color = "#FFFFFF"
        super().__init__(parent, title=title, expanded=True, bg_color=self.bg_color, **kwargs)
        self.configure(
            relief=tk.GROOVE,
            borderwidth=2,
        )

        self.on_delete = on_delete
        self.on_name_change = on_name_change
        self.on_config_change = on_config_change

        self.custom_rows_data = []
        self.default_row_data = {}
        
        # 常量
        self.ROLE_LIST = ['alice', 'bob', 'camila']
        self.SKILL_OPTIONS = ["左上技能", "右上技能", "左下技能", "右下技能", "防御", "双击自动"]
        self.TARGET_OPTIONS = ["左上", "中上", "右上", "左下", "右下", "中下", "低生命值", "不可用"]
        self.SKILL_LVL = [1, 2, 3, 4, 5, 6, 7]
        self.FREQ_OPTIONS = ["每场战斗仅一次", "每次启动仅一次", "重复"]

        # 用初始化内容构建
        self._setup_body_ui(init_config)
        
    def _setup_body_ui(self,init_config=None):
        # --- 1. 功能按钮 ---
        if init_config!=None and ('group_name' in init_config) and (init_config['group_name']!='全自动战斗'):
            action_bar = tk.Frame(self.content_frame, background=self.bg_color)
            action_bar.pack(fill=tk.X, pady=(0, 5))

            btn_add = ttk.Button(action_bar, text="➕新增角色", command=self.add_custom_row, width=9.5)
            btn_add.pack(side=tk.LEFT)
            
            btn_del = ttk.Button(action_bar, text="🗑删除此组", command=self.delete_panel, width=9.5)
            btn_del.pack(side=tk.RIGHT)

            btn_edit = ttk.Button(action_bar, text="✎重命名", command=self.edit_title, width=7)
            btn_edit.pack(side=tk.RIGHT, padx=(5, 0))

            ttk.Separator(self.content_frame, orient='horizontal').pack(fill='x', pady=2)

        # --- 2. 卡片容器 ---
        self.cards_container = tk.Frame(self.content_frame, background=self.bg_color)
        self.cards_container.pack(fill=tk.BOTH, expand=True)

        # 默认行
        self.default_row_frame = tk.Frame(self.cards_container)
        self.default_row_frame.pack(fill=tk.X)
        self.default_row_data = self._create_card_widget(self.default_row_frame, is_default=True)

        # 初始化内容
        if init_config:
            # 1. 清空已有的自定义行
            for row in self.custom_rows_data:
                row['frame'].destroy()
            self.custom_rows_data.clear()

            # 2. 设置组名
            if 'group_name' in init_config:
                self.label.config(text=init_config['group_name'])
            
            # 3. 创建新的自定义行
            if 'skill_settings' in init_config:
                skill_settings = init_config['skill_settings']
                
                for setting in skill_settings:
                    # 创建新的自定义行
                    wrapper_frame = tk.Frame(self.cards_container)
                    wrapper_frame.pack(fill=tk.X, pady=3, before=self.default_row_frame)
                    row_data = self._create_card_widget(wrapper_frame, is_default=False)
                    self.custom_rows_data.append(row_data)
                    
                    # 设置配置值
                    role = setting.get('role_var', '')
                    if role in self.ROLE_LIST:
                        row_data['role_var'].set(role)
                    else:
                        row_data['role_var'].set(self.ROLE_LIST[0])
                        
                    row_data['skill_var'].set(setting.get('skill_var', '左上技能'))
                    row_data['target_var'].set(setting.get('target_var', '低生命值'))
                    row_data['freq_var'].set(setting.get('freq_var', '重复'))
                    row_data['lvl_var'].set(setting.get('skill_lvl', 1))
                    
                    # 触发技能变更检查
                    self._on_skill_change(row_data)
        return

    # --- 功能实现 ---
    def edit_title(self):
        """修改标题"""
        current_title = self.label.cget("text")
        new_title = simpledialog.askstring("重命名", "修改配置组名称:", initialvalue=current_title, parent=self)
        
        if new_title and new_title != current_title:
            # 如果有回调函数，先调用它
            if self.on_name_change:
                result = self.on_name_change(self, new_title)
                if result is False:  # 如果回调返回False，认为修改失败
                    return
            
            # 修改成功，更新标签
            self.label.config(text=new_title)
            
        if self.on_config_change:
            self.on_config_change()

    def delete_panel(self):
        """删除整个面板"""
        if messagebox.askyesno("确认删除", f"确定要删除[{self.label.cget('text')}]吗？"):
            if self.on_delete:
                self.on_delete(self)
            self.destroy()
        if self.on_config_change:
            self.on_config_change()

    def add_custom_row(self):
        wrapper_frame = tk.Frame(self.cards_container)
        wrapper_frame.pack(fill=tk.X, pady=3, before=self.default_row_frame)
        row_data = self._create_card_widget(wrapper_frame, is_default=False)
        self.custom_rows_data.append(row_data)

        if self.on_config_change:
            self.on_config_change()

    def _create_card_widget(self, parent, is_default=False):
        # (保持原有的卡片创建逻辑，无变化)
        card_bg = "#F8F8F8"
        card = tk.Frame(parent, relief=tk.GROOVE, borderwidth=2, padx=5, pady=5, bg=card_bg)
        card.pack(fill=tk.X, expand=True)

        role_var = tk.StringVar()
        skill_var = tk.StringVar()
        target_var = tk.StringVar()
        lvl_var = tk.IntVar()
        freq_var = tk.StringVar()

        card.columnconfigure(0, weight=1)
        row_counter = 0
        row_frame = tk.Frame(card)
        row_frame.grid(row=row_counter, sticky=tk.EW)

        if is_default:
            role_var.set("默认")
            role_cb = ttk.Combobox(row_frame, textvariable=role_var, width=8, state="disabled")
        else:
            role_var.set(self.ROLE_LIST[0])
            role_cb = ttk.Combobox(row_frame, textvariable=role_var, values=self.ROLE_LIST, width=8, state="readonly")
        role_cb.grid(row=0, column=0, padx=(0, 5), sticky=tk.W)

        skill_cb = ttk.Combobox(row_frame, textvariable=skill_var, values=self.SKILL_OPTIONS, width=7, state="readonly")
        skill_cb.grid(row=0, column=1, padx=(0, 5), sticky=tk.W)
        
        if is_default:
            skill_var.set("双击自动")
            skill_cb.config(state="disabled")
        else:
            skill_cb.current(0)

        freq_cb = ttk.Combobox(row_frame, textvariable=freq_var, values=self.FREQ_OPTIONS, width=10, state="readonly")
        freq_cb.grid(row=0, column=2, sticky=tk.W)
        
        if is_default:
            freq_var.set("重复")
            freq_cb.config(state="disabled")
        else:
            freq_cb.current(2)

        row_counter = 1
        row_frame = tk.Frame(card)
        row_frame.grid(row=row_counter, sticky=tk.EW)

        tk.Label(row_frame, text="治疗:", font=("微软雅黑", 9), bg=card_bg).grid(row=0, column=0, sticky=tk.E, pady=(5, 0))
        target_cb = ttk.Combobox(row_frame, textvariable=target_var, values=self.TARGET_OPTIONS, width=7, state="readonly")
        target_cb.grid(row=0, column=1, sticky=tk.W, padx=(0, 5), pady=(5, 0))

        tk.Label(row_frame, text="等级:", font=("微软雅黑", 9), bg=card_bg).grid(row=0, column=2, sticky=tk.E, pady=(5, 0))
        skill_lvl = ttk.Combobox(row_frame, textvariable=lvl_var, values=self.SKILL_LVL, width=5, state="readonly")
        skill_lvl.grid(row=0, column=3, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        
        if is_default:
            target_var.set("不可用")
            lvl_var.set(1)
            target_cb.config(state="disabled")
            skill_lvl.config(state="disabled")
            tk.Label(row_frame, text="[默认]", font=("微软雅黑", 9), bg=card_bg).grid(row=0, column=4, sticky=tk.E, pady=(5, 0))
        else:
            target_cb.current(6)
            skill_lvl.current(0)  # 默认选择第1级
            del_btn = ttk.Button(row_frame, text="取消", width=6, command=lambda: self._remove_row(parent))
            del_btn.grid(row=0, column=4, sticky=tk.E, pady=(5, 0))

        row_data = {
            'frame': parent, 
            'role_var': role_var,
            'skill_var': skill_var, 'skill_widget': skill_cb,
            'target_var': target_var, 'target_widget': target_cb,
            'lvl_var': lvl_var, 'skill_lvl': skill_lvl,  # 添加lvl_var和skill_lvl
            'freq_var': freq_var, 'freq_widget': freq_cb
        }

        if not is_default:
            self._on_skill_change(row_data)
            role_cb.bind("<<ComboboxSelected>>", lambda e: self.on_config_change and self.on_config_change())
            skill_cb.bind("<<ComboboxSelected>>", lambda e: [self._on_skill_change(row_data), self.on_config_change and self.on_config_change()])
            target_cb.bind("<<ComboboxSelected>>", lambda e: self.on_config_change and self.on_config_change())
            freq_cb.bind("<<ComboboxSelected>>", lambda e: self.on_config_change and self.on_config_change())
            skill_lvl.bind("<<ComboboxSelected>>", lambda e: self.on_config_change and self.on_config_change())

        return row_data

    def _remove_row(self, frame_obj):
        frame_obj.destroy()
        self.custom_rows_data = [r for r in self.custom_rows_data if r['frame'] != frame_obj]

        if self.on_config_change:
            self.on_config_change()

    def _on_skill_change(self, row_data):
        current_skill = row_data['skill_var'].get()
        LOCK_TRIGGERS = ["防御", "双击自动"]
        if current_skill in LOCK_TRIGGERS:
            row_data['target_var'].set("不可用")
            row_data['target_widget'].config(state="disabled")
            # 对于锁定技能，也禁用技能等级选择
            row_data['skill_lvl'].config(state="disabled")
        else:
            if row_data['target_var'].get() == "不可用":
                row_data['target_var'].set("低生命值")
            row_data['target_widget'].config(state="readonly")
            # 对于非锁定技能，启用技能等级选择
            row_data['skill_lvl'].config(state="readonly")

    def get_config_list(self):
        """获取当前配置，返回指定格式的字典（只包含自定义行）"""
        skill_settings = []
        
        # 只添加自定义行，不包含默认行
        for row in self.custom_rows_data:
            item = {
                'role_var': row['role_var'].get(),
                'skill_var': row['skill_var'].get(),
                'target_var': row['target_var'].get(),
                'freq_var': row['freq_var'].get(),
                'skill_lvl': row['lvl_var'].get()  # 添加技能等级
            }
            skill_settings.append(item)
        
        # 返回指定格式，不包含默认行
        return {
            'group_name': self.label.cget("text"),
            'skill_settings': skill_settings
        }
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
        self.geometry('610x750')
        
        self.title(self.TITLE)

        self.adb_active = False

        # 关闭时退出整个程序
        self.protocol("WM_DELETE_WINDOW", self.controller.destroy)

        # --- 任务状态 ---
        self.quest_active = False

        # --- 任务点 ---
        self.task_point_vars = {}
        self.task_point_comboboxes = {}

        # --- ttk Style ---
        self.style = ttk.Style()
        self.style.configure("custom.TCheckbutton")
        self.style.map("Custom.TCheckbutton",
            foreground=[("disabled selected", "#8CB7DF"),("disabled", "#A0A0A0"), ("selected", "#196FBF")])
        self.style.configure("BoldFont.TCheckbutton", font=("微软雅黑", 9,"bold"))
        self.style.configure("LargeFont.TCheckbutton", font=("微软雅黑", 12,"bold"))

        # --- UI 变量 ---
        config_dict = self.load_config()
        logger.info(config_dict)
        for category, attr_name, var_type, default_value in CONFIG_VAR_LIST:
            if issubclass(var_type, tk.Variable):
                setattr(self, attr_name, var_type(value = (config_dict[attr_name] if attr_name in config_dict else default_value)))
            else:
                setattr(self, attr_name, var_type(config_dict[attr_name] if (attr_name in config_dict)and(config_dict[attr_name] is not None) else default_value))  

        self.create_widgets()
        self.updateACTIVE_REST_state() # 初始化时更新旅店住宿entry.
        

        logger.info("**********************************")
        logger.info(f"当前版本: {version}")
        logger.info(self.INTRODUCTION, extra={"summary": True})
        logger.info("**********************************")
        
        if self.LAST_VERSION.get() != version:
            ShowChangesLogWindow()
            self.LAST_VERSION.set(version)
            self.save_config()

    def load_config(self, specific = 'ALL'):
        raw_config = LoadRawConfigFromFile() or {}
        general_config = raw_config.get("GENERAL", {})

        task_specific = general_config.get("TASK_SPECIFIC_CONFIG", False)
        farm_target = general_config.get("FARM_TARGET")

        if task_specific and farm_target and farm_target in raw_config:
            # 任务特定模式：从对应任务字典加载
            task_config = raw_config.get(farm_target, {})
        else:
            # 非任务特定模式或目标无效：从 DEFAULT 加载
            task_config = raw_config.get("DEFAULT", {})

        if specific == "ALL":
            result_config = {}
            result_config.update(general_config)   # 先添加通用配置
            result_config.update(task_config)
        elif specific == "general":
            result_config = general_config
        elif specific == "specific":
            result_config = raw_config.get(farm_target, {})
        elif specific == "default":
            result_config = raw_config.get("DEFAULT", {})

        return result_config
    
    def load_setting_from_dict(self, input_dict):
        setting = FarmConfig()

        for category, attr_name, var_type, default_value in CONFIG_VAR_LIST:
            if attr_name not in input_dict:
                setattr(setting, attr_name, default_value)
            else:
                setattr(setting, attr_name, input_dict[attr_name])

        return setting

    def save_config(self):
        # karma
        if self.KARMA_ADJUST.get().isdigit():
            valuestr = self.KARMA_ADJUST.get()
            self.KARMA_ADJUST.set('+' + valuestr)

        # emu path
        emu_path = self.EMU_PATH.get()
        emu_path = emu_path.replace("HD-Adb.exe", "HD-Player.exe")
        self.EMU_PATH.set(emu_path)

        # farm target
        if self.FARM_TARGET_TEXT.get() in DUNGEON_TARGETS:
            self.FARM_TARGET.set(DUNGEON_TARGETS[self.FARM_TARGET_TEXT.get()])
        else:
            self.FARM_TARGET.set(None)
        
        ##################
        existing_config = LoadRawConfigFromFile() or {}
        other_task_spec_config = {k: v for k, v in existing_config.items()
                      if (k not in ["GENERAL"]) and (type(v) == dict)}

        new_general = {}
        other_items = {}

        for category, attr_name, var_type, default_value in CONFIG_VAR_LIST:
            if issubclass(var_type, tk.Variable):
                value = getattr(self, attr_name).get()
            else:
                value = getattr(self, attr_name)
            if category=='GENERAL':
                new_general[attr_name] = value
            else:
                other_items[attr_name] = value

        new_config = {}
        new_config["GENERAL"] = new_general
        for key, value in other_task_spec_config.items():
            new_config[key] = value
        
        task_specific = new_general.get('TASK_SPECIFIC_CONFIG', False)
        farm_target = new_general.get('FARM_TARGET')
        if task_specific and farm_target:
            new_config[farm_target] = other_items
        else:
            new_config["DEFAULT"] = other_items

        SaveConfigToFile(new_config)

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
        self.section_emu = CollapsibleSection(content_root, title="模拟器", expanded= False if self.EMU_PATH.get() else True,)
        self.section_emu.pack(fill="x", pady=(0, 5)) # 使用pack垂直堆叠
        
        # 获取折叠板的内容容器
        container = self.section_emu.content_frame 

        row_counter = 0 
        frame_row = ttk.Frame(container)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=2)
        
        self.adb_status_label = ttk.Label(frame_row)
        self.adb_status_label.grid(row=0, column=0)
        
        adb_entry = ttk.Entry(frame_row, textvariable=self.EMU_PATH)
        adb_entry.grid_remove()
        
        def selectADB_PATH():
            path = filedialog.askopenfilename(
                title="选择ADB执行文件",
                filetypes=[("Executable", "*.exe"), ("All files", "*.*")]
            )
            if path:
                self.EMU_PATH.set(path)
                self.save_config()

        self.adb_path_change_button = ttk.Button(
            frame_row, text="修改", command=selectADB_PATH, width=5
        )
        self.adb_path_change_button.grid(row=0, column=1)
        
        def update_adb_status(*args):
            if self.EMU_PATH.get():
                self.adb_status_label.config(text="已设置模拟器", foreground="green")
            else:
                self.adb_status_label.config(text="未设置模拟器", foreground="red")
        
        self.EMU_PATH.trace_add("write", lambda *args: update_adb_status())
        update_adb_status()

        # 端口和编号
        row_counter += 1
        frame_row = ttk.Frame(container)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=2)
        ttk.Label(frame_row, text="端口:").grid(row=0, column=2, sticky=tk.W, pady=5)
        vcmd_non_neg = self.register(lambda x: ((x=="")or(x.isdigit())))
        self.adb_port_entry = ttk.Entry(frame_row, textvariable=self.ADB_PORT, validate="key",
                                        validatecommand=(vcmd_non_neg, '%P'), width=7)
        self.adb_port_entry.grid(row=0, column=3)
        ttk.Label(frame_row, text=" 编号:").grid(row=0, column=4, sticky=tk.W, pady=5)
        self.emu_index_entry = ttk.Entry(frame_row, textvariable=self.EMU_INDEX, validate="key",
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
            
        def switch_task_specific_config():
            if self.TASK_SPECIFIC_CONFIG.get():
                task_config = self.load_config("specific")
            else:
                task_config = self.load_config("default")

            for category, attr_name, var_type, default_value in CONFIG_VAR_LIST:
                if attr_name in task_config:
                    value = task_config[attr_name]
                    if issubclass(var_type, tk.Variable):
                        # 获取或创建变量，然后设置值
                        if not hasattr(self, attr_name):
                            # 如果属性不存在，创建默认实例
                            setattr(self, attr_name, var_type())
                        getattr(self, attr_name).set(value)
                    else:
                        # 非 Variable 类型，直接赋值（假设属性已存在，否则创建）
                        setattr(self, attr_name, var_type(value if (value is not None) else default_value))
            
            # 更新开箱人选的文本
            open_value = self.WHO_WILL_OPEN_IT.get()
            self.who_will_open_text_var.set(self.open_chest_mapping.get(open_value, "随机"))

            # 更新善恶
            # TODO 暂时不写了 太麻烦了.

            # 任务点, 这里无论如何都要拿specific的设置.
            specific_config = self.load_config("specific")
            if ("TASK_POINT_STRATEGY" in specific_config)and(specific_config["TASK_POINT_STRATEGY"]!=None):
                self.TASK_POINT_STRATEGY = specific_config["TASK_POINT_STRATEGY"]
            else:
                self.TASK_POINT_STRATEGY = None

            self.save_config()

            color = "#196FBF" if self.TASK_SPECIFIC_CONFIG.get() else "black"
            for section in [self.section_karma, self.section_combat,self.section_advanced]:
                section.label.config(fg=color)

            return
        
        def close_task_specific_config():
            self.TASK_SPECIFIC_CONFIG.set(False)
            switch_task_specific_config()
            return
        
        def delete_task_specific_config():
            close_task_specific_config()
            raw_config = LoadRawConfigFromFile() or {}
    
            general_config = raw_config.get("GENERAL", {})
            farm_target = general_config.get("FARM_TARGET")
            if farm_target and farm_target in raw_config:
                logger.info(f"删除任务定制的配置文件, 任务为{farm_target}.")
                del raw_config[farm_target]
            
            SaveConfigToFile(raw_config)
            return

        ttk.Label(frame_row, text="任务目标:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.farm_target_combo = ttk.Combobox(frame_row,
                                              textvariable=self.FARM_TARGET_TEXT, 
                                              values=list(DUNGEON_TARGETS.keys()),
                                              state="readonly")
        self.farm_target_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)
        # self.farm_target_combo.bind("<<ComboboxSelected>>", lambda e: close_task_specific_config()) # 这里用后面的战斗部分的g更新方法覆盖

        row_counter += 1
        frame_row = ttk.Frame(container)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=2)
        self.task_specific_config_check = ttk.Checkbutton(
            frame_row, text="用任务定制的配置文件覆盖默认配置.",
            variable=self.TASK_SPECIFIC_CONFIG,
            command=switch_task_specific_config,
            style="BoldFont.TCheckbutton",
            )
        self.task_specific_config_check.grid(row=0, column=0, sticky=tk.W, pady=5)

        self.delete_task_specific_config_button = ttk.Button(frame_row, text="清除", command=delete_task_specific_config, width=4)
        self.delete_task_specific_config_button.grid(row=0, column=1, sticky=tk.W, pady=5)

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
        
        ttk.Label(frame_row, text="开箱人选:").grid(row=0, column=0, sticky=tk.W, pady=5)

        self.open_chest_mapping = {0:"随机", 1:"左上", 2:"中上", 3:"右上", 4:"左下", 5:"中下", 6:"右下"}
        self.who_will_open_text_var = tk.StringVar(value=self.open_chest_mapping.get(self.WHO_WILL_OPEN_IT.get(), "随机"))
        self.who_will_open_combobox = ttk.Combobox(frame_row, textvariable=self.who_will_open_text_var, 
                                                   values=list(self.open_chest_mapping.values()), state="readonly", width=4)
        self.who_will_open_combobox.grid(row=0, column=1, sticky=tk.W, pady=5)
        def handle_open_chest_selection(event=None):
            open_chest_reverse_mapping = {v: k for k, v in self.open_chest_mapping.items()}
            self.WHO_WILL_OPEN_IT.set(open_chest_reverse_mapping[self.who_will_open_text_var.get()])
            self.save_config()
        self.who_will_open_combobox.bind("<<ComboboxSelected>>", handle_open_chest_selection)

        ttk.Label(frame_row, text=" | ").grid(row=0, column=2, sticky=tk.W, pady=5)

        self.random_chest_check = ttk.Checkbutton(frame_row, text="快速开箱", variable=self.QUICK_DISARM_CHEST,
                                                  command=self.save_config, style="Custom.TCheckbutton")
        self.random_chest_check.grid(row=0, column=3, sticky=tk.W, pady=5)

        # 跳过恢复
        row_counter += 1
        row_recover = tk.Frame(container)
        row_recover.grid(row=row_counter, column=0, columnspan=2, sticky=tk.W, pady=2)
        self.skip_recover_check = ttk.Checkbutton(row_recover, text="跳过战后恢复", variable=self.SKIP_COMBAT_RECOVER,
                                                  command=self.save_config, style="Custom.TCheckbutton")
        self.skip_recover_check.grid(row=0, column=0)
        self.skip_chest_recover_check = ttk.Checkbutton(row_recover, text="跳过开箱后恢复", variable=self.SKIP_CHEST_RECOVER,
                                                        command=self.save_config, style="Custom.TCheckbutton")
        self.skip_chest_recover_check.grid(row=0, column=1)

        # 休息设置
        row_counter += 1
        frame_row = ttk.Frame(container)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=2)
        def checkcommand():
            self.updateACTIVE_REST_state()
            self.save_config()
        self.active_rest_check = ttk.Checkbutton(frame_row, variable=self.ACTIVE_REST, text="启用旅店休息",
                                                 command=checkcommand, style="Custom.TCheckbutton")
        self.active_rest_check.grid(row=0, column=0)
        ttk.Label(frame_row, text=" | 完成").grid(row=0, column=1, sticky=tk.W, pady=5)
        self.rest_intervel_entry = ttk.Entry(frame_row, textvariable=self.REST_INTERVEL, validate="key",
                                             validatecommand=(vcmd_non_neg, '%P'), width=2)
        self.rest_intervel_entry.grid(row=0, column=2)
        ttk.Label(frame_row, text="次后休息.").grid(row=0, column=3, sticky=tk.W, pady=5)
        self.button_save_rest_intervel = ttk.Button(frame_row, text="保存", command=self.save_config, width=4)
        self.button_save_rest_intervel.grid(row=0, column=4)

        # 善恶设置
        row_counter += 1
        frame_row = ttk.Frame(container)
        frame_row.grid(row=row_counter, column=0, sticky="ew", pady=2)
        ttk.Label(frame_row, text=f"善恶:").grid(row=0, column=0, sticky=tk.W, pady=5)
        
        # 善恶值逻辑保持不变
        self.karma_adjust_mapping = {"维持现状": "+0", "恶→中立,中立→善": "+17", "善→中立,中立→恶": "-17"}
        times = int(self.KARMA_ADJUST.get())
        if times == 0: self.karma_adjust_text_var = tk.StringVar(value="维持现状")
        elif times > 0: self.karma_adjust_text_var = tk.StringVar(value="恶→中立,中立→善")
        elif times < 0: self.karma_adjust_text_var = tk.StringVar(value="善→中立,中立→恶")
            
        self.karma_adjust_combobox = ttk.Combobox(frame_row, textvariable=self.karma_adjust_text_var,
                                                  values=list(self.karma_adjust_mapping.keys()), state="readonly", width=14)
        self.karma_adjust_combobox.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        def handle_karma_adjust_selection(event=None):
            karma_adjust_left = int(self.KARMA_ADJUST.get())
            karma_adjust_want = int(self.karma_adjust_mapping[self.karma_adjust_text_var.get()])
            if (karma_adjust_left == 0 and karma_adjust_want == 0) or (karma_adjust_left*karma_adjust_want > 0):
                return
            self.KARMA_ADJUST.set(self.karma_adjust_mapping[self.karma_adjust_text_var.get()])
            self.save_config()
        self.karma_adjust_combobox.bind("<<ComboboxSelected>>", handle_karma_adjust_selection)
        
        ttk.Label(frame_row, text="还需").grid(row=0, column=2, sticky=tk.W, pady=5)
        ttk.Label(frame_row, textvariable=self.KARMA_ADJUST).grid(row=0, column=3, sticky=tk.W, pady=5)
        ttk.Label(frame_row, text="点").grid(row=0, column=4, sticky=tk.W, pady=5)

        # ==========================================
        # 分组 4: 战斗
        # ==========================================
        self.section_combat = CollapsibleSection(content_root, title="战斗")
        self.section_combat.pack(fill="x", pady=5)
        self.combat_container = self.section_combat.content_frame
        row_counter = 0

        ttk.Label(self.combat_container, text="请先选择任务目标").pack()

        def save_task_point_strategy_config(event=None):
            """获取任务点策略配置，格式为：
            {"overall_strategy": strategy_name, "task_point": {0: strategy_name, 1: strategy_name, ...}}
            """
            config = {"overall_strategy": "", "task_point": {}}
            
            # 如果还没有创建任务点UI，直接返回空配置
            if not hasattr(self, 'task_point_vars') or not self.task_point_vars:
                return config
            
            # 获取全程策略
            if "全程" in self.task_point_vars:
                config["overall_strategy"] = self.task_point_vars["全程"].get()
            
            # 获取每个任务点的策略（按索引顺序）
            for idx, point in enumerate(self.current_task_points):
                if point in self.task_point_vars:
                    config["task_point"][idx] = self.task_point_vars[point].get()
            
            self.TASK_POINT_STRATEGY = config

            self.save_config()
            return 
        def _update_task_points_visibility(show):
            """控制任务点容器的显示/隐藏，并调整全程标签颜色"""
            if show:
                self.task_points_frame.pack(fill=tk.X, pady=5)
                self.overall_label.config(foreground="gray")  # 正常颜色
            else:
                self.task_points_frame.pack_forget()
                self.overall_label.config(foreground="black")   # 灰色
            return
        def on_switch_overall_update_ui(event=None):
            new_selection = self.overall_combo.get()
            is_custom = (new_selection == "自定义任务点策略")

            if is_custom:
                if not self.TASK_SPECIFIC_CONFIG.get():
                    # 弹出确认对话框
                    answer = messagebox.askyesno(
                        "启用任务专用配置",
                        "自定义任务点策略需要使用任务专用的配置文件。是否立即启用任务专用配置？"
                    )
                    if answer:
                        # 用户确认启用
                        self.TASK_SPECIFIC_CONFIG.set(True)
                        switch_task_specific_config()   # 调用已有方法更新UI
                        _update_task_points_visibility(True)
                        self.last_overall_selection = new_selection
                    else:
                        # 用户取消，恢复之前的选择
                        self.overall_combo.set(self.last_overall_selection)
                else:
                    # 已启用任务专用配置，直接显示
                    _update_task_points_visibility(True)
                    self.last_overall_selection = new_selection
            else:
                # 选择普通策略，隐藏任务点行
                _update_task_points_visibility(False)
                self.last_overall_selection = new_selection
            save_task_point_strategy_config()
            return
        def create_task_point_ui():
            task_name = self.FARM_TARGET.get()
            if not task_name:
                return

            # 清空原有内容
            for widget in self.combat_container.winfo_children():
                widget.destroy()

            # 获取任务点列表
            try:
                self.current_task_points = LoadQuest(task_name)._TARGETINFOLIST
            except NameError:
                logger.error('不可用的任务名.')
                self.current_task_points = []

            # 获取所有策略面板名称
            strategy_names = list(self.strategy_panels.values())

            # 重新创建每一行
            self.task_point_vars = {}
            self.task_point_comboboxes = {}

            # ---- 1. 创建全程行（单独设计，加粗，带间距） ----
            overall_frame = ttk.Frame(self.combat_container)
            overall_frame.pack(fill=tk.X, pady=(0, 10))  # 增加底部间距

            # 全程标签
            self.overall_label = ttk.Label(overall_frame, text="全程", font=('微软雅黑', 12, 'bold'))
            self.overall_label.pack(side=tk.LEFT, padx=5)

            # 全程下拉框
            overall_var = tk.StringVar()
            overall_values = strategy_names + ["自定义任务点策略"] if strategy_names else ["自定义任务点策略"]
            # 设置默认值
            saved_overall = None
            task_point_strategy = getattr(self, 'TASK_POINT_STRATEGY', None)
            if task_point_strategy and isinstance(task_point_strategy, dict):
                saved_overall = task_point_strategy.get('overall_strategy')
                if saved_overall and saved_overall in overall_values:
                    overall_var.set(saved_overall)
                    # 如果全程策略是“自定义任务点策略”，则后续要显示任务点
                    initial_show_task_points = (saved_overall == "自定义任务点策略")
                else:
                    # 保存的策略无效，回退
                    saved_overall = None
            if saved_overall is None:
                # 没有保存或无效，使用默认策略 "全自动战斗"
                overall_var.set("全自动战斗")
                initial_show_task_points = False

            # 初始化全程策略
            self.overall_combo = ttk.Combobox(overall_frame, textvariable=overall_var,
                                        values=overall_values, state="readonly", width=25)
            self.overall_combo.pack(side=tk.LEFT, padx=5)

            # 保存全程行相关对象
            self.task_point_vars["全程"] = overall_var
            self.task_point_comboboxes["全程"] = self.overall_combo

            # ---- 2. 创建任务点容器 ----
            self.task_points_frame = ttk.Frame(self.combat_container)
            self.task_points_frame.pack(fill=tk.X, pady=5)

            # 填充任务点行
            for idx, point in enumerate(self.current_task_points):
                row_frame = ttk.Frame(self.task_points_frame)
                row_frame.pack(fill=tk.X, pady=2)

                task_point_var = tk.StringVar()
                # 尝试从保存的配置获取该任务点的策略
                saved_point_strategy = None
                if task_point_strategy and isinstance(task_point_strategy, dict):
                    task_point_dict = task_point_strategy.get('task_point', {})
                    if isinstance(task_point_dict, dict):
                        saved_point_strategy = task_point_dict.get(str(idx))  # 注意索引可能是字符串或整数
                        if saved_point_strategy is None:
                            saved_point_strategy = task_point_dict.get(idx)  # 尝试整数键
                        if saved_point_strategy and saved_point_strategy in strategy_names:
                            task_point_var.set(saved_point_strategy)
                        else:
                            saved_point_strategy = None

                if saved_point_strategy is None:
                    # 没有保存或无效，使用默认策略 "全自动战斗"
                    task_point_var.set("全自动战斗")

                combo = ttk.Combobox(row_frame, textvariable=task_point_var, values=strategy_names,
                                    state="readonly", width=15)
                combo.bind("<<ComboboxSelected>>", save_task_point_strategy_config)    
                combo.pack(side=tk.LEFT, padx=5)

                point_name = point.target + ((' '+str(point.roi)) if point.target=='position' else '')
                ttk.Label(row_frame, text=point_name, width=20, anchor=tk.W).pack(side=tk.LEFT, padx=5)

                self.task_point_vars[point] = task_point_var
                self.task_point_comboboxes[point] = combo

            # ---- 3. 根据全程行初始选择控制任务点容器显示状态 ----
            _update_task_points_visibility(initial_show_task_points)

            # ---- 4. 绑定全程行选择事件 ----
            self.overall_combo.bind("<<ComboboxSelected>>", on_switch_overall_update_ui)

            logger.info(f"已刷新任务点界面，任务点数量: {len(self.current_task_points)}")
            return
        def update_combat_strategy_combobox_values():
            if not hasattr(self, 'task_point_comboboxes') or not self.task_point_comboboxes:
                return

            strategy_names = list(self.strategy_panels.values())

            for key, combo in self.task_point_comboboxes.items():
                if key == "全程":
                    new_values = strategy_names + ["自定义任务点策略"] if strategy_names else ["自定义任务点策略"]
                else:
                    new_values = strategy_names

                current = combo.get()
                combo['values'] = new_values
                # 如果当前值不在新列表中，重置为合适值
                if current not in new_values:
                    if new_values:
                        combo.set(new_values[0])
                    else:
                        combo.set('')

            if hasattr(self, 'overall_combo'):
                selected = self.overall_combo.get()
                show = (selected == "自定义任务点策略")
                _update_task_points_visibility(show)
            return
        def on_farm_target_selected(event):
            close_task_specific_config()
            create_task_point_ui()
        self.farm_target_combo.bind("<<ComboboxSelected>>", on_farm_target_selected)

        self.after(200, create_task_point_ui)

        # ==========================================
        # 分组 4: 高级
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
            variable=self.ACTIVE_BEG_MONEY,
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
            variable=self.ACTIVE_ROYALSUITE_REST,
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
            variable=self.ACTIVE_TRIUMPH,
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
            variable=self.ACTIVE_BEAUTIFUL_ORE,
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
            variable=self.ACTIVE_CSC,
            text="尝试调整因果",
            command=self.save_config,
            style="Custom.TCheckbutton"
        )
        self.active_csc.grid(row=0, column=0, sticky=tk.W)
        
        # ==========================================
        # 分组 5: 战斗方案
        # ==========================================
        self.section_combat_adv = CollapsibleSection(content_root, title="战斗方案")
        self.section_combat_adv.pack(fill="x")
        container = self.section_combat_adv.content_frame
        row_counter = 0

        self.strategy_panels = {}  # 改为字典 {panel: name}

        def save_strategy():
            """将当前设置打包并保存"""
            all_configs = []
            for panel in self.strategy_panels:  # 遍历字典的键（面板对象）
                config = panel.get_config_list()
                all_configs.append(config)

            self.STRATEGY = all_configs
            self.save_config()
            # 不需要 return

        def on_delete_panel(p):
            """删除面板的回调函数"""
            # 从字典中删除该panel
            if p in self.strategy_panels:
                del self.strategy_panels[p]

            # 销毁面板
            p.destroy()

            # 更新列表
            update_combat_strategy_combobox_values()

            # 如果没有面板了，隐藏容器
            if len(self.strategy_panels) == 0:
                self.strategy_panels_container.grid_forget()

            save_strategy()

        def on_panel_name_changed(panel, new_name):
            """面板名称改变时的回调"""
            # 检查新名称是否已经存在（排除自身）
            existing_names = [name for p, name in self.strategy_panels.items() if p != panel]
            if new_name in existing_names:
                messagebox.showerror("错误", f"名称 '{new_name}' 已存在，请使用其他名称")
                return False

            # 更新映射
            self.strategy_panels[panel] = new_name

            # 更新列表
            update_combat_strategy_combobox_values()

            # 保存
            save_strategy()
            return True

        def add_new_panel(init_config=None):
            self.strategy_panels_container.grid()

            # 确定标题
            if init_config and 'group_name' in init_config:
                title = init_config['group_name']
                # 检查是否重复（与现有面板名称比较）
                existing_names = list(self.strategy_panels.values())
                if title in existing_names:
                    # 如果名称重复，则添加序号
                    base_title = title
                    idx = 1
                    while f"{base_title} ({idx})" in existing_names:
                        idx += 1
                    title = f"{base_title} ({idx})"
            else:
                # 生成默认标题
                idx = 1
                existing_names = list(self.strategy_panels.values())
                while f"策略配置 {idx}" in existing_names:
                    idx += 1
                title = f"策略配置 {idx}"

            panel = SkillConfigPanel(
                self.strategy_panels_container,
                title=title,
                on_delete=on_delete_panel,
                on_name_change=on_panel_name_changed,
                on_config_change=save_strategy,
                init_config=init_config,
            )
            panel.pack(fill=tk.X, pady=2)

            # 将新面板加入字典
            self.strategy_panels[panel] = title

            # 更新下拉框
            update_combat_strategy_combobox_values()

            # 保存配置
            if init_config==None:
                save_strategy()

            return panel

        ttk.Button(container, text="➕ 添加新技能配置", command=add_new_panel).grid(row=row_counter, column=0, sticky=tk.W)

        row_counter += 1
        container.columnconfigure(0, weight=1)
        self.strategy_panels_container = tk.Frame(container)
        self.strategy_panels_container.grid(row=row_counter, column=0, sticky="ew")

        # 初始化
        if self.STRATEGY and isinstance(self.STRATEGY, list):
            # 有保存的策略，逐个创建
            for config in self.STRATEGY:
                add_new_panel(init_config=config)
        else:
            # 无策略，创建一个默认面板
            add_new_panel()

        ###################################################################
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

        self.update_text = ttk.Label(frame_row_update, textvariable=self.LATEST_VERSION,foreground="red")
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

    def updateACTIVE_REST_state(self):
        if self.ACTIVE_REST.get():
            self.rest_intervel_entry.config(state="normal")
            self.button_save_rest_intervel.config(state="normal")
        else:
            self.rest_intervel_entry.config(state="disable")
            self.button_save_rest_intervel.config(state="disable")

    def set_controls_state(self, state):
        self.button_and_entry = [
            self.adb_path_change_button,
            self.random_chest_check,
            self.who_will_open_combobox,
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
            self.task_specific_config_check,
            self.button_save_adb_port,
            self.delete_task_specific_config_button,
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
            self.updateACTIVE_REST_state()

    def toggle_start_stop(self):
        if not self.quest_active:
            self.start_stop_btn.config(text="停止")
            self.set_controls_state(tk.DISABLED)
            setting = self.load_setting_from_dict(self.load_config())
            setting._FINISHINGCALLBACK = self.finishingcallback
            self.msg_queue.put(('start_quest', setting))
            self.quest_active = True
        else:
            self.msg_queue.put(('stop_quest', None))

    def finishingcallback(self):
        logger.info("已停止.")
        self.start_stop_btn.config(text="脚本, 启动!")
        self.set_controls_state(tk.NORMAL)
        
        config = self.load_config()
        if 'KARMA_ADJUST' in config:
            self.KARMA_ADJUST.set(config['KARMA_ADJUST'])

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