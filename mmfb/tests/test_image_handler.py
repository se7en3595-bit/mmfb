"""ImageHandler 单元测试

测试覆盖：
- can_handle 方法（大小写、不相关扩展名）
- get_preview 基本行为（含最小 PNG 解析）
- EXIF 提取（含无 EXIF 情况）
- GIF 动画帧检测
- 大文件标记
- 缺失文件处理
- get_edit 返回 None
- get_mime 返回正确 MIME
- 注册表分发
"""
import os
import struct
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mmfb.handlers.image_handler import ImageHandler, IMAGE_EXTENSIONS, IMAGE_SIZE_THRESHOLD
from mmfb.core.registry import HandlerRegistry


def _create_minimal_png(width=4, height=4, mode="RGBA"):
    """生成一个最小有效 PNG 文件（纯色）"""
    def _chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    # PNG 签名
    signature = b"\x89PNG\r\n\x1a\n"

    # IHDR
    if mode == "RGBA":
        color_type = 6
        channels = 4
    elif mode == "RGB":
        color_type = 2
        channels = 3
    else:
        color_type = 6
        channels = 4

    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)

    # IDAT: 压缩图像数据
    raw_data = b""
    for y in range(height):
        raw_data += b"\x00"  # filter byte
        for x in range(width):
            if mode == "RGBA":
                raw_data += b"\xFF\x00\x00\xFF"  # 红色不透明
            else:
                raw_data += b"\xFF\x00\x00"

    compressed = zlib.compress(raw_data)
    idat = _chunk(b"IDAT", compressed)

    # IEND
    iend = _chunk(b"IEND", b"")

    return signature + ihdr + idat + iend


def _create_minimal_gif(width=2, height=2):
    """生成一个最小有效 GIF89a 文件（单帧）"""
    # Header
    header = b"GIF89a"

    # Logical Screen Descriptor
    lsd = struct.pack("<HH", width, height)
    lsd += b"\x80"  # GCT flag
    lsd += b"\x00"  # background color index
    lsd += b"\x00"  # pixel aspect ratio

    # Global Color Table (2 colors)
    gct = b"\xFF\x00\x00" + b"\x00\xFF\x00"

    # Image Descriptor
    desc = b"\x2C"
    desc += struct.pack("<HHHH", 0, 0, width, height)
    desc += b"\x00"  # no local color table

    # Image Data
    lzw_min = b"\x02"
    block = b"\x02\x4C\x01"  # minimal LZW data
    sub_block = struct.pack("B", len(block)) + block
    terminator = b"\x00"
    image_data = lzw_min + sub_block + terminator

    # Trailer
    trailer = b"\x3B"

    return header + lsd + gct + desc + image_data + trailer


def _create_minimal_bmp(width=2, height=2):
    """生成一个最小有效 BMP 文件"""
    # BMP File Header
    file_header = b"BM"
    pixel_data_size = width * height * 3
    file_size = 54 + pixel_data_size
    file_header += struct.pack("<I", file_size)
    file_header += b"\x00\x00"  # reserved
    file_header += b"\x00\x00"  # reserved
    file_header += struct.pack("<I", 54)  # pixel offset

    # DIB Header (BITMAPINFOHEADER)
    dib_header = struct.pack("<I", 40)  # header size
    dib_header += struct.pack("<i", width)
    dib_header += struct.pack("<i", height)
    dib_header += struct.pack("<H", 1)  # color planes
    dib_header += struct.pack("<H", 24)  # bits per pixel
    dib_header += struct.pack("<I", 0)  # no compression
    dib_header += struct.pack("<I", pixel_data_size)
    dib_header += struct.pack("<i", 2835)  # h res
    dib_header += struct.pack("<i", 2835)  # v res
    dib_header += struct.pack("<I", 0)  # colors in palette
    dib_header += struct.pack("<I", 0)  # important colors

    # Pixel data (BGR, bottom-up, padded to 4 bytes)
    row_size = (width * 3 + 3) & ~3
    pixel_data = b"\x00" * (row_size * height)

    return file_header + dib_header + pixel_data


