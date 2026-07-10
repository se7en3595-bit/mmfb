"""SVG 矢量格式处理器

职责：
1. 读取 .svg / .svgz 文件内容，解析 viewBox 与宽高属性
2. 预览模式：前端 <img src="file://..."> 直接渲染矢量图
3. 编辑模式：textarea 编辑源码 + 实时预览
4. 源码查看：直接展示 SVG XML
5. 导出 PNG：使用 QSvgRenderer 栅格化（无需 cairosvg / libcairo）

返回结构：
- mime: image/svg+xml
- template: 'svg'
- data.content: SVG 源码（UTF-8 文本）
- data.file_path: 文件绝对路径（file:// 可直接加载）
- data.width / height: viewBox 或 width/height 属性值（像素），0 表示未指定
- data.viewBox: viewBox 属性字符串
- data.file_size: 字节数
- data.line_count: 行数
- data.is_compressed: 是否为 .svgz（gzip 压缩）
- editable: True（支持就地编辑）
"""
import os
import re
import gzip
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from mmfb.core.handler_base import BaseHandler


SVG_EXTENSIONS: List[str] = [
    ".svg",
    ".svgz",
]

# SVG 命名空间
SVG_NS = "{http://www.w3.org/2000/svg}"
XLINK_NS = "{http://www.w3.org/1999/xlink}"


