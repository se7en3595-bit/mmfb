"""ArchiveHandler 单元测试

测试范围：
- 扩展名匹配 (单层后缀 .zip/.tar/.tgz, 复合后缀 .tar.gz/.tar.bz2/.tar.xz)
- 大小写不敏感
- ZIP 树形解析
- TAR 树形解析
- 内存解压接口
- Zip Slip 防护
- 错误处理 (文件不存在/空文件/损坏文件)
"""
import os
import tarfile
import tempfile
import zipfile

import pytest

from mmfb.handlers.archive_handler import (
    ArchiveHandler,
    extract_member_to_memory,
    _safe_member_name,
    _get_extension,
    _format_size,
)


# ========== 辅助函数 ==========

def _make_zip(path: str, entries: dict, password: str = ""):
    """创建测试 ZIP 文件

    entries: { "path/in/zip.txt": b"content", "dir/": None }
    """
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries.items():
            if content is None:
                # 目录
                zf.writestr(name, "")
            else:
                zf.writestr(name, content)


def _make_tar(path: str, entries: dict, mode: str = "w"):
    """创建测试 TAR 文件

    entries: { "path/in/tar.txt": b"content", "dir/": None }
    """
    with tarfile.open(path, mode) as tf:
        import io
        for name, content in entries.items():
            if content is None:
                # 目录
                info = tarfile.TarInfo(name=name)
                info.type = tarfile.DIRTYPE
                tf.addfile(info)
            else:
                info = tarfile.TarInfo(name=name)
                info.size = len(content)
                tf.addfile(info, io.BytesIO(content))


class TestCanHandle:
    """扩展名匹配测试"""

    @pytest.mark.parametrize("path", [
        "test.zip", "test.ZIP", "test.Zip",
    ])
    def test_zip(self, path):
        assert ArchiveHandler.can_handle(path)

    @pytest.mark.parametrize("path", [
        "test.tar", "test.TAR",
        "test.tar.gz", "test.TAR.GZ", "test.Tar.Gz",
        "test.tgz", "test.TGZ",
        "test.tar.bz2", "test.TAR.BZ2",
        "test.tar.xz", "test.TAR.XZ",
    ])
    def test_tar_variants(self, path):
        assert ArchiveHandler.can_handle(path)

    @pytest.mark.parametrize("path", [
        "test.pdf", "test.txt", "test.exe", "test",
        "test.gz",   # 单独的 .gz 不是压缩包
    ])
    def test_not_archive(self, path):
        assert not ArchiveHandler.can_handle(path)


class TestSafeMemberName:
    """Zip Slip 防护测试"""

    def test_valid_names(self):
        assert _safe_member_name("file.txt") == "file.txt"
        assert _safe_member_name("dir/file.txt") == "dir/file.txt"
        assert _safe_member_name("a/b/c.txt") == "a/b/c.txt"

    def test_slip_with_dotdot(self):
        assert _safe_member_name("../etc/passwd") is None
        assert _safe_member_name("foo/../../etc/passwd") is None

    def test_absolute_path(self):
        assert _safe_member_name("/etc/passwd") is None
        assert _safe_member_name("\\windows\\system32") is None

    def test_empty_name(self):
        assert _safe_member_name("") is None

    def test_normalizes_backslash(self):
        assert _safe_member_name("dir\\file.txt") == "dir/file.txt"


class TestGetExtension:
    """扩展名提取"""

    def test_simple(self):
        assert _get_extension("file.txt") == "txt"
        assert _get_extension("archive.zip") == "zip"

    def test_compound(self):
        assert _get_extension("archive.tar.gz") == "tar.gz"
        assert _get_extension("archive.tar.bz2") == "tar.bz2"


class TestFormatSize:
    """大小格式化"""

    def test_bytes(self):
        assert "B" in _format_size(100)

    def test_kb(self):
        result = _format_size(2048)
        assert "KB" in result

    def test_mb(self):
        result = _format_size(5 * 1024 * 1024)
        assert "MB" in result


