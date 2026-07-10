"""MMFB 窗口管理器

负责管理所有 MainWindow 实例的创建、跟踪和销毁。

职责：
  1. 维护窗口列表（Python 持有引用，避免 GC 回收）
  2. 提供 new_window() / split_window() / close_window() 入口
  3. 当窗口 close 时自动从列表移除
  4. 暴露窗口计数，便于前端判断

设计：
  - 模块级单例 WindowManager()
  - 每个 MainWindow 创建后向管理器注册
  - 通过 WA_DeleteOnClose + destroyed 信号联动清理

使用：
  mgr = get_window_manager()
  w = mgr.new_window(file_path="xxx.pdf")
  w.show()
"""
import logging
from typing import List, Optional
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow

from mmfb.core.window import MainWindow


class WindowManager:
    """窗口管理器（单例模式）"""

    def __init__(self):
        self._windows: List[MainWindow] = []

    # ------------------------------------------------------------------ #
    #  窗口生命周期
    # ------------------------------------------------------------------ #

    def new_window(self, file_path: str = None) -> MainWindow:
        """创建一个新窗口并注册到列表

        Args:
            file_path: 可选，初始打开的文件路径

        Returns:
            新的 MainWindow 实例
        """
        win = MainWindow(window_manager=self)
        self._register(win)

        if file_path:
            # 窗口 show 后再加载文件
            QTimer.singleShot(100, lambda: win.load_file(file_path))

        return win

    def _register(self, win: MainWindow):
        """注册窗口到管理器"""
        if win in self._windows:
            return
        self._windows.append(win)

    def _unregister(self, win: MainWindow):
        """从管理器移除窗口"""
        if win in self._windows:
            self._windows.remove(win)

    def register(self, win: MainWindow):
        """外部窗口（如启动时的首个窗口）注册入口"""
        self._register(win)

    # ------------------------------------------------------------------ #
    #  查询
    # ------------------------------------------------------------------ #

    @property
    def count(self) -> int:
        """当前存活的窗口数"""
        return len(self._windows)

    @property
    def windows(self) -> list:
        """获取窗口列表副本"""
        return list(self._windows)

    def active_window(self) -> Optional[MainWindow]:
        """返回当前活跃窗口（没有则返回首个）"""
        for w in self._windows:
            if w.isActiveWindow():
                return w
        return self._windows[0] if self._windows else None

    # ------------------------------------------------------------------ #
    #  全局操作
    # ------------------------------------------------------------------ #

    def close_all(self):
        """关闭全部窗口"""
        for w in list(self._windows):
            w.close()

    def shutdown(self):
        """应用退出时清理"""
        # 1) 先清理各窗口 bridge 中的 QThread（更新检查/下载）
        for w in list(self._windows):
            try:
                if hasattr(w, '_bridge') and w._bridge:
                    w._bridge.cleanup_threads()
                    logging.debug("[WindowManager] bridge threads cleaned for %s", w)
            except Exception:
                pass

        # 2) 注销全局热键，停止后台线程
        try:
            from mmfb.services.global_hotkey import get_manager
            get_manager().unregister()
        except Exception:
            pass

        self._windows.clear()


# ---------- 单例 ----------
_instance: Optional[WindowManager] = None


def get_window_manager() -> WindowManager:
    """返回全局 WindowManager 实例"""
    global _instance
    if _instance is None:
        _instance = WindowManager()
    return _instance
