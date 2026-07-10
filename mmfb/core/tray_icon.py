"""MMFB 系统托盘图标

功能：
  - 显示托盘图标（使用内建 fallback 图标，无需外部资源文件）
  - 右键菜单：显示主窗口 / 打开文件 / 退出
  - 双击托盘图标恢复窗口
  - 托盘气泡通知（转换完成等）

设计：
  - TrayIcon 封装 QSystemTrayIcon，持有对 MainWindow 的引用
  - 最小化到托盘：拦截 window changeEvent，隐藏窗口并从任务栏移除
  - 恢复窗口：双击/单击托盘图标 or 右键菜单"显示主窗口"
"""
import os
from PySide6.QtWidgets import (
    QSystemTrayIcon, QMenu, QApplication, QStyle
)
from PySide6.QtCore import Qt, QTimer, QObject
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QAction


def _build_fallback_icon() -> QIcon:
    """生成一个简单的 fallback 字母 O 图标（暖纸色背景 + 深色 O）

    用于没有外部 .ico/.png 资源文件时保证托盘图标可见。
    """
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # 背景圆
    painter.setBrush(QColor("#C7EDCC"))
    painter.setPen(QColor("#C47A3D"))
    painter.drawEllipse(4, 4, 56, 56)

    # 字母 O
    painter.setPen(QColor("#1E3A24"))
    font = QFont("Segoe UI", 28, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "O")
    painter.end()

    return QIcon(pixmap)


class TrayIcon(QObject):
    """MMFB 系统托盘图标

    通过 set_main_window() 绑定到主窗口，实现：
      - 最小化时隐藏窗口并显示托盘
      - 双击/右键菜单恢复窗口
      - 气泡消息通知
    """

    def __init__(self, parent: QObject = None):
        super().__init__(parent)

        self._main_window = None
        self._tray: QSystemTrayIcon = None
        self._menu: QMenu = None
        self._minimize_to_tray = True  # 是否最小化到托盘

    # ------------------------------------------------------------------ #
    #  初始化
    # ------------------------------------------------------------------ #

    def setup(self, main_window=None, app_name: str = "MMFB"):
        """创建托盘图标和右键菜单

        Args:
            main_window: 绑定的主窗口（可后续通过 set_main_window() 设置）
            app_name: 应用名（显示在托盘 tooltip 和菜单标题中）
        """
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self._main_window = main_window

        # 创建托盘图标
        self._tray = QSystemTrayIcon(self)
        icon = _build_fallback_icon()
        self._tray.setIcon(icon)
        self._tray.setToolTip(app_name)

        # 创建右键菜单
        self._menu = QMenu()
        self._build_menu(app_name)

        self._tray.setContextMenu(self._menu)

        # 托盘图标激活（单击/双击）
        self._tray.activated.connect(self._on_activated)

        # 显示托盘图标（必须显式调用 show 才能在系统托盘中可见）
        self._tray.show()

    def _build_menu(self, app_name: str):
        """构建托盘右键菜单"""
        # 显示主窗口
        self._action_show = QAction(f"显示 {app_name} 窗口", self._menu)
        self._action_show.triggered.connect(self.show_main_window)

        # 打开文件
        self._action_open = QAction("打开文件...", self._menu)
        self._action_open.triggered.connect(self._open_file_dialog)

        # 分隔线
        self._menu.addAction(self._action_show)
        self._menu.addAction(self._action_open)
        self._menu.addSeparator()

        # 退出
        self._action_quit = QAction("退出 MMFB", self._menu)
        self._action_quit.triggered.connect(self._quit_application)
        self._menu.addAction(self._action_quit)

    # ------------------------------------------------------------------ #
    #  公共接口
    # ------------------------------------------------------------------ #

    def set_main_window(self, window):
        """绑定/重新绑定主窗口"""
        self._main_window = window

    def set_minimize_to_tray(self, enabled: bool):
        """设置最小化到托盘"""
        self._minimize_to_tray = enabled

    def is_minimize_to_tray(self) -> bool:
        return self._minimize_to_tray

    def show_main_window(self):
        """恢复并显示主窗口"""
        if self._main_window is None:
            return

        w = self._main_window
        try:
            if w.isMinimized():
                w.showNormal()
            elif w.isHidden():
                w.show()
            else:
                w.showNormal()

            w.activateWindow()
            w.raise_()
        except RuntimeError:
            # 窗口已被销毁
            self._main_window = None

    def show_message(self, title: str, message: str, icon_type: str = "info", msecs: int = 3000):
        """显示托盘气泡通知（供 Bridge 调用）

        Args:
            title: 通知标题
            message: 通知内容
            icon_type: 图标类型 ("info" | "warning" | "critical")
            msecs: 显示毫秒数
        """
        if self._tray is None:
            return

        if not self._tray.supportsMessages():
            return

        icon_map = {
            "info": QSystemTrayIcon.MessageIcon.Information,
            "warning": QSystemTrayIcon.MessageIcon.Warning,
            "critical": QSystemTrayIcon.MessageIcon.Critical,
        }
        icon = icon_map.get(icon_type, QSystemTrayIcon.MessageIcon.Information)

        try:
            self._tray.showMessage(title, message, icon, msecs)
        except Exception:
            pass

    def show_notification(self, title: str, message: str,
                          icon=None, msecs: int = 3000):
        """显示托盘气泡通知（旧接口，保留向后兼容）

        Args:
            title: 通知标题
            message: 通知内容
            icon: 图标类型，默认 Information
            msecs: 显示毫秒数
        """
        if self._tray is None:
            return

        if not self._tray.supportsMessages():
            return

        if icon is None:
            icon = QSystemTrayIcon.MessageIcon.Information

        try:
            self._tray.showMessage(title, message, icon, msecs)
        except Exception:
            pass

    def hide(self):
        """隐藏托盘图标（应用退出前调用）"""
        if self._tray:
            self._tray.hide()

    def is_visible(self) -> bool:
        return self._tray is not None and self._tray.isVisible()

    # ------------------------------------------------------------------ #
    #  事件处理
    # ------------------------------------------------------------------ #

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason):
        """托盘图标被用户点击"""
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,      # 单击
            QSystemTrayIcon.ActivationReason.DoubleClick,  # 双击
        ):
            self.show_main_window()

    def _open_file_dialog(self):
        """右键菜单：打开文件"""
        from PySide6.QtWidgets import QFileDialog
        if self._main_window:
            file_path, _ = QFileDialog.getOpenFileName(
                self._main_window,
                "打开文件",
                "",
                "所有文件 (*.*)"
            )
        else:
            file_path, _ = QFileDialog.getOpenFileName(
                None,
                "打开文件",
                "",
                "所有文件 (*.*)"
            )

        if file_path and self._main_window:
            self._main_window.load_file(file_path)
            self.show_main_window()

    def _quit_application(self):
        """托盘菜单：退出应用"""
        QApplication.quit()


# ---------- 单例 ----------
_instance: TrayIcon = None


def get_tray_icon(parent: QObject = None) -> TrayIcon:
    """返回全局 TrayIcon 实例"""
    global _instance
    if _instance is None:
        _instance = TrayIcon(parent)
    return _instance
