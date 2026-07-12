# MMFB Windows - 万能阅览器项目

> 参考 Mac 版 MMFB，打造 Windows 版的"一个窗口，打开所有格式"

## 一、项目目标

### 核心定位
开发一款 Windows 平台的万能文件阅览器，实现三大核心能力：
- **看** (OPEN)：支持 155+ 种文件格式，一个应用搞定所有
- **改** (EDIT)：就地编辑常用文档，无需切换软件
- **转** (CONVERT)：在线格式互转，省去寻找工具的麻烦

### 设计哲学
- **内容优先**：默认隐藏工具栏，满屏显示文件内容
- **克制美学**：暖纸色调，优雅简洁，工具属性低于内容属性
- **隐私安全**：纯本地运行，文件不出本机，不上传云端
- **收纳整合**：替代 Dock 上的一堆专用应用，一个 App 解决所有阅读需求

---

## 二、技术选型

### 2.1 架构栈

**决策：Python + PySide6 (Qt for Python)**

- **理由**：用户已有 Python 环境，无需额外安装 Rust/MSVC；PySide6 提供原生 WebView (QWebEngineView 基于 Chromium)，可直接复用 MMFB 的 JS 渲染库；Python 格式解析库生态丰富，覆盖 155+ 格式更便捷
- **渲染层**：QWebEngineView (内嵌 Chromium 引擎，无需用户安装 WebView2 Runtime)
- **后端层**：Python 提供文件系统访问、格式解析、进程管理
- **前端**：HTML + CSS + JavaScript (与 MMFB 完全相同的 JS 库)
- **通信**：QWebChannel 实现 Python ↔ JavaScript 双向调用

### 2.2 核心依赖列表

**Python 后端库：**
- GUI 框架：`PySide6` (Qt6 绑定)
- Web 引擎：`PySide6-WebEngine` (QWebEngineView + QWebChannel)
- 图像处理：`Pillow` + `rawpy` + `pyheif`
- 文档解析：`python-docx` / `openpyxl` / `python-pptx` / `PyPDF2` / `pypdf`
- 压缩包：`zipfile` / `tarfile` (标准库) + `py7zr`
- 3D 模型：`pyassimp` (解析) + three.js (渲染)
- 格式转换：`pdf2image` / `mammoth` / `markdownify`
- 系统集成：`pywin32` (注册表/托盘/快捷键) / `pystray` (托盘图标)
- 打包：`PyInstaller` + `NSIS`

**前端渲染库（直接复用 MMFB 技术栈）：**
- PDF 渲染：`pdf.js`
- Markdown：`@milkdown/core` + `@milkdown/crepe`
- 代码高亮：`codemirror@6`（支持 80+ 语言）
- Excel：`sheetjs`
- Word：`docx.js`
- PPT：`pptxgenjs` + `@zip.js/zip.js`
- 图像处理：`pica`（前端缩放）
- 3D 模型：`three.js` + `@react-three/fiber`
- 压缩包：`jszip` + `fflate`
- PSD：`ag-psd`
- HEIC：`@jsquash/heic` 或 `libheif-js`
- RAW：`libraw-wasm`（提取内嵌 JPEG 预览）
- 游戏贴图：`@loaders.gl/textures`
- FFmpeg：`@ffmpeg/ffmpeg` + `@ffmpeg/core`（WASM 回退）
- 表格：`TanStack Table` 或 `ag-grid`

**格式转换引擎：**
- 文档互转：Milkdown + turndown + pdf-lib
- 表格互转：sheetjs
- 图像互转：Pillow (Python 后端)
- PDF 导出：`pdf-lib` (前端) 或 `reportlab` (后端)

**系统集成：**
- 文件关联：`winreg` (pywin32)
- 系统托盘：`pystray` 或 QSystemTrayIcon
- 全局快捷键：`pywin32` 或 `keyboard` 库
- 自动更新：自定义实现 (GitHub Releases API)

**打包部署：**
- PyInstaller 打单文件 exe
- NSIS 制作安装包
- 代码签名：Sectigo / DigiCert EV 证书

---

## 三、格式支持计划（与 v0.6 一致）

### 3.1 文档类 (15 种)
### 3.2 图像类 (37 种)
### 3.3 影音类 (10 种)
### 3.4 压缩包类 (4 种)
### 3.5 3D/图谱类 (6 种)
### 3.6 代码/数据类 (83 种)

