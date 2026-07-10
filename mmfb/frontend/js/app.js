/**
 * MMFB App - 应用入口
 *
 * 启动顺序：
 *     1. 初始化三栏布局（顶栏 / 底栏）
 *     2. 初始化路由，挂载路由容器
 *     3. 注册路由表（home / view / settings / about / history）
 *     4. 初始化 bridge（异步，不阻塞首屏）
 *     5. 初始化文件导航（接收拖拽信号）
 *     6. 绑定沉浸式 UI 信号 + 多窗口信号 + 分屏信号
 *     7. 绑定前端快捷键（Ctrl+K / Ctrl+, / Ctrl+N）
 */
(function (global) {
    'use strict';

    var MMFBApp = {
        _started: false,

        /**
         * 启动应用
         */
        start: function () {
            if (this._started) return;
            this._started = true;

            // 1. 初始化布局
            if (global.MMFBLayout) {
                global.MMFBLayout.init();
            }

            // 2. 初始化路由
            var root = document.getElementById('router-view');
            if (!root) return;

            global.MMFBRouter.init(root);

            // 3. 注册路由表
            this._registerRoutes();

            // 4. 初始化 bridge（异步）
            this._initBridge();

            // 5. 初始化文件导航
            if (global.MMFBNavigator) {
                global.MMFBNavigator.init();
            }

            // 6. 绑定沉浸式 UI 信号 + 多窗口 / 分屏信号
            this._bindImmersiveSignals();
            this._bindMultiWindowSignals();
            this._bindSplitSignals();

            // 7. 绑定前端快捷键（Ctrl+K / Ctrl+, / Ctrl+N）
            this._bindKeyboardShortcuts();

            console.log('[MMFB] app started');
        },

        /**
         * 注册所有路由
         */
        _registerRoutes: function () {
            // 首页 / 空状态
            global.MMFBRouter.register('/', function (root, params, query) {
                return MMFBPages.home(root, params, query);
            });

            // 文件预览（路径参数 ext + 查询参数 file）
            global.MMFBRouter.register('/view/:ext', function (root, params, query) {
                return MMFBPages.view(root, params, query);
            });

            // 兼容旧路由 /preview/:ext（重定向到 /view/:ext）
            global.MMFBRouter.register('/preview/:ext', function (root, params, query) {
                global.MMFBRouter.navigate('/view/' + params.ext + (query.file ? '?file=' + encodeURIComponent(query.file) : ''));
                return { destroy: function () {} };
            });

            // 打开历史页
            global.MMFBRouter.register('/history', function (root, params, query) {
                return MMFBPages.history(root, params, query);
            });

            // 设置页
            global.MMFBRouter.register('/settings', function (root, params, query) {
                return MMFBPages.settings(root, params, query);
            });

            // 关于页
            global.MMFBRouter.register('/about', function (root, params, query) {
                return MMFBPages.about(root, params, query);
            });

            // 格式转换页
            global.MMFBRouter.register('/convert', function (root, params, query) {
                return MMFBPages.conversion(root, params, query);
            });
        },

        /**
         * 初始化 QWebChannel bridge
         */
        _initBridge: function () {
            if (!global.MMFBBridge) return;

            global.MMFBBridge.ready().then(function (info) {
                console.log('[MMFB] bridge ready, mode:', info.mode);

                // 设置顶栏标题显示 bridge 状态
                if (info.mode === 'live') {
                    if (global.MMFBLayout) {
                        global.MMFBLayout.setFooterRight('MMFB v1.0 | bridge: live');
                    }
                }

                // 查询窗口状态（分屏 / 窗口数）
                if (global.MMFBBridge) {
                    global.MMFBBridge.getWindowState().then(function (state) {
                        if (state && typeof state.split === 'boolean') {
                            if (global.MMFBLayout) {
                                global.MMFBLayout.setSplitMode(state.split);
                            }
                        }
                    });
                }

                // 启动自动更新检查（跳过 check_updates=false 的用户）
                if (global.MMFBUpdateDialog) {
                    global.MMFBUpdateDialog.checkOnStartup();
                }

                // 初始化主题（需要 bridge 就绪）
                if (global.MMFBTheme) {
                    global.MMFBTheme.init();
                }
            }).catch(function (err) {
                console.warn('[MMFB] bridge init failed:', err);
            });
        },

        /**
         * 绑定沉浸式 UI 信号（Python -> JS）
         */
        _bindImmersiveSignals: function () {
            if (!global.MMFBBridge) return;

            // 顶栏显隐信号
            global.MMFBBridge.onHeaderVisibilityChanged = function (visible) {
                if (global.MMFBLayout) {
                    if (visible) {
                        global.MMFBLayout._showHeader();
                    } else {
                        global.MMFBLayout._hideHeader();
                    }
                }
            };

            // 命令面板信号（Ctrl+K）
            global.MMFBBridge.onShowCommandPanel = function () {
                if (global.MMFBCommandPalette) {
                    global.MMFBCommandPalette.open();
                }
            };

            // 设置页信号（Ctrl+,）
            global.MMFBBridge.onOpenSettings = function () {
                if (global.MMFBRouter) {
                    global.MMFBRouter.navigate('/settings');
                }
            };
        },

        /**
         * 绑定多窗口信号
         */
        _bindMultiWindowSignals: function () {
            if (!global.MMFBBridge) return;

            // 新窗口请求（Python Ctrl+N 透传出来）
            global.MMFBBridge.onNewWindowRequested = function () {
                // 这里可以显示一个 toast 提示
                if (global.MMFBLayout) {
                    global.MMFBLayout.openNewWindow();
                }
            };

            // 窗口计数变更
            global.MMFBBridge.onWindowCountChanged = function (count) {
                console.log('[MMFB] window count:', count);
            };
        },

        /**
         * 绑定分屏信号
         */
        _bindSplitSignals: function () {
            if (!global.MMFBBridge) return;

            global.MMFBBridge.onSplitModeChanged = function (split) {
                if (global.MMFBLayout) {
                    global.MMFBLayout.setSplitMode(split);
                }
            };
        },

        /**
         * 绑定前端快捷键（当 Python 侧未捕获时的前端兜底）
         */
        _bindKeyboardShortcuts: function () {
            document.addEventListener('keydown', function (e) {
                // Ctrl+K -> 命令面板
                if (e.key === 'k' && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault();
                    if (global.MMFBCommandPalette) {
                        if (global.MMFBCommandPalette.isVisible()) {
                            global.MMFBCommandPalette.close();
                        } else {
                            global.MMFBCommandPalette.open();
                        }
                    }
                    return;
                }

                // Ctrl+, -> 设置页
                if (e.key === ',' && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault();
                    if (global.MMFBRouter) {
                        global.MMFBRouter.navigate('/settings');
                    }
                    return;
                }

                // Ctrl+O -> 打开文件
                if (e.key === 'o' && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault();
                    if (global.MMFBCommandPalette) {
                        global.MMFBCommandPalette.open();
                    }
                    return;
                }

                // Ctrl+N -> 新建窗口
                if (e.key === 'n' && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault();
                    if (global.MMFBLayout) {
                        global.MMFBLayout.openNewWindow();
                    }
                    return;
                }

                // Ctrl+` -> 切换分屏
                if (e.key === '`' && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault();
                    if (global.MMFBLayout) {
                        global.MMFBLayout.toggleSplitMode();
                    }
                    return;
                }
            });
        }
    };

    global.MMFBApp = MMFBApp;

    // DOM 就绪后启动
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            MMFBApp.start();
        });
    } else {
        MMFBApp.start();
    }

})(window);