class TestZipPreview:
    """ZIP 预览测试"""

    def test_simple_zip(self, tmp_path):
        zip_path = str(tmp_path / "test.zip")
        _make_zip(zip_path, {
            "readme.txt": b"Hello World",
            "src/": None,
            "src/main.py": b"print('hello')",
        })

        handler = ArchiveHandler(zip_path)
        result = handler.get_preview()

        assert result is not None
        assert "error" not in result
        data = result["data"]
        assert data["archive_type"] == "zip"
        assert data["total_files"] == 2
        assert data["total_dirs"] == 1
        assert data["is_encrypted"] is False
        assert data["tree"]["name"] == "test.zip"

    def test_empty_zip(self, tmp_path):
        zip_path = str(tmp_path / "empty.zip")
        _make_zip(zip_path, {})

        handler = ArchiveHandler(zip_path)
        result = handler.get_preview()

        assert result is not None
        data = result["data"]
        assert data["total_files"] == 0
        assert data["total_dirs"] == 0

    def test_file_not_found(self):
        handler = ArchiveHandler("/nonexistent/path/file.zip")
        result = handler.get_preview()

        assert result is not None
        assert "error" in result

    def test_deep_nesting(self, tmp_path):
        zip_path = str(tmp_path / "deep.zip")
        _make_zip(zip_path, {
            "a/b/c/d/file.txt": b"deep content",
        })

        handler = ArchiveHandler(zip_path)
        result = handler.get_preview()

        assert result is not None
        data = result["data"]
        assert data["total_files"] == 1
        # 无显式目录项（不以 / 结尾），目录从路径隐式推断
        assert data["total_dirs"] == 0

    def test_slip_protection(self, tmp_path):
        """测试恶意 ZIP 的 Zip Slip 成员被过滤"""
        zip_path = str(tmp_path / "slip.zip")
        _make_zip(zip_path, {
            "safe.txt": b"safe",
            "../../../etc/passwd": b"malicious",
        })

        handler = ArchiveHandler(zip_path)
        result = handler.get_preview()

        assert result is not None
        data = result["data"]
        # 只统计 safe.txt，恶意成员被过滤
        assert data["total_files"] == 1


class TestTarPreview:
    """TAR 预览测试"""

    def test_simple_tar(self, tmp_path):
        tar_path = str(tmp_path / "test.tar")
        _make_tar(tar_path, {
            "readme.txt": b"Hello TAR",
        })

        handler = ArchiveHandler(tar_path)
        result = handler.get_preview()

        assert result is not None
        data = result["data"]
        assert data["archive_type"] == "tar"
        assert data["total_files"] == 1

    def test_tar_gz(self, tmp_path):
        tar_path = str(tmp_path / "test.tar.gz")
        _make_tar(tar_path, {
            "file1.txt": b"content1",
            "file2.txt": b"content2",
        }, mode="w:gz")

        handler = ArchiveHandler(tar_path)
        result = handler.get_preview()

        assert result is not None
        data = result["data"]
        assert data["total_files"] == 2


class TestExtractMember:
    """内存解压测试"""

    def test_extract_text_file(self, tmp_path):
        zip_path = str(tmp_path / "test.zip")
        _make_zip(zip_path, {
            "hello.txt": b"Hello from ZIP",
        })

        result = extract_member_to_memory(zip_path, "hello.txt")
        assert result["ok"] is True
        assert result["size"] == len(b"Hello from ZIP")
        assert "text" in result["mime"]

    def test_member_not_found(self, tmp_path):
        zip_path = str(tmp_path / "test.zip")
        _make_zip(zip_path, {"a.txt": b"x"})

        result = extract_member_to_memory(zip_path, "nonexistent.txt")
        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_archive_not_found(self):
        result = extract_member_to_memory("/nonexistent/file.zip", "a.txt")
        assert result["ok"] is False

    def test_extract_tar_member(self, tmp_path):
        tar_path = str(tmp_path / "test.tar")
        _make_tar(tar_path, {"data.txt": b"TAR content"})

        result = extract_member_to_memory(tar_path, "data.txt")
        assert result["ok"] is True
        assert result["size"] == len(b"TAR content")


class TestRegistryMatch:
    """注册表匹配测试"""

    def test_zip_match(self):
        from mmfb.core.registry import HandlerRegistry
        from mmfb.handlers.archive_handler import ArchiveHandler

        reg = HandlerRegistry()
        reg.register_class(ArchiveHandler)

        handler = reg.get_handler("test.zip")
        assert handler is not None
        assert isinstance(handler, ArchiveHandler)

    def test_tar_gz_match(self):
        from mmfb.core.registry import HandlerRegistry
        from mmfb.handlers.archive_handler import ArchiveHandler

        reg = HandlerRegistry()
        reg.register_class(ArchiveHandler)

        handler = reg.get_handler("archive.tar.gz")
        assert handler is not None
        assert isinstance(handler, ArchiveHandler)
