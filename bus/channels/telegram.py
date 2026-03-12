"""Telegram 通道实现 - 使用 python-telegram-bot SDK"""
from __future__ import annotations

import asyncio
import re
import time
import unicodedata
from typing import Any, Optional

# 延迟导入 telegram SDK
telegram = None
TELEGRAM_AVAILABLE = False
try:
    from telegram import BotCommand, ReplyParameters, Update
    from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
    from telegram.request import HTTPXRequest
    telegram = "available"
    TELEGRAM_AVAILABLE = True
except ImportError:
    BotCommand = None
    ReplyParameters = None
    Update = None
    Application = None
    CommandHandler = None
    ContextTypes = None
    MessageHandler = None
    filters = None
    HTTPXRequest = None

from bus.events import OutboundMessage
from bus.queue import MessageBus
from bus.channels.base import BaseChannel

# 消息字符限制
TELEGRAM_MAX_MESSAGE_LEN = 4000


class TelegramConfig:
    """Telegram 通道配置"""
    enabled: bool = False
    bot_token: str = ""
    allow_from: list[str] = []
    proxy: Optional[str] = None
    reply_to_message: bool = True


def _strip_md(s: str) -> str:
    """Strip markdown inline formatting from text."""
    s = re.sub(r'\*\*(.+?)\*\*', r'\1', s)
    s = re.sub(r'__(.+?)__', r'\1', s)
    s = re.sub(r'~~(.+?)~~', r'\1', s)
    s = re.sub(r'`([^`]+)`', r'\1', s)
    return s.strip()


def _render_table_box(table_lines: list[str]) -> str:
    """Convert markdown pipe-table to compact aligned text for <pre> display."""

    def dw(s: str) -> int:
        return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in s)

    rows: list[list[str]] = []
    has_sep = False
    for line in table_lines:
        cells = [_strip_md(c) for c in line.strip().strip('|').split('|')]
        if all(re.match(r'^:?-+:?$', c) for c in cells if c):
            has_sep = True
            continue
        rows.append(cells)
    if not rows or not has_sep:
        return '\n'.join(table_lines)

    ncols = max(len(r) for r in rows)
    for r in rows:
        r.extend([''] * (ncols - len(r)))
    widths = [max(dw(r[c]) for r in rows) for c in range(ncols)]

    def dr(cells: list[str]) -> str:
        return '  '.join(f'{c}{" " * (w - dw(c))}' for c, w in zip(cells, widths))

    out = [dr(rows[0])]
    out.append('  '.join('─' * w for w in widths))
    for row in rows[1:]:
        out.append(dr(row))
    return '\n'.join(out)


def _markdown_to_telegram_html(text: str) -> str:
    """Convert markdown to Telegram-safe HTML."""
    if not text:
        return ""

    # 1. Extract and protect code blocks
    code_blocks: list[str] = []

    def save_code_block(m: re.Match) -> str:
        code_blocks.append(m.group(1))
        return f"\x00CB{len(code_blocks) - 1}\x00"

    text = re.sub(r'```[\w]*\n?([\s\S]*?)```', save_code_block, text)

    # 1.5. Convert markdown tables
    lines = text.split('\n')
    rebuilt: list[str] = []
    li = 0
    while li < len(lines):
        if re.match(r'^\s*\|.+\|', lines[li]):
            tbl: list[str] = []
            while li < len(lines) and re.match(r'^\s*\|.+\|', lines[li]):
                tbl.append(lines[li])
                li += 1
            box = _render_table_box(tbl)
            if box != '\n'.join(tbl):
                code_blocks.append(box)
                rebuilt.append(f"\x00CB{len(code_blocks) - 1}\x00")
            else:
                rebuilt.extend(tbl)
        else:
            rebuilt.append(lines[li])
            li += 1
    text = '\n'.join(rebuilt)

    # 2. Extract inline code
    inline_codes: list[str] = []

    def save_inline_code(m: re.Match) -> str:
        inline_codes.append(m.group(1))
        return f"\x00IC{len(inline_codes) - 1}\x00"

    text = re.sub(r'`([^`]+)`', save_inline_code, text)

    # 3. Headers
    text = re.sub(r'^#{1,6}\s+(.+)$', r'\1', text, flags=re.MULTILINE)

    # 4. Blockquotes
    text = re.sub(r'^>\s*(.*)$', r'\1', text, flags=re.MULTILINE)

    # 5. Escape HTML
    text = text.replace("&", "&").replace("<", "<").replace(">", ">")

    # 6. Links
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)

    # 7. Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)

    # 8. Italic
    text = re.sub(r'(?<![a-zA-Z0-9])_([^_]+)_(?![a-zA-Z0-9])', r'<i>\1</i>', text)

    # 9. Strikethrough
    text = re.sub(r'~~(.+?)~~', r'<s>\1</s>', text)

    # 10. Bullet lists
    text = re.sub(r'^[-*]\s+', '• ', text, flags=re.MULTILINE)

    # 11. Restore inline code
    for i, code in enumerate(inline_codes):
        escaped = code.replace("&", "&").replace("<", "<").replace(">", ">")
        text = text.replace(f"\x00IC{i}\x00", f"<code>{escaped}</code>")

    # 12. Restore code blocks
    for i, code in enumerate(code_blocks):
        escaped = code.replace("&", "&").replace("<", "<").replace(">", ">")
        text = text.replace(f"\x00CB{i}\x00", f"<pre><code>{escaped}</code></pre>")

    return text


