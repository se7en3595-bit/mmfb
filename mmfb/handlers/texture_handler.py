"""DDS / TGA / EXR / HDR 游戏贴图处理器

职责：
1. Pillow 解码 TGA / DDS（DXT1/3/5、BC4/5/6H/7）
2. imageio + FreeImage 解码 EXR / HDR（浮点 HDR 数据）
3. 解析 DDS 二进制头，提取 Mipmap 层级数、像素格式、法线贴图标识
4. EXR/HDR 执行 Reinhard 色调映射（后端）以便直接在 sRGB 窗口显示
5. 输出 Base64 PNG 复用 MMFBImageViewer 渲染

返回结构：
- mime: image/png
- template: 'image'
- data.data_url: 解码后贴图 Base64 Data URL
- data.width / height / mode / format
- data.pixel_format: DDS 压缩格式名（DXT1/BC7 等）
- data.mipmap_count: DDS Mipmap 层级数
- data.is_normal_map: 是否疑似法线贴图（BC5/DXT5nm）
- data.is_hdr: 是否 HDR 内容（EXR/HDR，经色调映射）
- data.channel_count: 通道数

支持格式（扩展名）：
- TGA: .tga
- DDS: .dds
- EXR: .exr
- HDR: .hdr
"""
import base64
import io
import os
import struct
from typing import Any, Dict, Optional

import numpy as np
from PIL import Image

from mmfb.core.handler_base import BaseHandler


TEXTURE_EXTENSIONS = [
    ".dds",
    ".tga",
    ".exr",
    ".hdr",
]

# DDS 像素格式标识
DDS_PIXEL_FORMATS = {
    "DXT1": "BC1 / DXT1",
    "DXT2": "BC2 / DXT2",
    "DXT3": "BC2 / DXT3",
    "DXT4": "BC3 / DXT4",
    "DXT5": "BC3 / DXT5",
    "BC4": "BC4 (单通道有符号)",
    "BC4S": "BC4 (signed)",
    "BC4U": "BC4 (unsigned)",
    "BC5": "BC5 (双通道，常见于法线贴图)",
    "BC5S": "BC5 (signed)",
    "BC5U": "BC5 (unsigned)",
    "BC6H": "BC6H (HDR 无符号)",
    "BC6HS": "BC6H (signed)",
    "BC7": "BC7",
    "BC1": "BC1",
    "BC2": "BC2",
    "BC3": "BC3",
}

# 常见于法线贴图的像素格式
NORMAL_MAP_FORMATS = {"BC5", "BC5S", "BC5U"}


