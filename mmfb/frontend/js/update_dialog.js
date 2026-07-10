/**
 * MMFBUpdateDialog 自动更新对话框
 *
 * 用法:
 *   MMFBUpdateDialog.checkOnStartup();   // 启动时检查（自动跳过禁用状态）
 *   MMFBUpdateDialog.checkManual();      // 用户主动触发（关于页/设置页）
 *   MMFBUpdateDialog.show(data);         // 外部直接展示（data 为 updateCheckResult 数据）
 *
 * 状态机:
 *   idle -> checking -> (no_update | has_update -> downloading -> ready_to_install -> launching)
 */
(function (global) {
    'use strict';

    var STATE = {
        IDLE: 'idle',
        CHECKING: 'checking',
        HAS_UPDATE: 'has_update',
        DOWNLOADING: 'downloading',
        READY: 'ready',
        ERROR: 'error',
    };

    var _state = STATE.IDLE;
    var _currentData = null;       // 当前查询到的新版本数据
    var _installerPath = '';       // 本地安装器路径
    var _overlay = null;           // DOM 引用

    // ------------------------------------------------------------------
    //  启动时自动检查（可被用户设置关闭）
    // ------------------------------------------------------------------

    function checkOnStartup() {
        MMFBBridge.ready().then(function () {
            // 读取设置：关闭 check_updates 时跳过网络请求
            try {
                var stored = localStorage.getItem('mmfb_settings_general');
                if (stored) {
                    var general = JSON.parse(stored);
                    if (general.check_updates === false) return;
                }
            } catch (e) {
                // ignore
            }

            // 发起查询（通过 Python Bridge 异步返回）
            _state = STATE.CHECKING;
            _registerUpdateCallbacks();
            MMFBBridge.checkForUpdates();
        });
    }

    // ------------------------------------------------------------------
    //  用户主动触发（关于页等）
    // ------------------------------------------------------------------

    function checkManual() {
        _state = STATE.CHECKING;
        _registerUpdateCallbacks();
        _render();  // 显示 "正在检查..."
        MMFBBridge.checkForUpdates();
    }

    // ------------------------------------------------------------------
    //  外部直接展示（已拿到检查结果时直接渲染）
    // ------------------------------------------------------------------

    function show(data) {
        _registerUpdateCallbacks();
        _onCheckResult(JSON.stringify(data));
    }

    // ------------------------------------------------------------------
    //  注册 Bridge 回调（幂等）
    // ------------------------------------------------------------------

    var _callbacksRegistered = false;

    function _registerUpdateCallbacks() {
        if (_callbacksRegistered) return;
        _callbacksRegistered = true;

        MMFBBridge.onUpdateCheckResult = _onCheckResult;
        MMFBBridge.onUpdateDownloadProgress = _onDownloadProgress;
        MMFBBridge.onUpdateInstallerReady = _onInstallerReady;
    }

    // ------------------------------------------------------------------
    //  回调处理
    // ------------------------------------------------------------------

    function _onCheckResult(payload) {
        try {
            var data = JSON.parse(payload);
        } catch (e) {
            _state = STATE.ERROR;
            _renderError('解析失败');
            return;
        }

        if (data.error) {
            _state = STATE.ERROR;
            _renderError(data.error);
            return;
        }

        if (!data.available) {
            _state = STATE.IDLE;
            if (_isDialogVisible()) {
                _renderNoUpdate();
            }
            return;
        }

        // 检查是否被用户跳过
        if (_isSkipped(data.tag)) {
            _state = STATE.IDLE;
            _closeDialog();
            return;
        }

        _currentData = data;
        _state = STATE.HAS_UPDATE;
        _render();
    }

    function _onDownloadProgress(percent, status) {
        if (_state !== STATE.DOWNLOADING) return;
        _renderProgress(percent, status);
    }

    function _onInstallerReady(filePath, tagOrError) {
        if (_state !== STATE.DOWNLOADING) return;

        if (!filePath || tagOrError !== 'ok') {
            _state = STATE.ERROR;
            _renderError(tagOrError || '下载失败');
            return;
        }

        _installerPath = filePath;
        _state = STATE.READY;
        _render();
    }

    // ------------------------------------------------------------------
    //  用户操作
    // ------------------------------------------------------------------

    function _startDownload() {
        if (!_currentData || !_currentData.asset || !_currentData.asset.download_url) {
            // 没有直接下载 URL：跳转浏览器
            if (_currentData && _currentData.html_url) {
                window.open(_currentData.html_url, '_blank');
            }
            _closeDialog();
            return;
        }

        // 检查是否已被跳过（保险）
        if (_isSkipped(_currentData.tag)) {
            _closeDialog();
            return;
        }

        _state = STATE.DOWNLOADING;
        _render();
        MMFBBridge.downloadUpdate(
            _currentData.asset.download_url,
            _currentData.asset.name
        );
    }

    function _launchAndRestart() {
        if (!_installerPath) return;
        _state = STATE.READY;
        _renderLaunched();
        // 延迟 500ms 给 UI 一个反馈
        setTimeout(function () {
            MMFBBridge.launchInstaller(_installerPath);
        }, 500);
    }

    function _skipThisVersion() {
        if (_currentData && _currentData.tag) {
            MMFBBridge.skipVersion(_currentData.tag);
        }
        _closeDialog();
    }

    function _remindLater() {
        _closeDialog();
    }

    function _viewDetails() {
        if (_currentData && _currentData.html_url) {
            window.open(_currentData.html_url, '_blank');
        }
    }

    // ------------------------------------------------------------------
    //  Skipped Versions 本地缓存
    // ------------------------------------------------------------------

    function _isSkipped(tag) {
        if (!tag) return false;
        try {
            var raw = localStorage.getItem('mmfb_skipped_versions');
            var lst = raw ? JSON.parse(raw) : [];
            return lst.indexOf(tag) >= 0;
        } catch (e) {
            return false;
        }
    }

    // ------------------------------------------------------------------
    //  DOM 渲染
    // ------------------------------------------------------------------

    function _isDialogVisible() {
        return _overlay && _overlay.classList.contains('visible');
    }

    function _render() {
        if (!_overlay) {
            _buildDOM();
        }

        if (_state === STATE.CHECKING) {
            _renderChecking();
        } else if (_state === STATE.HAS_UPDATE) {
            _renderHasUpdate();
        } else if (_state === STATE.DOWNLOADING) {
            _renderProgress(0, '准备下载...');
        } else if (_state === STATE.READY) {
            _renderReady();
        }

        _overlay.classList.add('visible');
    }

    function _buildDOM() {
        _overlay = document.createElement('div');
        _overlay.className = 'update-overlay';
        _overlay.innerHTML =
            '<div class="update-dialog" role="dialog" aria-modal="true">' +
            '  <div class="update-dialog__header">' +
            '    <span class="update-dialog__icon">⬆</span>' +
            '    <h3 class="update-dialog__title">MMFB 更新</h3>' +
            '  </div>' +
            '  <div class="update-dialog__body"></div>' +
            '  <div class="update-dialog__footer"></div>' +
            '</div>';
        document.body.appendChild(_overlay);

        // 点击遮罩关闭（仅 idle 状态）
        _overlay.addEventListener('click', function (e) {
            if (e.target === _overlay) {
                _remindLater();
            }
        });
    }

    function _dialogBody() {
        return _overlay.querySelector('.update-dialog__body');
    }

    function _dialogFooter() {
        return _overlay.querySelector('.update-dialog__footer');
    }

    function _renderChecking() {
        _dialogBody().innerHTML =
            '<div style="text-align:center;padding:24px 0;color:var(--color-text-muted,#888);">' +
            '<div style="font-size:28px;margin-bottom:10px;">⟳</div>' +
            '<div>正在检查更新...</div>' +
            '</div>';
        _dialogFooter().innerHTML = '';
    }

    function _renderNoUpdate() {
        _dialogBody().innerHTML =
            '<div style="text-align:center;padding:20px 0;color:var(--color-text-muted,#888);">' +
            '<div style="font-size:24px;margin-bottom:8px;">✓</div>' +
            '<div>当前已是最新版本</div>' +
            '</div>';
        _dialogFooter().innerHTML =
            '<button class="update-btn update-btn--primary" data-action="close">关闭</button>';
        _bindFooter();
    }

    function _renderError(msg) {
        _dialogBody().innerHTML =
            '<div style="padding:12px 0;color:#E74C3C;">' +
            '<div style="margin-bottom:8px;font-weight:600;">检查失败</div>' +
            '<div style="font-size:12px;color:var(--color-text-muted,#888);word-break:break-all;">' +
            _escHtml(msg) + '</div>' +
            '</div>';
        _dialogFooter().innerHTML =
            '<button class="update-btn" data-action="retry">重试</button>' +
            '<button class="update-btn update-btn--primary" data-action="close">关闭</button>';
        _bindFooter();
    }

    function _renderHasUpdate() {
        var d = _currentData;
        var notesHtml = d.notes
            ? _escHtml(d.notes).replace(/\n/g, '<br>')
            : '<span style="color:var(--color-text-muted);">无更新说明</span>';

        var versionRow = '';
        if (d.tag) {
            versionRow =
                '<div class="update-dialog__version-row">' +
                '  <span class="update-dialog__version-label">最新版本</span>' +
                '  <span class="update-dialog__version-tag">' + _escHtml(d.tag) + '</span>' +
                '</div>';
        }

        var nameLine = d.name
            ? '<div style="font-weight:600;margin-bottom:8px;">' + _escHtml(d.name) + '</div>'
            : '';

        _dialogBody().innerHTML =
            versionRow + nameLine +
            '<div style="margin-top:10px;font-size:12px;color:var(--color-text-muted);margin-bottom:6px;">更新内容</div>' +
            '<div class="update-dialog__changelog">' + notesHtml + '</div>' +
            '<div class="update-dialog__progress">' +
            '  <div class="update-dialog__progress-bar">' +
            '    <div class="update-dialog__progress-bar-fill"></div>' +
            '  </div>' +
            '  <div class="update-dialog__progress-text"></div>' +
            '</div>';

        var canDownload = d.asset && d.asset.download_url;
        var canDetail = !!d.html_url;

        var footerHtml = '';
        if (canDetail) {
            footerHtml += '<button class="update-btn update-btn--link" data-action="detail">查看详情</button>';
        }
        footerHtml +=
            '<button class="update-btn update-btn--link" data-action="skip">忽略此版本</button>' +
            '<button class="update-btn" data-action="later">稍后</button>';

        if (canDownload) {
            footerHtml += '<button class="update-btn update-btn--primary" data-action="download">下载更新</button>';
        } else {
            footerHtml += '<button class="update-btn update-btn--primary" data-action="gotosite">前往下载</button>';
        }

        _dialogFooter().innerHTML = footerHtml;
        _bindFooter();
    }

    function _renderProgress(percent, status) {
        var body = _dialogBody();
        var progressEl = body.querySelector('.update-dialog__progress');
        var fillEl = body.querySelector('.update-dialog__progress-bar-fill');
        var textEl = body.querySelector('.update-dialog__progress-text');

        if (progressEl) progressEl.classList.add('visible');
        if (fillEl) fillEl.style.width = (percent >= 0 ? percent : 10) + '%';
        if (textEl) textEl.textContent =
            percent >= 0 ? ('下载 ' + percent + '%') : (status || '下载中...');

        _dialogFooter().innerHTML =
            '<button class="update-btn" data-action="later">稍后</button>';
        _bindFooter();
    }

    function _renderReady() {
        _dialogBody().innerHTML =
            '<div style="text-align:center;padding:16px 0;">' +
            '<div style="font-size:32px;margin-bottom:8px;">📦</div>' +
            '<div style="font-weight:600;margin-bottom:6px;">安装包已就绪</div>' +
            '<div style="font-size:12px;color:var(--color-text-muted,#888);">点击"安装并重启"将退出当前应用并启动安装程序</div>' +
            '</div>';
        _dialogFooter().innerHTML =
            '<button class="update-btn" data-action="later">稍后</button>' +
            '<button class="update-btn update-btn--primary" data-action="install">安装并重启</button>';
        _bindFooter();
    }

    function _renderLaunched() {
        _dialogBody().innerHTML =
            '<div style="text-align:center;padding:24px 0;color:var(--color-text-muted,#888);">' +
            '<div style="font-size:28px;margin-bottom:8px;">⏳</div>' +
            '<div>正在启动安装程序...</div>' +
            '</div>';
        _dialogFooter().innerHTML = '';
    }

    function _bindFooter() {
        var footer = _dialogFooter();
        var buttons = footer.querySelectorAll('button[data-action]');
        for (var i = 0; i < buttons.length; i++) {
            (function (btn) {
                btn.addEventListener('click', function () {
                    var action = btn.getAttribute('data-action');
                    if (action === 'download') {
                        _startDownload();
                    } else if (action === 'install') {
                        _launchAndRestart();
                    } else if (action === 'skip') {
                        _skipThisVersion();
                    } else if (action === 'later') {
                        _remindLater();
                    } else if (action === 'detail') {
                        _viewDetails();
                    } else if (action === 'gotosite') {
                        _startDownload();
                    } else if (action === 'retry') {
                        checkManual();
                    } else if (action === 'close') {
                        _closeDialog();
                    }
                });
            })(buttons[i]);
        }
    }

    function _closeDialog() {
        if (_overlay) {
            _overlay.classList.remove('visible');
        }
        _currentData = null;
        _installerPath = '';
        _state = STATE.IDLE;
    }

    // ------------------------------------------------------------------
    //  Utility
    // ------------------------------------------------------------------

    function _escHtml(s) {
        if (s == null) return '';
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // ------------------------------------------------------------------
    //  Public API
    // ------------------------------------------------------------------

    global.MMFBUpdateDialog = {
        checkOnStartup: checkOnStartup,
        checkManual: checkManual,
        show: show,
        close: _closeDialog,
    };

})(window);
