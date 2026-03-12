"""Provider 注册表测试."""

import pytest

from lanobot.providers.registry import (
    PROVIDERS,
    find_by_model,
    find_by_name,
    find_gateway,
    get_default_provider,
    get_provider,
    list_providers,
)


class TestProviderSpec:
    """ProviderSpec 数据类测试."""

    def test_create_spec(self):
        """测试创建 Provider 规范."""
        from lanobot.providers.registry import ProviderSpec

        spec = ProviderSpec(
            name="test",
            keywords=("test",),
            env_key="TEST_API_KEY",
            display_name="Test Provider",
            litellm_prefix="test",
        )
        assert spec.name == "test"
        assert spec.litellm_prefix == "test"
        assert spec.label == "Test Provider"

    def test_label_property(self):
        """测试 label 属性."""
        spec = get_provider("siliconflow")
        assert spec.label == "SiliconFlow"


class TestProviderRegistry:
    """Provider 注册表测试."""

    def test_providers_not_empty(self):
        """测试注册表不为空."""
        assert len(PROVIDERS) > 0

    def test_list_providers(self):
        """测试列出所有 Provider."""
        providers = list_providers()
        assert isinstance(providers, list)
        assert len(providers) > 0

    def test_gateway_providers(self):
        """测试网关 Provider."""
        # OpenRouter - 通过 API Key 前缀检测
        spec = get_provider("openrouter")
        assert spec.name == "openrouter"
        assert spec.is_gateway is True
        assert spec.detect_by_key_prefix == "sk-or-"
        assert spec.default_api_base == "https://openrouter.ai/api/v1"

        # SiliconFlow - 通过 URL 关键字检测
        spec = get_provider("siliconflow")
        assert spec.name == "siliconflow"
        assert spec.is_gateway is True
        assert "siliconflow" in spec.detect_by_base_keyword

        # VolcEngine
        spec = get_provider("volcengine")
        assert spec.name == "volcengine"
        assert spec.is_gateway is True
        assert "volces" in spec.detect_by_base_keyword

    def test_standard_providers(self):
        """测试标准 Provider."""
        # DeepSeek
        spec = get_provider("deepseek")
        assert spec.name == "deepseek"
        assert spec.is_gateway is False
        assert spec.litellm_prefix == "deepseek"
        assert spec.env_key == "DEEPSEEK_API_KEY"

        # OpenAI
        spec = get_provider("openai")
        assert spec.name == "openai"
        assert spec.litellm_prefix == ""

        # Anthropic
        spec = get_provider("anthropic")
        assert spec.name == "anthropic"
        assert spec.supports_prompt_caching is True

    def test_local_providers(self):
        """测试本地 Provider."""
        # Ollama
        spec = get_provider("ollama")
        assert spec.name == "ollama"
        assert spec.is_local is True
        assert spec.default_api_base == "http://localhost:11434"

        # vLLM
        spec = get_provider("vllm")
        assert spec.name == "vllm"
        assert spec.is_local is True

    def test_direct_providers(self):
        """测试直接调用 Provider."""
        spec = get_provider("custom")
        assert spec.name == "custom"
        assert spec.is_direct is True

        spec = get_provider("azure_openai")
        assert spec.name == "azure_openai"
        assert spec.is_direct is True

    def test_oauth_providers(self):
        """测试 OAuth Provider."""
        spec = get_provider("openai_codex")
        assert spec.name == "openai_codex"
        assert spec.is_oauth is True
        assert spec.env_key == ""

    def test_chinese_providers(self):
        """测试中文 Provider."""
        # Zhipu (智谱)
        spec = get_provider("zhipu")
        assert spec.name == "zhipu"
        assert "glm" in spec.keywords
        assert "zhi" in spec.display_name.lower()

        # DashScope (阿里云)
        spec = get_provider("dashscope")
        assert spec.name == "dashscope"
        assert "qwen" in spec.keywords

        # Moonshot (月之暗面)
        spec = get_provider("moonshot")
        assert spec.name == "moonshot"
        assert "kimi" in spec.keywords

        # MiniMax
        spec = get_provider("minimax")
        assert spec.name == "minimax"
        assert spec.default_api_base == "https://api.minimax.io/v1"

    def test_unknown_provider_raises_error(self):
        """测试未知 Provider 抛出错误."""
        with pytest.raises(ValueError) as exc:
            get_provider("unknown_provider")
        assert "Unknown provider" in str(exc.value)

    def test_default_provider(self):
        """测试获取默认 Provider (第一个非 Direct)."""
        default = get_default_provider()
        # 第一个非 Direct 应该是 OpenRouter (Gateway)
        assert default.is_gateway is True

    def test_find_by_name(self):
        """测试按名称查找."""
        spec = find_by_name("deepseek")
        assert spec is not None
        assert spec.name == "deepseek"

        # 不存在的名称返回 None
        assert find_by_name("nonexistent") is None

    def test_find_gateway_by_key_prefix(self):
        """测试通过 API Key 前缀检测网关."""
        # sk-or- -> OpenRouter
        spec = find_gateway(
            provider_name=None,
            api_key="sk-or-v1xxxxx",
            api_base=None,
        )
        assert spec is not None
        assert spec.name == "openrouter"

    def test_find_gateway_by_base_keyword(self):
        """测试通过 URL 关键字检测网关."""
        # siliconflow in URL -> SiliconFlow
        spec = find_gateway(
            provider_name=None,
            api_key="sk-xxxx",
            api_base="https://api.siliconflow.cn/v1",
        )
        assert spec is not None
        assert spec.name == "siliconflow"

    def test_find_by_model(self):
        """测试通过模型名称查找 Provider."""
        # gpt-* -> OpenAI
        spec = find_by_model("gpt-4o")
        assert spec is not None
        assert spec.name == "openai"

        # claude-* -> Anthropic
        spec = find_by_model("claude-3-opus")
        assert spec is not None
        assert spec.name == "anthropic"

        # deepseek-chat -> DeepSeek
        spec = find_by_model("deepseek-chat")
        assert spec is not None
        assert spec.name == "deepseek"

        # qwen-max -> DashScope
        spec = find_by_model("qwen-max")
        assert spec is not None
        assert spec.name == "dashscope"

        # kimi-k2.5 -> Moonshot
        spec = find_by_model("kimi-k2.5")
        assert spec is not None
        assert spec.name == "moonshot"

    def test_model_overrides(self):
        """测试模型参数覆盖."""
        spec = get_provider("moonshot")
        assert spec.model_overrides is not None
        # kimi-k2.5 有 temperature 覆盖
        has_override = any(m == "kimi-k2.5" for m, _ in spec.model_overrides)
        assert has_override is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])