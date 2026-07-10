"""PSD / PSB 图像处理

职责：
1. 使用 psd-tools 解析 PSD / PSB 图层结构
2. 生成合并预览图（composite），转为 Base64 PNG
3. 提取每个图层的缩略图（对 PixelLayer / SmartObjectLayer / TypeLayer）
4. 输出图层树（含图层类型、可见性、不透明度、尺寸）
5. 提取智能对象 / 文本图层信息（字体、内容等）

返回结构：
- mime: image/png
- template: 'psd'
- data.data_url: 合并预览图 Base64 Data URL
- data.width / height: 画布尺寸
- data.mode: 色彩模式（RGB / RGBA / CMYK）
- data.layer_count: 图层总数
- data.layers: 图层列表，每项：
    - name: 图层名
    - kind: 'pixel' | 'group' | 'smartobject' | 'type' | 'shape' | 'other'
    - visible: bool
    - opacity: 0-255
    - width / height: 图层像素尺寸 (无像素为 0)
    - offset_x / offset_y: 相对画布的偏移
    - thumbnail: Base64 Data URL (仅像素类图层)
    - text: 文本内容 (仅 type 图层)
    - font_names: 字体列表 (仅 type 图层)
- data.has_smart_object: 是否包含智能对象图层
- data.has_text_layer: 是否包含文字图层
"""
import base64
import io
import os
from typing import Any, Dict, List, Optional

from PIL import Image

from mmfb.core.handler_base import BaseHandler


PSD_EXTENSIONS = [
    ".psd",
    ".psb",
]


def _layer_kind(layer) -> str:
    """识别图层类型字符串"""
    from psd_tools.api.layers import Group, SmartObjectLayer, TypeLayer, ShapeLayer
    if isinstance(layer, TypeLayer):
        return "type"
    if isinstance(layer, SmartObjectLayer):
        return "smartobject"
    if isinstance(layer, ShapeLayer):
        return "shape"
    if isinstance(layer, Group):
        return "group"
    # PixelLayer 或普通图层
    if hasattr(layer, "topil") and layer.kind == "pixel":
        return "pixel"
    # 兜底：尝试判断是否有像素
    try:
        if layer.has_pixels():
            return "pixel"
    except Exception:
        pass
    if layer.is_group():
        return "group"
    return "other"


