"""Pydantic 配置模型定义"""
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from pydantic_settings import BaseSettings


class Base(BaseModel):
    """基础模型，支持 camelCase 和 snake_case 键名"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class LLMConfig(Base):
    """LLM 配置"""
    provider: str = "siliconflow"
    model: str = "Pro/deepseek-ai/DeepSeek-V3.2"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0)


class DatabaseConfig(Base):
    """数据库配置"""
    url: str = "sqlite:///./data/lanobot.db"
    echo: bool = False


class MessageBusConfig(Base):
    """消息总线配置"""
    max_queue_size: int = Field(default=1000, gt=0)
    timeout: float = Field(default=30.0, gt=0)


class LoggingConfig(Base):
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None


class AppConfig(BaseSettings):
    """应用配置"""
    version: str = "0.1.0"
    debug: bool = False
    llm: LLMConfig = Field(default_factory=LLMConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    message_bus: MessageBusConfig = Field(default_factory=MessageBusConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    model_config = ConfigDict(
        env_prefix="LANOBOT_",
        env_nested_delimiter="__",
    )

    @property
    def data_dir(self) -> Path:
        """获取数据目录路径"""
        return Path("./data")

    @property
    def config_dir(self) -> Path:
        """获取配置目录路径"""
        return Path("./config")