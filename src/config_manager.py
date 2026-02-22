import os
import json
from utils import LoadJson, logger
from config_vars import CONFIG_VAR_LIST

GLOBAL_CONFIG_FILE_PATH = "config.json"
GLOBAL_CONFIG_KEYS = [
    "_KARMAADJUST",
    "_EMUPATH",
    "_EMUIDX",
    "_ADBPORT",
    "LAST_VERSION",
    "LATEST_VERSION",
    "LAST_CONFIG_NAME",
]
TASK_CONFIG_FILES_DIR = "config"


class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.global_config = {}  # 存储全局配置的
        self.current_config = {}  # 仅存储当前任务配置的
        self.config_files = []

        # 读取工作目录下的 config.json 文件
        config_json_path = os.path.join(os.getcwd(), GLOBAL_CONFIG_FILE_PATH)
        self.global_config = LoadJson(config_json_path)

        # 获取工作目录下 config 子目录中所有 .json 文件的列表
        self._load_config_files()

        # 根据 global_config 的 last_config_name_var 读取对应的配置到 current_config
        self._load_last_config()

        self._initialized = True

    def _load_last_config(self):
        """根据 global_config 的 last_config_name_var 读取对应的配置到 current_config"""
        last_config_name = self.global_config.get("LAST_CONFIG_NAME", "")

        # 如果指定了最后使用的配置文件且存在，则加载它
        if last_config_name and last_config_name in self.config_files:
            self.load_config_file(last_config_name)
        # 否则如果有配置文件，则加载第一个
        elif self.config_files:
            first_config_name = self.config_files[0]
            self.load_config_file(first_config_name)
            # 更新 global_config 中的 LAST_CONFIG_NAME
            self.global_config["LAST_CONFIG_NAME"] = first_config_name
            # 保存到 config.json
            self.save_global_config()

    def create_default_config_file(self, file_name="new"):
        """以默认配置文件创建一个新的配置文件"""
        config_dir = os.path.join(os.getcwd(), TASK_CONFIG_FILES_DIR)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        # 使用CONFIG_VAR_LIST生成默认配置
        new_config = {}
        for attr_name, var_type, var_config_name, var_default_value in CONFIG_VAR_LIST:
            new_config[var_config_name] = var_default_value

        # 生成配置文件
        config_file_path = os.path.join(config_dir, f"{file_name}.json")
        result = SaveConfig(new_config, config_file_path)
        if result:
            logger.info(f"新配置文件 {file_name}.json 已创建。")
        else:
            logger.error(f"创建新配置文件 {file_name}.json 失败。")

        return result

    def _load_config_files(self):
        """加载 config 子目录中的所有 .json 文件列表"""
        config_dir = os.path.join(os.getcwd(), TASK_CONFIG_FILES_DIR)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        self.config_files = []
        if os.path.exists(config_dir):
            for file in os.listdir(config_dir):
                if file.endswith(".json"):
                    self.config_files.append(os.path.splitext(file)[0])

        # 如果没有任何配置文件存在
        if not self.config_files:
            # 照顾老用户，如果有以前的配置，则复制该配置为new，否则使用默认值生成
            import shutil
            src_file = os.path.join(os.getcwd(), GLOBAL_CONFIG_FILE_PATH)
            dst_file = os.path.join(os.getcwd(), TASK_CONFIG_FILES_DIR, "new.json")
            if os.path.exists(src_file):
                shutil.copy(src_file, dst_file)
                # 添加到配置文件列表
                self.config_files.append("new")
            else:
                # 如果源文件不存在，使用默认值生成
                if self.create_default_config_file("new"):
                    # 添加到配置文件列表
                    self.config_files.append("new")

    def get_config_files(self):
        return self.config_files

    def load_config_file(self, config_name):
        """加载指定名称的配置文件"""
        config_file_path = os.path.join(
            os.getcwd(), TASK_CONFIG_FILES_DIR, f"{config_name}.json"
        )
        if os.path.exists(config_file_path):
            try:
                with open(config_file_path, "r", encoding="utf-8") as f:
                    self.current_config = json.load(f)
                return self.current_config
            except Exception as e:
                logger.error(f"读取配置文件 {config_name}.json 失败: {e}")
                return {}
        return {}

    def save_global_config(self):
        """保存 global_config 到 config.json"""
        config_json_path = os.path.join(os.getcwd(), GLOBAL_CONFIG_FILE_PATH)
        result = SaveConfig(self.global_config, config_json_path)
        if result:
            logger.info("全局配置已保存。")
        else:
            logger.error("保存全局配置失败。")
        return result

    def save_current_config(self, config_name=None):
        """保存当前配置到指定名称的文件"""
        if not config_name:
            config_name = self.global_config.get("LAST_CONFIG_NAME", "")

        if not config_name:
            logger.error("保存当前配置失败：未指定配置名称")
            return False

        config_file_path = os.path.join(
            os.getcwd(), TASK_CONFIG_FILES_DIR, f"{config_name}.json"
        )
        result = SaveConfig(self.current_config, config_file_path)
        if result:
            logger.info(f"配置 {config_name} 已保存。")
        else:
            logger.error(f"保存配置 {config_name} 失败。")
        return result

    def save_all_configs(self, config_name=None):
        global_saved = self.save_global_config()
        current_saved = self.save_current_config(config_name)
        return global_saved and current_saved

    def get_combined_config(self):
        """获取组合配置数据：GLOBAL_CONFIG_KEYS 里有的从 global 里出，没有的从 current 里出"""
        combined_config = {}

        # 首先从 current_config 中获取所有配置
        combined_config.update(self.current_config)

        # 然后用 global_config 中 GLOBAL_CONFIG_KEYS 里的配置覆盖
        for key in GLOBAL_CONFIG_KEYS:
            if key in self.global_config:
                combined_config[key] = self.global_config[key]

        return combined_config

    def save_single_config(self, key, value):
        """保存单个配置属性"""
        # 判断是否是全局配置
        if key in GLOBAL_CONFIG_KEYS:
            self.global_config[key] = value
            return self.save_global_config()
        else:
            self.current_config[key] = value
            return self.save_current_config()

    def save_config_dict(self, config_dict):
        """保存配置字典，按 GLOBAL_CONFIG_KEYS 分配到 global 和 current"""
        # 分离配置到 global 和 current
        global_update = {}
        current_update = {}

        for key, value in config_dict.items():
            if key in GLOBAL_CONFIG_KEYS:
                global_update[key] = value
            else:
                current_update[key] = value

        # 更新并保存
        if global_update:
            self.global_config.update(global_update)
            global_saved = self.save_global_config()
        else:
            global_saved = True

        if current_update:
            self.current_config.update(current_update)
            current_saved = self.save_current_config()
        else:
            current_saved = True

        return global_saved and current_saved

    def switch_config(self, config_name):
        """切换配置文件并更新 LAST_CONFIG_NAME"""
        if config_name in self.config_files:
            # 加载选择的配置文件
            self.load_config_file(config_name)
            # 更新全局配置中的最后使用的配置名称
            self.global_config["LAST_CONFIG_NAME"] = config_name
            # 保存全局配置
            return self.save_global_config()
        return False

    def get_last_config_name(self):
        """获取当前的 LAST_CONFIG_NAME"""
        return self.global_config.get("LAST_CONFIG_NAME", "")

    def refresh_config_files(self):
        """刷新配置文件列表并重新加载最后使用的配置"""
        # 重新加载配置文件列表
        self._load_config_files()

        # 重新加载最后使用的配置
        self._load_last_config()

        return self.config_files


def SaveConfig(config_data, config_file_path):
    try:
        with open(config_file_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        return False

config_manager = ConfigManager()
