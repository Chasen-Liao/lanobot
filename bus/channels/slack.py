"""Slack 通道实现 - 使用 Socket Mode"""
import asyncio
import re
import importlib.util
from typing import Any, Optional

# 延迟导入
SLACK_AVAILABLE = importlib.util.find_spec("slack_sdk") is not None
SocketModeRequest = None
SocketModeResponse = None
SocketModeClient = None
AsyncWebClient = None

if SLACK_AVAILABLE:
    from slack_sdk.socket_mode.request import SocketModeRequest
    from slack_sdk.socket_mode.response import SocketModeResponse
    from slack_sdk.socket_mode.websockets import SocketModeClient
    from slack_sdk.web.async_client import AsyncWebClient

from bus.events import OutboundMessage
from bus.queue import MessageBus
from bus.channels.base import BaseChannel


class SlackConfig:
    """Slack 通道配置"""
    enabled: bool = False
    bot_token: str = ""
    app_token: str = ""
    signing_secret: str = ""
    allow_from: list[str] = []
    reply_in_thread: bool = True
    react_emoji: str = "eyes"


class SlackChannel(BaseChannel):
    """Slack 通道使用 Socket Mode"""

    name = "slack"

    def __init__(self, config: SlackConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: SlackConfig = config
        self._web_client: Optional[AsyncWebClient] = None
        self._socket_client: Optional[SocketModeClient] = None
        self._bot_user_id: Optional[str] = None

    async def start(self) -> None:
        """Start Slack Socket Mode client"""
        if not SLACK_AVAILABLE:
            print("[Slack] SDK 未安装。运行: pip install slack-sdk")
            return

        if not self.config.bot_token or not self.config.app_token:
            print("[Slack] bot_token 和 app_token 未配置")
            return

        self._running = True

        self._web_client = AsyncWebClient(token=self.config.bot_token)
        self._socket_client = SocketModeClient(
            app_token=self.config.app_token,
            web_client=self._web_client,
        )

        self._socket_client.socket_mode_request_listeners.append(self._on_socket_request)

        # Resolve bot user ID
        try:
            auth = await self._web_client.auth_test()
            self._bot_user_id = auth.get("user_id")
            print(f"[Slack] 机器人已连接: {self._bot_user_id}")
        except Exception as e:
            print(f"[Slack] auth_test 失败: {e}")

        print("[Slack] Socket Mode 启动中...")
        await self._socket_client.connect()

        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        """Stop the Slack client"""
        self._running = False
        if self._socket_client:
            try:
                await self._socket_client.close()
            except Exception as e:
                print(f"[Slack] socket close 失败: {e}")
            self._socket_client = None

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Slack"""
        if not self._web_client:
            print("[Slack] 客户端未运行")
            return
        try:
            slack_meta = msg.metadata.get("slack", {}) if msg.metadata else {}
            thread_ts = slack_meta.get("thread_ts")
            channel_type = slack_meta.get("channel_type")
            thread_ts_param = thread_ts if thread_ts and channel_type != "im" else None

            if msg.content or not (msg.media or []):
                await self._web_client.chat_postMessage(
                    channel=msg.chat_id,
                    text=self._to_mrkdwn(msg.content) if msg.content else " ",
                    thread_ts=thread_ts_param,
                )

            for media_path in msg.media or []:
                try:
                    await self._web_client.files_upload_v2(
                        channel=msg.chat_id,
                        file=media_path,
                        thread_ts=thread_ts_param,
                    )
                except Exception as e:
                    print(f"[Slack] 文件上传失败: {media_path}, {e}")
        except Exception as e:
            print(f"[Slack] 发送消息失败: {e}")

    async def _on_socket_request(
        self,
        client: SocketModeClient,
        req: SocketModeRequest,
    ) -> None:
        """Handle incoming Socket Mode requests"""
        if req.type != "events_api":
            return

        await client.send_socket_mode_response(
            SocketModeResponse(envelope_id=req.envelope_id)
        )

        payload = req.payload or {}
        event = payload.get("event") or {}
        event_type = event.get("type")

        if event_type not in ("message", "app_mention"):
            return

        sender_id = event.get("user")
        chat_id = event.get("channel")

        # Ignore bot messages
        if event.get("subtype"):
            return
        if self._bot_user_id and sender_id == self._bot_user_id:
            return

        # Avoid double-processing
        text = event.get("text") or ""
        if event_type == "message" and self._bot_user_id and f"<@{self._bot_user_id}>" in text:
            return

        if not sender_id or not chat_id:
            return

        channel_type = event.get("channel_type") or ""

        # Allow DMs, require mention in channels
        if channel_type != "im" and self._bot_user_id and f"<@{self._bot_user_id}>" not in text:
            return

        thread_ts = event.get("thread_ts")
        if self.config.reply_in_thread and not thread_ts:
            thread_ts = event.get("ts")

        # Add reaction
        try:
            if self._web_client and event.get("ts"):
                await self._web_client.reactions_add(
                    channel=chat_id,
                    name=self.config.react_emoji,
                    timestamp=event.get("ts"),
                )
        except Exception as e:
            print(f"[Slack] 添加 reaction 失败: {e}")

        # Session key for threads
        session_key = f"slack:{chat_id}:{thread_ts}" if thread_ts and channel_type != "im" else None

        try:
            await self._handle_message(
                sender_id=sender_id,
                chat_id=chat_id,
                content=self._strip_bot_mention(text),
                metadata={
                    "slack": {
                        "event": event,
                        "thread_ts": thread_ts,
                        "channel_type": channel_type,
                    },
                },
                session_key=session_key,
            )
        except Exception as e:
            print(f"[Slack] 处理消息失败: {e}")

    def _strip_bot_mention(self, text: str) -> str:
        """Strip bot mention from text"""
        if not text or not self._bot_user_id:
            return text
        return re.sub(rf"<@{re.escape(self._bot_user_id)}>\s*", "", text).strip()

    _TABLE_RE = re.compile(r"(?m)^\|.*\|$(?:\n\|[\s:|-]*\|$)(?:\n\|.*\|$)*")
    _CODE_FENCE_RE = re.compile(r"```[\s\S]*?```")
    _INLINE_CODE_RE = re.compile(r"`[^`]+`")
    _LEFTOVER_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
    _LEFTOVER_HEADER_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
    _BARE_URL_RE = re.compile(r"(?<![|<])(https?://\S+)")

    @classmethod
    def _to_mrkdwn(cls, text: str) -> str:
        """Convert Markdown to Slack mrkdwn"""
        if not text:
            return ""
        text = cls._TABLE_RE.sub(cls._convert_table, text)
        return cls._fixup_mrkdwn(cls._basic_slackify(text))

    @classmethod
    def _basic_slackify(cls, text: str) -> str:
        """Basic markdown to slack conversion"""
        # Basic conversions
        text = cls._CODE_FENCE_RE.sub(lambda m: m.group(0), text)
        text = cls._INLINE_CODE_RE.sub(lambda m: m.group(0), text)
        text = cls._LEFTOVER_BOLD_RE.sub(r"*\1*", text)
        text = cls._LEFTOVER_HEADER_RE.sub(r"*\1*", text)
        text = cls._BARE_URL_RE.sub(lambda m: m.group(0).replace("&", "&"), text)
        return text

    @classmethod
    def _fixup_mrkdwn(cls, text: str) -> str:
        """Fix markdown artifacts"""
        code_blocks: list[str] = []

        def _save_code(m: re.Match) -> str:
            code_blocks.append(m.group(0))
            return f"\x00CB{len(code_blocks) - 1}\x00"

        text = cls._CODE_FENCE_RE.sub(_save_code, text)
        text = cls._INLINE_CODE_RE.sub(_save_code, text)

        for i, block in enumerate(code_blocks):
            text = text.replace(f"\x00CB{i}\x00", block)
        return text

    @staticmethod
    def _convert_table(match: re.Match) -> str:
        """Convert Markdown table to Slack-readable list"""
        lines = [ln.strip() for ln in match.group(0).strip().splitlines() if ln.strip()]
        if len(lines) < 2:
            return match.group(0)
        headers = [h.strip() for h in lines[0].strip("|").split("|")]
        start = 2 if re.fullmatch(r"[|\s:\-]+", lines[1]) else 1
        rows: list[str] = []
        for line in lines[start:]:
            cells = [c.strip() for c in line.strip("|").split("|")]
            cells = (cells + [""] * len(headers))[: len(headers)]
            parts = [f"**{headers[i]}**: {cells[i]}" for i in range(len(headers)) if cells[i]]
            if parts:
                rows.append(" · ".join(parts))
        return "\n".join(rows)