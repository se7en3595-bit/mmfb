"""TextHandler 测试用例

测试纯文本处理器的功能，包括编码探测、预览、编辑支持等。
"""
import os
import sys
import json
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mmfb.handlers.text_handler import TextHandler


class TestTextHandlerPreview(unittest.TestCase):
    """TextHandler.get_preview() 测试"""

    def _write_temp_text(self, content, suffix=".txt", encoding="utf-8"):
        """写入临时文本文件"""
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, delete=False, encoding=encoding, newline=""
        )
        f.write(content)
        f.close()
        return f.name

    def _write_temp_bytes(self, content_bytes, suffix=".txt"):
        """写入临时二进制文件（任意编码）"""
        f = tempfile.NamedTemporaryFile(
            mode="wb", suffix=suffix, delete=False
        )
        f.write(content_bytes)
        f.close()
        return f.name

    def test_basic_preview_returns_dict(self):
        """基础预览应返回字典"""
        path = self._write_temp_text("Hello World")
        try:
            handler = TextHandler(path)
            result = handler.get_preview()

            self.assertIsNotNone(result)
            self.assertIsInstance(result, dict)
            self.assertEqual(result["mime"], "text/plain")
            self.assertEqual(result["template"], "text")
            self.assertTrue(result["editable"])
        finally:
            os.unlink(path)

    def test_preview_content_matches_file(self):
        """预览内容应与原文件一致"""
        content = "第一行\n第二行\n第三行\n"
        path = self._write_temp_text(content)
        try:
            handler = TextHandler(path)
            result = handler.get_preview()
            self.assertEqual(result["data"]["content"], content)
            self.assertEqual(result["data"]["file_path"], os.path.abspath(path))
            self.assertGreater(result["data"]["file_size"], 0)
        finally:
            os.unlink(path)

    def test_line_count(self):
        """行数统计应正确"""
        content = "line1\nline2\nline3\n"
        path = self._write_temp_text(content)
        try:
            handler = TextHandler(path)
            result = handler.get_preview()
            self.assertEqual(result["data"]["line_count"], 3)
        finally:
            os.unlink(path)

    def test_nonexistent_file_returns_error(self):
        """不存在的文件应在 error 字段标识"""
        handler = TextHandler("/tmp/this_does_not_exist_9999.txt")
        result = handler.get_preview()
        self.assertIsNotNone(result)
        self.assertIn("error", result)
        self.assertEqual(result["data"]["content"], "")

    def test_empty_file(self):
        """空文件应返回空内容"""
        path = self._write_temp_text("")
        try:
            handler = TextHandler(path)
            result = handler.get_preview()
            self.assertEqual(result["data"]["content"], "")
            self.assertEqual(result["data"]["line_count"], 0)
            self.assertNotIn("error", result)
        finally:
            os.unlink(path)

    def test_utf8_encoding(self):
        """UTF-8 编码应正确探测"""
        content = "中文、English、123\n新行\n"
        path = self._write_temp_text(content)
        try:
            handler = TextHandler(path)
            result = handler.get_preview()
            self.assertEqual(result["data"]["content"], content)
            self.assertEqual(result["data"]["encoding"], "utf-8")
        finally:
            os.unlink(path)

    def test_gbk_encoding_detection(self):
        """GBK 编码应被探测"""
        content_gbk = "中文内容\n第二行\n".encode("gbk")
        path = self._write_temp_bytes(content_gbk)
        try:
            handler = TextHandler(path)
            result = handler.get_preview()
            self.assertIn("中文", result["data"]["content"])
            self.assertIn(result["data"]["encoding"], ["gbk", "gb18030"])
        finally:
            os.unlink(path)

    def test_latin1_encoding(self):
        """Latin-1 编码被测为 'iso-8859-1' 或类似"""
        content_bytes = b"caf\xe9\n"  # café in latin1
        path = self._write_temp_bytes(content_bytes)
        try:
            handler = TextHandler(path)
            result = handler.get_preview()
            self.assertIn("caf", result["data"]["content"])
        finally:
            os.unlink(path)

    def test_ini_extension_support(self):
        """.ini 扩展名应被支持"""
        path = self._write_temp_text("[section]\nkey=value\n", suffix=".ini")
        try:
            handler = TextHandler(path)
            result = handler.get_preview()
            self.assertTrue(result)
            self.assertIn("key=value", result["data"]["content"])
        finally:
            os.unlink(path)

    def test_cfg_extension_support(self):
        """.cfg 扩展名应被支持"""
        path = self._write_temp_text("option=yes\n", suffix=".cfg")
        try:
            handler = TextHandler(path)
            result = handler.get_preview()
            self.assertTrue(result)
        finally:
            os.unlink(path)

    def test_log_extension_support(self):
        """.log 扩展名应被支持"""
        path = self._write_temp_text("2024-01-01 12:00:00 INFO Start\n", suffix=".log")
        try:
            handler = TextHandler(path)
            result = handler.get_preview()
            self.assertTrue(result)
        finally:
            os.unlink(path)


