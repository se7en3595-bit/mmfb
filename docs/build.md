# 构建与打包

MMFB Windows 使用 PyInstaller 打包为单文件 exe，再用 NSIS 制作安装包。

## 📦 依赖安装

### 1. 安装 PyInstaller

```bash
pip install pyinstaller
```

### 2. 安装 NSIS

下载 [NSIS (Nullsoft Scriptable Install System)](https://nsis.sourceforge.io/):
- 版本要求：3.0 或更高
- 安装到默认路径（如 `C:\Program Files\NSIS`）

验证：
```bash
makensis /VERSION
```

## 🔨 PyInstaller 打包

### 配置文件：`build.spec`

已提供 `build.spec`，核心配置：

```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('mmfb/frontend', 'mmfb/frontend'),
        ('mmfb/resources', 'mmfb/resources'),
        ('README.md', '.'),
    ],
    hiddenimports=[
        'PySide6.QtWebEngine',
        'PIL._tkinter_finder',  # Pillow 可能需要
        'mmfb.handlers.*',  # 所有 handlers
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',  # 未使用，排除以减小体积
        'scipy', 'numpy',
        'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 优化：UPX 压缩（如已安装）
if os.path.exists('upx.exe'):
    a.pure = [i for i in a.pure if not i[0].endswith('vcruntime140.dll')]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MMFB',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # 启用 UPX 压缩
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='mmfb/resources/icon.ico',  # 应用图标
    file_version='0.6.0.0',
    product_version='0.6.0',
)
```

### 执行打包

```bash
# 单文件打包（推荐）
pyinstaller build.spec

# 或命令行直接打包
pyinstaller --onefile --windowed --icon=mmfb/resources/icon.ico main.py
```

**输出位置：**
- `dist/MMFB.exe` - 单文件可执行程序

**打包时间：** 约 3-5 分钟（取决于机器性能）

**体积：** 约 85-100 MB（未签名，含 UPX 压缩）

### 排除不必要的依赖

如果体积过大，检查 `build.spec` 的 `excludes` 列表：

```python
excludes=[
    'matplotlib',
    'scipy',
    'numpy',
    'sklearn',
    'tensorflow',
    'torch',
    'nltk',
    'sphinx',
    'tkinter',
    'unittest',  # Python 标准库测试模块
    'email',  # 如果不用邮件功能
]
```

### 添加隐藏导入

某些库（如 PIL、PySide6 插件）需要显式声明：

```python
hiddenimports=[
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebEngine',
    'PIL._imaging',
    'PIL.ImageTk',  # 如果 Pillow 使用了 Tk 后端
    'xml.etree.ElementTree',
    'lxml.etree',
]
```

### 处理数据文件

确保前端资源被打包：

```python
datas=[
    ('mmfb/frontend', 'mmfb/frontend'),
    ('mmfb/resources', 'mmfb/resources'),
    ('mmfb/handlers', 'mmfb/handlers'),
]
```

**注意：** `datas` 是元组列表 `(源路径, 目标路径)`。

### 调试打包问题

如果打包后运行闪退，检查：

1. **查看日志**
   ```bash
   # 使用控制台模式重新打包
   pyinstaller --console build.spec
   dist/MMFB.exe  # 查看控制台错误
   ```

2. **缺失模块**
   错误：`ModuleNotFoundError: No module named 'xxx'`
   解决：在 `hiddenimports` 添加

3. **缺少 DLL**
   错误：`ImportError: DLL load failed`
   解决：将 DLL 加入 `binaries`：
   ```python
   binaries=[
       ('C:/path/to/vcruntime140.dll', '.'),
   ]
   ```

4. **文件路径问题**
   运行时资源文件路径与源码不同，使用：
   ```python
   if getattr(sys, 'frozen', False):
       # 打包后运行
       BASE_DIR = sys._MEIPASS
   else:
       # 源码运行
       BASE_DIR = os.path.dirname(__file__)
   ```

## 📀 NSIS 安装包

### 脚本：`installer.nsi`

已提供，核心配置：

```nsis
; MMFB Windows Installer
!include "MUI2.nsh"

; 基本信息
Name "MMFB Windows"
OutFile "MMFB-Setup-0.6.0.exe"
InstallDir "$PROGRAMFILES64\MMFB"
RequestExecutionLevel admin

; 界面设置
!define MUI_ABORTWARNING
!define MUI_WELCOMEFINISHPAGE
!define MUI_FINISHPAGE_RUN "$INSTDIR\MMFB.exe"

; 页面
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_LANGUAGE "SimpChinese"

Section "Install"
    SetOutPath "$INSTDIR"
    ; 复制所有文件
    File /r "dist\MMFB.exe"
    File /r "mmfb\frontend\*"
    File /r "mmfb\resources\*"
    File "README.md"
    File "LICENSE"

    ; 创建快捷方式
    CreateShortcut "$DESKTOP\MMFB.lnk" "$INSTDIR\MMFB.exe"
    CreateShortcut "$SMPROGRAMS\MMFB.lnk" "$INSTDIR\MMFB.exe"

    ; 注册文件关联（可选）
    ;ExecWait '"$INSTDIR\MMFB.exe" --register-associations'
SectionEnd

Section "Uninstall"
    Delete "$DESKTOP\MMFB.lnk"
    Delete "$SMPROGRAMS\MMFB.lnk"
    DeleteRegKey HKCR ".mmfb"
    RMDir /r "$INSTDIR"
SectionEnd
```

### 编译安装包

```bash
# 确保 dist/MMFB.exe 已存在
pyinstaller build.spec

# 编译 NSIS 脚本
makensis installer.nsi

# 输出：MMFB-Setup-0.6.0.exe
```

### 代码签名（可选但强烈推荐）

1. **获取证书**
   - EV 代码签名证书（Sectigo、DigiCert 等）
   - 导出为 `.pfx` 文件

2. **签名 exe**
   ```bash
   signtool sign /f certificate.pfx /p password /tr http://timestamp.digicert.com /td sha256 /fd sha256 dist/MMFB.exe
   ```

3. **签名安装包**
   ```bash
   signtool sign /f certificate.pfx /p password /tr http://timestamp.digicert.com /td sha256 /fd sha256 MMFB-Setup-0.6.0.exe
   ```

### 优化安装包体积

1. **UPX 压缩 exe**（已在 build.spec 启用）
2. **移除未使用的 handlers**
   ```python
   # 只保留常用的 handlers
   excluded_handlers = [
       'xmind_handler',  # 如果不需要 XMind
       'model3d_handler',  # 如果不支持 3D
   ]
   ```
3. **压缩图标**
   - 使用 `.ico` 格式，尺寸 256x256
   - 压缩工具：Greenfish Icon Editor Pro

## 🔄 自动化构建

### GitHub Actions 自动构建

已在 `.github/workflows/ci.yml` 配置：

**触发条件：**
- push 到 `main` 或 `develop` 分支 → 运行测试
- 创建 Git Tag（如 `v0.6.0`）→ 运行测试 + 打包 + 创建 Release

**手动触发构建：**
```bash
# 创建 tag
git tag v0.6.0
git push origin v0.6.0

# GitHub Actions 自动：
# 1. 运行测试
# 2. 打包 exe
# 3. 上传 artifact
# 4. 创建 GitHub Release（需要配置）
```

### 本地构建脚本

创建 `build.py` 简化流程：

```python
#!/usr/bin/env python
"""
MMFB 构建脚本
用法：python build.py [clean|build|installer|all]
"""

import os
import sys
import shutil
import subprocess

def clean():
    """清理构建产物"""
    dirs_to_remove = ['build', 'dist', '__pycache__']
    for d in dirs_to_remove:
        if os.path.exists(d):
            shutil.rmtree(d)
    print("✅ Clean complete")

def build_exe():
    """使用 PyInstaller 打包"""
    subprocess.run(['pyinstaller', 'build.spec'], check=True)
    print("✅ EXE build complete: dist/MMFB.exe")

def build_installer():
    """使用 NSIS 制作安装包"""
    subprocess.run(['makensis', 'installer.nsi'], check=True)
    print("✅ Installer build complete: MMFB-Setup-0.6.0.exe")

def main():
    commands = {
        'clean': clean,
        'build': build_exe,
        'installer': build_installer,
        'all': lambda: (clean(), build_exe(), build_installer()),
    }

    if len(sys.argv) < 2:
        print("Usage: python build.py [clean|build|installer|all]")
        return

    cmd = sys.argv[1]
    if cmd in commands:
        commands[cmd]()
    else:
        print(f"Unknown command: {cmd}")

if __name__ == '__main__':
    main()
```

使用：
```bash
python build.py all
```

## 🧪 构建验证

### 1. 功能测试

安装后在测试机器上验证：

- [ ] 应用正常启动
- [ ] 打开常见格式（PDF、Word、Excel、PPT、图片）
- [ ] 编辑功能正常（Markdown、Text）
- [ ] 转换功能正常（PDF/Word/Excel/PPT/MD/HTML）
- [ ] 卸载正常，无残留文件

### 2. 性能测试

```bash
# 启动时间
time MMFB.exe

# 内存占用（打开 10MB PDF）
# 使用任务管理器或 Process Explorer

# 安装包大小
dir MMFB-Setup-*.exe
```

### 3. 病毒扫描

上传安装包到 [VirusTotal](https://www.virustotal.com/) 检查误报。

如有误报，报告给杀毒厂商并考虑代码签名。

## 🚀 发布流程

### 1. 创建 GitHub Release

```bash
# 创建 tag
git tag -a v0.6.0 -m "Release v0.6.0"
git push origin v0.6.0

# GitHub Actions 自动构建并创建 Release Draft
# 手动确认后发布
```

### 2. 更新网站/文档

- 更新官网下载链接
- 更新 CHANGELOG.md
- 更新 README.md 版本号

### 3. 通知用户

- 通过官网公告
- 社交媒体（如适用）
- 邮件列表（如有）

---

**记住：** 当前版本使用自签名证书（暂未签名），未来版本升级 EV 证书。