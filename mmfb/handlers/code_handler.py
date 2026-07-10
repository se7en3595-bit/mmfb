"""代码高亮格式处理器

职责：
1. 读取源码文本文件（.py/.js/.ts/.java/.cpp/.c/.go/.rs 等语言）
2. 前端通过语法高亮引擎渲染（行号 + 暗色主题）
3. 只读模式，不支持编辑
4. 可选：扩展名到语言标签的映射（供前端选择高亮规则）

注意：.html/.htm/.css 由 HtmlHandler 处理，.csv/.tsv 由 CsvHandler 处理，
.json/.xml/.yaml/.yml/.toml/.conf/.env/.properties 由 TextHandler 处理，
这些扩展名不从 CodeHandler 注册，避免专门 Handler 被通用 Handler 覆盖。
"""
import os
from typing import Any, Dict, List, Optional

from mmfb.core.handler_base import BaseHandler
from mmfb.core.file_handler import safe_read_text

# 源码文件扩展名（按语言分组便于维护）
CODE_EXTENSIONS: List[str] = [
# Python / Ruby / Perl
".py", ".pyw", ".pyi", ".rb", ".rake", ".gemspec", ".pl", ".pm", ".t",
# JavaScript / TypeScript / Web framework
".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue", ".svelte",
# Java / JVM
".java", ".kt", ".kts", ".scala", ".groovy", ".clj", ".cljs",
# C / C++ / C#
".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".cs", ".csx",
# Go / Rust / Swift / Kotlin
".go", ".rs", ".swift",
# PHP (代码场景)
".php", ".phtml", ".ctp",
# Shell / Scripts
".sh", ".bash", ".zsh", ".fish", ".bat", ".cmd", ".ps1", ".psm1",
# SQL / Data
".sql", ".mysql", ".pgsql",
# Data / Config
".graphql", ".gql",
# Functional / Math
".hs", ".lhs", ".elm", ".erl", ".ex", ".exs", ".ml", ".mli", ".fs", ".fsx",
".r", ".mat", ".jl", ".lua",
# Assembly / Low level
".asm", ".s", ".nim", ".zig", ".v", ".sv",
# Other
".dart", ".flutter", ".coffee", ".litcoffee", ".sol", ".vy",
    # 结构化文本/配置格式（与 TextHandler 双重注册，registry 按优先级决定归属）
    ".ini", ".json", ".jsonc", ".xml", ".yaml", ".yml", ".toml",
    ".conf", ".env", ".properties",
]

# 扩展名 -> 语言标识（供前端选择高亮规则）
EXT_TO_LANG: Dict[str, str] = {
".py": "python", ".pyw": "python", ".pyi": "python",
".rb": "ruby", ".rake": "ruby", ".gemspec": "ruby",
".pl": "perl", ".pm": "perl", ".t": "perl",
".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
".ts": "typescript", ".tsx": "typescript",
".vue": "vue", ".svelte": "svelte",
".css": "css", ".scss": "css", ".sass": "css", ".less": "css", ".styl": "css",
".java": "java", ".kt": "kotlin", ".kts": "kotlin",
".scala": "scala", ".groovy": "groovy",
".clj": "clojure", ".cljs": "clojure",
".c": "c", ".h": "c",
".cpp": "cpp", ".hpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
".cs": "csharp", ".csx": "csharp",
".go": "go", ".rs": "rust", ".swift": "swift",
".php": "php", ".phtml": "php", ".ctp": "php",
".sh": "shell", ".bash": "shell", ".zsh": "shell", ".fish": "shell",
".bat": "batch", ".cmd": "batch", ".ps1": "powershell", ".psm1": "powershell",
".sql": "sql", ".mysql": "sql", ".pgsql": "sql",
".graphql": "graphql", ".gql": "graphql",
".hs": "haskell", ".lhs": "haskell", ".elm": "elm",
".erl": "erlang", ".ex": "elixir", ".exs": "elixir",
".ml": "ocaml", ".mli": "ocaml", ".fs": "fsharp", ".fsx": "fsharp",
".r": "r", ".mat": "matlab", ".jl": "julia", ".lua": "lua",
".asm": "assembly", ".s": "assembly",
".nim": "nim", ".zig": "zig", ".v": "vlang", ".sv": "systemverilog",
".dart": "dart", ".flutter": "dart",
".coffee": "coffeescript", ".litcoffee": "coffeescript",
".sol": "solidity", ".vy": "vyper",
".ini": "ini",
    ".json": "json", ".jsonc": "json",
    ".xml": "xml",
    ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml",
    ".conf": "ini", ".env": "ini", ".properties": "ini",
}


class CodeHandler(BaseHandler):
    """源码文件处理器

    支持的扩展名：60+ 种编程语言
    模式：只读预览（不支持编辑）
    """

    extensions = CODE_EXTENSIONS

    @classmethod
    def get_lang_for_ext(cls, ext: str) -> str:
        """根据扩展名返回语言标识"""
        return EXT_TO_LANG.get(ext.lower(), "plaintext")

    @classmethod
    def can_handle(cls, path: str) -> bool:
        """判断 Handler 是否支持该路径（复合后缀匹配：.tar.gz 等不在此处理）

        同时处理无扩展名的点文件（如 .env → .env 作为扩展名）。
        """
        from pathlib import Path
        p = Path(path)
        suffix = p.suffix.lower()
        if suffix:
            return suffix in cls.extensions
        # 无扩展名的点文件（如 .env）：将整个文件名当作扩展名处理
        name = p.name.lower()
        if name.startswith("."):
            return name in cls.extensions
        return False

    def get_preview(self) -> Optional[Dict[str, Any]]:
        """获取代码预览数据"""
        try:
            if not os.path.isfile(self.path):
                return {
                    "mime": "text/plain",
                    "template": "code",
                    "data": {
                        "content": "",
                        "file_path": self.path,
                        "file_size": 0,
                        "line_count": 0,
                        "language": "plaintext",
                    },
                    "editable": False,
                    "error": "file not found",
                }

            content = safe_read_text(self.path, encoding="utf-8")
            if content is None:
                return {
                    "mime": "text/plain",
                    "template": "code",
                    "data": {
                        "content": "",
                        "file_path": self.path,
                        "file_size": 0,
                        "line_count": 0,
                        "language": "plaintext",
                    },
                    "editable": False,
                    "error": "failed to read file (encoding issue or permission denied)",
                }

            file_size = os.path.getsize(self.path)
            if not content:
                line_count = 0
            else:
                line_count = content.count("\n") + (0 if content.endswith("\n") else 1)

            from pathlib import Path
            ext = Path(self.path).suffix.lower()
            language = EXT_TO_LANG.get(ext, "plaintext")

            return {
                "mime": "text/plain",
                "template": "code",
                "data": {
                    "content": content,
                    "file_path": self.path,
                    "file_size": file_size,
                    "line_count": line_count,
                    "language": language,
                },
                "editable": False,
            }
        except Exception as e:
            return {
                "mime": "text/plain",
                "template": "code",
                "data": {
                    "content": "",
                    "file_path": self.path,
                    "file_size": 0,
                    "line_count": 0,
                    "language": "plaintext",
                },
                "editable": False,
                "error": str(e),
            }

    def get_edit(self) -> Optional[Dict[str, Any]]:
        """代码文件不支持编辑，返回 None"""
        return None
