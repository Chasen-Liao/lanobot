"""飞书/Lark 通道实现 - 使用 lark-oapi SDK 的 WebSocket 长连接"""
import asyncio
import json
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

from bus.events import OutboundMessage
from bus.queue import MessageBus
from bus.channels.base import BaseChannel

import importlib.util

FEISHU_AVAILABLE = importlib.util.find_spec("lark_oapi") is not None

# 消息类型显示映射
MSG_TYPE_MAP = {
    "image": "[图片]",
    "audio": "[语音]",
    "file": "[文件]",
    "sticker": "[表情包]",
}


# 飞书配置（简化版）
class FeishuConfig:
    """飞书/Lark 通道配置"""
    enabled: bool = False
    app_id: str = ""  # 飞书开放平台的应用 ID
    app_secret: str = ""  # 应用密钥
    encrypt_key: str = ""  # 事件订阅的加密密钥（可选）
    verification_token: str = ""  # 事件订阅的验证令牌（可选）
    allow_from: list[str] = []  # 允许的用户 open_ids
    react_emoji: str = "THUMBSUP"  # 消息反应表情


class FeishuChannel(BaseChannel):
    """
    使用 WebSocket 长连接的飞书/Lark 通道。

    通过 WebSocket 接收事件 - 无需公网 IP 或 webhook。

    需要：
    - 来自飞书开放平台的应用 ID 和应用密钥
    - 启用机器人能力
    - 启用事件订阅 (im.message.receive_v1)
    """

    name = "feishu"

    def __init__(self, config: FeishuConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: FeishuConfig = config
        self._client: Any = None
        self._ws_client: Any = None
        self._ws_thread: threading.Thread | None = None
        self._processed_message_ids: OrderedDict[str, None] = OrderedDict()
        self._loop: asyncio.AbstractEventLoop | None = None

    async def start(self) -> None:
        """使用 WebSocket 长连接启动飞书机器人"""
        if not FEISHU_AVAILABLE:
            print("[飞书] SDK 未安装。运行: pip install lark-oapi")
            return

        if not self.config.app_id or not self.config.app_secret:
            print("[飞书] app_id 和 app_secret 未配置")
            return

        import lark_oapi as lark
        self._running = True
        self._loop = asyncio.get_running_loop()

        # 创建用于发送消息的 Lark 客户端
        self._client = lark.Client.builder() \
            .app_id(self.config.app_id) \
            .app_secret(self.config.app_secret) \
            .log_level(lark.LogLevel.INFO) \
            .build()

        builder = lark.EventDispatcherHandler.builder(
            self.config.encrypt_key or "",
            self.config.verification_token or "",
        ).register_p2_im_message_receive_v1(
            self._on_message_sync
        )
        event_handler = builder.build()

        # 为长连接创建 WebSocket 客户端
        self._ws_client = lark.ws.Client(
            self.config.app_id,
            self.config.app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO
        )

        # 在单独的线程中启动 WebSocket 客户端并重连
        def run_ws():
            import time
            import lark_oapi.ws.client as _lark_ws_client
            ws_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(ws_loop)
            _lark_ws_client.loop = ws_loop
            try:
                while self._running:
                    try:
                        self._ws_client.start()
                    except Exception as e:
                        print(f"[飞书] WebSocket 错误: {e}")
                    if self._running:
                        time.sleep(5)
            finally:
                ws_loop.close()

        self._ws_thread = threading.Thread(target=run_ws, daemon=True)
        self._ws_thread.start()

        print("[飞书] 机器人已启动（WebSocket 长连接）")
        print("[飞书] 无需公网 IP - 使用 WebSocket 接收事件")

    async def stop(self) -> None:
        """停止飞书机器人"""
        self._running = False
        print("[飞书] 机器人已停止")

    async def send(self, msg: OutboundMessage) -> None:
        """通过飞书发送消息"""
        if not self._client:
            print("[飞书] 客户端未初始化")
            return

        try:
            receive_id_type = "chat_id" if msg.chat_id.startswith("oc_") else "open_id"
            loop = asyncio.get_running_loop()

            if msg.content and msg.content.strip():
                # 简单文本消息
                text_body = json.dumps({"text": msg.content.strip()}, ensure_ascii=False)
                await loop.run_in_executor(
                    None, self._send_message_sync,
                    receive_id_type, msg.chat_id, "text", text_body,
                )

        except Exception as e:
            print(f"[飞书] 发送消息错误: {e}")

    def _send_message_sync(self, receive_id_type: str, receive_id: str, msg_type: str, content: str) -> bool:
        """同步发送单条消息"""
        from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody
        try:
            request = CreateMessageRequest.builder() \
                .receive_id_type(receive_id_type) \
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(receive_id)
                    .msg_type(msg_type)
                    .content(content)
                    .build()
                ).build()
            response = self._client.im.v1.message.create(request)
            if not response.success():
                print(f"[飞书] 发送失败: code={response.code}, msg={response.msg}")
                return False
            return True
        except Exception as e:
            print(f"[飞书] 发送错误: {e}")
            return False

    def _on_message_sync(self, data: Any) -> None:
        """传入消息的同步处理程序（从 WebSocket 线程调用）"""
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._on_message(data), self._loop)

    async def _on_message(self, data: Any) -> None:
        """处理来自飞书的传入消息"""
        try:
            event = data.event
            message = event.message
            sender = event.sender

            # 去重检查
            message_id = message.message_id
            if message_id in self._processed_message_ids:
                return
            self._processed_message_ids[message_id] = None

            # 修剪缓存
            while len(self._processed_message_ids) > 1000:
                self._processed_message_ids.popitem(last=False)

            # 跳过机器人消息
            if sender.sender_type == "bot":
                return

            sender_id = sender.sender_id.open_id if sender.sender_id else "unknown"
            chat_id = message.chat_id
            chat_type = message.chat_type
            msg_type = message.message_type

            # 添加反应
            await self._add_reaction(message_id, self.config.react_emoji)

            # 解析内容
            content_parts = []

            try:
                content_json = json.loads(message.content) if message.content else {}
            except json.JSONDecodeError:
                content_json = {}

            if msg_type == "text":
                text = content_json.get("text", "")
                if text:
                    content_parts.append(text)
            else:
                content_parts.append(MSG_TYPE_MAP.get(msg_type, f"[{msg_type}]"))

            content = "\n".join(content_parts) if content_parts else ""

            if not content:
                return

            # 转发到消息总线
            reply_to = chat_id if chat_type == "group" else sender_id
            await self._handle_message(
                sender_id=sender_id,
                chat_id=reply_to,
                content=content,
                metadata={
                    "message_id": message_id,
                    "chat_type": chat_type,
                    "msg_type": msg_type,
                }
            )

        except Exception as e:
            print(f"[飞书] 处理消息错误: {e}")

    async def _add_reaction(self, message_id: str, emoji_type: str = "THUMBSUP") -> None:
        """添加反应表情（非阻塞）"""
        if not self._client:
            return

        try:
            from lark_oapi.api.im.v1 import CreateMessageReactionRequest, CreateMessageReactionRequestBody, Emoji

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                self._add_reaction_sync,
                message_id,
                emoji_type
            )
        except Exception as e:
            print(f"[飞书] 添加反应错误: {e}")

    def _add_reaction_sync(self, message_id: str, emoji_type: str) -> None:
        """同步添加反应辅助方法"""
        from lark_oapi.api.im.v1 import CreateMessageReactionRequest, CreateMessageReactionRequestBody, Emoji
        try:
            request = CreateMessageReactionRequest.builder() \
                .message_id(message_id) \
                .request_body(
                    CreateMessageReactionRequestBody.builder()
                    .reaction_type(Emoji.builder().emoji_type(emoji_type).build())
                    .build()
                ).build()

            response = self._client.im.v1.message_reaction.create(request)

            if not response.success():
                print(f"[飞书] 添加反应失败: code={response.code}, msg={response.msg}")
        except Exception as e:
            print(f"[飞书] 添加反应错误: {e}")