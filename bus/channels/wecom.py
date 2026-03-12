"""企业微信通道实现"""
import asyncio
import os
from collections import OrderedDict
from typing import Any, Optional

import importlib.util

WECOM_AVAILABLE = importlib.util.find_spec("wecom_aibot_sdk") is not None

from bus.events import OutboundMessage
from bus.queue import MessageBus
from bus.channels.base import BaseChannel

# 消息类型显示映射
MSG_TYPE_MAP = {
    "image": "[图片]",
    "voice": "[语音]",
    "file": "[文件]",
    "mixed": "[混合内容]",
}


class WecomConfig:
    """企业微信通道配置"""
    enabled: bool = False
    corp_id: str = ""
    corp_secret: str = ""
    agent_id: str = ""
    allow_from: list[str] = []
    welcome_message: str = ""


class WecomChannel(BaseChannel):
    """企业微信通道使用 WebSocket 长连接"""

    name = "wecom"

    def __init__(self, config: WecomConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: WecomConfig = config
        self._client: Any = None
        self._processed_message_ids: OrderedDict[str, None] = OrderedDict()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._generate_req_id = None
        self._chat_frames: dict[str, Any] = {}

    async def start(self) -> None:
        """Start the WeCom bot with WebSocket long connection"""
        if not WECOM_AVAILABLE:
            print("[企业微信] SDK 未安装。运行: pip install wecom-aibot-sdk")
            return

        if not self.config.corp_id or not self.config.corp_secret:
            print("[企业微信] corp_id 和 corp_secret 未配置")
            return

        from wecom_aibot_sdk import WSClient, generate_req_id

        self._running = True
        self._loop = asyncio.get_running_loop()
        self._generate_req_id = generate_req_id

        self._client = WSClient({
            "corp_id": self.config.corp_id,
            "corp_secret": self.config.corp_secret,
            "agent_id": self.config.agent_id,
            "reconnect_interval": 1000,
            "max_reconnect_attempts": -1,
            "heartbeat_interval": 30000,
        })

        # Register event handlers
        self._client.on("connected", self._on_connected)
        self._client.on("authenticated", self._on_authenticated)
        self._client.on("disconnected", self._on_disconnected)
        self._client.on("error", self._on_error)
        self._client.on("message.text", self._on_text_message)
        self._client.on("message.image", self._on_image_message)
        self._client.on("message.voice", self._on_voice_message)
        self._client.on("message.file", self._on_file_message)

        print("[企业微信] 启动 WebSocket 长连接...")

        await self._client.connect_async()

        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        """Stop the WeCom bot"""
        self._running = False
        if self._client:
            await self._client.disconnect()
        print("[企业微信] 已停止")

    async def _on_connected(self, frame: Any) -> None:
        """Handle WebSocket connected event"""
        print("[企业微信] WebSocket 已连接")

    async def _on_authenticated(self, frame: Any) -> None:
        """Handle authentication success event"""
        print("[企业微信] 认证成功")

    async def _on_disconnected(self, frame: Any) -> None:
        """Handle WebSocket disconnected event"""
        reason = frame.body if hasattr(frame, 'body') else str(frame)
        print(f"[企业微信] WebSocket 断开: {reason}")

    async def _on_error(self, frame: Any) -> None:
        """Handle error event"""
        print(f"[企业微信] 错误: {frame}")

    async def _on_text_message(self, frame: Any) -> None:
        """Handle text message"""
        await self._process_message(frame, "text")

    async def _on_image_message(self, frame: Any) -> None:
        """Handle image message"""
        await self._process_message(frame, "image")

    async def _on_voice_message(self, frame: Any) -> None:
        """Handle voice message"""
        await self._process_message(frame, "voice")

    async def _on_file_message(self, frame: Any) -> None:
        """Handle file message"""
        await self._process_message(frame, "file")

    async def _process_message(self, frame: Any, msg_type: str) -> None:
        """Process incoming message"""
        try:
            if hasattr(frame, 'body'):
                body = frame.body or {}
            elif isinstance(frame, dict):
                body = frame.get("body", frame)
            else:
                body = {}

            if not isinstance(body, dict):
                return

            msg_id = body.get("msgid", "")
            if not msg_id:
                msg_id = f"{body.get('chatid', '')}_{body.get('sendertime', '')}"

            # Deduplication
            if msg_id in self._processed_message_ids:
                return
            self._processed_message_ids[msg_id] = None
            while len(self._processed_message_ids) > 1000:
                self._processed_message_ids.popitem(last=False)

            from_info = body.get("from", {})
            sender_id = from_info.get("userid", "unknown") if isinstance(from_info, dict) else "unknown"

            chat_type = body.get("chattype", "single")
            chat_id = body.get("chatid", sender_id)

            content_parts = []

            if msg_type == "text":
                text = body.get("text", {}).get("content", "")
                if text:
                    content_parts.append(text)
            elif msg_type == "image":
                content_parts.append("[图片]")
            elif msg_type == "voice":
                voice_content = body.get("voice", {}).get("content", "")
                if voice_content:
                    content_parts.append(f"[语音] {voice_content}")
                else:
                    content_parts.append("[语音]")
            elif msg_type == "file":
                file_name = body.get("file", {}).get("name", "unknown")
                content_parts.append(f"[文件: {file_name}]")

            content = "\n".join(content_parts) if content_parts else ""

            if not content:
                return

            # Store frame for reply
            self._chat_frames[chat_id] = frame

            await self._handle_message(
                sender_id=sender_id,
                chat_id=chat_id,
                content=content,
                metadata={
                    "message_id": msg_id,
                    "msg_type": msg_type,
                    "chat_type": chat_type,
                }
            )

        except Exception as e:
            print(f"[企业微信] 处理消息错误: {e}")

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through WeCom"""
        if not self._client:
            print("[企业微信] 客户端未初始化")
            return

        try:
            content = msg.content.strip()
            if not content:
                return

            frame = self._chat_frames.get(msg.chat_id)
            if not frame:
                print(f"[企业微信] 未找到 chat {msg.chat_id} 的 frame")
                return

            stream_id = self._generate_req_id("stream")
            await self._client.reply_stream(frame, stream_id, content, finish=True)

        except Exception as e:
            print(f"[企业微信] 发送消息失败: {e}")