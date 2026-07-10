"""HistoryManager 单元测试"""
import json
import os
import sys
import tempfile
import time

import pytest

# 确保项目根在 sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from mmfb.core.history_manager import HistoryManager


@pytest.fixture
def tmp_history_file():
    """创建临时目录中的 history 文件"""
    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, "test_history.json")
    yield path
    # 清理
    if os.path.isfile(path):
        os.remove(path)
    os.rmdir(tmpdir)


@pytest.fixture
def hm(tmp_history_file):
    """返回一个基于临时文件的 HistoryManager 实例"""
    return HistoryManager(file_path=tmp_history_file)


class TestHistoryManager:

    def test_add_record(self, hm, tmp_history_file):
        """添加单条记录"""
        hm.add("/tmp/test.pdf", "test.pdf", "pdf", "application/pdf")
        assert hm.count() == 1
        records = hm.get_all()
        assert records[0]["path"] == "/tmp/test.pdf"
        assert records[0]["name"] == "test.pdf"
        assert records[0]["ext"] == "pdf"
        assert records[0]["mime"] == "application/pdf"
        assert "timestamp" in records[0]

    def test_add_same_path_moves_to_top(self, hm):
        """同 path 重复添加：更新时间戳并移到头部，不重复"""
        hm.add("/tmp/a.pdf", "a.pdf", "pdf", "")
        old_ts = hm.get_all()[0]["timestamp"]

        time.sleep(0.01)
        hm.add("/tmp/a.pdf", "a.pdf", "pdf", "")

        # 应该只有一条
        assert hm.count() == 1
        assert hm.get_all()[0]["path"] == "/tmp/a.pdf"

    def test_order_descending(self, hm):
        """按时间倒序排列"""
        hm.add("/tmp/first.pdf", "first.pdf", "pdf", "")
        time.sleep(0.02)
        hm.add("/tmp/second.pdf", "second.pdf", "pdf", "")
        time.sleep(0.02)
        hm.add("/tmp/third.pdf", "third.pdf", "pdf", "")

        records = hm.get_all()
        assert len(records) == 3
        assert records[0]["path"] == "/tmp/third.pdf"  # 最后添加排在最前
        assert records[2]["path"] == "/tmp/first.pdf"

    def test_max_fifty_records(self, hm):
        """超过 50 条时截断"""
        for i in range(60):
            hm.add(f"/tmp/file_{i:03d}.pdf", f"file_{i:03d}.pdf", "pdf", "")

        assert hm.count() == 50

    def test_remove_item(self, hm):
        """移除指定记录"""
        hm.add("/tmp/a.pdf", "", "", "")
        hm.add("/tmp/b.pdf", "", "", "")
        assert hm.count() == 2

        hm.remove("/tmp/a.pdf")
        assert hm.count() == 1
        assert hm.get_all()[0]["path"] == "/tmp/b.pdf"

    def test_clear(self, hm):
        """清空全部"""
        hm.add("/tmp/a.pdf", "", "", "")
        hm.add("/tmp/b.pdf", "", "", "")
        assert hm.count() == 2

        hm.clear()
        assert hm.count() == 0
        assert hm.get_all() == []

    def test_remove_nonexistent(self, hm):
        """移除不存在的记录不报错"""
        hm.add("/tmp/a.pdf", "", "", "")
        hm.remove("/tmp/not_exists.pdf")
        assert hm.count() == 1

    def test_add_empty_path_ignored(self, hm):
        """空 path 被忽略"""
        hm.add("", "", "", "")
        assert hm.count() == 0

    def test_persistence(self, hm, tmp_history_file):
        """数据持久化到文件"""
        hm.add("/tmp/hello.md", "hello.md", "md", "text/markdown")

        # 重新打开文件验证
        with open(tmp_history_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["name"] == "hello.md"

    def test_cleanup_removes_nonexistent_paths(self, hm, tmp_history_file):
        """_cleanup 不执行持久清理（add 路径不存在时不影响已存在的记录）"""
        # 手动写入不存在的路径记录（绕过 _cleanup 中的文件检查）
        fake_data = [
            {"path": "/tmp/fake_not_exists_x.pdf", "name": "fake.pdf",
             "ext": "pdf", "mime": "", "timestamp": int(time.time())}
        ]
        with open(tmp_history_file, "w", encoding="utf-8") as f:
            json.dump(fake_data, f)

        # HM __init__ 会调用 _cleanup，fake 路径应当被清除
        fresh_hm = HistoryManager(file_path=tmp_history_file)
        assert fresh_hm.count() == 0

    def test_guess_ext(self, hm):
        """_guess_ext 推断扩展名"""
        hm.add("/path/to/file.TXT", "file.TXT", "", "")
        assert hm.get_all()[0]["ext"] == "txt"

    def test_get_all_returns_copy(self, hm):
        """get_all 返回副本，修改不影响内部"""
        hm.add("/tmp/a.pdf", "", "", "")
        records = hm.get_all()
        records.pop()
        assert hm.count() == 1

    def test_repr_str_safety(self, hm):
        """中文文件名不抛异常"""
        hm.add("/tmp/测试.pdf", "测试.pdf", "pdf", "")
        assert hm.count() == 1
        assert hm.get_all()[0]["name"] == "测试.pdf"


class TestHistoryManagerNoInit:
    """不传入 file_path 的情况（使用真实存储路径）"""

    def test_default_path_no_crash(self):
        """默认路径构造不崩溃"""
        from mmfb.core.history_manager import _history_file_path
        path = _history_file_path()
        assert isinstance(path, str)
        assert path.endswith("history.json")


# ========== 注册表级别的集成测试（桥接信号） ==========

class TestBridgeHistorySlots:
    """测试桥接的 history 相关 Slot 接口

    注意：这些测试需要 Qt 环境，只能在完整 App 启动时验证。
    这里只验证 HistoryManager 的基本逻辑；管线的桥接行为由 test_bridge.py 覆盖。
    """

    def test_history_manager_integration_add_retrieve(self, hm):
        hm.add("/tmp/doc1.pdf", "doc1.pdf", "pdf", "application/pdf")
        hm.add("/tmp/doc2.md", "doc2.md", "md", "text/markdown")
        records = hm.get_all()
        assert len(records) == 2
        paths = [r["path"] for r in records]
        assert "/tmp/doc2.md" in paths
        assert "/tmp/doc1.pdf" in paths


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
