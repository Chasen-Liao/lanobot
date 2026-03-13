"""Lanobot - 超轻量级个人AI助手"""
import asyncio
import signal
import sys
from pathlib import Path
from typing import Any, Literal, Optional

# 强制 stdout 不缓冲，确保日志立即输出
sys.stdout.reconfigure(line_buffering=True)

# 初始化基础日志（在导入任何可能使用日志的模块之前）
from loguru import logger as _logger
_logger.remove()
_logger.add(sys.stderr, level="WARNING", format="{level}: {message}", colorize=True)


def setup_logging(workspace: Path) -> None:
    """配置完整日志系统 - 写入文件，终端只显示关键信息"""
    from loguru import logger

    log_dir = workspace / "logs"
    log_dir.mkdir(exist_ok=True)

    # 清理默认 handler
    logger.remove()

    # 文件日志 - 完整记录
    log_file = log_dir / "lanobot.log"
    logger.add(
        log_file,
        rotation="10 MB",  # 10MB 轮转
        retention="7 days",  # 保留 7 天
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        encoding="utf-8",
    )

    # 终端日志 - 只显示重要信息
    logger.add(
        sys.stderr,
        level="WARNING",
        format="<level>{level}</level>: {message}",
        colorize=True,
    )


# 全局日志实例
from loguru import logger

# Windows 上需要设置正确的事件循环策略以支持信号处理
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 延迟导入 config（避免在日志初始化前执行）
from bus.queue import MessageBus
from bus.events import OutboundMessage
from lanobot.providers import create_llm
from lanobot.agent.graph import AgentGraph
from session import SessionManager, create_session_manager
from cron.service import CronService
from heartbeat.service import HeartbeatService


def load_soul_and_user_memory(workspace: Path) -> tuple[str, str]:
    """加载灵魂(SOUL)和用户(USER)记忆文件

    Args:
        workspace: 工作空间目录

    Returns:
        (soul_content, user_content) 元组
    """
    templates_dir = Path(__file__).parent / "lanobot" / "templates"

    # 加载 SOUL.md（Agent 的人格/灵魂）
    soul_path = templates_dir / "SOUL.md"
    soul_content = ""
    if soul_path.exists():
        try:
            soul_content = soul_path.read_text(encoding="utf-8").strip()
            logger.info(f"已加载 SOUL: {soul_path}")
        except Exception as e:
            logger.warning(f"加载 SOUL 失败: {e}")

    # 加载 USER.md（用户信息）
    user_path = workspace / "USER.md"
    user_content = ""
    if user_path.exists():
        try:
            user_content = user_path.read_text(encoding="utf-8").strip()
            logger.info(f"已加载 USER: {user_path}")
        except Exception as e:
            logger.warning(f"加载 USER 失败: {e}")
    else:
        # 尝试从 templates 加载默认模板
        default_user_path = templates_dir / "USER.md"
        if default_user_path.exists():
            try:
                user_content = default_user_path.read_text(encoding="utf-8").strip()
                logger.info(f"已加载 USER 模板: {default_user_path}")
            except Exception as e:
                logger.warning(f"加载 USER 模板失败: {e}")

    return soul_content, user_content


