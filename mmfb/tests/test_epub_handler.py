"""EpubHandler 测试用例

测试 EPUB 电子书解析功能。
"""
import os
import sys
import json
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mmfb.handlers.epub_handler import EpubHandler, EBOOKLIB_AVAILABLE


@unittest.skipIf(not EBOOKLIB_AVAILABLE, "ebooklib not installed")
class TestEpubHandlerPreview(unittest.TestCase):
    """EpubHandler.get_preview() 测试"""

    def _create_simple_epub(self, title="Test Book", author="Test Author", chapters=None):
        """创建一个简单的 EPUB 文件（使用 ebooklib）"""
        from ebooklib import epub

        if chapters is None:
            chapters = [
                ("Chapter 1", "<html><body><h1>Chapter 1</h1><p>This is chapter 1.</p></body></html>"),
                ("Chapter 2", "<html><body><h1>Chapter 2</h1><p>This is chapter 2.</p></body></html>"),
            ]

        book = epub.EpubBook()
        book.set_title(title)
        book.add_author(author)
        book.set_language("en")

        # 添加章节
        epub_items = []
        for idx, (chapter_title, html_content) in enumerate(chapters):
            chapter = epub.EpubHtml(title=chapter_title, file_name=f'chap_{idx+1}.xhtml', content=html_content)
            book.add_item(chapter)
            epub_items.append(chapter)

        # 构建 TOC（Link 对象列表）
        book.toc = []
        for ch in epub_items:
            link = epub.Link(ch.title, ch.file_name)
            book.toc.append((link, []))  # 叶子节点，无子章节

        # 添加导航项
        book.add_item(epub.EpubNav())

        # 书籍脊柱（阅读顺序）
        book.spine = ['nav'] + epub_items

        # 写入文件
        fd, path = tempfile.mkstemp(suffix=".epub")
        os.close(fd)
        epub.write_epub(path, book, {})
        return path

    def test_basic_preview_returns_dict(self):
        """EPUB 预览应返回字典"""
        path = self._create_simple_epub()
        try:
            handler = EpubHandler(path)
            result = handler.get_preview()
            self.assertIsNotNone(result)
            self.assertIsInstance(result, dict)
            self.assertEqual(result["mime"], "application/epub+zip")
            self.assertEqual(result["template"], "epub")
            self.assertFalse(result["editable"])
        finally:
            os.unlink(path)

    def test_metadata_extracted(self):
        """应提取书名和作者"""
        path = self._create_simple_epub(title="我的测试书", author="张三")
        try:
            handler = EpubHandler(path)
            result = handler.get_preview()
            data = result["data"]
            self.assertEqual(data["title"], "我的测试书")
            self.assertEqual(data["author"], "张三")
        finally:
            os.unlink(path)

    def test_toc_structure(self):
        """目录应包含章节条目"""
        path = self._create_simple_epub(chapters=[
            ("第一章", "<html><body><h1>一</h1></body></html>"),
            ("第二章", "<html><body><h1>二</h1></body></html>"),
        ])
        try:
            handler = EpubHandler(path)
            result = handler.get_preview()
            toc = result["data"]["toc"]
            self.assertIsInstance(toc, list)
            self.assertGreaterEqual(len(toc), 2)
            # 检查每个条目有 title 和 href
            for entry in toc:
                self.assertIn("title", entry)
                self.assertIn("href", entry)
        finally:
            os.unlink(path)

    def test_html_content_contains_chapters(self):
        """合并的 HTML 内容应包含章节"""
        path = self._create_simple_epub(chapters=[
            ("A", "<html><body><h1>A</h1></body></html>"),
            ("B", "<html><body><h1>B</h1></body></html>"),
        ])
        try:
            handler = EpubHandler(path)
            result = handler.get_preview()
            html = result["data"]["html_content"]
            self.assertIn("<!DOCTYPE html>", html)
            self.assertIn("epub-toc", html)
            self.assertIn("epub-chapter", html)
        finally:
            os.unlink(path)

    def test_nonexistent_file_returns_error(self):
        """不存在的 EPUB 应返回错误"""
        handler = EpubHandler("/tmp/not_exists.epub")
        result = handler.get_preview()
        self.assertIn("error", result)
        self.assertEqual(result["data"]["html_content"], "")

    def test_invalid_epub_returns_error(self):
        """无效 EPUB 文件应返回错误信息"""
        # 创建一个普通文本文件但命名为 .epub
        fd, path = tempfile.mkstemp(suffix=".epub")
        os.write(fd, b"Not an EPUB")
        os.close(fd)
        try:
            handler = EpubHandler(path)
            result = handler.get_preview()
            self.assertIn("error", result)
            self.assertIsNotNone(result["error"])  # should have error message
        finally:
            os.unlink(path)


class TestEpubHandlerCanHandle(unittest.TestCase):
    """EpubHandler.can_handle() 测试"""

    def test_can_handle_epub(self):
        self.assertTrue(EpubHandler.can_handle("book.epub"))

    def test_cannot_handle_pdf(self):
        self.assertFalse(EpubHandler.can_handle("doc.pdf"))

    def test_cannot_handle_txt(self):
        self.assertFalse(EpubHandler.can_handle("notes.txt"))


class TestEpubHandlerExtensions(unittest.TestCase):
    """extensions 类属性测试"""

    def test_epub_in_extensions(self):
        self.assertIn(".epub", EpubHandler.extensions)

    def test_extensions_lowercase(self):
        for ext in EpubHandler.extensions:
            self.assertEqual(ext, ext.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
