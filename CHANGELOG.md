# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- 无

### Changed
- 无

### Deprecated
- 无

### Removed
- 无

### Fixed
- 无

### Security
- 无

---

## [0.8.0] - 2026-07-12

### Added
- 沉浸式标题栏自动隐藏/显示逻辑优化
- 标题栏拖入文件后抑制自动隐藏机制
- 分屏模式 DWM 阴影重注册

### Fixed
- 拖入 PDF/Excel 文件后窗口边框消失问题（根本原因：沉浸式标题栏自动隐藏定时器触发）
- 拖入文件后窗口异常最小化问题（移除错误的 ReleaseCapture 调用）
- 路由器双重重渲染导致 PDF/XLSX Viewer 初始化两次的问题
- 分屏按钮点击后卡死约 4 秒及边框丢失问题
- Excel 字体颜色匹配（Indexed 颜色与主题色解析）
- 预览模式下文本复制支持
- 空数据表双击编辑功能

---

## [0.6.0] - 2026-07-10

### Added
- 🎉 首次开源发布
- 项目初始化，完成基础架构搭建
- 支持 155+ 文件格式的预览功能
- 支持 6 类文档就地编辑（Markdown、HTML、Text、CSV、JSON、XML）
- 9 类格式互转引擎（PDF、Word、Excel、PPT、Markdown、HTML、图像、文本、CSV）
- 内容优先的 UI 设计，自动隐藏工具栏
- 暖纸色调主题系统（浅色/深色/暖纸）
- 多窗口与分屏预览功能
- 文件拖拽打开支持
- 快捷键绑定与设置页面
- 打开历史记录（默认保留 50 条）
- 系统托盘图标与全局快捷键
- Windows 文件关联注册表集成
- 右键菜单 "Open with MMFB"
- PyInstaller 打包配置
- Smoke Test 自动化测试脚本

### Fixed
- PDF 渲染 CORS 问题（通过后端 base64 方案）
- 分屏预览功能修复
- 导航按钮无效问题修复
- 转换功能主线程阻塞崩溃问题
- 路径编码空格和特殊字符问题

### Security
- QWebEngineView 禁用远程内容加载
- 所有文件操作限制在用户指定路径
- 纯本地运行，无云端数据上传

---

## Version Format

`[版本号] - [发布日期]`

- **Added** - 新功能
- **Changed** - 功能变更
- **Deprecated** - 即将移除的功能
- **Removed** - 已移除的功能
- **Fixed** - Bug 修复
- **Security** - 安全相关更新

---

## Release Notes Archive

### v0.8.0 - 2026-07-12
修复拖拽文件后窗口边框消失、最小化振荡、分屏卡死等关键 Bug，优化沉浸式标题栏交互逻辑。

### v0.6.0 - 2026-07-10
首个开源版本，完成核心功能开发，支持 155+ 格式的预览、编辑和转换。

First open-source release with core functionality, supporting preview, edit, and convert for 155+ formats.