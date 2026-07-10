# 前端开发指南

MMFB Windows 的前端基于 HTML5 + CSS3 + JavaScript (ES6+)，运行在 QWebEngineView（Chromium）环境中。

## 📁 目录结构

```
mmfb/frontend/
├── index.html          # 应用入口，前端路由起点
├── css/
│   ├── main.css        # 主样式
│   ├── theme.css       # 主题变量（浅/深/暖纸）
│   └── components/     # 组件样式
├── js/
│   ├── router.js       # 路由系统（hash 路由）
│   ├── bridge.js       # QWebChannel Python 桥接封装
│   ├── command_palette.js  # 命令面板（Ctrl+K）
│   ├── conversion_viewer.js # 转换 UI
│   ├── history_viewer.js   # 历史记录
│   ├── settings_viewer.js  # 设置
│   ├── viewers/        # 各类格式预览器
│   │   ├── home_viewer.js
│   │   ├── pdf_viewer.js
│   │   ├── markdown_viewer.js
│   │   └── ...
│   └── handlers/       # 特定格式的前端渲染逻辑
│       ├── pdf.js      # PDF.js 集成
│       ├── three.js    # Three.js 3D 渲染
│       └── ...
└── libs/               # 第三方 JS 库（不修改）
    ├── pdfjs/
    ├── codemirror/
    ├── three/
    ├── milkdown/
    ├── sheetjs/
    └── ...
```

## 🚀 开发工作流

1. **本地修改**
   - 编辑前端文件（HTML/CSS/JS）
   - 不需要打包，直接重新运行应用即可看到效果

2. **热重载**
   - 应用默认启用开发模式（如果检测到 `DEBUG` 环境变量）
   - `QWebEngineView` 会自动加载最新文件
   - 按 F5 或调用 `window.location.reload()` 刷新

3. **调试**
   - 在 QWebEngineView 中按 F12 打开开发者工具
   - Console 查看 JavaScript 错误
   - Network 查看资源加载
   - Sources 查看源代码和设置断点

## 📡 桥接通信（bridge.js）

前端通过 `window.pybridge` 对象与 Python 后端通信：

```javascript
// 读取文件内容（文本或二进制）
async function readText(path) {
    const data = await pybridge.readFile(path);
    // data 是 Uint8Array 或 string（根据文件类型）
    const text = new TextDecoder().decode(data);
    return text;
}

// 保存文件
async function saveFile(path, content, mime = 'text/plain') {
    const blob = new Blob([content], { type: mime });
    await pybridge.saveFile(path, blob);
}

// 获取文件信息
const info = await pybridge.getFileInfo('/path/to/file.pdf');
// info = { size: 123456, modified: '2026-07-10T...', mimeType: 'application/pdf' }

// 格式转换（异步）
const jobId = await pybridge.convertFile(
    '/input.pdf',
    '/output.png',
    'pdf_to_image'
);
// 监听转换完成
pybridge.onConversionFinished((jobId, success, error, outputPath) => {
    if (success) {
        console.log('Converted to:', outputPath);
    }
});
```

**注意：**
- 所有通信都是异步（返回 Promise）
- `readFile` 读取大文件可能阻塞，建议只在必要时调用
- `saveFile` 会覆盖原文件，注意备份

## 🧭 路由系统（router.js）

应用使用 hash 路由，URL 格式：
```
index.html#/view/{ext}?file={encoded_path}
index.html#/edit/{ext}?file={encoded_path}
index.html#/convert
index.html#/settings
index.html#/history
```

### 路由跳转

```javascript
// 导航到文件预览
window.MMFBRouter.navigate(`/view/${ext}?file=${encodeURIComponent(path)}`);

// 导航到编辑模式
window.MMFBRouter.navigate(`/edit/${ext}?file=${encodeURIComponent(path)}`);

// 其他页面
window.MMFBRouter.navigate('/convert');
window.MMFBRouter.navigate('/settings');
```

### 路由拦截

在页面卸载前（如切换到其他文件）可以清理资源：

