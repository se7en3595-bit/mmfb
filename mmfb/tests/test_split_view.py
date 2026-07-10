"""测试 SplitView 分屏容器

验证：
  1. 创建 SplitView 后左右 webview 都存在
  2. set_split_ratio 限制在 10~90 范围内
  3. current_ratio 返回合理值
  4. destroy 清理资源
"""
import sys
import unittest
from unittest.mock import MagicMock, patch


# 需要 QApplication 才能创建 QWidget 子类
class _TestBase(unittest.TestCase):
    """基类：确保 QApplication 存在"""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        if QApplication.instance() is None:
            cls._app = QApplication([sys.argv[0]])
        else:
            cls._app = QApplication.instance()

    def _make_parent(self):
        """创建一个真实的 QWidget 作为 parent"""
        from PySide6.QtWidgets import QWidget
        return QWidget()


class TestSplitViewCreation(_TestBase):
    """SplitView 创建测试"""

    def test_create_split_view_has_views(self):
        """创建 SplitView 后 left_view 和 right_view 存在"""
        from mmfb.core.split_view import SplitView

        parent = self._make_parent()
        view = SplitView(parent)
        self.assertIsNotNone(view.left_view)
        self.assertIsNotNone(view.right_view)
        view.destroy()

    def test_split_view_default_ratio(self):
        """初始比例为 50:50"""
        from mmfb.core.split_view import SplitView

        parent = self._make_parent()
        view = SplitView(parent)
        ratio = view.current_ratio()
        self.assertEqual(ratio, 50)
        view.destroy()

    def test_split_view_has_splitter(self):
        """SplitView 包含 QSplitter"""
        from mmfb.core.split_view import SplitView

        parent = self._make_parent()
        view = SplitView(parent)
        self.assertIsNotNone(view._splitter)
        view.destroy()

    def test_split_view_has_two_widgets_in_splitter(self):
        """Splitter 中有两个 widget"""
        from mmfb.core.split_view import SplitView

        parent = self._make_parent()
        view = SplitView(parent)
        self.assertEqual(view._splitter.count(), 2)
        view.destroy()


class TestSplitViewRatio(_TestBase):
    """分屏比例测试"""

    def setUp(self):
        from mmfb.core.split_view import SplitView
        self.parent = self._make_parent()
        self.view = SplitView(self.parent)

    def tearDown(self):
        self.view.destroy()

    def test_set_split_ratio_30(self):
        """设置 30% 左栏比例"""
        self.view.set_split_ratio(30)
        ratio = self.view.current_ratio()
        # 整数除法可能有 +/-1 的舍入误差
        self.assertAlmostEqual(ratio, 30, delta=2)

    def test_set_split_ratio_clamped_max(self):
        """高于 90 的比例被限制为 90"""
        self.view.set_split_ratio(100)
        ratio = self.view.current_ratio()
        self.assertAlmostEqual(ratio, 90, delta=2)

    def test_set_split_ratio_clamped_min(self):
        """低于 10 的比例被限制为 10"""
        self.view.set_split_ratio(0)
        ratio = self.view.current_ratio()
        self.assertAlmostEqual(ratio, 10, delta=2)

    def test_set_split_ratio_negative(self):
        """负数比例被限制为 10"""
        self.view.set_split_ratio(-50)
        ratio = self.view.current_ratio()
        self.assertAlmostEqual(ratio, 10, delta=2)

    def test_set_split_ratio_over_100(self):
        """超过 100 的比例被限制为 90"""
        self.view.set_split_ratio(200)
        ratio = self.view.current_ratio()
        self.assertAlmostEqual(ratio, 90, delta=2)

    def test_set_split_ratio_exact_boundary(self):
        """边界值 10 和 90 正常通过"""
        self.view.set_split_ratio(10)
        ratio = self.view.current_ratio()
        self.assertAlmostEqual(ratio, 10, delta=2)

        self.view.set_split_ratio(90)
        ratio = self.view.current_ratio()
        self.assertAlmostEqual(ratio, 90, delta=2)


class TestSplitViewDestroy(_TestBase):
    """SplitView 资源清理测试"""

    def test_destroy_does_not_crash(self):
        """destroy 不抛出异常"""
        from mmfb.core.split_view import SplitView

        parent = self._make_parent()
        view = SplitView(parent)
        # 不应抛出异常
        view.destroy()

    def test_destroy_after_set_ratio(self):
        """设置比例后 destroy 不崩溃"""
        from mmfb.core.split_view import SplitView

        parent = self._make_parent()
        view = SplitView(parent)
        view.set_split_ratio(30)
        view.destroy()  # 不应崩溃


if __name__ == '__main__':
    unittest.main()
