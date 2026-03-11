"""配置模块测试"""
import pytest
from pathlib import Path

from config.schema import (
    AppConfig,
    LLMConfig,
    DatabaseConfig,
    MessageBusConfig,
    LoggingConfig,
)


class TestLLMConfig:
    """LLM 配置测试"""

    def test_default_values(self):
        """测试默认值"""
        config = LLMConfig()
        assert config.provider == "siliconflow"
        assert config.model == "Pro/deepseek-ai/DeepSeek-V3.2"
        assert config.api_key is None
        assert config.temperature == 0.7
        assert config.max_tokens == 4096

    def test_custom_values(self):
        """测试自定义值"""
        config = LLMConfig(
            provider="anthropic",
            model="claude-3-opus",
            api_key="test-key",
            temperature=0.5,
            max_tokens=8192,
        )
        assert config.provider == "anthropic"
        assert config.model == "claude-3-opus"
        assert config.api_key == "test-key"
        assert config.temperature == 0.5
        assert config.max_tokens == 8192

    def test_temperature_validation(self):
        """测试温度范围验证"""
        with pytest.raises(ValueError):
            LLMConfig(temperature=3.0)  # 超过最大值
        with pytest.raises(ValueError):
            LLMConfig(temperature=-1.0)  # 低于最小值


class TestDatabaseConfig:
    """数据库配置测试"""

    def test_default_values(self):
        """测试默认值"""
        config = DatabaseConfig()
        assert config.url == "sqlite:///./data/lanobot.db"
        assert config.echo is False


class TestMessageBusConfig:
    """消息总线配置测试"""

    def test_default_values(self):
        """测试默认值"""
        config = MessageBusConfig()
        assert config.max_queue_size == 1000
        assert config.timeout == 30.0


class TestLoggingConfig:
    """日志配置测试"""

    def test_default_values(self):
        """测试默认值"""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.file is None


class TestAppConfig:
    """应用配置测试"""

    def test_default_values(self):
        """测试默认值"""
        config = AppConfig()
        assert config.version == "0.1.0"
        assert config.debug is False
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.database, DatabaseConfig)
        assert isinstance(config.message_bus, MessageBusConfig)
        assert isinstance(config.logging, LoggingConfig)

    def test_nested_config(self):
        """测试嵌套配置"""
        config = AppConfig(
            debug=True,
            llm=LLMConfig(provider="deepseek", model="deepseek-chat"),
        )
        assert config.debug is True
        assert config.llm.provider == "deepseek"
        assert config.llm.model == "deepseek-chat"

    def test_data_dir_property(self):
        """测试 data_dir 属性"""
        config = AppConfig()
        assert config.data_dir == Path("./data")

    def test_config_dir_property(self):
        """测试 config_dir 属性"""
        config = AppConfig()
        assert config.config_dir == Path("./config")