```javascript
router.onBeforeUnload(async () => {
    // 清理工作：关闭 MediaPlayer、停止 Three.js 动画等
    if (window.currentPlayer) {
        window.currentPlayer.pause();
        window.currentPlayer = null;
    }
});
```

## 📺 预览器开发

### 1. 创建预览器模块

在 `frontend/js/viewers/` 创建 `myformat_viewer.js`：

```javascript
export class MyFormatViewer {
    constructor(container) {
        this.container = container;
        this.filePath = null;
    }

    async load(filePath) {
        this.filePath = filePath;
        this.container.innerHTML = 'Loading...';

        try {
            // 获取文件内容
            const data = await pybridge.readFile(filePath);

            // 渲染内容
            this.render(data);
        } catch (error) {
            this.container.innerHTML = `
                <div class="error">
                    <h3>Failed to load file</h3>
                    <p>${error.message}</p>
                </div>
            `;
        }
    }

    render(data) {
        // TODO: 实现渲染逻辑
        this.container.innerHTML = `<pre>${data}</pre>`;
    }

    destroy() {
        // 清理资源
        this.container.innerHTML = '';
    }
}

// 注册
window.viewers = window.viewers || {};
window.viewers['myformat'] = MyFormatViewer;
```

### 2. 在路由中调用

`router.js` 中的路由表：

```javascript
const routeHandlers = {
    '/view': async (params) => {
        const { ext, file } = params;
        const viewerClass = window.viewers[ext];
        if (!viewerClass) {
            // 未找到预览器，显示 "无法预览" 页面
            renderUnsupported(ext);
            return;
        }

        const viewer = new viewerClass(document.getElementById('content'));
        await viewer.load(file);
    },

    '/edit': async (params) => {
        // 类似，使用 editor 而不是 viewer
    }
};
```

## 🎨 CSS 主题系统

主题变量定义在 `css/theme.css`：

```css
:root {
    /* 暖纸色调（默认） */
    --bg-primary: #fdf6e3;
    --bg-secondary: #f5ead6;
    --text-primary: #333333;
    --text-secondary: #666666;
    --accent-color: #d4a574;
    --border-color: #e8dcc8;
    --toolbar-bg: rgba(253, 246, 227, 0.95);

    /* 字体 */
    --font-serif: Georgia, 'Times New Roman', serif;
    --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    --font-mono: 'Fira Code', 'Consolas', monospace;
}

/* 深色主题 */
[data-theme="dark"] {
    --bg-primary: #1a1a1a;
    --bg-secondary: #242424;
    --text-primary: #e0e0e0;
    --text-secondary: #a0a0a0;
    --accent-color: #4a90d9;
    --border-color: #333333;
    --toolbar-bg: rgba(26, 26, 26, 0.95);
}

/* 浅色主题 */
[data-theme="light"] {
    --bg-primary: #ffffff;
    --bg-secondary: #f5f5f5;
    --text-primary: #212121;
    --text-secondary: #757575;
    --accent-color: #2196f3;
    --border-color: #e0e0e0;
    --toolbar-bg: rgba(255, 255, 255, 0.95);
}
```

使用时：
```css
body {
    background: var(--bg-primary);
    color: var(--text-primary);
    font-family: var(--font-sans);
}
```

## 📦 第三方库使用

所有第三方库放在 `frontend/libs/`，不要修改这些库的文件。

### 加载方式

**ES Modules（推荐）：**
```html
<script type="module">
    import * as pdfjsLib from '../libs/pdfjs/pdf.min.mjs';
    pdfjsLib.GlobalWorkerOptions.workerSrc = '../libs/pdfjs/pdf.worker.min.mjs';
</script>
```

**Script 标签（传统）：**
```html
<script src="../libs/codemirror/codemirror.min.js"></script>
<link rel="stylesheet" href="../libs/codemirror/codemirror.min.css">
```

### 添加新库

1. 下载 JS 库到 `frontend/libs/{name}/`
2. 更新 `README.md` 依赖列表（如需）
3. 在使用的地方引入

## 🛠️ 常用工具函数

`bridge.js` 封装了一些常用方法：

