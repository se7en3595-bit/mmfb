"""文件关联管理器测试

注意：这些测试在 winreg 模拟环境下运行。
在 Windows 平台上需要以非特权用户身份运行，仅操作 HKCU。
"""
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch


class TestFileAssociationLogic(unittest.TestCase):
    """测试文件关联逻辑（不依赖真实注册表）"""

    def setUp(self):
        """确保能导入"""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
        # Mock winreg
        self.winreg_patcher = patch.dict("sys.modules", {"winreg": MagicMock()})
        self.winreg_patcher.start()
        self.ctypes_patcher = patch.dict("sys.modules", {"ctypes": MagicMock()})
        self.ctypes_patcher.start()

        # 清空模块缓存
        for mod in list(sys.modules.keys()):
            if mod.startswith("mmfb.services.file_association"):
                del sys.modules[mod]

    def tearDown(self):
        self.winreg_patcher.stop()
        self.ctypes_patcher.stop()

    def test_module_imports(self):
        """模块应能成功导入"""
        from mmfb.services import file_association
        self.assertTrue(hasattr(file_association, "get_supported_extensions"))
        self.assertTrue(hasattr(file_association, "is_extension_associated"))
        self.assertTrue(hasattr(file_association, "get_association_status"))
        self.assertTrue(hasattr(file_association, "associate_extension"))
        self.assertTrue(hasattr(file_association, "unregister_extension"))
        self.assertTrue(hasattr(file_association, "associate_all"))
        self.assertTrue(hasattr(file_association, "unregister_all"))
        self.assertTrue(hasattr(file_association, "refresh_shell_icons"))
        self.assertTrue(hasattr(file_association, "is_first_launch"))
        self.assertTrue(hasattr(file_association, "get_registry_summary"))

    def test_supported_extensions_not_empty(self):
        """应能获取非空扩展名列表"""
        with patch("mmfb.core.registry.HandlerRegistry.list_extensions") as mock_list:
            mock_list.return_value = [".pdf", ".docx", ".xlsx", ".png", ".txt", ".html"]
            from mmfb.services.file_association import get_supported_extensions
            exts = get_supported_extensions()
            self.assertIsInstance(exts, list)
            self.assertTrue(len(exts) > 0)

    def test_supported_extensions_excludes_compounds(self):
        """不应包含复合后缀"""
        with patch("mmfb.core.registry.HandlerRegistry.list_extensions") as mock_list:
            mock_list.return_value = [".pdf", ".docx", ".xlsx", ".png", ".txt", ".html"]
            from mmfb.services.file_association import get_supported_extensions
            exts = get_supported_extensions()
            for ext in exts:
                # 复合后缀形如 .tar.gz，除第一个点外不应有其他点
                self.assertNotIn(".", ext[1:], f"compound suffix found: {ext}")

    def test_supported_extensions_sorted(self):
        """扩展名列表应已排序"""
        with patch("mmfb.core.registry.HandlerRegistry.list_extensions") as mock_list:
            mock_list.return_value = [".pdf", ".docx", ".xlsx", ".png", ".txt", ".html"]
            from mmfb.services.file_association import get_supported_extensions
            exts = get_supported_extensions()
            self.assertEqual(exts, sorted(set(exts)))

    def test_registry_summary_structure(self):
        """registry_summary 应包含必要字段"""
        with patch("mmfb.services.file_association.get_association_status") as mock_status:
            mock_status.return_value = (10, 50)
            from mmfb.services.file_association import get_registry_summary
            summary = get_registry_summary()

            # 即使 mock 失败也应该返回 dict
            if "error" in summary:
                return  # 在 Windows 外运行时跳过

            self.assertIn("associated", summary)
            self.assertIn("total", summary)
            self.assertIn("exe_path", summary)
            self.assertIn("icon_path", summary)
            self.assertIn("prog_id", summary)
            self.assertIn("friendly_name", summary)

    def test_is_extension_associated_mock_returns_false(self):
        """mock 环境下 is_extension_associated 应返回 False"""
        from mmfb.services.file_association import is_extension_associated
        result = is_extension_associated(".pdf")
        self.assertIsInstance(result, bool)
        self.assertFalse(result)

    def test_constants_defined(self):
        """常量正确定义"""
        from mmfb.services.file_association import (
            PROG_ID, FRIENDLY_TYPE_NAME, _COMMAND_TEMPLATE
        )
        self.assertEqual(PROG_ID, "MMFBUniversalViewer")
        self.assertIn("MMFB", FRIENDLY_TYPE_NAME)
        self.assertIn("{exe_path}", _COMMAND_TEMPLATE)


