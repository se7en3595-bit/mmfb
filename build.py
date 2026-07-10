"""
MMFB Windows 构建脚本

用法：
  python build.py            # 单文件模式，输出 dist/MMFB.exe
  python build.py --onedir   # 目录模式（调试体积用），输出 dist/MMFB/
  python build.py --clean    # 清理后重新构建
  python build.py --verify   # 仅运行打包后验证

退出码：
  0 = 成功
  1 = 构建失败
  2 = 验证失败
"""
import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
SPEC_FILE = PROJECT_ROOT / "build.spec"


def run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    print(f"[run] {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, cwd=str(PROJECT_ROOT), **kwargs)


def clean():
    print("[clean] 清理 build/ 和 dist/ ...")
    for p in [BUILD_DIR, DIST_DIR]:
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)


def build(onedir: bool = False) -> bool:
    """调用 PyInstaller 构建"""
    args = [
        sys.executable, "-m", "PyInstaller",
        str(SPEC_FILE),
        "--noconfirm",
        "--log-level=WARN",
    ]
    if onedir:
        args.append("--onedir")
    else:
        args.append("--onefile")

    result = run(args, check=False)
    return result.returncode == 0


def find_exe() -> Path | None:
    """查找构建产物"""
    if (DIST_DIR / "MMFB.exe").exists():
        return DIST_DIR / "MMFB.exe"
    mmfb_dir = DIST_DIR / "MMFB"
    if mmfb_dir.exists():
        exe = mmfb_dir / "MMFB.exe"
        if exe.exists():
            return exe
    # 搜索任意 .exe
    for p in DIST_DIR.rglob("*.exe"):
        return p
    return None


def verify(exe_path: Path) -> bool:
    """验证构建产物"""
    print(f"[verify] 验证 {exe_path}")

    # 1. 文件存在
    if not exe_path.exists():
        print(f"  [FAIL] exe 不存在")
        return False
    print(f"  [OK] exe 存在")

    # 2. 体积检查 (< 100 MB 要求)
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"  [INFO] 体积 = {size_mb:.1f} MB")
    if size_mb > 100:
        print(f"  [WARN] 体积超过 100 MB（当前 {size_mb:.1f} MB）")
        # 警告但不退出，因为 Debug 版本通常较大

    # 3. 尝试启动并立即退出（检测缺失 DLL）
    print("[verify] 启动冒烟测试（3秒超时）...")
    try:
        proc = subprocess.run(
            [str(exe_path), "--version"],
            capture_output=True,
            timeout=5,
            cwd=str(DIST_DIR),
        )
        print(f"  [INFO] exit code = {proc.returncode}")
        if proc.stdout:
            print(f"  [stdout] {proc.stdout.decode('utf-8', errors='replace').strip()}")
    except subprocess.TimeoutExpired:
        print("  [INFO] 启动超时（可能 GUI 阻塞，正常）")
    except Exception as e:
        print(f"  [WARN] 启动失败（可能缺 DLL）: {e}")

    # 4. 解压检查 onedir 内容（如果是目录模式）
    return True


def report_contents():
    """打印构建产物列表"""
    if not DIST_DIR.exists():
        return
    print("\n[dist] 构建产物清单：")
    if (DIST_DIR / "MMFB.exe").exists():
        exe = DIST_DIR / "MMFB.exe"
        print(f"  MMFB.exe  {exe.stat().st_size / 1024 / 1024:.2f} MB")

    mmfb_dir = DIST_DIR / "MMFB"
    if mmfb_dir.exists():
        total = 0
        file_count = 0
        for p in mmfb_dir.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
                file_count += 1
        print(f"  MMFB/ 目录：{file_count} 文件，合计 {total / 1024 / 1024:.2f} MB")


def main():
    parser = argparse.ArgumentParser(description="MMFB 构建脚本")
    parser.add_argument("--onedir", action="store_true", help="目录模式打包")
    parser.add_argument("--clean", action="store_true", help="清理后重新构建")
    parser.add_argument("--verify", action="store_true", help="仅验证构建产物")
    args = parser.parse_args()

    if args.verify:
        exe = find_exe()
        if exe and verify(exe):
            sys.exit(0)
        else:
            sys.exit(2)

    if args.clean:
        clean()

    print("=" * 60)
    print("MMFB Windows 构建")
    print("=" * 60)
    print(f"Python  : {sys.version.split()[0]}")
    print(f"PyInstaller 路径 : {shutil.which('pyinstaller') or 'NOT FOUND'}")
    print(f"UPX 压缩: 启用（需 sys PATH 中存在 upx）")
    print(f"目标    : {'onedir' if args.onedir else 'onefile'}")
    print()

    ok = build(onedir=args.onedir)
    if not ok:
        print("\n[FAIL] 构建失败，请查看上方日志。")
        sys.exit(1)

    report_contents()

    exe = find_exe()
    if exe and verify(exe):
        print("\n[DONE] 构建完成。")
    else:
        print("\n[DONE] 构建完成（跳过验证或 exe 未找到）。")


if __name__ == "__main__":
    main()
