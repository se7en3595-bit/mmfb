# 长期记忆

## 2026-07-04
- 用户希望参考 Mac 软件 MMFB（万能阅览器），开发一款 Windows 版本的产品
- 产品名称：MMFB Windows / 万能阅览器
- 技术决策：Python + PySide6 (Qt for Python)【已从 Tauri 切换】
- 设计理念：内容优先、克制美学、纯本地、暖纸色调
- 核心功能：看(155+格式)、改(6类就地编辑)、转(9类互转)
- 用户 SE7EN 偏好：中文回复、有理有据、不用破折号
- 用户已有 Python 环境，拒绝安装 Rust/MSVC

## 2026-07-05 ~ 2026-07-07
（早期记忆已在文件中，此处省略以节省空间，完整内容保留在磁盘）

## 2026-07-08 分屏预览与导航修复

### 分屏预览修复
- **根因**：`_load_file_in_view()` (window.py 第 447-449 行) 原本只显示静态 HTML 占位符 "Bridge not connected"，没有利用子 view 已注入 of QWebChannel
- **修复**：改为使用 `setUrl()` 加载 `index.html#/view/<ext>?file=<encoded_path>`，利用前端路由自动解析 hash 触发预览
- **关键代码**：
  ```python
  url = QUrl.fromLocalFile(index_path)
  url.setFragment('/view/' + ext + '?file=' + encoded_path)
  webview.setUrl(url)
  ```
- **前提**：子 view 已通过 `SplitView` 获得共享的 `_channel`（在 `_setup_page()` 中调用 `setWebChannel`），所以前端 bridge 和 router 能正常工作

### 打开文件命令修复
- **根因**：`command_palette.js` 中 "打开文件..." 命令只创建 `<input type=file>` 并设置标题，没有真正打开文件预览
- **修复**：改为调用 `MMFBBridge.api.openFileDialog()` 打开系统对话框，选中文件后通过 `MMFBRouter.navigate('/view/<ext>?file=<path>')` 触发预览

### 导航菜单（命令面板 Ctrl+K）
- 用户提到的 "文件 导航 打开文件... 设置... 关于MMFB 打开历史 格式转换 返回首页" 实际是命令面板（Ctrl+K）中的命令列表
- 这些命令功能正常，分组标题（文件/导航/窗口/视图）本身不可点击（这是 GUI 惯例）

### 涉及文件
- `mmfb/core/window.py` - 修改 `_load_file_in_view()`
- `mmfb/frontend/js/command_palette.js` - 修改 "打开文件..." 命令的 action

## 2026-07-08 转换格式崩溃/卡死修复

### 根因
转换操作全部在主 UI 线程同步执行，阻塞 Qt 事件循环导致卡死；`html_to_pdf` 中 `QWebEngineView` 无父窗口且嵌套 `QEventLoop.exec()`，直接崩溃。

### 修复内容
1. **bridge.py**：
   - 新增 `conversionFinished` 信号
   - `convert_file` 改为启动后台线程 (`_thread.start_new_thread`)，立即返回 `{"ok":true,"accepted":true,"jobId":"..."}`
   - 后台线程执行转换，完成后通过 `conversionFinished` 信号返回结果
   - `convert_video_file` 同样改为异步

2. **conversion_engine.py**：
   - `html_to_pdf` 完全重写，不再使用 `QWebEngineView` + `QEventLoop`
   - 改用 `wkhtmltopdf`（优先）或 `weasyprint`（回退）纯子进程方式
   - 移除 PySide6.QtWebEngineWidgets / QEventLoop / QTimer 依赖

3. **bridge.js**：
   - 新增 `onConversionFinished` 回调
   - `_jobResolvers` 字典：jobId → {resolve, reject} 映射
   - `convertFile` / `convertVideoFile` 返回 Promise，等待 `conversionFinished` 信号解析
   - 5 分钟超时保护

4. **conversion_viewer.js**：
   - `_doConvert` 生成唯一 `item.jobId`
   - progress 回调通过 jobId 匹配更新对应 item
   - promise 完成后自动还原 progress 回调

### 涉及文件
- `mmfb/core/bridge.py` - convert_file / convert_video_file 异步化
- `mmfb/services/conversion_engine.py` - html_to_pdf 重写
- `mmfb/frontend/js/bridge.js` - conversionFinished 信号 / _jobResolvers
- `mmfb/frontend/js/conversion_viewer.js` - 异步回调适配

