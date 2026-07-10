"""QWebChannel Python 对象，暴露给前端"""
import os
import json
import base64
import subprocess
import threading
from pathlib import Path
from PySide6.QtCore import QObject, Slot, QFileInfo, Signal
from PySide6.QtWidgets import QFileDialog


def _get_history_path():
    """返回转换历史持久化文件路径"""
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        appdata = os.path.expanduser("~")
    base = os.path.join(appdata, "mmfb")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "conversion_history.json")


def _load_conversion_history(max_items: int = 10) -> list:
    """加载最近 N 条转换历史"""
    path = _get_history_path()
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return data[:max_items]
    except Exception:
        return []


def _append_conversion_history(entry: dict, max_items: int = 10):
    """写入一条转换历史并截断到 N 条"""
    path = _get_history_path()
    history = _load_conversion_history(max_items)
    history.insert(0, entry)
    history = history[:max_items]
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _get_system_theme_name() -> str:
    """检测 Windows 系统暗色/亮色模式，返回 'dark' 或 'light'

    注册表路径: HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Personalize
    键名: AppsUseLightTheme (1=亮色, 0=暗色)
    """
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Personalize"
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "dark" if value == 0 else "light"
    except Exception:
        return "light"  # 默认亮色


from mmfb.handlers.image_handler import ImageHandler
from mmfb.handlers.svg_handler import rasterize_to_png


