"""EPUB 电子书格式处理器

职责：
1. 使用 ebooklib 解析 EPUB 文件结构
2. 提取元数据（标题、作者）
3. 构建阅读目录（TOC）
4. 合并章节内容为单个 HTML 文档（简化处理）
5. 支持目录导航（锚点跳转）
"""
import os
from typing import Any, Dict, List, Optional

from mmfb.core.handler_base import BaseHandler


try:
    from ebooklib import epub
    from ebooklib import ITEM_DOCUMENT, ITEM_NAVIGATION
    EBOOKLIB_AVAILABLE = True
except ImportError:
    EBOOKLIB_AVAILABLE = False


# EPUB 扩展名
EPUB_EXTENSIONS: List[str] = [
    ".epub",
]


class EpubHandler(BaseHandler):
    """EPUB 电子书文件处理器

    支持的扩展名：
        .epub

    特性：
        - 提取书名、作者
        - 解析目录结构（TOC）
        - 生成合并的 HTML 文档（含目录导航）
        - 只读模式（不支持编辑）
    """

    extensions = EPUB_EXTENSIONS

    def get_preview(self) -> Optional[Dict[str, Any]]:
        """获取 EPUB 预览数据

        返回字典：
        - mime: application/epub+zip
        - template: 'epub'
        - data: {
            title: str,
            author: str,
            toc: list of {title, anchor} or nested,
            html_content: str (完整的 HTML 文档)
          }
        - editable: False
        """
        if not EBOOKLIB_AVAILABLE:
            return {
                "mime": "application/epub+zip",
                "template": "epub",
                "data": {
                    "title": "错误",
                    "author": "",
                    "toc": [],
                    "html_content": "<p>缺少 ebooklib 依赖，无法解析 EPUB。</p>",
                },
                "editable": False,
                "error": "ebooklib not installed",
            }

        try:
            if not os.path.isfile(self.path):
                return {
                    "mime": "application/epub+zip",
                    "template": "epub",
                    "data": {
                        "title": "",
                        "author": "",
                        "toc": [],
                        "html_content": "",
                    },
                    "editable": False,
                    "error": "file not found",
                }

            book = epub.read_epub(self.path)

            # 提取元数据
            title = ""
            author = ""
            try:
                titles = book.get_metadata('DC', 'title')
                if titles:
                    title = titles[0][0]
                authors = book.get_metadata('DC', 'creator')
                if authors:
                    author = authors[0][0]
            except Exception:
                pass

            # 获取目录 (toc)
            toc_entries = []
            try:
                raw_toc = book.toc
                if raw_toc:
                    # ebooklib 的 toc 是 Link 和 Section 的嵌套列表
                    # 我们需要平铺为带锚点的列表
                    def _flatten_toc(entries, depth=0):
                        items = []
                        for entry in entries:
                            if isinstance(entry, tuple):
                                # (Link, [subentries])
                                link, sub = entry
                                href = link.href
                                # 去掉锚点（可能包含 #）
                                anchor = href.split('#')[0] if href else ""
                                items.append({
                                    "title": link.title or "",
                                    "href": href or "",
                                    "depth": depth,
                                })
                                if sub:
                                    items.extend(_flatten_toc(sub, depth + 1))
                            elif isinstance(entry, list):
                                items.extend(_flatten_toc(entry, depth))
                        return items

                    toc_entries = _flatten_toc(raw_toc)
            except Exception as e:
                toc_entries = []

            # 提取所有文档项（HTML内容）
            # 构造一个文档列表：按照 spine 顺序，或者使用 toc_entries 的顺序
            # 为简化，我们将所有 ITEM_DOCUMENT 的 HTML 内容合并
            html_contents = []
            try:
                items = list(book.get_items_of_type(ITEM_DOCUMENT))
                for item in items:
                    # item.get_content() 返回 bytes
                    content_bytes = item.get_content()
                    try:
                        html_str = content_bytes.decode('utf-8')
                    except UnicodeDecodeError:
                        html_str = content_bytes.decode('latin-1', errors='replace')
                    html_contents.append(f'<div class="epub-chapter" data-href="{item.file_name}">\n{html_str}\n</div>')
            except Exception as e:
                html_contents = []

            # 构建合并的 HTML
            merged_html = self._build_merged_html(title, author, toc_entries, html_contents)

            return {
                "mime": "application/epub+zip",
                "template": "epub",
                "data": {
                    "title": title,
                    "author": author,
                    "toc": toc_entries,
                    "html_content": merged_html,
                },
                "editable": False,
            }

        except Exception as e:
            return {
                "mime": "application/epub+zip",
                "template": "epub",
                "data": {
                    "title": "",
                    "author": "",
                    "toc": [],
                    "html_content": f"<p>解析失败: {str(e)}</p>",
                },
                "editable": False,
                "error": str(e),
            }

    def _build_merged_html(
        self,
        title: str,
        author: str,
        toc: List[Dict],
        chapters: List[str]
    ) -> str:
        """构建单个 HTML 文档，包含目录和章节"""
        # 生成目录 HTML
        toc_html = '<div class="epub-toc"><h2>目录</h2><ul>'
        for entry in toc:
            depth = entry.get("depth", 0)
            indent = depth * 20
            toc_html += f'<li style="margin-left:{indent}px"><a href="#toc-{entry["href"]}">{entry["title"]}</a></li>'
        toc_html += '</ul></div>'

        # 章节内容
        chapters_html = '<div class="epub-chapters">' + ''.join(chapters) + '</div>'

        # 完整文档
        full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{title or 'EPUB 阅读'}</title>
<style>
body {{ font-family: serif; margin: 0; padding: 0; line-height: 1.6; }}
.epub-toc {{ background: #f5f5f5; padding: 20px; border-bottom: 1px solid #ddd; }}
.epub-toc h2 {{ margin-top: 0; }}
.epub-toc ul {{ list-style: none; padding-left: 0; }}
.epub-toc li {{ margin: 5px 0; }}
.epub-toc a {{ text-decoration: none; color: #0066cc; }}
.epub-chapters {{ padding: 20px; }}
.epub-chapter {{ margin-bottom: 40px; border-bottom: 1px solid #eee; padding-bottom: 20px; }}
</style>
</head>
<body>
{toc_html}
{chapters_html}
<script>
// 简单的目录跳转：使用锚点
document.addEventListener('DOMContentLoaded', function() {{
    const links = document.querySelectorAll('.epub-toc a');
    links.forEach(link => {{
        link.addEventListener('click', function(e) {{
            e.preventDefault();
            const targetId = this.getAttribute('href').substring(1);
            const target = document.getElementById(targetId) || document.querySelector('[data-href="' + this.getAttribute('href') + '"]');
            if (target) {{
                target.scrollIntoView({{behavior: 'smooth', block: 'start'}});
            }}
        }});
    }});
}});
</script>
</body>
</html>"""
        return full_html
