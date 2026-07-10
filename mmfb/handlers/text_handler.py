"""纯文本格式处理器

职责：
1. 读取 .txt / .log / .ini / .cfg 纯文本文件
2. 自动探测文件编码（chardet），支持 UTF-8 / GBK / GB2312 / Latin-1 等
3. 预览模式：前端显示文本内容
4. 编辑模式：textarea 编辑并保存回原文件
"""
import os
from typing import Any, Dict, List, Optional

import chardet

from mmfb.core.handler_base import BaseHandler
from mmfb.core.file_handler import safe_read_binary


# 纯文本扩展名
TEXT_EXTENSIONS: List[str] = [
    ".txt", ".log", ".ini", ".cfg",
]

# 常见编码探测的最小字节数（chardet 对短文本不可靠）
MIN_DETECT_BYTES = 256


class TextHandler(BaseHandler):
    """纯文本文件处理器

    支持的扩展名：
        .txt, .log, .ini, .cfg

    特性：
        - 自动编码探测（chardet），UTF-8 优先尝试
        - 支持预览和就地编辑
        - 保存时保留原编码（若探测失败默认 UTF-8）
    """

    # 结构化文本/配置格式（CodeHandler 不再覆盖）
    # .json/.xml 也可考虑未来做专门的 JSON/XML Handler
    TEXT_EXTENSIONS += [
        ".json", ".jsonc", ".xml",
        ".yaml", ".yml", ".toml",
        ".conf", ".env", ".properties",
    ]
    extensions = TEXT_EXTENSIONS

    # 文件实际编码（探测后填充，供保存时复用）
    _detected_encoding: str = "utf-8"

    @classmethod
    def detect_encoding(cls, raw: bytes) -> str:
        """探测二进制数据的编码

        策略：
        1. 先尝试 UTF-8 解码（最常用且无损）
        2. 失败则调用 chardet 探测
        3. chardet 也失败则返回 'utf-8'（降级用 errors='replace'）
        """
        # UTF-8 优先尝试
        try:
            raw.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            pass

        # chardet 探测（需要足够字节才可靠）
        if len(raw) >= MIN_DETECT_BYTES:
            result = chardet.detect(raw)
            encoding = result.get("encoding")
            confidence = result.get("confidence", 0)
            if encoding and confidence > 0.5:
                return encoding.lower()

        # 中文环境常见兜底
        if len(raw) >= 3:
            # GB18030 是大集合，包含 GBK/GB2312
            try:
                raw.decode("gb18030")
                return "gb18030"
            except UnicodeDecodeError:
                pass

        return "utf-8"

    def get_preview(self) -> Optional[Dict[str, Any]]:
        """获取纯文本预览数据

        返回字典：
        - mime: text/plain
        - template: 'text'（前端根据此键选择渲染器）
        - data.content: 文本内容（已解码的字符串）
        - data.file_path: 原文件绝对路径
        - data.file_size: 文件字节数
        - data.line_count: 行数
        - data.encoding: 探测到的编码名称
        - editable: True（支持就地编辑）
        - error: 如果读取失败包含错误信息
        """
        try:
            if not os.path.isfile(self.path):
                return {
                    "mime": "text/plain",
                    "template": "text",
                    "data": {
                        "content": "",
                        "file_path": self.path,
                        "file_size": 0,
                        "line_count": 0,
                        "encoding": "utf-8",
                    },
                    "editable": True,
                    "error": "file not found",
                }

            raw = safe_read_binary(self.path)
            if raw is None:
                return {
                    "mime": "text/plain",
                    "template": "text",
                    "data": {
                        "content": "",
                        "file_path": self.path,
                        "file_size": 0,
                        "line_count": 0,
                        "encoding": "utf-8",
                    },
                    "editable": True,
                    "error": "failed to read file (too large or permission denied)",
                }

            encoding = self.detect_encoding(raw)
            self._detected_encoding = encoding

            content = raw.decode(encoding, errors="replace")
            # 规范化换行：统一为 LF，避免 Windows 下保存时出现 \r\r\n
            content = content.replace("\r\n", "\n").replace("\r", "\n")
            file_size = os.path.getsize(self.path)

            if not content:
                line_count = 0
            else:
                line_count = content.count("\n") + (0 if content.endswith("\n") else 1)

            return {
                "mime": "text/plain",
                "template": "text",
                "data": {
                    "content": content,
                    "file_path": self.path,
                    "file_size": file_size,
                    "line_count": line_count,
                    "encoding": encoding,
                },
                "editable": True,
            }
        except Exception as e:
            return {
                "mime": "text/plain",
                "template": "text",
                "data": {
                    "content": "",
                    "file_path": self.path,
                    "file_size": 0,
                    "line_count": 0,
                    "encoding": "utf-8",
                },
                "editable": True,
                "error": str(e),
            }

    def get_edit(self) -> Optional[Dict[str, Any]]:
        """获取编辑数据

        与 get_preview 结构一致，显式启用 save 标志，
        前端据此显示"保存"按钮。
        """
        preview = self.get_preview()
        if preview is None:
            return None

        preview["data"]["save"] = True
        preview["data"]["mime"] = "text/plain"
        return preview