class TestTextHandlerCanHandle(unittest.TestCase):
    """TextHandler.can_handle() 类方法测试"""

    def test_can_handle_txt(self):
        self.assertTrue(TextHandler.can_handle("notes.txt"))

    def test_can_handle_TXT_case_insensitive(self):
        self.assertTrue(TextHandler.can_handle("notes.TXT"))

    def test_can_handle_log(self):
        self.assertTrue(TextHandler.can_handle("app.log"))

    def test_can_handle_ini(self):
        self.assertTrue(TextHandler.can_handle("config.ini"))

    def test_can_handle_cfg(self):
        self.assertTrue(TextHandler.can_handle("settings.cfg"))

    def test_cannot_handle_pdf(self):
        self.assertFalse(TextHandler.can_handle("doc.pdf"))

    def test_cannot_handle_jpg(self):
        self.assertFalse(TextHandler.can_handle("image.jpg"))


class TestTextHandlerGetEdit(unittest.TestCase):
    """TextHandler.get_edit() 测试"""

    def test_get_edit_returns_dict_with_save(self):
        """get_edit 应启用 save 标志"""
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8", newline=""
        )
        f.write("# Edit me")
        f.close()

        try:
            handler = TextHandler(f.name)
            edit_data = handler.get_edit()
            self.assertIsNotNone(edit_data)
            self.assertTrue(edit_data["data"]["save"])
            self.assertEqual(edit_data["data"]["mime"], "text/plain")
        finally:
            os.unlink(f.name)

    def test_supports_editing_returns_true(self):
        """supports_editing 应返回 True"""
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8", newline=""
        )
        f.write("content")
        f.close()

        try:
            handler = TextHandler(f.name)
            self.assertTrue(handler.supports_editing())
        finally:
            os.unlink(f.name)


class TestTextHandlerExtensions(unittest.TestCase):
    """extensions 类属性测试"""

    def test_extensions_list_not_empty(self):
        self.assertTrue(len(TextHandler.extensions) > 0)

    def test_extensions_start_with_dot(self):
        for ext in TextHandler.extensions:
            self.assertTrue(ext.startswith("."), f"extension {ext!r} does not start with .")

    def test_extensions_lowercase(self):
        for ext in TextHandler.extensions:
            self.assertEqual(ext, ext.lower(), f"extension {ext!r} is not lowercase")

    def test_txt_in_extensions(self):
        self.assertIn(".txt", TextHandler.extensions)

    def test_log_in_extensions(self):
        self.assertIn(".log", TextHandler.extensions)

    def test_ini_in_extensions(self):
        self.assertIn(".ini", TextHandler.extensions)

    def test_cfg_in_extensions(self):
        self.assertIn(".cfg", TextHandler.extensions)


class TestTextHandlerGetMime(unittest.TestCase):
    """get_mime() 测试"""

    def test_get_mime_returns_string(self):
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8", newline=""
        )
        f.write("test")
        f.close()

        try:
            handler = TextHandler(f.name)
            mime = handler.get_mime()
            self.assertIsInstance(mime, str)
            self.assertEqual(mime, "text/plain")
        finally:
            os.unlink(f.name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
