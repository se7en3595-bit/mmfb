# 架构概述

## 整体架构

MMFB Windows 采用 **Python 后端 + Qt WebEngine 前端** 的混合架构：

```
┌─────────────────────────────────────────────────────────────┐
│                        用户界面层                            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │            QMainWindow (PySide6)                      │  │
│  │  ┌─────────────┐  ┌─────────────────────────────────┐ │  │
│  │  │  Title Bar  │  │  Content Area (WebEngineView)   │ │  │
│  │  └─────────────┘  │  - 渲染 HTML/JS/CSS              │ │  │
│  │                    │  - 通过 QWebChannel 通信         │ │  │
│  └────────────────────┴─────────────────────────────────┘ │  │
└─────────────────────────────────────────────────────────────┘
                            │ QWebChannel
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     Python 桥接层                            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Bridge (bridge.py)                      │  │
│  │  - 暴露 Python 方法给前端                             │  │
│  │  - 接收前端调用并转换                                 │  │
│  │  - 信号槽机制                                        │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │ 调用
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    核心服务层                                │
│  ┌────────────┐  ┌────────────┐  ┌─────────────────────┐  │
│  │ File I/O   │  │  Registry  │  │  History Manager    │  │
│  │ - readFile │  │ - Handler  │  │  - 打开历史         │  │
│  │ - saveFile │  │   注册表   │  │  - 收藏管理         │  │
│  └────────────┘  └────────────┘  └─────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │           Handler 扩展点 (20+ handlers)              │  │
│  │  - pdf_handler.py  - image_handler.py               │  │
│  │  - docx_handler.py - xlsx_handler.py               │  │
│  │  - ...                                              │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │           Conversion Engine                          │  │
│  │  - 文档互转：Milkdown + pdf-lib                     │  │
│  │  - 图像互转：Pillow                                 │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    文件系统层                                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │             本地文件系统                              │  │
│  │  - *.pdf, *.docx, *.xlsx, *.png, ...               │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 核心模块说明

### 1. mmfb/core/

**window.py** - 主窗口
- QMainWindow 子类
- 管理标题栏、工具栏、内容区
- 处理全局事件（拖拽、快捷键）

**webview.py** - Web 视图封装
- QWebEngineView 单例
- 加载 `frontend/index.html`
- 注入 QWebChannel

**bridge.py** - 通信桥
- 继承 `QObject` 暴露给 JavaScript
- 定义槽函数供前端调用：
  - `readFile(path)` → bytes 或 str
  - `saveFile(path, data)`
  - `getFileInfo(path)`
  - `convertFile(src, dst, format)`
- 定义信号供前端订阅：
  - `fileOpened`
  - `conversionFinished`

**file_handler.py** - 文件处理抽象基类
- `FileHandler` 基类定义接口：
  - `can_handle(ext)` - 是否支持该格式
  - `get_editor_html(path)` - 返回编辑器 HTML（编辑模式）
  - `get_viewer_html(path)` - 返回预览器 HTML（预览模式）
- 具体格式的 handler 继承并实现

**registry.py** - Handler 注册表
- 应用启动时自动扫描 `mmfb/handlers/` 模块
- 注册所有 `FileHandler` 子类
- 根据文件扩展名查找合适的 handler

### 2. mmfb/handlers/

每个文件对应一种或一类格式的处理逻辑。

**文件命名规范：**
- `{format}_handler.py`（如 `pdf_handler.py`）
- 导出一个类 `{Format}Handler(FileHandler)`（如 `PdfHandler`）
- 实现 `can_handle()`、`get_viewer_html()`、`get_editor_html()`（如果支持）

**示例结构：**
```python
from ..core.file_handler import FileHandler

class PdfHandler(FileHandler):
    @classmethod
    def can_handle(cls, ext: str) -> bool:
        return ext in ['.pdf']

    def get_viewer_html(self, file_path: str) -> str:
        # 返回注入 PDF.js 的 HTML
        return self._render_template('pdf_viewer.html', path=file_path)

    def get_editor_html(self, file_path: str) -> str:
        # PDF 不支持编辑（只读）
        return None
```

### 3. mmfb/frontend/

前端资源目录，包含：

- `index.html` - 前端入口
- `css/` - 样式文件
  - `main.css` - 主样式
  - `theme.css` - 主题变量
- `js/` - JavaScript 模块
  - `router.js` - 前端路由（支持 #hash 路由）
  - `bridge.js` - QWebChannel 封装
  - `command_palette.js` - 命令面板（Ctrl+K）
  - `conversion_viewer.js` - 转换界面
  - `settings_viewer.js` - 设置界面
  - `history_viewer.js` - 历史记录
- `libs/` - 第三方 JS 库（npm 或手动下载）
  - `pdfs/` - PDF.js
  - `codemirror/` - CodeMirror 6
  - `three/` - Three.js
  - `milkdown/` - Milkdown Markdown 编辑器
  - `sheetjs/` - SheetJS（Excel）
  - `jszip/` - JSZip（压缩包）
  - ...

**前端路由机制：**

应用使用 hash 路由（`index.html#/view/{ext}?file={path}`）：

