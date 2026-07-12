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

        // 亮度/对比度调节
        this._brightness = 1.0;
        this._contrast = 1.0;

        // 文字颜色覆盖（null=默认/跟随原始颜色，否则为 '#rrggbb'）
        this._textColorOverride = null;

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

        // 亮度/对比度按钮
        var adjBtn = document.createElement('button');
        adjBtn.className = 'xlsx-viewer__adjust-btn';
        adjBtn.textContent = '◐';
        adjBtn.title = '亮度/对比度';
        adjBtn.addEventListener('click', function () {
            self._showAdjustDialog();
        });
        toolbar.querySelector('.xlsx-viewer__toolbar-right').prepend(adjBtn);
        this._adjustBtn = adjBtn;

        // 文字颜色切换按钮
        var colorBtn = document.createElement('button');
        colorBtn.className = 'xlsx-viewer__color-btn';
        colorBtn.textContent = 'A';
        colorBtn.title = '切换文字颜色';
        colorBtn.addEventListener('click', function (ev) {
            ev.stopPropagation();
            self._showColorPanel();
        });
        toolbar.querySelector('.xlsx-viewer__toolbar-right').prepend(colorBtn);
        this._colorBtn = colorBtn;

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
        var self = this;
        this._bodyEl.innerHTML =
            '<div class="xlsx-viewer__empty" style="cursor: pointer;" title="双击以初始化并编辑工作表">' +
            '<div class="xlsx-viewer__empty-icon">&#128203;</div>' +
            '<div class="xlsx-viewer__empty-title">无可预览数据</div>' +
            (this._editable ? '<div class="xlsx-viewer__empty-hint" style="font-size: 12px; color: var(--color-text-muted); margin-top: 8px;">双击以初始化默认工作表并开始编辑</div>' : '') +
            '</div>';

        if (this._editable) {
            var emptyEl = this._bodyEl.querySelector('.xlsx-viewer__empty');
            if (emptyEl) {
                emptyEl.addEventListener('dblclick', function() {
                    var newSheet = {
                        name: 'Sheet1',
                        title: 'Sheet1',
                        maxRow: 10,
                        maxCol: 5,
                        cells: []
                    };
                    for (var r = 0; r < 10; r++) {
                        for (var c = 0; c < 5; c++) {
                            var addr = self._colToLetter(c) + (r + 1);
                            newSheet.cells.push({
                                r: r,
                                c: c,
                                address: addr,
                                value: '',
                                type: 's',
                                style: {}
                            });
                        }
                    }
                    self._sheets = [newSheet];
                    self._currentSheetIdx = 0;
                    self._renderSheetTabs();
                    self._renderSheet(0);
                });
            }
        }
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
            var self = this;
            this._bodyEl.innerHTML =
                '<div class="xlsx-viewer__empty" style="cursor: pointer;" title="双击以初始化并编辑工作表">' +
                '<div class="xlsx-viewer__empty-title">工作表 "' + sheet.name + '" 为空</div>' +
                (this._editable ? '<div class="xlsx-viewer__empty-hint" style="font-size: 12px; color: var(--color-text-muted); margin-top: 8px;">双击以初始化表格并开始编辑</div>' : '') +
                '</div>';

            if (this._editable) {
                var emptyEl = this._bodyEl.querySelector('.xlsx-viewer__empty');
                if (emptyEl) {
                    emptyEl.addEventListener('dblclick', function() {
                        sheet.maxRow = 10;
                        sheet.maxCol = 5;
                        sheet.cells = [];
                        for (var r = 0; r < 10; r++) {
                            for (var c = 0; c < 5; c++) {
                                var addr = self._colToLetter(c) + (r + 1);
                                sheet.cells.push({
                                    r: r,
                                    c: c,
                                    address: addr,
                                    value: '',
                                    type: 's',
                                    style: {}
                                });
                            }
                        }
                        self._renderSheet(idx);
                    });
                }
            }
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

    /**
     * 应用亮度/对比度 filter 到表格区域
     * CSS filter 在 GPU 层合成，对 table 渲染性能影响可忽略
     */
    MMFBXlsxViewer.prototype._applyFilter = function () {
        if (!this._bodyEl) return;
        var parts = [];
        if (this._brightness !== 1.0) parts.push('brightness(' + this._brightness.toFixed(2) + ')');
        if (this._contrast !== 1.0) parts.push('contrast(' + this._contrast.toFixed(2) + ')');
        this._bodyEl.style.filter = parts.length > 0 ? parts.join(' ') : '';
    };

    /**
     * 将当前 _textColorOverride 应用到所有可见单元格
     * 如果 override 为 null，恢复到原始颜色（通过重新渲染实现）
     */
    MMFBXlsxViewer.prototype._applyTextColor = function () {
        var self = this;
        if (this._textColorOverride === null) {
            // 恢复默认：重新渲染当前 Sheet
            this._renderSheet(this._currentSheetIdx);
            return;
        }
        // 覆盖模式：遍历所有已渲染单元格
        this._domCellMap.forEach(function (td) {
            td.style.color = self._textColorOverride;
        });
        if (this._colorBtn) {
            this._colorBtn.style.borderBottomColor = this._textColorOverride;
            this._colorBtn.classList.add('is-override');
        }
    };

    /**
     * 文字颜色选择面板 — 弹出浮层，8 个常用色 + "默认"
     */
    MMFBXlsxViewer.prototype._showColorPanel = function () {
        var self = this;
        var host = this._root.querySelector('.xlsx-viewer__toolbar-right');
        var old = host.querySelector('.xlsx-color-panel');
        if (old) { old.remove(); return; }

        var palette = [
            { name: '默认', val: null },
            { name: '#1A1A1E', val: '#1A1A1E' },   // 近黑（Light/Warm 主题适用）
            { name: '#FFFFFF', val: '#FFFFFF' },   // 白（Dark 主题适用）
            { name: '#E74C3C', val: '#E74C3C' },   // 红
            { name: '#3498DB', val: '#3498DB' },   // 蓝
            { name: '#2ECC71', val: '#2ECC71' },   // 绿
            { name: '#F39C12', val: '#F39C12' },   // 橙
            { name: '#9B59B6', val: '#9B59B6' }    // 紫
        ];

        var html = '<div class="xlsx-color-panel">';
        palette.forEach(function (item) {
            var label = item.val === null ? '默认'
                : '<span class="xlsx-color-panel__swatch" style="background:' + item.val + '"></span>' + item.name;
            var cls = 'xlsx-color-panel__item' +
                ((self._textColorOverride === item.val) ? ' is-active' : '');
            html += '<button class="' + cls + '" data-val="' + (item.val || '') + '">' + label + '</button>';
        });
        html += '</div>';

        var div = document.createElement('div');
        div.innerHTML = html;
        var panel = div.firstElementChild;
        host.appendChild(panel);

        var items = panel.querySelectorAll('.xlsx-color-panel__item');
        for (var i = 0; i < items.length; i++) {
            (function (btn) {
                btn.addEventListener('click', function () {
                    var v = btn.getAttribute('data-val');
                    self._textColorOverride = v === '' ? null : v;
                    self._applyTextColor();
                    panel.remove();
                });
            })(items[i]);
        }

        setTimeout(function () {
            document.addEventListener('mousedown', function outside(ev) {
                if (self._colorBtn && self._colorBtn.contains(ev.target)) return;
                if (panel.contains(ev.target)) return;
                panel.remove();
                document.removeEventListener('mousedown', outside);
            });
        }, 100);
    };

    /**
     * 亮度/对比度调节弹窗
     */
    MMFBXlsxViewer.prototype._showAdjustDialog = function () {
        var self = this;
        var host = this._root.querySelector('.xlsx-viewer__toolbar-right');
        var old = host.querySelector('.xlsx-adjust-dialog');
        if (old) old.remove();

        var html =
            '<div class="xlsx-adjust-dialog">' +
            '<div class="xlsx-adjust-dialog__row">' +
            '<label>亮度</label>' +
            '<input type="range" id="xlsx-adj-brightness" min="0.3" max="2.0" step="0.05" value="' + this._brightness + '">' +
            '<span class="xlsx-adjust-dialog__val" id="xlsx-adj-brightness-val">' + this._brightness.toFixed(2) + '</span>' +
            '</div>' +
            '<div class="xlsx-adjust-dialog__row">' +
            '<label>对比度</label>' +
            '<input type="range" id="xlsx-adj-contrast" min="0.3" max="2.0" step="0.05" value="' + this._contrast + '">' +
            '<span class="xlsx-adjust-dialog__val" id="xlsx-adj-contrast-val">' + this._contrast.toFixed(2) + '</span>' +
            '</div>' +
            '<div class="xlsx-adjust-dialog__actions">' +
            '<button class="xlsx-adjust-dialog__btn xlsx-adjust-dialog__btn--reset" id="xlsx-adj-reset">重置</button>' +
            '<button class="xlsx-adjust-dialog__btn xlsx-adjust-dialog__btn--close" id="xlsx-adj-close">关闭</button>' +
            '</div>' +
            '</div>';

        var div = document.createElement('div');
        div.innerHTML = html;
        var dlg = div.firstElementChild;
        host.appendChild(dlg);

        var bInput = dlg.querySelector('#xlsx-adj-brightness');
        var cInput = dlg.querySelector('#xlsx-adj-contrast');
        var bVal = dlg.querySelector('#xlsx-adj-brightness-val');
        var cVal = dlg.querySelector('#xlsx-adj-contrast-val');

        var updateFilter = function () {
            self._brightness = parseFloat(bInput.value);
            self._contrast = parseFloat(cInput.value);
            bVal.textContent = self._brightness.toFixed(2);
            cVal.textContent = self._contrast.toFixed(2);
            self._applyFilter();
        };

        bInput.addEventListener('input', updateFilter);
        cInput.addEventListener('input', updateFilter);

        dlg.querySelector('#xlsx-adj-reset').addEventListener('click', function () {
            self._brightness = 1.0;
            self._contrast = 1.0;
            bInput.value = 1.0;
            cInput.value = 1.0;
            bVal.textContent = '1.00';
            cVal.textContent = '1.00';
            self._applyFilter();
        });

        dlg.querySelector('#xlsx-adj-close').addEventListener('click', function () { dlg.remove(); });

        setTimeout(function () {
            document.addEventListener('mousedown', function outside(ev) {
                if (self._adjustBtn && self._adjustBtn.contains(ev.target)) return;
                if (dlg.contains(ev.target)) return;
                dlg.remove();
                document.removeEventListener('mousedown', outside);
            });
        }, 100);
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
        var hex = raw.replace(/[^0-9A-Fa-f]/g, '');
        if (hex.length === 8) {
            // ARGB 格式：alpha 为 00 表示"自动"颜色，须跳过
            var alpha = hex.substring(0, 2);
            hex = hex.substring(2);
            if (alpha === '00') return '';
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
