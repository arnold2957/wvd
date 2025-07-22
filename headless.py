import sys
import os
import logging
import argparse
from threading import Thread,Event

# 設置無頭模式環境變數
os.environ['WVD_HEADLESS'] = '1'

# 解析命令列參數
def parse_args():
    parser = argparse.ArgumentParser(description='巫術 Daphne 自動刷怪程式（無頭模式）')
    parser.add_argument('-c', '--config', 
                      help='指定配置檔案路徑（預設：config.json）',
                      default=None)
    return parser.parse_args()

try:
    from gui import __version__
    from script import *
    from utils import *
except ImportError:
    # 如果直接導入失敗，嘗試從 src 目錄導入
    sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
    from gui import __version__
    from script import *
    from utils import *

def main():
    # 解析命令列參數
    args = parse_args()
    
    try:
        # 設置日誌
        logger = logging.getLogger("wvd_headless")
        logger.setLevel(logging.INFO)
        # 添加控制台處理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # 確保 print 輸出不被重定向
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        
        logger.info(f"WvDAS 巫术daphne自动刷怪 v{__version__} @德德Dellyla(B站)")
        logger.info("**********************************")
        logger.info(f"当前版本: {__version__}")
        logger.info("遇到问题? 请访问:" )
        logger.info("https://github.com/arnold2957/wvd")
        logger.info("或加入Q群: 922497356.", extra={"summary": True})
        logger.info("**********************************")

        # 載入設定
        config = LoadConfigFromFile(args.config)
        if not config:
            logger.error("無法載入設定檔 config.json，請確認檔案存在且格式正確。")
            sys.exit(1)
        logger.info("設定內容：%s", config)
        logger.info("**********************************")

        # 建立設定物件
        setting = init_setting(config)
        setting._LOGGER = logger

        # 檢查必要設定
        if not setting._ADBPATH:
            logger.error("未設定 ADB 路徑，請在 config.json 中設定 ADB_PATH。")
            sys.exit(1)

        # 目標副本
        farm_target = config.get("_FARMTARGET", "")
        if not farm_target:
            logger.error("未設定目標副本，請在 config.json 中設定 _FARMTARGET。")
            sys.exit(1)
        logger.info("目標副本：%s", farm_target)

        # 啟動ADB
        logger.info("正在啟動 ADB 服務...")
        if not StartAdbServer(setting):
            logger.error("ADB 啟動失敗，請檢查設定。")
            sys.exit(1)
        setting._ADBDEVICE = CreateAdbDevice(setting)
        if not setting._ADBDEVICE:
            logger.error("ADB 設備連接失敗。")
            sys.exit(1)
        logger.info("ADB 服務啟動成功")

        # 根據目標啟動對應流程
        init_farming(farm_target, setting)
        
    except Exception as e:
        logger.error(f"執行過程中發生錯誤：{str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

def init_setting(config):

    # 建立設定物件
    setting = FarmSetting()
    setting._SYSTEMAUTOCOMBAT = config.get("SYSTEM_AUTO_COMBAT_ENABLED", False)
    setting._RANDOMLYOPENCHEST = config.get("_RANDOMLYOPENCHEST", False)
    setting._WHOWILLOPENIT = config.get("_WHOWILLOPENIT", 0)
    setting._SKIPCOMBATRECOVER = config.get("_SKIPCOMBATRECOVER", False)
    setting._SKIPCHESTRECOVER = config.get("_SKIPCHESTRECOVER", False)
    setting._SPELLSKILLCONFIG = config.get("_SPELLSKILLCONFIG", [])
    setting._AOE_ONCE = config.get("AOE_ONCE", False)
    setting._AUTO_AFTER_AOE = config.get("AUTO_AFTER_AOE", False)
    setting._ACTIVE_REST = config.get("ACTIVE_REST", True)
    setting._RESTINTERVEL = int(config.get("_RESTINTERVEL", 0))
    setting._KARMAADJUST = str(config.get("_KARMAADJUST", "+0"))
    setting._ADBPATH = config.get("ADB_PATH", "")
    setting._ADBPORT = config.get("ADB_PORT", 5555)
    setting._FORCESTOPING = Event()
    
    return setting

# 此區需 copy 最新版，考慮請owner獨立方法
def init_farming(farm_target, setting):
    StreetFarm, QuestFarm = Factory()
    match farm_target:
        case "[宝箱]水路船一 shiphold":
            setting._FARMTARGET = 'shiphold'
            setting._TARGETLIST = ['chest','harken']
            StreetFarm(setting)
        case "[宝箱]水路船二 lounge":
            setting._FARMTARGET = 'shiphold'
            setting._TARGETINFOLIST = [
                TargetInfo('up_stair',  "左上", [292,394],),
                TargetInfo('chest',     "左上", [[0,0,900,739],[0,529,212,106]],),
                TargetInfo('down_stair',"左上", [292,394],),
                TargetInfo('harken',    None  , None),
                ]
            StreetFarm(setting)
        case "[宝箱]水路一号街":
            setting._FARMTARGET = 'Dist'
            setting._TARGETINFOLIST = [
                TargetInfo('chest'),
                TargetInfo('harken'),
                ]
            StreetFarm(setting)
        case "[矿石]土洞(5-9)":
            setting._FARMTARGET = 'DOE'
            setting._TARGETINFOLIST = [
                TargetInfo("position", "右下", [713,1027]),
                TargetInfo("DOE_quit", "右下", ),
                ]
            setting._SYSTEMAUTOCOMBAT = True
            StreetFarm(setting)
        case "[矿石]风洞(15-19)":
            setting._FARMTARGET = 'DOW'
            setting._TARGETINFOLIST = [
                TargetInfo('chest',    [[700,1200,100,100]], [[0,780,900,500],[0,780,150,120]],),
                TargetInfo('DOW_quit', [[700,1200,100,100]], None),
                ]
            setting._SYSTEMAUTOCOMBAT = True
            StreetFarm(setting)
        case "[矿石]火洞(10-14)":
            setting._FARMTARGET = 'DOF'
            setting._TARGETINFOLIST = [
                TargetInfo('position','左下',[347,866]),
                TargetInfo('position','左下',[400,1183]),
                TargetInfo('DOF_quit'),
                ]
            setting._SYSTEMAUTOCOMBAT = True
            StreetFarm(setting)
        case "[矿石]光洞(15-19)":
            setting._FARMTARGET = 'DOL'
            setting._TARGETINFOLIST = [
                TargetInfo('chest',    [[700,100,100,1200]], [[420,686,478,481]]),
                TargetInfo('DOL_quit', [[700,100,100,1200]], None),
                ]
            StreetFarm(setting)
        case "[宝箱]卢比肯 宝箱":
            setting._FARMTARGET = 'LBC'
            setting._TARGETINFOLIST = [
                TargetInfo('chest'),
                TargetInfo('LBC/LBC_quit'),
                ]
            StreetFarm(setting)
        case "[金币]7000G":
            setting._FARMTARGET = '7000G'
            QuestFarm(setting)
        case "[宝箱]鸟洞三层 fordraig B3F":
            setting._FARMTARGET = 'fordraig-B3F'
            setting._TARGETINFOLIST = [
                TargetInfo('chest',  None),
                TargetInfo('harken', [[100,1200,700,100],[700,800,100,800],[400,100,400,1200],[100,800,700,800],[400,1200,400,100],]),
                ]
            StreetFarm(setting)
        case "[宝箱]要塞三层":
            setting._FARMTARGET = 'fortress-B3F'
            setting._TARGETINFOLIST = [
                TargetInfo('chest',  [[100,1200,700,100]], [[0,355,480,805],[320,1053,300,200]]),
                TargetInfo('harken2',[[100,1200,700,100]], None),
                ]
            StreetFarm(setting)
        case "[宝箱]忍洞一层 刷怪":
            setting._FARMTARGET = 'SSC'
            setting._TARGETINFOLIST = [
                TargetInfo('position', '左下', [400,974]),
                TargetInfo('position', '左下', [560,438]),
                TargetInfo('position', '左下', [399,654]),
                TargetInfo('position', '左下', [81,226]),
                TargetInfo('position', '右下', [766,1078]),
                TargetInfo('SSC/SSC_quit','右下', 'default'),
                ]
            StreetFarm(setting)
        case "[任务]角鹫之剑 fordraig":
            setting._FARMTARGET = 'fordraig'
            QuestFarm(setting)
        case "[经验]击退敌势力":
            setting._FARMTARGET = 'repelEnemyForces'
            QuestFarm(setting)
        case "[任务]卢比肯 三牛":
            setting._FARMTARGET = 'LBC-oneGorgon'
            QuestFarm(setting)
        case "[任务]忍洞一层 金箱":
            setting._FARMTARGET = 'SSC-goldenchest'
            QuestFarm(setting)
        case _:
            logger.error(f"无效的任务名：{farm_target}")
            sys.exit(1)

if __name__ == "__main__":
    try:
        print("正在啟動無頭模式...")
        print("按 Ctrl+C 可以停止程式")
        print("**********************************")
        main()
    except KeyboardInterrupt:
        print("\n程式已被使用者中斷")
    except Exception as e:
        print(f"\n程式執行時發生錯誤：{str(e)}")
    finally:
        input("\n按 Enter 鍵結束程式...")