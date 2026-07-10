/**
 * MMFB Navigator - 文件导航调度
 *
 * 职责：
 * 1. 接收 Python 通过 QWebChannel 发出的 filesDropped 信号
 * 2. 更新窗口标题（首次打开时）
 * 3. 将文件分发给对应的路由（路由由后续 Handler 任务注册）
 * 4. 拖拽悬停视觉反馈（给 #router-view 添加/移除 drag-over 类）
 *
 * 当前版本不实现具体预览逻辑，仅提供分发框架：
 *   - 每次 drop 取第一个文件调用 _dispatch()
 *   - 触发 'mmfb:open-file' 自定义事件 + MMFBRouter.navigate()
 */
(function (global) {
    'use strict';

    var MMFBNavigator = {
        _initialized: false,
        _lastFiles: [],
        _rootEl: null,

        /**
         * 初始化：监听 bridge 信号 + 拖拽视觉反馈
         */
        init: function () {
            if (this._initialized) return;
            this._initialized = true;

            this._rootEl = document.getElementById('router-view');
            this._setupDragVisualFeedback();

            // 监听来自 Python 的 filesDropped 信号
            MMFBBridge.ready().then(function (info) {
                if (info.mode !== 'live') return;
                var bridge = MMFBBridge._bridge;
                if (!bridge) return;

                if (bridge.filesDropped) {
                    bridge.filesDropped.connect(function (payload) {
                        MMFBNavigator._onFilesDropped(payload);
                    });
                }
            });

            console.log('[MMFB] navigator ready');
        },

        /**
         * 设置拖拽视觉反馈：dragenter 加 class，dragleave/drop 移除 class
         */
        _setupDragVisualFeedback: function () {
            var self = this;
            var el = this._rootEl;
            if (!el) return;

            var dragCounter = 0;

            el.addEventListener('dragenter', function (e) {
                e.preventDefault();
                dragCounter++;
                el.classList.add('drag-over');
            });

            el.addEventListener('dragleave', function (e) {
                e.preventDefault();
                dragCounter--;
                if (dragCounter <= 0) {
                    dragCounter = 0;
                    el.classList.remove('drag-over');
                }
            });

            el.addEventListener('dragover', function (e) {
                e.preventDefault();
            });

            el.addEventListener('drop', function (e) {
                e.preventDefault();
                dragCounter = 0;
                el.classList.remove('drag-over');
            });
        },

        /**
         * 处理来自 Python 的 filesDropped 信号
         * @param {string} payload - JSON 字符串 {type:"filesDropped", files:[...]}
         */
        _onFilesDropped: function (payload) {
            var data;
            try {
                data = JSON.parse(payload);
            } catch (e) {
                console.warn('[MMFB] invalid filesDropped payload:', e);
                return;
            }

            if (data.type !== 'filesDropped' || !Array.isArray(data.files)) {
                return;
            }

            this._lastFiles = data.files;

            if (data.files.length === 0) return;

            // 更新窗口标题（取第一个文件，多文件时显示 +N）
            var first = data.files[0];
            if (global.MMFBWindow && global.MMFBWindow.setTitle) {
                var title = first.name;
                if (data.files.length > 1) {
                    title += ' (+' + (data.files.length - 1) + ')';
                }
                global.MMFBWindow.setTitle(title);
            }

            // 分发给对应路由
            this._dispatch(first);

            console.log('[MMFB] files dropped:', data.files.length, 'first:', first.name);
        },

        /**
         * 分发文件打开事件
         * - 触发 window 级别的自定义事件 'mmfb:open-file'，附带文件信息
         * - 触发 MMFBRouter.navigate() 尝试路由跳转
         * @param {object} file - 文件信息 {name, path, ext}
         */
        _dispatch: function (file) {
            // 事件机制（Handler 订阅此事件获取文件信息）
            var evt;
            try {
                evt = new CustomEvent('mmfb:open-file', { detail: file });
            } catch (e) {
                // IE 降级（理论上不存在，仅为安全）
                evt = document.createEvent('CustomEvent');
                evt.initCustomEvent('mmfb:open-file', false, false, file);
            }
            window.dispatchEvent(evt);

            // 路由跳转：先尝试 preview/<ext>，若无对应路由则由 app.js 的占位路由处理
            if (global.MMFBRouter) {
                global.MMFBRouter.navigate(
                    '/preview/' + (file.ext || 'unknown') +
                    '?file=' + encodeURIComponent(file.path)
                );
            }
        },

        /**
         * 获取最近一次 drop 的文件列表
         */
        getLastFiles: function () {
            return this._lastFiles;
        }
    };

    global.MMFBNavigator = MMFBNavigator;

})(window);
