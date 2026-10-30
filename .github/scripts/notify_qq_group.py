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
    QQ_BOT_AT_ALL        可选, true/false 强制开启或关闭 @所有人
                         不设置时: 正式版本 @所有人, beta 版本不 @
                         (要求机器人是群管理员, 每群每天仅 1 次; 失败会自动降级为普通消息)
    RELEASE_ZIP_PATH     可选, 发布包的本地路径; 设置后走分片上传 (推荐)
    RELEASE_ZIP_URL      可选, 发布包的公开下载地址; 没有本地文件时走 URL 上传
    QQ_BOT_SEND_FILE     可选, false 时不再发送群文件 (默认发送)

消息规则:
    - 版本号包含 beta  ->  "测试版本{版本号}已经发布!"
    - 正式版本         ->  CHANGES_LOG.md 中第一个 "###" 到第一个空行之间的内容
"""

import asyncio
import hashlib
import os
import re
import sys
import threading
import time
import urllib.request
from pathlib import Path

CHANGES_LOG = "CHANGES_LOG.md"
CONNECT_TIMEOUT_SECONDS = 90
# upload_prepare 的 md5_10m 字段: 文件前 10002432 字节的 MD5
MD5_PREFIX_BYTES = 10_002_432


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


def hash_file(path):
    """返回 (md5, sha1, 前 10MB 的 md5, 文件大小)。"""
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            md5.update(chunk)
            sha1.update(chunk)
    with open(path, "rb") as file:
        md5_prefix = hashlib.md5(file.read(MD5_PREFIX_BYTES))

    return md5.hexdigest(), sha1.hexdigest(), md5_prefix.hexdigest(), os.path.getsize(path)


def read_range(path, offset, size):
    with open(path, "rb") as file:
        file.seek(offset)
        return file.read(size)


def put_part(url, data, attempts=3):
    last_error = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url,
                data=data,
                method="PUT",
                headers={"Content-Type": "application/octet-stream"},
            )
            with urllib.request.urlopen(request, timeout=300) as response:
                response.read()
                if response.status >= 300:
                    raise RuntimeError(f"分片上传失败: HTTP {response.status}")
            return
        except Exception as error:  # noqa: BLE001
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(1)
    raise last_error


def main():
    version = os.environ.get("VERSION", "").strip()
    app_id = os.environ.get("QQ_BOT_APP_ID", "").strip()
    app_secret = os.environ.get("QQ_BOT_APP_SECRET", "").strip()
    group_openid = os.environ.get("QQ_BOT_GROUP_OPENID", "").strip()
    sandbox = os.environ.get("QQ_BOT_SANDBOX", "").strip().lower() in {"1", "true", "yes", "on"}

    at_all_setting = os.environ.get("QQ_BOT_AT_ALL", "").strip().lower()
    if at_all_setting in {"1", "true", "yes", "on"}:
        at_all = True
    elif at_all_setting in {"0", "false", "no", "off"}:
        at_all = False
    else:
        # 默认: 正式版本 @所有人, beta 版本不 @
        at_all = "beta" not in version.lower()

    release_zip_path = os.environ.get("RELEASE_ZIP_PATH", "").strip()
    release_zip_url = os.environ.get("RELEASE_ZIP_URL", "").strip()
    send_file_setting = os.environ.get("QQ_BOT_SEND_FILE", "").strip().lower()
    send_file = send_file_setting not in {"0", "false", "no", "off"} and bool(
        release_zip_path or release_zip_url
    )

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
        async def upload_group_file(self, path):
            """分片上传本地文件并直接发送到群聊。"""
            from botpy.http import Route

            file_name = os.path.basename(path)
            md5_hex, sha1_hex, md5_prefix_hex, file_size = await asyncio.to_thread(hash_file, path)
            log(f"开始分片上传群文件: {file_name} ({file_size} bytes)")

            prepare = await self.api._http.request(
                Route("POST", "/v2/groups/{group_openid}/upload_prepare", group_openid=group_openid),
                json={
                    "file_type": 4,
                    "file_size": str(file_size),
                    "file_name": file_name,
                    "md5": md5_hex,
                    "sha1": sha1_hex,
                    "md5_10m": md5_prefix_hex,
                },
            )

            upload_id = prepare["upload_id"]
            default_block_size = int(prepare["block_size"])
            parts = sorted(prepare["parts"], key=lambda part: part["index"])
            log(f"upload_id={upload_id}, 分片数={len(parts)}")

            offset = 0
            for part in parts:
                size = int(part.get("block_size") or default_block_size)
                data = await asyncio.to_thread(read_range, path, offset, size)
                part_md5 = hashlib.md5(data).hexdigest()
                await asyncio.to_thread(put_part, part["presigned_url"], data)
                await self.api._http.request(
                    Route(
                        "POST",
                        "/v2/groups/{group_openid}/upload_part_finish",
                        group_openid=group_openid,
                    ),
                    json={
                        "upload_id": upload_id,
                        "part_index": part["index"],
                        "block_size": str(len(data)),
                        "md5": part_md5,
                    },
                )
                offset += len(data)
                log(f"分片 {part['index'] + 1}/{len(parts)} 完成")

            return await self.api._http.request(
                Route("POST", "/v2/groups/{group_openid}/files", group_openid=group_openid),
                json={
                    "file_type": 4,
                    "file_name": file_name,
                    "upload_id": upload_id,
                    "srv_send_msg": True,
                },
            )

        async def on_ready(self):
            async def send(content):
                await self.api.post_group_message(
                    group_openid=group_openid,
                    msg_type=0,
                    content=content,
                )

            try:
                if at_all:
                    try:
                        # 每天每群只能 @所有人 一次, 失败时降级为普通消息
                        await send(f"<qqbot-at-everyone />\n{message}")
                        log("QQ 群通报发送成功 (已 @所有人)")
                    except Exception as error:  # noqa: BLE001
                        log(f"带 @所有人 发送失败 ({error}), 2 秒后改为不带 @所有人 重发")
                        await asyncio.sleep(2)
                        await send(message)
                        log("QQ 群通报发送成功 (未 @所有人)")
                else:
                    await send(message)
                    log("QQ 群通报发送成功")
            except Exception as error:  # noqa: BLE001
                log(f"QQ 群通报失败: {error}")
                code = 1
            else:
                code = 0

                # 发送群文件, 失败不影响文字通报
                if send_file:
                    try:
                        if release_zip_path and os.path.exists(release_zip_path):
                            await self.upload_group_file(release_zip_path)
                            log("群文件发送成功 (分片上传)")
                        elif release_zip_url:
                            # URL 上传依赖 QQ 服务器下载该地址, 部分地址会报 40093007
                            await self.api.post_group_file(
                                group_openid=group_openid,
                                file_type=4,
                                url=release_zip_url,
                                srv_send_msg=True,
                            )
                            log("群文件发送成功 (URL 上传)")
                        else:
                            log(f"跳过群文件: 本地文件不存在 ({release_zip_path})")
                    except Exception as error:  # noqa: BLE001
                        log(f"群文件发送失败 (文字通报已发送): {error}")

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
