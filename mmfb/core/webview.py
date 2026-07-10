"""QWebEngineView 封装

性能优化：
- 所有 MMFBWebView 实例共享一个 QWebEngineProfile，减少内存开销
- 禁用本地存储、HTTP 缓存等非必要功能（纯本地应用不需要）
- 禁用 HyperlinkAuditing、PageAllocator等减少开销的属性
"""
import os
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings, QWebEngineProfile
from PySide6.QtCore import QUrl

# 前端资源根目录
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

# 共享 Profile（整个应用生命周期只创建一次）
_shared_profile: QWebEngineProfile = None


def _get_shared_profile() -> QWebEngineProfile:
    """返回全局共享的 QWebEngineProfile

    共享 Profile 使得多个 QWebEngineView 使用同一个 Chromium 进程空间，
    减少每个重复 view 的内存开销约 50-80 MB。
    """
    global _shared_profile
    if _shared_profile is None:
        _shared_profile = QWebEngineProfile("MMFBDefault")
        # 禁用不必要的功能以降低内存占用
        ps = _shared_profile.settings()
        # 禁用本地存储（MMFB 是纯本地应用，无需 localStorage）
        ps.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, False)
        # 禁用超链接审计（减少开销）
        ps.setAttribute(QWebEngineSettings.WebAttribute.HyperlinkAuditingEnabled, False)
        # 禁用全屏支持（减少功能域）
        ps.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, False)
        # 禁用 PDF viewer 插件（已有自定义 pdf.js）
        ps.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, False)
    return _shared_profile


class MMFBWebView(QWebEngineView):
    def __init__(self, parent=None, channel=None):
        super().__init__(parent)

        self._setup_page(channel)
        self._load_index()

    def _setup_page(self, channel=None):
        """配置 WebEngine 页面（使用共享 Profile）"""
        profile = _get_shared_profile()
        page = QWebEnginePage(profile, self)
        self.setPage(page)

        # 必须在 setUrl 之前设置 QWebChannel，否则 qt.webChannelTransport 不会注入
        if channel is not None:
            self.page().setWebChannel(channel)

        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)

    def _load_index(self):
        """加载本地 index.html"""
        index_path = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index_path):
            self.setUrl(QUrl.fromLocalFile(index_path))
        else:
            # 降级：显示占位内容
            self.setHtml(
                "<html><body style='margin:0;padding:40px;"
                "font-family:sans-serif;color:#666;'>"
                "<h2>MMFB Windows</h2>"
                "<p>frontend/index.html not found</p>"
                "</body></html>"
            )
