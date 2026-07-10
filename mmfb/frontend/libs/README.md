# libs/ 第三方 JS 库

前端渲染所用的第三方 JavaScript 库，各 Handler 按需引入。

## 库清单

| 库 | 文件 | 用途 |
|---|---|---|
| pdf.js | pdfjs/ | PDF 文档渲染 |
| CodeMirror 6 | codemirror/ | 代码高亮编辑 |
| SheetJS | xlsx.mini.min.js | Excel 解析渲染 |
| pdf-lib | pdf-lib.min.js | PDF 生成编辑 |
| Three.js | three.min.js | 3D 模型渲染 |
| jszip | jszip.min.js | ZIP 压缩包解析 |
| Milkdown | milkdown/ | Markdown 编辑 |
| mammoth | mammoth.browser.min.js | DOCX 渲染 |
| pptxgenjs | pptxgen.bundle.js | PPT 生成 |

## 备注

- 这些库后续任务中逐步下载
- 下载方式：从 npm CDN (cdn.jsdelivr.net/npm/...) 下载到本地，确保纯本地运行
- 文件较大时不提交到 git，通过 build 脚本获取
