"""Markdown 格式处理器

职责：
1. 读取 .md / .markdown / .mdown 等文本内容，返回给前端
2. 预览模式：前端将 Markdown 转为 HTML 渲染
3. 编辑模式：textarea + 实时预览双栏，保存时调用 Bridge
4. 可选：Emoji/表格扩展（前端实现）
"""
import json
import os
from typing import Any, Dict, List, Optional

from mmfb.core.handler_base import BaseHandler
from mmfb.core.file_handler import safe_read_text


# Markdown 扩展名规范映射（来自 GitHub  Linguist）
MD_EXTENSIONS: List[str] = [
    ".md", ".markdown", ".mdown", ".mkd", ".mkdn",
    ".mdtxt", ".mdtext", ".text", ".rmd",
]


class MarkdownHandler(BaseHandler):
    """Markdown 文件处理器

    支持的扩展名：
        .md, .markdown, .mdown, .mkd, .mkdn,
        .mdtxt, .mdtext, .text, .rmd

    预览与编辑均用 Markdown 文本本身作为数据载荷，
    前端负责 Markdown → HTML 转换（marked.js 或 Milkdown）。
    """

    extensions = MD_EXTENSIONS

    def get_preview(self) -> Optional[Dict[str, Any]]:
        """获取 Markdown 预览数据

        返回字典：
        - mime: text/markdown
        - template: 'markdown'（前端根据此键选择渲染器）
        - data.content: 文件全文（UTF-8 字符串）
        - data.file_path: 原文件绝对路径
        - data.file_size: 文件字节数
        - data.line_count: 行数
        - editable: True（支持就地编辑）
        - error: 如果读取失败包含错误信息
        """
        try:
            if not os.path.isfile(self.path):
                return {
                    "mime": "text/markdown",
                    "template": "markdown",
                    "data": {
                        "content": "",
                        "file_path": self.path,
                        "file_size": 0,
                        "line_count": 0,
                    },
                    "editable": True,
                    "error": "file not found",
                }

            content = safe_read_text(self.path, encoding="utf-8")
            if content is None:
                return {
                    "mime": "text/markdown",
                    "template": "markdown",
                    "data": {
                        "content": "",
                        "file_path": self.path,
                        "file_size": 0,
                        "line_count": 0,
                    },
                    "editable": True,
                    "error": "failed to read file (encoding issue or permission denied)",
                }

            # 规范化换行，避免保存时重复 \r
            content = content.replace("\r\n", "\n").replace("\r", "\n")
            file_size = os.path.getsize(self.path)
            line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)

            return {
                "mime": "text/markdown",
                "template": "markdown",
                "data": {
                    "content": content,
                    "file_path": self.path,
                    "file_size": file_size,
                    "line_count": line_count,
                },
                "editable": True,
            }
        except Exception as e:
            return {
                "mime": "text/markdown",
                "template": "markdown",
                "data": {
                    "content": "",
                    "file_path": self.path,
                    "file_size": 0,
                    "line_count": 0,
                },
                "editable": True,
                "error": str(e),
            }

    def get_edit(self) -> Optional[Dict[str, Any]]:
        """获取编辑数据

        与 get_preview 结构一致，但显式启用 save 标志，
        前端据此显示"保存"按钮。
        """
        preview = self.get_preview()
        if preview is None:
            return None

        preview["data"]["save"] = True
        preview["data"]["mime"] = "text/markdown"
        return preview
