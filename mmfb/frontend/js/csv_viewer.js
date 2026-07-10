/**
 * MMFB CSV Viewer - 表格预览 + 排序 + 过滤 + 分页 + 导出
 *
 * 功能:
 *   - 原生 <table> 渲染（无第三方依赖）
 *   - 点击列头排序（字符串 / 数值 / 日期 三类）
 *   - 顶部过滤输入框（全字段模糊匹配）
 *   - 分页（每页 200 / 500 / 1000 行可选）
 *   - 导出 Excel (.xlsx) / TSV (.tsv) 按钮（通过 Bridge 后端执行）
 *   - 大文件截断提示 + 行数状态栏
 *
 * 依赖: MMFBBridge (bridge.js)
 */
(function (global) {
    'use strict';

    var DEFAULT_PAGE_SIZE = 200;

    /**
     * @param {HTMLElement} root - 挂载容器
     * @param {object} data - CsvHandler.get_preview 返回的 data 字段
     */
    function MMFBCSVViewer(root, data) {
        this._root = root;
        this._filePath = data.file_path;
        this._fileSize = data.file_size || 0;
        this._headers = data.headers || [];
        this._columns = data.columns || 0;
        this._totalRows = data.total_rows || 0;
        this._previewRows = data.preview_rows || 0;
        this._dtypes = data.dtypes || [];
        this._encoding = data.encoding || "utf-8";
        this._delimiter = data.delimiter || ",";
        this._truncated = !!data.truncated;

        // 原始行数据（不变，仅用于排序/过滤的源）
        this._allRows = data.rows || [];
        // 过滤/排序后的行（当前视图数据源）
        this._filteredRows = this._allRows.slice(0);
        // 当前页数据（filteredRows 的子集）
        this._pageRows = [];

        this._filterText = "";
        this._sortCol = -1;          // 排序列索引
        this._sortAsc = true;        // 升序为 true

        this._pageSize = DEFAULT_PAGE_SIZE;
        this._pageIndex = 0;         // 0-based

        this._init();
    }

    MMFBCSVViewer.prototype._init = function () {
        this._buildStructure();
        if (this._columns === 0 || this._allRows.length === 0) {
            this._renderEmpty();
            return;
        }
        this._applyFilterAndSort();
    };

    MMFBCSVViewer.prototype._buildStructure = function () {
        var self = this;
        var root = this._root;
        root.innerHTML = '';
        root.className = 'csv-viewer';

        // 工具栏
        var toolbar = document.createElement('div');
        toolbar.className = 'csv-viewer__toolbar';
        toolbar.innerHTML =
            '<div class="csv-viewer__toolbar-left">' +
            '<input type="text" class="csv-viewer__filter" id="csv-filter" placeholder="过滤（模糊匹配全字段）...">' +
            '<select class="csv-viewer__page-size" id="csv-page-size">' +
            '<option value="200">200 行/页</option>' +
            '<option value="500">500 行/页</option>' +
            '<option value="1000">1000 行/页</option>' +
            '</select>' +
            '</div>' +
            '<div class="csv-viewer__toolbar-right">' +
            '<button class="csv-viewer__export-btn" id="csv-export-xlsx">导出 Excel (.xlsx)</button>' +
            '<button class="csv-viewer__export-btn" id="csv-export-tsv">导出 TSV (.tsv)</button>' +
            '<span class="csv-viewer__status" id="csv-status"></span>' +
            '</div>';
        root.appendChild(toolbar);

        // 截断提示
        if (this._truncated) {
            var tip = document.createElement('div');
            tip.className = 'csv-viewer__truncated-tip';
            tip.textContent = '文件超过 ' + this._previewRows + ' 行，已截断预览（导出不受影响）';
            toolbar.appendChild(tip);
        }

        // 表格容器
        var body = document.createElement('div');
        body.className = 'csv-viewer__body';
        body.id = 'csv-body';
        root.appendChild(body);

        // 底栏
        var footer = document.createElement('div');
        footer.className = 'csv-viewer__footer';
        footer.innerHTML =
            '<span class="csv-viewer__footer-info" id="csv-footer-info"></span>' +
            '<span class="csv-viewer__pager" id="csv-pager"></span>';
        root.appendChild(footer);

        this._bodyEl = body;
        this._statusEl = document.getElementById('csv-status');
        this._footerInfoEl = document.getElementById('csv-footer-info');
        this._pagerEl = document.getElementById('csv-pager');

        // 事件绑定
        var filterEl = document.getElementById('csv-filter');
        var timer = null;
        filterEl.addEventListener('input', function () {
            clearTimeout(timer);
            var val = filterEl.value;
            timer = setTimeout(function () {
                self._filterText = val;
                self._pageIndex = 0;
                self._applyFilterAndSort();
            }, 200);
        });

        var pageSizeEl = document.getElementById('csv-page-size');
        pageSizeEl.value = String(DEFAULT_PAGE_SIZE);
        pageSizeEl.addEventListener('change', function () {
            var v = parseInt(pageSizeEl.value, 10);
            if (!isNaN(v)) {
                self._pageSize = v;
                self._pageIndex = 0;
                self._applyFilterAndSort();
            }
        });

        document.getElementById('csv-export-xlsx').addEventListener('click', function () {
            self._exportFile('xlsx');
        });
        document.getElementById('csv-export-tsv').addEventListener('click', function () {
            self._exportFile('tsv');
        });
    };

    // ========== 数据管道 ==========

    MMFBCSVViewer.prototype._applyFilterAndSort = function () {
        // 1. 过滤
        if (this._filterText) {
            var needle = this._filterText.toLowerCase();
            this._filteredRows = this._allRows.filter(function (row) {
                for (var i = 0; i < row.length; i++) {
                    var v = row[i];
                    if (v !== null && String(v).toLowerCase().indexOf(needle) >= 0) {
                        return true;
                    }
                }
                return false;
            });
        } else {
            this._filteredRows = this._allRows.slice(0);
        }

        // 2. 排序
        if (this._sortCol >= 0 && this._sortCol < this._columns) {
            var col = this._sortCol;
            var asc = this._sortAsc ? 1 : -1;
            var dtype = this._dtypes[col] || "string";

            this._filteredRows.sort(function (a, b) {
                return self._compareValues(a[col], b[col], dtype) * asc;
            });
        }

        // 3. 分页
        var total = this._filteredRows.length;
        var start = this._pageIndex * this._pageSize;
        var end = Math.min(start + this._pageSize, total);
        if (start >= total && total > 0) {
            this._pageIndex = 0;
            start = 0;
            end = Math.min(this._pageSize, total);
        }
        this._pageRows = this._filteredRows.slice(start, end);

        // 4. 渲染
        this._renderTable();
        this._renderPager();
        this._updateStatus();
    };

    MMFBCSVViewer.prototype._compareValues = function (a, b, dtype) {
        // 缺失值永远排最后
        if (a === null && b === null) return 0;
        if (a === null) return 1;
        if (b === null) return -1;

        if (dtype === "number") {
            var na = Number(a);
            var nb = Number(b);
            if (isNaN(na) && isNaN(nb)) return 0;
            if (isNaN(na)) return 1;
            if (isNaN(nb)) return -1;
            return na < nb ? -1 : (na > nb ? 1 : 0);
        }

        if (dtype === "datetime") {
            // ISO 字符串直接比字典序
            var sa = String(a);
            var sb = String(b);
            return sa < sb ? -1 : (sa > sb ? 1 : 0);
        }

        // 字符串
        var s1 = String(a);
        var s2 = String(b);
        return s1 < s2 ? -1 : (s1 > s2 ? 1 : 0);
    };

    // ========== 渲染 ==========

    MMFBCSVViewer.prototype._renderTable = function () {
        if (this._pageRows.length === 0) {
            this._bodyEl.innerHTML =
                '<div class="csv-viewer__empty">' +
                (this._filterText ? '无匹配行（过滤词：' + this._filterText + '）' : '该表无数据') +
                '</div>';
            return;
        }

        var self = this;
        var wrap = document.createElement('div');
        wrap.className = 'csv-table-wrap';

        var table = document.createElement('table');
        table.className = 'csv-table';

        // 表头
        var thead = document.createElement('thead');
        var headerTr = document.createElement('tr');
        for (var c = 0; c < this._columns; c++) {
            (function (colIdx) {
                var th = document.createElement('th');
                th.className = 'csv-table__header-cell';
                th.textContent = self._renderHeaderTitle(colIdx);

                // 排序列高亮
                if (self._sortCol === colIdx) {
                    th.classList.add('is-sort-' + (self._sortAsc ? 'asc' : 'desc'));
                }

                // 排序箭头条
                var indicator = document.createElement('span');
                indicator.className = 'csv-table__sort-indicator';
                indicator.textContent = (self._sortCol === colIdx)
                    ? (self._sortAsc ? ' ▲' : ' ▼')
                    : '';
                th.appendChild(indicator);

                th.addEventListener('click', function () {
                    if (self._sortCol === colIdx) {
                        self._sortAsc = !self._sortAsc;
                    } else {
                        self._sortCol = colIdx;
                        self._sortAsc = true;
                    }
                    self._applyFilterAndSort();
                });

                headerTr.appendChild(th);
            })(c);
        }
        thead.appendChild(headerTr);
        table.appendChild(thead);

        // 数据行
        var tbody = document.createElement('tbody');
        for (var r = 0; r < this._pageRows.length; r++) {
            (function (rowIdx) {
                var tr = document.createElement('tr');
                var row = self._pageRows[rowIdx];
                for (var cc = 0; cc < self._columns; cc++) {
                    var td = document.createElement('td');
                    td.className = 'csv-table__cell';
                    var dtype = self._dtypes[cc];

                    // 数值列右对齐
                    if (dtype === "number") {
                        td.classList.add('is-number');
                    }

                    var value = row[cc];
                    if (value === null) {
                        td.classList.add('is-null');
                        td.textContent = '(null)';
                    } else {
                        td.textContent = String(value);
                        td.title = String(value);
                    }

                    tr.appendChild(td);
                }
                tbody.appendChild(tr);
            })(r);
        }
        table.appendChild(tbody);
        wrap.appendChild(table);
        this._bodyEl.innerHTML = '';
        this._bodyEl.appendChild(wrap);
    };

    MMFBCSVViewer.prototype._renderHeaderTitle = function (colIdx) {
        var name = this._headers[colIdx] || ('列' + (colIdx + 1));
        var dtype = this._dtypes[colIdx];
        var tag = '';
        if (dtype === 'number') tag = ' [数]';
        else if (dtype === 'datetime') tag = ' [日]';
        else if (dtype === 'boolean') tag = ' [布]';
        return name + tag;
    };

    MMFBCSVViewer.prototype._renderPager = function () {
        var total = this._filteredRows.length;
        var totalPages = Math.max(1, Math.ceil(total / this._pageSize));
        // 修复：page 越界
        if (this._pageIndex >= totalPages) {
            this._pageIndex = totalPages - 1;
        }

        var self = this;
        this._pagerEl.innerHTML = '';

        var prevBtn = document.createElement('button');
        prevBtn.className = 'csv-viewer__pager-btn csv-viewer__pager-btn--text';
        prevBtn.textContent = '上一页';
        prevBtn.disabled = this._pageIndex <= 0;
        prevBtn.addEventListener('click', function () {
            if (self._pageIndex > 0) {
                self._pageIndex--;
                self._applyFilterAndSort();
            }
        });
        this._pagerEl.appendChild(prevBtn);

        var info = document.createElement('span');
        info.className = 'csv-viewer__pager-info';
        var startIdx = total > 0 ? (this._pageIndex * this._pageSize + 1) : 0;
        var endIdx = Math.min((this._pageIndex + 1) * this._pageSize, total);
        info.textContent = startIdx + '-' + endIdx + ' / ' + total + ' 行';
        this._pagerEl.appendChild(info);

        var nextBtn = document.createElement('button');
        nextBtn.className = 'csv-viewer__pager-btn csv-viewer__pager-btn--text';
        nextBtn.textContent = '下一页';
        nextBtn.disabled = this._pageIndex >= totalPages - 1;
        nextBtn.addEventListener('click', function () {
            if (self._pageIndex < totalPages - 1) {
                self._pageIndex++;
                self._applyFilterAndSort();
            }
        });
        this._pagerEl.appendChild(nextBtn);
    };

    MMFBCSVViewer.prototype._updateStatus = function () {
        if (this._statusEl) {
            var parts = [
                this._columns + ' 列',
                this._formatPreviewCount(),
                this._formatSize(this._fileSize),
                this._encoding
            ];
            if (this._truncated) parts.push('已截断预览');
            this._statusEl.textContent = parts.join(' | ');
        }
        if (this._footerInfoEl) {
            var info = this._encoding + ' | 分隔符: ' +
                (this._delimiter === '\t' ? 'Tab' : "'" + this._delimiter + "'");
            this._footerInfoEl.textContent = info;
        }
    };

    MMFBCSVViewer.prototype._formatPreviewCount = function () {
        var filtered = this._filteredRows.length;
        if (this._filterText) {
            return filtered + ' 行（过滤后）';
        }
        return this._allRows.length + ' / ' + this._totalRows + ' 行';
    };

    MMFBCSVViewer.prototype._renderEmpty = function () {
        this._bodyEl.innerHTML =
            '<div class="csv-viewer__empty">' +
            '<div class="csv-viewer__empty-icon">&#128203;</div>' +
            '<div class="csv-viewer__empty-title">无可预览数据</div>' +
            '</div>';
    };

    MMFBCSVViewer.prototype._renderError = function (msg) {
        this._bodyEl.innerHTML =
            '<div class="csv-viewer__error">' +
            '<div class="csv-viewer__error-icon">&#9888;</div>' +
            '<div class="csv-viewer__error-title">加载失败</div>' +
            '<div class="csv-viewer__error-msg">' + (msg || '未知错误') + '</div>' +
            '</div>';
    };

    MMFBCSVViewer.prototype._exportFile = function (format) {
        var self = this;
        if (!global.MMFBBridge) {
            alert('[Mock] Bridge 未就绪，无法导出');
            return;
        }

        // 构造导出路径：源文件同级，名 + 格式
        var srcPath = this._filePath;
        var dotIdx = srcPath.lastIndexOf('.');
        var base = (dotIdx > 0) ? srcPath.substring(0, dotIdx) : srcPath;
        var dstPath = base + '.' + format;

        this._flashStatus('正在导出 ' + format.toUpperCase() + '...');

        global.MMFBBridge.api.exportCsv(srcPath, dstPath, format).then(function (json) {
            var result = typeof json === 'string' ? JSON.parse(json) : json;
            if (result && result.ok) {
                self._flashStatus('导出成功: ' + result.path);
            } else {
                self._flashStatus('导出失败: ' + (result && result.error ? result.error : '未知错误'), true);
            }
        }).catch(function (err) {
            self._flashStatus('导出失败: ' + String(err), true);
        });
    };

    MMFBCSVViewer.prototype._flashStatus = function (msg, isError) {
        var self = this;
        if (!this._statusEl) return;
        this._statusEl.textContent = msg;
        if (isError) this._statusEl.classList.add('is-error');
        setTimeout(function () {
            self._updateStatus();
            self._statusEl.classList.remove('is-error');
        }, 3000);
    };

    MMFBCSVViewer.prototype._formatSize = function (bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / 1024 / 1024).toFixed(1) + ' MB';
    };

    MMFBCSVViewer.prototype.destroy = function () {
        this._root.innerHTML = '';
        this._root.className = '';
    };

    global.MMFBCSVViewer = MMFBCSVViewer;

})(window);
