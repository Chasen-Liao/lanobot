"""QQ 通道实现 - 使用 botpy SDK"""
import asyncio
from collections import deque
from typing import TYPE_CHECKING, Any

from bus.events import OutboundMessage
from bus.queue import MessageBus
from bus.channels.base import BaseChannel

try:
    import botpy
    from botpy.message import C2CMessage, GroupMessage

    QQ_AVAILABLE = True
except ImportError:
    QQ_AVAILABLE = False
    botpy = None
    C2CMessage = None
    GroupMessage = None

if TYPE_CHECKING:
    from botpy.message import C2CMessage, GroupMessage


# QQ 配置（简化版）
class QQConfig:
    """QQ 通道配置"""
    enabled: bool = False
    app_id: str = ""  # 机器人 ID (AppID)
    secret: str = ""  # 机器人密钥 (AppSecret)
    allow_from: list[str] = []  # 允许的用户 openids


def _make_bot_class(channel: "QQChannel") -> "type[botpy.Client]":
    """创建绑定到给定通道的 botpy Client 子类。"""
    intents = botpy.Intents(public_messages=True, direct_message=True)

    class _Bot(botpy.Client):
        def __init__(self):
            # 禁用 botpy 的文件日志
            super().__init__(intents=intents, ext_handlers=False)

        async def on_ready(self):
            print(f"[QQ] 机器人已就绪: {self.robot.name}")

        async def on_c2c_message_create(self, message: "C2CMessage"):
            await channel._on_message(message, is_group=False)

        async def on_group_at_message_create(self, message: "GroupMessage"):
            await channel._on_message(message, is_group=True)

        async def on_direct_message_create(self, message):
            await channel._on_message(message, is_group=False)

    return _Bot


class QQChannel(BaseChannel):
    """使用 botpy SDK 通过 WebSocket 连接 QQ 通道"""

    name = "qq"

    def __init__(self, config: QQConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: QQConfig = config
        self._client: "botpy.Client | None" = None
        self._processed_ids: deque = deque(maxlen=1000)
        self._msg_seq: int = 1  # 消息序列号，避免被 QQ API 去重
        self._chat_type_cache: dict[str, str] = {}

    async def start(self) -> None:
        """启动 QQ 机器人"""
        if not QQ_AVAILABLE:
            print("[QQ] SDK 未安装。运行: pip install qq-botpy")
            return

        if not self.config.app_id or not self.config.secret:
            print("[QQ] app_id 和 secret 未配置")
            return

        self._running = True
        BotClass = _make_bot_class(self)
        self._client = BotClass()
        print("[QQ] 机器人已启动（支持 C2C 和群聊）")
        await self._run_bot()

    async def _run_bot(self) -> None:
        """运行机器人连接并自动重连"""
        while self._running:
            try:
                await self._client.start(appid=self.config.app_id, secret=self.config.secret)
            except Exception as e:
                print(f"[QQ] 机器人错误: {e}")
            if self._running:
                print("[QQ] 5秒后重新连接...")
                await asyncio.sleep(5)

    async def stop(self) -> None:
        """停止 QQ 机器人"""
        self._running = False
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
        print("[QQ] 机器人已停止")

    async def send(self, msg: OutboundMessage) -> None:
        """通过 QQ 发送消息"""
        if not self._client:
            print("[QQ] 客户端未初始化")
            return

        try:
            msg_id = msg.metadata.get("message_id")
            self._msg_seq += 1
            msg_type = self._chat_type_cache.get(msg.chat_id, "c2c")
            if msg_type == "group":
                await self._client.api.post_group_message(
                    group_openid=msg.chat_id,
                    msg_type=2,
                    markdown={"content": msg.content},
                    msg_id=msg_id,
                    msg_seq=self._msg_seq,
                )
            else:
                await self._client.api.post_c2c_message(
                    openid=msg.chat_id,
                    msg_type=2,
                    markdown={"content": msg.content},
                    msg_id=msg_id,
                    msg_seq=self._msg_seq,
                )
        except Exception as e:
            print(f"[QQ] 发送消息错误: {e}")

    async def _on_message(self, data: "C2CMessage | GroupMessage", is_group: bool = False) -> None:
        """处理来自 QQ 的传入消息"""
        try:
            # 通过消息 ID 去重
            if data.id in self._processed_ids:
                return
            self._processed_ids.append(data.id)

            content = (data.content or "").strip()
            if not content:
                return

            if is_group:
                chat_id = data.group_openid
                user_id = data.author.member_openid
                self._chat_type_cache[chat_id] = "group"
            else:
                chat_id = str(getattr(data.author, 'id', None) or getattr(data.author, 'user_openid', 'unknown'))
                user_id = chat_id
                self._chat_type_cache[chat_id] = "c2c"

            await self._handle_message(
                sender_id=user_id,
                chat_id=chat_id,
                content=content,
                metadata={"message_id": data.id},
            )
        except Exception:
            print(f"[QQ] 处理消息错误")