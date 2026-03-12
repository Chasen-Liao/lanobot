"""会话管理器 - 持久化会话管理（JSONL 存储 + LLM 摘要）。

支持：
- 会话创建、加载、保存、删除
- 多渠道会话隔离
- 过期自动清理
- 消息摘要压缩（10万 tokens 触发 LLM 摘要）
- 标题管理（LLM 生成 + 用户自定义）
- 与 HistoryManager 集成
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from lanobot.memory.history import estimate_messages_tokens, ConversationHistory

from .types import Session, SessionMetadata, DEFAULT_COMPRESSION_THRESHOLD


def _ensure_dir(path: Path) -> Path:
    """确保目录存在."""
    path.mkdir(parents=True, exist_ok=True)
    return path


class SessionManager:
    """会话管理器 - 持久化 JSONL 存储 + 过期清理 + 摘要压缩.

    特性：
    - 基于文件系统的持久化（workspace/sessions/）
    - JSONL 追加写入
    - 多渠道会话隔离
    - 过期自动清理（30天）
    - 消息摘要压缩（10万 tokens，LLM 生成）
    """

    def __init__(
        self,
        workspace: Optional[Path] = None,
        sessions_dir: Optional[Path] = None,
        compression_threshold: int = DEFAULT_COMPRESSION_THRESHOLD,
        default_ttl_days: int = 30,
        auto_save: bool = True,
    ):
        """初始化会话管理器.

        Args:
            workspace: 工作目录，默认 Path.cwd() / "workspace"
            sessions_dir: 会话存储目录，默认 workspace/sessions/
            compression_threshold: token 压缩阈值
            default_ttl_days: 默认过期天数
            auto_save: 是否自动保存会话
        """
        self._workspace = workspace or Path.cwd() / "workspace"
        self._sessions_dir = sessions_dir or _ensure_dir(self._workspace / "sessions")
        self._summaries_dir = _ensure_dir(self._sessions_dir / "summaries")
        self._compression_threshold = compression_threshold
        self._default_ttl_days = default_ttl_days
        self._auto_save = auto_save

        # 内存缓存：key -> Session
        self._cache: dict[str, Session] = {}

    @property
    def sessions_dir(self) -> Path:
        """返回会话存储目录."""
        return self._sessions_dir

    @property
    def summaries_dir(self) -> Path:
        """返回摘要存储目录."""
        return self._summaries_dir

    def _get_session_path(self, key: str) -> Path:
        """获取会话文件路径（JSONL 格式）.

        Args:
            key: 会话 key

        Returns:
            会话文件路径
        """
        # 将 key 转为安全的文件名：telegram:123456 -> telegram_123456
        safe_name = key.replace("/", "-").replace("\\", "-").replace(":", "_")
        return self._sessions_dir / f"{safe_name}.jsonl"

    def _restore_key(self, filename: str) -> str:
        """从文件名恢复原始 key.

        Args:
            filename: 文件名（不含路径和扩展名）

        Returns:
            原始 key
        """
        # 恢复：telegram_123456 -> telegram:123456（第一个 _ 改为 :）
        return filename.replace("_", ":", 1)

    def _get_summary_path(self, key: str) -> Path:
        """获取摘要文件路径（JSONL 格式）.

        Args:
            key: 会话 key

        Returns:
            摘要文件路径
        """
        safe_name = key.replace("/", "-").replace("\\", "-").replace(":", "_")
        return self._summaries_dir / f"{safe_name}.summary.jsonl"

    def get_or_create(self, key: str) -> Session:
        """获取或创建会话.

        Args:
            key: 会话 key（channel:chat_id）

        Returns:
            Session 实例
        """
        # 优先从缓存获取
        if key in self._cache:
            session = self._cache[key]
            session.metadata.updated_at = datetime.now()
            return session

        # 尝试从文件加载
        session = self._load(key)
        if session is None:
            # 创建新会话
            session = Session(key=key)
            session.metadata.key = key
            session.metadata.expires_at = datetime.now() + timedelta(
                days=self._default_ttl_days
            )

        # 缓存
        self._cache[key] = session
        return session

    def get(self, key: str) -> Optional[Session]:
        """获取会话（不自动创建）.

        Args:
            key: 会话 key

        Returns:
            Session 实例或 None
        """
        # 优先从缓存获取
        if key in self._cache:
            return self._cache[key]

        # 尝试从文件加载
        session = self._load(key)
        if session:
            self._cache[key] = session
        return session

    def _load(self, key: str) -> Optional[Session]:
        """从 JSONL 文件加载会话.

        Args:
            key: 会话 key

        Returns:
            Session 实例或 None
        """
        path = self._get_session_path(key)
        if not path.exists():
            return None

        try:
            messages = []
            metadata_dict = {}
            for line in path.read_text(encoding="utf-8").strip().split("\n"):
                if not line:
                    continue
                record = json.loads(line)
                if record.get("type") == "metadata":
                    metadata_dict = record.get("data", {})
                elif record.get("type") == "message":
                    messages.append(record.get("data", {}))

            if not metadata_dict:
                return None

            session = Session.from_dict({
                "key": key,
                "messages": messages,
                "metadata": metadata_dict,
            })

            # 检查是否过期
            if session.metadata.should_expire():
                path.unlink()
                return None

            return session
        except (json.JSONDecodeError, KeyError, OSError) as e:
            print(f"Failed to load session {key}: {e}")
            return None

    def save(self, session: Session) -> None:
        """保存会话到 JSONL 文件（追加写入）.

        Args:
            session: 会话实例
        """
        path = self._get_session_path(session.key)

        try:
            # 追加写入模式
            with open(path, "a", encoding="utf-8") as f:
                # 写入元数据（只有第一条消息时写入，后续更新元数据）
                if path.stat().st_size == 0 or not path.exists():
                    metadata_record = {
                        "type": "metadata",
                        "timestamp": datetime.now().isoformat(),
                        "data": session.metadata.to_dict(),
                    }
                    f.write(json.dumps(metadata_record, ensure_ascii=False) + "\n")

                # 追加新消息
                if session.messages:
                    last_msg = session.messages[-1]
                    msg_record = {
                        "type": "message",
                        "timestamp": datetime.now().isoformat(),
                        "data": last_msg,
                    }
                    f.write(json.dumps(msg_record, ensure_ascii=False) + "\n")

        except OSError as e:
            print(f"Failed to save session {session.key}: {e}")

    def save_full(self, session: Session) -> None:
        """完整保存会话（覆盖写入，用于压缩后保存完整状态）.

        Args:
            session: 会话实例
        """
        path = self._get_session_path(session.key)

        try:
            with open(path, "w", encoding="utf-8") as f:
                # 写入元数据
                metadata_record = {
                    "type": "metadata",
                    "timestamp": datetime.now().isoformat(),
                    "data": session.metadata.to_dict(),
                }
                f.write(json.dumps(metadata_record, ensure_ascii=False) + "\n")

                # 写入所有消息
                for msg in session.messages:
                    msg_record = {
                        "type": "message",
                        "timestamp": msg.get("timestamp", datetime.now().isoformat()),
                        "data": msg,
                    }
                    f.write(json.dumps(msg_record, ensure_ascii=False) + "\n")

        except OSError as e:
            print(f"Failed to save session {session.key}: {e}")

    def delete(self, key: str) -> bool:
        """删除会话.

        Args:
            key: 会话 key

        Returns:
            是否成功删除
        """
        # 从缓存中移除
        if key in self._cache:
            del self._cache[key]

        # 删除会话文件
        session_path = self._get_session_path(key)
        if session_path.exists():
            try:
                session_path.unlink()
            except OSError:
                return False

        # 删除摘要文件
        summary_path = self._get_summary_path(key)
        if summary_path.exists():
            try:
                summary_path.unlink()
            except OSError:
                pass

        return True

    def list_sessions(
        self,
        channel: Optional[str] = None,
        include_expired: bool = False,
    ) -> list[SessionMetadata]:
        """列出所有会话元数据.

        Args:
            channel: 渠道过滤（可选）
            include_expired: 是否包含已过期的会话

        Returns:
            会话元数据列表（按更新时间排序）
        """
        sessions = []

        if not self._sessions_dir.exists():
            return sessions

        for jsonl_file in self._sessions_dir.glob("*.jsonl"):
            try:
                data = json.loads(jsonl_file.read_text(encoding="utf-8").split("\n")[0])
                if data.get("type") != "metadata":
                    continue
                key = self._restore_key(jsonl_file.stem)
                session = Session.from_dict({
                    "key": key,
                    "metadata": data.get("data", {}),
                    "messages": [],
                })

                # 过滤
                key_parts = session.key.split(":")
                session_channel = key_parts[0] if key_parts else "default"
                if channel and session_channel != channel:
                    continue
                if not include_expired and session.metadata.should_expire():
                    continue

                sessions.append(session.metadata)
            except (json.JSONDecodeError, KeyError, OSError):
                continue

        # 按更新时间排序
        sessions.sort(key=lambda m: m.updated_at, reverse=True)
        return sessions

    def cleanup_expired(self) -> int:
        """清理过期会话.

        Returns:
            清理的会话数量
        """
        count = 0
        now = datetime.now()

        if not self._sessions_dir.exists():
            return count

        for jsonl_file in self._sessions_dir.glob("*.jsonl"):
            try:
                data = json.loads(jsonl_file.read_text(encoding="utf-8").split("\n")[0])
                if data.get("type") != "metadata":
                    continue
                session = Session.from_dict({
                    "key": jsonl_file.stem,
                    "metadata": data.get("data", {}),
                    "messages": [],
                })

                # 检查是否过期（非 pinned 且已过期）
                if session.metadata.should_expire():
                    jsonl_file.unlink()
                    # 删除摘要文件
                    summary_path = self._get_summary_path(session.key)
                    if summary_path.exists():
                        summary_path.unlink()
                    # 从缓存中移除
                    if session.key in self._cache:
                        del self._cache[session.key]
                    count += 1
            except (json.JSONDecodeError, KeyError, OSError):
                continue

        return count

    async def compress_if_needed(self, session: Session, llm=None) -> bool:
        """如果需要则压缩会话，调用 LLM 生成摘要.

        Args:
            session: 会话实例
            llm: LLM 实例（用于生成摘要）

        Returns:
            是否执行了压缩
        """
        if session.needs_compression(self._compression_threshold):
            if llm:
                await self._generate_summary(session, llm)
            return True
        return False

    async def _generate_summary(self, session: Session, llm) -> None:
        """调用 LLM 生成对话摘要，保存到 summaries/.

        Args:
            session: 会话实例
            llm: LLM 实例
        """
        try:
            # 构建摘要 Prompt
            recent_messages = session.get_history(max_messages=50)
            prompt = self._build_summary_prompt(recent_messages)

            # 调用 LLM 生成摘要
            response = await llm.ainvoke(prompt)
            summary_text = response.content if hasattr(response, "content") else str(response)

            # 估算摘要 token 数
            summary_tokens = len(summary_text) // 4

            # 保存摘要到 JSONL
            summary_record = {
                "timestamp": datetime.now().isoformat(),
                "token_count": summary_tokens,
                "summary": summary_text,
            }

            summary_path = self._get_summary_path(session.key)
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(summary_record, ensure_ascii=False) + "\n")

            # 更新元数据
            session.metadata.last_summarized_at = datetime.now()
            session.metadata.summary_token_count += summary_tokens
            session.metadata.updated_at = datetime.now()

            # 压缩消息，保留最近 20 条
            session.compress(keep_recent=20)

            # 保存完整状态
            self.save_full(session)

            print(f"[Session] 已生成摘要，key={session.key}, tokens={summary_tokens}")

        except Exception as e:
            print(f"Failed to generate summary: {e}")
            # 摘要失败不影响主流程，简单压缩保留
            session.compress(keep_recent=20)

    def _build_summary_prompt(self, messages: list[dict[str, Any]]) -> str:
        """构建摘要 Prompt.

        Args:
            messages: 消息列表

        Returns:
            Prompt 字符串
        """
        conversation = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, list):
                # 处理多部分内容
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                content = " ".join(text_parts)
            conversation.append(f"{role}: {content}")

        conversation_text = "\n".join(conversation[-30:])  # 最近 30 条

        return f"""请为以下对话生成一个简洁的摘要，概括对话的主要内容和主题。

