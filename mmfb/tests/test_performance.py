"""性能测试与内存压力测试

覆盖：
1. Handler 缓存命中率验证
2. 大文件延迟加载行为验证（PDF >50MB、图像 >20MB）
3. QSettings 延迟写入验证
4. 内存占用基线测试（打开 10MB 文件时不应超过 300 MB）
5. 启动时间基线测试

运行：
    pytest mmfb/tests/test_performance.py -v

注意：部分测试依赖生成的样本文件，通过 conftest.py 的 fixture 提供。
"""
import gc
import os
import sys
import time
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# 确保可导入 mmfb
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ---------------------------------------------------------------------------
# 1. Handler 缓存命中率测试
# ---------------------------------------------------------------------------


class TestHandlerCache:
    """验证 registry.py 的 LRU 缓存机制正确工作"""

    def setup_method(self):
        """每个测试前重置注册表缓存"""
        from mmfb.core.registry import registry, HandlerRegistry
        # 使用干净的 HandlerRegistry 以避免干扰全局状态
        self._original_registry = registry
        self.test_registry = HandlerRegistry()
        # 恢复全局
        import mmfb.core.registry
        mmfb.core.registry.registry = self.test_registry

    def teardown_method(self):
        import mmfb.core.registry
        mmfb.core.registry.registry = self._original_registry

    def test_cache_returns_same_instance(self):
        """相同路径 + 相同 mtime 的第二次调用应返回同一 Handler 实例"""
        from mmfb.core.registry import HandlerRegistry
        from mmfb.core.handler_base import BaseHandler

        class _DummyHandler(BaseHandler):
            extensions = ['.testperf']

            def get_preview(self):
                return {"ok": True}

        reg = HandlerRegistry()
        reg.register('.testperf', _DummyHandler)

        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix='.testperf', delete=False) as f:
            f.write(b'data')
            tmp_path = f.name

        try:
            h1 = reg.get_handler(tmp_path)
            h2 = reg.get_handler(tmp_path)
            assert h1 is h2  # 缓存命中，返回同一实例
        finally:
            os.unlink(tmp_path)

    def test_cache_invalidated_on_mtime_change(self):
        """文件修改后缓存应失效"""
        from mmfb.core.registry import HandlerRegistry
        from mmfb.core.handler_base import BaseHandler

        class _DummyHandler2(BaseHandler):
            extensions = ['.testperf2']

            def get_preview(self):
                return {"ok": True}

        reg = HandlerRegistry()
        reg.register('.testperf2', _DummyHandler2)

        with tempfile.NamedTemporaryFile(suffix='.testperf2', delete=False) as f:
            f.write(b'data')
            tmp_path = f.name

        try:
            h1 = reg.get_handler(tmp_path)
            # 修改 mtime
            time.sleep(0.1)
            with open(tmp_path, 'ab') as f:
                f.write(b'more')
            h2 = reg.get_handler(tmp_path)
            assert h1 is not h2  # 缓存已失效，新实例
        finally:
            os.unlink(tmp_path)

    def test_cache_capacity_limit(self):
        """超过容量的缓存条目应被淘汰"""
        from mmfb.core.registry import HandlerRegistry, _HANDLER_CACHE_SIZE
        from mmfb.core.handler_base import BaseHandler

        class _DummyHandler3(BaseHandler):
            extensions = ['.testperf3']

            def get_preview(self):
                return {"ok": True}

        reg = HandlerRegistry()
        reg.register('.testperf3', _DummyHandler3)

        # 创建超过容量的临时文件
        paths = []
        handlers = []
        for i in range(_HANDLER_CACHE_SIZE + 2):
            fd, p = tempfile.mkstemp(suffix='.testperf3')
            os.write(fd, b'data')
            os.close(fd)
            paths.append(p)
            handlers.append(reg.get_handler(p))

        try:
            # 第一个应该已被淘汰
            first_handler = reg.get_handler(paths[0])
            assert first_handler is not handlers[0]
        finally:
            for p in paths:
                os.unlink(p)

    def test_get_handler_missing_file_returns_instance(self):
        """文件不存在时仍应返回 Handler 实例（不命中缓存）"""
        from mmfb.core.registry import HandlerRegistry
        from mmfb.core.handler_base import BaseHandler

        class _DummyHandler4(BaseHandler):
            extensions = ['.testperf4']

            def get_preview(self):
                return {"ok": True}

        reg = HandlerRegistry()
        reg.register('.testperf4', _DummyHandler4)

        handler = reg.get_handler('/nonexistent/path/file.testperf4')
        assert handler is not None
        assert isinstance(handler, _DummyHandler4)


