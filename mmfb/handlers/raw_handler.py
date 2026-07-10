"""相机 RAW 格式处理器

职责：
1. 使用 rawpy 解码 Canon CR2 / Nikon NEF / Sony ARW / Fuji RAF / DNG /
   Olympus ORF / Panasonic RW2 / Pentax PEF 等相机 RAW
2. 提取内嵌 JPEG 预览或 rawpy.postprocess() 转 PIL.Image
3. 提取 EXIF 元数据（相机型号/镜头/曝光/ISO/GPS 等）
4. 复用 MMFBImageViewer 渲染（前端通过 data_url 渲染 Base64 PNG）

返回结构（与 ImageHandler 一致）：
- mime: image/png
- template: 'image'
- data.data_url: base64 PNG Data URL
- data.width / height / mode / format
- data.has_exif / exif
- data.is_animated: 始终 False
- data.frame_count: 1
- data.raw_format: 相机 RAW 标识字符串

编辑流程：
- 预览和编辑共用 MMFBImageViewer
- 保存时不支持 RAW 编码，导出为 PNG/JPEG
"""
import base64
import io
import os
from typing import Any, Dict, Optional

import numpy as np
import rawpy
from PIL import Image, ExifTags

from mmfb.core.handler_base import BaseHandler


# 支持的 RAW 格式扩展名（23 种）
RAW_EXTENSIONS = [
    ".cr2",   # Canon RAW 2
    ".cr3",   # Canon RAW 3
    ".crw",   # Canon RAW (legacy)
    ".nef",   # Nikon Electronic Format
    ".nrw",   # Nikon (Coolpix)
    ".arw",   # Sony Alpha RAW
    ".arq",   # Sony RAW (sensor)
    ".srf",   # Sony RAW Format
    ".sr2",   # Sony RAW 2
    ".dng",   # Digital Negative (Adobe / 部分相机)
    ".orf",   # Olympus RAW Format
    ".rw2",   # Panasonic RAW
    ".pef",   # Pentax Electronic Format
    ".ptx",   # Pentax (另一种)
    ".raf",   # Fuji RAW Format
    ".x3f",   # Sigma X3F
    ".3fr",   # Hasselblad RAW
    ".fff",   # Hasselblad (另一格式)
    ".iiq",   # Phase One
    ".mos",   # Leaf
    ".rwl",   # Leica
    ".raw",   # 通用 RAW (部分相机)
]


