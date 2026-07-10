"""光栅图像格式处理器

职责：
1. 使用 Pillow 读取图像元数据（分辨率/色深/EXIF/GIF 帧数）
2. 将图像转为 Base64 Data URL 由前端直接渲染
3. 支持 PNG/JPG/BMP/GIF/TIFF/ICO/WebP
4. GIF 动画返回帧数和时长信息，前端决定是否逐帧加载
5. 支持编辑操作（裁剪/旋转/翻转/缩放/滤镜/亮度/对比度）

返回结构：
- mime: image/png (具体格式的 MIME)
- template: 'image'
- data.data_url: base64 编码的 Data URL (data:image/png;base64,...)
- data.width / height: 像素尺寸
- data.mode: Pillow 模式（RGBA/RGB/P 等）
- data.has_exif: 是否包含 EXIF 数据
- data.exif: EXIF 字典（部分关键字段）
- data.is_animated: GIF/WebP 动画帧
- data.frame_count: 帧数
- editable: True（支持裁剪/旋转/缩放/滤镜/亮度对比度调整）

编辑操作（apply_edit）：
- crop:     {"op":"crop","left":int,"top":int,"right":int,"bottom":int}
- rotate:   {"op":"rotate","angle":int}   // 90/180/270
- flip_h:   {"op":"flip_h"}
- flip_v:   {"op":"flip_v"}
- resize:   {"op":"resize","width":int,"height":int,"keep_ratio":bool}
- filter:   {"op":"filter","name":"blur|sharpen|contour|emboss|smooth|edge_enhance"}
- brightness: {"op":"brightness","factor":float}    // 1.0 = 不变, <1 变暗, >1 变亮
- contrast:   {"op":"contrast","factor":float}
"""
import base64
import io
import json
import os
from typing import Any, Dict, Optional

from PIL import Image, ImageFilter, ImageEnhance, ExifTags

from mmfb.core.handler_base import BaseHandler


# 支持的光栅格式扩展名
IMAGE_EXTENSIONS = [
    ".png", ".jpg", ".jpeg", ".jpe", ".jfif",
    ".bmp", ".dib",
    ".gif",
    ".tiff", ".tif",
    ".ico",
    ".webp",
]

# 扩展名 → MIME 类型映射
MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".jpe": "image/jpeg",
    ".jfif": "image/jpeg",
    ".bmp": "image/bmp",
    ".dib": "image/bmp",
    ".gif": "image/gif",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".ico": "image/x-icon",
    ".webp": "image/webp",
}

# 当前文件对应的 MIME（用于 Base64 前缀）
FORMAT_TO_MIME = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "BMP": "image/bmp",
    "GIF": "image/gif",
    "TIFF": "image/tiff",
    "ICO": "image/x-icon",
    "WEBP": "image/webp",
}

# 大文件阈值：20MB (图像转为 Base64 会膨胀 33%)
IMAGE_SIZE_THRESHOLD = 20 * 1024 * 1024

# 支持的滤镜名称
FILTER_MAP = {
    "blur": ImageFilter.GaussianBlur(radius=2),
    "sharpen": ImageFilter.SHARPEN,
    "contour": ImageFilter.CONTOUR,
    "emboss": ImageFilter.EMBOSS,
    "smooth": ImageFilter.SMOOTH,
    "edge_enhance": ImageFilter.EDGE_ENHANCE,
}