def _pil_to_base64(img: Image.Image, max_size: int = 256) -> str:
    """PIL Image 转 Base64 PNG，自动缩放到 max_size 边内"""
    if img is None:
        return ""
    # 确保 RGBA 或 RGB
    if img.mode not in ("RGB", "RGBA"):
        try:
            img = img.convert("RGBA")
        except Exception:
            img = img.convert("RGB")

    # 缩放
    w, h = img.size
    if w > 0 and h > 0:
        scale = min(max_size / w, max_size / h, 1.0)
        if scale < 1.0:
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            img = img.resize((new_w, new_h), Image.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return "data:image/png;base64," + encoded


def _extract_text_info(layer) -> Dict[str, Any]:
    """从 TypeLayer 提取文本信息"""
    info = {"text": "", "font_names": []}
    try:
        # .text 返回文本内容
        text = getattr(layer, "text", None)
        if text:
            if callable(text):
                text = text()
            info["text"] = str(text)[:200]  # 限制长度
    except Exception:
        pass
    try:
        fonts = getattr(layer, "font_names", None)
        if fonts:
            if callable(fonts):
                fonts = fonts()
            if isinstance(fonts, (list, tuple)):
                info["font_names"] = [str(f) for f in fonts[:10]]
    except Exception:
        pass
    return info


class PsdHandler(BaseHandler):
    """PSD / PSB 处理器

    支持的扩展名：
        .psd, .psb

    实现说明：
        - 使用 psd-tools 解析 PSD/PSB 文件结构
        - composite() 生成合并预览图（含所有可见图层）
        - 遍历图层树，对每个有像素的图层生成缩略图
        - 文本图层提取内容（最多 200 字符）
        - 智能对象图层仅提取 smart_object 元信息
    """

    extensions = PSD_EXTENSIONS

    def get_preview(self) -> Optional[Dict[str, Any]]:
        """获取 PSD/PSB 预览数据"""
        try:
            if not os.path.isfile(self.path):
                return self._error_result("file not found")

            file_size = os.path.getsize(self.path)

            try:
                from psd_tools import PSDImage
            except ImportError:
                return self._error_result("psd-tools not installed")

            try:
                psd = PSDImage.open(self.path)
            except Exception as e:
                return self._error_result(f"cannot open PSD: {e}")

            width = psd.width
            height = psd.height
            color_mode = str(psd.color_mode) if psd.color_mode else "UNKNOWN"

            # 合并预览图
            composite_data_url = ""
            try:
                composite_img = psd.composite()
                if composite_img is not None:
                    composite_data_url = _pil_to_base64(composite_img, max_size=2048)
            except Exception:
                composite_data_url = ""

            # 图层树
            layers = []
            has_smart_object = False
            has_text_layer = False
            layer_count = 0

            try:
                for layer in psd.descendants():
                    layer_count += 1
                    kind = _layer_kind(layer)
                    if kind == "smartobject":
                        has_smart_object = True
                    if kind == "type":
                        has_text_layer = True

                    layer_info: Dict[str, Any] = {
                        "name": getattr(layer, "name", ""),
                        "kind": kind,
                        "visible": getattr(layer, "visible", True),
                        "opacity": getattr(layer, "opacity", 255),
                        "width": getattr(layer, "width", 0) or 0,
                        "height": getattr(layer, "height", 0) or 0,
                        "offset_x": getattr(layer, "left", 0) or 0,
                        "offset_y": getattr(layer, "top", 0) or 0,
                    }

                    # 像素图层提取缩略图
                    if kind in ("pixel", "smartobject"):
                        try:
                            pil = layer.topil()
                            if pil is not None:
                                layer_info["thumbnail"] = _pil_to_base64(pil, max_size=256)
                        except Exception:
                            pass

                    # type 图层不尝试 topil（文本层像素化不稳定）
                    if kind == "type":
                        text_info = _extract_text_info(layer)
                        layer_info["text"] = text_info["text"]
                        layer_info["font_names"] = text_info["font_names"]

                    layers.append(layer_info)
            except Exception as e:
                layers.append({
                    "name": f"[parse error: {e}]",
                    "kind": "other",
                    "visible": True,
                    "opacity": 255,
                    "width": 0,
                    "height": 0,
                    "offset_x": 0,
                    "offset_y": 0,
                })

            result = {
                "mime": "image/png",
                "template": "psd",
                "data": {
                    "file_path": self.path,
                    "file_size": file_size,
                    "large_file": file_size > 50 * 1024 * 1024,
                    "width": width,
                    "height": height,
                    "mode": color_mode,
                    "layer_count": layer_count,
                    "has_smart_object": has_smart_object,
                    "has_text_layer": has_text_layer,
                    "composite": composite_data_url,
                    "layers": layers,
                },
                "editable": False,
            }
            return result

        except Exception as e:
            return self._error_result(str(e))

    def get_mime(self) -> str:
        """返回 PSD/PSB 对应 MIME"""
        return "image/vnd.adobe.photoshop"

    def get_edit(self) -> None:
        """PSD 不支持就地编辑"""
        return None

    def _error_result(self, message: str) -> Dict[str, Any]:
        """生成错误占位结果"""
        return {
            "mime": "image/vnd.adobe.photoshop",
            "template": "psd",
            "data": {
                "file_path": self.path,
                "file_size": 0,
                "large_file": False,
                "width": 0,
                "height": 0,
                "mode": "",
                "layer_count": 0,
                "has_smart_object": False,
                "has_text_layer": False,
                "composite": "",
                "layers": [],
            },
            "editable": False,
            "error": message,
        }
