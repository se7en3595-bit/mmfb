"""文件拖拽打开测试用例

测试 MainWindow 的 dragEnterEvent / dropEvent 核心逻辑：
1. 文件过滤（跳过目录、不存在的文件、超 50MB 文件）
2. 信号发射（验证 filesDropped 信号携带正确的 JSON）
3. dragEnterEvent 只接受含本地文件的拖拽
4. dropEvent 多文件支持

测试策略：
- 使用 unittest.mock 创造 MainWindow 实例，绕过完整 Qt 初始化
- 直接调用 dragEnterEvent / dropEvent 方法，验证事件处理和信号发射
"""
import os
import sys
import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication

# 确保有 QApplication 实例
_app = QApplication.instance() or QApplication(sys.argv)


def _make_local_file_url(path):
    """构造一个模拟的 QUrl：isLocalFile() 返回 True"""
    mock_url = MagicMock()
    mock_url.isLocalFile.return_value = True
    mock_url.toLocalFile.return_value = path
    return mock_url


def _make_remote_url(path="https://example.com/file.txt"):
    """构造一个模拟的 QUrl：isLocalFile() 返回 False"""
    mock_url = MagicMock()
    mock_url.isLocalFile.return_value = False
    mock_url.toLocalFile.return_value = path
    return mock_url


class TestFileFiltering(unittest.TestCase):
    """单元测试：文件过滤逻辑（不依赖 Qt GUI）"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.valid_file = os.path.join(self.tmp_dir, "test_document.pdf")
        with open(self.valid_file, "w") as f:
            f.write("dummy pdf content")

        self.another_file = os.path.join(self.tmp_dir, "notes.md")
        with open(self.another_file, "w") as f:
            f.write("# Notes")

        self.sub_dir = os.path.join(self.tmp_dir, "subdir")
        os.makedirs(self.sub_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _filter_files(self, urls):
        """复现 dropEvent 中的文件过滤逻辑"""
        MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
        file_paths = []
        for url in urls:
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if not os.path.isfile(path):
                continue
            try:
                if os.path.getsize(path) > MAX_FILE_SIZE_BYTES:
                    continue
            except OSError:
                continue
            file_paths.append(path)
        return file_paths

    def test_only_local_files_accepted(self):
        urls = [
            _make_local_file_url(self.valid_file),
            _make_remote_url(),
            _make_local_file_url(self.another_file),
        ]
        result = self._filter_files(urls)
        self.assertEqual(len(result), 2)
        self.assertIn(self.valid_file, result)
        self.assertIn(self.another_file, result)

    def test_directory_is_skipped(self):
        urls = [
            _make_local_file_url(self.valid_file),
            _make_local_file_url(self.sub_dir),
        ]
        result = self._filter_files(urls)
        self.assertEqual(result, [self.valid_file])

    def test_nonexistent_file_is_skipped(self):
        ghost = os.path.join(self.tmp_dir, "ghost.txt")
        urls = [
            _make_local_file_url(self.valid_file),
            _make_local_file_url(ghost),
        ]
        result = self._filter_files(urls)
        self.assertEqual(result, [self.valid_file])

    def test_oversized_file_is_skipped(self):
        big_file = os.path.join(self.tmp_dir, "big.bin")
        with open(big_file, "w") as f:
            f.write("small")

        mock_url = _make_local_file_url(big_file)
        original_getsize = os.path.getsize

        def fake_getsize(path, *args, **kwargs):
            if path == big_file:
                return 60 * 1024 * 1024
            return original_getsize(path, *args, **kwargs)

        with patch('os.path.getsize', side_effect=fake_getsize):
            urls = [mock_url, _make_local_file_url(self.valid_file)]
            result = self._filter_files(urls)

        self.assertEqual(result, [self.valid_file])

    def test_empty_url_list(self):
        result = self._filter_files([])
        self.assertEqual(result, [])

    def test_all_remote_urls(self):
        urls = [_make_remote_url(), _make_remote_url()]
        result = self._filter_files(urls)
        self.assertEqual(result, [])


class TestDragEnterEvent(unittest.TestCase):
    """测试 dragEnterEvent 是否正确接受/拒绝拖拽"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.temp_file = os.path.join(self.tmp_dir, "drag_test.txt")
        with open(self.temp_file, "w") as f:
            f.write("test")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_window(self):
        """创建一个 minimal MainWindow 实例"""
        from mmfb.core.window import MainWindow
        win = MagicMock(spec=MainWindow)
        win._bridge = MagicMock()
        return win

    def _call_drag_enter(self, win, mock_event):
        """调用 MainWindow.dragEnterEvent 的裸方法"""
        from mmfb.core.window import MainWindow
        MainWindow.dragEnterEvent(win, mock_event)

    def test_accept_drag_with_local_files(self):
        win = self._create_window()

        mock_mime = MagicMock()
        mock_mime.hasUrls.return_value = True
        mock_url = _make_local_file_url(self.temp_file)
        mock_mime.urls.return_value = [mock_url]

        mock_event = MagicMock()
        mock_event.mimeData.return_value = mock_mime

        self._call_drag_enter(win, mock_event)

        mock_event.acceptProposedAction.assert_called_once()
        mock_event.ignore.assert_not_called()

    def test_reject_drag_without_urls(self):
        win = self._create_window()

        mock_mime = MagicMock()
        mock_mime.hasUrls.return_value = False

        mock_event = MagicMock()
        mock_event.mimeData.return_value = mock_mime

        self._call_drag_enter(win, mock_event)

        mock_event.ignore.assert_called_once()
        mock_event.acceptProposedAction.assert_not_called()

    def test_reject_drag_with_only_remote_urls(self):
        win = self._create_window()

        mock_mime = MagicMock()
        mock_mime.hasUrls.return_value = True
        mock_mime.urls.return_value = [_make_remote_url()]

        mock_event = MagicMock()
        mock_event.mimeData.return_value = mock_mime

        self._call_drag_enter(win, mock_event)

        mock_event.ignore.assert_called_once()


