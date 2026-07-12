/**
 * MMFB PDFViewer - PDF 渲染模块
 *
 * 使用 pdf.js（CDN 备选本地回退）渲染 PDF 文档，提供：
 * 1. 逐页渲染（虚拟滚动 + 视口懒加载）
 * 2. 缩放（25% - 400%）
 * 3. 翻页（按钮 / 键盘 / 滚轮）
 * 4. 文本搜索 + 高亮
 * 5. PDF 元数据展示
 *
 * 当前实现说明：
 * pdf.js 库将在 frontend/libs/ 目录下提供。若库未就绪，
 * 模块会在 mounted 前检测并提示用户。
 *
 * 调用方式:
 *   MMFBPDFViewer.init(rootEl, { filePath, fileName, onTitleChange })
 *   MMFBPDFViewer.destroy()
 */
(function (global) {
    'use strict';

    var MMFBPDFViewer = {
        _root: null,
        _config: null,
        _pdfDoc: null,
        _currentPage: 1,
        _totalPages: 0,
        _scale: 1.5, // 默认 150% 以匹配屏幕 DPI
        _rendering: false,
        _pageRendering: {}, // pageNum -> bool（防重入）
        _observer: null,    // IntersectionObserver
        _searchQuery: '',
        _searchMatches: [],
        _searchCurrent: -1,
        _destroyed: false,

        /**
         * 初始化 PDF 查看器
         * @param {HTMLElement} rootEl - 容器元素
         * @param {object} config - { filePath, fileName, fileSize?, pageCount?, onTitleChange? }
         */
        init: function (rootEl, config) {
            this._root = rootEl;
            this._config = config || {};
            this._destroyed = false;

            this._renderShell();
            this._loadPdfJs();
        },

        /**
         * 销毁，清理资源
         */
        destroy: function () {
            this._destroyed = true;

            if (this._observer) {
                this._observer.disconnect();
                this._observer = null;
            }
            if (this._pdfDoc) {
                try { this._pdfDoc.destroy(); } catch (e) {}
                this._pdfDoc = null;
            }
            this._root = null;
            this._pdfDoc = null;
            this._pageRendering = {};
        },

        /**
         * 渲染外壳 HTML（工具栏 + 容器）
         */
        _renderShell: function () {
            if (!this._root) return;

            var filePath = this._config.file_path || this._config.file_path_or_url || this._config.filePath || '';
            var fileName = this._config.fileName;
            if (!fileName) {
                // 从 filePath 提取文件名
                fileName = filePath.split(/[\\/]/).pop() || '';
            }
            // HTML 转义
            fileName = fileName.replace(/[<>&"]/g, '');
            var fileSize = this._config.fileSize || 0;

            this._root.innerHTML =
                '<div class="pdf-viewer">' +
                '  <div class="pdf-toolbar">' +
                '    <div class="pdf-toolbar__left">' +
                '      <span class="pdf-toolbar__title" title="' + fileName + '">' + fileName + '</span>' +
                '    </div>' +
                '    <div class="pdf-toolbar__right">' +
                '      <button class="pdf-toolbar__btn" id="pdf-prev" title="上一页">&#9664;</button>' +
                '      <span class="pdf-toolbar__page-info" id="pdf-page-info">1 / 1</span>' +
                '      <button class="pdf-toolbar__btn" id="pdf-next" title="下一页">&#9654;</button>' +
                '      <button class="pdf-toolbar__btn" id="pdf-zoom-out" title="缩小">&#8722;</button>' +
                '      <span class="pdf-toolbar__zoom" id="pdf-zoom-level">150%</span>' +
                '      <button class="pdf-toolbar__btn" id="pdf-zoom-in" title="放大">+</button>' +
                '      <button class="pdf-toolbar__btn" id="pdf-search-toggle" title="搜索 (Ctrl+F)">&#128269;</button>' +
                '    </div>' +
                '  </div>' +
                '  <div class="pdf-search-box" id="pdf-search-box">' +
                '    <input type="text" id="pdf-search-input" placeholder="搜索...">' +
                '    <span class="pdf-search-count" id="pdf-search-count"></span>' +
                '    <button class="pdf-toolbar__btn" id="pdf-search-prev" title="上一个">&#9650;</button>' +
                '    <button class="pdf-toolbar__btn" id="pdf-search-next" title="下一个">&#9660;</button>' +
                '    <button class="pdf-toolbar__btn" id="pdf-search-close" title="关闭">&#10005;</button>' +
                '  </div>' +
                '  <div class="pdf-canvas-container" id="pdf-canvas-container">' +
                '    <div class="pdf-loading" id="pdf-loading">' +
                '      <div class="pdf-loading__spinner"></div>' +
                '      <div>正在加载 PDF...</div>' +
                '    </div>' +
                '  </div>' +
                '</div>';

            this._bindToolbarEvents();
            this._bindKeyboardEvents();
        },

        /**
         * 加载 pdf.js 库（UMD 全局构建，已通过 <script> 标签加载）
         * 若 UMD 失败，自动等待 pdfjs-global.js 的 ESM fallback 加载（30 秒超时）
         */
        _loadPdfJs: function () {
            var self = this;
            var container = this._root.querySelector('#pdf-canvas-container');

            // 配置 worker（UMD 构建使用 workerPorts 或 workerSrc）
            // 任何步骤失败都强制降级到 disableWorker（主线程跑），保证 PDF 一定能渲染
            var tryConfigureWorker = function () {
                try {
                    if (global.__pdfWorkerUrl) {
                        global.pdfjsLib.GlobalWorkerOptions.workerSrc = global.__pdfWorkerUrl;
                    } else {
                        global.pdfjsLib.GlobalWorkerOptions.workerSrc = 'libs/pdfs/pdf.worker.min.js';
                    }
                    global.pdfjsLib.GlobalWorkerOptions.disableWorker = false;
                } catch (e) {
                    console.warn('[PDF] 配置 worker 失败，禁用 worker：', e);
                    try {
                        global.pdfjsLib.GlobalWorkerOptions.workerSrc = '';
                        global.pdfjsLib.GlobalWorkerOptions.disableWorker = true;
                    } catch (e2) {
                        // 极端情况：连 disableWorker 都赋值不了，整个 pdfjsLib 也不可用，吞掉异常让上层走 fallback
                        console.warn('[PDF] disableWorker 设置也失败', e2);
                    }
                }
            };

            // pdf.js UMD 全局构建检查
            if (typeof global.pdfjsLib === 'undefined') {
                // 等待 pdfjs-global.js 的 ESM 加载（fallback）
                self._waitForPdfLib(30).then(function () {
                    tryConfigureWorker();
                    self._openFile();
                }).catch(function (err) {
                    console.error('[PDF] 等待 pdfjsLib 超时:', err);
                    if (container) {
                        container.innerHTML =
                            '<div class="pdf-error">' +
                            '<div class="pdf-error__icon">&#9888;</div>' +
                            '<div>PDF 渲染库未能加载</div>' +
                            '<div style="font-size:12px;opacity:0.7;margin-top:8px;">' +
                            '请检查 frontend/libs/pdfs/ 目录下的 pdf.min.js 与 pdfjs-global.js' +
                            '</div>' +
                            '</div>';
                    }
                });
                return;
            }

            try {
                tryConfigureWorker();
                this._openFile();
            } catch (e) {
                console.error('[PDF] _loadPdfJs 同步路径异常:', e);
                if (container) {
                    container.innerHTML =
                        '<div class="pdf-error">' +
                        '<div class="pdf-error__icon">&#9888;</div>' +
                        '<div>PDF 渲染初始化失败</div>' +
                        '<div style="font-size:12px;opacity:0.7;margin-top:8px;">' +
                        this._escapeHtml((e && e.message) || String(e)) +
                        '</div>' +
                        '</div>';
                }
            }
        },

        /**
         * 轮询等待 global.pdfjsLib 出现（由 pdfjs-global.js 异步注入）
         * @param {number} timeoutSeconds
         */
        _waitForPdfLib: function (timeoutSeconds) {
            return new Promise(function (resolve, reject) {
                var start = Date.now();
                (function poll() {
                    if (typeof global.pdfjsLib !== 'undefined') {
                        resolve();
                        return;
                    }
                    if ((Date.now() - start) / 1000 > timeoutSeconds) {
                        reject(new Error('timeout'));
                        return;
                    }
                    setTimeout(poll, 100);
                })();
            });
        },

        /**
         * 打开 PDF 文件并渲染（通过 bridge 读取 base64 数据，绕过 file:// CORS 限制）
         */
        _openFile: function () {
            var self = this;
            var container = this._root.querySelector('#pdf-canvas-container');
            var filePath = this._config.file_path || this._config.file_path_or_url || this._config.filePath;

            if (!filePath || typeof global.pdfjsLib === 'undefined') {
                return;
            }

            console.log('[PDF] reading file via bridge:', filePath);

            // 通过 Python bridge 读取文件为 base64，解码为 ArrayBuffer 后传给 PDF.js
            var api = global.MMFBBridge.api || global.MMFBBridge;
            api.readFileBase64(filePath).then(function (b64) {
                if (self._destroyed) return;
                if (!b64 || b64.indexOf('[') === 0) {
                    // 错误消息（"[Error..." 或 "[File too large]"）
                    if (container) {
                        container.innerHTML =
                            '<div class="pdf-error">' +
                            '<div class="pdf-error__icon">&#10060;</div>' +
                            '<div>无法读取 PDF 文件</div>' +
                            '<div style="font-size:12px;opacity:0.7;margin-top:8px;">' +
                            (b64 ? self._escapeHtml(b64) : '返回数据为空') +
                            '</div>' +
                            '</div>';
                    }
                    return;
                }

                console.log('[PDF] base64 received, length:', b64.length);

                // base64 → ArrayBuffer
                var raw = atob(b64);
                var uint8 = new Uint8Array(raw.length);
                for (var i = 0; i < raw.length; i++) {
                    uint8[i] = raw.charCodeAt(i);
                }

                var loadingTask = global.pdfjsLib.getDocument({ data: uint8.buffer });

                loadingTask.promise.then(function (pdfDoc) {
                    if (self._destroyed) return;
                    console.log('[PDF] loaded successfully, pages:', pdfDoc.numPages);
                    self._pdfDoc = pdfDoc;
                    self._totalPages = pdfDoc.numPages;
                    self._updatePageInfo();
                    self._setupVirtualScroll();
                    self._renderVisiblePages();
                }).catch(function (err) {
                    console.error('[PDF] parse error:', err);
                    if (!container) return;
                    container.innerHTML =
                        '<div class="pdf-error">' +
                        '<div class="pdf-error__icon">&#10060;</div>' +
                        '<div>无法解析 PDF</div>' +
                        '<div style="font-size:12px;opacity:0.7;margin-top:8px;">' +
                        (err && err.message ? self._escapeHtml(err.message) : '未知错误') +
                        '</div>' +
                        '</div>';
                });
            }).catch(function (err) {
                console.error('[PDF] bridge read error:', err);
                if (!container) return;
                container.innerHTML =
                    '<div class="pdf-error">' +
                    '<div class="pdf-error__icon">&#10060;</div>' +
                    '<div>无法读取 PDF 文件</div>' +
                    '<div style="font-size:12px;opacity:0.7;margin-top:8px;">' +
                    (err && err.message ? self._escapeHtml(err.message) : '未知错误') +
                    '</div>' +
                    '</div>';
            });
        },

        /**
         * 设置虚拟滚动：使用 IntersectionObserver 检测可见页
         */
        _setupVirtualScroll: function () {
            var self = this;
            var container = this._root.querySelector('#pdf-canvas-container');
            if (!container) return;

            // 预创建所有页的占位 div
            container.innerHTML = '';
            for (var i = 1; i <= this._totalPages; i++) {
                var placeholder = document.createElement('div');
                placeholder.className = 'pdf-page-placeholder';
                placeholder.setAttribute('data-page', String(i));
                placeholder.style.minHeight = '400px'; // 占位高度，真实高度在渲染后调整
                placeholder.setAttribute('id', 'pdf-page-' + i);
                container.appendChild(placeholder);
            }

            // 使用 IntersectionObserver 检测可视区域
            if (global.IntersectionObserver) {
                this._observer = new IntersectionObserver(function (entries) {
                    entries.forEach(function (entry) {
                        if (entry.isIntersecting) {
                            var pageNum = parseInt(entry.target.getAttribute('data-page'), 10);
                            if (pageNum) self._renderPage(pageNum);
                        }
                    });
                }, { root: container, rootMargin: '200px' });

                var placeholders = container.querySelectorAll('.pdf-page-placeholder');
                for (var i = 0; i < placeholders.length; i++) {
                    this._observer.observe(placeholders[i]);
                }
            } else {
                // 降级：渲染前 3 页
                for (var i = 1; i <= Math.min(3, this._totalPages); i++) {
                    this._renderPage(i);
                }
            }
        },

        /**
         * 渲染可见页（首次加载时触发）
         */
        _renderVisiblePages: function () {
            var container = this._root.querySelector('#pdf-canvas-container');
            if (!container) return;

            var viewTop = container.scrollTop;
            var viewBottom = viewTop + container.clientHeight;
            var placeholders = container.querySelectorAll('.pdf-page-placeholder');
            for (var i = 0; i < placeholders.length; i++) {
                var ph = placeholders[i];
                if (ph.offsetTop + ph.offsetHeight >= viewTop &&
                    ph.offsetTop <= viewBottom) {
                    var pageNum = parseInt(ph.getAttribute('data-page'), 10);
                    if (pageNum) this._renderPage(pageNum);
                }
            }
        },

        /**
         * 渲染单页的 canvas
         */
        _renderPage: function (pageNum) {
            if (!this._pdfDoc || this._pageRendering[pageNum] || this._destroyed) return;

            var placeholder = this._root.querySelector('#pdf-page-' + pageNum);
            if (!placeholder || placeholder.getAttribute('data-rendered') === '1') return;

            this._pageRendering[pageNum] = true;
            var self = this;

            this._pdfDoc.getPage(pageNum).then(function (page) {
                if (self._destroyed) return;

                var viewport = page.getViewport({ scale: self._scale });
                var canvas = document.createElement('canvas');
                var context = canvas.getContext('2d');
                canvas.height = viewport.height;
                canvas.width = viewport.width;
                canvas.setAttribute('data-page', String(pageNum));

                // 渲染 PDF 页面
                var renderContext = {
                    canvasContext: context,
                    viewport: viewport,
                };

                var renderTask = page.render(renderContext);
                renderTask.promise.then(function () {
                    if (self._destroyed) return;

                    placeholder.innerHTML = '';
                    placeholder.style.minHeight = viewport.height + 'px';
                    placeholder.appendChild(canvas);
                    placeholder.setAttribute('data-rendered', '1');
                    self._pageRendering[pageNum] = false;

                    // 渲染文本层（用于搜索）
                    self._renderTextLayer(page, viewport, placeholder);
                }).catch(function () {
                    self._pageRendering[pageNum] = false;
                });
            }).catch(function () {
                self._pageRendering[pageNum] = false;
            });
        },

        /**
         * 渲染文本层（搜索高亮用）
         */
        _renderTextLayer: function (page, viewport, container) {
            var self = this;
            page.getTextContent().then(function (textContent) {
                if (self._destroyed || !global.pdfjsLib) return;

                var textLayer = document.createElement('div');
                textLayer.className = 'pdf-text-layer';
                textLayer.style.width = viewport.width + 'px';
                textLayer.style.height = viewport.height + 'px';

                global.pdfjsLib.renderTextLayer({
                    textContent: textLayer,
                    container: textLayer,
                    viewport: viewport,
                    textDivs: [],
                });

                container.style.position = 'relative';
                container.appendChild(textLayer);
            }).catch(function() {});
        },

        /**
         * 更新工具栏页面信息
         */
        _updatePageInfo: function () {
            var el = this._root.querySelector('#pdf-page-info');
            if (el) el.textContent = this._currentPage + ' / ' + this._totalPages;
        },

        /**
         * 更新缩放信息
         */
        _updateZoomInfo: function () {
            var el = this._root.querySelector('#pdf-zoom-level');
            var basePercent = Math.round(this._scale / 1.5 * 100);
            if (el) el.textContent = basePercent + '%';
        },

        /**
         * 绑定工具栏按钮事件
         */
        _bindToolbarEvents: function () {
            var self = this;
            var root = this._root;
            if (!root) return;

            // 上一页
            var prevBtn = root.querySelector('#pdf-prev');
            if (prevBtn) prevBtn.addEventListener('click', function () { self._goToPage(self._currentPage - 1); });

            // 下一页
            var nextBtn = root.querySelector('#pdf-next');
            if (nextBtn) nextBtn.addEventListener('click', function () { self._goToPage(self._currentPage + 1); });

            // 放大
            var zoomInBtn = root.querySelector('#pdf-zoom-in');
            if (zoomInBtn) zoomInBtn.addEventListener('click', function () { self._zoom(0.25); });

            // 缩小
            var zoomOutBtn = root.querySelector('#pdf-zoom-out');
            if (zoomOutBtn) zoomOutBtn.addEventListener('click', function () { self._zoom(-0.25); });

            // 搜索开关
            var searchToggle = root.querySelector('#pdf-search-toggle');
            if (searchToggle) searchToggle.addEventListener('click', function () { self._toggleSearch(); });

            var searchClose = root.querySelector('#pdf-search-close');
            if (searchClose) searchClose.addEventListener('click', function () { self._closeSearch(); });

            var searchPrev = root.querySelector('#pdf-search-prev');
            if (searchPrev) searchPrev.addEventListener('click', function () { self._searchMove(-1); });

            var searchNext = root.querySelector('#pdf-search-next');
            if (searchNext) searchNext.addEventListener('click', function () { self._searchMove(1); });

            var searchInput = root.querySelector('#pdf-search-input');
            if (searchInput) {
                searchInput.addEventListener('input', function () {
                    self._search(searchInput.value);
                });
                searchInput.addEventListener('keydown', function (e) {
                    if (e.key === 'Enter') self._searchMove(1);
                    if (e.key === 'Escape') self._closeSearch();
                });
            }

            // 容器滚动时更新当前页
            var container = root.querySelector('#pdf-canvas-container');
            if (container) {
                container.addEventListener('scroll', self._debounce(function () {
                    self._updateCurrentPageFromScroll();
                }, 100));
            }
        },

        /**
         * 绑定全局键盘事件
         */
        _bindKeyboardEvents: function () {
            var self = this;
            this._onKeyDown = function (e) {
                if (self._destroyed) return;

                // Ctrl+F 搜索
                if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                    e.preventDefault();
                    self._toggleSearch();
                    return;
                }

                // 翻页
                if (e.key === 'PageDown' || e.key === 'ArrowDown' || e.key === ' ') {
                    self._goToPage(self._currentPage + 1);
                } else if (e.key === 'PageUp' || e.key === 'ArrowUp') {
                    self._goToPage(self._currentPage - 1);
                } else if (e.key === 'Home') {
                    self._goToPage(1);
                } else if (e.key === 'End') {
                    self._goToPage(self._totalPages);
                }
            };
            document.addEventListener('keydown', this._onKeyDown);
        },

        /**
         * 跳转到指定页
         */
        _goToPage: function (pageNum) {
            if (!this._pdfDoc || pageNum < 1 || pageNum > this._totalPages) return;
            this._currentPage = pageNum;
            this._updatePageInfo();

            // 滚动到对应占位符
            var placeholder = this._root.querySelector('#pdf-page-' + pageNum);
            if (placeholder) {
                placeholder.scrollIntoView({ behavior: 'auto', block: 'start' });
            }
        },

        /**
         * 缩放
         */
        _zoom: function (delta) {
            var newScale = this._scale + delta;
            if (newScale < 0.5) newScale = 0.5;
            if (newScale > 4.0) newScale = 4.0;
            this._scale = newScale;
            this._updateZoomInfo();

            // 重新渲染所有已渲染页
            var self = this;
            var rendered = this._root.querySelectorAll('.pdf-page-placeholder[data-rendered="1"]');
            rendered.forEach(function (ph) {
                ph.removeAttribute('data-rendered');
                ph.innerHTML = '';
            });

            // 清空渲染标记以强制重渲染
            this._pageRendering = {};
            this._renderVisiblePages();
        },

        /**
         * 从滚动位置更新当前页
         */
        _updateCurrentPageFromScroll: function () {
            var container = this._root.querySelector('#pdf-canvas-container');
            if (!container) return;
            var viewMid = container.scrollTop + container.clientHeight / 2;

            var maxVisiblePage = 1;
            var placeholders = container.querySelectorAll('.pdf-page-placeholder');
            for (var i = 0; i < placeholders.length; i++) {
                var ph = placeholders[i];
                if (ph.offsetTop <= viewMid) {
                    maxVisiblePage = parseInt(ph.getAttribute('data-page'), 10) || 1;
                }
            }
            if (maxVisiblePage !== this._currentPage) {
                this._currentPage = maxVisiblePage;
                this._updatePageInfo();
            }
        },

        /**
         * 打开/关闭搜索框
         */
        _toggleSearch: function () {
            var box = this._root.querySelector('#pdf-search-box');
            if (!box) return;
            box.classList.toggle('visible');
            if (box.classList.contains('visible')) {
                var input = box.querySelector('#pdf-search-input');
                if (input) input.focus();
            }
        },

        _closeSearch: function () {
            var box = this._root.querySelector('#pdf-search-box');
            if (box) box.classList.remove('visible');
            this._clearHighlights();
            this._searchQuery = '';
        },

        /**
         * 搜索文本
         */
        _search: function (query) {
            this._searchQuery = (query || '').trim();
            this._searchMatches = [];
            this._searchCurrent = -1;
            this._clearHighlights();

            if (!this._searchQuery || !this._pdfDoc) return;

            var self = this;
            var lowerQuery = this._searchQuery.toLowerCase();
            var totalMatchCount = 0;
            var pagesSearched = 0;

            function searchNextPage(pageNum) {
                if (pageNum > self._totalPages || self._destroyed) {
                    // 搜索完成
                    var countEl = self._root.querySelector('#pdf-search-count');
                    if (countEl) {
                        countEl.textContent = totalMatchCount > 0 ?
                            (self._searchCurrent + 1) + '/' + totalMatchCount : '无结果';
                    }
                    return;
                }

                self._pdfDoc.getPage(pageNum).then(function (page) {
                    return page.getTextContent();
                }).then(function (textContent) {
                    if (self._destroyed) return;

                    var pageText = textContent.items.map(function (item) { return item.str; }).join(' ');
                    var lowerPage = pageText.toLowerCase();
                    var offset = 0;
                    var matchIdx;
                    while ((matchIdx = lowerPage.indexOf(lowerQuery, offset)) !== -1) {
                        self._searchMatches.push({ page: pageNum, charIdx: matchIdx });
                        totalMatchCount++;
                        offset = matchIdx + lowerQuery.length;
                    }

                    pagesSearched++;
                    if (pagesSearched <= 20) { // 首轮搜索前 20 页
                        searchNextPage(pageNum + 1);
                    } else {
                        // 匹配结果汇报
                        var countEl = self._root.querySelector('#pdf-search-count');
                        if (countEl) {
                            countEl.textContent = totalMatchCount > 0 ? '1/' + totalMatchCount : '无结果';
                        }
                        if (totalMatchCount > 0) {
                            self._searchMove(0); // 跳到第一个匹配
                        }
                    }
                }).catch(function () {
                    pagesSearched++;
                    searchNextPage(pageNum + 1);
                });
            }

            searchNextPage(1);
        },

        _searchMove: function (direction) {
            if (this._searchMatches.length === 0) return;

            this._searchCurrent += direction;
            if (this._searchCurrent < 0) this._searchCurrent = this._searchMatches.length - 1;
            if (this._searchCurrent >= this._searchMatches.length) this._searchCurrent = 0;

            var match = this._searchMatches[this._searchCurrent];
            this._goToPage(match.page);

            var countEl = this._root.querySelector('#pdf-search-count');
            if (countEl) countEl.textContent = (this._searchCurrent + 1) + '/' + this._searchMatches.length;
        },

        _clearHighlights: function () {
            if (!this._root) return;
            var highlights = this._root.querySelectorAll('.pdf-text-layer .highlight');
            highlights.forEach(function (h) { h.classList.remove('highlight', 'selected'); });
        },

        /**
         * 简单 debounce
         */
        _debounce: function (fn, ms) {
            var timer = null;
            return function () {
                var self = this, args = arguments;
                if (timer) clearTimeout(timer);
                timer = setTimeout(function () { fn.apply(self, args); }, ms);
            };
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

    global.MMFBPDFViewer = MMFBPDFViewer;

})(window);
