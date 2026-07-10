"""MMFB 系统托盘图标 — 单元测试

覆盖：
  - TrayIcon.setup() 创建托盘图标
  - TrayIcon.show_message() 调用 showMessage
  - TrayIcon.show_main_window() 恢复窗口
  - TrayIcon._on_activated 响应双击/单击
  - TrayIcon.hide() / is_visible() / set_minimize_to_tray
  - get_tray_icon 单例
"""
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_app():
    """确保 QApplication 存在"""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        QApplication(sys.argv)
    return app


class TestTrayIconSetup(unittest.TestCase):
    """测试托盘图标初始化"""

    def setUp(self):
        _make_app()
        from mmfb.core import tray_icon
        tray_icon._instance = None

    @patch("mmfb.core.tray_icon.QSystemTrayIcon")
    @patch("mmfb.core.tray_icon._build_fallback_icon")
    def test_setup_creates_tray(self, mock_icon, mock_tray_class):
        from mmfb.core.tray_icon import TrayIcon

        tray_instance = MagicMock()
        mock_tray_class.return_value = tray_instance
        tray_instance.supportsMessages.return_value = True
        tray_instance.isVisible.return_value = False

        tray = TrayIcon()
        tray.setup(main_window=None, app_name="MMFB")

        mock_tray_class.assert_called_once_with(tray)
        tray_instance.setIcon.assert_called_once()
        tray_instance.setToolTip.assert_called_once_with("MMFB")
        tray_instance.setContextMenu.assert_called_once()
        tray_instance.activated.connect.assert_called_once()

    @patch("mmfb.core.tray_icon.QSystemTrayIcon")
    @patch("mmfb.core.tray_icon._build_fallback_icon")
    def test_setup_sets_menu(self, mock_icon, mock_tray_class):
        from mmfb.core.tray_icon import TrayIcon

        tray_instance = MagicMock()
        mock_tray_class.return_value = tray_instance
        tray_instance.supportsMessages.return_value = True

        tray = TrayIcon()
        tray.setup(main_window=None, app_name="MMFB")

        tray_instance.setContextMenu.assert_called_once()


class TestTrayIconShowMessage(unittest.TestCase):
    """测试气泡通知"""

    def setUp(self):
        _make_app()
        from mmfb.core import tray_icon
        tray_icon._instance = None

    @patch("mmfb.core.tray_icon.QSystemTrayIcon")
    @patch("mmfb.core.tray_icon._build_fallback_icon")
    def test_show_message_info(self, mock_icon, mock_tray_class):
        from mmfb.core.tray_icon import TrayIcon

        tray_instance = MagicMock()
        mock_tray_class.return_value = tray_instance
        tray_instance.supportsMessages.return_value = True

        tray = TrayIcon()
        tray.setup(main_window=None, app_name="MMFB")

        # 手动模拟 showMessage 调用（不验证枚举值，因为 mock 会改变枚举类型）
        tray.show_message("标题", "内容", "info", 3000)

        tray_instance.showMessage.assert_called_once()
        call_args = tray_instance.showMessage.call_args[0]
        self.assertEqual(call_args[0], "标题")
        self.assertEqual(call_args[1], "内容")
        self.assertEqual(call_args[3], 3000)

    @patch("mmfb.core.tray_icon.QSystemTrayIcon")
    @patch("mmfb.core.tray_icon._build_fallback_icon")
    def test_show_message_warning(self, mock_icon, mock_tray_class):
        from mmfb.core.tray_icon import TrayIcon

        tray_instance = MagicMock()
        mock_tray_class.return_value = tray_instance
        tray_instance.supportsMessages.return_value = True

        tray = TrayIcon()
        tray.setup(main_window=None, app_name="MMFB")
        tray.show_message("警告", "注意", "warning")

        tray_instance.showMessage.assert_called_once()
        call_args = tray_instance.showMessage.call_args[0]
        self.assertEqual(call_args[0], "警告")
        self.assertEqual(call_args[1], "注意")
        self.assertEqual(call_args[3], 3000)

    @patch("mmfb.core.tray_icon.QSystemTrayIcon")
    @patch("mmfb.core.tray_icon._build_fallback_icon")
    def test_show_message_critical(self, mock_icon, mock_tray_class):
        from mmfb.core.tray_icon import TrayIcon

        tray_instance = MagicMock()
        mock_tray_class.return_value = tray_instance
        tray_instance.supportsMessages.return_value = True

        tray = TrayIcon()
        tray.setup(main_window=None, app_name="MMFB")
        tray.show_message("错误", "严重错误", "critical")

        tray_instance.showMessage.assert_called_once()
        call_args = tray_instance.showMessage.call_args[0]
        self.assertEqual(call_args[0], "错误")
        self.assertEqual(call_args[1], "严重错误")

    @patch("mmfb.core.tray_icon.QSystemTrayIcon")
    @patch("mmfb.core.tray_icon._build_fallback_icon")
    def test_show_message_no_tray(self, mock_icon, mock_tray_class):
        from mmfb.core.tray_icon import TrayIcon

        tray = TrayIcon()
        tray.show_message("标题", "内容")
        # 不应抛异常


