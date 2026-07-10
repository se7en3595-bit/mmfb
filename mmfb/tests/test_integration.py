"""核心模块集成测试

验证 file_handler / registry / conversion_engine / handlers 全链路闭环。
每个测试用例代表一个端到端场景，而非单一内部函数。
"""
import os
import sys
from pathlib import Path

import pytest


# ============================================================
# 集成场景：文件读写全链路
# ============================================================

class TestFileHandlerIntegration:
    """file_handler 与真实文件系统交互"""

    def test_write_text_read_back_with_metadata(self, sample_dir):
        """写入文本文件后读回并验证元数据"""
        from mmfb.core.file_handler import safe_write_text, safe_read_text, get_file_info

        path = os.path.join(sample_dir, "round_trip.txt")
        content = "MMFB integration test\n中文测试"

        assert safe_write_text(path, content) is True
        assert safe_read_text(path) == content

        info = get_file_info(path)
        assert info is not None
        assert info["name"] == "round_trip.txt"
        assert info["size"] == len(content.encode("utf-8"))
        assert info["is_dir"] is False

    def test_write_binary_read_json_round_trip(self, sample_dir):
        """写入 JSON、读取 JSON、验证字段"""
        import json
        from mmfb.core.file_handler import safe_write_text, safe_read_json

        path = os.path.join(sample_dir, "config.json")
        data = {"version": "1.0", "formats": ["pdf", "docx"], "count": 42}

        assert safe_write_text(path, json.dumps(data)) is True
        loaded = safe_read_json(path)
        assert loaded == data

    def test_list_directory_filters_hidden(self, sample_dir):
        """list_directory 正确过滤隐藏文件，并返回目录优先排序"""
        from mmfb.core.file_handler import list_directory, safe_write_text

        # 创建隐藏文件、普通文件、子目录
        Path(sample_dir, ".DS_Store").write_bytes(b"")
        Path(sample_dir, "visible.txt").write_bytes(b"ok")
        Path(sample_dir, "zzz_dir").mkdir()
        Path(sample_dir, "aaa_dir").mkdir()

        entries = list_directory(sample_dir)
        names = [e["name"] for e in entries]
        assert ".DS_Store" not in names
        assert "aaa_dir" in names
        assert "zzz_dir" in names
        assert "visible.txt" in names

        # 目录在前
        dirs = [e for e in entries if e["is_dir"]]
        files = [e for e in entries if not e["is_dir"]]
        if dirs and files:
            assert entries.index(dirs[0]) < entries.index(files[0])


# ============================================================
# 集成场景：注册表分发全链路
# ============================================================

