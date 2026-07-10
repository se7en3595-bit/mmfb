/**
 * MMFB Code Viewer - 代码语法高亮查看器
 *
 * 职责：
 *   1. 读取源码文本，按行渲染
 *   2. 关键字/字符串/注释/数字/函数 语法高亮
 *   3. 行号栏显示
 *   4. 暗色主题配色（One Dark Style）
 *
 * 依赖：
 *   - MMFBBridge (bridge.js)
 *   - MMFBLayout (layout.js)
 *
 * 使用方式：
 *   MMFBCodeViewer.init(rootEl, { filePath, fileName, language });
 *   MMFBCodeViewer.destroy();
 */
(function (global) {
    'use strict';

    var MMFBCodeViewer = {
        _root: null,
        _filePath: '',
        _fileName: '',
        _language: 'plaintext',
        _content: '',
        _lines: [],

        /**
         * 初始化代码查看器
         * @param {HTMLElement} root - 挂载容器
         * @param {object} opts - { filePath, fileName, language }
         */
        init: function (root, opts) {
            this._root = root;
            // 兼容两种参数格式：后端 result.data (file_path) 和前端 (filePath)
            this._filePath = opts.filePath || opts.file_path || '';
            this._fileName = opts.fileName || opts.file_name || this._filePath.split(/[\\/]/).pop() || '';
            this._language = opts.language || 'plaintext';
            this._content = '';
            this._lines = [];

            this._renderShell();
            this._loadContent();

            return this;
        },

        /**
         * 渲染外壳容器
         */
        _renderShell: function () {
            MMFBLayout.setTitle(this._fileName);

            var langLabel = this._language !== 'plaintext' ? this._language.toUpperCase() : '';
            var footerParts = ['CODE'];
            if (langLabel) footerParts.push(langLabel);
            MMFBLayout.setFooterLeft(footerParts.join(' | '));

            this._root.innerHTML =
                '<div class="code-viewer">' +
                '<div class="code-viewer__status" id="code-status">加载中...</div>' +
                '<div class="code-viewer__scroll" id="code-scroll">' +
                '<div class="code-viewer__gutter" id="code-gutter"></div>' +
                '<pre class="code-viewer__pre" id="code-pre"><code id="code-content"></code></pre>' +
                '</div>' +
                '</div>';
        },

        /**
         * 加载文件内容
         */
        _loadContent: function () {
            var self = this;
            var statusEl = this._root.querySelector('#code-status');

            if (!statusEl) return;

            if (global.MMFBBridge && global.MMFBBridge.api) {
                global.MMFBBridge.api.readFile(this._filePath).then(function (content) {
                    self._content = content || '';
                    statusEl.textContent = '';
                    statusEl.style.display = 'none';
                    self._renderCode();
                }).catch(function (err) {
                    statusEl.textContent = '加载失败: ' + String(err);
                    statusEl.style.color = 'var(--color-error)';
                    self._content = '';
                    self._renderCode();
                });
            } else {
                // Mock 模式：显示示例代码
                this._content = this._getMockCode();
                statusEl.textContent = 'demo';
                statusEl.style.display = 'none';
                this._renderCode();
            }
        },

        /**
         * 渲染代码（分行 + 高亮 + 行号）
         */
        _renderCode: function () {
            this._lines = this._content.split('\n');
            // 末尾空行处理：如果最后一行是空字符串（以 \n 结尾产生），去掉
            if (this._lines.length > 0 && this._lines[this._lines.length - 1] === '') {
                this._lines.pop();
            }

            var contentEl = this._root.querySelector('#code-content');
            var gutterEl = this._root.querySelector('#code-gutter');

            if (!contentEl || !gutterEl) return;

            var htmlLines = [];
            var gutterHtml = [];

            for (var i = 0; i < this._lines.length; i++) {
                var lineNum = i + 1;
                var lineContent = this._lines[i];
                // 高亮单行
                var highlighted = this._highlightLine(lineContent, this._language);
                htmlLines.push('<div class="code-line" data-line="' + lineNum + '">' + highlighted + '</div>');
                gutterHtml.push('<div class="code-gutter__num" data-line="' + lineNum + '">' + lineNum + '</div>');
            }

            contentEl.innerHTML = htmlLines.join('');
            gutterEl.innerHTML = gutterHtml.join('');

            // 同步滚动
            this._setupScrollSync();
        },

        /**
         * 同步滚动：代码区滚动时同步行号栏
         */
        _setupScrollSync: function () {
            var scrollEl = this._root.querySelector('#code-scroll');
            var gutterEl = this._root.querySelector('#code-gutter');
            if (!scrollEl || !gutterEl) return;

            // 给行号栏阻止默认滚动行为，由 scroll 事件接管
            gutterEl.style.pointerEvents = 'none';

            scrollEl.addEventListener('scroll', function () {
                // 行号栏与代码区同步垂直滚动
                gutterEl.scrollTop = scrollEl.scrollTop;
            });
        },

        /**
         * 单行语法高亮
         *
         * @param {string} line - 源码行（不含 \n）
         * @param {string} lang - 语言标识
         * @returns {string} HTML 高亮后的字符串（已 HTML 转义）
         */
        _highlightLine: function (line, lang) {
            if (!line) return '';

            // 第一步：HTML 转义整个行
            var escaped = this._escapeHtml(line);

            // 第二步：各语言的特殊高亮规则
            if (lang === 'python') {
                return this._highlightPython(escaped);
            } else if (lang === 'javascript' || lang === 'typescript') {
                return this._highlightJsTs(escaped);
            } else if (lang === 'html' || lang === 'vue' || lang === 'svelte') {
                return this._highlightHtml(escaped);
            } else if (lang === 'css') {
                return this._highlightCss(escaped);
            } else if (lang === 'json') {
                return this._highlightJson(escaped);
            } else if (lang === 'sql') {
                return this._highlightSql(escaped);
            } else if (lang === 'shell' || lang === 'batch' || lang === 'powershell') {
                return this._highlightShell(escaped);
            } else {
                // 通用高亮（关键字+字符串+注释）
                return this._highlightGeneric(escaped, lang);
            }
        },

        /**
         * 通用高亮：注释（# 开头）、字符串、数字、关键字
         */
        _highlightGeneric: function (escaped, lang) {
            var result = escaped;

            // 行注释（# 开头，适用于 Python/Ruby/YAML/Shell/Perl）
            if (['python', 'ruby', 'shell', 'perl', 'yaml', 'r'].indexOf(lang) >= 0) {
                var commentIdx = result.indexOf('#');
                if (commentIdx >= 0 && !this._isInString(result, commentIdx)) {
                    var before = result.substring(0, commentIdx);
                    var after = result.substring(commentIdx);
                    return before + '<span class="tok-comment">' + after + '</span>';
                }
            }

            // 双引号字符串
            result = this._highlightString(result, '"', 'tok-string');
            // 单引号字符串
            result = this._highlightString(result, "'", 'tok-string');
            // 数字
            result = result.replace(/([^a-zA-Z0-9_$])(\d+(?:\.\d+)?)/g, '$1<span class="tok-number">$2</span>');

            return result;
        },

        /**
         * Python 高亮
         */
        _highlightPython: function (escaped) {
            var result = escaped;

            // 行注释
            var commentIdx = result.indexOf('#');
            if (commentIdx >= 0) {
                var before = result.substring(0, commentIdx);
                var after = result.substring(commentIdx);
                result = before + '<span class="tok-comment">' + after + '</span>';
                return result;
            }

            // 三引号字符串（简化：整行标为字符串）
            if (result.indexOf('"""') >= 0 || result.indexOf("'''") >= 0) {
                return '<span class="tok-string">' + result + '</span>';
            }

            // 关键字
            var pyKeywords = ['def', 'class', 'if', 'elif', 'else', 'for', 'while', 'return',
                'import', 'from', 'as', 'try', 'except', 'finally', 'with', 'raise',
                'pass', 'break', 'continue', 'lambda', 'yield', 'global', 'nonlocal',
                'and', 'or', 'not', 'in', 'is', 'True', 'False', 'None', 'assert', 'del'];
            result = this._highlightKeywords(result, pyKeywords, 'tok-keyword');

            // 字符串
            result = this._highlightString(result, '"', 'tok-string');
            result = this._highlightString(result, "'", 'tok-string');

            // 内建函数
            var pyBuiltins = ['print', 'len', 'range', 'int', 'str', 'float', 'list', 'dict',
                'set', 'tuple', 'type', 'isinstance', 'enumerate', 'zip', 'map', 'filter',
                'open', 'super', 'self', 'cls'];
            result = this._highlightKeywords(result, pyBuiltins, 'tok-builtin');

            // 数字
            result = result.replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="tok-number">$1</span>');

            // 函数定义 def function_name
            result = result.replace(/\b(def|class)\s+([A-Za-z_][A-Za-z0-9_]*)/g,
                '$1 <span class="tok-function">$2</span>');

            // 函数调用 func(
            result = result.replace(/\b([A-Za-z_][A-Za-z0-9_]*)\(/g,
                '<span class="tok-function">$1</span>(');

            // 装饰器
            result = result.replace(/(@\w+(?:\.\w+)*)/g, '<span class="tok-decorator">$1</span>');

            return result;
        },

        /**
         * JavaScript / TypeScript 高亮
         */
        _highlightJsTs: function (escaped) {
            var result = escaped;

            // 行注释
            var commentIdx = result.indexOf('//');
            if (commentIdx >= 0) {
                var before = result.substring(0, commentIdx);
                var after = result.substring(commentIdx);
                return before + '<span class="tok-comment">' + after + '</span>';
            }

            // 关键字
            var jsKeywords = ['const', 'let', 'var', 'function', 'return', 'if', 'else',
                'for', 'while', 'do', 'switch', 'case', 'break', 'continue', 'new',
                'this', 'class', 'extends', 'super', 'import', 'export', 'from',
                'default', 'typeof', 'instanceof', 'in', 'of', 'try', 'catch',
                'finally', 'throw', 'async', 'await', 'yield', 'delete', 'void',
                'true', 'false', 'null', 'undefined'];
            result = this._highlightKeywords(result, jsKeywords, 'tok-keyword');

            // 字符串（双引号、单引号、模板字符串）
            result = this._highlightString(result, '"', 'tok-string');
            result = this._highlightString(result, "'", 'tok-string');
            result = this._highlightString(result, '`', 'tok-string');

            // 数字
            result = result.replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="tok-number">$1</span>');

            // 正则表达式（简化）
            var regexMatch = result.match(/(\/[^\/\n]+\/[gimsuy]*)/);
            if (regexMatch) {
                result = result.replace(/(\/[^\/\n]+\/[gimsuy]*)/g, '<span class="tok-string">$1</span>');
            }

            // 函数调用
            result = result.replace(/\b([A-Za-z_$][A-Za-z0-9_$]*)\s*\(/g,
                '<span class="tok-function">$1</span>(');

            return result;
        },

        /**
         * HTML 标签高亮
         */
        _highlightHtml: function (escaped) {
            var result = escaped;

            // 注释
            if (result.indexOf('&lt;!--') >= 0) {
                var commentStart = result.indexOf('&lt;!--');
                var commentEnd = result.indexOf('--&gt;');
                if (commentStart >= 0 && commentEnd >= 0) {
                    var beforeComment = result.substring(0, commentStart);
                    var commentContent = result.substring(commentStart, commentEnd + '--&gt;'.length);
                    var afterComment = result.substring(commentEnd + '--&gt;'.length);
                    return beforeComment + '<span class="tok-comment">' + commentContent + '</span>' +
                        this._highlightHtml(afterComment);
                }
            }

            // 标签名（简化处理 转义后的 &lt;tagname ...）
            result = result.replace(/(&lt;\/?)([a-zA-Z][a-zA-Z0-9_-]*)/g,
                '$1<span class="tok-tag">$2</span>');

            // 结束符
            result = result.replace(/(\/?&gt;)/g, '<span class="tok-tag">$1</span>');

            // 属性名
            result = result.replace(/\b([a-zA-Z][a-zA-Z0-9_-]*)(=)/g,
                '<span class="tok-attr">$1</span>$2');

            // 属性值（引号内）
            result = this._highlightString(result, '&quot;', 'tok-string');

            return result;
        },

        /**
         * CSS 高亮
         */
        _highlightCss: function (escaped) {
            var result = escaped;

            // 注释
            var commentIdx = result.indexOf('/*');
            if (commentIdx >= 0) {
                var endIdx = result.indexOf('*/', commentIdx);
                if (endIdx >= 0) {
                    var beforeComment = result.substring(0, commentIdx);
                    var commentPart = result.substring(commentIdx, endIdx + 2);
                    var afterComment = result.substring(endIdx + 2);
                    return beforeComment + '<span class="tok-comment">' + commentPart + '</span>' +
                        this._highlightCss(afterComment);
                }
            }

            // 选择器（行首标识符）
            result = result.replace(/^(\s*)([.#]?[a-zA-Z][a-zA-Z0-9_-]*)/g,
                '$1<span class="tok-tag">$2</span>');

            // 属性名
            result = result.replace(/\b([a-zA-Z-]+)(\s*:)/g,
                '<span class="tok-attr">$1</span>$2');

            // 数值 + 单位
            result = result.replace(/(\d+(?:\.\d+)?)(px|em|rem|%|s|ms|vh|vw|pt|fr|deg|rad)/g,
                '<span class="tok-number">$1</span><span class="tok-unit">$2</span>');

            // 颜色值
            result = result.replace(/#([0-9a-fA-F]{3,8})\b/g,
                '<span class="tok-string">#$1</span>');

            // 关键字值
            result = result.replace(/\b(important|inherit|initial|none|auto|block|inline|flex|grid)\b/g,
                '<span class="tok-keyword">$1</span>');

            return result;
        },

        /**
         * JSON 高亮
         */
        _highlightJson: function (escaped) {
            var result = escaped;

            // 键（"key": 模式）
            result = result.replace(/"([^"]+)"(\s*:)/g,
                '<span class="tok-attr">"$1"</span>$2');

            // 字符串值
            result = this._highlightString(result, '"', 'tok-string');

            // 数字
            result = result.replace(/:\s*(\d+(?:\.\d+)?)/g,
                ': <span class="tok-number">$1</span>');

            // 布尔值和 null
            result = result.replace(/\b(true|false|null)\b/g,
                '<span class="tok-keyword">$1</span>');

            return result;
        },

        /**
         * SQL 高亮
         */
        _highlightSql: function (escaped) {
            var result = escaped;

            // 行注释
            var commentIdx = result.indexOf('--');
            if (commentIdx >= 0) {
                var before = result.substring(0, commentIdx);
                var after = result.substring(commentIdx);
                return before + '<span class="tok-comment">' + after + '</span>';
            }

            // 关键字（大小写不敏感，这里是简化版）
            var sqlKeywords = ['SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'AS',
                'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'ON', 'GROUP', 'BY',
                'ORDER', 'HAVING', 'LIMIT', 'OFFSET', 'INSERT', 'INTO', 'VALUES',
                'UPDATE', 'SET', 'DELETE', 'CREATE', 'TABLE', 'ALTER', 'DROP',
                'INDEX', 'VIEW', 'DISTINCT', 'COUNT', 'SUM', 'AVG', 'MAX', 'MIN',
                'BETWEEN', 'LIKE', 'IS', 'NULL', 'TRUE', 'FALSE', 'EXISTS', 'ALL'];
            result = this._highlightKeywords(result, sqlKeywords, 'tok-keyword', true);

            // 字符串
            result = this._highlightString(result, "'", 'tok-string');

            // 数字
            result = result.replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="tok-number">$1</span>');

            return result;
        },

        /**
         * Shell / Batch 高亮
         */
        _highlightShell: function (escaped) {
            var result = escaped;

            // 注释
            var commentIdx = result.indexOf('#');
            if (commentIdx >= 0) {
                var before = result.substring(0, commentIdx);
                var after = result.substring(commentIdx);
                return before + '<span class="tok-comment">' + after + '</span>';
            }

            // 关键字
            var shKeywords = ['if', 'then', 'else', 'elif', 'fi', 'for', 'while', 'do', 'done',
                'case', 'esac', 'function', 'return', 'exit', 'export', 'source',
                'echo', 'cd', 'ls', 'cat', 'grep', 'awk', 'sed', 'mkdir', 'rm', 'cp', 'mv',
                'chmod', 'sudo', 'apt', 'yum', 'pip', 'npm', 'node', 'python', 'set', 'env'];
            result = this._highlightKeywords(result, shKeywords, 'tok-keyword');

            // 字符串
            result = this._highlightString(result, '"', 'tok-string');
            result = this._highlightString(result, "'", 'tok-string');

            // 数字
            result = result.replace(/\b(\d+)\b/g, '<span class="tok-number">$1</span>');

            // 变量 $VAR
            result = result.replace(/(\$\w+)/g, '<span class="tok-variable">$1</span>');

            return result;
        },

        /**
         * 字符串高亮（引号匹配）
         */
        _highlightString: function (text, quote, className) {
            var result = '';
            var i = 0;
            while (i < text.length) {
                if (text[i] === quote) {
                    // 找到匹配的闭合引号
                    var j = i + 1;
                    while (j < text.length && text[j] !== quote) {
                        if (text[j] === '\\' && j + 1 < text.length) {
                            j++; // 转义字符
                        }
                        j++;
                    }
                    if (j < text.length) j++; // 包含闭合引号
                    result += '<span class="' + className + '">' + text.substring(i, j) + '</span>';
                    i = j;
                } else {
                    result += text[i];
                    i++;
                }
            }
            return result;
        },

        /**
         * 关键字高亮
         * @param {boolean} caseSensitive - 是否区分大小写
         */
        _highlightKeywords: function (text, keywords, className, caseSensitive) {
            var result = text;
            for (var k = 0; k < keywords.length; k++) {
                var kw = keywords[k];
                // 使用正则匹配完整单词
                var pattern = '\\b' + kw + '\\b';
                var flags = caseSensitive ? 'g' : 'gi';
                try {
                    var re = new RegExp(pattern, flags);
                    result = result.replace(re, '<span class="' + className + '">' + kw + '</span>');
                } catch (e) {}
            }
            return result;
        },

        /**
         * 判断某个索引位置是否在字符串内（简化：检查前方未闭合的引号）
         */
        _isInString: function (text, idx) {
            var inSingle = false;
            var inDouble = false;
            for (var i = 0; i < idx; i++) {
                if (text[i] === '"' && !inSingle) inDouble = !inDouble;
                else if (text[i] === "'" && !inDouble) inSingle = !inSingle;
            }
            return inSingle || inDouble;
        },

        /**
         * HTML 转义
         */
        _escapeHtml: function (str) {
            if (str === null || str === undefined) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        },

        /**
         * Mock 模式下显示的示例代码
         */
        _getMockCode: function () {
            return [
                '#!/usr/bin/env python3',
                '"""示例 Python 模块"""',
                '',
                'import os',
                'from pathlib import Path',
                '',
                '',
                'class MMFBCodeHandler:',
                '    """代码处理器 - 支持 80+ 语言高亮"""',
                '',
                '    def __init__(self, path: str):',
                '        self.path = path',
                '        self._cache = {}',
                '',
                '    def get_preview(self, max_lines: int = 500):',
                '        """获取代码预览数据"""',
                '        if not os.path.isfile(self.path):',
                '            return {"error": "file not found"}',
                '',
                '        content = self._read_file()',
                '        lines = content.split("\\n")',
                '        ',
                '        return {',
                '            "mime": "text/plain",',
                '            "template": "code",',
                '            "data": {',
                '                "content": content,',
                '                "language": self._detect_lang(),',
                '                "line_count": len(lines),',
                '            },',
                '            "editable": False,',
                '        }',
                '',
                '    def _read_file(self) -> str:',
                '        with open(self.path, "r", encoding="utf-8") as f:',
                '            return f.read()',
                '',
                '',
                'if __name__ == "__main__":',
                '    handler = MMFBCodeHandler("test.py")',
                '    result = handler.get_preview()',
                '    print(f"Language: {result[\'data\'][\'language\']}")',
                ''
            ].join('\n');
        },

        /**
         * 销毁
         */
        destroy: function () {
            this._root = null;
            this._filePath = '';
            this._fileName = '';
            this._language = 'plaintext';
            this._content = '';
            this._lines = [];
        }
    };

    global.MMFBCodeViewer = MMFBCodeViewer;

})(window);
