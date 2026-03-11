"""路径工具测试"""
import tempfile
from pathlib import Path

import pytest

from config.loader import set_config_path
from config.paths import (
    get_data_dir,
    get_runtime_subdir,
    get_logs_dir,
    get_workspace_path,
    get_config_dir,
)


class TestPaths:
    """路径工具测试"""

    def test_get_data_dir(self):
        """测试获取数据目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            set_config_path(config_path)
            data_dir = get_data_dir()
            assert data_dir == config_path.parent

    def test_get_runtime_subdir(self):
        """测试获取运行时子目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.touch()
            set_config_path(config_path)

            subdir = get_runtime_subdir("test")
            assert subdir.exists()
            assert subdir.is_dir()

    def test_get_logs_dir(self):
        """测试获取日志目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.touch()
            set_config_path(config_path)

            logs_dir = get_logs_dir()
            assert logs_dir.exists()
            assert (logs_dir.name) == "logs"

    def test_get_workspace_path_default(self):
        """测试默认工作区路径"""
        workspace = get_workspace_path()
        assert workspace.name == "workspace"
        assert ".lanobot" in str(workspace)

    def test_get_workspace_path_custom(self):
        """测试自定义工作区路径"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = get_workspace_path(tmpdir)
            assert workspace.exists()
            assert workspace == Path(tmpdir)

    def test_get_config_dir(self):
        """测试获取配置目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            set_config_path(config_path)
            config_dir = get_config_dir()
            assert config_dir == config_path.parent