"""HtmlHandler 测试用例

测试 HtmlHandler 的 get_preview / get_edit 输出结构，
以及扩展名匹配、边界场景、安全属性。

不依赖 PySide6 QApplication，仅测试纯 Python 逻辑。
"""
import os
import sys
import json
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mmfb.handlers.html_handler import HtmlHandler


class TestHtmlHandlerPreview(unittest.TestCase):
    """HtmlHandler.get_preview() 测试"""

    def _write_temp_html(self, content, suffix=".html"):
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, delete=False, encoding="utf-8", newline=""
        )
        f.write(content)
        f.close()
        return f.name

    def test_basic_preview_returns_dict(self):
        path = self._write_temp_html("<html><body>Hello</body></html>")
        try:
            handler = HtmlHandler(path)
            result = handler.get_preview()

            self.assertIsNotNone(result)
            self.assertIsInstance(result, dict)
            self.assertEqual(result["mime"], "text/html")
            self.assertEqual(result["template"], "html")
            self.assertTrue(result["editable"])
        finally:
            os.unlink(path)

    def test_preview_content_matches_file(self):
        content = "<!DOCTYPE html>\n<html><head><title>T</title></head><body>Hi</body></html>"
        path = self._write_temp_html(content)
        try:
            handler = HtmlHandler(path)
            result = handler.get_preview()

            self.assertEqual(result["data"]["content"], content)
            self.assertEqual(result["data"]["file_path"], os.path.abspath(path))
            self.assertGreater(result["data"]["file_size"], 0)
        finally:
            os.unlink(path)

    def test_line_count(self):
        content = "<html>\n<body>\n<p>line</p>\n</body>\n</html>\n"
        path = self._write_temp_html(content)
        try:
            handler = HtmlHandler(path)
            result = handler.get_preview()
            self.assertEqual(result["data"]["line_count"], 5)
        finally:
            os.unlink(path)

    def test_nonexistent_file_returns_error(self):
        handler = HtmlHandler("/tmp/this_does_not_exist_9999.html")
        result = handler.get_preview()

        self.assertIsNotNone(result)
        self.assertIn("error", result)
        self.assertEqual(result["data"]["content"], "")

    def test_empty_file(self):
        path = self._write_temp_html("")
        try:
            handler = HtmlHandler(path)
            result = handler.get_preview()

            self.assertEqual(result["data"]["content"], "")
            self.assertEqual(result["data"]["line_count"], 0)
            self.assertNotIn("error", result)
        finally:
            os.unlink(path)

    def test_utf8_multibyte_content(self):
        content = "<html><body><h1>标题</h1><p>中文内容</p></body></html>"
        path = self._write_temp_html(content)
        try:
            handler = HtmlHandler(path)
            result = handler.get_preview()
            self.assertEqual(result["data"]["content"], content)
        finally:
            os.unlink(path)

    def test_htm_extension(self):
        path = self._write_temp_html("<html>ok</html>", suffix=".htm")
        try:
            handler = HtmlHandler(path)
            result = handler.get_preview()
            self.assertEqual(result["mime"], "text/html")
        finally:
            os.unlink(path)


class TestHtmlHandlerCanHandle(unittest.TestCase):
    """HtmlHandler.can_handle() 类方法测试"""

    def test_can_handle_html(self):
        self.assertTrue(HtmlHandler.can_handle("test.html"))

    def test_can_handle_htm(self):
        self.assertTrue(HtmlHandler.can_handle("test.htm"))

    def test_can_handle_uppercase(self):
        self.assertTrue(HtmlHandler.can_handle("test.HTML"))

    def test_can_handle_mixed_case(self):
        self.assertTrue(HtmlHandler.can_handle("test.HtMl"))

    def test_cannot_handle_md(self):
        self.assertFalse(HtmlHandler.can_handle("test.md"))

    def test_cannot_handle_pdf(self):
        self.assertFalse(HtmlHandler.can_handle("test.pdf"))

    def test_cannot_handle_txt(self):
        self.assertFalse(HtmlHandler.can_handle("test.txt"))


class TestHtmlHandlerGetEdit(unittest.TestCase):
    """HtmlHandler.get_edit() 测试"""

    def test_get_edit_returns_dict_with_save(self):
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8", newline=""
        )
        f.write("<html>edit</html>")
        f.close()

        try:
            handler = HtmlHandler(f.name)
            edit_data = handler.get_edit()

            self.assertIsNotNone(edit_data)
            self.assertTrue(edit_data["data"]["save"])
            self.assertEqual(edit_data["data"]["mime"], "text/html")
        finally:
            os.unlink(f.name)

    def test_supports_editing_returns_true(self):
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8", newline=""
        )
        f.write("<html>x</html>")
        f.close()

        try:
            handler = HtmlHandler(f.name)
            self.assertTrue(handler.supports_editing())
        finally:
            os.unlink(f.name)


class TestHtmlHandlerExtensions(unittest.TestCase):
    """extensions 类属性测试"""

    def test_extensions_list_not_empty(self):
        self.assertTrue(len(HtmlHandler.extensions) > 0)

    def test_extensions_start_with_dot(self):
        for ext in HtmlHandler.extensions:
            self.assertTrue(ext.startswith("."))

    def test_extensions_lowercase(self):
        for ext in HtmlHandler.extensions:
            self.assertEqual(ext, ext.lower())

    def test_html_in_extensions(self):
        self.assertIn(".html", HtmlHandler.extensions)

    def test_htm_in_extensions(self):
        self.assertIn(".htm", HtmlHandler.extensions)


class TestHtmlHandlerGetMime(unittest.TestCase):
    """get_mime() 测试"""

    def test_get_mime_returns_string(self):
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8", newline=""
        )
        f.write("<html>test</html>")
        f.close()

        try:
            handler = HtmlHandler(f.name)
            mime = handler.get_mime()
            self.assertIsInstance(mime, str)
            self.assertTrue(len(mime) > 0)
        finally:
            os.unlink(f.name)


class TestHtmlHandlerRegistry(unittest.TestCase):
    """验证 HtmlHandler 正确注册到全局 registry"""

    def setUp(self):
        # 重建全局注册表（抵消其他测试文件的 registry.clear() 影响）
        from mmfb.core.registry import registry
        registry.clear()
        import mmfb.handlers as h
        import importlib
        importlib.reload(h)

    def test_registry_can_dispatch_html(self):
        from mmfb.core.registry import registry
        handler = registry.get_handler("test.html")
        self.assertIsNotNone(handler)
        self.assertIsInstance(handler, HtmlHandler)

    def test_registry_can_dispatch_htm(self):
        from mmfb.core.registry import registry
        handler = registry.get_handler("test.htm")
        self.assertIsNotNone(handler)
        self.assertIsInstance(handler, HtmlHandler)


if __name__ == "__main__":
    unittest.main(verbosity=2)