class TelegramChannel(BaseChannel):
    """Telegram 通道使用长轮询"""

    name = "telegram"

    def __init__(self, config: TelegramConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: TelegramConfig = config
        self._app: Optional[Application] = None
        self._chat_ids: dict[str, int] = {}
        self._typing_tasks: dict[str, asyncio.Task] = {}
        self._message_threads: dict[tuple[str, int], int] = {}
        self._bot_user_id: int | None = None
        self._bot_username: str | None = None

    @property
    def BOT_COMMANDS(self) -> list:
        """Bot commands - lazy initialization"""
        if TELEGRAM_AVAILABLE and BotCommand:
            return [
                BotCommand("start", "Start the bot"),
                BotCommand("new", "Start a new conversation"),
                BotCommand("stop", "Stop the current task"),
                BotCommand("help", "Show available commands"),
            ]
        return []

    async def start(self) -> None:
        """启动 Telegram 机器人"""
        if not TELEGRAM_AVAILABLE:
            print("[Telegram] SDK 未安装。运行: pip install python-telegram-bot")
            return

        if not self.config.bot_token:
            print("[Telegram] bot_token 未配置")
            return

        self._running = True

        req = HTTPXRequest(
            connection_pool_size=16,
            pool_timeout=5.0,
            connect_timeout=30.0,
            read_timeout=30.0,
            proxy=self.config.proxy if self.config.proxy else None,
        )
        builder = Application.builder().token(self.config.bot_token).request(req).get_updates_request(req)
        self._app = builder.build()
        self._app.add_error_handler(self._on_error)

        # 添加命令处理器
        self._app.add_handler(CommandHandler("start", self._on_start))
        self._app.add_handler(CommandHandler("new", self._forward_command))
        self._app.add_handler(CommandHandler("stop", self._forward_command))
        self._app.add_handler(CommandHandler("help", self._on_help))

        # 添加消息处理器
        self._app.add_handler(
            MessageHandler(
                (filters.TEXT | filters.PHOTO | filters.VOICE | filters.AUDIO | filters.Document.ALL)
                & ~filters.COMMAND,
                self._on_message
            )
        )

        print("[Telegram] 机器人启动中 (轮询模式)...")

        await self._app.initialize()
        await self._app.start()

        bot_info = await self._app.bot.get_me()
        self._bot_user_id = getattr(bot_info, "id", None)
        self._bot_username = getattr(bot_info, "username", None)
        print(f"[Telegram] 机器人 @${bot_info.username} 已连接")

        try:
            await self._app.bot.set_my_commands(self.BOT_COMMANDS)
        except Exception as e:
            print(f"[Telegram] 注册命令失败: {e}")

        await self._app.updater.start_polling(
            allowed_updates=["message"],
            drop_pending_updates=True
        )

        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        """停止 Telegram 机器人"""
        self._running = False

        for chat_id in list(self._typing_tasks):
            self._stop_typing(chat_id)

        if self._app:
            print("[Telegram] 机器人停止中...")
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            self._app = None

    async def send(self, msg: OutboundMessage) -> None:
        """通过 Telegram 发送消息"""
        if not self._app:
            print("[Telegram] 机器人未运行")
            return

        if not msg.metadata.get("_progress", False):
            self._stop_typing(msg.chat_id)

        try:
            chat_id = int(msg.chat_id)
        except ValueError:
            print(f"[Telegram] 无效的 chat_id: {msg.chat_id}")
            return

        reply_to_message_id = msg.metadata.get("message_id")
        message_thread_id = msg.metadata.get("message_thread_id")
        if message_thread_id is None and reply_to_message_id is not None:
            message_thread_id = self._message_threads.get((msg.chat_id, reply_to_message_id))
        thread_kwargs = {}
        if message_thread_id is not None:
            thread_kwargs["message_thread_id"] = message_thread_id

        reply_params = None
        if self.config.reply_to_message:
            if reply_to_message_id:
                reply_params = ReplyParameters(
                    message_id=reply_to_message_id,
                    allow_sending_without_reply=True
                )

        # 发送媒体文件
        for media_path in (msg.media or []):
            try:
                ext = media_path.rsplit(".", 1)[-1].lower() if "." in media_path else ""
                if ext in ("jpg", "jpeg", "png", "gif", "webp"):
                    media_type = "photo"
                elif ext == "ogg":
                    media_type = "voice"
                elif ext in ("mp3", "m4a", "wav", "aac"):
                    media_type = "audio"
                else:
                    media_type = "document"

                sender = {
                    "photo": self._app.bot.send_photo,
                    "voice": self._app.bot.send_voice,
                    "audio": self._app.bot.send_audio,
                }.get(media_type, self._app.bot.send_document)
                param = "photo" if media_type == "photo" else media_type if media_type in ("voice", "audio") else "document"
                with open(media_path, 'rb') as f:
                    await sender(
                        chat_id=chat_id,
                        **{param: f},
                        reply_parameters=reply_params,
                        **thread_kwargs,
                    )
            except Exception as e:
                filename = media_path.rsplit("/", 1)[-1]
                print(f"[Telegram] 发送媒体失败: {media_path}, {e}")
                await self._app.bot.send_message(
                    chat_id=chat_id,
                    text=f"[发送失败: {filename}]",
                    reply_parameters=reply_params,
                    **thread_kwargs,
                )

        # 发送文本内容
        if msg.content and msg.content != "[empty message]":
            is_progress = msg.metadata.get("_progress", False)

            for chunk in self._split_message(msg.content, TELEGRAM_MAX_MESSAGE_LEN):
                if not is_progress:
                    await self._send_with_streaming(chat_id, chunk, reply_params, thread_kwargs)
                else:
                    await self._send_text(chat_id, chunk, reply_params, thread_kwargs)

    def _split_message(self, text: str, max_len: int) -> list[str]:
        """Split message into chunks"""
        if len(text) <= max_len:
            return [text]
        return [text[i:i + max_len] for i in range(0, len(text), max_len)]

    async def _send_text(
        self,
        chat_id: int,
        text: str,
        reply_params=None,
        thread_kwargs: dict | None = None,
    ) -> None:
        """Send a plain text message with HTML fallback."""
        try:
            html = _markdown_to_telegram_html(text)
            await self._app.bot.send_message(
                chat_id=chat_id, text=html, parse_mode="HTML",
                reply_parameters=reply_params,
                **(thread_kwargs or {}),
            )
        except Exception as e:
            print(f"[Telegram] HTML 解析失败，回退到纯文本: {e}")
            try:
                await self._app.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_parameters=reply_params,
                    **(thread_kwargs or {}),
                )
            except Exception as e2:
                print(f"[Telegram] 发送消息失败: {e2}")

    async def _send_with_streaming(
        self,
        chat_id: int,
        text: str,
        reply_params=None,
        thread_kwargs: dict | None = None,
    ) -> None:
        """Simulate streaming via send_message_draft, then persist"""
        draft_id = int(time.time() * 1000) % (2**31)
        try:
            step = max(len(text) // 8, 40)
            for i in range(step, len(text), step):
                await self._app.bot.send_message_draft(
                    chat_id=chat_id, draft_id=draft_id, text=text[:i],
                )
                await asyncio.sleep(0.04)
            await self._app.bot.send_message_draft(
                chat_id=chat_id, draft_id=draft_id, text=text,
            )
            await asyncio.sleep(0.15)
        except Exception:
            pass
        await self._send_text(chat_id, text, reply_params, thread_kwargs)

    async def _on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not update.message or not update.effective_user:
            return

        user = update.effective_user
        await update.message.reply_text(
            f"Hi {user.first_name}! I'm Lanobot.\n\n"
            "Send me a message and I'll respond!\n"
            "Type /help to see available commands."
        )

    async def _on_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        if not update.message:
            return
        await update.message.reply_text(
            "Commands:\n"
            "/new — Start a new conversation\n"
            "/stop — Stop the current task\n"
            "/help — Show available commands"
        )

    @staticmethod
    def _sender_id(user) -> str:
        """Build sender_id with username for allowlist matching."""
        sid = str(user.id)
        return f"{sid}|{user.username}" if user.username else sid

    @staticmethod
    def _derive_topic_session_key(message) -> str | None:
        """Derive topic-scoped session key for non-private Telegram chats."""
        message_thread_id = getattr(message, "message_thread_id", None)
        if message.chat.type == "private" or message_thread_id is None:
            return None
        return f"telegram:{message.chat_id}:topic:{message_thread_id}"

    def _remember_thread_context(self, message) -> None:
        """Cache topic thread id by chat/message id"""
        message_thread_id = getattr(message, "message_thread_id", None)
        if message_thread_id is None:
            return
        key = (str(message.chat_id), message.message_id)
        self._message_threads[key] = message_thread_id
        if len(self._message_threads) > 1000:
            self._message_threads.pop(next(iter(self._message_threads)))

    async def _forward_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Forward slash commands to the bus."""
        if not update.message or not update.effective_user:
            return
        message = update.message
        user = update.effective_user
        self._remember_thread_context(message)
        await self._handle_message(
            sender_id=self._sender_id(user),
            chat_id=str(message.chat_id),
            content=message.text,
            metadata={
                "message_id": message.message_id,
                "user_id": user.id,
                "is_group": message.chat.type != "private",
            },
            session_key=self._derive_topic_session_key(message),
        )

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages"""
        if not update.message or not update.effective_user:
            return

        message = update.message
        user = update.effective_user
        chat_id = message.chat_id
        sender_id = self._sender_id(user)
        self._remember_thread_context(message)

        self._chat_ids[sender_id] = chat_id

        # Group message handling: private or mentioned
        if message.chat.type != "private":
            if self._bot_username:
                text = message.text or ""
                if f"@{self._bot_username}" not in text:
                    return
            else:
                return

        # Build content
        content_parts = []

        if message.text:
            content_parts.append(message.text)
        if message.caption:
            content_parts.append(message.caption)

        # Start typing
        self._start_typing(str(chat_id))

        content = "\n".join(content_parts) if content_parts else "[empty message]"

        await self._handle_message(
            sender_id=sender_id,
            chat_id=str(chat_id),
            content=content,
            metadata={
                "message_id": message.message_id,
                "user_id": user.id,
                "is_group": message.chat.type != "private",
            },
            session_key=self._derive_topic_session_key(message),
        )

    def _start_typing(self, chat_id: str) -> None:
        """Start typing indicator"""
        self._stop_typing(chat_id)
        self._typing_tasks[chat_id] = asyncio.create_task(self._typing_loop(chat_id))

    def _stop_typing(self, chat_id: str) -> None:
        """Stop typing indicator"""
        task = self._typing_tasks.pop(chat_id, None)
        if task and not task.done():
            task.cancel()

    async def _typing_loop(self, chat_id: str) -> None:
        """Typing indicator loop"""
        try:
            while self._app:
                await self._app.bot.send_chat_action(chat_id=int(chat_id), action="typing")
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[Telegram] typing indicator stopped: {e}")

    async def _on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log errors"""
        print(f"[Telegram] Error: {context.error}")