## 2026-07-08 自动提取
- 用户反馈"转换格式"功能存在严重 bug：点击后渲染失败、卡死甚至直接崩溃
- 根因已确认：转换操作全部在主 UI 线程同步执行，阻塞 Qt 事件循环
- 最严重问题点：`html_to_pdf` 函数使用两次嵌套 `QEventLoop.exec()`，最长可阻塞主线程 45 秒
- 次要问题：`QWebEngineView` 无父窗口导致特定场景下崩溃


## 2026-07-08 自动提取
- 用户正在开发一个基于 Python（3.14.5）+ Chromium 的桌面应用（路径：E:\WorkSpace\Newmax\projects\proj-1783171631051-7vrmw5）
- 用户使用 PDF.js 作为 PDF 渲染库，需放置于 frontend/libs/pdfs/ 目录（pdf.min.mjs + pdf.worker.min.mjs）
- 项目通过 file:// 协议加载本地文件，导致 Chromium CORS 策略禁用 fetch() 使 PDF.js 无法正常工作，计划改为后端读取文件并 base64 编码、前端解码后传给 PDF.js 的方案
- 拖拽文件时路径追加 .txt 后缀（.pdf.txt）是 Windows"隐藏已知文件扩展名"设置导致的副产物，不是代码 bug
- 用户技术栈：Python 后端 + 自定义前端（mmfb 框架），使用 Chromium 渲染，Python 版本 3.14.5


## 2026-07-08 自动提取
- 项目路径为 `E:\WorkSpace\Newmax\projects\proj-1783171631051-7vrmw5`
- 使用的 Python 版本为 3.14.5
- 项目前端 PDF 渲染依赖 pdfjs，文件应放置在 `frontend/libs/pdfs/`（含 `pdf.min.mjs`、`pdf.worker.min.mjs`、`pdfjs-global.js` 三个文件）
- Chromium 在 `file://` 协议下用 `fetch()` 加载 ESM 模块会因 CORS 策略失败（`--allow-file-access-from-files` 对 `fetch()` 无效，仅对 XMLHttpRequest 有效）
- Windows 默认隐藏已知扩展名，用户拖入文件如显示为 `xxx.pdf.txt` 是用户行为问题而非程序 bug
- 修复方案：将 `pdfjs-global.js` 的加载方式从 `fetch()` 改为 `XMLHttpRequest`


## 2026-07-09 自动提取
- 用户当前正在维护一个 PDF 查看器项目（pdf_viewer.js / MMFB），关注 worker 配置回退和 `_zoom` 方法的代码质量
- 用户的工作方式偏务实：希望先核对任务完成状态再行动，且会明确追问"做了吗"
- 用户对该项目的技术栈细节：使用 pdfjsLib、支持 UMD 和 ESM 加载路径，包含 `data-rendered`、`data-page`、`disableWorker` 等自定义机制
- 本轮已完成的两个修复：（1）删除 `_zoom` 中重复的 `removeAttribute('data-rendered')`；（2）放宽 `_loadPdfJs` 中的 worker 配置回退（增加嵌套 try/catch，超时兜底保留，主路径加错误页提示）


## 2026-07-10 GitHub 上传准备

### 任务背景
用户要求"整理一版软件描述，做将代码上传到github的准备"。

### 完成的工作

**1. 项目文档体系（9 个核心文件）**

- **README.md** - 双语项目介绍
  - Badge 统计、核心特性、技术架构
  - 格式支持对照表、快捷键、性能指标
  - 路线图、贡献指南入口、许可证

- **LICENSE** - MIT 许可证全文

- **CONTRIBUTING.md** - 贡献指南
  - 行为准则引用
  - Bug 报告和功能请求模板
  - 开发环境设置步骤（Python 虚拟环境、依赖安装、测试）
  - 代码风格（PEP 8、命名规范、提交信息格式 Conventional Commits）
  - PR 流程、分支策略、测试覆盖率要求（≥ 80%）
  - 开发者证书（DCO）说明

- **CODE_OF_CONDUCT.md** - 贡献者公约（中英文）
  - 承诺、标准、执行指南、处分等级

- **CHANGELOG.md** - 版本日志
  - Keep a Changelog 规范
  - 语义化版本（SemVer）
  - [Unreleased] 部分记录当前开发中的功能
  - v0.6.0 版本说明

- **SECURITY.md** - 安全策略
  - 支持版本范围（v0.6.x）
  - 漏洞报告流程（邮件 + GitHub Security Advisory）
  - 安全最佳实践（纯本地、无遥测、沙箱）
  - 依赖安全检查（pip-audit、safety）
  - 代码 signing 计划

