"""Cron tool for scheduling reminders and tasks."""

from contextvars import ContextVar
from typing import Any, Optional

from lanobot.tools.base import Tool


# 简化的 CronService 实现（用于工具层）
class CronJob:
    """Represents a scheduled cron job."""

    def __init__(
        self,
        id: str,
        name: str,
        message: str,
        schedule: dict,
        channel: str = "",
        to: str = "",
    ):
        self.id = id
        self.name = name
        self.message = message
        self.schedule = schedule
        self.channel = channel
        self.to = to


class CronSchedule:
    """Cron schedule definition."""

    def __init__(
        self,
        kind: str,  # "every", "cron", "at"
        every_ms: Optional[int] = None,
        expr: Optional[str] = None,
        tz: Optional[str] = None,
        at_ms: Optional[int] = None,
    ):
        self.kind = kind
        self.every_ms = every_ms
        self.expr = expr
        self.tz = tz
        self.at_ms = at_ms

    def __repr__(self) -> str:
        if self.kind == "every":
            return f"every {self.every_ms}ms"
        elif self.kind == "cron":
            return f"cron {self.expr}"
        elif self.kind == "at":
            return f"at {self.at_ms}ms"
        return "unknown"


class SimpleCronService:
    """Simple in-memory cron service for testing."""

    def __init__(self):
        self._jobs: dict[str, CronJob] = {}
        self._counter = 0

    def add_job(
        self,
        name: str,
        schedule: CronSchedule,
        message: str,
        deliver: bool = False,
        channel: str = "",
        to: str = "",
        delete_after_run: bool = False,
    ) -> CronJob:
        self._counter += 1
        job_id = f"job_{self._counter}"
        job = CronJob(
            id=job_id,
            name=name,
            message=message,
            schedule={
                "kind": schedule.kind,
                "every_ms": schedule.every_ms,
                "expr": schedule.expr,
                "tz": schedule.tz,
                "at_ms": schedule.at_ms,
            },
            channel=channel,
            to=to,
        )
        self._jobs[job_id] = job
        return job

    def list_jobs(self) -> list[CronJob]:
        return list(self._jobs.values())

    def remove_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False

    def get_job(self, job_id: str) -> Optional[CronJob]:
        return self._jobs.get(job_id)


class CronTool(Tool):
    """Tool to schedule reminders and recurring tasks."""

    def __init__(self, cron_service: Optional[SimpleCronService] = None):
        self._cron = cron_service or SimpleCronService()
        self._channel = ""
        self._chat_id = ""
        self._in_cron_context: ContextVar[bool] = ContextVar("cron_in_context", default=False)

    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the current session context for delivery."""
        self._channel = channel
        self._chat_id = chat_id

    def set_cron_context(self, active: bool):
        """Mark whether the tool is executing inside a cron job callback."""
        return self._in_cron_context.set(active)

    def reset_cron_context(self, token) -> None:
        """Restore previous cron context."""
        self._in_cron_context.reset(token)

    def get_service(self) -> SimpleCronService:
        """Get the cron service instance."""
        return self._cron

    @property
    def name(self) -> str:
        return "cron"

    @property
    def description(self) -> str:
        return "Schedule reminders and recurring tasks. Actions: add, list, remove."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "remove"],
                    "description": "Action to perform",
                },
                "message": {"type": "string", "description": "Reminder message (for add)"},
                "every_seconds": {
                    "type": "integer",
                    "description": "Interval in seconds (for recurring tasks)",
                },
                "cron_expr": {
                    "type": "string",
                    "description": "Cron expression like '0 9 * * *' (for scheduled tasks)",
                },
                "tz": {
                    "type": "string",
                    "description": "IANA timezone for cron expressions (e.g. 'Asia/Shanghai')",
                },
                "at": {
                    "type": "string",
                    "description": "ISO datetime for one-time execution (e.g. '2026-02-12T10:30:00')",
                },
                "job_id": {"type": "string", "description": "Job ID (for remove)"},
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        message: str = "",
        every_seconds: Optional[int] = None,
        cron_expr: Optional[str] = None,
        tz: Optional[str] = None,
        at: Optional[str] = None,
        job_id: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        if action == "add":
            if self._in_cron_context.get():
                return "Error: cannot schedule new jobs from within a cron job execution"
            return self._add_job(message, every_seconds, cron_expr, tz, at)
        elif action == "list":
            return self._list_jobs()
        elif action == "remove":
            return self._remove_job(job_id)
        return f"Unknown action: {action}"

    def _add_job(
        self,
        message: str,
        every_seconds: Optional[int],
        cron_expr: Optional[str],
        tz: Optional[str],
        at: Optional[str],
    ) -> str:
        if not message:
            return "Error: message is required for add"
        if not self._channel or not self._chat_id:
            return "Error: no session context (channel/chat_id)"
        if tz and not cron_expr:
            return "Error: tz can only be used with cron_expr"
        if tz:
            try:
                from zoneinfo import ZoneInfo
                ZoneInfo(tz)
            except (KeyError, Exception):
                return f"Error: unknown timezone '{tz}'"

        # Build schedule
        delete_after = False
        if every_seconds:
            schedule = CronSchedule(kind="every", every_ms=every_seconds * 1000)
        elif cron_expr:
            schedule = CronSchedule(kind="cron", expr=cron_expr, tz=tz)
        elif at:
            from datetime import datetime

            try:
                dt = datetime.fromisoformat(at)
            except ValueError:
                return f"Error: invalid ISO datetime format '{at}'. Expected format: YYYY-MM-DDTHH:MM:SS"
            at_ms = int(dt.timestamp() * 1000)
            schedule = CronSchedule(kind="at", at_ms=at_ms)
            delete_after = True
        else:
            return "Error: either every_seconds, cron_expr, or at is required"

        job = self._cron.add_job(
            name=message[:30],
            schedule=schedule,
            message=message,
            deliver=True,
            channel=self._channel,
            to=self._chat_id,
            delete_after_run=delete_after,
        )
        return f"Created job '{job.name}' (id: {job.id})"

    def _list_jobs(self) -> str:
        jobs = self._cron.list_jobs()
        if not jobs:
            return "No scheduled jobs."
        lines = [f"- {j.name} (id: {j.id}, {j.schedule['kind']})" for j in jobs]
        return "Scheduled jobs:\n" + "\n".join(lines)

    def _remove_job(self, job_id: Optional[str]) -> str:
        if not job_id:
            return "Error: job_id is required for remove"
        if self._cron.remove_job(job_id):
            return f"Removed job {job_id}"
        return f"Job {job_id} not found"