# Handler 开发指南

Handler（处理器）是 MMFB Windows 扩展文件格式支持的核心机制。每个 handler 封装一种或一类文件格式的预览、编辑逻辑。

## 📦 Handler 基础

### 1. 基类说明

所有 Handler 继承 `mmfb.core.file_handler.FileHandler`：

```python
from mmfb.core.file_handler import FileHandler

class MyHandler(FileHandler):
    @classmethod
    def can_handle(cls, ext: str) -> bool:
        """返回 True 表示此 handler 支持该扩展名"""
        pass

    def get_viewer_html(self, file_path: str) -> str:
        """返回预览模式 HTML 字符串"""
        pass

    def get_editor_html(self, file_path: str) -> Optional[str]:
        """返回编辑模式 HTML 字符串，不支持则返回 None"""
        pass

    def save_file(self, file_path: str, content: bytes) -> bool:
        """保存文件内容（编辑模式调用），默认实现为直接写入"""
        pass
```

### 2. 注册机制

应用启动时，`registry.py` 会自动扫描 `mmfb/handlers/` 目录下所有 `*_handler.py` 文件，导入模块并注册 `FileHandler` 子类。

**无需手动注册**，只需确保：
- 文件名以 `_handler.py` 结尾
- 类名采用 `{Format}Handler` 格式（大写开头）
- 类继承 `FileHandler`

## 🎯 实现示例

### 示例 1：纯文本处理（已存在）

参考 `text_handler.py`：

```python
from ...core.file_handler import FileHandler

class TextHandler(FileHandler):
    @classmethod
    def can_handle(cls, ext: str) -> bool:
        return ext in ['.txt', '.text', '.log']

    def get_viewer_html(self, file_path: str) -> str:
        # 读取文件内容
        content = self._read_file_content(file_path)
        # 返回简单的 HTML，使用 CodeMirror 只读
        return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <link rel="stylesheet" href="libs/codemirror/codemirror.min.css">
            <script src="libs/codemirror/codemirror.min.js"></script>
        </head>
        <body>
            <textarea id="editor">{content}</textarea>
            <script>
                const editor = CodeMirror.fromTextArea(document.getElementById('editor'), {{
                    mode: 'null',
                    readOnly: true,
                    theme: 'default'
                }});
            </script>
        </body>
        </html>
        '''

    def get_editor_html(self, file_path: str) -> str:
        # 编辑模式同理，但 readOnly: false
        content = self._read_file_content(file_path)
        # 可复用上面的模板，仅修改 readOnly 参数
        return self._build_editor_html(content, read_only=False)
```

### 示例 2：调用前端 JS 库（PDF）

参考 `pdf_handler.py`：

```python
class PdfHandler(FileHandler):
    @classmethod
    def can_handle(cls, ext: str) -> bool:
        return ext == '.pdf'

    def get_viewer_html(self, file_path: str) -> str:
        # 返回 HTML 模板，使用 PDF.js 渲染
        with open(os.path.join(self._template_dir, 'pdf_viewer.html'), 'r', encoding='utf-8') as f:
            html = f.read()

        # 替换占位符，注入文件路径和数据
        encoded_path = urllib.parse.quote(file_path)
        html = html.replace('{{file_path}}', encoded_path)

        return html
```

对应的前端模板 `pdf_viewer.html`：

```html
<!DOCTYPE html>
<html>
<head>
    <script src="libs/pdfjs/pdf.min.mjs" type="module"></script>
    <link rel="stylesheet" href="libs/pdfjs/pdf_viewer.min.css">
</head>
<body>
    <div id="viewerContainer">
        <div id="viewer" class="pdfViewer"></div>
    </div>
    <script type="module">
        pdfjsLib.GlobalWorkerOptions.workerSrc = 'libs/pdfjs/pdf.worker.min.mjs';

        const loadingTask = pdfjsLib.getDocument('{{file_path}}');
        loadingTask.promise.then(pdf => {
            // 渲染 PDF 页面
            pdf.getPage(1).then(page => {
                const viewport = page.getViewport({ scale: 1.5 });
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                canvas.height = viewport.height;
                canvas.width = viewport.width;
                document.getElementById('viewer').appendChild(canvas);

                const renderContext = { canvasContext: ctx, viewport: viewport };
                page.render(renderContext);
            });
        });
    </script>
</body>
</html>
```

