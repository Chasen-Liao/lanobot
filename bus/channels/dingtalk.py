"""钉钉通道实现 - 使用 Stream Mode"""
import asyncio
import json
import time
from typing import Any, Optional

import httpx

import importlib.util

DINGTALK_AVAILABLE = importlib.util.find_spec("dingtalk_stream") is not None

from bus.events import OutboundMessage
from bus.queue import MessageBus
from bus.channels.base import BaseChannel


class DingtalkConfig:
    """钉钉通道配置"""
    enabled: bool = False
    app_key: str = ""
    app_secret: str = ""
    allow_from: list[str] = []


class DingTalkChannel(BaseChannel):
    """钉钉通道使用 Stream Mode"""

    name = "dingtalk"

    def __init__(self, config: DingtalkConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: DingtalkConfig = config
        self._client: Any = None
        self._http: Optional[httpx.AsyncClient] = None
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0
        self._background_tasks: set[asyncio.Task] = set()

    async def start(self) -> None:
        """Start the DingTalk bot with Stream Mode"""
        if not DINGTALK_AVAILABLE:
            print("[钉钉] SDK 未安装。运行: pip install dingtalk-stream")
            return

        if not self.config.app_key or not self.config.app_secret:
            print("[钉钉] app_key 和 app_secret 未配置")
            return

        self._running = True
        self._http = httpx.AsyncClient()

        try:
            from dingtalk_stream import Credential, DingTalkStreamClient

            print(f"[钉钉] 初始化客户端: {self.config.app_key}...")
            credential = Credential(self.config.app_key, self.config.app_secret)
            self._client = DingTalkStreamClient(credential)

            # Register handler
            self._client.register_callback_handler(
                "ChatbotMessage",
                DingTalkHandler(self)
            )

            print("[钉钉] 启动 Stream 模式...")

            # Reconnect loop
            while self._running:
                try:
                    await self._client.start()
                except Exception as e:
                    print(f"[钉钉] Stream 错误: {e}")
                if self._running:
                    print("[钉钉] 5秒后重连...")
                    await asyncio.sleep(5)

        except Exception as e:
            print(f"[钉钉] 启动失败: {e}")

    async def stop(self) -> None:
        """Stop the DingTalk bot"""
        self._running = False
        if self._http:
            await self._http.aclose()
            self._http = None
        for task in self._background_tasks:
            task.cancel()
        self._background_tasks.clear()

    async def _get_access_token(self) -> Optional[str]:
        """Get or refresh Access Token"""
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token

        url = "https://api.dingtalk.com/v1.0/oauth2/accessToken"
        data = {
            "appKey": self.config.app_key,
            "appSecret": self.config.app_secret,
        }

        if not self._http:
            return None

        try:
            resp = await self._http.post(url, json=data)
            resp.raise_for_status()
            res_data = resp.json()
            self._access_token = res_data.get("accessToken")
            self._token_expiry = time.time() + int(res_data.get("expireIn", 7200)) - 60
            return self._access_token
        except Exception as e:
            print(f"[钉钉] 获取 access token 失败: {e}")
            return None

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through DingTalk"""
        token = await self._get_access_token()
        if not token:
            return

        if msg.content and msg.content.strip():
            await self._send_markdown_text(token, msg.chat_id, msg.content.strip())

    async def _send_markdown_text(self, token: str, chat_id: str, content: str) -> bool:
        """Send markdown text"""
        if not self._http:
            return False

        if chat_id.startswith("group:"):
            url = "https://api.dingtalk.com/v1.0/robot/groupMessages/send"
            payload = {
                "robotCode": self.config.app_key,
                "openConversationId": chat_id[6:],
                "msgKey": "sampleMarkdown",
                "msgParam": json.dumps({"text": content, "title": "Lanobot"}, ensure_ascii=False),
            }
        else:
            url = "https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend"
            payload = {
                "robotCode": self.config.app_key,
                "userIds": [chat_id],
                "msgKey": "sampleMarkdown",
                "msgParam": json.dumps({"text": content, "title": "Lanobot"}, ensure_ascii=False),
            }

        try:
            headers = {"x-acs-dingtalk-access-token": token}
            resp = await self._http.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                print(f"[钉钉] 发送失败: {resp.status_code}, {resp.text}")
                return False
            return True
        except Exception as e:
            print(f"[钉钉] 发送消息失败: {e}")
            return False

    async def _on_message(
        self,
        content: str,
        sender_id: str,
        sender_name: str,
        conversation_type: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> None:
        """Handle incoming message"""
        try:
            is_group = conversation_type == "2" and conversation_id
            chat_id = f"group:{conversation_id}" if is_group else sender_id
            await self._handle_message(
                sender_id=sender_id,
                chat_id=chat_id,
                content=str(content),
                metadata={
                    "sender_name": sender_name,
                    "platform": "dingtalk",
                    "conversation_type": conversation_type,
                },
            )
        except Exception as e:
            print(f"[钉钉] 处理消息失败: {e}")


class DingTalkHandler:
    """钉钉消息处理器"""

    def __init__(self, channel: DingTalkChannel):
        self.channel = channel

    async def process(self, message: Any) -> tuple[str, str]:
        """Process incoming message"""
        try:
            data = message.data

            # Extract content
            content = ""
            text = data.get("text", {})
            if text:
                content = text.get("content", "").strip()

            if not content:
                # Try extensions
                ext = data.get("extensions", {})
                if ext.get("content", {}).get("recognition"):
                    content = ext["content"]["recognition"].strip()

            if not content:
                return "OK", "OK"

            # Extract sender info
            sender_id = data.get("senderId", data.get("senderStaffId", "unknown"))
            sender_name = data.get("senderNick", "Unknown")

            conversation_type = data.get("conversationType")
            conversation_id = data.get("conversationId", data.get("openConversationId"))

            print(f"[钉钉] 收到消息 from {sender_name}: {content[:50]}...")

            # Forward to channel
            task = asyncio.create_task(
                self.channel._on_message(
                    content,
                    sender_id,
                    sender_name,
                    conversation_type,
                    conversation_id,
                )
            )
            self.channel._background_tasks.add(task)
            task.add_done_callback(self.channel._background_tasks.discard)

            return "OK", "OK"

        except Exception as e:
            print(f"[钉钉] 处理消息错误: {e}")
            return "OK", "Error"


# 别名，保持与其他通道命名风格一致
DingtalkChannel = DingTalkChannel