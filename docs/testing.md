# 测试指南

MMFB Windows 采用多层级测试策略，确保应用稳定性和功能正确性。

## 🧪 测试层级

### 1. 单元测试 (Unit Tests)

测试单个模块（Handler、工具函数等）。

**位置：** `mmfb/tests/unit/`

**文件名：** `test_*.py`

**示例：**
```python
# mmfb/tests/unit/handlers/test_pdf_handler.py
import pytest
from mmfb.handlers.pdf_handler import PdfHandler

def test_pdf_handler_can_handle():
    assert PdfHandler.can_handle('.pdf') == True
    assert PdfHandler.can_handle('.docx') == False
    assert PdfHandler.can_handle('.PDF') == True  # 大小写不敏感

def test_pdf_handler_get_viewer_html(tmp_path):
    test_pdf = tmp_path / "test.pdf"
    test_pdf.write_bytes(b'%PDF-1.4...')  # 最小 PDF 内容

    handler = PdfHandler()
    html = handler.get_viewer_html(str(test_pdf))

    assert '<!DOCTYPE html>' in html
    assert 'pdfjsLib' in html
    assert '{{file_path}}' not in html  # 变量已替换
```

运行单元测试：
```bash
pytest mmfb/tests/unit/ -v
```

### 2. 集成测试 (Integration Tests)

测试多个模块协作，如 Python 后端与前端通信、文件系统交互等。

**位置：** `mmfb/tests/integration/`

**示例：**
```python
# mmfb/tests/integration/test_bridge.py
import pytest
from mmfb.core.bridge import Bridge

def test_bridge_read_file(tmp_path):
    bridge = Bridge()
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello World")

    content = bridge.readFile(str(test_file))
    assert content == "Hello World"
```

运行集成测试：
```bash
pytest mmfb/tests/integration/ -v -m integration
```

### 3. 端到端测试 (E2E Tests)

测试完整用户工作流（打开文件、编辑、转换等）。

**使用：** 暂未配置，可使用 Playwright 或 Selenium

**示例（Playwright）：**
```python
# mmfb/tests/e2e/test_workflow.py
import pytest
from playwright.sync_api import Page, expect

@pytest.fixture
def page(page):
    # 启动应用（需要启动 HTTP server 或本地文件）
    page.goto("file:///path/to/mmfb/frontend/index.html")
    return page

def test_open_file(page):
    # 拖拽文件或调用 API
    page.evaluate(() => {
        window.pybridge.openFile('C:/test.pdf');
    });

    # 等待加载
    expect(page.locator('#viewer')).to_be_visible();
```

运行 E2E 测试：
```bash
pytest mmfb/tests/e2e/ -v
```

### 4. 烟雾测试 (Smoke Tests)

快速验证核心功能是否正常，通常在打包前运行。

**位置：** `smoke_test.py`

**内容：**
```python
#!/usr/bin/env python
"""
MMFB Windows 烟雾测试脚本
验证核心功能是否正常工作
"""

import sys
import tempfile
from pathlib import Path

def test_imports():
    """测试所有模块可导入"""
    try:
        from mmfb.core.window import MainWindow
        from mmfb.core.bridge import Bridge
        from mmfb.handlers.pdf_handler import PdfHandler
        print("✅ All imports OK")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_handler_registry():
    """测试 Handler 注册"""
    from mmfb.core.registry import Registry
    registry = Registry()
    assert len(registry.handlers) > 0
    print(f"✅ {len(registry.handlers)} handlers registered")
    return True

def test_pdf_handler():
    """测试 PDF Handler 基本功能"""
    from mmfb.handlers.pdf_handler import PdfHandler
    assert PdfHandler.can_handle('.pdf')
    print("✅ PDF handler works")
    return True

def test_conversion_engine():
    """测试转换引擎"""
    from mmfb.services.conversion_engine import ConversionEngine
    engine = ConversionEngine()
    # 创建测试文件
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
        f.write(b'Hello World')
        temp_path = f.name

    try:
        result = engine.convert(temp_path, temp_path + '.pdf', 'txt_to_pdf')
        print("✅ Conversion engine works")
        return result
    finally:
        Path(temp_path).unlink(missing_ok=True)
        Path(temp_path + '.pdf').unlink(missing_ok=True)

if __name__ == '__main__':
    tests = [
        test_imports,
        test_handler_registry,
        test_pdf_handler,
        test_conversion_engine,
    ]

    results = [test() for test in tests]

    print("\n" + "="*50)
    if all(results):
        print(f"✅ All {len(results)} smoke tests passed")
        sys.exit(0)
    else:
        failed = len([r for r in results if not r])
        print(f"❌ {failed}/{len(results)} tests failed")
        sys.exit(1)
```

运行烟雾测试：
```bash
python smoke_test.py
```

## 🛠️ 测试工具配置

### Pytest 配置 (`pyproject.toml`)

```toml
[tool.pytest.ini_options]
testpaths = ["mmfb/tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "-v",
    "--tb=short",
    "--strict-markers",
]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks integration tests",
    "e2e: marks end-to-end tests",
]
```

