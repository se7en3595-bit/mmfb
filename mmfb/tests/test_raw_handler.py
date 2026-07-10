"""RawHandler 单元测试

不依赖真实 RAW 文件，仅验证：
- RawHandler 能正确注册到 Registry
- can_known() 扩展名匹配逻辑
- 错误处理：文件不存在
- error_result 结构正确
"""
import os
import sys
import unittest

# 确保项目根在 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mmfb.handlers.raw_handler import RawHandler, RAW_EXTENSIONS
from mmfb.core.registry import registry


class TestRawHandlerRegistry(unittest.TestCase):
    """测试 RawHandler 是否已注册"""

    def setUp(self):
        import importlib
        import mmfb.handlers as h
        importlib.reload(h)

    def test_raw_handler_registered(self):
        """RAW 扩展名应注册到 registry"""
        for ext in RAW_EXTENSIONS:
            handler = registry.get_handler("/tmp/test" + ext)
            self.assertIsNotNone(handler, f"no handler for {ext}")
            self.assertIsInstance(handler, RawHandler)

    def test_unknown_ext_not_handled(self):
        """未知扩展名不应匹配"""
        self.assertIsNone(registry.get_handler("/tmp/test.xyz"))

    def test_can_handle_lower_case(self):
        """大小写忽略匹配"""
        self.assertTrue(RawHandler.can_handle("/tmp/test.CR2"))
        self.assertTrue(RawHandler.can_handle("/tmp/test.NEF"))
        self.assertTrue(RawHandler.can_handle("/tmp/test.ARW"))
        self.assertTrue(RawHandler.can_handle("/tmp/test.DNG"))


class TestRawHandlerErrors(unittest.TestCase):
    """测试错误处理"""

    def test_file_not_found(self):
        handler = RawHandler("/tmp/nonexistent_file.cr2")
        result = handler.get_preview()
        self.assertIn("error", result)
        self.assertFalse(result["editable"])

    def test_error_result_structure(self):
        handler = RawHandler("/tmp/nonexistent.cr2")
        result = handler.get_preview()
        self.assertIn("template", result)
        self.assertIn("data", result)
        self.assertEqual(result["template"], "image")
        # 错误时不包含 data_url
        self.assertNotIn("data_url", result["data"])
        self.assertEqual(result["data"]["exif"], {})
        self.assertFalse(result["editable"])


class TestRawHandlerAttributes(unittest.TestCase):
    """测试 RawHandler 属性"""

    def test_extensions_count(self):
        """至少支持 10 种 RAW 格式"""
        self.assertGreaterEqual(len(RawHandler.extensions), 10)

    def test_required_extensions_present(self):
        """核心 RAW 扩展名必须包含"""
        required = [".cr2", ".nef", ".arw", ".dng", ".raf", ".orf"]
        for ext in required:
            self.assertIn(ext, RawHandler.extensions)

    def test_format_fnumber(self):
        self.assertEqual(RawHandler._format_fnumber((28, 10)), "f/2.8")
        self.assertEqual(RawHandler._format_fnumber(4.0), "f/4.0")

    def test_format_exposure_time(self):
        self.assertEqual(RawHandler._format_exposure_time((1, 60)), "1/60s")


if __name__ == "__main__":
    unittest.main()
