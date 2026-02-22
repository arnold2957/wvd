import json
import os
from utils import LoadJson, ResourcePath

QUEST_FILE = 'resources/quest/quest.json'

class QuestManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(QuestManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
       
        self.reload_quest_data()
        self._initialized = True

    def reload_quest_data(self):
        self._quest_reflect_map = {}
        self._quest_data = {}
        self._error_logs = []
        self._load_builtin_quest_data()
        self._load_custom_quest_data()

    def _load_builtin_quest_data(self):
        """读取内置任务数据"""
        try:
            data = LoadJson(ResourcePath(QUEST_FILE))
            
            seen_names = set(self._quest_reflect_map.keys())
            
            for quest_code, quest_info in data.items():
                if "questName" not in quest_info:
                    error_msg = f"★　内置任务代码 '{quest_code}' 缺少 'questName' 属性"
                    self._error_logs.append(error_msg)
                    continue
                
                quest_name = quest_info["questName"]
                
                # 检查任务代码是否重复
                if quest_code in self._quest_data:
                    error_msg = f"★　内置任务数据发现重复的任务代码: '{quest_code}'"
                    self._error_logs.append(error_msg)
                    continue
                
                # 检查名称是否重复
                if quest_name in seen_names:
                    error_msg = f"★　内置任务数据发现重复的任务名称: '{quest_name}'，已有的任务代码 '{self._quest_reflect_map[quest_name]}'，当前出错任务代码 '{quest_code}'"
                    self._error_logs.append(error_msg)
                    continue
                
                # 添加数据
                self._quest_reflect_map[quest_name] = quest_code
                seen_names.add(quest_name)
                self._quest_data[quest_code] = quest_info

        except json.JSONDecodeError as e:
            error_msg = f"内置任务数据 JSON 解析错误，第 {e.lineno} 行，第 {e.colno} 列: {e.msg}"
            self._error_logs.append(error_msg)
        except FileNotFoundError as e:
            error_msg = f"内置任务数据文件未找到: {e}"
            self._error_logs.append(error_msg)

    def _load_custom_quest_data(self):
        """读取自定义任务数据"""
        try:
            custom_quest_dir = os.path.join(os.getcwd(), "quest")
            if not os.path.exists(custom_quest_dir):
                os.makedirs(custom_quest_dir)
                return
            
            seen_names = set(self._quest_reflect_map.keys())
            
            # 遍历quest目录下的所有json文件
            for file_name in os.listdir(custom_quest_dir):
                if file_name.endswith(".json"):
                    file_path = os.path.join(custom_quest_dir, file_name)
                    try:
                        data = LoadJson(file_path)
                        
                        for quest_code, quest_info in data.items():
                            if "questName" not in quest_info:
                                error_msg = f"★　自定义任务文件 '{file_name}' 中的任务代码 '{quest_code}' 缺少 'questName' 属性"
                                self._error_logs.append(error_msg)
                                continue
                            
                            quest_name = quest_info["questName"]
                            
                            # 检查任务代码是否重复
                            if quest_code in self._quest_data:
                                error_msg = f"★　自定义任务文件 '{file_name}' 中发现重复的任务代码: '{quest_code}'"
                                self._error_logs.append(error_msg)
                                continue
                            
                            if quest_name in seen_names:
                                error_msg = f"★　自定义任务文件 '{file_name}' 中发现重复的任务名称: '{quest_name}'，已有的任务代码 '{self._quest_reflect_map[quest_name]}'，当前出错任务代码 '{quest_code}'"
                                self._error_logs.append(error_msg)
                                continue
                            
                            self._quest_reflect_map[quest_name] = quest_code
                            seen_names.add(quest_name)
                            self._quest_data[quest_code] = quest_info
                    except json.JSONDecodeError as e:
                        error_msg = f"自定义任务文件 '{file_name}' JSON解析错误，第 {e.lineno} 行，第 {e.colno} 列: {e.msg}"
                        self._error_logs.append(error_msg)
                    except Exception as e:
                        error_msg = f"读取自定义任务文件 '{file_name}' 时出错: {str(e)}"
                        self._error_logs.append(error_msg)
        except Exception as e:
            error_msg = f"读取自定义任务数据时出错: {str(e)}"
            self._error_logs.append(error_msg)

    def get_quest_map(self):
        """获取任务名称到任务代码的映射表"""
        return self._quest_reflect_map

    def get_error_logs(self):
        """获取加载时的错误日志列表"""
        return self._error_logs

    def get_all_quest_codes(self):
        """获取所有任务代码列表"""
        return list(self._quest_data.keys())

    def get_all_quest_names(self):
        """获取所有任务名称列表"""
        return list(self._quest_reflect_map.keys())
    
    def get_quest_by_name(self, quest_name):
        """根据任务名称获取任务数据"""
        quest_code = self._quest_reflect_map.get(quest_name, None)
        if quest_code:
            return self._quest_data.get(quest_code, None)
        return None

    def get_quest_by_code(self, quest_code):
        """根据任务代码获取任务数据"""
        return self._quest_data.get(quest_code, None)

quest_manager = QuestManager()
