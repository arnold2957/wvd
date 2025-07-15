import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import os
import logging
from script import *
from auto_updater import *
from utils import *
from threading import Thread,Event
import shutil

__version__ = '1.4.2-beta1'

OWNER = "arnold2957"
REPO = "wvd"
############################################
RESTART_SCREENSHOT_FOLDER_NAME = "screenshotwhenrestart"
if os.path.exists(RESTART_SCREENSHOT_FOLDER_NAME):
    shutil.rmtree(RESTART_SCREENSHOT_FOLDER_NAME)
os.makedirs(RESTART_SCREENSHOT_FOLDER_NAME, exist_ok=True)

############################################
# --- 预定义的技能和目标 ---
DUNGEON_TARGETS = ["[刷图]水路一号街",
                   "[刷图]水路船一 shiphold",
                   "[刷图]水路船二 lounge",
                   "[刷图]鸟洞三层 fordraig B3F",
                   "[刷图]要塞三层",
                   "[刷图]卢比肯的洞窟",
                   "[刷图]忍洞一层 开箱",
                   "[刷图]忍洞一层 刷怪",
                   "[刷图]土洞(5-9)",
                   "[刷图]火洞(10-14)", 
                   "[刷图]风洞(15-19)",
                   "[刷图]光洞(15-19)",
                   "[任务]7000G",
                   "[任务]角鹫之剑 fordraig",
                   "[任务]击退敌势力",
                   "[任务]卢比肯-三牛",
                   "[任务]忍洞-金箱"
                   ]