对话内容：
{conversation_text}

请生成 2-3 句话的摘要："""

    async def generate_title_async(self, key: str, llm) -> Optional[str]:
        """异步生成会话标题（调用 LLM）。

        Args:
            key: 会话 key
            llm: LLM 实例

        Returns:
            生成的标题
        """
        session = self.get(key)
        if not session:
            return None

        try:
            # 获取前几条消息
            recent = session.get_history(max_messages=5)
            if not recent:
                return None

            # 构建标题生成 Prompt
            prompt = self._build_title_prompt(recent)

            # 调用 LLM
            response = await llm.ainvoke(prompt)
            title = response.content if hasattr(response, "content") else str(response)
            title = title.strip()

            # 保存标题
            session.metadata.title = title
            session.metadata.title_source = "auto"
            session.metadata.updated_at = datetime.now()

            if self._auto_save:
                self.save_full(session)

            return title

        except Exception as e:
            print(f"Failed to generate title: {e}")
            return None

    def _build_title_prompt(self, messages: list[dict[str, Any]]) -> str:
        """构建标题生成 Prompt.

        Args:
            messages: 消息列表

        Returns:
            Prompt 字符串
        """
        # 获取用户的第一条消息
        user_first_msg = ""
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    user_first_msg = content[:200]
                    break

        if not user_first_msg:
            user_first_msg = "新对话"

        return f"""请为以下对话生成一个简洁的标题（不超过 20 个字）：

