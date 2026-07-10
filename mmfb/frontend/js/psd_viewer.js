/**
 * MMFB PSD Viewer
 *
 * 职责：
 *   1. 显示合并预览图（composite）
 *   2. 在侧栏显示图层树（含缩略图、类型、可见性）
 *   3. 点击图层高亮对应图层区域
 *   4. 支持缩放预览图
 *
 * 输入 data 结构（来自 PsdHandler.get_preview().data）：
 *   composite: string  (data:image/png;base64,...)
 *   width: int
 *   height: int
 *   mode: string
 *   layer_count: int
 *   has_smart_object: bool
 *   has_text_layer: bool
 *   layers: Array<{
 *       name, kind, visible, opacity,
 *       width, height, offset_x, offset_y,
 *       thumbnail?, text?, font_names?
 *   }>
 */
(function (global) {
    'use strict';

    /**
     * PSD Viewer 构造函数
     * @param {HTMLElement} root  - 渲染容器
     * @param {Object} data       - preview data
     */
    function MMFBPsdViewer(root, data) {
        this.root = root;
        this.data = data || {};
        this.layers = this.data.layers || [];
        this.scale = 1.0;
        this.selectedLayerIndex = -1;

        this._render();
        this._bindEvents();
    }

    /**
     * 渲染整体布局
     */
    MMFBPsdViewer.prototype._render = function () {
        var self = this;

        var composite = this.data.composite || '';
        var width = this.data.width || 0;
        var height = this.data.height || 0;
        var mode = this.data.mode || '';
        var layerCount = this.data.layer_count || 0;
        var hasSmartObject = this.data.has_smart_object || false;
        var hasTextLayer = this.data.has_text_layer || false;

        // 顶部信息栏
        var topBarHtml =
            '<div class="psd-topbar">' +
            '<div class="psd-topbar__info">' +
            '<span class="psd-topbar__dim">' + width + ' x ' + height + '</span>' +
            '<span class="psd-topbar__mode">' + mode + '</span>' +
            '<span class="psd-topbar__layers">' + layerCount + ' 图层</span>' +
            (hasSmartObject ? '<span class="psd-topbar__tag">智能对象</span>' : '') +
            (hasTextLayer ? '<span class="psd-topbar__tag">文字</span>' : '') +
            '</div>' +
            '<div class="psd-topbar__zoom">' +
            '<button class="psd-topbar__zoom-btn" data-action="zoom-out" title="缩小">-</button>' +
            '<span class="psd-topbar__zoom-level" id="psd-zoom-level">100%</span>' +
            '<button class="psd-topbar__zoom-btn" data-action="zoom-in" title="放大">+</button>' +
            '<button class="psd-topbar__zoom-btn" data-action="zoom-fit" title="适应">↺</button>' +
            '</div>' +
            '</div>';

        // 中间两栏：左侧预览 + 右侧图层
        var mainHtml =
            '<div class="psd-main">' +
            '<div class="psd-canvas-wrap">' +
            (composite
                ? '<div class="psd-canvas" id="psd-canvas">' +
                  '<img src="' + composite + '" class="psd-composite-img" id="psd-composite-img" alt="composite" />' +
                  '</div>'
                : '<div class="psd-no-composite">无法生成预览</div>') +
            '</div>' +
            '<div class="psd-layers-panel">' +
            '<div class="psd-layers-header">图层</div>' +
            '<div class="psd-layers-list" id="psd-layers-list">' +
            this._renderLayerList() +
            '</div>' +
            '</div>' +
            '</div>';

        // 底部图层详情（选中图层后显示）
        var detailHtml =
            '<div class="psd-detail" id="psd-detail"></div>';

        this.root.innerHTML = topBarHtml + mainHtml + detailHtml;
    };

    /**
     * 渲染图层列表
     */
    MMFBPsdViewer.prototype._renderLayerList = function () {
        var html = '';
        for (var i = 0; i < this.layers.length; i++) {
            var layer = this.layers[i];
            var kindClass = 'psd-layer--' + layer.kind;
            var visibleClass = layer.visible ? '' : 'psd-layer--hidden';

            html +=
                '<div class="psd-layer ' + kindClass + ' ' + visibleClass + '" data-layer-index="' + i + '">' +
                (layer.thumbnail
                    ? '<img class="psd-layer__thumb" src="' + layer.thumbnail + '" alt="thumb" />'
                    : '<div class="psd-layer__thumb psd-layer__thumb--none">' + this._kindIcon(layer.kind) + '</div>') +
                '<div class="psd-layer__info">' +
                '<span class="psd-layer__name">' + this._escapeHtml(layer.name || '(未命名)') + '</span>' +
                '<span class="psd-layer__meta">' + this._kindLabel(layer.kind) + ' ' + layer.opacity + '/255</span>' +
                '</div>' +
                '</div>';
        }
        return html;
    };

    /**
     * 绑定事件（缩放按钮、图层点击）
     */
    MMFBPsdViewer.prototype._bindEvents = function () {
        var self = this;

        // 缩放按钮
        var zoomInBtn = this.root.querySelector('[data-action="zoom-in"]');
        var zoomOutBtn = this.root.querySelector('[data-action="zoom-out"]');
        var zoomFitBtn = this.root.querySelector('[data-action="zoom-fit"]');

        if (zoomInBtn) {
            zoomInBtn.addEventListener('click', function () {
                self._zoomBy(1.25);
            });
        }
        if (zoomOutBtn) {
            zoomOutBtn.addEventListener('click', function () {
                self._zoomBy(0.8);
            });
        }
        if (zoomFitBtn) {
            zoomFitBtn.addEventListener('click', function () {
                self._zoomFit();
            });
        }

        // 图层点击
        var listEl = this.root.querySelector('#psd-layers-list');
        if (listEl) {
            listEl.addEventListener('click', function (e) {
                var layerEl = e.target.closest('.psd-layer');
                if (!layerEl) return;
                var idx = parseInt(layerEl.getAttribute('data-layer-index'), 10);
                if (!isNaN(idx)) {
                    self._selectLayer(idx);
                }
            });
        }

        // 滚轮缩放
        var canvasEl = this.root.querySelector('#psd-canvas');
        if (canvasEl) {
            canvasEl.addEventListener('wheel', function (e) {
                if (e.deltaY < 0) {
                    self._zoomBy(1.1);
                } else {
                    self._zoomBy(0.9);
                }
                e.preventDefault();
            }, { passive: false });
        }
    };

    /**
     * 按系数缩放
     */
    MMFBPsdViewer.prototype._zoomBy = function (factor) {
        this.scale *= factor;
        this.scale = Math.max(0.1, Math.min(5, this.scale));
        this._applyZoom();
    };

    /**
     * 适应画布
     */
    MMFBPsdViewer.prototype._zoomFit = function () {
        var canvasEl = this.root.querySelector('#psd-canvas');
        if (!canvasEl) return;
        var wrapEl = canvasEl.parentElement;
        if (!wrapEl) return;
        var wrapW = wrapEl.clientWidth - 40;
        var wrapH = wrapEl.clientHeight - 40;
        var imgW = this.data.width || 1;
        var imgH = this.data.height || 1;
        this.scale = Math.min(wrapW / imgW, wrapH / imgH, 1.0);
        this._applyZoom();
    };

    /**
     * 应用缩放
     */
    MMFBPsdViewer.prototype._applyZoom = function () {
        var img = this.root.querySelector('#psd-composite-img');
        var zoomLevel = this.root.querySelector('#psd-zoom-level');
        if (img) {
            img.style.transform = 'scale(' + this.scale + ')';
            img.style.transformOrigin = '0 0';
        }
        if (zoomLevel) {
            zoomLevel.textContent = Math.round(this.scale * 100) + '%';
        }
    };

    /**
     * 选中图层，高亮显示
     */
    MMFBPsdViewer.prototype._selectLayer = function (idx) {
        this.selectedLayerIndex = idx;

        // 高亮选中的图层
        var layers = this.root.querySelectorAll('.psd-layer');
        for (var i = 0; i < layers.length; i++) {
            if (i === idx) {
                layers[i].classList.add('psd-layer--selected');
            } else {
                layers[i].classList.remove('psd-layer--selected');
            }
        }

        // 显示图层详情
        var detailEl = this.root.querySelector('#psd-detail');
        if (detailEl && idx >= 0 && idx < this.layers.length) {
            var layer = this.layers[idx];
            var html =
                '<div class="psd-detail__header">图层详情</div>' +
                '<div class="psd-detail__row"><span class="psd-detail__label">名称:</span>' +
                    '<span class="psd-detail__value">' + this._escapeHtml(layer.name || '(未命名)') + '</span></div>' +
                '<div class="psd-detail__row"><span class="psd-detail__label">类型:</span>' +
                    '<span class="psd-detail__value">' + this._kindLabel(layer.kind) + '</span></div>' +
                '<div class="psd-detail__row"><span class="psd-detail__label">可见:</span>' +
                    '<span class="psd-detail__value">' + (layer.visible ? '是' : '否') + '</span></div>' +
                '<div class="psd-detail__row"><span class="psd-detail__label">不透明度:</span>' +
                    '<span class="psd-detail__value">' + layer.opacity + ' / 255</span></div>' +
                '<div class="psd-detail__row"><span class="psd-detail__label">尺寸:</span>' +
                    '<span class="psd-detail__value">' + (layer.width || 0) + ' x ' + (layer.height || 0) + '</span></div>' +
                '<div class="psd-detail__row"><span class="psd-detail__label">偏移:</span>' +
                    '<span class="psd-detail__value">(' + (layer.offset_x || 0) + ', ' + (layer.offset_y || 0) + ')</span></div>';

            if (layer.text) {
                html += '<div class="psd-detail__row"><span class="psd-detail__label">文本:</span>' +
                    '<span class="psd-detail__value psd-detail__text">' + this._escapeHtml(layer.text) + '</span></div>';
            }
            if (layer.font_names && layer.font_names.length > 0) {
                html += '<div class="psd-detail__row"><span class="psd-detail__label">字体:</span>' +
                    '<span class="psd-detail__value">' + this._escapeHtml(layer.font_names.join(', ')) + '</span></div>';
            }
            detailEl.innerHTML = html;
        }
    };

    /**
     * 图层类型图标（utf-8 字符）
     */
    MMFBPsdViewer.prototype._kindIcon = function (kind) {
        var icons = {
            pixel: '■',
            group: '▣',
            smartobject: '✦',
            type: 'T',
            shape: '◇',
            other: '·'
        };
        return icons[kind] || '·';
    };

    /**
     * 图层类型中文标签
     */
    MMFBPsdViewer.prototype._kindLabel = function (kind) {
        var labels = {
            pixel: '像素',
            group: '组',
            smartobject: '智能对象',
            type: '文字',
            shape: '形状',
            other: '其他'
        };
        return labels[kind] || kind;
    };

    /**
     * HTML 转义
     */
    MMFBPsdViewer.prototype._escapeHtml = function (text) {
        if (!text) return '';
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    };

    /**
     * 销毁
     */
    MMFBPsdViewer.prototype.destroy = function () {
        this.root.innerHTML = '';
    };

    // 暴露到 global
    global.MMFBPsdViewer = MMFBPsdViewer;

})(window);
