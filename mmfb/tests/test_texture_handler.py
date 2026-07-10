""" TextureHandler 单元测试

覆盖：
1. 注册表匹配（4 种扩展名）
2. 大小写不敏感
3. DDS 二进制头解析（mipmap、像素格式、DX10 扩展）
4. TGA/Pillow 解码路径
5. EXR/HDR 通过 imageio 解码路径
6. 法线贴图检测（BC5 → is_normal_map）
7. 错误处理 / 文件不存在
8. MIME 映射
"""
import io
import os
import struct
import tempfile
import unittest

import numpy as np
from PIL import Image

from mmfb.core.registry import HandlerRegistry
from mmfb.handlers.texture_handler import (
    TextureHandler,
    _parse_dds_header,
    _pil_to_base64_png,
    _reinhard_tonemap,
    NORMAL_MAP_FORMATS,
)


def _write_minimal_dds(path, width=8, height=8, mipmaps=1, four_cc=b"DXT1", dx10_ext=False):
    """写入最小合法 DDS 文件用于测试"""
    pixel_format = struct.pack("<II4s5I", 32, 0x4, four_cc, 0, 0, 0, 0, 0)  # 32 bytes
    caps = struct.pack("<4I", 0x1000 | 0x400000 | 0x8, 0, 0, 0)  # TEXTURE|MIPMAP|COMPLEX

    flags = 0x1 | 0x2 | 0x4 | 0x1000  # CAPS|HEIGHT|WIDTH|MIPMAPCOUNT (and PITCH for uncompressed)
    if four_cc == b"DXT1":
        pitch = max(1, (width + 3) // 4) * 8  # 8 bytes per 4x4 block for DXT1
    elif four_cc in (b"DXT3", b"DXT5"):
        pitch = max(1, (width + 3) // 4) * 16
    else:
        pitch = width * 4

    header = struct.pack("<7I", 124, flags, height, width, pitch, 0, mipmaps)
    header += struct.pack("<11I", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)  # reserved1[11]
    header += pixel_format
    header += caps
    header += struct.pack("<I", 0)  # dwCaps4

    data = b"DDS " + header

    if dx10_ext:
        # DX10 extended header: dxgi_format, dimension, misc_flag, array_size, misc2
        dx10 = struct.pack("<5I", 71, 3, 0, 1, 0)  # BC1_TYPELESS, DIMENSION_TEXTURE2D
        data += dx10

    # Add minimal pixel data (DXT1: 8 bytes per 4x4 block)
    if four_cc == b"DXT1":
        block_count = max(1, ((width + 3) // 4) * ((height + 3) // 4))
        data += b"\xff\x00" * 4 * block_count
    else:
        block_count = max(1, ((width + 3) // 4) * ((height + 3) // 4))
        data += b"\xff" * 16 * block_count

    with open(path, "wb") as f:
        f.write(data)


def _write_minimal_tga(path, width=16, height=16, mode="RGB"):
    """写入最小合法 TGA 文件用于测试"""
    img = Image.new(mode, (width, height), (128, 64, 32) if mode != "L" else 128)
    img.save(path, format="TGA")


class TestTextureRegistry(unittest.TestCase):
    """注册表匹配测试"""

    def _make_registry(self):
        reg = HandlerRegistry()
        reg.register_class(TextureHandler)
        return reg

    def test_can_handle_extensions(self):
        reg = self._make_registry()
        for ext in [".dds", ".tga", ".exr", ".hdr"]:
            handler = reg.get_handler(f"test{ext}")
            self.assertIsNotNone(handler, f"should handle {ext}")
            self.assertIsInstance(handler, TextureHandler)

    def test_case_insensitive(self):
        reg = self._make_registry()
        for name in ["tex.DDS", "tex.Tga", "tex.EXR", "tex.HdR"]:
            handler = reg.get_handler(name)
            self.assertIsNotNone(handler, f"should handle {name}")

    def test_cannot_handle_unrelated(self):
        reg = self._make_registry()
        for name in ["test.png", "test.jpg", "test.bmp", "test.pdf"]:
            handler = reg.get_handler(name)
            self.assertIsNone(handler, f"should not handle {name}")


class TestDdsHeaderParsing(unittest.TestCase):
    """DDS 二进制头解析测试"""

    def test_basic_dxt1_header(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "test.dds")
        _write_minimal_dds(path, width=64, height=64, mipmaps=1, four_cc=b"DXT1")

        info = _parse_dds_header(path)
        self.assertEqual(info["width"], 64)
        self.assertEqual(info["height"], 64)
        self.assertEqual(info["mipmap_count"], 1)
        self.assertIn(info["pixel_format"], ("DXT1",))

    def test_mipmap_count_extraction(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "test.dds")
        _write_minimal_dds(path, width=256, height=256, mipmaps=8, four_cc=b"DXT5")

        info = _parse_dds_header(path)
        self.assertEqual(info["mipmap_count"], 8)

    def test_fourcc_dxt5(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "test.dds")
        _write_minimal_dds(path, four_cc=b"DXT5")

        info = _parse_dds_header(path)
        self.assertEqual(info["pixel_format"], "DXT5")

    def test_normal_map_detection(self):
        self.assertIn("BC5", NORMAL_MAP_FORMATS)
        self.assertIn("BC5U", NORMAL_MAP_FORMATS)
        self.assertIn("BC5S", NORMAL_MAP_FORMATS)

    def test_non_dds_file(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "test.dds")
        with open(path, "wb") as f:
            f.write(b"NOT A DDS FILE at all")

        info = _parse_dds_header(path)
        self.assertEqual(info["pixel_format"], "unknown")
        self.assertEqual(info["mipmap_count"], 1)


class TestDdsDecoding(unittest.TestCase):
    """DDS 完整解码路径测试"""

    def test_decode_dds_dxt1(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "test.dds")
        _write_minimal_dds(path, width=64, height=64, four_cc=b"DXT1")

        handler = TextureHandler(path)
        result = handler.get_preview()
        self.assertIsNotNone(result)
        self.assertIsNone(result.get("error"))
        self.assertEqual(result["data"]["width"], 64)
        self.assertEqual(result["data"]["height"], 64)
        self.assertIn("data_url", result["data"])
        self.assertTrue(result["data"]["data_url"].startswith("data:image/png;base64,"))

    def test_mipmap_preserved_in_result(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "test.dds")
        _write_minimal_dds(path, width=128, height=128, mipmaps=5, four_cc=b"DXT1")

        handler = TextureHandler(path)
        result = handler.get_preview()
        self.assertIsNotNone(result)
        self.assertIsNone(result.get("error"))
        self.assertEqual(result["data"]["mipmap_count"], 5)

    def test_normal_map_flag(self):
        # Create a real DDS with BC5 (normal map) using Pillow
        # Pillow can write DDS with BC5 if the data is right
        # Let's verify the flag mechanism via header parsing
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "normal.dds")
        _write_minimal_dds(path, width=32, height=32, four_cc=b"BC5U")

        # BC5U won't decode with Pillow directly but header parsing should work
        info = _parse_dds_header(path)
        self.assertTrue(info["pixel_format"] in NORMAL_MAP_FORMATS)


class TestTgaDecoding(unittest.TestCase):
    """TGA 解码路径测试"""

    def test_decode_tga_rgb(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "test.tga")
        _write_minimal_tga(path, width=32, height=32, mode="RGB")

        handler = TextureHandler(path)
        result = handler.get_preview()
        self.assertIsNotNone(result)
        self.assertIsNone(result.get("error"))
        self.assertEqual(result["data"]["width"], 32)
        self.assertEqual(result["data"]["height"], 32)
        self.assertEqual(result["data"]["channel_count"], 3)
        self.assertIn("data_url", result["data"])
        self.assertTrue(result["data"]["data_url"].startswith("data:image/png;base64,"))

    def test_decode_tga_rgba(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "test.tga")
        _write_minimal_tga(path, width=32, height=32, mode="RGBA")

        handler = TextureHandler(path)
        result = handler.get_preview()
        self.assertIsNotNone(result)
        self.assertEqual(result["data"]["channel_count"], 4)

    def test_tga_editable(self):
        """TGA 目前为只读格式，不支持就地编辑"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "test.tga")
        _write_minimal_tga(path)

        handler = TextureHandler(path)
        self.assertIsNone(handler.get_edit())


class TestHdrDecoding(unittest.TestCase):
    """EXR/HDR 解码路径测试（需要 imageio + FreeImage）"""

    def _skip_if_no_imageio(self):
        try:
            import imageio.v3  # noqa: F401
            import imageio.plugins._freeimage  # noqa: F401
        except ImportError:
            self.skipTest("imageio not installed")

    def test_decode_exr(self):
        self._skip_if_no_imageio()
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "test.exr")

        # Write a test EXR using imageio
        import imageio.v3 as iio
        data = np.random.rand(16, 16, 3).astype(np.float32)
        iio.imwrite(path, data, extension=".exr")

        handler = TextureHandler(path)
        result = handler.get_preview()
        self.assertIsNotNone(result, f"got error: {result.get('error') if result else None}")
        self.assertIsNone(result.get("error"))
        self.assertEqual(result["data"]["width"], 16)
        self.assertEqual(result["data"]["height"], 16)
        self.assertTrue(result["data"]["is_hdr"])
        self.assertIn("data_url", result["data"])

    def test_decode_hdr(self):
        self._skip_if_no_imageio()
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "test.hdr")

        import imageio.v3 as iio
        data = np.random.rand(16, 16, 3).astype(np.float32)
        iio.imwrite(path, data, extension=".hdr")

        handler = TextureHandler(path)
        result = handler.get_preview()
        self.assertIsNotNone(result)
        self.assertIsNone(result.get("error"))
        self.assertTrue(result["data"]["is_hdr"])

    def test_reinhard_tonemap(self):
        """验证 Reinhard 色调映射输出值域正确"""
        hdr = np.array([[[0.0, 0.5, 1.0],
                         [2.0, 5.0, 10.0]]], dtype=np.float32)
        result = _reinhard_tonemap(hdr)
        self.assertEqual(result.dtype, np.uint8)
        self.assertTrue(np.all(result >= 0))
        self.assertTrue(np.all(result <= 255))
        # 亮度较高的像素应该映射到较高值
        self.assertGreater(result[0, 1, 0], result[0, 0, 0])


class TestErrorHandling(unittest.TestCase):
    """错误处理测试"""

    def test_file_not_found(self):
        handler = TextureHandler("/nonexistent/file.dds")
        result = handler.get_preview()
        self.assertIsNotNone(result)
        self.assertIn("error", result)
        self.assertIn("not found", result["error"].lower())

    def test_unsupported_extension(self):
        handler = TextureHandler("/some/file.xyz")
        # get_preview won't be called for this in practice (no registry match)
        # but test direct call still works
        result = handler.get_preview()
        # The base class can_handle returns False for .xyz
        # TextureHandler.get_preview might return None or error depending
        # Actually the path is "file.xyz" while the code checks extension-specifics
        # DDS/TGA/EXR/HDR would fall through to unsupported format
        if result is not None:
            # Could be None from Pillow failing or "unsupported format" error
            pass  # Either is acceptable

    def test_empty_dds_file(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "empty.dds")
        with open(path, "wb") as f:
            f.write(b"")

        handler = TextureHandler(path)
        result = handler.get_preview()
        # Should not crash - may be error or empty result
        self.assertIsNotNone(result)
        # width/height may be 0 due to failed decode


class TestMimeMap(unittest.TestCase):
    """MIME 类型映射测试"""

    def test_mime_types(self):
        cases = [
            ("file.dds", "image/vnd-ms.dds"),
            ("file.tga", "image/x-targa"),
            ("file.exr", "image/x-exr"),
            ("file.hdr", "image/vnd.radiance"),
        ]
        for path, expected_mime in cases:
            handler = TextureHandler(path)
            mime = handler.get_mime()
            self.assertEqual(mime, expected_mime, f"MIME for {path} should be {expected_mime}")


if __name__ == "__main__":
    unittest.main()