```javascript
// URL 编解码（处理路径中的特殊字符）
const encodedPath = encodeURIComponent(filePath);
const decodedPath = decodeURIComponent(encodedPath);

// Base64 编码
const base64 = btoa(String.fromCharCode(...new Uint8Array(data)));
const binary = Uint8Array.from(atob(base64), c => c.charCodeAt(0));

// MIME 类型检测
const mime = await pybridge.getMimeType(filePath);
// 或使用浏览器 API
const mimeFromContent = blob.type;

// 防抖 & 节流
const debouncedSave = debounce(saveFile, 500);
const throttledResize = throttle(handleResize, 100);
```

## 🧪 测试

前端单元测试使用 Jest 或 Vitest（暂未配置，可后续添加）。

集成测试通过 Python 的 `smoke_test.py` 启动应用并模拟操作。

## 🐛 调试技巧

1. **查看桥接日志**
   ```javascript
   // 在 bridge.js 中启用调试
   window.pybridge.setDebug(true);
   ```

2. **捕获未处理的 Promise 错误**
   ```javascript
   window.addEventListener('unhandledrejection', (event) => {
       console.error('Unhandled promise rejection:', event.reason);
   });
   ```

3. **查看路由状态**
   ```javascript
   console.log('Current route:', window.MMFBRouter.currentRoute);
   ```

4. **强制刷新**
   ```javascript
   window.location.reload(true); // 强制从服务器加载（忽略缓存）
   ```

## ⚡ 性能优化

1. **懒加载大库**
   ```javascript
   // 按需加载 Three.js
   if (is3DFile) {
       const THREE = await import('../libs/three/build/three.module.js');
   }
   ```

2. **资源缓存**
   - QWebEngine 自动缓存静态资源
   - 大文件使用 `QWebEngineSettings.LocalStorageEnabled` 持久化

3. **避免内存泄漏**
   - 页面切换时调用 `destroy()` 清理资源
   - 移除事件监听器
   - 停止定时器和动画

4. **减少重排重绘**
   - 使用 `transform` 和 `opacity` 进行动画（GPU 加速）
   - 避免 `table` 布局，使用 Flex/Grid
   - 批量 DOM 操作，使用 `DocumentFragment`

## 📱 响应式设计

应用主要为桌面端设计，但也支持窗口缩放：

```css
/* 基础布局 */
#app {
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
}

/* 内容区域自适应 */
#content {
    flex: 1;
    overflow: auto;
}

/* 移动端适配（如果未来支持） */
@media (max-width: 768px) {
    .toolbar {
        flex-wrap: wrap;
    }

    .command-palette {
        width: 100%;
        max-height: 50vh;
    }
}
```

## 🔒 安全注意事项

1. **XSS 防护**
   - 不要使用 `innerHTML` 插入用户文件内容（除非 sanitize）
   - 使用 `textContent` 或专门的模板引擎

2. **路径验证**
   - 所有文件路径通过 `pybridge` API 获取，不要拼接字符串
   - Python 端已验证路径合法性（前端可信任）

3. **避免 eval()**
   - 不要使用 `eval()` 或 `new Function()`
   - JSON 解析使用 `JSON.parse()`

4. **内容安全策略（CSP）**
   - `index.html` 设置了 CSP meta 标签
   - 如需内联脚本，使用 nonce 或 hash

## 📚 参考资料

- [Qt WebEngine 文档](https://doc.qt.io/qt-6/qwebengineview.html)
- [QWebChannel 文档](https://doc.qt.io/qt-6/qwebchannel.html)
- [MDN Web Docs](https://developer.mozilla.org/)
- [PDF.js 指南](https://mozilla.github.io/pdf.js/)
- [Three.js 文档](https://threejs.org/docs/)
- [CodeMirror 6 手册](https://codemirror.net/)

---

## 🎯 快速检查清单

- [ ] 遵循现有代码风格（4 空格缩进、命名规范）
- [ ] Handler 在路由中注册（`window.viewers[ext]`）
- [ ] 错误处理（try-catch + 用户友好提示）
- [ ] 清理资源（destroy 方法）
- [ ] 测试边界情况（文件不存在、权限错误）
- [ ] 检查控制台无错误
- [ ] 更新相关文档

Happy coding! 🎉