class MMFBBridge(QObject):
    """暴露给前端的 Python 对象，通过 QWebChannel 通信"""

    # Python -> JS 单向通知信号
    messageReceived = Signal(str)

    # 文件拖拽打开信号：payload 为 JSON 字符串
    # {"type":"filesDropped","files":[{"name":"a.pdf","path":"C:/a.pdf","ext":"pdf"}, ...]}
    filesDropped = Signal(str)

    # JS -> Python 窗口标题变更请求
    windowTitleChangeRequested = Signal(str)

    # 转换进度信号：payload 为 JSON 字符串
    # {"jobId":"<uuid>","step":"converting","progress":0.5,"message":"..."}
    conversionProgress = Signal(str)

    # 转换完成信号：payload 为 JSON 字符串
    # {"jobId":"<uuid>","result":{"ok":bool,"path":str,"message":str,"error":str}}
    conversionFinished = Signal(str)

    # 沉浸式 UI 信号：通知前端显示/隐藏顶栏
    headerVisibilityChanged = Signal(bool)  # True = show, False = hide

    # 命令面板信号：通知前端打开命令面板
    showCommandPanel = Signal()

    # 设置页信号：通知前端打开设置页
    openSettings = Signal()

    # 系统主题变更信号：payload 为 'dark' 或 'light'
    systemThemeChanged = Signal(str)

    # 主题变更信号：Python 或前端切换主题后发射，用于同步原生窗口和前端 UI
    themeChanged = Signal(str)

    # 新窗口请求信号：前端 Ctrl+N / 菜单点击后发射
    newWindowRequested = Signal()

    # 分屏模式变更信号：(bool)
    splitModeChanged = Signal(bool)

    # 窗口计数变更信号：(int) 当前窗口数
    windowCountChanged = Signal(int)

    # 自动更新信号 ----------------------------------------------------------
    # 查询结果：payload 为 JSON 字符串
    updateCheckResult = Signal(str)
    # 下载进度：(percent:int, file_path_or_status:str)
    updateDownloadProgress = Signal(int, str)
    # 安装器下载完成：(file_path:str, tag:str)
    updateInstallerReady = Signal(str, str)

    # 托盘信号 --------------------------------------------------------------
    # 显示托盘气泡通知
    trayShowMessage = Signal(str, str, str, int)  # title, message, icon_type, msecs

    def __init__(self):
        super().__init__()
        self._threads = []

    def _register_thread(self, thread):
        self._threads.append(thread)
        thread.finished.connect(lambda: self._threads.remove(thread) if thread in self._threads else None)

    def cleanup_threads(self):
        """在程序退出时停止所有线程"""
        for thread in self._threads:
            if thread.isRunning():
                thread.quit()
                thread.wait(500)
        # 文件对话框父窗口（由 MainWindow 设置）
        self._dialog_parent = None
        # 标记用户是否在设置页显式选择过主题
        # (若 True，则不再自动跟随系统暗色模式变化)
        self._theme_user_set = False
        # 关联的 MainWindow 实例（用于分屏/新建窗口操作）
        self._window = None

    def set_dialog_parent(self, parent):
        """设置文件对话框的父窗口"""
        self._dialog_parent = parent

    def set_window(self, win):
        """设置关联的 MainWindow 实例"""
        self._window = win

    @Slot(str, result=str)
    def read_file(self, path: str) -> str:
        """读取文件内容，返回文本"""
        try:
            info = QFileInfo(path)
            if not info.exists():
                return ""
            if info.size() > 50 * 1024 * 1024:
                return "[File too large]"
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as e:
            return f"[Error reading file: {e}]"

    @Slot(str, result=str)
    def read_file_base64(self, path: str) -> str:
        """读取文件内容，返回 Base64 编码字符串（供二进制文件使用）"""
        try:
            import base64
            info = QFileInfo(path)
            if not info.exists():
                return ""
            if info.size() > 50 * 1024 * 1024:
                return "[File too large]"
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("ascii")
        except Exception as e:
            return f"[Error reading file: {e}]"

    @Slot(str, str, result=bool)
    def save_file(self, path: str, data: str) -> bool:
        """保存文本内容到文件"""
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)
            return True
        except Exception:
            return False

    @Slot(str, result=str)
    def get_file_info(self, path: str) -> str:
        """获取文件元信息，返回 JSON 字符串"""
        try:
            info = QFileInfo(path)
            if not info.exists():
                return "{}"
            result = {
                "path": path,
                "name": info.fileName(),
                "size": info.size(),
                "suffix": info.suffix(),
                "modified": info.lastModified().toString("yyyy-MM-dd hh:mm:ss"),
                "isDir": info.isDir(),
                "isFile": info.isFile()
            }
            return json.dumps(result, ensure_ascii=False)
        except Exception:
            return "{}"

    @Slot(str, result=str)
    def list_dir(self, path: str) -> str:
        """列出子目录与文件，返回 JSON 字符串"""
        try:
            if not os.path.isdir(path):
                return "[]"
            entries = []
            for name in sorted(os.listdir(path)):
                if name.startswith('.'):
                    continue
                full = os.path.join(path, name)
                is_dir = os.path.isdir(full)
                entry = {
                    "name": name,
                    "isDir": is_dir,
                }
                try:
                    stat = os.stat(full)
                    entry["size"] = stat.st_size if not is_dir else 0
                except OSError:
                    entry["size"] = 0
                entries.append(entry)
            return json.dumps(entries, ensure_ascii=False)
        except Exception:
            return "[]"

    @Slot(str, result=bool)
    def send_message(self, message: str) -> bool:
        """接收前端消息，回传 Python（可用于日志/调试）"""
        print(f"[MMFBBridge] {message}")
        return True

    @Slot(str, str, str, str, result=str)
    def convert_file(self, src: str, dst: str, fmt: str, job_id: str = "") -> str:
        """格式转换接口（异步执行，结果通过 conversionFinished 信号返回）"""
        try:
            from mmfb.services.conversion_engine import convert
            import _thread
            _thread.start_new_thread(self._convert_worker, (src, dst, fmt, job_id, convert))
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})
        # 立即返回，不阻塞 UI
        return json.dumps({"ok": True, "accepted": True, "jobId": job_id}, ensure_ascii=False)

    def _convert_worker(self, src, dst, fmt, job_id, convert_fn):
        """后台线程执行转换"""
        try:
            def _progress_cb(cur, total):
                if not job_id:
                    return
                try:
                    ratio = cur / total if total else 0.0
                    self.conversionProgress.emit(json.dumps({
                        "jobId": job_id,
                        "step": "converting",
                        "progress": ratio,
                        "message": f"{cur}/{total}",
                    }))
                except Exception:
                    pass

            result = convert_fn(src, dst, "", fmt, progress_cb=_progress_cb)

            result_payload = {
                "ok": result.ok,
                "path": result.output_path,
                "message": result.message,
                "error": result.error,
                "metadata": result.metadata,
            }
        except Exception as e:
            result_payload = {"ok": False, "error": str(e)}

        try:
            self.conversionFinished.emit(json.dumps({
                "jobId": job_id,
                "result": result_payload,
            }, ensure_ascii=False))
        except Exception:
            pass

    @Slot(result=str)
    def get_supported_conversions(self) -> str:
        """返回支持的格式转换列表"""
        try:
            from mmfb.services.conversion_engine import get_supported_conversions
            return json.dumps(get_supported_conversions(), ensure_ascii=False)
        except Exception:
            return "[]"

    @Slot(str, result=str)
    def get_files_info(self, paths_json: str) -> str:
        """批量获取文件元信息"""
        try:
            paths = json.loads(paths_json)
            if not isinstance(paths, list):
                return "[]"
            result = []
            for p in paths:
                if not isinstance(p, str):
                    continue
                if not os.path.isfile(p):
                    continue
                result.append({
                    "name": os.path.basename(p),
                    "path": p,
                    "ext": os.path.splitext(p)[1].lstrip(".").lower(),
                })
            return json.dumps(result, ensure_ascii=False)
        except Exception:
            return "[]"

    @Slot(str, result=bool)
    def set_window_title(self, title: str) -> bool:
        """前端请求设置窗口标题（通过信号转发给 MainWindow）"""
        self.windowTitleChangeRequested.emit(title)
        return True

    @Slot(result=str)
    def open_file_dialog(self) -> str:
        """打开文件选择对话框，返回选中文件路径 JSON，取消则返回空字符串"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self._dialog_parent,
                "打开文件",
                "",
                "所有文件 (*.*);;文档 (*.pdf *.docx *.doc *.txt *.md);;图像 (*.png *.jpg *.jpeg *.gif *.bmp)"
            )
            if file_path:
                return json.dumps({"path": file_path}, ensure_ascii=False)
            return ""
        except Exception:
            return ""

    @Slot(result=str)
    def open_subtitle_dialog(self) -> str:
        """打开字幕文件选择对话框，返回所选文件路径 JSON"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self._dialog_parent,
                "选择字幕文件",
                "",
                "字幕文件 (*.srt *.ass *.ssa *.sub *.vtt);;所有文件 (*.*)"
            )
            if file_path:
                return json.dumps({"path": file_path}, ensure_ascii=False)
            return ""
        except Exception:
            return ""

    # ========== 通用 Handler 分发接口 ==========

    @Slot(str, result=str)
    def get_preview(self, path: str) -> str:
        """通用预览接口：根据路径分发到对应 Handler，返回 JSON"""
        print(f"[BRIDGE DEBUG] get_preview called: {path}")
        try:
            from mmfb.core.registry import registry
            handler = registry.get_handler(path)
            if handler is None:
                return json.dumps({"error": "no handler for this file type"})
            result = handler.get_preview()
            if result is None:
                return json.dumps({"error": "preview returned None"})
            print(f"[BRIDGE DEBUG] get_preview result: template={result.get('template')}, content_len={len(result.get('data', {}).get('content', ''))}")
            ret = json.dumps(result, ensure_ascii=False, default=str)
            print(f"[BRIDGE DEBUG] json.dumps type={type(ret).__name__} repr={repr(ret)[:100]}")
            return ret
        except Exception as e:
            return json.dumps({"error": str(e)})

    @Slot(str, result=str)
    def get_edit(self, path: str) -> str:
        """通用编辑数据接口"""
        try:
            from mmfb.core.registry import registry
            handler = registry.get_handler(path)
            if handler is None:
                return json.dumps({"error": "no handler for this file type"})
            result = handler.get_edit()
            if result is None:
                return json.dumps({"error": "not editable"})
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    # ========== Word docx 专用接口 ==========

    @Slot(str, str, result=str)
    def save_docx(self, path: str, changes_json: str) -> str:
        """保存 docx 段落编辑"""
        try:
            from mmfb.handlers.docx_handler import DocxHandler
            handler = DocxHandler(path)
            ok = handler.save_paragraphs(changes_json)
            return json.dumps({"ok": ok})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    # ========== Excel xlsx 专用接口 ==========

    @Slot(str, str, str, result=bool)
    def save_xlsx_cell(self, path: str, address: str, value: str) -> bool:
        """保存 xlsx 单个单元格"""
        try:
            from mmfb.handlers.xlsx_handler import XlsxHandler
            parts = path.split("|", 1)
            file_path = parts[0]
            sheet_name = parts[1] if len(parts) > 1 else ""
            handler = XlsxHandler(file_path)
            try:
                if "." in value:
                    val = float(value)
                else:
                    val = int(value)
            except (ValueError, TypeError):
                val = value
            return handler.save_cell(sheet_name, address, val)
        except Exception as e:
            print(f"[Bridge] save_xlsx_cell error: {e}")
            return False

    @Slot(str, result=bool)
    def save_xlsx_cells(self, changes_json: str) -> bool:
        """批量保存 xlsx 单元格"""
        try:
            from mmfb.handlers.xlsx_handler import XlsxHandler
            payload = json.loads(changes_json)
            file_path = payload.get("path", "")
            changes = payload.get("changes", [])
            if not file_path or not changes:
                return False
            handler = XlsxHandler(file_path)
            return handler.save_cells(json.dumps(changes, ensure_ascii=False))
        except Exception as e:
            print(f"[Bridge] save_xlsx_cells error: {e}")
            return False

    # ========== PDF 接口 ==========

    @Slot(str, result=str)
    def get_pdf_metadata(self, path: str) -> str:
        """返回 PDF 文件的元信息和页数，JSON 格式"""
        try:
            info = QFileInfo(path)
            if not info.exists():
                return json.dumps({"error": "file not found"})

            file_size = info.size()
            result = {"fileSize": file_size}

            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(path)
                result["pageCount"] = len(reader.pages)

                meta = reader.metadata
                if meta:
                    result["title"] = meta.title or ""
                    result["author"] = meta.author or ""
                    result["subject"] = meta.subject or ""
                    result["creator"] = meta.creator or ""
                    result["producer"] = meta.producer or ""
                    result["creationDate"] = str(meta.get("/CreationDate", "")) if meta.get("/CreationDate") else ""
                    result["modDate"] = str(meta.get("/ModDate", "")) if meta.get("/ModDate") else ""
            except Exception as e:
                result["error"] = f"parse error: {str(e)}"
                result["pageCount"] = 0

            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    # ========== SVG 转 PNG 接口 ==========

    @Slot(str, result=str)
    def svg_to_png(self, payload_json: str) -> str:
        """将 SVG 栅格化为 PNG"""
        try:
            payload = json.loads(payload_json)
            src = payload.get("src", "")
            width = int(payload.get("width", 0) or 0)
            height = int(payload.get("height", 0) or 0)

            if not src or not os.path.isfile(src):
                return json.dumps({"ok": False, "error": "src not found: " + str(src)})

            base, _ = os.path.splitext(src)
            if src.lower().endswith(".svgz"):
                base = src[:-5]
            elif src.lower().endswith(".svg"):
                base = src[:-4]

            dst = base + "_raster.png"
            if os.path.exists(dst):
                idx = 1
                while os.path.exists(f"{base}_raster_{idx}.png"):
                    idx += 1
                dst = f"{base}_raster_{idx}.png"

            result = rasterize_to_png(src, dst, width, height)
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    # ========== 图像编辑接口 ==========

    @Slot(str, str, str, result=str)
    def apply_image_edit(self, file_path: str, operations_json: str, output_path: str = "") -> str:
        """执行图像编辑操作并保存"""
        try:
            operations = json.loads(operations_json)
            if not isinstance(operations, list):
                return json.dumps({"ok": False, "error": "operations must be a list"})

            result = ImageHandler.apply_edit(file_path, operations, output_path)
            return json.dumps(result, ensure_ascii=False)
        except json.JSONDecodeError as e:
            return json.dumps({"ok": False, "error": f"invalid JSON: {str(e)}"})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    # ========== 压缩包接口 ==========

    @Slot(str, str, str, result=str)
    def extract_archive_member(self, archive_path: str, member_name: str, password: str = "") -> str:
        """从压缩包解压单个成员到内存"""
        try:
            from mmfb.handlers.archive_handler import extract_member_to_memory
            result = extract_member_to_memory(archive_path, member_name, password)
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    @Slot(str, str, result=str)
    def unlock_encrypted_archive(self, archive_path: str, password: str) -> str:
        """尝试用密码解锁加密 ZIP，成功则返回树形数据"""
        try:
            import zipfile
            from mmfb.handlers.archive_handler import ArchiveHandler

            with zipfile.ZipFile(archive_path, "r") as zf:
                for info in zf.infolist():
                    if info.flag_bits & 0x1:
                        try:
                            zf.read(info.filename, pwd=password.encode("utf-8"))
                        except RuntimeError:
                            return json.dumps({"ok": False, "error": "wrong password"})

                handler = ArchiveHandler(archive_path)
                preview = handler.get_preview()
                if preview and "error" not in preview:
                    return json.dumps({"ok": True, "data": preview.get("data", {})}, ensure_ascii=False)
                return json.dumps({"ok": False, "error": "parse failed after unlock"})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    # ========== CSV 表格导出接口 ==========

    @Slot(str, str, str, result=str)
    def export_csv(self, src_path: str, dst_path: str, fmt: str) -> str:
        """将 CSV/TSV 文件导出为其他格式"""
        try:
            from mmfb.handlers.csv_handler import export_to_excel, export_to_tsv
            if fmt == "xlsx":
                result = export_to_excel(src_path, dst_path)
            elif fmt == "tsv":
                result = export_to_tsv(src_path, dst_path)
            else:
                return json.dumps({"ok": False, "error": "unsupported format: " + fmt})
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    # ========== 打开文件 / 文件夹 ==========

    @Slot(str, result=str)
    def open_path(self, path: str) -> str:
        """用系统默认程序打开文件或打开所在文件夹"""
        if not path or not os.path.exists(path):
            return json.dumps({"ok": False, "error": "path not found" if path else "empty path"})
        try:
            if os.path.isfile(path):
                os.startfile(path)
            else:
                subprocess.Popen(["explorer", os.path.normpath(path)])
            return json.dumps({"ok": True})
        except Exception:
            try:
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
                return json.dumps({"ok": True})
            except Exception as e2:
                return json.dumps({"ok": False, "error": str(e2)})

    # ========== 转换历史持久化 ==========

    @Slot(result=str)
    def get_conversion_history(self) -> str:
        """获取最近 10 条转换历史"""
        return json.dumps(_load_conversion_history(10), ensure_ascii=False)

    @Slot(str, result=str)
    def append_conversion_history(self, entry_json: str) -> str:
        """追加一条转换历史"""
        try:
            entry = json.loads(entry_json)
            _append_conversion_history(entry, 10)
            return json.dumps({"ok": True})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    @Slot(result=str)
    def clear_conversion_history(self) -> str:
        """清空转换历史"""
        path = _get_history_path()
        try:
            if os.path.isfile(path):
                os.remove(path)
            return json.dumps({"ok": True})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    # ========== 打开历史接口 ==========

    @Slot(result=str)
    def get_open_history(self) -> str:
        """获取全部打开历史，返回 JSON 数组"""
        try:
            from mmfb.core.history_manager import get_history
            records = get_history().get_all()
            return json.dumps(records, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @Slot(str, str, str, str, result=str)
    def add_to_history(self, path: str, name: str, ext: str, mime: str) -> str:
        """添加一条打开历史记录"""
        try:
            from mmfb.core.history_manager import get_history
            get_history().add(path or "", name or "", ext or "", mime or "")
            return json.dumps({"ok": True})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    @Slot(result=str)
    def clear_open_history(self) -> str:
        """清空全部打开历史"""
        try:
            from mmfb.core.history_manager import get_history
            get_history().clear()
            return json.dumps({"ok": True})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    @Slot(str, result=str)
    def remove_history_item(self, path: str) -> str:
        """移除一条打开历史"""
        try:
            from mmfb.core.history_manager import get_history
            get_history().remove(path or "")
            return json.dumps({"ok": True})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    # ========== 沉浸式 UI 接口 ==========

    @Slot(bool)
    def set_header_visible(self, visible: bool):
        """设置顶栏显隐状态（前端通过此方法同步 Python 侧标题栏显隐）"""
        self.headerVisibilityChanged.emit(visible)

    @Slot()
    def trigger_command_panel(self):
        """触发命令面板（由 Python 快捷键 Ctrl+K 调用）"""
        self.showCommandPanel.emit()

    @Slot()
    def trigger_open_settings(self):
        """触发设置页（由 Python 快捷键 Ctrl+, 调用）"""
        self.openSettings.emit()

    # ========== 多窗口 / 分屏接口 ==========

    @Slot(str, result=str)
    def new_window(self, file_path: str = "") -> str:
        """新建一个 MMFB 窗口

        Args:
            file_path: 可选，新窗口打开的文件路径

        Returns:
            JSON {"ok": bool, "message": str}
        """
        try:
            from mmfb.core.window_manager import get_window_manager
            mgr = get_window_manager()
            win = mgr.new_window(file_path if file_path else None)
            win.show()
            # 发射信号通知所有窗口计数变更
            self._emit_window_count(mgr.count)
            return json.dumps({"ok": True}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    @Slot(result=str)
    def close_window(self) -> str:
        """关闭当前窗口

        Returns:
            JSON {"ok": bool, "remaining": int}
        """
        try:
            if self._window is not None:
                self._window.close()
                return json.dumps({"ok": True}, ensure_ascii=False)
            return json.dumps({"ok": False, "error": "no window bound"})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    @Slot(result=str)
    def split_current_window(self) -> str:
        """切换当前窗口的分屏模式

        Returns:
            JSON {"ok": bool, "split": bool}
        """
        try:
            if self._window is None:
                return json.dumps({"ok": False, "error": "no window bound"})

            self._window.toggle_split_mode()
            is_split = self._window.is_split_mode
            return json.dumps({"ok": True, "split": is_split}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    @Slot(str, str, result=str)
    def enter_split(self, left_file: str = "", right_file: str = "") -> str:
        """进入分屏模式并加载文件

        Returns:
            JSON {"ok": bool, "split": bool}
        """
        try:
            if self._window is None:
                return json.dumps({"ok": False, "error": "no window bound"})

            self._window.enter_split_mode(
                left_file if left_file else None,
                right_file if right_file else None
            )
            return json.dumps({"ok": True, "split": True}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    @Slot(result=str)
    def exit_split(self) -> str:
        """退出分屏模式

        Returns:
            JSON {"ok": bool, "split": bool}
        """
        try:
            if self._window is None:
                return json.dumps({"ok": False, "error": "no window bound"})

            self._window.exit_split_mode()
            return json.dumps({"ok": True, "split": False}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    @Slot(result=str)
    def get_window_state(self) -> str:
        """获取当前窗口状态（分屏状态、窗口总数）"""
        try:
            from mmfb.core.window_manager import get_window_manager
            mgr = get_window_manager()
            split = self._window.is_split_mode if self._window else False
            return json.dumps({
                "split": split,
                "windowCount": mgr.count,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _emit_window_count(self, count: int):
        """通知所有窗口的 bridge 窗口总数变更"""
        try:
            from mmfb.core.window_manager import get_window_manager
            mgr = get_window_manager()
            for w in mgr.windows:
                if hasattr(w, '_bridge') and w._bridge:
                    w._bridge.windowCountChanged.emit(count)
        except Exception:
            pass

    # ========== 主题接口 ==========

    @Slot(result=str)
    def get_theme(self) -> str:
        """读取当前持久化主题，无则为 'warm'（默认）"""
        try:
            from mmfb.core.settings_manager import get_settings
            t = get_settings().get("display", "theme", "warm")
            return t if isinstance(t, str) else "warm"
        except Exception:
            return "warm"

    @Slot(result=str)
    def get_system_theme(self) -> str:
        """检测 Windows 系统暗色/亮色模式，返回 'dark' 或 'light'"""
        return _get_system_theme_name()

    @Slot(str, result=bool)
    def set_theme(self, theme_name: str) -> bool:
        """持久化主题偏好并发射 themeChanged 信号让 UI 更新"""
        if theme_name not in ("light", "dark", "warm"):
            return False
        try:
            from mmfb.core.settings_manager import get_settings
            settings = get_settings()
            current = settings.get("display", "theme", "warm")
            if current == theme_name:
                return True  # 主题未变化，无需持久化或发射信号
            settings.set("display", "theme", theme_name)
            self._theme_user_set = True
            self.themeChanged.emit(theme_name)
            return True
        except Exception:
            return False

    @Slot(str)
    def notify_theme_changed(self, theme_name: str):
        """前端通知后端主题已更新（用于保持两侧状态同步）"""
        if theme_name in ("light", "dark", "warm"):
            self._theme_user_set = True

    # ========== Windows 文件关联接口 ==========

    @Slot(result=str)
    def get_file_association_status(self) -> str:
        """获取文件关联状态摘要，返回 JSON"""
        try:
            import sys
            if sys.platform != "win32":
                return json.dumps({"error": "only available on Windows"})
            from mmfb.services.file_association import get_registry_summary
            return json.dumps(get_registry_summary(), ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @Slot(result=str)
    def register_file_associations(self) -> str:
        """注册所有关联，返回结果 JSON"""
        try:
            import sys
            if sys.platform != "win32":
                return json.dumps({"ok": False, "error": "only available on Windows"})
            from mmfb.services.file_association import (
                associate_all, refresh_shell_icons
            )
            success, failed = associate_all()
            refresh_shell_icons()
            return json.dumps({
                "ok": True,
                "success": success,
                "failed": failed,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    @Slot(result=str)
    def unregister_file_associations(self) -> str:
        """移除所有关联，返回结果 JSON"""
        try:
            import sys
            if sys.platform != "win32":
                return json.dumps({"ok": False, "error": "only available on Windows"})
            from mmfb.services.file_association import (
                unregister_all, refresh_shell_icons
            )
            success, failed = unregister_all()
            refresh_shell_icons()
            return json.dumps({
                "ok": True,
                "success": success,
                "failed": failed,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    # ========== 右键菜单 Open With MMFB 接口 ==========

    @Slot(result=str)
    def get_shell_extension_status(self) -> str:
        """获取右键菜单注册状态，返回 JSON"""
        try:
            import sys
            if sys.platform != "win32":
                return json.dumps({"error": "only available on Windows"})
            from mmfb.services.shell_extension import get_status
            return json.dumps(get_status(), ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @Slot(result=str)
    def register_shell_extension(self) -> str:
        """注册右键菜单 Open With MMFB，返回结果 JSON"""
        try:
            import sys
            if sys.platform != "win32":
                return json.dumps({"ok": False, "error": "only available on Windows"})
            from mmfb.services.shell_extension import register
            ok = register()
            return json.dumps({"ok": ok}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    @Slot(result=str)
    def unregister_shell_extension(self) -> str:
        """注销右键菜单 Open With MMFB，返回结果 JSON"""
        try:
            import sys
            if sys.platform != "win32":
                return json.dumps({"ok": False, "error": "only available on Windows"})
            from mmfb.services.shell_extension import unregister
            ok = unregister()
            return json.dumps({"ok": ok}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    # ---------- 自动更新 ----------

    @Slot(result=str)
    def get_version(self) -> str:
        """返回当前应用版本号 JSON"""
        try:
            from mmfb.version import MMFB_VERSION, MMFB_VERSION_NAME
            return json.dumps({
                "version": MMFB_VERSION,
                "name": MMFB_VERSION_NAME,
            })
        except Exception:
            return json.dumps({"version": "0.0.0", "name": ""})

    @Slot(result=str)
    def check_for_updates(self) -> str:
        """查询 GitHub Releases 是否有新版本

        无论成功失败，最终通过 updateCheckResult 信号发射结果。
        本 Slot 返回值为空字符串（非阻塞）。
        """
        # 在独立线程执行网络请求，避免阻塞 UI
        from PySide6.QtCore import QThread

        class _UpdateChecker(QThread):
            def __init__(self, signal):
                super().__init__()
                self._signal = signal

            def run(self):
                try:
                    from mmfb.services.update_service import check_for_updates
                    result = check_for_updates()
                    import json as _json
                    if result is None:
                        self._signal.emit(_json.dumps({"available": False}))
                    else:
                        result["available"] = True
                        self._signal.emit(_json.dumps(result, ensure_ascii=False))
                except Exception as e:
                    import json as _json
                    self._signal.emit(
                        _json.dumps({"available": False, "error": str(e)})
                    )

        try:
            thread = _UpdateChecker(self.updateCheckResult)
            thread.finished.connect(thread.deleteLater)
            self._register_thread(thread)
            thread.start()
        except Exception as e:
            self.updateCheckResult.emit(
                json.dumps({"available": False, "error": str(e)})
            )
        return ""

    @Slot(str, str, result=str)
    def download_update(self, download_url: str, filename: str = "") -> str:
        """异步下载安装器

        Args:
            download_url: 安装包下载 URL
            filename: 保存文件名（可选）

        进度通过 updateDownloadProgress 信号发射；
        完成时通过 updateInstallerReady 信号发射 (file_path, tag_or_error)。
        """
        from PySide6.QtCore import QThread

        class _Downloader(QThread):
            def __init__(self, signal_progress, signal_ready):
                super().__init__()
                self._progress = signal_progress
                self._ready = signal_ready
                self._url = ""
                self._filename = ""

            def configure(self, url, filename):
                self._url = url
                self._filename = filename

            def run(self):
                try:
                    from mmfb.services.update_service import download_installer
                    path = download_installer(
                        self._url,
                        self._filename or None,
                        progress_cb=lambda cur, total: self._emit_progress(cur, total),
                    )
                    if path:
                        self._ready.emit(path, "ok")
                    else:
                        self._ready.emit("", "download_failed")
                except Exception as e:
                    self._ready.emit("", str(e))

            def _emit_progress(self, cur, total):
                try:
                    pct = int(cur * 100 / total) if total > 0 else -1
                    if pct >= 0:
                        self._progress.emit(pct, "")
                    else:
                        self._progress.emit(-1, f"{cur // 1024}KB")
                except Exception:
                    pass

        try:
            thread = _Downloader(self.updateDownloadProgress, self.updateInstallerReady)
            thread.configure(download_url, filename)
            thread.finished.connect(thread.deleteLater)
            self._register_thread(thread)
            thread.start()
        except Exception as e:
            self.updateInstallerReady.emit("", str(e))
        return json.dumps({"ok": True})

    @Slot(str)
    def cancel_update_download(self):
        """占位：取消正在进行的下载（当前版本保留接口不做实现）"""
        pass

    @Slot(str, result=str)
    def launch_installer(self, installer_path: str) -> str:
        """启动安装器并退出当前应用

        Args:
            installer_path: 安装器文件路径

        策略：
          1. 校验文件存在
          2. Windows 下使用 subprocess 启动安装器（/S 静默参数备用）
          3. 发射信号让 Python 侧有机会清理
          4. 立即调用 QApplication.quit()
        """
        try:
            if not os.path.isfile(installer_path):
                return json.dumps({"ok": False, "error": "installer_not_found"})

            import subprocess
            # 正常打开安装器（UI 安装向导模式）
            subprocess.Popen(
                [installer_path],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )

            # 触发所有窗口关闭
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                app.quit()

            return json.dumps({"ok": True})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    @Slot(str)
    def skip_version(self, tag: str):
        """记录用户选择忽略的版本，后续不再提示"""
        try:
            from mmfb.core.settings_manager import get_settings
            import json as _json
            settings = get_settings()
            raw = settings.get("general", "skipped_versions", "[]")
            try:
                lst = _json.loads(raw) if isinstance(raw, str) else []
            except Exception:
                lst = []
            if tag not in lst:
                lst.append(tag)
                settings.set("general", "skipped_versions", _json.dumps(lst))
        except Exception:
            pass

    # ========== FFmpeg 媒体探测与转码接口 ==========

    @Slot(result=str)
    def check_ffmpeg_status(self) -> str:
        """探测本机 ffmpeg / ffprobe 是否安装，返回 JSON"""
        try:
            from mmfb.services.ffmpeg_service import check_ffmpeg, check_ffprobe
            ffmpeg_info = check_ffmpeg()
            ffprobe_info = check_ffprobe()
            return json.dumps({
                "ffmpeg": ffmpeg_info,
                "ffprobe": ffprobe_info,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @Slot(str, result=str)
    def probe_media_info(self, path: str) -> str:
        """读取媒体文件元数据（流信息 + 容器信息），返回 JSON"""
        try:
            from mmfb.services.ffmpeg_service import get_media_info
            result = get_media_info(path)
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    @Slot(str, str, str, str, result=str)
    def convert_video_file(self, src: str, dst: str, fmt: str, job_id: str = "") -> str:
        """视频转码接口（异步执行，结果通过 conversionFinished 信号返回）"""
        try:
            from mmfb.services.ffmpeg_service import convert_video
            import _thread
            _thread.start_new_thread(self._convert_video_worker, (src, dst, fmt, job_id, convert_video))
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})
        return json.dumps({"ok": True, "accepted": True, "jobId": job_id}, ensure_ascii=False)

    def _convert_video_worker(self, src, dst, fmt, job_id, convert_fn):
        """后台线程执行视频转码"""
        try:
            def _progress_cb(ratio, message):
                if not job_id:
                    return
                try:
                    self.conversionProgress.emit(json.dumps({
                        "jobId": job_id,
                        "step": "converting",
                        "progress": ratio,
                        "message": message,
                    }))
                except Exception:
                    pass

            result = convert_fn(src, dst, fmt, on_progress=_progress_cb)
            result_payload = {
                "ok": getattr(result, "ok", True),
                "path": dst,
                "message": getattr(result, "message", "视频转码完成"),
                "error": getattr(result, "error", ""),
            }
        except Exception as e:
            result_payload = {"ok": False, "error": str(e)}

        try:
            self.conversionFinished.emit(json.dumps({
                "jobId": job_id,
                "result": result_payload,
            }, ensure_ascii=False))
        except Exception:
            pass

    # ========== 系统托盘接口 ==========

    @Slot(str, str, str, result=str)
    def show_tray_notification(self, title: str, message: str, icon: str = "info") -> str:
        """显示系统托盘气泡通知

        Args:
            title: 通知标题
            message: 通知内容
            icon: 图标类型 ("info" | "warning" | "critical")

        Returns:
            JSON {"ok": bool}
        """
        try:
            from mmfb.core.tray_icon import get_tray_icon
            tray = get_tray_icon()
            if tray:
                tray.show_message(title, message, icon)
                return json.dumps({"ok": True}, ensure_ascii=False)
            return json.dumps({"ok": False, "error": "tray not available"})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    @Slot(result=str)
    def get_tray_status(self) -> str:
        """获取托盘图标状态"""
        try:
            from mmfb.core.tray_icon import get_tray_icon
            tray = get_tray_icon()
            if tray:
                return json.dumps({"ok": True, "visible": tray.isVisible()}, ensure_ascii=False)
            return json.dumps({"ok": False, "visible": False}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})