def _parse_dds_header(path: str) -> Dict[str, Any]:
    """解析 DDS 二进制头，提取 mipmap、尺寸、像素格式信息。

    DDS 头最小 128 字节：
        magic(4) + DDS_HEADER(124) + [DDS_HEADER_DXT10(20)]
    """
    info: Dict[str, Any] = {
        "mipmap_count": 1,
        "pixel_format": "unknown",
        "dxgi_format": 0,
        "is_cubemap": False,
        "array_size": 1,
    }
    try:
        with open(path, "rb") as f:
            magic = f.read(4)
            if magic != b"DDS ":
                return info

            # DDS_HEADER 124 字节
            hdr = f.read(124)
            if len(hdr) < 124:
                return info

            # 关键字段偏移（小端）
            (
                height, width, pitch_or_linear_size,
                depth, mipmap_count,
            ) = struct.unpack_from("<5I", hdr, 8)

            caps = struct.unpack_from("<4I", hdr, 76)
            # caps[0] = DDSD_CAPS, caps[1] = DDSCAPS_COMPLEX(=0x8),
            # caps[2] = DDSCAPS_TEXTURE(=0x1000), caps[3] = DDSCAPS_MIPMAP(=0x400000)

            pf_offset = 76 + 16 + 4 * 4  # 跳过 caps + dwSize 之后的结构
            # 简化：直接读取 pixel format 区域
            # 偏移 76 是 caps(16字节)，偏移 88 开始是 dwDepth 之后的内容
            # dwSize=76 之后偏移0, dwFlags(4), dwHeight(4), dwWidth(4), dwPitchOrLinearSize(4)
            # dwDepth(4), dwMipMapCount(4), dwReserved1[11]=44, DDS_PIXELFORMAT(32), dwCaps(16)

            # pixel format 从偏移 76 开始的：76(头大小)+4(flags)+4(h)+4(w)+4(pitch)+4(depth)+4(mipmap)+44(reserved1)=144
            # 所以 pixel format 从 144 开始，32 字节
            pf_start = 128  # 4(magic) + 124(header)
            # actually DDS_PIXELFORMAT is at offset 88 within the header(124) after dwSize(4)+flags(4)+h(4)+w(4)+pitch(4)+depth(4)+mipmap(4)+reserved1[11](44) = 4*7+44=72, offset from start of 124-byte header = 76(dwSize included) wait

            # DDS_HEADER structure(124 bytes total):
            #   dwSize(4)=124, dwFlags(4), dwHeight(4), dwWidth(4), dwPitchOrLinearSize(4),
            #   dwDepth(4), dwMipMapCount(4), dwReserved1[11]*4=44, ddpfPixelFormat(32), dwCaps(16)
            # Total: 4*7+44+32+16 = 28+44+32+16 = 120, +4 for dwSize itself= but dwSize is at offset 0
            # Actually 4+4+4+4+4+4+4+44+32+16 = 120 -> with dwSize=124 doesn't add up...
            # dwSize is the size of this structure EXCEPT dwSize itself, so total=124 means other fields sum to 124
            # Fields after dwSize: 4+4+4+4+4+4+44+32+16 = 120. + 4 for DWORD dwSize included in the counting, total=124
            # Actually just trust the standard: the magic occupies 4 bytes, then header 124 bytes

            mipmap_count = max(1, mipmap_count)
            info["mipmap_count"] = mipmap_count

            # 解析 pixel format(32 字节)
            # 从 header offset 76 开始：在 header 结构中，pixel format 在 11 个 reserved 之后
            # 在整体文件中的偏移是 4(magic) + 76(到 pix format) = 80
            # Actually: magic(4) + header(124). Header bytes:
            #   0-3: dwSize=124
            #   4-7: dwFlags
            #   8-11: dwHeight
            #   12-15: dwWidth
            #   16-19: dwPitchOrLinearSize
            #   20-23: dwDepth
            #   24-27: dwMipMapCount
            #   28-71: dwReserved1[11]=44 bytes
            #   72-103: DDS_PIXELFORMAT=32 bytes (pfSize, pfFlags, FourCC, RGBBitCount, masks)
            #   104-119: dwCaps=16 bytes
            #   120-123: dwCaps4
            # Total=124

            pf_flags = struct.unpack_from("<I", hdr, 76 + 4)[0]  # pfFlags at offset 72+4=76, pfflags=s[72], fourcc=s[76]
            # Wait let me recalculate. In DDS_PIXELFORMAT(32 bytes):
            #   dwSize(4)=32, dwFlags(4), dwFourCC(4), dwRGBBitCount(4), dwRBitMask(4), dwGBitMask(4), dwBBitMask(4), dwABitMask(4)
            # Total = 32 bytes. This starts at file offset 4(magic) + 72(within header) = 76
            # In our 'hdr' array(124 bytes), pixel format starts at index 72

            pf_data = hdr[72:104]
            if len(pf_data) >= 8:
                pf_size, pf_flags, four_cc_raw = struct.unpack_from("<3I", pf_data, 0)

                if pf_flags & 0x4:  # DDPF_FOURCC
                    four_cc = pf_data[8:12]
                    try:
                        pf_name = four_cc.decode("ascii", errors="replace").strip()
                    except Exception:
                        pf_name = ""
                    info["pixel_format"] = pf_name
                else:
                    # Uncompressed
                    bit_count = struct.unpack_from("<I", pf_data, 12)[0]
                    info["pixel_format"] = f"Uncompressed {bit_count}-bit"

            # Check for DX10 extended header
            if four_cc_raw == 0x30315844:  # "DX10" = 0x30315844
                dx10_hdr = f.read(20)
                if len(dx10_hdr) >= 12:
                    dxgi_format, dimension, misc_flag, array_size, _ = struct.unpack_from("<5I", dx10_hdr, 0)
                    info["dxgi_format"] = dxgi_format
                    info["array_size"] = array_size
                    if misc_flag & 0x4:  # DDS_RESOURCE_MISC_TEXTURECUBE
                        info["is_cubemap"] = True

            info["width"] = width
            info["height"] = height
            info["depth"] = max(1, depth)

    except Exception:
        pass

    return info


