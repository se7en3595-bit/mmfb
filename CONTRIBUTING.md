# Contributing to MMFB Windows

感谢您考虑为 MMFB Windows 项目做出贡献！您的帮助将让这个项目变得更好。

Thank you for considering contributing to MMFB Windows! Your help will make this project better.

## 📋 行为准则 / Code of Conduct

本项目遵守 [Contributor Covenant](https://www.contributor-covenant.org/) 行为准则。
参与本社区即表示您同意维护一个安全、包容和友好的环境。

This project adheres to the [Contributor Covenant](https://www.contributor-covenant.org/) code of conduct.
By participating, you agree to maintain a safe, inclusive, and welcoming environment.

## 🐛 报告 Bug

如果您发现了一个 Bug，请先搜索 [Issues](https://github.com/mmfb-windows/mmfb/issues) 确认是否已有人报告。

If you find a bug, please search [Issues](https://github.com/mmfb-windows/mmfb/issues) first to see if it's already reported.

### Bug 报告模板 / Bug Report Template

```markdown
## 描述 / Description
<!-- 清晰简洁地描述 Bug 是什么 -->
<!-- A clear and concise description of what the bug is -->

## 复现步骤 / Steps to Reproduce
1. 前往 '...'
2. 点击 '....'
3. 滚动到 '....'
4. 看到错误

## 预期行为 / Expected Behavior
<!-- 描述您期望发生什么 -->
<!-- A clear and concise description of what you expected to happen -->

## 截图 / Screenshots
<!-- 如果适用，添加截图 -->
<!-- If applicable, add screenshots -->

## 系统信息 / System Info
- 操作系统：Windows 10/11 版本
- MMFB 版本：v0.8.0
- Python 版本：3.x（仅源码运行）
- 文件格式及大小：

## 附加信息 / Additional Context
<!-- 添加任何其他相关信息 -->
<!-- Add any other context about the problem here -->
```

## 💡 提出功能建议

我们欢迎新功能建议！请先搜索是否已有类似的建议。

Feature suggestions are welcome! Please search for similar requests first.

### 功能请求模板 / Feature Request Template

```markdown
## 问题描述 / Problem Description
<!-- 清晰的描述问题。例如："我每次都需要..." -->
<!-- A clear description of the problem. E.g.: "I'm always frustrated when..." -->

## 建议的解决方案 / Proposed Solution
<!-- 描述您希望看到的功能 -->
<!-- A clear and concise description of what you want to happen -->

## 替代方案 / Alternatives Considered
<!-- 描述您考虑过的其他解决方案 -->
<!-- A clear and concise description of any alternative solutions -->

## 使用场景 / Use Cases
<!-- 描述谁会使用这个功能以及如何使用的例子 -->
<!-- Describe who will use this feature and example scenarios -->
```

## 🔧 本地开发

我们强烈建议在开始编码前先与我们讨论您计划的变化，以确保您的工作方向正确。

We strongly encourage discussing proposed changes before starting work to ensure your effort is aligned with project goals.

### 开发环境设置 / Development Setup

1. **Fork 本仓库**
   Fork the repository on GitHub

2. **克隆到本地**
   ```bash
   git clone https://github.com/YOUR_USERNAME/mmfb.git
   cd mmfb
   ```

3. **创建虚拟环境**
   ```bash
   # Windows PowerShell
   python -m venv venv
   venv\Scripts\Activate.ps1

   # 或 CMD
   venv\Scripts\activate.bat
   ```

4. **安装依赖**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

5. **安装预提交钩子（可选）**
   ```bash
   pre-commit install
   ```

6. **运行应用测试**
   ```bash
   # 单元测试
   pytest

   # 集成测试
   pytest -m integration

   # 所有测试
   pytest -v
   ```

7. **运行应用**
   ```bash
   python main.py
   ```

### 代码风格 / Code Style

- 遵循 [PEP 8](https://pep8.org/) Python 代码规范
- 使用 4 个空格缩进（不用 Tab）
- 代码行长度限制 88 字符（参考 Black 格式化）
- 函数/类/方法命名遵循 `snake_case` / `PascalCase`
- 变量名使用有意义的英文单词，避免缩写

前端代码：
- JavaScript 使用 ES6+ 语法
- 遵循项目现有的代码风格
- CSS 使用驼峰命名或短横线分隔（参考现有代码）

### 提交规范 / Commit Convention

我们使用类似 [Conventional Commits](https://www.conventionalcommits.org/) 的格式：

```
类型(范围): 简短描述

详细描述（可选）

关联 Issue: #123
```

**常用类型：**
- `fix:` - Bug 修复
- `feat:` - 新功能
- `docs:` - 文档变更
- `style:` - 不影响代码逻辑的格式调整
- `refactor:` - 代码重构
- `test:` - 添加测试
- `chore:` - 构建或工具更改

**示例：**
```
feat(pdf): add support for digital signature verification

Implement signature panel in PDF viewer to display signature status.
Handles both certified and signed PDFs.

Closes #123
```

### 分支管理 / Branching Strategy

- `main` - 稳定分支，只包含已发布版本
- `develop` - 开发分支（如果有多人协作）
- `feature/xxx` - 功能分支（从 develop 创建）
- `fix/xxx` - Bug 修复分支

对于单个贡献者的小修改，可以直接在 main 分支提交 PR（如果被授权）或创建临时分支。

### Pull Request 流程 / Pull Request Process

1. **在 GitHub 上创建 Pull Request**
   - 标题清晰描述变更内容
   - 关联相关 Issue（如 `Closes #123`）
   - 填写 PR 模板完整信息

2. **代码审查 / Code Review**
   - 至少一名 Maintainer 审核通过
   - 解决审查意见的修改
   - 确保所有 CI 检查通过

3. **合并 / Merge**
   - Squash merge 到 main 分支
   - PR 标题作为提交信息
   - 删除功能分支

4. **发布 / Release**
   - 合并后自动触发 CI（如果配置）
   - Maintainer 创建 GitHub Release

### 测试指南 / Testing Guidelines

- **单元测试**：放在 `mmfb/tests/` 目录，文件名 `test_*.py`
- **新功能**：添加对应的测试用例
- **Bug 修复**：先写测试复现 Bug，然后修复
- **覆盖率**：新代码覆盖率 ≥ 80%

运行测试：
```bash
pytest mmfb/tests/ -v
```

### 开发者证书 / Developer Certificate of Origin (DCO)

通过提交 PR，您确认以下内容（类似 DCO 1.1）：

```
By submitting this pull request, I represent that I have the right to
submit this contribution and agree to its distribution under the project's
license. I confirm that this contribution is my own work or properly
attributed to its source.
```

## 📖 文档改进 / Documentation Improvements

文档改进同样重要！您可以：
- 修正错别字或语法错误
- 补充缺失的说明
- 改进代码注释
- 重写模糊的表述

直接在 GitHub 上点击文档文件的 "Edit" 按钮即可在线编辑。

## ❓ 获取帮助 / Get Help

- **Issues**：提交技术问题或使用问题
- **Discussions**：https://github.com/mmfb-windows/mmfb/discussions（可创建）
- **邮件**：暂无

## 👥 维护者 / Maintainers

项目的维护者是 [SE7EN](https://github.com/your-username)。

## 📜 许可证 / License

通过贡献代码，您同意您的贡献将在 [MIT License](LICENSE) 下发布。

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).

---

再次感谢您的贡献！🎉

Thank you again for your contribution! 🎉