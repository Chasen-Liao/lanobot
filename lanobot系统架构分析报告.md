# Lanobot 系统架构分析报告

## 1. 项目概述

### 1.1 项目定位
Lanobot 是一个**超轻量级个人 AI 助手**，基于 LangChain 1.2 和 LangGraph 开发。它采用模块化架构，支持多 LLM 提供商、多渠道接入、工具扩展和记忆管理。

### 1.2 核心特性
- 🤖 **LLM 集成** - 支持 19+ 种 LLM 提供商（SiliconFlow、DeepSeek、OpenAI、Anthropic 等）
- 💬 **多渠道支持** - 飞书、QQ、Telegram、Slack、Discord、钉钉、企业微信、WhatsApp
- 🔌 **MCP 支持** - Model Context Protocol 扩展
- 📡 **消息总线** - 异步消息队列架构
- ⏰ **定时任务** - Cron 定时提醒和任务
- 💓 **心跳服务** - 自动执行周期性任务
- 💾 **会话管理** - 持久化存储、自动摘要、过期清理
- 🧠 **记忆系统** - 短期记忆（Checkpointer）+ 长期记忆（Store）

### 1.3 技术栈
- **LangChain 1.2** - Agent 框架
- **LangGraph** - 状态流和持久化
- **Pydantic V2** - 配置管理
- **Python 3.11+** - 运行环境

---

## 2. 系统架构总览

### 2.1 整体架构图

```mermaid
graph TB
    subgraph "用户层"
        U1[飞书]
        U2[Telegram]
        U3[QQ]
        U4[其他渠道]
    end
    
    subgraph "渠道网关层 (Gateway)"
        CM[ChannelManager<br/>渠道管理器]
        U1 --> CM
        U2 --> CM
        U3 --> CM
        U4 --> CM
    end
    
    subgraph "消息总线层 (Bus)"
        MB[MessageBus<br/>异步消息队列]
        IQ[InboundQueue<br/>入站队列]
        OQ[OutboundQueue<br/>出站队列]
        CM --> IQ
        IQ --> MB
        MB --> OQ
        OQ --> CM
    end
    
    subgraph "Agent 核心层 (Lanobot)"
        AG[AgentGraph<br/>状态图引擎]
        SM[SessionManager<br/>会话管理]
        MB --> AG
        AG --> SM
    end
    
    subgraph "服务层 (Services)"
        CS[CronService<br/>定时任务]
        HS[HeartbeatService<br/>心跳服务]
        CS -.定时消息.-> MB
        HS -.周期任务.-> MB
    end
    
    subgraph "存储层 (Storage)"
        WS[Workspace<br/>工作空间]
        DB[(Sessions<br/>会话数据)]
        KB[(Knowledge<br/>知识库)]
        SM --> DB
        AG --> KB
        CS --> WS
        HS --> WS
    end
    
    style AG fill:#e1f5ff
    style MB fill:#fff3e0
    style CM fill:#f3e5f5
    style SM fill:#e8f5e9
```

### 2.2 运行模式

Lanobot 支持三种运行模式：

| 模式 | 说明 | 启动命令 | 包含组件 |
|------|------|----------|----------|
| **agent** | 仅 Agent 核心 | `lanobot run agent` | AgentGraph + Tools + Memory |
| **gateway** | 仅渠道网关 | `lanobot run gateway` | ChannelManager + MessageBus |
| **all** | 完整服务 | `lanobot run start` | 所有组件 |

---

## 3. Agent 核心架构

### 3.1 AgentGraph 状态图

AgentGraph 是 Lanobot 的核心，基于 LangGraph StateGraph 构建，实现了一个可扩展的 Agent 执行流程。


```mermaid
graph LR
    START([开始]) --> RAG[RAG 节点<br/>知识检索]
    RAG --> ROUTER[Router 节点<br/>模型路由]
    ROUTER --> LLM[LLM 节点<br/>模型推理]
    LLM --> DECISION{需要工具?}
    DECISION -->|是| TOOLS[Tools 节点<br/>工具执行]
    DECISION -->|否| END([结束])
    TOOLS --> LLM
    
    style RAG fill:#e3f2fd
    style ROUTER fill:#f3e5f5
    style LLM fill:#fff3e0
    style TOOLS fill:#e8f5e9
```

