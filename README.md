# Lanobot

超轻量级个人 AI 助手，基于 LangChain 1.2 开发。

## 项目状态

**基础开发已完成** - 所有 Phase 开发完成

**下一阶段** -- 修复BUG

## 功能特性

- 🤖 **LLM 集成** - 支持 19+ 种 LLM 提供商（SiliconFlow、DeepSeek、OpenAI、Anthropic 等）
- 💬 **多渠道支持** - 飞书、QQ、Telegram、Slack、Discord、钉钉、企业微信、WhatsApp
- 🔌 **MCP 支持** - Model Context Protocol 扩展
- 📡 **消息总线** - 异步消息队列架构
- ⏰ **定时任务** - Cron 定时提醒和任务
- 💓 **心跳服务** - 自动执行周期性任务
- 💾 **会话管理** - 持久化存储、自动摘要、过期清理
- 🧠 **记忆系统** - 短期记忆（Checkpointer）+ 长期记忆（Store）

## 技术栈

- **LangChain 1.2** - Agent 框架
- **LangGraph** - 状态流和持久化
- **Pydantic V2** - 配置管理
- **Python 3.11+** - 运行环境

## 快速开始

```bash
# 克隆项目
cd lanobot

# 安装依赖
uv sync

# 初始化配置
uv run lanobot init

# 启动服务（选择一种模式）

# 模式1：仅 Agent 核心（不含渠道）
uv run lanobot run agent

# 模式2：渠道网关（需配合 agent 模式）
uv run lanobot run gateway

# 模式3：完整服务
uv run lanobot run start
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `lanobot init` | 初始化项目 |
| `lanobot run agent` | 启动 Agent 核心 |
| `lanobot run gateway` | 启动渠道网关 |
| `lanobot run start` | 启动完整服务 |
| `lanobot config show` | 显示配置 |
| `lanobot config set` | 设置配置 |
| `lanobot channel list` | 列出渠道 |
| `lanobot session list` | 列出会话 |
| `lanobot doctor check` | 系统检查 |

## 项目结构

```
lanobot/
├── main.py              # 入口点
├── config.json          # 配置文件
├── pyproject.toml       # 项目配置
├── config/              # 配置层
├── bus/                 # 消息总线 + 渠道
│   └── channels/        # 8个渠道实现
├── lanobot/             # Agent 核心
│   ├── agent/           # StateGraph、RAG、路由
│   ├── tools/           # 7个工具
│   ├── memory/          # 记忆系统
│   └── providers/       # 19+ 个 LLM 提供商
├── session/             # 会话管理
├── cron/                # 定时任务服务
├── heartbeat/           # 心跳服务
├── cli/                 # CLI 命令
├── templates/           # 系统提示词模板
├── workspace/           # 工作空间
└── tests/               # 测试
```

## 开发计划

详见 [plan/构建计划.md](./plan/构建计划.md)

## 许可证

MIT