"""PsdHandler 测试用例

测试 PsdHandler 的 get_preview / can_handle / extensions 输出结构。
不依赖 PySide6，仅测试纯 Python 逻辑。

使用 psd-tools 程序化生成一个迷你 PSD 文件（带2个图层），作为夹具测试。
"""
import os
import sys
import json
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mmfb.handlers.psd_handler import PsdHandler, _layer_kind, _pil_to_base64


def _create_minimal_psd(path: str) -> str:
    """程序化生成一个2图层的 PSD 文件用于测试"""
    from psd_tools import PSDImage
    from PIL import Image

    psd = PSDImage.new(mode="RGB", size=(64, 64), color=(255, 200, 150))

    layer1 = psd.create_pixel_layer(
        image=Image.new("RGB", (64, 64), (255, 0, 0)),
        name="Red Box",
    )
    psd.append(layer1)

    layer2 = psd.create_pixel_layer(
        image=Image.new("RGBA", (32, 32), (0, 255, 0, 128)),
        name="Green Overlay",
        top=16, left=16,
    )
    psd.append(layer2)

    psd.save(path)
    return path


class TestPsdHandlerPreview(unittest.TestCase):
    """PsdHandler.get_preview() 测试"""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.psd_path = os.path.join(cls.temp_dir, "test.psd")
        _create_minimal_psd(cls.psd_path)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_preview_returns_dict(self):
        handler = PsdHandler(self.psd_path)
        result = handler.get_preview()
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)

    def test_mime_and_template(self):
        handler = PsdHandler(self.psd_path)
        result = handler.get_preview()
        self.assertEqual(result["mime"], "image/png")
        self.assertEqual(result["template"], "psd")

    def test_canvas_dimensions(self):
        handler = PsdHandler(self.psd_path)
        result = handler.get_preview()
        self.assertEqual(result["data"]["width"], 64)
        self.assertEqual(result["data"]["height"], 64)

    def test_has_composite_data_url(self):
        handler = PsdHandler(self.psd_path)
        result = handler.get_preview()
        composite = result["data"]["composite"]
        self.assertIsInstance(composite, str)
        self.assertTrue(composite.startswith("data:image/png;base64,"))

    def test_layer_count(self):
        handler = PsdHandler(self.psd_path)
        result = handler.get_preview()
        layer_count = result["data"]["layer_count"]
        # 至少包含2个像素图层（可能还有其他元图层，看 psd-tools 版本）
        self.assertGreaterEqual(layer_count, 2)

    def test_layers_is_list(self):
        handler = PsdHandler(self.psd_path)
        result = handler.get_preview()
        layers = result["data"]["layers"]
        self.assertIsInstance(layers, list)
        self.assertTrue(len(layers) > 0)

    def test_layer_structure(self):
        handler = PsdHandler(self.psd_path)
        result = handler.get_preview()
        layers = result["data"]["layers"]
        for layer in layers:
            self.assertIn("name", layer)
            self.assertIn("kind", layer)
            self.assertIn("visible", layer)
            self.assertIn("opacity", layer)
            self.assertIn("width", layer)
            self.assertIn("height", layer)
            self.assertIsInstance(layer["name"], str)
            self.assertIsInstance(layer["kind"], str)

    def test_pixel_layer_has_thumbnail(self):
        handler = PsdHandler(self.psd_path)
        result = handler.get_preview()
        layers = result["data"]["layers"]
        pixel_layers = [l for l in layers if l.get("kind") == "pixel"]
        self.assertTrue(len(pixel_layers) > 0)
        for pl in pixel_layers:
            # 缩略图可能提取失败为空，但不应该抛异常
            self.assertIsInstance(pl.get("thumbnail", ""), str)

    def test_editable_is_false(self):
        handler = PsdHandler(self.psd_path)
        result = handler.get_preview()
        self.assertFalse(result.get("editable", True))

    def test_color_mode_present(self):
        handler = PsdHandler(self.psd_path)
        result = handler.get_preview()
        mode = result["data"]["mode"]
        self.assertIsInstance(mode, str)
        self.assertTrue(len(mode) > 0)


class TestPsdHandlerErrors(unittest.TestCase):
    """边界情况测试"""

    def test_nonexistent_file_returns_error(self):
        handler = PsdHandler("/tmp/does_not_exist_xyz_999.psd")
        result = handler.get_preview()
        self.assertIsNotNone(result)
        self.assertIn("error", result)

    def test_empty_file_returns_error(self):
        f = tempfile.NamedTemporaryFile(suffix=".psd", delete=False)
        f.write(b"not a psd file at all")
        f.close()
        try:
            handler = PsdHandler(f.name)
            result = handler.get_preview()
            self.assertIsNotNone(result)
            self.assertIn("error", result)
        finally:
            os.unlink(f.name)

    def test_invalid_extension_no_preview(self):
        # 传入一个 .png 给 PsdHandler 不应崩溃
        from PIL import Image
        f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        img = Image.new("RGB", (16, 16), (100, 100, 100))
        img.save(f, format="PNG")
        f.close()
        try:
            handler = PsdHandler(f.name)
            result = handler.get_preview()
            # 应返回错误（因为 PNG 不是有效 PSD）
            self.assertIsNotNone(result)
            self.assertIn("error", result)
        finally:
            os.unlink(f.name)


