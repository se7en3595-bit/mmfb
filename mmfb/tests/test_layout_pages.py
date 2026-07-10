# -*- coding: utf-8 -*-
"""前端 Layout / Pages / Router 集成测试

验证：
1. 前端文件结构齐全
2. index.html 引用了所有必要模块
3. bridge.py 已包含 open_file_dialog slot
"""
import os
import sys
import unittest

# __file__ = mmfb/tests/test_layout_pages.py
# 项目根 = tests/ 上一层 = mmfb/ 上一层 = 项目根
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
MMFB_DIR = os.path.dirname(TESTS_DIR)
PROJECT_ROOT = os.path.dirname(MMFB_DIR)
FRONTEND_DIR = os.path.join(MMFB_DIR, 'frontend')
CORE_DIR = os.path.join(MMFB_DIR, 'core')


class TestFrontendFilesExist(unittest.TestCase):
    """验证前端文件结构完整"""

    def test_index_html_exists(self):
        self.assertTrue(os.path.exists(os.path.join(FRONTEND_DIR, 'index.html')))

    def test_layout_css_exists(self):
        self.assertTrue(os.path.exists(os.path.join(FRONTEND_DIR, 'css', 'layout.css')))

    def test_layout_js_exists(self):
        self.assertTrue(os.path.exists(os.path.join(FRONTEND_DIR, 'js', 'layout.js')))

    def test_pages_js_exists(self):
        self.assertTrue(os.path.exists(os.path.join(FRONTEND_DIR, 'js', 'pages.js')))

    def test_app_js_exists(self):
        self.assertTrue(os.path.exists(os.path.join(FRONTEND_DIR, 'js', 'app.js')))

    def test_router_js_exists(self):
        self.assertTrue(os.path.exists(os.path.join(FRONTEND_DIR, 'js', 'router.js')))

    def test_bridge_js_exists(self):
        self.assertTrue(os.path.exists(os.path.join(FRONTEND_DIR, 'js', 'bridge.js')))

    def test_navigator_js_exists(self):
        self.assertTrue(os.path.exists(os.path.join(FRONTEND_DIR, 'js', 'navigator.js')))


class TestIndexHtmlContent(unittest.TestCase):
    """验证 index.html 引用了所有必要模块"""

    def setUp(self):
        with open(os.path.join(FRONTEND_DIR, 'index.html'), 'r', encoding='utf-8') as f:
            self.html = f.read()

    def test_has_layout_css(self):
        self.assertIn('css/layout.css', self.html)

    def test_has_layout_js(self):
        self.assertIn('js/layout.js', self.html)

    def test_has_pages_js(self):
        self.assertIn('js/pages.js', self.html)

    def test_has_router_js(self):
        self.assertIn('js/router.js', self.html)

    def test_has_app_js(self):
        self.assertIn('js/app.js', self.html)

    def test_has_router_view(self):
        self.assertIn('id="router-view"', self.html)

    def test_has_navigator_js(self):
        self.assertIn('js/navigator.js', self.html)


class TestBridgePyHasOpenFileDialog(unittest.TestCase):
    """验证 bridge.py 已包含 open_file_dialog slot"""

    def setUp(self):
        with open(os.path.join(CORE_DIR, 'bridge.py'), 'r', encoding='utf-8') as f:
            self.src = f.read()

    def test_has_open_file_dialog(self):
        self.assertIn('open_file_dialog', self.src)

    def test_has_dialog_parent(self):
        self.assertIn('set_dialog_parent', self.src)

    def test_has_qfiledialog_import(self):
        self.assertIn('QFileDialog', self.src)


class TestLayoutJsExportsAPI(unittest.TestCase):
    """验证 layout.js 导出了预期的 API"""

    def setUp(self):
        with open(os.path.join(FRONTEND_DIR, 'js', 'layout.js'), 'r', encoding='utf-8') as f:
            self.src = f.read()

    def test_has_init(self):
        self.assertIn('init:', self.src)

    def test_has_set_title(self):
        self.assertIn('setTitle:', self.src)

    def test_has_set_footer_left(self):
        self.assertIn('setFooterLeft:', self.src)

    def test_has_set_active_route(self):
        self.assertIn('setActiveRoute:', self.src)


class TestPagesJsExportsAPI(unittest.TestCase):
    """验证 pages.js 导出了预期的页面组件"""

    def setUp(self):
        with open(os.path.join(FRONTEND_DIR, 'js', 'pages.js'), 'r', encoding='utf-8') as f:
            self.src = f.read()

    def test_has_home(self):
        self.assertIn('home:', self.src)

    def test_has_view(self):
        self.assertIn('view:', self.src)

    def test_has_settings(self):
        self.assertIn('settings:', self.src)

    def test_has_about(self):
        self.assertIn('about:', self.src)

    def test_has_not_found(self):
        self.assertIn('notFound:', self.src)


if __name__ == '__main__':
    unittest.main()