- **README.dev.md** - 开发者快速入门
  - 5 分钟上手指南（克隆、venv、pip install、运行）
  - 推荐工具（VS Code、Black、isort、flake8、pre-commit）
  - 开发工具链配置
  - 常见任务（添加格式、修改样式、修复 Bug）
  - 测试速查命令
  - 调试技巧（Python 端、前端、桥接）
  - 首次贡献检查清单

- **GITHUB_PREP_CHECKLIST.md** - GitHub 上传准备清单
  - ✅ 已完成 28 项检查
  - ⚠️ 上传前 5 项验证（敏感信息、大文件、临时文件、CI、版本号）
  - 🚀 4 步上传流程
  - 📊 项目统计
  - 🎯 8 项后续任务

**2. 配置文件（7 个）**

- **`.gitignore`** - Python + Windows + IDE + 构建产物 + 敏感文件
- **`.editorconfig`** - 统一跨编辑器配置（LF、UTF-8、4空格 Python / 2空格 JS-CSS）
- **`.gitattributes`** - Git 属性（文本文件 LF、二进制文件标记、vendored 库）
- **`requirements.txt`** - 依赖清单（PySide6、Pillow、python-docx、openpyxl 等 20+ 包）
- **`.pre-commit-config.yaml`** - 8 个钩子（ws、eof、yaml、black、isort、flake8、bandit、mypy）
- **`.bandit.yml`** - Bandit 安全扫描排除规则（B101/B103/B110 等）
- **`pyproject.toml`** - pytest 配置已存在，补充工具配置

**3. GitHub Actions 与模板（5 个）**

- **`.github/workflows/ci.yml`** - CI 三阶段
  1. Test: pytest + coverage + Codecov
  2. Build: PyInstaller 打包 → artifact
  3. Release: Tag 触发 → 自动创建 GitHub Release

- **`.github/PULL_REQUEST_TEMPLATE.md`** - PR 模板
  - 变更类型（bug/feature/breaking/docs/refactor）
  - 测试确认、检查清单、截图、还原 2026-07-12 修改后关联 Issue

- **`.github/ISSUE_TEMPLATE/bug_report.md`** - Bug 报告表单
  - 描述、复现步骤、预期、截图、系统信息、调试日志

- **`.github/ISSUE_TEMPLATE/feature_request.md`** - 功能请求表单
  - 问题描述、建议方案、替代方案、使用场景

- **`.github/release-draft.md`** - Release Notes 模板
  - 版本信息、新功能、Bug 修复、改进、打包说明、已知问题

**4. 开发者文档（docs/ 7 个）**

- `README.md` - 文档导航
- `architecture.md` - **架构深度解析**（15000 字）
  - 整体架构图 + 四层架构说明
  - 核心模块详解（12 个核心文件）
  - 数据流：打开文件、编辑文件、格式转换
  - 安全设计、性能优化、错误处理、日志系统
  - 扩展性说明

- `handler-development.md` - **Handler 开发完整指南**
  - FileHandler 基类接口
  - 3 个示例（纯文本、PDF、二进制）
  - 模板文件和静态资源组织
  - 前端集成步骤（路由、桥接）
  - 测试要求（覆盖率 ≥ 80%）
  - 调试技巧、最佳实践
  - 6 步流程：添加新格式（从创建文件到提交）

- `frontend-development.md` - **前端开发全流程**
  - 目录结构、开发工作流（热重载、F12 调试）
  - 桥接通信 API（readFile、saveFile、convertFile）
  - 路由系统（hash 模式、导航、拦截）
  - 预览器开发（类结构、示例）
  - CSS 主题系统（CSS 变量、三套主题）
  - 第三方库加载（ESM vs Script）
  - 性能优化（懒加载、缓存、避免泄漏）
  - 安全注意事项（XSS、路径验证、不用 eval）
  - 调试技巧、响应式设计

- `testing.md` - **测试策略与工具**
  - 4 层测试：单元、集成、E2E、烟雾
  - pytest 配置、覆盖率报告
  - fixtures 管理、测试资源
  - GitHub Actions CI 配置说明
  - 调试失败测试技巧
  - 覆盖率目标（整体 ≥ 90%、新代码 ≥ 80%）
  - TDD 工作流、压力测试示例

- `build.md` - **构建与打包实战**
  - PyInstaller 配置详解（build.spec）
  - 排除依赖、隐藏导入、数据文件
  - 调试打包问题（日志、缺失模块、DLL、路径）
  - NSIS 安装脚本（installer.nsi）
  - 代码签名流程（EV 证书）
  - 优化安装包体积（UPX、图标压缩）
  - 自动化 build.py 脚本
  - 构建验证清单、病毒扫描

