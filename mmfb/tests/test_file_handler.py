"""file_handler.py 单元测试"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 确保可导入 mmfb 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from mmfb.core.file_handler import (
    FileOperationError,
    PathValidationError,
    _validate_path,
    safe_read_binary,
    safe_read_text,
    safe_read_json,
    safe_write_binary,
    safe_write_text,
    get_file_info,
    list_directory,
    MAX_FILE_SIZE_BYTES,
)


class TestValidatePath(unittest.TestCase):
    """路径验证测试"""

    def test_empty_path_raises(self):
        with self.assertRaises(PathValidationError):
            _validate_path("")

    def test_null_byte_raises(self):
        with self.assertRaises(PathValidationError):
            _validate_path("foo\x00bar.txt")

    def test_normal_path_returns_path(self):
        p = _validate_path("/tmp/test.txt")
        self.assertIsInstance(p, Path)


class TestSafeReadBinary(unittest.TestCase):

    def test_read_existing_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello binary")
            path = f.name
        try:
            result = safe_read_binary(path)
            self.assertEqual(result, b"hello binary")
        finally:
            os.unlink(path)

    def test_read_nonexistent_returns_none(self):
        result = safe_read_binary("/nonexistent/path/file.bin")
        self.assertIsNone(result)

    def test_read_directory_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            result = safe_read_binary(d)
            self.assertIsNone(result)

    def test_read_large_file_returns_none(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            # 写入超过限制的数据
            f.write(b"x" * (MAX_FILE_SIZE_BYTES + 1))
            path = f.name
        try:
            result = safe_read_binary(path)
            self.assertIsNone(result)
        finally:
            os.unlink(path)


class TestSafeReadText(unittest.TestCase):

    def test_read_utf8_text(self):
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".txt") as f:
            f.write("Hello 世界")
            path = f.name
        try:
            result = safe_read_text(path)
            self.assertEqual(result, "Hello 世界")
        finally:
            os.unlink(path)

    def test_read_nonexistent_returns_none(self):
        result = safe_read_text("/nonexistent/file.txt")
        self.assertIsNone(result)


class TestSafeReadJson(unittest.TestCase):

    def test_read_valid_json(self):
        data = {"key": "value", "num": 42, "list": [1, 2, 3]}
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".json") as f:
            json.dump(data, f)
            path = f.name
        try:
            result = safe_read_json(path)
            self.assertEqual(result, data)
        finally:
            os.unlink(path)

    def test_read_invalid_json_returns_none(self):
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".json") as f:
            f.write("{invalid json}")
            path = f.name
        try:
            result = safe_read_json(path)
            self.assertIsNone(result)
        finally:
            os.unlink(path)


class TestSafeWriteBinary(unittest.TestCase):

    def test_write_and_read_back(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.bin")
            self.assertTrue(safe_write_binary(path, b"test data"))
            self.assertEqual(safe_read_binary(path), b"test data")

    def test_write_creates_parent_dir(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "subdir1", "subdir2", "test.bin")
            self.assertTrue(safe_write_binary(path, b"auto mkdir"))
            self.assertTrue(os.path.isfile(path))

    def test_write_invalid_path_returns_false(self):
        # Windows 上含 null byte 的路径无法创建
        result = safe_write_binary("foo\x00bar.bin", b"data")
        self.assertFalse(result)


class TestSafeWriteText(unittest.TestCase):

    def test_write_text_and_read_back(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.txt")
            self.assertTrue(safe_write_text(path, "Hello MMFB"))
            self.assertEqual(safe_read_text(path), "Hello MMFB")


class TestGetFileInfo(unittest.TestCase):

    def test_file_info_fields(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test")
            path = f.name
        try:
            info = get_file_info(path)
            self.assertIsNotNone(info)
            self.assertIn("path", info)
            self.assertIn("name", info)
            self.assertIn("size", info)
            self.assertIn("mime", info)
            self.assertIn("modified", info)
            self.assertIn("is_dir", info)
            self.assertFalse(info["is_dir"])
            self.assertEqual(info["size"], 4)
        finally:
            os.unlink(path)

    def test_directory_info(self):
        with tempfile.TemporaryDirectory() as d:
            info = get_file_info(d)
            self.assertIsNotNone(info)
            self.assertTrue(info["is_dir"])
            self.assertEqual(info["size"], 0)
            self.assertEqual(info["mime"], "directory")

    def test_nonexistent_returns_none(self):
        result = get_file_info("/nonexistent/path")
        self.assertIsNone(result)


class TestListDirectory(unittest.TestCase):

    def test_list_mixed_entries(self):
        with tempfile.TemporaryDirectory() as d:
            Path(os.path.join(d, "dir_b")).mkdir()
            Path(os.path.join(d, "dir_a")).mkdir()
            Path(os.path.join(d, "file_b.txt")).write_text("bbb")
            Path(os.path.join(d, "file_a.txt")).write_text("aaa")
            entries = list_directory(d)
            self.assertEqual(len(entries), 4)
            # 验证排序：目录优先，并按名称排序
            names = [e["name"] for e in entries]
            self.assertEqual(names, ["dir_a", "dir_b", "file_a.txt", "file_b.txt"])
            # 验证目录标记
            dirs = [e for e in entries if e["is_dir"]]
            files = [e for e in entries if not e["is_dir"]]
            self.assertEqual(len(dirs), 2)
            self.assertEqual(len(files), 2)

    def test_hidden_files_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            Path(os.path.join(d, ".hidden")).write_text("secret")
            Path(os.path.join(d, "visible.txt")).write_text("ok")
            entries = list_directory(d)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["name"], "visible.txt")

    def test_nonexistent_returns_empty(self):
        result = list_directory("/nonexistent/dir")
        self.assertEqual(result, [])

    def test_file_path_returns_empty(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            result = list_directory(path)
            self.assertEqual(result, [])
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
