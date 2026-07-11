// pdfjs-global.js
// 在 file:// 协议下，Chromium 的 fetch() 受 CORS 限制。
// 采用 XHR + Blob URL + script 标签注入策略加载 ESM 模块。

(function () {
'use strict';

// 使用绝对路径，避免 hash 路由改变时相对路径解析错误
var _baseUrl;
try {
    // 优先使用 document.currentScript 的 src 计算 baseUrl（最准确）
    var scriptEl = document.currentScript;
    if (scriptEl && scriptEl.src) {
        _baseUrl = scriptEl.src.replace(/\/[^\/]*$/, '/');
    } else {
        _baseUrl = (document.baseURI || '').replace(/#/g, '').replace(/\/[^\/]*$/, '/');
    }
} catch (e) {
    _baseUrl = window.location.href.split('#')[0].replace(/\/[^\/]*$/, '/');
}

// pdfjs-global.js 位于 libs/pdfs/，PDF.js 模块在 libs/pdfjs/
var MODULE_URL = _baseUrl + '../pdfjs/pdf.min.mjs';
var WORKER_URL = _baseUrl + '../pdfjs/pdf.worker.min.mjs';

// 调试输出
console.log('[PDF.js] baseUrl:', _baseUrl);
console.log('[PDF.js] MODULE_URL:', MODULE_URL);
console.log('[PDF.js] WORKER_URL:', WORKER_URL);

function xhrAsText(url) {
    return new Promise(function (resolve, reject) {
        console.log('[PDF.js] XHR GET ' + url);
        var xhr = new XMLHttpRequest();
        xhr.open('GET', url, true);
        xhr.onload = function () {
            console.log('[PDF.js] XHR onload status:', xhr.status);
            if (xhr.status >= 200 && xhr.status < 300) {
                resolve(xhr.responseText);
            } else {
                reject(new Error('XHR load failed: ' + url + ' status=' + xhr.status));
            }
        };
        xhr.onerror = function () {
            console.error('[PDF.js] XHR network error for ' + url);
            reject(new Error('XHR network error: ' + url));
        };
        xhr.ontimeout = function () {
            console.error('[PDF.js] XHR timeout for ' + url);
            reject(new Error('XHR timeout: ' + url));
        };
        xhr.timeout = 30000; // 30s
        xhr.send();
    });
}

function createWorkerBlobUrl(workerScript) {
    var blob = new Blob([workerScript], { type: 'application/javascript' });
    return URL.createObjectURL(blob);
}

function injectScript(url) {
    return new Promise(function (resolve, reject) {
        var script = document.createElement('script');
        script.type = 'module';
        script.src = url;
        script.onload = function () { resolve(); };
        script.onerror = function () { reject(new Error('script load failed: ' + url)); };
        (document.head || document.documentElement).appendChild(script);
    });
}

// 主流程：先加载模块源码 + worker 源码，然后注入
var _loaded = false;
var _loadPromise = null;

function doLoad() {
    if (_loaded) return Promise.resolve();
    if (_loadPromise) return _loadPromise;

    _loadPromise = xhrAsText(MODULE_URL).then(function (moduleSrc) {
        // XHR 成功：将模块源码转为 Blob URL 并注入
        console.log('[PDF.js] XHR module success, size:', moduleSrc.length);
        var blob = new Blob([moduleSrc], { type: 'application/javascript' });
        var blobUrl = URL.createObjectURL(blob);
        return injectScript(blobUrl).then(function () {
            URL.revokeObjectURL(blobUrl);
        });
    }).catch(function (err) {
        // XHR 失败：降级使用 <script type="module" src="..."> 直接加载
        console.warn('[PDF.js] XHR failed, falling back to direct script tag:', err && err.message || String(err));
        return new Promise(function (resolve, reject) {
            var script = document.createElement('script');
            script.type = 'module';
            script.src = MODULE_URL;
            script.onload = function () { console.log('[PDF.js] direct script onload'); resolve(); };
            script.onerror = function (e) { reject(new Error('direct script load failed: ' + MODULE_URL)); };
            (document.head || document.documentElement).appendChild(script);
        });
    }).then(function () {
        // 模块已就绪，加载 worker（统一 XHR 策略）
        console.log('[PDF.js] module ready, loading worker...');
        return xhrAsText(WORKER_URL);
    }).then(function (workerSrc) {
        var workerBlob = new Blob([workerSrc], { type: 'application/javascript' });
        window.__pdfWorkerUrl = URL.createObjectURL(workerBlob);
        console.log('[PDF.js] ESM module + worker loaded successfully');
        _loaded = true;
    }).catch(function (e) {
        console.error('[PDF.js] Failed to load module or worker:', e && e.message ? e.message : String(e));
        // 不设置 _loaded，允许重试
    });

    return _loadPromise;
}

// 启动加载（不阻塞页面）
if (document.readyState === 'loading') {
    window.addEventListener('DOMContentLoaded', doLoad);
} else {
    doLoad();
}

// 暴露状态
window.__pdfjsReady = function () {
    return _loaded && !!window.pdfjsLib;
};

})();
