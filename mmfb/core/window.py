"""MMFB 主窗口"""
import json
import logging
import os
import sys
import ctypes
import subprocess
from ctypes import wintypes, Structure, c_ulong, c_void_p, POINTER
logger = logging.getLogger(__name__)

def get_log_dir():
	"""返回用户可写日志目录"""
	if sys.platform == "win32":
		appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
		log_dir = os.path.join(appdata, "MMFB", "logs")
	else:
		log_dir = os.path.join(os.path.expanduser("~"), ".mmfb", "logs")
	os.makedirs(log_dir, exist_ok=True)
	return log_dir

def get_log_file():
	"""返回当前会话日志文件路径"""
	return os.path.join(get_log_dir(), "mmfb_latest.log")

def open_log_file():
	"""用系统默认程序打开日志文件"""
	log_file = get_log_file()
	if not os.path.exists(log_file):
		return False
	try:
		if sys.platform == "win32":
			os.startfile(log_file)
		elif sys.platform == "darwin":
			subprocess.Popen(["open", log_file])
		else:
			subprocess.Popen(["xdg-open", log_file])
		return True
	except Exception:
		return False
from PySide6.QtWidgets import (
	QMainWindow, QVBoxLayout, QWidget, QApplication, QStackedWidget,
	QSystemTrayIcon, QMessageBox
)
from PySide6.QtCore import (
	Qt, QUrl, QPoint, QTimer, QEvent, QRect, QAbstractNativeEventFilter
)
from PySide6.QtGui import QResizeEvent, QMouseEvent, QKeyEvent, QPalette, QColor, QDragEnterEvent, QDropEvent
from PySide6.QtWebChannel import QWebChannel

from mmfb.core.title_bar import TitleBar
from mmfb.core.bridge import MMFBBridge
from mmfb.core.settings_manager import get_settings
from mmfb.core.tray_icon import TrayIcon


# ========== Windows 原生拖拽过滤器 ==========
class _NativeDDMessage(Structure):
	_fields_ = [
		("hwnd", wintypes.HWND),
		("message", wintypes.UINT),
		("wParam", wintypes.WPARAM),
		("lParam", wintypes.LPARAM),
		("time", wintypes.DWORD),
		("pt_x", wintypes.LONG),
		("pt_y", wintypes.LONG),
	]

class _NativeDragDropFilter(QAbstractNativeEventFilter):
	"""拦截 Windows WM_DROPFILES 消息，解决 QWebEngineView(Chromium) 吃拖拽的问题"""

	def __init__(self, callback):
		super().__init__()
		self._cb = callback

	def nativeEventFilter(self, eventType, message):
		if eventType != b'windows_generic_MSG':
			return False, 0
		try:
			msg = ctypes.cast(message, POINTER(_NativeDDMessage)).contents
		except Exception:
			return False, 0
		if msg.message != 0x0233:  # WM_DROPFILES
			return False, 0
		logger.debug("[NativeFilter] WM_DROPFILES received, wParam=%s", hex(msg.wParam))
		hDrop = msg.wParam
		try:
			file_count = ctypes.windll.shell32.DragQueryFileW(hDrop, 0xFFFFFFFF, None, 0)
		except Exception as e:
			logger.warning("[NativeFilter] DragQueryFileW failed: %s", e)
			return False, 0
		paths = []
		for i in range(file_count):
			try:
				length = ctypes.windll.shell32.DragQueryFileW(hDrop, i, None, 0)
			except Exception:
				continue
			if length < 1:
				continue
			buf = ctypes.create_unicode_buffer(length + 1)
			try:
				ctypes.windll.shell32.DragQueryFileW(hDrop, i, buf, length + 1)
			except Exception:
				continue
			paths.append(buf.value)
		logger.debug("[NativeFilter] extracted %d paths: %s", len(paths), paths[:3])
		try:
			ctypes.windll.shell32.DragFinish(hDrop)
		except Exception:
			pass
		if paths and self._cb:
			logger.debug("[NativeFilter] invoking callback with hwnd=%s", hex(msg.hwnd))
			self._cb(paths, msg.hwnd)
		else:
			logger.debug("[NativeFilter] no paths or no callback")
		return True, 0

_NDD_CALLBACK = None  # 由 MainWindow.__init__ 赋值

from mmfb.services.global_hotkey import GlobalHotkeySignals, get_manager

HOTZONE_HEIGHT = 40
AUTOHIDE_DELAY_MS = 2000

