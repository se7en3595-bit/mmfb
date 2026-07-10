"""压缩包格式处理器

职责：
1. 使用 zipfile / tarfile (标准库) 解析 ZIP / TAR / TAR.GZ / TGZ / TAR.BZ2 / TAR.XZ
2. 返回树形目录结构供前端渲染
3. 提供单文件内存解压接口 (不落地)，供前端预览压缩包内文件
4. 支持加密 ZIP (通过 Bridge 弹窗获取密码后重试)

安全：
- 防护 Zip Slip 路径遍历攻击 (成员名含 .. 或绝对路径时跳过)
- 单成员解压上限 50MB (与 file_handler.MAX_FILE_SIZE_BYTES 同步)
- 不写入磁盘，全部在内存操作
"""
import os
import tarfile
import zipfile
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from mmfb.core.handler_base import BaseHandler
from mmfb.core.file_handler import MAX_FILE_SIZE_BYTES


# 压缩包扩展名
ARCHIVE_EXTENSIONS: List[str] = [
    ".zip",
    ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz",
]

# 树形结构中单个目录最大成员数 (防止 JSON 爆炸)
MAX_ENTRIES_PER_ARCHIVE = 5000


def _safe_member_name(name: str) -> Optional[str]:
    """安全校验压缩包成员名，防止 Zip Slip 攻击

    - 拒绝绝对路径 (以 / 或 \\ 开头)
    - 拒绝含 .. 的相对路径
    - 返回清洗后的名字，或 None 表示应跳过
    """
    if not name:
        return None
    # 统一分隔符
    normalized = name.replace("\\", "/")
    # 拒绝绝对路径
    if normalized.startswith("/"):
        return None
    # 拒绝路径遍历
    parts = normalized.split("/")
    for part in parts:
        if part == "..":
            return None
    return normalized


def _get_extension(name: str) -> str:
    """从文件名取扩展名 (小写，不含 .)"""
    # 处理复合后缀如 .tar.gz
    lower = name.lower()
    if lower.endswith(".tar.gz") or lower.endswith(".tar.bz2") or lower.endswith(".tar.xz"):
        return lower.split(".", 1)[1]
    return Path(name).suffix.lstrip(".").lower()


def _format_size(size: int) -> str:
    """格式化文件大小为可读字符串"""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 10224:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.1f} GB"


