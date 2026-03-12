# Phase 7: 会话管理实施计划

## Context

Lanobot 项目已完成 Phase 1-6，需要实现 Phase 7 会话管理。

**核心需求**：
- 复用现有的 `lanobot/memory/history.py`（HistoryManager - 内存会话历史）
- 参考 nanobot 的 `session/manager.py` 实现持久化会话管理
- 与现有 AgentGraph、MessageBus 集成
- 支持多渠道会话隔离
- 双轨制：AgentGraph checkpointer + SessionManager 独立持久化

## Technical Solution

### 架构设计

```
session/
├── __init__.py           # 模块导出
├── manager.py            # SessionManager（持久化会话管理）
├── types.py              # Session/Meta 数据类
└── summaries/            # 消息摘要目录

memory/
├── history.py            # 现有：HistoryManager（内存会话历史）
└── ...
```

**核心类**：
1. **Session** - 单个会话数据类（消息列表、时间戳、元数据）
2. **SessionManager** - 会话管理器（持久化 JSONL 文件 + 过期清理 + 摘要压缩）
3. **SessionMetadata** - 会话元数据（标题、过期时间、是否永久保存）
4. **HistoryManager** - 已有：内存会话历史（保留，用于 AgentGraph context）

**数据流（双轨制）**：

```
用户消息
    ↓
SessionManager.get_or_create(key) → 从 JSONL 加载历史
    ↓
session.add_message("user", content) → 内存
    ↓
HistoryManager.load_from_session(session) → 加载到内存缓存
    ↓
AgentGraph.invoke() → 使用 HistoryManager 作为 context
    ↓
session.add_message("assistant", response) → 内存
    ↓
SessionManager.save(session) → 写入 JSONL 文件
    ↓
检查是否需要压缩（>100k tokens）→ 生成摘要到 summaries/
    ↓
检查过期 → 清理过期会话（非 pinned 且 >30 天）
```

### 详细设计

#### 1. SessionMetadata - 会话元数据

```python
@dataclass
class SessionMetadata:
    """会话元数据"""
    key: str                          # channel:chat_id
    title: str = ""                   # 会话标题（用户自定义或 LLM 生成）
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = None       # 过期时间，None=永久保存
    is_pinned: bool = False           # 永久保存标记
    message_count: int = 0
    last_summarized_at: datetime = None  # 上次摘要时间
    summary_token_count: int = 0      # 摘要 token 数

    # 标题来源
    title_source: str = "auto"        # "auto" | "user"
```

#### 2. Session - 会话数据类

```python
@dataclass
class Session:
    """单个会话"""
    key: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    metadata: SessionMetadata = field(default_factory=SessionMetadata)
    last_consolidated: int = 0

    def add_message(self, role: str, content: str, **kwargs) -> None: ...
    def get_history(self, max_messages: int = 500) -> list[dict]: ...
    def estimate_tokens(self) -> int: ...
    def needs_compression(self, threshold: int = 100000) -> bool: ...
    def generate_title(self) -> str: ...  # 调用 LLM 生成
```

#### 3. SessionManager - 会话管理器

```python
class SessionManager:
    """会话管理器 - 持久化 JSONL 存储 + 过期清理 + 摘要压缩"""

    def __init__(
        self,
        workspace: Path,
        default_ttl_days: int = 30,       # 默认 30 天过期
        compression_threshold: int = 100000,  # 100k tokens 压缩
    ):
        self.workspace = workspace
        self.sessions_dir = ensure_dir(workspace / "sessions")
        self.summaries_dir = ensure_dir(workspace / "sessions" / "summaries")
        self._cache: dict[str, Session] = {}

    # === 核心方法 ===
    def get_or_create(self, key: str) -> Session: ...
    def save(self, session: Session) -> None: ...     # 写入 JSONL
    def load(self, key: str) -> Session | None: ...   # 从 JSONL 加载
    def delete(self, key: str) -> bool: ...
    def list_sessions(self) -> list[dict]: ...

    # === 过期管理 ===
    def cleanup_expired(self) -> int:
        """清理过期会话（非 pinned 且已过期），返回删除数量"""
        ...

    # === 摘要压缩 ===
    def compress_if_needed(self, session: Session, llm=None) -> bool:
        """检查是否需要压缩，如需要则生成摘要"""
        if session.estimate_tokens() > self.compression_threshold:
            await self._generate_summary(session, llm)
            return True
        return False

    def _generate_summary(self, session: Session, llm) -> None:
        """调用 LLM 生成对话摘要，保存到 summaries/"""
        ...

    # === 标题管理 ===
    def set_title(self, key: str, title: str) -> bool: ...
    def pin_session(self, key: str, pinned: bool = True) -> bool: ...
    async def generate_title_async(self, key: str, llm) -> str: ...

    # === 便捷方法 ===
    def load_to_history_manager(
        self,
        key: str,
        history_manager: HistoryManager
    ) -> None:
        """将会话加载到 HistoryManager"""
        ...
```

### 消息摘要文件格式

```
sessions/
├── telegram_123456789.jsonl          # 原始消息
├── dingtalk_88888888.jsonl
└── summaries/
    ├── telegram_123456789.summary.jsonl  # 摘要文件
    └── dingtalk_88888888.summary.jsonl
```

