"""Windows 全局热键服务

使用 ``win32api.RegisterHotKey`` 注册系统级热键，
即使 MMFB 窗口最小化或失去焦点也能响应。

当前默认热键: Ctrl+Alt+O — 激活/置顶 MMFB 主窗口

架构:
- 后台 daemon 线程负责注册 + 消息轮询（PeekMessage）
- 热键触发时通过 **QObject 信号** (Qt.QueuedConnection) 安全通知主线程
- 应用退出时 UnregisterHotKey 清理

调用示例::

    from mmfb.services.global_hotkey import get_manager
    from PySide6.QtCore import QObject, Signal

    class HotkeySignals(QObject):
        activated = Signal()

    sig = HotkeySignals()
    sig.activated.connect(main_window.activate_window)

    mgr = get_manager()
    mgr.register(description="Ctrl+Alt+O", callback=sig.activated)
"""
import os
import sys
import time
import ctypes
import threading
import logging
from ctypes import wintypes
from typing import Optional, Callable

try:
    from PySide6.QtCore import QObject, Signal, Qt
    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False

logger = logging.getLogger(__name__)

# Windows 消息常量
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
PM_REMOVE = 0x0001

# 热键 ID
HOTKEY_ID = 1


class _MSG(ctypes.Structure):
    """Windows MSG 结构体 (ctypes)"""
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]

# 默认热键: Ctrl+Alt+O
DEFAULT_HOTKEY = "Ctrl+Alt+O"
DEFAULT_MODIFIERS = 0x0002 | 0x0001  # MOD_CONTROL | MOD_ALT
DEFAULT_VK = 0x4F  # VK_O


class GlobalHotkeySignals(QObject if _QT_AVAILABLE else object):
    """热键触发信号。

    在主线程创建实例，通过 ``callback`` 连接到业务逻辑。
    信号通过 Qt.QueuedConnection 自动跨越线程边界。
    """
    activated = Signal() if _QT_AVAILABLE else None


