/**
 * MMFB ImageViewer - 光栅图像渲染与编辑模块
 *
 * 功能：
 * 1. 自适应窗口（初始 fit-window）
 * 2. 缩放（10% - 800%，滚轮 / 按钮）
 * 3. 旋转（90 度步进，显示与保存）
 * 4. 翻转（水平/垂直）
 * 5. 裁剪（拖拽选区，保存到文件）
 * 6. 滤镜（模糊/锐化/轮廓/浮雕/平滑/边缘增强）
 * 7. 亮度/对比度调整
 * 8. 自动对比度
 * 9. 适应窗口 / 实际大小切换
 * 10. GIF 动画自动播放
 * 11. 图像元信息展示（分辨率/模式/EXIF）
 *
 * 调用方式:
 *   MMFBImageViewer.init(rootEl, { filePath, fileName, fileSize?, width?, height?, data_url?, exif?, is_animated?, frame_count? })
 *   MMFBImageViewer.destroy()
 */
(function (global) {
    'use strict';

    var MMFBImageViewer = {
        _root: null,
        _config: null,
        _img: null,
        _canvas: null,
        _ctx: null,
        _scale: 1.0,
        _rotation: 0,
        _destroyed: false,
        _isDragging: false,
        _dragStart: { x: 0, y: 0 },
        _scrollStart: { x: 0, y: 0 },

        // 裁剪相关
        _cropMode: false,
        _cropSelecting: false,
        _cropRect: null,
        _cropStart: null,

        // 编辑状态
        _editMode: false,

        /**
         * 初始化图像查看器
         */
        init: function (rootEl, config) {
            this._root = rootEl;
            this._config = config || {};
            this._destroyed = false;
            this._scale = 1.0;
            this._rotation = 0;

            this._renderShell();
            this._loadImage();
        },

        /**
         * 销毁，清理资源
         */
        destroy: function () {
            this._destroyed = true;
            this._img = null;
            this._canvas = null;
            this._ctx = null;
            this._root = null;
        },

        /**
         * 渲染外壳 HTML
         */
        _renderShell: function () {
            if (!this._root) return;

            var fileName = (this._config.fileName || '').replace(/[<>&"]/g, '');
            var width = this._config.width || 0;
            var height = this._config.height || 0;
            var format = this._config.format || '';
            var mode = this._config.mode || '';
            var isAnimated = this._config.is_animated || false;
            var frameCount = this._config.frame_count || 1;

            var metaParts = [];
            if (width && height) metaParts.push(width + ' x ' + height);
            if (format) metaParts.push(format);
            if (mode) metaParts.push(mode);
            if (isAnimated) metaParts.push(frameCount + ' frames');

            var metaStr = metaParts.join(' | ');
            var editable = this._config.editable !== false;

            this._root.innerHTML =
                '<div class="image-viewer">' +
                '  <div class="image-toolbar" id="image-toolbar">' +
                '    <div class="image-toolbar__left">' +
                '      <span class="image-toolbar__title" title="' + fileName + '">' + fileName + '</span>' +
                '      <span class="image-toolbar__meta" id="image-meta">' + this._escapeHtml(metaStr) + '</span>' +
                '    </div>' +
                '    <div class="image-toolbar__right" id="image-toolbar-right">' +
                '      <button class="image-toolbar__btn" id="image-edit-toggle" title="切换编辑模式">&#9998;</button>' +
                '      <span class="image-toolbar__sep image-edit-btn" id="image-edit-sep" style="display:none">|</span>' +
                '      <button class="image-toolbar__btn image-edit-btn" id="image-crop" title="裁剪" style="display:none">&#9684;</button>' +
                '      <button class="image-toolbar__btn image-edit-btn" id="image-flip-h" title="水平翻转" style="display:none">&#10548;</button>' +
                '      <button class="image-toolbar__btn image-edit-btn" id="image-flip-v" title="垂直翻转" style="display:none">&#10549;</button>' +
                '      <span class="image-toolbar__sep image-edit-btn" id="image-edit-sep2" style="display:none">|</span>' +
                '      <button class="image-toolbar__btn image-edit-btn" id="image-filter" title="滤镜" style="display:none">&#128292;</button>' +
                '      <button class="image-toolbar__btn image-edit-btn" id="image-adjust" title="亮度/对比度" style="display:none">&#9728;</button>' +
                '      <span class="image-toolbar__sep image-edit-btn" id="image-edit-sep3" style="display:none">|</span>' +
                '      <button class="image-toolbar__btn image-edit-btn" id="image-save" title="保存" style="display:none">&#128190;</button>' +
                '      <span class="image-toolbar__sep">|</span>' +
                '      <button class="image-toolbar__btn" id="image-rotate-left" title="逆时针旋转">&#8634;</button>' +
                '      <button class="image-toolbar__btn" id="image-rotate-right" title="顺时针旋转">&#8635;</button>' +
                '      <button class="image-toolbar__btn" id="image-zoom-out" title="缩小">&#8722;</button>' +
                '      <span class="image-toolbar__zoom" id="image-zoom-level">100%</span>' +
                '      <button class="image-toolbar__btn" id="image-zoom-in" title="放大">+</button>' +
                '      <button class="image-toolbar__btn" id="image-fit" title="适应窗口">&#8862;</button>' +
                '      <button class="image-toolbar__btn" id="image-actual" title="实际大小">&#9635;</button>' +
                '      <button class="image-toolbar__btn" id="image-info" title="元信息">&#8505;</button>' +
                '    </div>' +
                '  </div>' +
                '  <div class="image-edit-bar" id="image-edit-bar" style="display:none">' +
                '    <span class="image-edit-bar__label">裁剪选区</span>' +
                '    <span class="image-edit-bar__coords" id="image-crop-coords">--</span>' +
                '    <button class="image-edit-bar__btn image-edit-bar__btn--primary" id="image-crop-apply">应用</button>' +
                '    <button class="image-edit-bar__btn" id="image-crop-cancel">取消</button>' +
                '  </div>' +
                '  <div class="image-canvas-container" id="image-canvas-container">' +
                '    <div class="image-loading" id="image-loading">' +
                '      <div class="image-loading__spinner"></div>' +
                '      <div>正在加载图像...</div>' +
                '    </div>' +
                '    <div class="image-crop-overlay" id="image-crop-overlay" style="display:none"></div>' +
                '  </div>' +
                '  <div class="image-info-panel" id="image-info-panel"></div>' +
                '</div>';

            this._bindToolbarEvents();
            this._bindWheelEvents();
            this._bindDragEvents();
            this._bindCropEvents();

            if (!editable) {
                var toggle = this._root.querySelector('#image-edit-toggle');
                if (toggle) toggle.style.display = 'none';
            }
        },

        /**
         * 加载图像
         */
        _loadImage: function () {
            var self = this;
            var container = this._root.querySelector('#image-canvas-container');
            if (!container) return;

            var dataUrl = this._config.data_url;
            if (!dataUrl) {
                container.innerHTML =
                    '<div class="image-error">' +
                    '<div class="image-error__icon">&#9888;</div>' +
                    '<div>图像数据不可用</div>' +
                    '<div style="font-size:12px;opacity:0.7;margin-top:8px;">' +
                    '文件可能过大或读取失败' +
                    '</div>' +
                    '</div>';
                return;
            }

            this._img = new Image();
            this._img.onload = function () {
                if (self._destroyed) return;
                self._initCanvas();
                self._fitToWindow();
                self._render();
            };
            this._img.onerror = function () {
                if (!container) return;
                container.innerHTML =
                    '<div class="image-error">' +
                    '<div class="image-error__icon">&#10060;</div>' +
                    '<div>无法加载图像</div>' +
                    '</div>';
            };
            this._img.src = dataUrl;
        },

        /**
         * 初始化 canvas
         */
        _initCanvas: function () {
            var container = this._root.querySelector('#image-canvas-container');
            if (!container) return;

            var loading = container.querySelector('#image-loading');
            if (loading) loading.remove();

            var oldCanvas = container.querySelector('canvas.image-canvas');
            if (oldCanvas) oldCanvas.remove();

            this._canvas = document.createElement('canvas');
            this._canvas.className = 'image-canvas';
            this._ctx = this._canvas.getContext('2d');
            var overlay = container.querySelector('#image-crop-overlay');
            if (overlay) {
                container.insertBefore(this._canvas, overlay);
            } else {
                container.appendChild(this._canvas);
            }
        },

        /**
         * 渲染图像到 canvas
         */
        _render: function () {
            if (!this._ctx || !this._img) return;

            var imgW = this._img.naturalWidth || this._img.width;
            var imgH = this._img.naturalHeight || this._img.height;

            var isRotated90 = (this._rotation % 180 !== 0);
            var drawW = isRotated90 ? imgH : imgW;
            var drawH = isRotated90 ? imgW : imgH;

            var canvasW = Math.round(drawW * this._scale);
            var canvasH = Math.round(drawH * this._scale);

            this._canvas.width = canvasW;
            this._canvas.height = canvasH;

            this._ctx.clearRect(0, 0, canvasW, canvasH);
            this._ctx.save();

            this._ctx.translate(canvasW / 2, canvasH / 2);
            this._ctx.rotate((this._rotation * Math.PI) / 180);
            this._ctx.drawImage(this._img, -imgW * this._scale / 2, -imgH * this._scale / 2,
                imgW * this._scale, imgH * this._scale);

            this._ctx.restore();
        },

        /**
         * 适应窗口
         */
        _fitToWindow: function () {
            if (!this._img || !this._root) return;

            var container = this._root.querySelector('#image-canvas-container');
            if (!container) return;

            var imgW = this._img.naturalWidth || this._img.width;
            var imgH = this._img.naturalHeight || this._img.height;

            var availW = container.clientWidth - 40;
            var availH = container.clientHeight - 40;

            var scaleW = availW / imgW;
            var scaleH = availH / imgH;
            this._scale = Math.min(scaleW, scaleH, 1.0);
            if (this._scale < 0.05) this._scale = 0.05;

            this._updateZoomInfo();
        },

        /**
         * 实际大小
         */
        _actualSize: function () {
            this._scale = 1.0;
            this._updateZoomInfo();
            this._render();
        },

        /**
         * 缩放
         */
        _zoom: function (factor) {
            var newScale = this._scale * factor;
            if (newScale < 0.1) newScale = 0.1;
            if (newScale > 8.0) newScale = 8.0;
            this._scale = newScale;
            this._updateZoomInfo();
            this._render();
        },

        /**
         * 旋转（仅显示，不修改原图）
         */
        _rotate: function (degrees) {
            this._rotation = (this._rotation + degrees + 360) % 360;
            this._render();
            this._updateRotatedMeta();
        },

        /**
         * 更新旋转后 meta 显示
         */
        _updateRotatedMeta: function () {
            var width = this._config.width || 0;
            var height = this._config.height || 0;
            if (width && height) {
                var displayW = (this._rotation % 180 !== 0) ? height : width;
                var displayH = (this._rotation % 180 !== 0) ? width : height;
                var metaEl = this._root.querySelector('#image-meta');
                if (metaEl) {
                    var parts = metaEl.textContent.split(' | ');
                    var newParts = [displayW + ' x ' + displayH];
                    for (var i = 1; i < parts.length; i++) {
                        if (parts[i].indexOf('deg') < 0) newParts.push(parts[i]);
                    }
                    if (this._rotation !== 0) newParts.push(this._rotation + ' deg');
                    metaEl.textContent = newParts.join(' | ');
                }
            }
        },

        /**
         * 更新缩放信息
         */
        _updateZoomInfo: function () {
            var el = this._root.querySelector('#image-zoom-level');
            if (el) el.textContent = Math.round(this._scale * 100) + '%';
        },

        /**
         * 切换编辑模式 UI
         */
        _toggleEditMode: function () {
            this._editMode = !this._editMode;
            var editBtns = this._root.querySelectorAll('.image-edit-btn');
            for (var i = 0; i < editBtns.length; i++) {
                editBtns[i].style.display = this._editMode ? '' : 'none';
            }
            var toggle = this._root.querySelector('#image-edit-toggle');
            if (toggle) toggle.classList.toggle('active', this._editMode);
            if (!this._editMode) this._exitCropMode();
        },

        /**
         * 进入裁剪模式
         */
        _enterCropMode: function () {
            this._cropMode = true;
            this._cropRect = null;
            var overlay = this._root.querySelector('#image-crop-overlay');
            if (overlay) {
                overlay.style.display = 'block';
                overlay.innerHTML = '<div class="image-crop-hint">拖拽鼠标选择裁剪区域</div>';
            }
            var editBar = this._root.querySelector('#image-edit-bar');
            if (editBar) editBar.style.display = 'flex';
            this._updateCropCoords(null);
        },

        /**
         * 退出裁剪模式
         */
        _exitCropMode: function () {
            this._cropMode = false;
            this._cropSelecting = false;
            this._cropRect = null;
            this._cropStart = null;
            var overlay = this._root.querySelector('#image-crop-overlay');
            if (overlay) {
                overlay.style.display = 'none';
                overlay.innerHTML = '';
                var box = overlay.querySelector('.image-crop-box');
                if (box) box.remove();
            }
            var editBar = this._root.querySelector('#image-edit-bar');
            if (editBar) editBar.style.display = 'none';
        },

        /**
         * 更新裁剪坐标显示
         */
        _updateCropCoords: function (rect) {
            var el = this._root.querySelector('#image-crop-coords');
            if (!el) return;
            if (!rect) {
                el.textContent = '--';
                return;
            }
            el.textContent = 'x:' + Math.round(rect.left) + ' y:' + Math.round(rect.top) + ' ' +
                Math.round(rect.right - rect.left) + 'x' + Math.round(rect.bottom - rect.top);
        },

        /**
         * 发送编辑操作到后端
         */
        _applyEdit: function (operations, callback) {
            var self = this;
            var filePath = this._config.data ? this._config.data.file_path : (this._config.filePath || '');

            var container = this._root.querySelector('#image-canvas-container');
            if (container) {
                var loader = document.createElement('div');
                loader.className = 'image-edit-loading';
                loader.innerHTML = '<div class="image-loading__spinner"></div><div>处理中...</div>';
                container.appendChild(loader);
            }

            if (!global.MMFBBridge) {
                if (container) {
                    var ld = container.querySelector('.image-edit-loading');
                    if (ld) ld.remove();
                }
                if (callback) callback({ ok: false, error: 'Bridge 未就绪' });
                return;
            }

            global.MMFBBridge.api.applyImageEdit(filePath, operations).then(function (json) {
                if (container) {
                    var ld = container.querySelector('.image-edit-loading');
                    if (ld) ld.remove();
                }
                var result = typeof json === 'string' ? JSON.parse(json) : json;
                if (callback) callback(result);
            }).catch(function (err) {
                if (container) {
                    var ld = container.querySelector('.image-edit-loading');
                    if (ld) ld.remove();
                }
                if (callback) callback({ ok: false, error: String(err) });
            });
        },

        /**
         * 应用裁剪
         */
        _applyCrop: function () {
            if (!this._cropRect) return;

            var self = this;
            var rect = this._cropRect;
            var imgW = this._img.naturalWidth || this._img.width;
            var imgH = this._img.naturalHeight || this._img.height;
            var canvasDisplayW = this._canvas.clientWidth || this._canvas.width;
            var canvasDisplayH = this._canvas.clientHeight || this._canvas.height;

            var pixelRatio = imgW / canvasDisplayW;

            var left = Math.max(0, Math.round(rect.left * pixelRatio));
            var top = Math.max(0, Math.round(rect.top * pixelRatio));
            var right = Math.min(imgW, Math.round(rect.right * pixelRatio));
            var bottom = Math.min(imgH, Math.round(rect.bottom * pixelRatio));

            if (right - left < 2 || bottom - top < 2) {
                self._exitCropMode();
                return;
            }

            this._applyEdit([{ op: 'crop', left: left, top: top, right: right, bottom: bottom }], function (result) {
                if (result.ok) {
                    self._config.width = result.width;
                    self._config.height = result.height;
                    self._exitCropMode();
                    self._reloadImage(result.path);
                } else {
                    alert('裁剪失败: ' + (result.error || '未知错误'));
                }
            });
        },

        /**
         * 翻转操作
         */
        _applyFlip: function (direction) {
            var self = this;
            var op = direction === 'h' ? { op: 'flip_h' } : { op: 'flip_v' };
            this._applyEdit([op], function (result) {
                if (result.ok) {
                    self._reloadImage(result.path);
                } else {
                    alert('翻转失败: ' + (result.error || '未知错误'));
                }
            });
        },

        /**
         * 滤镜
         */
        _applyFilter: function (filterName) {
            var self = this;
            this._applyEdit([{ op: 'filter', name: filterName }], function (result) {
                if (result.ok) {
                    self._reloadImage(result.path);
                } else {
                    alert('滤镜失败: ' + (result.error || '未知错误'));
                }
            });
        },

        /**
         * 亮度与对比度调整
         */
        _applyBrightnessContrast: function (brightness, contrast) {
            var self = this;
            var ops = [];
            if (brightness !== 1.0) ops.push({ op: 'brightness', factor: brightness });
            if (contrast !== 1.0) ops.push({ op: 'contrast', factor: contrast });
            if (ops.length === 0) return;
            this._applyEdit(ops, function (result) {
                if (result.ok) {
                    self._reloadImage(result.path);
                } else {
                    alert('调整失败: ' + (result.error || '未知错误'));
                }
            });
        },

        /**
         * 自动对比度
         */
        _applyAutoContrast: function () {
            var self = this;
            this._applyEdit([{ op: 'auto_contrast' }], function (result) {
                if (result.ok) {
                    self._reloadImage(result.path);
                } else {
                    alert('自动对比度失败: ' + (result.error || '未知错误'));
                }
            });
        },

        /**
         * 保存（将显示旋转写入文件）
         */
        _saveImage: function () {
            if (this._rotation !== 0) {
                var self = this;
                this._applyEdit([{ op: 'rotate', angle: this._rotation }], function (result) {
                    if (result.ok) {
                        self._config.width = result.width;
                        self._config.height = result.height;
                        self._rotation = 0;
                        self._reloadImage(result.path);
                    }
                });
            }
        },

        /**
         * 重新加载已编辑的图像
         */
        _reloadImage: function (path) {
            var self = this;
            var filePath = path || (this._config.data && this._config.data.file_path);

            if (!global.MMFBBridge || !filePath) return;

            global.MMFBBridge.api.getPreview(filePath).then(function (json) {
                var result = typeof json === 'string' ? JSON.parse(json) : json;
                if (result.error || !result.data) return;

                self._config.data_url = result.data.data_url;
                self._config.width = result.data.width;
                self._config.height = result.data.height;
                self._config.data = result.data;
                self._rotation = 0;
                self._loadImage();
            });
        },

        /**
         * 弹窗选择滤镜
         */
        _showFilterDialog: function () {
            var self = this;
            var filters = [
                { name: 'blur', label: '高斯模糊' },
                { name: 'sharpen', label: '锐化' },
                { name: 'contour', label: '轮廓' },
                { name: 'emboss', label: '浮雕' },
                { name: 'smooth', label: '平滑' },
                { name: 'edge_enhance', label: '边缘增强' }
            ];
            var current = this._root;
            var old = current.querySelector('.image-filter-dialog');
            if (old) old.remove();

            var html = '<div class="image-filter-dialog">';
            for (var i = 0; i < filters.length; i++) {
                html += '<button class="image-filter-dialog__btn" data-filter="' + filters[i].name + '">' +
                    filters[i].label + '</button>';
            }
            html += '<button class="image-filter-dialog__btn image-filter-dialog__btn--cancel">取消</button>';
            html += '</div>';

            var div = document.createElement('div');
            div.innerHTML = html;
            var dlg = div.firstElementChild;
            current.appendChild(dlg);

            var btns = dlg.querySelectorAll('.image-filter-dialog__btn');
            for (var j = 0; j < btns.length; j++) {
                btns[j].addEventListener('click', function (e) {
                    var name = e.target.getAttribute('data-filter');
                    dlg.remove();
                    if (name) self._applyFilter(name);
                });
            }

            setTimeout(function () {
                document.addEventListener('mousedown', function outside(ev) {
                    if (!dlg.contains(ev.target)) {
                        dlg.remove();
                        document.removeEventListener('mousedown', outside);
                    }
                });
            }, 100);
        },

        /**
         * 弹窗调整亮度/对比度
         */
        _showAdjustDialog: function () {
            var self = this;
            var current = this._root;
            var old = current.querySelector('.image-adjust-dialog');
            if (old) old.remove();

            var html =
                '<div class="image-adjust-dialog">' +
                '<div class="image-adjust-dialog__row">' +
                '<label>亮度</label>' +
                '<input type="range" id="adjust-brightness" min="0.2" max="2.0" step="0.05" value="1.0">' +
                '<span class="image-adjust-dialog__val" id="adjust-brightness-val">1.0</span>' +
                '</div>' +
                '<div class="image-adjust-dialog__row">' +
                '<label>对比度</label>' +
                '<input type="range" id="adjust-contrast" min="0.2" max="2.0" step="0.05" value="1.0">' +
                '<span class="image-adjust-dialog__val" id="adjust-contrast-val">1.0</span>' +
                '</div>' +
                '<div class="image-adjust-dialog__actions">' +
                '<button class="image-edit-bar__btn image-edit-bar__btn--primary" id="adjust-auto">自动对比度</button>' +
                '<button class="image-edit-bar__btn" id="adjust-apply">应用</button>' +
                '<button class="image-edit-bar__btn image-filter-dialog__btn--cancel" id="adjust-close">关闭</button>' +
                '</div>' +
                '</div>';

            var div = document.createElement('div');
            div.innerHTML = html;
            var dlg = div.firstElementChild;
            current.appendChild(dlg);

            var bInput = dlg.querySelector('#adjust-brightness');
            var cInput = dlg.querySelector('#adjust-contrast');
            var bVal = dlg.querySelector('#adjust-brightness-val');
            var cVal = dlg.querySelector('#adjust-contrast-val');

            bInput.addEventListener('input', function () { bVal.textContent = bInput.value; });
            cInput.addEventListener('input', function () { cVal.textContent = cInput.value; });

            dlg.querySelector('#adjust-auto').addEventListener('click', function () {
                dlg.remove();
                self._applyAutoContrast();
            });

            dlg.querySelector('#adjust-apply').addEventListener('click', function () {
                var bf = parseFloat(bInput.value);
                var cf = parseFloat(cInput.value);
                dlg.remove();
                self._applyBrightnessContrast(bf, cf);
            });

            dlg.querySelector('#adjust-close').addEventListener('click', function () { dlg.remove(); });

            setTimeout(function () {
                document.addEventListener('mousedown', function outside(ev) {
                    if (!dlg.contains(ev.target)) {
                        dlg.remove();
                        document.removeEventListener('mousedown', outside);
                    }
                });
            }, 100);
        },

        /**
         * 显示/隐藏信息面板
         */
        _toggleInfoPanel: function () {
            var panel = this._root.querySelector('#image-info-panel');
            if (!panel) return;

            if (panel.classList.contains('visible')) {
                panel.classList.remove('visible');
                return;
            }

            var cfg = this._config;
            var rows = [];

            rows.push(['文件', this._escapeHtml(cfg.fileName || '')]);
            rows.push(['尺寸', (cfg.width || 0) + ' x ' + (cfg.height || 0) + ' px']);
            rows.push(['格式', cfg.format || '']);
            rows.push(['色彩模式', cfg.mode || '']);
            rows.push(['文件大小', this._formatSize(cfg.file_size || 0)]);

            if (cfg.is_animated) {
                rows.push(['动画', 'Yes (' + (cfg.frame_count || 1) + ' frames)']);
            }

            if (cfg.exif && Object.keys(cfg.exif).length > 0) {
                rows.push(['---', '---']);
                var exifLabels = {
                    make: '相机厂商', model: '相机型号',
                    datetime: '拍摄时间', datetime_original: '原始时间',
                    exposure_time: '曝光时间', f_number: '光圈',
                    iso: 'ISO', focal_length: '焦距',
                    lens_model: '镜头', orientation: '方向',
                    software: '软件'
                };
                var exifKeys = Object.keys(cfg.exif);
                for (var i = 0; i < exifKeys.length; i++) {
                    var key = exifKeys[i];
                    var label = exifLabels[key] || key;
                    rows.push([label, cfg.exif[key]]);
                }
            }

            var html = '<table class="image-info-table">';
            for (var i = 0; i < rows.length; i++) {
                if (rows[i][0] === '---') {
                    html += '<tr class="image-info-separator"><td colspan="2"></td></tr>';
                } else {
                    html += '<tr><td class="image-info-key">' + rows[i][0] + '</td>' +
                        '<td class="image-info-val">' + this._escapeHtml(String(rows[i][1])) + '</td></tr>';
                }
            }
            html += '</table>';

            panel.innerHTML = html;
            panel.classList.add('visible');
        },

        /**
         * 格式化文件大小
         */
        _formatSize: function (bytes) {
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
            if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
            return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
        },

        /**
         * 绑定工具栏事件
         */
        _bindToolbarEvents: function () {
            var self = this;
            var root = this._root;
            if (!root) return;

            var toggle = root.querySelector('#image-edit-toggle');
            if (toggle) toggle.addEventListener('click', function () { self._toggleEditMode(); });

            var crop = root.querySelector('#image-crop');
            if (crop) crop.addEventListener('click', function () { self._enterCropMode(); });

            var flipH = root.querySelector('#image-flip-h');
            if (flipH) flipH.addEventListener('click', function () { self._applyFlip('h'); });

            var flipV = root.querySelector('#image-flip-v');
            if (flipV) flipV.addEventListener('click', function () { self._applyFlip('v'); });

            var filter = root.querySelector('#image-filter');
            if (filter) filter.addEventListener('click', function () { self._showFilterDialog(); });

            var adjust = root.querySelector('#image-adjust');
            if (adjust) adjust.addEventListener('click', function () { self._showAdjustDialog(); });

            var save = root.querySelector('#image-save');
            if (save) save.addEventListener('click', function () { self._saveImage(); });

            var cropApply = root.querySelector('#image-crop-apply');
            if (cropApply) cropApply.addEventListener('click', function () { self._applyCrop(); });

            var cropCancel = root.querySelector('#image-crop-cancel');
            if (cropCancel) cropCancel.addEventListener('click', function () { self._exitCropMode(); });

            var rotateLeft = root.querySelector('#image-rotate-left');
            if (rotateLeft) rotateLeft.addEventListener('click', function () { self._rotate(-90); });

            var rotateRight = root.querySelector('#image-rotate-right');
            if (rotateRight) rotateRight.addEventListener('click', function () { self._rotate(90); });

            var zoomIn = root.querySelector('#image-zoom-in');
            if (zoomIn) zoomIn.addEventListener('click', function () { self._zoom(1.25); });

            var zoomOut = root.querySelector('#image-zoom-out');
            if (zoomOut) zoomOut.addEventListener('click', function () { self._zoom(0.8); });

            var fit = root.querySelector('#image-fit');
            if (fit) fit.addEventListener('click', function () { self._fitToWindow(); self._render(); });

            var actual = root.querySelector('#image-actual');
            if (actual) actual.addEventListener('click', function () { self._actualSize(); });

            var info = root.querySelector('#image-info');
            if (info) info.addEventListener('click', function () { self._toggleInfoPanel(); });
        },

        /**
         * 绑定滚轮缩放
         */
        _bindWheelEvents: function () {
            var self = this;
            var container = this._root.querySelector('#image-canvas-container');
            if (!container) return;

            container.addEventListener('wheel', function (e) {
                if (self._cropMode) return;
                e.preventDefault();
                var delta = e.deltaY > 0 ? 0.9 : 1.1;
                self._zoom(delta);
            }, { passive: false });
        },

        /**
         * 绑定拖拽平移
         */
        _bindDragEvents: function () {
            var self = this;
            var container = this._root.querySelector('#image-canvas-container');
            if (!container) return;

            container.addEventListener('mousedown', function (e) {
                if (self._cropMode) return;
                self._isDragging = true;
                self._dragStart = { x: e.clientX, y: e.clientY };
                self._scrollStart = { x: container.scrollLeft, y: container.scrollTop };
                container.style.cursor = 'grabbing';
            });

            document.addEventListener('mousemove', function (e) {
                if (!self._isDragging) return;
                var dx = e.clientX - self._dragStart.x;
                var dy = e.clientY - self._dragStart.y;
                container.scrollLeft = self._scrollStart.x - dx;
                container.scrollTop = self._scrollStart.y - dy;
            });

            document.addEventListener('mouseup', function () {
                self._isDragging = false;
                if (container) container.style.cursor = 'grab';
            });
        },

        /**
         * 绑定裁剪事件
         */
        _bindCropEvents: function () {
            var self = this;
            var container = this._root.querySelector('#image-canvas-container');
            if (!container) return;

            container.addEventListener('mousedown', function (e) {
                if (!self._cropMode) return;
                e.preventDefault();

                var rect = self._canvas.getBoundingClientRect();
                self._cropSelecting = true;
                self._cropStart = {
                    x: e.clientX - rect.left,
                    y: e.clientY - rect.top
                };

                var overlay = self._root.querySelector('#image-crop-overlay');
                if (overlay) {
                    var box = overlay.querySelector('.image-crop-box');
                    if (!box) {
                        box = document.createElement('div');
                        box.className = 'image-crop-box';
                        overlay.appendChild(box);
                    }
                    box.style.left = self._cropStart.x + 'px';
                    box.style.top = self._cropStart.y + 'px';
                    box.style.width = '0px';
                    box.style.height = '0px';
                    box.style.display = 'block';
                    var hint = overlay.querySelector('.image-crop-hint');
                    if (hint) hint.style.display = 'none';
                }
            });

            document.addEventListener('mousemove', function (e) {
                if (!self._cropSelecting || !self._cropMode) return;
                var rect = self._canvas.getBoundingClientRect();
                var currentX = e.clientX - rect.left;
                var currentY = e.clientY - rect.top;

                var left = Math.min(self._cropStart.x, currentX);
                var top = Math.min(self._cropStart.y, currentY);
                var right = Math.max(self._cropStart.x, currentX);
                var bottom = Math.max(self._cropStart.y, currentY);

                var canvasW = self._canvas.clientWidth || self._canvas.width;
                var canvasH = self._canvas.clientHeight || self._canvas.height;
                left = Math.max(0, left);
                top = Math.max(0, top);
                right = Math.min(canvasW, right);
                bottom = Math.min(canvasH, bottom);

                var overlay = self._root.querySelector('#image-crop-overlay');
                if (overlay) {
                    var box = overlay.querySelector('.image-crop-box');
                    if (box) {
                        box.style.left = left + 'px';
                        box.style.top = top + 'px';
                        box.style.width = (right - left) + 'px';
                        box.style.height = (bottom - top) + 'px';
                    }
                }

                self._updateCropCoords({ left: left, top: top, right: right, bottom: bottom });
            });

            document.addEventListener('mouseup', function (e) {
                if (!self._cropSelecting || !self._cropMode) return;
                self._cropSelecting = false;

                var rect = self._canvas.getBoundingClientRect();
                var endX = e.clientX - rect.left;
                var endY = e.clientY - rect.top;

                var left = Math.max(0, Math.min(self._cropStart.x, endX));
                var top = Math.max(0, Math.min(self._cropStart.y, endY));
                var right = Math.min(self._canvas.clientWidth || self._canvas.width,
                    Math.max(self._cropStart.x, endX));
                var bottom = Math.min(self._canvas.clientHeight || self._canvas.height,
                    Math.max(self._cropStart.y, endY));

                if (right - left >= 4 && bottom - top >= 4) {
                    self._cropRect = { left: left, top: top, right: right, bottom: bottom };
                } else {
                    self._cropRect = null;
                    var overlay = self._root.querySelector('#image-crop-overlay');
                    if (overlay) {
                        var box = overlay.querySelector('.image-crop-box');
                        if (box) box.style.display = 'none';
                        var hint = overlay.querySelector('.image-crop-hint');
                        if (hint) hint.style.display = '';
                    }
                }
            });
        },

        /**
         * HTML 转义
         */
        _escapeHtml: function (str) {
            var div = document.createElement('div');
            div.appendChild(document.createTextNode(String(str)));
            return div.innerHTML;
        },
    };

    global.MMFBImageViewer = MMFBImageViewer;

})(window);
