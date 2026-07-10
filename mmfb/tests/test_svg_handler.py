"""SVG Handler 单元测试"""

import os
import tempfile
import unittest
from pathlib import Path

from mmfb.core.handler_base import BaseHandler
from mmfb.core.registry import registry
from mmfb.handlers.svg_handler import SvgHandler, rasterize_to_png, SVG_EXTENSIONS


class TestSvgHandler(unittest.TestCase):
    """SVG 处理器测试套件"""

    @classmethod
    def setUpClass(cls):
        """测试前注册 Handler"""
        registry.register_class(SvgHandler)

    def test_extensions_contains_svg_and_svgz(self):
        """扩展名列表包含 svg 和 svgz"""
        self.assertIn('.svg', SVG_EXTENSIONS)
        self.assertIn('.svgz', SVG_EXTENSIONS)

    def test_registry_matches_svg(self):
        """注册表能识别 .svg 文件"""
        handler = registry.get_handler("dummy.svg")
        self.assertIsNotNone(handler)
        self.assertIsInstance(handler, SvgHandler)

    def test_registry_matches_svgz_case_insensitive(self):
        """大小写不敏感匹配 .svgz"""
        handler = registry.get_handler("dummy.SVGZ")
        self.assertIsNotNone(handler)
        self.assertIsInstance(handler, SvgHandler)

    def test_mime_type(self):
        """SvgHandler 声明的 MIME 类型正确"""
        self.assertEqual(SvgHandler.mime, "image/svg+xml")

    def test_preview_returns_expected_structure(self):
        """preview 返回包含 content, width, height, viewBox"""
        svg_content = '''<?xml version="1.0"?>
<svg width="100" height="50" viewBox="0 0 100 50" xmlns="http://www.w3.org/2000/svg">
  <rect width="100" height="50" fill="red"/>
</svg>'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False, encoding='utf-8') as f:
            f.write(svg_content)
            tmp_path = f.name

        try:
            handler = SvgHandler(tmp_path)
            preview = handler.get_preview()
            self.assertIsNotNone(preview)
            self.assertEqual(preview['mime'], 'image/svg+xml')
            self.assertEqual(preview['template'], 'svg')
            data = preview['data']
            self.assertIn('content', data)
            self.assertIn('width', data)
            self.assertIn('height', data)
            self.assertIn('viewBox', data)
            self.assertEqual(data['width'], 100)
            self.assertEqual(data['height'], 50)
            self.assertEqual(data['is_compressed'], False)
            self.assertTrue(data['file_size'] > 0)
        finally:
            os.unlink(tmp_path)

    def test_preview_svgz_gzip_detected(self):
        """.svgz 文件标记 is_compressed=True"""
        svg_content = b'''<?xml version="1.0"?>
<svg width="10" height="10" xmlns="http://www.w3.org/2000/svg">
  <circle cx="5" cy="5" r="5" fill="blue"/>
</svg>'''
        import gzip
        compressed = gzip.compress(svg_content)

        with tempfile.NamedTemporaryFile(suffix='.svgz', delete=False) as f:
            f.write(compressed)
            tmp_path = f.name

        try:
            handler = SvgHandler(tmp_path)
            preview = handler.get_preview()
            self.assertIsNotNone(preview)
            self.assertTrue(preview['data']['is_compressed'])
        finally:
            os.unlink(tmp_path)

    def test_edit_returns_save_flag(self):
        """edit 模式返回可保存数据"""
        svg_content = '<svg width="10" height="10"></svg>'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False, encoding='utf-8') as f:
            f.write(svg_content)
            tmp_path = f.name

        try:
            handler = SvgHandler(tmp_path)
            edit = handler.get_edit()
            self.assertIsNotNone(edit)
            self.assertIn('data', edit)
            self.assertTrue(edit['data'].get('save', False))
            self.assertEqual(edit['data']['content'], svg_content)
        finally:
            os.unlink(tmp_path)

    def test_preview_file_not_found(self):
        """文件不存在时返回错误"""
        handler = SvgHandler("nonexistent.svg")
        preview = handler.get_preview()
        self.assertIsNotNone(preview)
        self.assertIn('error', preview)

    def test_rasterize_to_png_basic(self):
        """rasterize_to_png 基本功能（如果 QtSvg 可用）"""
        svg_content = '''<svg width="64" height="64" xmlns="http://www.w3.org/2000/svg">
  <rect width="64" height="64" fill="green"/>
</svg>'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False, encoding='utf-8') as f:
            f.write(svg_content)
            src_path = f.name

        dst_path = tempfile.NamedTemporaryFile(suffix='.png', delete=False).name

        try:
            result = rasterize_to_png(src_path, dst_path)
            self.assertTrue(result['ok'])
            self.assertTrue(os.path.isfile(dst_path))
            self.assertEqual(result['width'], 64)
            self.assertEqual(result['height'], 64)
        except ImportError as e:
            if 'QtSvg' in str(e) or 'PySide6' in str(e):
                self.skipTest(f"QtSvg 不可用: {e}")
            else:
                raise
        finally:
            try:
                os.unlink(src_path)
                os.unlink(dst_path)
            except OSError:
                pass

    def test_rasterize_to_png_custom_size(self):
        """指定宽高栅格化"""
        svg_content = '''<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <circle cx="50" cy="50" r="50" fill="red"/>
</svg>'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False, encoding='utf-8') as f:
            f.write(svg_content)
            src_path = f.name

        dst_path = tempfile.NamedTemporaryFile(suffix='.png', delete=False).name

        try:
            result = rasterize_to_png(src_path, dst_path, width=200, height=150)
            self.assertTrue(result['ok'])
            self.assertEqual(result['width'], 200)
            self.assertEqual(result['height'], 150)
        except ImportError as e:
            if 'QtSvg' in str(e) or 'PySide6' in str(e):
                self.skipTest(f"QtSvg 不可用: {e}")
            else:
                raise
        finally:
            try:
                os.unlink(src_path)
                os.unlink(dst_path)
            except OSError:
                pass

    def test_rasterize_to_png_invalid_svg(self):
        """无效 SVG 文件返回错误"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False, encoding='utf-8') as f:
            f.write("not valid svg content")
            src_path = f.name

        dst_path = tempfile.NamedTemporaryFile(suffix='.png', delete=False).name

        try:
            result = rasterize_to_png(src_path, dst_path)
            self.assertFalse(result['ok'])
            self.assertIn('error', result)
        finally:
            try:
                os.unlink(src_path)
                os.unlink(dst_path)
            except OSError:
                pass


if __name__ == '__main__':
    unittest.main()
