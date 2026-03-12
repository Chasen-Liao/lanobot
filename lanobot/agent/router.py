"""多模型路由中间件 - 根据任务类型选择合适的模型."""

from typing import Callable, Optional
from langchain_core.runnables import Runnable
from langchain_core.language_models import BaseChatModel


class ModelRouter:
    """多模型路由器.

    根据任务特征自动选择合适的模型，提升效率并降低成本。

    路由策略：
    - 简单问题 → 小/快模型（如 Haiku、mini 模型）
    - 复杂问题 → 大/强模型（如 Sonnet、Pro 模型）
    - 代码问题 → 代码专用模型
    - 中文问题 → 中文优化模型
    """

    def __init__(
        self,
        default_model: BaseChatModel,
        fast_model: Optional[BaseChatModel] = None,
        strong_model: Optional[BaseChatModel] = None,
        code_model: Optional[BaseChatModel] = None,
        router_fn: Optional[Callable[[str], str]] = None,
    ):
        """初始化路由器.

        Args:
            default_model: 默认模型
            fast_model: 快速模型（简单任务）
            strong_model: 强力模型（复杂任务）
            code_model: 代码专用模型
            router_fn: 自定义路由函数 (message) -> model_type
                       返回: "default", "fast", "strong", "code"
        """
        self.default_model = default_model
        self.fast_model = fast_model
        self.strong_model = strong_model
        self.code_model = code_model
        self.router_fn = router_fn or self._default_router

        # 模型映射
        self._model_map = {
            "default": default_model,
            "fast": fast_model or default_model,
            "strong": strong_model or default_model,
            "code": code_model or default_model,
        }

    def _default_router(self, message: str) -> str:
        """默认路由策略.

        Args:
            message: 用户消息

        Returns:
            模型类型标识
        """
        msg_lower = message.lower()

        # 代码相关关键词
        code_keywords = [
            "代码", "写代码", "编程", "function", "def ", "class ",
            "algorithm", "debug", "bug", "fix", "error",
            "implement", "refactor", "review code",
        ]
        if any(kw in msg_lower for kw in code_keywords):
            return "code"

        # 复杂任务关键词
        complex_keywords = [
            "分析", "详细", "解释", "比较", "总结", "论文",
            "详细说明", "深入", "全面", "explain", "analyze",
            "compare", "detailed", "comprehensive",
        ]
        if any(kw in msg_lower for kw in complex_keywords):
            return "strong"

        # 简单任务关键词
        simple_keywords = [
            "你好", "hello", "hi", "天气", "时间", "日期",
            "计算", "convert", "什么是", "what is", "翻译",
        ]
        if any(kw in msg_lower for kw in simple_keywords):
            return "fast"

        return "default"

    def select_model(self, message: str) -> BaseChatModel:
        """根据消息选择合适的模型.

        Args:
            message: 用户消息

        Returns:
            选中的模型实例
        """
        model_type = self.router_fn(message)
        return self._model_map.get(model_type, self.default_model)

    def get_model_info(self, message: str) -> dict:
        """获取模型选择信息（用于调试）.

        Args:
            message: 用户消息

        Returns:
            包含选择结果的字典
        """
        model_type = self.router_fn(message)
        model = self._model_map.get(model_type, self.default_model)
        return {
            "message": message[:50] + "...",
            "selected_type": model_type,
            "model_name": getattr(model, "model", "unknown"),
        }


# 便捷函数
def create_router(
    default_model: BaseChatModel,
    **model_overrides
) -> ModelRouter:
    """创建多模型路由器.

    Args:
        default_model: 默认模型
        **model_overrides: 可选参数
            - fast_model: 快速模型
            - strong_model: 强力模型
            - code_model: 代码模型
            - router_fn: 自定义路由函数

    Returns:
        ModelRouter 实例

    Examples:
        >>> router = create_router(
        ...     default_model=gpt4,
        ...     fast_model=gpt4_mini,
        ...     strong_model=gpt4_turbo,
        ... )
        >>> model = router.select_model("你好")
    """
    return ModelRouter(
        default_model=default_model,
        fast_model=model_overrides.get("fast_model"),
        strong_model=model_overrides.get("strong_model"),
        code_model=model_overrides.get("code_model"),
        router_fn=model_overrides.get("router_fn"),
    )