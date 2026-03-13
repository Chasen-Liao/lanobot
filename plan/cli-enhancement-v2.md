# CLI 界面美化执行计划

## 概述

为 Lanobot 的 CLI 交互界面进行全面美化，提供更友好的用户体验。

## 需求确认

| 功能 | 方案 |
|------|------|
| 思考/工具调用区分 | 浅灰色字体，实时流式显示 |
| 输出折叠 | 用户可控折叠（快捷键切换） |
| 聊天框样式 | 左右分离大R角气泡（用户绿、Agent蓝） |
| 命令系统 | 斜杠命令（/exit, /resume, /rename, /help, /clear） |
| 思考动画 | ASCII 可爱狗狗头像 🐕 |

---

## 详细设计

### 1. 模块结构

```
lanobot/
├── cli/
│   ├── __init__.py          # 主入口（已存在）
│   ├── components/          # 新增：UI 组件
│   │   ├── __init__.py
│   │   ├── bubble.py        # 气泡框组件
│   │   ├── spinner.py       # 思考中的狗狗动画
│   │   ├── command.py      # 命令处理
│   │   └── folding.py      # 可折叠区域
│   └── repl.py             # 新增：交互式 REPL
└── main.py                  # 修改：使用新的 REPL
```

### 2. UI 样式规范

#### 2.1 颜色方案

| 元素 | 颜色 | Rich 标签 |
|------|------|-----------|
| 用户消息气泡 | 绿色边框 #22c55e | `border_style="green"` |
| Agent 消息气泡 | 蓝色边框 #3b82f6 | `border_style="cyan"` |
| 思考内容 | 浅灰色 #9ca3af | `style="dim"` |
| 工具调用 | 青色 #06b6d4 | `style="cyan"` |
| 命令提示 | 洋红 #d946ef | `style="bold magenta"` |
| 错误信息 | 红色 #ef4444 | `style="red bold"` |
| 成功信息 | 绿色 #22c55e | `style="green"` |

#### 2.2 气泡框样式

```
┌─────────────────────────────────────┐
│ 🐕 思考中...                        │
│                                     │
│ （思考内容流式输出）                │
└─────────────────────────────────────┘
         ↓ 思考完成
┌─────────────────────────────────────┐
│ 💡 思考过程 [按空格折叠]           │
│                                     │
│ （最终回复内容）                    │
└─────────────────────────────────────┘
```

用户消息：
```
┌─────────────────────────────────────┐
│ 你                                 │
│                                     │
│ 今天天气怎么样？                    │
└─────────────────────────────────────┘
```

#### 2.3 ASCII 狗狗表情

```python
THINKING_DOG = """
       ████████
     ██          ██
   ██    ████    ██
   ██   ██  ██   ██
   ██   ██████   ██
    ██  ██  ██  ██
     ██        ██
       ████████
"""
```

动画效果（帧循环）：
```
[1] 🐕  思考中...   [2] 🐕  思考中...   [3] 🐕  思考中...
    ◠                      ◡                      ◝
```

### 3. 命令系统设计

#### 3.1 支持的命令

| 命令 | 描述 | 示例 |
|------|------|------|
| `/help` | 显示帮助信息 | `/help` |
| `/exit` 或 `/quit` | 退出程序 | `/exit` |
| `/clear` | 清空屏幕 | `/clear` |
| `/resume` | 恢复中断的对话 | `/resume` |
| `/rename <name>` | 重命名当前会话 | `/rename my-session` |
| `/session` | 显示会话信息 | `/session` |
| `/model` | 切换模型 | `/model gpt-4` |
| `/think` | 切换思考显示 | `/think` (开启/关闭) |

#### 3.2 命令处理流程

```
用户输入 → 检查是否 / 开头 → 解析命令 → 执行 → 返回结果
                                              ↓
否 → 作为普通消息发送给 Agent → 流式响应 → 显示
```

### 4. 可折叠区域设计

#### 4.1 状态管理

```python
class FoldingState:
    thinking_expanded: bool = True   # 思考过程是否展开
    tool_calls_collapsed: bool = False  # 工具调用是否折叠
    final_response_expanded: bool = True  # 最终回复是否展开
```

#### 4.2 快捷键

| 按键 | 功能 |
|------|------|
| 空格 | 折叠/展开当前区块 |
| ↑/↓ | 查看历史消息 |
| Ctrl+C | 中断当前响应 |
| Tab | 切换到命令模式 |

