"""Cron types and data structures."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional


@dataclass
class CronSchedule:
    """Cron schedule definition."""

    kind: str  # "every", "cron", "at"
    every_ms: Optional[int] = None
    expr: Optional[str] = None
    tz: Optional[str] = None
    at_ms: Optional[int] = None

    def next_run(self) -> Optional[datetime]:
        """Calculate next run time based on schedule kind."""
        now = datetime.now()
        if self.kind == "every" and self.every_ms:
            from datetime import timedelta
            return now + timedelta(milliseconds=self.every_ms)
        elif self.kind == "cron" and self.expr:
            try:
                from croniter import croniter

                tz = self.tz if self.tz else "local"
                cron = croniter(self.expr, now, tzinfo=tz)
                return cron.get_next(datetime)
            except Exception:
                return None
        elif self.kind == "at" and self.at_ms:
            dt = datetime.fromtimestamp(self.at_ms / 1000)
            return dt if dt > now else None
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "kind": self.kind,
            "every_ms": self.every_ms,
            "expr": self.expr,
            "tz": self.tz,
            "at_ms": self.at_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CronSchedule":
        """Create from dictionary."""
        return cls(
            kind=data["kind"],
            every_ms=data.get("every_ms"),
            expr=data.get("expr"),
            tz=data.get("tz"),
            at_ms=data.get("at_ms"),
        )

    def __repr__(self) -> str:
        if self.kind == "every":
            return f"every {self.every_ms}ms"
        elif self.kind == "cron":
            return f"cron {self.expr}"
        elif self.kind == "at":
            return f"at {self.at_ms}ms"
        return "unknown"


@dataclass
class CronJob:
    """Represents a scheduled cron job."""

    id: str
    name: str
    message: str
    schedule: CronSchedule
    channel: str = ""
    to: str = ""
    delete_after_run: bool = False
    enabled: bool = True
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

        # Support schedule as dict (for deserialization)
        if isinstance(self.schedule, dict):
            self.schedule = CronSchedule.from_dict(self.schedule)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "message": self.message,
            "schedule": self.schedule.to_dict() if isinstance(self.schedule, CronSchedule) else self.schedule,
            "channel": self.channel,
            "to": self.to,
            "delete_after_run": self.delete_after_run,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CronJob":
        """Create from dictionary."""
        schedule_data = data.get("schedule", {})
        return cls(
            id=data["id"],
            name=data["name"],
            message=data["message"],
            schedule=CronSchedule.from_dict(schedule_data) if isinstance(schedule_data, dict) else schedule_data,
            channel=data.get("channel", ""),
            to=data.get("to", ""),
            delete_after_run=data.get("delete_after_run", False),
            enabled=data.get("enabled", True),
            created_at=data.get("created_at", ""),
        )


@dataclass
class CronStore:
    """Store for cron jobs with persistence."""

    jobs: dict[str, CronJob] = field(default_factory=dict)

    def add(self, job: CronJob) -> None:
        """Add a job to the store."""
        self.jobs[job.id] = job

    def remove(self, job_id: str) -> bool:
        """Remove a job from the store."""
        if job_id in self.jobs:
            del self.jobs[job_id]
            return True
        return False

    def get(self, job_id: str) -> Optional[CronJob]:
        """Get a job by ID."""
        return self.jobs.get(job_id)

    def list_all(self) -> list[CronJob]:
        """List all jobs."""
        return list(self.jobs.values())

    def list_enabled(self) -> list[CronJob]:
        """List all enabled jobs."""
        return [j for j in self.jobs.values() if j.enabled]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "jobs": {job_id: job.to_dict() for job_id, job in self.jobs.items()}
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CronStore":
        """Create from dictionary."""
        jobs = {}
        for job_id, job_data in data.get("jobs", {}).items():
            jobs[job_id] = CronJob.from_dict(job_data)
        return cls(jobs=jobs)