/**
 * MMFBSvgViewer - SVG 矢量图渲染 + 编辑 + 源码查看 + 导出 PNG
 *
 * 模式：
 *   - preview 预览模式: <img> 加载矢量图，CSS transform 缩放
 *   - edit    编辑模式: 左 textarea 源码 + 右 <img> 预览（实时）
 *   - source  源码模式: 全文展示 SVG XML
 *
 * 功能：
 *   1. 适应窗口 / 实际大小 / 百分比缩放（10%~800%）
 *   2. 滚轮缩放
 *   3. 导出 PNG（调用后端 QSvgRenderer 栅格化）
 *   4. 源码编辑 + 防抖实时预览 + 保存写回
 *
 * 依赖：MMFBBridge (bridge.js)
 *
 * 使用方式：
 *   MMFBSvgViewer.init(rootEl, { filePath, fileName });
 *   MMFBSvgViewer.destroy();
 */
(function (global) {
    'use strict';

    var MMFBSvgViewer = {
        _root: null,
        _config: null,
        _filePath: '',
        _fileName: '',
        _mode: 'preview',    // 'preview' | 'edit' | 'source'
        _content: '',        // 当前 SVG 源码文本
        _dirty: false,
        _scale: 1.0,
        _imgEl: null,
        _textarea: null,
        _saveTimer: null,
        _destroyed: false,

        /**
         * 初始化
         */
        init: function (rootEl, opts) {
            this._root = rootEl;
            this._config = opts || {};
            this._filePath = this._config.filePath || '';
            this._fileName = this._config.fileName || '';
            this._mode = 'preview';
            this._content = '';
            this._dirty = false;
            this._scale = 1.0;
            this._destroyed = false;

            this._renderShell();
            this._loadContent();
            return this;
        },

        /**
         * 销毁
         */
        destroy: function () {
            this._destroyed = true;
            if (this._saveTimer) {
                clearTimeout(this._saveTimer);
                this._saveTimer = null;
            }
            this._root = null;
            this._imgEl = null;
            this._textarea = null;
            this._config = null;
            this._content = '';
        },

        // =========================================================================
        // 外壳渲染
        // =========================================================================

        _renderShell: function () {
            var self = this;
            var w = this._config.width || 0;
            var h = this._config.height || 0;
            var viewbox = this._config.viewBox || '';
            var metaStr = '';
            if (w && h) {
                metaStr = w + ' x ' + h + ' px';
                if (viewbox) metaStr += ' | viewBox';
            } else if (viewbox) {
                metaStr = 'viewBox ' + viewbox;
            }

            this._root.innerHTML =
                '<div class="svg-viewer">' +
                '  <div class="svg-toolbar" id="svg-toolbar">' +
                '    <div class="svg-toolbar__left">' +
                '      <span class="svg-toolbar__title" title="' + this._esc(this._fileName) + '">' +
                this._esc(this._fileName) + '</span>' +
                '      <span class="svg-toolbar__meta" id="svg-meta">' + this._esc(metaStr) + '</span>' +
                '    </div>' +
                '    <div class="svg-toolbar__right">' +
                '      <span class="svg-toolbar__sep">|</span>' +
                '      <button class="svg-toolbar__btn active" id="svg-mode-preview" title="预览">&#128065;</button>' +
                '      <button class="svg-toolbar__btn" id="svg-mode-edit" title="编辑">&#9998;</button>' +
                '      <button class="svg-toolbar__btn" id="svg-mode-source" title="源码">&#128187;</button>' +
                '      <span class="svg-toolbar__sep">|</span>' +
                '      <button class="svg-toolbar__btn" id="svg-export-png" title="导出 PNG">&#128190;</button>' +
                '      <span class="svg-toolbar__sep">|</span>' +
                '      <button class="svg-toolbar__btn" id="svg-zoom-out" title="缩小">&#8722;</button>' +
                '      <span class="svg-toolbar__zoom" id="svg-zoom-level">100%</span>' +
                '      <button class="svg-toolbar__btn" id="svg-zoom-in" title="放大">+</button>' +
                '      <button class="svg-toolbar__btn" id="svg-fit" title="适应窗口">&#8862;</button>' +
                '      <button class="svg-toolbar__btn" id="svg-actual" title="实际大小">&#9635;</button>' +
                '      <span class="svg-toolbar__sep">|</span>' +
                '      <button class="svg-viewer__save-btn" id="svg-save-btn" disabled>&#128190; 保存</button>' +
                '      <span class="svg-viewer__footer-status" id="svg-status"></span>' +
                '    </div>' +
                '  </div>' +
                '  <div class="svg-canvas-container" id="svg-canvas-container">' +
                '    <div class="svg-loading" id="svg-loading">' +
                '      <div class="svg-loading__spinner"></div>' +
                '      <div>正在加载 SVG...</div>' +
                '    </div>' +
                '  </div>' +
                '</div>';

            this._bindToolbarEvents();
        },

        // =========================================================================
        // 内容加载
        // =========================================================================

        _loadContent: function () {
            var self = this;
            var container = this._root.querySelector('#svg-canvas-container');

            if (!global.MMFBBridge) {
                this._fallbackLoad();
                return;
            }

            global.MMFBBridge.api.getPreview(this._filePath).then(function (json) {
                if (self._destroyed) return;
                var result = typeof json === 'string' ? JSON.parse(json) : json;
                if (result.error) {
                    self._showError(result.error);
                    return;
                }
                var data = result.data || {};
                self._content = data.content || '';
                self._config.width = data.width || 0;
                self._config.height = data.height || 0;
                self._config.viewBox = data.viewBox || '';
                self._config.file_path = data.file_path || '';
                self._config.file_url = data.file_url || '';
                self._config.is_compressed = data.is_compressed || false;
                self._config.line_count = data.line_count || 0;

                // 更新 meta 信息
                var metaEl = self._root.querySelector('#svg-meta');
                if (metaEl && self._config.width && self._config.height) {
                    metaEl.textContent = self._config.width + ' x ' + self._config.height + ' px';
                }

                self._renderBody();
            }).catch(function (err) {
                if (self._destroyed) return;
                self._showError('加载失败: ' + String(err));
            });
        },

        _fallbackLoad: function () {
            var self = this;
            if (!global.MMFBBridge) return;
            global.MMFBBridge.api.readFile(this._filePath).then(function (text) {
                if (self._destroyed) return;
                self._content = text || '';
                self._renderBody();
            }).catch(function (err) {
                self._showError('加载失败: ' + String(err));
            });
        },

        // =========================================================================
        // 模式渲染
        // =========================================================================

        _renderBody: function () {
            var container = this._root.querySelector('#svg-canvas-container');
            if (!container) return;

            if (this._mode === 'preview') {
                this._renderPreview(container);
            } else if (this._mode === 'edit') {
                this._renderEdit(container);
            } else if (this._mode === 'source') {
                this._renderSource(container);
            }
        },

        _renderPreview: function (container) {
            var self = this;
            var statusEl = this._root.querySelector('#svg-status');
            if (statusEl) statusEl.textContent = '';

            container.className = 'svg-canvas-container';
            container.innerHTML =
                '<img class="svg-image" id="svg-preview-img" alt="SVG preview" draggable="false">';
            this._imgEl = container.querySelector('#svg-preview-img');

            this._imgEl.onload = function () {
                if (self._destroyed) return;
                self._fitToWindow();
            };
            this._imgEl.onerror = function () {
                container.innerHTML =
                    '<div class="svg-error">' +
                    '<div class="svg-error__icon">&#10060;</div>' +
                    '<div>SVG 渲染失败，请切换到源码模式查看</div>' +
                    '</div>';
            };

            this._loadSvgIntoImg(this._imgEl);
        },

        _loadSvgIntoImg: function (imgEl) {
            // 优先使用 file:// URL（避免大 SVG 的 base64 膨胀）
            var fileUrl = this._config.file_url;
            if (fileUrl) {
                imgEl.src = fileUrl;
                return;
            }
            // fallback: base64 data URL
            try {
                var base64 = btoa(unescape(encodeURIComponent(this._content)));
                imgEl.src = 'data:image/svg+xml;base64,' + base64;
            } catch (e) {
                // 含非 Latin1 URI 编码失败时，走URIComponent路径
                try {
                    imgEl.src = 'data:image/svg+xml,' + encodeURIComponent(this._content);
                } catch (e2) {
                    // 无法加载
                }
            }
        },

        _renderEdit: function (container) {
            var self = this;
            container.className = 'svg-canvas-container';
            container.innerHTML =
                '<div class="svg-editor">' +
                '  <textarea class="svg-editor__input" id="svg-textarea" spellcheck="false"></textarea>' +
                '  <div class="svg-editor__preview" id="svg-editor-preview"></div>' +
                '</div>';

            this._textarea = container.querySelector('#svg-textarea');
            var previewBox = container.querySelector('#svg-editor-preview');

            this._textarea.value = this._content;
            this._renderEditPreview(previewBox);

            this._textarea.addEventListener('input', function () {
                self._content = self._textarea.value;
                self._dirty = true;
                self._updateSaveBtn();
                self._schedulePreviewUpdate(previewBox);
            });
        },

        _schedulePreview: null,

        _schedulePreviewUpdate: function (previewBox) {
            var self = this;
            if (this._schedulePreview) clearTimeout(this._schedulePreview);
            this._schedulePreview = setTimeout(function () {
                self._renderEditPreview(previewBox);
            }, 300);
        },

        _renderEditPreview: function (previewBox) {
            if (!previewBox) return;
            previewBox.innerHTML = '<img class="svg-image" id="svg-edit-preview-img" alt="SVG preview" draggable="false">';
            var img = previewBox.querySelector('#svg-edit-preview-img');
            this._loadSvgIntoImg(img);
        },

        _renderSource: function (container) {
            var lineCount = this._content.split('\n').length;
            var lineNumbers = '';
            for (var i = 1; i <= lineCount; i++) {
                lineNumbers += i + '\n';
            }
            container.className = 'svg-canvas-container';
            container.innerHTML =
                '<div class="svg-source-pane" style="display:flex;font-family:var(--font-mono);font-size:13px;line-height:1.5;">' +
                '<pre style="color:rgba(255,255,255,0.35);text-align:right;padding-right:12px;margin:0;user-select:none;min-width:36px;">' +
                lineNumbers + '</pre>' +
                '<pre id="svg-source-content" style="flex:1;margin:0;color:#E0E0E0;white-space:pre-wrap;word-break:break-all;">' +
                this._esc(this._content || '(空文件)') + '</pre>' +
                '</div>';
        },

        // =========================================================================
        // 缩放
        // =========================================================================

        _zoom: function (factor) {
            var newScale = this._scale * factor;
            if (newScale < 0.1) newScale = 0.1;
            if (newScale > 8.0) newScale = 8.0;
            this._scale = newScale;
            this._applyScale();
        },

        _fitToWindow: function () {
            if (!this._imgEl) return;
            var container = this._root.querySelector('#svg-canvas-container');
            if (!container) return;

            var availW = container.clientWidth - 48;
            var availH = container.clientHeight - 48;
            var natW = this._imgEl.naturalWidth || availW;
            var natH = this._imgEl.naturalHeight || availH;
            var scaleW = availW / natW;
            var scaleH = availH / natH;
            this._scale = Math.min(scaleW, scaleH, 1.0);
            if (this._scale < 0.05) this._scale = 0.05;
            this._applyScale();
        },

        _actualSize: function () {
            this._scale = 1.0;
            this._applyScale();
        },

        _applyScale: function () {
            if (this._imgEl) {
                this._imgEl.style.transform = 'scale(' + this._scale + ')';
            }
            var el = this._root.querySelector('#svg-zoom-level');
            if (el) el.textContent = Math.round(this._scale * 100) + '%';
        },

        // =========================================================================
        // 模式切换
        // =========================================================================

        _switchMode: function (mode) {
            if (mode === this._mode) return;

            // edit -> 其他：先同步 textarea
            if (this._mode === 'edit' && this._textarea) {
                this._content = this._textarea.value;
            }

            this._mode = mode;

            // 更新按钮高亮
            var map = {
                preview: this._root.querySelector('#svg-mode-preview'),
                edit: this._root.querySelector('#svg-mode-edit'),
                source: this._root.querySelector('#svg-mode-source'),
            };
            for (var key in map) {
                if (map[key]) map[key].classList.toggle('active', key === mode);
            }

            this._renderBody();
        },

        // =========================================================================
        // 保存
        // =========================================================================

        _save: function () {
            var self = this;
            var statusEl = this._root.querySelector('#svg-status');
            var saveBtn = this._root.querySelector('#svg-save-btn');

            if (this._mode === 'edit' && this._textarea) {
                this._content = this._textarea.value;
            }

            if (!global.MMFBBridge) {
                if (statusEl) statusEl.textContent = 'Bridge 未就绪';
                return;
            }

            if (statusEl) statusEl.textContent = '保存中...';
            if (saveBtn) saveBtn.disabled = true;

            global.MMFBBridge.api.saveFile(this._filePath, this._content).then(function (ok) {
                if (self._destroyed) return;
                if (ok) {
                    self._dirty = false;
                    if (statusEl) {
                        statusEl.textContent = '已保存';
                        setTimeout(function () {
                            if (statusEl && !self._destroyed) statusEl.textContent = '';
                        }, 1500);
                    }
                    self._updateSaveBtn();
                    // 预览模式需要重加载
                    if (self._mode === 'preview') {
                        var container = self._root.querySelector('#svg-canvas-container');
                        if (container) self._renderPreview(container);
                    }
                } else {
                    if (statusEl) statusEl.textContent = '保存失败';
                    if (saveBtn) saveBtn.disabled = false;
                }
            }).catch(function (err) {
                if (statusEl) statusEl.textContent = '保存失败: ' + String(err);
                if (saveBtn) saveBtn.disabled = false;
            });
        },

        _updateSaveBtn: function () {
            var saveBtn = this._root.querySelector('#svg-save-btn');
            if (saveBtn) saveBtn.disabled = !this._dirty;
        },

        // =========================================================================
        // 导出 PNG
        // =========================================================================

        _showExportDialog: function () {
            var self = this;
            this._hideExportDialog();

            var defaultW = this._config.width || 1024;
            var defaultH = this._config.height || 1024;

            var maskDiv = document.createElement('div');
            maskDiv.className = 'svg-overlay-mask';
            maskDiv.id = 'svg-export-mask';
            this._root.appendChild(maskDiv);

            var dialogDiv = document.createElement('div');
            dialogDiv.className = 'svg-export-dialog';
            dialogDiv.id = 'svg-export-dialog';
            dialogDiv.innerHTML =
                '<div class="svg-export-dialog__title">导出 PNG</div>' +
                '<div class="svg-export-dialog__row">' +
                '  <label>宽度</label>' +
                '  <input type="number" id="svg-export-width" min="1" max="8192" value="' + defaultW + '">' +
                '  <span style="color:rgba(255,255,255,0.5);font-size:11px;">px</span>' +
                '</div>' +
                '<div class="svg-export-dialog__row">' +
                '  <label>高度</label>' +
                '  <input type="number" id="svg-export-height" min="1" max="8192" value="' + defaultH + '">' +
                '  <span style="color:rgba(255,255,255,0.5);font-size:11px;">px</span>' +
                '</div>' +
                '<div class="svg-export-dialog__actions">' +
                '  <button class="svg-export-dialog__btn svg-export-dialog__btn--primary" id="svg-export-confirm">导出</button>' +
                '  <button class="svg-export-dialog__btn" id="svg-export-cancel">取消</button>' +
                '</div>';
            this._root.appendChild(dialogDiv);

            this._root.querySelector('#svg-export-cancel').addEventListener('click', function () {
                self._hideExportDialog();
            });
            maskDiv.addEventListener('click', function () {
                self._hideExportDialog();
            });
            this._root.querySelector('#svg-export-confirm').addEventListener('click', function () {
                var wEl = self._root.querySelector('#svg-export-width');
                var hEl = self._root.querySelector('#svg-export-height');
                var w = wEl ? parseInt(wEl.value, 10) || 0 : 0;
                var h = hEl ? parseInt(hEl.value, 10) || 0 : 0;
                self._hideExportDialog();
                self._doExportPng(w, h);
            });
        },

        _hideExportDialog: function () {
            var dlg = this._root.querySelector('#svg-export-dialog');
            if (dlg) dlg.remove();
            var mask = this._root.querySelector('#svg-export-mask');
            if (mask) mask.remove();
        },

        _doExportPng: function (width, height) {
            var self = this;
            var statusEl = this._root.querySelector('#svg-status');
            if (statusEl) statusEl.textContent = '栅格化中...';

            if (!global.MMFBBridge) {
                if (statusEl) statusEl.textContent = 'Bridge 未就绪';
                return;
            }

            var payload = {
                src: this._filePath,
                width: width,
                height: height,
            };

            global.MMFBBridge.api.svgToPng(payload).then(function (json) {
                if (self._destroyed) return;
                var result = typeof json === 'string' ? JSON.parse(json) : json;
                if (result.ok) {
                    if (statusEl) {
                        statusEl.textContent = '导出成功 (' + result.width + 'x' + result.height + ')';
                        setTimeout(function () {
                            if (statusEl && !self._destroyed) statusEl.textContent = '';
                        }, 2500);
                    }
                } else {
                    if (statusEl) statusEl.textContent = '导出失败: ' + (result.error || '未知');
                }
            }).catch(function (err) {
                if (statusEl) statusEl.textContent = '导出失败: ' + String(err);
            });
        },

        // =========================================================================
        // 事件绑定
        // =========================================================================

        _bindToolbarEvents: function () {
            var self = this;
            var root = this._root;
            if (!root) return;

            var btnPreview = root.querySelector('#svg-mode-preview');
            var btnEdit = root.querySelector('#svg-mode-edit');
            var btnSource = root.querySelector('#svg-mode-source');
            var btnExport = root.querySelector('#svg-export-png');
            var btnZoomIn = root.querySelector('#svg-zoom-in');
            var btnZoomOut = root.querySelector('#svg-zoom-out');
            var btnFit = root.querySelector('#svg-fit');
            var btnActual = root.querySelector('#svg-actual');
            var btnSave = root.querySelector('#svg-save-btn');

            if (btnPreview) btnPreview.addEventListener('click', function () { self._switchMode('preview'); });
            if (btnEdit) btnEdit.addEventListener('click', function () { self._switchMode('edit'); });
            if (btnSource) btnSource.addEventListener('click', function () { self._switchMode('source'); });
            if (btnExport) btnExport.addEventListener('click', function () { self._showExportDialog(); });
            if (btnZoomIn) btnZoomIn.addEventListener('click', function () { self._zoom(1.25); });
            if (btnZoomOut) btnZoomOut.addEventListener('click', function () { self._zoom(0.8); });
            if (btnFit) btnFit.addEventListener('click', function () { self._fitToWindow(); });
            if (btnActual) btnActual.addEventListener('click', function () { self._actualSize(); });
            if (btnSave) btnSave.addEventListener('click', function () { self._save(); });

            // 滚轮缩放（仅在 preview 模式）
            var container = root.querySelector('#svg-canvas-container');
            if (container) {
                container.addEventListener('wheel', function (e) {
                    if (self._mode !== 'preview') return;
                    e.preventDefault();
                    var factor = e.deltaY > 0 ? 0.88 : 1.14;
                    self._zoom(factor);
                }, { passive: false });
            }
        },

        /**
         * 显示错误
         */
        _showError: function (msg) {
            var container = this._root.querySelector('#svg-canvas-container');
            if (!container) return;
            container.innerHTML =
                '<div class="svg-error">' +
                '<div class="svg-error__icon">&#9888;</div>' +
                '<div>预览失败</div>' +
                '<div style="font-size:11px;opacity:0.7;margin-top:8px;">' + this._esc(msg || '未知错误') + '</div>' +
                '</div>';
        },

        /**
         * HTML 转义
         */
        _esc: function (str) {
            if (str === null || str === undefined) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        },
    };

    global.MMFBSvgViewer = MMFBSvgViewer;

})(window);
