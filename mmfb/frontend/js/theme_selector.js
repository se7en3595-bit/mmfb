/**
 * MMFB Theme Selector - 主题选择器组件
 *
 * 渲染三套主题选项供用户选择。
 * 配合 MMFBTheme 使用：点击选项切换主题并持久化。
 *
 * 使用：
 *   MMFBThemeSelector.render(containerEl);
 */
(function (global) {
    'use strict';

    var MMFBThemeSelector = {
        _root: null,

        /**
         * 渲染选择器到指定容器
         * @param {HTMLElement} root
         */
        render: function (root) {
            this._root = root;
            this._root.innerHTML = this._buildHTML();
            this._bindEvents();
            this._updateActiveState();
        },

        /**
         * 销毁（清理引用，不一定会移除 DOM）
         */
        destroy: function () {
            this._root = null;
        },

        // ----------------------------------------------------------------

        _buildHTML: function () {
            return (
                '<div class="theme-selector">' +
                '  <h3>主题外观</h3>' +
                '  <p class="theme-selector__desc">选择应用的主题颜色，温暖舒适的暖纸色，或跟随系统暗色模式。</p>' +
                '  <div class="theme-selector__options">' +
                '    <div class="theme-selector__option" data-theme="light">' +
                '      <div class="theme-selector__swatch theme-selector__swatch--light"></div>' +
                '      <div class="theme-selector__name">明亮</div>' +
                '    </div>' +
                '    <div class="theme-selector__option" data-theme="dark">' +
                '      <div class="theme-selector__swatch theme-selector__swatch--dark"></div>' +
                '      <div class="theme-selector__name">暗黑</div>' +
                '    </div>' +
                '    <div class="theme-selector__option" data-theme="warm">' +
                '      <div class="theme-selector__swatch theme-selector__swatch--warm"></div>' +
                '      <div class="theme-selector__name">暖纸</div>' +
                '    </div>' +
                '  </div>' +
                '</div>'
            );
        },

        _bindEvents: function () {
            var self = this;
            if (!this._root) return;

            var options = this._root.querySelectorAll('.theme-selector__option');
            options.forEach(function (opt) {
                opt.addEventListener('click', function () {
                    var theme = opt.getAttribute('data-theme');
                    if (global.MMFBTheme) {
                        global.MMFBTheme.set(theme, false);
                    }
                });
            });
        },

        _updateActiveState: function () {
            if (!this._root || !global.MMFBTheme) return;
            var current = global.MMFBTheme.get();
            var options = this._root.querySelectorAll('.theme-selector__option');
            options.forEach(function (opt) {
                var theme = opt.getAttribute('data-theme');
                if (theme === current) {
                    opt.classList.add('theme-selector__option--active');
                } else {
                    opt.classList.remove('theme-selector__option--active');
                }
            });
        }
    };

    global.MMFBThemeSelector = MMFBThemeSelector;

})(window);
