/**
 * MMFB EpubViewer - EPUB 电子书阅读器
 *
 * 职责：
 *   1. 显示 EPUB 阅读界面（左侧可选目录）
 *   2. 使用 iframe 渲染完整的 HTML 文档
 *   3. 支持目录内部锚点跳转
 *
 * 使用方式:
 *   new MMFBEpubViewer(rootEl, { title, author, toc, html_content })
 *   MMFBEpubViewer.init(rootEl, opts) // 兼容
 */
(function (global) {
    'use strict';

    var MMFBEpubViewer = function (root, data) {
        this.root = root;
        this.data = data || {};
        this._filePath = this.data.file_path || '';
        this._fileName = this.data.fileName || '';
        this._title = this.data.title || '';
        this._author = this.data.author || '';
        this._htmlContent = this.data.html_content || '';
        this._init();
    };

    MMFBEpubViewer.prototype._init = function () {
        var self = this;

        // 设置标题
        if (global.MMFBLayout) {
            global.MMFBLayout.setTitle(this._fileName || this._title || 'EPUB');
            global.MMFBLayout.setFooterLeft('EPUB');
        }

        // 渲染容器
        this.root.innerHTML =
            '<div class="epub-viewer">' +
                '<div class="epub-viewer__container"></div>' +
            '</div>';

        var container = this.root.querySelector('.epub-viewer__container');

        // 创建 iframe 用于隔离文档
        var iframe = document.createElement('iframe');
        iframe.className = 'epub-iframe';
        iframe.setAttribute('sandbox', 'allow-scripts allow-same-origin');
        iframe.style.width = '100%';
        iframe.style.height = '100%';
        iframe.style.border = 'none';
        iframe.title = this._title;
        container.appendChild(iframe);

        // 写入文档
        var doc = iframe.contentDocument || iframe.contentWindow.document;
        doc.open();
        doc.write(this._htmlContent);
        doc.close();
    };

    MMFBEpubViewer.prototype.destroy = function () {
        if (this.root) {
            this.root.innerHTML = '';
        }
    };

    global.MMFBEpubViewer = MMFBEpubViewer;

})(window);
