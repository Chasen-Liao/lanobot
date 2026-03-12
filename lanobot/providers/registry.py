"""Provider 注册表 - 支持多 LLM 提供商.

该模块参考 nanobot 的 Provider 注册表设计，支持以下类型的 Provider:
- Gateway: 网关，可以路由任意模型 (OpenRouter, AiHubMix, VolcEngine, SiliconFlow)
- Standard: 标准提供商，按模型名称匹配 (OpenAI, Anthropic, DeepSeek, Gemini 等)
- Local: 本地部署 (vLLM, Ollama)
- Direct: 直接调用 (Azure OpenAI, Custom)
- OAuth: OAuth 认证 (OpenAI Codex, GitHub Copilot)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class ProviderSpec:
    """提供商规范定义.

    Attributes:
        name: 提供商配置名称 (如 "siliconflow", "deepseek", "openrouter")
        keywords: 模型名称关键字，用于自动匹配 (不区分大小写)
        env_key: API Key 环境变量名
        display_name: 显示名称 (如 "SiliconFlow")
        litellm_prefix: LiteLLM 风格前缀 (如 "deepseek/" 用于 DeepSeek API)
        skip_prefixes: 跳过添加前缀的模型前缀元组
        env_extras: 额外环境变量元组 ((环境变量名, 值模板), ...)
        is_gateway: 是否为网关 (可路由任意模型)
        is_local: 是否为本地部署
        detect_by_key_prefix: API Key 前缀匹配 (如 "sk-or-" 匹配 OpenRouter)
        detect_by_base_keyword: API URL 关键字匹配
        default_api_base: 默认 API 基础 URL
        strip_model_prefix: 是否在重新添加前缀前剥离原有前缀
        model_overrides: 模型参数覆盖 ((模型名, 参数字典), ...)
        is_oauth: 是否为 OAuth 认证
        is_direct: 是否直接调用 (绕过 LiteLLM)
        supports_prompt_caching: 是否支持提示缓存
    """

    name: str
    keywords: tuple[str, ...]
    env_key: str
    display_name: str = ""
    litellm_prefix: str = ""
    skip_prefixes: tuple[str, ...] = ()
    env_extras: tuple[tuple[str, str], ...] = ()
    is_gateway: bool = False
    is_local: bool = False
    detect_by_key_prefix: str = ""
    detect_by_base_keyword: str = ""
    default_api_base: str = ""
    strip_model_prefix: bool = False
    model_overrides: tuple[tuple[str, dict[str, Any]], ...] = ()
    is_oauth: bool = False
    is_direct: bool = False
    supports_prompt_caching: bool = False

    @property
    def label(self) -> str:
        """获取显示名称."""
        return self.display_name or self.name.title()

    @property
    def default_model(self) -> str:
        """获取默认模型 (子类可覆盖)."""
        return ""


# ============================================================================
# Provider 注册表 - 按优先级排序
# 顺序很重要 - 控制匹配优先级和回退。网关优先。
# ============================================================================

PROVIDERS: tuple[ProviderSpec, ...] = (
    # === Direct Providers (直接调用，绕过 LiteLLM) ==========================
    # Custom: 自定义 OpenAI 兼容端点
    ProviderSpec(
        name="custom",
        keywords=(),
        env_key="",
        display_name="Custom",
        litellm_prefix="",
        is_direct=True,
    ),
    # Azure OpenAI: 直接 API 调用
    ProviderSpec(
        name="azure_openai",
        keywords=("azure", "azure-openai"),
        env_key="",
        display_name="Azure OpenAI",
        litellm_prefix="",
        is_direct=True,
    ),

    # === Gateways (网关，通过 api_key/api_base 自动检测) ===================
    # 可以路由任意模型，所以在回退时优先匹配

    # OpenRouter: 全球网关，API Key 以 "sk-or-" 开头
    ProviderSpec(
        name="openrouter",
        keywords=("openrouter",),
        env_key="OPENROUTER_API_KEY",
        display_name="OpenRouter",
        litellm_prefix="openrouter",
        is_gateway=True,
        detect_by_key_prefix="sk-or-",
        detect_by_base_keyword="openrouter",
        default_api_base="https://openrouter.ai/api/v1",
        supports_prompt_caching=True,
    ),

    # AiHubMix: 全球网关，OpenAI 兼容接口
    ProviderSpec(
        name="aihubmix",
        keywords=("aihubmix",),
        env_key="OPENAI_API_KEY",
        display_name="AiHubMix",
        litellm_prefix="openai",
        is_gateway=True,
        detect_by_base_keyword="aihubmix",
        default_api_base="https://aihubmix.com/v1",
        strip_model_prefix=True,  # anthropic/claude-3 -> claude-3 -> openai/claude-3
    ),

    # SiliconFlow (硅基流动): OpenAI 兼容网关
    # 注意：SiliconFlow 直接使用模型名，不需要 litellm 前缀
    ProviderSpec(
        name="siliconflow",
        keywords=("siliconflow",),
        env_key="OPENAI_API_KEY",
        display_name="SiliconFlow",
        litellm_prefix=None,  # 不添加前缀，直接使用原始模型名
        is_gateway=True,
        detect_by_base_keyword="siliconflow",
        default_api_base="https://api.siliconflow.cn/v1",
    ),

    # VolcEngine (火山引擎/方舟): OpenAI 兼容网关
    ProviderSpec(
        name="volcengine",
        keywords=("volcengine", "volces", "ark"),
        env_key="OPENAI_API_KEY",
        display_name="VolcEngine",
        litellm_prefix="volcengine",
        is_gateway=True,
        detect_by_base_keyword="volces",
        default_api_base="https://ark.cn-beijing.volces.com/api/v3",
    ),

    # === Standard Providers (标准提供商，按模型名称关键字匹配) =============

    # Anthropic: LiteLLM 原生识别 "claude-*"
    ProviderSpec(
        name="anthropic",
        keywords=("anthropic", "claude"),
        env_key="ANTHROPIC_API_KEY",
        display_name="Anthropic",
        litellm_prefix="",
        supports_prompt_caching=True,
    ),

    # OpenAI: LiteLLM 原生识别 "gpt-*"
    ProviderSpec(
        name="openai",
        keywords=("openai", "gpt"),
        env_key="OPENAI_API_KEY",
        display_name="OpenAI",
        litellm_prefix="",
    ),

    # OpenAI Codex: OAuth 认证
    ProviderSpec(
        name="openai_codex",
        keywords=("openai-codex",),
        env_key="",
        display_name="OpenAI Codex",
        litellm_prefix="",
        detect_by_base_keyword="codex",
        default_api_base="https://chatgpt.com/backend-api",
        is_oauth=True,
    ),

    # GitHub Copilot: OAuth 认证
    ProviderSpec(
        name="github_copilot",
        keywords=("github_copilot", "copilot"),
        env_key="",
        display_name="GitHub Copilot",
        litellm_prefix="github_copilot",
        skip_prefixes=("github_copilot/",),
        is_oauth=True,
    ),

    # DeepSeek: 需要 "deepseek/" 前缀
    ProviderSpec(
        name="deepseek",
        keywords=("deepseek",),
        env_key="DEEPSEEK_API_KEY",
        display_name="DeepSeek",
        litellm_prefix="deepseek",
        skip_prefixes=("deepseek/",),
    ),

    # Gemini: 需要 "gemini/" 前缀
    ProviderSpec(
        name="gemini",
        keywords=("gemini",),
        env_key="GEMINI_API_KEY",
        display_name="Gemini",
        litellm_prefix="gemini",
        skip_prefixes=("gemini/",),
    ),

    # Zhipu (智谱): 需要 "zai/" 前缀
    ProviderSpec(
        name="zhipu",
        keywords=("zhipu", "glm", "zai"),
        env_key="ZAI_API_KEY",
        display_name="Zhipu AI",
        litellm_prefix="zai",
        skip_prefixes=("zhipu/", "zai/", "openrouter/", "hosted_vllm/"),
        env_extras=(("ZHIPUAI_API_KEY", "{api_key}"),),
    ),

    # DashScope (阿里云): Qwen 模型，需要 "dashscope/" 前缀
    ProviderSpec(
        name="dashscope",
        keywords=("qwen", "dashscope"),
        env_key="DASHSCOPE_API_KEY",
        display_name="DashScope",
        litellm_prefix="dashscope",
        skip_prefixes=("dashscope/", "openrouter/"),
    ),

    # Moonshot (月之暗面): Kimi 模型，需要 "moonshot/" 前缀
    ProviderSpec(
        name="moonshot",
        keywords=("moonshot", "kimi"),
        env_key="MOONSHOT_API_KEY",
        display_name="Moonshot",
        litellm_prefix="moonshot",
        skip_prefixes=("moonshot/", "openrouter/"),
        default_api_base="https://api.moonshot.ai/v1",
        model_overrides=(("kimi-k2.5", {"temperature": 1.0}),),
    ),

    # MiniMax: 需要 "minimax/" 前缀
    ProviderSpec(
        name="minimax",
        keywords=("minimax",),
        env_key="MINIMAX_API_KEY",
        display_name="MiniMax",
        litellm_prefix="minimax",
        skip_prefixes=("minimax/", "openrouter/"),
        default_api_base="https://api.minimax.io/v1",
    ),

    # === Local (本地部署) ==================================================

    # vLLM: 本地 OpenAI 兼容服务器
    ProviderSpec(
        name="vllm",
        keywords=("vllm",),
        env_key="HOSTED_VLLM_API_KEY",
        display_name="vLLM/Local",
        litellm_prefix="hosted_vllm",
        is_local=True,
    ),

    # Ollama: 本地模型
    ProviderSpec(
        name="ollama",
        keywords=("ollama", "nemotron"),
        env_key="OLLAMA_API_KEY",
        display_name="Ollama",
        litellm_prefix="ollama_chat",
        skip_prefixes=("ollama/", "ollama_chat/"),
        is_local=True,
        detect_by_base_keyword="11434",
        default_api_base="http://localhost:11434",
    ),

    # === Auxiliary (辅助 Provider) =========================================

    # Groq: 主要用于 Whisper 语音转录，也可用于 LLM
    ProviderSpec(
        name="groq",
        keywords=("groq",),
        env_key="GROQ_API_KEY",
        display_name="Groq",
        litellm_prefix="groq",
        skip_prefixes=("groq/",),
    ),
)

# Provider 名称到 Spec 的映射 (用于快速查找)
_PROVIDER_MAP: dict[str, ProviderSpec] = {p.name: p for p in PROVIDERS}


# ============================================================================
# 查找辅助函数
# ============================================================================


def find_by_model(model: str) -> ProviderSpec | None:
    """根据模型名称匹配标准提供商 (不区分大小写).

    跳过网关和本地部署 - 它们通过 api_key/api_base 匹配.

    Args:
        model: 模型名称

    Returns:
        匹配的 ProviderSpec，如未找到则返回 None
    """
    model_lower = model.lower()
    model_normalized = model_lower.replace("-", "_")
    model_prefix = model_lower.split("/", 1)[0] if "/" in model_lower else ""
    normalized_prefix = model_prefix.replace("-", "_")

    # 获取标准提供商 (非网关、非本地)
    std_specs = [s for s in PROVIDERS if not s.is_gateway and not s.is_local]

    # 优先精确匹配提供商前缀
    # 防止 `github-copilot/...codex` 匹配到 openai_codex
    for spec in std_specs:
        if model_prefix and normalized_prefix == spec.name:
            return spec

    # 按关键字匹配
    for spec in std_specs:
        if any(
            kw in model_lower or kw.replace("-", "_") in model_normalized
            for kw in spec.keywords
        ):
            return spec
    return None


def find_gateway(
    provider_name: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
) -> ProviderSpec | None:
    """检测网关/本地提供商.

    优先级:
      1. provider_name - 如果映射到网关/本地规范，直接使用
      2. api_key 前缀 - 如 "sk-or-" -> OpenRouter
      3. api_base 关键字 - 如 URL 中包含 "aihubmix"

    Args:
        provider_name: 提供商名称
        api_key: API Key
        api_base: API 基础 URL

    Returns:
        匹配的 ProviderSpec，如未找到则返回 None
    """
    # 1. 按配置键直接匹配
    if provider_name:
        spec = find_by_name(provider_name)
        if spec and (spec.is_gateway or spec.is_local):
            return spec

    # 2. 通过 api_key 前缀 / api_base 关键字自动检测
    for spec in PROVIDERS:
        if spec.detect_by_key_prefix and api_key and api_key.startswith(spec.detect_by_key_prefix):
            return spec
        if spec.detect_by_base_keyword and api_base and spec.detect_by_base_keyword in api_base:
            return spec

    return None


def find_by_name(name: str) -> ProviderSpec | None:
    """根据配置字段名称查找提供商规范，如 "dashscope".

    Args:
        name: 提供商名称

    Returns:
        ProviderSpec，如未找到则返回 None
    """
    return _PROVIDER_MAP.get(name)


def get_provider(name: str) -> ProviderSpec:
    """根据名称获取 Provider 规范.

    Args:
        name: Provider 名称

    Returns:
        ProviderSpec 实例

    Raises:
        ValueError: 当 provider 不存在时
    """
    spec = find_by_name(name)
    if spec is None:
        available = ", ".join(_PROVIDER_MAP.keys())
        raise ValueError(f"Unknown provider: {name}. Available: {available}")
    return spec


def list_providers() -> list[str]:
    """获取所有可用的 Provider 名称.

    Returns:
        Provider 名称列表
    """
    return list(_PROVIDER_MAP.keys())


def get_default_provider() -> ProviderSpec:
    """获取默认 Provider (最高优先级，即第一个非 Direct Provider).

    Returns:
        默认 Provider 规范
    """
    # 跳过 Direct providers，返回第一个 Gateway 或 Standard provider
    for spec in PROVIDERS:
        if not spec.is_direct:
            return spec
    return PROVIDERS[0]