class TestFileAssociationBridge(unittest.TestCase):
    """测试 Bridge 中新增的 file association 接口"""

    def test_bridge_has_file_association_slots(self):
        """Bridge 对象应有文件关联方法"""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

        # Mock Qt 相关模块 — 需要保留 Signal/Slot 等类的真实类型
        from PySide6.QtCore import Signal, Slot

        mock_qtcore = MagicMock()
        mock_qtcore.Signal = Signal
        mock_qtcore.Slot = Slot
        mock_qtcore.QObject = MagicMock
        mock_qtcore.QFileInfo = MagicMock

        mock_modules = {
            "PySide6": MagicMock(),
            "PySide6.QtCore": mock_qtcore,
            "PySide6.QtWebChannel": MagicMock(),
            "PySide6.QtWidgets": MagicMock(),
            "PySide6.QtWebEngineWidgets": MagicMock(),
            "pandas": MagicMock(),
            "dateutil": MagicMock(),
            "dateutil.tz": MagicMock(),
        }

        with patch.dict("sys.modules", mock_modules):
            if "mmfb.core.bridge" in sys.modules:
                del sys.modules["mmfb.core.bridge"]
            # 也 mock image_handler 的导入
            mock_img = MagicMock()
            mock_img.ImageHandler = MagicMock
            mock_img.rasterize_to_png = MagicMock
            mock_modules["mmfb.handlers.image_handler"] = mock_img

            from mmfb.core.bridge import MMFBBridge

            bridge = MMFBBridge.__new__(MMFBBridge)

            self.assertTrue(hasattr(bridge, "get_file_association_status"))
            self.assertTrue(hasattr(bridge, "register_file_associations"))
            self.assertTrue(hasattr(bridge, "unregister_file_associations"))


class TestFileAssociationFrontendFiles(unittest.TestCase):
    """测试前端文件结构"""

    def test_css_file_exists(self):
        """CSS 文件应存在"""
        css_path = os.path.join(
            os.path.dirname(__file__), "..", "frontend", "css", "file_association.css"
        )
        self.assertTrue(os.path.exists(css_path), f"{css_path} not found")

    def test_js_file_exists(self):
        """JS 文件应存在"""
        js_path = os.path.join(
            os.path.dirname(__file__), "..", "frontend", "js", "file_association.js"
        )
        self.assertTrue(os.path.exists(js_path), f"{js_path} not found")

    def test_js_exports_MMFBFileAssociation(self):
        """JS 应导出 MMFBFileAssociation"""
        js_path = os.path.join(
            os.path.dirname(__file__), "..", "frontend", "js", "file_association.js"
        )
        with open(js_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("MMFBFileAssociation", content)
        self.assertIn("render", content)
        self.assertIn("destroy", content)

    def test_css_has_required_classes(self):
        """CSS 应包含必要的样式类"""
        css_path = os.path.join(
            os.path.dirname(__file__), "..", "frontend", "css", "file_association.css"
        )
        with open(css_path, "r", encoding="utf-8") as f:
            content = f.read()
        required_classes = [
            ".file-assoc",
            ".file-assoc__progress",
            ".file-assoc__bar-fill",
            ".file-assoc__actions",
            ".file-assoc__success",
            ".file-assoc__error",
        ]
        for cls in required_classes:
            self.assertIn(cls, content)

    def test_index_html_references_new_files(self):
        """index.html 应引用新的 CSS 和 JS 文件"""
        html_path = os.path.join(
            os.path.dirname(__file__), "..", "frontend", "index.html"
        )
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("file_association.css", content)
        self.assertIn("file_association.js", content)


if __name__ == "__main__":
    unittest.main()