############################################
class ConfigPanelApp(tk.Toplevel):
    def __init__(self, master_controller):
        super().__init__(master_controller)
        self.controller = master_controller
        self.geometry('550x580')
        # self.root.resizable(False, False)
        self.title(f"WvDAS 巫术daphne自动刷怪 v{__version__} @德德Dellyla(B站)")

        self.adb_active = False

        # 关闭时退出整个程序
        self.protocol("WM_DELETE_WINDOW", self.controller.destroy)

        # --- 后台线程 ---
        self.thread = None
        self.stop_event = Event()

        # --- ttk Style ---
        self.style = ttk.Style()
        self.style.configure("Active.TButton", foreground="green")
        self.style.configure("Active.TButton", foreground="green")
        

        # --- UI 变量 ---
        self.var_list = [
            # var_name, type, config_name, default_value
            ["farm_target_var", tk.StringVar, "_FARMTARGET", DUNGEON_TARGETS[0] if DUNGEON_TARGETS else ""],
            ["randomly_open_chest_var", tk.BooleanVar, "_RANDOMLYOPENCHEST", False],
            ["who_will_open_it_var", tk.IntVar,"_WHOWILLOPENIT",0],
            ["skip_recover_var", tk.BooleanVar, "_SKIPCOMBATRECOVER", False],
            ["skip_chest_recover_var",tk.BooleanVar,"_SKIPCHESTRECOVER",False],
            ["system_auto_combat_var", tk.BooleanVar, "SYSTEM_AUTO_COMBAT_ENABLED", False],
            ["aoe_once_var",tk.BooleanVar,"AOE_ONCE",False],
            ["auto_after_aoe_var",tk.BooleanVar,"AUTO_AFTER_AOE",False],
            ["active_rest_var",tk.BooleanVar,"ACTIVE_REST",True],
            ["rest_intervel_var", tk.StringVar, "_RESTINTERVEL", 0],
            ["karma_adjust_var", tk.StringVar, "_KARMAADJUST", "+0"],
            ["adb_path_var", tk.StringVar, "ADB_PATH", ""],
            ["adb_port_var", tk.StringVar, "ADB_PORT", 5555],
            ["last_version",tk.StringVar,"LAST_VERSION",""],
            ["latest_version",tk.StringVar,"LATEST_VERSION",None]
            ]
        
        self.config = LoadConfigFromFile()
        for attr_name, var_type, var_config_name, var_default_value in self.var_list:
            setattr(self, attr_name, var_type(value = self.config.get(var_config_name,var_default_value)))

        self._spell_skill_config_internal = list(self.config.get("_SPELLSKILLCONFIG", []))

        self.skill_buttons_map = [] # 用于存储按钮和它们关联的技能列表

        self.create_widgets()
        self.update_combat_buttons_state() # 初始化时更新按钮状态 (包括启用/禁用)
        self.update_skill_button_visuals() # 初始化时更新技能按钮颜色
        self.update_current_skills_display() # 初始化时更新技能显示
        self.update_active_rest_state() # 初始化时更新旅店住宿entry.
        self.update_change_aoe_once_check() #

        logger.info("**********************************\n" \
                    f"当前版本: {__version__}\n遇到问题? 请访问:\nhttps://github.com/arnold2957/wvd \n或加入Q群: 922497356\n"\
                    "**********************************\n" )
        
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

        for attr_name, _, var_config_name, _ in self.var_list:
            self.config[var_config_name] = getattr(self, attr_name).get()

        # 统计启用技能
        if self.system_auto_combat_var.get():
            self.config["_SPELLSKILLCONFIG"] = []
        else:
            self.config["_SPELLSKILLCONFIG"] = list(set(self._spell_skill_config_internal))
        
        SaveConfigToFile(self.config)

    def updata_config(self):
        config = LoadConfigFromFile()
        if '_KARMAADJUST' in config:
            self.karma_adjust_var.set(config['_KARMAADJUST'])

    def create_widgets(self):
        self.log_display = scrolledtext.ScrolledText(self, wrap=tk.WORD, state=tk.DISABLED, bg='white', width = 34, height = 1)
        self.log_display.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.scrolled_text_handler = ScrolledTextHandler(self.log_display)
        self.scrolled_text_handler.setLevel(logging.INFO)
        self.scrolled_text_handler.setFormatter(scrolled_text_formatter)
        logger.addHandler(self.scrolled_text_handler)

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
        self.farm_target_combo = ttk.Combobox(frame_row2, textvariable=self.farm_target_var, values=DUNGEON_TARGETS, state="readonly")
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
            command=self.save_config
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
            command=self.save_config
        )
        self.skip_recover_check.grid(row=0, column=0)
        self.skip_chest_recover_check = ttk.Checkbutton(
            row_recover,
            text="跳过开箱后恢复",
            variable=self.skip_chest_recover_var,
            command=self.save_config
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
            command=checkcommand
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

        # 启动!
        row_counter += 1
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row_counter, column=0, columnspan=2, pady=5, sticky=tk.W)
        s = ttk.Style()
        s.configure('start.TButton', font=('微软雅黑', 15))
        def btn_command():
            self.toggle_start_stop()
            self.save_config()
        self.start_stop_btn = ttk.Button(
            button_frame,
            text="脚本, 启动!",
            command=btn_command,
            style='start.TButton'
        )
        self.start_stop_btn.grid(row=0, column=0, padx=2)

        # 分割线
        row_counter += 1
        ttk.Separator(main_frame, orient='horizontal').grid(row=row_counter, column=0, columnspan=3, sticky='ew', pady=10)

        # 技能配置 文本
        row_counter += 1
        ttk.Label(main_frame, text="技能配置:", font=('Arial', 10, 'bold')).grid(row=row_counter, column=0, sticky=tk.W, pady=5)

        # 系统自动战斗
        row_counter += 1
        style = ttk.Style()
        style.configure("LargeFont.TCheckbutton", font=("微软雅黑", 10,"bold"))  # 修改字体和字号
        self.system_auto_check = ttk.Checkbutton(
            main_frame,
            text="启用自动战斗",
            variable=self.system_auto_combat_var,
            command=self.toggle_system_auto_combat,
            style="LargeFont.TCheckbutton"  # 应用自定义样式
        )
        self.system_auto_check.grid(row=row_counter, column=0, columnspan=2, sticky=tk.W, pady=5)

        #仅释放一次aoe
        def aoe_once_command():
            self.update_change_aoe_once_check()
            self.save_config()
        row_counter += 1
        self.aoe_once_check = ttk.Checkbutton(
            main_frame,
            text="一场战斗中仅释放一次全体AOE",
            variable=self.aoe_once_var,
            command= aoe_once_command
        )
        self.aoe_once_check.grid(row=row_counter, column=0, columnspan=2, sticky=tk.W, pady=5)

        #任何aoe后自动战斗
        row_counter += 1
        self.auto_after_aoe_check = ttk.Checkbutton(
            main_frame,
            text="全体AOE后开启自动战斗",
            variable=self.auto_after_aoe_var,
            command= self.save_config
        )
        self.auto_after_aoe_check.grid(row=row_counter, column=0, columnspan=2, sticky=tk.W, pady=5)



        # 技能按钮框架
        row_counter += 1
        self.skills_button_frame = ttk.Frame(main_frame)
        self.skills_button_frame.grid(row=row_counter, column=0, columnspan=2, sticky=tk.W)

        self.btn_enable_all = ttk.Button(self.skills_button_frame, text="启用所有技能", command=lambda: self.update_spell_config(ALL_SKILLS, "all"))
        self.btn_enable_all.grid(row=0, column=0, padx=2, pady=2)
        self.skill_buttons_map.append({"button": self.btn_enable_all, "skills": ALL_SKILLS, "name": "all"})

        self.btn_enable_horizontal_aoe = ttk.Button(self.skills_button_frame, text="启用所有横排AOE", command=lambda: self.update_spell_config(ROW_AOE_SKILLS, "horizontal_aoe"))
        self.btn_enable_horizontal_aoe.grid(row=0, column=1, padx=2, pady=2)
        self.skill_buttons_map.append({"button": self.btn_enable_horizontal_aoe, "skills": ROW_AOE_SKILLS, "name": "horizontal_aoe"})

        self.btn_enable_full_aoe = ttk.Button(self.skills_button_frame, text="启用所有全体AOE", command=lambda: self.update_spell_config(FULL_AOE_SKILLS, "full_aoe"))
        self.btn_enable_full_aoe.grid(row=1, column=0, padx=2, pady=2)
        self.skill_buttons_map.append({"button": self.btn_enable_full_aoe, "skills": FULL_AOE_SKILLS, "name": "full_aoe"})

        self.btn_enable_secret_aoe = ttk.Button(self.skills_button_frame, text="启用秘术AOE", command=lambda: self.update_spell_config(SECRET_AOE_SKILLS, "secret_aoe"))
        self.btn_enable_secret_aoe.grid(row=1, column=1, padx=2, pady=2)
        self.skill_buttons_map.append({"button": self.btn_enable_secret_aoe, "skills": SECRET_AOE_SKILLS, "name": "secret_aoe"})

        self.btn_enable_physical = ttk.Button(self.skills_button_frame, text="启用强力单体", command=lambda: self.update_spell_config(PHYSICAL_SKILLS, "physical_skills"))
        self.btn_enable_physical.grid(row=2, column=0, padx=2, pady=2)
        self.skill_buttons_map.append({"button": self.btn_enable_physical, "skills": PHYSICAL_SKILLS, "name": "physical_skills"})

        self.btn_enable_cc = ttk.Button(self.skills_button_frame, text="启用群体控制", command=lambda: self.update_spell_config(CC_SKILLS, "cc_skills"))
        self.btn_enable_cc.grid(row=2, column=1, padx=2, pady=2)
        self.skill_buttons_map.append({"button": self.btn_enable_cc, "skills": CC_SKILLS, "name": "cc_skills"})

        # (不使用)技能选择结果展示
        self.current_skills_label_var = tk.StringVar()

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

        self.aoe_once_check.config(state = button_state)
        self.auto_after_aoe_check.config(state = button_state)
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
                logger.info(f"已启用 {category_name} 技能. 当前技能: {self._spell_skill_config_internal}")

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
        self.updata_config()

    def dungeonLoop(self):
        logger.info(f"目标地下城:{self.farm_target_var.get()}")
        setting = FarmSetting()
        setting._SYSTEMAUTOCOMBAT = self.system_auto_combat_var.get()
        setting._RANDOMLYOPENCHEST = self.randomly_open_chest_var.get()
        setting._WHOWILLOPENIT = self.who_will_open_it_var.get()
        setting._SKIPCOMBATRECOVER = self.skip_recover_var.get()
        setting._SKIPCHESTRECOVER = self.skip_chest_recover_var.get()
        setting._FORCESTOPING = self.stop_event
        setting._SPELLSKILLCONFIG = [s for s in ALL_SKILLS if s in list(set(self._spell_skill_config_internal))]
        setting._FINISHINGCALLBACK = self.finishingcallback
        setting._AOE_ONCE = self.aoe_once_var.get()
        setting._AUTO_AFTER_AOE = self.auto_after_aoe_var.get()
        setting._ACTIVE_REST = self.active_rest_var.get()
        setting._RESTINTERVEL = int(self.rest_intervel_var.get())
        setting._KARMAADJUST = str(self.karma_adjust_var.get())
        setting._LOGGER = logger
        setting._ADBPATH = self.adb_path_var.get()
        setting._ADBPORT = self.adb_port_var.get()
        StreetFarm,QuestFarm = Factory()

        if not self.adb_active:
            self.adb_active = StartAdbServer(setting)
            if not self.adb_active:
                self.finishingcallback()
                return

        setting._ADBDEVICE = CreateAdbDevice(setting)

        match self.farm_target_var.get():
            case "[刷图]水路船一 shiphold":
                setting._FARMTARGET = 'shiphold'
                setting._TARGETLIST = ['chest','harken']
                StreetFarm(setting)
            case "[刷图]水路船二 lounge":
                setting._FARMTARGET = 'shiphold'
                setting._TARGETLIST = ['shiphold_upstair_once','chest','lounge_downstair_once','harken']
                setting._TARGETSEARCHDIR = [
                    [[1,1,1,1]],
                    [[100,100,700,1500]],
                    [[100,100,700,1500]],
                    None]
                setting._TARGETROI = [
                    [[0,0,900,739]],
                    [[0,0,900,739],[0,529,212,106]],
                    [[0,0,900,739]],
                    None]
                StreetFarm(setting)
            case "[刷图]水路一号街":
                setting._FARMTARGET = 'Dist'
                setting._TARGETLIST = ['chest','harken']
                StreetFarm(setting)
            case "[刷图]土洞(5-9)":
                setting._FARMTARGET = 'DOE'
                setting._TARGETLIST = ['DOEtarget','DOE_quit']
                setting._DUNGWAITTIMEOUT = 0
                setting._SYSTEMAUTOCOMBAT = True
                StreetFarm(setting)
            case "[刷图]风洞(15-19)":
                setting._FARMTARGET = 'DOW'
                setting._TARGETLIST = ['chest','DOW_quit']
                setting._TARGETSEARCHDIR = [
                    [[700,1200,100,100]],
                    [[700,1200,100,100]]]
                setting._TARGETROI = [
                    [[0,780,900,500],[0,780,150,120]],
                    None]
                setting._SYSTEMAUTOCOMBAT = True
                StreetFarm(setting)
            case "[刷图]火洞(10-14)":
                setting._FARMTARGET = 'DOF'
                setting._TARGETLIST = ['DOFtarget1','DOFtarget2','DOF_quit']
                setting._DUNGWAITTIMEOUT = 0
                setting._SYSTEMAUTOCOMBAT = True
                StreetFarm(setting)
            case "[刷图]光洞(15-19)":
                setting._FARMTARGET = 'DOL'
                setting._TARGETLIST = ['chest','DOL_quit']
                setting._TARGETSEARCHDIR = [
                    [[700,100,100,1200]],
                    [[700,100,100,1200]]]
                setting._TARGETROI = [
                    [[420,686,478,481]],
                    None]
                StreetFarm(setting)
            case "[刷图]卢比肯的洞窟":
                setting._FARMTARGET = 'LBC'
                setting._TARGETLIST = ['chest','LBC/LBC_quit']
                StreetFarm(setting)
            case "[刷图]忍洞一层 开箱":
                setting._FARMTARGET = 'SSC'
                setting._TARGETLIST = ['chest','chest','SSC/SSC_quit']
                setting._TARGETSEARCHDIR = [
                    [[100,1200,700,100]],
                    [[700,1200,100,100]],
                    [[700,1200,100,100]]]
                setting._TARGETROI = [
                    [[0,0,900,1600],[650,0,250,811],[507,166,179,165],],
                    [[0,0,900,1600],[0,0,900,800]],
                    None]
                StreetFarm(setting)
            case "[刷图]忍洞一层 刷怪":
                setting._FARMTARGET = 'SSC'
                setting._TARGETLIST = ['SSC/SSC1F_left_once','SSC/SSC1F_left_1_once','SSC/SSC1F_left_2_once','SSC/SSC1F_left_3_once','SSC/SSC1F_right_once','SSC/SSC_quit']
                setting._TARGETSEARCHDIR = [
                    [[100,1200,700,100]],
                    [[100,1200,700,100]],
                    [[100,1200,700,100]],
                    [[100,1200,700,100]],
                    [[700,1200,100,100]],
                    [[700,1200,100,100]]]
                setting._TARGETROI = [
                    [[0,0,900,1600],[0,0,900,800],[500,0,400,1600],],
                    'default',
                    'default',
                    'default',
                    [[0,0,900,1600],[0,0,900,800]],
                    'default']
                StreetFarm(setting)
            case "[任务]7000G":
                setting._FARMTARGET = '7000G'
                QuestFarm(setting)
            case "[刷图]鸟洞三层 fordraig B3F":
                setting._FARMTARGET = 'fordraig-B3F'
                setting._TARGETLIST = ['chest','harken']
                setting._TARGETSEARCHDIR = [None,[[100,1200,700,100],[700,800,100,800],[400,100,400,1200],[100,800,700,800],[400,1200,400,100],]]
                StreetFarm(setting)
            case "[刷图]要塞三层":
                setting._FARMTARGET = 'fortress-B3F'
                setting._TARGETLIST = ['chest','harken2']
                setting._TARGETSEARCHDIR = [
                    [[100,1200,700,100]],
                    [[100,1200,700,100]]]
                setting._TARGETROI = [
                    [[0,355,480,805],[320,1053,300,200]],
                    None]
                StreetFarm(setting)
            case "[任务]角鹫之剑 fordraig":
                setting._FARMTARGET = 'fordraig'
                QuestFarm(setting)
            case "[任务]击退敌势力":
                setting._FARMTARGET = 'repelEnemyForces'
                QuestFarm(setting)
            case "[任务]卢比肯-三牛":
                setting._FARMTARGET = 'LBC-oneGorgon'
                QuestFarm(setting)
            case "[任务]忍洞-金箱":
                setting._FARMTARGET = 'SSC-goldenchest'
                QuestFarm(setting)
            case _:
                logger.info(f"无效的任务名:{self.farm_target_var.get()}")
                self.finishingcallback()
                
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