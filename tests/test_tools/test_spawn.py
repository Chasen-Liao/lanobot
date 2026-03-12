"""Tests for SpawnTool and SubagentManager."""

import pytest
from lanobot.tools.spawn import SpawnTool, SubagentManager


class TestSubagentManager:
    """Test cases for SubagentManager."""

    def test_manager_without_factory(self):
        """Test manager without agent factory."""
        manager = SubagentManager()

        # Creating a spawn tool should work
        tool = SpawnTool(manager=manager)
        assert tool._manager is manager

    def test_manager_with_factory(self):
        """Test manager with agent factory."""
        def dummy_factory():
            return "mock_agent"

        manager = SubagentManager(agent_factory=dummy_factory)
        assert manager._agent_factory is dummy_factory

    def test_list_subagents_empty(self):
        """Test listing subagents when none exist."""
        manager = SubagentManager()
        assert manager.list_subagents() == []

    def test_get_subagent_not_found(self):
        """Test getting non-existent subagent."""
        manager = SubagentManager()
        assert manager.get_subagent("nonexistent") is None


class TestSpawnTool:
    """Test cases for SpawnTool."""

    @pytest.mark.asyncio
    async def test_spawn_without_factory(self):
        """Test spawning without factory returns error."""
        tool = SpawnTool()

        result = await tool.execute(task="Do something")

        assert "Error" in result
        assert "not configured" in result

    @pytest.mark.asyncio
    async def test_set_context(self):
        """Test setting spawn context."""
        tool = SpawnTool()
        tool.set_context("telegram", "chat123")

        assert tool._origin_channel == "telegram"
        assert tool._origin_chat_id == "chat123"
        assert tool._session_key == "telegram:chat123"

    @pytest.mark.asyncio
    async def test_spawn_labels(self):
        """Test spawn with custom label."""
        def factory():
            return None

        manager = SubagentManager(agent_factory=factory)
        tool = SpawnTool(manager=manager)

        # This will try to spawn but fail due to agent being None
        result = await tool.execute(task="Test task", label="my-label")

        # Should create a subagent record
        subagents = manager.list_subagents()
        assert len(subagents) >= 1