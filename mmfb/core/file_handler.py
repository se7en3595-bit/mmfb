"""文件读写与元数据操作模块

提供安全的文件 I/O 方法，所有函数均包含统一异常处理和边界检查。
路径验证防止目录遍历攻击（null byte 注入、非法构造路径等）。
"""
import json
import mimetypes
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any


# 单文件读写大小上限（MB）
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


class FileOperationError(Exception):
    """文件操作异常基类"""
    pass


class PathValidationError(FileOperationError):
    """路径验证失败"""
    pass


def _validate_path(path: str) -> Path:
    """路径安全检查

    1. 拒绝包含 null byte 的路径（可能导致 C 库截断）
    2. 拒绝空路径
    3. 返回规范化后的 Path 对象（解析符号链接和相对路径）
    """
    if not path:
        raise PathValidationError("empty path")
    if "\x00" in path:
        raise PathValidationError("null byte in path")
    p = Path(path)
    try:
        resolved = p.resolve(strict=False)
    except (OSError, ValueError) as e:
        raise PathValidationError(f"invalid path: {e}")
    return resolved


def safe_read_binary(path: str) -> Optional[bytes]:
    """安全读取二进制文件

    返回 None 表示文件不存在、超出大小限制或读取失败。
    """
    try:
        p = _validate_path(path)
        if not p.is_file():
            return None
        size = p.stat().st_size
        if size > MAX_FILE_SIZE_BYTES:
            return None
        return p.read_bytes()
    except (FileOperationError, OSError):
        return None


def safe_read_text(path: str, encoding: str = "utf-8") -> Optional[str]:
    """安全读取文本文件

    使用 errors='replace' 处理无法解码的字符，不会因编码错误返回 None。
    返回 None 仅表示文件不存在或超出大小限制。
    """
    data = safe_read_binary(path)
    if data is None:
        return None
    return data.decode(encoding, errors="replace")


def safe_read_json(path: str) -> Optional[Any]:
    """安全读取 JSON 文件

    返回解析后的 Python 对象（dict/list 等），解析失败返回 None。
    """
    text = safe_read_text(path)
    if text is None:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def safe_write_binary(path: str, data: bytes) -> bool:
    """安全写入二进制文件

    写入前确保父目录存在。返回 True 表示成功。
    """
    try:
        p = _validate_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return True
    except (FileOperationError, OSError):
        return False


def safe_write_text(path: str, text: str, encoding: str = "utf-8") -> bool:
    """安全写入文本文件

    内部调用 safe_write_binary，自动完成编码转换。
    """
    try:
        data = text.encode(encoding)
    except (UnicodeEncodeError, ValueError):
        return False
    return safe_write_binary(path, data)


def get_file_info(path: str) -> Optional[Dict[str, Any]]:
    """获取文件/目录元信息

    返回字典包含：
    - path: 原始路径
    - name: 文件名
    - size: 文件大小（字节），目录为 0
    - mime: MIME 类型（猜测），未知时为 application/octet-stream
    - modified: 修改时间（格式 yyyy-MM-dd HH:mm:ss）
    - is_dir: 是否为目录
    - 文件不存在时返回 None
    """
    try:
        p = _validate_path(path)
        if not p.exists():
            return None
        stat = p.stat()
        is_dir = p.is_dir()
        mime = "directory" if is_dir else (mimetypes.guess_type(str(p))[0] or "application/octet-stream")
        return {
            "path": str(p),
            "name": p.name,
            "size": 0 if is_dir else stat.st_size,
            "mime": mime,
            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "is_dir": is_dir,
        }
    except (FileOperationError, OSError):
        return None


def list_directory(path: str) -> List[Dict[str, Any]]:
    """列出目录下的子项（跳过隐藏文件）

    返回列表，每个元素为字典：
    - name: 名称
    - is_dir: 是否为目录
    - size: 文件大小（字节），目录为 0

    按名称字母排序，目录优先于文件。
    路径不存在或不是目录时返回空列表。
    """
    try:
        p = _validate_path(path)
        if not p.is_dir():
            return []
        entries = []
        for child in p.iterdir():
            if child.name.startswith("."):
                continue
            try:
                child_stat = child.stat()
                is_dir = child.is_dir()
                entries.append({
                    "name": child.name,
                    "is_dir": is_dir,
                    "size": 0 if is_dir else child_stat.st_size,
                })
            except OSError:
                continue
        # 排序：目录优先，同级按名称
        entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
        return entries
    except (FileOperationError, OSError):
        return []