### 3.2 节点详解

#### 3.2.1 RAG 节点（知识检索）
- **功能**：在 LLM 调用前自动检索知识库
- **输入**：用户最新消息
- **输出**：`rag_context`（检索到的上下文）
- **实现**：`lanobot/agent/nodes.py::create_rag_node()`
- **检索器**：`InMemoryRAG`（简单关键词匹配）或自定义向量检索器

#### 3.2.2 Router 节点（模型路由）
- **功能**：根据任务类型自动选择合适的模型
- **路由策略**：
  - 简单问题 → 快速模型（如 Haiku、mini）
  - 复杂问题 → 强力模型（如 Sonnet、Pro）
  - 代码问题 → 代码专用模型
- **输入**：用户消息
- **输出**：`selected_model`（选中的模型实例）
- **实现**：`lanobot/agent/router.py::ModelRouter`

#### 3.2.3 LLM 节点（模型推理）
- **功能**：使用选中的模型执行推理
- **输入**：
  - `messages`（对话历史）
  - `selected_model`（Router 选择的模型）
  - `rag_context`（RAG 检索的上下文）
  - `system_prompt`（系统提示词）
- **输出**：新的 AI 消息（可能包含工具调用）
- **实现**：`lanobot/agent/nodes.py::create_llm_node()`


#### 3.2.4 Tools 节点（工具执行）
- **功能**：执行 LLM 请求的工具调用
- **输入**：`tool_calls`（工具调用列表）
- **输出**：工具执行结果
- **实现**：`langgraph.prebuilt.ToolNode`
- **循环**：执行完工具后返回 LLM 节点继续推理

### 3.3 状态定义

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]  # 对话历史
    session_id: Optional[str]                              # 会话ID
    user_id: Optional[str]                                 # 用户ID
    context: Optional[dict]                                # 额外上下文
    rag_context: Optional[str]                             # RAG 检索上下文
    selected_model: Optional[Any]                          # Router 选择的模型
    tool_calls: Optional[list[Any]]                        # 工具调用列表
```

### 3.4 执行流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant AG as AgentGraph
    participant RAG as RAG节点
    participant Router as Router节点
    participant LLM as LLM节点
    participant Tools as Tools节点
    
    User->>AG: 发送消息
    AG->>RAG: 检索知识库
    RAG-->>AG: 返回上下文
    AG->>Router: 选择模型
    Router-->>AG: 返回模型实例
    AG->>LLM: 调用模型推理
    LLM-->>AG: 返回响应（可能含工具调用）
    
    alt 需要工具
        AG->>Tools: 执行工具
        Tools-->>AG: 返回结果
        AG->>LLM: 继续推理
        LLM-->>AG: 返回最终响应
    end
    
    AG-->>User: 返回响应
```

---

## 4. 工具系统

### 4.1 工具注册表架构

```mermaid
classDiagram
    class ToolRegistry {
        -dict~str,Tool~ _tools
        +register(tool: Tool)
        +unregister(name: str)
        +get(name: str) Tool
        +get_definitions() list
        +get_langchain_tools() list
        +execute(name: str, params: dict) str
    }
    
    class Tool {
        +str name
        +str description
        +dict schema
        +to_schema() dict
        +to_langchain_tool() Any
        +execute(**params) str
        +validate_params(params: dict) list
        +cast_params(params: dict) dict
    }
    
    ToolRegistry "1" --> "*" Tool
```


### 4.2 内置工具列表