```json
// summary.jsonl 格式
{"timestamp": "2026-03-12T10:00:00", "token_count": 5000, "summary": "用户讨论了..."}
{"timestamp": "2026-03-13T15:30:00", "token_count": 6000, "summary": "继续讨论..."}
```

### 过期清理策略

- 启动时自动清理一次
- 可选：定时任务每小时清理
- 清理条件：`not is_pinned and expires_at and now() > expires_at`

## Implementation Steps

### 7.1 创建会话模块结构

| 文件 | 操作 | 描述 |
|------|------|------|
| `session/__init__.py` | 新建 | 模块导出 |
| `session/types.py` | 新建 | Session / SessionMetadata 数据类 |
| `session/manager.py` | 新建 | SessionManager 持久化管理 |

### 7.2 实现 Session 数据类

```
# session/types.py
- SessionMetadata: 元数据（标题、过期、pinned）
- Session: 消息列表 + 元数据
- add_message(), get_history(), needs_compression()
```

### 7.3 实现 SessionManager

```
# session/manager.py
- __init__(workspace, default_ttl_days, compression_threshold)
- get_or_create(key) / save(session) / load(key)
- delete(key) / list_sessions()
- cleanup_expired() - 过期清理
- compress_if_needed() - 摘要压缩（>100k tokens）
- set_title() / pin_session() - 标题和永久保存
- generate_title_async() - LLM 生成标题
```

### 7.4 集成到 main.py

```python
# main.py - 添加会话管理
from session.manager import SessionManager

class Lanobot:
    async def setup(self) -> None:
        # 现有代码...

        # 创建会话管理器
        self.session_manager = SessionManager(
            workspace=self.config.workspace_dir,
            default_ttl_days=30,
            compression_threshold=100000,
        )

        # 启动时清理过期会话
        deleted = self.session_manager.cleanup_expired()
        if deleted:
            print(f"[Session] 清理了 {deleted} 个过期会话")

    async def _handle_message(self, message) -> None:
        # 获取会话
        session = self.session_manager.get_or_create(message.session_key)

        # 首次消息生成标题（如果还没有）
        if not session.metadata.title and session.message_count == 0:
            session.metadata.title = await self._generate_title(
                message.content,
                self.agent.model
            )

        # 添加用户消息
        session.add_message("user", message.content)

        # 加载到 HistoryManager 供 Agent 使用
        self.session_manager.load_to_history_manager(
            message.session_key,
            self.agent.history
        )

        # 调用 Agent
        response = await self.agent.ainvoke(
            message.content,
            thread_id=message.session_key
        )

        # 添加回复到会话
        session.add_message("assistant", response["messages"][-1].content)

        # 保存会话
        self.session_manager.save(session)

        # 检查是否需要压缩
        self.session_manager.compress_if_needed(
            session,
            self.agent.model
        )
```

### 7.5 命令支持

添加会话管理命令：

| 命令 | 功能 |
|------|------|
| `/pin` | 永久保存当前会话 |
| `/unpin` | 取消永久保存 |
| `/title 新标题` | 设置会话标题 |
| `/sessions` | 列出所有会话 |

### 7.6 编写测试

```python
# tests/test_session/test_manager.py
def test_session_creation(): ...
def test_session_persistence(): ...
def test_session_list(): ...
def test_session_deletion(): ...
def test_session_expiry(): ...
def test_session_pin(): ...
def test_session_compression_trigger(): ...
```

## Key Files

| 文件 | 操作 | 描述 |
|------|------|------|
| `session/__init__.py` | 新建 | 模块导出 |
| `session/types.py` | 新建 | Session / SessionMetadata 数据类 |
| `session/manager.py` | 新建 | SessionManager 持久化管理 |
| `main.py` | 修改 | 集成 SessionManager 到消息循环 |
| `tests/test_session/` | 新建 | 会话管理测试 |

## Dependencies

- `tiktoken` - Token 估算（已有）
- 无新依赖

## Risks and Mitigation

| Risk | Level | Mitigation |
|------|-------|------------|
| 与 HistoryManager 功能重叠 | Low | SessionManager 负责持久化，HistoryManager 负责内存缓存，各司其职 |
| 会话文件过大 | Medium | 使用 JSONL 格式追加写入，100k tokens 自动压缩摘要 |
| 并发写入冲突 | Low | 简单实现不考虑并发，后续可加锁 |
| LLM 摘要生成失败 | Medium | 压缩失败不影响主流程，记录日志继续运行 |

## Verification

1. `uv run pytest tests/test_session/` - 会话测试通过
2. 启动 main.py 后，会话自动保存到 `workspace/sessions/` 目录
3. 重启后能加载历史会话
4. 超过 100k tokens 自动生成摘要到 `summaries/`
5. 超过 30 天非 pinned 会话自动清理
6. `/pin` 命令可以永久保存会话
7. 会话标题正确显示

## 复用参考

- `nanobot/nanobot/session/manager.py` - 完整 SessionManager 实现（JSONL 存储）
- `lanobot/memory/history.py` - 已有 HistoryManager（内存历史）
- `lanobot/config/paths.py` - 路径管理工具