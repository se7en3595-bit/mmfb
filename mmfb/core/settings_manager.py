"""MMFB 设置管理器

职责：
  1. 通过 QSettings 持久化到 %APPDATA%/mmfb/mmfb.ini
  2. 提供 get / set / reset 分组接口
  3. 默认值由 DEFAULT_SETTINGS 定义，首次运行时写入

分组：
  - general    : 启动行为（默认打开上次文件、恢复窗口位置）
  - display     : 主题、字体大小、沉浸式模式
  - shortcuts  : 快捷键自定义（字符串序列化）
  - about      : 版本号（只读，不需要持久化）

使用：
  settings = MMFBSettings()
  theme = settings.get('display', 'theme')
  settings.set('display', 'theme', 'dark')

性能优化：
  - set() 写入仅更新内存缓存，不立即 sync 到磁盘
  - 通过延迟写入定时器（默认 2s 防抖）批量刷盘，减少 I/O 次数
  - 可手动调用 flush() 强制同步
"""
import os
import json
from PySide6.QtCore import QSettings, QTimer


# ---------- 默认值 ----------
_DEFAULTS = {
    "general": {
        "open_last_file": False,
        "restore_window_geometry": True,
        "check_updates": True,
        "language": "zh-CN",
        "skipped_versions": "[]",
    },
    "display": {
        "theme": "warm",              # warm | light | dark
        "font_size": 14,              # 前端基准字号 px
        "immersive_mode": True,
        "show_footer": True,
    },
    "shortcuts": {
        "open_file": "Ctrl+O",
        "close_window": "Ctrl+W",
        "find": "Ctrl+F",
        "undo": "Ctrl+Z",
        "fullscreen": "F11",
        "command_palette": "Ctrl+K",
        "settings": "Ctrl+,",
    },
}


class MMFBSettings:
    """基于 QSettings 的持久化管理器"""

    def __init__(self, app_name: str = "mmfb"):
        # 用 NativeFormat + UserScope -> %APPDATA%/mmfb/mmfb.ini
        self._settings = QSettings(
            QSettings.Format.NativeFormat,
            QSettings.Scope.UserScope,
            "MMFB",
            app_name,
        )
        # 快速写入用的内存缓冲：full_key -> value
        self._dirty_keys: set = set()
        self._flush_timer = None
        self._ensure_defaults()

    def _ensure_defaults(self):
        """首次启动时将默认值写入 INI"""
        for group, kv in _DEFAULTS.items():
            self._settings.beginGroup(group)
            for key, value in kv.items():
                # 仅在 INI 中不存在时写入
                if not self._settings.contains(key):
                    self._settings.setValue(key, value)
            self._settings.endGroup()
        # 首次启动时立即刷盘（一次性操作，不影响性能）
        self._settings.sync()

    # ---------- 通用接口 ----------

    def get(self, group: str, key: str, default=None):
        """读取某个设置值"""
        full_key = f"{group}/{key}"
        if not self._settings.contains(full_key):
            if default is not None:
                return default
            # 尝试从 _DEFAULTS 取
            return _DEFAULTS.get(group, {}).get(key)
        return self._settings.value(full_key)

    def set(self, group: str, key, value):
        """写入某个设置值（延迟刷盘，默认 2 秒防抖）"""
        full_key = f"{group}/{key}"
        self._settings.setValue(full_key, value)
        self._dirty_keys.add(full_key)
        self._schedule_flush()

    def remove(self, group: str, key: str):
        full_key = f"{group}/{key}"
        self._settings.remove(full_key)
        self._dirty_keys.add(full_key)
        self._schedule_flush()

    def flush(self):
        """强制将内存缓冲写入磁盘

        通常在应用退出前调用，确保最新设置不丢失。
        """
        if self._dirty_keys:
            self._settings.sync()
            self._dirty_keys.clear()
        if self._flush_timer is not None:
            self._flush_timer.stop()
            self._flush_timer = None

    def _schedule_flush(self):
        """调度一次延迟刷盘（2 秒防抖，避免频繁写入）"""
        if self._flush_timer is None:
            self._flush_timer = QTimer()
            self._flush_timer.setSingleShot(True)
            self._flush_timer.setInterval(2000)
            self._flush_timer.timeout.connect(self.flush)
        self._flush_timer.start()  # 重置定时器（防抖）

    def all(self) -> dict:
        """返回全部设置（含默认值）"""
        result = {}
        for group, kv in _DEFAULTS.items():
            result[group] = {}
            for key in kv:
                result[group][key] = self.get(group, key)
        return result

    def reset_group(self, group: str):
        """恢复某个分组到默认值"""
        if group not in _DEFAULTS:
            return
        # 删除分组下所有 key
        self._settings.beginGroup(group)
        self._settings.remove("")  # 清空当前 group
        self._settings.endGroup()
        # 重新写入默认值
        for key, value in _DEFAULTS[group].items():
            self.set(group, key, value)

    def reset_all(self):
        """恢复全部到默认值"""
        for group in _DEFAULTS:
            self.reset_group(group)

    def ini_path(self) -> str:
        """返回当前 INI 文件路径"""
        return self._settings.fileName()


# ---------- 模块级单例 ----------
_settings_instance = None


def get_settings() -> MMFBSettings:
    """返回全局 MMFBSettings 实例"""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = MMFBSettings()
    return _settings_instance