class SvgHandler(BaseHandler):
    """SVG 矢量图处理器

    支持的扩展名：
        .svg, .svgz (gzip 压缩)

    实现策略：
        - 直读源码：SVG 是文本域，无需二进制解码
        - .svgz：gzip.decompress 后再解码
        - 解析宽高：优先从 viewBox 取，再回退 width/height 属性
        - 保存：编辑后写回 UTF-8 文本；.svgz 需 gzip 压缩后写回
    """

    extensions = SVG_EXTENSIONS
    mime = "image/svg+xml"

    def get_preview(self) -> Optional[Dict[str, Any]]:
        """获取 SVG 预览数据"""
        try:
            if not os.path.isfile(self.path):
                return self._result("", 0, 0, "", 0, False, error="file not found")

            raw_bytes = self._read_raw()
            if raw_bytes is None:
                return self._result("", 0, 0, "", 0, False, error="file not found or too large")

            is_compressed = self.path.lower().endswith(".svgz")
            content = self._decode_svg(raw_bytes, is_compressed)
            if content is None:
                return self._result("", 0, 0, "", 0, False, error="failed to decode file (not valid gzip?)")

            width, height, viewbox = self._parse_dimensions(content)
            file_size = os.path.getsize(self.path)
            line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)

            return self._result(
                content=content,
                width=width,
                height=height,
                viewbox=viewbox,
                file_size=file_size,
                is_compressed=is_compressed,
                line_count=line_count,
                error=None,
            )
        except Exception as e:
            return self._result("", 0, 0, "", 0, False, error=str(e))

    def get_edit(self) -> Optional[Dict[str, Any]]:
        """获取编辑数据"""
        preview = self.get_preview()
        if preview is None:
            return None
        preview["data"]["save"] = True
        preview["data"]["mime"] = "image/svg+xml"
        return preview

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _read_raw(self) -> Optional[bytes]:
        """读取原始二进制内容（上限 50MB）"""
        size = os.path.getsize(self.path)
        if size > 50 * 1024 * 1024:
            return None
        with open(self.path, "rb") as f:
            return f.read()

    def _decode_svg(self, raw: bytes, is_compressed: bool) -> Optional[str]:
        """解码为 UTF-8 文本"""
        try:
            if is_compressed:
                raw = gzip.decompress(raw)
            return raw.decode("utf-8", errors="replace")
        except (gzip.BadGzipFile, OSError):
            # 尝试作为纯文本解析（有些 .svgz 实际是未压缩的 SVG）
            try:
                return raw.decode("utf-8", errors="replace")
            except Exception:
                return None

    def _parse_dimensions(self, content: str) -> tuple:
        """从 SVG 内容解析宽度、高度、viewBox

        策略：
        - 用正则提取根 <svg> 的 width / height / viewBox 属性
        - viewBox="minX minY width height" 取后两项
        - width/height 去单位（px / pt / mm 等）取数字部分
        """
        # 查找根 <svg ...> 标签
        svg_tag_match = re.search(r"<svg\b([^>]*)>", content, re.IGNORECASE | re.DOTALL)
        if not svg_tag_match:
            return 0, 0, ""

        attrs_str = svg_tag_match.group(1)

        viewbox = self._extract_attr(attrs_str, "viewBox")
        width_attr = self._extract_attr(attrs_str, "width")
        height_attr = self._extract_attr(attrs_str, "height")

        # 从 viewBox 取宽高
        vb_width, vb_height = 0, 0
        if viewbox:
            parts = viewbox.replace(",", " ").split()
            if len(parts) >= 4:
                try:
                    vb_width = int(float(parts[2]))
                    vb_height = int(float(parts[3]))
                except (ValueError, TypeError):
                    pass

        width = self._parse_length(width_attr) or vb_width
        height = self._parse_length(height_attr) or vb_height

        return width, height, viewbox or ""

    @staticmethod
    def _extract_attr(attrs_str: str, name: str) -> str:
        # 双引号
        m = re.search(name + r'\s*=\s*"([^"]*)"', attrs_str, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        # 单引号
        m = re.search(name + r"\s*=\s*'([^']*)'", attrs_str, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return ""

    @staticmethod
    def _parse_length(s: str) -> int:
        """解析 '100px' / '100' / '100.5pt' 等为整像素"""
        if not s:
            return 0
        m = re.match(r"([0-9]*\.?[0-9]+)", s.strip())
        if m:
            try:
                return int(float(m.group(1)))
            except ValueError:
                return 0
        return 0

    def _result(
        self,
        content: str,
        width: int,
        height: int,
        viewbox: str,
        file_size: int,
        is_compressed: bool,
        line_count: int = 0,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = {
            "mime": "image/svg+xml",
            "template": "svg",
            "data": {
                "content": content,
                "file_path": self.path,
                "file_url": "file:///" + self.path.replace("\\", "/"),
                "width": width,
                "height": height,
                "viewBox": viewbox,
                "file_size": file_size,
                "line_count": line_count,
                "is_compressed": is_compressed,
            },
            "editable": True,
        }
        if error:
            result["error"] = error
        return result


def rasterize_to_png(
    svg_path: str,
    png_path: str,
    width: int = 0,
    height: int = 0,
) -> Dict[str, Any]:
    """将 SVG 栅格化为 PNG

    使用 PySide6.QtSvg.QSvgRenderer + QPainter + QImage。
    不需要 libcairo / cairosvg。

    参数：
        svg_path: SVG 文件路径
        png_path: 输出 PNG 路径
        width: 输出宽度（像素），0 表示使用 SVG 默认宽度
        height: 输出高度（像素），0 表示使用 SVG 默认高度

    返回：
        {"ok": true, "path": "...", "width": int, "height": int}
        或 {"ok": false, "error": "..."}
    """
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtGui import QPainter, QImage
        from PySide6.QtCore import QSize, QRectF, Qt
    except ImportError as e:
        return {"ok": False, "error": f"QtSvg import failed: {e}"}

    try:
        # 确保有 QApplication 实例（Qt 要求渲染有 app）
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        renderer = QSvgRenderer(svg_path)
        if not renderer.isValid():
            return {"ok": False, "error": "invalid SVG or file not found: " + svg_path}

        default_size = renderer.defaultSize()
        if default_size.width() <= 0 or default_size.height() <= 0:
            # 缺省尺寸 fallback
            default_size = QSize(512, 512)

        # 计算输出尺寸 (保持宽高比)
        if width > 0 and height > 0:
            out_w, out_h = width, height
        elif width > 0:
            ratio = width / default_size.width()
            out_w = width
            out_h = max(1, int(default_size.height() * ratio))
        elif height > 0:
            ratio = height / default_size.height()
            out_w = max(1, int(default_size.width() * ratio))
            out_h = height
        else:
            out_w = default_size.width()
            out_h = default_size.height()

        # 渲染
        image = QImage(out_w, out_h, QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        renderer.render(painter, QRectF(0, 0, out_w, out_h))
        painter.end()

        if not image.save(png_path, "PNG"):
            return {"ok": False, "error": "failed to save PNG: " + png_path}

        return {"ok": True, "path": png_path, "width": out_w, "height": out_h}
    except Exception as e:
        return {"ok": False, "error": str(e)}
