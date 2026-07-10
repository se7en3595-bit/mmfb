"""Windows 文件关联注册表管理器

职责：
  1. 读取已注册扩展名列表
  2. 在 HKEY_CURRENT_USER\Software\Classes\ 下创建 ProgID 和扩展名关联
  3. 设置 FriendlyTypeName / DefaultIcon / shell\open\command
  4. 调用 SHChangeNotify 刷新图标缓存
  5. 检测当前关联状态，避免重复注册

设计约束：
  - 仅操作 HKEY_CURRENT_USER（不需要管理员权限）
  - 仅注册 Handler 注册表中的扩展名
  - 不覆盖用户已有自定义关联（比较现有 command 是否指向 MMFB）
"""
import ctypes
import os
import sys
import winreg
from typing import List, Optional, Tuple


# ---------- 常量 ----------

PROG_ID = "MMFBUniversalViewer"

FRIENDLY_TYPE_NAME = "MMFB 万能阅览器"

# shell\open\command 的值模板：exe 路径 + "\"%1\""
_COMMAND_TEMPLATE = '"{exe_path}" "%1"'

# SHChangeNotify 标志
SHCNE_ASSOCCHANGED = 0x08000000
SHCNF_IDLIST = 0x0000


# ---------- 注册表操作 ----------


def _exe_path() -> str:
    """返回当前可执行文件路径（支持 PyInstaller 单文件模式）"""
    if getattr(sys, "frozen", False):
        return sys.executable
    # 开发模式：返回 python.exe + main.py
    main_py = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "main.py")
    main_py = os.path.normpath(main_py)
    return f'"{sys.executable}" "{main_py}"'


def _icon_path() -> str:
    """返回默认图标路径（exe 内置 icon,0）"""
    if getattr(sys, "frozen", False):
        return f"{sys.executable},0"
    # 开发模式暂用系统默认图标
    return "%SystemRoot%\\System32\\shell32.dll,42"


def _open_user_classes():
    """打开 HKEY_CURRENT_USER\\Software\\Classes 根键"""
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes", 0, winreg.KEY_READ | winreg.KEY_WRITE)


def _set_value(key, sub_path: str, value_name: str, value_data: str):
    """在 key 下创建子路径并写入值"""
    try:
        with winreg.CreateKeyEx(key, sub_path, 0, winreg.KEY_WRITE) as sub:
            winreg.SetValueEx(sub, value_name, 0, winreg.REG_SZ, value_data)
    except OSError:
        pass


def _get_value(key, sub_path: str, value_name: str) -> Optional[str]:
    """读取子路径下的值，不存在返回 None"""
    try:
        with winreg.OpenKey(key, sub_path, 0, winreg.KEY_READ) as sub:
            data, _ = winreg.QueryValueEx(sub, value_name)
            return data
    except (OSError, FileNotFoundError):
        return None


def _key_exists(key, sub_path: str) -> bool:
    """检查子路径是否存在"""
    try:
        with winreg.OpenKey(key, sub_path, 0, winreg.KEY_READ):
            return True
    except (OSError, FileNotFoundError):
        return False


# ---------- 主接口 ----------


def get_supported_extensions() -> List[str]:
    """从 Handler 注册表收集所有已注册的扩展名，过滤出可用于文件关联的扩展名

    排除复合后缀（如 .tar.gz）、多人共用后缀（.zip/.xml 部分保留）
    """
    from mmfb.core.registry import registry
    all_exts = registry.list_extensions()

    # 过滤：只保留单层后缀且不在排除列表中的扩展名
    excluded = {
        # 这些后缀有多重语义，不应全局关联
        ".s", ".h", ".c", ".mli", ".mpl", ".fs", ".fsx",
    }
    result = []
    for ext in all_exts:
        # 跳过复合后缀
        if "." in ext[1:]:
            continue
        if ext in excluded:
            continue
        result.append(ext)

    return sorted(set(result))


def is_extension_associated(ext: str) -> bool:
    """检查扩展名是否已关联到 MMFB"""
    exe = _exe_path().split('"')[1] if '"' in _exe_path() else _exe_path()
    try:
        root = winreg.HKEY_CURRENT_USER
        # 检查 ProgID 是否指向 MMFB
        prog_id = _get_value(root, f"Software\\Classes{ext}", "")
        if prog_id != PROG_ID:
            return False
        # 再确认 shell\open\command 的 exe 路径正确
        cmd = _get_value(root, f"Software\\Classes\\{PROG_ID}\\shell\\open\\command", "")
        if cmd is None:
            return False
        # 检查 exe 路径是否包含在当前 command 中（允许开发模式/发布模式切换）
        return exe.lower() in cmd.lower()
    except Exception:
        return False