class ArchiveHandler(BaseHandler):
    """压缩包处理器

    支持的扩展名：
        .zip, .tar, .tar.gz, .tgz, .tar.bz2, .tar.xz

    特性：
        - 标准库解析，无额外依赖
        - 树形目录结构 (嵌套 children)
        - 内存解压单文件 (不落地)
        - Zip Slip 防护
        - 加密 ZIP 检测 (通过 flag_bits & 0x1)
    """

    extensions = ARCHIVE_EXTENSIONS

    @classmethod
    def can_handle(cls, path: str) -> bool:
        """判断 Handler 是否支持该路径

        覆盖基类方法以支持复合后缀 (.tar.gz 等)。
        """
        lower = path.lower()
        # 先检查复合后缀
        for ext in [".tar.gz", ".tar.bz2", ".tar.xz"]:
            if lower.endswith(ext):
                return True
        # 再检查单层后缀
        suffix = Path(path).suffix.lower()
        return suffix in cls.extensions

    def get_preview(self) -> Optional[Dict[str, Any]]:
        """获取压缩包树形预览数据

        返回字典：
        - mime: application/zip 等
        - template: 'archive'
        - data.tree: 树形结构根节点
        - data.total_files: 文件总数
        - data.total_dirs: 目录总数
        - data.total_size: 解压总大小 (字节)
        - data.file_count: 实际成员数 (含目录)
        - data.is_encrypted: 是否加密 (仅 ZIP)
        - data.archive_type: 'zip' | 'tar'
        - data.file_path: 原文件路径
        - data.file_size: 压缩包大小
        - editable: False
        """
        try:
            if not os.path.isfile(self.path):
                return self._error_result("file not found")

            file_size = os.path.getsize(self.path)
            if file_size == 0:
                return self._error_result("empty file")

            lower = self.path.lower()
            if lower.endswith(".zip"):
                return self._parse_zip(file_size)
            else:
                return self._parse_tar(file_size)
        except Exception as e:
            return self._error_result(str(e))

    def get_edit(self) -> Optional[Dict[str, Any]]:
        """压缩包不支持就地编辑"""
        return None

    def _parse_zip(self, file_size: int) -> Dict[str, Any]:
        """解析 ZIP 文件"""
        try:
            with zipfile.ZipFile(self.path, "r") as zf:
                # 检测加密
                is_encrypted = False
                for info in zf.infolist():
                    if info.flag_bits & 0x1:
                        is_encrypted = True
                        break

                if is_encrypted:
                    return {
                        "mime": "application/zip",
                        "template": "archive",
                        "data": {
                            "tree": {"name": Path(self.path).name, "isDir": True, "children": []},
                            "total_files": 0,
                            "total_dirs": 0,
                            "total_size": 0,
                            "file_count": 0,
                            "is_encrypted": True,
                            "archive_type": "zip",
                            "file_path": self.path,
                            "file_size": file_size,
                        },
                        "editable": False,
                    }

                members = zf.infolist()
                return self._build_zip_tree(members, file_size)
        except zipfile.BadZipFile as e:
            return self._error_result(f"invalid zip: {e}")
        except Exception as e:
            return self._error_result(str(e))

    def _build_zip_tree(self, members: list, file_size: int) -> Dict[str, Any]:
        """从 ZIP 成员列表构建树形结构"""
        # 根节点
        root = {
            "name": Path(self.path).name,
            "isDir": True,
            "children": [],
        }

        # 用字典加速查找: path -> node
        dir_map: Dict[str, Dict] = {"": root}

        total_files = 0
        total_dirs = 0
        total_size = 0
        entry_count = 0

        for info in members:
            if entry_count >= MAX_ENTRIES_PER_ARCHIVE:
                break

            name = _safe_member_name(info.filename)
            if name is None:
                continue

            total_size += info.file_size
            entry_count += 1

            # 判断是否为目录 (以 / 结尾)
            is_dir = name.endswith("/")
            parts = name.rstrip("/").split("/")

            if is_dir:
                total_dirs += 1
                # 确保路径上所有目录节点存在
                current_path = ""
                for i, part in enumerate(parts):
                    if current_path:
                        current_path = current_path + "/" + part
                    else:
                        current_path = part
                    if current_path not in dir_map:
                        dir_node = {
                            "name": part,
                            "isDir": True,
                            "children": [],
                        }
                        dir_map[current_path] = dir_node
                        # 挂到父节点
                        parent_path = "/".join(parts[:i])
                        parent = dir_map.get(parent_path, root)
                        parent["children"].append(dir_node)
            else:
                total_files += 1
                # 文件节点
                file_node = {
                    "name": parts[-1],
                    "isDir": False,
                    "size": info.file_size,
                    "size_human": _format_size(info.file_size),
                    "ext": _get_extension(parts[-1]),
                    "compressed_size": info.compress_size,
                    "compressed_human": _format_size(info.compress_size),
                }
                # 挂到父目录
                parent_path = "/".join(parts[:-1])
                parent = dir_map.get(parent_path, root)
                parent["children"].append(file_node)

        return {
            "mime": "application/zip",
            "template": "archive",
            "data": {
                "tree": root,
                "total_files": total_files,
                "total_dirs": total_dirs,
                "total_size": total_size,
                "file_count": entry_count,
                "is_encrypted": False,
                "archive_type": "zip",
                "file_path": self.path,
                "file_size": file_size,
            },
            "editable": False,
        }

    def _parse_tar(self, file_size: int) -> Dict[str, Any]:
        """解析 TAR 文件 (含 .tar.gz / .tgz / .tar.bz2 / .tar.xz)"""
        try:
            with tarfile.open(self.path, "r:*") as tf:
                members = tf.getmembers()
                return self._build_tar_tree(members, file_size)
        except tarfile.TarError as e:
            return self._error_result(f"invalid tar: {e}")
        except Exception as e:
            return self._error_result(str(e))

    def _build_tar_tree(self, members: list, file_size: int) -> Dict[str, Any]:
        """从 TAR 成员列表构建树形结构"""
        root = {
            "name": Path(self.path).name,
            "isDir": True,
            "children": [],
        }

        dir_map: Dict[str, Dict] = {"": root}
        total_files = 0
        total_dirs = 0
        total_size = 0
        entry_count = 0

        for member in members:
            if entry_count >= MAX_ENTRIES_PER_ARCHIVE:
                break

            name = _safe_member_name(member.name)
            if name is None:
                continue

            total_size += member.size
            entry_count += 1

            is_dir = member.isdir()
            parts = name.rstrip("/").split("/")

            if is_dir:
                total_dirs += 1
                current_path = ""
                for i, part in enumerate(parts):
                    if current_path:
                        current_path = current_path + "/" + part
                    else:
                        current_path = part
                    if current_path not in dir_map:
                        dir_node = {
                            "name": part,
                            "isDir": True,
                            "children": [],
                        }
                        dir_map[current_path] = dir_node
                        parent_path = "/".join(parts[:i])
                        parent = dir_map.get(parent_path, root)
                        parent["children"].append(dir_node)
            else:
                if member.isfile():
                    total_files += 1
                    file_node = {
                        "name": parts[-1],
                        "isDir": False,
                        "size": member.size,
                        "size_human": _format_size(member.size),
                        "ext": _get_extension(parts[-1]),
                        "compressed_size": 0,
                        "compressed_human": "-",
                    }
                    parent_path = "/".join(parts[:-1])
                    parent = dir_map.get(parent_path, root)
                    parent["children"].append(file_node)

        return {
            "mime": "application/x-tar",
            "template": "archive",
            "data": {
                "tree": root,
                "total_files": total_files,
                "total_dirs": total_dirs,
                "total_size": total_size,
                "file_count": entry_count,
                "is_encrypted": False,
                "archive_type": "tar",
                "file_path": self.path,
                "file_size": file_size,
            },
            "editable": False,
        }

    def _error_result(self, error_msg: str) -> Dict[str, Any]:
        return {
            "mime": "application/octet-stream",
            "template": "archive",
            "data": {
                "tree": {"name": Path(self.path).name, "isDir": True, "children": []},
                "total_files": 0,
                "total_dirs": 0,
                "total_size": 0,
                "file_count": 0,
                "is_encrypted": False,
                "archive_type": "unknown",
                "file_path": self.path,
                "file_size": 0,
            },
            "editable": False,
            "error": error_msg,
        }