class ImageHandler(BaseHandler):
    """光栅图像处理器

    支持的扩展名：
        PNG/JPG/BMP/GIF/TIFF/ICO/WebP 及其大小写变体

    实现说明：
        - 后端读取图像元数据，计算 Base64 Data URL
        - 前端通过 img 标签 / canvas 渲染
        - 大图 (>20MB) 标记 large_image，前端可启用渐进加载
        - GIF 动画返回帧数，前端可按需逐帧解码
        - 编辑操作通过 apply_edit() 执行，保存到原文件或指定路径
    """

    extensions = IMAGE_EXTENSIONS

    def get_preview(self) -> Optional[Dict[str, Any]]:
        """获取图像预览数据

        返回字典包含图像尺寸、元数据、Base64 Data URL。
        大图仅在元信息模式下不内嵌 Base64。
        """
        try:
            if not os.path.isfile(self.path):
                return self._error_result("file not found")

            file_size = os.path.getsize(self.path)
            is_large = file_size > IMAGE_SIZE_THRESHOLD

            with Image.open(self.path) as img:
                width, height = img.size
                mode = img.mode
                fmt = img.format or "UNKNOWN"

                # 基础元数据
                result = {
                    "mime": FORMAT_TO_MIME.get(fmt, "image/png"),
                    "template": "image",
                    "data": {
                        "file_path": self.path,
                        "file_size": file_size,
                        "width": width,
                        "height": height,
                        "mode": mode,
                        "format": fmt,
                        "large_image": is_large,
                    },
                    "editable": True,
                }

                # EXIF 提取 (仅 JPEG/TIFF 等相机格式)
                exif_data = self._extract_exif(img)
                result["data"]["has_exif"] = bool(exif_data)
                result["data"]["exif"] = exif_data

                # GIF / WebP 动画帧信息
                is_animated = False
                frame_count = 1
                if fmt == "GIF":
                    is_animated = getattr(img, "is_animated", False)
                    frame_count = getattr(img, "n_frames", 1)
                elif fmt == "WEBP":
                    is_animated = getattr(img, "is_animated", False)
                    frame_count = getattr(img, "n_frames", 1)

                result["data"]["is_animated"] = is_animated
                result["data"]["frame_count"] = frame_count

                # 非大文件时内嵌 Base64
                if not is_large:
                    try:
                        data_url = self._to_base64(img, fmt)
                        result["data"]["data_url"] = data_url
                    except Exception as e:
                        result["data"]["_base64_error"] = str(e)

                return result

        except ImportError:
            return self._error_result("Pillow not installed")
        except Exception as e:
            return self._error_result(str(e))

    def get_edit(self) -> Optional[Dict[str, Any]]:
        """获取编辑数据

        返回图像编辑所需的数据（与预览数据相同，标记可读和可编辑）。
        文件不存在或出错时返回 None。
        """
        preview = self.get_preview()
        if preview is None:
            return None
        if isinstance(preview, dict) and preview.get("error"):
            return None
        return {
            "mime": preview.get("mime", "image/png"),
            "data": preview.get("data", {}),
            "editable": True,
        }

    def get_mime(self) -> str:
        """返回文件对应的 MIME 类型"""
        from pathlib import Path
        suffix = Path(self.path).suffix.lower()
        return MIME_MAP.get(suffix, "image/png")

    @staticmethod
    def apply_edit(file_path: str, operations: list, output_path: str = "") -> Dict[str, Any]:
        """执行编辑操作并保存

        参数：
            file_path: 源文件路径
            operations: 操作列表，每项 {"op": "...", ...}
            output_path: 输出路径，为空则覆盖原文件

        返回：
            {"ok": true, "path": "...", "width": int, "height": int}
            或 {"ok": false, "error": "..."}
        """
        try:
            if not os.path.isfile(file_path):
                return {"ok": False, "error": "file not found"}

            if not output_path:
                output_path = file_path

            img = Image.open(file_path)

            # 处理每项操作
            for op in operations:
                op_type = op.get("op", "")

                if op_type == "crop":
                    left = max(0, int(op.get("left", 0)))
                    top = max(0, int(op.get("top", 0)))
                    right = min(img.width, int(op.get("right", img.width)))
                    bottom = min(img.height, int(op.get("bottom", img.height)))
                    if right <= left or bottom <= top:
                        continue
                    img = img.crop((left, top, right, bottom))

                elif op_type == "rotate":
                    angle = int(op.get("angle", 0)) % 360
                    if angle == 90:
                        img = img.transpose(Image.Transpose.ROTATE_270)
                    elif angle == 180:
                        img = img.transpose(Image.Transpose.ROTATE_180)
                    elif angle == 270:
                        img = img.transpose(Image.Transpose.ROTATE_90)

                elif op_type == "flip_h":
                    img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

                elif op_type == "flip_v":
                    img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

                elif op_type == "resize":
                    target_w = int(op.get("width", img.width))
                    target_h = int(op.get("height", img.height))
                    keep_ratio = bool(op.get("keep_ratio", True))
                    if keep_ratio:
                        img.thumbnail((target_w, target_h), Image.LANCZOS)
                    else:
                        img = img.resize((target_w, target_h), Image.LANCZOS)

                elif op_type == "filter":
                    filt_name = op.get("name", "")
                    filt = FILTER_MAP.get(filt_name)
                    if filt is not None:
                        img = img.filter(filt)

                elif op_type == "brightness":
                    factor = float(op.get("factor", 1.0))
                    enhancer = ImageEnhance.Brightness(img)
                    img = enhancer.enhance(factor)

                elif op_type == "contrast":
                    factor = float(op.get("factor", 1.0))
                    enhancer = ImageEnhance.Contrast(img)
                    img = enhancer.enhance(factor)

                elif op_type == "auto_contrast":
                    from PIL import ImageOps
                    img = ImageOps.autocontrast(img)

            # 保存
            save_fmt, mime, save_kwargs = _infer_save_params(output_path, img)

            # JPEG 不支持 RGBA，需先转 RGB
            if save_fmt == "JPEG" and img.mode == "RGBA":
                # 透明背景使用白色
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
            elif save_fmt == "JPEG" and img.mode == "P":
                img = img.convert("RGB")

            img.save(output_path, format=save_fmt, **save_kwargs)

            return {
                "ok": True,
                "path": output_path,
                "width": img.width,
                "height": img.height,
                "format": save_fmt,
            }

        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _extract_exif(self, img) -> Dict[str, str]:
        """从 PIL.Image 提取常用 EXIF 字段"""
        try:
            exif_raw = img._getexif()
            if not exif_raw:
                return {}

            result = {}
            desired_tags = {
                "Make": "make",
                "Model": "model",
                "DateTime": "datetime",
                "DateTimeOriginal": "datetime_original",
                "ExposureTime": "exposure_time",
                "FNumber": "f_number",
                "ISOSpeedRatings": "iso",
                "FocalLength": "focal_length",
                "LensModel": "lens_model",
                "Orientation": "orientation",
                "Software": "software",
            }

            id_to_name = {v: k for k, v in ExifTags.TAGS.items()}

            for tag_id, value in exif_raw.items():
                tag_name = id_to_name.get(tag_id, str(tag_id))
                if tag_name in desired_tags:
                    result[desired_tags[tag_name]] = str(value)

            return result
        except Exception:
            return {}

    def _to_base64(self, img, fmt: str) -> str:
        """将 PIL.Image 转为 Base64 Data URL"""
        buffer = io.BytesIO()

        save_fmt = fmt if fmt in ("PNG", "JPEG", "GIF", "WEBP", "TIFF") else "PNG"
        mime = FORMAT_TO_MIME.get(save_fmt, "image/png")

        save_img = img
        if save_fmt == "JPEG" and img.mode in ("RGBA", "P"):
            save_img = img.convert("RGB")

        save_kwargs = {}
        if save_fmt == "JPEG":
            save_kwargs["quality"] = 90
        elif save_fmt == "WEBP":
            save_kwargs["quality"] = 85

        # 动画 GIF：仅保存第一帧作为预览
        if save_fmt == "GIF" and getattr(img, "is_animated", False):
            save_img = img.copy()
            save_img.seek(0)

        save_img.save(buffer, format=save_fmt, **save_kwargs)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return "data:" + mime + ";base64," + encoded

    def _error_result(self, message: str) -> Dict[str, Any]:
        """生成错误占位结果"""
        return {
            "mime": "image/png",
            "template": "image",
            "data": {
                "file_path": self.path,
                "file_size": 0,
                "width": 0,
                "height": 0,
                "mode": "",
                "format": "",
                "large_image": False,
                "has_exif": False,
                "exif": {},
                "is_animated": False,
                "frame_count": 1,
            },
            "editable": False,
            "error": message,
        }


def _infer_save_params(path: str, img: Image.Image):
    """根据路径推断保存格式、MIME 和参数"""
    suffix = os.path.splitext(path)[1].upper().lstrip(".")
    if suffix in ("JPG", "JPEG", "JPE", "JFIF"):
        return "JPEG", "image/jpeg", {"quality": 92}
    elif suffix == "PNG":
        return "PNG", "image/png", {}
    elif suffix == "WEBP":
        return "WEBP", "image/webp", {"quality": 85}
    elif suffix == "GIF":
        return "GIF", "image/gif", {}
    elif suffix in ("TIF", "TIFF"):
        return "TIFF", "image/tiff", {}
    elif suffix == "BMP":
        return "BMP", "image/bmp", {}
    else:
        return "PNG", "image/png", {}