- `code-style.md` - **代码规范 Bible**
  - Python：PEP 8、Black（88 字符）、isort、flake8、命名、类型提示、文档字符串、注释、日志、异常处理
  - JavaScript：ES6+、async/await、模板字符串、无分号、2 空格、JSDoc
  - CSS：BEM/蛇形命名、2 空格、简短十六进制
  - 代码质量：DRY、单一职责、注释要解释"为什么"
  - 提交前检查清单（black、isort、flake8、pytest、覆盖率）

**5. 准备清单**

`GITHUB_PREP_CHECKLIST.md` - 28 项 ✅ + 5 项 ⚠️ + 4 步 🚀

### 关键决策

1. **MIT 许可证** - 最宽松，适合商业和个人
2. **双语文档** - 中英文，覆盖本地和国际用户
3. **完整 CI/CD** - 自动测试、打包、Release 三阶段
4. **严格质量门控** - pre-commit 集成格式化、lint、安全扫描
5. **详尽贡献指南** - 从环境搭建到 PR 全流程，TDD 要求
6. **架构文档优先** - 让新贡献者快速理解系统设计（四层架构、扩展机制）
7. **版本 v0.6** - 用户要求从 v1.0.0 降级，删除 v1.5/v2.0/v3.0 远期规划

### 文档特色

- **实战导向**：所有文档含代码示例、命令、配置片段
- **深度技术**：architecture.md 约 15000 字，覆盖安全、性能、错误处理
- **可操作**：每个指南都有"快速开始"和"调试技巧"
- **质量第一**：测试覆盖率要求、TDD、预提交钩子
- **社区友好**：行为准则、贡献模板、开发者证书

### 项目当前状态

- **开发进度**：50/53 任务完成（94%）
- **版本号**：v0.6.0
- **技术栈**：Python 3.8+、PySide6、HTML5/JS/ES6+
- **格式支持**：155+ 格式预览、6 类编辑、9 类转换
- **性能指标**：冷启动 ≤ 3 秒，内存 ≤ 300 MB，安装包 ~85 MB
- **代码规模**：约 15,000 行（Python 8000、JS 4000、HTML-CSS 3000）

### 上传前最后检查

用户需要：
1. ✅ 创建 GitHub 仓库（Public/Private）
2. ✅ 推送代码（git push origin main）
3. ✅ 验证 CI 自动触发并通过
4. ✅ 检查 README 渲染、徽章显示
5. ✅ 确认 Templates 正常工作
6. 🏷️ 创建 v0.6.0 Tag 触发 Release

建议执行：
- 替换 `mmfb/version.py` 中 `MMFB_UPDATE_REPO = "mmfb-windows/mmfb"` 为实际用户名
- 测试 Issue 和 PR 模板是否正常

## 2026-07-10 用户偏好提醒

- 中文回复、有理有据、不用破折号
- 务实风格："做了吗" 明确追问
- 代码优先质量：先核对任务状态再行动

## 2026-07-10 自动提取
- 版本号从 v1.0.0 (Musubi) 改为 v0.6.0，并删除了代号
- 删除了 V3 远期版本规划路线图
- 共修改了 12 个文件以更新版本号 and 路线图信息

## 2026-07-10 GitHub 上传最终执行

### 检查与清理
- ✅ 敏感信息扫描：未发现硬编码 API 密钥、密码、令牌
- ✅ 临时文件清理：删除 `project - 副本.txt`
- ✅ 构建产物忽略：`build/` (333M)、`dist/` 已配置在 `.gitignore`
- ✅ 缓存文件忽略：`__pycache__/`、`.pytest_cache/` 已忽略
- ✅ 版本号验证：v0.6.0（无 Musubi 代号，无 v3.0 规划）
- ✅ 文档完整性：README、LICENSE、CONTRIBUTING 等 30+ 文件齐全

### Git 初始化与提交
- 初始化本地 Git 仓库
- 重命名分支为 `main`
- 提交 194 个文件，50,485 行新增代码
- Commit message: `feat: prepare GitHub release - MMFB Windows v0.6.0`
- 包含完整文档、CI/CD 配置、贡献指南、开发者文档

### 待用户执行（上传到 GitHub）
1. 在 https://github.com/new 创建仓库（建议 `mmfb-windows/mmfb`）
2. 添加远程：`git remote add origin https://github.com/YOUR-USERNAME/REPO-NAME.git`
3. 推送：`git push -u origin main`
4. 验证 CI 流水线运行
5. 创建 Tag 触发 Release：`git tag -a v0.6.0 -m "MMFB Windows v0.6.0"` → `git push origin v0.6.0`