| 工具名称 | 文件 | 功能 | 关键方法 |
|---------|------|------|---------|
| **filesystem** | `lanobot/tools/filesystem.py` | 文件系统操作 | read_file, write_file, list_dir |
| **shell** | `lanobot/tools/shell.py` | Shell 命令执行 | exec_command |
| **web** | `lanobot/tools/web.py` | 网页抓取 | fetch_url, search_web |
| **message** | `lanobot/tools/message.py` | 消息发送 | send_message |
| **cron** | `lanobot/tools/cron.py` | 定时任务管理 | add_cron, remove_cron |
| **spawn** | `lanobot/tools/spawn.py` | 子 Agent 创建 | spawn_subagent |
| **mcp** | `lanobot/tools/mcp.py` | MCP 协议扩展 | call_mcp_tool |

### 4.3 工具创建流程

```python
# 1. 创建工具注册表
from lanobot.tools import create_tool_registry

registry = create_tool_registry(
    workspace="./workspace",
    include_filesystem=True,
    include_shell=True,
    include_web=False,
    include_message=True,
    include_cron=False,
)

# 2. 获取 LangChain 工具
tools = registry.get_langchain_tools()

# 3. 绑定到 AgentGraph
agent = AgentGraph(model=model, tools=tools)
```

---

## 5. 记忆系统

### 5.1 记忆架构

```mermaid
graph TB
    subgraph "短期记忆 (Checkpointer)"
        CP[MemorySaver<br/>内存检查点]
        CP_DESC[存储对话状态<br/>支持状态回溯]
    end
    
    subgraph "长期记忆 (Store)"
        ST[MemoryStore<br/>持久化存储]
        ST_DESC[存储用户偏好<br/>历史摘要]
    end
    
    subgraph "会话管理 (Session)"
        SM[SessionManager<br/>会话管理器]
        JSONL[JSONL 文件<br/>追加写入]
        META[Metadata<br/>元数据]
        SM --> JSONL
        SM --> META
    end
    
    subgraph "知识库 (RAG)"
        KB[Knowledge Base<br/>知识库]
        VEC[Vector Store<br/>向量存储]
        KB --> VEC
    end
    
    AG[AgentGraph] --> CP
    AG --> ST
    AG --> SM
    AG --> KB
    
    style CP fill:#e3f2fd
    style ST fill:#f3e5f5
    style SM fill:#fff3e0
    style KB fill:#e8f5e9
```


### 5.2 记忆类型对比

| 记忆类型 | 实现 | 存储内容 | 生命周期 | 用途 |
|---------|------|---------|---------|------|
| **短期记忆** | MemorySaver | 对话状态、消息历史 | 会话期间 | 状态持久化、回溯 |
| **长期记忆** | MemoryStore | 用户偏好、历史摘要 | 永久 | 跨会话记忆 |
| **会话管理** | SessionManager | 完整对话记录 | 30天（可配置） | 会话恢复、摘要 |
| **知识库** | RAGNode | 文档、知识片段 | 永久 | 上下文检索 |

### 5.3 会话管理流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant CM as ChannelManager
    participant SM as SessionManager
    participant DB as JSONL 文件
    participant LLM as LLM（摘要）
    
    User->>CM: 发送消息
    CM->>SM: get_or_create(session_key)
    SM->>DB: 加载会话（如果存在）
    DB-->>SM: 返回历史消息
    SM-->>CM: 返回 Session 对象
    
    CM->>SM: add_message(role, content)
    SM->>SM: 检查 token 数量
    
    alt 超过阈值（10万 tokens）
        SM->>LLM: 请求摘要
        LLM-->>SM: 返回摘要
        SM->>SM: 压缩历史
    end
    
    CM->>SM: save(session)
    SM->>DB: 追加写入 JSONL
    
    Note over SM,DB: 定期清理过期会话（30天）
