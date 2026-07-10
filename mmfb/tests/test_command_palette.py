"""测试命令面板 Python 侧桥接信号发射逻辑

此模块不依赖 QApplication 或 QWebEngineView，通过模拟信号接收
验证 MMFBBridge.showCommandPanel / openSettings 信号能正确触发。
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 跳过无 QApplication 时的 Qt 测试
try:
    from PySide6.QtWidgets import QApplication
    _has_qt = True
except ImportError:
    _has_qt = False


def _make_app_or_none():
    """如果已有 QApplication 则返回它，否则尝试创建。"""
    if not _has_qt:
        return None
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class SignalRecorder:
    """用于捕获 Qt 信号发射"""
    def __init__(self):
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)


class TestMMFBBridgeImmersiveSignals(unittest.TestCase):
    """验证 MMFBBridge 的沉浸式 UI 信号"""

    def _fresh_bridge(self):
        from mmfb.core.bridge import MMFBBridge
        return MMFBBridge()

    def test_show_command_panel_signal_exists(self):
        """bridge 应该有 showCommandPanel 信号属性"""
        bridge = self._fresh_bridge()
        self.assertTrue(hasattr(bridge, 'showCommandPanel'))

    def test_open_settings_signal_exists(self):
        """bridge 应该有 openSettings 信号属性"""
        bridge = self._fresh_bridge()
        self.assertTrue(hasattr(bridge, 'openSettings'))

    def test_header_visibility_changed_signal_exists(self):
        """bridge 应该有 headerVisibilityChanged 信号属性"""
        bridge = self._fresh_bridge()
        self.assertTrue(hasattr(bridge, 'headerVisibilityChanged'))

    def test_trigger_command_panel_emits_signal(self):
        """trigger_command_panel 应该 emit showCommandPanel 信号"""
        bridge = self._fresh_bridge()
        recorder = SignalRecorder()
        bridge.showCommandPanel.connect(recorder)
        bridge.trigger_command_panel()
        self.assertEqual(len(recorder.calls), 1)

    def test_trigger_open_settings_emits_signal(self):
        """trigger_open_settings 应该 emit openSettings 信号"""
        bridge = self._fresh_bridge()
        recorder = SignalRecorder()
        bridge.openSettings.connect(recorder)
        bridge.trigger_open_settings()
        self.assertEqual(len(recorder.calls), 1)

    def test_set_header_visible_emits_signal_true(self):
        """set_header_visible(True) 应该 emit headerVisibilityChanged(True)"""
        bridge = self._fresh_bridge()
        recorder = SignalRecorder()
        bridge.headerVisibilityChanged.connect(recorder)
        bridge.set_header_visible(True)
        self.assertEqual(len(recorder.calls), 1)
        self.assertEqual(recorder.calls[0], (True,))

    def test_set_header_visible_emits_signal_false(self):
        """set_header_visible(False) 应该 emit headerVisibilityChanged(False)"""
        bridge = self._fresh_bridge()
        recorder = SignalRecorder()
        bridge.headerVisibilityChanged.connect(recorder)
        bridge.set_header_visible(False)
        self.assertEqual(len(recorder.calls), 1)
        self.assertEqual(recorder.calls[0], (False,))


if __name__ == '__main__':
    unittest.main()
