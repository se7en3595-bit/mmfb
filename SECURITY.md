# Security Policy

## Supported Versions

We currently support the following versions with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.8.x   | ✅ Yes             |
| < 0.8   | ❌ No              |

## Reporting a Vulnerability

我们非常重视安全性。如果您发现安全漏洞，请负责任地披露，不要公开讨论。

We take security seriously. If you discover a security vulnerability, please disclose it responsibly.

### How to Report

**请通过邮件发送至：** security@mmfb.windows（示例，需替换为实际邮箱）

Alternatively, you can open a private security advisory on GitHub:
1. Go to [Security Advisories](https://github.com/mmfb-windows/mmfb/security/advisories)
2. Click "New draft security advisory"
3. Fill in details and submit

**Please include:**
- 漏洞类型和严重程度估计
- 复现步骤（尽可能详细）
- 受影响的代码位置
- 建议的修复方案（如果有）

**What to expect:**
- 我们会在 3 个工作日内确认收到报告
- 会评估漏洞严重程度并制定修复计划
- 修复后会发布安全公告（如需）
- 贡献者会获得致谢（可选择匿名）

### Security Best Practices for Users

MMFB Windows 是一个纯本地运行的应用程序，遵循以下原则：

1. **No Cloud Upload** - 所有文件处理在本地完成，不上传到云端
2. **No Telemetry** - 不收集用户文件内容或使用行为数据
3. **Sandboxed Rendering** - 使用 QWebEngineView 沙箱模式
4. **File Access Control** - 仅访问用户明确打开的文件
5. **Optional Updates** - 自动更新功能可关闭

### 已知限制 / Known Limitations

- Windows 平台仅（未在其他平台测试）
- 自动更新功能需要网络连接（可禁用）
- 第三方库可能存在漏洞（建议定期更新）

### 依赖安全 / Dependency Security

我们定期检查依赖漏洞。运行依赖安全扫描：

```bash
# 使用 pip-audit 检查漏洞
pip install pip-audit
pip-audit

# 或使用 safety
pip install safety
safety check
```

所有依赖版本固定到 `requirements.txt`，定期更新依赖以获取安全补丁。

### 安全更新流程

1. 收到漏洞报告并评估严重性
2. 创建安全修复分支（不公开）
3. 开发并测试修复
4. 发布新的安全版本（patch 版本）
5. 发布安全公告（严重漏洞）
6. 通知用户更新

### Code Signing

正式版本使用 EV 代码签名证书签名，确保应用来源可信。

- v0.8.0: 自签名证书（暂未签名）

---

感谢您帮助我们保持 MMFB Windows 的安全！

Thank you for helping keep MMFB Windows secure!