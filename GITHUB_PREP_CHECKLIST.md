# GitHub 上传准备清单

已完成的准备工作（2026-07-10）：

## ✅ 核心文件

- [x] README.md - 双语项目介绍（中英文）
- [x] LICENSE - MIT 许可证
- [x] CONTRIBUTING.md - 贡献指南
- [x] CODE_OF_CONDUCT.md - 行为准则
- [x] CHANGELOG.md - 版本更新日志
- [x] SECURITY.md - 安全策略
- [x] README.dev.md - 开发者快速入门

## ✅ 配置文件

- [x] .gitignore - Git 忽略配置
- [x] .editorconfig - 编辑器配置（统一代码风格）
- [x] .gitattributes - Git 属性（换行符、二进制文件标记）
- [x] requirements.txt - Python 依赖清单

## ✅ 质量保证

- [x] .pre-commit-config.yaml - 预提交钩子配置
- [x] .bandit.yml - 安全扫描配置
- [x] pyproject.toml - pytest 配置已存在
- [x] smoke_test.py - 烟雾测试脚本（已存在）

## ✅ GitHub 集成

- [x] .github/workflows/ci.yml - CI 流水线（测试 + 打包）
- [x] .github/PULL_REQUEST_TEMPLATE.md - PR 模板
- [x] .github/ISSUE_TEMPLATE/bug_report.md - Bug 报告模板
- [x] .github/ISSUE_TEMPLATE/feature_request.md - 功能请求模板
- [x] .github/release-draft.md - 发布说明模板

## ✅ 文档

- [x] docs/README.md - 文档总览
- [x] docs/architecture.md - 架构概述
- [x] docs/handler-development.md - Handler 开发指南
- [x] docs/frontend-development.md - 前端开发指南
- [x] docs/testing.md - 测试指南
- [x] docs/build.md - 构建与打包
- [x] docs/code-style.md - 代码规范

## ✅ 项目结构

```
mmfb/
├── core/           # 核心模块（17 个文件）
├── handlers/       # 格式处理器（22 个）
├── frontend/       # 前端资源
├── services/       # 转换引擎
├── resources/      # 图标主题
├── tests/          # 测试文件
└── version.py      # 版本号

build.py, build.spec, pyproject.toml, main.py
```

## ⚠️ 上传前检查

### 1. 敏感信息检查

```bash
# 搜索硬编码的密码、密钥、令牌
git grep -i "password\|secret\|token\|api_key\|authorization"

# 检查是否包含临时文件
git status --porcelain
```

### 2. 大文件检查

确保没有意外的大文件（>50MB）：

```bash
# 查看所有文件大小
find . -type f -size +50M -exec ls -lh {} \;

# Git 跟踪的大文件
git rev-list --objects --all | \
  git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | \
  awk '/^blob/ {print substr($0,6)}' | \
  sort --numeric-sort --key=2 | \
  tail -10
```

### 3. 清理临时文件

```bash
# 删除构建产物（如果不在版本控制）
rm -rf build/ dist/ __pycache__/
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete
find . -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null
```

### 4. 验证 CI 配置

确保 GitHub Actions 能正常工作：

```bash
# 本地测试（需要 act 或直接推送到 GitHub）
# 推荐直接推送到测试仓库
```

### 5. 版本号确认

检查 `mmfb/version.py`：
```python
MMFB_VERSION = "0.6.0"  # ✅ 正确
MMFB_UPDATE_REPO = "mmfb-windows/mmfb"  # ✅ 替换为实际用户名/仓库名
```

## 🚀 上传步骤

### 第一步：创建 GitHub 仓库

1. 访问 https://github.com/new
2. 仓库名：`mmfb` 或 `mmfb-windows`
3. 描述：Universal File Viewer for Windows - Open, Edit, Convert 155+ formats
4. 选择 **Public**（开源）或 **Private**（私有）
5. **不要** 勾选 "Initialize this repository with a README"
6. 创建仓库

### 第二步：关联远程并推送

```bash
# 初始化 Git（如果尚未）
git init
git add .
git commit -m "feat: initial commit - MMFB Windows v0.6.0"

# 添加远程仓库（替换 YOUR-USERNAME 和 REPO-NAME）
git remote add origin https://github.com/YOUR-USERNAME/REPO-NAME.git

# 推送到 GitHub
git branch -M main
git push -u origin main
```

### 第三步：验证

1. 访问仓库页面确认文件全部上传
2. 检查 CI 是否自动触发（.github/workflows/ci.yml）
3. 检查 README 渲染是否正确
4. 测试 Issue 和 PR 模板是否正常

### 第四步：创建第一次 Release

```bash
# 创建 Tag
git tag -a v0.6.0 -m "MMFB Windows v0.6.0"
git push origin v0.6.0

# GitHub Actions 会自动：
# 1. 运行测试
# 2. 打包 exe
# 3. 创建 Release Draft
# 手动检查并发布 Release
```

## 📊 仓库统计

- **总文件数**：~150+（含前端库）
- **代码行数**：约 15,000 行
  - Python：~8,000 行
  - JavaScript：~4,000 行
  - HTML/CSS：~3,000 行
- **核心模块**：53 个原子任务完成 50 个（94%）
- **当前版本**：v0.6.0

## 🎯 后续任务（项目中）

- [ ] 替换 `mmfb/version.py` 中的 `MMFB_UPDATE_REPO` 为实际 GitHub 用户名
- [ ] 更新 README.md 中的 GitHub 链接
- [ ] 创建官网（可选）
- [ ] 配置代码签名（未来版本）
- [ ] 设置 Dependabot（自动更新依赖）
- [ ] 设置 CODEOWNERS（代码所有者）
- [ ] 添加 ISSUE 标签（bug, enhancement, documentation, etc.）
- [ ] 创建 Wiki（可选，放详细文档）
- [ ] 配置项目主页（GitHub Pages）

## 🎉 完成！

所有 GitHub 相关文件已准备完毕，可以安全上传。

上传后，社区可以通过：
- **Issues** 报告 Bug 或请求功能
- **Pull Requests** 贡献代码
- **Discussions** 进行讨论（如需开启）
- **Releases** 下载安装包

---

**最后更新时间：** 2026-07-10
**准备人员：** SE7EN / Claude
**版本：** v0.6.0