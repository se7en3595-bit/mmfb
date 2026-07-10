"""Handlers 包

提供各格式的 Handler 实现，统一导入路径：
    from mmfb.handlers import (
        PdfHandler, MarkdownHandler, HtmlHandler,
        ImageHandler, MediaHandler, CodeHandler,
        CsvHandler, DocxHandler, XlsxHandler, PptxHandler,
        PsdHandler, RawHandler, TextureHandler,
        Model3DHandler, ArchiveHandler, XmindHandler,
    )

注册方式：
    在 Handler 类定义后调用 registry.register_class(HandlerClass)，
    或在 handlers/__init__.py 末尾显式注册。
"""
from mmfb.core.handler_base import BaseHandler
from mmfb.core.registry import registry
from mmfb.handlers.pdf_handler import PdfHandler
from mmfb.handlers.markdown_handler import MarkdownHandler
from mmfb.handlers.html_handler import HtmlHandler
from mmfb.handlers.image_handler import ImageHandler
from mmfb.handlers.svg_handler import SvgHandler
from mmfb.handlers.media_handler import MediaHandler
from mmfb.handlers.code_handler import CodeHandler
from mmfb.handlers.csv_handler import CsvHandler
from mmfb.handlers.docx_handler import DocxHandler
from mmfb.handlers.xlsx_handler import XlsxHandler
from mmfb.handlers.pptx_handler import PptxHandler
from mmfb.handlers.psd_handler import PsdHandler
from mmfb.handlers.raw_handler import RawHandler
from mmfb.handlers.texture_handler import TextureHandler
from mmfb.handlers.heic_handler import HeicHandler
from mmfb.handlers.text_handler import TextHandler
from mmfb.handlers.epub_handler import EpubHandler
from mmfb.handlers.model3d_handler import Model3DHandler
from mmfb.handlers.archive_handler import ArchiveHandler
from mmfb.handlers.xmind_handler import XmindHandler

# 自动注册
registry.register_class(PdfHandler)
registry.register_class(MarkdownHandler)
registry.register_class(HtmlHandler)
registry.register_class(ImageHandler)
registry.register_class(SvgHandler)
registry.register_class(MediaHandler)
registry.register_class(CodeHandler)
registry.register_class(CsvHandler)
registry.register_class(DocxHandler)
registry.register_class(XlsxHandler)
registry.register_class(PptxHandler)
registry.register_class(PsdHandler)
registry.register_class(RawHandler)
registry.register_class(TextureHandler)
registry.register_class(HeicHandler)
registry.register_class(TextHandler)
registry.register_class(EpubHandler)
registry.register_class(Model3DHandler)
registry.register_class(ArchiveHandler)
registry.register_class(XmindHandler)

__all__ = [
    "BaseHandler", "registry",
    "PdfHandler", "MarkdownHandler", "HtmlHandler",
    "ImageHandler", "SvgHandler", "MediaHandler", "CodeHandler",
    "CsvHandler",
    "DocxHandler", "XlsxHandler", "PptxHandler",
    "PsdHandler", "RawHandler", "TextureHandler", "HeicHandler",
    "TextHandler", "EpubHandler",
    "Model3DHandler", "ArchiveHandler", "XmindHandler",
]
