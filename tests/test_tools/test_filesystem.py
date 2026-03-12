"""Tests for filesystem tools."""

import pytest
from pathlib import Path

from lanobot.tools.filesystem import (
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    ListDirTool,
)


class TestReadFileTool:
    """Test cases for ReadFileTool."""

    @pytest.mark.asyncio
    async def test_read_file_success(self, tmp_path):
        """Test reading a file successfully."""
        test_file = tmp_path / "test.txt"
        test_content = "Hello, World!"
        test_file.write_text(test_content, encoding="utf-8")

        tool = ReadFileTool(workspace=tmp_path)
        result = await tool.execute(path="test.txt")

        assert result == test_content

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, tmp_path):
        """Test reading a file that doesn't exist."""
        tool = ReadFileTool(workspace=tmp_path)
        result = await tool.execute(path="nonexistent.txt")

        assert "Error" in result
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_read_file_as_directory(self, tmp_path):
        """Test reading a directory as a file."""
        tool = ReadFileTool(workspace=tmp_path)
        result = await tool.execute(path=".")

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_read_file_absolute_path(self, tmp_path):
        """Test reading file with absolute path."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content", encoding="utf-8")

        tool = ReadFileTool()
        result = await tool.execute(path=str(test_file))

        assert result == "content"

    @pytest.mark.asyncio
    async def test_read_file_truncation(self, tmp_path):
        """Test that large files are truncated."""
        test_file = tmp_path / "large.txt"
        # Create a file larger than MAX_CHARS
        test_content = "x" * 200000
        test_file.write_text(test_content, encoding="utf-8")

        tool = ReadFileTool(workspace=tmp_path)
        result = await tool.execute(path="large.txt")

        assert "truncated" in result


class TestWriteFileTool:
    """Test cases for WriteFileTool."""

    @pytest.mark.asyncio
    async def test_write_file_success(self, tmp_path):
        """Test writing a file successfully."""
        tool = WriteFileTool(workspace=tmp_path)
        result = await tool.execute(path="new_file.txt", content="Hello, World!")

        assert "Successfully" in result
        assert (tmp_path / "new_file.txt").read_text(encoding="utf-8") == "Hello, World!"

    @pytest.mark.asyncio
    async def test_write_file_create_parent_dirs(self, tmp_path):
        """Test that parent directories are created."""
        tool = WriteFileTool(workspace=tmp_path)
        result = await tool.execute(
            path="subdir/nested/file.txt",
            content="nested content"
        )

        assert "Successfully" in result
        assert (tmp_path / "subdir" / "nested" / "file.txt").read_text(encoding="utf-8") == "nested content"

    @pytest.mark.asyncio
    async def test_write_file_overwrite(self, tmp_path):
        """Test overwriting an existing file."""
        test_file = tmp_path / "existing.txt"
        test_file.write_text("old content", encoding="utf-8")

        tool = WriteFileTool(workspace=tmp_path)
        result = await tool.execute(path="existing.txt", content="new content")

        assert "Successfully" in result
        assert test_file.read_text(encoding="utf-8") == "new content"


class TestEditFileTool:
    """Test cases for EditFileTool."""

    @pytest.mark.asyncio
    async def test_edit_file_success(self, tmp_path):
        """Test editing a file successfully."""
        test_file = tmp_path / "edit_test.txt"
        test_file.write_text("Hello, World!", encoding="utf-8")

        tool = EditFileTool(workspace=tmp_path)
        result = await tool.execute(
            path="edit_test.txt",
            old_text="World",
            new_text="Python"
        )

        assert "Successfully" in result
        assert test_file.read_text(encoding="utf-8") == "Hello, Python!"

    @pytest.mark.asyncio
    async def test_edit_file_not_found(self, tmp_path):
        """Test editing a file that doesn't exist."""
        tool = EditFileTool(workspace=tmp_path)
        result = await tool.execute(
            path="nonexistent.txt",
            old_text="old",
            new_text="new"
        )

        assert "Error" in result
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_edit_file_old_text_not_found(self, tmp_path):
        """Test editing with non-existent old text."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!", encoding="utf-8")

        tool = EditFileTool(workspace=tmp_path)
        result = await tool.execute(
            path="test.txt",
            old_text="NonExistent",
            new_text="New"
        )

        assert "Error" in result
        assert "old_text not found" in result

    @pytest.mark.asyncio
    async def test_edit_file_multiple_occurrences(self, tmp_path):
        """Test editing with ambiguous old text."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello hello hello", encoding="utf-8")

        tool = EditFileTool(workspace=tmp_path)
        result = await tool.execute(
            path="test.txt",
            old_text="hello",
            new_text="hi"
        )

        assert "Warning" in result
        assert "appears" in result


class TestListDirTool:
    """Test cases for ListDirTool."""

    @pytest.mark.asyncio
    async def test_list_dir_success(self, tmp_path):
        """Test listing a directory successfully."""
        # Create some files and directories
        (tmp_path / "file1.txt").write_text("content")
        (tmp_path / "file2.txt").write_text("content")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "nested.txt").write_text("content")

        tool = ListDirTool(workspace=tmp_path)
        result = await tool.execute(path=".")

        assert "file1.txt" in result
        assert "file2.txt" in result
        assert "subdir" in result
        # Check directory indicator
        assert "D subdir" in result
        assert "F file1.txt" in result

    @pytest.mark.asyncio
    async def test_list_dir_empty(self, tmp_path):
        """Test listing an empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        tool = ListDirTool(workspace=tmp_path)
        result = await tool.execute(path="empty")

        assert "empty" in result
        assert "is empty" in result

    @pytest.mark.asyncio
    async def test_list_dir_not_found(self, tmp_path):
        """Test listing a directory that doesn't exist."""
        tool = ListDirTool(workspace=tmp_path)
        result = await tool.execute(path="nonexistent")

        assert "Error" in result
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_list_dir_as_file(self, tmp_path):
        """Test listing a file as a directory."""
        test_file = tmp_path / "file.txt"
        test_file.write_text("content")

        tool = ListDirTool(workspace=tmp_path)
        result = await tool.execute(path="file.txt")

        assert "Error" in result
        assert "Not a directory" in result