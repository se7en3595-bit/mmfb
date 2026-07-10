"""右键菜单 ``Open With MMFB`` 服务层测试

模块：``mmfb.services.shell_extension``

测试策略：
  * 所有测试均通过模拟 ``winreg`` / ``ctypes`` 实现，不依赖真实注册表
  * 仅测试逻辑路径与数据结构，不涉及 Windows API 副作用
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# 确保能从项目根导入
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


class TestShellExtensionLogic(unittest.TestCase):
    """逻辑性测试（无需 Qt）"""

    def setUp(self):
        # Mock winreg 模块
        self.mock_winreg = MagicMock()
        self.mock_winreg.HKEY_CURRENT_USER = 0x80000001
        self.mock_winreg.REG_SZ = 1
        self.winreg_patcher = patch.dict("sys.modules", {
            "winreg": self.mock_winreg,
            "ctypes": MagicMock(),
        })
        self.winreg_patcher.start()

        # 清空缓存强制重新加载
        if "mmfb.services.shell_extension" in sys.modules:
            del sys.modules["mmfb.services.shell_extension"]

    def tearDown(self):
        self.winreg_patcher.stop()

    def test_module_imports(self):
        """模块应有完整公共 API"""
        from mmfb.services.shell_extension import (
            is_registered,
            register,
            unregister,
            get_status,
            parse_cli_file_args,
            MENU_TITLE,
            MULTI_SELECT_MODEL,
        )
        self.assertTrue(callable(is_registered))
        self.assertTrue(callable(register))
        self.assertTrue(callable(unregister))
        self.assertTrue(callable(get_status))
        self.assertTrue(callable(parse_cli_file_args))

    def test_menu_title_is_chinese(self):
        """菜单显示名应为中文 ``用 MMFB 打开``"""
        from mmfb.services.shell_extension import MENU_TITLE
        self.assertEqual(MENU_TITLE, "用 MMFB 打开")

    def test_multi_select_model_is_player(self):
        """多选模型应为 Player（所有文件一次进程调用）"""
        from mmfb.services.shell_extension import MULTI_SELECT_MODEL
        self.assertEqual(MULTI_SELECT_MODEL, "Player")

    def test_parse_cli_file_args_ignores_exe(self):
        """parse_cli_file_args 应该跳过 .exe 自身"""
        from mmfb.services.shell_extension import parse_cli_file_args
        # 全是 .exe 应当返回空列表
        result = parse_cli_file_args(["C:\\some\\path.exe", "C:\\other.exe"])
        self.assertEqual(result, [])

    def test_parse_cli_file_args_accepts_real_file(self):
        """parse_cli_file_args 应该接受真正的文件路径"""
        from mmfb.services.shell_extension import parse_cli_file_args
        import tempfile
        # 用 .txt 避免 .pdf 被其他补丁影响; 不在 finally 中删除，保证 is_file() 可用
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            tmp_path = f.name
        try:
            with patch("os.path.isfile", return_value=True):
                result = parse_cli_file_args(["mmfb.exe", tmp_path])
                self.assertEqual(len(result), 1)
                self.assertTrue(os.path.isabs(result[0]))
                self.assertTrue(str(result[0]).endswith(".txt"))
        finally:
            os.unlink(tmp_path)

    def test_parse_cli_file_args_skips_nonexistent(self):
        """不存在的路径应该被跳过"""
        from mmfb.services.shell_extension import parse_cli_file_args
        result = parse_cli_file_args(["mmfb.exe", "C:/nonexistent/path/file.pdf"])
        self.assertEqual(result, [])

    def test_parse_cli_file_args_returns_absolute(self):
        """返回的路径应是绝对路径"""
        from mmfb.services.shell_extension import parse_cli_file_args
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            tmp_path = f.name
        try:
            result = parse_cli_file_args(["mmfb.exe", tmp_path])
            self.assertTrue(os.path.isabs(result[0]))
        finally:
            os.unlink(tmp_path)

    def test_get_status_returns_structured_dict(self):
        """get_status 应返回结构化 dict"""
        from mmfb.services.shell_extension import get_status

        # 模拟一个已注册的状态
        mock_open = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_open)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        self.mock_winreg.OpenKey.return_value = mock_ctx
        self.mock_winreg.QueryValueEx.return_value = ("用 MMFB 打开", 1)

        status = get_status()
        self.assertIsInstance(status, dict)
        self.assertIn("registered", status)
        self.assertIn("menu_title", status)
        self.assertIn("exe_path", status)
        self.assertIn("icon_path", status)
        self.assertIn("supported", status)

    def test_register_writes_three_keys(self):
        """register 应该写入三条注册表项（默认值、Icon、MultiSelectModel）"""
        from mmfb.services.shell_extension import register

        # 结构化记录: (subpath, name, value)
        written_record = []
        mock_key = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_key)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        self.mock_winreg.CreateKeyEx.return_value = mock_ctx
        _current_subpath = [""]

        def fake_create_key(root, subpath, _, access):
            _current_subpath[0] = subpath
            return mock_ctx

        def fake_set_value(key, name, _, reg_type, value):
            written_record.append((_current_subpath[0], name, value))

        self.mock_winreg.CreateKeyEx.side_effect = fake_create_key
        self.mock_winreg.SetValueEx.side_effect = fake_set_value

        with patch("mmfb.services.shell_extension.refresh_shell_icons") as mock_refresh:
            ok = register()

        self.assertTrue(ok)
        # 查找 Icon / MultiSelectModel 的写入
        keys_written = {name for _, name, _ in written_record if name}
        values_written = {name: value for _, name, value in written_record if name}
        self.assertIn("Icon", keys_written)
        self.assertIn("MultiSelectModel", keys_written)
        self.assertEqual(values_written["MultiSelectModel"], "Player")
        # 检查菜单标题默认值
        shell_defaults = [v for p, n, v in written_record
                          if not n and "shell" in p.lower()]
        self.assertIn("用 MMFB 打开", shell_defaults)
        # 检查 command 写入（在 command 子路径下）
        command_defaults = [v for p, n, v in written_record
                            if not n and "command" in p.lower()]
        self.assertTrue(len(command_defaults) > 0)
        self.assertIn("%1", command_defaults[0])
        # 调用了外壳刷新
        self.assertTrue(mock_refresh.called)

    def test_is_registered_true(self):
        """注册表值匹配菜单标题时应返回 True"""
        from mmfb.services.shell_extension import is_registered

        mock_key = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_key)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        self.mock_winreg.OpenKey.return_value = mock_ctx
        self.mock_winreg.QueryValueEx.return_value = ("用 MMFB 打开", 1)

        self.assertTrue(is_registered())

    def test_is_registered_false_when_mismatch(self):
        """注册表值与标题不匹配时返回 False"""
        from mmfb.services.shell_extension import is_registered

        mock_key = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_key)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        self.mock_winreg.OpenKey.return_value = mock_ctx
        self.mock_winreg.QueryValueEx.return_value = ("Other App", 1)

        self.assertFalse(is_registered())

    def test_is_registered_false_when_missing(self):
        """注册表路径不存在时返回 False"""
        from mmfb.services.shell_extension import is_registered
        self.mock_winreg.OpenKey.side_effect = OSError("not found")

        self.assertFalse(is_registered())


class TestShellExtensionBridgeSlots(unittest.TestCase):
    """测试 Bridge 中新增的右键菜单接口（通过测试 bridge.py 源码）"""

    def test_bridge_has_shell_extension_slots(self):
        """bridge.py 源码中应包含右键菜单三个方法名的字符串字面量"""
        bridge_path = os.path.join(
            PROJECT_ROOT, "mmfb", "core", "bridge.py"
        )
        with open(bridge_path, "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("get_shell_extension_status", src)
        self.assertIn("register_shell_extension", src)
        self.assertIn("unregister_shell_extension", src)


class TestShellExtensionCLI(unittest.TestCase):
    """CLI 参数解析集成测试"""

    def test_parse_cli_file_args_multiple_files(self):
        """多文件应该全部返回"""
        with patch("os.path.isfile") as mock_isfile:
            mock_isfile.return_value = True
            from mmfb.services.shell_extension import parse_cli_file_args
            files = ["/path/a.pdf", "/path/b.md", "/path/c.txt"]
            result = parse_cli_file_args(["mmfb.exe"] + files)
            self.assertEqual(len(result), 3)

    def test_parse_cli_file_args_filters_invalid(self):
        """无效路径应该被过滤"""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            real_file = f.name
        try:
            from mmfb.services.shell_extension import parse_cli_file_args
            files = [real_file, "/fake/not/exist.txt"]
            result = parse_cli_file_args(["mmfb.exe"] + files)
            self.assertEqual(len(result), 1)
            self.assertEqual(str(result[0]), os.path.abspath(real_file))
        finally:
            os.unlink(real_file)


if __name__ == "__main__":
    unittest.main()
