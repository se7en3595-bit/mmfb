/**
 * MMFB Router - 简易前端路由
 *
 * 职责：
 *   1. 解析 location.hash 获取当前路径和查询参数
 *   2. 匹配注册的路由表，调用对应 handler
 *   3. 监听 hashchange 事件实现无刷新导航
 *   4. 管理路由生命周期（destroy 清理）
 *
 * 路由表由各页面模块注册，router 只负责调度。
 *
 * 使用方式:
 *   MMFBRouter.register('/settings', settingsHandler);
 *   MMFBRouter.navigate('/settings');
 *
 * Handler 签名: handler(rootEl, params, query) => { destroy: fn }
 */
(function (global) {
    'use strict';

    var MMFBRouter = {
        _routes: [],
        _currentRoute: null,
        _currentHandler: null,
        _root: null,
        _initialized: false,

        /**
         * 初始化路由
         * @param {HTMLElement} root - 路由挂载点
         */
        init: function (root) {
            this._root = root;
            this._initialized = true;

            // 监听 hash 变化
            global.addEventListener('hashchange', this._onHashChange.bind(this));

            // 解析当前 hash 并渲染
            this._parseHash();
        },

        /**
         * 注册路由
         * @param {string} pattern - 路由模式，支持 :param 占位符
         * @param {Function} handler - 路由处理器 (rootEl, params, query) => { destroy }
         */
        register: function (pattern, handler) {
            var paramNames = [];
            // 将路由模式转为正则
            var regexStr = pattern
                .replace(/:[a-zA-Z_][a-zA-Z0-9_]*/g, function (match) {
                    paramNames.push(match.substring(1));
                    return '([^/]+)';
                })
                .replace(/\//g, '\\/');
            // 确保根路径 / 的匹配
            if (pattern === '/') {
                regexStr = '\\/';
            }
            var regex = new RegExp('^' + regexStr + '$');

            // 移除相同 pattern 的旧注册（后注册优先）
            this._routes = this._routes.filter(function (r) {
                return r.pattern !== pattern;
            });

            this._routes.push({
                pattern: pattern,
                regex: regex,
                paramNames: paramNames,
                handler: handler
            });
        },

        /**
         * 导航到指定路径
         * @param {string} path - 路径（不含 #），如 '/settings' 或 '/view/pdf?file=xxx'
         */
        navigate: function (path) {
            console.log('[Router] navigate called with:', path);
            // 规范化路径
            if (path && path.indexOf('#') === 0) {
                path = path.substring(1);
            }
            var target = '#' + (path || '/');
            console.log('[Router] setting hash to:', target);
            // 更新 hash（会自动触发 hashchange 事件）
            global.location.hash = target;
            // 某些情况下 hash 不变（导航回同一位置），需要手动触发
            this._parseHash();
            console.log('[Router] current route after parse:', this._currentRoute);
            try {
                this.render();
            } catch (e) {
                console.error('[MMFB] render error:', e);
                // 延迟重试一次
                var self = this;
                setTimeout(function () {
                    try { self.render(); } catch (e2) { console.error('[MMFB] render retry error:', e2); }
                }, 50);
            }
        },

        /**
         * 重新渲染当前路由（供外部在数据变更后刷新）
         */
        rerender: function () {
            this.render();
        },

        /**
         * hashchange 回调
         */
        _onHashChange: function () {
            this._parseHash();
            this.render();
        },

        /**
         * 解析当前 hash
         */
        _parseHash: function () {
            var hash = global.location.hash || '#/';
            console.log('[Router] parsing hash:', hash);
            var pathPart = '/';
            var queryPart = '';
            if (hash.length > 1) {
                pathPart = hash.substring(1);
            // Qt setFragment encodes ? -> %3F, = -> %3D
            pathPart = pathPart.replace(/%3F/g, "?");
            pathPart = pathPart.replace(/%3D/g, "=");
                var qIdx = pathPart.indexOf('?');
                if (qIdx >= 0) {
                    queryPart = pathPart.substring(qIdx + 1);
                    pathPart = pathPart.substring(0, qIdx);
                }
            }
            console.log('[Router] parsed pathPart:', pathPart, 'queryPart:', queryPart);

            // 解析 query string
            var query = {};
            if (queryPart) {
                queryPart.split('&').forEach(function (pair) {
                    var eqIdx = pair.indexOf('=');
                    if (eqIdx >= 0) {
                        var k = decodeURIComponent(pair.substring(0, eqIdx));
                        var v = decodeURIComponent(pair.substring(eqIdx + 1));
                        query[k] = v;
                    } else if (pair) {
                        query[decodeURIComponent(pair)] = '';
                    }
                });
            }
            console.log('[Router] final query:', query);

            this._currentRoute = { path: pathPart || '/', query: query };
        },

        /**
         * 匹配并渲染当前路由
         */
        render: function () {
            if (!this._root || !this._currentRoute) return;

            // 清理上一个路由 handler
            if (this._currentHandler && typeof this._currentHandler.destroy === 'function') {
                try {
                    this._currentHandler.destroy();
                } catch (e) {
                    console.warn('[MMFB] route destroy error:', e);
                }
            }
            this._currentHandler = null;

            // 清空视图容器
            this._root.innerHTML = '';

            // 匹配路由
            var route = this._currentRoute;
            for (var i = 0; i < this._routes.length; i++) {
                var r = this._routes[i];
                var match = route.path.match(r.regex);
                if (match) {
                    var params = {};
                    r.paramNames.forEach(function (name, idx) {
                        params[name] = match[idx + 1];
                    });
                    this._destroyed = false;

                    try {
                        this._currentHandler = r.handler(this._root, params, route.query);
                    } catch (e) {
                        console.error('[MMFB] route handler error:', e);
                        this._renderError(e);
                    }
                    return;
                }
            }

            // 未匹配到：显示 404
            if (global.MMFBPages && global.MMFBPages.notFound) {
                this._currentHandler = global.MMFBPages.notFound(this._root, route.path);
            } else {
                this._renderNotFound(route.path);
            }
        },

        /**
         * 渲染 404
         */
        _renderNotFound: function (path) {
            this._root.innerHTML =
                '<div class="empty-state">' +
                '<div class="empty-state__icon">&#10060;</div>' +
                '<div class="empty-state__title">页面未找到</div>' +
                '<div class="empty-state__subtitle">' + path + '</div>' +
                '</div>';
        },

        /**
         * 渲染错误
         */
        _renderError: function (err) {
            this._root.innerHTML =
                '<div class="empty-state">' +
                '<div class="empty-state__icon">&#9888;</div>' +
                '<div class="empty-state__title">渲染出错</div>' +
                '<div class="empty-state__subtitle">' + (err && err.message ? err.message : String(err)) + '</div>' +
                '</div>';
        },

        /**
         * 获取当前路由信息
         */
        getCurrentRoute: function () {
            return this._currentRoute ? Object.assign({}, this._currentRoute) : null;
        },

        /**
         * 获取已注册路由列表（调试用）
         */
        getRoutes: function () {
            return this._routes.map(function (r) { return r.pattern; });
        }
    };

    global.MMFBRouter = MMFBRouter;

})(window);