def get_association_status() -> Tuple[int, int]:
    """返回 (已关联数量, 总数量)"""
    extensions = get_supported_extensions()
    total = len(extensions)
    associated = sum(1 for ext in extensions if is_extension_associated(ext))
    return associated, total


def associate_extension(ext: str, exe_path: str = "", icon_path: str = "") -> bool:
    """注册单个扩展名到 MMFB

    Args:
        ext: 扩展名，如 '.pdf'
        exe_path: 可选，覆盖默认 exe 路径
        icon_path: 可选，覆盖默认图标路径

    Returns:
        True 表示成功注册，False 表示失败
    """
    if not exe_path:
        exe_path = _exe_path()
    if not icon_path:
        icon_path = _icon_path()

    command = _COMMAND_TEMPLATE.format(exe_path=exe_path) if '"' not in exe_path or '.py' in exe_path else f'"{exe_path}" "%1"'

    try:
        root = winreg.HKEY_CURRENT_USER
        classes_path = r"Software\Classes"

        # 1. 设置扩展名的默认值为 ProgID
        _set_value(root, f"{classes_path}{ext}", "", PROG_ID)

        # 2. 设置 FriendlyTypeName
        _set_value(root, f"{classes_path}{ext}", "FriendlyTypeName", FRIENDLY_TYPE_NAME)
        _set_value(root, f"{classes_path}{ext}", "PerceivedType", "document")

        # 3. 创建 ProgID 节点
        _set_value(root, f"{classes_path}\\{PROG_ID}", "", FRIENDLY_TYPE_NAME)
        _set_value(root, f"{classes_path}\\{PROG_ID}\\DefaultIcon", "", icon_path)
        _set_value(root, f"{classes_path}\\{PROG_ID}\\shell\\open\\command", "", command)

        # 4. 设置 ProgID 的 FriendlyTypeName
        _set_value(root, f"{classes_path}\\{PROG_ID}", "FriendlyTypeName", FRIENDLY_TYPE_NAME)

        return True
    except Exception as e:
        print(f"[FileAssociation] Failed to associate {ext}: {e}")
        return False


def unregister_extension(ext: str) -> bool:
    """移除单个扩展名的 MMFB 关联

    Args:
        ext: 扩展名，如 '.pdf'

    Returns:
        True 表示成功移除
    """
    try:
        root = winreg.HKEY_CURRENT_USER
        classes_path = r"Software\Classes"

        # 获取当前 ProgID，只有是 MMFB 才删除
        current_prog_id = _get_value(root, f"{classes_path}{ext}", "")
        if current_prog_id != PROG_ID:
            return False

        # 删除扩展名键
        try:
            winreg.DeleteKey(root, f"{classes_path}{ext}")
        except OSError:
            pass

        return True
    except Exception as e:
        print(f"[FileAssociation] Failed to unregister {ext}: {e}")
        return False


def associate_all(exe_path: str = "", icon_path: str = "") -> Tuple[int, int]:
    """批量注册所有支持的扩展名

    Args:
        exe_path: 可选，覆盖默认 exe 路径
        icon_path: 可选，覆盖默认图标路径

    Returns:
        (成功数量, 失败数量)
    """
    extensions = get_supported_extensions()
    success = 0
    failed = 0

    for ext in extensions:
        if associate_extension(ext, exe_path, icon_path):
            success += 1
        else:
            failed += 1

    return success, failed


def unregister_all() -> Tuple[int, int]:
    """批量移除所有 MMFB 关联

    Returns:
        (成功数量, 失败数量)
    """
    extensions = get_supported_extensions()
    success = 0
    failed = 0

    for ext in extensions:
        if unregister_extension(ext):
            success += 1
        else:
            failed += 1

    return success, failed


def is_elevation_required() -> bool:
    """当前实现不需要管理员权限（只操作 HKCU）"""
    return False


def refresh_shell_icons():
    """调用 SHChangeNotify 通知系统图标关联已变更"""
    try:
        ctypes.windll.shell32.SHChangeNotify(
            SHCNE_ASSOCCHANGED,
            SHCNF_IDLIST,
            None,
            None
        )
    except Exception:
        pass


def is_first_launch() -> bool:
    """检查是否是首次启动（无文件关联记录）"""
    associated, total = get_association_status()
    return associated == 0 and total > 0


# ---------- 快捷查询 ----------


def get_registry_summary() -> dict:
    """返回注册表状态的摘要信息，供 Bridge 调用"""
    associated, total = get_association_status()
    exe = _exe_path()
    icon = _icon_path()

    return {
        "associated": associated,
        "total": total,
        "exe_path": exe,
        "icon_path": icon,
        "prog_id": PROG_ID,
        "friendly_name": FRIENDLY_TYPE_NAME,
        "elevation_required": is_elevation_required(),
        "first_launch": is_first_launch(),
    }
