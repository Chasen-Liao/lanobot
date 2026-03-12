"""Session 模块测试."""

import json
import pytest
import asyncio
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from session import (
    Session,
    SessionMetadata,
    SessionManager,
    create_session_manager,
    DEFAULT_COMPRESSION_THRESHOLD,
    DEFAULT_EXPIRE_DAYS,
)


class TestSessionMetadata:
    """SessionMetadata 测试."""

    def test_default_values(self):
        """测试默认值."""
        metadata = SessionMetadata()
        assert metadata.key == ""
        assert metadata.title == ""
        assert metadata.title_source == "auto"
        assert metadata.is_pinned is False
        assert metadata.expires_at is None
        assert metadata.message_count == 0
        assert metadata.estimated_tokens == 0

    def test_pin_unpin(self):
        """测试固定/取消固定."""
        metadata = SessionMetadata()
        metadata.pin()
        assert metadata.is_pinned is True
        assert metadata.expires_at is None
        assert metadata.should_expire() is False

        metadata.unpin()
        assert metadata.is_pinned is False
        assert metadata.expires_at is not None
        assert metadata.should_expire() is False

    def test_should_expire(self):
        """测试过期检查."""
        metadata = SessionMetadata(is_pinned=True)
        assert metadata.should_expire() is False

        # 未过期
        metadata = SessionMetadata()
        metadata.expires_at = datetime.now() + timedelta(days=1)
        assert metadata.should_expire() is False

        # 已过期
        metadata = SessionMetadata()
        metadata.expires_at = datetime.now() - timedelta(days=1)
        assert metadata.should_expire() is True

    def test_touch(self):
        """测试 touch."""
        metadata = SessionMetadata()
        initial_count = metadata.message_count
        before = metadata.updated_at
        metadata.touch()
        assert metadata.message_count == initial_count + 1
        assert metadata.updated_at >= before

    def test_serialization(self):
        """测试序列化/反序列化."""
        metadata = SessionMetadata(
            key="telegram:123456",
            title="Test Session",
            title_source="user",
            is_pinned=True,
        )
        data = metadata.to_dict()
        restored = SessionMetadata.from_dict(data)

        assert restored.key == metadata.key
        assert restored.title == metadata.title
        assert restored.title_source == metadata.title_source
        assert restored.is_pinned == metadata.is_pinned


class TestSession:
    """Session 测试."""

    def test_create_session(self):
        """测试创建会话."""
        session = Session(key="telegram:123456")
        assert session.key == "telegram:123456"
        assert len(session.messages) == 0
        assert session.last_consolidated == 0

    def test_add_message(self):
        """测试添加消息."""
        session = Session(key="telegram:123456")
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there!")

        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "user"
        assert session.messages[0]["content"] == "Hello"
        assert session.metadata.message_count == 2
        assert session.metadata.key == "telegram:123456"

    def test_get_history(self):
        """测试获取历史."""
        session = Session(key="telegram:123456")
        for i in range(30):
            session.add_message("user", f"Message {i}")

        # 获取全部
        history = session.get_history()
        assert len(history) == 30

        # 限制数量
        history = session.get_history(max_messages=10)
        assert len(history) == 10

    def test_needs_compression(self):
        """测试压缩检查."""
        session = Session(key="test-123")
        # 添加足够多的消息来触发压缩（使用阈值参数）
        for _ in range(100):
            session.add_message("user", "x" * 500)  # 约 125 tokens 每条

        # 使用较低的阈值测试
        assert session.needs_compression(threshold=5000) is True

    def test_compress(self):
        """测试压缩."""
        session = Session(key="test-123")
        # 先添加一条 system 消息
        session.add_message("system", "You are a helpful assistant")
        for i in range(50):
            session.add_message("user", f"Message {i}")

        initial_tokens = session.metadata.estimated_tokens
        compressed = session.compress(keep_recent=10)

        # 应该保留系统消息 + 最近消息
        assert len(session.messages) >= 10  # system + 10 recent
        assert len(compressed) > 0

    def test_serialization(self):
        """测试序列化/反序列化."""
        session = Session(key="telegram:123456")
        session.add_message("user", "Hello")
        session.metadata.title = "Test Title"

        data = session.to_dict()
        restored = Session.from_dict(data)

        assert restored.key == session.key
        assert restored.metadata.title == "Test Title"
        assert len(restored.messages) == 1


