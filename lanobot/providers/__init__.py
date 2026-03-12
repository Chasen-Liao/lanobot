"""LLM Provider 包装器.

支持多类型 Provider:
- Gateway: 网关 (OpenRouter, AiHubMix, VolcEngine, SiliconFlow)
- Standard: 标准 (OpenAI, Anthropic, DeepSeek, Gemini, Zhipu, DashScope, Moonshot, MiniMax, Groq)
- Local: 本地 (vLLM, Ollama)
- Direct: 直接调用 (Azure OpenAI, Custom)
- OAuth: OAuth 认证 (OpenAI Codex, GitHub Copilot)
"""

from lanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from lanobot.providers.factory import (
    create_llm,
    create_llm_with_config,
    detect_provider_from_config,
)
from lanobot.providers.registry import (
    ProviderSpec,
    find_by_model,
    find_by_name,
    find_gateway,
    get_default_provider,
    get_provider,
    list_providers,
    PROVIDERS,
)
from lanobot.providers.langchain_wrapper import create_llm as _create_llm_legacy

# 为了向后兼容，保留旧的 create_llm
create_llm_legacy = _create_llm_legacy

__all__ = [
    # 抽象基类 (base.py)
    "LLMProvider",
    "LLMResponse",
    "ToolCallRequest",
    # 工厂函数
    "create_llm",
    "create_llm_with_config",
    "create_llm_legacy",
    "detect_provider_from_config",
    # 注册表
    "ProviderSpec",
    "get_provider",
    "find_by_name",
    "find_by_model",
    "find_gateway",
    "list_providers",
    "get_default_provider",
    "PROVIDERS",
]