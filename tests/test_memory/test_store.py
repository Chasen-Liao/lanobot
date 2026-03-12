"""Store 模块测试."""

import pytest
from pathlib import Path

from lanobot.memory.store import (
    MemoryStore,
    FileMemoryStore,
    MemoryFile,
    get_store,
    DEFAULT_MEMORY_PATH,
)


class TestMemoryFile:
    """MemoryFile 类测试."""

    def test_create_memory_file(self, tmp_path):
        """测试创建记忆文件对象."""
        memory_file = MemoryFile(path=tmp_path / "test.md")
        assert memory_file.path == tmp_path / "test.md"
        assert memory_file.content == ""
        assert memory_file.exists() is False

    def test_save_and_load(self, tmp_path):
        """测试保存和加载内容."""
        memory_file = MemoryFile(path=tmp_path / "test.md")
        memory_file.save("Hello World")
        assert memory_file.exists() is True
        assert memory_file.content == "Hello World"

    def test_load_existing(self, tmp_path):
        """测试加载已存在的文件."""
        test_file = tmp_path / "test.md"
        test_file.write_text("Existing content", encoding="utf-8")

        memory_file = MemoryFile(path=test_file)
        memory_file.load()
        assert memory_file.content == "Existing content"
        assert memory_file.last_updated is not None


class TestFileMemoryStore:
    """FileMemoryStore 类测试."""

    def test_create_file_store(self, tmp_path):
        """测试创建文件系统记忆存储."""
        store = FileMemoryStore(memory_path=tmp_path)
        assert store.memory_path == tmp_path
        assert tmp_path.exists()

    def test_get_nonexistent(self, tmp_path):
        """测试获取不存在的记忆."""
        store = FileMemoryStore(memory_path=tmp_path)
        assert store.get("nonexistent") is None

    def test_write_and_read(self, tmp_path):
        """测试写入和读取记忆."""
        store = FileMemoryStore(memory_path=tmp_path)
        store.write("test", "Test content")
        assert store.read("test") == "Test content"

    def test_get_or_create(self, tmp_path):
        """测试获取或创建记忆."""
        store = FileMemoryStore(memory_path=tmp_path)
        memory_file = store.get_or_create("test")
        assert memory_file is not None
        assert memory_file.path == tmp_path / "test.md"

    def test_list_all(self, tmp_path):
        """测试列出所有记忆."""
        store = FileMemoryStore(memory_path=tmp_path)
        store.write("file1", "Content 1")
        store.write("file2", "Content 2")

        files = store.list_all()
        # 包含 README.md 和新创建的文件
        assert len(files) >= 2

    def test_delete(self, tmp_path):
        """测试删除记忆."""
        store = FileMemoryStore(memory_path=tmp_path)
        store.write("test", "Test content")
        assert store.read("test") == "Test content"

        store.delete("test")
        assert store.read("test") == ""

    def test_search(self, tmp_path):
        """测试搜索记忆."""
        store = FileMemoryStore(memory_path=tmp_path)
        store.write("test", "This is a Python programming test")
        store.write("other", "Some other content")

        results = store.search("Python")
        assert len(results) == 1
        assert results[0]["name"] == "test"

    def test_readme_index(self, tmp_path):
        """测试 README 索引更新."""
        store = FileMemoryStore(memory_path=tmp_path)
        store.write("user_profile", "User profile content")

        readme = store.get_readme_content()
        assert "Memory Index" in readme
        assert "user_profile" in readme


class TestMemoryStore:
    """MemoryStore 类测试."""

    def test_create_memory_store(self, tmp_path):
        """测试创建内存存储."""
        store = MemoryStore(memory_path=tmp_path)
        assert store.store is None  # 懒加载
        assert store.file_store is not None

    def test_get_store_creates_instance(self, tmp_path):
        """测试懒加载创建 store."""
        store = MemoryStore(memory_path=tmp_path)
        s = store._get_store()
        assert s is not None
        assert store.store is s

    def test_read_long_term(self, tmp_path):
        """测试读取长期记忆."""
        store = MemoryStore(memory_path=tmp_path)
        store.write_long_term("user_profile", "Test profile")

        content = store.read_long_term("user_profile")
        assert content == "Test profile"

    def test_write_long_term(self, tmp_path):
        """测试写入长期记忆."""
        store = MemoryStore(memory_path=tmp_path)
        store.write_long_term("preferences", "Dark mode")

        content = store.read_long_term("preferences")
        assert content == "Dark mode"

    def test_list_long_term_memories(self, tmp_path):
        """测试列出长期记忆."""
        store = MemoryStore(memory_path=tmp_path)
        store.write_long_term("user_profile", "Profile")
        store.write_long_term("preferences", "Prefs")

        memories = store.list_long_term_memories()
        names = [m["name"] for m in memories]
        assert "user_profile" in names
        assert "preferences" in names

    def test_get_memory_context(self, tmp_path):
        """测试获取记忆上下文."""
        store = MemoryStore(memory_path=tmp_path)
        store.write_long_term("user_profile", "Test profile")

        context = store.get_memory_context()
        assert "Memory Index" in context
        assert "user_profile" in context


class TestGetStore:
    """get_store 工厂函数测试."""

    def test_get_store_with_custom_path(self, tmp_path):
        """测试使用自定义路径获取存储."""
        store = get_store(memory_path=tmp_path)
        assert isinstance(store, MemoryStore)
        assert store.file_store.memory_path == tmp_path

    def test_get_store_defaults(self):
        """测试默认参数."""
        store = get_store()
        assert isinstance(store, MemoryStore)
        # 默认路径应该是 ~/.lanobot/memory/
        assert store.file_store.memory_path == DEFAULT_MEMORY_PATH


if __name__ == "__main__":
    pytest.main([__file__, "-v"])