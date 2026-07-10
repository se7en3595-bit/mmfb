"""MMFB Services 包

可重用的服务：
- ffmpeg_service : 本地 ffmpeg 探测、subprocess 调用、元数据读取、转码（含进度）
- conversion_engine : MD/HTML/DOCX/PDF 互转引擎 + 视频转码
"""
from mmfb.services.ffmpeg_service import (
    FFmpegService,
    check_ffprobe,
    check_ffmpeg,
    probe_media,
    get_media_info,
    convert_video,
)
from mmfb.services.conversion_engine import (
    ConversionResult,
    convert,
    get_supported_conversions,
    md_to_html,
    html_to_md,
    md_to_docx,
    docx_to_html,
    docx_to_md,
    html_to_pdf,
    pdf_to_text,
    pdf_to_md,
    pdf_to_png,
    pdf_to_png_folder,
    convert_video_ffmpeg,
    _VIDEO_FORMAT_PARAMS,
    _INPUT_CONTAINER_MAP,
)

__all__ = [
    # ffmpeg
    "FFmpegService",
    "check_ffprobe",
    "check_ffmpeg",
    "probe_media",
    "get_media_info",
    "convert_video",
    # conversion engine
    "ConversionResult",
    "convert",
    "get_supported_conversions",
    "md_to_html",
    "html_to_md",
    "md_to_docx",
    "docx_to_html",
    "docx_to_md",
    "html_to_pdf",
    "pdf_to_text",
    "pdf_to_md",
    "pdf_to_png",
    "pdf_to_png_folder",
    "convert_video_ffmpeg",
    "_VIDEO_FORMAT_PARAMS",
    "_INPUT_CONTAINER_MAP",
]
