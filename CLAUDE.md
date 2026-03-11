# CLAUDE.md

本文件为Claude Code（claude.ai/code）在此代码库中工作提供指导。

## 项目概述

Lanobot，使用 LangChain 1.2 构建的超轻量级个人AI助手。一定要参考nanobot的源码，一定要使用Langchain 1.2

## 构建计划

详细构建计划请参考：`plan/构建计划.md`

## 已有 Skills（构建时参考）

### nanobot 项目中的 skills
- `nanobot/nanobot/skills/weather/` - 天气技能
- `nanobot/nanobot/skills/summarize/` - 摘要技能
- `nanobot/nanobot/skills/github/` - GitHub 技能
- `nanobot/nanobot/skills/memory/` - 记忆技能
- `nanobot/nanobot/skills/cron/` - 定时任务技能
- `nanobot/nanobot/skills/skill-creator/` - 技能创建器
- `nanobot/nanobot/skills/clawhub/` - Clawhub 技能

### LangChain 开发相关 Skills

构建时根据需要使用以下 Claude Code Skills：

| Skill | 用途 |
|-------|------|
| `framework-selection` | 框架选择决策（必用） |
| `langchain-dependencies` | 项目依赖配置、版本管理 |
| `langchain-fundamentals` | `create_agent()`、工具定义、中间件基础 |
| `langchain-middleware` | HumanInTheLoopMiddleware、自定义中间件 |
| `langchain-rag` | RAG 流水线、文档加载、向量存储 |
| `langchain-architecture` | Agent 架构设计模式 |
| `langgraph-fundamentals` | StateGraph、节点、边、Command |
| `langgraph-human-in-the-loop` | interrupt()、人机协作审批 |
| `langgraph-persistence` | checkpointer、thread_id、时间旅行 |
| `mcp-builder` | MCP Server 创建指南 |

**重要**：涉及到Langchain的API时，使用`docs-langchain`MCP查询 LangChain 官方文档获取最新 API。

## 构建时可用 Agents

根据任务使用以下 Claude Code Agents 提高效率：

| Agent | 用途 |
|-------|------|
| `python-reviewer` | Python 代码审查（PEP 8、类型提示、安全） |
| `build-error-resolver` | 构建和类型错误解决 |
| `tdd-guide` | 测试驱动开发（TDD）指导 |
| `doc-updater` | 文档和 codemap 更新 |
| `code-reviewer` | 通用代码审查（质量、安全、可维护性） |
| `security-reviewer` | 安全漏洞检测 |

**使用示例**：
- 写完代码后 → 调用 `python-reviewer` 审查
- 构建失败时 → 调用 `build-error-resolver` 修复
- 新功能开发 → 调用 `tdd-guide` 先写测试
- E2E 测试 → 调用 `e2e-runner` 生成测试用例