```

### 5.4 会话压缩策略

- **触发条件**：消息总 token 数超过 10 万
- **压缩方式**：使用 LLM 生成摘要，保留最近 N 条消息
- **保留策略**：
  - 保留系统消息
  - 保留最近 20 条消息
  - 其他消息压缩为摘要

---

## 6. 提供商系统

### 6.1 提供商架构

```mermaid
classDiagram
    class ProviderSpec {
        +str name
        +str default_model
        +str env_key
        +str default_api_base
        +str litellm_prefix
        +list skip_prefixes
        +bool strip_model_prefix
        +dict model_overrides
    }
    
    class ProviderRegistry {
        +dict~str,ProviderSpec~ _providers
        +register(spec: ProviderSpec)
        +get_provider(name: str) ProviderSpec
        +find_by_name(name: str) ProviderSpec
        +find_by_model(model: str) ProviderSpec
        +find_gateway(...) ProviderSpec
    }
    
    class ProviderFactory {
        +create_llm(...) ChatOpenAI
        +create_llm_with_config(...) ChatOpenAI
        +detect_provider_from_config(...) str
    }
    
    ProviderRegistry "1" --> "*" ProviderSpec
    ProviderFactory --> ProviderRegistry
```


### 6.2 支持的提供商（19+）

| 提供商 | 默认模型 | API Base | 特点 |
|-------|---------|----------|------|
| **SiliconFlow** | Qwen/Qwen2.5-7B-Instruct | api.siliconflow.cn | 国内高性价比 |
| **DeepSeek** | deepseek-chat | api.deepseek.com | 国产强力模型 |
| **OpenAI** | gpt-4o-mini | api.openai.com | 官方 API |
| **Anthropic** | claude-3-5-sonnet-20241022 | api.anthropic.com | Claude 系列 |
| **OpenRouter** | - | openrouter.ai | 聚合网关 |
| **Groq** | llama-3.3-70b-versatile | api.groq.com | 超快推理 |
| **Together** | - | api.together.xyz | 开源模型托管 |
| **Fireworks** | - | api.fireworks.ai | 高性能推理 |
| **Replicate** | - | api.replicate.com | 模型市场 |
| **Cohere** | command-r-plus | api.cohere.ai | 企业级 |
| **AI21** | jamba-1.5-large | api.ai21.com | Jamba 系列 |
| **Mistral** | mistral-large-latest | api.mistral.ai | Mistral 官方 |
| **Perplexity** | llama-3.1-sonar-large-128k-online | api.perplexity.ai | 联网搜索 |
| **Gemini** | gemini-2.0-flash-exp | generativelanguage.googleapis.com | Google 官方 |
| **xAI** | grok-beta | api.x.ai | Grok 系列 |
| **Cerebras** | llama3.1-70b | api.cerebras.ai | 超快推理 |
| **Sambanova** | Meta-Llama-3.1-70B-Instruct | api.sambanova.ai | Llama 优化 |
| **Hyperbolic** | meta-llama/Meta-Llama-3.1-70B-Instruct | api.hyperbolic.xyz | 低成本 |
| **Novita** | meta-llama/llama-3.1-70b-instruct | api.novita.ai | 多模型支持 |

### 6.3 提供商创建流程

```python
from lanobot.providers import create_llm

# 方式1：使用默认配置
llm = create_llm("siliconflow")

# 方式2：指定模型
llm = create_llm("deepseek", model="deepseek-chat")

# 方式3：完整配置
llm = create_llm(
    provider="openai",
    model="gpt-4o",
    api_key="sk-xxx",
    base_url="https://api.openai.com/v1",
    temperature=0.5,
    max_tokens=4096,
    extra_headers={"Custom-Header": "value"},
)
```

---

## 7. 消息总线系统

### 7.1 消息总线架构

```mermaid
graph LR
    subgraph "渠道层"
        CH1[飞书]
        CH2[Telegram]
        CH3[QQ]
    end
    
    subgraph "消息总线"
        IQ[InboundQueue<br/>入站队列]
        OQ[OutboundQueue<br/>出站队列]
    end
    
    subgraph "Agent 层"
        AG[AgentGraph]
    end
    
    CH1 -->|publish_inbound| IQ
    CH2 -->|publish_inbound| IQ
    CH3 -->|publish_inbound| IQ
    
    IQ -->|consume_inbound| AG
    AG -->|publish_outbound| OQ
    
    OQ -->|consume_outbound| CH1
    OQ -->|consume_outbound| CH2
    OQ -->|consume_outbound| CH3
    
    style IQ fill:#e3f2fd
    style OQ fill:#fff3e0