class RawHandler(BaseHandler):
    """相机 RAW 格式处理器

    支持的扩展名（23 种）：
        CR2/CR3/CRW/NEF/NRW/ARW/ARQ/SRF/SR2/DNG/ORF/RW2/PEF/PTX/RAF/X3F/3FR/FFF/IIQ/MOS/RWL/RAW

    实现说明：
        - 优先使用 extract_thumb() 获取内嵌 JPEG 预览（速度快、省内存）
        - 预览图尺寸不足时回退到 rawpy.postprocess() 完整解码
        - 完整解码使用 Camera White Balance、sRGB 色彩空间、8bit 输出
        - EXIF 通过 rawpy 元数据字段 + 内嵌 JPEG 预览的 EXIF 提取
        - 前端复用 MMFBImageViewer（渲染 Base64 PNG）
    """

    extensions = RAW_EXTENSIONS

    def get_preview(self) -> Optional[Dict[str, Any]]:
        """获取 RAW 预览数据

        流程：
            1. rawpy 解码 RAW
            2. 尝试 extract_thumb() 获取内嵌 JPEG 预览
            3. 预览尺寸不足时回退到 rawpy.postprocess() 完整解码
            4. 转 PNG Base64 Data URL
            5. 提取 EXIF 元数据
        """
        try:
            if not os.path.isfile(self.path):
                return self._error_result("file not found")

            file_size = os.path.getsize(self.path)

            with rawpy.imread(self.path) as raw:
                raw_format = self._detect_raw_format(raw)

                # 提取 EXIF
                exif_data = self._extract_metadata(raw)

                # 策略 1：提取内嵌 JPEG 预览（更快）
                img = self._try_extract_thumb(raw)

                # 策略 2：回退到完整 postprocess
                if img is None:
                    img = self._postprocess_raw(raw)

                if img is None:
                    return self._error_result("RAW decode failed")

                width, height = img.size
                mode = img.mode

                result = {
                    "mime": "image/png",
                    "template": "image",
                    "data": {
                        "file_path": self.path,
                        "file_size": file_size,
                        "width": width,
                        "height": height,
                        "mode": mode,
                        "format": raw_format,
                        "raw_format": raw_format,
                        "large_image": False,
                        "is_animated": False,
                        "frame_count": 1,
                        "raw_decoded": True,
                    },
                    "editable": False,
                }

                # EXIF 元数据
                result["data"]["has_exif"] = bool(exif_data)
                result["data"]["exif"] = exif_data

                # 转 Base64 PNG
                try:
                    data_url = self._to_base64_png(img)
                    result["data"]["data_url"] = data_url
                except Exception as e:
                    result["data"]["_base64_error"] = str(e)

                return result

        except ImportError as e:
            return self._error_result("rawpy not installed: " + str(e))
        except Exception as e:
            err_str = str(e)
            if "unsupported" in err_str.lower():
                return self._error_result("unsupported RAW format")
            if "invalid" in err_str.lower() or "corrupt" in err_str.lower():
                return self._error_result("invalid or corrupt RAW file")
            return self._error_result("RAW decode error: " + err_str)

    def get_edit(self) -> Optional[Dict[str, Any]]:
        """RAW 格式暂不支持就地编辑，返回 None"""
        return None

    def get_mime(self) -> str:
        """返回 RAW 对应 MIME"""
        return "image/x-raw"

    def _detect_raw_format(self, raw: rawpy.RawPy) -> str:
        """根据文件扩展名 + rawpy 属性识别 RAW 格式"""
        ext = os.path.splitext(self.path)[1].lower()
        format_map = {
            ".cr2": "CR2", ".cr3": "CR3", ".crw": "CRW",
            ".nef": "NEF", ".nrw": "NRW",
            ".arw": "ARW", ".arq": "ARQ", ".srf": "SRF", ".sr2": "SR2",
            ".dng": "DNG",
            ".orf": "ORF", ".rw2": "RW2",
            ".pef": "PEF", ".ptx": "PTX",
            ".raf": "RAF",
            ".x3f": "X3F", ".3fr": "3FR", ".fff": "FFF",
            ".iiq": "IIQ", ".mos": "MOS", ".rwl": "RWL",
            ".raw": "RAW",
        }
        fmt = format_map.get(ext, "RAW")

        try:
            if hasattr(raw, 'color_desc') and raw.color_desc:
                desc = raw.color_desc.decode('ascii', errors='replace')
                if desc and desc not in ('RGBG', 'RGGB', 'BGGR', 'GRBG'):
                    fmt += " (" + desc + ")"
        except Exception:
            pass

        return fmt

    def _try_extract_thumb(self, raw: rawpy.RawPy) -> Optional[Image.Image]:
        """尝试提取内嵌 JPEG 预览

        返回 PIL.Image 或 None（预览不存在或提取失败）。
        """
        try:
            thumb = raw.extract_thumb()
            if thumb is None:
                return None

            thumb_format, thumb_data = thumb

            if thumb_format == rawpy.ThumbFormat.JPEG:
                img = Image.open(io.BytesIO(bytes(thumb_data)))
                return img

            if thumb_format == rawpy.ThumbFormat.BITMAP:
                try:
                    img = Image.open(io.BytesIO(thumb_data))
                    return img
                except Exception:
                    return None

            return None
        except Exception:
            return None

    def _postprocess_raw(self, raw: rawpy.RawPy) -> Optional[Image.Image]:
        """完整 postprocess RAW

        使用 Camera White Balance、sRGB 色彩空间、8bit 输出。
        返回 PIL.Image（RGB）。
        """
        try:
            rgb = raw.postprocess(
                use_camera_wb=True,
                output_color=rawpy.ColorSpace.sRGB,
                output_bps=8,
                no_auto_bright=True,
                gamma=(1.0, 1.0),
            )

            if isinstance(rgb, np.ndarray):
                if rgb.dtype == np.uint16:
                    rgb = (rgb / 256).astype(np.uint8)
                img = Image.fromarray(rgb, mode="RGB")
                return img

            return None
        except Exception:
            return None

    def _extract_metadata(self, raw: rawpy.RawPy) -> Dict[str, str]:
        """从 rawpy.RawPy 提取相机元数据"""
        result = {}

        try:
            # 传感器/色彩阵列
            if hasattr(raw, 'color_desc') and raw.color_desc:
                desc = raw.color_desc.decode('ascii', errors='replace')
                result["color_filter_array"] = desc

            # raw 传感器尺寸（可见区域）
            if hasattr(raw, 'raw_image_visible'):
                h, w = raw.raw_image_visible.shape[:2]
                result["sensor_width"] = str(w)
                result["sensor_height"] = str(h)

            # 输出尺寸
            if hasattr(raw, 'sizes'):
                sz = raw.sizes
                if hasattr(sz, 'iwidth') and hasattr(sz, 'iheight'):
                    result["output_width"] = str(sz.iwidth)
                    result["output_height"] = str(sz.iheight)
                    if hasattr(sz, 'flip') and sz.flip != 0:
                        result["flipped"] = str(sz.flip)

            # Black/White level
            if hasattr(raw, 'black_level_per_channel'):
                bl = raw.black_level_per_channel
                if isinstance(bl, (list, tuple, np.ndarray)) and len(bl) > 0:
                    try:
                        result["black_level"] = str(int(bl[0]))
                    except Exception:
                        pass

            if hasattr(raw, 'camera_white_level_per_channel'):
                wl = raw.camera_white_level_per_channel
                try:
                    if isinstance(wl, (list, tuple, np.ndarray)) and len(wl) > 0:
                        result["white_level"] = str(int(wl[0]))
                    elif isinstance(wl, (int, float)):
                        result["white_level"] = str(int(wl))
                except Exception:
                    pass

            # Camera white balance (R/G/B gains)
            if hasattr(raw, 'camera_whitebalance'):
                wb = raw.camera_whitebalance
                if isinstance(wb, (list, tuple, np.ndarray)) and len(wb) >= 3:
                    try:
                        result["camera_wb"] = (
                            "R=" + self._fmt_float(wb[0]) +
                            " G=" + self._fmt_float(wb[1]) +
                            " B=" + self._fmt_float(wb[2])
                        )
                    except Exception:
                        pass

            # num_colors
            if hasattr(raw, 'num_colors'):
                result["num_colors"] = str(raw.num_colors)

            # 尝试从内嵌 JPEG 预览提取 EXIF
            self._extract_exif_from_thumb(raw, result)

        except Exception:
            pass

        return result

    @staticmethod
    def _fmt_float(v) -> str:
        try:
            return f"{float(v):.4g}"
        except Exception:
            return str(v)

    @staticmethod
    def _extract_exif_from_thumb(raw: rawpy.RawPy, result: Dict[str, str]) -> None:
        """从内嵌 JPEG 预览提取 EXIF（相机型号/参数等）"""
        try:
            thumb = raw.extract_thumb()
        except Exception:
            return

        if thumb is None:
            return

        thumb_format, thumb_data = thumb

        if thumb_format != rawpy.ThumbFormat.JPEG:
            return

        try:
            thumb_img = Image.open(io.BytesIO(bytes(thumb_data)))
            exif_raw = thumb_img._getexif()
            if not exif_raw:
                return

            desired_tags = {
                "Make": "make",
                "Model": "model",
                "DateTimeOriginal": "datetime_original",
                "ExposureTime": "exposure_time",
                "FNumber": "f_number",
                "ISOSpeedRatings": "iso",
                "FocalLength": "focal_length",
                "LensModel": "lens_model",
                "Software": "software",
                "ExposureBiasValue": "exposure_bias",
                "Flash": "flash",
                "WhiteBalance": "white_balance",
                "MeteringMode": "metering_mode",
                "ExposureProgram": "exposure_program",
            }

            id_to_name = {v: k for k, v in ExifTags.TAGS.items()}
            for tag_id, value in exif_raw.items():
                tag_name = id_to_name.get(tag_id, str(tag_id))
                if tag_name in desired_tags:
                    key = desired_tags[tag_name]
                    if tag_name == "ExposureTime":
                        result[key] = RawHandler._format_exposure_time(value)
                    elif tag_name == "FNumber":
                        result[key] = RawHandler._format_fnumber(value)
                    else:
                        result[key] = str(value)
        except Exception:
            pass

    @staticmethod
    def _format_exposure_time(value) -> str:
        try:
            if isinstance(value, tuple) and len(value) == 2:
                n, d = value
                if d == 1:
                    return str(n) + "s"
                if n == 1:
                    return "1/" + str(d) + "s"
                sec = n / d
                if sec < 1.0:
                    return "1/" + str(int(round(1/sec))) + "s"
                return f"{sec:.2f}s"
            v = float(value)
            if v < 1.0:
                return "1/" + str(int(round(1/v))) + "s"
            return f"{v:.2f}s"
        except Exception:
            return str(value)

    @staticmethod
    def _format_fnumber(value) -> str:
        try:
            if isinstance(value, tuple) and len(value) == 2:
                n, d = value
                return "f/" + f"{n/d:.1f}"
            v = float(value)
            return "f/" + f"{v:.1f}"
        except Exception:
            return str(value)

    def _to_base64_png(self, img: Image.Image) -> str:
        buffer = io.BytesIO()
        save_img = img

        if save_img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
            save_img = save_img.convert("RGB")

        save_img.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return "data:image/png;base64," + encoded

    def _error_result(self, message: str) -> Dict[str, Any]:
        return {
            "mime": "image/png",
            "template": "image",
            "data": {
                "file_path": self.path,
                "file_size": 0,
                "width": 0,
                "height": 0,
                "mode": "",
                "format": "RAW",
                "raw_format": "RAW",
                "large_image": False,
                "has_exif": False,
                "exif": {},
                "is_animated": False,
                "frame_count": 1,
                "raw_decoded": False,
            },
            "editable": False,
            "error": message,
        }
