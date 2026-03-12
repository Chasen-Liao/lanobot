"""Lanobot - 超轻量级个人AI助手"""
import asyncio
import signal
from pathlib import Path
from typing import Any, Literal, Optional

from config import load_config
from bus.queue import MessageBus
from bus.events import OutboundMessage
from lanobot.providers import create_llm
from lanobot.agent.graph import AgentGraph
from session import SessionManager, create_session_manager
from cron.service import CronService
from heartbeat.service import HeartbeatService


# 延迟导入 ChannelManager（仅在 gateway/all 模式需要）
def _get_channel_manager(config_channels, bus, agent, session_manager):
    from bus.channels import ChannelManager

    return ChannelManager(
        config=config_channels,
        bus=bus,
        agent=agent,
        session_manager=session_manager,
    )


class Lanobot:
    """Lanobot 应用主类"""

    def __init__(self, mode: Literal["agent", "gateway", "all"] = "all"):
        """
        初始化 Lanobot

        Args:
            mode: 运行模式
                - "agent": 仅运行 Agent 核心（不启动渠道）
                - "gateway": 仅运行渠道网关
                - "all": 运行全部（默认）
        """
        self.config = load_config()
        self.mode = mode
        self.bus = MessageBus()
        self.channel_manager: Optional[ChannelManager] = None
        self.agent: Optional[AgentGraph] = None
        self.session_manager: Optional[SessionManager] = None
        self.cron_service: Optional[CronService] = None
        self.heartbeat_service: Optional[HeartbeatService] = None
        self.workspace: Optional[Path] = None
        self._running = False

    async def setup(self) -> None:
        """初始化组件"""
        mode_desc = {
            "agent": "Agent 核心",
            "gateway": "渠道网关",
            "all": "完整服务",
        }
        print(f"Lanobot v{self.config.version} 启动中... ({mode_desc[self.mode]})")

        # 创建工作空间目录
        self.workspace = Path.cwd() / "workspace"
        self.workspace.mkdir(exist_ok=True)
        print("[Setup] 工作空间已创建")

        # 创建会话管理器
        self.session_manager = create_session_manager(
            workspace=self.workspace,
            compression_threshold=100_000,  # 10万 tokens 触发压缩
            expire_days=30,  # 30 天过期
        )
        print("[Setup] 会话管理器已创建")

        # 启动时清理过期会话
        deleted = self.session_manager.cleanup_expired()
        if deleted:
            print(f"[Session] 清理了 {deleted} 个过期会话")

        # Agent 模式需要 LLM 和 AgentGraph
        if self.mode in ("agent", "all"):
            print("[Setup] 初始化 Agent...")
            await self._setup_agent()
            print("[Setup] Agent 已初始化")

        # Gateway 模式需要渠道
        if self.mode in ("gateway", "all"):
            await self._setup_gateway()

        # 启动 Cron 服务（所有模式都需要定时任务）
        await self._setup_cron()

        # 启动 Heartbeat 服务
        await self._setup_heartbeat()

    async def _setup_agent(self) -> None:
        """设置 Agent 核心"""
        # 创建 LLM
        model = create_llm(
            provider=self.config.llm.provider,
            model=self.config.llm.model,
            api_key=self.config.llm.api_key,
            base_url=self.config.llm.base_url,
        )

        # 创建 AgentGraph
        self.agent = AgentGraph(
            model=model,
            checkpointer_backend="memory",
        )

        print(f"已初始化 LLM: {self.config.llm.provider}/{self.config.llm.model}")

    async def _setup_gateway(self) -> None:
        """设置渠道网关"""
        # 创建渠道管理器（需要 Agent 来处理消息） - 延迟导入
        from bus.channels import ChannelManager
        self.channel_manager = ChannelManager(
            config=self.config.channels,
            bus=self.bus,
            agent=self.agent,
            session_manager=self.session_manager,
        )

        print(f"已启动渠道: {', '.join(self.config.channels.keys()) if self.config.channels else '无'}")

    async def _setup_cron(self) -> None:
        """设置 Cron 服务"""
        cron_store_path = self.workspace / "cron" / "jobs.json"

        async def on_cron_job(job):
            """Cron job 回调：发送消息到渠道"""
            if job.channel and job.to:
                msg = OutboundMessage(
                    channel=job.channel,
                    chat_id=job.to,
                    content=job.message,
                )
                await self.bus.publish_outbound(msg)

        self.cron_service = CronService(
            store_path=cron_store_path,
            on_job=on_cron_job,
        )
        await self.cron_service.start()

    async def _setup_heartbeat(self) -> None:
        """设置 Heartbeat 服务"""
        self.heartbeat_service = HeartbeatService(
            workspace=self.workspace,
            provider=self.config.llm.provider,
            model=self.config.llm.model,
            api_key=self.config.llm.api_key,
            base_url=self.config.llm.base_url,
            on_execute=self._on_heartbeat_execute,
            interval_s=1800,  # 30 分钟
        )
        await self.heartbeat_service.start()

    async def start(self) -> None:
        """启动应用"""
        await self.setup()

        # 如果是 Gateway 或 All 模式，启动渠道
        if self.mode in ("gateway", "all") and self.channel_manager:
            await self.channel_manager.start_all()

        self._running = True
        print(f"Lanobot ({self.mode}) 已启动，按 Ctrl+C 停止")

        # 保持运行
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    async def _on_heartbeat_execute(self, task: dict[str, Any]) -> None:
        """Heartbeat task 回调处理"""
        task_name = task.get("name", "unnamed")
        task_description = task.get("description", "")

        if self.config.channels:
            msg = OutboundMessage(
                channel="admin",
                chat_id="system",
                content=f"🔔 Heartbeat 任务执行: {task_name}\n\n{task_description}",
            )
            await self.bus.publish_outbound(msg)

    async def stop(self) -> None:
        """停止应用"""
        self._running = False

        # 停止渠道
        if self.channel_manager:
            await self.channel_manager.stop_all()

        # 停止 Cron 服务
        if self.cron_service:
            await self.cron_service.stop()

        # 停止 Heartbeat 服务
        if self.heartbeat_service:
            await self.heartbeat_service.stop()

        # 保存所有会话
        if self.session_manager:
            count = self.session_manager.flush()
            if count > 0:
                print(f"已保存 {count} 个会话")

        print("Lanobot 已停止")


async def run_agent() -> None:
    """运行 Agent 核心（不含渠道）"""
    app = Lanobot(mode="agent")
    await run_app(app)


async def run_gateway() -> None:
    """运行渠道网关（需要配合 agent 模式使用）"""
    app = Lanobot(mode="gateway")
    await run_app(app)


async def run_all() -> None:
    """运行完整服务"""
    app = Lanobot(mode="all")
    await run_app(app)


async def run_app(app: Lanobot) -> None:
    """通用运行函数"""
    # 设置信号处理
    def shutdown(sig: int, frame: Any) -> None:
        print("\n正在停止...")
        asyncio.create_task(app.stop())
        loop = asyncio.get_event_loop()
        loop.call_later(1, loop.stop)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    await app.start()


# 兼容旧接口
async def main() -> None:
    """默认启动（全部功能）"""
    await run_all()


if __name__ == "__main__":
    asyncio.run(main())