_THEME_COLORS = {
	"light": {
		"bg": "#FFFFFF",
		"bg_elevated": "#F7F7F8",
		"text_primary": "#1A1A1E",
		"text_secondary": "#5C5C64",
		"border": "#E0E0E5",
		"accent": "#C47A3D",
	},
	"dark": {
		"bg": "#1E1E22",
		"bg_elevated": "#26262C",
		"text_primary": "#E8E8EC",
		"text_secondary": "#A8A8B0",
		"border": "#35353D",
		"accent": "#D6894A",
	},
	"warm": {
		"bg": "#C7EDCC",
		"bg_elevated": "#D9F0DC",
		"text_primary": "#1E3A24",
		"text_secondary": "#4A6B50",
		"border": "#8BA888",
		"accent": "#C47A3D",
	},
}

class MainWindow(QMainWindow):
	"""MMFB 主窗口

	支持模式：
	- 单视图模式：默认，一个 webview 占满
	- 分屏模式：左右两个 webview 加载不同文件

	通过 window_manager 参数关联到 WindowManager
	"""

	def __init__(self, window_manager=None):
		super().__init__()

		self._window_manager = window_manager
		self._split_mode = False
		self._webview_handles = {}  # hwnd -> webview mapping
		self._split_view = None  # SplitView 实例
		self._webview_handles = {}  # hwnd -> webview 映射，用于原生拖拽路由

		self._init_window_flags()
		self._init_dwm_shadow()
		self._init_ui()
		# Register native Win32 drag-drop filter
		global _NDD_CALLBACK
		_NDD_CALLBACK = self._on_native_drop_files
		self._dd_filter = _NativeDragDropFilter(_NDD_CALLBACK)
		from PySide6.QtWidgets import QApplication
		QApplication.instance().installNativeEventFilter(self._dd_filter)

		# 沉浸式定时器
		self._hide_timer = QTimer(self)
		self._hide_timer.setSingleShot(True)
		self._hide_timer.timeout.connect(self._on_hide_timeout)

		# 鼠标追踪状态
		self._mouse_in_hotzone = False
		self._immersive_mode = True
		self._header_auto_hide = False  # 启动后固定显示标题栏
		self._suppress_auto_hide = False  # 拖入文件后短暂抑制自动隐藏

		self._current_theme = "warm"

		# 系统托盘
		self._tray_icon = None
		self._minimize_to_tray = True  # 默认启用：关闭/最小化均隐藏到托盘
		self._init_tray_icon()

		self.setMouseTracking(True)
		self._central.setMouseTracking(True)

		self._load_theme()

		# 全局热键
		if sys.platform == "win32":
			try:
				self._hotkey_signals = GlobalHotkeySignals()
				self._hotkey_signals.activated.connect(self.activate_window)
				get_manager().register(
					description="Ctrl+Alt+O",
					callback=self._hotkey_signals.activated,
				)
			except Exception as e:
				logger.warning("[MainWindow] global hotkey init failed: %s", e)
				self._hotkey_signals = None
		else:
			self._hotkey_signals = None

	def _init_window_flags(self):
		self.setWindowFlags(
			Qt.WindowType.FramelessWindowHint
			| Qt.WindowType.WindowSystemMenuHint
			| Qt.WindowType.WindowMinimizeButtonHint
			| Qt.WindowType.WindowMaximizeButtonHint
		)
		self.resize(1280, 800)
		self.setMinimumSize(800, 500)
		self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

	def _init_dwm_shadow(self):
		if sys.platform != "win32":
			return
		try:
			dwmapi = ctypes.windll.dwmapi
			hwnd = wintypes.HWND(int(self.winId()))
			class MARGINS(ctypes.Structure):
				_fields_ = [
					("cxLeftWidth", ctypes.c_int),
					("cxRightWidth", ctypes.c_int),
					("cyTopHeight", ctypes.c_int),
					("cyBottomHeight", ctypes.c_int),
				]
			margins = MARGINS(-1, -1, -1, -1)
			dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
		except Exception as e:
			pass

	def _init_ui(self):
		self._central = QWidget()
		self._central.setObjectName("mainCentral")
		self.setCentralWidget(self._central)

		self._layout = QVBoxLayout(self._central)
		self._layout.setContentsMargins(0, 0, 0, 0)
		self._layout.setSpacing(0)

		self._title_bar = TitleBar(self)
		self._title_bar.title_bar_double_clicked.connect(self._toggle_maximize)
		self._layout.addWidget(self._title_bar)

		self._stack = QStackedWidget()
		self._layout.addWidget(self._stack, 1)

		self._single_container = QWidget()
		self._single_layout = QVBoxLayout(self._single_container)
		self._single_layout.setContentsMargins(0, 0, 0, 0)
		self._single_layout.setSpacing(0)

		self._stack.addWidget(self._single_container)

		self._setup_webengine()
		self.setAcceptDrops(True)  # Qt drag events (for non-Win32 or fallback)

	def _setup_webengine(self):
		"""初始化 WebEngine（必须在 QApplication 创建后调用）"""
		# 延迟导入：只有在 QApplication 创建后才能导入 QtWebEngine
		from PySide6.QtWebEngineWidgets import QWebEngineView
		from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings

		# 创建 webview 并添加到容器
		self._webview = QWebEngineView(self._single_container)
		self._single_layout.addWidget(self._webview)

		# 安装拖拽事件过滤器（QWebEngineView 拦截原生拖拽，需转发给 MainWindow）
		self._webview.installEventFilter(self)
		self._webview.setAcceptDrops(False)

		# 配置 Profile 和 Page
		from mmfb.core.webview import _get_shared_profile
		profile = _get_shared_profile()
		page = QWebEnginePage(profile, self._webview)
		self._webview.setPage(page)

		# 配置设置
		settings = self._webview.settings()
		settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
		settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
		settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

		# 为单屏 webview 注册原生拖拽（窗口句柄现已创建）
		if sys.platform == "win32":
		    try:
		        import ctypes
		        hwnd = int(self._webview.winId())
		        ctypes.windll.shell32.DragAcceptFiles(hwnd, True)
		        self._webview_handles[hwnd] = self._webview
		        logger.debug("[Drag] Single webview registered: hwnd=%s", hex(hwnd))
		    except Exception as e:
		        logger.warning("[Drag] Single webview registration failed: %s", e)
		# 初始化 Bridge
		self._init_bridge()

		# 加载 index.html
		index_path = os.path.join(
			os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
			"frontend", "index.html"
		)
		if os.path.exists(index_path):
			self._webview.setUrl(QUrl.fromLocalFile(index_path))
		else:
			self._webview.setHtml("<h1>MMFB Windows</h1>")

	def _init_bridge(self):
		self._bridge = MMFBBridge()
		self._channel = QWebChannel()
		self._channel.registerObject("pybridge", self._bridge)
		self._webview.page().setWebChannel(self._channel)

		self._bridge.filesDropped.connect(self._on_files_dropped)
		self._bridge.windowTitleChangeRequested.connect(self._on_window_title_changed)
		self._bridge.headerVisibilityChanged.connect(self._on_header_visibility_changed)
		self._bridge.showCommandPanel.connect(self._on_show_command_panel)
		self._bridge.openSettings.connect(self._on_open_settings)
		self._bridge.systemThemeChanged.connect(self._on_system_theme_changed)
		self._bridge.themeChanged.connect(self.apply_native_theme)
		self.destroyed.connect(self._on_destroyed)

	def _on_destroyed(self, obj=None):
		mgr = self._window_manager
		if mgr is not None:
			try:
				mgr._unregister(self)
			except Exception:
				pass

	def _init_tray_icon(self):
		if not QSystemTrayIcon.isSystemTrayAvailable():
			return
		self._tray_icon = TrayIcon(parent=self)
		self._tray_icon.setup(main_window=self, app_name="MMFB")

	def _load_theme(self):
		theme = get_settings().get("display", "theme", "warm")
		if theme not in _THEME_COLORS:
			theme = "warm"
		self.apply_native_theme(theme)

	def apply_native_theme(self, theme_name):
		if theme_name not in _THEME_COLORS:
			return
		self._current_theme = theme_name
		colors = _THEME_COLORS[theme_name]
		self.setStyleSheet("QMainWindow { background: " + colors["bg"] + "; } #mainCentral { background: " + colors["bg"] + "; }")
		palette = QPalette()
		palette.setColor(QPalette.ColorRole.Window, QColor(colors["bg"]))
		palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["text_primary"]))
		palette.setColor(QPalette.ColorRole.Base, QColor(colors["bg"]))
		palette.setColor(QPalette.ColorRole.Text, QColor(colors["text_primary"]))
		palette.setColor(QPalette.ColorRole.Button, QColor(colors["bg_elevated"]))
		palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["text_primary"]))
		palette.setColor(QPalette.ColorRole.Highlight, QColor(colors["accent"]))
		self.setPalette(palette)
		if hasattr(self, "_title_bar") and self._title_bar:
			self._apply_title_bar_theme(theme_name)

	def _apply_title_bar_theme(self, theme_name):
		colors = _THEME_COLORS.get(theme_name, _THEME_COLORS["warm"])
		bar = self._title_bar
		if bar is None:
			return
		bar.setStyleSheet("#titleBar { background: " + colors["bg"] + "; border-bottom: 1px solid " + colors["border"] + "; }")
		bar.title_label.setStyleSheet("color: " + colors["text_secondary"] + ";")

	def notify_frontend_theme(self, theme_name):
		if hasattr(self, "_bridge") and self._bridge:
			js = "if (window.MMFBTheme) window.MMFBTheme.set(\"" + theme_name + "\", false);"
			self._webview.page().runJavaScript(js)

	def _on_system_theme_changed(self, theme_name):
		is_dark = theme_name == "dark"
		try:
			user_theme = get_settings().get("display", "theme", None)
			if user_theme in ("light", "dark", "warm"):
				return
		except Exception:
			pass
		self.apply_native_theme("dark" if is_dark else "light")

	def _on_files_dropped(self, payload):
		try:
			data = json.loads(payload)
			files = data.get("files", [])
			if files:
				first = files[0]
				self._record_history(first.get("path", ""), first.get("name", ""), first.get("ext", ""))
		except (json.JSONDecodeError, KeyError):
			pass

	def _record_history(self, path, name, ext):
		try:
			from mmfb.core.history_manager import get_history
			get_history().add(path, name, ext, "")
		except Exception:
			pass

	def eventFilter(self, obj, event):
	    """转发 QWebEngineView 的拖拽事件到 MainWindow"""
	    if obj is self._webview:
	        from PySide6.QtCore import QEvent as _QEvt
	        if event.type() == _QEvt.Type.DragEnter:
	            self.dragEnterEvent(event)
	            return True
	        elif event.type() == _QEvt.Type.DragMove:
	            return True
	        elif event.type() == _QEvt.Type.Drop:
	            self.dropEvent(event)
	            return True
	    return super(MainWindow, self).eventFilter(obj, event)

	def dragEnterEvent(self, event):
		mime = event.mimeData()
		if not mime.hasUrls():
			event.ignore()
			return
		has_local = False
		for url in mime.urls():
			if url.isLocalFile():
				path = url.toLocalFile()
				if os.path.isfile(path):
					has_local = True
					break
		if has_local:
			event.acceptProposedAction()
		else:
			event.ignore()

	def _on_native_drop_files(self, file_paths, hwnd=None):
		"""Native Win32 drag-drop: process same as dropEvent"""
		logger.debug("[NativeDrop] received %d files: %s", len(file_paths), file_paths[:3])
		logger.debug("[NativeDrop] hwnd=%s", hex(hwnd) if hwnd else "None")
		if not file_paths:
			return
		import json, os
		dropped = []
		for p in file_paths:
			if not os.path.isfile(p):
				continue
			name = os.path.basename(p)
			ext = os.path.splitext(name)[1].lstrip('.').lower()
			dropped.append({'name': name, 'path': p, 'ext': ext})
		if not dropped:
			return
		# 智能路由：如果 hwnd 已映射到某个 webview，则直接加载到该 view（分屏模式）
		target_view = None
		if hwnd is not None and hasattr(self, "_webview_handles") and self._webview_handles:
		    target_view = self._webview_handles.get(hwnd)
		    if target_view is not None and self._split_mode and target_view is not self._webview:
		        logger.debug("[NativeDrop] Routing to mapped webview (hwnd=%s)", hex(hwnd))
		        try:
		            self._load_file_in_view(target_view, dropped[0]['path'])
		        except Exception as e:
		            logger.error("[NativeDrop] Direct load failed: %s", e)
		        # 剩余文件处理
		        if len(dropped) > 1 and hasattr(self, "_split_view") and self._split_mode:
		            other_view = self._split_view.right_view if target_view is self._split_view.left_view else self._split_view.left_view
		            try:
		                self._load_file_in_view(other_view, dropped[1]['path'])
		            except Exception as e:
		                logger.error("[NativeDrop] Second file load failed: %s", e)
		        return  # 直接加载完成，不再发射信号
		# 单屏模式或无 hwnd 映射，fallback 到前端路由（通过 bridge 信号）
		payload = json.dumps({'type': 'filesDropped', 'files': dropped}, ensure_ascii=False)
		logger.debug("[NativeDrop] emitting filesDropped payload: %s", payload[:200])
		if hasattr(self, '_bridge') and self._bridge:
			self._bridge.filesDropped.emit(payload)
			self._record_history(dropped[0]['path'], dropped[0]['name'], dropped[0]['ext'])
			self._suppress_auto_hide_for(3000)
			self._show_header()
		else:
			logger.warning("[NativeDrop] bridge not ready, dropping payload")

	def dropEvent(self, event):
		try:
			mime = event.mimeData()
			if not mime.hasUrls():
				event.ignore()
				return
			MAX_FILE_SIZE = 50 * 1024 * 1024
			dropped_files = []
			for url in mime.urls():
				if not url.isLocalFile():
					continue
				path = url.toLocalFile()
				if not os.path.isfile(path):
					continue
				try:
					if os.path.getsize(path) > MAX_FILE_SIZE:
						continue
				except OSError:
					continue
				name = os.path.basename(path)
				ext = os.path.splitext(name)[1].lstrip(".").lower()
				dropped_files.append({"name": name, "path": path, "ext": ext})
			if not dropped_files:
				event.ignore()
				return
			event.acceptProposedAction()
			payload = json.dumps({"type": "filesDropped", "files": dropped_files}, ensure_ascii=False)
			self._bridge.filesDropped.emit(payload)
			if dropped_files:
				self._record_history(dropped_files[0]["path"], dropped_files[0]["name"], dropped_files[0]["ext"])
				self._suppress_auto_hide_for(3000)
				self._show_header()
		except Exception as e:
			logger.error("[dropEvent] error: %s", e)
			event.ignore()

	def check_file_association_on_first_launch(self):
		if sys.platform != "win32":
			return
		try:
			from mmfb.services.file_association import is_first_launch
			if is_first_launch():
				self._bridge.messageReceived.emit(json.dumps({
					"type": "file_association_prompt",
					"title": "关联文件格式",
					"message": "检测到尚未将 MMFB 注册为默认打开程序。\n\n是否立即关联？"
				}))
		except Exception:
			pass

	def load_file(self, file_path):
		file_path = str(file_path)
		self.setWindowTitle(file_path)
		if self._title_bar:
			self._title_bar.set_title(os.path.basename(file_path))
		if hasattr(self, "_bridge") and self._bridge:
			import json
			name = os.path.basename(file_path)
			ext = os.path.splitext(name)[1].lstrip(".").lower()
			payload = json.dumps({"type": "filesDropped", "files": [{"name": name, "path": file_path, "ext": ext}]}, ensure_ascii=False)
			self._bridge.filesDropped.emit(payload)
			self._suppress_auto_hide_for(3000)
			self._show_header()

	def setWindowTitle(self, title):
		super().setWindowTitle(title)
		if hasattr(self, "_title_bar") and self._title_bar:
			self._title_bar.set_title(title)

	def _on_window_title_changed(self, title):
		self.setWindowTitle(title)

	@property
	def is_split_mode(self):
		return self._split_mode

	def enter_split_mode(self, left_file=None, right_file=None):
		if self._split_mode:
			return
		# 抑制标题栏自动隐藏，避免创建 webview 期间触发隐藏
		self._suppress_auto_hide_for(3000)
		from mmfb.core.split_view import SplitView
		self._split_view = SplitView(self, channel=getattr(self, '_channel', None))
		self._stack.addWidget(self._split_view)
		self._stack.setCurrentWidget(self._split_view)
		self._split_mode = True
		self._notify_split_changed()
		# 分屏切换后重新注册 DWM 阴影，防止边框丢失
		self._init_dwm_shadow()
		if left_file:
			self._load_file_in_view(self._split_view.left_view, left_file)
		if right_file:
			self._load_file_in_view(self._split_view.right_view, right_file)

	def exit_split_mode(self):
		if not self._split_mode:
			return
		self._suppress_auto_hide_for(3000)
		self._stack.setCurrentWidget(self._single_container)
		if self._split_view:
			self._split_view.destroy()
			self._split_view.setParent(None)
			self._split_view = None
		self._split_mode = False
		self._notify_split_changed()
		# 退出分屏后重新注册 DWM 阴影，防止边框丢失
		self._init_dwm_shadow()

	def toggle_split_mode(self):
		if self._split_mode:
			self.exit_split_mode()
		else:
			self.enter_split_mode()

	def _on_split_ratio_changed(self, ratio):
		pass

	def _load_file_in_view(self, webview, file_path):
		"""在分屏子 view 中加载文件预览（通过 hash 路由触发前端预览）"""
		# 计算文件扩展名，路径不预编码，交由 QUrl 处理
		file_name = os.path.basename(file_path)
		ext = os.path.splitext(file_name)[1].lstrip(".").lower()

		# 构造 index.html#/view/<ext>?file=<path> URL
		# 注意：不做 urllib.parse.quote，避免双重编码
		index_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "index.html")
		url = QUrl.fromLocalFile(index_path)
		url.setFragment('/view/' + ext + '?file=' + file_path)

		# 加载 URL（子 view 已设置 QWebChannel，前端路由会自动解析 hash）
		webview.setUrl(url)

	def _notify_split_changed(self):
		if hasattr(self, "_bridge") and self._bridge:
			self._bridge.splitModeChanged.emit(self._split_mode)

	def _is_in_hotzone(self, pos):
		return 0 <= pos.y() <= HOTZONE_HEIGHT and 0 <= pos.x() <= self.width()

	def _show_header(self):
		if hasattr(self, "_title_bar") and self._title_bar:
			if not self._title_bar.is_fully_visible():
				self._title_bar.slide_in()
			self._hide_timer.stop()

	def _hide_header(self):
		if hasattr(self, "_title_bar") and self._title_bar:
			if self._title_bar.is_fully_visible():
				self._title_bar.slide_out()
			self._hide_timer.stop()

	def _on_hide_timeout(self):
		if self._suppress_auto_hide:
			return
		if self._immersive_mode:
			self._hide_header()

	def _update_hotzone_state(self, pos):
		in_hotzone = self._is_in_hotzone(pos)
		if in_hotzone and not self._mouse_in_hotzone:
			self._mouse_in_hotzone = True
			self._show_header()
		elif not in_hotzone and self._mouse_in_hotzone:
			self._mouse_in_hotzone = False
			self._hide_timer.start(AUTOHIDE_DELAY_MS)

	def mouseMoveEvent(self, event):
		if self._immersive_mode and not self.isMaximized():
			self._update_hotzone_state(event.pos())
		super().mouseMoveEvent(event)

	def enterEvent(self, event):
		if not self._header_auto_hide:
			self._header_auto_hide = True
		super().enterEvent(event)

	def leaveEvent(self, event):
		if self._immersive_mode and self._header_auto_hide and not self._suppress_auto_hide:
			self._hide_timer.start(AUTOHIDE_DELAY_MS)
			self._mouse_in_hotzone = False
		super().leaveEvent(event)

	def _on_header_visibility_changed(self, visible):
		if visible:
			self._show_header()
		else:
			self._hide_header()

	def _on_show_command_panel(self):
		pass

	def _on_open_settings(self):
		pass

	def keyPressEvent(self, event):
		key = event.key()
		modifiers = event.modifiers()

		# Ctrl+N -> 新建窗口
		if key == Qt.Key.Key_N and modifiers == Qt.KeyboardModifier.ControlModifier:
			event.accept()
			self._new_window_shortcut()
			return

		# Ctrl+W -> 关闭当前窗口
		if key == Qt.Key.Key_W and modifiers == Qt.KeyboardModifier.ControlModifier:
			event.accept()
			self.close()
			return

		# Ctrl+` -> 切换分屏
		if key == Qt.Key.Key_QuoteLeft and modifiers == Qt.KeyboardModifier.ControlModifier:
			event.accept()
			self.toggle_split_mode()
			return

		if key == Qt.Key.Key_K and modifiers == Qt.KeyboardModifier.ControlModifier:
			event.accept()
			self._bridge.showCommandPanel.emit()
			return

		if key == Qt.Key.Key_Comma and modifiers == Qt.KeyboardModifier.ControlModifier:
			event.accept()
			self._bridge.openSettings.emit()
			return

		if key == Qt.Key.Key_O and modifiers == Qt.KeyboardModifier.ControlModifier:
			event.accept()
			self._open_file_dialog()
			return

		if (key == Qt.Key.Key_T and
			modifiers == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)):
			event.accept()
			self._toggle_theme()
			return

		# Ctrl+Shift+L -> 打开日志文件
		if key == Qt.Key.Key_L and modifiers == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
			event.accept()
			self._open_log_file()
			return

		super().keyPressEvent(event)

	def _new_window_shortcut(self):
		if hasattr(self, "_bridge") and self._bridge:
			self._bridge.newWindowRequested.emit()

	def _toggle_theme(self):
		order = ["light", "warm", "dark"]
		idx = order.index(self._current_theme) if self._current_theme in order else 0
		next_theme = order[(idx + 1) % len(order)]
		self._bridge.set_theme(next_theme)

	def _open_file_dialog(self):
		js = "(function() { var input = document.createElement(\'input\'); input.type = \'file\'; var file = e.target.files[0]; if (file) { window.MMFBBridge._bridge.set_window_title(file.name); } input.click(); })();"
		self._webview.page().runJavaScript(js)

	def resizeEvent(self, event):
		super().resizeEvent(event)
		if hasattr(self, "_title_bar") and self._title_bar:
			self._title_bar.setFixedWidth(self.width())

	def nativeEvent(self, eventType, event):
		if eventType != b"windows_generic_msg":
			return super().nativeEvent(eventType, event)

		hwnd = int(self.winId())
		msg = int(event[1])
		wparam = int(event[2])
		lparam = int(event[3])

		# WM_NCHITTEST (lparam 包含屏幕坐标 x=low16, y=high16)
		if msg == 0x0084:
			x = lparam & 0xFFFF
			y = (lparam >> 16) & 0xFFFF
			if self.isMaximized():
				try:
					rect = self.geometry()
					lx = x - rect.x()
					ly = y - rect.y()
					title_bar_h = 36
					if 0 <= lx <= rect.width() and 0 <= ly <= title_bar_h:
						return True, 2  # HTCAPTION
					return True, 1
				except Exception:
					return True, 1

			border = 8
			try:
				rect = self.geometry()
				lx = x - rect.x()
				ly = y - rect.y()
				rw, rh = rect.width(), rect.height()
				if lx < border and ly < border:
					return True, 13
				if lx >= rw - border and ly < border:
					return True, 14
				if lx < border and ly >= rh - border:
					return True, 16
				if lx >= rw - border and ly >= rh - border:
					return True, 17
				if lx < border:
					return True, 10
				if lx >= rw - border:
					return True, 11
				if ly < border:
					return True, 12
				if ly >= rh - border:
					return True, 15
				title_bar_h = 36
				if 0 <= lx <= rw and 0 <= ly <= title_bar_h:
					return True, 2  # HTCAPTION
				return True, 1
			except Exception:
				return True, 1

		if msg == 0x00A3:  # WM_NCLBUTTONDBLCLK
			self._toggle_maximize()
			return True, 0

		if msg == 0x00A5:  # WM_NCRBUTTONUP
			hit = int(wparam)
			if hit == 2:
				from PySide6.QtGui import QCursor
				self._show_system_menu(QCursor.pos())
				return True, 0

		return super().nativeEvent(eventType, event)

	def _show_system_menu(self, global_pos):
		try:
			menu = self.createPopupMenu()
			if menu is None:
				from PySide6.QtWidgets import QMenu
				from PySide6.QtGui import QAction
				menu = QMenu(self)
				actions_data = [
					("还原", self.showNormal, not (self.isMaximized() or self.isMinimized())),
					("最小化", self.showMinimized, True),
					("最大化", self.showMaximized, not self.isMaximized()),
					("关闭", self.close, True),
				]
				for text, slot, enabled in actions_data:
					act = QAction(text, menu)
					act.triggered.connect(slot)
					act.setEnabled(enabled)
					menu.addAction(act)
				menu.exec(global_pos)
		except Exception:
			logger.warning("[MainWindow] show system menu failed")

	def set_immersive_mode(self, enabled):
		self._immersive_mode = enabled
		if not enabled:
			self._hide_timer.stop()
			self._show_header()

	def is_immersive_mode(self):
		return self._immersive_mode

	def _toggle_maximize(self):
		if self.isMaximized():
			self.showNormal()
		else:
			self.showMaximized()

	def _open_log_file(self):
		"""打开日志文件供用户查看（快捷键 Ctrl+Shift+L）"""
		try:
			log_file = get_log_file()
			if os.path.exists(log_file):
				if sys.platform == "win32":
					os.startfile(log_file)
				else:
					import subprocess
					subprocess.Popen(["xdg-open", log_file])
				logger.info("[MainWindow] 打开日志文件: %s", log_file)
			else:
				QMessageBox.information(self, "日志", f"日志文件不存在:\n{log_file}")
		except Exception as e:
			logger.error("[MainWindow] 打开日志失败: %s", e)
			QMessageBox.warning(self, "错误", f"无法打开日志:\n{e}")

	def activate_window(self):
		try:
			self.showNormal()
			self.raise_()
			self.activateWindow()
		except RuntimeError:
			pass

	def _safe_stop_hide_timer(self):
		"""安全停止沉浸式隐藏定时器（修复名称修饰 bug）"""
		try:
			timer = getattr(self, "_hide_timer", None)
			if timer is not None:
				timer.stop()
		except Exception:
			pass

	def _suppress_auto_hide_for(self, ms):
		"""在拖入文件后短暂抑制沉浸式隐藏，避免标题栏在预览稳定前滑出"""
		self._suppress_auto_hide = True
		QTimer.singleShot(ms, self._on_suppress_timeout)

	def _on_suppress_timeout(self):
		self._suppress_auto_hide = False

	def _safe_restore_title_bar(self):
		"""安全恢复标题栏到完全显示状态"""
		if not hasattr(self, "_title_bar") or not self._title_bar:
			return
		try:
			self._safe_stop_hide_timer()
			self._title_bar.stop_animation()
			self._title_bar.show()
			self._title_bar.setGeometry(0, 0, self.width(), 36)
			self._title_bar.raise_()
			self._mouse_in_hotzone = False
			self._header_auto_hide = False
		except Exception as e:
			logger.warning("[_safe_restore_title_bar] %s", e)

	def showEvent(self, event):
		"""窗口每次可见时强制恢复标题栏，注册 Win32 拖拽，重注册 DWM 阴影"""
		logger.debug("[showEvent] 窗口显示事件")
		super().showEvent(event)
		self._safe_restore_title_bar()
		# 重注册 DWM 阴影：最小化再恢复后 Qt 可能会重置帧扩展，需要补调
		if sys.platform == "win32":
			try:
				self._init_dwm_shadow()
			except Exception as e:
				logger.debug("[showEvent] DWM shadow reinit failed: %s", e)
		# 注册 WM_DROPFILES（窗口句柄此时已有效）
		if sys.platform == "win32":
			try:
				ctypes.windll.shell32.DragAcceptFiles(int(self.winId()), True)
				logger.debug("[MainWindow] DragAcceptFiles(True)")
			except Exception as e:
				logger.warning("[MainWindow] DragAcceptFiles failed: %s", e)

	def changeEvent(self, event):
		"""窗口状态变更处理"""
		if event.type() == QEvent.Type.WindowStateChange:
			try:
				if hasattr(self, "_title_bar") and self._title_bar:
					self._title_bar.update_maximize_button(self.isMaximized())
				logger.debug("[changeEvent] isMinimized=%s isMaximized=%s", self.isMinimized(), self.isMaximized())
			except Exception as e:
				logger.warning("[changeEvent] 状态读取异常: %s", e)

		super().changeEvent(event)

	def showMinimized(self):
		"""最小化到任务栏（不隐藏到托盘）"""
		logger.debug("[showMinimized] 正常最小化到任务栏")
		super().showMinimized()

	def _safe_hide_to_tray(self, msg=""):
		"""安全隐藏窗口到托盘（绕过 changeEvent 嵌套状态变更）"""
		self._safe_stop_hide_timer()
		if hasattr(self, "_title_bar") and self._title_bar:
			self._title_bar.stop_animation()
		self.hide()
		if self._tray_icon and msg:
			try:
				if self._tray_icon.is_visible():
					self._tray_icon.show_message("MMFB", msg, "info", 1500)
			except Exception:
				pass

	def closeEvent(self, event):
		"""关闭事件：真正退出软件"""
		logger.debug("[closeEvent] 真正关闭")
		if self._bridge:
		    self._bridge.cleanup_threads()
		if self._tray_icon:
		    self._tray_icon.hide()
		super().closeEvent(event)
	def run_startup_update_check(self):
		try:
			settings = get_settings()
			if not settings.get("general", "check_updates", True):
				return
			QTimer.singleShot(3000, self._bridge.check_for_updates)
		except Exception:
			pass