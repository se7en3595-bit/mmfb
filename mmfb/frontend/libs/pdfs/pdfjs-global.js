// pdfjs-global.js
// 在 file:// 协议下，Chromium 的 fetch() 受 CORS 限制（即使 --allow-file-access-from-files
// 也只放行 XMLHttpRequest，不放行 fetch）。所以采用 XHR + Blob URL 策略加载 ESM 模块，
// 然后再用动态 import() 注入 window.pdfjsLib。
//
// 同时把 worker 也用相同策略转成 Blob URL，避免 worker 创建时的同源限制。

(function () {
    'use strict';

    var MODULE_URL = './pdf.min.mjs';
    var WORKER_URL = './pdf.worker.min.mjs';

    function xhrAsBlob(url) {
        return new Promise(function (resolve, reject) {
            var xhr = new XMLHttpRequest();
            xhr.open('GET', url, true);
            xhr.responseType = 'blob';
            xhr.onload = function () {
                if (xhr.status >= 200 && xhr.status < 300) {
                    resolve(xhr.response);
                } else {
                    reject(new Error('XHR 加载失败: ' + url + ' status=' + xhr.status));
                }
            };
            xhr.onerror = function () {
                reject(new Error('XHR 网络错误: ' + url));
            };
            xhr.send();
        });
    }

    function showError(msg) {
        console.error('[PDF.js] ' + msg);
        if (typeof window !== 'undefined') {
            window.__pdfjsLoadError = msg;
        }
    }

    // 主流程
    xhrAsBlob(MODULE_URL)
        .then(function (blob) {
            var blobUrl = URL.createObjectURL(blob);
            // 动态 import 一个 Blob URL，绕开 file:// CORS
            return import(blobUrl).then(function (mod) {
                URL.revokeObjectURL(blobUrl);
                var lib = mod && (mod.default || mod);
                if (!lib) {
                    throw new Error('pdf.min.mjs 没有可用的导出');
                }
                window.pdfjsLib = lib;
                window['pdfjsLib-build'] = lib.version || '';
            });
        })
        .then(function () {
            // 同步设置 worker blob URL
            return xhrAsBlob(WORKER_URL);
        })
        .then(function (workerBlob) {
            window.__pdfWorkerUrl = URL.createObjectURL(workerBlob);
            console.log('[PDF.js] ESM 模块 + worker 已通过 XHR+Blob 注入成功');
        })
        .catch(function (e) {
            showError('Failed to load: ' + (e && e.message ? e.message : String(e)));
        });
})();
