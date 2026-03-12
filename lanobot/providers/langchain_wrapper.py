"""LangChain LLM 包装器 - 支持多种 Provider."""

from typing import Optional

from langchain_openai import ChatOpenAI


# Provider 默认配置
PROVIDER_DEFAULTS = {
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "default_model": "Pro/deepseek-ai/DeepSeek-V3.2",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
    },
    "openai": {
        "base_url": None,  # 使用官方 API
        "default_model": "gpt-4o-mini",
    },
}


def create_llm(
    provider: str = "siliconflow",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> ChatOpenAI:
    """创建 LangChain LLM 实例.

    Args:
        provider: 提供商名称 (siliconflow/deepseek/openai)
        model: 模型名称，默认使用提供商的最佳模型
        api_key: API Key，默认从环境变量或配置读取
        api_base: API 基础 URL
        temperature: 温度参数
        max_tokens: 最大 token 数

    Returns:
        ChatOpenAI 实例

    Examples:
        >>> llm = create_llm(
        ...     provider="siliconflow",
        ...     model="Pro/deepseek-ai/DeepSeek-V3.2",
        ...     api_key="sk-xxx"
        ... )
    """
    # 获取提供商默认配置
    provider_config = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["siliconflow"])

    # 确定使用的模型
    actual_model = model or provider_config["default_model"]

    # 确定 base_url
    actual_base_url = api_base or provider_config["base_url"]

    # 构建参数
    kwargs = {
        "model": actual_model,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if api_key:
        kwargs["api_key"] = api_key
    if actual_base_url:
        kwargs["base_url"] = actual_base_url

    return ChatOpenAI(**kwargs)