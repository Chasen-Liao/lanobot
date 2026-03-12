"""Provider 工厂函数 - 创建 LLM 实例.

支持多种 Provider 的配置选项，包括:
- extra_headers: 自定义请求头
- reasoning_effort: 推理努力程度 (low/medium/high)
- 各种模型参数覆盖
"""

import os
from typing import Any, Dict, Optional

from langchain_openai import ChatOpenAI

from lanobot.providers.registry import ProviderSpec, get_provider


def create_llm(
    provider: str = "siliconflow",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    extra_headers: Optional[Dict[str, str]] = None,
    reasoning_effort: Optional[str] = None,
    **kwargs: Any,
) -> ChatOpenAI:
    """创建 LangChain LLM 实例.

    Args:
        provider: 提供商名称 (siliconflow/deepseek/openai/anthropic 等)
        model: 模型名称，默认使用提供商的默认模型
        api_key: API Key，默认从环境变量读取
        base_url: API 基础 URL，覆盖默认的 Provider URL
        temperature: 温度参数
        max_tokens: 最大 token 数
        extra_headers: 自定义请求头 (dict)
        reasoning_effort: 推理努力 (low/medium/high)，仅支持部分模型
        **kwargs: 其他传递给 ChatOpenAI 的参数

    Returns:
        ChatOpenAI 实例

    Examples:
        >>> llm = create_llm("siliconflow")
        >>> llm = create_llm("deepseek", model="deepseek-chat")
        >>> llm = create_llm("openai", model="gpt-4o", temperature=0.5)
        >>> llm = create_llm("openrouter", extra_headers={"HTTP-Referer": "https://example.com"})
    """
    # 获取 Provider 规范
    spec = get_provider(provider)

    # 确定使用的模型
    actual_model = model or spec.default_model

    # 处理模型前缀 (某些 Provider 需要 LiteLLM 风格前缀)
    if spec.litellm_prefix and actual_model:
        # 检查是否需要添加前缀
        should_add_prefix = True
        for skip_prefix in spec.skip_prefixes:
            if actual_model.startswith(skip_prefix):
                should_add_prefix = False
                break

        if should_add_prefix:
            # 如果 strip_model_prefix 为 True，先剥离原有前缀
            if spec.strip_model_prefix and "/" in actual_model:
                actual_model = actual_model.split("/", 1)[1]

            # 添加 litellm_prefix
            actual_model = f"{spec.litellm_prefix}/{actual_model}"

    # 获取 API Key (优先使用传入的，否则从环境变量)
    if not api_key:
        api_key = os.environ.get(spec.env_key)

    # 构建参数
    llm_kwargs: Dict[str, Any] = {
        "model": actual_model,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    # 添加 API Key (仅当提供时)
    if api_key:
        llm_kwargs["api_key"] = api_key

    # 添加 base_url (优先使用传入的，否则使用 Provider 默认的)
    if base_url:
        llm_kwargs["base_url"] = base_url
    elif spec.default_api_base:
        llm_kwargs["base_url"] = spec.default_api_base

    # 添加 extra_headers (仅当提供时)
    if extra_headers:
        llm_kwargs["extra_headers"] = extra_headers

    # 添加 reasoning_effort (仅当提供时)
    if reasoning_effort:
        llm_kwargs["reasoning_effort"] = reasoning_effort

    # 检查模型参数覆盖
    if spec.model_overrides and model:
        for override_model, override_params in spec.model_overrides:
            if model == override_model or actual_model.endswith(f"/{override_model}"):
                llm_kwargs.update(override_params)
                break

    # 合并其他参数
    llm_kwargs.update(kwargs)

    return ChatOpenAI(**llm_kwargs)


def create_llm_with_config(config: Dict[str, Any]) -> ChatOpenAI:
    """根据配置字典创建 LLM 实例.

    Args:
        config: 配置字典，支持以下键:
            - provider: 提供商名称
            - model: 模型名称 (可选)
            - api_key: API Key (可选)
            - base_url: API 基础 URL (可选)
            - temperature: 温度 (可选)
            - max_tokens: 最大 tokens (可选)
            - extra_headers: 自定义请求头 (可选)
            - reasoning_effort: 推理努力 (可选)
            - 其他 ChatOpenAI 参数

    Returns:
        ChatOpenAI 实例
    """
    return create_llm(
        provider=config.get("provider", "siliconflow"),
        model=config.get("model"),
        api_key=config.get("api_key"),
        base_url=config.get("base_url"),
        temperature=config.get("temperature", 0.2),
        max_tokens=config.get("max_tokens", 4096),
        extra_headers=config.get("extra_headers"),
        reasoning_effort=config.get("reasoning_effort"),
        **{
            k: v
            for k, v in config.items()
            if k
            not in (
                "provider",
                "model",
                "api_key",
                "base_url",
                "temperature",
                "max_tokens",
                "extra_headers",
                "reasoning_effort",
            )
        },
    )


def detect_provider_from_config(
    provider_name: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    model: Optional[str] = None,
) -> Optional[str]:
    """根据配置自动检测 Provider.

    优先级:
      1. provider_name - 如果指定，直接使用
      2. api_key 前缀 - 如 "sk-or-" -> openrouter
      3. api_base 关键字 - 如 "siliconflow" -> siliconflow
      4. model 关键字 - 如 "gpt-4" -> openai

    Args:
        provider_name: 显式指定的提供商名称
        api_key: API Key
        api_base: API 基础 URL
        model: 模型名称

    Returns:
        检测到的 Provider 名称，如未检测到则返回 None
    """
    from lanobot.providers.registry import find_by_name, find_gateway, find_by_model

    # 1. 如果指定了 provider_name 且有效，直接使用
    if provider_name:
        spec = find_by_name(provider_name)
        if spec:
            return provider_name

    # 2. 检测 Gateway/Local
    gateway_spec = find_gateway(
        provider_name=provider_name,
        api_key=api_key,
        api_base=api_base,
    )
    if gateway_spec:
        return gateway_spec.name

    # 3. 按模型名称检测
    if model:
        model_spec = find_by_model(model)
        if model_spec:
            return model_spec.name

    return None