---

## 四、功能模块设计（与 v0.6 一致）

### 4.1 打开模块 (OPEN)
### 4.2 编辑模块 (EDIT)
### 4.3 转换模块 (CONVERT)

---

## 五、技术实现细节

### 5.1 PySide6 应用结构

```
mmfb/
├── main.py                 # 应用入口
├── core/
│   ├── window.py           # 主窗口 (QMainWindow)
│   ├── webview.py          # QWebEngineView 封装
│   ├── bridge.py           # QWebChannel Python 对象
│   ├── file_handler.py     # 文件读写基类
│   └── registry.py         # Handler 注册表
├── handlers/               # 各格式处理器
│   ├── pdf_handler.py
│   ├── image_handler.py
│   └── ...
├── frontend/               # 前端资源
│   ├── index.html
│   ├── css/
│   ├── js/
│   └── libs/               # 第三方 JS 库
├── resources/              # 图标、主题等
└── build.spec              # PyInstaller 配置
```

### 5.2 Python ↔ JS 通信

通过 QWebChannel 暴露 Python 对象给前端：
- `pybridge.readFile(path)` → 返回文件内容
- `pybridge.saveFile(path, data)` → 保存文件
- `pybridge.getFileInfo(path)` → 返回元数据
- `pybridge.convertFile(src, dst, format)` → 格式转换

前端通过 `window.pybridge` 调用上述方法。

### 5.3 安全考虑

- QWebEngineView 禁用远程内容加载
- 所有文件操作限制在用户指定路径
- 不发起任何网络请求（纯本地运行）
- 沙箱模式运行前端 JS

---

## 六、开发里程碑（12 周，2026-07-06 ~ 2026-08-13）

| 阶段 | 周次 | 里程碑 | 状态 |
|------|------|--------|------|
| 1 基础框架 | W1 (7/6-7/11) | PySide6 骨架；无边框窗口；WebChannel 通信；文件拖拽；Handler 基类 | ✅ |
| 2 文档核心 | W2 (7/14-7/16) | 文档类 15 种预览 + 6 种编辑 | ✅ |
| 3 图像系统 | W3 (7/18-7/22) | 图像类 37 种预览 + 基础编辑 | ✅ |
| 4 影音与3D | W4 (7/23-7/25) | 影音 + 压缩包 + 3D/ XMind | ✅ |
| 5 转换引擎 | W5 (7/28-7/30) | 9 类互转引擎 + 转换 UI | ✅ |
| 6 UI/UX | W5 末- W6 初 (7/31-8/1) | 内容优先；主题；历史；快捷键 | ✅ |
| 7 系统集成 | W6 (8/4-8/6) | 文件关联；右键菜单；托盘；快捷键；更新 | ✅ |
| 8 打包与发布 | W7-W8 (8/7-8/13) | PyInstaller+NSIS；签名；CI/CD；文档；官网；v0.6 发版 | ⬜ |

**任务共 53 个，全部 manual 排期，用户逐个执行。**

---

## 七、交付清单

- MMFB Windows v0.6 安装包 (.exe)
- NSIS 安装脚本
- 用户手册 (PDF)
- 开发者文档
- 官网页面
- 源代码 (GitHub)

---

## 八、验收标准

- 支持 155+ 格式正确打开
- 6 类文档可就地编辑并保存
- 9 类格式互转功能正常
- 安装包体积 ≤ 100 MB
- 冷启动时间 ≤ 3 秒
- 内存占用 ≤ 300 MB (打开 10MB 文件时)

---

## 九、风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| PyInstaller 打包体积大 | 使用 UPX 压缩；排除不必要依赖 |
| QWebEngineView 内存占用高 | 单进程模式；大文件分块加载 |
| 部分格式 Python 库支持不足 | 调用外部工具或 WASM 兜底 |
| 代码签名证书费用 | 初期可用自签名，正式版再购买 EV 证书 |

---

## 十、版本路线图

- v0.8：基础格式支持 + 预览 + 编辑 + 转换 + 拖拽/分屏稳定性修复

---

## 十一、当前任务进度

共拆解为 53 个原子子任务，详见项目管理工具（list_tasks）。