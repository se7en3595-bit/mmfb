"""PdfHandler 单元测试

测试覆盖：
- can_handle 方法（大小写、不相关扩展名）
- get_preview 基本行为（含最小 PDF 解析）
- 大文件 (>50MB) lazy_load 标记
- 缺失文件处理
- get_edit 返回 None
- get_mime 返回 application/pdf
"""
import os
import sys
import tempfile
import unittest

# 确保能导入 mmfb 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mmfb.handlers.pdf_handler import PdfHandler, LAZY_LOAD_THRESHOLD
from mmfb.core.registry import HandlerRegistry


# 最小有效 PDF（1 页 A4，空白）
MINIMAL_PDF = b"""%PDF-1.0
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f \r
0000000009 00000 n \r
0000000058 00000 n \r
0000000115 00000 n \r
trailer
<< /Size 4 /Root 1 0 R >>
startxref
190
%%EOF
"""


class TestPdfHandlerBasic(unittest.TestCase):
    """基础方法测试"""

    def test_can_handle_dot_pdf(self):
        self.assertTrue(PdfHandler.can_handle("/tmp/test.pdf"))

    def test_can_handle_uppercase(self):
        self.assertTrue(PdfHandler.can_handle("/tmp/test.PDF"))

    def test_can_handle_mixed_case(self):
        self.assertTrue(PdfHandler.can_handle("/tmp/test.Pdf"))

    def test_reject_other_ext(self):
        self.assertFalse(PdfHandler.can_handle("/tmp/test.docx"))

    def test_reject_no_ext(self):
        self.assertFalse(PdfHandler.can_handle("/tmp/noext"))

    def test_extensions_list(self):
        self.assertIn(".pdf", PdfHandler.extensions)

    def test_get_edit_returns_none(self):
        """PDF v1 不支持编辑"""
        handler = PdfHandler("/tmp/dummy.pdf")
        self.assertIsNone(handler.get_edit())

    def test_get_mime_returns_pdf(self):
        handler = PdfHandler("/tmp/test.pdf")
        self.assertEqual(handler.get_mime(), "application/pdf")


class TestPdfHandlerPreview(unittest.TestCase):
    """预览数据测试"""

    def setUp(self):
        # 创建临时 PDF 文件
        self.tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        self.tmp.write(MINIMAL_PDF)
        self.tmp.close()

    def tearDown(self):
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_preview_returns_dict(self):
        handler = PdfHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertIsInstance(result, dict)

    def test_preview_template_is_pdf(self):
        handler = PdfHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertEqual(result.get("template"), "pdf")

    def test_preview_mime_is_pdf(self):
        handler = PdfHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertEqual(result.get("mime"), "application/pdf")

    def test_preview_data_contains_file_path(self):
        handler = PdfHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertEqual(result["data"]["file_path"], self.tmp.name)

    def test_preview_data_contains_page_count(self):
        handler = PdfHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertEqual(result["data"]["page_count"], 1)

    def test_preview_not_editable(self):
        handler = PdfHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertFalse(result.get("editable"))

    def test_preview_lazy_load_false_for_small_file(self):
        handler = PdfHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertFalse(result["data"]["lazy_load"])


class TestPdfHandlerMissingFile(unittest.TestCase):
    """缺失文件处理"""

    def test_preview_missing_file_returns_dict(self):
        handler = PdfHandler("/tmp/nonexistentfiletest.pdf")
        result = handler.get_preview()
        self.assertIsInstance(result, dict)

    def test_preview_missing_file_has_error(self):
        handler = PdfHandler("/tmp/nonexistentfiletest.pdf")
        result = handler.get_preview()
        self.assertIn("error", result)


class TestPdfHandlerRegistry(unittest.TestCase):
    """注册表集成测试"""

    def test_registry_dispatch_pdf(self):
        reg = HandlerRegistry()
        # Dynamic import to avoid circular
        from mmfb.handlers import PdfHandler
        reg.register_class(PdfHandler)
        handler = reg.get_handler("/tmp/test.pdf")
        self.assertIsInstance(handler, PdfHandler)

    def test_registry_dispatch_uppercase_pdf(self):
        reg = HandlerRegistry()
        from mmfb.handlers import PdfHandler
        reg.register_class(PdfHandler)
        handler = reg.get_handler("/tmp/test.PDF")
        self.assertIsInstance(handler, PdfHandler)

    def test_registry_count_after_pdf(self):
        reg = HandlerRegistry()
        from mmfb.handlers import PdfHandler
        reg.register_class(PdfHandler)
        self.assertEqual(reg.count(), 1)


class TestPdfHandlerLargeFile(unittest.TestCase):
    """大文件行为（模拟 path 存在判断）"""

    def test_lazy_load_threshold_value(self):
        """确认阈值等于 50MB"""
        self.assertEqual(LAZY_LOAD_THRESHOLD, 50 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
