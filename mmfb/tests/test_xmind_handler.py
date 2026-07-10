"""XmindHandler 单元测试

测试范围：
- 扩展名匹配 (.xmind)
- 大小写不敏感
- 预览数据提取（metadata + sheets 树形结构）
- 错误处理（文件不存在/非 XMind 文件）
- 不可编辑标志
"""

import os
import tempfile
import zipfile

import pytest

from mmfb.handlers.xmind_handler import XmindHandler


def _create_minimal_xmind(path: str):
    """创建最小化的 XMind 文件（符合 XMind 8+ 结构）"""
    import json

    # 我们采用简化但有效的 structure（符合 xmind 库的 content.json）
    content = {
        "content": {
            "sheets": [
                {
                    "id": "sheet-1",
                    "title": "Test Canvas",
                    "rootTopic": {
                        "id": "topic-1",
                        "title": "Central Topic",
                        "notes": {"plain": {"content": "This is a note"}},
                        "labels": ["Important", "Todo"],
                        "children": {
                            "attached": [
                                {
                                    "id": "topic-2",
                                    "title": "Child Topic 1",
                                    "labels": ["Done"],
                                    "children": {
                                        "attached": [
                                            {
                                                "id": "topic-3",
                                                "title": "Grandchild Topic",
                                                "notes": {"plain": {"content": "Deeper note"}}
                                            }
                                        ]
                                    }
                                },
                                {
                                    "id": "topic-4",
                                    "title": "Child Topic 2"
                                }
                            ]
                        }
                    }
                }
            ]
        }
    }

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("content.json", json.dumps(content, ensure_ascii=False))


def test_can_handle_by_extension():
    """测试扩展名匹配"""
    assert XmindHandler.can_handle("test.xmind")
    assert XmindHandler.can_handle("file.XMIND")


def test_can_handle_case_insensitive():
    """测试大小写不敏感"""
    assert XmindHandler.can_handle("test.XMind")
    assert XmindHandler.can_handle("test.XMIND")
    assert XmindHandler.can_handle("test.Xmind")


def test_get_preview_success(tmp_path):
    """测试成功预览 XMind 文件"""
    xmind_path = str(tmp_path / "test.xmind")
    _create_minimal_xmind(xmind_path)

    handler = XmindHandler(xmind_path)
    result = handler.get_preview()

    assert result is not None
    assert "error" not in result
    assert result["mime"] == "application/x-xmind"
    assert result["template"] == "xmind"
    assert result["editable"] is False

    data = result["data"]
    assert "metadata" in data
    assert "sheets" in data
    assert data["metadata"]["sheetCount"] == 1
    assert len(data["sheets"]) == 1

    sheet = data["sheets"][0]
    assert sheet["name"] == "Test Canvas"
    root = sheet["rootTopic"]
    assert root["title"] == "Central Topic"
    # 检查子主题数量
    assert len(root["children"]) == 2
    child1 = root["children"][0]
    assert child1["title"] == "Child Topic 1"
    assert "Done" in child1["labels"]


def test_get_preview_missing_file():
    """测试文件不存在"""
    handler = XmindHandler("/nonexistent/file.xmind")
    result = handler.get_preview()
    assert result is not None
    assert "error" in result
    assert "不存在" in result["error"] or "not found" in result["error"].lower()


def test_get_preview_invalid_file(tmp_path):
    """测试非 XMind 文件"""
    invalid_path = str(tmp_path / "bad.xmind")
    with open(invalid_path, "wb") as f:
        f.write(b"This is not a zip file")

    handler = XmindHandler(invalid_path)
    result = handler.get_preview()
    assert result is not None
    assert "error" in result


def test_save_content_not_implemented(tmp_path):
    """测试保存功能未实现"""
    xmind_path = str(tmp_path / "test.xmind")
    _create_minimal_xmind(xmind_path)

    handler = XmindHandler(xmind_path)
    with pytest.raises(NotImplementedError):
        handler.save_content(xmind_path, {})