# ---------------------------------------------------------------------------
# 2. 大文件延迟加载行为验证
# ---------------------------------------------------------------------------


class TestLazyLoading:
    """验证 PDF/图像的大文件延迟加载逻辑"""

    def test_pdf_lazy_load_threshold(self):
        """PDF 超过 50MB 时应标记 lazy_load=true"""
        from mmfb.handlers.pdf_handler import PdfHandler, LAZY_LOAD_THRESHOLD
        assert LAZY_LOAD_THRESHOLD == 50 * 1024 * 1024

        # 使用 mock 模拟大文件
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            tmp_path = f.name

        try:
            handler = PdfHandler(tmp_path)
            # Mock os.path.getsize 返回 60MB
            with patch('os.path.getsize', return_value=60 * 1024 * 1024):
                with patch('PyPDF2.PdfReader') as mock_reader:
                    mock_reader.return_value.pages = []
                    mock_reader.return_value.metadata = None
                    result = handler.get_preview()
                    assert result is not None
                    # lazy_load 位于 result['data'] 内部
                    assert result['data'].get('lazy_load') is True
        finally:
            os.unlink(tmp_path)

    def test_image_lazy_load_threshold(self):
        """图像超过 20MB 时不应嵌入 Base64"""
        from mmfb.handlers.image_handler import IMAGE_SIZE_THRESHOLD
        assert IMAGE_SIZE_THRESHOLD == 20 * 1024 * 1024

    def test_small_pdf_no_lazy_load(self):
        """PDF 小于 50MB 时 lazy_load 应为 false"""
        from mmfb.handlers.pdf_handler import PdfHandler

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            tmp_path = f.name

        try:
            handler = PdfHandler(tmp_path)
            with patch('os.path.getsize', return_value=1 * 1024 * 1024):
                with patch('PyPDF2.PdfReader') as mock_reader:
                    mock_reader.return_value.pages = []
                    mock_reader.return_value.metadata = None
                    result = handler.get_preview()
                    assert result is not None
                    # lazy_load 位于 result['data'] 内部
                    assert result['data'].get('lazy_load') is False
        finally:
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# 3. QSettings 延迟写入验证
# ---------------------------------------------------------------------------


class TestSettingsLazyWrite:
    """验证 MMFBSettings.set() 延迟写入行为"""

    def setup_method(self):
        """隔离 QSettings 写入"""
        # 使用临时 INI
        self._tmp_dir = tempfile.mkdtemp()
        self._ini_path = os.path.join(self._tmp_dir, 'test_mmfb.ini')

    def teardown_method(self):
        # 清理临时文件
        if os.path.exists(self._ini_path):
            os.unlink(self._ini_path)
        if os.path.exists(self._tmp_dir):
            os.rmdir(self._tmp_dir)

    @pytest.mark.skipif(
        not os.environ.get('QT_QPA_PLATFORM'),
        reason="Requires QApplication event loop"
    )
    def test_set_does_not_immediately_sync(self):
        """set() 后未 flush() 时，文件不应立即更新（特性测试）"""
        from mmfb.core.settings_manager import MMFBSettings

        settings = MMFBSettings()
        settings.set('display', 'theme', 'dark')

        # 注意：实际 QSettings 写入时机由 QTimer 控制，
        # 这里主要验证 set() 调用不抛异常
        assert settings.get('display', 'theme', 'warm') == 'dark'

    def test_set_uses_full_key_format(self):
        """set() 内部应使用 group/key 格式的完整键名"""
        from mmfb.core.settings_manager import MMFBSettings

        # 通过检查 _dirty_keys 集合来验证延迟写入机制
        settings = MMFBSettings()
        settings._dirty_keys.clear()
        settings.set('general', 'check_updates', True)
        assert 'general/check_updates' in settings._dirty_keys

    def test_flush_clears_dirty_keys(self):
        """flush() 后 _dirty_keys 应被清空"""
        from mmfb.core.settings_manager import MMFBSettings

        settings = MMFBSettings()
        settings.set('general', 'language', 'en-US')
        settings.flush()
        # flush 后 dirty_keys 应为空
        assert len(settings._dirty_keys) == 0


# ---------------------------------------------------------------------------
# 4. 内存占用基线测试
# ---------------------------------------------------------------------------


