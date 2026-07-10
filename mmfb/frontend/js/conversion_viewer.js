/**
 * MMFBConversionViewer - 格式转换工作流
 *
 * 功能：
 * 1. 拖入文件 / 选择文件
 * 2. 批量转换队列
 * 3. 目标格式选择（动态根据源格式过滤）
 * 4. 转换进度条（conversionProgress 信号）
 * 5. 成功/失败/重试
 * 6. 输出文件打开（系统默认程序）
 * 7. 最近 10 条转换历史
 */
(function (global) {
  'use strict';

  var MMFBConversionViewer = function (root, options) {
    this.root = root;
    this.options = options || {};
    this.filePath = this.options.file_path || '';
    this._bridge = global.MMFBBridge || {};
    this._queue = [];       // [{src, dst, status, outputPath, error}]
    this._history = [];
    this._tab = 'convert';  // convert | history
    this._init();
  };

  // ============ 初始化 ============
  MMFBConversionViewer.prototype._init = function () {
    this._render();
    this._loadHistory();
    this._loadSupported();
  };

  // ============ 渲染主界面 ============
  MMFBConversionViewer.prototype._render = function () {
    var html =
      '<div class="conv-container">' +
        // 标签切换
        '<div class="conv-tabs">' +
          '<button class="conv-tab active" data-tab="convert">格式转换</button>' +
          '<button class="conv-tab" data-tab="history">转换历史</button>' +
        '</div>' +
        // 转换面板
        '<div class="conv-panel" data-panel="convert">' +
          // 拖入区
          '<div class="conv-dropzone">' +
            '<div class="conv-dropzone__icon">&#128230;</div>' +
            '<div class="conv-dropzone__text">拖入文件或点击选择</div>' +
            '<div class="conv-dropzone__hint">支持单个或批量转换</div>' +
            '<input type="file" class="conv-dropzone__input" multiple />' +
          '</div>' +
          // 源文件列表
          '<div class="conv-queue" style="display:none">' +
            '<div class="conv-queue__header">' +
              '<span>文件列表</span>' +
              '<span class="conv-queue__count" id="conv-queue-count"></span>' +
            '</div>' +
            '<div class="conv-queue__list" id="conv-queue-list"></div>' +
          '</div>' +
          // 批量目标格式
          '<div class="conv-bulk-action" style="display:none">' +
            '<label>批量目标格式</label>' +
            '<select class="conv-bulk-format" id="conv-bulk-format">' +
              '<option value="pdf">PDF (.pdf)</option>' +
              '<option value="html">HTML (.html)</option>' +
              '<option value="md">Markdown (.md)</option>' +
              '<option value="docx">Word (.docx)</option>' +
              '<option value="txt">纯文本 (.txt)</option>' +
              '<option value="png">PNG (.png)</option>' +
              '<option value="jpg">JPEG (.jpg)</option>' +
              '<option value="webp">WebP (.webp)</option>' +
              '<option value="csv">CSV (.csv)</option>' +
              '<option value="mp4">MP4 (.mp4)</option>' +
              '<option value="mkv">MKV (.mkv)</option>' +
              '<option value="avi">AVI (.avi)</option>' +
              '<option value="mov">MOV (.mov)</option>' +
              '<option value="webm">WebM (.webm)</option>' +
            '</select>' +
            '<button class="conv-btn conv-btn-primary" id="conv-batch-btn">批量转换</button>' +
          '</div>' +
          // 进度条
          '<div class="conv-progress-wrap" id="conv-progress-wrap" style="display:none">' +
            '<div class="conv-progress-bar">' +
              '<div class="conv-progress-fill" id="conv-progress-fill"></div>' +
            '</div>' +
            '<div class="conv-progress-text" id="conv-progress-text"></div>' +
          '</div>' +
          // 全部操作按钮
          '<div class="conv-actions-row" id="conv-actions-row" style="display:none">' +
            '<button class="conv-btn-secondary" id="conv-clear-all-btn">清空列表</button>' +
            '<button class="conv-btn-secondary" id="conv-clear-done-btn">清除已完成</button>' +
          '</div>' +
        '</div>' +
        // 历史面板
        '<div class="conv-panel" data-panel="history" style="display:none">' +
          '<div class="conv-history-list" id="conv-history-list"></div>' +
          '<div class="conv-history-empty" id="conv-history-empty">暂无转换记录</div>' +
          '<button class="conv-btn-secondary" id="conv-clear-history-btn" style="margin-top:16px">清除全部历史</button>' +
        '</div>' +
      '</div>';

    this.root.innerHTML = html;
    this._bindTabs();
    this._bindDropzone();
    this._bindQueueActions();
    this._bindHistoryActions();

    // 如果外部传入文件路径
    if (this.filePath) {
      this._addFile(this.filePath);
    }
  };

  // ============ 标签切换 ============
  MMFBConversionViewer.prototype._bindTabs = function () {
    var self = this;
    var tabs = this.root.querySelectorAll('.conv-tab');
    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        var name = tab.getAttribute('data-tab');
        self._switchTab(name);
      });
    });
  };

  MMFBConversionViewer.prototype._switchTab = function (name) {
    this._tab = name;
    // Tabs
    this.root.querySelectorAll('.conv-tab').forEach(function (t) {
      t.classList.toggle('active', t.getAttribute('data-tab') === name);
    });
    // Panels
    this.root.querySelectorAll('.conv-panel').forEach(function (p) {
      p.style.display = p.getAttribute('data-panel') === name ? '' : 'none';
    });
    if (name === 'history') {
      this._renderHistory();
    }
  };

  // ============ 拖入区 ============
  MMFBConversionViewer.prototype._bindDropzone = function () {
    var self = this;
    var dz = this.root.querySelector('.conv-dropzone');
    var input = this.root.querySelector('.conv-dropzone__input');

    // 拖拽事件
    dz.addEventListener('dragover', function (e) {
      e.preventDefault();
      e.stopPropagation();
      dz.classList.add('conv-dropzone--over');
    });
    dz.addEventListener('dragleave', function (e) {
      e.preventDefault();
      dz.classList.remove('conv-dropzone--over');
    });
    dz.addEventListener('drop', function (e) {
      e.preventDefault();
      e.stopPropagation();
      dz.classList.remove('conv-dropzone--over');
      self._handleDrop(e.dataTransfer.files);
    });

    // 点击选择
    dz.addEventListener('click', function (e) {
      if (e.target.tagName === 'INPUT') return;
      input.click();
    });
    input.addEventListener('change', function () {
      self._handleDrop(input.files);
      input.value = '';
    });
  };

  MMFBConversionViewer.prototype._handleDrop = function (fileList) {
    if (!fileList || !fileList.length) return;
    var files = [];
    for (var i = 0; i < fileList.length; i++) {
      files.push({ name: fileList[i].name, path: fileList[i].path || fileList[i].webkitRelativePath || fileList[i].name });
    }
    for (var j = 0; j < files.length; j++) {
      this._addFile(files[j].path, files[j].name);
    }
    this._updateQueueUI();
  };

  MMFBConversionViewer.prototype._addFile = function (path, name) {
    var ext = this._getExt(path);
    // 去重
    if (this._queue.some(function (item) { return item.src === path; })) return;
    if (!this._bridge || typeof this._bridge.getFileInfo !== 'function') return;

    var self = this;
    // 先获取文件信息确认存在
    var item = { src: path, name: name || path.split(/[\\/]/).pop(), ext: ext, status: 'pending', dstFormat: '', outputPath: '', progress: 0 };
    this._queue.push(item);

    this._bridge.getFileInfo(path).then(function (json) {
      try {
        var info = typeof json === 'string' ? JSON.parse(json) : json;
        if (info && info.error) {
          item.status = 'error';
          item.error = info.error;
          self._updateQueueUI();
        }
      } catch (e) {
        // 允许无 bridge 模式
      }
    });
  };

  // ============ 队列 UI ============
  MMFBConversionViewer.prototype._updateQueueUI = function () {
    var queueWrap = this.root.querySelector('.conv-queue');
    var bulkAction = this.root.querySelector('.conv-bulk-action');
    var actionsRow = document.getElementById
      ? null
      : null; // not needed

    if (this._queue.length === 0) {
      queueWrap.style.display = 'none';
      bulkAction.style.display = 'none';
      document.getElementById('conv-actions-row').style.display = 'none';
      return;
    }

    queueWrap.style.display = '';
    bulkAction.style.display = '';

    var countEl = document.getElementById('conv-queue-count');
    if (countEl) {
      countEl.textContent = this._queue.length + ' 个文件';
    }

    var listEl = document.getElementById('conv-queue-list');
    if (!listEl) return;

    var self = this;
    listEl.innerHTML = this._queue.map(function (item, idx) {
      var fmtIcon = { pdf: '&#128196;', html: '&#127448;', md: '&#128221;', docx: '&#128190;', txt: '&#128196;', png: '&#127912;', jpg: '&#127912;', webp: '&#127912;', csv: '&#128202;' };
      var icon = fmtIcon[item.dstFormat] || '&#128196;';
      var statusLabel = { pending: '等待中', converting: '转换中 ' + item.progress + '%', done: '完成', error: '失败', skipped: '跳过' };
      var statusClass = item.status;

      var actionsHtml = '';
      if (item.status === 'done') {
        actionsHtml = '<button class="conv-item-action" data-action="open" data-idx="' + idx + '" title="打开文件">&#128279;打开</button>';
      }
      if (item.status === 'error') {
        actionsHtml = '<button class="conv-item-action btn-retry" data-action="retry" data-idx="' + idx + '" title="重试">&#128260;重试</button>' +
                      '<button class="conv-item-action" data-action="remove" data-idx="' + idx + '" title="移除">&#128465;</button>';
      }
      if (item.status === 'pending' || item.status === 'skipped') {
        actionsHtml = '<button class="conv-item-action" data-action="remove" data-idx="' + idx + '" title="移除">&#128465;</button>';
      }
      if (item.status === 'converting') {
        // no action buttons while converting
      }

      return '<div class="conv-item ' + statusClass + '">' +
        '<span class="conv-item__icon">' + icon + '</span>' +
        '<div class="conv-item__info">' +
          '<div class="conv-item__name">' + self._escape(item.name) + '</div>' +
          '<div class="conv-item__sub">' + item.ext.toUpperCase() +
            (item.dstFormat ? ' -> ' + item.dstFormat.toUpperCase() : ' 未指定目标') +
            ' ' + (statusLabel[item.status] || item.status) + '</div>' +
          (item.status === 'converting'
            ? '<div class="conv-item__progress"><div class="conv-mini-bar"><div class="conv-mini-fill" style="width:' + item.progress + '%"></div></div></div>'
            : '') +
          (item.error ? '<div class="conv-item__error">' + self._escape(item.error) + '</div>' : '') +
        '</div>' +
        '<div class="conv-item__actions">' + actionsHtml + '</div>' +
      '</div>';
    }).join('');

    // 绑定行内操作按钮
    listEl.querySelectorAll('[data-action]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var action = btn.getAttribute('data-action');
        var idx = parseInt(btn.getAttribute('data-idx'), 10);
        if (action === 'remove') self._removeQueueItem(idx);
        if (action === 'retry') self._convertSingle(idx);
        if (action === 'open') self._openOutput(idx);
      });
    });

    // 全局操作按钮
    var actionsRow = document.getElementById('conv-actions-row');
    if (actionsRow) actionsRow.style.display = '';
  };

  MMFBConversionViewer.prototype._removeQueueItem = function (idx) {
    var item = this._queue[idx];
    if (!item) return;
    if (item.status === 'converting') return; // 转换中不可移除
    this._queue.splice(idx, 1);
    this._updateQueueUI();
  };

  // ============ 批量操作按钮 ============
  MMFBConversionViewer.prototype._bindQueueActions = function () {
    var self = this;

    // 批量转换
    var batchBtn = document.getElementById('conv-batch-btn');
    if (batchBtn) {
      batchBtn.addEventListener('click', function () {
        self._convertBatch();
      });
    }

    // 清空全部
    var clearAllBtn = document.getElementById('conv-clear-all-btn');
    if (clearAllBtn) {
      clearAllBtn.addEventListener('click', function () {
        var converting = self._queue.some(function (i) { return i.status === 'converting'; });
        if (converting) {
          alert('有文件正在转换中，请稍后操作');
          return;
        }
        self._queue = [];
        self._updateQueueUI();
      });
    }

    // 清除已完成
    var clearDoneBtn = document.getElementById('conv-clear-done-btn');
    if (clearDoneBtn) {
      clearDoneBtn.addEventListener('click', function () {
        self._queue = self._queue.filter(function (i) { return i.status !== 'done' && i.status !== 'error'; });
        self._updateQueueUI();
      });
    }
  };

  // ============ 格式选择 ============
  MMFBConversionViewer.prototype._getExt = function (path) {
    if (!path) return '';
    var m = path.match(/\.([^.]+)$/);
    return m ? m[1].toLowerCase() : '';
  };

  MMFBConversionViewer.prototype._getAllowedTargets = function (srcExt) {
    var map = {
      md:  ['html', 'docx', 'pdf', 'txt', 'png'],
      markdown: ['html', 'docx', 'pdf', 'txt', 'png'],
      html: ['md', 'docx', 'pdf', 'txt'],
      htm:  ['md', 'docx', 'pdf', 'txt'],
      docx: ['md', 'html', 'txt', 'pdf'],
      pdf:  ['txt', 'md', 'html', 'png'],
      xlsx: ['csv', 'tsv', 'html'],
      xls:  ['csv', 'tsv'],
      csv:  ['xlsx', 'html', 'md'],
      tsv:  ['xlsx', 'html', 'md'],
      png:  ['jpg', 'webp', 'bmp', 'tiff', 'gif', 'pdf'],
      jpg:  ['png', 'webp', 'bmp', 'tiff', 'gif', 'pdf'],
      jpeg: ['png', 'webp', 'bmp', 'tiff', 'gif', 'pdf'],
      webp: ['png', 'jpg', 'bmp', 'tiff', 'gif', 'pdf'],
      bmp:  ['png', 'jpg', 'webp', 'tiff', 'gif', 'pdf'],
      gif:  ['png', 'jpg', 'webp', 'bmp'],
      tiff: ['png', 'jpg', 'webp', 'bmp'],
      tif:  ['png', 'jpg', 'webp', 'bmp'],
      mp4:  ['mkv', 'avi', 'mov', 'webm', 'flv', 'wmv'],
      mkv:  ['mp4', 'avi', 'mov', 'webm', 'flv', 'wmv'],
      avi:  ['mp4', 'mkv', 'mov', 'webm', 'flv', 'wmv'],
      mov:  ['mp4', 'mkv', 'avi', 'webm', 'flv', 'wmv'],
      webm: ['mp4', 'mkv', 'avi', 'mov', 'flv'],
      flv:  ['mp4', 'mkv', 'avi', 'mov', 'webm'],
      wmv:  ['mp4', 'mkv', 'avi', 'mov', 'webm'],
      mp3:  ['mp4', 'wav', 'ogg', 'aac', 'flac'],
      wav:  ['mp4', 'mp3', 'ogg', 'aac', 'flac'],
      flac: ['mp4', 'mp3', 'ogg', 'wav'],
      aac:  ['mp4', 'mp3', 'wav'],
      ogg:  ['mp4', 'mp3', 'wav'],
      opus: ['mp4', 'mp3', 'wav'],
      ts:   ['mp4', 'mkv', 'avi'],
      m4a:  ['mp3', 'wav', 'ogg'],
      m4v:  ['mp4', 'mkv', 'avi'],
      wma:  ['mp4', 'mp3', 'wav'],
    };
    return map[srcExt] || ['pdf', 'html', 'md', 'txt'];
  };

  MMFBConversionViewer.prototype._getDefaultTarget = function (srcExt) {
    var dfm = { md: 'html', markdown: 'html', html: 'md', docx: 'md', pdf: 'txt',
                xlsx: 'csv', csv: 'xlsx', png: 'jpg', jpg: 'png' };
    return dfm[srcExt] || 'pdf';
  };

  // ============ 批量转换 ============
  MMFBConversionViewer.prototype._convertBatch = function () {
    if (this._queue.length === 0) return;

    var bulkSelect = document.getElementById('conv-bulk-format');
    if (!bulkSelect) return;
    var dstFormat = bulkSelect.value;

    // 检查队列中 pending 项
    var pending = this._queue.filter(function (item) { return item.status === 'pending'; });
    if (pending.length === 0) {
      alert('没有待转换的文件');
      return;
    }

    // 对每个 pending 项设置目标和输出路径
    var self = this;
    pending.forEach(function (item) {
      item.dstFormat = dstFormat;
      item.status = 'pending';
      item.progress = 0;
      var base = item.src.replace(/\.[^.]+$/, '');
      item.outputPath = base + '.' + dstFormat;
    });

    this._updateQueueUI();
    this._showGlobalProgress(0, pending.length, '准备转换...');

    // 逐个转换
    this._convertNext(0, pending);
  };

  MMFBConversionViewer.prototype._convertNext = function (index, list) {
    var self = this;
    if (index >= list.length) {
      this._hideGlobalProgress();
      this._updateQueueUI();
      this._loadHistory();
      return;
    }

    var item = list[index];
    this._doConvert(item).then(function () {
      self._updateQueueUI();
      self._showGlobalProgress(index + 1, list.length, '转换中...');
      // 短暂延迟避免 UI 卡顿
      setTimeout(function () {
        self._convertNext(index + 1, list);
      }, 100);
    }).catch(function () {
      self._updateQueueUI();
      self._showGlobalProgress(index + 1, list.length, '转换中...');
      setTimeout(function () {
        self._convertNext(index + 1, list);
      }, 100);
    });
  };

  // ============ 单个转换 ============
  MMFBConversionViewer.prototype._convertSingle = function (idx) {
    var item = this._queue[idx];
    if (!item) return;
    if (!item.dstFormat) {
      // 第一个允许的目标格式
      item.dstFormat = this._getAllowedTargets(item.ext)[0];
    }
    if (!item.outputPath) {
      item.outputPath = item.src.replace(/\.[^.]+$/, '.' + item.dstFormat);
    }
    var self = this;
    this._showGlobalProgress(0, 1, '转换中...');
    this._doConvert(item).then(function () {
      self._hideGlobalProgress();
      self._updateQueueUI();
    }).catch(function () {
      self._hideGlobalProgress();
      self._updateQueueUI();
    });
  };

  // ============ 核心转换逻辑 ============
  MMFBConversionViewer.prototype._doConvert = function (item) {
    var self = this;
    item.status = 'converting';
    item.progress = 0;

    var progressHandler = null;
    if (this._bridge && typeof this._bridge.onConversionProgress === 'function') {
      // 注册 progress 回调
    }

    // 为本次转换生成唯一 jobId
    item.jobId = 'batch_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6);

    var promise;
    if (this._bridge && typeof this._bridge.convertFile === 'function') {
      promise = this._bridge.convertFile(item.src, item.outputPath, item.dstFormat, item.jobId).then(function (result) {
        var r = typeof result === 'string' ? JSON.parse(result) : result;
        if (r && r.ok) {
          item.status = 'done';
          item.progress = 100;
          self._saveHistory(item);
        } else {
          item.status = 'error';
          item.error = (r && r.error) || '转换失败';
        }
      }).catch(function (err) {
        item.status = 'error';
        item.error = (err && err.message) || (err && err.error) || String(err);
      });
    } else {
      // fake mode fallback
      promise = new Promise(function (resolve) {
        setTimeout(function () {
          item.status = 'error';
          item.error = '转换服务不可用（离线模式）';
          resolve();
        }, 500);
      });
    }

    // 绑定 progress 信号（基于 jobId 匹配）
    var origProgressCb = null;
    if (this._bridge && typeof this._bridge.onConversionProgress === 'function') {
      origProgressCb = this._bridge.onConversionProgress;
    }
    if (this._bridge) {
      this._bridge.onConversionProgress = function (payload) {
        try {
          var data = typeof payload === 'string' ? JSON.parse(payload) : payload;
          if (data && data.jobId === item.jobId) {
            item.progress = Math.round((data.progress || 0) * 100);
            self._updateQueueUI();
          }
        } catch (e) {}
        // 转发给原始回调（如有）
        if (typeof origProgressCb === 'function') {
          origProgressCb(payload);
        }
      };
    }

    // promise 完成后还原 progress 回调
    promise.then(function (r) {
      if (self._bridge && typeof origProgressCb === 'function') {
        self._bridge.onConversionProgress = origProgressCb;
      }
      return r;
    }, function (err) {
      if (self._bridge && typeof origProgressCb === 'function') {
        self._bridge.onConversionProgress = origProgressCb;
      }
      throw err;
    });

    return promise;
  };

  // ============ 打开输出文件 ============
  MMFBConversionViewer.prototype._openOutput = function (idx) {
    var item = this._queue[idx];
    if (!item || !item.outputPath) return;
    if (this._bridge && typeof this._bridge.openPath === 'function') {
      this._bridge.openPath(item.outputPath);
    } else {
      // fallback
      var a = document.createElement('a');
      a.href = item.outputPath;
      a.target = '_blank';
      a.click();
    }
  };

  // ============ 全局进度条 ============
  MMFBConversionViewer.prototype._showGlobalProgress = function (cur, total, text) {
    var wrap = document.getElementById('conv-progress-wrap');
    var fill = document.getElementById('conv-progress-fill');
    var label = document.getElementById('conv-progress-text');
    if (wrap) wrap.style.display = '';
    if (fill) {
      var pct = total > 0 ? Math.round(cur / total * 100) : 0;
      fill.style.width = pct + '%';
    }
    if (label) label.textContent = text || '';
  };

  MMFBConversionViewer.prototype._hideGlobalProgress = function () {
    var wrap = document.getElementById('conv-progress-wrap');
    if (wrap) wrap.style.display = 'none';
  };

  // ============ 转换历史 ============
  MMFBConversionViewer.prototype._bindHistoryActions = function () {
    var self = this;
    var btn = document.getElementById('conv-clear-history-btn');
    if (btn) {
      btn.addEventListener('click', function () {
        if (!confirm('确认清除全部转换历史？')) return;
        if (self._bridge && typeof self._bridge.clear_conversion_history === 'function') {
          self._bridge.clear_conversion_history().then(function () {
            self._history = [];
            self._renderHistory();
          });
        } else {
          self._history = [];
          self._renderHistory();
        }
      });
    }
  };

  MMFBConversionViewer.prototype._loadHistory = function () {
    var self = this;
    if (this._bridge && typeof this._bridge.get_conversion_history === 'function') {
      this._bridge.get_conversion_history().then(function (json) {
        try {
          self._history = typeof json === 'string' ? JSON.parse(json) : json;
        } catch (e) {
          self._history = [];
        }
        if (self._tab === 'history') {
          self._renderHistory();
        }
      }).catch(function () {
        self._history = [];
      });
    }
  };

  MMFBConversionViewer.prototype._saveHistory = function (item) {
    var entry = {
      source: item.src,
      sourceName: item.name,
      sourceExt: item.ext,
      dstFormat: item.dstFormat,
      outputPath: item.outputPath,
      timestamp: new Date().toISOString()
    };
    if (this._bridge && typeof this._bridge.append_conversion_history === 'function') {
      this._bridge.append_conversion_history(JSON.stringify(entry));
    }
    this._history.unshift(entry);
    if (this._history.length > 10) this._history = this._history.slice(0, 10);
  };

  MMFBConversionViewer.prototype._renderHistory = function () {
    var listEl = document.getElementById('conv-history-list');
    var emptyEl = document.getElementById('conv-history-empty');
    if (!listEl || !emptyEl) return;

    if (!this._history.length) {
      listEl.innerHTML = '';
      emptyEl.style.display = '';
      return;
    }
    emptyEl.style.display = 'none';

    var self = this;
    listEl.innerHTML = this._history.map(function (item) {
      var time = item.timestamp ? new Date(item.timestamp).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '--';
      var okIcon = '&#10003;';
      return '<div class="conv-history-item">' +
        '<div class="conv-history-item__info">' +
          '<div class="conv-history-item__name">' + self._escape(item.sourceName || item.source.split(/[\\/]/).pop()) + '</div>' +
          '<div class="conv-history-item__detail">' + (item.sourceExt || '').toUpperCase() + ' -> ' + (item.dstFormat || '').toUpperCase() + '</div>' +
        '</div>' +
        '<div class="conv-history-item__time">' + time + '</div>' +
        '<button class="conv-item-action" data-action="open-history" data-path="' + self._escapeAttr(item.outputPath) + '" title="打开输出文件">&#128279;打开</button>' +
      '</div>';
    }).join('');

    // 绑定打开按钮
    listEl.querySelectorAll('[data-action="open-history"]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var path = btn.getAttribute('data-path');
        if (self._bridge && typeof self._bridge.openPath === 'function') {
          self._bridge.openPath(path);
        }
      });
    });
  };

  // ============ 加载支持列表 ============
  MMFBConversionViewer.prototype._loadSupported = function () {
    if (this._bridge && typeof this._bridge.getSupportedConversions === 'function') {
      this._bridge.getSupportedConversions().then(function () {}).catch(function () {});
    }
  };

  // ============ 工具函数 ============
  MMFBConversionViewer.prototype._escape = function (s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  };

  MMFBConversionViewer.prototype._escapeAttr = function (s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  };

  MMFBConversionViewer.prototype.destroy = function () {
    if (this.root) this.root.innerHTML = '';
  };

  global.MMFBConversionViewer = MMFBConversionViewer;

})(typeof window !== 'undefined' ? window : this);