def build_system_prompt(soul: str, user: str) -> str:
    """构建系统提示词

    Args:
        soul: SOUL 内容（Agent 的人格）
        user: USER 内容（用户信息）

    Returns:
        完整的系统提示词
    """
    parts = []

    if soul:
        parts.append(f"""# Soul（灵魂）
{soul}""")

    if user:
        parts.append(f"""# User Profile（用户信息）
{user}""")

    if parts:
        return "\n\n".join(parts)
    return ""  # 返回空字符串而非 None，方便后续处理


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
        # 延迟导入 config，避免在导入时执行日志
        from config import load_config
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
        # 创建工作空间目录
        self.workspace = Path.cwd() / "workspace"
        self.workspace.mkdir(exist_ok=True)

        # 配置日志系统
        setup_logging(self.workspace)

        mode_desc = {
            "agent": "Agent 核心",
            "gateway": "渠道网关",
            "all": "完整服务",
        }
        logger.info(f"Lanobot v{self.config.version} 启动中... ({mode_desc[self.mode]})")
        logger.info(f"工作空间: {self.workspace}")

        # 创建会话管理器
        self.session_manager = create_session_manager(
            workspace=self.workspace,
            compression_threshold=100_000,  # 10万 tokens 触发压缩
            expire_days=30,  # 30 天过期
        )

        # 启动时清理过期会话
        deleted = self.session_manager.cleanup_expired()
        if deleted:
            logger.info(f"清理了 {deleted} 个过期会话")

        # Agent 模式需要 LLM 和 AgentGraph
        if self.mode in ("agent", "all"):
            await self._setup_agent()
            logger.info("Agent 已初始化")

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

        # 加载 SOUL 和 USER 记忆
        soul, user = load_soul_and_user_memory(self.workspace)
        system_prompt = build_system_prompt(soul, user)

        if system_prompt:
            logger.info(f"系统提示词已构建 ({len(system_prompt)} 字符)")

        # 创建工具注册表
        from lanobot.tools import create_tool_registry
        registry = create_tool_registry(
            workspace=str(self.workspace),
            include_filesystem=True,
            include_shell=True,
            include_web=False,
            include_message=True,
            include_cron=False,
        )
        tools = registry.get_langchain_tools()
        logger.info(f"已加载 {len(tools)} 个工具")

        # 创建 RAG 节点（知识库检索）
        from lanobot.memory.rag import create_rag_node
        knowledge_dir = self.workspace / "knowledge"
        if knowledge_dir.exists() and any(knowledge_dir.iterdir()):
            rag_node = create_rag_node(knowledge_dir=knowledge_dir, k=3)
            logger.info(f"已加载知识库: {knowledge_dir}")
        else:
            rag_node = None

        # 创建 AgentGraph（不启用 checkpointer 以避免序列化问题）
        self.agent = AgentGraph(
            model=model,
            tools=tools,
            rag_node=rag_node,
            checkpointer=None,  # CLI 模式不需要状态持久化
            system_prompt=system_prompt if system_prompt else None,
        )

        logger.info(f"已初始化 LLM: {self.config.llm.provider}/{self.config.llm.model}")

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

        logger.info(f"已启动渠道: {', '.join(self.config.channels.keys()) if self.config.channels else '无'}")

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
        logger.info(f"Lanobot ({self.mode}) 已启动，按 Ctrl+C 停止")

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
                logger.info(f"已保存 {count} 个会话")


def _safe_print(text: str) -> None:
    """安全地打印文本，处理 Unicode 问题"""
    if not text:
        return

    # 移除 Unicode 代理字符（Windows 终端不支持）
    safe_chars = []
    for char in text:
        code_point = ord(char)
        # 跳过代理区字符 (0xD800-0xDFFF)
        if 0xD800 <= code_point <= 0xDFFF:
            continue
        safe_chars.append(char)
    safe_text = "".join(safe_chars)

    # 尝试处理其他无法编码的字符
    try:
        print(safe_text)
    except UnicodeEncodeError:
        # 最后的 fallback：移除所有非ASCII字符
        safe_text = safe_text.encode("ascii", errors="ignore").decode("ascii")
        print(safe_text)


def _clean_message(message) -> str:
    """清理消息内容中的无效字符"""
    # 获取消息内容字符串
    if hasattr(message, "content"):
        content = str(message.content)
    else:
        content = str(message)

    # 移除无效的 Unicode 代理字符
    safe_chars = []
    for char in content:
        code_point = ord(char)
        # 跳过代理区 (0xD800-0xDFFF)
        if 0xD800 <= code_point <= 0xDFFF:
            continue
        safe_chars.append(char)
    return "".join(safe_chars)


async def run_agent() -> None:
    """运行 Agent 核心（不含渠道）"""
    from lanobot.cli.repl import InteractiveREPL

    app = Lanobot(mode="agent")
    await app.setup()

    if not app.agent:
        print("[错误] Agent 未正确初始化")
        return

    # 使用新的美化 REPL
    repl = InteractiveREPL(
        agent=app.agent,
        session_manager=app.session_manager,
        config=app.config,
    )

    try:
        await repl.run()
    finally:
        # 清理
        await app.stop()


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
    # 设置信号处理，让信号触发时直接停止应用
    def shutdown(sig: int, frame: Any) -> None:
        logger.info("正在停止...")
        # 停止 app.start() 中的主循环
        app._running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # 启动应用
    await app.start()

    # 优雅停止 - 仍然调用 stop 清理资源
    await app.stop()
    logger.info("Lanobot 已停止")


# 兼容旧接口
async def main() -> None:
    """默认启动（全部功能）"""
    await run_all()


if __name__ == "__main__":
    asyncio.run(main())