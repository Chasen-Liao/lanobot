"""聊天通道模块 - 插件架构"""
from bus.channels.base import BaseChannel

# 导出各通道实现
from bus.channels.feishu import FeishuChannel, FeishuConfig
from bus.channels.qq import QQChannel, QQConfig
from bus.channels.telegram import TelegramChannel, TelegramConfig
from bus.channels.slack import SlackChannel, SlackConfig
from bus.channels.discord import DiscordChannel, DiscordConfig
from bus.channels.dingtalk import DingtalkChannel, DingtalkConfig
from bus.channels.wecom import WecomChannel, WecomConfig
from bus.channels.whatsapp import WhatsAppChannel, WhatsAppConfig

# 导出管理器
from bus.channels.manager import ChannelManager

__all__ = [
    "BaseChannel",
    # 飞书
    "FeishuChannel",
    "FeishuConfig",
    # QQ
    "QQChannel",
    "QQConfig",
    # Telegram
    "TelegramChannel",
    "TelegramConfig",
    # Slack
    "SlackChannel",
    "SlackConfig",
    # Discord
    "DiscordChannel",
    "DiscordConfig",
    # 钉钉
    "DingtalkChannel",
    "DingtalkConfig",
    # 企业微信
    "WecomChannel",
    "WecomConfig",
    # WhatsApp
    "WhatsAppChannel",
    "WhatsAppConfig",
    # 管理器
    "ChannelManager",
]