```


### 7.2 消息类型

```python
# 入站消息（从渠道到 Agent）
class InboundMessage:
    channel: str        # 渠道名称（如 "telegram"）
    chat_id: str        # 聊天ID
    user_id: str        # 用户ID
    content: str        # 消息内容
    timestamp: float    # 时间戳
    metadata: dict      # 额外元数据

# 出站消息（从 Agent 到渠道）
class OutboundMessage:
    channel: str        # 目标渠道
    chat_id: str        # 目标聊天ID
    content: str        # 消息内容
    reply_to: str       # 回复的消息ID（可选）
    metadata: dict      # 额外元数据
```

### 7.3 消息流转流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant Channel as 渠道（Telegram）
    participant Bus as MessageBus
    participant Agent as AgentGraph
    participant Session as SessionManager
    
    User->>Channel: 发送消息
    Channel->>Bus: publish_inbound(msg)
    Bus->>Agent: consume_inbound()
    Agent->>Session: get_or_create(session_key)
    Session-->>Agent: 返回会话
    Agent->>Agent: 执行推理
    Agent->>Session: add_message(response)
    Agent->>Bus: publish_outbound(response)
    Bus->>Channel: consume_outbound()
    Channel->>User: 发送响应
```

---

## 8. 服务系统

### 8.1 服务架构

```mermaid
graph TB
    subgraph "定时任务服务 (CronService)"
        CS[CronService]
        CJ[CronJob 列表]
        CSTORE[jobs.json]
        CS --> CJ
        CS --> CSTORE
    end
    
    subgraph "心跳服务 (HeartbeatService)"
        HS[HeartbeatService]
        HF[HEARTBEAT.md]
        HLLM[LLM 决策器]
        HS --> HF
        HS --> HLLM
    end
    
    subgraph "消息总线"
        MB[MessageBus]
    end
    
    CS -.定时触发.-> MB
    HS -.周期检查.-> MB
    
    style CS fill:#e3f2fd
    style HS fill:#fff3e0
```

### 8.2 CronService（定时任务）

#### 功能
- 支持 cron 表达式（如 `0 9 * * *`）
- 支持间隔执行（如每 30 分钟）
- 支持一次性任务（at 时间点）
- 持久化存储（JSON 文件）

#### 任务格式
```python
class CronJob:
    id: str                    # 任务ID
    name: str                  # 任务名称
    message: str               # 要发送的消息
    schedule: CronSchedule     # 调度配置
    channel: str               # 目标渠道
    to: str                    # 接收者
    enabled: bool              # 是否启用
    delete_after_run: bool     # 执行后删除
```


#### 调度类型
```python
class CronSchedule:
    kind: str           # "cron" | "every" | "at"
    expr: str           # cron 表达式（kind=cron）
    every_ms: int       # 间隔毫秒（kind=every）
    at_ms: int          # 时间戳（kind=at）
    tz: str             # 时区
```

#### 使用示例
```python
# 每天早上 9 点发送提醒
cron_service.add_job(
    name="每日提醒",
    schedule=CronSchedule(kind="cron", expr="0 9 * * *"),
    message="早上好！今天要做什么？",
    channel="telegram",
    to="user_123",
)

# 每 30 分钟检查一次
cron_service.add_job(
    name="定期检查",
    schedule=CronSchedule(kind="every", every_ms=1800000),  # 30分钟
    message="定期检查任务",
    channel="admin",
    to="system",
)
```

### 8.3 HeartbeatService（心跳服务）

#### 功能
- 定期检查 `HEARTBEAT.md` 文件
- 使用 LLM 决策哪些任务需要执行
- 支持任务标记（完成/未完成）
- 自动更新任务状态

#### HEARTBEAT.md 格式
```markdown
# Heartbeat Tasks

- [ ] 每日总结: 生成今天的工作总结
- [x] 周报生成: 每周五生成周报（已完成）
- [ ] 数据备份: 检查数据库备份状态
```

