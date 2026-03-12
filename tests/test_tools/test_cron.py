"""Tests for CronTool."""

import pytest
from lanobot.tools.cron import CronTool, CronSchedule, SimpleCronService


class TestCronSchedule:
    """Test cases for CronSchedule."""

    def test_every_schedule(self):
        """Test every-second schedule."""
        schedule = CronSchedule(kind="every", every_ms=60000)
        assert schedule.kind == "every"
        assert schedule.every_ms == 60000

    def test_cron_schedule(self):
        """Test cron expression schedule."""
        schedule = CronSchedule(kind="cron", expr="0 9 * * *", tz="Asia/Shanghai")
        assert schedule.kind == "cron"
        assert schedule.expr == "0 9 * * *"

    def test_at_schedule(self):
        """Test one-time schedule."""
        schedule = CronSchedule(kind="at", at_ms=1700000000000)
        assert schedule.kind == "at"
        assert schedule.at_ms == 1700000000000


class TestSimpleCronService:
    """Test cases for SimpleCronService."""

    def test_add_job(self):
        """Test adding a cron job."""
        service = SimpleCronService()
        schedule = CronSchedule(kind="every", every_ms=60000)

        job = service.add_job(
            name="test_task",
            schedule=schedule,
            message="Test message",
            channel="cli",
            to="user123",
        )

        assert job.id is not None
        assert job.name == "test_task"
        assert job.message == "Test message"

    def test_list_jobs(self):
        """Test listing jobs."""
        service = SimpleCronService()
        schedule = CronSchedule(kind="every", every_ms=60000)

        service.add_job(name="job1", schedule=schedule, message="msg1")
        service.add_job(name="job2", schedule=schedule, message="msg2")

        jobs = service.list_jobs()
        assert len(jobs) == 2

    def test_remove_job(self):
        """Test removing a job."""
        service = SimpleCronService()
        schedule = CronSchedule(kind="every", every_ms=60000)

        job = service.add_job(name="job1", schedule=schedule, message="msg1")
        assert service.remove_job(job.id) is True
        assert service.remove_job(job.id) is False  # Already removed


class TestCronTool:
    """Test cases for CronTool."""

    @pytest.mark.asyncio
    async def test_list_jobs_empty(self):
        """Test listing jobs when none exist."""
        tool = CronTool()
        tool.set_context("cli", "user123")

        result = await tool.execute(action="list")

        assert "No scheduled jobs" in result

    @pytest.mark.asyncio
    async def test_add_job_every_seconds(self):
        """Test adding a job with every_seconds."""
        tool = CronTool()
        tool.set_context("cli", "user123")

        result = await tool.execute(
            action="add",
            message="Remind me",
            every_seconds=3600,
        )

        assert "Created job" in result
        assert "job_" in result

    @pytest.mark.asyncio
    async def test_add_job_missing_message(self):
        """Test adding job without message returns error."""
        tool = CronTool()
        tool.set_context("cli", "user123")

        result = await tool.execute(action="add", every_seconds=60)

        assert "Error" in result
        assert "message is required" in result

    @pytest.mark.asyncio
    async def test_add_job_no_context(self):
        """Test adding job without context returns error."""
        tool = CronTool()

        result = await tool.execute(action="add", message="Test", every_seconds=60)

        assert "Error" in result
        assert "session context" in result

    @pytest.mark.asyncio
    async def test_add_job_with_cron(self):
        """Test adding job with cron expression."""
        tool = CronTool()
        tool.set_context("cli", "user123")

        result = await tool.execute(
            action="add",
            message="Daily task",
            cron_expr="0 9 * * *",
        )

        assert "Created job" in result

    @pytest.mark.asyncio
    async def test_add_job_with_invalid_tz(self):
        """Test adding job with invalid timezone."""
        tool = CronTool()
        tool.set_context("cli", "user123")

        result = await tool.execute(
            action="add",
            message="Task",
            cron_expr="0 9 * * *",
            tz="Invalid/Timezone",
        )

        assert "Error" in result
        assert "unknown timezone" in result

    @pytest.mark.asyncio
    async def test_remove_job(self):
        """Test removing a job."""
        tool = CronTool()
        tool.set_context("cli", "user123")

        # First add a job
        add_result = await tool.execute(
            action="add",
            message="Temp task",
            every_seconds=60,
        )
        assert "Created job" in add_result

        # List to get job id
        list_result = await tool.execute(action="list")
        assert "Temp task" in list_result

        # Extract job id from result (format: job_1)
        import re
        match = re.search(r"id: (job_\d+)", list_result)
        assert match is not None
        job_id = match.group(1)

        # Remove it
        remove_result = await tool.execute(action="remove", job_id=job_id)
        assert "Removed job" in remove_result

    @pytest.mark.asyncio
    async def test_remove_job_no_id(self):
        """Test removing job without id returns error."""
        tool = CronTool()

        result = await tool.execute(action="remove")

        assert "Error" in result
        assert "job_id is required" in result

    @pytest.mark.asyncio
    async def test_unknown_action(self):
        """Test unknown action returns error."""
        tool = CronTool()

        result = await tool.execute(action="invalid")

        assert "Unknown action" in result