### 5. 核心组件实现

#### 5.1 BubblePanel 组件

```python
class BubblePanel:
    """消息气泡框组件"""

    @staticmethod
    def user(message: str) -> Panel:
        """用户消息气泡（绿色左边框）"""
        return Panel(
            message,
            border_style="green",
            border_style="rounded",
            padding=(0, 1),
            width=None,  # 自动宽度
        )

    @staticmethod
    def agent(message: str, collapsed: bool = False) -> Panel:
        """Agent 消息气泡（蓝色左边框）"""
        title = "💡 点击展开" if collapsed else "💡"
        return Panel(
            message,
            border_style="cyan",
            border_style="rounded",
            padding=(0, 1),
            title=title if collapsed else None,
        )
```

#### 5.2 Spinner 组件

```python
class ThinkingSpinner:
    """思考中的狗狗动画"""

    FRAMES = [
        "🐕 思考中 ◠",
        "🐕 思考中 ◡",
        "🐕 思考中 ◠",
        "🐕 思考中 ◝",
    ]

    def __init__(self):
        self.frame = 0

    def update(self) -> str:
        self.frame = (self.frame + 1) % len(self.FRAMES)
        return self.FRAMES[self.frame]
```

#### 5.3 REPL 主循环

```python
class InteractiveREPL:
    """交互式 REPL"""

    def __init__(self, agent: AgentGraph):
        self.agent = agent
        self.console = Console()
        self.folding_state = FoldingState()
        self.command_handler = CommandHandler()
        self.spinner = ThinkingSpinner()

    async def run(self):
        """主循环"""
        self.print_welcome()

        while True:
            # 显示用户输入提示
            user_input = self.console.input("[bold green]你[/bold green] > ")

            # 处理命令
            if user_input.startswith("/"):
                result = self.command_handler.handle(user_input)
                if result == CommandResult.EXIT:
                    break
                continue

            # 处理普通消息
            await self.process_message(user_input)
```

---

## 实施步骤

### Phase 1: 基础组件（30%）

1. **创建 cli/components/ 目录**
2. **实现 BubblePanel** - 气泡框组件
3. **实现 ThinkingSpinner** - 狗狗动画
4. **实现颜色主题配置**

### Phase 2: 命令系统（25%）

5. **实现 CommandHandler** - 命令解析与执行
6. **添加命令自动补全**
7. **实现 /help 命令**

### Phase 3: REPL 集成（30%）

8. **创建 InteractiveREPL 类**
9. **修改 main.py 使用新 REPL**
10. **实现流式响应的实时显示**

### Phase 4: 可折叠功能（15%）

11. **实现 FoldingState 状态管理**
12. **添加快捷键监听**
13. **优化用户体验细节**

---

## 待确认问题

1. **快捷键方案**：
   - 当前方案：空格折叠
   - 问题：Windows cmd 可能不支持某些按键
   - 需要确认：是否改为输入命令 `/fold` 来切换？

2. **历史消息**：
   - 当前方案：↑/↓ 翻阅历史
   - 问题：需要持久化存储
   - 需要确认：是否需要历史消息功能？

3. **多会话支持**：
   - 当前方案：每次启动新 session
   - 问题：是否需要命名 session 并保存？
   - 需要确认：是否需要 session 管理功能？

---

## 预期效果预览

```
╔═══════════════════════════════════════════╗
║  🟠 Lanobot v0.1.0                         ║
║  输入 /help 查看可用命令                   ║
╚═══════════════════════════════════════════╝

┌─────────────────────────────────────────┐
│ 你                                       │
│                                         │
│ 帮我写一个 hello world                   │
└─────────────────────────────────────────┘

🐕 思考中 ◠

[调用工具: Bash] ← 浅灰色
  执行: echo "hello world"
  结果: hello world
[工具完成]

┌─────────────────────────────────────────┐
│ 💡                                        │
│                                         │
│ 当然可以！这是最简单的 Hello World:     │
│                                         │
│ ```python                                │
│ print("Hello, World!")                   │
│ ```                                      │
│                                         │
│ [按空格折叠]                             │
└─────────────────────────────────────────┘

你 > /help
```

---

请确认以上设计是否符合你的预期，特别是「待确认问题」部分的细节。