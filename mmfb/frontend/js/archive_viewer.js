/**
 * MMFB Archive Viewer - 压缩包树形预览
 *
 * 功能：
 * 1. 渲染 ZIP/TAR/TGZ/TAR.GZ/TAR.BZ2/TAR.XZ 的树形目录结构
 * 2. 点击文件时调用 Bridge.extractArchiveMember 解压到内存预览
 * 3. 支持文本文件直接显示，图像文件 Base64 渲染
 * 4. 支持加密 ZIP (密码弹窗重试)
 */
(function (global) {
    'use strict';

    /**
     * @param {HTMLElement} root - 容器元素
     * @param {Object} data - ArchiveHandler.get_preview() 返回的 data 字段
     */
    function MMFBArchiveViewer(root, data) {
        this.root = root;
        this.data = data;
        this.filePath = data.file_path;
        this.archiveType = data.archive_type;
        this.isEncrypted = data.is_encrypted;
        this.password = '';
        this._render();
    }

    MMFBArchiveViewer.prototype._render = function () {
        if (this.isEncrypted) {
            this._renderEncrypted();
            return;
        }

        var self = this;

        // 统计摘要
        var summary = this._buildSummary();

        // 主容器
        var html =
            '<div class="archive-viewer">' +
            '<div class="archive-viewer__header">' +
            '<div class="archive-viewer__icon">&#128193;</div>' +
            '<div class="archive-viewer__info">' +
            '<div class="archive-viewer__title">' + this.data.tree.name + '</div>' +
            '<div class="archive-viewer__summary">' + summary + '</div>' +
            '</div>' +
            '</div>' +
            '<div class="archive-viewer__toolbar">' +
            '<button class="archive-btn archive-btn--expand" id="archive-expand-all">展开所有</button>' +
            '<button class="archive-btn archive-btn--collapse" id="archive-collapse-all">折叠所有</button>' +
            '</div>' +
            '<div class="archive-viewer__tree" id="archive-tree"></div>' +
            '<div class="archive-viewer__preview" id="archive-preview"></div>' +
            '</div>';

        this.root.innerHTML = html;

        // 渲染树
        this._renderTree();

        // 工具栏事件
        var expandBtn = this.root.querySelector('#archive-expand-all');
        var collapseBtn = this.root.querySelector('#archive-collapse-all');
        if (expandBtn) {
            expandBtn.addEventListener('click', function () {
                self._expandAll();
            });
        }
        if (collapseBtn) {
            collapseBtn.addEventListener('click', function () {
                self._collapseAll();
            });
        }
    };

    MMFBArchiveViewer.prototype._buildSummary = function () {
        var d = this.data;
        var parts = [];
        if (d.total_files > 0) {
            parts.push(d.total_files + ' 个文件');
        }
        if (d.total_dirs > 0) {
            parts.push(d.total_dirs + ' 个目录');
        }
        parts.push(this._formatSize(d.total_size));
        if (d.file_count >= 5000) {
            parts.push('(仅显示前 5000 项)');
        }
        return parts.join('，');
    };

    MMFBArchiveViewer.prototype._formatSize = function (bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
    };

    /**
     * 递归渲染树形结构
     */
    MMFBArchiveViewer.prototype._renderTree = function () {
        var treeContainer = this.root.querySelector('#archive-tree');
        if (!treeContainer) return;

        var self = this;
        var html = '<ul class="archive-tree" role="tree">';
        html += this._renderNode(this.data.tree, '', 0, true);
        html += '</ul>';
        treeContainer.innerHTML = html;

        // 绑定事件
        var items = treeContainer.querySelectorAll('[data-member-path]');
        items.forEach(function (item) {
            item.addEventListener('click', function (e) {
                e.stopPropagation();
                var memberPath = this.getAttribute('data-member-path');
                var isDir = this.getAttribute('data-is-dir') === 'true';
                if (isDir) {
                    self._toggleDir(this, memberPath);
                } else {
                    self._previewFile(memberPath);
                }
            });
        });
    };

    /**
     * 渲染单个节点 (递归)
     */
    MMFBArchiveViewer.prototype._renderNode = function (node, parentPath, depth, isRoot) {
        var self = this;
        var html = '';
        var indent = depth * 16;
        var currentPath = parentPath ? parentPath + '/' + node.name : node.name;

        if (isRoot) {
            // 根节点：直接渲染 children
            if (node.children && node.children.length > 0) {
                node.children.forEach(function (child) {
                    html += self._renderNode(child, '', depth, false);
                });
            } else {
                html += '<li class="archive-tree__empty">压缩包为空</li>';
            }
            return html;
        }

        if (node.isDir) {
            // 目录节点
            var dirId = 'dir-' + Math.abs(this._hashString(currentPath));
            html += '<li class="archive-tree__item archive-tree__item--dir" role="treeitem" ' +
                'data-member-path="' + this._escapeAttr(currentPath) + '" data-is-dir="true"' +
                'aria-expanded="true">';
            html += '<span class="archive-tree__toggle" style="margin-left:' + indent + 'px">';
            html += '<span class="archive-tree__arrow">&#9660;</span>'; // ▼
            html += '<span class="archive-tree__icon">&#128193;</span> '; // 📁
            html += '<span class="archive-tree__name">' + this._escapeHtml(node.name) + '</span>';
            html += '</span>';
            html += '<ul class="archive-tree__children" id="' + dirId + '">';
            if (node.children && node.children.length > 0) {
                node.children.forEach(function (child) {
                    html += self._renderNode(child, currentPath, 0, false);
                });
            }
            html += '</ul>';
            html += '</li>';
        } else {
            // 文件节点
            html += '<li class="archive-tree__item archive-tree__item--file" role="treeitem" ' +
                'data-member-path="' + this._escapeAttr(currentPath) + '" data-is-dir="false"' +
                'title="' + this._escapeAttr(currentPath) + '">';
            html += '<span class="archive-tree__toggle archive-toggle--file" style="margin-left:' + indent + 'px">';
            html += '<span class="archive-tree__file-icon">' + this._getFileIcon(node.ext) + '</span> ';
            html += '<span class="archive-tree__name">' + this._escapeHtml(node.name) + '</span>';
            if (node.size_human) {
                html += '<span class="archive-tree__size">' + node.size_human + '</span>';
            }
            html += '</span>';
            html += '</li>';
        }

        return html;
    };

    MMFBArchiveViewer.prototype._getFileIcon = function (ext) {
        var iconMap = {
            'txt': '&#128196;',
            'md': '&#128196;',
            'pdf': '&#128196;',
            'py': '&#128496;',
            'js': '&#128496;',
            'html': '&#127760;',
            'css': '&#127760;',
            'json': '&#128190;',
            'jpg': '&#128444;',
            'jpeg': '&#128444;',
            'png': '&#128444;',
            'gif': '&#128444;',
            'bmp': '&#128444;',
            'svg': '&#128444;',
        };
        return iconMap[ext] || '&#128196;'; // 📄
    };

    /**
     * 展开/折叠目录
     */
    MMFBArchiveViewer.prototype._toggleDir = function (element, path) {
        var childrenUl = element.querySelector('.archive-tree__children');
        var arrow = element.querySelector('.archive-tree__arrow');
        if (!childrenUl) return;

        var isExpanded = childrenUl.style.display !== 'none';
        if (isExpanded) {
            childrenUl.style.display = 'none';
            if (arrow) arrow.innerHTML = '&#9654;'; // ▶
            element.setAttribute('aria-expanded', 'false');
        } else {
            childrenUl.style.display = '';
            if (arrow) arrow.innerHTML = '&#9660;'; // ▼
            element.setAttribute('aria-expanded', 'true');
        }
    };

    MMFBArchiveViewer.prototype._expandAll = function () {
        var self = this;
        var uls = this.root.querySelectorAll('.archive-tree__children');
        uls.forEach(function (ul) {
            ul.style.display = '';
        });
        var arrows = this.root.querySelectorAll('.archive-tree__arrow');
        arrows.forEach(function (arrow) {
            arrow.innerHTML = '&#9660;';
        });
    };

    MMFBArchiveViewer.prototype._collapseAll = function () {
        var self = this;
        var uls = this.root.querySelectorAll('.archive-tree__children');
        uls.forEach(function (ul) {
            ul.style.display = 'none';
        });
        var arrows = this.root.querySelectorAll('.archive-tree__arrow');
        arrows.forEach(function (arrow) {
            arrow.innerHTML = '&#9654;';
        });
    };

    /**
     * 预览压缩包内文件
     */
    MMFBArchiveViewer.prototype._previewFile = function (memberPath) {
        var self = this;
        var previewEl = this.root.querySelector('#archive-preview');
        if (!previewEl) return;

        previewEl.innerHTML = '<div class="archive-preview__loading">加载 ' +
            this._escapeHtml(memberPath) + ' ...</div>';

        if (!global.MMFBBridge || !global.MMFBBridge.api.extractArchiveMember) {
            previewEl.innerHTML = '<div class="archive-preview__error">Bridge 未就绪</div>';
            return;
        }

        global.MMFBBridge.api.extractArchiveMember(
            this.filePath,
            memberPath,
            this.password
        ).then(function (json) {
            var result = typeof json === 'string' ? JSON.parse(json) : json;
            if (!result.ok) {
                if (result.need_password) {
                    self._promptPassword(memberPath);
                } else {
                    previewEl.innerHTML = '<div class="archive-preview__error">' +
                        self._escapeHtml(result.error || '解压失败') + '</div>';
                }
                return;
            }
            self._renderPreview(memberPath, result);
        }).catch(function (err) {
            previewEl.innerHTML = '<div class="archive-preview__error">请求失败: ' +
                self._escapeHtml(String(err)) + '</div>';
        });
    };

    /**
     * 渲染解压后的内容预览
     */
    MMFBArchiveViewer.prototype._renderPreview = function (memberPath, result) {
        var previewEl = this.root.querySelector('#archive-preview');
        if (!previewEl) return;

        var mime = result.mime || '';
        var fileName = memberPath.split('/').pop() || memberPath;

        // 头部信息
        var headerHtml =
            '<div class="archive-preview__header">' +
            '<span class="archive-preview__name">' + this._escapeHtml(fileName) + '</span>' +
            '<span class="archive-preview__meta">' + this._escapeHtml(mime) + ' · ' +
            this._formatSize(result.size) + '</span>' +
            '<button class="archive-preview__close" id="archive-preview-close">✕</button>' +
            '</div>';

        var contentHtml = '';

        // 文本类型
        if (mime.startsWith('text/') || mime === 'application/json' ||
            mime === 'application/javascript' || mime === 'application/xml' ||
            this._isTextFileName(fileName)) {
            try {
                var text = atob(result.data);
                contentHtml = '<pre class="archive-preview__text">' +
                    this._escapeHtml(text) + '</pre>';
            } catch (e) {
                contentHtml = '<div class="archive-preview__error">解码失败</div>';
            }
        }
        // 图像类型
        else if (mime.startsWith('image/')) {
            contentHtml = '<div class="archive-preview__image">' +
                '<img src="data:' + mime + ';base64,' + result.data + '" ' +
                'alt="' + this._escapeAttr(fileName) + '" ' +
                'class="archive-preview__img" />' +
                '</div>';
        }
        // 其他类型：显示下载信息和 hex 预览
        else {
            contentHtml = '<div class="archive-preview__unsupported">' +
                '<p>该格式暂不支持预览</p>' +
                '<p class="archive-preview__mime">' + this._escapeHtml(mime) + '</p>' +
                '<p class="archive-preview__size">' + this._formatSize(result.size) + '</p>' +
                '</div>';
        }

        previewEl.innerHTML = headerHtml + '<div class="archive-preview__content">' + contentHtml + '</div>';

        // 绑定关闭按钮
        var closeBtn = previewEl.querySelector('#archive-preview-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', function () {
                previewEl.innerHTML = '';
            });
        }
    };

    MMFBArchiveViewer.prototype._isTextFileName = function (fileName) {
        var textExts = [
            'txt', 'md', 'markdown', 'log', 'ini', 'cfg', 'conf', 'env',
            'py', 'js', 'ts', 'jsx', 'tsx', 'css', 'scss', 'less',
            'c', 'cpp', 'h', 'hpp', 'java', 'kt', 'go', 'rs', 'swift',
            'rb', 'php', 'pl', 'sh', 'bash', 'zsh', 'bat', 'ps1',
            'sql', 'graphql', 'r', 'm', 'scala', 'lua', 'vim',
            'toml', 'yaml', 'yml', 'xml', 'json', 'csv', 'tsv',
            'html', 'htm', 'svg', 'diff', 'patch', 'rtf'
        ];
        var ext = fileName.split('.').pop().toLowerCase();
        return textExts.indexOf(ext) >= 0;
    };

    /**
     * 加密 ZIP 密码弹窗
     */
    MMFBArchiveViewer.prototype._promptPassword = function (memberPath) {
        var self = this;
        var previewEl = this.root.querySelector('#archive-preview');
        if (!previewEl) return;

        previewEl.innerHTML =
            '<div class="archive-preview__password">' +
            '<p>该文件需要密码</p>' +
            '<input type="password" id="archive-password-input" class="archive-preview__pw-input" placeholder="输入解压密码" />' +
            '<button id="archive-password-submit" class="archive-btn archive-btn--primary">确定</button>' +
            '<p id="archive-password-error" class="archive-preview__pw-error" style="display:none">密码错误，请重试</p>' +
            '</div>';

        var input = previewEl.querySelector('#archive-password-input');
        var submitBtn = previewEl.querySelector('#archive-password-submit');
        var errorEl = previewEl.querySelector('#archive-password-error');

        function tryPassword() {
            var pw = input.value;
            if (!pw) return;
            self.password = pw;
            if (errorEl) errorEl.style.display = 'none';
            self._previewFile(memberPath);
        }

        if (submitBtn) {
            submitBtn.addEventListener('click', tryPassword);
        }
        if (input) {
            input.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') tryPassword();
            });
            input.focus();
        }
    };

    /**
     * 加密 ZIP 整体提示
     */
    MMFBArchiveViewer.prototype._renderEncrypted = function () {
        var self = this;
        this.root.innerHTML =
            '<div class="archive-viewer">' +
            '<div class="archive-viewer__header">' +
            '<div class="archive-viewer__icon">&#128274;</div>' +
            '<div class="archive-viewer__info">' +
            '<div class="archive-viewer__title">' + this._escapeHtml(this.data.tree.name) + '</div>' +
            '<div class="archive-viewer__summary">加密 ZIP，需要密码才能查看内容</div>' +
            '</div>' +
            '</div>' +
            '<div class="archive-preview__password">' +
            '<input type="password" id="archive-password-input" class="archive-preview__pw-input" placeholder="输入 ZIP 密码" />' +
            '<button id="archive-password-submit" class="archive-btn archive-btn--primary">解锁</button>' +
            '<p id="archive-password-error" class="archive-preview__pw-error" style="display:none">密码错误，请重试</p>' +
            '</div>' +
            '</div>';

        var input = this.root.querySelector('#archive-password-input');
        var submitBtn = this.root.querySelector('#archive-password-submit');
        var errorEl = this.root.querySelector('#archive-password-error');

        function tryUnlock() {
            var pw = input.value;
            if (!pw) return;
            if (errorEl) errorEl.style.display = 'none';

            if (!global.MMFBBridge || !global.MMFBBridge.api.extractArchiveMember) {
                if (errorEl) {
                    errorEl.textContent = 'Bridge 未就绪';
                    errorEl.style.display = '';
                }
                return;
            }

            // 尝试解压任意一个成员来验证密码
            global.MMFBBridge.api.unlockEncryptedArchive(self.filePath, pw).then(function (json) {
                var result = typeof json === 'string' ? JSON.parse(json) : json;
                if (result.ok) {
                    self.password = pw;
                    self.isEncrypted = false;
                    self.data = result.data;
                    self._render();
                } else {
                    if (errorEl) {
                        errorEl.textContent = result.error || '密码错误';
                        errorEl.style.display = '';
                    }
                }
            }).catch(function (err) {
                if (errorEl) {
                    errorEl.textContent = String(err);
                    errorEl.style.display = '';
                }
            });
        }

        if (submitBtn) {
            submitBtn.addEventListener('click', tryUnlock);
        }
        if (input) {
            input.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') tryUnlock();
            });
            input.focus();
        }
    };

    // ========== 工具方法 ==========

    MMFBArchiveViewer.prototype._escapeHtml = function (str) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    };

    MMFBArchiveViewer.prototype._escapeAttr = function (str) {
        return str.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    };

    MMFBArchiveViewer.prototype._hashString = function (str) {
        var hash = 0;
        for (var i = 0; i < str.length; i++) {
            hash = ((hash << 5) - hash) + str.charCodeAt(i);
            hash |= 0;
        }
        return hash;
    };

    MMFBArchiveViewer.prototype.destroy = function () {
        this.root.innerHTML = '';
    };

    // 暴露到全局
    global.MMFBArchiveViewer = MMFBArchiveViewer;

})(window);
