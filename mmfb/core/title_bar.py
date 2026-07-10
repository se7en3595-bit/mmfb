"""自定义标题栏

支持显示/隐藏动画（沉浸式内容优先模式）
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QPoint, Signal, QEasingCurve, QPropertyAnimation, QParallelAnimationGroup
from PySide6.QtGui import QMouseEvent, QFont


class TitleBarButton(QPushButton):
    """标题栏圆形按钮基类"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(14, 14)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)


class TitleBar(QWidget):
    """自绘标题栏

    支持沉浸式模式下自动隐藏（向下滑出视口）和悬停显示。

    Signals:
        title_bar_double_clicked: 双击标题栏时发射
    """
    title_bar_double_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent_window = parent
        self._drag_pos: QPoint = QPoint()
        self._animation = None
        self._init_ui()

    def _init_ui(self):
        self.setFixedHeight(36)
        self.setObjectName("titleBar")
        self.setStyleSheet("""
            #titleBar {
                background: #C7EDCC;
                border-bottom: 1px solid #8BA888;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(0)

        # 文件名标签（居中显示）
        self.title_label = QLabel("MMFB")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(13)
        font.setWeight(QFont.Weight.Medium)
        self.title_label.setFont(font)
        self.title_label.setStyleSheet("color: #4A6B50;")

        # 按钮容器
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        # 最小化按钮
        self.btn_minimize = TitleBarButton()
        self.btn_minimize.setText("─")
        self.btn_minimize.setToolTip("最小化")
        self.btn_minimize.clicked.connect(self._on_minimize)
        self.btn_minimize.setStyleSheet("""
            TitleBarButton {
                background: #FEBC2E;
                border: none;
                border-radius: 7px;
                color: #995E00;
                font-size: 10px;
            }
            TitleBarButton:hover { background: #F5B320; }
        """)

        # 最大化/还原按钮
        self.btn_maximize = TitleBarButton()
        self.btn_maximize.setText("□")
        self.btn_maximize.setToolTip("最大化")
        self.btn_maximize.clicked.connect(self._on_maximize)
        self.btn_maximize.setStyleSheet("""
            TitleBarButton {
                background: #28C840;
                border: none;
                border-radius: 7px;
                color: #0A5E18;
                font-size: 9px;
            }
            TitleBarButton:hover { background: #24B83B; }
        """)

        # 关闭按钮
        self.btn_close = TitleBarButton()
        self.btn_close.setText("×")
        self.btn_close.setToolTip("关闭")
        self.btn_close.clicked.connect(self._on_close)
        self.btn_close.setStyleSheet("""
            TitleBarButton {
                background: #FF5F57;
                border: none;
                border-radius: 7px;
                color: #990000;
                font-size: 14px;
                font-weight: bold;
            }
            TitleBarButton:hover { background: #F24A42; }
        """)

        btn_layout.addWidget(self.btn_minimize)
        btn_layout.addWidget(self.btn_maximize)
        btn_layout.addWidget(self.btn_close)

        layout.addStretch(1)
        layout.addWidget(self.title_label, 2, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)
        layout.addWidget(btn_container)

    def set_title(self, title: str):
        """设置标题文字"""
        self.title_label.setText(title)

    def update_maximize_button(self, is_maximized: bool):
        """更新最大化按钮图标（最大化/还原）"""
        self.btn_maximize.setText("❐" if is_maximized else "□")
        self.btn_maximize.setToolTip("还原" if is_maximized else "最大化")

    # ------------------------------------------------------------------ #
    #  沉浸式动画
    # ------------------------------------------------------------------ #

    def slide_in(self):
        """显示标题栏（从顶部滑入）"""
        if self._animation is not None:
            self._animation.stop()
            self._animation.deleteLater()

        self.show()
        self.raise_()

        anim = QPropertyAnimation(self, b"geometry")
        anim.setDuration(200)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        current = self.geometry()
        target = current.adjusted(0, 0, 0, 0)
        # 如果当前不可见（高度为 0）则展开
        if current.height() < 36:
            target.setHeight(36)
            target.setTop(current.top())  # 从当前位置展开

        anim.setStartValue(current)
        anim.setEndValue(target)
        anim.start()

        self._animation = anim

    def slide_out(self):
        """隐藏标题栏（向下滑出视口）"""
        if self._animation is not None:
            self._animation.stop()
            self._animation.deleteLater()
            self._animation = None

        anim = QPropertyAnimation(self, b"geometry")
        anim.setDuration(200)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)

        current = self.geometry()
        # 收缩到高度 0
        collapsed = current.adjusted(0, current.height(), 0, 0)

        anim.setStartValue(current)
        anim.setEndValue(collapsed)
        anim.finished.connect(lambda: self.hide())
        anim.start()

        self._animation = anim

    def stop_animation(self):
        """停止当前动画并清理（避免 finished 信号触发 hide）"""
        if self._animation is not None:
            self._animation.stop()
            self._animation.deleteLater()
            self._animation = None

    def is_fully_visible(self) -> bool:
        """判断标题栏是否完全展开"""
        return self.isVisible() and self.height() >= 36

    # 拖拽移动
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.position().toPoint())
            if child is None or isinstance(child, (QLabel, QWidget)) and not isinstance(child, TitleBarButton):
                self._drag_pos = event.globalPosition().toPoint()
                event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.MouseButton.LeftButton:
            global_pos = event.globalPosition().toPoint()
            delta = global_pos - self._drag_pos
            if self._parent_window:
                self._parent_window.move(self._parent_window.pos() + delta)
            self._drag_pos = global_pos
            event.accept()
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.title_bar_double_clicked.emit()
        super().mouseDoubleClickEvent(event)

    # 按钮槽函数
    def _on_minimize(self):
        if self._parent_window:
            self._parent_window.showMinimized()

    def _on_maximize(self):
        if self._parent_window:
            if self._parent_window.isMaximized():
                self._parent_window.showNormal()
            else:
                self._parent_window.showMaximized()

    def _on_close(self):
        if self._parent_window:
            self._parent_window.close()
