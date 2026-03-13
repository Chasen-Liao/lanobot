"""
折叠状态管理组件
"""
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class FoldableSection(Enum):
    """可折叠的区域类型"""
    THINKING = "thinking"        # 思考过程
    TOOL_CALLS = "tool_calls"    # 工具调用
    FINAL_RESPONSE = "final_response"  # 最终回复


@dataclass
class FoldingState:
    """折叠状态管理"""

    # 各区域展开/折叠状态
    thinking_expanded: bool = True        # 思考过程是否展开
    tool_calls_collapsed: bool = False    # 工具调用是否折叠
    final_response_expanded: bool = True  # 最终回复是否展开

    # 折叠提示
    fold_hint: str = "[按空格键折叠/展开]"
    collapsed_hint: str = "[按空格键展开]"

    def toggle(self, section: FoldableSection) -> bool:
        """切换指定区域的折叠状态

        Args:
            section: 要切换的区域类型

        Returns:
            bool: 切换后的展开状态
        """
        if section == FoldableSection.THINKING:
            self.thinking_expanded = not self.thinking_expanded
            return self.thinking_expanded
        elif section == FoldableSection.TOOL_CALLS:
            self.tool_calls_collapsed = not self.tool_calls_collapsed
            return not self.tool_calls_collapsed
        elif section == FoldableSection.FINAL_RESPONSE:
            self.final_response_expanded = not self.final_response_expanded
            return self.final_response_expanded
        return False

    def is_expanded(self, section: FoldableSection) -> bool:
        """检查指定区域是否展开

        Args:
            section: 区域类型

        Returns:
            bool: 是否展开
        """
        if section == FoldableSection.THINKING:
            return self.thinking_expanded
        elif section == FoldableSection.TOOL_CALLS:
            return not self.tool_calls_collapsed
        elif section == FoldableSection.FINAL_RESPONSE:
            return self.final_response_expanded
        return True

    def expand_all(self):
        """展开所有区域"""
        self.thinking_expanded = True
        self.tool_calls_collapsed = False
        self.final_response_expanded = True

    def collapse_all(self):
        """折叠所有区域"""
        self.thinking_expanded = False
        self.tool_calls_collapsed = True
        self.final_response_expanded = False

    def get_hint(self, section: FoldableSection) -> str:
        """获取折叠提示文本

        Args:
            section: 区域类型

        Returns:
            str: 提示文本
        """
        expanded = self.is_expanded(section)
        return self.collapsed_hint if not expanded else self.fold_hint


@dataclass
class MessageHistory:
    """消息历史记录"""

    messages: List[dict] = field(default_factory=list)
    max_size: int = 100  # 最大保存消息数

    def add_user(self, content: str):
        """添加用户消息"""
        self.messages.append({
            "role": "user",
            "content": content,
        })
        self._trim()

    def add_agent(self, content: str):
        """添加 Agent 消息"""
        self.messages.append({
            "role": "agent",
            "content": content,
        })
        self._trim()

    def _trim(self):
        """修剪消息历史"""
        if len(self.messages) > self.max_size:
            # 保留最新的 max_size 条消息
            self.messages = self.messages[-self.max_size:]

    def get_history(self, limit: int = 10) -> List[dict]:
        """获取最近的对话历史

        Args:
            limit: 返回最近的消息数

        Returns:
            List[dict]: 消息列表
        """
        return self.messages[-limit:] if self.messages else []

    def clear(self):
        """清空历史"""
        self.messages.clear()

    def __len__(self) -> int:
        return len(self.messages)