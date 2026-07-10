"""自动更新服务

职责：
  1. 查询 GitHub Releases API 检查新版本
  2. 下载 .exe 安装包到临时目录
  3. 校验文件大小
  4. 提供安装器路径供 Bridge 调用系统命令启动

API 响应格式::

    {
      "tag_name": "v1.2.0",
      "name": "MMFB 1.2.0",
      "body": "## 更新内容...",
      "published_at": "2026-07-05T10:00:00Z",
      "assets": [
        {
          "name": "MMFB-Setup-1.2.0.exe",
          "browser_download_url": "https://...",
          "size": 52428800
        }
      ]
    }
"""
import json
import os
import re
import tempfile
import urllib.request
import urllib.error
from typing import Callable, Dict, List, Optional, Tuple

from mmfb.version import MMFB_VERSION, MMFB_UPDATE_API, MMFB_UPDATE_REPO


# ---------- 版本解析 ----------

_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


def parse_version(tag: str) -> Optional[Tuple[int, int, int]]:
    """解析形如 'v1.2.3' / '1.2.3' / '1.2.3-beta' 的标签为 (major, minor, patch)

    无法解析时返回 None（例如 'latest' 或 'nightly'）。
    """
    m = _TAG_RE.match(tag.strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


# ---------- 查询更新 ----------

def _build_api_url() -> str:
    return MMFB_UPDATE_REPO and MMFB_UPDATE_API.format(repo=MMFB_UPDATE_REPO) or ""


def check_for_updates(timeout: float = 5.0) -> Optional[Dict]:
    """查询 GitHub Releases 的最新版本

    Args:
        timeout: 网络请求超时秒数

    Returns:
        有新版本时返回::

            {
                "tag": "v1.2.0",
                "name": "MMFB 1.2.0",
                "notes": "## 更新内容...",
                "published_at": "2026-07-05T10:00:00Z",
                "html_url": "https://github.com/...",
                "asset": {
                    "name": "MMFB-Setup-1.2.0.exe",
                    "size": 52428800,
                    "download_url": "https://..."
                }
            }

        已是最新版 / 网络错误 / 解析失败时返回 None。

    不会因为网络问题而抛出异常；任何错误静默返回 None。
    """
    api_url = _build_api_url()
    if not api_url:
        return None

    try:
        req = urllib.request.Request(api_url)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", f"MMFB-Update-Checker/{MMFB_VERSION}")

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        return None

    tag = data.get("tag_name", "")
    remote = parse_version(tag)
    if remote is None:
        return None

    current = parse_version(MMFB_VERSION)
    if current is None:
        return None

    # 已是最新
    if remote <= current:
        return None

    # 寻找 .exe 安装包资产
    asset = _find_exe_asset(data.get("assets", []))
    if asset is None:
        # 没有 .exe 安装包时仍然提示更新，但不提供直接下载
        asset = {}

    return {
        "tag": tag,
        "name": data.get("name", tag),
        "notes": data.get("body", "")[:2000],
        "published_at": data.get("published_at", ""),
        "html_url": data.get("html_url", ""),
        "asset": asset,
    }


def _find_exe_asset(assets: List[Dict]) -> Optional[Dict]:
    """从资产列表中选择 .exe 安装包（优先 .exe，其次 .msi/.msix）

    选择最大文件（假设是完整安装包而非 Web 安装器）。
    """
    candidates = []
    for a in assets:
        name = a.get("name", "").lower()
        url = a.get("browser_download_url", "")
        if not url:
            continue
        if name.endswith((".exe", ".msi", ".msix")):
            candidates.append(a)

    if not candidates:
        return None

    # 选择 size 最大的，回退到第一个
    candidates.sort(key=lambda x: x.get("size", 0), reverse=True)
    best = candidates[0]
    return {
        "name": best.get("name", "setup.exe"),
        "size": best.get("size", 0),
        "download_url": best.get("browser_download_url", ""),
    }


# ---------- 下载 ----------

def download_installer(
    url: str,
    filename: str = None,
    timeout: float = 30.0,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> Optional[str]:
    """下载安装器到临时目录

    Args:
        url: 下载 URL
        filename: 保存文件名，默认从 URL 提取
        timeout: 单次网络读写超时
        progress_cb: 回调 (bytes_downloaded, total_bytes)；total_bytes 未知时为 -1

    Returns:
        成功返回本地文件路径；失败返回 None。
    """
    if not url:
        return None

    if not filename:
        filename = url.split("/")[-1].split("?")[0] or "MMFB-Setup.exe"

    dest_dir = tempfile.mkdtemp(prefix="mmfb_update_")
    dest_path = os.path.join(dest_dir, filename)

    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", f"MMFB-Updater/{MMFB_VERSION}")

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            total = resp.headers.get("Content-Length")
            total = int(total) if total and total.isdigit() else -1

            downloaded = 0
            with open(dest_path, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        progress_cb(downloaded, total)

        return dest_path
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        # 清理失败残留
        try:
            if os.path.isfile(dest_path):
                os.remove(dest_path)
            os.rmdir(dest_dir)
        except OSError:
            pass
        return None


# ---------- 清理 ----------

def cleanup_downloaded(path: str):
    """删除已下载的安装包文件及其目录"""
    if not path or not os.path.isfile(path):
        return
    try:
        os.remove(path)
    except OSError:
        return
    try:
        os.rmdir(os.path.dirname(path))
    except OSError:
        pass


# ---------- 比较工具 ----------

def is_newer_version(remote_tag: str, current_version: str = MMFB_VERSION) -> bool:
    """判定 remote_tag 是否比 current_version 新"""
    r = parse_version(remote_tag)
    c = parse_version(current_version)
    if r is None or c is None:
        return False
    return r > c
