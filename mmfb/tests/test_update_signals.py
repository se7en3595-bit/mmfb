"""测试 Bridge 新增的更新信号和槽"""
import json
import unittest

try:
    from PySide6.QtCore import QCoreApplication
    HAS_QT = True
except ImportError:
    HAS_QT = False


@unittest.skipUnless(HAS_QT, "PySide6 not available")
class TestBridgeUpdateSignals(unittest.TestCase):
    """测试 MMFBBridge 的更新信号和槽是否可调用"""

    def _make_bridge(self):
        # 创建最小 QCoreApplication
        app = QCoreApplication.instance() or QCoreApplication([])
        from mmfb.core.bridge import MMFBBridge
        return MMFBBridge()

    def test_update_signals_exist(self):
        bridge = self._make_bridge()
        self.assertTrue(hasattr(bridge, "updateCheckResult"))
        self.assertTrue(hasattr(bridge, "updateDownloadProgress"))
        self.assertTrue(hasattr(bridge, "updateInstallerReady"))

    def test_update_slots_callable(self):
        bridge = self._make_bridge()
        self.assertTrue(callable(getattr(bridge, "get_version", None)))
        self.assertTrue(callable(getattr(bridge, "check_for_updates", None)))
        self.assertTrue(callable(getattr(bridge, "download_update", None)))
        self.assertTrue(callable(getattr(bridge, "launch_installer", None)))
        self.assertTrue(callable(getattr(bridge, "skip_version", None)))

    def test_get_version_format(self):
        bridge = self._make_bridge()
        result = bridge.get_version()
        data = json.loads(result)
        self.assertIn("version", data)
        self.assertIn("name", data)

    def test_launch_installer_not_found(self):
        """不在 Windows 上也能测：路径不存在时应返回错误 JSON"""
        bridge = self._make_bridge()
        result = bridge.launch_installer("/noop/nonexistent.exe")
        data = json.loads(result)
        self.assertFalse(data["ok"])


if __name__ == "__main__":
    unittest.main()
