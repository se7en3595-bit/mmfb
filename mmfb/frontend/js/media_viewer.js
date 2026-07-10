/**
 * MMFB MediaViewer - 视频/音频播放模块
 *
 * 使用 HTML5 <video>/<audio> 原生标签播放媒体文件，提供：
 * 1. 自适应窗口的视频渲染
 * 2. 自定义播放控件（播放/暂停/进度条/音量/全屏）
 * 3. 字幕加载 (.srt/.ass)
 * 4. 播放速度调节
 * 5. 键盘快捷键 (空格/方向键/M/F)
 * 6. 音频模式的波形占位
 *
 * 调用方式:
 *   MMFBMediaViewer.init(rootEl, { filePath, fileName, mediaType?, mime?, format?, subtitlePaths? })
 *   MMFBMediaViewer.destroy()
 */
(function (global) {
    'use strict';

    var MMFBMediaViewer = {
        _root: null,
        _config: null,
        _media: null,
        _destroyed: false,
        _isVideo: true,
        _isDraggingProgress: false,
        _hideControlsTimer: null,
        _isPlaying: false,
        _subtitleTrack: null,

        /**
         * 初始化播放器
         */
        init: function (rootEl, config) {
            this._root = rootEl;
            this._config = config || {};
            this._destroyed = false;
            this._isVideo = (this._config.mediaType || 'video') === 'video';
            this._isPlaying = false;

            this._renderShell();
            this._initMedia();
        },

        /**
         * 销毁
         */
        destroy: function () {
            this._destroyed = true;
            this._clearHideTimer();
            if (this._subtitleTrack) {
                try { this._subtitleTrack.mode = 'disabled'; } catch (e) {}
            }
            if (this._media) {
                try {
                    this._media.pause();
                    this._media.removeAttribute('src');
                    this._media.load();
                } catch (e) {}
            }
            this._media = null;
            this._root = null;
        },

        /**
         * 渲染外壳 HTML
         */
        _renderShell: function () {
            if (!this._root) return;

            var fileName = this._escapeHtml(this._config.fileName || '');
            var format = this._escapeHtml(this._config.format || '');
            var mime = this._escapeHtml(this._config.mime || '');

            var mediaAttrs = this._isVideo
                ? 'autoplay playsinline'
                : 'autoplay';

            var mediaTag = this._isVideo
                ? '<video id="mmfb-media" class="mmfb-media-video" ' + mediaAttrs + '></video>'
                : '<audio id="mmfb-media" class="mmfb-media-audio" ' + mediaAttrs + '></audio>';

            // 音频模式显示中央图标
            var audioIconHtml = this._isVideo ? '' :
                '<div class="mmfb-audio-icon">' +
                '<div class="mmfb-audio-icon__symbol">&#9835;</div>' +
                '<div class="mmfb-audio-icon__name" id="mmfb-audio-name">' + fileName + '</div>' +
                '</div>';

            this._root.innerHTML =
                '<div class="mmfb-media-viewer">' +
                '  <div class="mmfb-media-stage" id="mmfb-media-stage">' +
                audioIconHtml +
                mediaTag +
                '    <div class="mmfb-media-controls" id="mmfb-media-controls">' +
                '      <div class="mmfb-progress-bar" id="mmfb-progress-bar">' +
                '        <div class="mmfb-progress-buffer" id="mmfb-progress-buffer"></div>' +
                '        <div class="mmfb-progress-current" id="mmfb-progress-current">' +
                '          <div class="mmfb-progress-thumb"></div>' +
                '        </div>' +
                '      </div>' +
                '      <div class="mmfb-controls-row">' +
                '        <div class="mmfb-controls-left">' +
                '          <button class="mmfb-btn mmfb-btn-play" id="mmfb-btn-play" title="播放/暂停 (空格)">&#9654;</button>' +
                '          <button class="mmfb-btn mmfb-btn-skip" id="mmfb-btn-backward" title="后退 5s">&#9664;&#9664;</button>' +
                '          <button class="mmfb-btn mmfb-btn-skip" id="mmfb-btn-forward" title="前进 5s">&#9654;&#9654;</button>' +
                '          <span class="mmfb-time" id="mmfb-time">0:00 / 0:00</span>' +
                '        </div>' +
                '        <div class="mmfb-controls-right">' +
                '          <div class="mmfb-volume-group">' +
                '            <button class="mmfb-btn mmfb-btn-volume" id="mmfb-btn-mute" title="静音 (M)">&#128266;</button>' +
                '            <input type="range" class="mmfb-volume-slider" id="mmfb-volume-slider" min="0" max="100" value="100" title="音量">' +
                '          </div>' +
                '          <select class="mmfb-select mmfb-speed-select" id="mmfb-speed-select" title="播放速度">' +
                '            <option value="0.5">0.5x</option>' +
                '            <option value="0.75">0.75x</option>' +
                '            <option value="1" selected>1x</option>' +
                '            <option value="1.25">1.25x</option>' +
                '            <option value="1.5">1.5x</option>' +
                '            <option value="2">2x</option>' +
                '          </select>' +
                '          <button class="mmfb-btn mmfb-btn-subtitle" id="mmfb-btn-subtitle" title="字幕">&#128172;</button>' +
                '          <button class="mmfb-btn mmfb-btn-fullscreen" id="mmfb-btn-fullscreen" title="全屏 (F)">&#9974;</button>' +
                '        </div>' +
                '      </div>' +
                '    </div>' +
                '    <div class="mmfb-subtitle-popup" id="mmfb-subtitle-popup"></div>' +
                '  </div>' +
                '</div>';

            this._bindEvents();
        },

        /**
         * 初始化媒体元素
         */
        _initMedia: function () {
            var self = this;
            this._media = this._root.querySelector('#mmfb-media');
            if (!this._media) return;

            // 设置源文件路径
            var filePath = this._config.filePath || '';
            if (filePath) {
                // 将 Windows 路径转为 file:// URL
                var fileUrl = this._pathToFileUrl(filePath);
                this._media.src = fileUrl;
            }

            // 事件监听
            this._media.addEventListener('loadedmetadata', function () {
                self._updateTimeDisplay();
                self._updateFooter();
            });

            this._media.addEventListener('timeupdate', function () {
                if (!self._isDraggingProgress) {
                    self._updateProgress();
                }
                self._updateTimeDisplay();
            });

            this._media.addEventListener('play', function () {
                self._isPlaying = true;
                self._updatePlayButton();
            });

            this._media.addEventListener('pause', function () {
                self._isPlaying = false;
                self._updatePlayButton();
            });

            this._media.addEventListener('ended', function () {
                self._isPlaying = false;
                self._updatePlayButton();
            });

            this._media.addEventListener('progress', function () {
                self._updateBuffer();
            });

            this._media.addEventListener('error', function () {
                self._showError();
            });

            this._media.addEventListener('waiting', function () {
                self._showBuffering(true);
            });

            this._media.addEventListener('canplay', function () {
                self._showBuffering(false);
            });

            // 双击全屏
            this._media.addEventListener('dblclick', function () {
                self._toggleFullscreen();
            });

            // 单击播放/暂停
            this._media.addEventListener('click', function () {
                self._togglePlay();
            });
        },

        /**
         * 绑定控件事件
         */
        _bindEvents: function () {
            var self = this;
            var root = this._root;
            if (!root) return;

            var btnPlay = root.querySelector('#mmfb-btn-play');
            if (btnPlay) btnPlay.addEventListener('click', function (e) { e.stopPropagation(); self._togglePlay(); });

            var btnBack = root.querySelector('#mmfb-btn-backward');
            if (btnBack) btnBack.addEventListener('click', function (e) { e.stopPropagation(); self._skip(-5); });

            var btnForward = root.querySelector('#mmfb-btn-forward');
            if (btnForward) btnForward.addEventListener('click', function (e) { e.stopPropagation(); self._skip(5); });

            var btnMute = root.querySelector('#mmfb-btn-mute');
            if (btnMute) btnMute.addEventListener('click', function (e) { e.stopPropagation(); self._toggleMute(); });

            var btnFullscreen = root.querySelector('#mmfb-btn-fullscreen');
            if (btnFullscreen) btnFullscreen.addEventListener('click', function (e) { e.stopPropagation(); self._toggleFullscreen(); });

            var btnSubtitle = root.querySelector('#mmfb-btn-subtitle');
            if (btnSubtitle) btnSubtitle.addEventListener('click', function (e) { e.stopPropagation(); self._toggleSubtitleMenu(); });

            var volumeSlider = root.querySelector('#mmfb-volume-slider');
            if (volumeSlider) {
                volumeSlider.addEventListener('input', function (e) {
                    e.stopPropagation();
                    self._setVolume(e.target.value / 100);
                });
            }

            var speedSelect = root.querySelector('#mmfb-speed-select');
            if (speedSelect) {
                speedSelect.addEventListener('change', function (e) {
                    e.stopPropagation();
                    self._setPlaybackRate(parseFloat(e.target.value));
                });
            }

            // 进度条拖拽
            var progressBar = root.querySelector('#mmfb-progress-bar');
            if (progressBar) {
                progressBar.addEventListener('click', function (e) {
                    e.stopPropagation();
                    self._seekToPosition(e);
                });

                progressBar.addEventListener('mousedown', function (e) {
                    self._isDraggingProgress = true;
                    self._seekToPosition(e);
                });
            }

            document.addEventListener('mousemove', function (e) {
                if (self._isDraggingProgress) {
                    var bar = self._root.querySelector('#mmfb-progress-bar');
                    if (bar) {
                        var rect = bar.getBoundingClientRect();
                        var ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
                        self._seekToRatio(ratio);
                    }
                }
            });

            document.addEventListener('mouseup', function () {
                self._isDraggingProgress = false;
            });

            // 键盘快捷键
            document.addEventListener('keydown', function (e) {
                if (self._destroyed) return;
                switch (e.key) {
                    case ' ':
                        e.preventDefault();
                        self._togglePlay();
                        break;
                    case 'ArrowLeft':
                        e.preventDefault();
                        self._skip(-5);
                        break;
                    case 'ArrowRight':
                        e.preventDefault();
                        self._skip(5);
                        break;
                    case 'ArrowUp':
                        e.preventDefault();
                        self._adjustVolume(0.1);
                        break;
                    case 'ArrowDown':
                        e.preventDefault();
                        self._adjustVolume(-0.1);
                        break;
                    case 'm':
                    case 'M':
                        self._toggleMute();
                        break;
                    case 'f':
                    case 'F':
                        self._toggleFullscreen();
                        break;
                }
            });

            // 鼠标移动显示控件
            var stage = root.querySelector('#mmfb-media-stage');
            if (stage) {
                stage.addEventListener('mousemove', function () {
                    self._showControls();
                });
                stage.addEventListener('mouseleave', function () {
                    if (self._isPlaying) self._scheduleHideControls();
                });
            }
        },

        /**
         * 播放/暂停切换
         */
        _togglePlay: function () {
            if (!this._media) return;
            if (this._media.paused) {
                this._media.play().catch(function () {});
            } else {
                this._media.pause();
            }
        },

        /**
         * 更新播放按钮图标
         */
        _updatePlayButton: function () {
            var btn = this._root.querySelector('#mmfb-btn-play');
            if (btn) {
                btn.innerHTML = this._isPlaying ? '&#10074;&#10074;' : '&#9654;';
            }
        },

        /**
         * 跳转
         */
        _skip: function (seconds) {
            if (!this._media) return;
            this._media.currentTime = Math.max(0, Math.min(
                this._media.duration || 0,
                this._media.currentTime + seconds
            ));
        },

        /**
         * 设置音量
         */
        _setVolume: function (value) {
            if (!this._media) return;
            this._media.volume = Math.max(0, Math.min(1, value));
            this._media.muted = false;
            this._updateVolumeIcon();
        },

        /**
         * 调整音量
         */
        _adjustVolume: function (delta) {
            if (!this._media) return;
            this._setVolume(this._media.volume + delta);
            var slider = this._root.querySelector('#mmfb-volume-slider');
            if (slider) slider.value = Math.round(this._media.volume * 100);
        },

        /**
         * 静音切换
         */
        _toggleMute: function () {
            if (!this._media) return;
            this._media.muted = !this._media.muted;
            this._updateVolumeIcon();
        },

        /**
         * 更新音量图标
         */
        _updateVolumeIcon: function () {
            var btn = this._root.querySelector('#mmfb-btn-mute');
            if (!btn || !this._media) return;
            if (this._media.muted || this._media.volume === 0) {
                btn.innerHTML = '&#128263;';
            } else if (this._media.volume < 0.5) {
                btn.innerHTML = '&#128265;';
            } else {
                btn.innerHTML = '&#128266;';
            }
        },

        /**
         * 设置播放速度
         */
        _setPlaybackRate: function (rate) {
            if (!this._media) return;
            this._media.playbackRate = rate;
        },

        /**
         * 进度条点击
         */
        _seekToPosition: function (e) {
            if (!this._media) return;
            var bar = this._root.querySelector('#mmfb-progress-bar');
            if (!bar) return;
            var rect = bar.getBoundingClientRect();
            var ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            this._seekToRatio(ratio);
        },

        /**
         * 按比率跳转
         */
        _seekToRatio: function (ratio) {
            if (!this._media || !this._media.duration) return;
            this._media.currentTime = ratio * this._media.duration;
            this._updateProgress();
        },

        /**
         * 更新进度条
         */
        _updateProgress: function () {
            if (!this._media || !this._root) return;
            var current = this._media.currentTime || 0;
            var duration = this._media.duration || 0;
            var ratio = duration > 0 ? current / duration : 0;

            var progressEl = this._root.querySelector('#mmfb-progress-current');
            if (progressEl) {
                progressEl.style.width = (ratio * 100) + '%';
            }
        },

        /**
         * 更新缓冲条
         */
        _updateBuffer: function () {
            if (!this._media || !this._root) return;
            if (this._media.buffered.length === 0) return;
            var buffered = this._media.buffered.end(this._media.buffered.length - 1);
            var duration = this._media.duration || 0;
            if (duration <= 0) return;

            var bufferEl = this._root.querySelector('#mmfb-progress-buffer');
            if (bufferEl) {
                bufferEl.style.width = ((buffered / duration) * 100) + '%';
            }
        },

        /**
         * 更新时间显示
         */
        _updateTimeDisplay: function () {
            if (!this._media || !this._root) return;
            var current = this._media.currentTime || 0;
            var duration = this._media.duration || 0;
            var timeEl = this._root.querySelector('#mmfb-time');
            if (timeEl) {
                timeEl.textContent = this._formatTime(current) + ' / ' + this._formatTime(duration);
            }
        },

        /**
         * 格式化时间
         */
        _formatTime: function (seconds) {
            if (!seconds || isNaN(seconds)) return '0:00';
            var h = Math.floor(seconds / 3600);
            var m = Math.floor((seconds % 3600) / 60);
            var s = Math.floor(seconds % 60);
            if (h > 0) {
                return h + ':' + this._pad(m) + ':' + this._pad(s);
            }
            return m + ':' + this._pad(s);
        },

        _pad: function (n) {
            return n < 10 ? '0' + n : String(n);
        },

        /**
         * 全屏切换
         */
        _toggleFullscreen: function () {
            var stage = this._root.querySelector('#mmfb-media-stage');
            if (!stage) return;

            if (document.fullscreenElement) {
                document.exitFullscreen();
            } else {
                stage.requestFullscreen().catch(function () {});
            }
        },

        /**
         * 字幕菜单切换
         */
        _toggleSubtitleMenu: function () {
            var popup = this._root.querySelector('#mmfb-subtitle-popup');
            if (!popup) return;

            if (popup.classList.contains('visible')) {
                popup.classList.remove('visible');
                return;
            }

            var self = this;
            var subtitles = this._config.subtitlePaths || [];
            var html = '<div class="mmfb-subtitle-title">字幕轨道</div>';

            // 关闭字幕选项
            html += '<div class="mmfb-subtitle-item" data-action="off">关闭字幕</div>';

            // 从 Python 扫描到的字幕文件
            subtitles.forEach(function (sub) {
                html += '<div class="mmfb-subtitle-item" data-path="' + self._escapeAttr(sub.path) + '">' +
                    self._escapeHtml(sub.name) + ' (' + self._escapeHtml(sub.format) + ')</div>';
            });

            // 从 bridge 加载字幕文件
            html += '<div class="mmfb-subtitle-item mmfb-subtitle-load" data-action="load">从文件加载...</div>';

            popup.innerHTML = html;
            popup.classList.add('visible');

            // 绑定点击
            var items = popup.querySelectorAll('.mmfb-subtitle-item');
            items.forEach(function (item) {
                item.addEventListener('click', function () {
                    var action = item.getAttribute('data-action');
                    var path = item.getAttribute('data-path');
                    if (action === 'off') {
                        self._disableSubtitle();
                    } else if (action === 'load') {
                        self._loadSubtitleFromFile();
                    } else if (path) {
                        self._loadSubtitle(path);
                    }
                    popup.classList.remove('visible');
                });
            });
        },

        /**
         * 加载字幕 (通过 bridge 读取文件内容)
         */
        _loadSubtitle: function (path) {
            if (!global.MMFBBridge || !global.MMFBBridge.api) return;
            var self = this;
            global.MMFBBridge.api.readFile(path).then(function (content) {
                self._applySubtitle(content, path);
            });
        },

        /**
         * 从文件选择加载字幕
         */
        _loadSubtitleFromFile: function () {
            if (!global.MMFBBridge || !global.MMFBBridge.call) return;
            var self = this;
            global.MMFBBridge.call('open_subtitle_dialog', [], function (result) {
                if (result && result.path) {
                    self._loadSubtitle(result.path);
                }
            });
        },

        /**
         * 应用字幕内容
         */
        _applySubtitle: function (content, path) {
            if (!this._media) return;

            // 移除旧 track
            var oldTracks = this._media.querySelectorAll('track');
            oldTracks.forEach(function (t) { t.remove(); });

            // 创建 Blob URL
            var blob = new Blob([content], { type: 'text/vtt' });
            var url = URL.createObjectURL(blob);

            var track = document.createElement('track');
            track.kind = 'subtitles';
            track.src = url;
            track.srclang = 'zh';
            track.label = 'Subtitle';
            track.default = true;
            track.mode = 'showing';
            this._media.appendChild(track);
            this._subtitleTrack = track;
        },

        /**
         * 禁用字幕
         */
        _disableSubtitle: function () {
            if (this._subtitleTrack) {
                this._subtitleTrack.mode = 'disabled';
            }
            var tracks = this._media.querySelectorAll('track');
            tracks.forEach(function (t) { t.remove(); });
            this._subtitleTrack = null;
        },

        /**
         * 显示/隐藏控件
         */
        _showControls: function () {
            var controls = this._root.querySelector('#mmfb-media-controls');
            if (controls) controls.classList.remove('hidden');
            this._clearHideTimer();
            if (this._isPlaying) this._scheduleHideControls();
        },

        _scheduleHideControls: function () {
            var self = this;
            this._clearHideTimer();
            this._hideControlsTimer = setTimeout(function () {
                var controls = self._root.querySelector('#mmfb-media-controls');
                if (controls) controls.classList.add('hidden');
            }, 3000);
        },

        _clearHideTimer: function () {
            if (this._hideControlsTimer) {
                clearTimeout(this._hideControlsTimer);
                this._hideControlsTimer = null;
            }
        },

        /**
         * 显示缓冲指示
         */
        _showBuffering: function (show) {
            var stage = this._root.querySelector('#mmfb-media-stage');
            if (!stage) return;
            if (show) {
                stage.classList.add('buffering');
            } else {
                stage.classList.remove('buffering');
            }
        },

        /**
         * 显示错误
         */
        _showError: function () {
            if (!this._root) return;
            var stage = this._root.querySelector('#mmfb-media-stage');
            if (stage) {
                stage.innerHTML =
                    '<div class="mmfb-media-error">' +
                    '<div class="mmfb-media-error__icon">&#9888;</div>' +
                    '<div>无法播放此媒体文件</div>' +
                    '<div class="mmfb-media-error__hint">格式可能不受支持或文件已损坏</div>' +
                    '</div>';
            }
        },

        /**
         * 更新底部状态栏
         */
        _updateFooter: function () {
            if (!global.MMFBLayout) return;
            var format = this._config.format || '';
            var mime = this._config.mime || '';
            var parts = [];
            if (format) parts.push(format);
            if (mime) parts.push(mime);
            global.MMFBLayout.setFooterLeft(parts.join(' | '));
        },

        /**
         * Windows 路径转 file:// URL
         */
        _pathToFileUrl: function (path) {
            // C:\foo\bar.mp4 -> file:///C:/foo/bar.mp4
            var normalized = path.replace(/\\/g, '/');
            if (normalized.charAt(0) !== '/') {
                normalized = '/' + normalized;
            }
            return 'file://' + normalized;
        },

        /**
         * HTML 转义
         */
        _escapeHtml: function (str) {
            if (str === null || str === undefined) return '';
            var div = document.createElement('div');
            div.appendChild(document.createTextNode(String(str)));
            return div.innerHTML;
        },

        _escapeAttr: function (str) {
            return String(str).replace(/"/g, '&quot;').replace(/</g, '&lt;');
        },
    };

    global.MMFBMediaViewer = MMFBMediaViewer;

})(window);
