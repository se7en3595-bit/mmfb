# 代码规范

本文档定义 MMFB Windows 项目的代码风格和质量标准。

## 📐 Python 规范

### 遵循标准

- **PEP 8** - [Style Guide for Python Code](https://pep8.org/)
- **Black** 格式化（行宽 88）
- **isort** 导入排序
- **flake8** 代码检查

### 自动格式化

安装：
```bash
pip install black isort
```

格式化整个项目：
```bash
black mmfb/
isort mmfb/
```

### 代码检查

```bash
pip install flake8
flake8 mmfb/
```

flake8 配置（`.flake8`）：
```ini
[flake8]
max-line-length = 88
extend-ignore = E203, W503
exclude =
    .git,
    __pycache__,
    build,
    dist,
    .venv,
    venv,
    migrations,
    node_modules,
    frontend/libs
```

### 命名约定

| 类型 | 约定 | 示例 |
|------|------|------|
| 模块 | snake_case | `pdf_handler.py`, `file_utils.py` |
| 包 | snake_case | `mmfb`, `handlers` |
| 类 | PascalCase | `PdfHandler`, `MainWindow` |
| 函数 | snake_case | `read_file()`, `can_handle()` |
| 变量 | snake_case | `file_path`, `handler` |
| 常量 | UPPER_SNAKE_CASE | `MMFB_VERSION`, `MAX_FILE_SIZE` |
| 私有成员 | _前缀 | `_read_private()` |
| 魔术方法 | __双下划线__ | `__init__()`, `__str__()` |

### 文档字符串

使用 Google 风格：

```python
def read_file(file_path: str) -> bytes:
    """读取文件内容为字节流。

    Args:
        file_path: 文件绝对路径

    Returns:
        文件内容的字节流

    Raises:
        FileNotFoundError: 文件不存在
        PermissionError: 无权限读取
    """
    with open(file_path, 'rb') as f:
        return f.read()
```

类文档：
```python
class PdfHandler(FileHandler):
    """PDF 文件处理器。

    支持 PDF 文档的预览和文本提取。
    不支持的编辑操作（PDF 为只读格式）。

    Attributes:
        DEFAULT_ZOOM (float): 默认缩放比例 1.0
    """

    DEFAULT_ZOOM = 1.0
```

### 类型提示

**必须** 为所有公共函数和类方法添加类型提示：

```python
from typing import Optional, List, Dict, Any

def process_file(
    file_path: str,
    options: Optional[Dict[str, Any]] = None
) -> bool:
    """处理文件并返回是否成功"""
    ...

def get_supported_formats() -> List[str]:
    """返回支持的格式列表"""
    return ['.pdf', '.docx']
```

### 导入顺序

遵循 PEP 8 导入顺序（isort 会自动排序）：

1. 标准库
2. 第三方库
3. 本地应用/库

示例：
```python
# 1. 标准库
import os
import sys
import logging
from pathlib import Path
from typing import Optional

# 2. 第三方库
from PySide6.QtWidgets import QMainWindow
from PIL import Image
import numpy as np

# 3. 本地模块
from mmfb.core.bridge import Bridge
from mmfb.handlers.pdf_handler import PdfHandler
```

### 代码行长度

- **88 字符**（遵循 Black 默认）
- 长表达式可以换行，保持可读性：

```python
# Good
result = some_very_long_function_name(
    argument_one, argument_two,
    argument_three, argument_four
)

# Bad
result = some_very_long_function_name(argument_one, argument_two, argument_three, argument_four, argument_five, argument_six)
```

### 条件判断

**不要**使用 `if x == True` 或 `if x == False`：

```python
# Good
if is_valid:
if not is_valid:

# Bad
if is_valid == True:
if is_valid == False:
```

### 列表推导式

优先使用列表推导式（更 Pythonic）：

```python
# Good
files = [f for f in os.listdir(dir) if f.endswith('.pdf')]

# Bad
files = []
for f in os.listdir(dir):
    if f.endswith('.pdf'):
        files.append(f)
```

### 上下文管理器

使用 `with` 语句管理资源：

```python
# Good
with open(file_path, 'r') as f:
    content = f.read()

# Bad
f = open(file_path, 'r')
content = f.read()
f.close()
```

## 🎨 JavaScript 规范

### ES6+ 语法

- 使用 `const` 定义常量，`let` 定义变量
- 不使用 `var`
- 使用箭头函数

```javascript
// Good
const name = 'MMFB';
let count = 0;
const handler = () => { ... };

// Bad
var name = 'MMFB';
var count = 0;
function handler() { ... }
```

### 异步代码

优先使用 `async/await`：

```javascript
// Good
async function loadFile(path) {
    const content = await pybridge.readFile(path);
    return content;
}

// Bad
function loadFile(path) {
    return pybridge.readFile(path).then(content => {
        return content;
    });
}
```

### 字符串拼接

使用模板字符串：

```javascript
// Good
const message = `Hello, ${name}! You have ${count} files.`;

// Bad
const message = 'Hello, ' + name + '! You have ' + count + ' files.';
```

### 分号

**项目使用**：**不加分号**（JavaScript 标准风格）

```javascript
// Good
const name = 'MMFB'
function foo() { ... }

// Bad
const name = 'MMFB';
```

### 缩进

- **2 空格**（与 CSS 一致）
- 不使用 Tab

### 注释

- 单行注释：`//`
- 多行注释：`/* */`

函数头部应添加 JSDoc：

```javascript
/**
 * 读取文件内容
 * @param {string} path - 文件路径
 * @returns {Promise<string>} 文件内容
 */
async function readText(path) {
    const data = await pybridge.readFile(path);
    return new TextDecoder().decode(data);
}
```

### 错误处理

使用 `try-catch` 处理异步错误：

```javascript
async function loadFile(path) {
    try {
        const content = await pybridge.readFile(path);
        return content;
    } catch (error) {
        console.error('Failed to load file:', error);
        throw error;
    }
}
```

## 🎭 CSS 规范

### 命名方法

- **BEM**（推荐）：Block__Element--Modifier
- **蛇形命名**（小写 + 短横线）

示例：
```css
/* Good */
.toolbar__button--active
.file-viewer
.settings-panel

/* Bad */
ToolbarButtonActive
fileViewer
SettingsPanel
```

### 缩进

2 空格，属性对齐（可选）：

```css
/* Good */
.button {
    background: var(--accent-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
}

/* Bad（属性不换行） */
.button { background: var(--accent-color); border: 1px solid var(--border-color); border-radius: 4px; }
```

### 十六进制颜色

小写字母，尽量使用 3 位简写：

```css
/* Good */
color: #abc;
color: #a1b2c3;

/* Bad */
color: #A1B2C3;
color: #ABC;
```

### 前缀

避免通用选择器前缀（如 `.mmfb-`），使用组件化命名。

## 🧹 代码质量

### 避免重复代码

- DRY 原则（Don't Repeat Yourself）
- 提取公共函数
- 使用继承或组合

### 单一职责

每个函数/类只做一件事：

```python
# Bad
def process_file(path):
    data = read_file(path)
    parsed = parse_data(data)
    validated = validate(parsed)
    save_to_db(validated)  # 做了太多事

# Good
def process_file(path):
    data = read_file(path)
    parsed = parse_data(data)
    return validated_data

# 调用方处理保存
result = process_file(path)
save_to_db(result)
```

### 注释

- 解释 **为什么**（而非做什么，代码已说明）
- 更新代码时同步更新注释
- 复杂算法必须添加注释

```python
# Good
# 使用 RSA 2048 位签名验证（符合 FIPS 186-4）
signature = rsa.sign(data, private_key, 'SHA-256')

# Bad
# 签名
signature = rsa.sign(data, private_key, 'SHA-256')
```

### 日志

使用标准库 `logging`：

```python
import logging

logger = logging.getLogger(__name__)

def process_file(path):
    logger.info("Processing file: %s", path)
    try:
        ...
    except Exception as e:
        logger.error("Failed to process %s: %s", path, e, exc_info=True)
        raise
```

**日志级别：**
- `DEBUG` - 调试信息
- `INFO` - 正常运行信息
- `WARNING` - 可恢复的问题
- `ERROR` - 失败但可继续
- `CRITICAL` - 致命错误

### 异常处理

捕获具体的异常，不要用裸 `except:`：

```python
# Good
try:
    with open(path, 'r') as f:
        return f.read()
except FileNotFoundError:
    logger.error("File not found: %s", path)
    raise
except PermissionError:
    logger.error("Permission denied: %s", path)
    raise

# Bad
try:
    with open(path, 'r') as f:
        return f.read()
except:  # 捕获所有异常（包括 KeyboardInterrupt）
    pass
```

## ✅ 提交前检查

```bash
# 1. 代码格式化
black mmfb/

# 2. 导入排序
isort mmfb/

# 3. 代码检查
flake8 mmfb/

# 4. 运行测试
pytest mmfb/tests/

# 5. 查看覆盖率
pytest --cov=mmfb --cov-report=term-missing

# 6. 烟雾测试（可选）
python smoke_test.py
```

如果所有检查通过，即可提交。

---

遵循这些规范，MMFB Windows 代码库将保持一致、可维护、高质量。

Happy coding! 🎉
