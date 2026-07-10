"""HTML 格式处理器

职责：
1. 读取 .html / .htm 文件内容, ".css", ".scss",
2. 预览模式：前端通过 sandboxed iframe 渲染（禁止网络请求/JS执行）
3. 编辑模式：textarea 编辑源码，点击保存写回原文件

安全约束：
- sandboxed iframe 不开启 allow-scripts/allow-same-origin
- 不发起任何外部网络请求
"""
import json
import os
from typing import Any, Dict, List, Optional

from mmfb.core.handler_base import BaseHandler
from mmfb.core.file_handler import safe_read_text


# HTML 扩展名
HTML_EXTENSIONS: List[str] = [
    ".html", ".htm",
]


class HtmlHandler(BaseHandler):
    """HTML 文件处理器

    支持的扩展名：
        .html, .htm

    预览与编辑均用 HTML 源码本身作为数据载荷，
    前端负责 sandboxed 渲染。
    """

    extensions = HTML_EXTENSIONS

    def get_preview(self) -> Optional[Dict[str, Any]]:
        """获取 HTML 预览数据

        返回字典：
        - mime: text/html
        - template: 'html'
        - data.content: HTML 源码
        - data.file_path: 原文件路径
        - data.file_size: 字节数
        - data.line_count: 行数
        - editable: True（支持就地编辑）
        """
        try:
            if not os.path.isfile(self.path):
                return self._make_result("", "file not found")

            content = safe_read_text(self.path, encoding="utf-8")
            if content is None:
                return self._make_result("", "failed to read file")
            # 规范化换行，避免保存时重复 \r
            content = content.replace("\r\n", "\n").replace("\r", "\n")
            file_size = os.path.getsize(self.path)

            file_size = os.path.getsize(self.path)
            line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)

            return self._make_result(
                content,
                error=None,
                file_size=file_size,
                line_count=line_count,
            )
        except Exception as e:
            return self._make_result("", str(e))

    def get_edit(self) -> Optional[Dict[str, Any]]:
        """获取编辑数据

        与 get_preview 结构一致，但显式启用 save 标志。
        """
        preview = self.get_preview()
        if preview is None:
            return None

        preview["data"]["save"] = True
        preview["data"]["mime"] = "text/html"
        return preview

    def _make_result(
        self,
        content: str,
        error: Optional[str] = None,
        file_size: int = 0,
        line_count: int = 0,
    ) -> Dict[str, Any]:
        """构造统一返回结构"""
        result = {
            "mime": "text/html",
            "template": "html",
            "data": {
                "content": content,
                "file_path": self.path,
                "file_size": file_size,
                "line_count": line_count,
            },
            "editable": True,
        }
        if error:
            result["error"] = error
        return result
