"""测试 WindowManager 窗口生命周期管理

验证：
  1. 单例模式正确
  2. new_window 创建并注册
  3. 窗口销毁时自动注销
  4. count / windows / active_window 查询
  5. close_all 关闭全部
  6. shutdown 清理
"""
import unittest
from unittest.mock import MagicMock, patch


class TestWindowManagerSingleton(unittest.TestCase):
    """单例模式测试"""

    def setUp(self):
        import mmfb.core.window_manager as wm
        wm._instance = None

    def tearDown(self):
        import mmfb.core.window_manager as wm
        wm._instance = None

    def test_singleton_returns_same_instance(self):
        from mmfb.core.window_manager import get_window_manager
        mgr1 = get_window_manager()
        mgr2 = get_window_manager()
        self.assertIs(mgr1, mgr2)

    def test_initial_count_is_zero(self):
        from mmfb.core.window_manager import get_window_manager
        mgr = get_window_manager()
        self.assertEqual(mgr.count, 0)

    def test_initial_windows_list_empty(self):
        from mmfb.core.window_manager import get_window_manager
        mgr = get_window_manager()
        self.assertEqual(len(mgr.windows), 0)


class TestWindowManagerLifecycle(unittest.TestCase):
    """窗口生命周期测试"""

    def setUp(self):
        import mmfb.core.window_manager as wm
        wm._instance = None

    def tearDown(self):
        import mmfb.core.window_manager as wm
        wm._instance = None

    def test_register_and_count(self):
        """注册窗口后 count 增加"""
        from mmfb.core.window_manager import get_window_manager
        mgr = get_window_manager()
        mock_win = MagicMock()
        mgr.register(mock_win)
        self.assertEqual(mgr.count, 1)

    def test_register_duplicate_noop(self):
        """重复注册同一窗口不增加计数"""
        from mmfb.core.window_manager import get_window_manager
        mgr = get_window_manager()
        mock_win = MagicMock()
        mgr.register(mock_win)
        mgr.register(mock_win)
        self.assertEqual(mgr.count, 1)

    def test_unregister_removes_window(self):
        """注销窗口后 count 减少"""
        from mmfb.core.window_manager import get_window_manager
        mgr = get_window_manager()
        mock_win = MagicMock()
        mgr.register(mock_win)
        self.assertEqual(mgr.count, 1)
        mgr._unregister(mock_win)
        self.assertEqual(mgr.count, 0)

    def test_windows_property_returns_copy(self):
        """windows 返回副本，修改不影响内部列表"""
        from mmfb.core.window_manager import get_window_manager
        mgr = get_window_manager()
        mock_win = MagicMock()
        mgr.register(mock_win)
        wins = mgr.windows
        wins.clear()
        self.assertEqual(mgr.count, 1)

    def test_active_window_returns_active(self):
        """active_window 返回 isActiveWindow() 为 True 的窗口"""
        from mmfb.core.window_manager import get_window_manager
        mgr = get_window_manager()
        mock_win1 = MagicMock()
        mock_win1.isActiveWindow.return_value = False
        mock_win2 = MagicMock()
        mock_win2.isActiveWindow.return_value = True
        mgr.register(mock_win1)
        mgr.register(mock_win2)
        self.assertIs(mgr.active_window(), mock_win2)

    def test_active_window_fallback_to_first(self):
        """没有活跃窗口时返回首个"""
        from mmfb.core.window_manager import get_window_manager
        mgr = get_window_manager()
        mock_win = MagicMock()
        mock_win.isActiveWindow.return_value = False
        mgr.register(mock_win)
        self.assertIs(mgr.active_window(), mock_win)

    def test_active_window_none_when_empty(self):
        """空列表时返回 None"""
        from mmfb.core.window_manager import get_window_manager
        mgr = get_window_manager()
        self.assertIsNone(mgr.active_window())

    def test_close_all_calls_close_on_each(self):
        """close_all 调用每个窗口的 close()"""
        from mmfb.core.window_manager import get_window_manager
        mgr = get_window_manager()
        mock_win1 = MagicMock()
        mock_win2 = MagicMock()
        mgr.register(mock_win1)
        mgr.register(mock_win2)
        mgr.close_all()
        mock_win1.close.assert_called_once()
        mock_win2.close.assert_called_once()

    def test_shutdown_clears_list(self):
        """shutdown 清空列表"""
        from mmfb.core.window_manager import get_window_manager
        mgr = get_window_manager()
        mock_win = MagicMock()
        mgr.register(mock_win)
        self.assertEqual(mgr.count, 1)
        mgr.shutdown()
        self.assertEqual(mgr.count, 0)


class TestDestroySignalIntegration(unittest.TestCase):
    """窗口 destroyed 信号与 manager 清理集成测试"""

    def setUp(self):
        import mmfb.core.window_manager as wm
        wm._instance = None

    def tearDown(self):
        import mmfb.core.window_manager as wm
        wm._instance = None

    def test_on_destroyed_unregisters(self):
        """验证 MainWindow._on_destroyed 调用 manager._unregister"""
        from mmfb.core.window_manager import get_window_manager

        mgr = get_window_manager()
        mock_win = MagicMock()
        mock_win.isActiveWindow.return_value = False
        mock_win._window_manager = mgr

        # 将 MainWindow 的 _on_destroyed 方法绑定到 mock 上
        from mmfb.core.window import MainWindow
        mock_win._on_destroyed = MainWindow._on_destroyed.__get__(mock_win, MagicMock)

        mgr.register(mock_win)
        self.assertEqual(mgr.count, 1)

        mock_win._on_destroyed(None)
        self.assertEqual(mgr.count, 0)


if __name__ == '__main__':
    unittest.main()
