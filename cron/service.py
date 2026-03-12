"""Cron service for scheduling and executing periodic tasks."""
import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Callable, Optional

from cron.types import CronJob, CronSchedule, CronStore

logger = logging.getLogger(__name__)


class CronService:
    """Async cron service with persistence support."""

    def __init__(
        self,
        store_path: Optional[Path] = None,
        on_job: Optional[Callable[[CronJob], Any]] = None,
    ):
        """
        Initialize CronService.

        Args:
            store_path: Path to persist jobs (JSON file)
            on_job: Callback function when a job should execute
        """
        self._store_path = store_path
        self._on_job = on_job
        self._store = CronStore()
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Load existing jobs from disk
        if store_path and store_path.exists():
            self._load()

    def _load(self) -> None:
        """Load jobs from disk."""
        try:
            with open(self._store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._store = CronStore.from_dict(data)
            logger.info(f"Loaded {len(self._store.jobs)} cron jobs from {self._store_path}")
        except Exception as e:
            logger.warning(f"Failed to load cron jobs: {e}")

    def _save(self) -> None:
        """Save jobs to disk."""
        if not self._store_path:
            return

        try:
            self._store_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._store_path, "w", encoding="utf-8") as f:
                json.dump(self._store.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save cron jobs: {e}")

    async def start(self) -> None:
        """Start the cron service."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Cron service started")

    async def stop(self) -> None:
        """Stop the cron service."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._save()
        logger.info("Cron service stopped")

    async def _run_loop(self) -> None:
        """Main loop that checks and executes jobs."""
        while self._running:
            try:
                await self._check_and_execute()
            except Exception as e:
                logger.error(f"Error in cron loop: {e}")

            # Check every second
            await asyncio.sleep(1)

    async def _check_and_execute(self) -> None:
        """Check each enabled job and execute if due."""
        now = asyncio.get_event_loop().time()

        for job in self._store.list_enabled():
            next_run = self._get_next_run_time(job.schedule)
            if next_run is None:
                continue

            # Check if it's time to run (within 1 second window)
            if next_run <= now:
                logger.info(f"Executing cron job: {job.name} (id: {job.id})")

                # Execute callback if provided
                if self._on_job:
                    try:
                        result = self._on_job(job)
                        # Support both sync and async callbacks
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(f"Error executing job {job.id}: {e}")

                # Handle one-time jobs
                if job.delete_after_run or job.schedule.kind == "at":
                    self.remove_job(job.id)
                else:
                    # Update next run time is handled by recalculating in next iteration
                    pass

    def _get_next_run_time(self, schedule: CronSchedule) -> Optional[float]:
        """Calculate next run time as a timestamp."""
        from datetime import datetime

        now = datetime.now()
        loop = asyncio.get_event_loop()
        now_ts = loop.time()

        if schedule.kind == "every" and schedule.every_ms:
            return now_ts + (schedule.every_ms / 1000)
        elif schedule.kind == "cron" and schedule.expr:
            try:
                from croniter import croniter

                tz = schedule.tz if schedule.tz else "local"
                cron = croniter(schedule.expr, now, tzinfo=tz)
                next_dt = cron.get_next(datetime)
                return next_dt.timestamp()
            except Exception as e:
                logger.error(f"Failed to calculate cron next run: {e}")
                return None
        elif schedule.kind == "at" and schedule.at_ms:
            at_ts = schedule.at_ms / 1000
            return at_ts if at_ts > now_ts else None
        return None

    def add_job(
        self,
        name: str,
        schedule: CronSchedule,
        message: str,
        channel: str = "",
        to: str = "",
        delete_after_run: bool = False,
    ) -> CronJob:
        """
        Add a new cron job.

        Args:
            name: Job name
            schedule: Cron schedule
            message: Message to deliver
            channel: Channel name for delivery
            to: Recipient identifier
            delete_after_run: Delete job after execution

        Returns:
            The created CronJob
        """
        import uuid

        job_id = str(uuid.uuid4())[:8]
        job = CronJob(
            id=job_id,
            name=name,
            message=message,
            schedule=schedule,
            channel=channel,
            to=to,
            delete_after_run=delete_after_run,
        )
        self._store.add(job)
        self._save()
        logger.info(f"Added cron job: {job.name} (id: {job.id})")
        return job

    def remove_job(self, job_id: str) -> bool:
        """
        Remove a cron job.

        Args:
            job_id: Job ID to remove

        Returns:
            True if job was removed, False if not found
        """
        result = self._store.remove(job_id)
        if result:
            self._save()
            logger.info(f"Removed cron job: {job_id}")
        return result

    def get_job(self, job_id: str) -> Optional[CronJob]:
        """Get a job by ID."""
        return self._store.get(job_id)

    def list_jobs(self) -> list[CronJob]:
        """List all jobs."""
        return self._store.list_all()

    def list_enabled_jobs(self) -> list[CronJob]:
        """List all enabled jobs."""
        return self._store.list_enabled()