#### 决策流程
```mermaid
sequenceDiagram
    participant HS as HeartbeatService
    participant HF as HEARTBEAT.md
    participant LLM as LLM
    participant MB as MessageBus
    
    loop 每 30 分钟
        HS->>HF: 读取任务列表
        HF-->>HS: 返回任务
        HS->>LLM: 请求决策（哪些任务需要执行）
        LLM-->>HS: 返回任务名称列表
        
        loop 对每个任务
            HS->>MB: publish_outbound(task_message)
            HS->>HF: 更新任务状态
        end
    end
```

---

## 9. 渠道系统

### 9.1 渠道管理器架构

```mermaid
classDiagram
    class ChannelManager {
        -dict~str,Channel~ _channels
        -MessageBus _bus
        -AgentGraph _agent
        -SessionManager _session_manager
        +start_all()
        +stop_all()
        +start_channel(name: str)
        +stop_channel(name: str)
    }
    
    class Channel {
        <<interface>>
        +start()
        +stop()
        +send_message(chat_id, content)
        +on_message(callback)
    }
    
    class FeishuChannel {
        +start()
        +stop()
        +send_message(...)
    }
    
    class TelegramChannel {
        +start()
        +stop()
        +send_message(...)
    }
    
    ChannelManager "1" --> "*" Channel
    Channel <|-- FeishuChannel
    Channel <|-- TelegramChannel
```


### 9.2 支持的渠道

| 渠道 | 文件 | 状态 | 特点 |
|------|------|------|------|
| **飞书** | `bus/channels/feishu.py` | ✅ | 企业级，支持卡片消息 |
| **Telegram** | `bus/channels/telegram.py` | ✅ | 国际主流，功能丰富 |
| **QQ** | `bus/channels/qq.py` | ✅ | 国内主流 |
| **Slack** | `bus/channels/slack.py` | ✅ | 企业协作 |
| **Discord** | `bus/channels/discord.py` | ✅ | 游戏社区 |
| **钉钉** | `bus/channels/dingtalk.py` | ✅ | 企业办公 |
| **企业微信** | `bus/channels/wechat_work.py` | ✅ | 企业办公 |
| **WhatsApp** | `bus/channels/whatsapp.py` | ✅ | 国际主流 |

### 9.3 渠道消息处理流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant CH as Channel
    participant CM as ChannelManager
    participant Bus as MessageBus
    participant AG as AgentGraph
    participant SM as SessionManager
    
    User->>CH: 发送消息
    CH->>CM: on_message(event)
    CM->>Bus: publish_inbound(msg)
    
    Note over CM: 异步处理循环
    
    Bus->>CM: consume_inbound()
    CM->>SM: get_or_create(session_key)
    SM-->>CM: 返回会话
    CM->>AG: ainvoke_with_history(messages, thread_id)
    AG-->>CM: 返回响应
    CM->>SM: add_message(response)
    CM->>Bus: publish_outbound(response)
    
    Bus->>CM: consume_outbound()
    CM->>CH: send_message(chat_id, content)
    CH->>User: 发送响应
```

---

## 10. 配置系统

### 10.1 配置架构

```mermaid
graph TB
    subgraph "配置文件"
        CF[config.json]
    end
    
    subgraph "配置模块 (config/)"
        SCHEMA[schema.py<br/>Pydantic 模型]
        LOADER[loader.py<br/>配置加载器]
        PATHS[paths.py<br/>路径管理]
    end
    
    subgraph "配置对象"
        AC[AppConfig]
        LLM[LLMConfig]
        CH[ChannelsConfig]
    end
    
    CF --> LOADER
    LOADER --> SCHEMA
    SCHEMA --> AC
    AC --> LLM
    AC --> CH
    
    style CF fill:#e3f2fd
    style SCHEMA fill:#fff3e0
```

### 10.2 配置结构

```python
class AppConfig:
    version: str                    # 版本号
    llm: LLMConfig                  # LLM 配置
    channels: ChannelsConfig        # 渠道配置
    workspace: str                  # 工作空间路径
    log_level: str                  # 日志级别

