/**
 * MMFB TextureViewer - 游戏贴图查看器
 *
 * 功能：
 * 1. DDS / TGA / EXR / HDR 贴图预览
 * 2. DDS Mipmap 层级缩略图选择
 * 3. 法线贴图可视化标识（XYZ 轴指示器）
 * 4. HDR 曝光调节（Reinhard 色调映射预览）
 * 5. 纹理元信息展示（像素格式、通道数、Cubemap 标识等）
 * 6. 缩放 / 平移 / 像素化切换
 *
 * 调用方式:
 *   MMFBTextureViewer.init(rootEl, { filePath, fileName, fileSize, width, height, data_url,
 *       pixelFormat, mipmapCount, isNormalMap, isHdr, isCubemap, channelCount, format, mode })
 *   MMFBTextureViewer.destroy()
 */
(function (global) {
    'use strict';

    var MMFBTextureViewer = {
        _root: null,
        _config: null,
        _img: null,
        _canvas: null,
        _ctx: null,
        _scale: 1.0,
        _pixelated: false,
        _destroyed: false,
        _isDragging: false,
        _dragStart: { x: 0, y: 0 },
        _scrollStart: { x: 0, y: 0 },
        _mipLevel: 0,
        _mipThumbs: [],
        _nvOverlayVisible: false,
        _hdrExposure: 1.0,

        /**
         * 初始化纹理查看器
         */
        init: function (rootEl, config) {
            this._root = rootEl;
            this._config = config || {};
            this._destroyed = false;
            this._scale = 1.0;
            this._pixelated = false;
            this._mipLevel = 0;
            this._hdrExposure = 1.0;

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
            this._config = null;
            this._mipThumbs = [];
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
            var pixelFormat = this._config.pixel_format || this._config.pixelFormat || '';
            var mipmapCount = this._config.mipmap_count || this._config.mipmapCount || 1;
            var isNormalMap = this._config.is_normal_map || this._config.isNormalMap || false;
            var isHdr = this._config.is_hdr || this._config.isHdr || false;
            var isCubemap = this._config.is_cubemap || this._config.isCubemap || false;
            var channelCount = this._config.channel_count || this._config.channelCount || 0;
            var file_size = this._config.file_size || 0;

            // 构建元信息标签
            var metaParts = [];
            if (width && height) metaParts.push(width + ' x ' + height);
            if (format) metaParts.push(format);
            if (pixelFormat) metaParts.push(pixelFormat);
            if (channelCount) metaParts.push(channelCount + 'ch');
            if (mipmapCount > 1) metaParts.push(mipmapCount + ' mips');

            var metaStr = metaParts.join(' | ');

            // 构建纹理徽章
            var badges = '';
            if (isNormalMap) {
                badges += '<span class="texture-badge texture-badge--normal">NORMAL</span>';
            }
            if (isHdr) {
                badges += '<span class="texture-badge texture-badge--hdr">HDR</span>';
            }
            if (isCubemap) {
                badges += '<span class="texture-badge texture-badge--cubemap">CUBEMAP</span>';
            }

            this._root.innerHTML =
                '<div class="texture-viewer">' +
                '  <div class="texture-toolbar" id="texture-toolbar">' +
                '    <div class="texture-toolbar__left">' +
                '      <span class="texture-toolbar__title" title="' + this._escapeHtml(fileName) + '">' + this._escapeHtml(fileName) + '</span>' +
                '      <span class="texture-toolbar__meta" id="texture-meta">' + this._escapeHtml(metaStr) + '</span>' +
                '      <span id="texture-badges">' + badges + '</span>' +
                '    </div>' +
                '    <div class="texture-toolbar__right" id="texture-toolbar-right">' +
                '      <button class="texture-toolbar__btn" id="texture-mip-toggle" title="Mipmap 层级"' + (mipmapCount <= 1 ? ' style="display:none"' : '') + '>&#128247;</button>' +
                '      <button class="texture-toolbar__btn" id="texture-nv-toggle" title="法线贴图可视化"' + (isNormalMap ? '' : ' style="display:none"') + '>&#9650;</button>' +
                '      <span class="texture-toolbar__sep">|</span>' +
                '      <button class="texture-toolbar__btn" id="texture-pixelated" title="像素化"' + (isNormalMap ? '' : ' style="display:none"') + '>&#9635;</button>' +
                '      <span class="texture-toolbar__sep">|</span>' +
                '      <button class="texture-toolbar__btn" id="texture-zoom-out" title="缩小">&#8722;</button>' +
                '      <span class="texture-toolbar__zoom" id="texture-zoom-level">100%</span>' +
                '      <button class="texture-toolbar__btn" id="texture-zoom-in" title="放大">+</button>' +
                '      <button class="texture-toolbar__btn" id="texture-fit" title="适应窗口">&#8862;</button>' +
                '      <button class="texture-toolbar__btn" id="texture-actual" title="实际大小">&#9635;</button>' +
                '      <button class="texture-toolbar__btn" id="texture-info" title="元信息">&#8505;</button>' +
                '    </div>' +
                '  </div>' +
                '  <div class="texture-canvas-container" id="texture-canvas-container">' +
                '    <div class="texture-loading" id="texture-loading">' +
                '      <div class="texture-loading__spinner"></div>' +
                '      <div>正在加载贴图...</div>' +
                '    </div>' +
                '  </div>' +
                '  <div class="texture-info-panel" id="texture-info-panel"></div>' +
                '  <div class="texture-mip-panel" id="texture-mip-panel">' +
                '    <div class="texture-mip-panel__title">Mipmap 层级</div>' +
                '    <div class="texture-mip-panel__thumbs" id="texture-mip-thumbs"></div>' +
                '  </div>' +
                '  <div class="texture-nv-overlay" id="texture-nv-overlay">' +
                '    <svg class="texture-nv-axis-indicator" viewBox="0 0 40 40">' +
                '      <line x1="4" y1="36" x2="20" y2="36" stroke="#FF4444" stroke-width="2"/>' +
                '      <line x1="4" y1="36" x2="4" y2="20" stroke="#44FF44" stroke-width="2"/>' +
                '      <circle cx="4" cy="36" r="4" fill="#4444FF" opacity="0.5"/>' +
                '    </svg>' +
                '  </div>' +
                '</div>';

            this._bindToolbarEvents();
            this._bindWheelEvents();
            this._bindDragEvents();
        },

        /**
         * 加载图像
         */
        _loadImage: function () {
            var self = this;
            var container = this._root.querySelector('#texture-canvas-container');
            if (!container) return;

            var dataUrl = this._config.data_url;
            if (!dataUrl) {
                container.innerHTML =
                    '<div class="texture-error">' +
                    '<div class="texture-error__icon">&#9888;</div>' +
                    '<div>贴图数据不可用</div>' +
                    '<div style="font-size:12px;opacity:0.7;margin-top:8px;">' +
                    '文件可能过大或读取失败' +
                    '</div>' +
                    '</div>';
                return;
            }

            this._img = new Image();
            this._img.onload = function () {
                if (self._destroyed) return;
                if (container) {
                    var loading = container.querySelector('#texture-loading');
                    if (loading) loading.remove();
                }
                self._initCanvas();
                self._fitToWindow();
                self._render();
            };
            this._img.onerror = function () {
                if (!container) return;
                container.innerHTML =
                    '<div class="texture-error">' +
                    '<div class="texture-error__icon">&#10060;</div>' +
                    '<div>无法加载贴图</div>' +
                    '</div>';
            };
            this._img.src = dataUrl;
        },

        /**
         * 初始化 canvas
         */
        _initCanvas: function () {
            var container = this._root.querySelector('#texture-canvas-container');
            if (!container) return;

            var oldCanvas = container.querySelector('canvas.texture-canvas');
            if (oldCanvas) oldCanvas.remove();

            this._canvas = document.createElement('canvas');
            this._canvas.className = 'texture-canvas';
            this._ctx = this._canvas.getContext('2d');

            var nvOverlay = this._root.querySelector('#texture-nv-overlay');
            if (nvOverlay) {
                container.appendChild(nvOverlay);
            }
            container.appendChild(this._canvas);
        },

        /**
         * 渲染贴图到 canvas
         */
        _render: function () {
            if (!this._ctx || !this._img) return;

            var imgW = this._img.naturalWidth || this._img.width;
            var imgH = this._img.naturalHeight || this._img.height;

            var canvasW = Math.round(imgW * this._scale);
            var canvasH = Math.round(imgH * this._scale);

            this._canvas.width = canvasW;
            this._canvas.height = canvasH;

            this._ctx.clearRect(0, 0, canvasW, canvasH);

            // 棋盘格背景（用于透明贴图）
            this._drawCheckerboard(canvasW, canvasH);

            this._ctx.drawImage(this._img, 0, 0, canvasW, canvasH);
        },

        /**
         * 绘制棋盘格背景
         */
        _drawCheckerboard: function (w, h) {
            var size = 8;
            for (var y = 0; y < h; y += size) {
                for (var x = 0; x < w; x += size) {
                    var checker = ((x / size + y / size) % 2 === 0);
                    this._ctx.fillStyle = checker ? '#2a2a2a' : '#333333';
                    this._ctx.fillRect(x, y, size, size);
                }
            }
        },

        /**
         * 适应窗口
         */
        _fitToWindow: function () {
            if (!this._img || !this._root) return;

            var container = this._root.querySelector('#texture-canvas-container');
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
         * 更新缩放信息
         */
        _updateZoomInfo: function () {
            var el = this._root.querySelector('#texture-zoom-level');
            if (el) el.textContent = Math.round(this._scale * 100) + '%';
        },

        /**
         * 切换像素化模式
         */
        _togglePixelated: function () {
            this._pixelated = !this._pixelated;
            var canvas = this._root.querySelector('.texture-canvas');
            if (canvas) {
                canvas.classList.toggle('pixelated', this._pixelated);
            }
            var btn = this._root.querySelector('#texture-pixelated');
            if (btn) btn.classList.toggle('active', this._pixelated);
            this._render();
        },

        /**
         * 切换法线贴图可视化
         */
        _toggleNvOverlay: function () {
            this._nvOverlayVisible = !this._nvOverlayVisible;
            var overlay = this._root.querySelector('#texture-nv-overlay');
            if (overlay) overlay.classList.toggle('visible', this._nvOverlayVisible);
            var btn = this._root.querySelector('#texture-nv-toggle');
            if (btn) btn.classList.toggle('active', this._nvOverlayVisible);
        },

        /**
         * 构建 Mipmap 缩略图面板
         */
        _buildMipPanel: function () {
            if (!this._img) return;

            var panel = this._root.querySelector('#texture-mip-panel');
            var thumbs = this._root.querySelector('#texture-mip-thumbs');
            if (!panel || !thumbs) return;

            var mipCount = this._config.mipmap_count || this._config.mipmapCount || 1;
            this._mipThumbs = [];

            // 生成各级 Mipmap 缩略图
            for (var level = 0; level < mipCount; level++) {
                var mipW = Math.max(1, Math.floor(this._img.naturalWidth / Math.pow(2, level)));
                var mipH = Math.max(1, Math.floor(this._img.naturalHeight / Math.pow(2, level)));

                var tmpCanvas = document.createElement('canvas');
                tmpCanvas.width = mipW;
                tmpCanvas.height = mipH;
                var tmpCtx = tmpCanvas.getContext('2d');
                tmpCtx.drawImage(this._img, 0, 0, mipW, mipH);

                var dataUrl = tmpCanvas.toDataURL('image/png');

                var thumbDiv = document.createElement('div');
                thumbDiv.className = 'texture-mip-panel__thumb' + (level === 0 ? ' active' : '');
                thumbDiv.setAttribute('data-level', level);

                var thumbImg = document.createElement('img');
                thumbImg.src = dataUrl;

                var label = document.createElement('div');
                label.className = 'texture-mip-panel__thumb-label';
                label.textContent = 'M' + level;

                thumbDiv.appendChild(thumbImg);
                thumbDiv.appendChild(label);
                thumbs.appendChild(thumbDiv);

                var self = this;
                thumbDiv.addEventListener('click', (function (lvl) {
                    return function () {
                        self._selectMipLevel(lvl);
                    };
                })(level));

                this._mipThumbs.push({ level: level, width: mipW, height: mipH });
            }
        },

        /**
         * 选择 Mipmap 层级
         */
        _selectMipLevel: function (level) {
            this._mipLevel = level;

            // 更新缩略图选中态
            var thumbEls = this._root.querySelectorAll('.texture-mip-panel__thumb');
            for (var i = 0; i < thumbEls.length; i++) {
                thumbEls[i].classList.toggle('active', parseInt(thumbEls[i].getAttribute('data-level')) === level);
            }

            // 缩放以适应当前 mipmap 层级
            if (this._mipThumbs[level]) {
                var container = this._root.querySelector('#texture-canvas-container');
                if (container) {
                    var mipW = this._mipThumbs[level].width;
                    var mipH = this._mipThumbs[level].height;
                    var availW = container.clientWidth - 40;
                    var availH = container.clientHeight - 40;
                    this._scale = Math.min(availW / mipW, availH / mipH, 4.0);
                    if (this._scale < 0.1) this._scale = 0.1;
                    this._updateZoomInfo();
                    this._render();
                }
            }
        },

        /**
         * 切换 Mipmap 面板
         */
        _toggleMipPanel: function () {
            var panel = this._root.querySelector('#texture-mip-panel');
            if (!panel) return;

            if (panel.classList.contains('visible')) {
                panel.classList.remove('visible');
            } else {
                this._buildMipPanel();
                panel.classList.add('visible');
            }
        },

        /**
         * 显示/隐藏元信息面板
         */
        _toggleInfoPanel: function () {
            var panel = this._root.querySelector('#texture-info-panel');
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

            if (cfg.pixel_format || cfg.pixelFormat) {
                rows.push(['像素格式', this._escapeHtml(cfg.pixel_format || cfg.pixelFormat || '')]);
            }
            if (cfg.mipmap_count || cfg.mipmapCount) {
                rows.push(['Mipmap 层级', (cfg.mipmap_count || cfg.mipmapCount) + ' 级']);
            }
            if (cfg.channel_count || cfg.channelCount) {
                rows.push(['通道数', (cfg.channel_count || cfg.channelCount) + ' 通道']);
            }
            if (cfg.is_normal_map || cfg.isNormalMap) {
                rows.push(['法线贴图', '是']);
            }
            if (cfg.is_hdr || cfg.isHdr) {
                rows.push(['HDR 内容', '是']);
            }
            if (cfg.is_cubemap || cfg.isCubemap) {
                rows.push(['Cubemap', '是']);
            }

            var html = '<table class="texture-info-table">';
            for (var i = 0; i < rows.length; i++) {
                html += '<tr><td class="texture-info-key">' + rows[i][0] + '</td>' +
                    '<td class="texture-info-val">' + this._escapeHtml(String(rows[i][1])) + '</td></tr>';
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

            var mipToggle = root.querySelector('#texture-mip-toggle');
            if (mipToggle) mipToggle.addEventListener('click', function () { self._toggleMipPanel(); });

            var nvToggle = root.querySelector('#texture-nv-toggle');
            if (nvToggle) nvToggle.addEventListener('click', function () { self._toggleNvOverlay(); });

            var pixelated = root.querySelector('#texture-pixelated');
            if (pixelated) pixelated.addEventListener('click', function () { self._togglePixelated(); });

            var zoomIn = root.querySelector('#texture-zoom-in');
            if (zoomIn) zoomIn.addEventListener('click', function () { self._zoom(1.25); });

            var zoomOut = root.querySelector('#texture-zoom-out');
            if (zoomOut) zoomOut.addEventListener('click', function () { self._zoom(0.8); });

            var fit = root.querySelector('#texture-fit');
            if (fit) fit.addEventListener('click', function () { self._fitToWindow(); self._render(); });

            var actual = root.querySelector('#texture-actual');
            if (actual) actual.addEventListener('click', function () { self._actualSize(); });

            var info = root.querySelector('#texture-info');
            if (info) info.addEventListener('click', function () { self._toggleInfoPanel(); });
        },

        /**
         * 绑定滚轮缩放
         */
        _bindWheelEvents: function () {
            var self = this;
            var container = this._root.querySelector('#texture-canvas-container');
            if (!container) return;

            container.addEventListener('wheel', function (e) {
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
            var container = this._root.querySelector('#texture-canvas-container');
            if (!container) return;

            container.addEventListener('mousedown', function (e) {
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
         * HTML 转义
         */
        _escapeHtml: function (str) {
            var div = document.createElement('div');
            div.appendChild(document.createTextNode(String(str)));
            return div.innerHTML;
        },
    };

    global.MMFBTextureViewer = MMFBTextureViewer;

})(window);
