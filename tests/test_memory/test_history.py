"""History 模块测试."""

import pytest

from lanobot.memory.history import (
    ConversationHistory,
    HistoryManager,
    estimate_message_tokens,
    estimate_messages_tokens,
)


class TestEstimateTokens:
    """Token 估算测试."""

    def test_estimate_empty_message(self):
        """测试空消息."""
        assert estimate_message_tokens({}) >= 1

    def test_estimate_string_content(self):
        """测试字符串内容."""
        tokens = estimate_message_tokens({"content": "Hello, world!"})
        assert tokens > 0

    def test_estimate_list_content(self):
        """测试列表内容."""
        msg = {
            "content": [
                {"type": "text", "text": "Hello"},
                {"type": "image", "data": "..."},
            ]
        }
        tokens = estimate_message_tokens(msg)
        assert tokens > 0

    def test_estimate_with_tool_calls(self):
        """测试带工具调用的消息."""
        msg = {
            "content": "Called tool",
            "tool_calls": [{"name": "test", "arguments": {}}],
        }
        tokens = estimate_message_tokens(msg)
        assert tokens > 0

    def test_estimate_messages_tokens(self):
        """测试多条消息."""
        messages = [
            {"content": "Hello"},
            {"content": "World"},
        ]
        tokens = estimate_messages_tokens(messages)
        assert tokens > 0


class TestConversationHistory:
    """ConversationHistory 类测试."""

    def test_create_empty(self):
        """测试创建空历史."""
        history = ConversationHistory()
        assert len(history.messages) == 0
        assert history.last_consolidated == 0

    def test_add_message(self):
        """测试添加消息."""
        history = ConversationHistory()
        history.add_message({"role": "user", "content": "Hello"})
        assert len(history.messages) == 1
        assert history.messages[0]["content"] == "Hello"

    def test_add_message_adds_timestamp(self):
        """测试添加消息时自动添加时间戳."""
        history = ConversationHistory()
        history.add_message({"role": "user", "content": "Hello"})
        assert "timestamp" in history.messages[0]

    def test_get_messages(self):
        """测试获取消息."""
        history = ConversationHistory()
        history.add_message({"role": "system", "content": "System"})
        history.add_message({"role": "user", "content": "User1"})
        history.add_message({"role": "user", "content": "User2"})

        # 获取所有消息
        all_msgs = history.get_messages()
        assert len(all_msgs) == 3

    def test_get_messages_max(self):
        """测试限制消息数量."""
        history = ConversationHistory()
        for i in range(10):
            history.add_message({"role": "user", "content": f"Message {i}"})

        msgs = history.get_messages(max_messages=3)
        assert len(msgs) == 3

    def test_get_recent(self):
        """测试获取最近消息."""
        history = ConversationHistory()
        for i in range(10):
            history.add_message({"role": "user", "content": f"Message {i}"})

        recent = history.get_recent(3)
        assert len(recent) == 3

    def test_estimate_tokens(self):
        """测试 token 估算."""
        history = ConversationHistory()
        history.add_message({"role": "user", "content": "Hello, world!"})
        tokens = history.estimate_tokens()
        assert tokens > 0

    def test_needs_compression_false(self):
        """测试不需要压缩."""
        history = ConversationHistory(max_tokens=100000)
        history.add_message({"role": "user", "content": "Short"})
        assert not history.needs_compression()

    def test_compress(self):
        """测试压缩."""
        history = ConversationHistory(max_tokens=1000)
        for i in range(30):
            history.add_message({"role": "user", "content": f"Message {i}"})

        compressed = history.compress(keep_recent=10)
        assert len(compressed) > 0
        assert len(history.messages) == 10

    def test_mark_consolidated(self):
        """测试标记已整合."""
        history = ConversationHistory()
        for i in range(5):
            history.add_message({"role": "user", "content": f"Msg {i}"})

        history.mark_consolidated(3)
        assert history.last_consolidated == 3

    def test_clear(self):
        """测试清空历史."""
        history = ConversationHistory()
        history.add_message({"role": "user", "content": "Hello"})
        history.clear()
        assert len(history.messages) == 0
        assert history.last_consolidated == 0


class TestHistoryManager:
    """HistoryManager 类测试."""

    def test_create(self):
        """测试创建管理器."""
        manager = HistoryManager()
        assert len(manager.list_threads()) == 0

    def test_get_or_create(self):
        """测试获取或创建."""
        manager = HistoryManager()
        history1 = manager.get_or_create("thread-1")
        history2 = manager.get_or_create("thread-1")
        assert history1 is history2

    def test_add_message(self):
        """测试添加消息."""
        manager = HistoryManager()
        manager.add_message("thread-1", "Hello", role="user")
        msgs = manager.get_history("thread-1")
        assert len(msgs) == 1

    def test_get_history_not_exists(self):
        """测试获取不存在的历史."""
        manager = HistoryManager()
        msgs = manager.get_history("non-existent")
        assert msgs == []

    def test_estimate_tokens(self):
        """测试估算 token."""
        manager = HistoryManager()
        manager.add_message("thread-1", "Hello, world!")
        tokens = manager.estimate_tokens("thread-1")
        assert tokens > 0

    def test_estimate_tokens_not_exists(self):
        """测试估算不存在会话的 token."""
        manager = HistoryManager()
        assert manager.estimate_tokens("non-existent") == 0

    def test_compress_if_needed(self):
        """测试需要时压缩."""
        manager = HistoryManager(max_tokens=1000)
        # 添加大量消息触发压缩
        for i in range(30):
            manager.add_message("thread-1", f"Message {i}" * 100)

        # token 超过限制，应该压缩
        compressed = manager.compress_if_needed("thread-1")
        assert len(compressed) > 0

    def test_compress_if_needed_not_needed(self):
        """测试不需要压缩."""
        manager = HistoryManager(max_tokens=100000)
        manager.add_message("thread-1", "Short message")
        compressed = manager.compress_if_needed("thread-1")
        assert compressed == []

    def test_delete(self):
        """测试删除会话."""
        manager = HistoryManager()
        manager.add_message("thread-1", "Hello")
        assert manager.delete("thread-1")
        assert manager.get_history("thread-1") == []

    def test_delete_not_exists(self):
        """测试删除不存在的会话."""
        manager = HistoryManager()
        assert not manager.delete("non-existent")

    def test_clear_all(self):
        """测试清空所有."""
        manager = HistoryManager()
        manager.add_message("thread-1", "Hello")
        manager.add_message("thread-2", "World")
        manager.clear_all()
        assert len(manager.list_threads()) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])