class TestSessionManager:
    """SessionManager 测试."""

    @pytest.fixture
    def temp_dir(self):
        """临时目录."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_dir):
        """会话管理器."""
        return SessionManager(
            sessions_dir=temp_dir,
            auto_save=False,
        )

    def test_get_or_create(self, manager):
        """测试获取/创建会话."""
        session = manager.get_or_create("telegram:123456")
        assert session.key == "telegram:123456"

    def test_get_existing(self, manager):
        """测试获取已存在的会话."""
        # 创建
        session1 = manager.get_or_create("telegram:123456")
        session1.add_message("user", "Hello")

        # 再次获取（应该返回同一个会话）
        session2 = manager.get_or_create("telegram:123456")
        assert session2.key == session1.key

    def test_save_and_load(self, manager):
        """测试保存和加载（JSONL 格式）."""
        session = manager.get_or_create("telegram:123456")
        session.add_message("user", "Test message")
        session.metadata.title = "Test Title"

        # 使用 save_full 完整保存
        manager.save_full(session)

        # 加载
        loaded = manager.get("telegram:123456")
        assert loaded is not None
        assert loaded.metadata.title == "Test Title"
        assert len(loaded.messages) == 1

    def test_delete(self, manager):
        """测试删除会话."""
        session = manager.get_or_create("telegram:123456")
        key = session.key
        manager.save_full(session)

        # 删除
        assert manager.delete(key) is True

        # 验证已删除
        assert manager.get(key) is None

    def test_list_sessions(self, manager):
        """测试列出会话."""
        # 创建多个会话并保存
        s1 = manager.get_or_create("telegram:user1")
        manager.save_full(s1)
        s2 = manager.get_or_create("telegram:user2")
        manager.save_full(s2)
        s3 = manager.get_or_create("discord:user3")
        manager.save_full(s3)

        # 列出全部
        sessions = manager.list_sessions()
        assert len(sessions) == 3

        # 按渠道过滤
        sessions = manager.list_sessions(channel="telegram")
        assert len(sessions) == 2

    def test_cleanup_expired(self, manager):
        """测试过期清理."""
        # 创建一个会话并设为已过期
        session = manager.get_or_create("telegram:user1")
        session.metadata.expires_at = datetime.now() - timedelta(days=1)
        session.metadata.is_pinned = False
        manager.save_full(session)

        # 创建一个未过期的会话
        session2 = manager.get_or_create("telegram:user2")
        manager.save_full(session2)

        # 清理
        count = manager.cleanup_expired()
        assert count == 1

        # 验证
        sessions = manager.list_sessions()
        assert len(sessions) == 1

    def test_pin_unpin_session(self, manager):
        """测试固定/取消固定会话."""
        session = manager.get_or_create("telegram:user1")
        key = session.key

        # 固定
        assert manager.pin_session(key, pinned=True) is True
        session = manager.get(key)
        assert session.metadata.is_pinned is True

        # 取消固定
        assert manager.pin_session(key, pinned=False) is True
        session = manager.get(key)
        assert session.metadata.is_pinned is False

    def test_set_title(self, manager):
        """测试设置标题."""
        session = manager.get_or_create("telegram:user1")
        key = session.key

        assert manager.set_title(key, "My Custom Title") is True
        session = manager.get(key)
        assert session.metadata.title == "My Custom Title"
        assert session.metadata.title_source == "user"

    def test_compression(self, manager):
        """测试自动压缩（同步版本）."""
        # 使用低阈值
        manager._compression_threshold = 100

        session = manager.get_or_create("telegram:user1")
        # 添加足以触发压缩的消息
        for _ in range(50):
            session.add_message("user", "x" * 50)

        # 压缩（同步版本，无 LLM）
        was_compressed = session.needs_compression(manager._compression_threshold)
        assert was_compressed is True

    @pytest.mark.asyncio
    async def test_compress_if_needed_async(self, manager):
        """测试异步压缩（带 mock LLM）."""
        # 使用低阈值
        manager._compression_threshold = 100

        session = manager.get_or_create("telegram:user1")
        # 添加足以触发压缩的消息
        for _ in range(50):
            session.add_message("user", "x" * 50)

        # 创建 async mock LLM
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "这是对话摘要"
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        # 执行异步压缩
        was_compressed = await manager.compress_if_needed(session, mock_llm)

        # 验证
        assert was_compressed is True

    def test_summaries_dir_created(self, temp_dir):
        """测试 summaries 目录自动创建."""
        manager = SessionManager(sessions_dir=temp_dir, auto_save=False)
        assert manager.summaries_dir.exists()
        assert manager.summaries_dir.name == "summaries"

    def test_create_session_manager(self, temp_dir):
        """测试便捷函数."""
        manager = create_session_manager(
            sessions_dir=temp_dir,
            compression_threshold=50000,
            expire_days=7,
        )
        assert manager._compression_threshold == 50000
        assert manager._default_ttl_days == 7

    def test_jsonl_format(self, manager):
        """测试 JSONL 格式保存."""
        session = manager.get_or_create("telegram:test")
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there!")

        manager.save_full(session)

        # 验证文件是 JSONL 格式
        file_path = manager._get_session_path("telegram:test")
        content = file_path.read_text(encoding="utf-8")
        lines = content.strip().split("\n")

        # 应该有多行 JSON
        assert len(lines) >= 2

        # 每行应该是有效的 JSON
        for line in lines:
            parsed = json.loads(line)
            assert "type" in parsed
            assert "data" in parsed