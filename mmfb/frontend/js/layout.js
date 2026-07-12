/**
 * MMFB Layout - 三栏布局组件
 *
 * 负责渲染顶栏和底栏，并提供更新接口供其他模块调用。
 *
 * 顶栏：左侧导航按钮 + 中间标题 + 右侧操作按钮
 * 底栏：左侧状态信息 + 右侧版本号
 *
 * 支持沉浸式模式（顶栏默认隐藏，鼠标触顶显示）。
 */
(function (global) {
    'use strict';

    var HEADER_HOTZONE_PX = 40;  // 顶部触发区高度
    var AUTOHIDE_DELAY_MS = 2000; // 自动隐藏延时

    var MMFBLayout = {
        _headerEl: null,
        _footerEl: null,
        _titleEl: null,
        _footerLeftEl: null,
        _footerRightEl: null,
        _immersiveMode: false,
        _hideTimer: null,
        _mouseInHotzone: false,
        _headerVisible: true,
        _splitMode: false,

        /**
         * 初始化布局，渲染顶栏和底栏
         */
        init: function () {
            var app = document.getElementById('app');
            if (!app) return;

            // 取出 router-view，重新组织 DOM
            var routerView = document.getElementById('router-view');
            if (!routerView) return;

            // 清空 #app
            app.innerHTML = '';

            // 顶栏
            this._headerEl = document.createElement('header');
            this._headerEl.className = 'layout-header';
            this._headerEl.innerHTML =
                '<div class="layout-header__left">' +
                '<button class="layout-header__btn" data-route="/" title="首页">&#8962;</button>' +
                '<button class="layout-header__btn" data-route="/history" title="打开历史 (H)">&#8983;</button>' +
                '</div>' +
                '<div class="layout-header__center" id="layout-title">MMFB</div>' +
                '<div class="layout-header__right">' +
                '<button class="layout-header__btn" data-action="toggle-split" title="分屏模式 (Ctrl+`)">&#9645;</button>' +
                '<button class="layout-header__btn" data-action="new-window" title="新窗口 (Ctrl+N)">&#9729;</button>' +
                '<button class="layout-header__btn" data-route="/convert" title="格式转换">&#128268;</button>' +
                '<button class="layout-header__btn" data-route="/settings" title="设置">&#9881;</button>' +
                '<button class="layout-header__btn" data-route="/about" title="关于">&#128736;</button>' +
                '<button class="layout-header__btn" data-action="cmd-palette" title="命令面板 (Ctrl+K)">&#8984;</button>' +
                '</div>';
            app.appendChild(this._headerEl);

            // 主区域容器
            var main = document.createElement('main');
            main.className = 'layout-main';
            main.appendChild(routerView);
            app.appendChild(main);

            // 底栏
            this._footerEl = document.createElement('footer');
            this._footerEl.className = 'layout-footer';
            this._footerEl.innerHTML =
                '<div class="layout-footer__left" id="footer-left"></div>' +
                '<div class="layout-footer__right" id="footer-right">MMFB v1.0</div>';
            app.appendChild(this._footerEl);

            // 缓存引用
            this._titleEl = document.getElementById('layout-title');
            this._footerLeftEl = document.getElementById('footer-left');
            this._footerRightEl = document.getElementById('footer-right');

            // 绑定顶栏按钮事件
            this._bindHeaderButtons();

            // 绑定沉浸式鼠标事件
            this._bindImmersiveEvents();

            console.log('[MMFB] layout ready');
        },

        /**
         * 绑定顶栏导航按钮点击
         */
        _bindHeaderButtons: function () {
            var self = this;
            var btns = this._headerEl.querySelectorAll('[data-route]');
            btns.forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var route = btn.getAttribute('data-route');
                    if (global.MMFBRouter) {
                        global.MMFBRouter.navigate(route);
                    }
                });
            });

            // 命令面板按钮
            var cmdBtn = this._headerEl.querySelector('[data-action="cmd-palette"]');
            if (cmdBtn) {
                cmdBtn.addEventListener('click', function () {
                    if (global.MMFBCommandPalette) {
                        global.MMFBCommandPalette.open();
                    }
                });
            }

            // 分屏切换按钮
            var splitBtn = this._headerEl.querySelector('[data-action="toggle-split"]');
            if (splitBtn) {
                splitBtn.addEventListener('click', function () {
                    self.toggleSplitMode();
                });
            }

            // 新窗口按钮
            var newBtn = this._headerEl.querySelector('[data-action="new-window"]');
            if (newBtn) {
                newBtn.addEventListener('click', function () {
                    self.openNewWindow();
                });
            }
        },

        /**
         * 绑定沉浸式鼠标追踪事件
         */
        _bindImmersiveEvents: function () {
            var self = this;

            // 全局 mousemove 监听
            document.addEventListener('mousemove', function (e) {
                if (!self._immersiveMode) return;
                self._handleMouseMove(e.clientY);
            }, { passive: true });

            // 鼠标离开视口时启动隐藏定时器
            document.addEventListener('mouseleave', function () {
                if (!self._immersiveMode) return;
                self._hideHeaderAfterDelay();
            }, { passive: true });
        },

        /**
         * 处理鼠标移动（沉浸式模式）
         */
        _handleMouseMove: function (clientY) {
            var inHotzone = clientY <= HEADER_HOTZONE_PX;

            if (inHotzone && !this._mouseInHotzone) {
                this._mouseInHotzone = true;
                this._showHeader();
            } else if (!inHotzone && this._mouseInHotzone) {
                this._mouseInHotzone = false;
                this._hideHeaderAfterDelay();
            }
        },

        /**
         * 显示顶栏
         */
        _showHeader: function () {
            if (!this._headerEl) return;
            this._headerVisible = true;

            // 移除沉浸模式 CSS 类 -> 顶栏回到正常布局流
            this._headerEl.classList.add('layout-header--show');

            clearTimeout(this._hideTimer);
        },

        /**
         * 启动延时隐藏定时器
         */
        _hideHeaderAfterDelay: function () {
            var self = this;
            clearTimeout(this._hideTimer);
            this._hideTimer = setTimeout(function () {
                self._hideHeader();
            }, AUTOHIDE_DELAY_MS);
        },

        /**
         * 隐藏顶栏
         */
        _hideHeader: function () {
            if (!this._headerEl) return;
            this._headerVisible = false;
            this._headerEl.classList.remove('layout-header--show');

            clearTimeout(this._hideTimer);
        },

        /**
         * 开关沉浸式模式
         * @param {boolean} enabled
         */
        setImmersiveMode: function (enabled) {
            this._immersiveMode = enabled;

            if (enabled) {
                // 启用沉浸：顶栏初始隐藏
                this._headerEl.classList.add('layout-header--immersive');
                this._hideHeader();
            } else {
                // 退出沉浸：移除沉浸 CSS 类并显示顶栏
                this._headerEl.classList.remove('layout-header--immersive');
                this._showHeader();
            }
        },

        /**
         * 进入 / 退出分屏模式
         */
        toggleSplitMode: function () {
            if (this._splitMode) {
                this.exitSplitMode();
            } else {
                this.enterSplitMode();
            }
        },

        /**
         * 进入分屏模式
         */
        enterSplitMode: function () {
            if (this._splitMode) return;
            this._splitMode = true;

            // 调用 bridge API
            if (global.MMFBBridge) {
                global.MMFBBridge.toggleSplit().then(function (data) {
                    console.log('[MMFB] split toggled:', data);
                });
            }

            // 更新顶栏 UI：分屏按钮高亮
            var splitBtn = this._headerEl
                ? this._headerEl.querySelector('[data-action="toggle-split"]')
                : null;
            if (splitBtn) {
                splitBtn.classList.add('active');
            }

            this.setFooterLeft('[分屏模式]');
        },

        /**
         * 退出分屏模式
         */
        exitSplitMode: function () {
            if (!this._splitMode) return;
            this._splitMode = false;

            if (global.MMFBBridge) {
                global.MMFBBridge.toggleSplit().then(function (data) {
                    console.log('[MMFB] exited split:', data);
                });
            }

            // 更新顶栏 UI：分屏按钮取消高亮
            var splitBtn = this._headerEl
                ? this._headerEl.querySelector('[data-action="toggle-split"]')
                : null;
            if (splitBtn) {
                splitBtn.classList.remove('active');
            }

            this.setFooterLeft('');
        },

        /**
         * 从 bridge 通知同步分屏状态
         * @param {boolean} split
         */
        setSplitMode: function (split) {
            if (this._splitMode === split) return;
            this._splitMode = !!split;

            var splitBtn = this._headerEl
                ? this._headerEl.querySelector('[data-action="toggle-split"]')
                : null;
            if (splitBtn) {
                if (split) {
                    splitBtn.classList.add('active');
                } else {
                    splitBtn.classList.remove('active');
                }
            }

            this.setFooterLeft(split ? '[分屏模式]' : '');
        },

        /**
         * 新建窗口
         */
        openNewWindow: function () {
            // 优先调用 bridge API 新建原生窗口
            if (global.MMFBBridge) {
                global.MMFBBridge.newWindow().then(function (data) {
                    if (!data || !data.ok) {
                        console.warn('[MMFB] newWindow failed:', data);
                    }
                });
            }
        },

        /**
         * 更新顶栏标题
         * @param {string} title
         */
        setTitle: function (title) {
            if (this._titleEl) {
                this._titleEl.textContent = title;
            }
        },

        /**
         * 更新底栏左侧状态
         * @param {string} text
         */
        setFooterLeft: function (text) {
            if (this._footerLeftEl) {
                this._footerLeftEl.textContent = text;
            }
        },

        /**
         * 更新底栏右侧信息
         * @param {string} text
         */
        setFooterRight: function (text) {
            if (this._footerRightEl) {
                this._footerRightEl.textContent = text;
            }
        },

        /**
         * 高亮当前路由对应的顶栏按钮
         * @param {string} route - 当前路由路径
         */
        setActiveRoute: function (route) {
            if (!this._headerEl) return;
            var btns = this._headerEl.querySelectorAll('[data-route]');
            btns.forEach(function (btn) {
                var btnRoute = btn.getAttribute('data-route');
                if (btnRoute === route || (route.indexOf(btnRoute) === 0 && btnRoute !== '/')) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });
        }
    };

    global.MMFBLayout = MMFBLayout;

})(window);
