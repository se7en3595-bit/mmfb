/**
 * MMFB History Viewer
 *
 * 职责：
 *   1. 展示最近打开的文件列表
 *   2. 点击重新打开
 *   3. 单条删除 + 清空全部
 *   4. 空状态提示
 */
(function (global) {
    'use strict';

    // 按日期分组
    function groupByDate(records) {
        var groups = [];
        var now = new Date();
        var today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() / 1000;
        var yesterday = today - 86400;

        var bucketToday = { label: '今天', items: [] };
        var bucketYesterday = { label: '昨天', items: [] };
        var bucketEarlier = { label: '更早', items: [] };

        records.forEach(function (rec) {
            var ts = rec.timestamp || 0;
            if (ts >= today) {
                bucketToday.items.push(rec);
            } else if (ts >= yesterday) {
                bucketYesterday.items.push(rec);
            } else {
                bucketEarlier.items.push(rec);
            }
        });

        if (bucketToday.items.length) groups.push(bucketToday);
        if (bucketYesterday.items.length) groups.push(bucketYesterday);
        if (bucketEarlier.items.length) groups.push(bucketEarlier);
        return groups;
    }

    function formatTime(timestamp) {
        var d = new Date(timestamp * 1000);
        var h = d.getHours();
        var m = d.getMinutes();
        return (h < 10 ? '0' + h : h) + ':' + (m < 10 ? '0' + m : m);
    }

    function fileIcon(ext) {
        var map = {
            'pdf': '📄', 'doc': '📝', 'docx': '📝',
            'xls': '📊', 'xlsx': '📊',
            'ppt': '📽', 'pptx': '📽',
            'png': '🖼', 'jpg': '🖼', 'jpeg': '🖼', 'gif': '🖼', 'webp': '🖼', 'svg': '🖼',
            'mp4': '🎬', 'mkv': '🎬', 'avi': '🎬', 'mov': '🎬',
            'mp3': '🎵', 'wav': '🎵', 'flac': '🎵',
            'zip': '📦', 'tar': '📦', 'gz': '📦',
            'md': '📃', 'txt': '📃', 'log': '📃',
            'py': '⌨', 'js': '⌨', 'css': '⌨', 'html': '⌨',
            'glb': '🧊', 'obj': '🧊', 'stl': '🧊',
        };
        return map[(ext || '').toLowerCase()] || '📎';
    }

    var MMFBHistoryViewer = {
        _root: null,
        _records: [],
        _destroyed: false,

        render: function (rootEl) {
            this._root = rootEl;
            this._destroyed = false;
            this._buildShell();
            this._load();
        },

        destroy: function () {
            this._destroyed = true;
            this._root = null;
        },

        _buildShell: function () {
            var el = this._root;
            el.innerHTML =
                '<div class="history-page">' +
                '  <div class="history-header">' +
                '    <h1 class="history-title">打开历史</h1>' +
                '    <div class="history-actions">' +
                '      <span class="history-count"></span>' +
                '      <button class="history-clear-btn" type="button">清除全部</button>' +
                '    </div>' +
                '  </div>' +
                '  <div class="history-body"></div>' +
                '</div>';

            // 清除全部
            var self = this;
            el.querySelector('.history-clear-btn').addEventListener('click', function () {
                self._confirmClear();
            });
        },

        _load: function () {
            var self = this;
            if (!global.MMFBBridge) return;
            global.MMFBBridge.ready().then(function (info) {
                if (info.mode === 'live' && global.MMFBBridge.getHistory) {
                    global.MMFBBridge.getHistory().then(function (records) {
                        self._records = records || [];
                        self._render();
                    }).catch(function () {
                        self._records = [];
                        self._render();
                    });
                } else {
                    self._records = [];
                    self._render();
                }
            }).catch(function () {
                self._render();
            });
        },

        _render: function () {
            if (this._destroyed || !this._root) return;
            var body = this._root.querySelector('.history-body');
            var countEl = this._root.querySelector('.history-count');
            if (!body) return;

            countEl.textContent = this._records.length + ' 个文件';

            if (this._records.length === 0) {
                body.innerHTML =
                    '<div class="history-empty">' +
                    '  <div class="history-empty__icon">🕘</div>' +
                    '  <div class="history-empty__title">暂无打开记录</div>' +
                    '  <div class="history-empty__subtitle">打开过的文件会显示在这里，方便快速回到最近的工作</div>' +
                    '</div>';
                return;
            }

            var groups = groupByDate(this._records);
            var html = '';
            var self = this;
            groups.forEach(function (g) {
                html += '<div class="history-group">';
                html += '<div class="history-group__label">' + g.label + '</div>';
                html += '<ul class="history-list">';
                g.items.forEach(function (rec, idx) {
                    var safePath = _escapeAttr(rec.path || '');
                    var safeName = _escapeHtml(rec.name || '未命名');
                    var safeDir = _escapeHtml(_dirname(rec.path));
                    var icon = fileIcon(rec.ext);
                    var timeStr = rec.timestamp ? formatTime(rec.timestamp) : '';
                    var globalIdx = self._records.indexOf(rec);
                    html += '<li class="history-item" data-path="' + safePath + '" data-idx="' + globalIdx + '">' +
                        '<span class="history-item__icon">' + icon + '</span>' +
                        '<div class="history-item__info">' +
                        '  <span class="history-item__name" title="' + safePath + '">' + safeName + '</span>' +
                        '  <span class="history-item__dir">' + safeDir + '</span>' +
                        '</div>' +
                        '<span class="history-item__time">' + timeStr + '</span>' +
                        '<button class="history-item__del" title="移除" type="button">×</button>' +
                        '</li>';
                });
                html += '</ul></div>';
            });
            body.innerHTML = html;

            // 绑定事件
            var items = body.querySelectorAll('.history-item');
            items.forEach(function (li) {
                li.addEventListener('click', function (e) {
                    // 删除按钮单独处理
                    if (e.target.classList.contains('history-item__del')) return;
                    var p = li.getAttribute('data-path');
                    if (p) self._reopen(p);
                });
            });
            var dels = body.querySelectorAll('.history-item__del');
            dels.forEach(function (btn) {
                btn.addEventListener('click', function (e) {
                    e.stopPropagation();
                    var li = btn.closest('.history-item');
                    if (!li) return;
                    var p = li.getAttribute('data-path');
                    if (p) self._removeItem(p, li);
                });
            });
        },

        _reopen: function (path) {
            var rec = null;
            this._records.forEach(function (r) {
                if (r.path === path) rec = r;
            });
            if (!rec) return;

            // 通过 navigator 逻辑跳转
            if (global.MMFBRouter) {
                global.MMFBRouter.navigate(
                    '/view/' + (rec.ext || 'unknown') +
                    '?file=' + encodeURIComponent(path)
                );
            }
        },

        _removeItem: function (path, liEl) {
            var self = this;
            // 视觉先行
            liEl.style.opacity = '0.3';
            // 调后端移除
            if (global.MMFBBridge && global.MMFBBridge.removeHistoryItem) {
                global.MMFBBridge.removeHistoryItem(path).then(function () {
                    // 移除本地记录并刷新
                    self._records = self._records.filter(function (r) { return r.path !== path; });
                    self._render();
                }).catch(function () {
                    liEl.style.opacity = '1';
                });
            } else {
                liEl.style.opacity = '1';
            }
        },

        _confirmClear: function () {
            if (this._records.length === 0) return;
            var ok = window.confirm('确定要清除全部 ' + this._records.length + ' 条打开历史吗？此操作不可撤销。');
            if (!ok) return;
            var self = this;
            if (global.MMFBBridge && global.MMFBBridge.clearHistory) {
                global.MMFBBridge.clearHistory().then(function () {
                    self._records = [];
                    self._render();
                });
            }
        }
    };

    function _dirname(path) {
        if (!path) return '';
        var idx = path.lastIndexOf('/');
        if (idx < 0) idx = path.lastIndexOf('\\');
        if (idx < 0) return path;
        return path.substring(0, idx);
    }

    function _escapeHtml(s) {
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function _escapeAttr(s) {
        return _escapeHtml(s).replace(/'/g, '&#39;');
    }

    global.MMFBHistoryViewer = MMFBHistoryViewer;

})(window);
