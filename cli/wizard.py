"""
交互式配置向导
"""
import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

console = Console()

# 支持的渠道
CHANNELS = [
    {"id": "feishu", "name": "飞书"},
    {"id": "telegram", "name": "Telegram"},
    {"id": "slack", "name": "Slack"},
    {"id": "discord", "name": "Discord"},
    {"id": "dingtalk", "name": "钉钉"},
    {"id": "wecom", "name": "企业微信"},
    {"id": "whatsapp", "name": "WhatsApp"},
    {"id": "qq", "name": "QQ"},
]

# LLM 提供商
LLM_PROVIDERS = [
    {"id": "siliconflow", "name": "SiliconFlow", "model": "Pro/deepseek-ai/DeepSeek-V3.2", "base_url": "https://api.siliconflow.cn/v1"},
    {"id": "deepseek", "name": "DeepSeek", "model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1"},
    {"id": "openai", "name": "OpenAI", "model": "gpt-4o-mini", "base_url": "https://api.openai.com/v1"},
    {"id": "anthropic", "name": "Anthropic", "model": "claude-3-haiku-20240307", "base_url": "https://api.anthropic.com"},
    {"id": "ollama", "name": "Ollama (本地部署)", "model": "llama3", "base_url": "http://localhost:11434/v1"},
]