class TestPsdHandlerCanHandle(unittest.TestCase):
    """can_handle() 类方法测试"""

    def test_can_handle_psd(self):
        self.assertTrue(PsdHandler.can_handle("test.psd"))

    def test_can_handle_psb(self):
        self.assertTrue(PsdHandler.can_handle("test.psb"))

    def test_can_handle_uppercase(self):
        self.assertTrue(PsdHandler.can_handle("TEST.PSD"))

    def test_can_handle_mixed_case(self):
        self.assertTrue(PsdHandler.can_handle("MyFile.Psd"))

    def test_cannot_handle_png(self):
        self.assertFalse(PsdHandler.can_handle("test.png"))

    def test_cannot_handle_jpg(self):
        self.assertFalse(PsdHandler.can_handle("test.jpg"))


class TestPsdHandlerExtensions(unittest.TestCase):
    """extensions 类属性"""

    def test_extensions_list(self):
        self.assertIn(".psd", PsdHandler.extensions)
        self.assertIn(".psb", PsdHandler.extensions)

    def test_extensions_all_start_with_dot(self):
        for ext in PsdHandler.extensions:
            self.assertTrue(ext.startswith("."))


class TestPsdHandlerGetMime(unittest.TestCase):
    def test_get_mime(self):
        handler = PsdHandler("foo.psd")
        self.assertEqual(handler.get_mime(), "image/vnd.adobe.photoshop")


class TestPsdHandlerGetEdit(unittest.TestCase):
    def test_get_edit_returns_none(self):
        handler = PsdHandler("foo.psd")
        self.assertIsNone(handler.get_edit())


class TestPsdHandlerRegistry(unittest.TestCase):
    """验证正确注册到全局 registry"""

    def setUp(self):
        import importlib
        import mmfb.handlers as h
        importlib.reload(h)

    def test_registry_can_dispatch_psd(self):
        from mmfb.core.registry import registry
        handler = registry.get_handler("test.psd")
        self.assertIsNotNone(handler)
        self.assertIsInstance(handler, PsdHandler)

    def test_registry_can_dispatch_psb(self):
        from mmfb.core.registry import registry
        handler = registry.get_handler("test.psb")
        self.assertIsNotNone(handler)
        self.assertIsInstance(handler, PsdHandler)


class TestPilToBase64(unittest.TestCase):
    """_pil_to_base64 工具函数"""

    def test_generates_data_url(self):
        from PIL import Image
        img = Image.new("RGB", (10, 10), (255, 0, 0))
        result = _pil_to_base64(img)
        self.assertTrue(result.startswith("data:image/png;base64,"))
        self.assertTrue(len(result) > 50)

    def test_none_input_returns_empty(self):
        from mmfb.handlers.psd_handler import _pil_to_base64 as f
        self.assertEqual(f(None), "")

    def test_large_image_resized(self):
        from PIL import Image
        # 创建一个 512x512 的图，max_size=64，应该被缩放
        img = Image.new("RGB", (512, 512), (0, 128, 255))
        result = _pil_to_base64(img, max_size=64)
        self.assertTrue(len(result) > 0)


class TestLayerKind(unittest.TestCase):
    """_layer_kind 分类映射"""

    def test_pixel_layer(self):
        from unittest.mock import MagicMock
        mock = MagicMock()
        mock.has_pixels.return_value = True
        mock.is_group.return_value = False
        self.assertEqual(_layer_kind(mock), "pixel")

    def test_group_layer(self):
        from unittest.mock import MagicMock
        mock = MagicMock()
        mock.has_pixels.side_effect = Exception("no pixels")
        mock.is_group.return_value = True
        self.assertEqual(_layer_kind(mock), "group")

    def test_unknown_layer_returns_other(self):
        from unittest.mock import MagicMock
        mock = MagicMock()
        mock.has_pixels.side_effect = RuntimeError("nope")
        mock.is_group.return_value = False
        self.assertEqual(_layer_kind(mock), "other")


class TestPsdHandlerLargeFile(unittest.TestCase):
    """大文件标记测试"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.psd_path = os.path.join(self.tmpdir, "big.psd")
        _create_minimal_psd(self.psd_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_small_file_not_large(self):
        handler = PsdHandler(self.psd_path)
        result = handler.get_preview()
        self.assertFalse(result["data"]["large_file"])


class TestPsdHandlerIntegration(unittest.TestCase):
    """端到端测试：完整流程校验"""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.psd_path = os.path.join(cls.temp_dir, "integ.psd")
        _create_minimal_psd(cls.psd_path)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_preview_serializable(self):
        """返回结果可被 JSON 序列化（不含 bytes / MagicMock）"""
        handler = PsdHandler(self.psd_path)
        result = handler.get_preview()
        # 转为 JSON 再转回来，确保无不可序列化对象
        serialized = json.dumps(result)
        restored = json.loads(serialized)
        self.assertEqual(restored["template"], "psd")
        self.assertIsInstance(restored["data"]["layers"], list)

    def test_all_layers_have_required_keys(self):
        handler = PsdHandler(self.psd_path)
        result = handler.get_preview()
        required = {"name", "kind", "visible", "opacity", "width", "height", "offset_x", "offset_y"}
        for layer in result["data"]["layers"]:
            for key in required:
                self.assertIn(key, layer, f"图层缺少字段 {key}: {layer}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
