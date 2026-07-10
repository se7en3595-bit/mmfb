"""QWebChannel 通信桥测试用例

测试 MMFBBridge（Python Slot）的前后端对接能力。
直接实例化 MMFBBridge 调用 Slot，验证返回值与 JSON 序列化。
"""
import os
import sys
import json
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication

# 确保有 QApplication
_app = QApplication.instance() or QApplication(sys.argv)

from mmfb.core.bridge import MMFBBridge


class TestMMFBBridgeBase(unittest.TestCase):
    """基础 fixture：创建 Bridge 实例"""

    def setUp(self):
        self.bridge = MMFBBridge()

    def tearDown(self):
        self.bridge.deleteLater()
        self.bridge = None


class TestReadFile(TestMMFBBridgeBase):
    """read_file slot 测试"""

    def test_read_existing_file(self):
        """读取存在的文本文件应返回内容"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("hello mmfb")
            path = f.name
        try:
            result = self.bridge.read_file(path)
            self.assertEqual(result, "hello mmfb")
        finally:
            os.unlink(path)

    def test_read_nonexistent_file(self):
        """读取不存在的文件应返回空字符串"""
        result = self.bridge.read_file("/tmp/this_file_does_not_exist_999.txt")
        self.assertEqual(result, "")

    def test_read_utf8_with_multibyte(self):
        """读取含多字节字符的文件应正确返回"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("中文内容\nemoji test")
            path = f.name
        try:
            result = self.bridge.read_file(path)
            self.assertEqual(result, "中文内容\nemoji test")
        finally:
            os.unlink(path)


class TestSaveFile(TestMMFBBridgeBase):
    """save_file slot 测试"""

    def test_save_and_read_back(self):
        """保存后再读取应得到相同内容"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            path = f.name

        try:
            ok = self.bridge.save_file(path, "saved content")
            self.assertTrue(ok)

            with open(path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "saved content")
        finally:
            os.unlink(path)

    def test_save_invalid_path_returns_false(self):
        """保存到非法路径应返回 False"""
        ok = self.bridge.save_file("/nonexistent_dir_999/test.txt", "data")
        self.assertFalse(ok)


class TestGetFileInfo(TestMMFBBridgeBase):
    """get_file_info slot 测试"""

    def test_file_info_returns_valid_json(self):
        """文件元信息应返回合法 JSON"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("test")
            path = f.name
        try:
            result = self.bridge.get_file_info(path)
            data = json.loads(result)
            self.assertEqual(data["name"], os.path.basename(path))
            self.assertEqual(data["suffix"], "md")
            self.assertTrue(data["isFile"])
            self.assertFalse(data["isDir"])
        finally:
            os.unlink(path)

    def test_nonexistent_file_returns_empty_object(self):
        """不存在文件应返回 {}"""
        result = self.bridge.get_file_info("/tmp/nonexistent_999.txt")
        self.assertEqual(result, "{}")


class TestListDir(TestMMFBBridgeBase):
    """list_dir slot 测试"""

    def test_list_directory_contents(self):
        """列出目录内容应返回合法 JSON 数组"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试文件与子目录
            open(os.path.join(tmpdir, "file1.txt"), "w").close()
            open(os.path.join(tmpdir, "file2.md"), "w").close()
            os.makedirs(os.path.join(tmpdir, "subdir"))

            result = self.bridge.list_dir(tmpdir)
            data = json.loads(result)

            self.assertIsInstance(data, list)
            names = [e["name"] for e in data]
            self.assertIn("file1.txt", names)
            self.assertIn("file2.md", names)
            self.assertIn("subdir", names)

            # 验证 isDir 标志
            for e in data:
                if e["name"] == "subdir":
                    self.assertTrue(e["isDir"])
                elif e["name"].endswith(".txt"):
                    self.assertFalse(e["isDir"])

    def test_list_nonexistent_dir_returns_empty_array(self):
        """不存在的目录应返回 []"""
        result = self.bridge.list_dir("/nonexistent_dir_999")
        self.assertEqual(result, "[]")

    def test_list_file_path_returns_empty_array(self):
        """传入文件路径（非目录）应返回 []"""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            path = f.name
        try:
            result = self.bridge.list_dir(path)
            self.assertEqual(result, "[]")
        finally:
            os.unlink(path)

    def test_hidden_files_are_skipped(self):
        """隐藏文件（以 . 开头）应被跳过"""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, ".hidden"), "w").close()
            open(os.path.join(tmpdir, "visible.txt"), "w").close()

            result = self.bridge.list_dir(tmpdir)
            data = json.loads(result)
            names = [e["name"] for e in data]
            self.assertNotIn(".hidden", names)
            self.assertIn("visible.txt", names)


class TestSendMessage(TestMMFBBridgeBase):
    """send_message slot 测试"""

    def test_send_message_returns_true(self):
        """发送消息应返回 True"""
        ok = self.bridge.send_message("hello from test")
        self.assertTrue(ok)


class TestConvertFile(TestMMFBBridgeBase):
    """convert_file slot 测试"""

    def test_convert_nonexistent_source_returns_error_json(self):
        """转换不存在的源文件应返回包含 error 的 JSON"""
        result_json = self.bridge.convert_file("/nonexistent/a.txt", "/tmp/b.pdf", "pdf")
        result = json.loads(result_json)
        self.assertFalse(result.get("ok"))
        self.assertIn("error", result)

    def test_convert_unsupported_format_returns_error_json(self):
        """不支持的转换应返回错误"""
        # 使用不存在的转换对
        result_json = self.bridge.convert_file("/tmp/a.unknown", "/tmp/b.pdf", "pdf")
        result = json.loads(result_json)
        self.assertFalse(result.get("ok"))
        self.assertIn("error", result)


class TestBridgeSignal(unittest.TestCase):
    """messageReceived 信号测试"""

    def test_signal_exists(self):
        """MMFBBridge 应有 messageReceived 信号"""
        bridge = MMFBBridge()
        self.assertTrue(hasattr(bridge, 'messageReceived'))
        bridge.deleteLater()


if __name__ == "__main__":
    unittest.main(verbosity=2)