用户首条消息：{user_first_msg}

请直接返回标题，不要任何前缀："""

    def load_to_history_manager(
        self,
        key: str,
        history_manager: "ConversationHistory",
    ) -> None:
        """将会话加载到 HistoryManager（或 ConversationHistory）。

        Args:
            key: 会话 key
            history_manager: HistoryManager 或 ConversationHistory 实例
        """
        session = self.get(key)
        if not session:
            return

        # 设置 max_tokens 为压缩阈值
        history_manager.max_tokens = self._compression_threshold
        history_manager.messages = session.messages.copy()

    # ==================== 同步标题生成（兼容旧接口） ====================

    def set_title(self, key: str, title: str) -> bool:
        """设置会话标题.

        Args:
            key: 会话 key
            title: 标题

        Returns:
            是否成功
        """
        session = self.get(key)
        if session is None:
            return False
        session.metadata.title = title
        session.metadata.title_source = "user"
        session.metadata.updated_at = datetime.now()
        if self._auto_save:
            self.save_full(session)
        return True

    def pin_session(self, key: str, pinned: bool = True) -> bool:
        """固定/取消固定会话.

        Args:
            key: 会话 key
            pinned: 是否固定

        Returns:
            是否成功
        """
        session = self.get(key)
        if session is None:
            return False
        if pinned:
            session.metadata.pin()
        else:
            session.metadata.unpin()
        session.metadata.updated_at = datetime.now()
        if self._auto_save:
            self.save_full(session)
        return True

    # ==================== 缓存管理 ====================

    def clear_cache(self) -> None:
        """清空内存缓存."""
        self._cache.clear()

    def flush(self) -> int:
        """将所有缓存的会话写入磁盘.

        Returns:
            保存的会话数量
        """
        count = 0
        for session in self._cache.values():
            self.save_full(session)
            count += 1
        return count


# ==================== 便捷函数 ====================


def create_session_manager(
    workspace: Optional[Path] = None,
    sessions_dir: Optional[Path] = None,
    compression_threshold: int = DEFAULT_COMPRESSION_THRESHOLD,
    expire_days: int = 30,
) -> SessionManager:
    """创建会话管理器实例.

    Args:
        workspace: 工作目录
        sessions_dir: 会话存储目录
        compression_threshold: token 压缩阈值
        expire_days: 过期天数

    Returns:
        SessionManager 实例
    """
    return SessionManager(
        workspace=workspace,
        sessions_dir=sessions_dir,
        compression_threshold=compression_threshold,
        default_ttl_days=expire_days,
    )


# 类型别名
SessionManagerType = SessionManager

__all__ = [
    "SessionManager",
    "SessionManagerType",
    "create_session_manager",
]