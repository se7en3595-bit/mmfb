"""ffmpeg_service: 本地 ffmpeg 探测与 subprocess 转码

为 MMFB 提供媒体转码能力，包含：
- 探测本机 ffmpeg / ffprobe 是否安装 (check_ffmpeg / check_ffprobe)
- 读取媒体元数据 (probe_media / get_media_info)
- 调用 ffmpeg 执行容器互转，带进度回调 (convert_video)

转码记录（持续时间 / 当前时间 / fps / 速度）通过 stderr 行中的
"time=00:00:05.12" 字段解析后按回调上报。

延迟设计：
    首次调用才真正执行 subprocess 探测并缓存结果，避免无关用户触发。
"""
import json
import os
import re
import subprocess
import sys
import threading
import shutil
from typing import Any, Callable, Dict, List, Optional

# 进度行正则
# 示例：frame=  123 fps= 25 q=28.0 size=    256kB time=00:00:05.12 bitrate= 409.6kbits/s speed=1.02x
_RE_PROGRESS = re.compile(
    r"frame=\s*(\d+)\s+"
    r"fps=\s*([\d.]+)\s+"
    r"q=([-\d.]+)\s+"
    r"size=\s*(\S+)\s+"
    r"time=(\d{2}):(\d{2}):(\d{2})\.\d+\s+"
    r"bitrate=\s*(\S+)\s+"
    r"speed=\s*([\d.]+)x"
)
# 从输入行提取 Duration: 00:05:23.12, start: ...
_RE_DURATION = re.compile(r"Duration:\s*(\d{2}):(\d{2}):(\d{2}\.\d+)")


def _run(args: List[str], timeout: float = 10.0) -> subprocess.CompletedProcess:
    """统一 subprocess 调用，隐藏控制台窗口 (Windows)"""
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        startupinfo=startupinfo,
        encoding="utf-8",
        errors="replace",
    )


def _find_exe(name: str) -> Optional[str]:
    """查找可执行文件路径，找不到返回 None"""
    return shutil.which(name)


def check_ffmpeg() -> Dict[str, Any]:
    """探测本机 ffmpeg 是否可用

    返回: {"ok": bool, "path": str|null, "version": str, "error": str|null}
    """
    path = _find_exe("ffmpeg")
    if not path:
        return {"ok": False, "path": None, "version": "", "error": "ffmpeg not found in PATH"}
    try:
        r = _run(["ffmpeg", "-version"])
        version_line = (r.stdout or "").splitlines()[0] if r.stdout else ""
        return {"ok": True, "path": path, "version": version_line, "error": None}
    except Exception as e:
        return {"ok": False, "path": path, "version": "", "error": str(e)}


def check_ffprobe() -> Dict[str, Any]:
    """探测本机 ffprobe 是否可用

    返回: {"ok": bool, "path": str|null, "version": str, "error": str|null}
    """
    path = _find_exe("ffprobe")
    if not path:
        return {"ok": False, "path": None, "version": "", "error": "ffprobe not found in PATH"}
    try:
        r = _run(["ffprobe", "-version"])
        version_line = (r.stdout or "").splitlines()[0] if r.stdout else ""
        return {"ok": True, "path": path, "version": version_line, "error": None}
    except Exception as e:
        return {"ok": False, "path": path, "version": "", "error": str(e)}


def get_media_info(path: str) -> Dict[str, Any]:
    """读取媒体元数据（流信息 + 容器信息）

    返回: {"ok": bool, "streams": [...], "format": {...}, "error": str|null}
    """
    if not path or not os.path.isfile(path):
        return {"ok": False, "streams": [], "format": {}, "error": "file not found"}
    r = check_ffprobe()
    if not r["ok"]:
        return {"ok": False, "streams": [], "format": {}, "error": r["error"]}

    try:
        proc = _run([
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            path,
        ])
        if proc.returncode != 0:
            return {"ok": False, "streams": [], "format": {}, "error": proc.stderr or "ffprobe error"}
        data = json.loads(proc.stdout or "{}")
        return {
            "ok": True,
            "streams": data.get("streams", []),
            "format": data.get("format", {}),
            "error": None,
        }
    except Exception as e:
        return {"ok": False, "streams": [], "format": {}, "error": str(e)}


# probe_media 作为 get_media_info 的兼容别名
probe_media = get_media_info


