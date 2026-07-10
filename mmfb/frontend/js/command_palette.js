/**
 * MMFB Command Palette (Ctrl+K)
 *
 * 命令面板组件, 提供快速跳转、文件操作、窗口/分屏管理。
 *
 * 调用方式:
 *   MMFBCommandPalette.open();
 *   MMFBCommandPalette.close();
 */
(function (global) {
    'use strict';

    // ---- 命令注册表 ----
    var COMMANDS = [
        {
            id: 'open-file',
            label: '打开文件...',
            shortcut: 'Ctrl+O',
            icon: '📂',
            group: '文件',
            action: function () {
                // 通过 Python bridge 打开系统文件选择对话框
                if (global.MMFBBridge && MMFBBridge.api && MMFBBridge.api.openFileDialog) {
                    MMFBBridge.api.openFileDialog().then(function (result) {
                        try {
                            var data = typeof result === 'string' ? JSON.parse(result) : result;
                            if (data && data.path) {
                                if (global.MMFBRouter) {
                                    var ext = data.path.split('.').pop().toLowerCase();
                                    global.MMFBRouter.navigate('/view/' + ext + '?file=' + encodeURIComponent(data.path));
                                }
                            }
                        } catch (e) {
                            console.warn('[MMFB] openFileDialog result error:', e);
                        }
                    });
                }
            }
        },
        {
            id: 'settings',
            label: '设置...',
            shortcut: 'Ctrl+,',
            icon: '⚙️',
            group: '导航',
            action: function () {
                if (global.MMFBRouter) {
                    global.MMFBRouter.navigate('/settings');
                }
            }
        },
        {
            id: 'about',
            label: '关于 MMFB',
            icon: 'ℹ️',
            group: '导航',
            action: function () {
                if (global.MMFBRouter) {
                    global.MMFBRouter.navigate('/about');
                }
            }
        },
        {
            id: 'history',
            label: '打开历史',
            icon: '🕘',
            group: '导航',
            action: function () {
                if (global.MMFBRouter) {
                    global.MMFBRouter.navigate('/history');
                }
            }
        },
        {
            id: 'conversion',
            label: '格式转换',
            icon: '🔁',
            group: '导航',
            action: function () {
                if (global.MMFBRouter) {
                    global.MMFBRouter.navigate('/convert');
                }
            }
        },
        {
            id: 'home',
            label: '返回首页',
            icon: '🏠',
            group: '导航',
            action: function () {
                if (global.MMFBRouter) {
                    global.MMFBRouter.navigate('/');
                }
            }
        },
        {
            id: 'new-window',
            label: '新建窗口',
            shortcut: 'Ctrl+N',
            icon: '🪟',
            group: '窗口',
            action: function () {
                if (global.MMFBLayout) {
                    global.MMFBLayout.openNewWindow();
                }
            }
        },
        {
            id: 'split-on',
            label: '进入分屏模式',
            shortcut: 'Ctrl+`',
            icon: '⫿',
            group: '窗口',
            action: function () {
                if (global.MMFBLayout) {
                    global.MMFBLayout.enterSplitMode();
                }
            }
        },
        {
            id: 'split-off',
            label: '退出分屏模式',
            shortcut: 'Ctrl+`',
            icon: '▣',
            group: '窗口',
            action: function () {
                if (global.MMFBLayout) {
                    global.MMFBLayout.exitSplitMode();
                }
            }
        },
        {
            id: 'immersive-on',
            label: '进入沉浸模式',
            shortcut: 'F11',
            icon: '🖥️',
            group: '视图',
            action: function () {
                if (global.MMFBLayout) {
                    global.MMFBLayout.setImmersiveMode(true);
                }
            }
        },
        {
            id: 'immersive-off',
            label: '退出沉浸模式',
            shortcut: 'F11',
            icon: '🔳',
            group: '视图',
            action: function () {
                if (global.MMFBLayout) {
                    global.MMFBLayout.setImmersiveMode(false);
                }
            }
        },
        {
            id: 'toggle-theme',
            label: '切换主题',
            shortcut: 'Ctrl+Shift+T',
            icon: '🎨',
            group: '视图',
            action: function () {
                if (global.MMFBTheme) {
                    global.MMFBTheme.toggle();
                }
            }
        }
    ];

    var CommandPalette = {
        _el: null,
        _inputEl: null,
        _resultsEl: null,
        _activeIndex: 0,
        _filteredCommands: [],
        _visible: false,

        /**
         * 打开命令面板
         */
        open: function () {
            if (this._visible) return;
            this._visible = true;
            this._activeIndex = 0;
            this._render();
            this._updateResults('');

            var self = this;
            setTimeout(function () {
                if (self._inputEl) {
                    self._inputEl.value = '';
                    self._inputEl.focus();
                }
            }, 50);

            console.log('[MMFB] command palette opened');
        },

        /**
         * 关闭命令面板
         */
        close: function () {
            if (!this._visible) return;
            this._visible = false;

            if (this._el) {
                this._el.remove();
                this._el = null;
                this._inputEl = null;
                this._resultsEl = null;
            }

            if (this._onGlobalKeydown) {
                document.removeEventListener('keydown', this._onGlobalKeydown, true);
                this._onGlobalKeydown = null;
            }

            console.log('[MMFB] command palette closed');
        },

        /**
         * 渲染面板 DOM
         */
        _render: function () {
            var self = this;

            var overlay = document.createElement('div');
            overlay.className = 'command-palette-overlay';

            var panel = document.createElement('div');
            panel.className = 'command-palette';

            var inputWrapper = document.createElement('div');
            inputWrapper.className = 'command-palette__input-wrapper';
            inputWrapper.innerHTML =
                '<span class="command-palette__icon">⌘</span>' +
                '<input type="text" class="command-palette__input" placeholder="搜索命令..." />';

            var resultsList = document.createElement('div');
            resultsList.className = 'command-palette__results';

            panel.appendChild(inputWrapper);
            panel.appendChild(resultsList);
            overlay.appendChild(panel);

            this._el = overlay;
            this._inputEl = inputWrapper.querySelector('input');
            this._resultsEl = resultsList;

            this._inputEl.addEventListener('input', function (e) {
                self._updateResults(e.target.value);
            });

            panel.addEventListener('click', function (e) {
                e.stopPropagation();
            });

            overlay.addEventListener('click', function () {
                self.close();
            });

            this._onGlobalKeydown = function (e) {
                if (e.key === 'Escape') {
                    e.preventDefault();
                    self.close();
                    return;
                }
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    self._moveActive(1);
                    return;
                }
                if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    self._moveActive(-1);
                    return;
                }
                if (e.key === 'Enter') {
                    e.preventDefault();
                    self._executeActive();
                    return;
                }
            };
            document.addEventListener('keydown', this._onGlobalKeydown, true);

            document.body.appendChild(overlay);
        },

        /**
         * 更新搜索结果
         */
        _updateResults: function (query) {
            var q = query.toLowerCase().trim();
            this._filteredCommands = COMMANDS.filter(function (cmd) {
                return cmd.label.toLowerCase().indexOf(q) !== -1 ||
                       (cmd.group && cmd.group.toLowerCase().indexOf(q) !== -1);
            });

            this._activeIndex = 0;
            this._renderResults();
        },

        /**
         * 渲染结果列表
         */
        _renderResults: function () {
            var self = this;
            var el = this._resultsEl;
            if (!el) return;

            el.innerHTML = '';

            if (this._filteredCommands.length === 0) {
                var empty = document.createElement('div');
                empty.className = 'command-palette__empty';
                empty.textContent = '未找到匹配的命令';
                el.appendChild(empty);
                return;
            }

            var groups = {};
            this._filteredCommands.forEach(function (cmd) {
                var g = cmd.group || '其他';
                if (!groups[g]) groups[g] = [];
                groups[g].push(cmd);
            });

            var idx = 0;
            Object.keys(groups).forEach(function (groupName) {
                var groupTitle = document.createElement('div');
                groupTitle.className = 'command-palette__group-title';
                groupTitle.textContent = groupName;
                el.appendChild(groupTitle);

                groups[groupName].forEach(function (cmd) {
                    var item = document.createElement('div');
                    item.className = 'command-palette__item';
                    if (idx === self._activeIndex) {
                        item.classList.add('command-palette__item--active');
                    }

                    var icon = document.createElement('span');
                    icon.className = 'command-palette__item-icon';
                    icon.textContent = cmd.icon || '•';

                    var text = document.createElement('span');
                    text.className = 'command-palette__item-text';
                    text.textContent = cmd.label;

                    item.appendChild(icon);
                    item.appendChild(text);

                    if (cmd.shortcut) {
                        var shortcut = document.createElement('span');
                        shortcut.className = 'command-palette__item-shortcut';
                        shortcut.textContent = cmd.shortcut;
                        item.appendChild(shortcut);
                    }

                    item.addEventListener('mousedown', (function (command) {
                        return function (e) {
                            e.preventDefault();
                            e.stopPropagation();
                            var action = command.action;
                            self.close();
                            // 延迟执行 action，避免 DOM 移除过程中执行导航导致时序问题
                            setTimeout(function () {
                                try {
                                    if (action) action();
                                } catch (err) {
                                    console.error('[MMFB] command action error:', err);
                                }
                            }, 10);
                        };
                    })(cmd));

                    item.addEventListener('mouseenter', (function (i) {
                        return function () {
                            self._activeIndex = i;
                            self._renderResults();
                        };
                    })(idx));

                    el.appendChild(item);
                    idx++;
                });
            });
        },

        /**
         * 移动活动项
         */
        _moveActive: function (delta) {
            var newIndex = this._activeIndex + delta;
            if (newIndex < 0) newIndex = 0;
            if (newIndex >= this._filteredCommands.length) {
                newIndex = this._filteredCommands.length - 1;
            }
            this._activeIndex = newIndex;
            this._renderResults();

            var activeEl = this._resultsEl.querySelector('.command-palette__item--active');
            if (activeEl) {
                activeEl.scrollIntoView({ block: 'nearest' });
            }
        },

        /**
         * 执行当前激活的命令
         */
        _executeActive: function () {
            var cmd = this._filteredCommands[this._activeIndex];
            if (!cmd) return;

            var action = cmd.action;
            this.close();
            setTimeout(function () {
                try {
                    if (action) action();
                } catch (err) {
                    console.error('[MMFB] command action error:', err);
                }
            }, 10);
        },

        /**
         * 返回当前面板是否可见
         */
        isVisible: function () {
            return this._visible;
        }
    };

    global.MMFBCommandPalette = CommandPalette;

})(window);
