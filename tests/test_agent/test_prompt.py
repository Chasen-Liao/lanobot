"""系统提示词加载测试."""

import pytest
from pathlib import Path

from lanobot.agent.prompt import load_system_prompt


class TestLoadSystemPrompt:
    """测试 load_system_prompt 函数."""

    def test_load_default_templates(self):
        """测试加载默认模板目录."""
        prompt = load_system_prompt()
        assert prompt is not None
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_load_custom_templates(self, tmp_path):
        """测试加载自定义模板目录."""
        # 创建测试模板文件
        (tmp_path / "SOUL.md").write_text("Test Soul", encoding="utf-8")
        (tmp_path / "AGENTS.md").write_text("Test Agents", encoding="utf-8")
        (tmp_path / "TOOLS.md").write_text("Test Tools", encoding="utf-8")
        (tmp_path / "USER.md").write_text("User: Test", encoding="utf-8")

        prompt = load_system_prompt(tmp_path)
        assert "Test Soul" in prompt
        assert "Test Agents" in prompt
        assert "Test Tools" in prompt
        assert "User: Test" in prompt

    def test_load_partial_templates(self, tmp_path):
        """测试加载部分模板文件（缺少某些文件）."""
        (tmp_path / "SOUL.md").write_text("Soul content", encoding="utf-8")
        # 不创建其他文件

        prompt = load_system_prompt(tmp_path)
        assert "Soul content" in prompt
        # 注释仍应存在（因为 USER.md 不存在）
        assert "<!-- SOUL.md -->" in prompt

    def test_empty_directory(self, tmp_path):
        """测试空目录（无模板文件）."""
        # 创建空目录，不放入任何模板文件
        prompt = load_system_prompt(tmp_path)
        assert prompt == ""

    def test_template_order(self, tmp_path):
        """测试模板文件按正确顺序加载."""
        (tmp_path / "SOUL.md").write_text("1. SOUL", encoding="utf-8")
        (tmp_path / "AGENTS.md").write_text("2. AGENTS", encoding="utf-8")
        (tmp_path / "TOOLS.md").write_text("3. TOOLS", encoding="utf-8")
        (tmp_path / "USER.md").write_text("4. USER", encoding="utf-8")

        prompt = load_system_prompt(tmp_path)
        # 检查顺序
        soul_pos = prompt.find("1. SOUL")
        agents_pos = prompt.find("2. AGENTS")
        tools_pos = prompt.find("3. TOOLS")
        user_pos = prompt.find("4. USER")
        assert soul_pos < agents_pos < tools_pos < user_pos