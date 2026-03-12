"""WhatsApp 通道实现 - 通过 Node.js bridge"""
import asyncio
import json
from collections import OrderedDict
from typing import Optional

import websockets

import importlib.util

WEBSOCKETS_AVAILABLE = importlib.util.find_spec("websockets") is not None

from bus.events import OutboundMessage
from bus.queue import MessageBus
from bus.channels.base import BaseChannel


class WhatsAppConfig:
    """WhatsApp 通道配置"""
    enabled: bool = False
    webhook_url: str = ""  # WebSocket bridge URL
    verify_token: str = ""
    allow_from: list[str] = []


class WhatsAppChannel(BaseChannel):
    """WhatsApp 通道连接 Node.js bridge"""

    name = "whatsapp"

    def __init__(self, config: WhatsAppConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: WhatsAppConfig = config
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        self._processed_message_ids: OrderedDict[str, None] = OrderedDict()

    async def start(self) -> None:
        """Start WhatsApp channel by connecting to bridge"""
        if not WEBSOCKETS_AVAILABLE:
            print("[WhatsApp] websockets 库未安装。运行: pip install websockets")
            return

        bridge_url = self.config.webhook_url

        if not bridge_url:
            print("[WhatsApp] webhook_url 未配置")
            return

        print(f"[WhatsApp] 连接 bridge: {bridge_url}...")

        self._running = True

        while self._running:
            try:
                async with websockets.connect(bridge_url) as ws:
                    self._ws = ws
                    self._connected = True
                    print("[WhatsApp] 已连接 bridge")

                    async for message in ws:
                        try:
                            await self._handle_bridge_message(message)
                        except Exception as e:
                            print(f"[WhatsApp] 处理消息失败: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._connected = False
                self._ws = None
                print(f"[WhatsApp] bridge 连接错误: {e}")

                if self._running:
                    print("[WhatsApp] 5秒后重连...")
                    await asyncio.sleep(5)

    async def stop(self) -> None:
        """Stop WhatsApp channel"""
        self._running = False
        self._connected = False

        if self._ws:
            await self._ws.close()
            self._ws = None

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through WhatsApp"""
        if not self._ws or not self._connected:
            print("[WhatsApp] bridge 未连接")
            return

        try:
            payload = {
                "type": "send",
                "to": msg.chat_id,
                "text": msg.content
            }
            await self._ws.send(json.dumps(payload, ensure_ascii=False))
        except Exception as e:
            print(f"[WhatsApp] 发送消息失败: {e}")

    async def _handle_bridge_message(self, raw: str) -> None:
        """Handle a message from the bridge"""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            print(f"[WhatsApp] 无效 JSON: {raw[:100]}")
            return

        msg_type = data.get("type")

        if msg_type == "message":
            # Incoming message from WhatsApp
            pn = data.get("pn", "")
            sender = data.get("sender", "")
            content = data.get("content", "")
            message_id = data.get("id", "")

            if message_id:
                if message_id in self._processed_message_ids:
                    return
                self._processed_message_ids[message_id] = None
                while len(self._processed_message_ids) > 1000:
                    self._processed_message_ids.popitem(last=False)

            # Extract just the phone number or lid as chat_id
            user_id = pn if pn else sender
            sender_id = user_id.split("@")[0] if "@" in user_id else user_id

            print(f"[WhatsApp] 收到消息 from {sender_id}: {content[:50]}...")

            # Handle voice message
            if content == "[Voice Message]":
                content = "[语音消息: 暂不支持转录]"

            # Extract media paths
            media_paths = data.get("media") or []

            if media_paths:
                for p in media_paths:
                    content = f"{content}\n[{p}]" if content else f"[{p}]"

            await self._handle_message(
                sender_id=sender_id,
                chat_id=sender,
                content=content,
                media=media_paths,
                metadata={
                    "message_id": message_id,
                    "timestamp": data.get("timestamp"),
                    "is_group": data.get("isGroup", False)
                }
            )

        elif msg_type == "status":
            status = data.get("status")
            print(f"[WhatsApp] 状态: {status}")

            if status == "connected":
                self._connected = True
            elif status == "disconnected":
                self._connected = False

        elif msg_type == "qr":
            print("[WhatsApp] 请扫描终端中的二维码连接 WhatsApp")