### 示例 3：处理二进制文件

某些格式（如图像）可能需要直接读取二进制数据：

```python
class ImageHandler(FileHandler):
    @classmethod
    def can_handle(cls, ext: str) -> bool:
        # 使用 Pillow 判断
        try:
            from PIL import Image
            Image.open('dummy' + ext)  # 实际使用时应捕获异常
            return True
        except:
            return False

    def get_viewer_html(self, file_path: str) -> str:
        # 读取二进制数据并.encode('base64')
        with open(file_path, 'rb') as f:
            img_data = f.read()
        import base64
        encoded = base64.b64encode(img_data).decode('utf-8')

        # 返回 HTML 直接嵌入 img 标签
        mime = mimetypes.guess_type(file_path)[0] or 'image/jpeg'
        return f'<img src="data:{mime};base64,{encoded}" style="max-width:100%;">'
```

**注意：** 大文件使用 base64 嵌入会导致 HTML 体积过大。建议：
- 小文件（< 5MB）：base64 直接嵌入
- 大文件：让前端通过 QWebChannel 的 `readFile` 方法读取（已暴露的桥接方法）

## 📂 文件组织

### 模板文件

如果 Handler 需要复杂的 HTML 结构，建议使用模板文件：

1. 在 `mmfb/handlers/templates/` 创建子目录（如 `pdf/`）
2. 存放 `.html` 模板文件
3. 在 `get_viewer_html()` 中读取模板并替换变量

示例：
```python
template_path = os.path.join(
    os.path.dirname(__file__), 'templates', 'pdf', 'viewer.html'
)
with open(template_path, 'r', encoding='utf-8') as f:
    template = f.read()

return template.replace('{{file_path}}', encoded_path)
```

### 静态资源

如果 Handler 需要额外的 CSS/JS 文件：
- 放入 `mmfb/handlers/{format}/static/` 目录
- 在 HTML 模板中使用相对路径引用：`static/style.css`
- 前端会将 `handler_path` 注入全局变量，使用 `window.getHandlerAssetUrl('style.css')` 加载

## 🔌 前端集成

### 路由注册

应用使用 hash 路由，URL 格式：
```
index.html#/view/{ext}?file={encoded_path}
index.html#/edit/{ext}?file={encoded_path}
```

前端 `router.js` 会自动解析 hash，根据扩展名调用对应的 handler 渲染逻辑。

### 桥接通信

前端可通过 `window.pybridge` 调用 Python 方法：

```javascript
// 读取文件
pybridge.readFile('/path/to/file.txt').then(content => {
    console.log(content);
});

// 保存文件
pybridge.saveFile('/path/to/file.txt', new Blob(['Hello World'])).then(() => {
    console.log('Saved');
});

// 获取文件信息
pybridge.getFileInfo('/path/to/file.txt').then(info => {
    console.log(info); // { size, modified, mimeType }
});
```

### 自定义前端逻辑

如果某个格式需要特殊的 JavaScript 渲染逻辑（如 Three.js 3D 渲染），在前端创建对应的模块：

`frontend/js/handlers/pdf.js`:
```javascript
import * as pdfjsLib from 'libs/pdfjs/pdf.min.mjs';

export class PdfHandler {
    static render(container, filePath) {
        // 实现 PDF 渲染逻辑
    }

    static edit(container, filePath) {
        // 实现 PDF 编辑逻辑（如果支持）
    }
}

// 注册到全局
window.handlers = window.handlers || {};
window.handlers['pdf'] = PdfHandler;
```

