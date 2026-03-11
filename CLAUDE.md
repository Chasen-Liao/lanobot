# CLAUDE.md

本文件为Claude Code（claude.ai/code）在此代码库中工作提供指导。

## 项目概述
使用LangChain 1.2重构nanobot（超轻量级个人AI助手）。原nanobot是一个模块化框架，包含渠道、提供商和核心Agent。并且还要留有后续的开发模块接入。

## 开发环境
- 本项目采用uv来管理python的包
- 使用的是Windows系统，要使用Windows的命令

## 原始nanobot架构
- **agent/**: 核心循环、记忆、技能、工具（文件系统、MCP、Shell、Web等）
- **bus/**: 模块间通信的消息总线
- **channels/**: 外部渠道（Telegram、Slack、钉钉、飞书等）
- **providers/**: AI服务（OpenAI、Azure OpenAI、LiteLLM）
- **session/**: 会话管理
- **cron/**: 定时任务
- **cli/**: 基于Typer的命令行界面

## lanobot架构



## LangChain 1.2集成
重构将替换以下组件：
- Agent循环 → LangChain实现
- 工具 → LangChain工具集成
- 记忆 → LangChain记忆管理
- 提供商 → LangChain LLM接口
- 编写命令行的一键配置脚本，提供可视化的安装部署流程
- 外部渠道保留原始的，但是要和重构后的代码兼容