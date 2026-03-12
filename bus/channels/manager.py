"""渠道管理器 - 管理所有聊天渠道并协调消息路由"""
import asyncio
import logging
from typing import TYPE_CHECKING, Any, Optional

from bus.channels.base import BaseChannel
from bus.events import InboundMessage, OutboundMessage
from langchain_core.messages import HumanMessage, AIMessage
from bus.channels.feishu import FeishuChannel, FeishuConfig
from bus.channels.qq import QQChannel, QQConfig
from bus.channels.telegram import TelegramChannel, TelegramConfig
from bus.channels.slack import SlackChannel, SlackConfig
from bus.channels.discord import DiscordChannel, DiscordConfig
from bus.channels.dingtalk import DingtalkChannel, DingtalkConfig
from bus.channels.wecom import WecomChannel, WecomConfig
from bus.channels.whatsapp import WhatsAppChannel, WhatsAppConfig
from bus.queue import MessageBus
from config.schema import ChannelsConfig

if TYPE_CHECKING:
    from lanobot.agent.graph import AgentGraph
    from session import SessionManager

logger = logging.getLogger(__name__)


class ChannelManager:
    """
    管理所有聊天渠道并协调消息路由。

    负责：
    1. 根据配置初始化所有启用的渠道
    2. 协调消息从渠道到 Agent 的路由
    3. 协调消息从 Agent 到渠道的发送
    4. 渠道的生命周期管理（启动/停止）
    """

    def __init__(
        self,
        config: ChannelsConfig,
        bus: MessageBus,
        agent: "AgentGraph | None" = None,
        session_manager: "SessionManager | None" = None,
    ):
        """
        初始化渠道管理器。

        Args:
            config: 渠道配置
            bus: 消息总线
            agent: AgentGraph 实例（可选）
            session_manager: 会话管理器（可选）
        """
        self.config = config
        self.bus = bus
        self.agent = agent
        self.session_manager = session_manager
        self._channels: dict[str, BaseChannel] = {}
        self._running = False

    def _create_feishu_channel(self) -> Optional[FeishuChannel]:
        """创建飞书通道"""
        if not self.config.feishu_enabled:
            return None

        feishu_config = FeishuConfig(
            enabled=True,
            app_id=self.config.feishu_app_id,
            app_secret=self.config.feishu_app_secret,
            encrypt_key=self.config.feishu_encrypt_key,
            verification_token=self.config.feishu_verification_token,
            allow_from=self.config.feishu_allow_from,
            react_emoji=self.config.feishu_react_emoji,
        )
        return FeishuChannel(feishu_config, self.bus)

    def _create_qq_channel(self) -> Optional[QQChannel]:
        """创建 QQ 通道"""
        if not self.config.qq_enabled:
            return None

        qq_config = QQConfig(
            enabled=True,
            app_id=self.config.qq_app_id,
            secret=self.config.qq_secret,
            allow_from=self.config.qq_allow_from,
        )
        return QQChannel(qq_config, self.bus)

    def _create_telegram_channel(self) -> Optional[TelegramChannel]:
        """创建 Telegram 通道"""
        if not self.config.telegram_enabled:
            return None

        telegram_config = TelegramConfig(
            enabled=True,
            bot_token=self.config.telegram_bot_token,
            allow_from=self.config.telegram_allow_from,
        )
        return TelegramChannel(telegram_config, self.bus)

    def _create_slack_channel(self) -> Optional[SlackChannel]:
        """创建 Slack 通道"""
        if not self.config.slack_enabled:
            return None

        slack_config = SlackConfig(
            enabled=True,
            bot_token=self.config.slack_bot_token,
            app_token=self.config.slack_app_token,
            signing_secret=self.config.slack_signing_secret,
            allow_from=self.config.slack_allow_from,
        )
        return SlackChannel(slack_config, self.bus)

    def _create_discord_channel(self) -> Optional[DiscordChannel]:
        """创建 Discord 通道"""
        if not self.config.discord_enabled:
            return None

        discord_config = DiscordConfig(
            enabled=True,
            bot_token=self.config.discord_bot_token,
            allow_from=self.config.discord_allow_from,
        )
        return DiscordChannel(discord_config, self.bus)

    def _create_dingtalk_channel(self) -> Optional[DingtalkChannel]:
        """创建钉钉通道"""
        if not self.config.dingtalk_enabled:
            return None

        dingtalk_config = DingtalkConfig(
            enabled=True,
            app_key=self.config.dingtalk_app_key,
            app_secret=self.config.dingtalk_app_secret,
            allow_from=self.config.dingtalk_allow_from,
        )
        return DingtalkChannel(dingtalk_config, self.bus)

    def _create_wecom_channel(self) -> Optional[WecomChannel]:
        """创建企业微信通道"""
        if not self.config.wecom_enabled:
            return None

        wecom_config = WecomConfig(
            enabled=True,
            corp_id=self.config.wecom_corp_id,
            corp_secret=self.config.wecom_corp_secret,
            agent_id=self.config.wecom_agent_id,
            allow_from=self.config.wecom_allow_from,
        )
        return WecomChannel(wecom_config, self.bus)

    def _create_whatsapp_channel(self) -> Optional[WhatsAppChannel]:
        """创建 WhatsApp 通道"""
        if not self.config.whatsapp_enabled:
            return None

        whatsapp_config = WhatsAppConfig(
            enabled=True,
            webhook_url=self.config.whatsapp_webhook_url,
            verify_token=self.config.whatsapp_verify_token,
            allow_from=self.config.whatsapp_allow_from,
        )
        return WhatsAppChannel(whatsapp_config, self.bus)

    def _init_channels(self) -> dict[str, BaseChannel]:
        """初始化所有启用的渠道"""
        channels = {}

        # 创建各渠道实例
        channel_factories = [
            ("feishu", self._create_feishu_channel),
            ("qq", self._create_qq_channel),
            ("telegram", self._create_telegram_channel),
            ("slack", self._create_slack_channel),
            ("discord", self._create_discord_channel),
            ("dingtalk", self._create_dingtalk_channel),
            ("wecom", self._create_wecom_channel),
            ("whatsapp", self._create_whatsapp_channel),
        ]

        for name, factory in channel_factories:
            channel = factory()
            if channel:
                channels[name] = channel
                logger.info(f"已配置渠道: {name}")

        return channels

    async def start_all(self) -> None:
        """
        启动所有启用的渠道。

        启动顺序：
        1. 初始化所有渠道
        2. 并发启动所有渠道
        3. 启动消息处理循环（如果有 Agent）
        """
        if self._running:
            logger.warning("渠道管理器已在运行")
            return

        # 初始化渠道
        self._channels = self._init_channels()

        if not self._channels:
            logger.warning("没有启用的渠道")
            return

        self._running = True

        # 启动所有渠道
        start_tasks = [
            channel.start()
            for channel in self._channels.values()
        ]
        await asyncio.gather(*start_tasks, return_exceptions=True)

        # 启动消息处理循环
        # 入站循环：消费用户消息 -> 调用 Agent -> 发布响应
        asyncio.create_task(self._inbound_loop())
        # 出站循环：消费 Agent 响应 -> 发送到渠道
        asyncio.create_task(self._message_loop())

        logger.info(f"已启动 {len(self._channels)} 个渠道")

    async def stop_all(self) -> None:
        """停止所有渠道"""
        if not self._running:
            return

        self._running = False

        # 停止所有渠道
        stop_tasks = [
            channel.stop()
            for channel in self._channels.values()
        ]
        await asyncio.gather(*stop_tasks, return_exceptions=True)

        self._channels.clear()
        logger.info("已停止所有渠道")

    async def _inbound_loop(self) -> None:
        """入站消息处理循环：从入站队列获取消息，调用 Agent，处理响应"""
        if not self.agent:
            logger.warning("Agent 未设置，跳过入站消息处理")
            return

        while self._running:
            try:
                # 消费入站消息（用户发送的消息）
                inbound_msg = await self.bus.consume_inbound()
                session_key = inbound_msg.session_key

                logger.debug(f"收到消息 from {session_key}: {inbound_msg.content[:50]}...")

                # 1. 加载会话历史（如果使用 SessionManager）
                messages = []
                if self.session_manager:
                    session = self.session_manager.get_or_create(session_key)
                    # 将历史消息转换为 LangChain 格式
                    # session.messages 是 list[dict] 而不是对象列表
                    for msg_dict in session.messages:
                        role = msg_dict.get("role", "user")
                        content = msg_dict.get("content", "")
                        if role == "user":
                            messages.append(HumanMessage(content=content))
                        elif role == "assistant":
                            messages.append(AIMessage(content=content))

                # 2. 调用 Agent 处理消息
                # 使用 session_key 作为 thread_id 实现会话隔离
                thread_id = f"channel-{session_key}"

                # 将新消息添加到列表
                if messages:
                    # 有历史消息，追加新消息，使用新方法
                    all_messages = messages + [HumanMessage(content=inbound_msg.content)]
                    result = await self.agent.ainvoke_with_history(all_messages, thread_id)
                else:
                    # 无历史消息，直接传入新消息
                    result = await self.agent.ainvoke(inbound_msg.content, thread_id)
                    # 包装结果以保持一致的处理逻辑
                    result = {"messages": result.get("messages", [])}

                # 3. 获取 Agent 回复
                response_messages = result.get("messages", [])
                agent_response = ""
                if response_messages:
                    # 最后一个消息是 Agent 的回复
                    last_msg = response_messages[-1]
                    if hasattr(last_msg, "content"):
                        agent_response = last_msg.content
                    else:
                        agent_response = str(last_msg)

                # 4. 保存会话历史到 SessionManager
                if self.session_manager:
                    session = self.session_manager.get_or_create(session_key)
                    session.add_message("user", inbound_msg.content)
                    if agent_response:
                        session.add_message("assistant", agent_response)
                    self.session_manager.save(session)

                # 5. 发布响应到出站队列
                if agent_response:
                    outbound_msg = OutboundMessage(
                        channel=inbound_msg.channel,
                        chat_id=inbound_msg.chat_id,
                        content=agent_response,
                    )
                    await self.bus.publish_outbound(outbound_msg)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"入站消息处理错误: {e}", exc_info=True)
                # 发送错误消息给用户（如果能获取入站消息）
                try:
                    error_msg = OutboundMessage(
                        channel=inbound_msg.channel,
                        chat_id=inbound_msg.chat_id,
                        content=f"抱歉，处理您的消息时发生错误: {str(e)[:100]}",
                    )
                    await self.bus.publish_outbound(error_msg)
                except Exception:
                    pass  # 避免错误消息发送也失败导致循环中断

    async def _message_loop(self) -> None:
        """出站消息处理循环：从出站队列获取消息，发送到对应渠道"""
        if not self.agent:
            # 即使没有 Agent，也处理出站消息（比如系统通知）
            pass

        while self._running:
            try:
                # 获取出站消息（Agent 响应或系统通知）
                msg = await self.bus.consume_outbound()

                # 获取对应渠道
                channel = self._channels.get(msg.channel)
                if not channel:
                    logger.warning(f"未知渠道: {msg.channel}")
                    continue

                # 发送消息
                await channel.send(msg)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"出站消息处理错误: {e}")

    def get_channel(self, name: str) -> Optional[BaseChannel]:
        """获取指定渠道"""
        return self._channels.get(name)

    @property
    def channels(self) -> dict[str, BaseChannel]:
        """返回所有渠道"""
        return self._channels

    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running

    async def restart_channel(self, name: str) -> bool:
        """重启指定渠道"""
        channel = self._channels.get(name)
        if not channel:
            logger.warning(f"渠道不存在: {name}")
            return False

        await channel.stop()
        await channel.start()
        return True