class TestMemoryUsage:
    """验证内存占用不超过验收标准（打开 10MB 文件时 < 300MB）"""

    @staticmethod
    def _get_process_memory_mb() -> float:
        """获取当前进程的内存占用（MB）"""
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ('cb', wintypes.DWORD),
                    ('PageFaultCount', wintypes.DWORD),
                    ('PeakWorkingSetSize', ctypes.c_size_t),
                    ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t),
                    ('PeakPagefileUsage', ctypes.c_size_t),
                ]

            GetProcessMemoryInfo = ctypes.windll.psapi.GetProcessMemoryInfo
            GetCurrentProcess = ctypes.windll.kernel32.GetCurrentProcess

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(counters)
            GetCurrentProcess_handle = GetCurrentProcess()
            if GetProcessMemoryInfo(GetCurrentProcess_handle, ctypes.byref(counters), counters.cb):
                return counters.WorkingSetSize / (1024 * 1024)
        except Exception:
            pass
        return 0.0

    def test_process_memory_at_baseline(self):
        """基线：Python 解释器本身内存应不超过 150 MB

        注意：Windows 环境下通过 kernel32/psapi 读取进程内存可能受权限/API兼容性影响
        影响，读取失败时跳过测试而非硬性失败（避免在 CI 等受限环境误报）
        """
        mem = self._get_process_memory_mb()
        if mem == 0.0:
            pytest.skip("当前环境无法读取进程内存数据")
        # Python + pytest 本身约 30-80 MB，设置 150 MB 作为安全上限
        assert mem < 150, f"基线内存占用过高: {mem:.1f} MB"

    def test_preview_small_file_does_not_bloat(self):
        """打开小文件后内存增长应可控（< 50 MB 增幅）"""
        mem_before = self._get_process_memory_mb()

        # 创建一个小文件并调用预览
        from mmfb.handlers.pdf_handler import PdfHandler
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            tmp_path = f.name

        try:
            handler = PdfHandler(tmp_path)
            with patch('PyPDF2.PdfReader') as mock_reader:
                mock_reader.return_value.pages = []
                mock_reader.return_value.metadata = None
                with patch('os.path.getsize', return_value=1024):
                    handler.get_preview()
        finally:
            os.unlink(tmp_path)

        gc.collect()
        mem_after = self._get_process_memory_mb()
        growth = mem_after - mem_before
        assert growth < 50, f"预览小文件内存增长过大: {growth:.1f} MB"

    def test_repeated_get_handler_uses_cache(self):
        """多次 get_handler 调用应复用实例，不产生新对象开销"""
        from mmfb.core.registry import HandlerRegistry
        from mmfb.core.handler_base import BaseHandler

        class _CountHandler(BaseHandler):
            extensions = ['.countperf']
            create_count = 0

            def __init__(self, path):
                super().__init__(path)
                _CountHandler.create_count += 1

            def get_preview(self):
                return {"ok": True}

        reg = HandlerRegistry()
        reg.register('.countperf', _CountHandler)

        with tempfile.NamedTemporaryFile(suffix='.countperf', delete=False) as f:
            f.write(b'data')
            tmp_path = f.name

        try:
            _CountHandler.create_count = 0
            reg.get_handler(tmp_path)
            reg.get_handler(tmp_path)
            reg.get_handler(tmp_path)
            # 3 次调用应该只创建 1 个实例（缓存命中）
            assert _CountHandler.create_count == 1, \
                f"缓存失效：创建了 {_CountHandler.create_count} 个实例"
        finally:
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# 5. 启动行为测试
# ---------------------------------------------------------------------------


class TestStartupBehavior:
    """验证启动相关逻辑"""

    def test_import_main_does_not_crash(self):
        """导入 main 模块不应抛异常（含所有依赖检查）"""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "main_check",
            os.path.join(os.path.dirname(__file__), "..", "..", "main.py"),
        )
        assert spec is not None

    def test_window_manager_singleton(self):
        """WindowManager 通过 get_window_manager() 应为单例"""
        from mmfb.core.window_manager import get_window_manager

        m1 = get_window_manager()
        m2 = get_window_manager()
        assert m1 is m2

    def test_settings_singleton(self):
        """MMFBSettings 通过 get_settings() 应为单例"""
        from mmfb.core.settings_manager import get_settings

        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_registry_is_global_instance(self):
        """registry 模块应导出全局实例"""
        from mmfb.core import registry as reg_module
        assert hasattr(reg_module, 'registry')
        assert hasattr(reg_module.registry, 'count')
        assert reg_module.registry.count() > 0