def convert_video(
    input_path: str,
    output_path: str,
    output_format: str = "",
    extra_args: Optional[List[str]] = None,
    on_progress: Optional[Callable[[float, str], None]] = None,
    on_done: Optional[Callable[[bool, str], None]] = None,
) -> None:
    """同步执行 ffmpeg 转码

    Args:
        input_path: 源文件路径
        output_path: 输出文件路径
        output_format: 容器格式 (如 "mp4", "mkv", "avi")，为空时从 output_path 扩展名推断
        extra_args: 额外 ffmpeg 参数 (如 ["-crf", "23"])
        on_progress: 进度回调，参数为 (ratio 0~1, message_str)
        on_done: 完成回调，参数为 (ok_bool, message)

    Raises:
        FileNotFoundError: ffmpeg 未安装或输入文件不存在
        RuntimeError: 转码失败 (returncode!=0)
    """
    if not input_path or not os.path.isfile(input_path):
        raise FileNotFoundError(f"input not found: {input_path}")

    r = check_ffmpeg()
    if not r["ok"]:
        raise FileNotFoundError(r["error"] or "ffmpeg not found")

    # 构造命令
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-progress", "pipe:2",  # 进度写到 stderr
        "-nostats",              # 避免 stderr 混入统计块
    ]
    if extra_args:
        cmd.extend(extra_args)

    # 若未指定输出格式且输出路径有空扩展名，让 ffmpeg 自行推断
    cmd.append(output_path)

    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    # 从源文件探一下总时长，供进度计算
    total_duration = _probe_duration(input_path)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        startupinfo=startupinfo,
        encoding="utf-8",
        errors="replace",
    )

    # 在子线程读 stderr 以解析进度，避免阻塞调用方
    def _reader():
        last_ratio = 0.0
        last_msg = "running"
        try:
            for line in proc.stderr or []:
                m = _RE_PROGRESS.search(line)
                if m:
                    h, mi, se = int(m.group(5)), int(m.group(6)), float(m.group(7).lstrip("0") or "0")
                    cur = h * 3600 + mi * 60 + se
                    ratio = max(0.0, min(1.0, (cur / total_duration) if total_duration > 0 else 0.0))
                    last_ratio = ratio
                    last_msg = f"fps={m.group(2)} speed={m.group(9)}x time={int(cur)}s"
                    if on_progress:
                        on_progress(ratio, last_msg)
                elif "Conversion failed" in line or "Error" in line:
                    last_msg = line.strip()[-200:]
        except Exception:
            pass

    t = threading.Thread(target=_reader, daemon=True)
    t.start()

    proc.wait()
    t.join(timeout=5.0)

    if proc.returncode != 0:
        msg = f"ffmpeg exit code {proc.returncode}"
        if on_done:
            on_done(False, msg)
        raise RuntimeError(msg)

    ok = os.path.isfile(output_path) and os.path.getsize(output_path) > 0
    msg = output_path if ok else "output not generated"
    if on_done:
        on_done(ok, msg)


def _probe_duration(path: str) -> float:
    """返回媒体时长秒数，失败返回 0"""
    try:
        r = _run([
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ], timeout=5.0)
        if r.returncode == 0 and r.stdout:
            return float((r.stdout or "0").strip().splitlines()[0])
    except Exception:
        pass
    return 0.0


class FFmpegService:
    """FFmpeg 服务封装

    提供同步探测 + 转换接口，供 MMFB Bridge 调用。
    """

    def __init__(self):
        self._cache: Dict[str, Any] = {}

    @property
    def is_available(self) -> bool:
        if "ffmpeg" not in self._cache:
            self._cache["ffmpeg"] = check_ffmpeg()
        return bool(self._cache["ffmpeg"].get("ok"))

    @property
    def info(self) -> Dict[str, Any]:
        if "ffmpeg" not in self._cache:
            self._cache["ffmpeg"] = check_ffmpeg()
        return self._cache["ffmpeg"]

    def reset_cache(self):
        self._cache.clear()

    def convert(
        self,
        input_path: str,
        output_path: str,
        output_format: str = "",
        extra_args: Optional[List[str]] = None,
        on_progress: Optional[Callable[[float, str], None]] = None,
        on_done: Optional[Callable[[bool, str], None]] = None,
    ):
        convert_video(
            input_path=input_path,
            output_path=output_path,
            output_format=output_format,
            extra_args=extra_args,
            on_progress=on_progress,
            on_done=on_done,
        )

    def probe(self, path: str) -> Dict[str, Any]:
        return get_media_info(path)


# 全局单例
ffmpeg_service = FFmpegService()