然后在 HTML 模板中调用：
```html
<script type="module">
    import { PdfHandler } from '../js/handlers/pdf.js';
    PdfHandler.render(document.getElementById('viewer'), '{{file_path}}');
</script>
```

## 🧪 测试

为 Handler 编写单元测试：

```python
import pytest
from mmfb.handlers.text_handler import TextHandler

def test_text_handler_can_handle():
    assert TextHandler.can_handle('.txt') == True
    assert TextHandler.can_handle('.pdf') == False

def test_text_handler_get_viewer_html(tmp_path):
    # 创建测试文件
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello World")

    handler = TextHandler()
    html = handler.get_viewer_html(str(test_file))

    assert 'Hello World' in html
    assert '<!DOCTYPE html>' in html
```

运行测试：
```bash
pytest mmfb/tests/handlers/test_text_handler.py -v
```

### 覆盖率要求

新 Handler 必须：
- 测试 `can_handle()` 对支持和不支持的扩展名
- 测试 `get_viewer_html()` 返回有效 HTML 且包含文件内容
- 测试 `get_editor_html()`（如果支持编辑）
- 测试边界情况（文件不存在、权限错误等）

## 📝 最佳实践

1. **保持简单**：Handler 只负责生成 HTML，复杂逻辑放在前端 JS 或 Python 后端
2. **错误处理**：`can_handle()` 不应抛出异常；读取文件失败时返回错误 HTML
3. **性能**：预览大型文件时使用懒加载和分块渲染
4. **缓存**：利用 QWebEngine 缓存静态资源（CSS/JS 文件）
5. **一致性**：保持与其他 Handler 相似的代码风格
6. **文档**：在类 docstring 中说明支持哪些格式和功能

## 🔍 调试技巧

1. **查看日志**：应用日志在 `%APPDATA%/MMFB/mmfb.log`
2. **控制台输出**：前端 console.log 可在 Qt 开发者工具中查看（F12）
3. **Python 调试**：使用 `print()` 或 `logging.debug()` 输出调试信息
4. **异常捕获**：Handler 方法中使用 try-catch，错误时记录日志

启用开发者工具（Window 类中添加）：
```python
from PySide6.QtWebEngineWidgets import QWebEngineView
self.webview.settings().setAttribute(QWebSettings.LocalContentCanAccessFileUrls, True)
self.webview.page().setDevToolsPage(self.webview.page())  # 允许 F12
```

## 📦 添加新格式的完整步骤

假设要添加 `.foo` 格式支持：

1. **创建 Handler 文件**
   ```bash
   touch mmfb/handlers/foo_handler.py
   ```

2. **实现 Handler 类**
   ```python
   from ...core.file_handler import FileHandler

   class FooHandler(Handler):
       @classmethod
       def can_handle(cls, ext):
           return ext == '.foo'

       def get_viewer_html(self, file_path):
           # TODO: 实现
           pass

       def get_editor_html(self, file_path):
           # 如果支持编辑
           return self.get_viewer_html(file_path)  # 或返回 None（不支持）
   ```

3. **编写单元测试**
   ```bash
   touch mmfb/tests/handlers/test_foo_handler.py
   ```

4. **添加前端资源（可选）**
   - 创建 `frontend/js/handlers/foo.js`
   - 或在 HTML 模板中直接内联脚本

5. **更新文档**
   - 在 `project.md` 格式支持列表中提及
   - 在 CHANGELOG 中记录

6. **提交**
   ```bash
   git add mmfb/handlers/foo_handler.py mmfb/tests/handlers/test_foo_handler.py
   git commit -m "feat: add support for .foo format"
   ```

完成！

---

## 📖 更多资源

- [架构概述](architecture.md) - 理解系统整体设计
- [前端开发指南](frontend-development.md) - 前端资源组织
- [测试指南](testing.md) - 完整测试策略