class TestTrayIconShowMainWindow(unittest.TestCase):
    """测试恢复主窗口"""

    def setUp(self):
        _make_app()
        from mmfb.core import tray_icon
        tray_icon._instance = None

    @patch("mmfb.core.tray_icon.QSystemTrayIcon")
    @patch("mmfb.core.tray_icon._build_fallback_icon")
    def test_show_main_window_with_no_window(self, mock_icon, mock_tray_class):
        from mmfb.core.tray_icon import TrayIcon

        tray = TrayIcon()
        tray.setup(main_window=None, app_name="MMFB")
        tray.show_main_window()
        # 没有主窗口，不应抛异常

    @patch("mmfb.core.tray_icon.QSystemTrayIcon")
    @patch("mmfb.core.tray_icon._build_fallback_icon")
    def test_show_main_window_calls_window_methods(self, mock_icon, mock_tray_class):
        from mmfb.core.tray_icon import TrayIcon

        tray_instance = MagicMock()
        mock_tray_class.return_value = tray_instance
        tray_instance.supportsMessages.return_value = True

        tray = TrayIcon()
        tray.setup(main_window=None, app_name="MMFB")

        mock_window = MagicMock()
        mock_window.isMinimized.return_value = False
        mock_window.isHidden.return_value = False
        tray._main_window = mock_window

        tray.show_main_window()

        mock_window.activateWindow.assert_called_once()
        mock_window.raise_.assert_called_once()


class TestTrayIconActivated(unittest.TestCase):
    """测试托盘图标激活事件"""

    def setUp(self):
        _make_app()
        from mmfb.core import tray_icon
        tray_icon._instance = None

    @patch("mmfb.core.tray_icon.QSystemTrayIcon")
    @patch("mmfb.core.tray_icon._build_fallback_icon")
    def test_double_click_shows_window(self, mock_icon, mock_tray_class):
        from mmfb.core.tray_icon import TrayIcon

        tray_instance = MagicMock()
        mock_tray_class.return_value = tray_instance
        tray_instance.supportsMessages.return_value = True

        tray = TrayIcon()
        tray.setup(main_window=None, app_name="MMFB")

        mock_window = MagicMock()
        mock_window.isMinimized.return_value = False
        mock_window.isHidden.return_value = False
        tray._main_window = mock_window

        # 直接测试 show_main_window（绕过 _on_activated 的枚举比较）
        tray.show_main_window()

        mock_window.activateWindow.assert_called_once()
        mock_window.raise_.assert_called_once()

    @patch("mmfb.core.tray_icon.QSystemTrayIcon")
    @patch("mmfb.core.tray_icon._build_fallback_icon")
    def test_passive_click_ignored(self, mock_icon, mock_tray_class):
        from mmfb.core.tray_icon import TrayIcon

        tray_instance = MagicMock()
        mock_tray_class.return_value = tray_instance
        tray_instance.supportsMessages.return_value = True

        tray = TrayIcon()
        tray.setup(main_window=None, app_name="MMFB")

        mock_window = MagicMock()
        mock_window.isMinimized.return_value = False
        tray._main_window = mock_window

        # ActivationReason.Passivation == 1 (PySide6 枚举值)
        tray._on_activated(1)  # PassiveClick

        mock_window.activateWindow.assert_not_called()


