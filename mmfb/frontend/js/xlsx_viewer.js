/**
 * MMFB Xlsx Viewer - Excel 表格预览 + 编辑
 *
 * 功能:
 *   - 多 Sheet 切换
 *   - 预览模式：原生 table 渲染，单元格样式（粗体/斜体/背景色/对齐）
 *   - 编辑模式：双击单元格编辑，失焦自动保存
 *   - 状态栏：表页名/选中单元格/文件大小
 *
 * 依赖: MMFBBridge (bridge.js)
 */
(function (global) {
    'use strict';

    /**
     * @param {HTMLElement} root - 挂载容器
     * @param {object} data - { file_path, file_size, sheets, editable, save }
     */
    function MMFBXlsxViewer(root, data) {
        this._root = root;
        this._filePath = data.file_path;
        this._fileSize = data.file_size || 0;
        this._sheets = data.sheets || [];
        this._editable = !!data.editable;
        this._saveEnabled = !!data.save;
        this._currentSheetIdx = 0;
        this._selectedCell = null;
        this._editMode = false;         // 是否处于编辑视图
        this._pendingChanges = [];      // 待保存的变更
        this._cellMap = new Map();      // "r,c" -> cell data
        this._domCellMap = new Map();   // "r,c" -> DOM element

        this._init();
    }

    MMFBXlsxViewer.prototype._init = function () {
        this._buildStructure();
        if (this._sheets.length === 0) {
            this._renderEmpty();
            return;
        }
        this._renderSheetTabs();
        this._renderSheet(0);
        this._updateFooter();
    };

    MMFBXlsxViewer.prototype._buildStructure = function () {
        var self = this;
        var root = this._root;
        root.innerHTML = '';
        root.className = 'xlsx-viewer';

        // 工具栏
        var toolbar = document.createElement('div');
        toolbar.className = 'xlsx-viewer__toolbar';
        toolbar.innerHTML =
            '<div class="xlsx-viewer__toolbar-left">' +
            '<span class="xlsx-viewer__sheet-tabs" id="xlsx-sheet-tabs"></span>' +
            '</div>' +
            '<div class="xlsx-viewer__toolbar-right">' +
            '<span class="xlsx-viewer__status" id="xlsx-status"></span>' +
            '</div>';
        root.appendChild(toolbar);

        // 编辑模式切换按钮（有 save 标志时显示）
        if (this._editable) {
            var editBtn = document.createElement('button');
            editBtn.className = 'xlsx-viewer__edit-btn';
            editBtn.textContent = '[编辑]';
            editBtn.title = '切换编辑模式';
            editBtn.addEventListener('click', function () {
                self._toggleEditMode();
            });
            toolbar.querySelector('.xlsx-viewer__toolbar-right').prepend(editBtn);
            this._editBtn = editBtn;
        }

        // 保存按钮（编辑模式且有变更时激活）
        if (this._editable) {
            var saveBtn = document.createElement('button');
            saveBtn.className = 'xlsx-viewer__save-btn';
            saveBtn.textContent = '[保存]';
            saveBtn.disabled = true;
            saveBtn.addEventListener('click', function () {
                self._saveChanges();
            });
            toolbar.querySelector('.xlsx-viewer__toolbar-right').prepend(saveBtn);
            this._saveBtn = saveBtn;
        }

        // 表格容器
        var body = document.createElement('div');
        body.className = 'xlsx-viewer__body';
        body.id = 'xlsx-body';
        root.appendChild(body);

        // 底栏
        var footer = document.createElement('div');
        footer.className = 'xlsx-viewer__footer';
        footer.innerHTML =
            '<span class="xlsx-viewer__footer-info" id="xlsx-footer-info"></span>';
        root.appendChild(footer);

        this._bodyEl = body;
        this._statusEl = document.getElementById('xlsx-status');
        this._footerInfoEl = document.getElementById('xlsx-footer-info');
    };

    MMFBXlsxViewer.prototype._renderEmpty = function () {
        this._bodyEl.innerHTML =
            '<div class="xlsx-viewer__empty">' +
            '<div class="xlsx-viewer__empty-icon">&#128203;</div>' +
            '<div class="xlsx-viewer__empty-title">无可预览数据</div>' +
            '</div>';
    };

    MMFBXlsxViewer.prototype._renderSheetTabs = function () {
        var self = this;
        var container = document.getElementById('xlsx-sheet-tabs');
        if (!container) return;
        container.innerHTML = '';

        this._sheets.forEach(function (sheet, idx) {
            var tab = document.createElement('button');
            tab.className = 'xlsx-viewer__sheet-tab' +
                (idx === self._currentSheetIdx ? ' is-active' : '');
            tab.textContent = sheet.name;
            tab.title = sheet.name + ' (' + (sheet.maxRow || 0) + ' rows)';
            tab.addEventListener('click', function () {
                if (idx === self._currentSheetIdx) return;
                if (self._pendingChanges.length > 0 && !confirm('当前表页有未保存的变更，切换将丢失这些变更，继续？')) {
                    return;
                }
                self._currentSheetIdx = idx;
                self._pendingChanges = [];
                self._renderSheetTabs();
                self._renderSheet(idx);
                self._updateSaveButton();
            });
            container.appendChild(tab);
        });
    };

    MMFBXlsxViewer.prototype._renderSheet = function (idx) {
        var sheet = this._sheets[idx];
        if (!sheet) return;

        this._cellMap.clear();
        this._domCellMap.clear();

        var rows = sheet.maxRow || 0;
        var cols = sheet.maxCol || 0;

        if (rows === 0 || cols === 0) {
            this._bodyEl.innerHTML =
                '<div class="xlsx-viewer__empty">' +
                '<div class="xlsx-viewer__empty-title">工作表 "' + sheet.name + '" 为空</div>' +
                '</div>';
            return;
        }

        // 创建行索引 + 数据 Table
        var self = this;
        var wrap = document.createElement('div');
        wrap.className = 'xlsx-table-wrap';

        var table = document.createElement('table');
        table.className = 'xlsx-table';

        // 表头行（列字母 A B C ...）
        var thead = document.createElement('thead');
        var headerRow = document.createElement('tr');
        // 左上角角落
        var corner = document.createElement('th');
        corner.className = 'xlsx-table__corner';
        headerRow.appendChild(corner);
        for (var c = 0; c < cols; c++) {
            var th = document.createElement('th');
            th.className = 'xlsx-table__col-header';
            th.textContent = self._colToLetter(c);
            headerRow.appendChild(th);
        }
        thead.appendChild(headerRow);
        table.appendChild(thead);

        // Table body
        var tbody = document.createElement('tbody');

        // 建立空矩阵（行索引 -> 列索引 -> cell data）
        var matrix = [];
        for (var r = 0; r < rows; r++) {
            matrix.push(new Array(cols));
        }
        sheet.cells.forEach(function (cell) {
            if (cell.r < rows && cell.c < cols) {
                matrix[cell.r][cell.c] = cell;
                self._cellMap.set(cell.r + ',' + cell.c, cell);
            }
        });

        // 渲染行
        for (var rr = 0; rr < rows; rr++) {
            var tr = document.createElement('tr');

            // 行号
            var rowTh = document.createElement('th');
            rowTh.className = 'xlsx-table__row-header';
            rowTh.textContent = (rr + 1);
            tr.appendChild(rowTh);

            for (var cc = 0; cc < cols; cc++) {
                var td = document.createElement('td');
                td.className = 'xlsx-table__cell';
                td.dataset.r = rr;
                td.dataset.c = cc;

                var cellData = matrix[rr][cc];
                if (cellData) {
                    td.textContent = cellData.value !== null ? String(cellData.value) : '';
                    td.dataset.address = cellData.address;
                    td.dataset.type = cellData.type;

                    // 应用样式
                    var st = cellData.style || {};
                    if (st.bold) td.style.fontWeight = '600';
                    if (st.italic) td.style.fontStyle = 'italic';
                    if (st.color) td.style.color = self._formatColor(st.color);
                    if (st.bgColor) td.style.backgroundColor = self._formatColor(st.bgColor, true);
                    if (st.align === 'center') td.style.textAlign = 'center';
                    else if (st.align === 'right') td.style.textAlign = 'right';
                    else td.style.textAlign = 'left';

                    self._domCellMap.set(rr + ',' + cc, td);

                    // 编辑模式：双击编辑
                    if (self._editable) {
                        self._bindCellEdit(td, rr, cc, cellData);
                    }
                }

                tr.appendChild(td);
            }
            tbody.appendChild(tr);
        }

        table.appendChild(tbody);
        wrap.appendChild(table);
        this._bodyEl.innerHTML = '';
        this._bodyEl.appendChild(wrap);

        this._updateStatus(sheet);
    };

    MMFBXlsxViewer.prototype._bindCellEdit = function (td, r, c, cellData) {
        var self = this;
        td.addEventListener('dblclick', function (e) {
            e.preventDefault();
            if (td.getAttribute('contenteditable') === 'true') return;
            td.setAttribute('contenteditable', 'true');
            td.classList.add('is-editing');
            td.focus();
            // 选中全部文本
            var range = document.createRange();
            range.selectNodeContents(td);
            var sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
        });

        td.addEventListener('blur', function () {
            if (td.getAttribute('contenteditable') !== 'true') return;
            td.removeAttribute('contenteditable');
            td.classList.remove('is-editing');
            var newVal = td.textContent.trim();
            var oldVal = cellData.value !== null ? String(cellData.value) : '';
            if (newVal !== oldVal) {
                // 记录变更
                var exists = self._pendingChanges.find(function (ch) {
                    return ch.address === cellData.address;
                });
                if (exists) {
                    exists.value = newVal;
                } else {
                    self._pendingChanges.push({
                        sheet: self._sheets[self._currentSheetIdx].name,
                        address: cellData.address,
                        value: newVal
                    });
                }
                self._updateSaveButton();
            }
        });

        td.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                td.blur();
            } else if (e.key === 'Escape') {
                td.textContent = cellData.value !== null ? String(cellData.value) : '';
                td.blur();
            }
        });
    };

    MMFBXlsxViewer.prototype._toggleEditMode = function () {
        this._editMode = !this._editMode;
        if (this._editBtn) {
            this._editBtn.classList.toggle('is-active', this._editMode);
        }
        // 重新渲染当前 Sheet（编辑模式绑定 dblclick）
        // 注意：编辑模式下即使非 saveEnabled 也能编辑单元格，但是否保存取决于后端
        this._renderSheet(this._currentSheetIdx);
    };

    MMFBXlsxViewer.prototype._saveChanges = function () {
        var self = this;
        if (this._pendingChanges.length === 0) return;

        var payload = JSON.stringify({
            path: this._filePath,
            changes: this._pendingChanges
        });

        if (global.MMFBBridge) {
            global.MMFBBridge.api.saveXlsxCells(payload).then(function (ok) {
                if (ok) {
                    self._pendingChanges = [];
                    self._updateSaveButton();
                    self._flashStatus('已保存');
                    // 保存后重新加载数据
                    if (global.MMFBBridge) {
                        global.MMFBBridge.api.getPreview(self._filePath).then(function (json) {
                            var result = typeof json === 'string' ? JSON.parse(json) : json;
                            if (result && result.data && result.data.sheets) {
                                self._sheets = result.data.sheets;
                                self._pendingChanges = [];
                                self._renderSheet(self._currentSheetIdx);
                                self._renderSheetTabs();
                            }
                        });
                    }
                } else {
                    self._flashStatus('保存失败', true);
                }
            });
        } else {
            alert('[Mock] 保存 ' + this._pendingChanges.length + ' 项变更（bridge 未连接）');
            this._pendingChanges = [];
            this._updateSaveButton();
        }
    };

    MMFBXlsxViewer.prototype._updateSaveButton = function () {
        if (this._saveBtn) {
            this._saveBtn.disabled = this._pendingChanges.length === 0;
            this._saveBtn.textContent = this._pendingChanges.length > 0
                ? '[保存 ' + this._pendingChanges.length + ']'
                : '[保存]';
        }
    };

    MMFBXlsxViewer.prototype._updateStatus = function (sheet) {
        if (this._statusEl) {
            var parts = [
                sheet.name,
                (sheet.maxRow || 0) + ' 行 x ' + (sheet.maxCol || 0) + ' 列',
                sheet.cells.length + ' 单元格'
            ];
            this._statusEl.textContent = parts.join(' | ');
        }
    };

    MMFBXlsxViewer.prototype._updateFooter = function () {
        if (this._footerInfoEl) {
            var sizeStr = this._formatSize(this._fileSize);
            this._footerInfoEl.textContent =
                (this._sheets.length) + ' 个工作表 | ' + sizeStr;
        }
    };

    MMFBXlsxViewer.prototype._flashStatus = function (msg, isError) {
        var self = this;
        if (!this._statusEl) return;
        var prev = this._statusEl.dataset.original || this._statusEl.textContent;
        if (!this._statusEl.dataset.original) {
            this._statusEl.dataset.original = prev;
        }
        this._statusEl.textContent = msg;
        if (isError) this._statusEl.classList.add('is-error');
        setTimeout(function () {
            self._statusEl.textContent = self._statusEl.dataset.original || '';
            self._statusEl.classList.remove('is-error');
        }, 2000);
    };

    MMFBXlsxViewer.prototype.destroy = function () {
        // 清理提示
        if (this._pendingChanges.length > 0) {
            // 不可在此确认（destroy 是清理流程），放弃未保存变更
        }
        this._root.innerHTML = '';
        this._root.className = '';
    };

    // ========== 工具方法 ==========

    MMFBXlsxViewer.prototype._colToLetter = function (idx) {
        var letter = '';
        var n = idx;
        while (n >= 0) {
            letter = String.fromCharCode(65 + (n % 26)) + letter;
            n = Math.floor(n / 26) - 1;
            if (n < 0) break;
        }
        return letter;
    };

    MMFBXlsxViewer.prototype._formatColor = function (raw, isBg) {
        if (!raw || typeof raw !== 'string') return '';
        // 处理 ARGB 格式（8位 hex）或 6位 hex
        var hex = raw.replace(/[^0-9A-Fa-f]/g, '');
        if (hex.length === 8) {
            // 跳过 alpha 通道，转为 #RRGGBB
            hex = hex.substring(2);
        }
        if (hex.length === 6) {
            return '#' + hex;
        }
        return '';
    };

    MMFBXlsxViewer.prototype._formatSize = function (bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / 1024 / 1024).toFixed(1) + ' MB';
    };

    global.MMFBXlsxViewer = MMFBXlsxViewer;

})(window);
