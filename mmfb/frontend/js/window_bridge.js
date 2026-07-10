/**
 * MMFB Window Bridge - 窗口标题同步
 *
 * 提供 setTitle(title) 方法，通过 QWebChannel 调用 Python
 * 设置窗口标题（自定义标题栏同步显示）。
 *
 * 调用方式:
 *   MMFBWindow.setTitle('myfile.pdf');
 */
(function (global) {
    'use strict';

    const MMFBWindow = {
        _title: 'MMFB',

        /**
         * 设置窗口标题
         * @param {string} title - 新标题文字
         */
        setTitle: function (title) {
            this._title = title;
            document.title = title;

            // 通过 bridge 同步到 Python 侧（自定义标题栏）
            MMFBBridge.ready().then(function (info) {
                if (info.mode !== 'live') return;
                // 直接调用 Python slot
                if (MMFBBridge._bridge && MMFBBridge._bridge.set_window_title) {
                    try {
                        MMFBBridge._bridge.set_window_title(title);
                    } catch (e) {
                        // 忽略：标题同步非关键操作
                    }
                }
            });
        },

        /**
         * 获取当前标题
         */
        getTitle: function () {
            return this._title;
        }
    };

    global.MMFBWindow = MMFBWindow;

})(window);
