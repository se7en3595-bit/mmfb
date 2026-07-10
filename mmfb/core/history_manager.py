"""MMFB 历史记录管理器

职责：
  1. 维护最近打开的 50 个文件记录（history.json）
  2. 每条记录：path / name / ext / mime / timestamp
  3. 启动时去重并清理不存在的路径
  4. 新记录插入头部，按时间倒序排列

存储位置：%APPDATA%/mmfb/history.json
"""
import json
import os
import time

from PySide6.QtCore import QStandardPaths, QDir


MAX_HISTORY = 50


def _history_file_path() -> str:
    """返回 history.json 的完整路径，必要时创建父目录"""
    data_dir = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    # AppDataLocation 在 Windows 下通常是 .../AppData/Roaming/MMFB
    dir_obj = QDir(data_dir)
    if not dir_obj.exists():
        QDir().mkpath(data_dir)
    return os.path.join(data_dir, "history.json")


class HistoryManager:
    """历史记录读写器"""

    def __init__(self, file_path: str = None):
        self._file_path = file_path or _history_file_path()
        self._records = []
        self._load()
        self._cleanup()

    # ---------- 内部 IO ----------

    def _load(self):
        """从 JSON 文件读取记录"""
        if not os.path.isfile(self._file_path):
            self._records = []
            return
        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._records = data
            else:
                self._records = []
        except (json.JSONDecodeError, OSError):
            self._records = []

    def _save(self):
        """持久化到 JSON 文件"""
        dir_name = os.path.dirname(self._file_path)
        if not os.path.isdir(dir_name):
            QDir().mkpath(dir_name)
        try:
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump(self._records, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _cleanup(self):
        """移除 path 不存在的记录 + 去重 + 截断"""
        seen = set()
        cleaned = []
        for rec in self._records:
            path = rec.get("path", "")
            if not path:
                continue
            # 去重（保留第一条）
            if path in seen:
                continue
            seen.add(path)
            # 检查文件是否存在（仅当文件确实不存在时才移除）
            if os.path.isfile(path):
                cleaned.append(rec)
            # 不存在的文件直接丢弃
        # 截断
        self._records = cleaned[:MAX_HISTORY]
        if len(cleaned) != len(self._records):
            self._save()

    # ---------- 公共接口 ----------

    def add(self, path: str, name: str = None, ext: str = None, mime: str = None):
        """添加一条记录（如已存在则更新时间戳并移到头部）"""
        if not path:
            return
        # 移除旧记录（同 path）
        self._records = [r for r in self._records if r.get("path") != path]
        entry = {
            "path": path,
            "name": name or os.path.basename(path),
            "ext": ext or _guess_ext(path),
            "mime": mime or "",
            "timestamp": int(time.time()),
        }
        self._records.insert(0, entry)
        # 截断
        if len(self._records) > MAX_HISTORY:
            self._records = self._records[:MAX_HISTORY]
        self._save()

    def get_all(self) -> list:
        """返回全部记录（按时间倒序）"""
        return list(self._records)

    def count(self) -> int:
        return len(self._records)

    def clear(self):
        """清空全部历史"""
        self._records = []
        self._save()

    def remove(self, path: str):
        """移除指定 path 的记录"""
        before = len(self._records)
        self._records = [r for r in self._records if r.get("path") != path]
        if len(self._records) < before:
            self._save()

    def file_path(self) -> str:
        return self._file_path


def _guess_ext(path: str) -> str:
    """从路径提取小写扩展名（不含 dot）"""
    _, ext = os.path.splitext(path)
    return ext.lstrip(".").lower()


# ---------- 模块级单例 ----------

_instance = None


def get_history() -> HistoryManager:
    """返回全局单例"""
    global _instance
    if _instance is None:
        _instance = HistoryManager()
    return _instance