class TestImageHandlerBasic(unittest.TestCase):
    """基础方法测试"""

    def test_can_handle_png(self):
        self.assertTrue(ImageHandler.can_handle("/tmp/test.png"))

    def test_can_handle_jpg(self):
        self.assertTrue(ImageHandler.can_handle("/tmp/test.jpg"))

    def test_can_handle_jpeg(self):
        self.assertTrue(ImageHandler.can_handle("/tmp/test.jpeg"))

    def test_can_handle_bmp(self):
        self.assertTrue(ImageHandler.can_handle("/tmp/test.bmp"))

    def test_can_handle_gif(self):
        self.assertTrue(ImageHandler.can_handle("/tmp/test.gif"))

    def test_can_handle_tiff(self):
        self.assertTrue(ImageHandler.can_handle("/tmp/test.tiff"))

    def test_can_handle_tif(self):
        self.assertTrue(ImageHandler.can_handle("/tmp/test.tif"))

    def test_can_handle_ico(self):
        self.assertTrue(ImageHandler.can_handle("/tmp/test.ico"))

    def test_can_handle_webp(self):
        self.assertTrue(ImageHandler.can_handle("/tmp/test.webp"))

    def test_can_handle_uppercase(self):
        self.assertTrue(ImageHandler.can_handle("/tmp/test.PNG"))

    def test_can_handle_mixed_case(self):
        self.assertTrue(ImageHandler.can_handle("/tmp/test.Png"))

    def test_reject_other_ext(self):
        self.assertFalse(ImageHandler.can_handle("/tmp/test.pdf"))

    def test_reject_no_ext(self):
        self.assertFalse(ImageHandler.can_handle("/tmp/noext"))

    def test_reject_markdown(self):
        self.assertFalse(ImageHandler.can_handle("/tmp/test.md"))

    def test_extensions_list_complete(self):
        expected = {".png", ".jpg", ".jpeg", ".jpe", ".jfif",
                     ".bmp", ".dib", ".gif", ".tiff", ".tif",
                     ".ico", ".webp"}
        self.assertEqual(set(IMAGE_EXTENSIONS), expected)

    def test_get_edit_returns_none(self):
        handler = ImageHandler("/tmp/dummy.png")
        self.assertIsNone(handler.get_edit())


class TestImageHandlerMime(unittest.TestCase):
    """MIME 类型测试"""

    def test_mime_png(self):
        handler = ImageHandler("/tmp/test.png")
        self.assertEqual(handler.get_mime(), "image/png")

    def test_mime_jpg(self):
        handler = ImageHandler("/tmp/test.jpg")
        self.assertEqual(handler.get_mime(), "image/jpeg")

    def test_mime_jpeg(self):
        handler = ImageHandler("/tmp/test.jpeg")
        self.assertEqual(handler.get_mime(), "image/jpeg")

    def test_mime_gif(self):
        handler = ImageHandler("/tmp/test.gif")
        self.assertEqual(handler.get_mime(), "image/gif")

    def test_mime_bmp(self):
        handler = ImageHandler("/tmp/test.bmp")
        self.assertEqual(handler.get_mime(), "image/bmp")

    def test_mime_webp(self):
        handler = ImageHandler("/tmp/test.webp")
        self.assertEqual(handler.get_mime(), "image/webp")

    def test_mime_unknown_fallback(self):
        handler = ImageHandler("/tmp/test.xyz")
        self.assertEqual(handler.get_mime(), "image/png")


class TestImageHandlerPreviewPNG(unittest.TestCase):
    """PNG 预览测试"""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        self.tmp.write(_create_minimal_png(8, 8, "RGBA"))
        self.tmp.close()

    def tearDown(self):
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_preview_returns_dict(self):
        handler = ImageHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertIsInstance(result, dict)

    def test_preview_template_is_image(self):
        handler = ImageHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertEqual(result.get("template"), "image")

    def test_preview_mime_is_png(self):
        handler = ImageHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertEqual(result.get("mime"), "image/png")

    def test_preview_dimensions(self):
        handler = ImageHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertEqual(result["data"]["width"], 8)
        self.assertEqual(result["data"]["height"], 8)

    def test_preview_mode_is_rgba(self):
        handler = ImageHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertEqual(result["data"]["mode"], "RGBA")

    def test_preview_format_is_png(self):
        handler = ImageHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertEqual(result["data"]["format"], "PNG")

    def test_preview_has_data_url(self):
        handler = ImageHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertIn("data_url", result["data"])
        self.assertTrue(result["data"]["data_url"].startswith("data:image/png;base64,"))

    def test_preview_editable_true(self):
        handler = ImageHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertTrue(result.get("editable"))

    def test_preview_large_image_false(self):
        handler = ImageHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertFalse(result["data"]["large_image"])

    def test_preview_has_exif_field(self):
        handler = ImageHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertIn("has_exif", result["data"])
        self.assertIn("exif", result["data"])

    def test_preview_animated_false(self):
        handler = ImageHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertFalse(result["data"]["is_animated"])
        self.assertEqual(result["data"]["frame_count"], 1)


