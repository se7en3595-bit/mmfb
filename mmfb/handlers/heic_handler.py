"""HEIC / HEIF 图像格式处理器

职责：
1. 使用 pillow-heif 解码 HEIC/HEIF 为 PIL.Image
2. 复用 ImageHandler 的渲染和编辑逻辑（前端通过 data_url 渲染）
3. 提取 EXIF 元数据（相机型号/曝光/ISO/GPS 等）
4. iOS 常见格式重点测试（.heic/.heif，含 HDR/10bit）

返回结构（与 ImageHandler 一致）：
- mime: image/png
- template: 'image'
- data.data_url: base64 PNG Data URL
- data.width / height / mode / format
- data.has_exif / exif
- data.is_animated: 始终 False（HEIC 不支持动画）
- data.frame_count: 1

编辑流程：
- 预览和编辑共用 MMFBImageViewer
- 保存时根据输出路径推断格式（PNG/JPEG/WEBP 等）
- HEIC 编码暂不支持（pillow-heif 只读），保存为 PNG/JPEG
"""
import base64
import io
import os
from typing import Any, Dict, Optional

import pillow_heif
from PIL import Image, ExifTags

from mmfb.core.handler_base import BaseHandler
from mmfb.handlers.image_handler import ImageHandler, FORMAT_TO_MIME


# 注册 pillow-heif opener（全局注册一次，Pillow 即可识别 HEIC/HEIF）
pillow_heif.register_heif_opener()


# HEIC/HEIF 支持的扩展名
HEIC_EXTENSIONS = [
    ".heic",
    ".heif",
    ".hif",     # 部分相机厂商使用
    ".heics",   # HEIC 序列
    ".heifs",   # HEIF 序列
]


