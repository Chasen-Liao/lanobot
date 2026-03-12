"""长期记忆存储模块 - 基于 LangGraph Store API 和文件系统.

支持：
- InMemoryStore：运行时语义记忆（LangGraph Store API）
- 文件系统长期记忆：~/.lanobot/memory/ 目录下的 markdown 文件

架构：
- 工作目录/memory/README.md - 索引文件（Agent 首先读取）
- 工作目录/memory/user_profile.md - 用户画像
- 工作目录/memory/*.md - 其他主题记忆
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# LangGraph Store API - 延迟导入
InMemoryStoreImpl = None


def _ensure_in_memory_store():
    """确保 InMemoryStore 可用."""
    global InMemoryStoreImpl
    if InMemoryStoreImpl is None:
        from langgraph.store.memory import InMemoryStore as InMemoryStoreImpl
    return InMemoryStoreImpl


# 默认用户记忆路径
DEFAULT_MEMORY_PATH = Path.home() / ".lanobot" / "memory"


@dataclass
class MemoryFile:
    """单个记忆文件."""

    path: Path
    title: str = ""
    content: str = ""
    last_updated: Optional[datetime] = None

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> None:
        """从文件加载内容."""
        if self.exists():
            self.content = self.path.read_text(encoding="utf-8")
            self.last_updated = datetime.fromtimestamp(self.path.stat().st_mtime)
            # 从文件名提取标题
            if not self.title:
                self.title = self.path.stem.replace("_", " ").replace("-", " ").title()

    def save(self, content: str) -> None:
        """保存内容到文件.

        Raises:
            IOError: 当写入文件失败时
        """
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(content, encoding="utf-8")
            self.content = content
            self.last_updated = datetime.now()
        except OSError as e:
            raise IOError(f"Failed to save memory file {self.path}: {e}") from e


class FileMemoryStore:
    """文件系统长期记忆存储.

    管理 ~/.lanobot/memory/ 目录下的 markdown 记忆文件。
    自动维护 README.md 索引。
    """

    DEFAULT_FILES = [
        "README.md",
        "user_profile.md",
        "preferences.md",
    ]

    def __init__(self, memory_path: Optional[Path] = None):
        """初始化文件系统记忆存储.

        Args:
            memory_path: 记忆目录路径，默认 ~/.lanobot/memory/
        """
        self._memory_path = memory_path or DEFAULT_MEMORY_PATH
        self._memory_path.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, MemoryFile] = {}
        self._load_index()

    def _load_index(self) -> None:
        """加载现有记忆文件索引."""
        self._index.clear()
        if not self._memory_path.exists():
            return

        for md_file in self._memory_path.glob("*.md"):
            memory_file = MemoryFile(path=md_file)
            memory_file.load()
            self._index[md_file.stem] = memory_file

    @property
    def memory_path(self) -> Path:
        return self._memory_path

    def get(self, name: str) -> Optional[MemoryFile]:
        """获取指定名称的记忆文件.

        Args:
            name: 记忆文件名（不含扩展名）

        Returns:
            MemoryFile 对象或 None
        """
        return self._index.get(name)

    def get_or_create(self, name: str) -> MemoryFile:
        """获取或创建记忆文件.

        Args:
            name: 记忆文件名（不含扩展名）

        Returns:
            MemoryFile 对象
        """
        if name not in self._index:
            self._index[name] = MemoryFile(path=self._memory_path / f"{name}.md")
        return self._index[name]

    def list_all(self) -> list[MemoryFile]:
        """列出所有记忆文件.

        Returns:
            按修改时间排序的记忆文件列表
        """
        files = list(self._index.values())
        files.sort(key=lambda f: f.last_updated or datetime.min, reverse=True)
        return files

    def read(self, name: str) -> str:
        """读取记忆内容.

        Args:
            name: 记忆文件名

        Returns:
            记忆内容，文件不存在返回空字符串
        """
        memory_file = self.get(name)
        return memory_file.content if memory_file else ""

    def write(self, name: str, content: str) -> None:
        """写入记忆内容.

        Args:
            name: 记忆文件名
            content: 记忆内容
        """
        memory_file = self.get_or_create(name)
        memory_file.save(content)
        # 同步更新索引
        self._update_readme_index()

    def delete(self, name: str) -> bool:
        """删除记忆文件.

        Args:
            name: 记忆文件名

        Returns:
            是否成功删除
        """
        if name in self._index:
            memory_file = self._index.pop(name)
            if memory_file.exists():
                memory_file.path.unlink()
                self._update_readme_index()
                return True
        return False

    def search(self, query: str) -> list[dict[str, Any]]:
        """在记忆文件中搜索内容（简单文本搜索）.

        Args:
            query: 搜索关键词

        Returns:
            匹配的记忆列表
        """
        results = []
        query_lower = query.lower()
        for name, memory_file in self._index.items():
            if query_lower in memory_file.content.lower():
                results.append({
                    "name": name,
                    "title": memory_file.title,
                    "path": str(memory_file.path),
                    "last_updated": memory_file.last_updated.isoformat() if memory_file.last_updated else None,
                })
        return results

    def _update_readme_index(self) -> None:
        """更新 README.md 索引."""
        readme_path = self._memory_path / "README.md"
        files = self.list_all()

        # 构建索引内容
        lines = [
            "# Memory Index",
            "",
            "本目录包含 Lanobot 的长期记忆。",
            "",
            "## 文件列表",
            "",
        ]

        # 排除 README.md 本身
        other_files = [f for f in files if f.path.name != "README.md"]
        for memory_file in other_files:
            title = memory_file.title or memory_file.path.stem
            last_update = memory_file.last_updated.strftime("%Y-%m-%d") if memory_file.last_updated else "Unknown"
            lines.append(f"- [{title}]({memory_file.path.name}) (更新时间: {last_update})")

        lines.extend([
            "",
            "## 使用说明",
            "",
            "Agent 可以直接读取这些 markdown 文件来获取长期记忆。",
            "README.md 是索引，建议首先读取它来了解可用的记忆。",
        ])

        content = "\n".join(lines)
        readme = self.get_or_create("README")
        readme.save(content)

    def get_readme_content(self) -> str:
        """获取 README.md 索引内容.

        Returns:
            README.md 内容
        """
        return self.read("README")


class MemoryStore:
    """Lanobot 专用记忆存储 - 两层结构.

    - 运行时记忆（InMemoryStore）：基于 LangGraph Store API，
      支持语义搜索，适用于会话级上下文
    - 长期记忆（FileMemoryStore）：基于文件系统 (markdown)，
      保留在 ~/.lanobot/memory/ 目录
    """

    def __init__(
        self,
        store: Optional[Any] = None,
        *,
        # 文件存储路径
        memory_path: Optional[Path] = None,
    ):
        """初始化记忆存储.

        Args:
            store: LangGraph Store 实例（可选）
            memory_path: 长期记忆目录路径，默认 ~/.lanobot/memory/
        """
        self._store = store
        self._file_store = FileMemoryStore(memory_path)

    @property
    def store(self) -> Optional[Any]:
        """返回底层 LangGraph Store."""
        return self._store

    @property
    def file_store(self) -> FileMemoryStore:
        """返回文件系统记忆存储."""
        return self._file_store

    def _get_store(self) -> Any:
        """获取或创建 store（懒加载）."""
        if self._store is None:
            InMemoryStore = _ensure_in_memory_store()
            self._store = InMemoryStore()
        return self._store

    # ==================== 运行时语义记忆操作 ====================

    async def aput(
        self,
        key: str,
        value: dict[str, Any],
        *,
        namespace: Optional[tuple[str, ...]] = None,
    ) -> None:
        """异步保存记忆.

        Args:
            key: 记忆键
            value: 记忆值（字典）
            namespace: 命名空间（可选）
        """
        ns = namespace or ("lanobot", "memory")
        await self._get_store().aput(ns, key, value)

    async def aget(
        self,
        key: str,
        *,
        namespace: Optional[tuple[str, ...]] = None,
    ) -> Optional[dict[str, Any]]:
        """异步获取记忆.

        Args:
            key: 记忆键
            namespace: 命名空间（可选）

        Returns:
            记忆值或 None
        """
        ns = namespace or ("lanobot", "memory")
        result = await self._get_store().aget(ns, key)
        return result.value if result else None

    async def adelete(
        self,
        key: str,
        *,
        namespace: Optional[tuple[str, ...]] = None,
    ) -> bool:
        """异步删除记忆.

        Args:
            key: 记忆键
            namespace: 命名空间（可选）

        Returns:
            是否成功删除
        """
        ns = namespace or ("lanobot", "memory")
        return await self._get_store().adelete(ns, key)

    async def asearch(
        self,
        query: str,
        *,
        namespace: Optional[tuple[str, ...]] = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """语义搜索记忆.

        Args:
            query: 查询字符串
            namespace: 命名空间（可选）
            limit: 返回数量限制

        Returns:
            匹配的记忆列表
        """
        ns = namespace or ("lanobot", "memory")
        results = await self._get_store().asearch(ns, query, limit=limit)
        return [{"key": r.key, "value": r.value} for r in results]

    # 同步版本
    def put(
        self,
        key: str,
        value: dict[str, Any],
        *,
        namespace: Optional[tuple[str, ...]] = None,
    ) -> None:
        """同步保存记忆."""
        import asyncio
        ns = namespace or ("lanobot", "memory")
        asyncio.run(self._get_store().aput(ns, key, value))

    def get(
        self,
        key: str,
        *,
        namespace: Optional[tuple[str, ...]] = None,
    ) -> Optional[dict[str, Any]]:
        """同步获取记忆."""
        import asyncio
        ns = namespace or ("lanobot", "memory")
        result = asyncio.run(self._get_store().aget(ns, key))
        return result.value if result else None

    def delete(
        self,
        key: str,
        *,
        namespace: Optional[tuple[str, ...]] = None,
    ) -> bool:
        """同步删除记忆."""
        import asyncio
        ns = namespace or ("lanobot", "memory")
        return asyncio.run(self._get_store().adelete(ns, key))

    def search(
        self,
        query: str,
        *,
        namespace: Optional[tuple[str, ...]] = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """同步语义搜索."""
        import asyncio
        ns = namespace or ("lanobot", "memory")
        results = asyncio.run(self._get_store().asearch(ns, query, limit=limit))
        return [{"key": r.key, "value": r.value} for r in results]

    # ==================== 文件系统长期记忆操作 ====================

    def read_long_term(self, name: str = "user_profile") -> str:
        """读取长期记忆.

        Args:
            name: 记忆文件名（不含扩展名），默认 user_profile

        Returns:
            记忆内容
        """
        return self._file_store.read(name)

    def write_long_term(self, name: str, content: str) -> None:
        """写入长期记忆.

        Args:
            name: 记忆文件名
            content: 记忆内容
        """
        self._file_store.write(name, content)

    def list_long_term_memories(self) -> list[dict[str, Any]]:
        """列出所有长期记忆文件.

        Returns:
            记忆文件信息列表
        """
        files = self._file_store.list_all()
        return [
            {
                "name": f.path.stem,
                "title": f.title,
                "path": str(f.path),
                "last_updated": f.last_updated.isoformat() if f.last_updated else None,
            }
            for f in files
            if f.path.name != "README.md"
        ]

    def get_memory_context(self) -> str:
        """获取记忆上下文（用于 LLM 提示词）.

        读取 README.md 索引作为入口。
        """
        readme = self._file_store.get_readme_content()
        if not readme:
            return ""
        return f"## Long-term Memory\n\n{readme}"


def get_store(
    memory_path: Optional[Path] = None,
) -> MemoryStore:
    """获取记忆存储实例。

    Args:
        memory_path: 长期记忆目录路径，默认 ~/.lanobot/memory/

    Returns:
        MemoryStore 实例

    Examples:
        # 使用默认路径
        >>> store = get_store()

        # 指定自定义路径
        >>> store = get_store(Path("./my_memory"))
    """
    InMemoryStore = _ensure_in_memory_store()
    store_instance = InMemoryStore()
    return MemoryStore(store=store_instance, memory_path=memory_path)


# 类型别名
MemoryStoreType = MemoryStore

__all__ = [
    "MemoryStore",
    "FileMemoryStore",
    "MemoryFile",
    "get_store",
    "DEFAULT_MEMORY_PATH",
]