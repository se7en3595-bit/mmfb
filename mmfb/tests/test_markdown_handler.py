"""MarkdownHandler 测试用例

测试 MarkdownHandler 的 get_preview / get_edit 输出结构，
以及扩展名匹配、边界场景等。

不依赖 PySide6 QApplication，仅测试纯 Python 逻辑。
"""
import os
import sys
import json
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mmfb.handlers.markdown_handler import MarkdownHandler


class TestMarkdownHandlerPreview(unittest.TestCase):
    """MarkdownHandler.get_preview() 测试"""

    def _write_temp_md(self, content, suffix=".md"):
        """写入临时 Markdown 文件，返回路径（保留原始换行符，不转换 \n -> \r\n）"""
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, delete=False, encoding="utf-8", newline=""
        )
        f.write(content)
        f.close()
        return f.name

    def test_basic_preview_returns_dict(self):
        """基础预览应返回字典"""
        path = self._write_temp_md("# Hello\n\nWorld")
        try:
            handler = MarkdownHandler(path)
            result = handler.get_preview()

            self.assertIsNotNone(result)
            self.assertIsInstance(result, dict)
            self.assertEqual(result["mime"], "text/markdown")
            self.assertEqual(result["template"], "markdown")
            self.assertTrue(result["editable"])
        finally:
            os.unlink(path)

    def test_preview_content_matches_file(self):
        """预览数据中文件内容应与原文件一致"""
        content = "# Title\n\n- item1\n- item2\n\n```python\nprint(1)\n```\n"
        path = self._write_temp_md(content)
        try:
            handler = MarkdownHandler(path)
            result = handler.get_preview()

            self.assertEqual(result["data"]["content"], content)
            self.assertEqual(result["data"]["file_path"], os.path.abspath(path))
            self.assertGreater(result["data"]["file_size"], 0)
        finally:
            os.unlink(path)

    def test_line_count(self):
        """行数统计应正确"""
        content = "line1\nline2\nline3\n"
        path = self._write_temp_md(content)
        try:
            handler = MarkdownHandler(path)
            result = handler.get_preview()
            self.assertEqual(result["data"]["line_count"], 3)
        finally:
            os.unlink(path)

    def test_nonexistent_file_returns_error(self):
        """不存在的文件应在 error 字段标识"""
        handler = MarkdownHandler("/tmp/this_does_not_exist_9999.md")
        result = handler.get_preview()

        self.assertIsNotNone(result)
        self.assertIn("error", result)
        self.assertEqual(result["data"]["content"], "")

    def test_empty_file(self):
        """空文件应返回空内容"""
        path = self._write_temp_md("")
        try:
            handler = MarkdownHandler(path)
            result = handler.get_preview()

            self.assertEqual(result["data"]["content"], "")
            # 空文件结束符处理：无内容的文件行数为 0
            self.assertEqual(result["data"]["line_count"], 0)
            self.assertNotIn("error", result)
        finally:
            os.unlink(path)

    def test_utf8_multibyte_content(self):
        """含多字节字符的 Markdown 应正确读取"""
        content = "# 标题\n\n中文内容 **加粗** `代码`\n"
        path = self._write_temp_md(content)
        try:
            handler = MarkdownHandler(path)
            result = handler.get_preview()

            self.assertEqual(result["data"]["content"], content)
        finally:
            os.unlink(path)

    def test_markdown_extension_mdown(self):
        """扩展名 .mdown 应能被处理"""
        path = self._write_temp_md("# test", suffix=".mdown")
        try:
            handler = MarkdownHandler(path)
            result = handler.get_preview()
            self.assertEqual(result["mime"], "text/markdown")
        finally:
            os.unlink(path)

    def test_markdown_extension_markdown(self):
        """扩展名 .markdown 应能被处理"""
        path = self._write_temp_md("# test", suffix=".markdown")
        try:
            handler = MarkdownHandler(path)
            result = handler.get_preview()
            self.assertEqual(result["mime"], "text/markdown")
        finally:
            os.unlink(path)

    def test_markdown_extension_rmd(self):
        """扩展名 .rmd (R Markdown) 应能被处理"""
        path = self._write_temp_md("# R Markdown\n```{r}\n1+1\n```\n", suffix=".rmd")
        try:
            handler = MarkdownHandler(path)
            result = handler.get_preview()
            self.assertEqual(result["mime"], "text/markdown")
            self.assertIn("R Markdown", result["data"]["content"])
        finally:
            os.unlink(path)


