/**
 * MMFB Pptx Viewer - PPT 幻灯片预览
 *
 * 职责：
 *   1. 左侧缩略图列表 + 右侧当前幻灯片预览
 *   2. 幻灯片切换（点击缩略图/上下键/工具栏按钮）
 *   3. 全屏演示模式（F11/Esc）
 *   4. 备注显示
 *   5. 表格、图片、文本混合渲染
 *
 * 依赖：MMFBBridge, MMFBLayout
 */
(function (global) {
    'use strict';

    /**
     * PPTX 查看器构造函数
     * @param {HTMLElement} root - 根容器
     * @param {Object} data - getPreview 返回的 data
     */
    function PptxViewer(root, data) {
        this._root = root;
        this._data = data;
        this._currentIndex = 0;
        this._slides = data && data.slides ? data.slides : [];
        this._slideWidth = data && data.slideWidth ? data.slideWidth : 9144000;
        this._slideHeight = data && data.slideHeight ? data.slideHeight : 5143500;
        this._isFullscreen = false;
        this._slideScale = 1;
        this._fullscreenEl = null;
        this._navHandlers = [];

        this._init();
    }

    PptxViewer.prototype._init = function () {
        this._render();
        this._bindEvents();
        this._updateCounter();
        this._updateFooter();

        // 默认渲染第一张
        this._renderSlide(0);
    };

    /**
     * 渲染主结构
     */
    PptxViewer.prototype._render = function () {
        var slideCount = this._slides.length;
        var fileName = (this._data && this._data.file_name) ? this._data.file_name : 'PPT';
        var fileSize = (this._data && this._data.file_size) ? this._formatSize(this._data.file_size) : '';

        this._root.innerHTML =
            '<div class="pptx-viewer">' +

            // 工具栏
            '<div class="pptx-viewer__toolbar">' +
            '<div class="pptx-toolbar__title" id="pptx-title">' +
            this._escapeHtml(fileName) +
            '<span id="pptx-size" style="font-weight:400;margin-left:8px;color:var(--text-secondary,#888);font-size:11px">' +
            fileSize + '</span>' +
            '</div>' +
            '<div class="pptx-toolbar__nav">' +
            '<button class="pptx-nav__btn" id="pptx-prev" title="上一页 (↑/←)" disabled>&#8593;</button>' +
            '<span class="pptx-nav__info" id="pptx-counter">0 / 0</span>' +
            '<button class="pptx-nav__btn" id="pptx-next" title="下一页 (↓/→)" disabled>&#8595;</button>' +
            '</div>' +
            '<div>' +
            '<button class="pptx-toolbar__btn" id="pptx-notes" title="显示备注">备注</button>' +
            '<button class="pptx-toolbar__btn" id="pptx-fullscreen" title="全屏演示 (F11)">演示</button>' +
            '</div>' +
            '</div>' +

            // 主区域：左侧缩略图 + 右侧预览
            '<div class="pptx-viewer__main">' +

            // 缩略图栏
            '<div class="pptx-viewer__sidebar" id="pptx-sidebar"></div>' +

            // 预览区
            '<div class="pptx-viewer__slide" id="pptx-slide-area">' +
            '<div class="pptx-slide-canvas" id="pptx-canvas"></div>' +
            '</div>' +

            // 备注面板
            '<div class="pptx-viewer__notes" id="pptx-notes-panel">' +
            '<div class="pptx-viewer__notes-label">备注</div>' +
            '<div class="pptx-viewer__notes-text" id="pptx-notes-text"></div>' +
            '</div>' +

            '</div>' +  // end __main

            '</div>';   // end pptx-viewer

        // 更新标题
        if (global.MMFBLayout) {
            global.MMFBLayout.setTitle(fileName);
        }

        this._renderThumbnails();
    };

    /**
     * 渲染缩略图列表
     */
    PptxViewer.prototype._renderThumbnails = function () {
        var sidebar = this._root.querySelector('#pptx-sidebar');
        if (!sidebar) return;

        var html = '';
        for (var i = 0; i < this._slides.length; i++) {
            var slide = this._slides[i];
            var isActive = (i === this._currentIndex);
            var layoutName = slide.layoutName ? this._escapeHtml(slide.layoutName) : '';
            var textPreview = this._getTextPreview(slide, 50);

            html +=
                '<div class="pptx-thumb' + (isActive ? ' active' : '') + '" data-idx="' + i + '">' +
                '<div class="pptx-thumb__label">' + (i + 1) + '</div>' +
                '<div class="pptx-thumb__overlay">' +
                '<div class="pptx-thumb__layout">' + layoutName + '</div>' +
                '<div class="pptx-thumb__text">' + textPreview + '</div>' +
                '</div>' +
                '</div>';
        }

        sidebar.innerHTML = html;

        // 绑定点击
        var self = this;
        var thumbs = sidebar.querySelectorAll('.pptx-thumb');
        for (var j = 0; j < thumbs.length; j++) {
            (function (idx) {
                thumbs[idx].addEventListener('click', function () {
                    self._goTo(idx);
                });
            })(j);
        }
    };

    /**
     * 从幻灯片中提取文字预览
     */
    PptxViewer.prototype._getTextPreview = function (slide, maxLen) {
        var shapes = slide.shapes || [];
        for (var i = 0; i < shapes.length; i++) {
            var s = shapes[i];
            if (s.type === 'text' && s.text) {
                var text = s.text.trim();
                if (text) {
                    return this._escapeHtml(text.substring(0, maxLen) + (text.length > maxLen ? '...' : ''));
                }
            }
        }
        return '';
    };

    /**
     * 绑定交互事件
     */
    PptxViewer.prototype._bindEvents = function () {
        var self = this;

        // 工具栏按钮
        var prevBtn = this._root.querySelector('#pptx-prev');
        var nextBtn = this._root.querySelector('#pptx-next');
        var fsBtn = this._root.querySelector('#pptx-fullscreen');
        var notesBtn = this._root.querySelector('#pptx-notes');

        if (prevBtn) prevBtn.addEventListener('click', function () { self._navigate(-1); });
        if (nextBtn) nextBtn.addEventListener('click', function () { self._navigate(1); });
        if (fsBtn) fsBtn.addEventListener('click', function () { self._enterFullscreen(); });
        if (notesBtn) notesBtn.addEventListener('click', function () { self._toggleNotes(); });

        // 键盘
        var keyHandler = function (e) {
            // 全屏模式
            if (self._isFullscreen) {
                if (e.key === 'Escape' || e.key === 'F11') {
                    self._exitFullscreen();
                    e.preventDefault();
                } else if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === ' ' || e.key === 'PageDown') {
                    self._navigate(1);
                    e.preventDefault();
                } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp' || e.key === 'PageUp') {
                    self._navigate(-1);
                    e.preventDefault();
                }
                return;
            }

            // 普通模式
            if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === 'PageDown') {
                self._navigate(1);
                e.preventDefault();
            } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp' || e.key === 'PageUp') {
                self._navigate(-1);
                e.preventDefault();
            } else if (e.key === 'F11') {
                self._enterFullscreen();
                e.preventDefault();
            }
        };

        document.addEventListener('keydown', keyHandler);
        this._navHandlers.push(function () { document.removeEventListener('keydown', keyHandler); });

        // 全屏点击下一页
        if (this._fullscreenEl) {
            this._fullscreenEl.addEventListener('click', function (e) {
                if (e.target === self._fullscreenEl || e.target.classList.contains('pptx-presentation__slide')) {
                    self._navigate(1);
                }
            });
        }
    };

    /**
     * 渲染指定索引的幻灯片
     */
    PptxViewer.prototype._renderSlide = function (index) {
        var slide = this._slides[index];
        if (!slide) return;

        var canvas = this._root.querySelector('#pptx-canvas');
        if (!canvas) return;

        // 计算缩放：按视口 95% 自适应
        var area = this._root.querySelector('#pptx-slide-area');
        var areaW = area ? area.clientWidth - 32 : 800;
        var areaH = area ? area.clientHeight - 32 : 450;

        var aspectRatio = this._slideWidth / this._slideHeight;
        var scaleX = areaW / this._slideWidth;
        var scaleY = areaH / this._slideHeight;
        this._slideScale = Math.min(scaleX, scaleY, 1);  // 不放大，只缩小

        var cssW = this._slideWidth * this._slideScale;
        var cssH = this._slideHeight * this._slideScale;

        canvas.style.width = cssW + 'px';
        canvas.style.height = cssH + 'px';

        // 渲染形状
        var shapesHtml = '';
        var shapes = slide.shapes || [];
        for (var i = 0; i < shapes.length; i++) {
            shapesHtml += this._renderShape(shapes[i], this._slideScale);
        }

        var images = slide.images || [];
        for (var j = 0; j < images.length; j++) {
            shapesHtml += this._renderShape(images[j], this._slideScale);
        }

        canvas.innerHTML = shapesHtml;

        // 备注
        this._renderNotes(slide);

        // 更新计数器
        this._updateCounter();

        // 高亮当前缩略图
        this._highlightThumb(index);
    };

    /**
     * 渲染单个形状（EMU 坐标转 CSS px）
     */
    PptxViewer.prototype._renderShape = function (shape, scale) {
        if (!shape) return '';

        var left = (shape.left || 0) * scale;
        var top = (shape.top || 0) * scale;
        var w = (shape.width || 0) * scale;
        var h = (shape.height || 0) * scale;

        // 忽略太小/无尺寸的形状
        if (w < 1 || h < 1) return '';

        var style = 'position:absolute;left:' + left.toFixed(1) + 'px;top:' + top.toFixed(1) + 'px;width:' + w.toFixed(1) + 'px;height:' + h.toFixed(1) + 'px;';

        if (shape.type === 'image') {
            if (shape.imageData) {
                var mime = shape.imageMime || 'image/png';
                return '<img class="pptx-slide-canvas__image" src="data:' + mime + ';base64,' + shape.imageData + '" style="' + style + '" alt="">';
            }
            return '';
        }

        if (shape.type === 'table') {
            return this._renderTable(shape, left, top, w, h);
        }

        // 文本/其他形状
        var paragraphs = shape.paragraphs || [];
        var textContent = '';
        if (paragraphs.length > 0) {
            var parasHtml = '';
            for (var i = 0; i < paragraphs.length; i++) {
                parasHtml += this._renderParagraph(paragraphs[i]);
            }
            textContent = parasHtml;
        } else {
            var rawText = shape.text || '';
            if (rawText) {
                // 简单处理：换行转 <br>
                textContent = '<p class="pptx-para">' + this._escapeHtml(rawText).replace(/\n/g, '<br>') + '</p>';
            }
        }

        if (!textContent) {
            // 纯形状无文本
            return '<div class="pptx-slide-canvas__shape" style="' + style + '"></div>';
        }

        return '<div class="pptx-slide-canvas__text" style="' + style + '">' + textContent + '</div>';
    };

    /**
     * 渲染段落（含 run 级别样式）
     */
    PptxViewer.prototype._renderParagraph = function (para) {
        if (!para) return '<p class="pptx-para">&nbsp;</p>';

        var runs = para.runs || [];
        var html = '';

        if (runs.length > 0) {
            for (var i = 0; i < runs.length; i++) {
                var run = runs[i];
                var text = this._escapeHtml(run.text || '');
                if (!text) continue;

                var styles = [];
                if (run.bold) text = '<strong>' + text + '</strong>';
                if (run.italic) text = '<em>' + text + '</em>';
                if (run.underline) text = '<u>' + text + '</u>';
                if (run.color) styles.push('color:#' + String(run.color).replace(/^#/, ''));
                if (run.sizePt) styles.push('font-size:' + run.sizePt + 'pt');
                if (run.fontName) styles.push('font-family:' + run.fontName + ',sans-serif');

                if (styles.length > 0) {
                    text = '<span style="' + styles.join(';') + '">' + text + '</span>';
                }

                html += text;
            }
        } else {
            html = this._escapeHtml(para.text || '');
        }

        return '<p class="pptx-para">' + html + '</p>';
    };

    /**
     * 渲染表格
     */
    PptxViewer.prototype._renderTable = function (shape, left, top, w, h) {
        var rows = shape.rows || [];
        if (rows.length === 0) return '';

        var cellsHtml = '';
        for (var r = 0; r < rows.length; r++) {
            cellsHtml += '<tr>';
            for (var c = 0; c < rows[r].length; c++) {
                cellsHtml += '<td>' + this._escapeHtml(rows[r][c]) + '</td>';
            }
            cellsHtml += '</tr>';
        }

        return '<div class="pptx-slide-canvas__shape" ' +
            'style="position:absolute;left:' + left.toFixed(1) + 'px;top:' + top.toFixed(1) + 'px;' +
            'width:' + w.toFixed(1) + 'px;height:' + h.toFixed(1) + 'px;overflow:auto;">' +
            '<table class="pptx-slide-canvas__table">' + cellsHtml + '</table>' +
            '</div>';
    };

    /**
     * 渲染备注
     */
    PptxViewer.prototype._renderNotes = function (slide) {
        var el = this._root.querySelector('#pptx-notes-text');
        if (!el) return;

        var notes = slide && slide.notes ? slide.notes : '';
        if (notes) {
            el.textContent = notes;
        } else {
            el.innerHTML = '<em style="color:var(--text-secondary,#888)">无备注</em>';
        }
    };

    /**
     * 更新计数器
     */
    PptxViewer.prototype._updateCounter = function () {
        var counter = this._root.querySelector('#pptx-counter');
        if (counter) {
            counter.textContent = (this._currentIndex + 1) + ' / ' + this._slides.length;
        }

        var prevBtn = this._root.querySelector('#pptx-prev');
        var nextBtn = this._root.querySelector('#pptx-next');
        if (prevBtn) prevBtn.disabled = this._currentIndex <= 0;
        if (nextBtn) nextBtn.disabled = this._currentIndex >= this._slides.length - 1;
    };

    /**
     * 更新底栏
     */
    PptxViewer.prototype._updateFooter = function () {
        if (global.MMFBLayout) {
            var sizeStr = this._data && this._data.file_size ? this._formatSize(this._data.file_size) : '';
            global.MMFBLayout.setFooterLeft('PPTX | ' + this._slides.length + ' 页 | ' + sizeStr);
        }
    };

    /**
     * 切换备注面板
     */
    PptxViewer.prototype._toggleNotes = function () {
        var panel = this._root.querySelector('#pptx-notes-panel');
        if (panel) {
            panel.classList.toggle('visible');
        }
    };

    /**
     * 进入全屏演示
     */
    PptxViewer.prototype._enterFullscreen = function () {
        if (this._isFullscreen) return;
        this._isFullscreen = true;

        var slide = this._slides[this._currentIndex];
        var slideW = this._slideWidth;
        var slideH = this._slideHeight;

        // 容器尺寸
        var winW = window.innerWidth;
        var winH = window.innerHeight;
        var scale = Math.min(winW / slideW, winH / slideH, 1);
        var cssW = slideW * scale;
        var cssH = slideH * scale;

        var fsHtml =
            '<div class="pptx-presentation" id="pptx-fs">' +
            '<div class="pptx-presentation__slide" id="pptx-fs-slide" ' +
            'style="width:' + cssW + 'px;height:' + cssH + 'px;">' +
            '</div>' +
            '<div class="pptx-presentation__controls">' +
            '<button class="pptx-presentation__btn" id="pptx-fs-prev">&#8593; 上一页</button>' +
            '<div class="pptx-presentation__progress">' +
            '<div class="pptx-presentation__progress-bar" id="pptx-fs-progress" ' +
            'style="width:' + ((this._currentIndex + 1) / this._slides.length * 100) + '%"></div>' +
            '</div>' +
            '<span id="pptx-fs-info">' + (this._currentIndex + 1) + ' / ' + this._slides.length + '</span>' +
            '<button class="pptx-presentation__btn" id="pptx-fs-next">下一页 &#8595;</button>' +
            '<button class="pptx-presentation__btn" id="pptx-fs-exit">退出 (Esc)</button>' +
            '</div>' +
            '</div>';

        document.body.insertAdjacentHTML('beforeend', fsHtml);

        this._fullscreenEl = document.getElementById('pptx-fs');
        this._renderFullscreenSlide(slide, scale);

        // 绑定控制按钮
        var self = this;
        var fsPrev = document.getElementById('pptx-fs-prev');
        var fsNext = document.getElementById('pptx-fs-next');
        var fsExit = document.getElementById('pptx-fs-exit');

        if (fsPrev) fsPrev.addEventListener('click', function (e) { e.stopPropagation(); self._navigate(-1); });
        if (fsNext) fsNext.addEventListener('click', function (e) { e.stopPropagation(); self._navigate(1); });
        if (fsExit) fsExit.addEventListener('click', function (e) { e.stopPropagation(); self._exitFullscreen(); });
    };

    /**
     * 渲染全屏幻灯片内容
     */
    PptxViewer.prototype._renderFullscreenSlide = function (slide, scale) {
        var container = document.getElementById('pptx-fs-slide');
        if (!container) return;

        var shapesHtml = '';
        var shapes = slide.shapes || [];
        for (var i = 0; i < shapes.length; i++) {
            shapesHtml += this._renderShape(shapes[i], scale);
        }

        var images = slide.images || [];
        for (var j = 0; j < images.length; j++) {
            shapesHtml += this._renderShape(images[j], scale);
        }

        container.innerHTML = shapesHtml;
    };

    /**
     * 退出全屏演示
     */
    PptxViewer.prototype._exitFullscreen = function () {
        if (!this._isFullscreen) return;
        this._isFullscreen = false;

        if (this._fullscreenEl) {
            this._fullscreenEl.remove();
            this._fullscreenEl = null;
        }

        // 重新渲染当前幻灯片（非全屏）
        this._renderSlide(this._currentIndex);
    };

    /**
     * 导航到指定幻灯片
     */
    PptxViewer.prototype._navigate = function (delta) {
        var newIdx = this._currentIndex + delta;
        if (newIdx < 0 || newIdx >= this._slides.length) return;

        if (this._isFullscreen) {
            this._currentIndex = newIdx;
            var slide = this._slides[newIdx];
            var winW = window.innerWidth;
            var winH = window.innerHeight;
            var scale = Math.min(winW / this._slideWidth, winH / this._slideHeight, 1);
            var cssW = this._slideWidth * scale;
            var cssH = this._slideHeight * scale;

            var fsSlide = document.getElementById('pptx-fs-slide');
            if (fsSlide) {
                fsSlide.style.width = cssW + 'px';
                fsSlide.style.height = cssH + 'px';
            }

            this._renderFullscreenSlide(slide, scale);

            // 更新进度条
            var progress = document.getElementById('pptx-fs-progress');
            if (progress) progress.style.width = ((newIdx + 1) / this._slides.length * 100) + '%';
            var info = document.getElementById('pptx-fs-info');
            if (info) info.textContent = (newIdx + 1) + ' / ' + this._slides.length;
        } else {
            this._goTo(newIdx);
        }
    };

    /**
     * 跳转并更新视图
     */
    PptxViewer.prototype._goTo = function (index) {
        if (index === this._currentIndex) return;
        this._currentIndex = index;
        this._renderThumbnails();
        this._renderSlide(index);
    };

    /**
     * 高亮当前缩略图
     */
    PptxViewer.prototype._highlightThumb = function (index) {
        var sidebar = this._root.querySelector('#pptx-sidebar');
        if (!sidebar) return;

        var thumbs = sidebar.querySelectorAll('.pptx-thumb');
        for (var i = 0; i < thumbs.length; i++) {
            thumbs[i].classList.toggle('active', i === index);
        }

        // 滚动到可见
        var activeThumb = sidebar.querySelector('.pptx-thumb.active');
        if (activeThumb) {
            activeThumb.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    };

    /**
     * HTML 转义
     */
    PptxViewer.prototype._escapeHtml = function (str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&')
            .replace(/</g, '<')
            .replace(/>/g, '>')
            .replace(/"/g, '"')
            .replace(/'/g, '&#39;');
    };

    /**
     * 文件大小格式化
     */
    PptxViewer.prototype._formatSize = function (bytes) {
        if (!bytes || bytes < 1024) return (bytes || 0) + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
    };

    /**
     * 销毁
     */
    PptxViewer.prototype.destroy = function () {
        if (this._isFullscreen) {
            this._exitFullscreen();
        }

        for (var i = 0; i < this._navHandlers.length; i++) {
            try { this._navHandlers[i](); } catch (e) {}
        }

        this._root.innerHTML = '';
        this._root = null;
        this._slides = [];
        this._data = null;
    };

    // 暴露到全局
    global.MMFBPptxViewer = PptxViewer;

})(window);