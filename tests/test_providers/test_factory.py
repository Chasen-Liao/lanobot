"""Provider 工厂函数测试."""

import os
from unittest.mock import patch, MagicMock

import pytest

from lanobot.providers.factory import (
    create_llm,
    create_llm_with_config,
    detect_provider_from_config,
)


class TestCreateLLM:
    """create_llm 工厂函数测试."""

    @patch("lanobot.providers.factory.ChatOpenAI")
    def test_create_siliconflow_llm(self, mock_openai):
        """测试创建 SiliconFlow LLM."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            create_llm(provider="siliconflow", api_key="test-key")
            mock_openai.assert_called_once()
            call_kwargs = mock_openai.call_args[1]
            # SiliconFlow 使用默认模型为空，需要显式指定
            assert call_kwargs["base_url"] == "https://api.siliconflow.cn/v1"
            assert call_kwargs["api_key"] == "test-key"

    @patch("lanobot.providers.factory.ChatOpenAI")
    def test_create_deepseek_llm_with_prefix(self, mock_openai):
        """测试创建 DeepSeek LLM (需要前缀)."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            create_llm(provider="deepseek", model="deepseek-chat", api_key="test-key")
            mock_openai.assert_called_once()
            call_kwargs = mock_openai.call_args[1]
            # DeepSeek 需要添加 litellm_prefix
            assert call_kwargs["model"] == "deepseek/deepseek-chat"

    @patch("lanobot.providers.factory.ChatOpenAI")
    def test_create_openai_llm(self, mock_openai):
        """测试创建 OpenAI LLM."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            create_llm(provider="openai", api_key="test-key")
            mock_openai.assert_called_once()
            call_kwargs = mock_openai.call_args[1]
            # OpenAI 不需要 base_url，使用官方 API
            assert "base_url" not in call_kwargs

    @patch("lanobot.providers.factory.ChatOpenAI")
    def test_custom_base_url_override(self, mock_openai):
        """测试自定义 base_url 覆盖默认值."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            create_llm(
                provider="deepseek",
                model="deepseek-chat",
                api_key="test-key",
                base_url="https://custom-proxy.com/v1",
            )
            mock_openai.assert_called_once()
            call_kwargs = mock_openai.call_args[1]
            assert call_kwargs["base_url"] == "https://custom-proxy.com/v1"

    @patch("lanobot.providers.factory.ChatOpenAI")
    def test_extra_headers(self, mock_openai):
        """测试传递额外请求头."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            create_llm(
                provider="openrouter",
                model="openai/gpt-4o-mini",
                api_key="sk-or-xxx",
                extra_headers={"HTTP-Referer": "https://example.com"},
            )
            mock_openai.assert_called_once()
            call_kwargs = mock_openai.call_args[1]
            assert call_kwargs["extra_headers"]["HTTP-Referer"] == "https://example.com"

    @patch("lanobot.providers.factory.ChatOpenAI")
    def test_reasoning_effort(self, mock_openai):
        """测试推理努力参数."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            create_llm(
                provider="deepseek",
                model="deepseek-reasoner",
                api_key="test-key",
                reasoning_effort="high",
            )
            mock_openai.assert_called_once()
            call_kwargs = mock_openai.call_args[1]
            assert call_kwargs["reasoning_effort"] == "high"

    @patch("lanobot.providers.factory.ChatOpenAI")
    def test_skip_prefix(self, mock_openai):
        """测试跳过添加前缀."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            # 模型已经包含 deepseek/ 前缀，不应重复添加
            create_llm(provider="deepseek", model="deepseek/deepseek-chat", api_key="test-key")
            mock_openai.assert_called_once()
            call_kwargs = mock_openai.call_args[1]
            assert call_kwargs["model"] == "deepseek/deepseek-chat"

    @patch("lanobot.providers.factory.ChatOpenAI")
    def test_strip_model_prefix(self, mock_openai):
        """测试剥离模型前缀 (AiHubMix)."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            # AiHubMix 需要 strip_model_prefix
            create_llm(provider="aihubmix", model="anthropic/claude-3-haiku", api_key="test-key")
            mock_openai.assert_called_once()
            call_kwargs = mock_openai.call_args[1]
            # anthropic/claude-3 -> claude-3 -> openai/claude-3
            assert call_kwargs["model"] == "openai/claude-3-haiku"

    @patch("lanobot.providers.factory.ChatOpenAI")
    def test_local_provider_ollama(self, mock_openai):
        """测试本地 Provider (Ollama)."""
        with patch.dict(os.environ, {"OLLAMA_API_KEY": "test-key"}):
            create_llm(provider="ollama", model="llama3", api_key="test-key")
            mock_openai.assert_called_once()
            call_kwargs = mock_openai.call_args[1]
            # Ollama 使用 ollama_chat 前缀
            assert call_kwargs["model"] == "ollama_chat/llama3"
            assert call_kwargs["base_url"] == "http://localhost:11434"

    @patch("lanobot.providers.factory.ChatOpenAI")
    def test_api_key_from_env(self, mock_openai):
        """测试从环境变量获取 API Key."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "env-key"}):
            create_llm(provider="deepseek", model="deepseek-chat")
            mock_openai.assert_called_once()
            call_kwargs = mock_openai.call_args[1]
            assert call_kwargs["api_key"] == "env-key"

    def test_unknown_provider_raises_error(self):
        """测试未知 Provider 抛出错误."""
        with pytest.raises(ValueError):
            create_llm(provider="unknown")

    @patch("lanobot.providers.factory.ChatOpenAI")
    def test_passes_extra_kwargs(self, mock_openai):
        """测试传递额外参数."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            create_llm(
                provider="openai",
                api_key="test-key",
                timeout=60,
                streaming=True,
            )
            mock_openai.assert_called_once()
            call_kwargs = mock_openai.call_args[1]
            assert call_kwargs["timeout"] == 60
            assert call_kwargs["streaming"] is True


