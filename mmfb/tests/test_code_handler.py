"""CodeHandler 测试用例

测试 CodeHandler 的 get_preview / can_handle / extensions 以及
扩展名匹配、语言映射、边界场景等。

不依赖 PySide6 QApplication，仅测试纯 Python 逻辑。
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mmfb.handlers.code_handler import CodeHandler, EXT_TO_LANG


class TestCodeHandlerPreview(unittest.TestCase):
    """CodeHandler.get_preview() 测试"""

    def _write_temp(self, content, suffix=".py"):
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, delete=False, encoding="utf-8", newline=""
        )
        f.write(content)
        f.close()
        return f.name

    def test_basic_preview_returns_dict(self):
        path = self._write_temp("print('hello')")
        try:
            result = CodeHandler(path).get_preview()
            self.assertIsNotNone(result)
            self.assertIsInstance(result, dict)
            self.assertEqual(result["mime"], "text/plain")
            self.assertEqual(result["template"], "code")
            self.assertFalse(result["editable"])
        finally:
            os.unlink(path)

    def test_content_matches_file(self):
        content = "def main():\n    return 42\n"
        path = self._write_temp(content)
        try:
            result = CodeHandler(path).get_preview()
            self.assertEqual(result["data"]["content"], content)
        finally:
            os.unlink(path)

    def test_line_count(self):
        path = self._write_temp("line1\nline2\nline3\n")
        try:
            result = CodeHandler(path).get_preview()
            self.assertEqual(result["data"]["line_count"], 3)
        finally:
            os.unlink(path)

    def test_line_count_no_trailing_newline(self):
        path = self._write_temp("a\nb\nc")
        try:
            result = CodeHandler(path).get_preview()
            self.assertEqual(result["data"]["line_count"], 3)
        finally:
            os.unlink(path)

    def test_line_count_empty(self):
        path = self._write_temp("")
        try:
            result = CodeHandler(path).get_preview()
            self.assertEqual(result["data"]["line_count"], 0)
        finally:
            os.unlink(path)

    def test_language_python(self):
        path = self._write_temp("x = 1", suffix=".py")
        try:
            result = CodeHandler(path).get_preview()
            self.assertEqual(result["data"]["language"], "python")
        finally:
            os.unlink(path)

    def test_language_javascript(self):
        path = self._write_temp("var x = 1", suffix=".js")
        try:
            result = CodeHandler(path).get_preview()
            self.assertEqual(result["data"]["language"], "javascript")
        finally:
            os.unlink(path)

    def test_language_typescript(self):
        path = self._write_temp("let x: number = 1", suffix=".ts")
        try:
            result = CodeHandler(path).get_preview()
            self.assertEqual(result["data"]["language"], "typescript")
        finally:
            os.unlink(path)

    def test_language_rust(self):
        path = self._write_temp("fn main() {}", suffix=".rs")
        try:
            result = CodeHandler(path).get_preview()
            self.assertEqual(result["data"]["language"], "rust")
        finally:
            os.unlink(path)

    def test_language_json(self):
        path = self._write_temp('{"key": "value"}', suffix=".json")
        try:
            result = CodeHandler(path).get_preview()
            self.assertEqual(result["data"]["language"], "json")
        finally:
            os.unlink(path)

    def test_language_shell(self):
        path = self._write_temp("echo hello", suffix=".sh")
        try:
            result = CodeHandler(path).get_preview()
            self.assertEqual(result["data"]["language"], "shell")
        finally:
            os.unlink(path)

    def test_language_unknown(self):
        path = self._write_temp("data", suffix=".custom_ext_not_mapped")
        try:
            result = CodeHandler(path).get_preview()
            # 虽然没有 .can_handle 支持，但直接实例化时扩展名不在表里应返回 plaintext
            self.assertEqual(result["data"]["language"], "plaintext")
        finally:
            os.unlink(path)

    def test_nonexistent_file_returns_error(self):
        result = CodeHandler("/tmp/nonexistent_999.py").get_preview()
        self.assertIsNotNone(result)
        self.assertIn("error", result)
        self.assertEqual(result["data"]["content"], "")
        self.assertFalse(result["editable"])

    def test_utf8_content(self):
        content = '# 中文注释\nprint("你好世界")\n'
        path = self._write_temp(content)
        try:
            result = CodeHandler(path).get_preview()
            self.assertEqual(result["data"]["content"], content)
        finally:
            os.unlink(path)

    def test_file_info_fields(self):
        path = self._write_temp("a = 1\nb = 2\n")
        try:
            result = CodeHandler(path).get_preview()
            self.assertIn("file_path", result["data"])
            self.assertIn("file_size", result["data"])
            self.assertIn("line_count", result["data"])
            self.assertIn("language", result["data"])
            self.assertGreater(result["data"]["file_size"], 0)
        finally:
            os.unlink(path)


class TestCodeHandlerCanHandle(unittest.TestCase):
    """CodeHandler.can_handle() 测试"""

    def test_python(self):
        self.assertTrue(CodeHandler.can_handle("main.py"))
        self.assertTrue(CodeHandler.can_handle("MAIN.PY"))

    def test_javascript(self):
        self.assertTrue(CodeHandler.can_handle("app.js"))

    def test_typescript(self):
        self.assertTrue(CodeHandler.can_handle("app.ts"))
        self.assertTrue(CodeHandler.can_handle("app.tsx"))

    def test_c_cpp(self):
        self.assertTrue(CodeHandler.can_handle("main.c"))
        self.assertTrue(CodeHandler.can_handle("main.cpp"))
        self.assertTrue(CodeHandler.can_handle("main.h"))

    def test_rust(self):
        self.assertTrue(CodeHandler.can_handle("lib.rs"))

    def test_go(self):
        self.assertTrue(CodeHandler.can_handle("main.go"))

    def test_java(self):
        self.assertTrue(CodeHandler.can_handle("App.java"))

    def test_csharp(self):
        self.assertTrue(CodeHandler.can_handle("Program.cs"))

    def test_ruby(self):
        self.assertTrue(CodeHandler.can_handle("app.rb"))

    def test_php(self):
        self.assertTrue(CodeHandler.can_handle("index.php"))

    def test_shell(self):
        self.assertTrue(CodeHandler.can_handle("script.sh"))
        self.assertTrue(CodeHandler.can_handle("build.bat"))
        self.assertTrue(CodeHandler.can_handle("deploy.ps1"))

    def test_config(self):
        self.assertTrue(CodeHandler.can_handle("config.json"))
        self.assertTrue(CodeHandler.can_handle("config.yaml"))
        self.assertTrue(CodeHandler.can_handle("config.yml"))
        self.assertTrue(CodeHandler.can_handle("Cargo.toml"))
        self.assertTrue(CodeHandler.can_handle(".env"))

    def test_sql(self):
        self.assertTrue(CodeHandler.can_handle("query.sql"))

    def test_markdown_not_handled(self):
        """.md 应由 MarkdownHandler 处理"""
        self.assertFalse(CodeHandler.can_handle("readme.md"))

    def test_pdf_not_handled(self):
        self.assertFalse(CodeHandler.can_handle("doc.pdf"))

    def test_image_not_handled(self):
        self.assertFalse(CodeHandler.can_handle("photo.png"))
        self.assertFalse(CodeHandler.can_handle("photo.jpg"))

    def test_uppercase_extension(self):
        self.assertTrue(CodeHandler.can_handle("MAIN.PY"))
        self.assertTrue(CodeHandler.can_handle("APP.JS"))

    def test_mixed_case(self):
        self.assertTrue(CodeHandler.can_handle("Main.Py"))

    def test_video_not_handled(self):
        self.assertFalse(CodeHandler.can_handle("video.mp4"))
        self.assertFalse(CodeHandler.can_handle("audio.mp3"))


class TestCodeHandlerGetEdit(unittest.TestCase):
    """CodeHandler.get_edit() 测试"""

    def test_get_edit_returns_none(self):
        """代码文件不支持编辑"""
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8", newline=""
        )
        f.write("print('hello')")
        f.close()
        try:
            result = CodeHandler(f.name).get_edit()
            self.assertIsNone(result)
        finally:
            os.unlink(f.name)

    def test_supports_editing_returns_false(self):
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8", newline=""
        )
        f.write("print('hello')")
        f.close()
        try:
            self.assertFalse(CodeHandler(f.name).supports_editing())
        finally:
            os.unlink(f.name)


class TestCodeHandlerExtensions(unittest.TestCase):
    """extensions 类属性测试"""

    def test_extensions_not_empty(self):
        self.assertTrue(len(CodeHandler.extensions) >= 80)

    def test_extensions_unique(self):
        """所有扩展名应不重复"""
        self.assertEqual(len(CodeHandler.extensions), len(set(CodeHandler.extensions)))

    def test_extensions_start_with_dot(self):
        for ext in CodeHandler.extensions:
            self.assertTrue(ext.startswith("."), f"{ext!r} does not start with .")

    def test_extensions_lowercase(self):
        for ext in CodeHandler.extensions:
            self.assertEqual(ext, ext.lower(), f"{ext!r} is not lowercase")

    def test_py_in_extensions(self):
        self.assertIn(".py", CodeHandler.extensions)

    def test_js_in_extensions(self):
        self.assertIn(".js", CodeHandler.extensions)

    def test_rs_in_extensions(self):
        self.assertIn(".rs", CodeHandler.extensions)


class TestCodeHandlerExtToLang(unittest.TestCase):
    """EXT_TO_LANG 映射测试"""

    def test_python_exts(self):
        self.assertEqual(CodeHandler.get_lang_for_ext(".py"), "python")
        self.assertEqual(CodeHandler.get_lang_for_ext(".pyw"), "python")

    def test_js_exts(self):
        self.assertEqual(CodeHandler.get_lang_for_ext(".js"), "javascript")
        self.assertEqual(CodeHandler.get_lang_for_ext(".mjs"), "javascript")

    def test_typescript_exts(self):
        self.assertEqual(CodeHandler.get_lang_for_ext(".ts"), "typescript")
        self.assertEqual(CodeHandler.get_lang_for_ext(".tsx"), "typescript")

    def test_rust_ext(self):
        self.assertEqual(CodeHandler.get_lang_for_ext(".rs"), "rust")

    def test_known_ext_returns_string(self):
        for ext in EXT_TO_LANG:
            self.assertIsInstance(EXT_TO_LANG[ext], str)

    def test_unknown_ext_returns_plaintext(self):
        self.assertEqual(CodeHandler.get_lang_for_ext(".zzz"), "plaintext")


class TestCodeHandlerRegistry(unittest.TestCase):
    """注册表集成测试"""

    def test_registry_dispatch_py(self):
        from mmfb.core.registry import registry
        handler = registry.get_handler("/path/to/test.py")
        self.assertIsInstance(handler, CodeHandler)

    def test_registry_dispatch_js(self):
        from mmfb.core.registry import registry
        handler = registry.get_handler("/path/to/app.js")
        self.assertIsInstance(handler, CodeHandler)

    def test_registry_dispatch_json(self):
        from mmfb.core.registry import registry
        handler = registry.get_handler("/path/to/config.json")
        self.assertIsInstance(handler, CodeHandler)

    def test_registry_dispatch_unknown(self):
        from mmfb.core.registry import registry
        handler = registry.get_handler("/path/to/data.xyz")
        self.assertIsNone(handler)


if __name__ == "__main__":
    unittest.main(verbosity=2)
