# MMFB Windows - 万能阅览器

[中文](#中文) | [English](#english)

---

## 中文

一个窗口，打开所有格式。

MMFB Windows 是一款基于 Python + PySide6 开发的 Windows 平台万能文件阅览器，支持 155+ 种文件格式的预览、编辑和格式转换。

![版本](https://img.shields.io/badge/version-0.6.0-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

### ✨ 核心特性

- **看** - 支持 155+ 种文件格式
  - 文档：PDF、Word、Excel、PPT、Markdown、HTML、代码等
  - 图像：JPG、PNG、GIF、HEIC、PSD、RAW、SVG 等
  - 影音：MP4、MP3、AVI、MKV 等（通过系统默认解码器）
  - 压缩包：ZIP、TAR、GZ、7Z
  - 3D 模型：GLB、GLTF、OBJ、STL、PLY
  - 思维导图：XMind

- **改** - 就地编辑常用文档
  - 6 类文档支持直接编辑：Markdown、HTML、纯文本、CSV、JSON、XML
  - 无需切换软件，修改后直接保存

- **转** - 在线格式互转
  - 9 类格式互转：PDF、Word、Excel、PPT、Markdown、HTML、图片、文本、CSV
  - 内置转换引擎，无需寻找第三方工具

- **设计哲学**
  - 内容优先：默认隐藏工具栏，满屏显示内容
  - 克制美学：暖纸色调，优雅简洁
  - 隐私安全：纯本地运行，文件不出本机
  - 收纳整合：一个应用替代一堆专用阅读器

### 🚀 快速开始

#### 安装方式

**方式一：下载安装包（推荐）**
- 访问 [Releases](https://github.com/mmfb-windows/mmfb/releases) 页面
- 下载 `MMFB-Setup-0.6.0.exe`
- 运行安装向导

**方式二：从源码运行**
```bash
# 克隆仓库
git clone https://github.com/mmfb-windows/mmfb.git
cd mmfb

# 安装依赖（Python 3.8+）
pip install -r requirements.txt

# 运行应用
python main.py
```

#### 系统要求
- Windows 10 或更高版本
- Python 3.8+（仅限源码运行）
- 推荐内存 ≥ 4GB

### 📦 技术架构

```
mmfb/
├── main.py                 # 应用入口
├── core/                   # 核心模块
│   ├── window.py          # 主窗口
│   ├── webview.py         # Web 视图封装
│   ├── bridge.py          # Python-JS 通信桥
│   ├── file_handler.py    # 文件读写基类
│   └── registry.py        # Handler 注册表
├── handlers/              # 格式处理器（20+ 个）
│   ├── pdf_handler.py
│   ├── image_handler.py
│   ├── docx_handler.py
│   └── ...
├── frontend/              # 前端资源
│   ├── index.html
│   ├── css/
│   ├── js/
│   └── libs/              # PDF.js, CodeMirror, Three.js 等
├── services/
│   └── conversion_engine.py  # 格式转换引擎
└── resources/             # 图标、主题
```

**技术栈：**
- **后端**：Python 3.8+、PySide6（Qt6）、Pillow、python-docx、openpyxl、python-pptx、PyPDF2
- **前端**：HTML5 + CSS3 + JavaScript（ES6+）
- **渲染引擎**：QWebEngineView（内嵌 Chromium）
- **通信机制**：QWebChannel 双向调用

### 🎯 支持的格式

| 类别 | 格式 | 编辑 | 转换 |
|------|------|------|------|
| **文档类** | PDF, DOCX, XLSX, PPTX, MD, HTML, TXT, EPUB, CSV, XML, JSON, LOG | ✅ | ✅ |
| **图像类** | JPG, PNG, GIF, BMP, WEBP, HEIC, PSD, RAW(CR2/NEF/ARW), SVG, TIFF, EXR, HDR, TGA, DDS | ✅ | ✅ |
| **影音类** | MP4, MP3, AVI, MKV, MOV, WAV, FLAC, OGG | ⏯️ | ❌ |
| **压缩包** | ZIP, TAR, GZ, 7Z | 📁 | ❌ |
| **3D/模型** | GLB, GLTF, OBJ, STL, PLY, XMind | 🎮 | ❌ |
| **代码类** | 80+ 种编程语言语法高亮 | ✅ | ❌ |

**说明：** ⏯️=播放 🎮=预览 📁=浏览 ❌=不支持

### 🔧 功能详述

#### Open（打开）
- 拖拽文件到窗口直接打开
- 支持文件关联（可选安装）
- 支持最近打开历史（默认保留 50 条）
- 支持多窗口与分屏预览

#### Edit（编辑）
- Markdown：双模式（预览/编辑），实时渲染
- HTML：代码高亮 + 实时预览
- TXT：纯文本编辑
- CSV：表格编辑
- JSON/XML：语法高亮编辑
- 所有编辑操作支持撤销/重做

#### Convert（转换）
- 文档互转：PDF ↔ Word ↔ Excel ↔ PPT ↔ Markdown ↔ HTML
- 图像互转：主流图片格式互转（WebP、PNG、JPG、TIFF 等）
- PDF 导出：任意文档类可导出为 PDF
- Excel 列转换：自动识别列表/列数据
- 图片转 Base64：前端编码输出

### ⚙️ 快捷键

| 功能 | 快捷键 |
|------|--------|
| 打开文件 | `Ctrl+O` |
| 保存文件 | `Ctrl+S` |
| 命令面板 | `Ctrl+K` |
| 返回首页 | `Ctrl+H` |
| 放大 | `Ctrl++` |
| 缩小 | `Ctrl+-` |
| 全屏 | `F11` |
| 分屏预览 | `Ctrl+Shift+S` |
| 格式转换 | `Ctrl+Shift+C` |
| 打开历史 | `Ctrl+Shift+H` |

### 🛡️ 隐私与安全

- **纯本地运行**：所有文件操作在本地完成，不上传到云端
- **无网络请求**：应用不主动发起任何网络连接（自动更新除外，可选）
- **无遥测数据**：不收集用户文件内容、使用行为等任何数据
- **开源透明**：所有代码公开，欢迎审计

### 📊 性能指标

基于默认配置（Intel i5, 8GB RAM）：

| 指标 | 数值 |
|------|------|
| 冷启动时间 | ≤ 3 秒 |
| 打开 PDF（10MB） | ≤ 1.5 秒 |
| 内存占用（空闲） | 150-200 MB |
| 内存占用（打开大文件） | ≤ 300 MB |
| 安装包体积（未签名） | ~85 MB |

### 🗺️ 路线图

- **v0.6**（当前）：基础格式支持 + 预览 + 编辑 + 转换 ✅

### 🤝 贡献指南

我们欢迎社区贡献！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解如何参与。

**如何贡献：**
- 报告 Bug：提交 [Issue](https://github.com/mmfb-windows/mmfb/issues)
- 功能建议：提交 [Feature Request](https://github.com/mmfb-windows/mmfb/issues)
- 代码贡献：Fork 项目，提交 Pull Request
- 文档改进：修正错别字、补充说明

### 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

### 🙏 致谢

- 感谢 [MMFB Mac 版](https://github.com/xxx) 提供设计理念和前端渲染技术
- 感谢所有开源社区贡献者

---

## English

**One window, open all formats.**

MMFB Windows is a universal file viewer for Windows built with Python + PySide6, supporting preview, edit, and convert for 155+ file formats.

![Version](https://img.shields.io/badge/version-0.6.0-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

### ✨ Features

- **OPEN** - Support 155+ file formats
  - Documents: PDF, Word, Excel, PPT, Markdown, HTML, Code, etc.
  - Images: JPG, PNG, GIF, HEIC, PSD, RAW, SVG, etc.
  - Media: MP4, MP3, AVI, MKV (via system default decoder)
  - Archives: ZIP, TAR, GZ, 7Z
  - 3D Models: GLB, GLTF, OBJ, STL, PLY
  - Mindmaps: XMind

- **EDIT** - In-place editing for common documents
  - 6 document types: Markdown, HTML, Text, CSV, JSON, XML
  - No need to switch software

- **CONVERT** - Online format conversion
  - 9 categories: PDF, Word, Excel, PPT, Markdown, HTML, Images, Text, CSV
  - Built-in conversion engine

- **Design Philosophy**
  - Content First: Auto-hide toolbar, fullscreen content
  - Minimal Aesthetics: Warm paper tone, elegant simplicity
  - Privacy & Security: Pure local operation, no cloud upload
  - All-in-One: Replace dozens of specialized readers

### 🚀 Quick Start

#### Installation

**Option 1: Download Installer (Recommended)**
- Visit [Releases](https://github.com/mmfb-windows/mmfb/releases)
- Download `MMFB-Setup-0.6.0.exe`
- Run installer

**Option 2: Run from Source**
```bash
# Clone repository
git clone https://github.com/mmfb-windows/mmfb.git
cd mmfb

# Install dependencies (Python 3.8+)
pip install -r requirements.txt

# Run application
python main.py
```

#### Requirements
- Windows 10 or higher
- Python 3.8+ (source only)
- Recommended RAM ≥ 4GB

### 📦 Architecture

```
mmfb/
├── main.py                 # Entry point
├── core/                   # Core modules
│   ├── window.py          # Main window
│   ├── webview.py         # Web view wrapper
│   ├── bridge.py          # Python-JS bridge
│   ├── file_handler.py    # File I/O base
│   └── registry.py        # Handler registry
├── handlers/              # Format handlers (20+)
│   ├── pdf_handler.py
│   ├── image_handler.py
│   ├── docx_handler.py
│   └── ...
├── frontend/              # Frontend assets
│   ├── index.html
│   ├── css/
│   ├── js/
│   └── libs/              # PDF.js, CodeMirror, Three.js, etc.
├── services/
│   └── conversion_engine.py  # Conversion engine
└── resources/             # Icons, themes
```

**Tech Stack:**
- **Backend**: Python 3.8+, PySide6 (Qt6), Pillow, python-docx, openpyxl, python-pptx, PyPDF2
- **Frontend**: HTML5 + CSS3 + JavaScript (ES6+)
- **Rendering Engine**: QWebEngineView (Chromium-based)
- **Communication**: QWebChannel bidirectional bridge

### 🎯 Supported Formats

| Category | Formats | Edit | Convert |
|----------|---------|------|---------|
| **Documents** | PDF, DOCX, XLSX, PPTX, MD, HTML, TXT, EPUB, CSV, XML, JSON, LOG | ✅ | ✅ |
| **Images** | JPG, PNG, GIF, BMP, WEBP, HEIC, PSD, RAW(CR2/NEF/ARW), SVG, TIFF, EXR, HDR, TGA, DDS | ✅ | ✅ |
| **Media** | MP4, MP3, AVI, MKV, MOV, WAV, FLAC, OGG | ⏯️ | ❌ |
| **Archives** | ZIP, TAR, GZ, 7Z | 📁 | ❌ |
| **3D/Models** | GLB, GLTF, OBJ, STL, PLY, XMind | 🎮 | ❌ |
| **Code** | 80+ programming languages syntax highlighting | ✅ | ❌ |

**Legend:** ⏯️=playback 🎮=preview 📁=browse ❌=unsupported

### 🔧 Features Detail

#### Open
- Drag & drop file to open
- Optional file association
- Recent files history (50 items)
- Multi-window & split view

#### Edit
- Markdown: dual mode (preview/edit), real-time rendering
- HTML: syntax highlighting + live preview
- TXT: plain text editing
- CSV: table editing
- JSON/XML: syntax highlighted editing
- Undo/Redo support

#### Convert
- Document conversion: PDF ↔ Word ↔ Excel ↔ PPT ↔ Markdown ↔ HTML
- Image conversion: popular formats (WebP, PNG, JPG, TIFF, etc.)
- PDF export: any document to PDF
- Excel column conversion: auto-detect list/column data
- Image to Base64: frontend encoding output

### ⚙️ Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Open File | `Ctrl+O` |
| Save File | `Ctrl+S` |
| Command Palette | `Ctrl+K` |
| Back to Home | `Ctrl+H` |
| Zoom In | `Ctrl++` |
| Zoom Out | `Ctrl+-` |
| Fullscreen | `F11` |
| Split View | `Ctrl+Shift+S` |
| Convert Format | `Ctrl+Shift+C` |
| Open History | `Ctrl+Shift+H` |

### 🛡️ Privacy & Security

- **Pure Local**: All operations on your machine, no cloud upload
- **No Telemetry**: Zero data collection about your files or usage
- **No Network**: No outbound connections (optional updates only)
- **Open Source**: Full transparency, community auditable

### 📊 Performance

Default configuration (Intel i5, 8GB RAM):

| Metric | Value |
|--------|-------|
| Cold Start | ≤ 3 sec |
| PDF Open (10MB) | ≤ 1.5 sec |
| Memory (idle) | 150-200 MB |
| Memory (large file) | ≤ 300 MB |
| Installer Size (unsigned) | ~85 MB |

### 🗺️ Roadmap

- **v0.6** (current): Basic format support + preview + edit + convert ✅

### 🤝 Contributing

We welcome community contributions! Please read [CONTRIBUTING.md](CONTRIBUTING.md) to learn how to get involved.

**Ways to contribute:**
- Report bugs: Submit [Issue](https://github.com/mmfb-windows/mmfb/issues)
- Feature requests: Submit [Feature Request](https://github.com/mmfb-windows/mmfb/issues)
- Code contributions: Fork and submit Pull Request
- Documentation: Fix typos, add clarifications

### 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### 🙏 Acknowledgments

- Thanks to [MMFB Mac](https://github.com/xxx) for design philosophy and frontend rendering tech
- Thanks to all open source contributors

---

**Built with ❤️ for Windows users who love simplicity**.