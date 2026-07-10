/**
 * MMFB HTML Viewer - HTML 预览 + 编辑双模式
 *
 * 安全策略：
 *   - 预览模式：使用 sandboxed iframe 渲染本地 HTML
 *     (sandbox="" 不开启 allow-scripts / allow-same-origin / allow-top-navigation)
 *   - 编辑模式：左侧 textarea + 右侧 sandboxed 预览
 *   - 仅读取本地文件内容，不发起网络请求
 *
 * 依赖：
 *   - MMFBBridge (bridge.js)
 *   - MMFBLayout (layout.js)
 *
 * 使用方式：
 *   MMFBHTMLViewer.init(rootEl, { filePath, fileName });
 *   MMFBHTMLViewer.destroy();
 */
(function (global) {
    'use strict';

    var MMFBHTMLViewer = {
        _root: null,
        _filePath: '',
        _fileName: '',
        _mode: 'preview',  // 'preview' | 'edit'
        _content: '',
        _textarea: null,
        _previewEl: null,
        _saveTimer: null,
        _dirty: false,

        /**
         * 初始化 HTML 查看器
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
            MMFBLayout.setFooterLeft('HTML');

            this._root.innerHTML =
                '<div class="html-viewer">' +
                '<div class="html-viewer__toolbar">' +
                '<div class="view-switcher">' +
                '<button class="view-switcher__btn active" data-mode="preview">预览</button>' +
                '<button class="view-switcher__btn" data-mode="edit">编辑</button>' +
                '</div>' +
                '<div class="html-viewer__toolbar-right">' +
                '<span class="html-viewer__status" id="html-status"></span>' +
                '<button class="html-viewer__save-btn" id="html-save-btn" disabled>保存</button>' +
                '</div>' +
                '</div>' +
                '<div class="html-viewer__body" id="html-body"></div>' +
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
            var saveBtn = this._root.querySelector('#html-save-btn');
            saveBtn.addEventListener('click', function () {
                self._save();
            });
        },

        /**
         * 通过 Bridge 加载文件内容
         */
        _loadContent: function () {
            var self = this;
            var statusEl = this._root.querySelector('#html-status');
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
                this._content = '<!DOCTYPE html>\n<html>\n<head>\n  <meta charset="UTF-8">\n  <title>Mock HTML</title>\n</head>\n<body>\n  <h1>Mock Content</h1>\n  <p>This is a preview of HTML rendering.</p>\n</body>\n</html>';
                statusEl.textContent = 'mock';
                this._renderBody();
            }
        },

        /**
         * 根据当前模式渲染主体
         */
        _renderBody: function () {
            var body = this._root.querySelector('#html-body');
            if (!body) return;

            if (this._mode === 'preview') {
                this._renderPreview(body);
            } else {
                this._renderEdit(body);
            }
        },

        /**
         * 渲染预览模式：使用 sandboxed iframe 加载 srcdoc
         *
         * sandbox="" 禁止一切权限（脚本执行、表单提交、网络请求等）
         * srcdoc 直接内嵌内容，不发起 file:// 请求
         */
        _renderPreview: function (body) {
            var iframeHtml = this._buildSandboxedIframe(this._content);
            body.innerHTML = iframeHtml;
            body.className = 'html-viewer__body html-viewer__body--preview';
        },

        /**
         * 渲染编辑模式：左侧 textarea + 右侧 sandboxed iframe 预览
         */
        _renderEdit: function (body) {
            var self = this;
            body.innerHTML =
                '<div class="html-editor">' +
                '<textarea class="html-editor__input" id="html-textarea" spellcheck="false"></textarea>' +
                '<div class="html-editor__preview" id="html-preview"></div>' +
                '</div>';
            body.className = 'html-viewer__body html-viewer__body--edit';

            this._textarea = body.querySelector('#html-textarea');
            this._previewEl = body.querySelector('#html-preview');

            this._textarea.value = this._content;
            this._updateEditPreview();

            // 实时预览（防抖 300ms）
            this._textarea.addEventListener('input', function () {
                self._content = self._textarea.value;
                self._dirty = true;
                self._updateSaveButton();
                self._schedulePreviewUpdate();
            });
        },

        /**
         * 更新编辑模式的预览 iframe
         */
        _updateEditPreview: function () {
            if (!this._previewEl) return;
            this._previewEl.innerHTML = this._buildSandboxedIframe(this._content);
        },

        /**
         * 防抖预览更新
         */
        _schedulePreviewUpdate: function () {
            var self = this;
            if (this._saveTimer) clearTimeout(this._saveTimer);
            this._saveTimer = setTimeout(function () {
                self._updateEditPreview();
            }, 300);
        },

        /**
         * 构建 sandboxed iframe 的 HTML 字符串
         *
         * 使用 srcdoc 避免额外网络请求
         * sandbox="" 属性完全禁用脚本与同源
         */
        _buildSandboxedIframe: function (htmlContent) {
            var escaped = this._escapeAttr(htmlContent);
            return '<iframe class="html-viewer__iframe" ' +
                'sandbox="" ' +
                'srcdoc="' + escaped + '" ' +
                'loading="lazy"></iframe>';
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
            var statusEl = this._root.querySelector('#html-status');
            var saveBtn = this._root.querySelector('#html-save-btn');

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
            var saveBtn = this._root.querySelector('#html-save-btn');
            if (saveBtn) {
                saveBtn.disabled = !this._dirty;
            }
        },

        /**
         * 渲染错误
         */
        _renderError: function (msg) {
            var body = this._root.querySelector('#html-body');
            if (body) {
                body.innerHTML =
                    '<div class="html-error">' +
                    '<div class="html-error__icon">&#9888;</div>' +
                    '<div class="html-error__msg">' + this._escapeHtml(msg) + '</div>' +
                    '</div>';
            }
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
         * 属性转义（更严格的转义，防止 srcdoc 注入）
         */
        _escapeAttr: function (str) {
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;')
                .replace(/`/g, '&#96;');
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
            this._dirty = false;
        }
    };

    global.MMFBHTMLViewer = MMFBHTMLViewer;

})(window);
