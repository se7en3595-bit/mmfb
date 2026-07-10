/**
 * MMFB Docx Viewer - Word 文档预览 + 编辑模式
 *
 * 职责：
 *   1. 预览模式：直接渲染后端生成的 HTML
 *   2. 编辑模式：显示段落列表（textarea 逐段编辑）
 *   3. 保存：将编辑后的段落文本发回后端
 *
 * 依赖：
 *   - MMFBBridge (bridge.js)
 *   - MMFBLayout (layout.js)
 *
 * 使用方式：
 *   MMFBDocxViewer.init(rootEl, { filePath, fileName });
 *   MMFBDocxViewer.destroy();
 */
(function (global) {
    'use strict';

    var MMFBDocxViewer = {
        _root: null,
        _filePath: '',
        _fileName: '',
        _mode: 'preview',
        _html: '',
        _images: [],
        _paragraphs: [],
        _dirty: false,
        _statusEl: null,
        _saveBtn: null,

        /**
         * 初始化 Docx 查看器
         */
        init: function (root, opts) {
            this._root = root;
            this._filePath = opts.filePath || '';
            this._fileName = opts.fileName || '';
            this._mode = 'preview';
            this._html = '';
            this._paragraphs = [];
            this._dirty = false;

            this._renderShell();
            this._loadContent();

            return this;
        },

        /**
         * 渲染外壳
         */
        _renderShell: function () {
            var self = this;

            MMFBLayout.setTitle(this._fileName);
            MMFBLayout.setFooterLeft('DOCX');

            this._root.innerHTML =
                '<div class="docx-viewer">' +
                '<div class="docx-viewer__toolbar">' +
                '<div class="view-switcher">' +
                '<button class="view-switcher__btn active" data-mode="preview">预览</button>' +
                '<button class="view-switcher__btn" data-mode="edit">编辑</button>' +
                '</div>' +
                '<div class="docx-viewer__toolbar-right">' +
                '<span class="docx-viewer__status" id="docx-status"></span>' +
                '<button class="docx-viewer__save-btn" id="docx-save-btn" disabled>保存</button>' +
                '</div>' +
                '</div>' +
                '<div class="docx-viewer__body" id="docx-body"></div>' +
                '</div>';

            this._statusEl = this._root.querySelector('#docx-status');
            this._saveBtn = this._root.querySelector('#docx-save-btn');

            // 模式切换
            var btns = this._root.querySelectorAll('.view-switcher__btn');
            btns.forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var mode = btn.getAttribute('data-mode');
                    self._switchMode(mode);
                });
            });

            // 保存按钮
            this._saveBtn.addEventListener('click', function () {
                self._save();
            });

            // 获取文件信息
            if (global.MMFBBridge && global.MMFBBridge.api) {
                global.MMFBBridge.api.getFileInfo(this._filePath).then(function (info) {
                    try {
                        var sizeStr = MMFBDocxViewer._formatSize(info.size || 0);
                        MMFBLayout.setFooterLeft('DOCX | ' + sizeStr);
                    } catch (e) {}
                });
            }
        },

        /**
         * 通过 Bridge 加载预览 HTML
         */
        _loadContent: function () {
            var self = this;
            this._statusEl.textContent = '加载中...';

            if (global.MMFBBridge && global.MMFBBridge.api) {
                global.MMFBBridge.api.getPreview(this._filePath).then(function (preview) {
                    try {
                        // bridge.js 已自动 JSON.parse，preview 直接是对象
                        if (preview && preview.data && preview.data.html) {
                            self._html = preview.data.html;
                            // 存储图片数据
                            self._images = preview.data.images || [];
                            // 同时将 counts 发到 footer
                            var footerLabel = 'DOCX';
                            if (preview.data.paragraph_count !== undefined) {
                                footerLabel += ' | ' + preview.data.paragraph_count + ' 段';
                            }
                            if (preview.data.table_count) {
                                footerLabel += '/' + preview.data.table_count + ' 表';
                            }
                            MMFBLayout.setFooterLeft(footerLabel);
                        }
                        self._loadParagraphs();
                    } catch (e) {
                        self._html = '';
                        self._renderError('解析预览数据失败: ' + String(e));
                    }
                }).catch(function (err) {
                    self._renderError('加载失败: ' + String(err));
                });
            } else {
                // Mock 模式
                this._html = '<div class="docx-body"><h1 class="docx-para">Mock Document</h1><p class="docx-para">This is mock content for testing.</p></div>';
                this._paragraphs = [
                    { index: 0, text: 'Mock Document', style: 'Heading 1' },
                    { index: 1, text: 'This is mock content for testing.', style: 'Normal' },
                ];
                this._statusEl.textContent = 'mock';
                this._renderBody();
            }
        },

        /**
         * 获取编辑模式下的段落数据
         */
        _loadParagraphs: function () {
            var self = this;
            // 若有段落数据，则在切换编辑模式时用
            // 这里暂缓；切换编辑模式时再请求 getEdit
            this._renderBody();
        },

        /**
         * 根据当前模式渲染内容
         */
        _renderBody: function () {
            var body = this._root.querySelector('#docx-body');
            if (!body) return;

            if (this._mode === 'preview') {
                this._renderPreview(body);
            } else {
                this._renderEdit(body);
            }
        },

        /**
         * 预览模式：渲染 HTML
         */
        _renderPreview: function (body) {
            var html = this._html;
            // 替换图片占位符为 base64 内联图片
            if (this._images && this._images.length > 0) {
                for (var i = 0; i < this._images.length; i++) {
                    var img = this._images[i];
                    if (img.id && img.mime && img.base64) {
                        var src = 'data:' + img.mime + ';base64,' + img.base64;
                        // 匹配 data-id="xxx" 的占位符图片
                        var pattern = 'data-id="' + img.id + '"';
                        html = html.replace(pattern, 'src="' + src + '"');
                    }
                }
            }
            body.innerHTML = '<div class="docx-preview">' + html + '</div>';
            body.className = 'docx-viewer__body docx-viewer__body--preview';
            this._statusEl.textContent = '';
        },

        /**
         * 编辑模式：逐段落 textarea
         */
        _renderEdit: function (body) {
            var self = this;

            if (global.MMFBBridge && global.MMFBBridge.api) {
                global.MMFBBridge.api.getEdit(this._filePath).then(function (edit) {
                    try {
                        if (edit && edit.data && Array.isArray(edit.data.paragraphs)) {
                            // 深拷贝一份用于编辑
                            self._paragraphs = edit.data.paragraphs.map(function (p) {
                                return { index: p.index, text: p.text, style: p.style };
                            });
                            MMFBLayout.setFooterLeft('DOCX EDIT | ' + self._paragraphs.length + ' 段');
                        }
                        self._renderEditAreas(body);
                    } catch (e) {
                        self._renderError('解析段落数据失败: ' + String(e));
                    }
                }).catch(function (err) {
                    self._renderError('加载编辑数据失败: ' + String(err));
                });
            } else {
                this._renderEditAreas(body);
            }
        },

        /**
         * 渲染段落 textarea 列表
         */
        _renderEditAreas: function (body) {
            var self = this;
            var html =
                '<div class="docx-editor">' +
                '<div class="docx-editor__hint">编辑模式：修改下方任一段落后点击"保存"回写原文档</div>' +
                '<div id="docx-paragraph-list"></div>' +
                '</div>';
            body.innerHTML = html;
            body.className = 'docx-viewer__body docx-viewer__body--edit';

            var listEl = body.querySelector('#docx-paragraph-list');
            if (!listEl) return;

            this._paragraphs.forEach(function (p, i) {
                var textarea = document.createElement('textarea');
                textarea.className = 'docx-editor__textarea';
                textarea.value = p.text || '';
                textarea.setAttribute('data-index', String(i));
                textarea.setAttribute('data-style', p.style || 'Normal');
                textarea.rows = Math.max(1, (p.text || '').split('\n').length + 1);
                textarea.addEventListener('input', function () {
                    var idx = parseInt(textarea.getAttribute('data-index'), 10);
                    if (!isNaN(idx) && self._paragraphs[idx]) {
                        self._paragraphs[idx].text = textarea.value;
                        self._dirty = true;
                        self._updateSaveButton();
                    }
                });
                listEl.appendChild(textarea);
            });

            if (this._paragraphs.length === 0) {
                listEl.innerHTML = '<div class="docx-editor__empty">无可编辑段落</div>';
            }
        },

        /**
         * 切换预览/编辑模式
         */
        _switchMode: function (mode) {
            if (mode === this._mode) return;
            this._mode = mode;

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
         * 更新保存按钮状态
         */
        _updateSaveButton: function () {
            if (this._saveBtn) {
                this._saveBtn.disabled = !this._dirty;
            }
        },

        /**
         * 保存文档
         */
        _save: function () {
            var self = this;
            if (!this._dirty) return;

            this._statusEl.textContent = '保存中...';
            this._saveBtn.disabled = true;

            // 构造段落文本内容（以段落索引:文本 的 map 传给简单 B ridge）
            var payload = JSON.stringify(this._paragraphs);

            if (global.MMFBBridge && global.MMFBBridge.api) {
                // 调用 saveDocx 自定义方法（会由 Python Bridge 实现）
                global.MMFBBridge.api.saveDocx(this._filePath, payload).then(function (ok) {
                    if (ok) {
                        self._dirty = false;
                        self._statusEl.textContent = '已保存';
                        setTimeout(function () { self._statusEl.textContent = ''; }, 2000);
                        self._updateSaveButton();
                    } else {
                        self._statusEl.textContent = '保存失败';
                        self._saveBtn.disabled = false;
                    }
                }).catch(function (err) {
                    self._statusEl.textContent = '保存失败: ' + String(err);
                    self._saveBtn.disabled = false;
                });
            } else {
                setTimeout(function () {
                    self._dirty = false;
                    self._statusEl.textContent = '已保存 (mock)';
                    setTimeout(function () { self._statusEl.textContent = ''; }, 2000);
                    self._updateSaveButton();
                }, 300);
            }
        },

        /**
         * 渲染错误
         */
        _renderError: function (msg) {
            var body = this._root.querySelector('#docx-body');
            if (body) {
                body.innerHTML =
                    '<div class="docx-error">' +
                    '<div class="docx-error__icon">&#9888;</div>' +
                    '<div class="docx-error__msg">' + this._escapeHtml(msg) + '</div>' +
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
         * 文件大小格式化
         */
        _formatSize: function (bytes) {
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
            if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
            return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
        },

        /**
         * 销毁
         */
        destroy: function () {
            this._root = null;
            this._filePath = '';
            this._fileName = '';
            this._html = '';
            this._paragraphs = [];
            this._statusEl = null;
            this._saveBtn = null;
            this._dirty = false;
        }
    };

    global.MMFBDocxViewer = MMFBDocxViewer;

})(window);