class GlobalHotkeyManager:
    """管理 Windows 全局热键注册。

    单例模式。内部用一个 daemon 线程轮询 Windows 消息队列，
    收到 WM_HOTKEY 后通过 Qt 信号通知主线程。
    """

    _instance: Optional["GlobalHotkeyManager"] = None

    def __init__(self):
        self._modifiers: int = DEFAULT_MODIFIERS
        self._vk: int = DEFAULT_VK
        self._description: str = DEFAULT_HOTKEY
        self._callback: Optional[Callable] = None
        self._qt_signal = None
        self._signal_obj = None
        self._active = False
        self._registered = False
        self._thread: Optional[threading.Thread] = None

    # ---------- 单例 ----------

    @classmethod
    def instance(cls) -> "GlobalHotkeyManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """测试用：重置单例"""
        inst = cls._instance
        if inst:
            try:
                inst.unregister()
            except Exception:
                pass
        cls._instance = None

    # ---------- 热键组合字符串解析 ----------

    @staticmethod
    def parse_hotkey(combo: str) -> tuple:
        """解析热键组合字符串 → (modifiers, vk)。

        支持 "Ctrl+Alt+O" / "Ctrl+Shift+F5" / "Alt+F4" 等格式。
        """
        try:
            import win32con
        except ImportError:
            return (0, 0)

        modifiers = 0
        vk = 0
        parts = [p.strip() for p in combo.split("+")]
        key_part = parts[-1] if parts else ""

        for part in parts[:-1]:
            p = part.lower()
            if p in ("ctrl", "control"):
                modifiers |= win32con.MOD_CONTROL
            elif p == "alt":
                modifiers |= win32con.MOD_ALT
            elif p == "shift":
                modifiers |= win32con.MOD_SHIFT
            elif p in ("win", "lwin", "rwin"):
                modifiers |= win32con.MOD_WIN

        if len(key_part) == 1:
            vk = ord(key_part.upper())
        elif key_part.lower().startswith("f") and key_part[1:].isdigit():
            n = int(key_part[1:])
            if 1 <= n <= 24:
                vk = getattr(win32con, f"VK_F{n}", 0)
        else:
            vk = getattr(win32con, f"VK_{key_part.upper()}", 0)

        return modifiers, vk

    # ---------- 注册 / 注销 ----------

    def register(self, modifiers: int = None, vk: int = None,
                 callback: Callable = None, description: str = None) -> bool:
        """注册全局热键（非阻塞，后台完成）。

        Args:
            modifiers: 修饰键位掩码（默认 Ctrl+Alt）
            vk: 虚拟键码（默认 O）
            callback: QObject 信号 或普通 callable。
                      信号通过 QueuedConnection 安全跨线程。
            description: 热键描述字符串，如 "Ctrl+Alt+O"

        Returns:
            True 表示注册成功
        """
        mods = modifiers if modifiers is not None else self._modifiers
        vk_code = vk if vk is not None else self._vk
        desc = description or self._hotkey_label(mods, vk_code)

        if mods == 0 or vk_code == 0:
            logger.error("[GlobalHotkey] invalid hotkey combo: %s", desc)
            return False

        # 先注销旧注册
        self.unregister()

        # 检查 pywin32
        try:
            import win32gui  # noqa: F401
            import win32con  # noqa: F401
            has_pywin32 = True
        except ImportError:
            logger.error("[GlobalHotkey] pywin32 not available")
            return False

        # 存储描述
        self._description = desc
        self._modifiers = mods
        self._vk = vk_code

        # 保存回调（将在后台线程中安全触发）
        if callback is not None:
            self._callback = callback

        # 启动后台线程
        self._active = True
        self._thread = threading.Thread(
            target=self._run_loop, args=(mods, vk_code, has_pywin32),
            daemon=True, name="global-hotkey"
        )
        self._thread.start()

        # 等待注册结果（上限 3 秒）
        deadline = time.time() + 3.0
        while self._active and time.time() < deadline:
            time.sleep(0.05)

        if not self._registered:
            logger.error("[GlobalHotkey] registration failed for %s", desc)
            self._active = False
            return False

        logger.info("[GlobalHotkey] registered: %s (id=%d)", desc, HOTKEY_ID)
        return True

    def unregister(self) -> bool:
        """注销热键并停止消息线程。

        Returns:
            True
        """
        if not self._active and not self._registered:
            return True

        self._active = False

        # 向消息线程的队列发送消息（使用 PostThreadMessage 如果是 Windows 线程）
        tid = self._thread.ident if self._thread and self._thread.is_alive() else 0
        if tid:
            try:
                import win32api
                win32api.PostThreadMessage(tid, WM_QUIT, 0, 0)
            except Exception:
                pass

        # 等待线程结束
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        self._registered = False
        return True

    def is_active(self) -> bool:
        """消息线程是否正在运行"""
        return self._active

    def is_registered(self) -> bool:
        """是否已成功注册系统热键"""
        return self._registered

    def current_hotkey(self) -> str:
        """返回当前热键描述"""
        return self._description

    def set_callback(self, callback: Callable):
        """更新回调（可在主线程随时调用）"""
        self._callback = callback

    # ---------- 后台线程 ----------

    def _run_loop(self, modifiers: int, vk: int, has_pywin32: bool):
        """后台线程：注册热键 + PeekMessage 轮询。

        必须在同一线程内完成注册和消息处理（Windows API 约束）。
        """
        # 注册热键
        if not self._do_register(modifiers, vk, has_pywin32):
            self._active = False
            self._registered = False
            return

        self._registered = True

        # 消息轮询 (使用 ctypes 直接调用 PeekMessageW，避免 pywin32 参数兼容问题)
        msg = _MSG()
        user32 = ctypes.windll.user32
        while self._active:
            try:
                ret = user32.PeekMessageW(
                    ctypes.byref(msg), 0, 0, 0, PM_REMOVE
                )
                if ret:
                    if msg.message == WM_QUIT:
                        break
                    if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                        # 翻译并分发消息，保持队列健康
                        user32.TranslateMessage(ctypes.byref(msg))
                        user32.DispatchMessageW(ctypes.byref(msg))
                        self._fire_callback()
                else:
                    time.sleep(0.03)
            except Exception as e:
                if self._active:
                    logger.warning("[GlobalHotkey] msg loop error: %s", e)
                    time.sleep(0.1)

        # 清理注册
        try:
            import win32api
            win32api.UnregisterHotKey(0, HOTKEY_ID)
        except Exception:
            pass

        self._registered = False
        self._active = False

    def _do_register(self, modifiers: int, vk: int, has_pywin32: bool) -> bool:
        """执行 RegisterHotKey 调用（win32gui 版本）

        RegisterHotKey 成功时返回 None，失败时抛出 win32gui.error 异常。
        """
        if not has_pywin32:
            return False
        try:
            import win32gui
            import win32con
            # 成功返回 None，失败抛出异常
            win32gui.RegisterHotKey(0, HOTKEY_ID, modifiers, vk)
            return True
        except Exception as e:
            err_msg = str(e)
            if "1409" in err_msg or "already" in err_msg.lower():
                logger.error("[GlobalHotkey] hotkey conflict: %s", self._description)
                self._description = self._description + " (已被占用)"
            else:
                logger.error("[GlobalHotkey] RegisterHotKey exception: %s", e)
            return False

    def _fire_callback(self):
        """热键触发：安全执行回调。

        注意：此方法运行在后台线程。
        - 如果 callback 是 QObject 信号（如 Signal()），直接 emit 通过
          Qt.QueuedConnection 自动传递到主线程
        - 如果 callback 是普通函数，直接调用（线程安全取决于调用方）
        """
        cb = self._callback
        if cb is None:
            return

        if hasattr(cb, 'emit'):
            # QObject 信号：直接 emit（Qt 自动跨线程排队）
            try:
                cb.emit()
            except Exception as e:
                logger.error("[GlobalHotkey] signal emit error: %s", e)
        else:
            # 普通 callable
            try:
                cb()
            except Exception as e:
                logger.error("[GlobalHotkey] callback error: %s", e)

    # ---------- 辅助方法 ----------

    def _hotkey_label(self, modifiers: int, vk: int) -> str:
        """根据 modifiers 和 vk 生成友好描述字符串"""
        parts = []
        try:
            import win32con
            if modifiers & win32con.MOD_CONTROL:
                parts.append("Ctrl")
            if modifiers & win32con.MOD_ALT:
                parts.append("Alt")
            if modifiers & win32con.MOD_SHIFT:
                parts.append("Shift")
            if modifiers & win32con.MOD_WIN:
                parts.append("Win")
        except ImportError:
            pass
        key_name = _vk_to_name(vk)
        if key_name:
            parts.append(key_name)
        return "+".join(parts) if parts else "Unknown"


def _vk_to_name(vk: int) -> str:
    """虚拟键码转名称"""
    if 1 <= vk <= 26:
        return chr(ord("A") + vk - 1)
    if 0x30 <= vk <= 0x39:
        return chr(vk)
    if 0x60 <= vk <= 0x69:
        return f"Num{vk - 0x60}"
    try:
        import win32con
        for i in range(1, 25):
            if getattr(win32con, f"VK_F{i}", 0) == vk:
                return f"F{i}"
    except ImportError:
        pass
    if 0x20 <= vk < 0x7F:
        return chr(vk)
    return ""


# ---------- 便捷全局单例 ----------

_manager = GlobalHotkeyManager.instance()


def register_hotkey(description: str = DEFAULT_HOTKEY, callback: Callable = None) -> bool:
    """快捷注册全局热键。

    Args:
        description: 热键组合，如 "Ctrl+Alt+O"
        callback: QObject 信号 或 callable

    Returns:
        True 表示注册成功
    """
    modifiers, vk = _manager.parse_hotkey(description)
    if modifiers == 0 or vk == 0:
        logger.error("[GlobalHotkey] invalid combo: %s", description)
        return False
    return _manager.register(
        modifiers=modifiers, vk=vk,
        callback=callback, description=description
    )


def get_manager() -> GlobalHotkeyManager:
    """返回全局热键管理器单例"""
    return _manager


def unregister_hotkey() -> bool:
    """注销全局热键"""
    return _manager.unregister()


def is_hotkey_active() -> bool:
    """是否已注册且线程运行中"""
    return _manager.is_active()