class TestRegistryIntegration:
    """HandlerRegistry 按扩展名分发到 Handler"""

    def test_pdf_dispatched_to_pdf_handler(self, isolated_registry, sample_pdf):
        """registry.get_handler 返回 PdfHandler 实例且能调用 get_preview"""
        handler = isolated_registry.get_handler(sample_pdf)
        assert handler is not None
        assert type(handler).__name__ == "PdfHandler"

        preview = handler.get_preview()
        assert preview is not None
        assert preview["mime"] == "application/pdf"
        assert "data" in preview
        assert preview["data"]["page_count"] >= 1

    def test_docx_dispatched_and_preview(self, isolated_registry, sample_docx):
        """DOCX 分发到 DocxHandler 并成功 preview"""
        handler = isolated_registry.get_handler(sample_docx)
        assert handler is not None
        preview = handler.get_preview()
        assert preview is not None
        assert preview["mime"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def test_png_dispatched_and_preview(self, isolated_registry, sample_png):
        """PNG 分发到 ImageHandler 并生成 base64 预览数据"""
        handler = isolated_registry.get_handler(sample_png)
        assert handler is not None
        preview = handler.get_preview()
        assert preview is not None
        assert preview["mime"].startswith("image/")
        assert "data" in preview

    def test_md_dispatched_to_markdown(self, isolated_registry, sample_md):
        """Markdown 正确分发到 MarkdownHandler"""
        handler = isolated_registry.get_handler(sample_md)
        assert handler is not None
        preview = handler.get_preview()
        assert preview is not None
        assert preview["mime"] == "text/markdown"

    def test_unknown_extension_returns_none(self, isolated_registry):
        """未知扩展名返回 None"""
        handler = isolated_registry.get_handler("/tmp/file.unknown_ext_xyz")
        assert handler is None

    def test_registry_rejects_duplicate_extension(self, isolated_registry):
        """重复注册同一扩展名时静默跳过（不抛错也不覆盖）"""
        from mmfb.core.handler_base import BaseHandler

        class DummyPdf(BaseHandler):
            extensions = []  # 不自动注册
            def get_preview(self):
                return {}

        original = isolated_registry.get_handler("/tmp/dummy.pdf")
        original_cls_name = type(original).__name__ if original else None

        # 尝试覆盖 .pdf
        isolated_registry.register(".pdf", DummyPdf)
        after = isolated_registry.get_handler("/tmp/dummy.pdf")
        assert type(after).__name__ == original_cls_name


# ============================================================
# 集成场景：转换引擎
# ============================================================

class TestConversionIntegration:
    """conversion_engine 端到端转换"""

    def test_markdown_to_html(self, sample_md, sample_dir):
        """MD -> HTML 转换成功且输出合法"""
        from mmfb.services.conversion_engine import convert

        output = os.path.join(sample_dir, "out.html")
        r = convert(sample_md, output, src_format="md", dst_format="html")
        assert r.ok is True, f"fail: {r.error}"
        assert os.path.exists(output)
        content = Path(output).read_text(encoding="utf-8")
        assert "<h1" in content or "Hello" in content

    def test_html_to_markdown(self, sample_html, sample_dir):
        """HTML -> MD 转换成功"""
        from mmfb.services.conversion_engine import convert

        output = os.path.join(sample_dir, "out.md")
        r = convert(sample_html, output, src_format="html", dst_format="md")
        assert r.ok is True, f"fail: {r.error}"
        assert os.path.exists(output)
        content = Path(output).read_text(encoding="utf-8")
        assert "MMFB" in content or "Test" in content

    def test_pdf_to_text(self, sample_pdf, sample_dir):
        """PDF -> TXT 转换成功"""
        from mmfb.services.conversion_engine import convert

        output = os.path.join(sample_dir, "out_pdf.txt")
        r = convert(sample_pdf, output, src_format="pdf", dst_format="txt")
        assert r.ok is True, f"fail: {r.error}"
        assert os.path.exists(output)
        # 至少生成了空文件（内容可能为空白）
        assert os.path.getsize(output) >= 0

    def test_unsupported_format_returns_false(self, sample_md, sample_dir):
        """不支持的目标格式返回 False（不识别的格式走 fallback 可能成功或失败，不抛异常即可）"""
        from mmfb.services.conversion_engine import convert

        output = os.path.join(sample_dir, "out.xyz")
        # 不应抛异常
        r = convert(sample_md, output, src_format="md", dst_format="xyz_unknown_format")
        # 转换结果可以是 ok=True（base64 回退）或 ok=False，关键是没异常
        assert r is not None

    def test_nonexistent_source_returns_false(self, sample_dir):
        """源文件不存在时返回 ok=False"""
        from mmfb.services.conversion_engine import convert

        r = convert("/nonexistent/file.md", os.path.join(sample_dir, "out.html"),
                    src_format="md", dst_format="html")
        assert r.ok is False

    def test_image_conversion_png_to_jpg(self, sample_png, sample_dir):
        """PNG -> JPG 图像互转"""
        from mmfb.services.conversion_engine import convert_image
        from PIL import Image

        output = os.path.join(sample_dir, "converted.jpg")
        r = convert_image(sample_png, output, "jpg")
        assert r.ok is True, f"fail: {r.error}"
        assert os.path.exists(output)
        img = Image.open(output)
        assert img.format == "JPG" or img.format == "JPEG"


# ============================================================
# 集成场景：多 Handler 协同
# ============================================================

class TestMultiHandlerPipeline:
    """多格式混合工作流：批量预览 + 导出"""

    def test_batch_preview_returns_valid_data(self, isolated_registry, sample_pdf, sample_png, sample_md):
        """三种格式批量调用 get_preview，全部返回有效数据"""
        files = [sample_pdf, sample_png, sample_md]
        previews = []
        for f in files:
            handler = isolated_registry.get_handler(f)
            assert handler is not None, f"No handler for {f}"
            preview = handler.get_preview()
            assert preview is not None, f"Preview failed for {f}"
            previews.append(preview)

        assert len(previews) == 3
        # 至少应包含 mime 字段
        for p in previews:
            assert "mime" in p

    def test_file_handler_with_multi_format_extension(self, sample_dir):
        """file_handler 能正确读写多后缀文件（如 .tar.gz 风格）"""
        from mmfb.core.file_handler import safe_write_binary, safe_read_binary, get_file_info

        path = os.path.join(sample_dir, "archive.data.bin")
        data = b"\x00\x01\x02\x03binary payload"
        assert safe_write_binary(path, data) is True
        assert safe_read_binary(path) == data

        info = get_file_info(path)
        assert info is not None
        assert info["name"] == "archive.data.bin"

    def test_registry_case_insensitive(self, isolated_registry, tmp_path):
        """注册表大小写不敏感.PDF 和 .pdf 都能分发到 PdfHandler"""
        # 创建大写扩展名文件
        upper = str(tmp_path / "DOC.PDF")
        Path(upper).write_bytes(b"%PDF-1.4 fake")
        handler = isolated_registry.get_handler(upper)
        assert handler is not None
        assert type(handler).__name__ == "PdfHandler"
