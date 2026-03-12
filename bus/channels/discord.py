"""Discord 通道实现 - 使用 Gateway websocket"""
import asyncio
import json
from pathlib import Path
from typing import Any, Optional

import httpx
import websockets

import importlib.util

DISCORD_AVAILABLE = importlib.util.find_spec("discord") is not None or importlib.util.find_spec("websockets") is not None

from bus.events import OutboundMessage
from bus.queue import MessageBus
from bus.channels.base import BaseChannel

DISCORD_API_BASE = "https://discord.com/api/v10"
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024  # 20MB
MAX_MESSAGE_LEN = 2000


class DiscordConfig:
    """Discord 通道配置"""
    enabled: bool = False
    bot_token: str = ""
    gateway_url: str = "wss://gateway.discord.gg/?v=10&encoding=json"
    intents: int = 513  # GUILDS + GUILD_MESSAGES
    allow_from: list[str] = []


class DiscordChannel(BaseChannel):
    """Discord 通道使用 Gateway websocket"""

    name = "discord"

    def __init__(self, config: DiscordConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: DiscordConfig = config
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._seq: Optional[int] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._typing_tasks: dict[str, asyncio.Task] = {}
        self._http: Optional[httpx.AsyncClient] = None
        self._bot_user_id: Optional[str] = None

    async def start(self) -> None:
        """Start the Discord gateway connection"""
        if not self.config.bot_token:
            print("[Discord] bot_token 未配置")
            return

        self._running = True
        self._http = httpx.AsyncClient(timeout=30.0)

        while self._running:
            try:
                print("[Discord] 连接网关中...")
                async with websockets.connect(self.config.gateway_url) as ws:
                    self._ws = ws
                    await self._gateway_loop()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Discord] 网关错误: {e}")
                if self._running:
                    print("[Discord] 5秒后重连...")
                    await asyncio.sleep(5)

    async def stop(self) -> None:
        """Stop the Discord channel"""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        for task in self._typing_tasks.values():
            task.cancel()
        self._typing_tasks.clear()
        if self._ws:
            await self._ws.close()
            self._ws = None
        if self._http:
            await self._http.aclose()
            self._http = None

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Discord REST API"""
        if not self._http:
            print("[Discord] HTTP 客户端未初始化")
            return

        url = f"{DISCORD_API_BASE}/channels/{msg.chat_id}/messages"
        headers = {"Authorization": f"Bot {self.config.bot_token}"}

        try:
            # 发送文本内容
            chunks = self._split_message(msg.content or "", MAX_MESSAGE_LEN)
            if not chunks:
                return

            for i, chunk in enumerate(chunks):
                payload: dict[str, Any] = {"content": chunk}
                if i == 0 and msg.reply_to:
                    payload["message_reference"] = {"message_id": msg.reply_to}
                    payload["allowed_mentions"] = {"replied_user": False}

                await self._send_payload(url, headers, payload)
        finally:
            await self._stop_typing(msg.chat_id)

    def _split_message(self, text: str, max_len: int) -> list[str]:
        """Split message into chunks"""
        if len(text) <= max_len:
            return [text] if text else []
        return [text[i:i + max_len] for i in range(0, len(text), max_len)]

    async def _send_payload(
        self, url: str, headers: dict[str, str], payload: dict[str, Any]
    ) -> bool:
        """Send a single Discord API payload with retry on rate-limit"""
        for attempt in range(3):
            try:
                response = await self._http.post(url, headers=headers, json=payload)
                if response.status_code == 429:
                    data = response.json()
                    retry_after = float(data.get("retry_after", 1.0))
                    print(f"[Discord] 速率限制，{retry_after}秒后重试")
                    await asyncio.sleep(retry_after)
                    continue
                response.raise_for_status()
                return True
            except Exception as e:
                if attempt == 2:
                    print(f"[Discord] 发送消息失败: {e}")
                else:
                    await asyncio.sleep(1)
        return False

    async def _gateway_loop(self) -> None:
        """Main gateway loop"""
        if not self._ws:
            return

        async for raw in self._ws:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                print(f"[Discord] 无效 JSON: {raw[:100]}")
                continue

            op = data.get("op")
            event_type = data.get("t")
            seq = data.get("s")
            payload = data.get("d")

            if seq is not None:
                self._seq = seq

            if op == 10:
                interval_ms = payload.get("heartbeat_interval", 45000)
                await self._start_heartbeat(interval_ms / 1000)
                await self._identify()
            elif op == 0 and event_type == "READY":
                print("[Discord] 网关就绪")
                user_data = payload.get("user") or {}
                self._bot_user_id = user_data.get("id")
                print(f"[Discord] 机器人已连接: {self._bot_user_id}")
            elif op == 0 and event_type == "MESSAGE_CREATE":
                await self._handle_message_create(payload)
            elif op == 7:
                print("[Discord] 请求重连")
                break
            elif op == 9:
                print("[Discord] 无效会话")
                break

    async def _identify(self) -> None:
        """Send IDENTIFY payload"""
        if not self._ws:
            return

        identify = {
            "op": 2,
            "d": {
                "token": self.config.bot_token,
                "intents": self.config.intents,
                "properties": {
                    "os": "lanobot",
                    "browser": "lanobot",
                    "device": "lanobot",
                },
            },
        }
        await self._ws.send(json.dumps(identify))

    async def _start_heartbeat(self, interval_s: float) -> None:
        """Start heartbeat loop"""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        async def heartbeat_loop() -> None:
            while self._running and self._ws:
                payload = {"op": 1, "d": self._seq}
                try:
                    await self._ws.send(json.dumps(payload))
                except Exception as e:
                    print(f"[Discord] 心跳失败: {e}")
                    break
                await asyncio.sleep(interval_s)

        self._heartbeat_task = asyncio.create_task(heartbeat_loop())

    async def _handle_message_create(self, payload: dict[str, Any]) -> None:
        """Handle incoming Discord messages"""
        author = payload.get("author") or {}
        if author.get("bot"):
            return

        sender_id = str(author.get("id", ""))
        channel_id = str(payload.get("channel_id", ""))
        content = payload.get("content") or ""
        guild_id = payload.get("guild_id")

        if not sender_id or not channel_id:
            return

        if not self.is_allowed(sender_id):
            return

        # Group channel: require mention
        if guild_id is not None:
            if not self._should_respond_in_group(payload, content):
                return

        await self._start_typing(channel_id)

        await self._handle_message(
            sender_id=sender_id,
            chat_id=channel_id,
            content=content or "[empty message]",
            metadata={
                "message_id": str(payload.get("id", "")),
                "guild_id": guild_id,
            },
        )

    def _should_respond_in_group(self, payload: dict[str, Any], content: str) -> bool:
        """Check if bot should respond in a group channel"""
        if not self._bot_user_id:
            return True

        mentions = payload.get("mentions") or []
        for mention in mentions:
            if str(mention.get("id")) == self._bot_user_id:
                return True
        if f"<@{self._bot_user_id}>" in content or f"<@!{self._bot_user_id}>" in content:
            return True

        return False

    async def _start_typing(self, channel_id: str) -> None:
        """Start periodic typing indicator"""
        await self._stop_typing(channel_id)

        async def typing_loop() -> None:
            url = f"{DISCORD_API_BASE}/channels/{channel_id}/typing"
            headers = {"Authorization": f"Bot {self.config.bot_token}"}
            while self._running:
                try:
                    await self._http.post(url, headers=headers)
                except Exception:
                    return
                await asyncio.sleep(8)

        self._typing_tasks[channel_id] = asyncio.create_task(typing_loop())

    async def _stop_typing(self, channel_id: str) -> None:
        """Stop typing indicator"""
        task = self._typing_tasks.pop(channel_id, None)
        if task:
            task.cancel()