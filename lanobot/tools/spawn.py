"""Spawn tool for creating background subagents."""

from typing import Any, Optional

from lanobot.tools.base import Tool


class SubagentManager:
    """Manager for spawning and tracking subagents."""

    def __init__(self, agent_factory: Optional[callable] = None):
        self._agent_factory = agent_factory
        self._subagents: dict[str, Any] = {}

    async def spawn(
        self,
        task: str,
        label: Optional[str] = None,
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
        session_key: str = "cli:direct",
    ) -> str:
        """Spawn a subagent to execute the given task."""
        if not self._agent_factory:
            return "Error: Subagent manager not configured. Provide an agent_factory."

        import uuid
        agent_id = str(uuid.uuid4())[:8]
        agent_label = label or f"task-{agent_id}"

        try:
            # Create a new agent instance for the subagent
            agent = self._agent_factory()

            # Store the subagent for tracking
            self._subagents[agent_id] = {
                "label": agent_label,
                "task": task,
                "agent": agent,
                "status": "running",
            }

            # Start the subagent task in background
            asyncio.create_task(self._run_subagent(agent_id, task, origin_channel, origin_chat_id))

            return f"Subagent '{agent_label}' (id: {agent_id}) spawned to handle task"
        except Exception as e:
            return f"Error spawning subagent: {str(e)}"

    async def _run_subagent(
        self,
        agent_id: str,
        task: str,
        origin_channel: str,
        origin_chat_id: str,
    ) -> None:
        """Run the subagent task."""
        if agent_id not in self._subagents:
            return

        subagent = self._subagents[agent_id]
        try:
            agent = subagent["agent"]
            # Execute the task
            result = await agent.ainvoke(task)

            subagent["status"] = "completed"
            subagent["result"] = result
        except Exception as e:
            subagent["status"] = "failed"
            subagent["error"] = str(e)

    def list_subagents(self) -> list[dict[str, Any]]:
        """List all active subagents."""
        return [
            {
                "id": aid,
                "label": info["label"],
                "status": info["status"],
                "task": info["task"],
            }
            for aid, info in self._subagents.items()
        ]

    def get_subagent(self, agent_id: str) -> Optional[dict[str, Any]]:
        """Get subagent by ID."""
        return self._subagents.get(agent_id)


class SpawnTool(Tool):
    """Tool to spawn a subagent for background task execution."""

    def __init__(self, manager: Optional[SubagentManager] = None):
        self._manager = manager or SubagentManager()
        self._origin_channel = "cli"
        self._origin_chat_id = "direct"
        self._session_key = "cli:direct"

    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the origin context for subagent announcements."""
        self._origin_channel = channel
        self._origin_chat_id = chat_id
        self._session_key = f"{channel}:{chat_id}"

    @property
    def name(self) -> str:
        return "spawn"

    @property
    def description(self) -> str:
        return (
            "Spawn a subagent to handle a task in the background. "
            "Use this for complex or time-consuming tasks that can run independently. "
            "The subagent will complete the task and report back when done."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task for the subagent to complete",
                },
                "label": {
                    "type": "string",
                    "description": "Optional short label for the task (for display)",
                },
            },
            "required": ["task"],
        }

    async def execute(self, task: str, label: Optional[str] = None, **kwargs: Any) -> str:
        """Spawn a subagent to execute the given task."""
        return await self._manager.spawn(
            task=task,
            label=label,
            origin_channel=self._origin_channel,
            origin_chat_id=self._origin_chat_id,
            session_key=self._session_key,
        )


# Backward compat - need to import asyncio for SubagentManager
import asyncio