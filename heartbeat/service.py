"""Heartbeat service for periodic task checking and execution."""
import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Default heartbeat file path relative to workspace
HEARTBEAT_FILE = "HEARTBEAT.md"


class HeartbeatService:
    """Async heartbeat service that checks for periodic tasks."""

    def __init__(
        self,
        workspace: Path,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        on_execute: Optional[Callable[[dict[str, Any]], Any]] = None,
        interval_s: int = 1800,  # 30 minutes default
    ):
        """
        Initialize HeartbeatService.

        Args:
            workspace: Workspace directory path
            provider: LLM provider name
            model: LLM model name
            api_key: LLM API key (optional, will use env var if not provided)
            base_url: Custom base URL for LLM API (optional)
            on_execute: Callback function when a task should execute
            interval_s: Check interval in seconds
        """
        self._workspace = workspace
        self._provider = provider
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._on_execute = on_execute
        self._interval_s = interval_s
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._llm = None

    async def start(self) -> None:
        """Start the heartbeat service."""
        self._running = True

        # Initialize LLM client
        await self._setup_llm()

        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Heartbeat service started (interval: {self._interval_s}s)")

    async def _setup_llm(self) -> None:
        """Setup LLM client for decision making."""
        try:
            from lanobot.providers import create_llm

            self._llm = create_llm(
                provider=self._provider,
                model=self._model,
                api_key=self._api_key,
                base_url=self._base_url,
            )
            logger.info(f"Heartbeat LLM initialized: {self._provider}/{self._model}")
        except Exception as e:
            logger.warning(f"Failed to setup heartbeat LLM: {e}")
            self._llm = None

    async def stop(self) -> None:
        """Stop the heartbeat service."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Heartbeat service stopped")

    async def _run_loop(self) -> None:
        """Main loop that checks for tasks."""
        while self._running:
            try:
                await self._check_and_execute()
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")

            # Wait for next check
            await asyncio.sleep(self._interval_s)

    async def _check_and_execute(self) -> None:
        """Check HEARTBEAT.md and execute tasks if needed."""
        heartbeat_path = self._workspace / HEARTBEAT_FILE

        if not heartbeat_path.exists():
            # Create default HEARTBEAT.md if it doesn't exist
            await self._create_default_heartbeat(heartbeat_path)
            return

        try:
            # Read heartbeat file
            content = heartbeat_path.read_text(encoding="utf-8")

            # Parse task entries from the file
            tasks = self._parse_heartbeat_file(content)

            if not tasks:
                logger.debug("No tasks found in HEARTBEAT.md")
                return

            # Use LLM to decide which tasks to execute
            tasks_to_run = await self._decide_tasks(tasks)

            for task in tasks_to_run:
                logger.info(f"Executing heartbeat task: {task.get('name', 'unnamed')}")

                if self._on_execute:
                    try:
                        result = self._on_execute(task)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(f"Error executing heartbeat task: {e}")

                # Update last run time in the file
                await self._update_last_run(heartbeat_path, task.get("name", ""))

        except Exception as e:
            logger.error(f"Error processing heartbeat file: {e}")

    def _parse_heartbeat_file(self, content: str) -> list[dict[str, Any]]:
        """Parse HEARTBEAT.md content into task list."""
        tasks = []
        lines = content.split("\n")
        current_task: Optional[dict[str, Any]] = None

        for line in lines:
            line = line.strip()

            # Check for task header (e.g., "- [ ] TaskName or - [x] TaskName)
            if line.startswith("- [") and "]" in line:
                # Save previous task if exists
                if current_task:
                    tasks.append(current_task)

                # Parse new task
                completed = line[2:3] == "x"
                name = line[4:].strip()
                current_task = {
                    "name": name,
                    "completed": completed,
                    "description": "",
                    "last_run": None,
                }
            elif current_task and line:
                # Add to task description
                current_task["description"] += line + "\n"

        # Don't forget the last task
        if current_task:
            tasks.append(current_task)

        return tasks

    async def _decide_tasks(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Use LLM to decide which tasks should run."""
        if not self._llm:
            # No LLM available, run all incomplete tasks
            return [t for t in tasks if not t.get("completed", False)]

        # Build prompt for LLM
        task_list = "\n".join([
            f"- {t['name']} (completed: {t.get('completed', False)})"
            for t in tasks
        ])

        prompt = f"""You are a task scheduler deciding which periodic tasks to execute.

Current tasks in HEARTBEAT.md:
{task_list}

Based on the current time and task descriptions, which tasks should be executed now?
Consider:
1. Tasks that are due for execution based on their schedule
2. Incomplete tasks that need to be worked on
3. Tasks that haven't been run in a while

Respond with a JSON list of task names that should be executed now.
Example: ["TaskName1", "TaskName2"]

Only respond with the JSON list, nothing else."""

        try:
            response = await self._llm.ainvoke(prompt)
            content = str(response.content).strip()

            # Parse JSON response
            import json

            # Try to extract JSON from response (handles markdown code blocks)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            task_names = json.loads(content)

            # Filter tasks that match the names
            return [t for t in tasks if t.get("name") in task_names]

        except Exception as e:
            logger.warning(f"LLM decision failed: {e}, running all incomplete tasks")
            return [t for t in tasks if not t.get("completed", False)]

    async def _create_default_heartbeat(self, path: Path) -> None:
        """Create default HEARTBEAT.md file."""
        default_content = """# Heartbeat Tasks

Periodic tasks to check and execute.

<!--
Tasks format:
- [ ] TaskName: Description of the task

The heartbeat service will check this file periodically and use LLM to decide which tasks to execute.
-->

"""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(default_content, encoding="utf-8")
            logger.info(f"Created default HEARTBEAT.md at {path}")
        except Exception as e:
            logger.error(f"Failed to create HEARTBEAT.md: {e}")

    async def _update_last_run(self, path: Path, task_name: str) -> None:
        """Update last run timestamp for a task (optional feature)."""
        # For now, just mark task as in progress
        # Could extend to track last_run timestamps
        pass