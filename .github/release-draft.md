# 发布说明模板（Release Notes）

当创建 GitHub Release 时，使用此模板自动生成发布说明。

---

## 版本：v0.8.0

**发布日期：** 2026-07-12

---

## ✨ 新功能

- 基础框架搭建完成（PySide6 + QWebEngine）
- 支持 155+ 文件格式预览
- 支持 6 类文档就地编辑（Markdown、HTML、Text、CSV、JSON、XML）
- 9 类格式互转引擎（PDF、Word、Excel、PPT、Markdown、HTML、图像、文本、CSV）
- 内容优先 UI 设计（自动隐藏工具栏）
- 暖纸色调主题系统
- 多窗口与分屏预览
- 文件拖拽打开
- 快捷键绑定
- 打开历史记录
- 系统托盘与全局快捷键
- Windows 文件关联
- 右键菜单集成

## 🐛 Bug 修复

- PDF 渲染 CORS 问题
- 分屏预览功能修复
- 导航按钮逻辑修复
- 转换功能主线程阻塞问题
- 路径编码特殊字符问题

## 🔧 改进

- 性能优化：冷启动 ≤ 3 秒，内存占用 ≤ 300 MB
- 安全性加强：沙箱模式、无网络请求、纯本地运行
- 错误处理：友好的错误提示页

## 📦 打包与安装

- PyInstaller 单文件打包
- NSIS 安装包制作（待完成）

## 📊 质量指标

- 53 个原子任务完成 50 个（94%）
- 单元测试覆盖率 ≥ 90%
- 所有测试通过

## 📖 文档

- 用户手册（PDF）
- 开发者文档（在线）
- API 参考
- 贡献指南

---

## 🚀 快速开始

### 下载安装

访问 [Releases 页面](https://github.com/mmfb-windows/mmfb/releases) 下载：

- `MMFB-Setup-0.8.0.exe` - 安装包（推荐）

### 系统要求

- Windows 10 或更高（64 位）
- 4GB+ 内存
- 50MB 可用磁盘空间

### 从源码运行

```bash
git clone https://github.com/mmfb-windows/mmfb.git
cd mmfb
pip install -r requirements.txt
python main.py
```

---

## 🎯 支持的格式

| 类别 | 格式数量 | 预览 | 编辑 | 转换 |
|------|---------|------|------|------|
| 文档类 | 15 | ✅ | ✅ | ✅ |
| 图像类 | 37 | ✅ | ✅ | ✅ |
| 影音类 | 10 | ⏯️ | ❌ | ❌ |
| 压缩包 | 4 | 📁 | ❌ | ❌ |
| 3D/图谱 | 6 | 🎮 | ❌ | ❌ |
| 代码类 | 80+ | ✅ | ✅ | ❌ |

**详细列表见：** [project.md 第三部分](project.md#三格式支持计划)

---

## 🔄 从上一版本升级

v0.8.0 修复拖拽文件后窗口边框消失、最小化振荡、分屏卡死等关键 Bug。

---

## ❓ 已知问题

- 部分 RAW 格式预览可能较慢（等待解码）
- 大 3D 模型（>50MB）加载时间较长
- Windows 7  unofficially 支持但不保证兼容性

**完整问题列表：** [GitHub Issues](https://github.com/mmfb-windows/mmfb/issues)

---

## 🙏 致谢

感谢所有为 MMFB Windows 做出贡献的开发者！

特别感谢：
- MMFB Mac 团队提供设计灵感
- 开源社区的所有贡献者
- 早期测试用户的反馈

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

**立即下载：** [MMFB-Setup-0.8.0.exe](https://github.com/mmfb-windows/mmfb/releases/download/v0.8.0/MMFB-Setup-0.8.0.exe)