class LLMConfig:
    provider: str                   # 提供商名称
    model: str                      # 模型名称
    api_key: str                    # API Key
    base_url: Optional[str]         # API Base URL
    temperature: float              # 温度
    max_tokens: int                 # 最大 tokens

class ChannelsConfig:
    feishu: Optional[FeishuConfig]
    telegram: Optional[TelegramConfig]
    qq: Optional[QQConfig]
    # ... 其他渠道
```


### 10.3 配置加载流程

```python
from config import load_config

# 加载配置（自动从 config.json 读取）
config = load_config()

# 访问配置
print(config.llm.provider)      # "siliconflow"
print(config.llm.model)          # "Qwen/Qwen2.5-7B-Instruct"
print(config.channels.keys())    # ["telegram", "feishu"]
```

---

## 11. 完整数据流

### 11.1 用户消息处理完整流程

```mermaid
sequenceDiagram
    participant User as 👤 用户
    participant CH as 📱 渠道<br/>(Telegram)
    participant CM as 🔀 ChannelManager
    participant Bus as 📬 MessageBus
    participant SM as 💾 SessionManager
    participant AG as 🤖 AgentGraph
    participant RAG as 📚 RAG节点
    participant Router as 🧭 Router节点
    participant LLM as 🧠 LLM节点
    participant Tools as 🔧 Tools节点
    
    User->>CH: 1. 发送消息
    CH->>CM: 2. on_message(event)
    CM->>Bus: 3. publish_inbound(msg)
    
    Note over Bus,AG: === 异步处理 ===
    
    Bus->>CM: 4. consume_inbound()
    CM->>SM: 5. get_or_create(session_key)
    SM-->>CM: 6. 返回会话（含历史）
    
    CM->>AG: 7. ainvoke_with_history(messages)
    
    Note over AG: === Agent 执行流程 ===
    
    AG->>RAG: 8. 检索知识库
    RAG-->>AG: 9. 返回上下文
    
    AG->>Router: 10. 选择模型
    Router-->>AG: 11. 返回模型实例
    
    AG->>LLM: 12. 调用模型推理
    LLM-->>AG: 13. 返回响应（含工具调用）
    
    alt 需要工具
        AG->>Tools: 14. 执行工具
        Tools-->>AG: 15. 返回结果
        AG->>LLM: 16. 继续推理
        LLM-->>AG: 17. 返回最终响应
    end
    
    AG-->>CM: 18. 返回响应
    
    CM->>SM: 19. add_message(response)
    CM->>Bus: 20. publish_outbound(response)
    
    Bus->>CM: 21. consume_outbound()
    CM->>CH: 22. send_message(chat_id, content)
    CH->>User: 23. 发送响应
```

### 11.2 关键路径分析

| 阶段 | 步骤 | 耗时估计 | 优化点 |
|------|------|---------|--------|
| **消息接收** | 1-3 | <10ms | 渠道 SDK 性能 |
| **会话加载** | 4-6 | 10-50ms | JSONL 读取优化 |
| **RAG 检索** | 8-9 | 50-200ms | 向量索引优化 |
| **模型路由** | 10-11 | <5ms | 规则匹配 |
| **LLM 推理** | 12-13 | 1-5s | 模型选择、流式输出 |
| **工具执行** | 14-17 | 100ms-10s | 工具性能、并发 |
| **响应发送** | 18-23 | 10-100ms | 网络延迟 |

**总耗时**：1.5s - 15s（取决于是否使用工具）

---

## 12. 核心设计模式

### 12.1 状态图模式（StateGraph）

**优势**：
- 清晰的节点和边定义
- 支持条件路由
- 内置状态持久化
- 易于调试和可视化

**实现**：
```python
workflow = StateGraph(AgentState)
workflow.add_node("rag", rag_node)
workflow.add_node("router", router_node)
workflow.add_node("llm", llm_node)
workflow.add_node("tools", tool_node)
workflow.add_edge(START, "rag")
workflow.add_edge("rag", "router")
workflow.add_conditional_edges("llm", should_continue, {...})
graph = workflow.compile(checkpointer=checkpointer)
```


### 12.2 消息总线模式（Message Bus）

**优势**：
- 解耦渠道和 Agent
- 支持异步处理
- 易于扩展新渠道
- 支持消息持久化

**实现**：
```python
class MessageBus:
    def __init__(self):
        self.inbound = asyncio.Queue()
        self.outbound = asyncio.Queue()
    
    async def publish_inbound(self, msg):
        await self.inbound.put(msg)
    
    async def consume_inbound(self):
        return await self.inbound.get()