# ========== 内存解压辅助 (被 Bridge 调用) ==========

def extract_member_to_memory(archive_path: str, member_name: str, password: str = "") -> Dict[str, Any]:
    """从压缩包中解压单个成员到内存

    参数：
        archive_path: 压缩包路径
        member_name: 成员路径 (如 "folder/file.txt")
        password: ZIP 密码 (仅 ZIP 加密时用到)

    返回：
        {"ok": true, "data": base64_content, "size": int, "mime": str}
        或 {"ok": false, "error": "..."}
        或 {"ok": false, "need_password": true}
    """
    import base64
    import mimetypes

    try:
        if not os.path.isfile(archive_path):
            return {"ok": False, "error": "archive not found"}

        lower = archive_path.lower()
        if lower.endswith(".zip"):
            return _extract_zip_member(archive_path, member_name, password)
        else:
            return _extract_tar_member(archive_path, member_name)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _extract_zip_member(archive_path: str, member_name: str, password: str) -> Dict[str, Any]:
    """从 ZIP 解压单个成员"""
    import base64
    import mimetypes

    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            # 查找成员 (兼容带 / 不带前导路径)
            info = None
            for zi in zf.infolist():
                normalized = zi.filename.replace("\\", "/").rstrip("/")
                target = member_name.replace("\\", "/").rstrip("/")
                if normalized == target:
                    info = zi
                    break

            if info is None:
                return {"ok": False, "error": f"member not found: {member_name}"}

            if info.flag_bits & 0x1:
                # 加密
                if not password:
                    return {"ok": False, "need_password": True}
                try:
                    data = zf.read(info.filename, pwd=password.encode("utf-8"))
                except RuntimeError:
                    # 密码错误
                    return {"ok": False, "error": "wrong password"}
            else:
                data = zf.read(info.filename)

            if len(data) > MAX_FILE_SIZE_BYTES:
                return {"ok": False, "error": f"member too large: {len(data)} bytes"}

            mime = mimetypes.guess_type(member_name)[0] or "application/octet-stream"
            b64 = base64.b64encode(data).decode("ascii")

            return {
                "ok": True,
                "data": b64,
                "size": len(data),
                "mime": mime,
            }
    except zipfile.BadZipFile as e:
        return {"ok": False, "error": f"invalid zip: {e}"}


def _extract_tar_member(archive_path: str, member_name: str) -> Dict[str, Any]:
    """从 TAR 解压单个成员"""
    import base64
    import mimetypes

    try:
        with tarfile.open(archive_path, "r:*") as tf:
            member = None
            for m in tf.getmembers():
                normalized = m.name.replace("\\", "/").rstrip("/")
                target = member_name.replace("\\", "/").rstrip("/")
                if normalized == target and m.isfile():
                    member = m
                    break

            if member is None:
                return {"ok": False, "error": f"member not found: {member_name}"}

            f = tf.extractfile(member)
            if f is None:
                return {"ok": False, "error": "cannot extract member"}

            data = f.read()
            if len(data) > MAX_FILE_SIZE_BYTES:
                return {"ok": False, "error": f"member too large: {len(data)} bytes"}

            mime = mimetypes.guess_type(member_name)[0] or "application/octet-stream"
            b64 = base64.b64encode(data).decode("ascii")

            return {
                "ok": True,
                "data": b64,
                "size": len(data),
                "mime": mime,
            }
    except tarfile.TarError as e:
        return {"ok": False, "error": f"invalid tar: {e}"}
