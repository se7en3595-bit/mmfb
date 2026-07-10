/**
 * MMFB Markdown Viewer - Markdown 预览 + 编辑双模式
 *
 * 职责：
 *   1. 预览模式：将 Markdown 文本转为 HTML 渲染
 *   2. 编辑模式：左侧 textarea + 右侧实时预览
 *   3. 保存：调用 Bridge.saveFile 写回原文件
 *   4. 模式切换：顶栏按钮切换预览/编辑
 *
 * 依赖：
 *   - MMFBBridge (bridge.js)
 *   - MMFBLayout (layout.js)
 *
 * 使用方式：
 *   MMFBMDViewer.init(rootEl, { filePath, fileName });
 *   MMFBMDViewer.destroy();
 */
(function (global) {
    'use strict';

    var MMFBMDViewer = {
        _root: null,
        _filePath: '',
        _fileName: '',
        _mode: 'preview',  // 'preview' | 'edit'
        _content: '',
        _rendered: '',
        _textarea: null,
        _previewEl: null,
        _saveTimer: null,
        _dirty: false,

        /**
         * 初始化 Markdown 查看器
         * @param {HTMLElement} root - 挂载容器
         * @param {object} opts - { filePath, fileName }
         */
        init: function (root, opts) {
            this._root = root;
            this._filePath = opts.filePath || '';
            this._fileName = opts.fileName || '';
            this._mode = 'preview';
            this._content = '';
            this._dirty = false;

            this._renderShell();
            this._loadContent();

            return this;
        },

        /**
         * 渲染外壳：顶栏切换按钮 + 主区域
         */
        _renderShell: function () {
            var self = this;

            MMFBLayout.setTitle(this._fileName);
            MMFBLayout.setFooterLeft('Markdown');

            this._root.innerHTML =
                '<div class="md-viewer">' +
                '<div class="md-viewer__toolbar">' +
                '<div class="view-switcher">' +
                '<button class="view-switcher__btn active" data-mode="preview">预览</button>' +
                '<button class="view-switcher__btn" data-mode="edit">编辑</button>' +
                '</div>' +
                '<div class="md-viewer__toolbar-right">' +
                '<span class="md-viewer__status" id="md-status"></span>' +
                '<button class="md-viewer__save-btn" id="md-save-btn" disabled>保存</button>' +
                '</div>' +
                '</div>' +
                '<div class="md-viewer__body" id="md-body"></div>' +
                '</div>';

            // 模式切换
            var btns = this._root.querySelectorAll('.view-switcher__btn');
            btns.forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var mode = btn.getAttribute('data-mode');
                    self._switchMode(mode);
                });
            });

            // 保存按钮
            var saveBtn = this._root.querySelector('#md-save-btn');
            saveBtn.addEventListener('click', function () {
                self._save();
            });
        },

        /**
         * 通过 Bridge 加载文件内容
         */
        _loadContent: function () {
            var self = this;
            var statusEl = this._root.querySelector('#md-status');
            statusEl.textContent = '加载中...';

            if (global.MMFBBridge && global.MMFBBridge.api) {
                global.MMFBBridge.api.readFile(this._filePath).then(function (content) {
                    self._content = content || '';
                    statusEl.textContent = '';
                    self._renderBody();
                }).catch(function (err) {
                    statusEl.textContent = '加载失败';
                    self._content = '';
                    self._renderError(String(err));
                });
            } else {
                // Mock 模式
                this._content = '# Mock Content\n\n这是模拟的 Markdown 内容。\n\n## 二级标题\n\n- 列表项 1\n- 列表项 2\n\n```python\nprint("hello")\n```';
                statusEl.textContent = 'mock';
                this._renderBody();
            }
        },

        /**
         * 根据当前模式渲染主体
         */
        _renderBody: function () {
            var body = this._root.querySelector('#md-body');
            if (!body) return;

            if (this._mode === 'preview') {
                this._renderPreview(body);
            } else {
                this._renderEdit(body);
            }
        },

        /**
         * 渲染预览模式
         */
        _renderPreview: function (body) {
            this._rendered = this._markdownToHtml(this._content);
            body.innerHTML = '<div class="md-preview">' + this._rendered + '</div>';
            body.className = 'md-viewer__body md-viewer__body--preview';
        },

        /**
         * 渲染编辑模式：左侧 textarea + 右侧实时预览
         */
        _renderEdit: function (body) {
            var self = this;
            body.innerHTML =
                '<div class="md-editor">' +
                '<textarea class="md-editor__input" id="md-textarea"></textarea>' +
                '<div class="md-editor__preview md-preview" id="md-preview"></div>' +
                '</div>';
            body.className = 'md-viewer__body md-viewer__body--edit';

            this._textarea = body.querySelector('#md-textarea');
            this._previewEl = body.querySelector('#md-preview');

            this._textarea.value = this._content;
            this._previewEl.innerHTML = this._markdownToHtml(this._content);

            // 实时预览（防抖 200ms）
            this._textarea.addEventListener('input', function () {
                self._content = self._textarea.value;
                self._dirty = true;
                self._updateSaveButton();
                self._schedulePreviewUpdate();
            });

            // 同步滚动（textarea 滚动时按比例滚动预览）
            this._textarea.addEventListener('scroll', function () {
                var st = self._textarea.scrollTop;
                var sh = self._textarea.scrollHeight - self._textarea.clientHeight;
                var pt = self._previewEl.scrollTop;
                var ph = self._previewEl.scrollHeight - self._previewEl.clientHeight;
                if (sh > 0 && ph > 0) {
                    self._previewEl.scrollTop = (st / sh) * ph;
                }
            });
        },

        /**
         * 防抖预览更新
         */
        _schedulePreviewUpdate: function () {
            var self = this;
            if (this._saveTimer) clearTimeout(this._saveTimer);
            this._saveTimer = setTimeout(function () {
                if (self._previewEl) {
                    self._previewEl.innerHTML = self._markdownToHtml(self._content);
                }
            }, 200);
        },

        /**
         * 切换预览/编辑模式
         */
        _switchMode: function (mode) {
            if (mode === this._mode) return;

            // 编辑 -> 预览：先同步 textarea 内容
            if (this._mode === 'edit' && this._textarea) {
                this._content = this._textarea.value;
            }

            this._mode = mode;

            // 更新按钮状态
            var btns = this._root.querySelectorAll('.view-switcher__btn');
            btns.forEach(function (btn) {
                if (btn.getAttribute('data-mode') === mode) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });

            this._renderBody();
        },

        /**
         * 保存文件
         */
        _save: function () {
            var self = this;
            var statusEl = this._root.querySelector('#md-status');
            var saveBtn = this._root.querySelector('#md-save-btn');

            if (this._mode === 'edit' && this._textarea) {
                this._content = this._textarea.value;
            }

            statusEl.textContent = '保存中...';
            saveBtn.disabled = true;

            if (global.MMFBBridge && global.MMFBBridge.api) {
                global.MMFBBridge.api.saveFile(this._filePath, this._content).then(function (ok) {
                    if (ok) {
                        self._dirty = false;
                        statusEl.textContent = '已保存';
                        setTimeout(function () { statusEl.textContent = ''; }, 2000);
                        self._updateSaveButton();
                    } else {
                        statusEl.textContent = '保存失败';
                        saveBtn.disabled = false;
                    }
                }).catch(function (err) {
                    statusEl.textContent = '保存失败: ' + String(err);
                    saveBtn.disabled = false;
                });
            } else {
                // Mock 模式
                setTimeout(function () {
                    self._dirty = false;
                    statusEl.textContent = '已保存 (mock)';
                    setTimeout(function () { statusEl.textContent = ''; }, 2000);
                    self._updateSaveButton();
                }, 300);
            }
        },

        /**
         * 更新保存按钮状态
         */
        _updateSaveButton: function () {
            var saveBtn = this._root.querySelector('#md-save-btn');
            if (saveBtn) {
                saveBtn.disabled = !this._dirty;
            }
        },

        /**
         * 渲染错误
         */
        _renderError: function (msg) {
            var body = this._root.querySelector('#md-body');
            if (body) {
                body.innerHTML =
                    '<div class="md-error">' +
                    '<div class="md-error__icon">&#9888;</div>' +
                    '<div class="md-error__msg">' + this._escapeHtml(msg) + '</div>' +
                    '</div>';
            }
        },

        /**
         * Markdown → HTML 转换（轻量级实现）
         *
         * 支持：标题、粗体、斜体、删除线、行内代码、代码块、
         *       链接、图片、列表（有序/无序）、引用、表格、分割线
         */
        _markdownToHtml: function (md) {
            if (!md) return '';

            var html = md;

            // 代码块（先处理，避免内部内容被转义）
            var codeBlocks = [];
            html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function (match, lang, code) {
                var idx = codeBlocks.length;
                var langAttr = lang ? ' data-lang="' + MMFBMDViewer._escapeAttr(lang) + '"' : '';
                codeBlocks.push('<pre class="md-code-block"' + langAttr + '><code>' +
                    MMFBMDViewer._escapeHtml(code.trim()) + '</code></pre>');
                return '%%CODEBLOCK_' + idx + '%%';
            });

            // 行内代码
            html = html.replace(/`([^`]+)`/g, function (match, code) {
                return '<code class="md-inline-code">' + MMFBMDViewer._escapeHtml(code) + '</code>';
            });

            // 图片 ![alt](url)
            html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, function (match, alt, url) {
                return '<img class="md-img" src="' + MMFBMDViewer._escapeAttr(url) + '" alt="' + MMFBMDViewer._escapeAttr(alt) + '">';
            });

            // 链接 [text](url)
            html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function (match, text, url) {
                return '<a class="md-link" href="' + MMFBMDViewer._escapeAttr(url) + '" target="_blank">' + text + '</a>';
            });

            // 标题
            html = html.replace(/^######\s+(.+)$/gm, '<h6>$1</h6>');
            html = html.replace(/^#####\s+(.+)$/gm, '<h5>$1</h5>');
            html = html.replace(/^####\s+(.+)$/gm, '<h4>$1</h4>');
            html = html.replace(/^###\s+(.+)$/gm, '<h3>$1</h3>');
            html = html.replace(/^##\s+(.+)$/gm, '<h2>$1</h2>');
            html = html.replace(/^#\s+(.+)$/gm, '<h1>$1</h1>');

            // 粗体 + 斜体
            html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
            html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
            html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

            // 删除线
            html = html.replace(/~~(.+?)~~/g, '<del>$1</del>');

            // 分割线
            html = html.replace(/^---+$/gm, '<hr>');
            html = html.replace(/^\*\*\*+$/gm, '<hr>');

            // 引用块
            html = html.replace(/^&gt;\s+(.+)$/gm, '<blockquote>$1</blockquote>');

            // 无序列表
            html = html.replace(/^[\s]*[-*]\s+(.+)$/gm, '<li class="md-li">$1</li>');
            html = html.replace(/(<li class="md-li">.*<\/li>\n?)+/g, function (match) {
                return '<ul class="md-ul">' + match + '</ul>';
            });

            // 有序列表
            html = html.replace(/^[\s]*\d+\.\s+(.+)$/gm, '<li class="md-li">$1</li>');

            // 表格（简化：仅处理带 | 分隔符的行）
            html = html.replace(/^\|(.+)\|$/gm, function (match, row) {
                var cells = row.split('|').map(function (c) { return c.trim(); });
                if (cells.every(function (c) { return /^[-:]+$/.test(c); })) {
                    return ''; // 分隔行
                }
                var tds = cells.map(function (c) { return '<td>' + c + '</td>'; }).join('');
                return '<tr>' + tds + '</tr>';
            });
            html = html.replace(/(<tr>.*<\/tr>\n?)+/g, function (match) {
                return '<table class="md-table">' + match + '</table>';
            });

            // 段落（空行分隔）
            html = html.split(/\n\n+/).map(function (block) {
                block = block.trim();
                if (!block) return '';
                if (block.startsWith('<h') || block.startsWith('<ul') ||
                    block.startsWith('<ol') || block.startsWith('<blockquote') ||
                    block.startsWith('<pre') || block.startsWith('<table') ||
                    block.startsWith('<hr')) {
                    return block;
                }
                // 将单个换行符转为 <br>
                block = block.replace(/\n/g, '<br>');
                return '<p>' + block + '</p>';
            }).join('\n');

            // 还原代码块
            html = html.replace(/%%CODEBLOCK_(\d+)%%/g, function (match, idx) {
                return codeBlocks[parseInt(idx, 10)] || '';
            });

            return html;
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
         * 属性转义
         */
        _escapeAttr: function (str) {
            return this._escapeHtml(str);
        },

        /**
         * 销毁
         */
        destroy: function () {
            if (this._saveTimer) {
                clearTimeout(this._saveTimer);
                this._saveTimer = null;
            }
            this._root = null;
            this._textarea = null;
            this._previewEl = null;
            this._content = '';
            this._rendered = '';
            this._dirty = false;
        }
    };

    global.MMFBMDViewer = MMFBMDViewer;

})(window);