```

### 12.3 工具注册表模式（Registry）

**优势**：
- 动态注册工具
- 统一工具接口
- 支持参数验证
- 易于测试和模拟

**实现**：
```python
class ToolRegistry:
    def __init__(self):
        self._tools = {}
    
    def register(self, tool: Tool):
        self._tools[tool.name] = tool
    
    def get_langchain_tools(self):
        return [tool.to_langchain_tool() for tool in self._tools.values()]
```

### 12.4 提供商工厂模式（Factory）

**优势**：
- 统一创建接口
- 支持多提供商
- 配置驱动
- 易于切换

**实现**：
```python
def create_llm(provider: str, model: str, **kwargs):
    spec = get_provider(provider)
    return ChatOpenAI(
        model=model or spec.default_model,
        base_url=spec.default_api_base,
        **kwargs
    )
```

---

## 13. 扩展性分析

### 13.1 扩展点

| 扩展点 | 位置 | 扩展方式 | 难度 |
|-------|------|---------|------|
| **新增 LLM 提供商** | `lanobot/providers/registry.py` | 注册 ProviderSpec | ⭐ |
| **新增工具** | `lanobot/tools/` | 继承 Tool 基类 | ⭐⭐ |
| **新增渠道** | `bus/channels/` | 实现 Channel 接口 | ⭐⭐⭐ |
| **自定义节点** | `lanobot/agent/nodes.py` | 添加节点函数 | ⭐⭐ |
| **自定义路由策略** | `lanobot/agent/router.py` | 实现 router_fn | ⭐⭐ |
| **自定义 RAG** | `lanobot/memory/rag.py` | 实现 RAGRetriever | ⭐⭐⭐ |
| **自定义中间件** | `lanobot/agent/middleware.py` | 使用 LangChain 中间件 | ⭐⭐⭐ |

### 13.2 新增工具示例

```python
# 1. 创建工具类
from lanobot.tools.base import Tool

class WeatherTool(Tool):
    name = "get_weather"
    description = "获取指定城市的天气信息"
    
    schema = {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "城市名称"}
        },
        "required": ["city"]
    }
    
    async def execute(self, city: str) -> str:
        # 实现天气查询逻辑
        return f"{city} 的天气是晴天"

# 2. 注册工具
registry = ToolRegistry()
registry.register(WeatherTool())

# 3. 使用工具
tools = registry.get_langchain_tools()
agent = AgentGraph(model=model, tools=tools)
```

### 13.3 新增渠道示例

```python
# 1. 实现渠道类
from bus.channels.base import Channel

class MyChannel(Channel):
    def __init__(self, config, bus):
        self.config = config
        self.bus = bus
    
    async def start(self):
        # 启动渠道（如 WebSocket 连接）
        pass
    
    async def stop(self):
        # 停止渠道
        pass
    
    async def send_message(self, chat_id, content):
        # 发送消息到渠道
        pass

# 2. 注册渠道
channel_manager.register("my_channel", MyChannel(config, bus))
channel_manager.start_channel("my_channel")
```

---

## 14. 性能优化建议

### 14.1 当前性能瓶颈

| 瓶颈 | 影响 | 优化方案 |
|------|------|---------|
| **LLM 推理延迟** | 1-5s | 使用流式输出、选择快速模型 |
| **RAG 检索** | 50-200ms | 使用向量数据库（FAISS、Milvus） |
| **会话加载** | 10-50ms | 使用缓存、索引优化 |
| **工具执行** | 100ms-10s | 并发执行、超时控制 |
| **消息序列化** | <10ms | 使用 msgpack、protobuf |
