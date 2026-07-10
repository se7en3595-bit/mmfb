# XMind 思维导图处理器
# 支持 .xmind 文件解析与树形结构展示

import json
import os
import zipfile
from typing import Any, Dict, List, Optional

from mmfb.core.handler_base import BaseHandler


class XmindHandler(BaseHandler):
    """XMind 思维导图处理器

    XMind 8+ 格式:
    - content.json: 画布与主题数据
    - metadata.json: 文件元数据
    - styles.json: 样式定义

    此 Handler 直接解析 content.json，不依赖 xmind 库。
    """

    # 支持扩展名
    extensions = [".xmind"]

    # 单文件大小上限 (20MB)
    MAX_FILE_SIZE = 20 * 1024 * 1024

    def get_preview(self) -> Optional[Dict[str, Any]]:
        """获取 XMind 预览数据"""
        try:
            # 文件检查
            if not os.path.isfile(self.path):
                raise RuntimeError("文件不存在")

            file_size = os.path.getsize(self.path)
            if file_size > self.MAX_FILE_SIZE:
                raise RuntimeError(f"文件过大({file_size} > {self.MAX_FILE_SIZE})")

            if not zipfile.is_zipfile(self.path):
                raise RuntimeError("无效的 XMind 文件格式（不是 ZIP 容器）")

            # 解析内容
            data = self._parse_xmind(self.path)
            return {
                "mime": "application/x-xmind",
                "template": "xmind",
                "data": data,
                "editable": False
            }
        except Exception as e:
            return {
                "mime": "application/x-xmind",
                "template": "xmind",
                "data": None,
                "editable": False,
                "error": str(e)
            }

    def _parse_xmind(self, file_path: str) -> Dict[str, Any]:
        """解析 XMind ZIP 文件"""
        with zipfile.ZipFile(file_path, "r") as zf:
            # 读取 content.json
            try:
                content_bytes = zf.read("content.json")
            except KeyError:
                raise RuntimeError("XMind 文件缺少 content.json")

            content = json.loads(content_bytes.decode("utf-8"))

            # 提取 sheets
            sheets_data = content.get("content", {}).get("sheets", [])
            sheets = []

            for sheet in sheets_data:
                root_topic = sheet.get("rootTopic", {})
                sheet_entry = {
                    "id": sheet.get("id", ""),
                    "name": sheet.get("title", "未命名画布"),
                    "rootTopic": self._topic_to_dict(root_topic)
                }
                sheets.append(sheet_entry)

            # 元数据
            file_size = os.path.getsize(file_path)
            metadata = {
                "type": "xmind",
                "fileName": os.path.basename(file_path),
                "fileSize": file_size,
                "sheetCount": len(sheets),
                "sheets": [
                    {
                        "id": s.get("id", ""),
                        "name": s.get("title", "未命名画布"),
                        "rootTopic": {
                            "id": s.get("rootTopic", {}).get("id", ""),
                            "title": s.get("rootTopic", {}).get("title", ""),
                            "labels": s.get("rootTopic", {}).get("labels", []),
                            "notes": self._get_notes(s.get("rootTopic", {})),
                        },
                        "topicCount": self._count_topics(s.get("rootTopic", {}))
                    } for s in sheets_data
                ]
            }

            return {
                "metadata": metadata,
                "sheets": sheets
            }

    def _topic_to_dict(self, topic: Dict) -> Dict:
        """将 topic 字典转换为前端结构"""
        data = {
            "id": topic.get("id", ""),
            "title": topic.get("title", ""),
            "notes": self._get_notes(topic),
            "labels": topic.get("labels", []),
            "link": topic.get("link"),
            "isRoot": topic.get("isRoot", False)
        }

        # 子主题处理：children.attached 数组
        children = []
        children_container = topic.get("children", {})
        if isinstance(children_container, dict):
            attached = children_container.get("attached", [])
            for child in attached:
                children.append(self._topic_to_dict(child))
        data["children"] = children

        return data

    def _get_notes(self, topic: Dict) -> str:
        """提取笔记内容"""
        note = topic.get("notes")
        if not note:
            return ""
        # content.json 中 notes 结构: {"plain": {"content": "..."}}
        if isinstance(note, dict):
            plain = note.get("plain", {})
            if isinstance(plain, dict):
                return plain.get("content", "")
            return str(plain)
        return str(note)

    def _count_topics(self, root_topic: Dict) -> int:
        """递归统计主题数量"""
        count = 1
        children_container = root_topic.get("children", {})
        if isinstance(children_container, dict):
            attached = children_container.get("attached", [])
            for child in attached:
                count += self._count_topics(child)
        return count

    def save_content(self, file_path: str, content: Any) -> bool:
        """XMind 编辑暂未实现"""
        raise NotImplementedError("XMind 编辑暂未实现，建议导出后重新创建")
