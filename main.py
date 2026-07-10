"""MMFB Windows - 万能阅览器入口"""
import os
import sys
import logging
import faulthandler
import traceback as _traceback

# === 诊断日志配置 ===
def _setup_logging():
    """配置日志：写入用户可写目录，同时输出到 stderr（如有控制台）"""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        log_dir = os.path.join(appdata, "MMFB", "logs")
    else:
        log_dir = os.path.join(os.path.expanduser("~"), ".mmfb", "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "mmfb_latest.log")
    c_log_file = os.path.join(log_dir, "mmfb_c_crash.log")

    cfg = {
        "level": logging.DEBUG,
        "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    }

    handlers = [logging.FileHandler(log_file, mode="w", encoding="utf-8")]
    if hasattr(sys, "_getframe"):
        try:
            handlers.append(logging.StreamHandler(sys.stderr))
        except Exception:
            pass

    logging.basicConfig(**cfg, handlers=handlers)

    return log_file, c_log_file

_diag_log, _c_log = _setup_logging()

def _diag(msg):
    logging.debug(msg)
    try:
        print(f"[DIAG] {msg}", flush=True)
    except Exception:
        pass

def _excepthook(etype, val, tb):
    _diag(f"!!! Unhandled Python Exception: {etype.__name__}: {val}")
    _diag("".join(_traceback.format_exception(etype, val, tb)))
    sys.__excepthook__(etype, val, tb)

sys.excepthook = _excepthook
try:
    faulthandler.enable(file=open(_c_log, "w"))
except Exception:
    faulthandler.enable()

_diag(f"Python {sys.version}")
_diag(f"CWD: {os.getcwd()}")
_diag(f"Log file: {_diag_log}")

def open_log_file():
    """打开日志文件供用户查看"""
    try:
        if sys.platform == "win32":
            os.startfile(_diag_log)
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", _diag_log])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", _diag_log])
        return True
    except Exception as e:
        _diag(f"open_log_file failed: {e}")
        return False
# === END 诊断日志 ===

# CLI 必须在导入任何 Qt 模块前处理（避免 QApplication 初始化开销）
if "--help" in sys.argv or "-h" in sys.argv:
    print("MMFB Windows - 万能阅览器")
    print()
    print("用法：")
    print("  MMFB.exe <file1> [file2 ...]   打开给定文件")
    print("  MMFB.exe --version             打印版本号")
    print("  MMFB.exe --help                打印帮助")
    sys.exit(0)

from mmfb.version import MMFB_VERSION

if "--version" in sys.argv or "-V" in sys.argv:
    print(f"MMFB {MMFB_VERSION}")
    sys.exit(0)

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QTimer
from mmfb.core.window import MainWindow
from mmfb.core.window_manager import get_window_manager


def _prompt_file_association(window):
    """首次启动时提示用户注册文件关联"""
    try:
        from mmfb.services.file_association import is_first_launch, get_association_status
        if not is_first_launch():
            return

        status = get_association_status()
        if status.get("total", 0) == 0:
            return

        # 如全部已关联则不需要提示
        if status.get("associated", 0) == status.get("total", 0):
            return

        # 弹窗提示
        msg = QMessageBox(window)
        msg.setWindowTitle("关联文件格式")
        msg.setText(
            "检测到系统中有 {} 个支持的文件格式，其中 {} 个已关联到 MMFB。\n\n"
            "是否立即让 MMFB 关联所有支持的文件格式？\n"
            "双击文件时即可在 MMFB 中打开。".format(
                status.get("total", 0),
                status.get("associated", 0),
            )
        )
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        msg.setIcon(QMessageBox.Icon.Question)

        ret = msg.exec()
        if ret == QMessageBox.StandardButton.Yes:
            from mmfb.services.file_association import associate_all, refresh_shell_icons
            associate_all()
            refresh_shell_icons()
    except Exception:
        pass


def _open_cli_files(mgr, files):
    """从命令行打开多个文件

    策略：
      1. 若接收到的文件数 >= 2，第一个在新窗口打开，其余文件在新建窗口依次加载
      2. 若只传一个文件，打开一个窗口并加载该文件
      3. 若没有文件，也至少创建一个空窗口
    """
    if not files:
        return mgr.new_window()

    first_file = str(files[0])
    win = mgr.new_window(first_file)

    # 其余文件：每个一个新窗口，延迟加载避免启动时卡顿
    for i, path in enumerate(files[1:], start=1):
        new_win = mgr.new_window()
        new_win.show()
        QTimer.singleShot(
            100 + i * 150,
            lambda p=str(path), w=new_win: w.load_file(p)
        )

    return win


