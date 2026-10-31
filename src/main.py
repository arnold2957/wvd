from gui import *
from utils import HardExit

import argparse
import os
import queue
import subprocess
import sys
import threading
import time

__version__ = '3.2.0'
OWNER = "arnold2957"
REPO = "wvd"


class AppController:
    """应用控制器.

    不再继承 tk.Tk: 窗口由 gui.ConfigPanelApp 里的 pywebview 创建,
    后台消息队列由一个普通线程持续消费.
    """

    def __init__(self, headless, config_path):
        self.headless = headless
        self._stop = threading.Event()
        self.msg_queue = queue.Queue()
        self.main_window = None

        if not headless:
            self.main_window = ConfigPanelApp(__version__, self.msg_queue)
        else:
            HeadlessActive(config_path, self.msg_queue)

        self.quest_threading = None
        self.quest_setting = None

        self.is_checking_for_update = False
        self.updater = AutoUpdater(
            msg_queue=self.msg_queue,
            github_user=OWNER,
            github_repo=REPO,
            current_version=__version__,
        )

        self._queue_thread = threading.Thread(target=self._queue_loop, daemon=True)
        self._queue_thread.start()

        if not headless:
            self._schedule_thread = threading.Thread(
                target=self._schedule_periodic_update_check, daemon=True)
            self._schedule_thread.start()

    # ------------------------------------------------------------------
    def run(self):
        if self.headless:
            # 无头模式没有窗口, 主线程保持存活, 让任务线程继续运行.
            while not self._stop.is_set():
                self._stop.wait(1)
        else:
            self.main_window.run()  # webview.start(), 关闭所有窗口后返回
        HardExit(0)

    def _schedule_periodic_update_check(self):
        # 先让窗口完成首帧渲染, 避免更新检查与 WebView2 启动抢资源.
        self._stop.wait(3)
        while not self._stop.is_set():
            if not self.is_checking_for_update:
                self.is_checking_for_update = True
                try:
                    self.updater.check_for_updates()
                except Exception:
                    logger.exception("检查更新失败")
                finally:
                    self.is_checking_for_update = False
            self._stop.wait(1000)

    def switch_quest(self, target):
        """把当前任务切换为 target(FARM_TARGET), 并重启任务线程."""
        if self.quest_setting is None:
            return
        quest_name = QUEST_DATA.get(target, {}).get("questName", target)
        logger.info(f'切换任务到"{quest_name}"({target})...')
        self.quest_setting.FARM_TARGET = target
        self.quest_setting.FARM_TARGET_TEXT = quest_name
        self.quest_setting._COUNTERDUNG = 0
        for underscore in range(50):
            if self.quest_threading is None or not self.quest_threading.is_alive():
                Farm = Factory()
                self.quest_threading = threading.Thread(
                    target=Farm, args=(self.quest_setting,), daemon=True)
                self.quest_threading.start()
                break
            time.sleep(0.1)
        else:
            logger.error("旧任务线程仍在运行, 本次任务切换已取消.")
            return
        if self.main_window:
            self.main_window.turn_to_quest(target)

    # ------------------------------------------------------------------
    def _queue_loop(self):
        while not self._stop.is_set():
            try:
                message = self.msg_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self._handle_message(message)
            except Exception:
                logger.exception("处理后台消息失败")

    def _handle_message(self, message):
        command, value = message

        match command:
            case 'start_quest':
                self.quest_setting = value
                self.quest_setting._MSGQUEUE = self.msg_queue
                GlobalStopEvent.clear()
                Farm = Factory()
                self.quest_threading = threading.Thread(
                    target=Farm, args=(self.quest_setting,), daemon=True)
                self.quest_threading.start()
                logger.info(f'启动任务\"{self.quest_setting.FARM_TARGET_TEXT}\"...')

            case 'stop_quest':
                logger.info('停止任务...')
                if self.quest_threading and self.quest_threading.is_alive():
                    GlobalStopEvent.set()

            case 'switch_quest':
                self.switch_quest(value)

            case 'update_available':
                update_data = value
                version = update_data['version']
                if self.main_window:
                    self.main_window.show_update_notice(
                        version, self.updater.download)
                    self.main_window.save_config()

            case 'download_started':
                if self.main_window:
                    self.main_window.push_event(
                        {"type": "download_started", "total": value})

            case 'progress':
                if self.main_window:
                    self.main_window.push_event(
                        {"type": "download_progress", "value": value})

            case 'download_complete':
                if self.main_window:
                    self.main_window.push_event({"type": "download_complete"})

            case 'error':
                logger.error(str(value))
                if self.main_window:
                    self.main_window.push_event(
                        {"type": "error", "message": str(value)})

            case 'restart_ready':
                script_path = value
                if self.main_window:
                    self.main_window.push_event({"type": "restart_ready"})
                threading.Timer(1.2, lambda: self._restart(script_path)).start()

            case 'no_update_found':
                logger.debug("未发现更新。")

    @staticmethod
    def _restart(script_path):
        try:
            if sys.platform == "win32":
                subprocess.Popen([script_path], shell=True,
                                 creationflags=CREATE_NO_WINDOW)
            else:
                os.system(script_path)
        except Exception:
            logger.exception("重启失败")
        HardExit(0)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='WvDAS命令行参数')

    parser.add_argument(
        '-headless',
        '--headless',
        action='store_true',
        help='以无头模式运行程序',
    )

    parser.add_argument(
        '-config',
        '--config',
        type=str,
        default=None,
        help='配置文件路径 (例如: c:/config.json)',
    )

    return parser.parse_args()


def main():
    args = parse_args()

    controller = AppController(args.headless, args.config)
    controller.run()


def HeadlessActive(config_path, msg_queue):
    RegisterConsoleHandler()

    setting = FarmConfig()
    setting = LoadSettingFromDict(LoadConfig())
    msg_queue.put(('start_quest', setting))

    logger.info(f"WvDAS 巫术daphne自动刷怪 v{__version__} @德德Dellyla(B站)")


if __name__ == "__main__":
    main()
