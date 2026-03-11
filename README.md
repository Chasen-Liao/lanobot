# Lanobot

超轻量级个人 AI 助手，基于 LangChain 开发。

## 项目状态

🛠️ **开发中** - Phase 1 基础架构搭建完成

## 功能特性

- 🤖 **LLM 集成** - 支持多种 LLM 提供商（OpenAI、Anthropic、SiliconFlow 等）
- 💬 **多通道支持** - QQ、飞书等聊天平台
- 🔌 **MCP 支持** - Model Context Protocol 扩展
- 📡 **消息总线** - 异步消息队列架构

## 技术栈

- **LangChain** - Agent 框架
- **LangGraph** - 状态流和持久化
- **Pydantic** - 配置管理
- **Python 3.11+** - 运行环境

## 快速开始

```bash
# 安装依赖
uv venv && uv pip install -e ".[dev]"

# 运行
uv run python main.py

# 测试
uv run pytest tests/
```

## 项目结构

```
lanobot/
├── config/          # 配置模块
│   ├── schema.py    # Pydantic 配置模型
│   ├── loader.py    # 配置加载器
│   └── paths.py     # 路径工具
├── bus/             # 消息总线
│   ├── queue.py     # MessageBus 实现
│   ├── events.py    # 消息事件定义
│   └── channels/    # 通道实现
│       ├── base.py  # 通道基类
│       ├── qq.py    # QQ 通道
│       └── feishu.py # 飞书通道
└── tests/           # 测试
```

## 开发计划

详见 [plan/构建计划.md](./plan/构建计划.md)

## 许可证

MIT