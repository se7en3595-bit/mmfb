"""测试全局热键服务

注意：实际注册测试需要在 Windows 桌面环境运行（依赖 win32api）。
在 CI 或无 win32py的环境中自动跳过。
"""
import sys
import unittest

# pywin32 是否可用
try:
    import win32con  # noqa: F401
    HAS_PYWIN32 = True
except ImportError:
    HAS_PYWIN32 = False


class TestParseHotkey(unittest.TestCase):
    """热键组合字符串解析（无需 Windows 环境）"""

    @classmethod
    def setUpClass(cls):
        from mmfb.services.global_hotkey import GlobalHotkeyManager
        cls.mgr = GlobalHotkeyManager.instance()

    def test_ctrl_alt_o(self):
        c, v = self.mgr.parse_hotkey("Ctrl+Alt+O")
        self.assertEqual(c, 3)          # MOD_CONTROL | MOD_ALT
        self.assertEqual(v, ord("O"))   # VK_O

    def test_ctrl_shift_f5(self):
        c, v = self.mgr.parse_hotkey("Ctrl+Shift+F5")
        import win32con
        self.assertEqual(c, win32con.MOD_CONTROL | win32con.MOD_SHIFT)
        self.assertEqual(v, win32con.VK_F5)

    def test_alt_f4(self):
        c, v = self.mgr.parse_hotkey("Alt+F4")
        import win32con
        self.assertEqual(c, win32con.MOD_ALT)
        self.assertEqual(v, win32con.VK_F4)

    def test_ctrl_o(self):
        c, v = self.mgr.parse_hotkey("Ctrl+O")
        import win32con
        self.assertEqual(c, win32con.MOD_CONTROL)
        self.assertEqual(v, ord("O"))

    def test_single_key_letter(self):
        c, v = self.mgr.parse_hotkey("A")
        self.assertEqual(c, 0)
        self.assertEqual(v, ord("A"))

    def test_uppercase_key(self):
        c, v = self.mgr.parse_hotkey("Ctrl+Z")
        self.assertEqual(c, 2)          # MOD_CONTROL
        self.assertEqual(v, ord("Z"))

    def test_ctrl_no_plus(self):
        # 单个字符的热键（无修饰键）
        c, v = self.mgr.parse_hotkey("F1")
        import win32con
        self.assertEqual(c, 0)
        self.assertEqual(v, win32con.VK_F1)

    def test_unknown_modifier_ignored(self):
        # 未知修饰键应被忽略但不崩溃
        c, v = self.mgr.parse_hotkey("Foo+Ctrl+A")
        self.assertIsNotNone(c)
        self.assertIsNotNone(v)


class TestManagerStructure(unittest.TestCase):
    """测试接口结构（无需实际注册）"""

    @classmethod
    def setUpClass(cls):
        from mmfb.services.global_hotkey import GlobalHotkeyManager
        # 创建全新实例不污染测试
        cls.mgr = GlobalHotkeyManager()

    def test_default_description(self):
        self.assertEqual(self.mgr.current_hotkey(), "Ctrl+Alt+O")
        self.assertFalse(self.mgr.is_active())
        self.assertFalse(self.mgr.is_registered() if hasattr(self.mgr, 'is_registered') else True)

    def test_parse_returns_tuple(self):
        result = self.mgr.parse_hotkey("Ctrl+Alt+O")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_hotkey_label_default(self):
        # 使用全新实例避免状态污染
        from mmfb.services.global_hotkey import GlobalHotkeyManager
        fresh = GlobalHotkeyManager()
        label = fresh._hotkey_label(
            fresh._modifiers, fresh._vk
        )
        self.assertIn("Ctrl", label)
        self.assertIn("Alt", label)
        self.assertIn("O", label)

    def test_hotkey_label_no_modifiers(self):
        label = self.mgr._hotkey_label(0, ord("A"))
        self.assertEqual(label, "A")


@unittest.skipUnless(HAS_PYWIN32, "pywin32 not available")
class TestRegistrationLive(unittest.TestCase):
    """实际注册/注销（需要 Windows 桌面环境）"""

    def test_register_and_unregister(self):
        from mmfb.services.global_hotkey import GlobalHotkeyManager
        mgr = GlobalHotkeyManager()
        self.assertFalse(mgr.is_active())

        # 注册
        fired = []

        def on_fire():
            fired.append(True)

        ok = mgr.register(callback=on_fire, description="Ctrl+Shift+X")
        self.assertTrue(ok, "注册应该成功")
        self.assertTrue(mgr.is_active())

        # 注销
        mgr.unregister()
        # 等待线程退出
        import time
        time.sleep(0.2)
        self.assertFalse(mgr.is_active())


if __name__ == "__main__":
    unittest.main()
