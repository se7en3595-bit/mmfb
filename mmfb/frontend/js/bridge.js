/**
 * MMFB Bridge - QWebChannel JS 封装
 *
 * 提供统一的 Python 调用接口：
 *   MMFBBridge.readFile(path) -> Promise<string>
 *   MMFBBridge.saveFile(path, data) -> Promise<boolean>
 *   MMFBBridge.getFileInfo(path) -> Promise<object>
 *
 * 以及从 Python 接收通知：
 *   MMFBBridge.onFilesDropped = function(payload) { ... }
 *   MMFBBridge.onMessageReceived = function(msg) { ... }
 *   MMFBBridge.onHeaderVisibilityChanged = function(visible) { ... }
 *   MMFBBridge.onShowCommandPanel = function() { ... }
 *   MMFBBridge.onOpenSettings = function() { ... }
 *   MMFBBridge.onSystemThemeChanged = function(themeName) { ... }
 *   MMFBBridge.onNewWindowRequested = function() { ... }
 *   MMFBBridge.onSplitModeChanged = function(split) { ... }
 *   MMFBBridge.onWindowCountChanged = function(count) { ... }
 *   MMFBBridge.onUpdateCheckResult = function(resultJson) { ... }
 *   MMFBBridge.onUpdateDownloadProgress = function(percent, status) { ... }
 *   MMFBBridge.onUpdateInstallerReady = function(filePath, tagOrError) { ... }
 *
 * 用法:
 *   MMFBBridge.ready().then(function(info) { ... });
 */
