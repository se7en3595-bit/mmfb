/**
 * MMFB TextViewer - 纯文本预览 + 编辑双模式
 *
 * 职责：
 *   1. 预览模式：显示纯文本（<pre>保持换行）
 *   2. 编辑模式：textarea 编辑 + 保存
 *   3. 模式切换：工具栏按钮
 *
 * 使用方式:
 *   new MMFBTextViewer(rootEl, { filePath, fileName, content, encoding, lineCount })
 *   或者
 *   MMFBTextViewer.init(rootEl, opts) // compatible
 */
(function (global) {
    'use strict';

    var MMFBTextViewer = function (root, data) {
        console.log('[TextViewer:diag] constructor called, root:', root, 'data keys:', Object.keys(data || {}));
        this._root = root;
        this._data = data || {};
        this._filePath = this._data.file_path || '';
        this._fileName = this._data.fileName || '';
        this._content = this._data.content || '';
        this._encoding = this._data.encoding || 'utf-8';
        this._lineCount = this._data.lineCount || 0;
        this._mode = 'preview'; // 'preview' | 'edit'
        this._dirty = false;
        this._textarea = null;
        this._saveTimer = null;

        // 兼容：如果外部使用 init，也能工作
        if (this.init) {
            this.init.call(this, root, { filePath: this._filePath, fileName: this._fileName });
        } else {
            this._init();
        }
    };

    /**
     * 初始化（供直接调用 init 使用）
     */
    MMFBTextViewer.prototype._init = function () {
        this._renderShell();
        this._renderBody();
        this._bindEvents();
    };

    /**
     * 渲染外壳
     */
    MMFBTextViewer.prototype._renderShell = function () {
        var self = this;
        if (!this._root) return;

        // 设置窗口标题
        if (global.MMFBLayout) {
            global.MMFBLayout.setTitle(this._fileName);
            global.MMFBLayout.setFooterLeft('文本');
        }

        this._root.innerHTML =
            '<div class="text-viewer">' +
                '<div class="text-viewer__toolbar">' +
                    '<div class="view-switcher">' +
                        '<button class="view-switcher__btn active" data-mode="preview">预览</button>' +
                        '<button class="view-switcher__btn" data-mode="edit">编辑</button>' +
                    '</div>' +
                    '<div class="text-viewer__toolbar-right">' +
                        '<span class="text-viewer__status" id="text-status"></span>' +
                        '<button class="text-viewer__save-btn" id="text-save-btn" disabled>保存</button>' +
                    '</div>' +
                '</div>' +
                '<div class="text-viewer__body" id="text-body"></div>' +
            '</div>';
    };

    /**
     * 根据模式渲染主体
     */
    MMFBTextViewer.prototype._renderBody = function () {
        var body = this._root.querySelector('#text-body');
        if (!body) return;

        if (this._mode === 'preview') {
            this._renderPreview(body);
        } else {
            this._renderEdit(body);
        }
    };

    /**
     * 渲染预览模式
     */
    MMFBTextViewer.prototype._renderPreview = function (container) {
        console.log('[TextViewer:diag] _renderPreview, content length:', this._content.length, 'root innerHTML length:', this._root.innerHTML.length);
        // 对 HTML 转义，防止 XSS
        var escaped = this._escapeHtml(this._content);
        container.innerHTML =
            '<pre class="text-viewer__pre">' + escaped + '</pre>';
        container.className = 'text-viewer__body text-viewer__body--preview';
    };

    /**
     * 渲染编辑模式
     */
    MMFBTextViewer.prototype._renderEdit = function (container) {
        var self = this;
        container.innerHTML =
            '<textarea class="text-viewer__textarea" id="text-textarea" spellcheck="false">' +
                this._escapeHtml(this._content) +
            '</textarea>';
        container.className = 'text-viewer__body text-viewer__body--edit';

        this._textarea = container.querySelector('#text-textarea');
        if (this._textarea) {
            this._textarea.addEventListener('input', function () {
                self._content = self._textarea.value;
                self._dirty = true;
                self._updateSaveButton();
            });
        }
    };

    /**
     * 绑定事件
     */
    MMFBTextViewer.prototype._bindEvents = function () {
        var self = this;
        var root = this._root;
        if (!root) return;

        // 模式切换按钮
        var btns = root.querySelectorAll('.view-switcher__btn');
        btns.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var mode = btn.getAttribute('data-mode');
                self._switchMode(mode);
            });
        });

        // 保存按钮
        var saveBtn = root.querySelector('#text-save-btn');
        if (saveBtn) {
            saveBtn.addEventListener('click', function () {
                self._save();
            });
        }
    };

    /**
     * 切换预览/编辑模式
     */
    MMFBTextViewer.prototype._switchMode = function (mode) {
        if (mode === this._mode) return;

        // 编辑 -> 预览：同步 textarea 内容
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
    };

    /**
     * 保存文件
     */
    MMFBTextViewer.prototype._save = function () {
        var self = this;
        var statusEl = this._root.querySelector('#text-status');
        var saveBtn = this._root.querySelector('#text-save-btn');

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
    };

    /**
     * 更新保存按钮状态
     */
    MMFBTextViewer.prototype._updateSaveButton = function () {
        var saveBtn = this._root.querySelector('#text-save-btn');
        if (saveBtn) {
            saveBtn.disabled = !this._dirty;
        }
    };

    /**
     * HTML 转义
     */
    MMFBTextViewer.prototype._escapeHtml = function (str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    };

    /**
     * 销毁
     */
    MMFBTextViewer.prototype.destroy = function () {
        if (this._saveTimer) {
            clearTimeout(this._saveTimer);
            this._saveTimer = null;
        }
        this._root = null;
        this._textarea = null;
        this._content = '';
        this._dirty = false;
    };

    // 工厂方法：兼容 pages.js 的 .init() 调用风格
    MMFBTextViewer.init = function (root, data) {
        console.log('[TextViewer:diag] init called, data:', JSON.stringify(data).substring(0, 200));
        return new MMFBTextViewer(root, data);
    };

    // 导出
    global.MMFBTextViewer = MMFBTextViewer;

})(window);