### 建议后续配置
- 修改 `mmfb/version.py` 的 `MMFB_UPDATE_REPO` 为实际用户名
- 启用 GitHub Pages（可选，用于文档托管）
- 配置 Dependabot（.github/dependabot.yml）
- 设置 CODEOWNERS 文件
- 添加项目徽章（ Shields.io ）至 README

## 2026-07-10 自动提取
- 用户在提交到版本控制（如 GitHub）前，会主动检查敏感信息并清理

## 2026-07-10 自动提取
- 用户明确要求直接产出实际内容而非管理动作，边做边推进，不创建或更新任务清单
- 用户指定了明确的完成判断标准：以正文是否实际覆盖目标为准，结束时必须输出 GOAL_STATUS 标记（complete/continue/blocked）
- 当前修复任务：拖拽文件预览功能，最多10轮，token预算1000000
- 已确认现有修复：showEvent 中 DragAcceptFiles 注册（Line 868-874）、_on_native_drop_files 方法

## 2026-07-10 自动提取
- 文件位置：`mmfb/frontend/js/xlsx_viewer.js` 的 `_formatColor` 方法
- 修复逻辑：纯黑文字色 (`#000000`) 返回空字符串，让 CSS 变量 `--color-text-primary` 接管
- 原因：Excel 默认文字色就是 `FF000000`，_dark 主题下深色背景+纯黑文字=看不清
- 修复效果：Light/Warm 主题下 CSS 变量本身就是近黑色，视觉差异很小；Dark 主题下 CSS 变量是浅色文字 (`#E8E8EC`)，文字立刻清晰可见
- 纯黑背景色不受影响（只针对文字颜色）

## 2026-07-10 自动提取
- 添加了一个文字颜色切换功能，用于解决绿色背景下白色字体不可见的问题
- 具体操作：用户通过点击工具栏的 A 按钮，弹出 8 色调色板，可切换文字颜色
- 选项包括“默认”、黑、白、红、蓝、绿、橙、紫
- 切换后，所有单元格文本颜色立即改变，按钮底部会显示对应的彩色指示条
- 此功能作为显示层覆盖，不会影响保存的 Excel 数据

## 2026-07-12 原生多窗口分屏/拖拽调整/Excel颜色/预览复制/空表编辑修复
- **分屏按钮修复**：修改 `bridge.js` 修复 `splitCurrentWindow` 调用为 `split_current_window`，并正确解析返回的 JSON，实现分屏点击生效。
- **拖放窗口大小调整修复**：在 `window.py` 里的原生拖拽消息处理函数 `_on_native_drop_files` 结尾处调用 `ctypes.windll.user32.ReleaseCapture()` 释放鼠标捕获，使拖拽文件后边框调整恢复正常。
- **Excel 字体颜色匹配**：重构 `xlsx_handler.py` 里的 `_extract_style` 样式提取机制，支持解析 Indexed 颜色与含 tint 亮度换算的主题色，并将 read_only 参数改为 False 使得 openpyxl 能够正常解析主题配置。
- **预览复制支持**：在 `base.css` 里将 `.layout-main` 专门重写为 `user-select: text`，在预览状态下允许选中文本进行复制。
- **空数据表双击编辑**：改进 `xlsx_viewer.js` 空数据表及空工作表渲染逻辑，当工作表个数为 0 时或工作表为空时，双击空背景自动初始化为 10x5 的空网格，支持双击单元格就地编辑与保存。


## 2026-07-12 自动提取
- `ReleaseCapture()` 调用在拖放处理中可能导致窗口异常最小化（通过发送 WM_CAPTURECHANGED 消息在某些情况下打断拖放会话）
- `WM_DROPFILES` 是旧式拖放机制，本身不涉及鼠标捕获状态，不需要调用 `ReleaseCapture()`
- 技术方案：移除 `ReleaseCapture()` 调用，添加窗口状态保护机制（拖拽后检测意外最小化并自动恢复）
- 在 `showMinRESSED` 方法中区分用户主动最小化与意外最小化，避免误恢复


## 2026-07-12 自动提取
- 用户报告 "第一次拖入文件窗口正常显示，再拖入一个新文件，2秒后窗口边框就又消失"
- 问题根源是沉浸式标题栏自动隐藏定时器（`AUTOHIDE_DELAY_MS = 2000`）恰好在拖入第二个文件后触发，导致标题栏滑出
- 修复方案：在 `mmfb/core/window.py` 中新增 `_suppress_auto_hide_for(ms)` 方法，拖入文件后启动 3 秒抑制窗口
- 修复涉及：所有文件拖入入口调用 `_suppress_auto_hide_for(3000)` + `_show_header()`