### 覆盖率报告

安装 pytest-cov：
```bash
pip install pytest-cov
```

运行带覆盖率：
```bash
pytest mmfb/tests/ --cov=mmfb --cov-report=html
```

查看报告：
```bash
open htmlcov/index.html  # macOS
start htmlcov\index.html  # Windows
```

### 预提交钩子 (pre-commit)

创建 `.pre-commit-config.yaml`：

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 23.7.0
    hooks:
      - id: black
        language_version: python3.9

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
```

安装：
```bash
pip install pre-commit
pre-commit install
```

## 🧬 测试数据管理

### Fixtures

使用 pytest fixtures 创建测试数据：

```python
# mmfb/tests/conftest.py
import pytest
import tempfile
from pathlib import Path

@pytest.fixture
def temp_dir():
    """创建临时目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def sample_pdf(temp_dir):
    """创建示例 PDF 文件"""
    pdf_path = temp_dir / "sample.pdf"
    pdf_path.write_bytes(b'%PDF-1.4...')  # 最小或真实 PDF 内容
    return str(pdf_path)

@pytest.fixture
def bridge():
    """创建 Bridge 实例"""
    from mmfb.core.bridge import Bridge
    return Bridge()
```

使用：
```python
def test_something(sample_pdf, bridge):
    # 直接使用 fixture
    content = bridge.readFile(sample_pdf)
    assert content is not None
```

### 测试资源

将真实测试文件放在 `mmfb/tests/resources/`：

```
mmfb/tests/
├── resources/
│   ├── sample.pdf
│   ├── sample.docx
│   ├── sample.xlsx
│   ├── images/
│   │   ├── sample.jpg
│   │   └── sample.heic
│   └── large/  # 大文件测试
│       └── 50mb.pdf
```

## 📊 持续集成 (CI)

已在 `.github/workflows/ci.yml` 配置 GitHub Actions：

**流程：**
1. **Test** - 运行单元测试 + 覆盖率
2. **Build** - 使用 PyInstaller 打包
3. **Release** - 创建 GitHub Release（仅 Tag 触发）

**手动触发：**
```bash
git push origin main
# GitHub Actions 自动运行
```

本地模拟 CI：
```bash
# 运行所有测试
pytest mmfb/tests/ -v --cov=mmfb --cov-report=xml

# 代码检查
flake8 mmfb/

# 构建测试
pyinstaller build.spec
```

## 🐛 调试失败测试

1. **查看详细错误**
   ```bash
   pytest mmfb/tests/unit/test_x.py -vv --tb=long
   ```

2. **仅运行失败测试（上次）**
   ```bash
   pytest mmfb/tests/ --last-failed
   ```

3. **进入调试器（失败时）**
   ```bash
   pytest mmfb/tests/unit/test_x.py --pdb
   ```

4. **打印日志**
   ```bash
   pytest mmfb/tests/ -o log_cli=true
   ```

5. **检查覆盖率缺口**
   ```bash
   pytest --cov=mmfb --cov-report=term-missing
   ```

## 📈 覆盖率目标

- **整体**：≥ 90%
- **新代码**：≥ 80%
- **核心模块（bridge, registry）**：≥ 95%

忽略测试的代码：
```python
def complex_algorithm():  # pragma: no cover
    # 复杂算法暂不测试（TODO）
    pass
```

## ♻️ 测试驱动开发 (TDD)

建议流程：

1. **编写失败的测试**
   ```python
   def test_new_feature():
       result = my_function()
       assert result == expected
   ```

2. **实现最小代码**
   ```python
   def my_function():
       return expected  # 硬编码
   ```

3. **重构优化**
   保持测试通过的同时优化实现。

4. **添加更多测试**
   - 边界情况
   - 异常情况
   - 性能（可选）

## 🧪 压力测试

对于大文件处理，需要压力测试：

```python
# mmfb/tests/stress/test_large_files.py
import pytest

@pytest.mark.slow
def test_large_pdf(tmp_path):
    """测试大 PDF 文件（50MB+）"""
    large_pdf = tmp_path / "large.pdf"
    # 生成大文件或使用预置文件
    large_pdf.write_bytes(b'0' * (50 * 1024 * 1024))

    from mmfb.handlers.pdf_handler import PdfHandler
    handler = PdfHandler()
    html = handler.get_viewer_html(str(large_pdf))

    assert html is not None
    assert len(html) < 1024 * 1024  # HTML 不应过大（懒加载）
```

运行慢测试：
```bash
pytest mmfb/tests/stress/ -m slow
```

## 📝 测试清单

提交 PR 前检查：

- [ ] 新增代码有对应测试
- [ ] 所有测试通过（本地运行 `pytest`）
- [ ] 覆盖率未下降（新代码 ≥ 80%）
- [ ] 无 lint 错误（`flake8`）
- [ ] 代码格式化（`black .`）
- [ ] 导入排序（`isort .`）
- [ ] 烟雾测试通过（`python smoke_test.py`）

---

通过系统的测试保证，MMFB Windows 才能稳定可靠地服务用户。
