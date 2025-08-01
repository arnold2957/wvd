import signal
import sys
import os
import logging
import argparse
from threading import Thread,Event

# 設置無頭模式環境變數
os.environ['WVD_HEADLESS'] = '1'

try:
    from gui import __version__, FarmConfig, LoadConfigFromFile, CONFIG_VAR_LIST, Factory
except ImportError:
    # 如果直接導入失敗，嘗試從 src 目錄導入
    sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

    from gui import __version__, FarmConfig, LoadConfigFromFile, CONFIG_VAR_LIST, Factory

def signal_handler(sig, frame):
    # 這邊目前沒啥用，thread卡住進不來...
    print('\n收到 Ctrl+C，準備結束...')
    # 通知 thread 結束
    global setting
    if setting and hasattr(setting, "_FORCESTOPING"):
        setting._FORCESTOPING.set()

# 解析命令列參數
def parse_args():
    parser = argparse.ArgumentParser(description='巫術 Daphne 自動刷怪程式（無頭模式）')
    parser.add_argument('-c', '--config', 
                      help='指定配置檔案路徑（預設：config.json）',
                      default=None)
    return parser.parse_args()

def main():
    # 解析命令列參數
    args = parse_args()
    
    setting = FarmConfig()
    config = LoadConfigFromFile(args.config or 'config.json')
    for attr_name, var_type, var_config_name, var_default_value in CONFIG_VAR_LIST:
        setattr(setting, var_config_name, config[var_config_name])
        
    setting._FORCESTOPING = Event()
    setting._FINISHINGCALLBACK = lambda: logger.info("已中断.")
    
    Farm = Factory()
    thread = Thread(target=Farm,args=(setting, ))
    thread.start()
    
    logger = logging.getLogger("WvDASLogger")
    logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 確保 print 輸出不被重定向
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
        
    logger.info(f"目标地下城:{setting._FARMTARGET_TEXT}")
    
    thread.join()
    
if __name__ == "__main__":
    # signal.signal(signal.SIGINT, signal_handler)
    try:
        print("正在啟動無頭模式...")
        print("按 Ctrl+C 可以停止程式")
        print("**********************************")
        main()
    except KeyboardInterrupt:
        print("程式已被使用者中斷")
    except Exception as e:
        print(f"程式執行時發生錯誤：{str(e)}")
    # finally:
    #     input("\n按 Enter 鍵結束程式...")