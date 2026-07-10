# 开发者快速入门指南

本指南帮助新贡献者快速搭建 MMFB Windows 开发环境。

## 📋 环境要求

- **操作系统**：Windows 10 或 11（64 位）
- **Python**：3.8+（推荐 3.9 或 3.10）
- **Git**：用于版本控制
- **内存**：≥ 4GB（推荐 8GB+）
- **磁盘空间**：≥ 2GB（包含依赖和构建产物）

## 🚀 5 分钟快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/mmfb-windows/mmfb.git
cd mmfb
```

### 2. 创建虚拟环境（推荐）

```powershell
# PowerShell
python -m venv venv
venv\Scripts\Activate.ps1

# CMD
venv\Scripts\activate.bat
```

### 3. 安装依赖

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. 运行应用

```bash
python main.py
```

看到欢迎界面即表示成功！

### 5. 运行测试（可选）

```bash
# 单元测试
pytest mmfb/tests/unit/

# 集成测试
pytest mmfb/tests/integration/ -m integration

# 全部测试
pytest mmfb/tests/

# 带覆盖率
pytest --cov=mmfb --cov-report=html
```

## 🔧 开发工具推荐

### 编辑器 / IDE

- **VS Code**（推荐）：Python 扩展 + Pylance + Black Formatter
- **PyCharm**：专业 Python IDE，Qt 支持

### 代码质量

```bash
# 自动格式化（Black）
pip install black
black mmfb/

# 导入排序（isort）
pip install isort
isort mmfb/

# 代码检查（flake8）
pip install flake8
flake8 mmfb/
```

### 预提交钩子（自动检查）

```bash
pip install pre-commit
pre-commit install
```

现在每次 `git commit` 会自动运行格式化、检查、测试。

## 📂 项目结构速览

```
mmfb/
├── core/              # 核心模块（窗口、桥接、注册表）
├── handlers/          # 文件格式处理器（20+ 个）
├── services/          # 转换引擎等
├── frontend/          # HTML/CSS/JS 前端资源
├── resources/         # 图标、主题、字体
└── tests/             # 测试文件
```

**关键文件：**
- `main.py` - 应用入口
- `core/window.py` - 主窗口逻辑
- `core/bridge.py` - Python-JS 通信
- `handlers/pdf_handler.py` - PDF 处理示例

## 🔨 常见任务

### 添加新格式支持

1. 创建 `mmfb/handlers/myformat_handler.py`
2. 实现 `FileHandler` 接口（见 [Handler 开发指南](docs/handler-development.md)）
3. 编写测试 `mmfb/tests/handlers/test_myformat_handler.py`
4. 运行测试：`pytest mmfb/tests/handlers/test_myformat_handler.py -v`
5. 提交 PR

### 修改前端样式

1. 编辑 `mmfb/frontend/css/main.css` 或主题文件
2. 运行应用查看效果（F5 刷新）
3. 按 **F12** 打开开发者工具调试

### 修复 Bug

1. 在 GitHub Issues 查找或创建 Bug 报告
2. 创建功能分支：`git checkout -b fix/issue-123`
3. 编写复现 Bug 的测试（先让测试失败）
4. 修复代码，让测试通过
5. 提交并创建 PR

### 添加新的转换格式

1. 修改 `services/conversion_engine.py`
2. 在 `converters` 字典添加新转换器
3. 更新前端转换 UI（`frontend/js/conversion_viewer.js`）
4. 测试转换流程

## 🧪 测试速查

```bash
# 运行所有测试
pytest

# 只运行一个文件
pytest mmfb/tests/unit/handlers/test_pdf_handler.py

# 只运行一个测试函数
pytest mmfb/tests/unit/handlers/test_pdf_handler.py::test_pdf_handler_can_handle

# 打印详细输出
pytest -vv

# 最后一次失败的测试
pytest --last-failed

# 进入调试器（失败时）
pytest --pdb

# 查看覆盖率
pytest --cov=mmfb --cov-report=html
start htmlcov\index.html
```

## 🐛 调试技巧

### Python 端调试

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logging.debug("Debug message")
```

日志文件位置：`%APPDATA%/MMFB/mmfb.log`

### 前端调试

1. 运行应用
2. 在 QWebEngineView 窗口按 **F12**
3. 使用 Console 查看 `console.log()`
4. 使用 Sources 面板设置断点

### 桥接调试

在 `bridge.js` 中启用调试日志：

```javascript
window.pybridge.setDebug(true);
```

## 📖 更多资源

- [架构概述](docs/architecture.md) - 理解系统设计
- [Handler 开发指南](docs/handler-development.md) - 扩展格式支持
- [前端开发指南](docs/frontend-development.md) - 前端开发
- [构建与打包](docs/build.md) - 打包发布
- [测试指南](docs/testing.md) - 完整测试策略
- [代码规范](docs/code-style.md) - PEP 8 & JavaScript 规范

## 🤝 寻求帮助

- **Issues**: 提交技术问题或 Bug 报告
- **Discussions**: 社区讨论（待创建）
- **文档**: 先阅读本文档和相关文档

## ✅ 首次贡献检查清单

- [ ] 克隆仓库并成功运行应用
- [ ] 阅读 CONTRIBUTING.md
- [ ] 阅读 CODE_OF_CONDUCT.md
- [ ] 运行测试并全部通过
- [ ] 选择或创建 Issue
- [ ] 创建分支（命名规范：`feature/xxx` 或 `fix/xxx`）
- [ ] 编写代码并添加测试
- [ ] 运行检查：`pytest && flake8`
- [ ] 提交并推送到远程
- [ ] 创建 Pull Request，填写 PR 模板

**当前版本：** v0.6.0

---

**欢迎加入 MMFB Windows 社区！** 🎉