class TestDropEventSignal(unittest.TestCase):
    """测试 dropEvent 正确解析文件并发射 filesDropped 信号"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.file1 = os.path.join(self.tmp_dir, "hello.pdf")
        with open(self.file1, "w") as f:
            f.write("pdf content")

        self.file2 = os.path.join(self.tmp_dir, "world.txt")
        with open(self.file2, "w") as f:
            f.write("text content")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_drop_emits_files_dropped_signal(self):
        from mmfb.core.window import MainWindow

        mock_win = MagicMock()
        mock_win._bridge = MagicMock()
        mock_win._record_history = MagicMock()

        mock_mime = MagicMock()
        mock_mime.hasUrls.return_value = True
        mock_mime.urls.return_value = [
            _make_local_file_url(self.file1),
            _make_local_file_url(self.file2),
        ]

        mock_event = MagicMock()
        mock_event.mimeData.return_value = mock_mime

        MainWindow.dropEvent(mock_win, mock_event)

        mock_event.acceptProposedAction.assert_called_once()
        mock_win._bridge.filesDropped.emit.assert_called_once()

        payload = mock_win._bridge.filesDropped.emit.call_args[0][0]
        data = json.loads(payload)
        self.assertEqual(data["type"], "filesDropped")
        self.assertEqual(len(data["files"]), 2)

        names = [f["name"] for f in data["files"]]
        self.assertIn("hello.pdf", names)
        self.assertIn("world.txt", names)

    def test_drop_with_no_valid_files_is_ignored(self):
        from mmfb.core.window import MainWindow

        mock_win = MagicMock()
        mock_win._bridge = MagicMock()

        mock_mime = MagicMock()
        mock_mime.hasUrls.return_value = True
        mock_mime.urls.return_value = [_make_remote_url()]

        mock_event = MagicMock()
        mock_event.mimeData.return_value = mock_mime

        MainWindow.dropEvent(mock_win, mock_event)

        mock_event.ignore.assert_called_once()
        mock_win._bridge.filesDropped.emit.assert_not_called()

    def test_drop_without_urls_is_ignored(self):
        from mmfb.core.window import MainWindow

        mock_win = MagicMock()
        mock_win._bridge = MagicMock()

        mock_mime = MagicMock()
        mock_mime.hasUrls.return_value = False

        mock_event = MagicMock()
        mock_event.mimeData.return_value = mock_mime

        MainWindow.dropEvent(mock_win, mock_event)

        mock_event.ignore.assert_called_once()
        mock_win._bridge.filesDropped.emit.assert_not_called()

    def test_drop_single_file(self):
        """单文件 drop 也能正常工作"""
        from mmfb.core.window import MainWindow

        mock_win = MagicMock()
        mock_win._bridge = MagicMock()
        mock_win._record_history = MagicMock()

        mock_mime = MagicMock()
        mock_mime.hasUrls.return_value = True
        mock_mime.urls.return_value = [_make_local_file_url(self.file1)]

        mock_event = MagicMock()
        mock_event.mimeData.return_value = mock_mime

        MainWindow.dropEvent(mock_win, mock_event)

        mock_event.acceptProposedAction.assert_called_once()
        payload = mock_win._bridge.filesDropped.emit.call_args[0][0]
        data = json.loads(payload)
        self.assertEqual(len(data["files"]), 1)
        self.assertEqual(data["files"][0]["name"], "hello.pdf")
        self.assertEqual(data["files"][0]["ext"], "pdf")

    def test_drop_records_history(self):
        """drop 成功后应调用 _record_history"""
        from mmfb.core.window import MainWindow

        mock_win = MagicMock()
        mock_win._bridge = MagicMock()
        mock_win._record_history = MagicMock()

        mock_mime = MagicMock()
        mock_mime.hasUrls.return_value = True
        mock_mime.urls.return_value = [_make_local_file_url(self.file1)]

        mock_event = MagicMock()
        mock_event.mimeData.return_value = mock_mime

        MainWindow.dropEvent(mock_win, mock_event)

        mock_win._record_history.assert_called_once()
        call_args = mock_win._record_history.call_args
        self.assertEqual(call_args[0][0], self.file1)
        self.assertEqual(call_args[0][1], "hello.pdf")
        self.assertEqual(call_args[0][2], "pdf")


class TestFilePayloadFormat(unittest.TestCase):
    """验证信号 payload 格式符合 navigator.js 的期望"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.tmp_dir, "Test File (v2).PDF")
        with open(self.test_file, "w") as f:
            f.write("content")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_payload_structure(self):
        from mmfb.core.window import MainWindow

        mock_win = MagicMock()
        mock_win._bridge = MagicMock()

        mock_mime = MagicMock()
        mock_mime.hasUrls.return_value = True
        mock_mime.urls.return_value = [_make_local_file_url(self.test_file)]

        mock_event = MagicMock()
        mock_event.mimeData.return_value = mock_mime

        MainWindow.dropEvent(mock_win, mock_event)

        payload = mock_win._bridge.filesDropped.emit.call_args[0][0]
        data = json.loads(payload)

        self.assertIn("type", data)
        self.assertIn("files", data)
        self.assertIsInstance(data["files"], list)

        f = data["files"][0]
        self.assertIn("name", f)
        self.assertIn("path", f)
        self.assertIn("ext", f)
        self.assertEqual(f["name"], "Test File (v2).PDF")
        self.assertEqual(f["ext"], "pdf")
        self.assertEqual(f["path"], self.test_file)

    def test_case_insensitive_ext(self):
        """扩展名应统一转为小写"""
        from mmfb.core.window import MainWindow

        tmp_dir = tempfile.mkdtemp()
        try:
            test_file = os.path.join(tmp_dir, "UPPER.PNG")
            with open(test_file, "w") as f:
                f.write("png")

            mock_win = MagicMock()
            mock_win._bridge = MagicMock()

            mock_mime = MagicMock()
            mock_mime.hasUrls.return_value = True
            mock_mime.urls.return_value = [_make_local_file_url(test_file)]

            mock_event = MagicMock()
            mock_event.mimeData.return_value = mock_mime

            MainWindow.dropEvent(mock_win, mock_event)

            payload = mock_win._bridge.filesDropped.emit.call_args[0][0]
            data = json.loads(payload)
            self.assertEqual(data["files"][0]["ext"], "png")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_special_characters_in_path(self):
        """路径中包含特殊字符时应正确处理"""
        from mmfb.core.window import MainWindow

        tmp_dir = tempfile.mkdtemp()
        try:
            test_file = os.path.join(tmp_dir, "文件 #1 (副本).docx")
            with open(test_file, "w") as f:
                f.write("docx")

            mock_win = MagicMock()
            mock_win._bridge = MagicMock()

            mock_mime = MagicMock()
            mock_mime.hasUrls.return_value = True
            mock_mime.urls.return_value = [_make_local_file_url(test_file)]

            mock_event = MagicMock()
            mock_event.mimeData.return_value = mock_mime

            MainWindow.dropEvent(mock_win, mock_event)

            payload = mock_win._bridge.filesDropped.emit.call_args[0][0]
            data = json.loads(payload)
            self.assertEqual(data["files"][0]["name"], "文件 #1 (副本).docx")
            self.assertEqual(data["files"][0]["ext"], "docx")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