def _configure_chromium_flags():
    """配置 Chromium 启动参数，优化内存与启动速度

    参数说明：
    - --single-process: 单进程模式，QtWebEngine 不再启动子进程，
      节省约 80-150 MB 内存，减少进程创建开销。注意：单进程模式下
      QWebEngineView 仅用于展示本地 HTML，无跨站安全风险。
    - --disable-gpu: 禁用 GPU 加速渲染。MMFB 的前端资源为
      文档/图像渲染，无需 GPU 合成，禁用后可减少 30-50 MB 内存。
    - --disable-gpu-compositing: 禁用 GPU 合成，避免 Chromium
      占用 OpenGL/Vulkan 上下文。
    - --disable-software-rasterizer: 禁用软件栅格化器，避免
      与 disable-gpu 冲突导致的警告。
    - --disable-features=TranslateUI,BackForwardCache: 禁用不需要的
      内置功能（翻译提示、页面缓存）。
    """
    flags = [
        # "--single-process",  # 禁用单进程模式，防止渲染器崩溃
        # "--disable-gpu",     # 临时启用 GPU，排除 GPU 驱动不兼容问题
        "--disable-gpu-compositing",
        "--disable-software-rasterizer",
        "--disable-features=TranslateUI,BackForwardCache,AcceptCHFrame",
        "--no-sandbox",
        "--allow-file-access-from-files",  # 允许 file:// 协议下 fetch 本地文件（PDF.js 加载模块和读取 PDF 必需）
        "--enable-logging=stderr",
        "--v=1",
    ]
    current = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    if current:
        flags.insert(0, current)
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(flags)


def main():
    _diag("=== main() 进入 ===")

    # 在 QApplication 创建前设置 Chromium 标志（必须在 QApplication 之前生效）
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

    # 配置 Chromium 参数（必须在 QApplication 之前设置环境变量）
    _configure_chromium_flags()
    _diag(f"Chromium flags: {os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '(none)')}")

    _diag("导入 PySide6 窗口模块...")
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        from PySide6.QtCore import Qt, QTimer
        from mmfb.core.window import MainWindow
        from mmfb.core.window_manager import get_window_manager
        _diag("PySide6 模块导入成功")
    except Exception as e:
        _diag(f"导入异常: {e}")
        raise

    _diag("创建 QApplication...")
    app = QApplication(sys.argv)
    app.setApplicationName("MMFB")
    app.setOrganizationName("MMFB")
    _diag("QApplication 创建成功")

    # 解析命令行传入的文件路径（右键菜单 / 命令行拖入）
    cli_files = []
    if sys.platform == "win32":
        from mmfb.services.shell_extension import parse_cli_file_args
        _diag("调用 parse_cli_file_args()...")
        try:
            cli_files = parse_cli_file_args(sys.argv)
            _diag(f"命令行文件: {cli_files}")
        except Exception as e:
            _diag(f"parse_cli_file_args 异常: {e}")
            cli_files = []

    _diag("获取 WindowManager...")
    mgr = get_window_manager()
    _diag("WindowManager 获取成功")

    _diag("创建主窗口...")
    if cli_files:
        window = _open_cli_files(mgr, cli_files)
    else:
        window = mgr.new_window()
    _diag("主窗口创建成功")

    _diag("注入 window 到 bridge...")
    window._bridge.set_window(window)
    _diag("bridge 注入完成")

    _diag("执行 window.show()...")
    window.show()
    _diag("window.show() 完成")

    # 启动时主动将 cli_files 中第一个文件的元信息注入历史
    if cli_files:
        first = str(cli_files[0])
        QTimer.singleShot(200, lambda f=first: window._record_history(
            f,
            os.path.basename(f),
            os.path.splitext(f)[1],
        ))

    # 首次启动文件关联提示（延迟 800ms，确保窗口已显示）
    QTimer.singleShot(800, lambda: _prompt_file_association(window))

    # 启动自动更新检查（窗口自行延时 3s 后发起网络请求）
    _diag("启动自动更新检查...")
    try:
        window.run_startup_update_check()
    except Exception as e:
        _diag(f"自动更新检查异常: {e}")
    _diag("自动更新检查完成")

    _diag("即将进入事件循环 app.exec()")
    exit_code = app.exec()
    _diag(f"事件循环退出，exit_code={exit_code}")

    # 退出前刷盘设置，确保最新配置不丢失
    try:
        from mmfb.core.settings_manager import get_settings
        get_settings().flush()
    except Exception:
        pass

    _diag("调用 mgr.shutdown()...")
    # 安全退出：清理 WindowManager
    mgr.shutdown()
    _diag("mgr.shutdown() 完成")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
