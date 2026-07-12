"""MMFB 分屏视图

在主 MainWindow 中实现左右分屏能力：
1. QSplitter 容器，左右两栏各嵌入一个 MMFBWebView
2. 中间拖拽调整比例
3. 可加载不同文档进行对比查看
4. 进入/退出分屏时隐藏 splitter，单视图占满

职责：
- 提供 create_split(parent_window) 工厂方法
- 提供 enter_split(file_left, file_right) / exit_split() 切换
- 维护 split 状态供 Python/JS 交互查询
"""
import logging
import os
import sys
import json

logger = logging.getLogger(__name__)

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QSplitter
)

from mmfb.core.webview import MMFBWebView


class SplitView(QWidget):
    """左右分屏容器

    Signals:
    splitRatioChanged(int): 左栏比例（百分比 0~100）
    """
    splitRatioChanged = Signal(int)

    def __init__(self, parent=None, channel=None):
        super().__init__(parent)
        self._window = parent  # MainWindow 引用
        self._channel = channel
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # QSplitter 作为分屏容器
        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._splitter.setHandleWidth(4)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setStyleSheet("""
            QSplitter::handle { background: #8BA888; }
            QSplitter::handle:hover { background: #6B9E6F; }
        """)

        # 左右两个 webview，使用独立的 QWebChannel 避免抢占 transport 通道
        from PySide6.QtWebChannel import QWebChannel
        self._left_channel = QWebChannel(self)
        self._left_channel.registerObject("pybridge", self._window._bridge)
        self._right_channel = QWebChannel(self)
        self._right_channel.registerObject("pybridge", self._window._bridge)

        self._left_view = MMFBWebView(self, channel=self._left_channel)
        self._right_view = MMFBWebView(self, channel=self._right_channel)

        # 确保鼠标事件可以正常传递，允许网页接收点击聚焦
        self._left_view.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._right_view.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        # 子 webview 不接收拖拽，由 SplitView 统一处理
        self._left_view.setAcceptDrops(False)
        self._right_view.setAcceptDrops(False)

        self._splitter.addWidget(self._left_view)
        self._splitter.addWidget(self._right_view)

        # 为分屏子 webview 注册原生拖拽
        if sys.platform == "win32":
            try:
                import ctypes
                left_hwnd = int(self._left_view.winId())
                right_hwnd = int(self._right_view.winId())
                ctypes.windll.shell32.DragAcceptFiles(left_hwnd, True)
                ctypes.windll.shell32.DragAcceptFiles(right_hwnd, True)
                # 将 hwnd 映射关系存入 MainWindow
                if hasattr(self._window, "_webview_handles"):
                    self._window._webview_handles[left_hwnd] = self._left_view
                    self._window._webview_handles[right_hwnd] = self._right_view
                    logger.debug("[SplitView] DragAcceptFiles on left/right views (hwnd=%s, %s)", hex(left_hwnd), hex(right_hwnd))
                else:
                    logger.warning("[SplitView] MainWindow missing _webview_handles")
            except Exception as e:
                logger.warning("[SplitView] DragAcceptFiles failed: %s", e)

        # 设置比例为 50:50
        self._splitter.setSizes([500, 500])

        # 拖拽比例信号
        self._splitter.splitterMoved.connect(self._on_splitter_moved)

        layout.addWidget(self._splitter)

        # 启用分屏容器自身接收拖拽文件
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """分屏模式下也接受文件拖拽"""
        mime = event.mimeData()
        if mime.hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        """分屏模式拖入文件：根据鼠标位置加载到左栏或右栏"""
        mime = event.mimeData()
        if not mime.hasUrls():
            event.ignore()
            return
        paths = []
        for url in mime.urls():
            if url.isLocalFile():
                path = url.toLocalFile()
                if os.path.isfile(path):
                    paths.append(path)
        if not paths:
            event.ignore()
            return
        event.acceptProposedAction()

        # 根据 event.pos() 判断鼠标落在左栏还是右栏
        mid_x = self.width() // 2 if self.width() > 0 else 0
        drop_on_left = event.pos().x() < mid_x

        # 通知 MainWindow 加载文件
        if self._window is not None:
            first = paths[0]
            if drop_on_left:
                self._window._load_file_in_view(self._left_view, first)
            else:
                self._window._load_file_in_view(self._right_view, first)
            # 多文件时第二个文件加载到另一栏
            if len(paths) > 1:
                second = paths[1]
                if drop_on_left:
                    self._window._load_file_in_view(self._right_view, second)
                else:
                    self._window._load_file_in_view(self._left_view, second)

    def _on_splitter_moved(self, pos: int, index: int):
        """中手柄拖动后计算比例"""
        total = self._splitter.width()
        if total > 0:
            ratio = int(pos * 100 / total)
            self.splitRatioChanged.emit(ratio)

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    @property
    def left_view(self) -> MMFBWebView:
        return self._left_view

    @property
    def right_view(self) -> MMFBWebView:
        return self._right_view

    def set_split_ratio(self, left_percent: int):
        """设置左栏比例（0~100）"""
        left_percent = max(10, min(90, left_percent))
        sizes = self._splitter.sizes()
        total = sum(sizes)
        if total == 0:
            total = 1000
        left_size = int(total * left_percent / 100)
        right_size = total - left_size
        self._splitter.setSizes([left_size, right_size])

    def current_ratio(self) -> int:
        """返回当前左栏比例"""
        sizes = self._splitter.sizes()
        total = sum(sizes)
        if total == 0:
            return 50
        return int(sizes[0] * 100 / total)

    def destroy(self):
        """清理资源"""
        try:
            self._left_view.stop_all()
        except Exception:
            pass
        try:
            self._right_view.stop_all()
        except Exception:
            pass
