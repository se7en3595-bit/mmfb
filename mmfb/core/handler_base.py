"""Handler 抽象基类与 MIME 探测缓存

所有格式 Handler 必须继承 BaseHandler 并实现：
- 类属性 extensions：支持的扩展名列表
- get_preview()：返回预览数据
可选择实现：
- get_edit()：返回编辑数据（默认返回 None 表示不可编辑）
- get_mime()：覆盖默认 MIME 探测逻辑
"""
import mimetypes
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any, Dict, List, Optional


class MimeCache:
    """MIME 探测缓存，避免重复调用 mimetypes.guess_type

    使用 functools.lru_cache 实现，缓存容量 512 条，覆盖常见格式。
    """

    @staticmethod
    @lru_cache(maxsize=512)
    def get_mime(path: str) -> str:
        """根据路径猜测 MIME 类型，结果被 LRU 缓存"""
        return mimetypes.guess_type(path)[0] or "application/octet-stream"

    @staticmethod
    def clear() -> None:
        """清空 MIME 缓存（主要用于测试）"""
        MimeCache.get_mime.cache_clear()


class BaseHandler(ABC):
    """所有格式 Handler 的抽象基类

    子类需定义：
        extensions: List[str]  # 支持的扩展名，如 ['.pdf', '.PDF']

    子类需实现：
        get_preview() -> Optional[Dict[str, Any]]

    子类可选覆盖：
        get_edit() -> Optional[Dict[str, Any]]  # 默认返回 None
        get_mime() -> str                       # 默认使用 MimeCache
    """

    extensions: List[str] = []

    def __init__(self, path: str):
        self.path = path

    @classmethod
    def can_handle(cls, path: str) -> bool:
        """判断 Handler 是否支持该路径

        仅比较最后一个后缀（如 .tar.gz 中的 .gz）。
        复合后缀匹配由 HandlerRegistry 负责。
        """
        from pathlib import Path
        suffix = Path(path).suffix.lower()
        return suffix in cls.extensions

    @abstractmethod
    def get_preview(self) -> Optional[Dict[str, Any]]:
        """获取预览数据

        返回字典通常包含：
        - mime: str          MIME 类型
        - template: str     前端模板名称
        - data: Any         预览所需数据（文本/base64/文件路径等）
        - editable: bool    是否支持就地编辑
        - error: str        如果预览生成失败，包含错误原因

        返回 None 表示预览生成失败。
        """
        ...

    def get_edit(self) -> Optional[Dict[str, Any]]:
        """获取编辑数据

        默认返回 None 表示不支持编辑。
        子类覆盖时返回字典，通常包含：
        - mime: str         编辑内容的 MIME 类型
        - data: Any         可编辑数据
        - save: bool        是否支持保存回原文件
        """
        return None

    def get_mime(self) -> str:
        """获取该文件的 MIME 类型"""
        return MimeCache.get_mime(self.path)

    def get_file_info(self) -> Optional[Dict[str, Any]]:
        """获取文件元信息，委托给 file_handler 模块"""
        from mmfb.core.file_handler import get_file_info
        return get_file_info(self.path)

    def supports_editing(self) -> bool:
        """判断该 Handler 是否支持编辑"""
        return self.get_edit() is not None