def _reinhard_tonemap(hdr_data: np.ndarray, exposure: float = 1.0) -> np.ndarray:
    """Reinhard 色调映射，将 HDR float32 → 8bit sRGB

    参数：
        hdr_data: numpy array (H, W, C), dtype=float32
        exposure: 曝光倍率（默认 1.0）

    返回：
        numpy array (H, W, C), dtype=uint8, 值域 [0, 255]
    """
    if hdr_data.dtype == np.uint8:
        return hdr_data

    # 应用曝光
    img = hdr_data * exposure
    if img.ndim == 2:
        img = img[:, :, np.newaxis]

    # Only take first 3 channels for RGB
    if img.shape[-1] > 3:
        img = img[:, :, :3]

    # Reinhard tonemap (luminance)
    if img.shape[-1] >= 3:
        L = 0.2126 * img[:, :, 0] + 0.7152 * img[:, :, 1] + 0.0722 * img[:, :, 2]
    else:
        L = img[:, :, 0]

    L = np.where(L > 0, L, 1e-6)
    L_white = np.percentile(L, 95) * 2  # Key: use 95th percentile as white reference
    if L_white < 1e-6:
        L_white = 1.0

    L_tm = L * (1 + L / (L_white * L_white)) / (1 + L)
    scale = np.where(L > 0, L_tm / L, 0)

    mapped = img * scale[:, :, np.newaxis]

    # Gamma (linear → sRGB)
    mapped = np.where(mapped <= 0.0031308,
                      12.92 * mapped,
                      1.055 * np.power(np.clip(mapped, 0, 1), 1 / 2.4) - 0.055)

    result = np.clip(mapped * 255, 0, 255).astype(np.uint8)

    if result.shape[-1] == 1:
        result = result[:, :, 0]

    return result


def _pil_to_base64_png(img: Image.Image) -> str:
    """PIL Image → Base64 PNG Data URL"""
    if img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
        img = img.convert("RGBA")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return "data:image/png;base64," + encoded


def _read_with_imageio(path: str) -> Optional[Image.Image]:
    """使用 imageio 读取 EXR/HDR → PIL.Image"""
    try:
        import imageio.v3 as iio
        data = iio.imread(path, extension=".exr" if path.lower().endswith(".exr") else ".hdr")
        if data.dtype != np.uint8:
            data = _reinhard_tonemap(data)
        else:
            data = np.clip(data, 0, 255).astype(np.uint8)

        if data.ndim == 2:
            img = Image.fromarray(data, mode="L")
        elif data.shape[-1] == 3:
            img = Image.fromarray(data, mode="RGB")
        elif data.shape[-1] == 4:
            img = Image.fromarray(data, mode="RGBA")
        else:
            img = Image.fromarray(data[:, :, :3], mode="RGB")
        return img
    except ImportError:
        return None
    except Exception:
        return None