(function (global) {
    'use strict';

    var MMFBBridge = {
        _bridge: null,
        _ready: false,
        _readyPromise: null,
        _readyResolve: null,

        // 标记用户是否显式设置过主题（用于决定是否跟随系统）
        _themeUserSet: false,

        // 回调注册（可被外部覆盖）
        onFilesDropped: null,
        onMessageReceived: null,
        onConversionProgress: null,
        onConversionFinished: null,
        onHeaderVisibilityChanged: null,
        onShowCommandPanel: null,
        onOpenSettings: null,
        onSystemThemeChanged: null,
        onThemeChanged: null,
        onNewWindowRequested: null,
        onSplitModeChanged: null,
        onWindowCountChanged: null,
        onUpdateCheckResult: null,
        onUpdateDownloadProgress: null,
        onUpdateInstallerReady: null,
        onTrayShowMessage: null,  // 托盘气泡通知回调

        /**
         * 初始化：等待 qwebchannel.js 加载完毕并初始化 QWebChannel。
         * 返回 Promise，完成后 info.mode = 'live' | 'fake'
         */
        ready: function () {
            if (this._ready) {
            console.warn("[MMFBBridge] ready() called, qt=" + (typeof global.qt) + ", transport=" + (!!global.qt && !!global.qt.webChannelTransport));
                return Promise.resolve(this._get_info());
            }
            if (this._readyPromise) return this._readyPromise;

            var self = this;

            // Helper: 执行实际的 QWebChannel 连接
            function connectChannel(transport) {
                return new Promise(function (resolve) {
                    new global.QWebChannel(transport, function (channel) {
                        self._bridge = channel.objects.pybridge;
        self._qtConnected = true;
        self._ready = true;
                        self._bind_signals();
                        resolve(self._get_info());
                    });
                });
            }

            // 如果 qt 已就绪，立即连接
            if (typeof global.qt !== 'undefined' && global.qt.webChannelTransport) {
                self._readyPromise = connectChannel(global.qt.webChannelTransport);
                return self._readyPromise;
            }

            // 否则，等待 qt 对象注入（轮询）
            console.warn('[MMFBBridge] QWebChannel not ready yet, waiting for page load...');
            self._readyPromise = new Promise(function (resolve, reject) {
                function startPolling() {
                    if (typeof global.qt !== 'undefined' && global.qt.webChannelTransport) {
                        connectChannel(global.qt.webChannelTransport).then(resolve).catch(reject);
                        return;
                    }
                    var timeoutMs = 30000;
                    var start = Date.now();
                    (function poll() {
                        if (typeof global.qt !== 'undefined' && global.qt.webChannelTransport) {
                            connectChannel(global.qt.webChannelTransport).then(resolve).catch(reject);
                            return;
                        }
                        if (Date.now() - start >= timeoutMs) {
                            console.error('[MMFBBridge] QWebChannel timeout after ' + timeoutMs + 'ms, falling back to fake mode');
                            self._ready = true;
                            self._qtConnected = false;
                            self._bridge = self._create_fake_bridge();
                            resolve(self._get_info());
                            return;
                        }
                        setTimeout(poll, 50);
                    })();
                }
                if (document.readyState === 'complete') {
                    startPolling();
                } else {
                    window.addEventListener('load', startPolling);
                }
            });

            return self._readyPromise;
        },

        /**
         * 返回连接信息
         */
        _get_info: function () {
            return {
                mode: (this._qtConnected ? 'live' : 'fake'),
                available: !!(this._bridge && this._qtConnected)
            };
        },

        /**
         * 绑定 Python 信号到本地回调
         */
        _bind_signals: function () {
            var self = this;
            if (!this._bridge) return;

            // 文件拖拽信号
            if (this._bridge.filesDropped) {
                this._bridge.filesDropped.connect(function (payload) {
                    if (typeof self.onFilesDropped === 'function') {
                        self.onFilesDropped(payload);
                    }
                });
            }

            // 通用消息信号
            if (this._bridge.messageReceived) {
                this._bridge.messageReceived.connect(function (msg) {
                    if (typeof self.onMessageReceived === 'function') {
                        self.onMessageReceived(msg);
                    }
                });
            }

            // 转换进度信号
            if (this._bridge.conversionProgress) {
                this._bridge.conversionProgress.connect(function (payload) {
                    if (typeof self.onConversionProgress === 'function') {
                        self.onConversionProgress(payload);
                    }
                });
            }

            // 转换完成信号
            if (this._bridge.conversionFinished) {
                this._bridge.conversionFinished.connect(function (payload) {
                    try {
                        var data = typeof payload === 'string' ? JSON.parse(payload) : payload;
                        var jid = data.jobId || '';
                        var res = self._jobResolvers[jid];
                        if (res) {
                            delete self._jobResolvers[jid];
                            res.resolve(data.result || { ok: false, error: 'no result' });
                            return;
                        }
                    } catch (e) {
                        // fall through
                    }
                    // 兜底：转发给外部回调
                    if (typeof self.onConversionFinished === 'function') {
                        self.onConversionFinished(payload);
                    }
                });
            }

            // 顶栏显隐信号（前 -> 后）
            if (this._bridge.headerVisibilityChanged) {
                this._bridge.headerVisibilityChanged.connect(function (visible) {
                    if (typeof self.onHeaderVisibilityChanged === 'function') {
                        self.onHeaderVisibilityChanged(visible);
                    }
                });
            }

            // 命令面板信号（后 -> 前）
            if (this._bridge.showCommandPanel) {
                this._bridge.showCommandPanel.connect(function () {
                    if (typeof self.onShowCommandPanel === 'function') {
                        self.onShowCommandPanel();
                    }
                });
            }

            // 设置页信号（后 -> 前）
            if (this._bridge.openSettings) {
                this._bridge.openSettings.connect(function () {
                    if (typeof self.onOpenSettings === 'function') {
                        self.onOpenSettings();
                    }
                });
            }

            // 系统主题变更信号（后 -> 前）
            if (this._bridge.systemThemeChanged) {
                this._bridge.systemThemeChanged.connect(function (themeName) {
                    if (typeof self.onSystemThemeChanged === 'function') {
                        self.onSystemThemeChanged(themeName);
                    }
                });
            }

            // 主题变更信号（用于 Python 与前端同步）
            if (this._bridge.themeChanged) {
                this._bridge.themeChanged.connect(function (themeName) {
                    if (typeof self.onThemeChanged === 'function') {
                        self.onThemeChanged(themeName);
                    }
                });
            }

            // 新窗口请求信号（后 -> 前：Ctrl+N 经 Python 透传）
            if (this._bridge.newWindowRequested) {
                this._bridge.newWindowRequested.connect(function () {
                    if (typeof self.onNewWindowRequested === 'function') {
                        self.onNewWindowRequested();
                    }
                });
            }

            // 分屏模式变更信号
            if (this._bridge.splitModeChanged) {
                this._bridge.splitModeChanged.connect(function (split) {
                    if (typeof self.onSplitModeChanged === 'function') {
                        self.onSplitModeChanged(split);
                    }
                });
            }

            // 窗口计数变更信号
            if (this._bridge.windowCountChanged) {
                this._bridge.windowCountChanged.connect(function (count) {
                    if (typeof self.onWindowCountChanged === 'function') {
                        self.onWindowCountChanged(count);
                    }
                });
            }

            // 自动更新：查询结果
            if (this._bridge.updateCheckResult) {
                this._bridge.updateCheckResult.connect(function (payload) {
                    if (typeof self.onUpdateCheckResult === 'function') {
                        self.onUpdateCheckResult(payload);
                    }
                });
            }

            // 自动更新：下载进度
            if (this._bridge.updateDownloadProgress) {
                this._bridge.updateDownloadProgress.connect(function (pct, status) {
                    if (typeof self.onUpdateDownloadProgress === 'function') {
                        self.onUpdateDownloadProgress(pct, status);
                    }
                });
            }

            // 自动更新：安装器下载完成
            if (this._bridge.updateInstallerReady) {
                this._bridge.updateInstallerReady.connect(function (filePath, tagOrError) {
                    if (typeof self.onUpdateInstallerReady === 'function') {
                        self.onUpdateInstallerReady(filePath, tagOrError);
                    }
                });
            }

            // 托盘气泡通知信号（后 -> 前）
            if (this._bridge.trayShowMessage) {
                this._bridge.trayShowMessage.connect(function (title, message, iconType, msecs) {
                    if (typeof self.onTrayShowMessage === 'function') {
                        self.onTrayShowMessage(title, message, iconType, parseInt(msecs) || 3000);
                    }
                });
            }
        },

        /**
         * 读取文件内容
         * @param {string} path - 文件绝对路径
         * @returns {Promise<string>} 文件内容
         */
        readFile: function (path) {
            return this.ready().then(function (info) {
                if (info.mode === 'live' && this._bridge && this._bridge.read_file) {
                    return this._bridge.read_file(path).then(function(r) { return r !== undefined ? r : ''; });
                }
                return '';
            }.bind(this));
        },

        /**
         * 读取文件并返回 base64 编码（用于二进制文件如 PDF）
         * @param {string} path - 文件绝对路径
         * @returns {Promise<string>} base64 编码的文件内容
         */
        readFileBase64: function (path) {
            return this.ready().then(function (info) {
                if (info.mode === 'live' && this._bridge && this._bridge.read_file_base64) {
                    return this._bridge.read_file_base64(path).then(function(r) { return r || ''; });
                }
                return '';
            }.bind(this));
        },

        /**
         * 保存文本文件
         * @param {string} path
         * @param {string} data
         * @returns {Promise<boolean>}
         */
        saveFile: function (path, data) {
            return this.ready().then(function (info) {
                if (info.mode === 'live' && this._bridge && this._bridge.save_file) {
                    return this._bridge.save_file(path, data);
                }
                return false;
            }.bind(this));
        },

        /**
         * 获取文件元信息
         * @param {string} path
         * @returns {Promise<object>}
         */
        getFileInfo: function (path) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.get_file_info) {
                    return this._bridge.get_file_info(path).then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return {}; }
                    });
                }
                return {};
            }.bind(this));
        },

        /**
         * 列出子目录
         * @param {string} path
         * @returns {Promise<Array>}
         */
        listDir: function (path) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.list_dir) {
                    return this._bridge.list_dir(path).then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return []; }
                    });
                }
                return [];
            }.bind(this));
        },

        /**
         * 获取 PDF 元信息
         * @param {string} path
         * @returns {Promise<object>}
         */
        getPdfMetadata: function (path) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.get_pdf_metadata) {
                    return this._bridge.get_pdf_metadata(path).then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return {}; }
                    });
                }
                return {};
            }.bind(this));
        },

        /**
         * 批量获取文件元信息
         * @param {Array<string>} paths
         * @returns {Promise<Array>}
         */
        getFilesInfo: function (paths) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.get_files_info) {
                    return this._bridge.get_files_info(JSON.stringify(paths)).then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return []; }
                    });
                }
                return [];
            }.bind(this));
        },

        /**
         * 保存 xlsx 单元格
         * @param {string} path  - "C:/file.xlsx|Sheet1" 格式
         * @param {string} address - 如 "A1"
         * @param {string} value  - 要写入的字符串
         * @returns {Promise<boolean>}
         */
        saveXlsxCell: function (path, address, value) {
            return this.ready().then(function (info) {
                if (info.mode === 'live' && this._bridge && this._bridge.save_xlsx_cell) {
                    return this._bridge.save_xlsx_cell(path, address, value);
                }
                return false;
            });
        },

        /**
         * 批量保存 xlsx 单元格
         * @param {object} payload {path, changes:[{address,value}]}
         * @returns {Promise<boolean>}
         */
        saveXlsxCells: function (payload) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.save_xlsx_cells) {
                    return this._bridge.save_xlsx_cells(JSON.stringify(payload));
                }
                return false;
            }.bind(this));
        },

        /**
         * 转换接口
         * @param {string} src
         * @param {string} dst
         * @param {string} fmt
         * @param {string} jobId
         * @returns {Promise<object>}
         */
        _jobResolvers: {},  // jobId -> {resolve, reject}

        convertFile: function (src, dst, fmt, jobId) {
            var self = this;
            jobId = jobId || ('job_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8));
            return this.ready().then(function () {
                if (self._bridge && self._bridge.convert_file) {
                    // 创建工作 jobId 对应的 Promise，等待 conversionFinished 信号
                    var resultPromise = new Promise(function (resolve, reject) {
                        self._jobResolvers[jobId] = { resolve: resolve, reject: reject };
                        // 超时 5 分钟
                        setTimeout(function () {
                            if (self._jobResolvers[jobId]) {
                                delete self._jobResolvers[jobId];
                                reject({ ok: false, error: 'conversion timeout (5min)' });
                            }
                        }, 300000);
                    });
                    self._bridge.convert_file(src, dst, fmt, jobId);
                    return resultPromise;
                }
                return { ok: false, error: 'no bridge' };
            });
        },

        convertVideoFile: function (src, dst, fmt, jobId) {
            var self = this;
            jobId = jobId || ('vjob_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8));
            return this.ready().then(function () {
                if (self._bridge && self._bridge.convert_video_file) {
                    var resultPromise = new Promise(function (resolve, reject) {
                        self._jobResolvers[jobId] = { resolve: resolve, reject: reject };
                        setTimeout(function () {
                            if (self._jobResolvers[jobId]) {
                                delete self._jobResolvers[jobId];
                                reject({ ok: false, error: 'video conversion timeout (5min)' });
                            }
                        }, 300000);
                    });
                    self._bridge.convert_video_file(src, dst, fmt, jobId);
                    return resultPromise;
                }
                return { ok: false, error: 'no bridge' };
            });
        },

        /**
         * 获取支持的转换格式列表
         * @returns {Promise<Array>}
         */
        getSupportedConversions: function () {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.get_supported_conversions) {
                    return this._bridge.get_supported_conversions().then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return []; }
                    });
                }
                return [];
            }.bind(this));
        },

        /**
         * 导出 CSV 格式转换
         * @param {string} srcPath
         * @param {string} dstPath
         * @param {string} fmt - "xlsx" / "tsv"
         * @returns {Promise<object>}
         */
        exportCsv: function (srcPath, dstPath, fmt) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.export_csv) {
                    return this._bridge.export_csv(srcPath, dstPath, fmt).then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return { ok: false, error: 'parse error' }; }
                    });
                }
                return { ok: false, error: 'no bridge' };
            }.bind(this));
        },

        /**
         * 获取转换历史
         * @returns {Promise<Array>}
         */
        getConversionHistory: function () {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.get_conversion_history) {
                    return this._bridge.get_conversion_history().then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return []; }
                    });
                }
                return [];
            }.bind(this));
        },

        /**
         * 追加一条转换历史记录
         * @param {object} entry - {src, dst, fmt, jobId, timestamp, status, error?}
         * @returns {Promise<object>}
         */
        appendConversionHistory: function (entry) {
          return this.ready().then(function () {
            if (this._bridge && this._bridge.append_conversion_history) {
              return this._bridge.append_conversion_history(JSON.stringify(entry)).then(function(result) {
                try { return JSON.parse(result); }
                catch (e) { return { ok: false, error: 'parse error' }; }
              });
            }
            return { ok: false, error: 'no bridge' };
          }.bind(this));
        },

        /**
         * 清空转换历史
         * @returns {Promise<object>}
         */
        clearConversionHistory: function () {
          return this.ready().then(function () {
            if (this._bridge && this._bridge.clear_conversion_history) {
              return this._bridge.clear_conversion_history().then(function(result) {
                try { return JSON.parse(result); }
                catch (e) { return { ok: false, error: 'parse error' }; }
              });
            }
            return { ok: false, error: 'no bridge' };
          }.bind(this));
        },

        /**
         * 检查 FFmpeg 可用性
         * @returns {Promise<object>}
         */
        checkFfmpegStatus: function () {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.check_ffmpeg_status) {
                    return this._bridge.check_ffmpeg_status().then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return { error: 'parse error' }; }
                    });
                }
                return { error: 'no bridge' };
            }.bind(this));
        },

        /**
         * 探测媒体元数据
         * @param {string} path
         * @returns {Promise<object>}
         */
        probeMediaInfo: function (path) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.probe_media_info) {
                    try {
                        return this._bridge.probe_media_info(path).then(function(res) { return JSON.parse(res); });
                    } catch (e) {
                        return { ok: false, error: 'parse error' };
                    }
                }
                return { ok: false, error: 'no bridge' };
            }.bind(this));
        },

        /**
         * 视频转码
         * @param {string} src
         * @param {string} dst
         * @param {string} format 目标格式 (mp4/mkv/avi/wmv/flv/mov/webm)
         * @param {string} jobId
         * @returns {Promise<object>}
         */
        convertVideoFile: function (src, dst, format, jobId) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.convert_video_file) {
                    try {
                        return this._bridge.convert_video_file(src, dst, format, jobId || '').then(function(res) { return JSON.parse(res); });
                    } catch (e) {
                        return { ok: false, error: 'parse error' };
                    }
                }
                return { ok: false, error: 'no bridge' };
            }.bind(this));
        },

        /**
         * 打开文件（系统默认程序）
         * @param {string} path
         * @returns {Promise<object>}
         */
        openPath: function (path) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.open_path) {
                    try {
                        return this._bridge.open_path(path).then(function(res) { return JSON.parse(res); });
                    } catch (e) {
                        return { ok: false, error: 'parse error' };
                    }
                }
                return { ok: false, error: 'no bridge' };
            }.bind(this));
        },

        /**
         * 应用图像编辑操作
         * @param {string} filePath
         * @param {Array} operations
         * @param {string} outputPath
         * @returns {Promise<object>}
         */
        applyImageEdit: function (filePath, operations, outputPath) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.apply_image_edit) {
                    try {
                        return this._bridge.apply_image_edit(
                            filePath,
                            JSON.stringify(operations),
                            outputPath || ''
                        ).then(function(res) { return JSON.parse(res); });
                    } catch (e) {
                        return { ok: false, error: 'parse error' };
                    }
                }
                return { ok: false, error: 'no bridge' };
            }.bind(this));
        },

        /**
         * 解压压缩包成员到内存
         * @param {string} archivePath
         * @param {string} memberName
         * @param {string} password
         * @returns {Promise<object>}
         */
        extractArchiveMember: function (archivePath, memberName, password) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.extract_archive_member) {
                    try {
                        return this._bridge.extract_archive_member(
                            archivePath, memberName, password || ''
                        ).then(function(res) { return JSON.parse(res); });
                    } catch (e) {
                        return { ok: false, error: 'parse error' };
                    }
                }
                return { ok: false, error: 'no bridge' };
            }.bind(this));
        },

        /**
         * 解锁加密压缩包
         * @param {string} archivePath
         * @param {string} password
         * @returns {Promise<object>}
         */
        unlockEncryptedArchive: function (archivePath, password) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.unlock_encrypted_archive) {
                    try {
                        return this._bridge.unlock_encrypted_archive(archivePath, password).then(function(res) { return JSON.parse(res); });
                    } catch (e) {
                        return { ok: false, error: 'parse error' };
                    }
                }
                return { ok: false, error: 'no bridge' };
            }.bind(this));
        },

        /**
         * 获取预览数据（通过 Python handler 分发）
         * @param {string} path
         * @returns {Promise<object>}
         */
        getPreview: function (path) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.get_preview) {
                    return this._bridge.get_preview(path).then(function(res) {
                        if (typeof res === 'string') {
                            try { return JSON.parse(res); } catch(e) { return { error: 'parse error' }; }
                        }
                        return res;
                    });
                }
                return { error: 'no bridge' };
            }.bind(this));
        },

        /**
         * 获取打开历史
         * @returns {Promise<Array>}
         */
        getHistory: function () {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.get_open_history) {
                    return this._bridge.get_open_history().then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return []; }
                    });
                }
                return [];
            }.bind(this));
        },

        /**
         * 添加一条打开历史
         * @param {string} path
         * @param {string} name
         * @param {string} ext
         * @param {string} mime
         * @returns {Promise<object>}
         */
        addHistory: function (path, name, ext, mime) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.add_to_history) {
                    return this._bridge.add_to_history(path || '', name || '', ext || '', mime || '').then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return { ok: false }; }
                    });
                }
                return { ok: false };
            }.bind(this));
        },

        /**
         * 清空打开历史
         * @returns {Promise<object>}
         */
        clearHistory: function () {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.clear_open_history) {
                    return this._bridge.clear_open_history().then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return { ok: false }; }
                    });
                }
                return { ok: false };
            }.bind(this));
        },

        /**
         * 移除一条打开历史
         * @param {string} path
         * @returns {Promise<object>}
         */
        removeHistoryItem: function (path) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.remove_history_item) {
                    return this._bridge.remove_history_item(path || '').then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return { ok: false }; }
                    });
                }
                return { ok: false };
            }.bind(this));
        },

        // ----------------------------------------------------------------
        //  Windows 文件关联 API
        // ----------------------------------------------------------------

        /**
         * 获取文件关联状态
         * @returns {Promise<object>}
         */
        getFileAssociationStatus: function () {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.get_file_association_status) {
                    return this._bridge.get_file_association_status().then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return { error: 'parse error' }; }
                    });
                }
                return { available: false };
            }.bind(this));
        },

        /**
         * 注册所有文件关联
         * @returns {Promise<object>}
         */
        registerFileAssociations: function () {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.register_file_associations) {
                    return this._bridge.register_file_associations().then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return { ok: false, error: 'parse error' }; }
                    });
                }
                return { ok: false, error: 'no bridge' };
            }.bind(this));
        },

        /**
         * 移除所有文件关联
         * @returns {Promise<object>}
         */
        unregisterFileAssociations: function () {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.unregister_file_associations) {
                    return this._bridge.unregister_file_associations().then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return { ok: false, error: 'parse error' }; }
                    });
                }
                return { ok: false, error: 'no bridge' };
            }.bind(this));
        },

        // ----------------------------------------------------------------
        //  右键菜单 Open With MMFB API
        // ----------------------------------------------------------------

        /**
         * 获取右键菜单注册状态
         * @returns {Promise<object>}
         */
        getShellExtensionStatus: function () {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.get_shell_extension_status) {
                    return this._bridge.get_shell_extension_status().then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return { error: 'parse error' }; }
                    });
                }
                return { supported: false };
            }.bind(this));
        },

        /**
         * 注册右键菜单 Open With MMFB
         * @returns {Promise<object>}
         */
        registerShellExtension: function () {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.register_shell_extension) {
                    return this._bridge.register_shell_extension().then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return { ok: false, error: 'parse error' }; }
                    });
                }
                return { ok: false, error: 'no bridge' };
            }.bind(this));
        },

        /**
         * 取消注册表右键菜单 Open With MMFB
         * @returns {Promise<object>}
         */
        unregisterShellExtension: function () {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.unregister_shell_extension) {
                    return this._bridge.unregister_shell_extension().then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return { ok: false, error: 'parse error' }; }
                    });
                }
                return { ok: false, error: 'no bridge' };
            }.bind(this));
        },

        /**
         * 获取编辑数据（通过 Python handler 分发）
         * @param {string} path
         * @returns {Promise<object>}
         */
        getEdit: function (path) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.get_edit) {
                    return this._bridge.get_edit(path).then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return { error: 'parse error' }; }
                    });
                }
                return { error: 'no bridge' };
            }.bind(this));
        },

        /**
         * 保存 docx 段落编辑
         * @param {string} filePath
         * @param {string} changesJson - JSON 数组 [{index, text, style}]
         * @returns {Promise<object>}
         */
        saveDocx: function (filePath, changesJson) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.save_docx) {
                    return this._bridge.save_docx(filePath || '', changesJson || '[]').then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return { ok: false, error: 'parse error' }; }
                    });
                }
                return { ok: false, error: 'no bridge' };
            }.bind(this));
        },

        // ----------------------------------------------------------------
        //  多窗口 / 分屏 API（新增）
        // ----------------------------------------------------------------

        /**
         * 新建 MMFB 窗口
         * @param {string} filePath - 可选，新窗口打开的文件
         * @returns {Promise<object>}
         */
        newWindow: function (filePath) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.new_window) {
                    return this._bridge.new_window(filePath || '').then(function(r) { return r; });
                }
                return { ok: false, error: 'no bridge' };
            }.bind(this));
        },

        /**
         * 关闭当前窗口
         * @returns {Promise<object>}
         */
        closeWindow: function () {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.close_window) {
                    return this._bridge.close_window().then(function(r) { return r; });
                }
                return { ok: false, error: 'no bridge' };
            }.bind(this));
        },

        /**
         * 切换当前窗口的分屏模式（进入/退出）
         * @returns {Promise<object>} {ok, split: boolean}
         */
        toggleSplit: function () {
            return this.ready().then(function () {
                if (this._bridge && typeof this._bridge.split_current_window === 'function') {
                    return this._bridge.split_current_window().then(function(r) {
                        try { return JSON.parse(r); } catch (e) { return r; }
                    });
                }
                return { ok: false, error: 'no bridge' };
            }.bind(this));
        },

        /**
         * 进入分屏模式（可指定左右文件）
         * @param {string} leftFile
         * @param {string} rightFile
         * @returns {Promise<object>}
         */
        enterSplit: function (leftFile, rightFile) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.enter_split) {
                    return this._bridge.enter_split(leftFile || '', rightFile || '').then(function(r) { return r; });
                }
                return { ok: false, error: 'no bridge' };
            }.bind(this));
        },

        /**
         * 退出分屏模式
         * @returns {Promise<object>}
         */
        exitSplit: function () {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.exit_split) {
                    return this._bridge.exit_split().then(function(r) { return r; });
                }
                return { ok: false, error: 'no bridge' };
            }.bind(this));
        },

        /**
         * 获取当前窗口状态
         * @returns {Promise<object>} {split, windowCount}
         */
        getWindowState: function () {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.get_window_state) {
                    return this._bridge.get_window_state().then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return {}; }
                    });
                }
                return {};
            }.bind(this));
        },

        // ----------------------------------------------------------------
        //  主题相关接口
        // ----------------------------------------------------------------

        /**
         * 读取当前持久化主题
         * @returns {Promise<string>} 'light' | 'dark' | 'warm'
         */
        getTheme: function () {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.get_theme) {
                    var t = this._bridge.get_theme();
                    return (t === 'light' || t === 'dark' || t === 'warm') ? t : 'warm';
                }
                return 'warm';
            }.bind(this));
        },

        /**
         * 检测系统主题
         * @returns {Promise<string>} 'dark' | 'light'
         */
        getSystemTheme: function () {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.get_system_theme) {
                    var t = this._bridge.get_system_theme();
                    return t === 'dark' ? 'dark' : 'light';
                }
                // 浏览器端兜底
                if (global.matchMedia && global.matchMedia('(prefers-color-scheme: dark)').matches) {
                    return 'dark';
                }
                return 'light';
            }.bind(this));
        },

        /**
         * 持久化主题偏好
         * @param {string} themeName - 'light' | 'dark' | 'warm'
         * @returns {Promise<boolean>}
         */
        setTheme: function (themeName) {
            return this.ready().then(function () {
                this._themeUserSet = true;
                if (this._bridge && this._bridge.set_theme) {
                    return this._bridge.set_theme(themeName);
                }
                return false;
            }.bind(this));
        },

        // ----------------------------------------------------------------
        //  自动更新 API
        // ----------------------------------------------------------------

        /**
         * 获取当前应用版本
         * @returns {Promise<{version, name}>}
         */
        getVersion: function () {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.get_version) {
                    try {
                        return this._bridge.get_version().then(r => JSON.parse(r));
                    } catch (e) {
                        return { version: '0.0.0', name: '' };
                    }
                }
                return { version: '0.0.0', name: '' };
            }.bind(this));
        },

        /**
         * 查询 GitHub Releases 是否有新版本（不阻塞）
         * 结果通过 onUpdateCheckResult 回调返回
         * @returns {Promise<string>} 返回空字符串（Slot 接口需要）
         */
        checkForUpdates: function () {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.check_for_updates) {
                    try {
                        this._bridge.check_for_updates();
                    } catch (e) {
                        // ignore
                    }
                }
                return '';
            }.bind(this));
        },

        /**
         * 下载更新安装器
         * @param {string} downloadUrl - 安装包 URL
         * @param {string} filename - 保存文件名（可选）
         * @returns {Promise<object>}
         */
        downloadUpdate: function (downloadUrl, filename) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.download_update) {
                    try {
                        return this._bridge.download_update(downloadUrl, filename || '').then(r => JSON.parse(r));
                    } catch (e) {
                        return { ok: false, error: 'parse error: ' + e.message };
                    }
                }
                return { ok: false, error: 'no bridge' };
            }.bind(this));
        },

        /**
         * 启动下载好的安装器并退出当前应用
         * @param {string} installerPath - 安装器本地路径
         * @returns {Promise<object>}
         */
        launchInstaller: function (installerPath) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.launch_installer) {
                    try {
                        return this._bridge.launch_installer(installerPath).then(r => JSON.parse(r));
                    } catch (e) {
                        return { ok: false, error: 'parse error' };
                    }
                }
                return { ok: false, error: 'no bridge' };
            }.bind(this));
        },

        /**
         * 跳过某个版本（不再提示）
         * @param {string} tag - 版本标签
         */
        skipVersion: function (tag) {
            if (this._bridge && this._bridge.skip_version && tag) {
                try {
                    this._bridge.skip_version(tag);
                } catch (e) {
                    // ignore
                }
            }
        },

        // ----------------------------------------------------------------
        //  系统托盘 API
        // ----------------------------------------------------------------

        /**
         * 显示托盘气泡通知
         * @param {string} title - 通知标题
         * @param {string} message - 通知内容
         * @param {string} iconType - "info" | "warning" | "critical"
         * @param {number} msecs - 显示毫秒数（默认 3000）
         * @returns {Promise<object>}
         */
        showTrayNotification: function (title, message, iconType, msecs) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.show_tray_notification) {
                    try {
                        return this._bridge.show_tray_notification(
                            title || '', message || '', iconType || 'info'
                        ).then(r => JSON.parse(r));
                    } catch (e) {
                        return { ok: false, error: 'parse error' };
                    }
                }
                return { ok: false, error: 'no bridge' };
            }.bind(this));
        },

        /**
         * 获取托盘图标状态
         * @returns {Promise<object>} {ok, visible}
         */
        getTrayStatus: function () {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.get_tray_status) {
                    try {
                        return this._bridge.get_tray_status().then(r => JSON.parse(r));
                    } catch (e) {
                        return { ok: false, visible: false };
                    }
                }
                return { ok: false, visible: false };
            }.bind(this));
        },

        // ----------------------------------------------------------------
        //  补充 API：SVG 转 PNG
        // ----------------------------------------------------------------

        /**
         * 将 SVG 栅格化为 PNG
         * @param {object} payload {src, width, height}
         * @returns {Promise<object>}
         */
        svgToPng: function (payload) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.svg_to_png) {
                    return this._bridge.svg_to_png(JSON.stringify(payload)).then(function(result) {
                        try { return JSON.parse(result); }
                        catch (e) { return { ok: false, error: 'parse error' }; }
                    });
                }
                return { ok: false, error: 'no bridge' };
            }.bind(this));
        },

        // ----------------------------------------------------------------
        //  补充 API：窗口标题 / 消息 / 文件对话框
        // ----------------------------------------------------------------

        /**
         * 设置窗口标题
         * @param {string} title
         * @returns {Promise<boolean>}
         */
        setWindowTitle: function (title) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.set_window_title) {
                    return this._bridge.set_window_title(title || '');
                }
                return false;
            }.bind(this));
        },

        /**
         * 发送消息到 Python
         * @param {string} message
         * @returns {Promise<boolean>}
         */
        sendMessage: function (message) {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.send_message) {
                    return this._bridge.send_message(message || '');
                }
                return false;
            }.bind(this));
        },

        /**
         * 打开文件选择对话框
         * @returns {Promise<object>} {path: string}
         */
        openFileDialog: function () {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.open_file_dialog) {
                    return this._bridge.open_file_dialog().then(function(result) {
                        if (!result) return { path: '' };
                        try { return JSON.parse(result); }
                        catch (e) { return { path: '' }; }
                    });
                }
                return { path: '' };
            }.bind(this));
        },

        /**
         * 打开字幕文件选择对话框
         * @returns {Promise<object>} {path: string}
         */
        openSubtitleDialog: function () {
            return this.ready().then(function () {
                if (this._bridge && this._bridge.open_subtitle_dialog) {
                    return this._bridge.open_subtitle_dialog().then(function(result) {
                        if (!result) return { path: '' };
                        try { return JSON.parse(result); }
                        catch (e) { return { path: '' }; }
                    });
                }
                return { path: '' };
            }.bind(this));
        },

        // ----------------------------------------------------------------
        //  离线 Fake Bridge（当 QWebChannel 不可用时的降级）
        // ----------------------------------------------------------------
        _create_fake_bridge: function () {
            console.warn('[MMFBBridge] using fake bridge (offline mode)');
            var self = this;
            return {
                ready: function () { return Promise.resolve({ mode: 'fake' }); },
                read_file: function () { return ''; },
                save_file: function () { return false; },
                get_file_info: function () { return '{}'; },
                list_dir: function () { return '[]'; },
                get_pdf_metadata: function () { return '{}'; },
                get_files_info: function () { return '[]'; },
                convert_file: function () { return JSON.stringify({ ok: false, error: 'offline' }); },
                get_supported_conversions: function () { return '[]'; },
                export_csv: function () { return JSON.stringify({ ok: false }); },
                open_path: function () { return JSON.stringify({ ok: false }); },
                apply_image_edit: function () { return JSON.stringify({ ok: false }); },
                extract_archive_member: function () { return JSON.stringify({ ok: false }); },
                unlock_encrypted_archive: function () { return JSON.stringify({ ok: false }); },
                get_conversion_history: function () { return '[]'; },
                clear_conversion_history: function () { return JSON.stringify({ok:false}); },
                append_conversion_history: function () { return JSON.stringify({ok:false}); },
                check_ffmpeg_status: function () { return JSON.stringify({ffmpeg:{ok:false,error:'offline'},ffprobe:{ok:false,error:'offline'}}); },
                probe_media_info: function () { return JSON.stringify({ok:false,error:'offline'}); },
                convert_video_file: function () { return JSON.stringify({ok:false,error:'offline'}); },
                show_files_dialog: function () { return ''; },
                show_subtitle_dialog: function () { return ''; },
                open_file_dialog: function () { return ''; },
                open_subtitle_dialog: function () { return ''; },
                set_window_title: function () { return true; },
                send_message: function () { return true; },
                svg_to_png: function () { return JSON.stringify({ ok: false, error: 'offline' }); },
                get_preview: function () { return JSON.stringify({ error: 'offline' }); },
                get_edit: function () { return JSON.stringify({ error: 'offline' }); },
                get_theme: function () {
                    try {
                        var t = localStorage.getItem('mmfb.theme');
                        return t || 'warm';
                    } catch (e) { return 'warm'; }
                },
                get_system_theme: function () {
                    if (global.matchMedia && global.matchMedia('(prefers-color-scheme: dark)').matches) {
                        return 'dark';
                    }
                    return 'light';
                },
                set_theme: function (name) {
                    try { localStorage.setItem('mmfb.theme', name); } catch (e) {}
                    return true;
                },
                new_window: function () {
                    // 在 fake 模式下使用浏览器新标签模拟
                    try {
                        global.open(location.href, '_blank');
                        return JSON.stringify({ ok: true });
                    } catch (e) {
                        return JSON.stringify({ ok: false, error: e.message });
                    }
                },
                close_window: function () {
                    try { global.close(); return JSON.stringify({ ok: true }); }
                    catch (e) { return JSON.stringify({ ok: false }); }
                },
                split_current_window: function () {
                    return JSON.stringify({ ok: false, error: 'split not available in offline mode' });
                },
                enter_split: function () { return JSON.stringify({ ok: false }); },
                exit_split: function () { return JSON.stringify({ ok: false }); },
                get_window_state: function () { return JSON.stringify({ split: false, windowCount: 1 }); },
                // 打开历史桩
                get_open_history: function () { return '[]'; },
                add_to_history: function () { return JSON.stringify({ok:false}); },
                clear_open_history: function () { return JSON.stringify({ok:false}); },
                remove_history_item: function () { return JSON.stringify({ok:false}); },
                // 右键菜单 API 桩
                get_shell_extension_status: function () {
                    return JSON.stringify({ supported: false, registered: false });
                },
                // 文件关联桩
                get_file_association_status: function () { return JSON.stringify({ available: false, error: 'offline' }); },
                register_file_associations: function () { return JSON.stringify({ ok: false, error: 'offline' }); },
                unregister_file_associations: function () { return JSON.stringify({ ok: false, error: 'offline' }); },
                // 右键菜单桩
                register_shell_extension: function () { return JSON.stringify({ ok: false, error: 'offline' }); },
                unregister_shell_extension: function () { return JSON.stringify({ ok: false, error: 'offline' }); },
                // 自动更新桩
                get_version: function () { return JSON.stringify({ version: '1.0.0', name: '' }); },
                check_for_updates: function () { return ''; },
                download_update: function () { return JSON.stringify({ ok: false, error: 'offline' }); },
                launch_installer: function () { return JSON.stringify({ ok: false, error: 'offline' }); },
                skip_version: function () {},
                // 托盘桩
                show_tray_notification: function () { return JSON.stringify({ ok: false, error: 'offline' }); },
                get_tray_status: function () { return JSON.stringify({ ok: false, visible: false }); },
                // Excel xlsx 编辑桩
                save_xlsx_cell: function () { return JSON.stringify({ ok: false, error: 'offline' }); },
                save_xlsx_cells: function () { return JSON.stringify({ ok: false, error: 'offline' }); },
                save_docx: function () { return JSON.stringify({ ok: false, error: 'offline' }); },
            };
        }
    };

    global.MMFBBridge = MMFBBridge;

    // Expose all methods under MMFBBridge.api for convenience
    // This allows MMFBBridge.api.applyImageEdit() style calls
    MMFBBridge.api = {};
    var api_methods = [
        'readFile', 'readFileBase64', 'saveFile', 'getFileInfo', 'listDir', 'getPdfMetadata',
        'getFilesInfo', 'saveXlsxCell', 'saveXlsxCells', 'convertFile',
        'getSupportedConversions', 'exportCsv', 'getConversionHistory',
        'appendConversionHistory', 'clearConversionHistory', 'checkFfmpegStatus',
        'probeMediaInfo', 'convertVideoFile', 'openPath',
        'applyImageEdit', 'extractArchiveMember', 'unlockEncryptedArchive',
        'getPreview', 'getEdit', 'saveDocx',
        'getHistory', 'addHistory', 'clearHistory', 'removeHistoryItem',
        'getFileAssociationStatus', 'registerFileAssociations',
        'unregisterFileAssociations',
        'getShellExtensionStatus', 'registerShellExtension',
        'unregisterShellExtension',
        'newWindow', 'closeWindow', 'toggleSplit', 'enterSplit',
        'exitSplit', 'getWindowState',
        'getTheme', 'getSystemTheme', 'setTheme',
        'getVersion', 'checkForUpdates', 'downloadUpdate', 'launchInstaller',
        'skipVersion',
        'showTrayNotification', 'getTrayStatus',
        // 补充遗漏的 API
        'svgToPng', 'setWindowTitle', 'sendMessage',
        'openFileDialog', 'openSubtitleDialog'];
    api_methods.forEach(function(name) {
        if (typeof MMFBBridge[name] === 'function') {
            MMFBBridge.api[name] = MMFBBridge[name].bind(MMFBBridge);
        }
    });

})(window);
