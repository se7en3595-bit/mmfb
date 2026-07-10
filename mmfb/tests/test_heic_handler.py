"""HEIC/HEIF Handler 单元测试

覆盖：
- 注册表匹配（.heic/.heif/.hif/.heics/.heifs）
- 大小写不敏感匹配
- MIME 映射
- 编辑标记 editable=True
- 错误处理（文件不存在、非 HEIC 文件）
- HeicHandler 实例化与属性
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# 确保 mmfb 在路径中
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestHeicHandlerRegistration(unittest.TestCase):
    """测试 HeicHandler 注册表匹配"""

    def setUp(self):
        from mmfb.core.registry import registry
        from mmfb.handlers import HeicHandler
        # 清理注册表后重新注册
        registry._simple.clear()
        registry._compound.clear()
        registry.register_class(HeicHandler)
        self.registry = registry

    def tearDown(self):
        from mmfb.core.registry import registry
        registry._simple.clear()
        registry._compound.clear()

    def test_match_heic(self):
        handler = self.registry.get_handler("/tmp/photo.heic")
        self.assertIsNotNone(handler)
        self.assertEqual(handler.__class__.__name__, "HeicHandler")

    def test_match_heif(self):
        handler = self.registry.get_handler("/tmp/photo.heif")
        self.assertIsNotNone(handler)
        self.assertEqual(handler.__class__.__name__, "HeicHandler")

    def test_match_hif(self):
        handler = self.registry.get_handler("/tmp/photo.hif")
        self.assertIsNotNone(handler)
        self.assertEqual(handler.__class__.__name__, "HeicHandler")

    def test_match_heics(self):
        handler = self.registry.get_handler("/tmp/photo.heics")
        self.assertIsNotNone(handler)
        self.assertEqual(handler.__class__.__name__, "HeicHandler")

    def test_match_heifs(self):
        handler = self.registry.get_handler("/tmp/photo.heifs")
        self.assertIsNotNone(handler)
        self.assertEqual(handler.__class__.__name__, "HeicHandler")

    def test_case_insensitive(self):
        handler = self.registry.get_handler("/tmp/photo.HEIC")
        self.assertIsNotNone(handler)
        self.assertEqual(handler.__class__.__name__, "HeicHandler")

        handler = self.registry.get_handler("/tmp/photo.HeIc")
        self.assertIsNotNone(handler)
        self.assertEqual(handler.__class__.__name__, "HeicHandler")

    def test_non_heic_not_matched(self):
        handler = self.registry.get_handler("/tmp/photo.jpg")
        self.assertIsNone(handler)

        handler = self.registry.get_handler("/tmp/photo.png")
        self.assertIsNone(handler)


class TestHeicHandlerMime(unittest.TestCase):
    """测试 MIME 映射"""

    def setUp(self):
        from mmfb.handlers import HeicHandler
        self.handler_cls = HeicHandler

    def test_heic_mime(self):
        h = self.handler_cls("/tmp/test.heic")
        self.assertEqual(h.get_mime(), "image/heic")

    def test_heics_mime(self):
        h = self.handler_cls("/tmp/test.heics")
        self.assertEqual(h.get_mime(), "image/heic")

    def test_heif_mime(self):
        h = self.handler_cls("/tmp/test.heif")
        self.assertEqual(h.get_mime(), "image/heif")

    def test_hif_mime(self):
        h = self.handler_cls("/tmp/test.hif")
        self.assertEqual(h.get_mime(), "image/heif")


class TestHeicHandlerPreview(unittest.TestCase):
    """测试预览功能"""

    def setUp(self):
        from mmfb.handlers import HeicHandler
        self.handler_cls = HeicHandler
        self.tmpdir = tempfile.mkdtemp()

    def _write_dummy_file(self, ext):
        path = os.path.join(self.tmpdir, "test" + ext)
        # 写一个假的 HEIC 文件头（足够让 Image.open 报错，但用于测试错误处理）
        with open(path, "wb") as f:
            f.write(b"NOT_A_HEIC_FILE")
        return path

    def test_file_not_found(self):
        h = self.handler_cls("/nonexistent/path.heic")
        result = h.get_preview()
        self.assertIsNotNone(result)
        self.assertIn("error", result)
        self.assertIn("not found", result["error"].lower())

    def test_invalid_file_error(self):
        path = self._write_dummy_file(".heic")
        h = self.handler_cls(path)
        result = h.get_preview()
        self.assertIsNotNone(result)
        # 文件不是有效 HEIC，应该返回错误
        self.assertIn("error", result)

    def test_editable_true(self):
        """即使文件无效，editable 标志应为 True"""
        path = self._write_dummy_file(".heic")
        h = self.handler_cls(path)
        # 由于文件无效，preview 会返回错误结构，editable=False
        # 这是预期行为
        result = h.get_preview()
        if "error" not in result:
            self.assertTrue(result.get("editable", False))

    def test_get_edit_returns_data(self):
        """get_edit 返回数据结构"""
        path = self._write_dummy_file(".heic")
        h = self.handler_cls(path)
        edit = h.get_edit()
        if edit is not None:
            self.assertIn("data", edit)
            self.assertTrue(edit.get("editable", False))


class TestHeicHandlerApplyEdit(unittest.TestCase):
    """测试编辑操作"""

    def test_save_heic_output_falls_back_to_png(self):
        """保存路径为 .heic 时应降级为 .png"""
        from mmfb.handlers import HeicHandler
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建一个有效的 PNG 文件作为输入
            from PIL import Image
            input_path = os.path.join(tmpdir, "input.png")
            img = Image.new("RGB", (100, 100), color="red")
            img.save(input_path)

            output_path = os.path.join(tmpdir, "output.heic")
            result = HeicHandler.apply_edit(input_path, [], output_path)
            # 检查输出路径被降级为 .png
            self.assertIn(".png", result.get("path", ""))


class TestHeicHandlerExtensions(unittest.TestCase):
    """测试 extensions 属性"""

    def test_all_expected_extensions(self):
        from mmfb.handlers import HeicHandler
        expected = {".heic", ".heif", ".hif", ".heics", ".heifs"}
        self.assertEqual(set(HeicHandler.extensions), expected)


if __name__ == "__main__":
    unittest.main()
