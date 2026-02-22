import tkinter as tk
from quest_manager import quest_manager


CONFIG_VAR_LIST = [
            #var_name,                      type,          config_name,                  default_value
            ["farm_target_text_var",        tk.StringVar,  "_FARMTARGET_TEXT",           quest_manager.get_all_quest_codes()[0] if quest_manager.get_all_quest_codes() else ""],
            ["farm_target_var",             tk.StringVar,  "_FARMTARGET",                ""],
            # ["randomly_open_chest_var",     tk.BooleanVar, "_SMARTDISARMCHEST",          False],
            ["randomly_open_chest_var",     tk.BooleanVar, "_QUICKDISARMCHEST",          False],
            ["who_will_open_it_var",        tk.IntVar,     "_WHOWILLOPENIT",             0],
            ["skip_recover_var",            tk.BooleanVar, "_SKIPCOMBATRECOVER",         False],
            ["skip_chest_recover_var",      tk.BooleanVar, "_SKIPCHESTRECOVER",          False],
            ["system_auto_combat_var",      tk.BooleanVar, "_SYSTEMAUTOCOMBAT",          False],
            ["aoe_once_var",                tk.BooleanVar, "_AOE_ONCE",                  False],
            ["custom_aoe_time_var",         tk.IntVar,     "_AOE_TIME",                  1],
            ["auto_after_aoe_var",          tk.BooleanVar, "_AUTO_AFTER_AOE",            False],
            ["active_rest_var",             tk.BooleanVar, "_ACTIVE_REST",               True],
            ["active_royalsuite_rest_var",  tk.BooleanVar, "_ACTIVE_ROYALSUITE_REST",    False],
            ["active_triumph_var",          tk.BooleanVar, "_ACTIVE_TRIUMPH",            False],
            ["active_beautiful_ore_var",    tk.BooleanVar, "_ACTIVE_BEAUTIFUL_ORE",      False],
            ["active_beg_money_var",        tk.BooleanVar, "_ACTIVE_BEG_MONEY",          True],
            ["rest_intervel_var",           tk.IntVar,     "_RESTINTERVEL",              1],
            ["karma_adjust_var",            tk.StringVar,  "_KARMAADJUST",               "+0"],
            ["emu_path_var",                tk.StringVar,  "_EMUPATH",                   ""],
            ["emu_index_var",               tk.IntVar,     "_EMUIDX",                    0],
            ["adb_port_var",                tk.StringVar,  "_ADBPORT",                   5555],
            ["last_version",                tk.StringVar,  "LAST_VERSION",               ""],
            ["latest_version",              tk.StringVar,  "LATEST_VERSION",             None],
            ["_spell_skill_config_internal",list,          "_SPELLSKILLCONFIG",          []],
            ["active_csc_var",              tk.BooleanVar, "ACTIVE_CSC",                 True],
            ["last_config_name_var",        str,           "LAST_CONFIG_NAME",           ""]
            ]
