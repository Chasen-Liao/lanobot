"""
思考中的狗狗动画组件
"""
import asyncio
from typing import Optional


# ASCII 狗狗样式
ASCII_DOG = r"""
       ████████
     ██          ██
   ██    ████    ██
   ██   ██  ██   ██
   ██   ██████   ██
    ██  ██  ██  ██
     ██        ██
       ████████
"""


class ThinkingSpinner:
    """思考中的狗狗动画"""

    # 动画帧（循环显示不同符号）
    FRAMES = [
        ("🐕", "◠"),  # 向上
        ("🐕", "◡"),  # 向下
        ("🐕", "◠"),  # 向上
        ("🐕", "◝"),  # 向右上
    ]

    # 简单模式（不需要 ASCII 狗狗）
    SIMPLE_FRAMES = [
        "🐕 思考中",
        "🐕 思考中",
        "🐕 思考中",
        "🐕 思考中",
    ]

    def __init__(self, use_ascii: bool = True):
        """初始化动画器

        Args:
            use_ascii: 是否使用 ASCII 狗狗图案
        """
        self.frame = 0
        self.use_ascii = use_ascii
        self._task: Optional[asyncio.Task] = None
        self._stop_event: Optional[asyncio.Event] = None

    def update(self) -> str:
        """获取下一帧动画

        Returns:
            str: 当前帧的字符串表示
        """
        self.frame = (self.frame + 1) % len(self.FRAMES)
        return self.get_text()

    def get_text(self) -> str:
        """获取当前帧的文本

        Returns:
            str: 当前帧显示的文本
        """
        if self.use_ascii:
            dog, symbol = self.FRAMES[self.frame]
            return f"{dog} 思考中 {symbol}"
        else:
            return self.SIMPLE_FRAMES[self.frame]

    async def start_animation(self, console, update_callback=None):
        """开始动画循环

        Args:
            console: Rich Console 实例
            update_callback: 可选的回调函数，在每帧更新时调用
        """
        self._stop_event = asyncio.Event()

        async def animate():
            while not self._stop_event.is_set():
                text = self.get_text()
                if update_callback:
                    update_callback(text)
                else:
                    console.print(f"\r[dim]{text}[/dim]", end="", highlight=False)
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=0.5)
                    break
                except asyncio.TimeoutError:
                    pass

        self._task = asyncio.create_task(animate())

    def stop_animation(self):
        """停止动画"""
        if self._stop_event:
            self._stop_event.set()
        if self._task:
            try:
                self._task.cancel()
            except asyncio.CancelledError:
                pass

    def reset(self):
        """重置动画帧"""
        self.frame = 0
        self._task = None
        self._stop_event = None


class SimpleSpinner:
    """简单的文本旋转动画（不需要异步）"""

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    DONE_FRAMES = ["✓"]

    def __init__(self):
        self.frame = 0
        self.done = False

    def update(self) -> str:
        """获取下一帧

        Returns:
            str: 当前帧字符
        """
        if self.done:
            return self.DONE_FRAMES[0]

        self.frame = (self.frame + 1) % len(self.FRAMES)
        return self.FRAMES[self.frame]

    def mark_done(self):
        """标记完成状态"""
        self.done = True
        self.frame = 0

    def reset(self):
        """重置"""
        self.frame = 0
        self.done = False