class ConfigWizard:
    """交互式配置向导"""

    def __init__(self):
        self.config = self._load_existing_config()

    def _load_existing_config(self) -> dict:
        """加载现有配置"""
        config_path = Path("config.json")
        if config_path.exists():
            try:
                return json.loads(config_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return self._default_config()

    def _default_config(self) -> dict:
        """默认配置"""
        return {
            "llm": {
                "provider": "siliconflow",
                "model": "Pro/deepseek-ai/DeepSeek-V3.2",
                "api_key": "",
                "base_url": "https://api.siliconflow.cn/v1",
                "temperature": 0.7,
                "max_tokens": 4096,
            },
            "channels": [],
            "templates_dir": "./lanobot/templates",
            "workspace": "./workspace",
            "mcp_servers": [],
            "skills_dir": "./skills",
            "logging": {"level": "INFO"},
        }

    def run(self):
        """运行配置向导"""
        console.print(Panel.fit(
            "🟠 [orange1]Lanobot 配置向导[/orange1] 🟠",
            border_style="orange1",
        ))
        console.print()

        # 第一步：选择模型提供商
        self._step_select_provider()

        # 第二步：输入 API Key
        self._step_api_key()

        # 第三步：选择渠道
        self._step_select_channels()

        # 第四步：配置选中的渠道
        self._step_configure_channels()

        # 保存配置
        self._save_config()

        console.print(Panel.fit(
            "[success]✓ 配置完成！[/success]",
            border_style="green",
        ))
        console.print("\n[info]运行 [cyan]lanobot run[/] 启动服务[/info]")

    def _step_select_provider(self):
        """第一步：选择模型提供商"""
        console.print("[1/4] [orange1]选择模型提供商[/orange1]")
        console.print("━" * 40)

        for i, provider in enumerate(LLM_PROVIDERS, 1):
            recommended = " [gold3](推荐)[/gold3]" if i == 1 else ""
            console.print(f"  [{i}] {provider['name']}{recommended}")

        console.print()

        while True:
            try:
                choice = Prompt.ask(
                    "请选择",
                    choices=[str(i) for i in range(1, len(LLM_PROVIDERS) + 1)],
                    default="1",
                )
                idx = int(choice) - 1
                self.selected_provider = LLM_PROVIDERS[idx]
                break
            except (ValueError, KeyError):
                console.print("[error]请输入有效的选项[/error]")

        # 更新配置
        self.config["llm"]["provider"] = self.selected_provider["id"]
        self.config["llm"]["model"] = self.selected_provider["model"]
        self.config["llm"]["base_url"] = self.selected_provider["base_url"]

        console.print(f"[success]✓[/success] 已选择: {self.selected_provider['name']}\n")

    def _step_api_key(self):
        """第二步：输入 API Key"""
        console.print("[2/4] [orange1]输入 API Key[/orange1]")
        console.print("━" * 40)

        while True:
            api_key = Prompt.ask(
                f"请输入 {self.selected_provider['name']} 的 API Key",
                password=True,
            )
            if api_key.strip():
                break
            console.print("[error]API Key 不能为空[/error]")

        self.config["llm"]["api_key"] = api_key.strip()
        console.print(f"[success]✓[/success] API Key 已设置\n")

    def _step_select_channels(self):
        """第三步：选择渠道"""
        console.print("[3/4] [orange1]选择启用渠道[/orange1]")
        console.print("━" * 40)

        console.print("可选渠道:")
        for i, ch in enumerate(CHANNELS, 1):
            console.print(f"  [{i}] {ch['name']}")

        console.print()

        while True:
            choice = Prompt.ask(
                "请选择渠道编号（用逗号分隔，如 1,3,5）",
                default="",
            )

            if not choice.strip():
                self.selected_channels = []
                break

            try:
                indices = [int(x.strip()) for x in choice.split(",")]
                self.selected_channels = [CHANNELS[i - 1] for i in indices if 1 <= i <= len(CHANNELS)]
                break
            except (ValueError, IndexError):
                console.print("[error]请输入有效的渠道编号[/error]")

        # 更新配置
        self.config["channels"] = [ch["id"] for ch in self.selected_channels]

        if self.selected_channels:
            channel_names = ", ".join([ch["name"] for ch in self.selected_channels])
            console.print(f"[success]✓[/success] 已选择: {channel_names}\n")
        else:
            console.print(f"[warning]未选择任何渠道[/warning]\n")

    def _step_configure_channels(self):
        """第四步：配置选中的渠道"""
        if not self.selected_channels:
            return

        console.print("[4/4] [orange1]配置渠道参数[/orange1]")
        console.print("━" * 40)

        for channel in self.selected_channels:
            console.print(f"\n[{channel['name']} 配置]")
            self._configure_single_channel(channel)

    def _configure_single_channel(self, channel: dict):
        """配置单个渠道"""
        channel_id = channel["id"]

        if channel_id == "feishu":
            self._configure_feishu()
        elif channel_id == "telegram":
            self._configure_telegram()
        elif channel_id == "slack":
            self._configure_slack()
        elif channel_id == "discord":
            self._configure_discord()
        elif channel_id == "dingtalk":
            self._configure_dingtalk()
        elif channel_id == "wecom":
            self._configure_wecom()
        elif channel_id == "whatsapp":
            self._configure_whatsapp()
        elif channel_id == "qq":
            self._configure_qq()

    def _ask_field(self, field_name: str, prompt_text: str, required: bool = True, default: str = "") -> str:
        """询问字段值"""
        while True:
            value = Prompt.ask(
                prompt_text,
                default=default,
            )
            if required and not value.strip():
                console.print(f"[error]{field_name} 不能为空[/error]")
                continue
            return value.strip() if value else default

    def _configure_feishu(self):
        """配置飞书"""
        app_id = self._ask_field("App ID", "请输入 App ID")
        app_secret = self._ask_field("App Secret", "请输入 App Secret", default="")

        self.config["feishu_app_id"] = app_id
        self.config["feishu_app_secret"] = app_secret
        console.print("[success]✓ 飞书配置完成[/success]")

    def _configure_telegram(self):
        """配置 Telegram"""
        bot_token = self._ask_field("Bot Token", "请输入 Bot Token")
        self.config["telegram_bot_token"] = bot_token
        console.print("[success]✓ Telegram 配置完成[/success]")

    def _configure_slack(self):
        """配置 Slack"""
        bot_token = self._ask_field("Bot Token", "请输入 Bot Token (xoxb-...)")
        signing_secret = self._ask_field("Signing Secret", "请输入 Signing Secret")

        self.config["slack_bot_token"] = bot_token
        self.config["slack_signing_secret"] = signing_secret
        console.print("[success]✓ Slack 配置完成[/success]")

    def _configure_discord(self):
        """配置 Discord"""
        bot_token = self._ask_field("Bot Token", "请输入 Bot Token")
        self.config["discord_bot_token"] = bot_token
        console.print("[success]✓ Discord 配置完成[/success]")

    def _configure_dingtalk(self):
        """配置钉钉"""
        app_key = self._ask_field("App Key", "请输入 App Key")
        app_secret = self._ask_field("App Secret", "请输入 App Secret")

        self.config["dingtalk_app_key"] = app_key
        self.config["dingtalk_app_secret"] = app_secret
        console.print("[success]✓ 钉钉配置完成[/success]")

    def _configure_wecom(self):
        """配置企业微信"""
        corp_id = self._ask_field("Corp ID", "请输入 Corp ID")
        corp_secret = self._ask_field("Corp Secret", "请输入 Corp Secret")
        agent_id = self._ask_field("Agent ID", "请输入 Agent ID")

        self.config["wecom_corp_id"] = corp_id
        self.config["wecom_corp_secret"] = corp_secret
        self.config["wecom_agent_id"] = agent_id
        console.print("[success]✓ 企业微信配置完成[/success]")

    def _configure_whatsapp(self):
        """配置 WhatsApp"""
        webhook_url = self._ask_field("Webhook URL", "请输入 Webhook URL")
        verify_token = self._ask_field("Verify Token", "请输入 Verify Token", required=False)

        self.config["whatsapp_webhook_url"] = webhook_url
        self.config["whatsapp_verify_token"] = verify_token
        console.print("[success]✓ WhatsApp 配置完成[/success]")

    def _configure_qq(self):
        """配置 QQ"""
        app_id = self._ask_field("App ID", "请输入 App ID")
        secret = self._ask_field("Secret", "请输入 Secret")

        self.config["qq_app_id"] = app_id
        self.config["qq_secret"] = secret
        console.print("[success]✓ QQ 配置完成[/success]")

    def _save_config(self):
        """保存配置"""
        config_path = Path("config.json")
        config_path.write_text(
            json.dumps(self.config, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        console.print(f"\n[info]配置已保存到: {config_path}[/info]")