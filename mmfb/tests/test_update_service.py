"""测试 mmfb.services.update_service"""
import os
import sys
import json
import tempfile
import unittest
from unittest import mock


# ---------- Mock 对象（支持 context manager 协议） ----------

class _MockResponse:
    """Minimal mock for urllib.response（支持 with 语句）"""
    def __init__(self, body_bytes):
        self._body = body_bytes

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._body


class TestParseVersion(unittest.TestCase):
    """测试 parse_version"""

    def test_standard(self):
        from mmfb.services.update_service import parse_version
        self.assertEqual(parse_version("v1.2.3"), (1, 2, 3))

    def test_no_v_prefix(self):
        from mmfb.services.update_service import parse_version
        self.assertEqual(parse_version("2.0.1"), (2, 0, 1))

    def test_with_prerelease(self):
        from mmfb.services.update_service import parse_version
        self.assertEqual(parse_version("1.2.3-beta"), (1, 2, 3))

    def test_invalid(self):
        from mmfb.services.update_service import parse_version
        self.assertIsNone(parse_version("latest"))
        self.assertIsNone(parse_version("nightly"))
        self.assertIsNone(parse_version(""))
        self.assertIsNone(parse_version("abc"))


class TestIsNewerVersion(unittest.TestCase):
    """测试 is_newer_version"""

    def test_newer_patch(self):
        from mmfb.services.update_service import is_newer_version
        self.assertTrue(is_newer_version("v1.0.1", "1.0.0"))

    def test_newer_minor(self):
        from mmfb.services.update_service import is_newer_version
        self.assertTrue(is_newer_version("v1.1.0", "1.0.5"))

    def test_newer_major(self):
        from mmfb.services.update_service import is_newer_version
        self.assertTrue(is_newer_version("v2.0.0", "1.9.9"))

    def test_same_version(self):
        from mmfb.services.update_service import is_newer_version
        self.assertFalse(is_newer_version("v1.0.0", "1.0.0"))

    def test_older_not_newer(self):
        from mmfb.services.update_service import is_newer_version
        self.assertFalse(is_newer_version("v0.9.0", "1.0.0"))


class TestCheckForUpdates(unittest.TestCase):
    """测试 check_for_updates（模拟 HTTP）"""

    def _make_http_response(self, data):
        """构造模拟的 HTTP 响应（支持 context manager 协议）"""
        body = json.dumps(data).encode('utf-8')
        return _MockResponse(body)

    def test_no_update_if_current_is_newer(self):
        """当前版本与远程相同时，返回 None"""
        from mmfb.services import update_service
        remote = {
            "tag_name": "v1.0.0",
            "name": "MMFB 1.0.0",
            "body": "release",
            "assets": [],
        }
        response = self._make_http_response(remote)
        with mock.patch.object(update_service.urllib.request, "urlopen",
                                return_value=response):
            result = update_service.check_for_updates()

        self.assertIsNone(result)

    def test_has_update(self):
        """当远程版本较新时，返回更新数据"""
        from mmfb.services import update_service
        remote = {
            "tag_name": "v1.2.0",
            "name": "MMFB 1.2.0",
            "body": "New features",
            "html_url": "https://example.com/release/1.2.0",
            "assets": [
                {
                    "name": "MMFB-Setup-1.2.0.exe",
                    "browser_download_url": "https://example.com/setup.exe",
                    "size": 52428800,
                }
            ],
        }
        response = self._make_http_response(remote)
        with mock.patch.object(update_service.urllib.request, "urlopen",
                                return_value=response):
            result = update_service.check_for_updates()

        self.assertIsNotNone(result)
        # available 字段由 bridge 层添加，此处只验证 service 层返回的数据
        self.assertEqual(result["tag"], "v1.2.0")
        self.assertIn("asset", result)
        self.assertEqual(result["asset"]["name"], "MMFB-Setup-1.2.0.exe")

    def test_handles_network_error(self):
        """网络异常时静默返回 None"""
        from mmfb.services import update_service
        import urllib.error
        with mock.patch.object(
            update_service.urllib.request, "urlopen",
            side_effect=urllib.error.URLError("timeout"),
        ):
            result = update_service.check_for_updates()
        self.assertIsNone(result)

    def test_handles_invalid_tag(self):
        """远程标签无法解析时返回 None"""
        from mmfb.services import update_service
        remote = {"tag_name": "nightly", "assets": []}
        response = self._make_http_response(remote)
        with mock.patch.object(update_service.urllib.request, "urlopen",
                                return_value=response):
            result = update_service.check_for_updates()
        self.assertIsNone(result)


class TestFindExeAsset(unittest.TestCase):
    """测试 _find_exe_asset"""

    def test_pick_largest_exe(self):
        from mmfb.services.update_service import _find_exe_asset
        assets = [
            {"name": "small.exe", "browser_download_url": "u1", "size": 1000},
            {"name": "MMFB-Setup-1.2.0.exe", "browser_download_url": "u2", "size": 50000},
        ]
        result = _find_exe_asset(assets)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "MMFB-Setup-1.2.0.exe")

    def test_no_exe_returns_none(self):
        from mmfb.services.update_service import _find_exe_asset
        assets = [
            {"name": "source.tar.gz", "browser_download_url": "u1", "size": 5000},
        ]
        result = _find_exe_asset(assets)
        self.assertIsNone(result)


class TestVersionConstants(unittest.TestCase):
    """测试 mmfb.version 导出"""

    def test_version_exists(self):
        from mmfb import version
        self.assertTrue(hasattr(version, "MMFB_VERSION"))
        self.assertTrue(hasattr(version, "MMFB_UPDATE_REPO"))
        # 基本语义校验
        parts = version.MMFB_VERSION.split(".")
        self.assertEqual(len(parts), 3)
        for p in parts:
            self.assertTrue(p.isdigit())


if __name__ == "__main__":
    unittest.main()
