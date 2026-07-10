"""MediaHandler 单元测试

测试目标：
1. 扩展名识别（视频/音频/大小写/不支持格式）
2. can_handle 行为
3. get_preview 正常路径
4. MIME 映射正确性
5. 错误处理（文件不存在）
6. get_mime 覆盖
7. 字幕扫描功能
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from mmfb.handlers.media_handler import (
    MediaHandler,
    VIDEO_EXTENSIONS,
    AUDIO_EXTENSIONS,
    MIME_MAP,
    FORMAT_MAP,
)


class TestMediaHandlerExtensions(unittest.TestCase):
    """测试扩展名覆盖"""

    def test_video_extensions_list(self):
        expected = [".mp4", ".m4v", ".mkv", ".avi", ".wmv", ".flv", ".mov", ".webm", ".ts", ".m2ts", ".mts", ".3gp"]
        self.assertEqual(VIDEO_EXTENSIONS, expected)

    def test_audio_extensions_list(self):
        expected = [".mp3", ".wav", ".flac", ".aac", ".ogg", ".oga", ".opus", ".wma"]
        self.assertEqual(AUDIO_EXTENSIONS, expected)

    def test_handler_extensions_union(self):
        self.assertEqual(MediaHandler.extensions, VIDEO_EXTENSIONS + AUDIO_EXTENSIONS)


class TestMediaHandlerCanHandle(unittest.TestCase):
    """测试 can_handle 分发"""

    def test_video_lowercase(self):
        self.assertTrue(MediaHandler.can_handle("/path/to/video.mp4"))

    def test_video_uppercase(self):
        self.assertTrue(MediaHandler.can_handle("/path/to/VIDEO.MP4"))

    def test_video_mixed_case(self):
        self.assertTrue(MediaHandler.can_handle("/path/to/Video.Mp4"))

    def test_audio_flac(self):
        self.assertTrue(MediaHandler.can_handle("C:\\Music\\song.flac"))

    def test_audio_opus(self):
        self.assertTrue(MediaHandler.can_handle("/music/track.opus"))

    def test_video_m2ts(self):
        self.assertTrue(MediaHandler.can_handle("/video/clip.m2ts"))

    def test_video_mts(self):
        self.assertTrue(MediaHandler.can_handle("/video/clip.mts"))

    def test_unsupported_pdf(self):
        self.assertFalse(MediaHandler.can_handle("/path/to/file.pdf"))

    def test_unsupported_txt(self):
        self.assertFalse(MediaHandler.can_handle("/path/to/file.txt"))

    def test_unsupported_no_ext(self):
        self.assertFalse(MediaHandler.can_handle("/path/to/file"))

    def test_directory_like(self):
        self.assertFalse(MediaHandler.can_handle("/path/to/media/"))


class TestMediaHandlerGetPreview(unittest.TestCase):
    """测试 get_preview 返回值"""

    def _make_dummy_file(self, name: str) -> str:
        """在二进制临时目录创建空文件"""
        tmp = tempfile.mkdtemp()
        p = os.path.join(tmp, name)
        with open(p, "wb") as f:
            f.write(b"")
        return p

    def test_video_preview_keys(self):
        path = self._make_dummy_file("test_video.mp4")
        handler = MediaHandler(path)
        result = handler.get_preview()

        self.assertIsNotNone(result)
        self.assertIn("mime", result)
        self.assertIn("template", result)
        self.assertIn("data", result)
        self.assertEqual(result["template"], "media")
        self.assertFalse(result["editable"])

    def test_video_mime_correct(self):
        path = self._make_dummy_file("movie.mkv")
        handler = MediaHandler(path)
        result = handler.get_preview()
        self.assertEqual(result["mime"], "video/x-matroska")

    def test_audio_preview(self):
        path = self._make_dummy_file("song.mp3")
        handler = MediaHandler(path)
        result = handler.get_preview()

        self.assertIsNotNone(result)
        self.assertEqual(result["data"]["media_type"], "audio")
        self.assertEqual(result["data"]["format"], "MP3")

    def test_file_not_found(self):
        handler = MediaHandler("/nonexistent/path/video.mp4")
        result = handler.get_preview()
        self.assertIsNotNone(result)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "file not found")

    def test_data_has_subtitle_paths(self):
        path = self._make_dummy_file("movie.mp4")
        handler = MediaHandler(path)
        result = handler.get_preview()
        self.assertIn("subtitle_paths", result["data"])
        self.assertIsInstance(result["data"]["subtitle_paths"], list)

    def test_webm_format(self):
        path = self._make_dummy_file("clip.webm")
        handler = MediaHandler(path)
        result = handler.get_preview()
        self.assertEqual(result["data"]["format"], "WebM")
        self.assertEqual(result["data"]["media_type"], "video")

    def test_flac_format(self):
        path = self._make_dummy_file("album.flac")
        handler = MediaHandler(path)
        result = handler.get_preview()
        self.assertEqual(result["data"]["format"], "FLAC")

    def test_large_file_flag(self):
        """验证 large_file 字段存在"""
        path = self._make_dummy_file("small.mp3")
        handler = MediaHandler(path)
        result = handler.get_preview()
        self.assertIn("large_file", result["data"])
        self.assertFalse(result["data"]["large_file"])


class TestMediaHandlerGetMime(unittest.TestCase):
    """测试 get_mime 返回正确的 MIME 类型"""

    def test_mp4_mime(self):
        h = MediaHandler("/x/test.mp4")
        self.assertEqual(h.get_mime(), "video/mp4")

    def test_mkv_mime(self):
        h = MediaHandler("/x/test.mkv")
        self.assertEqual(h.get_mime(), "video/x-matroska")

    def test_mp3_mime(self):
        h = MediaHandler("/x/test.mp3")
        self.assertEqual(h.get_mime(), "audio/mpeg")

    def test_wav_mime(self):
        h = MediaHandler("/x/test.wav")
        self.assertEqual(h.get_mime(), "audio/wav")

    def test_flac_mime(self):
        h = MediaHandler("/x/test.flac")
        self.assertEqual(h.get_mime(), "audio/flac")

    def test_unknown_fallback(self):
        # 直接创建一个不在理论上能被 can_handle 的扩展名的情况
        h = MediaHandler("/x/test")
        self.assertEqual(h.get_mime(), "application/octet-stream")


class TestMediaHandlerSubtitleScan(unittest.TestCase):
    """测试字幕扫描功能"""

    def test_scan_finds_srt(self):
        tmp = tempfile.mkdtemp()
        # 创建视频文件 + 同名 srt
        video_path = os.path.join(tmp, "movie.mp4")
        srt_path = os.path.join(tmp, "movie.srt")
        with open(video_path, "wb") as f:
            f.write(b"")
        with open(srt_path, "wb") as f:
            f.write(b"1\n00:00:01,000 --> 00:00:02,000\nHello\n")

        handler = MediaHandler(video_path)
        subs = handler._scan_subtitles()
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0]["format"], "SRT")

    def test_scan_finds_ass(self):
        tmp = tempfile.mkdtemp()
        video_path = os.path.join(tmp, "episode.mkv")
        ass_path = os.path.join(tmp, "episode.ass")
        with open(video_path, "wb") as f:
            f.write(b"")
        with open(ass_path, "wb") as f:
            f.write(b"[Script Info]\n")

        handler = MediaHandler(video_path)
        subs = handler._scan_subtitles()
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0]["format"], "ASS")

    def test_scan_no_subtitles(self):
        tmp = tempfile.mkdtemp()
        video_path = os.path.join(tmp, "lonely.mp4")
        with open(video_path, "wb") as f:
            f.write(b"")

        handler = MediaHandler(video_path)
        subs = handler._scan_subtitles()
        self.assertEqual(len(subs), 0)


class TestMediaHandlerEdit(unittest.TestCase):
    """确认不支持编辑"""

    def test_get_edit_returns_none(self):
        h = MediaHandler("/x/test.mp4")
        self.assertIsNone(h.get_edit())

    def test_supports_editing_false(self):
        h = MediaHandler("/x/test.mp3")
        self.assertFalse(h.supports_editing())


class TestMimeMapCompleteness(unittest.TestCase):
    """确保每个扩展名都有对应的 MIME 映射"""

    def test_all_video_extensions_have_mime(self):
        for ext in VIDEO_EXTENSIONS:
            self.assertIn(ext, MIME_MAP, f"Missing MIME for video ext: {ext}")
            self.assertIn(ext, FORMAT_MAP, f"Missing format for video ext: {ext}")

    def test_all_audio_extensions_have_mime(self):
        for ext in AUDIO_EXTENSIONS:
            self.assertIn(ext, MIME_MAP, f"Missing MIME for audio ext: {ext}")
            self.assertIn(ext, FORMAT_MAP, f"Missing format for audio ext: {ext}")


if __name__ == "__main__":
    unittest.main()