class HeicHandler(BaseHandler):
    """HEIC/HEIF 图像处理器

    支持的扩展名：
        .heic / .heif / .hif / .heics / .heifs

    实现说明：
        - 通过 pillow_heif.register_heif_opener() 让 Pillow 直接读取 HEIC
        - 前端复用 MMFBImageViewer（渲染 Base64 PNG）
        - EXIF 提取复用 ImageHandler._extract_exif 逻辑
        - 保存（导出）时不支持 HEIC 编码，转为 PNG/JPEG/WEBP
    """

    extensions = HEIC_EXTENSIONS

    def get_preview(self) -> Optional[Dict[str, Any]]:
        """获取 HEIC/HEIF 预览数据

        流程：
            1. HEIC → PIL.Image (通过 pillow-heif opener)
            2. 转为 PNG Base64 Data URL
            3. 提取 EXIF
            4. 返回与 ImageHandler 一致的结构
        """
        try:
            if not os.path.isfile(self.path):
                return self._error_result("file not found")

            file_size = os.path.getsize(self.path)

            with Image.open(self.path) as img:
                width, height = img.size
                mode = img.mode  # HEIC 通常为 RGB 或 RGBA（HDR 10bit 可能为 I;16）
                fmt = img.format or "HEIF"

                # 转换为 RGB（确保后续 Base64 PNG 正常生成）
                # HDR/10bit → 8bit sRGB 简单转换
                if mode == "I;16" or mode == "I;16L":
                    # 16bit 整型灰度（HDR 情况），转 8bit
                    img_8bit = img.point(lambda x: x / 256).convert("RGB")
                    img = img_8bit
                    mode = "RGB"
                elif mode not in ("RGB", "RGBA", "L", "LA"):
                    img = img.convert("RGB")
                    mode = "RGB"

                result = {
                    "mime": "image/png",
                    "template": "image",
                    "data": {
                        "file_path": self.path,
                        "file_size": file_size,
                        "width": width,
                        "height": height,
                        "mode": mode,
                        "format": fmt,
                        "large_image": False,
                        "is_animated": False,
                        "frame_count": 1,
                    },
                    "editable": True,
                }

                # EXIF 元数据提取
                exif_data = self._extract_exif(img)
                result["data"]["has_exif"] = bool(exif_data)
                result["data"]["exif"] = exif_data

                # 转 Base64 PNG（HEIC 是无损/有损压缩，转 PNG 无损保存预览）
                try:
                    data_url = self._to_base64_png(img)
                    result["data"]["data_url"] = data_url
                except Exception as e:
                    result["data"]["_base64_error"] = str(e)

                return result

        except ImportError as e:
            return self._error_result("pillow-heif not installed: " + str(e))
        except Exception as e:
            return self._error_result("HEIC decode error: " + str(e))

    def get_edit(self) -> Optional[Dict[str, Any]]:
        """获取编辑数据

        与预览数据相同，前端通过 MMFBImageViewer 渲染。
        """
        preview = self.get_preview()
        if preview is None:
            return None
        return {
            "mime": preview.get("mime", "image/png"),
            "data": preview.get("data", {}),
            "editable": True,
        }

    def get_mime(self) -> str:
        """返回 HEIC/HEIF 对应 MIME"""
        from pathlib import Path
        suffix = Path(self.path).suffix.lower()
        if suffix in (".heic", ".heics"):
            return "image/heic"
        return "image/heif"

    @staticmethod
    def apply_edit(file_path: str, operations: list, output_path: str = "") -> Dict[str, Any]:
        """执行编辑操作

        注意：pillow-heif 只支持读取，不支持编码。
        保存时根据 output_path 后缀推断格式：
            - .png → PNG
            - .jpg/.jpeg → JPEG
            - .webp → WebP
            - .heic/.heif → 降级为 PNG（不支持 HEIC 编码）
        """
        try:
            # 检查输出路径：HEIC/HEIF 编码不支持，强制改后缀
            if output_path:
                from pathlib import Path
                suffix = Path(output_path).suffix.lower()
                if suffix in (".heic", ".heif", ".hif"):
                    # 不支持写 HEIC，改为 PNG
                    output_path = str(Path(output_path).with_suffix(".png"))

            # 先用 pillow-heif 打开 HEIC（register_heif_opener 已全局注册）
            # 直接委托给 ImageHandler.apply_edit
            return ImageHandler.apply_edit(file_path, operations, output_path)

        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _extract_exif(self, img) -> Dict[str, str]:
        """从 PIL.Image 提取常用 EXIF 字段

        优先级：
        1. img._getexif() -> 旧式 dict (tag_id: int, value: ...)
        2. img.getexif() -> 新式 dict (tag_id: int, value: ...)
        3. img.info["exif"] -> raw EXIF bytes，用 piexif 解析
        """
        try:
            exif_raw = None

            # 1. 旧式 _getexif()
            exif_raw = getattr(img, "_getexif", lambda: None)()

            # 2. 如果 _getexif 返回 None，尝试 getexif()
            if not exif_raw:
                exif_raw = getattr(img, "getexif", lambda: None)()

            # 3. 如果 getexif 也返回 None，尝试 info["exif"] raw bytes
            if not exif_raw:
                info = img.info or {}
                exif_bytes = info.get("exif")
                if exif_bytes:
                    try:
                        import piexif
                        exif_dict = piexif.load(exif_bytes)
                        exif_raw = {}
                        for exif_id, tag_id in exif_dict.get("Exif", {}).items():
                            tag_name = ExifTags.Tags(tag_id).title
                            exif_raw[tag_id] = exif_dict["Exif"][exif_id]
                        for exif_id, tag_id in exif_dict.get("GPS", {}).items():
                            tag_name = ExifTags.GPSTAGS.get(exif_id, str(exif_id))
                            exif_raw[tag_id] = exif_dict["GPS"][tag_id]
                    except Exception:
                        return {}

            if not exif_raw:
                return {}

            # 解析 dict（无论是 _getexif 还是 getexif 返回的）
            result = {}
            id_to_name = {v: k for k, v in ExifTags.TAGS.items()}
            for tag_id, value in exif_raw.items():
                if isinstance(tag_id, int):
                    tag_name = id_to_name.get(tag_id, str(tag_id))
                else:
                    tag_name = str(tag_id)
                result[tag_name] = str(value)
            return result

        except Exception:
            return {}

    def _to_base64_png(self, img: Image.Image) -> str:
        """将 PIL.Image 转为 Base64 PNG Data URL"""
        buffer = io.BytesIO()
        save_img = img

        # PNG 不支持某些模式，需要转换
        if save_img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
            save_img = save_img.convert("RGB")

        save_img.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return "data:image/png;base64," + encoded

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
