#!/usr/bin/env python3
"""发布版本通报到 QQ 群（QQ 机器人开放平台）。

由 GitHub Actions 在构建成功后调用。
QQ 官方要求：发送主动群消息时机器人必须保持 WebSocket 在线，
因此本脚本会先用 qq-botpy 连接机器人服务，在 on_ready 里发送消息后退出。

环境变量:
    QQ_BOT_APP_ID        机器人 AppID       (开放平台 -> 开发设置)
    QQ_BOT_APP_SECRET    机器人 AppSecret   (开放平台 -> 开发设置)
    QQ_BOT_GROUP_OPENID  目标群的 group_openid
    VERSION              本次发布的版本号 (来自 src/main.py 的 __version__)
    QQ_BOT_SANDBOX       可选, true 时连接沙箱环境 (机器人未上线时使用)

消息规则:
    - 版本号包含 beta  ->  "测试版本{版本号}已经发布!"
    - 正式版本         ->  CHANGES_LOG.md 中第一个 "###" 到第一个空行之间的内容
"""

import os
import re
import sys
import threading
from pathlib import Path

CHANGES_LOG = "CHANGES_LOG.md"
CONNECT_TIMEOUT_SECONDS = 90


def log(message):
    print(message, flush=True)


# Windows runner 的控制台编码不一定是 UTF-8, 避免打印中文时报错
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def warn(message):
    log(f"::warning::{message}")


def build_message(version):
    """根据版本类型生成通报内容。"""
    if "beta" in version.lower():
        return f"测试版本{version}已经发布!"

    text = Path(CHANGES_LOG).read_text(encoding="utf-8-sig")

    # 第一个 "###" 标题所在的整行
    header = re.search(r"^###[ \t]*(.+?)[ \t]*$", text, re.MULTILINE)
    if not header:
        raise RuntimeError(f"{CHANGES_LOG} 中找不到 '###' 开头的版本标题")

    # 从标题之后到第一个空行为止
    end = text.find("\n\n", header.end())
    if end == -1:
        end = len(text)
    body = text[header.end():end]

    lines = [line.rstrip() for line in body.splitlines()]
    lines = [line for line in lines if line.strip()]

    # QQ 群消息是纯文本, 去掉 markdown 标题符号, 保留版本号
    return "\n".join([header.group(1).strip(), *lines])


def main():
    version = os.environ.get("VERSION", "").strip()
    app_id = os.environ.get("QQ_BOT_APP_ID", "").strip()
    app_secret = os.environ.get("QQ_BOT_APP_SECRET", "").strip()
    group_openid = os.environ.get("QQ_BOT_GROUP_OPENID", "").strip()
    sandbox = os.environ.get("QQ_BOT_SANDBOX", "").strip().lower() in {"1", "true", "yes", "on"}

    missing = [
        name
        for name, value in (
            ("VERSION", version),
            ("QQ_BOT_APP_ID", app_id),
            ("QQ_BOT_APP_SECRET", app_secret),
            ("QQ_BOT_GROUP_OPENID", group_openid),
        )
        if not value
    ]
    if missing:
        warn(f"缺少环境变量/Secret: {', '.join(missing)}, 跳过 QQ 群通报")
        return 0

    try:
        message = build_message(version)
    except Exception as error:  # noqa: BLE001 - CI 中需要打印完整原因
        log(f"生成通报内容失败: {error}")
        return 1

    log("----- 即将发送的通报内容 -----")
    log(message)
    log("-----------------------------")

    try:
        import botpy
    except ImportError:
        log("未安装 qq-botpy, 请先执行: python -m pip install qq-botpy")
        return 1

    class NotifyClient(botpy.Client):
        async def on_ready(self):
            try:
                await self.api.post_group_message(
                    group_openid=group_openid,
                    msg_type=0,
                    content=message,
                )
                log("QQ 群通报发送成功")
                code = 0
            except Exception as error:  # noqa: BLE001
                log(f"QQ 群通报失败: {error}")
                code = 1
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(code)

    def on_timeout():
        log(f"QQ 群通报失败: 连接 QQ 机器人服务超时 ({CONNECT_TIMEOUT_SECONDS}s)")
        sys.stdout.flush()
        os._exit(1)

    timer = threading.Timer(CONNECT_TIMEOUT_SECONDS, on_timeout)
    timer.daemon = True
    timer.start()

    client = NotifyClient(
        intents=botpy.Intents(public_messages=True),
        is_sandbox=sandbox,
        bot_log=False,
    )

    try:
        client.run(appid=app_id, secret=app_secret)
    except Exception as error:  # noqa: BLE001
        log(f"QQ 群通报失败: 连接机器人服务出错: {error}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
