"""PDF 格式处理器

职责：
1. 使用 PyPDF2 提取页面数/元数据，返回给前端
2. 将 PDF 文件路径传给前端，由 Chromium 内置 PDF 查看器直接渲染
3. 大文件 (>50MB) 标记延迟加载

注意：当前使用 QWebEngineView (Chromium) 内置 PDF 渲染能力，
      pdf.js 库将在后续任务中集成为独立前端渲染方案。
"""
import os
from typing import Any, Dict, Optional

from mmfb.core.handler_base import BaseHandler


# 大文件阈值：50MB
LAZY_LOAD_THRESHOLD = 50 * 1024 * 1024


class PdfHandler(BaseHandler):
    """PDF 文件处理器

    支持的扩展名：.pdf（大小写不敏感）
    """

    extensions = [".pdf"]

    def get_preview(self) -> Optional[Dict[str, Any]]:
        """获取 PDF 预览数据

        返回字典：
        - mime: application/pdf
        - template: 'pdf'（前端根据此值选择渲染器）
        - data.file_path: PDF 文件绝对路径
        - data.file_size: 文件大小（字节）
        - data.page_count: 页数（PyPDF2 解析）
        - data.lazy_load: 是否大文件延迟加载
        - data.metadata: PDF 元数据字典（title/author/...）
        - error: 解析失败时的错误信息
        """
        try:
            if not os.path.isfile(self.path):
                return {
                    "mime": "application/pdf",
                    "template": "pdf",
                    "data": {"file_path": self.path, "file_size": 0, "page_count": 0, "lazy_load": False, "metadata": {}},
                    "editable": False,
                    "error": "file not found",
                }

            file_size = os.path.getsize(self.path)
            lazy_load = file_size > LAZY_LOAD_THRESHOLD

            # 提取页数和元数据
            page_count = 0
            metadata = {}
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(self.path)
                page_count = len(reader.pages)
                meta = reader.metadata
                if meta:
                    metadata = {
                        "title": meta.title or "",
                        "author": meta.author or "",
                        "subject": meta.subject or "",
                        "creator": meta.creator or "",
                        "producer": meta.producer or "",
                    }
            except Exception as e:
                # 解析失败仍返回基本信息，前端可降级为纯路径渲染
                metadata = {"_parse_error": str(e)}

            return {
                "mime": "application/pdf",
                "template": "pdf",
                "data": {
                    "file_path": self.path,
                    "file_size": file_size,
                    "page_count": page_count,
                    "lazy_load": lazy_load,
                    "metadata": metadata,
                },
                "editable": False,
            }
        except Exception as e:
            return {
                "mime": "application/pdf",
                "template": "pdf",
                "data": {"file_path": self.path, "file_size": 0, "page_count": 0, "lazy_load": False, "metadata": {}},
                "editable": False,
                "error": str(e),
            }

    def get_edit(self) -> None:
        """PDF 不支持就地编辑（v1 阶段仅预览）"""
        return None