class TestMarkdownHandlerCanHandle(unittest.TestCase):
    """MarkdownHandler.can_handle() 类方法测试"""

    def _write_temp(self, content, suffix):
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, delete=False, encoding="utf-8", newline=""
        )
        f.write(content)
        f.close()
        return f.name

    def test_can_handle_md(self):
        self.assertTrue(MarkdownHandler.can_handle("test.md"))

    def test_can_handle_uppercase(self):
        """大写扩展名 .MD 也应被支持"""
        self.assertTrue(MarkdownHandler.can_handle("test.MD"))

    def test_can_handle_mixed_case(self):
        """混合大小写 .Md 也应被支持"""
        self.assertTrue(MarkdownHandler.can_handle("test.Md"))

    def test_can_handle_markdown(self):
        self.assertTrue(MarkdownHandler.can_handle("readme.markdown"))

    def test_can_handle_mdown(self):
        self.assertTrue(MarkdownHandler.can_handle("doc.mdown"))

    def test_can_handle_rmd(self):
        self.assertTrue(MarkdownHandler.can_handle("analysis.rmd"))

    def test_cannot_handle_pdf(self):
        """PDF 不是 Markdown 支持的扩展名"""
        self.assertFalse(MarkdownHandler.can_handle("doc.pdf"))

    def test_cannot_handle_txt(self):
        """.txt 不在 Markdown 扩展名列表中"""
        self.assertFalse(MarkdownHandler.can_handle("notes.txt"))


class TestMarkdownHandlerGetEdit(unittest.TestCase):
    """MarkdownHandler.get_edit() 测试"""

    def test_get_edit_returns_dict_with_save(self):
        """get_edit 应启用 save 标志"""
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8", newline=""
        )
        f.write("# edit me")
        f.close()

        try:
            handler = MarkdownHandler(f.name)
            edit_data = handler.get_edit()

            self.assertIsNotNone(edit_data)
            self.assertTrue(edit_data["data"]["save"])
            self.assertEqual(edit_data["data"]["mime"], "text/markdown")
        finally:
            os.unlink(f.name)

    def test_supports_editing_returns_true(self):
        """supports_editing 应返回 True"""
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8", newline=""
        )
        f.write("content")
        f.close()

        try:
            handler = MarkdownHandler(f.name)
            self.assertTrue(handler.supports_editing())
        finally:
            os.unlink(f.name)


class TestMarkdownHandlerExtensions(unittest.TestCase):
    """extensions 类属性测试"""

    def test_extensions_list_not_empty(self):
        """extensions 列表应非空"""
        self.assertTrue(len(MarkdownHandler.extensions) > 0)

    def test_extensions_start_with_dot(self):
        """所有扩展名应以 . 开头"""
        for ext in MarkdownHandler.extensions:
            self.assertTrue(ext.startswith("."), f"extension {ext!r} does not start with .")

    def test_extensions_lowercase(self):
        """所有扩展名应为小写"""
        for ext in MarkdownHandler.extensions:
            self.assertEqual(ext, ext.lower(), f"extension {ext!r} is not lowercase")

    def test_md_in_extensions(self):
        """.md 应在 extensions 列表中"""
        self.assertIn(".md", MarkdownHandler.extensions)

    def test_markdown_in_extensions(self):
        """.markdown 应在 extensions 列表中"""
        self.assertIn(".markdown", MarkdownHandler.extensions)


class TestMarkdownHandlerGetMime(unittest.TestCase):
    """get_mime() 测试"""

    def test_get_mime_returns_string(self):
        """get_mime 应返回字符串"""
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8", newline=""
        )
        f.write("test")
        f.close()

        try:
            handler = MarkdownHandler(f.name)
            mime = handler.get_mime()
            self.assertIsInstance(mime, str)
            self.assertTrue(len(mime) > 0)
        finally:
            os.unlink(f.name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