class TestImageHandlerPreviewGIF(unittest.TestCase):
    """GIF 预览测试"""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".gif", delete=False)
        self.tmp.write(_create_minimal_gif(2, 2))
        self.tmp.close()

    def tearDown(self):
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_preview_template_is_image(self):
        handler = ImageHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertEqual(result.get("template"), "image")

    def test_preview_mime_is_gif(self):
        handler = ImageHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertEqual(result.get("mime"), "image/gif")

    def test_preview_format_is_gif(self):
        handler = ImageHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertEqual(result["data"]["format"], "GIF")

    def test_preview_dimensions(self):
        handler = ImageHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertEqual(result["data"]["width"], 2)
        self.assertEqual(result["data"]["height"], 2)


class TestImageHandlerPreviewBMP(unittest.TestCase):
    """BMP 预览测试"""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".bmp", delete=False)
        self.tmp.write(_create_minimal_bmp(2, 2))
        self.tmp.close()

    def tearDown(self):
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_preview_template_is_image(self):
        handler = ImageHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertEqual(result.get("template"), "image")

    def test_preview_mime_is_bmp(self):
        handler = ImageHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertEqual(result.get("mime"), "image/bmp")

    def test_preview_format_is_bmp(self):
        handler = ImageHandler(self.tmp.name)
        result = handler.get_preview()
        self.assertEqual(result["data"]["format"], "BMP")


class TestImageHandlerMissingFile(unittest.TestCase):
    """缺失文件处理"""

    def test_preview_missing_file_returns_dict(self):
        handler = ImageHandler("/tmp/nonexistentfiletest.png")
        result = handler.get_preview()
        self.assertIsInstance(result, dict)

    def test_preview_missing_file_has_error(self):
        handler = ImageHandler("/tmp/nonexistentfiletest.png")
        result = handler.get_preview()
        self.assertIn("error", result)

    def test_preview_missing_file_template_still_image(self):
        handler = ImageHandler("/tmp/nonexistentfiletest.png")
        result = handler.get_preview()
        self.assertEqual(result.get("template"), "image")


class TestImageHandlerRegistry(unittest.TestCase):
    """注册表集成测试"""

    def test_registry_dispatch_png(self):
        reg = HandlerRegistry()
        from mmfb.handlers import ImageHandler
        reg.register_class(ImageHandler)
        handler = reg.get_handler("/tmp/test.png")
        self.assertIsInstance(handler, ImageHandler)

    def test_registry_dispatch_jpg(self):
        reg = HandlerRegistry()
        from mmfb.handlers import ImageHandler
        reg.register_class(ImageHandler)
        handler = reg.get_handler("/tmp/test.jpg")
        self.assertIsInstance(handler, ImageHandler)

    def test_registry_dispatch_gif(self):
        reg = HandlerRegistry()
        from mmfb.handlers import ImageHandler
        reg.register_class(ImageHandler)
        handler = reg.get_handler("/tmp/test.gif")
        self.assertIsInstance(handler, ImageHandler)

    def test_registry_dispatch_webp(self):
        reg = HandlerRegistry()
        from mmfb.handlers import ImageHandler
        reg.register_class(ImageHandler)
        handler = reg.get_handler("/tmp/test.webp")
        self.assertIsInstance(handler, ImageHandler)

    def test_registry_dispatch_uppercase(self):
        reg = HandlerRegistry()
        from mmfb.handlers import ImageHandler
        reg.register_class(ImageHandler)
        handler = reg.get_handler("/tmp/test.PNG")
        self.assertIsInstance(handler, ImageHandler)

    def test_registry_count_after_image(self):
        """count() 返回已注册的扩展名数量，ImageHandler 有 12 个扩展名"""
        reg = HandlerRegistry()
        from mmfb.handlers import ImageHandler
        reg.register_class(ImageHandler)
        self.assertEqual(reg.count(), len(ImageHandler.extensions))


class TestImageHandlerThreshold(unittest.TestCase):
    """阈值常量测试"""

    def test_image_size_threshold_value(self):
        self.assertEqual(IMAGE_SIZE_THRESHOLD, 20 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
