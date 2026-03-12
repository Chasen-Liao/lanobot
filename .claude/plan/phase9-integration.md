# Phase 9: 服务集成

## 目标

将各个模块集成到一起，实现完整的服务启动流程。

## 9.1 服务启动集成

**方案**：在 CLI run.py 中调用 main.py 的异步启动逻辑

```python
# cli/commands/run.py
import asyncio
from main import main as run_service

@app.command()
def start(...):
    """启动 Lanobot 服务"""
    asyncio.run(run_service())
```

**启动流程**：
1. 加载 config.json
2. 初始化 LLM
3. 创建 AgentGraph
4. 启动消息总线
5. 初始化渠道管理器
6. 启动 Cron 服务
7. 启动 Heartbeat 服务
8. 开始消息处理循环

## 9.2 Cron 服务（定时任务）

**架构**（参考 nanobot）：
```
cron/
├── __init__.py
├── types.py          # CronJob, CronSchedule, CronPayload, CronStore
└── service.py        # CronService 服务实现
```

**核心功能**：
- 支持三种调度类型：every（间隔）、cron（定时）、at（一次性）
- 通过 Agent 工具 `cron` 让用户对话创建
- 任务持久化到 `workspace/cron/jobs.json`
- 支持 enable/disable/remove 操作

**Agent 工具接口**：
```python
@tool
async def cron(
    action: str,          # "add" | "list" | "remove"
    message: str,         # 提醒消息
    every_seconds: int,   # 间隔秒数
    cron_expr: str,       # cron 表达式
    tz: str,              # 时区
    at: str,              # 一次性执行时间
    job_id: str,          # 删除任务用
) -> str
```

**使用示例**：
- "每天早上9点叫我起床" → cron add, cron_expr="0 9 * * *"
- "每30分钟检查一次" → cron add, every_seconds=1800

## 9.3 Heartbeat 服务（心跳）

**架构**（参考 nanobot）：
```
heartbeat/
├── __init__.py
└── service.py        # HeartbeatService
```

**核心功能**：
- 定期检查 `workspace/HEARTBEAT.md` 文件
- 调用 LLM 决定是否需要执行任务
- 发现任务时通过 Agent 执行
- 默认间隔 30 分钟

**配置**：
```json
{
  "heartbeat": {
    "enabled": true,
    "interval_s": 1800
  }
}
```

## 实现顺序

1. **服务启动集成** - 将 main.py 逻辑接入 CLI
2. **Cron 服务** - 实现 cron/types.py + service.py
3. **Heartbeat 服务** - 实现 heartbeat/service.py
4. **Agent 工具集成** - 在 tools/ 中添加 cron 工具（复用现有 tools/cron.py）

## 依赖

```
croniter>=3.0  # cron 表达式解析
```