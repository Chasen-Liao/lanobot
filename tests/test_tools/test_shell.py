"""Tests for ExecTool."""

import pytest
from lanobot.tools.shell import ExecTool


class TestExecTool:
    """Test cases for ExecTool."""

    @pytest.mark.asyncio
    async def test_execute_simple_command(self):
        """Test executing a simple command."""
        tool = ExecTool(timeout=30)

        # Use a simple command that works on both Windows and Unix
        result = await tool.execute(command="echo hello")

        assert "hello" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_with_working_dir(self, tmp_path):
        """Test executing a command with custom working directory."""
        tool = ExecTool(timeout=30)

        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        # Read the file - use type for Windows
        result = await tool.execute(command=f"type {tmp_path}\\test.txt")

        assert "test content" in result

    @pytest.mark.asyncio
    async def test_dangerous_command_blocked(self):
        """Test that dangerous commands are blocked."""
        tool = ExecTool(timeout=30, deny_patterns=[
            r"\brm\s+-[rf]{1,2}\b",
            r"\bdel\b",
        ])

        result = await tool.execute(command="rm -rf /")

        assert "blocked" in result.lower()

    @pytest.mark.asyncio
    async def test_command_timeout(self):
        """Test command timeout."""
        tool = ExecTool(timeout=1)

        # Use a command that sleeps longer than timeout
        # On Windows: timeout /t 10 > nul, on Unix: sleep 10
        result = await tool.execute(command="timeout /t 10 2>nul || sleep 10")

        # Should timeout
        assert "timed out" in result.lower() or "timeout" in result.lower()

    @pytest.mark.asyncio
    async def test_nonexistent_command(self):
        """Test executing a non-existent command."""
        tool = ExecTool(timeout=30)

        result = await tool.execute(command="nonexistent_command_xyz")

        # Should have exit code non-zero (error)
        assert "Exit code:" in result
        assert "1" in result

    @pytest.mark.asyncio
    async def test_command_with_stderr(self):
        """Test command that produces stderr output."""
        tool = ExecTool(timeout=30)

        # Using a command that produces both stdout and stderr
        # On Windows: dir nonexistent, on Unix: ls /nonexistent 2>&1
        result = await tool.execute(command="ls /nonexistentdirectory 2>&1")

        # Should contain error output
        assert result  # Should have some output

    def test_guard_command_deny_patterns(self):
        """Test command guard with deny patterns."""
        tool = ExecTool(deny_patterns=[r"\brm\b", r"\bfork\b"])

        assert tool._guard_command("rm -rf /", "/tmp") is not None
        assert tool._guard_command("fork()", "/tmp") is not None

    def test_guard_command_allowed(self):
        """Test command guard allows safe commands."""
        tool = ExecTool()

        assert tool._guard_command("ls -la", "/tmp") is None
        assert tool._guard_command("echo hello", "/tmp") is None

    def test_guard_command_allow_patterns(self):
        """Test command guard with allow patterns."""
        tool = ExecTool(allow_patterns=[r"^git", r"^ls"])

        # Should be allowed
        assert tool._guard_command("git status", "/tmp") is None
        assert tool._guard_command("ls -la", "/tmp") is None

        # Should be blocked (not in allowlist)
        assert tool._guard_command("echo hello", "/tmp") is not None

    def test_extract_absolute_paths(self):
        """Test extracting absolute paths from commands."""
        tool = ExecTool()

        # Windows paths
        win_paths = tool._extract_absolute_paths("copy C:\\file.txt D:\\backup\\")
        assert "C:\\file.txt" in win_paths

        # POSIX paths
        posix_paths = tool._extract_absolute_paths("cat /etc/hostname")
        assert "/etc/hostname" in posix_paths