"""媒体格式处理器 (视频/音频)

职责：
1. 使用文件扩展名判断视频/音频类型，返回对应 MIME
2. 将文件绝对路径传给前端，由 HTML5 <video>/<audio> 直接播放
3. 支持 MP4/MKV/AVI/WMV/FLV/MOV/WEBM/MP3/WAV/FLAC/AAC/OGG

设计说明：
    QMediaPlayer 需要独占 QWidget 顶层窗口，与 QWebEngineView 的单窗口架构冲突。
    HTML5 media 标签由内嵌 Chromium 直接解码主流格式 (H.264/AAC/VP9/Opus)，
    零 Python 依赖，兼容当前架构，故采用此方案。

返回结构：
- mime: video/mp4 或 audio/mpeg 等
- template: 'media'
- data.file_path: 文件绝对路径（前端转为 file:// URL）
- data.media_type: 'video' 或 'audio'
- data.file_size: 字节
- data.format: 容器格式名
- data.subtitle_paths: 同目录下匹配的字幕文件列表 (.srt/.ass/.ssa/.sub)
- editable: False
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from mmfb.core.handler_base import BaseHandler


# 视频扩展名
VIDEO_EXTENSIONS = [
    ".mp4", ".m4v",
    ".mkv",
    ".avi",
    ".wmv",
    ".flv",
    ".mov",
    ".webm",
    ".ts",
    ".m2ts", ".mts",
    ".3gp",
]

# 音频扩展名
AUDIO_EXTENSIONS = [
    ".mp3",
    ".wav",
    ".flac",
    ".aac",
    ".ogg",
    ".oga",
    ".opus",
    ".wma",
]

# 字幕扩展名
SUBTITLE_EXTENSIONS = [".srt", ".ass", ".ssa", ".sub", ".vtt"]

# 扩展名 → MIME
MIME_MAP: Dict[str, str] = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
    ".wmv": "video/x-ms-wmv",
    ".flv": "video/x-flv",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".ts": "video/mp2t",
    ".m2ts": "video/mp2t",
    ".mts": "video/mp2t",
    ".3gp": "video/3gpp",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".opus": "audio/opus",
    ".wma": "audio/x-ms-wma",
}

# 容器格式名（给前端展示）
FORMAT_MAP: Dict[str, str] = {
    ".mp4": "MP4", ".m4v": "M4V",
    ".mkv": "MKV",
    ".avi": "AVI",
    ".wmv": "WMV",
    ".flv": "FLV",
    ".mov": "MOV",
    ".webm": "WebM",
    ".ts": "MPEG-TS",
    ".m2ts": "M2TS",
    ".mts": "MTS",
    ".3gp": "3GP",
    ".mp3": "MP3",
    ".wav": "WAV",
    ".flac": "FLAC",
    ".aac": "AAC",
    ".ogg": "OGG", ".oga": "OGA",
    ".opus": "Opus",
    ".wma": "WMA",
}

# 大文件阈值：200MB（超过后提示用户）
LARGE_FILE_THRESHOLD = 200 * 1024 * 1024


class MediaHandler(BaseHandler):
    """视频/音频文件处理器

    支持的扩展名：
        视频：MP4/MKV/AVI/WMV/FLV/MOV/WEBM/TS/3GP
        音频：MP3/WAV/FLAC/AAC/OGG/Opus/WMA

    实现说明：
        - 后端仅返回文件路径和元信息，不做转码
        - 前端用 HTML5 media 标签直接播放
        - 自动扫描同目录下的字幕文件
    """

    extensions = VIDEO_EXTENSIONS + AUDIO_EXTENSIONS

    @classmethod
    def can_handle(cls, path: str) -> bool:
        suffix = Path(path).suffix.lower()
        return suffix in cls.extensions

    def get_preview(self) -> Optional[Dict[str, Any]]:
        """获取媒体预览数据"""
        try:
            if not os.path.isfile(self.path):
                return self._error_result("file not found")

            file_size = os.path.getsize(self.path)
            suffix = Path(self.path).suffix.lower()
            mime = MIME_MAP.get(suffix, "application/octet-stream")
            fmt = FORMAT_MAP.get(suffix, suffix.lstrip(".").upper())
            media_type = "video" if suffix in VIDEO_EXTENSIONS else "audio"

            # 扫描同目录下的字幕文件
            subtitle_paths = self._scan_subtitles()

            return {
                "mime": mime,
                "template": "media",
                "data": {
                    "file_path": self.path,
                    "file_size": file_size,
                    "mime": mime,
                    "media_type": media_type,
                    "format": fmt,
                    "large_file": file_size > LARGE_FILE_THRESHOLD,
                    "subtitle_paths": subtitle_paths,
                },
                "editable": False,
            }
        except Exception as e:
            return self._error_result(str(e))

    def get_edit(self) -> None:
        """媒体不支持就地编辑"""
        return None

    def get_mime(self) -> str:
        suffix = Path(self.path).suffix.lower()
        return MIME_MAP.get(suffix, "application/octet-stream")

    def _scan_subtitles(self) -> List[Dict[str, str]]:
        """扫描同目录下与媒体文件同名的字幕文件"""
        try:
            parent = Path(self.path).parent
            stem = Path(self.path).stem
            results = []

            # 在同目录下查找同名的 .srt / .ass 等
            for sub_ext in SUBTITLE_EXTENSIONS:
                candidate = parent / (stem + sub_ext)
                if candidate.exists():
                    results.append({
                        "path": str(candidate),
                        "name": candidate.name,
                        "format": sub_ext.lstrip(".").upper(),
                    })

            # 也扫一层通用字幕名
            for sub_ext in SUBTITLE_EXTENSIONS:
                for f in parent.glob("*" + sub_ext):
                    info = {"path": str(f), "name": f.name, "format": sub_ext.lstrip(".").upper()}
                    if info not in results:
                        results.append(info)

            return results
        except Exception:
            return []

    def _error_result(self, message: str) -> Dict[str, Any]:
        suffix = Path(self.path).suffix.lower()
        media_type = "video" if suffix in VIDEO_EXTENSIONS else "audio"
        return {
            "mime": MIME_MAP.get(suffix, "application/octet-stream"),
            "template": "media",
            "data": {
                "file_path": self.path,
                "file_size": 0,
                "mime": MIME_MAP.get(suffix, "application/octet-stream"),
                "media_type": media_type,
                "format": suffix.lstrip(".").upper(),
                "large_file": False,
                "subtitle_paths": [],
            },
            "editable": False,
            "error": message,
        }