class TestCreateLLMWithConfig:
    """create_llm_with_config 测试."""

    @patch("lanobot.providers.factory.ChatOpenAI")
    def test_create_from_config(self, mock_openai):
        """测试从配置字典创建 LLM."""
        config = {
            "provider": "openai",
            "model": "gpt-4o",
            "temperature": 0.5,
            "max_tokens": 2048,
        }
        create_llm_with_config(config)
        mock_openai.assert_called_once()
        call_kwargs = mock_openai.call_args[1]
        assert call_kwargs["model"] == "gpt-4o"
        assert call_kwargs["temperature"] == 0.5
        assert call_kwargs["max_tokens"] == 2048

    @patch("lanobot.providers.factory.ChatOpenAI")
    def test_config_with_extra_headers(self, mock_openai):
        """测试配置中的 extra_headers."""
        config = {
            "provider": "openrouter",
            "model": "openai/gpt-4o-mini",
            "api_key": "sk-or-xxx",
            "extra_headers": {"X-Custom-Header": "value"},
        }
        create_llm_with_config(config)
        mock_openai.assert_called_once()
        call_kwargs = mock_openai.call_args[1]
        assert call_kwargs["extra_headers"]["X-Custom-Header"] == "value"


class TestDetectProviderFromConfig:
    """detect_provider_from_config 测试."""

    def test_detect_by_provider_name(self):
        """测试通过 Provider 名称检测."""
        result = detect_provider_from_config(provider_name="deepseek")
        assert result == "deepseek"

    def test_detect_by_api_key_prefix(self):
        """测试通过 API Key 前缀检测 (OpenRouter)."""
        result = detect_provider_from_config(
            provider_name=None,
            api_key="sk-or-v1xxxxx",
            api_base=None,
        )
        assert result == "openrouter"

    def test_detect_by_api_base_keyword(self):
        """测试通过 URL 关键字检测 (SiliconFlow)."""
        result = detect_provider_from_config(
            provider_name=None,
            api_key="sk-xxxx",
            api_base="https://api.siliconflow.cn/v1",
        )
        assert result == "siliconflow"

    def test_detect_by_model_keyword(self):
        """测试通过模型关键字检测."""
        result = detect_provider_from_config(model="gpt-4o")
        assert result == "openai"

        result = detect_provider_from_config(model="claude-3-opus")
        assert result == "anthropic"

        result = detect_provider_from_config(model="qwen-max")
        assert result == "dashscope"

    def test_detect_priority(self):
        """测试检测优先级."""
        # provider_name 优先于其他检测
        result = detect_provider_from_config(
            provider_name="deepseek",
            api_key="sk-or-xxx",  # 会被识别为 openrouter
            api_base="https://api.siliconflow.cn/v1",  # 会被识别为 siliconflow
            model="gpt-4o",  # 会识别为 openai
        )
        assert result == "deepseek"

    def test_no_match_returns_none(self):
        """测试无匹配时返回 None."""
        result = detect_provider_from_config()
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])