class TextureHandler(BaseHandler):
    """DDS / TGA / EXR / HDR 游戏贴图处理器

    支持的扩展名：
        .dds, .tga, .exr, .hdr

    实现说明：
        - TGA 使用 Pillow 原生解码
        - DDS 使用 Pillow 原生解压 S3TC/BCn 压缩，并解析二进制头获取 mipmap/像素格式
        - EXR/HDR 使用 imageio + FreeImage 解码浮点数据，经 Reinhard 色调映射输出 8bit
        - 法线贴图（BC5/DXT5nm）自动标记 is_normal_map
        - 所有格式最终转 PNG Base64 由 MMFBImageViewer 渲染
        - DDS 不支持编辑（GPU 压缩编码复杂）；TGA 支持基础编辑
    """

    extensions = TEXTURE_EXTENSIONS

    def get_preview(self) -> Optional[Dict[str, Any]]:
        """获取贴图预览数据"""
        try:
            if not os.path.isfile(self.path):
                return self._error_result("file not found")

            file_size = os.path.getsize(self.path)
            ext = os.path.splitext(self.path)[1].lower()

            result: Dict[str, Any] = {
                "mime": "image/png",
                "template": "image",
                "data": {
                    "file_path": self.path,
                    "file_size": file_size,
                    "width": 0,
                    "height": 0,
                    "mode": "",
                    "format": ext.lstrip(".").upper(),
                    "pixel_format": "",
                    "mipmap_count": 1,
                    "is_normal_map": False,
                    "is_hdr": False,
                    "channel_count": 0,
                },
                "editable": False,
            }

            if ext == ".dds":
                return self._decode_dds(result)
            elif ext == ".tga":
                return self._decode_tga(result)
            elif ext in (".exr", ".hdr"):
                return self._decode_hdr_format(result)
            else:
                return self._error_result("unsupported format")

        except Exception as e:
            return self._error_result(str(e))

    def _decode_dds(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """解码 DDS 贴图 + 解析元数据"""
        # Parse header metadata
        header_info = _parse_dds_header(self.path)
        pixel_format = header_info.get("pixel_format", "unknown")

        # Default size from header
        width_h = header_info.get("width", 0)
        height_h = header_info.get("height", 0)

        try:
            with Image.open(self.path) as img:
                width, height = img.size
                mode = img.mode
                pformat = getattr(img, "pixel_format", pixel_format)
                # Pillow's pixel_format may be more accurate
                if not pixel_format or pixel_format == "unknown":
                    pixel_format = pformat

                data = result["data"]
                data["width"] = width
                data["height"] = height
                data["mode"] = mode
                data["pixel_format"] = DDS_PIXEL_FORMATS.get(pixel_format, pixel_format)
                data["mipmap_count"] = header_info.get("mipmap_count", 1)
                data["is_normal_map"] = pixel_format in NORMAL_MAP_FORMATS
                data["channel_count"] = len(mode) if mode else 3
                data["is_hdr"] = pixel_format in ("BC6H", "BC6HS")
                data["is_cubemap"] = header_info.get("is_cubemap", False)
                data["array_size"] = header_info.get("array_size", 1)

                # Convert to base64
                try:
                    data["data_url"] = _pil_to_base64_png(img)
                except Exception as e:
                    data["_base64_error"] = str(e)

                return result
        except Exception as e:
            return self._error_result(f"DDS decode error: {e}")

    def _decode_tga(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """解码 TGA 贴图"""
        try:
            with Image.open(self.path) as img:
                width, height = img.size
                mode = img.mode
                fmt = img.format or "TGA"

                data = result["data"]
                data["width"] = width
                data["height"] = height
                data["mode"] = mode
                data["pixel_format"] = "TGA (uncompressed/RLE)"
                data["channel_count"] = len(mode) if mode and mode not in ("P", "L") else 3

                # TGA with alpha channel
                if mode == "RGBA":
                    data["channel_count"] = 4
                elif mode == "L":
                    data["channel_count"] = 1

                # GIF animation check (for animated TGA - rare but possible)
                data["is_animated"] = getattr(img, "is_animated", False)
                data["frame_count"] = getattr(img, "n_frames", 1)

                try:
                    data["data_url"] = _pil_to_base64_png(img)
                except Exception as e:
                    data["_base64_error"] = str(e)

                # TGA currently read-only, no save implementation
                return result
        except Exception as e:
            return self._error_result(f"TGA decode error: {e}")

    def _decode_hdr_format(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """解码 EXR/HDR 浮点格式，色调映射后输出 8bit PNG"""
        img = _read_with_imageio(self.path)
        if img is None:
            return self._error_result("imageio + FreeImage not available for EXR/HDR")

        width, height = img.size
        mode = img.mode

        data = result["data"]
        data["width"] = width
        data["height"] = height
        data["mode"] = mode
        data["is_hdr"] = True

        ext = os.path.splitext(self.path)[1].lower()
        if ext == ".exr":
            data["pixel_format"] = "EXR (float32, OpenEXR)"
        else:
            data["pixel_format"] = "HDR (RGBE Radiance)"

        data["channel_count"] = len(mode) if mode and mode not in ("P", "L") else 3
        if mode == "RGBA":
            data["channel_count"] = 4
        elif mode == "L":
            data["channel_count"] = 1

        try:
            data["data_url"] = _pil_to_base64_png(img)
        except Exception as e:
            data["_base64_error"] = str(e)

        return result

    def get_edit(self) -> Optional[Dict[str, Any]]:
        """游戏贴图暂不支持就地编辑"""
        return None

    def get_mime(self) -> str:
        """返回文件对应 MIME"""
        ext_map = {
            ".dds": "image/vnd-ms.dds",
            ".tga": "image/x-targa",
            ".exr": "image/x-exr",
            ".hdr": "image/vnd.radiance",
        }
        from pathlib import Path
        return ext_map.get(Path(self.path).suffix.lower(), "image/png")

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
                "pixel_format": "",
                "mipmap_count": 1,
                "is_normal_map": False,
                "is_hdr": True if os.path.splitext(self.path)[1].lower() in (".exr", ".hdr") else False,
                "channel_count": 0,
            },
            "editable": False,
            "error": message,
        }
