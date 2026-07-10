"""
Shell extension for "Open With MMFB" – registers a context-menu entry that
passes file paths to the MMFB executable.

The module works both when run from source (Python) and when packaged with
PyInstaller (frozen).
"""

import os
import sys
import winreg
import ctypes
from pathlib import Path

# ----------------------------------------------------------------------
# Public constants
# ----------------------------------------------------------------------
MENU_TITLE = "用 MMFB 打开"
MULTI_SELECT_MODEL = "Player"

# ----------------------------------------------------------------------
# Internal constants
# ----------------------------------------------------------------------
REG_PATH = r"Software\Classes\*\shell\OpenWithMMFB"
COMMAND_PATH = REG_PATH + r"\command"


def _open_key(path, access=None):
    """Open a registry key, creating it if necessary.

    Uses CreateKeyEx for KEY_SET_VALUE (needed for SetValueEx).
    Returns the key handle (not a context manager - caller closes it).
    """
    if access is None:
        access = winreg.KEY_SET_VALUE | winreg.KEY_ALL_ACCESS
    hive, subkey = path.split("\\", 1)
    hive_obj = getattr(winreg, hive)
    # CreateKeyEx: (key, sub_key, reserved=0, access=KEY_ALL_ACCESS)
    return winreg.CreateKeyEx(hive_obj, subkey, 0, access)


def _ensure_registry_keys():
    """Create the base key and set default values (MenuTitle, Icon, MultiSelectModel)."""
    base_key = _open_key(REG_PATH)
    try:
        winreg.SetValueEx(base_key, None, 0, winreg.REG_SZ, MENU_TITLE)
        exe_path = _get_exe_path()
        winreg.SetValueEx(base_key, "Icon", 0, winreg.REG_SZ, f'"{exe_path}",0')
        winreg.SetValueEx(base_key, "MultiSelectModel", 0, winreg.REG_SZ, MULTI_SELECT_MODEL)
    finally:
        winreg.CloseKey(base_key)


def _get_exe_path():
    """Return the path to the current executable (works when frozen or from source)."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return sys.executable


def _refresh_shell_icons():
    """Notify the shell to refresh its icon cache (SHCNE_ASSOCCHANGED)."""
    SHChangeNotify = ctypes.windll.shell32.SHChangeNotify
    SHChangeNotify(0x8000000, 0, None, None)


def is_registered():
    """Check whether the Open With MMFB context menu entry is registered.

    Returns True if the registry key exists and its default value matches MENU_TITLE.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, "")
            return val == MENU_TITLE
    except FileNotFoundError:
        return False
    except OSError:
        return False


def refresh_shell_icons():
    """Notify the shell to refresh its icon cache (SHCNE_ASSOCCHANGED).

    Alias for _refresh_shell_icons exposed at the public module level.
    """
    _refresh_shell_icons()


def register():
    """Register the "Open With MMFB" context menu entry.

    Writes three values to the registry:
      - (default)  = menu title ("用 MMFB 打开")
      - Icon       = path to the MMFB executable
      - MultiSelectModel = "Player"

    Then refreshes the shell icon cache.
    """
    try:
        _ensure_registry_keys()

        # Write the command (overwrites with real exe path)
        exe_path = _get_exe_path()
        cmd_key = _open_key(COMMAND_PATH)
        try:
            winreg.SetValueEx(cmd_key, None, 0, winreg.REG_SZ, f'"{exe_path}" "%1"')
        finally:
            winreg.CloseKey(cmd_key)

        refresh_shell_icons()
        return True
    except Exception:
        return False


def unregister():
    """Remove the "Open With MMFB" context menu entry."""
    try:
        # Delete the whole key tree: first command subkey, then base key
        try:
            winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, COMMAND_PATH, 0, winreg.KEY_SET_VALUE)
        except (FileNotFoundError, OSError):
            pass
        try:
            winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE)
        except (FileNotFoundError, OSError):
            pass
        refresh_shell_icons()
        return True
    except Exception:
        return False


def get_status():
    """Return a dict with registration status and relevant paths.

    Returns:
        dict with keys: registered, menu_title, exe_path, icon_path,
                        command, supports_multi_select, supported
    """
    registered = is_registered()
    exe_path = _get_exe_path()
    icon_path = f'"{exe_path}",0'

    return {
        "registered": registered,
        "menu_title": MENU_TITLE,
        "exe_path": exe_path,
        "icon_path": icon_path,
        "command": f'"{exe_path}" "%1"',
        "supports_multi_select": True,
        "supported": True,
    }


def parse_cli_file_args(argv):
    """
    Extract valid file paths from a typical CLI call like:
        myapp.exe "C:\\file1.pdf" "C:\\file2.png"

    Filtering rules:
      - Skips the executable itself (argv[0])
      - Strips surrounding quotes
      - Ignores paths that do not point to an existing file
      - Ignores .exe files (treated as executables, not data files)

    Returns a list of absolute string paths.
    """
    files = []
    for arg in argv[1:]:  # skip the executable itself
        arg = arg.strip('"')
        if not arg:
            continue
        path = Path(arg).resolve()
        # Skip non-existent paths and executables
        if not path.is_file():
            continue
        if path.suffix.lower() == ".exe":
            continue
        files.append(str(path))
    return files


# ----------------------------------------------------------------------
# Entry point for direct execution (debugging)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("=== Shell Extension Status ===")
    print(get_status())
    print("Parsed args:", parse_cli_file_args(sys.argv))