"""LLM Provider 抽象基类.

参考 nanobot 的 base.py 实现，提供统一的 Provider 接口。
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolCallRequest:
    """LLM 产生的工具调用请求."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """LLM Provider 的响应."""

    content: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    reasoning_content: str | None = None  # Kimi, DeepSeek-R1 等推理模型
    thinking_blocks: list[dict] | None = None  # Anthropic 扩展思考

    @property
    def has_tool_calls(self) -> bool:
        """检查响应是否包含工具调用."""
        return len(self.tool_calls) > 0


class LLMProvider(ABC):
    """LLM Provider 抽象基类.

    各提供商的实现应处理其特定 API，同时保持一致的接口。
    """

    _CHAT_RETRY_DELAYS = (1, 2, 4)
    _TRANSIENT_ERROR_MARKERS = (
        "429",
        "rate limit",
        "500",
        "502",
        "503",
        "504",
        "overloaded",
        "timeout",
        "timed out",
        "connection",
        "server error",
        "temporarily unavailable",
    )

    def __init__(self, api_key: str | None = None, api_base: str | None = None):
        """初始化 Provider.

        Args:
            api_key: API Key
            api_base: API 基础 URL
        """
        self.api_key = api_key
        self.api_base = api_base

    @staticmethod
    def _sanitize_empty_content(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """替换导致 Provider 400 错误的空内容.

        当 MCP 工具返回空内容时会出现此问题。大多数提供商
        会拒绝空字符串内容或列表内容中的空文本块。
        """
        result: list[dict[str, Any]] = []
        for msg in messages:
            content = msg.get("content")

            if isinstance(content, str) and not content:
                clean = dict(msg)
                # 如果是 assistant 且有 tool_calls，内容设为 None
                clean["content"] = None if (msg.get("role") == "assistant" and msg.get("tool_calls")) else "(empty)"
                result.append(clean)
                continue

            if isinstance(content, list):
                filtered = [
                    item for item in content
                    if not (
                        isinstance(item, dict)
                        and item.get("type") in ("text", "input_text", "output_text")
                        and not item.get("text")
                    )
                ]
                if len(filtered) != len(content):
                    clean = dict(msg)
                    if filtered:
                        clean["content"] = filtered
                    elif msg.get("role") == "assistant" and msg.get("tool_calls"):
                        clean["content"] = None
                    else:
                        clean["content"] = "(empty)"
                    result.append(clean)
                    continue

            if isinstance(content, dict):
                clean = dict(msg)
                clean["content"] = [content]
                result.append(clean)
                continue

            result.append(msg)
        return result

    @staticmethod
    def _sanitize_request_messages(
        messages: list[dict[str, Any]],
        allowed_keys: frozenset[str],
    ) -> list[dict[str, Any]]:
        """仅保留 Provider 安全的消息键，并规范化 assistant 内容."""
        sanitized = []
        for msg in messages:
            clean = {k: v for k, v in msg.items() if k in allowed_keys}
            if clean.get("role") == "assistant" and "content" not in clean:
                clean["content"] = None
            sanitized.append(clean)
        return sanitized

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
    ) -> LLMResponse:
        """发送聊天完成请求.

        Args:
            messages: 消息字典列表，包含 'role' 和 'content'
            tools: 可选的工具定义列表
            model: 模型标识符 (提供商特定)
            max_tokens: 响应最大 token 数
            temperature: 采样温度

        Returns:
            包含内容和/或工具调用的 LLMResponse
        """
        pass

    @classmethod
    def _is_transient_error(cls, content: str | None) -> bool:
        """判断是否为临时错误."""
        err = (content or "").lower()
        return any(marker in err for marker in cls._TRANSIENT_ERROR_MARKERS)

    async def chat_with_retry(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
    ) -> LLMResponse:
        """带重试的 chat 调用."""
        for attempt, delay in enumerate(self._CHAT_RETRY_DELAYS, start=1):
            try:
                response = await self.chat(
                    messages=messages,
                    tools=tools,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    reasoning_effort=reasoning_effort,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                response = LLMResponse(
                    content=f"Error calling LLM: {exc}",
                    finish_reason="error",
                )

            if response.finish_reason != "error":
                return response
            if not self._is_transient_error(response.content):
                return response

            err = (response.content or "").lower()
            logger.warning(
                "LLM transient error (attempt {}/{}), retrying in {}s: {}",
                attempt,
                len(self._CHAT_RETRY_DELAYS),
                delay,
                err[:120],
            )
            await asyncio.sleep(delay)

        try:
            return await self.chat(
                messages=messages,
                tools=tools,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                reasoning_effort=reasoning_effort,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return LLMResponse(
                content=f"Error calling LLM: {exc}",
                finish_reason="error",
            )

    @abstractmethod
    def get_default_model(self) -> str:
        """获取此 Provider 的默认模型."""
        pass