"""Checkpointer 模块测试."""

import pytest

from lanobot.memory.checkpointer import (
    get_checkpointer,
    create_checkpointer,
)


class TestGetCheckpointer:
    """get_checkpointer 工厂函数测试."""

    def test_get_memory_checkpointer(self):
        """测试获取内存 checkpointer."""
        checkpointer = get_checkpointer()
        assert checkpointer is not None

    def test_get_memory_checkpointer_explicit(self):
        """测试显式指定内存后端."""
        checkpointer = get_checkpointer("memory")
        assert checkpointer is not None

    def test_invalid_backend(self):
        """测试无效后端."""
        with pytest.raises(ValueError, match="Unknown backend"):
            get_checkpointer("postgres")


class TestCreateCheckpointer:
    """create_checkpointer 兼容函数测试."""

    def test_create_with_defaults(self):
        """测试默认参数."""
        checkpointer = create_checkpointer()
        assert checkpointer is not None

    def test_create_with_config(self):
        """测试从配置创建."""
        config = {"backend": "memory"}
        checkpointer = create_checkpointer(config)
        assert checkpointer is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])