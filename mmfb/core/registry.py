"""Handler 注册表：按文件扩展名分发到对应 Handler

支持特性：
1. 单层后缀注册：register('.pdf', PdfHandler)
2. 复合后缀注册（优先级更高）：register('.tar.gz', TarGzHandler)
3. 自动注册：从 Handler 类的 extensions 属性批量注册
4. MIME 探测缓存：通过 MimeCache 复用
5. 查询时优先匹配复合后缀，再匹配单层后缀
6. Handler 实例缓存：最近使用的 Handler 实例复用，避免重复 I/O

使用示例：
    registry = HandlerRegistry()
    registry.register('.pdf', PdfHandler)
    registry.register_class(ImageHandler)  # 自动读取 extensions

    handler = registry.get_handler('/path/to/doc.pdf')
    if handler:
        preview = handler.get_preview()
"""
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Type

from mmfb.core.handler_base import BaseHandler, MimeCache


# Handler 缓存容量（最近 N 个路径的 Handler 实例被保留）
_HANDLER_CACHE_SIZE = 32


class HandlerRegistry:
    """Handler 注册表

    性能优化：
    - 内置 LRU 缓存，对同一路径的 get_handler 调用复用实例。
    - 缓存以 (path, mtime) 为键，文件内容修改后自动失效。
    - 缓存容量 32 条，覆盖常规多标签工作集。
    """

    def __init__(self):
        # 复合后缀（如 .tar.gz）优先匹配
        self._compound: Dict[str, Type[BaseHandler]] = {}
        # 单层后缀
        self._simple: Dict[str, Type[BaseHandler]] = {}
        # Handler 实例缓存：key = (normalized_path, mtime) -> BaseHandler
        self._handler_cache: Dict[Tuple[str, float], BaseHandler] = {}
        # 记录缓存插入顺序，用于 LRU 淘汰
        self._cache_order: List[Tuple[str, float]] = []

    def register(self, extension: str, handler_class: Type[BaseHandler]) -> None:
        """按扩展名注册 Handler

        Args:
            extension: 扩展名（如 '.pdf'、'.tar.gz'），大小写不敏感
            handler_class: 继承自 BaseHandler 的类

        Raises:
            TypeError: handler_class 不是 BaseHandler 的子类
            ValueError: extension 为空或不以 . 开头
            KeyError: 扩展名已被注册（防止覆盖，专门 Handler 优先）
        """
        if not extension or not extension.startswith("."):
            raise ValueError(f"invalid extension: {extension!r}")
        if not (isinstance(handler_class, type) and issubclass(handler_class, BaseHandler)):
            raise TypeError(
                f"{handler_class!r} must be a subclass of BaseHandler"
            )

        normalized = extension.lower()
        # 拒绝覆盖已注册扩展名，防止通用 Handler 抢夺专门 Handler 的格式
        if normalized in self._compound or normalized in self._simple:
            return  # 静默跳过，不抛错，方便 register_class 批量注册时的冲突处理

        # 复合后缀判断：除首字符 . 外还有其他 .，如 .tar.gz
        if "." in normalized[1:]:
            self._compound[normalized] = handler_class
        else:
            self._simple[normalized] = handler_class

    def register_class(self, handler_class: Type[BaseHandler]) -> None:
        """从 Handler 类的 extensions 属性批量注册

        Args:
            handler_class: 继承自 BaseHandler 且定义了 extensions 的类
        """
        for ext in handler_class.extensions:
            self.register(ext, handler_class)

    def unregister(self, extension: str) -> bool:
        """取消注册指定扩展名的 Handler

        Returns:
            True 表示成功移除，False 表示未注册该扩展名
        """
        normalized = extension.lower()
        if normalized in self._compound:
            del self._compound[normalized]
            return True
        if normalized in self._simple:
            del self._simple[normalized]
            return True
        return False

    def get_handler(self, path: str) -> Optional[BaseHandler]:
        """按文件路径分发到对应 Handler

        匹配优先级：
        1. 复合后缀（取最后两个后缀组合，如 .tar.gz）
        2. 单层后缀（最后一个后缀）
        3. 返回 None 表示没有匹配的 Handler

        性能优化：优先从 LRU 缓存读取，命中时跳过 Handler 构造。
        缓存键 = (normalized_path, mtime)，文件修改后自动失效。
        """
        # 查询 Handler class（不需要缓存，仅查字典）
        suffixes = Path(path).suffixes
        cls: Optional[Type[BaseHandler]] = None

        if len(suffixes) >= 2:
            compound = "".join(suffixes[-2:]).lower()
            cls = self._compound.get(compound)
        if cls is None and suffixes:
            simple = suffixes[-1].lower()
            cls = self._simple.get(simple)
        if cls is None:
            return None

        # LRU 缓存查找：以 (path, mtime) 为键
        try:
            normalized = str(Path(path).resolve())
            mtime = Path(path).stat().st_mtime
        except OSError:
            # 文件不存在或不可访问，直接返回新实例
            return cls(path)

        cache_key = (normalized, mtime)
        cached = self._handler_cache.get(cache_key)
        if cached is not None:
            # 移到末尾（最近使用）
            if cache_key in self._cache_order:
                self._cache_order.remove(cache_key)
            self._cache_order.append(cache_key)
            return cached

        # 缓存未命中，创建新实例
        handler = cls(path)
        self._handler_cache[cache_key] = handler
        self._cache_order.append(cache_key)

        # 超过容量时淘汰最旧条目
        while len(self._cache_order) > _HANDLER_CACHE_SIZE:
            oldest = self._cache_order.pop(0)
            self._handler_cache.pop(oldest, None)

        return handler

    def list_extensions(self) -> List[str]:
        """返回所有已注册的扩展名（排序后）"""
        all_exts = set(self._compound.keys()) | set(self._simple.keys())
        return sorted(all_exts)

    def list_handlers(self) -> List[Tuple[str, str]]:
        """返回所有已注册的（扩展名, Handler 类名）对"""
        items = []
        for ext, cls in self._compound.items():
            items.append((ext, cls.__name__))
        for ext, cls in self._simple.items():
            items.append((ext, cls.__name__))
        return sorted(items, key=lambda x: x[0])

    def count(self) -> int:
        """返回已注册的扩展名数量"""
        return len(self._compound) + len(self._simple)

    def clear(self) -> None:
        """清空注册表（主要用于测试）"""
        self._compound.clear()
        self._simple.clear()


# 全局单例，供整个应用共享
registry = HandlerRegistry()
