/**
 * MMFBThemeManager - 主题管理器
 *
 * 负责三方联动：
 *   1. 当前主题 preferences (document.body data-theme 属性)
 *   2. 系统偏好 (matchMedia prefers-color-scheme)
 *   3. 持久化 (bridge.setTheme)
 *
 * 对外暴露：
 *   MMFBTheme.get()        -> 当前 theme 名
 *   MMFBTheme.set(name)    -> 设置并持久化
 *   MMFBTheme.toggle()     -> 在 light / dark / warm 间轮换
 */
(function (global) {
    'use strict';

    var THEMES = ['light', 'dark', 'warm'];

    var MMFBTheme = {
        _current: 'warm',
        _bridgeReady: false,

        /**
         * 初始化主题
         * 从 bridge 读取持久化的用户偏好，若无则跟随系统
         */
        init: function () {
            var self = this;

            // 1. 先尝试从 bridge 读取持久化偏好
            if (global.MMFBBridge) {
                global.MMFBBridge.ready().then(function (info) {
                    self._bridgeReady = true;

                    // 读取已保存的主题偏好
                    global.MMFBBridge.getTheme().then(function (savedTheme) {
                        if (savedTheme && THEMES.indexOf(savedTheme) !== -1) {
                            self.set(savedTheme, true);
                        } else {
                            // 无保存偏好 -> 跟随系统
                            var sysTheme = self._detectSystemTheme();
                            self.set(sysTheme, true);
                        }
                    }).catch(function () {
                        // bridge 不可用时直接跟随系统
                        var sysTheme = self._detectSystemTheme();
                        self.set(sysTheme, true);
                    });

                    // 注册系统暗色模式变化回调 (Python -> JS)
                    global.MMFBBridge.onSystemThemeChanged = function (isDark) {
                        // 仅在没有显式用户偏好时自动跟随
                        if (!global.MMFBBridge._themeUserSet) {
                            self.set(isDark ? 'dark' : 'light', true);
                        }
                    };

                    // 注册主题变更回调（用于 Python 侧触发前端同步）
                    // 注意：silent=true 避免回写 Python 导致无限循环
                    global.MMFBBridge.onThemeChanged = function (themeName) {
                        if (global.MMFBTheme) {
                            global.MMFBTheme.set(themeName, true);
                        }
                    };

                }).catch(function () {
                    // bridge 不可用 -> 跟随系统
                    var sysTheme = self._detectSystemTheme();
                    self.set(sysTheme, true);
                });
            } else {
                // 无 bridge（独立调试模式）
                var sysTheme = this._detectSystemTheme();
                this.set(sysTheme, true);
            }

            // 2. 监听前端 prefers-color-scheme 变化（作为 Python 检测的兜底）
            this._listenSystemThemeChange();
        },

        /**
         * 获取当前主题
         */
        get: function () {
            return this._current;
        },

        /**
         * 设置主题并切换 CSS 类
         * @param {string} name  - 'light' | 'dark' | 'warm'
         * @param {boolean} silent - 是否跳过持久化（初始化时使用）
         */
        set: function (name, silent) {
            if (THEMES.indexOf(name) === -1) return;
            if (name === this._current) {
                // 主题未变化：仅在非静默模式下回写持久化
                if (!silent && global.MMFBBridge) {
                    global.MMFBBridge._themeUserSet = true;
                    global.MMFBBridge.setTheme(name);
                }
                return;
            }

            var previous = this._current;
            this._current = name;

            // 应用过渡动画
            document.body.classList.add('theme-transition');
            document.body.setAttribute('data-theme', name);

            // 延迟移除过渡类
            clearTimeout(this._transitionTimer);
            this._transitionTimer = setTimeout(function () {
                document.body.classList.remove('theme-transition');
            }, 300);

            // 持久化
            if (!silent && global.MMFBBridge) {
                global.MMFBBridge._themeUserSet = true;
                global.MMFBBridge.setTheme(name);
            }

            console.log('[MMFB] theme changed: ' + previous + ' -> ' + name);
        },

        /**
         * 轮换主题：light -> warm -> dark -> light
         */
        toggle: function () {
            var idx = THEMES.indexOf(this._current);
            var next = THEMES[(idx + 1) % THEMES.length];
            this.set(next, false);
        },

        /**
         * 获取所有可选主题（给 UI 渲染用）
         */
        getAll: function () {
            return THEMES.slice();
        },

        // ------------------------------------------------------------------
        //  内部方法
        // ------------------------------------------------------------------

        /**
         * 检测系统颜色方案
         * @returns 'dark' | 'light'
         */
        _detectSystemTheme: function () {
            if (global.matchMedia && global.matchMedia('(prefers-color-scheme: dark)').matches) {
                return 'dark';
            }
            return 'light';
        },

        /**
         * 监听系统颜色方案变化（兜底机制）
         */
        _listenSystemThemeChange: function () {
            if (!global.matchMedia) return;

            var mql = global.matchMedia('(prefers-color-scheme: dark)');
            var self = this;

            var handler = function (e) {
                // 仅在用户未设置显式偏好时自动跟随
                if (!global.MMFBBridge || !global.MMFBBridge._themeUserSet) {
                    self.set(e.matches ? 'dark' : 'light', true);
                }
            };

            // 新 API / 旧 API 兼容
            if (mql.addEventListener) {
                mql.addEventListener('change', handler);
            } else if (mql.addListener) {
                mql.addListener(handler);
            }
        }
    };

    global.MMFBTheme = MMFBTheme;

})(window);
