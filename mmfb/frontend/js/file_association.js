/**
 * MMFB File Association UI - 文件关联设置面板
 *
 * 展示当前文件关联状态，提供"全部关联""取消关联"按钮。
 * 通过 MMFBBridge 与 Python 侧通信。
 */
(function (global) {
    'use strict';

    var MMFBFileAssociation = {
        _root: null,
        _status: null,

        /**
         * 渲染面板
         * @param {HTMLElement} root
         */
        render: function (root) {
            this._root = root;
            this._root.innerHTML = this._build_html();
            this._bind_events();
            this._load_status();
        },

        /**
         * 销毁（移除事件）
         */
        destroy: function () {
            this._root = null;
        },

        // ----------------------------------------------------------------

        _build_html: function () {
            return (
                '<div class="file-assoc">' +
                '  <div class="file-assoc__header">' +
                '    <h3>文件关联</h3>' +
                '    <p class="file-assoc__subtitle">让资源管理器中双击文件时直接用 MMFB 打开</p>' +
                '  </div>' +

                '  <div class="file-assoc__status" id="file-assoc-status">' +
                '    <div class="file-assoc__loading">正在检测...</div>' +
                '  </div>' +

                '  <div class="file-assoc__actions" id="file-assoc-actions" style="display:none">' +
                '    <button class="mmfb-btn mmfb-btn--primary" id="file-assoc-btn-register">' +
                '      关联全部支持的文件格式' +
                '    </button>' +
                '    <button class="mmfb-btn mmfb-btn--secondary" id="file-assoc-btn-unregister">' +
                '      取消关联' +
                '    </button>' +
                '  </div>' +

                '  <div class="file-assoc__result" id="file-assoc-result"></div>' +

                '  <div class="file-assoc__info">' +
                '    <small>此操作仅修改当前用户设置 (HKEY_CURRENT_USER)，无需管理员权限</small>' +
                '  </div>' +
                '</div>'
            );
        },

        _bind_events: function () {
            var btnRegister = this._root.querySelector('#file-assoc-btn-register');
            var btnUnregister = this._root.querySelector('#file-assoc-btn-unregister');

            if (btnRegister) {
                btnRegister.addEventListener('click', this._on_register.bind(this));
            }
            if (btnUnregister) {
                btnUnregister.addEventListener('click', this._on_unregister.bind(this));
            }
        },

        _load_status: function () {
            var self = this;
            var statusEl = this._root.querySelector('#file-assoc-status');

            if (!global.MMFBBridge || typeof global.MMFBBridge.getFileAssociationStatus !== 'function') {
                if (statusEl) statusEl.innerHTML = '<div class="file-assoc__error">文件关联 API 不可用（需要 Windows 平台）</div>';
                return;
            }

            global.MMFBBridge.ready().then(function () {
                return global.MMFBBridge.getFileAssociationStatus();
            }).then(function (status) {
                if (status && !status.available && status.error) {
                    // 非 Windows 或不可用
                    statusEl.innerHTML = '<div class="file-assoc__error">' +
                        '当前平台不支持文件关联注册</div>';
                    return;
                }
                self._status = status;
                self._render_status(status);
                var actionsEl = self._root.querySelector('#file-assoc-actions');
                if (actionsEl) actionsEl.style.display = '';
            }).catch(function (err) {
                statusEl.innerHTML = '<div class="file-assoc__error">检测失败: ' +
                    (err && err.message ? err.message : 'unknown') + '</div>';
            });
        },

        _render_status: function (status) {
            var statusEl = this._root.querySelector('#file-assoc-status');
            if (!statusEl) return;

            var associated = status.associated || 0;
            var total = status.total || 0;
            var pct = total > 0 ? Math.round((associated / total) * 100) : 0;

            statusEl.innerHTML = (
                '<div class="file-assoc__progress">' +
                '  <div class="file-assoc__bar">' +
                '    <div class="file-assoc__bar-fill" style="width:' + pct + '%"></div>' +
                '  </div>' +
                '  <div class="file-assoc__stats">' +
                '    <span>' + associated + ' / ' + total + ' 个扩展名已关联</span>' +
                '    <span>' + pct + '%</span>' +
                '  </div>' +
                '</div>' +
                '<div class="file-assoc__detail">' +
                '  <small>ProgID: ' + (status.prog_id || '') + '</small>' +
                '  <small>名称: ' + (status.friendly_name || '') + '</small>' +
                '</div>'
            );
        },

        _on_register: function () {
            var self = this;
            var btn = this._root.querySelector('#file-assoc-btn-register');
            var resultEl = this._root.querySelector('#file-assoc-result');

            if (btn) {
                btn.disabled = true;
                btn.textContent = '正在关联...';
            }
            if (resultEl) resultEl.innerHTML = '';

            global.MMFBBridge.ready().then(function () {
                return global.MMFBBridge.registerFileAssociations();
            }).then(function (result) {
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = '关联全部支持的文件格式';
                }
                if (result && result.ok) {
                    resultEl.innerHTML = '<div class="file-assoc__success">' +
                        '成功关联 ' + (result.success || 0) + ' 个格式' +
                        (result.failed > 0 ? '，' + result.failed + ' 个失败' : '') +
                        '</div>';
                } else {
                    resultEl.innerHTML = '<div class="file-assoc__error">' +
                        '注册失败: ' + (result && result.error ? result.error : 'unknown') + '</div>';
                }
                // 重新加载状态
                self._load_status();
            }).catch(function (err) {
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = '关联全部支持的文件格式';
                }
                resultEl.innerHTML = '<div class="file-assoc__error">请求失败: ' +
                    (err && err.message ? err.message : 'unknown') + '</div>';
            });
        },

        _on_unregister: function () {
            var self = this;
            var btn = this._root.querySelector('#file-assoc-btn-unregister');
            var resultEl = this._root.querySelector('#file-assoc-result');

            if (!confirm('确定要取消所有文件格式关联吗？')) return;

            if (btn) {
                btn.disabled = true;
                btn.textContent = '取消中...';
            }

            global.MMFBBridge.ready().then(function () {
                return global.MMFBBridge.unregisterFileAssociations();
            }).then(function (result) {
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = '取消关联';
                }
                if (result && result.ok) {
                    resultEl.innerHTML = '<div class="file-assoc__success">' +
                        '已移除 ' + (result.success || 0) + ' 个关联</div>';
                } else {
                    resultEl.innerHTML = '<div class="file-assoc__error">' +
                        '操作失败: ' + (result && result.error ? result.error : 'unknown') + '</div>';
                }
                self._load_status();
            }).catch(function (err) {
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = '取消关联';
                }
                resultEl.innerHTML = '<div class="file-assoc__error">请求失败: ' +
                    (err && err.message ? err.message : 'unknown') + '</div>';
            });
        },
    };

    global.MMFBFileAssociation = MMFBFileAssociation;

})(window);
