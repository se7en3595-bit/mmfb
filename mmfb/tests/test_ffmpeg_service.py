"""ffmpeg_service.py 单元测试

覆盖任务：实现 FFmpeg 调用或 WASM 转码兜底
- check_ffmpeg / check_ffprobe 探测
- get_media_info 元数据读取
- FFmpegService 单例接口
- 进度正则解析
- 错误处理路径
"""
import os
import re
import sys
import unittest
from unittest import mock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from mmfb.services.ffmpeg_service import (
    FFmpegService,
    check_ffmpeg,
    check_ffprobe,
    get_media_info,
    convert_video,
    _RE_PROGRESS,
    _RE_DURATION,
    _probe_duration,
    _run,
)


class TestProgressRegex(unittest.TestCase):
    """进度行正则表达式测试"""

    def test_parse_standard_progress_line(self):
        line = "frame=  123 fps= 25 q=28.0 size=    256kB time=00:00:05.12 bitrate= 409.6kbits/s speed=1.02x"
        m = _RE_PROGRESS.search(line)
        self.assertIsNotNone(m)
        self.assertEqual(int(m.group(1)), 123)
        self.assertEqual(float(m.group(2)), 25.0)
        self.assertEqual(int(m.group(5)), 0)
        self.assertEqual(int(m.group(6)), 0)
        # group(7) 只匹配整数秒部分 (\d{2})，小数部分在下一个未命名组
        self.assertEqual(int(m.group(7)), 5)

    def test_parse_long_duration(self):
        line = "frame= 9999 fps=30 q=0.0 size=  10240kB time=01:30:45.67 bitrate= 256.0kbits/s speed=1.5x"
        m = _RE_PROGRESS.search(line)
        self.assertIsNotNone(m)
        self.assertEqual(int(m.group(5)), 1)
        self.assertEqual(int(m.group(6)), 30)
        self.assertEqual(int(m.group(7)), 45)

    def test_non_matching_line(self):
        line = "Too many open files"
        m = _RE_PROGRESS.search(line)
        self.assertIsNone(m)

    def test_duration_regex(self):
        line = "Duration: 00:05:23.12, start: 0.000000"
        m = _RE_DURATION.search(line)
        self.assertIsNotNone(m)
        self.assertEqual(int(m.group(1)), 0)
        self.assertEqual(int(m.group(2)), 5)
        self.assertAlmostEqual(float(m.group(3)), 23.12)


class TestCheckFfmpeg(unittest.TestCase):
    """ffmpeg / ffprobe 探测测试"""

    def test_check_ffmpeg_not_found(self):
        """ffmpeg 不在 PATH 时返回 ok=False"""
        with mock.patch("mmfb.services.ffmpeg_service.shutil.which", return_value=None):
            r = check_ffmpeg()
            self.assertFalse(r["ok"])
            self.assertIsNone(r["path"])
            self.assertIn("not found", r["error"])

    def test_check_ffprobe_not_found(self):
        """ffprobe 不在 PATH 时返回 ok=False"""
        with mock.patch("mmfb.services.ffmpeg_service.shutil.which", return_value=None):
            r = check_ffprobe()
            self.assertFalse(r["ok"])
            self.assertIsNone(r["path"])
            self.assertIn("not found", r["error"])

    def test_check_ffmpeg_exception(self):
        """ffmpeg 命令执行异常时返回 ok=False"""
        with mock.patch("mmfb.services.ffmpeg_service.shutil.which", return_value="/usr/bin/ffmpeg"):
            with mock.patch("mmfb.services.ffmpeg_service._run", side_effect=Exception("permission denied")):
                r = check_ffmpeg()
                self.assertFalse(r["ok"])
                self.assertEqual(r["path"], "/usr/bin/ffmpeg")
                self.assertIn("permission denied", r["error"])


class TestGetMediaInfo(unittest.TestCase):
    """get_media_info 元数据读取测试"""

    def test_nonexistent_file(self):
        r = get_media_info("/nonexistent/path/video.mp4")
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "file not found")

    def test_ffprobe_not_available(self):
        """ffprobe 不可用时返回错误"""
        with mock.patch("mmfb.services.ffmpeg_service.check_ffprobe", return_value={"ok": False, "error": "not found"}):
            with mock.patch("os.path.isfile", return_value=True):
                r = get_media_info("/fake/path.mp4")
                self.assertFalse(r["ok"])
                self.assertIn("not found", r["error"])


class TestFFmpegService(unittest.TestCase):
    """FFmpegService 单例类测试"""

    def setUp(self):
        self.service = FFmpegService()
        self.service.reset_cache()

    def test_is_available_when_not_installed(self):
        with mock.patch("mmfb.services.ffmpeg_service.check_ffmpeg", return_value={"ok": False}):
            self.assertFalse(self.service.is_available)

    def test_info_when_not_installed(self):
        with mock.patch("mmfb.services.ffmpeg_service.check_ffmpeg", return_value={"ok": False, "error": "missing"}):
            info = self.service.info
            self.assertFalse(info["ok"])

    def test_probe_delegates_to_get_media_info(self):
        with mock.patch("mmfb.services.ffmpeg_service.get_media_info") as mock_probe:
            mock_probe.return_value = {"ok": True, "streams": [], "format": {}}
            r = self.service.probe("/fake.mp4")
            self.assertTrue(r["ok"])
            mock_probe.assert_called_once_with("/fake.mp4")

    def test_reset_cache(self):
        self.service._cache["test"] = "value"
        self.service.reset_cache()
        self.assertNotIn("test", self.service._cache)


class TestConvertVideoErrors(unittest.TestCase):
    """convert_video 错误路径测试"""

    def test_input_not_found(self):
        with self.assertRaises(FileNotFoundError):
            convert_video("/nonexistent.mp4", "/tmp/out.mp4")

    def test_ffmpeg_not_available(self):
        with mock.patch("mmfb.services.ffmpeg_service.check_ffmpeg", return_value={"ok": False, "error": "not found"}):
            with mock.patch("os.path.isfile", return_value=True):
                with self.assertRaises(FileNotFoundError):
                    convert_video("/fake.mp4", "/tmp/out.mp4")


class TestProbeDuration(unittest.TestCase):
    """_probe_duration 辅助函数测试"""

    def test_returns_zero_for_nonexistent(self):
        """不存在文件返回 0"""
        result = _probe_duration("/nonexistent.mp4")
        self.assertEqual(result, 0.0)

    def test_returns_zero_on_ffprobe_error(self):
        """ffprobe 失败返回 0"""
        with mock.patch("mmfb.services.ffmpeg_service._run", return_value=mock.Mock(returncode=1, stdout="")):
            result = _probe_duration("/fake.mp4")
            self.assertEqual(result, 0.0)


class TestRunHelper(unittest.TestCase):
    """_run 辅助函数测试"""

    def test_hidden_console_windows(self):
        """Windows 下应设置 STARTF_USESHOWWINDOW"""
        with mock.patch("sys.platform", "win32"):
            with mock.patch("subprocess.run") as mock_run:
                mock_run.return_value = mock.Mock(stdout="ffmpeg version 5.0", stderr="")
                _run(["ffmpeg", "-version"])
                mock_run.assert_called_once()
                kwargs = mock_run.call_args[1]
                self.assertIsNotNone(kwargs.get("startupinfo"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