| Route | Handler | 描述 |
|-------|---------|------|
| `/` | HomeViewer | 首页（欢迎页、快捷入口） |
| `/view/{ext}` | 对应 Handler Viewer | 文件预览 |
| `/edit/{ext}` | 对应 Handler Editor | 文件编辑 |
| `/convert` | ConversionViewer | 格式转换工具 |
| `/settings` | SettingsViewer | 设置页面 |
| `/history` | HistoryViewer | 打开历史 |

### 4. mmfb/services/

**conversion_engine.py** - 格式转换引擎
提供统一的文件格式转换接口：
```python
class ConversionEngine:
    def convert(src: str, dst: str, from_format: str, to_format: str) -> bool:
        ...
```

支持的转换：
- 文档：Markdown ↔ HTML ↔ PDF ↔ Word ↔ Excel ↔ PPT
- 图像：任意格式 ↔ WebP/PNG/JPG/TIFF
- 文本提取：PDF → TXT，Word → TXT，Excel → CSV

## 数据流

### 打开文件

```
用户拖拽文件
    ↓
Window.dropEvent()
    ↓
Bridge.openFile(path) → 读取文件
    ↓
Router.navigate('/view/{ext}?file={path}')
    ↓
HandlerRegistry.get_handler(ext).get_viewer_html()
    ↓
WebView.setHtml() + QWebChannel 注入
    ↓
前端根据 ext 选择渲染器（PDF.js、CodeMirror、Three.js 等）
```

### 编辑文件

```
前端调用 pybridge.saveFile(path, data)
    ↓
Bridge.saveFile() → 写入文件
    ↓
emit fileSaved 信号
    ↓
前端显示 "已保存" 提示
```

### 格式转换

```
前端调用 pybridge.convertFile(src, dst, format)
    ↓
Bridge.convert_file() → 启动后台线程
    ↓
ConversionEngine.convert() 执行转换
    ↓
emit conversionFinished(jobId, success, error)
    ↓
前端根据 jobId 更新进度状态
```

## 安全设计

1. **沙箱浏览器**
   - QWebEngineView 使用 `--no-sandbox` 禁用危险的沙箱逃逸
   - 禁用远程内容加载：`settings().setAttribute(QWebSettings.LocalContentCanAccessRemoteUrls, False)`
   - 仅允许 file:// 协议访问本地文件

2. **文件系统权限**
   - 所有文件操作基于用户选择的路径
   - 不对系统目录进行写入
   - 路径合法性检查（防范路径遍历攻击）

3. **无网络通信**
   - 除自动更新（可选）外，不发网络请求
   - 更新检查使用 GitHub Releases API（HTTPS）

4. **代码签名**
   - v1.0+ 使用 EV 证书签名
   - Windows SmartScreen 信任

## 性能优化

- **单进程模式**：QWebEngine 使用单进程避免多进程开销
- **懒加载**：前端 JS 库按需加载
- **缓存**：QWebEngine 缓存静态资源（CSS/JS）
- **分块读取**：大文件（PDF、图像）分块处理
- **Worker 线程**：转换操作在后台线程执行

## 错误处理

- **前端**：try-catch + 用户友好的错误提示页
- **后端**：异常捕获 + 日志记录到 mmfb.log
- **桥接**：跨线程通信使用信号传递错误码
- **Handler**：`can_handle()` 失败返回静态找不到资源的页

## 日志系统

日志文件位置：`%APPDATA%/MMFB/mmfb.log`

日志级别：DEBUG、INFO、WARNING、ERROR

示例：
```python
import logging
logging.basicConfig(
    filename=os.path.join(app_data_path, 'mmfb.log'),
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
```

## 扩展性

要添加新格式支持：

1. 在 `mmfb/handlers/` 创建 `newformat_handler.py`
2. 实现 `FileHandler` 基类接口
3. 在前端 `frontend/js/` 添加对应的渲染逻辑（或使用通用渲染器）
4. 在 `frontend/libs/` 添加所需的 JS 库（如有）
5. 在 `project.md` 格式支持列表中更新

无需修改核心代码，仅需添加新 handler 即可。注册表会自动发现。

---

## 相关文档

- [Handler 开发指南](handler-development.md)
- [前端开发指南](frontend-development.md)
- [构建与打包](build.md)
- [测试指南](testing.md)