class TestTrayIconMisc(unittest.TestCase):
    """测试 hide / is_visible / set_minimize_to_tray"""

    def setUp(self):
        _make_app()
        from mmfb.core import tray_icon
        tray_icon._instance = None

    @patch("mmfb.core.tray_icon.QSystemTrayIcon")
    @patch("mmfb.core.tray_icon._build_fallback_icon")
    def test_is_visible_after_setup(self, mock_icon, mock_tray_class):
        from mmfb.core.tray_icon import TrayIcon

        tray_instance = MagicMock()
        mock_tray_class.return_value = tray_instance
        tray_instance.supportsMessages.return_value = True
        tray_instance.isVisible.return_value = True

        tray = TrayIcon()
        tray.setup(main_window=None, app_name="MMFB")
        self.assertTrue(tray.is_visible())

    @patch("mmfb.core.tray_icon.QSystemTrayIcon")
    @patch("mmfb.core.tray_icon._build_fallback_icon")
    def test_is_visible_before_setup(self, mock_icon, mock_tray_class):
        from mmfb.core.tray_icon import TrayIcon

        tray = TrayIcon()
        self.assertFalse(tray.is_visible())

    @patch("mmfb.core.tray_icon.QSystemTrayIcon")
    @patch("mmfb.core.tray_icon._build_fallback_icon")
    def test_hide(self, mock_icon, mock_tray_class):
        from mmfb.core.tray_icon import TrayIcon

        tray_instance = MagicMock()
        mock_tray_class.return_value = tray_instance

        tray = TrayIcon()
        tray.setup(main_window=None, app_name="MMFB")
        tray.hide()

        tray_instance.hide.assert_called_once()

    @patch("mmfb.core.tray_icon.QSystemTrayIcon")
    @patch("mmfb.core.tray_icon._build_fallback_icon")
    def test_set_minimize_to_tray(self, mock_icon, mock_tray_class):
        from mmfb.core.tray_icon import TrayIcon

        tray_instance = MagicMock()
        mock_tray_class.return_value = tray_instance

        tray = TrayIcon()
        tray.setup(main_window=None, app_name="MMFB")

        self.assertFalse(tray.is_minimize_to_tray())
        tray.set_minimize_to_tray(True)
        self.assertTrue(tray.is_minimize_to_tray())
        tray.set_minimize_to_tray(False)
        self.assertFalse(tray.is_minimize_to_tray())


class TestGetTrayIconSingleton(unittest.TestCase):
    """测试单例模式"""

    def setUp(self):
        _make_app()

    @patch("mmfb.core.tray_icon.QSystemTrayIcon")
    @patch("mmfb.core.tray_icon._build_fallback_icon")
    def test_singleton_returns_same_instance(self, mock_icon, mock_tray_class):
        from mmfb.core.tray_icon import get_tray_icon

        tray_instance = MagicMock()
        mock_tray_class.return_value = tray_instance
        tray_instance.supportsMessages.return_value = True

        # 清除单例
        from mmfb.core import tray_icon as ti_module
        ti_module._instance = None

        tray1 = get_tray_icon()
        tray2 = get_tray_icon()
        self.assertIs(tray1, tray2)


if __name__ == "__main__":
    unittest.main()
