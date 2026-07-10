/**
 * MMFB Pages - 页面渲染器
 *
 * 职责：
 *   1. 首页（空状态）
 *   2. 文件预览页（根据扩展名分发到对应 Viewer）
 *   3. 设置页 / 关于页
 *
 * 文件预览流程：
 *   - 从路由 query 获取 file 参数（绝对路径）
 *   - 根据扩展名选择 Viewer
 *   - 调用 Bridge.getPreview(path) 获取数据
 *   - 渲染对应 Viewer 组件
 */
(function (global) {
    'use strict';

    var MMFBPages = {

        /**
         * 首页（空状态）
         */
        home: function (root, params, query) {
            root.innerHTML =
                '<div class="empty-state">' +
                '<div class="empty-state__icon">&#128196;</div>' +
                '<div class="empty-state__title">MMFB 万能阅览器</div>' +
                '<div class="empty-state__subtitle">拖拽文件到窗口，或点击右上角打开文件</div>' +
                '</div>';
            return { destroy: function () {} };
        },

        /**
         * 404 页面
         */
        notFound: function (root, path) {
            root.innerHTML =
                '<div class="empty-state">' +
                '<div class="empty-state__icon">&#10060;</div>' +
                '<div class="empty-state__title">页面未找到</div>' +
                '<div class="empty-state__subtitle">' + path + '</div>' +
                '</div>';
            return { destroy: function () {} };
        },

        /**
         * 打开历史页
         * 委托给 MMFBHistoryViewer 渲染
         */
        history: function (root, params, query) {
            // 更新顶栏标题
            if (global.MMFBLayout) {
                global.MMFBLayout.setTitle('打开历史');
            }
            if (global.MMFBHistoryViewer) {
                global.MMFBHistoryViewer.render(root);
                return {
                    destroy: function () {
                        if (global.MMFBHistoryViewer) {
                            global.MMFBHistoryViewer.destroy();
                        }
                    }
                };
            }
            // 降级显示
            root.innerHTML = '<div class="empty-state"><div class="empty-state__title">历史组件未加载</div></div>';
            return { destroy: function () {} };
        },

        /**
         * 设置页
         */
        settings: function (root, params, query) {
            root.innerHTML =
                '<div class="settings-page">' +
                '<h2>设置</h2>' +
                '<div class="settings-page__section" id="settings-theme"></div>' +
                '<div class="settings-page__section" id="settings-file-assoc"></div>' +
                '</div>';

            // 渲染主题选择器
            var themeSection = root.querySelector('#settings-theme');
            if (themeSection && global.MMFBThemeSelector) {
                global.MMFBThemeSelector.render(themeSection);
            }

            // 渲染文件关联面板
            var assocSection = root.querySelector('#settings-file-assoc');
            if (assocSection && global.MMFBFileAssociation) {
                global.MMFBFileAssociation.render(assocSection);
                return {
                    destroy: function () {
                        if (global.MMFBThemeSelector) {
                            global.MMFBThemeSelector.destroy();
                        }
                        if (global.MMFBFileAssociation) {
                            global.MMFBFileAssociation.destroy();
                        }
                    }
                };
            }
            return { destroy: function () {} };
        },

        /**
         * 关于页
         */
        about: function (root, params, query) {
            root.innerHTML =
                '<div class="about-page">' +
                '<h2>关于 MMFB</h2>' +
                '<p>MMFB Windows v1.0</p>' +
                '<p>一个窗口，打开所有格式</p>' +
                '<p class="about-page__placeholder">参考 Mac 版 MMFB</p>' +
                '</div>';
            return { destroy: function () {} };
        },

        /**
         * 格式转换页
         */
        conversion: function (root, params, query) {
            // 更新顶栏标题
            if (global.MMFBLayout) {
                global.MMFBLayout.setTitle('格式转换');
            }
            if (global.MMFBConversionViewer) {
                // MMFBConversionViewer 构造函数接受 root 和 options
                var viewer = new global.MMFBConversionViewer(root, {});
                // 保存引用以便 destroy
                root._conversionViewer = viewer;
                return {
                    destroy: function () {
                        if (root._conversionViewer && root._conversionViewer.destroy) {
                            root._conversionViewer.destroy();
                            root._conversionViewer = null;
                        }
                        root.innerHTML = '';
                        root.className = '';
                    }
                };
            }
            // 降级显示
            root.innerHTML = '<div class="empty-state"><div class="empty-state__title">转换组件未加载</div></div>';
            return { destroy: function () {} };
        },

        /**
         * 文件预览页（路由 /view/:ext?file=xxx）
         */
        view: function (root, params, query) {
            var filePath = query.file || '';
            var fileExt = (params.ext || '').toLowerCase();
            var fileName = filePath.split(/[\\/]/).pop() || '未知文件';

            if (!filePath) {
                return this._viewError(root, '未指定文件路径');
            }

            // 更新顶栏标题
            if (global.MMFBLayout) {
                global.MMFBLayout.setTitle(fileName);
            }

            // CSV/TSV/Tab 走专属表格查看器
            var csvExts = ['csv', 'tsv', 'tab'];
            if (csvExts.indexOf(fileExt) >= 0) {
                return this._viewCsv(root, filePath, fileName, fileExt, query);
            }

            // PDF 走专属查看器
            if (fileExt === 'pdf') {
                return this._viewPdf(root, filePath, fileName, query);
            }

            // SVG 矢量图走独立查看器
            var svgExts = ['svg', 'svgz'];
            if (svgExts.indexOf(fileExt) >= 0) {
                return this._viewSvg(root, filePath, fileName, fileExt, query);
            }

            // 游戏贴图 (DDS/TGA/EXR/HDR) 走专属纹理查看器
            var textureExts = ['dds', 'tga', 'exr', 'hdr'];
            if (textureExts.indexOf(fileExt) >= 0) {
                return this._viewTexture(root, filePath, fileName, fileExt, query);
            }

            // PSD/PSB 走图层查看器（支持图层面板 + 合并预览）
            var psdExts = ['psd', 'psb'];
            if (psdExts.indexOf(fileExt) >= 0) {
                return this._viewPsd(root, filePath, fileName, fileExt, query);
            }

            // 图像走专属查看器（包含所有光栅图像 + 相机 RAW）
            var imageExts = [
                'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'tif', 'webp', 'ico',
                'heic', 'heif', 'avif',
                // 相机 RAW 格式（23 种，均复用 MMFBImageViewer）
                'cr2', 'cr3', 'crw', 'nef', 'nrw', 'arw', 'arq', 'srf', 'sr2',
                'dng', 'orf', 'rw2', 'pef', 'ptx', 'raf', 'x3f',
                '3fr', 'fff', 'iiq', 'mos', 'rwl', 'raw',
            ];
            if (imageExts.indexOf(fileExt) >= 0) {
                return this._viewImage(root, filePath, fileName, fileExt, query);
            }

            // 媒体走专属查看器
            var mediaExts = [
                'mp4', 'webm', 'mkv', 'avi', 'mov', 'wmv', 'flv',
                'mp3', 'wav', 'flac', 'aac', 'ogg', 'wma', 'm4a', 'opus'
            ];
            if (mediaExts.indexOf(fileExt) >= 0) {
                return this._viewMedia(root, filePath, fileName, fileExt, query);
            }

            // 3D 模型走专属查看器
            var model3dExts = ['glb', 'gltf', 'obj', 'stl', 'ply'];
            if (model3dExts.indexOf(fileExt) >= 0) {
                return this._viewModel3D(root, filePath, fileName, fileExt, query);
            }

            // Word docx 走专属查看器
            var docxExts = ['docx'];
            if (docxExts.indexOf(fileExt) >= 0) {
                return this._viewDocx(root, filePath, fileName, query);
            }

            // Excel xlsx 走专属查看器
            var xlsxExts = ['xlsx', 'xlsm', 'xltx', 'xltm'];
            if (xlsxExts.indexOf(fileExt) >= 0) {
                return this._viewXlsx(root, filePath, fileName, query);
            }

            // PowerPoint pptx 走专属查看器
            var pptxExts = ['pptx', 'pptm', 'potx', 'potm', 'ppsx', 'ppsm'];
            if (pptxExts.indexOf(fileExt) >= 0) {
                return this._viewPptx(root, filePath, fileName, query);
            }

            // 压缩包走专属树形查看器
            var archiveExts = ['zip', 'tar', 'tar.gz', 'tar.bz2', 'tar.xz', 'tgz'];
            if (archiveExts.indexOf(fileExt) >= 0) {
                return this._viewArchive(root, filePath, fileName, fileExt, query);
            }

            // XMind 思维导图走树形查看器
            if (fileExt === 'xmind') {
                return this._viewXmind(root, filePath, fileName, query);
            }

            // EPUB 电子书走专属查看器
            var epubExts = ['epub'];
            if (epubExts.indexOf(fileExt) >= 0) {
                return this._viewEpub(root, filePath, fileName, fileExt, query);
            }

            // 根据扩展名分发
            // 文本类（Markdown / HTML / 代码）走通用文本预览
            var textExts = [
                'md', 'markdown', 'mdown', 'mkd', 'mkdn', 'mdtxt', 'mdtext', 'text', 'rmd',
                'html', 'htm',
                'json', 'xml', 'yaml', 'yml', 'toml', 'ini', 'cfg', 'conf',
                'py', 'js', 'ts', 'jsx', 'tsx', 'css', 'scss', 'less',
                'c', 'cpp', 'h', 'hpp', 'java', 'kt', 'go', 'rs', 'swift',
                'rb', 'php', 'pl', 'sh', 'bash', 'zsh', 'bat', 'ps1',
                'sql', 'graphql', 'r', 'm', 'scala', 'lua', 'vim',
                'log', 'diff', 'patch',
                'txt', 'rtf'
            ];
            if (textExts.indexOf(fileExt) >= 0) {
                return this._viewText(root, filePath, fileName, fileExt, query);
            }

            // 不支持的格式
            return this._viewUnsupported(root, filePath, fileName, fileExt);
        },

        /**
         * 3D 模型预览
         */
        _viewModel3D: function (root, filePath, fileName, fileExt, query) {
            var self = this;
            root.innerHTML = '<div class="loading">加载 3D 模型...</div>';

            if (!global.MMFBBridge) {
                root.innerHTML = '<div class="error-state">Bridge 未就绪</div>';
                return { destroy: function () {} };
            }

            global.MMFBBridge.api.getPreview(filePath).then(function (json) {
                var result = typeof json === 'string' ? JSON.parse(json) : json;
                if (result.error) {
                    self._viewError(root, result.error);
                    return;
                }
                if (global.MMFBModel3DViewer) {
                    root.innerHTML = '';
                    var viewer = new global.MMFBModel3DViewer(root, result.data);
                    // 保存 viewer 引用供 destroy
                    root._viewerRef = viewer;
                } else {
                    self._viewError(root, '3D 模型查看器未加载');
                }
            }).catch(function (err) {
                self._viewError(root, '加载失败: ' + (err && err.message ? err.message : String(err)));
            });

            return {
                destroy: function () {
                    if (root._viewerRef && root._viewerRef.destroy) {
                        root._viewerRef.destroy();
                        root._viewerRef = null;
                    }
                    root.innerHTML = '';
                    root.className = '';
                }
            };
        },

        /**
         * CSV/TSV/Tab 表格预览
         */
        _viewCsv: function (root, filePath, fileName, fileExt, query) {
            var self = this;
            root.innerHTML = '<div class="loading">加载表格...</div>';

            if (!global.MMFBBridge) {
                root.innerHTML = '<div class="error-state">Bridge 未就绪</div>';
                return { destroy: function () {} };
            }

            global.MMFBBridge.api.getPreview(filePath).then(function (json) {
                var result = typeof json === 'string' ? JSON.parse(json) : json;
                if (result.error) {
                    self._viewError(root, result.error);
                    return;
                }
                if (global.MMFBCSVViewer) {
                    root.innerHTML = '';
                    new global.MMFBCSVViewer(root, result.data);
                } else {
                    // 降级：尝试用纯文本显示
                    self._viewFallbackText(root, JSON.stringify(result.data || {}, null, 2), fileName);
                }
            }).catch(function (err) {
                self._viewError(root, '加载失败: ' + (err && err.message ? err.message : String(err)));
            });

            return {
                destroy: function () {
                    root.innerHTML = '';
                    root.className = '';
                }
            };
        },

        /**
         * 文本预览（Markdown / HTML / 代码高亮）
         */
        _viewText: function (root, filePath, fileName, fileExt, query) {
            var self = this;
            root.innerHTML = '<div class="loading">加载中...</div>';

            if (!global.MMFBBridge) {
                root.innerHTML = '<div class="error-state">Bridge 未就绪</div>';
                return { destroy: function () {} };
            }

            global.MMFBBridge.api.getPreview(filePath).then(function (json) {
                console.log('[pages:diag] getPreview raw json:', json);
                var result = typeof json === 'string' ? JSON.parse(json) : json;
                console.log('[pages:diag] parsed result:', JSON.stringify(result).substring(0, 200));
                if (result.error) {
                    console.error('[pages:diag] result has error:', result.error);
                    self._viewError(root, result.error);
                    return;
                }
                var data = result.data || {};
                var template = result.template || '';
                console.log('[pages:diag] template:', template, '| content len:', (data.content || '').length);

                if (template === 'markdown') {
                    if (global.MMFBMDViewer) {
                        root.innerHTML = '';
                        global.MMFBMDViewer.init(root, { filePath: filePath, fileName: fileName || '' });
                    } else {
                        self._viewError(root, 'Markdown Viewer 未加载');
                    }
                } else if (template === 'html') {
                    if (global.MMFBHTMLViewer) {
                        root.innerHTML = '';
                        global.MMFBHTMLViewer.init(root, { filePath: filePath, fileName: fileName || '' });
                    } else {
                        self._viewError(root, 'HTML Viewer 未加载');
                    }
                } else if (template === 'code') {
                    if (global.MMFBCodeViewer) {
                        root.innerHTML = '';
                        var lang = data.language || 'plaintext';
                        global.MMFBCodeViewer.init(root, { filePath: filePath, fileName: fileName || '', language: lang });
                    } else {
                        self._viewError(root, 'Code Viewer 未加载');
                    }
                } else if (template === 'text') {
                    if (global.MMFBTextViewer) {
                        root.innerHTML = '';
                        global.MMFBTextViewer.init(root, {
                            filePath: filePath,
                            fileName: fileName || '',
                            content: data.content || '',
                            encoding: data.encoding || 'utf-8',
                            lineCount: data.lineCount || 0
                        });
                    } else {
                        self._viewFallbackText(root, data.content || '', fileName);
                    }
                } else {
                    // 降级：纯文本显示
                    self._viewFallbackText(root, data.content || '', fileName);
                }
            }).catch(function (err) {
                self._viewError(root, '加载失败: ' + (err && err.message ? err.message : String(err)));
            });

            return {
                destroy: function () {
                    root.innerHTML = '';
                    try { if (global.MMFBMDViewer) global.MMFBMDViewer.destroy(); } catch (e) {}
                    try { if (global.MMFBHTMLViewer) global.MMFBHTMLViewer.destroy(); } catch (e) {}
                    try { if (global.MMFBCodeViewer) global.MMFBCodeViewer.destroy(); } catch (e) {}
                    try { if (global.MMFBTextViewer) global.MMFBTextViewer.destroy(); } catch (e) {}
                }
            };
        },

        /**
         * PDF 预览
         */
        _viewPdf: function (root, filePath, fileName, query) {
            var self = this;
            root.innerHTML = '<div class="loading">加载 PDF...</div>';

            if (!global.MMFBBridge) {
                root.innerHTML = '<div class="error-state">Bridge 未就绪</div>';
                return { destroy: function () {} };
            }

            global.MMFBBridge.api.getPreview(filePath).then(function (json) {
                var result = typeof json === 'string' ? JSON.parse(json) : json;
                if (result.error) {
                    self._viewError(root, result.error);
                    return;
                }
                if (global.MMFBPDFViewer) {
                    root.innerHTML = '';
                    global.MMFBPDFViewer.init(root, result.data);
                    // 保存 viewer 引用以便 destroy
                    root._pdfViewerRef = global.MMFBPDFViewer;
                } else {
                    self._viewError(root, 'PDF Viewer 未加载');
                }
            }).catch(function (err) {
                self._viewError(root, '加载失败: ' + (err && err.message ? err.message : String(err)));
            });

            return {
                destroy: function () {
                    if (root._pdfViewerRef) {
                        try { root._pdfViewerRef.destroy(); } catch (e) {}
                        root._pdfViewerRef = null;
                    }
                    root.innerHTML = '';
                    root.className = '';
                }
            };
        },

        /**
         * SVG 矢量图预览 / 双栏编辑 / 源码查看 / 导出 PNG
         */
        _viewSvg: function (root, filePath, fileName, fileExt, query) {
            var self = this;
            root.innerHTML = '<div class="svg-loading"><div class="svg-loading__spinner"></div><div>加载 SVG...</div></div>';

            if (!global.MMFBSvgViewer) {
                root.innerHTML = '<div class="error-state">SVG 查看器未加载</div>';
                return { destroy: function () { root.innerHTML = ''; } };
            }

            global.MMFBSvgViewer.init(root, {
                filePath: filePath,
                fileName: fileName,
            });

            return {
                destroy: function () {
                    root.innerHTML = '';
                    try { global.MMFBSvgViewer.destroy(); } catch (e) {}
                }
            };
        },

        /**
         * 图像预览
         */
        _viewImage: function (root, filePath, fileName, fileExt, query) {
            var self = this;
            root.innerHTML = '<div class="loading">加载图像...</div>';

            if (!global.MMFBBridge) {
                root.innerHTML = '<div class="error-state">Bridge 未就绪</div>';
                return { destroy: function () {} };
            }

            global.MMFBBridge.api.getPreview(filePath).then(function (json) {
                var result = typeof json === 'string' ? JSON.parse(json) : json;
                if (result.error) {
                    self._viewError(root, result.error);
                    return;
                }
                if (global.MMFBImageViewer) {
                    root.innerHTML = '';
                    global.MMFBImageViewer.init(root, result.data);
                } else {
                    self._viewError(root, 'Image Viewer 未加载');
                }
            }).catch(function (err) {
                self._viewError(root, '加载失败: ' + (err && err.message ? err.message : String(err)));
            });

            return {
                destroy: function () {
                    root.innerHTML = '';
                    try { if (global.MMFBImageViewer) global.MMFBImageViewer.destroy(); } catch (e) {}
                }
            };
        },

        /**
         * PSD/PSB 图层查看器
         * 调用模式：构造函数 new MMFBPsdViewer(root, result.data)
         */
        _viewPsd: function (root, filePath, fileName, fileExt, query) {
            var self = this;
            root.innerHTML = '<div class="loading">解析 PSD 文件...</div>';

            if (!global.MMFBBridge) {
                root.innerHTML = '<div class="error-state">Bridge 未就绪</div>';
                return { destroy: function () {} };
            }

            global.MMFBBridge.api.getPreview(filePath).then(function (json) {
                var result = typeof json === 'string' ? JSON.parse(json) : json;
                if (result.error) {
                    self._viewError(root, result.error);
                    return;
                }
                if (global.MMFBPsdViewer) {
                    root.innerHTML = '';
                    var viewer = new global.MMFBPsdViewer(root, result.data);
                    root._psdViewer = viewer;
                } else {
                    self._viewError(root, 'PSD 查看器未加载');
                }
            }).catch(function (err) {
                self._viewError(root, '加载失败: ' + (err && err.message ? err.message : String(err)));
            });

            return {
                destroy: function () {
                    if (root._psdViewer && root._psdViewer.destroy) {
                        root._psdViewer.destroy();
                        root._psdViewer = null;
                    }
                    root.innerHTML = '';
                    root.className = '';
                }
            };
        },

        /**
         * 游戏贴图 (DDS/TGA/EXR/HDR) 预览
         */
        _viewTexture: function (root, filePath, fileName, fileExt, query) {
            var self = this;
            root.innerHTML = '<div class="loading">加载贴图...</div>';

            if (!global.MMFBBridge) {
                root.innerHTML = '<div class="error-state">Bridge 未就绪</div>';
                return { destroy: function () {} };
            }

            global.MMFBBridge.api.getPreview(filePath).then(function (json) {
                var result = typeof json === 'string' ? JSON.parse(json) : json;
                if (result.error) {
                    self._viewError(root, result.error);
                    return;
                }
                if (global.MMFBTextureViewer) {
                    root.innerHTML = '';
                    result.data.fileName = fileName;
                    new global.MMFBTextureViewer(root, result.data);
                } else {
                    self._viewError(root, 'Texture Viewer 未加载');
                }
            }).catch(function (err) {
                self._viewError(root, '加载失败: ' + (err && err.message ? err.message : String(err)));
            });

            return { destroy: function () { root.innerHTML = ''; } };
        },

        /**
         * 媒体预览
         */
        _viewMedia: function (root, filePath, fileName, fileExt, query) {
            var self = this;
            root.innerHTML = '<div class="loading">加载媒体...</div>';

            if (!global.MMFBBridge) {
                root.innerHTML = '<div class="error-state">Bridge 未就绪</div>';
                return { destroy: function () {} };
            }

            global.MMFBBridge.api.getPreview(filePath).then(function (json) {
                var result = typeof json === 'string' ? JSON.parse(json) : json;
                if (result.error) {
                    self._viewError(root, result.error);
                    return;
                }
                if (global.MMFBMediaViewer) {
                    root.innerHTML = '';
                    global.MMFBMediaViewer.init(root, result.data);
                } else {
                    self._viewError(root, 'Media Viewer 未加载');
                }
            }).catch(function (err) {
                self._viewError(root, '加载失败: ' + (err && err.message ? err.message : String(err)));
            });

            return { destroy: function () { root.innerHTML = ''; } };
        },

        /**
         * Word docx 预览
         */
        _viewDocx: function (root, filePath, fileName, query) {
            var self = this;
            root.innerHTML = '<div class="loading">加载 Word 文档...</div>';

            if (!global.MMFBBridge) {
                root.innerHTML = '<div class="error-state">Bridge 未就绪</div>';
                return { destroy: function () {} };
            }

            global.MMFBBridge.api.getPreview(filePath).then(function (json) {
                var result = typeof json === 'string' ? JSON.parse(json) : json;
                if (result.error) {
                    self._viewError(root, result.error);
                    return;
                }
                if (global.MMFBDocxViewer) {
                    root.innerHTML = '';
                    global.MMFBDocxViewer.init(root, { filePath: filePath, fileName: fileName || '', data: result.data || null });
                } else {
                    self._viewError(root, 'Docx Viewer 未加载');
                }
            }).catch(function (err) {
                self._viewError(root, '加载失败: ' + (err && err.message ? err.message : String(err)));
            });

            return { destroy: function () { root.innerHTML = ''; } };
        },

        /**
         * Excel xlsx 预览
         */
        _viewXlsx: function (root, filePath, fileName, query) {
            var self = this;
            root.innerHTML = '<div class="loading">加载 Excel 表格...</div>';

            if (!global.MMFBBridge) {
                root.innerHTML = '<div class="error-state">Bridge 未就绪</div>';
                return { destroy: function () {} };
            }

            global.MMFBBridge.api.getPreview(filePath).then(function (json) {
                var result = typeof json === 'string' ? JSON.parse(json) : json;
                if (result.error) {
                    self._viewError(root, result.error);
                    return;
                }
                if (global.MMFBXlsxViewer) {
                    root.innerHTML = '';
                    new global.MMFBXlsxViewer(root, result.data);
                } else {
                    self._viewError(root, 'Xlsx Viewer 未加载');
                }
            }).catch(function (err) {
                self._viewError(root, '加载失败: ' + (err && err.message ? err.message : String(err)));
            });

            return { destroy: function () { root.innerHTML = ''; } };
        },

        /**
         * 压缩包树形预览
         */
        _viewArchive: function (root, filePath, fileName, fileExt, query) {
            var self = this;
            root.innerHTML = '<div class="loading">解析压缩包...</div>';

            if (!global.MMFBBridge) {
                root.innerHTML = '<div class="error-state">Bridge 未就绪</div>';
                return { destroy: function () {} };
            }

            global.MMFBBridge.api.getPreview(filePath).then(function (json) {
                var result = typeof json === 'string' ? JSON.parse(json) : json;
                if (result.error) {
                    self._viewError(root, result.error);
                    return;
                }
                if (global.MMFBArchiveViewer) {
                    root.innerHTML = '';
                    new global.MMFBArchiveViewer(root, result.data);
                } else {
                    self._viewError(root, 'Archive Viewer 未加载');
                }
            }).catch(function (err) {
                self._viewError(root, '加载失败: ' + (err && err.message ? err.message : String(err)));
            });

            return { destroy: function () { root.innerHTML = ''; } };
        },

        /**
         * XMind 思维导图预览
         */
        _viewXmind: function (root, filePath, fileName, query) {
            var self = this;
            root.innerHTML = '<div class="loading">解析 XMind 文件...</div>';

            if (!global.MMFBBridge) {
                root.innerHTML = '<div class="error-state">Bridge 未就绪</div>';
                return { destroy: function () {} };
            }

            global.MMFBBridge.api.getPreview(filePath).then(function (json) {
                var result = typeof json === 'string' ? JSON.parse(json) : json;
                if (result.error) {
                    self._viewError(root, result.error);
                    return;
                }
                if (global.MMFBXmindViewer) {
                    root.innerHTML = '';
                    new global.MMFBXmindViewer(root, result.data);
                } else {
                    self._viewError(root, 'XMind Viewer 未加载');
                }
            }).catch(function (err) {
                self._viewError(root, '加载失败: ' + (err && err.message ? err.message : String(err)));
            });

            return { destroy: function () {
                root.innerHTML = '';
                if (root._viewerRef && root._viewerRef.destroy) {
                    root._viewerRef.destroy();
                    root._viewerRef = null;
                }
            } };
        },

        /**
         * EPUB 电子书预览
         */
        _viewEpub: function (root, filePath, fileName, fileExt, query) {
            var self = this;
            root.innerHTML = '<div class="loading">解析 EPUB...</div>';

            if (!global.MMFBBridge) {
                root.innerHTML = '<div class="error-state">Bridge 未就绪</div>';
                return { destroy: function () {} };
            }

            global.MMFBBridge.api.getPreview(filePath).then(function (json) {
                var result = typeof json === 'string' ? JSON.parse(json) : json;
                if (result.error) {
                    self._viewError(root, result.error);
                    return;
                }
                if (global.MMFBEpubViewer) {
                    root.innerHTML = '';
                    new global.MMFBEpubViewer(root, result.data);
                } else {
                    self._viewError(root, 'EPUB 查看器未加载');
                }
            }).catch(function (err) {
                self._viewError(root, '加载失败: ' + (err && err.message ? err.message : String(err)));
            });

            return { destroy: function () { root.innerHTML = ''; } };
        },

        /**
         * 降级：纯文本显示
         */
        _viewFallbackText: function (root, content, fileName) {
            root.innerHTML =
                '<div class="text-fallback">' +
                '<div class="text-fallback__header">' + fileName + '</div>' +
                '<pre class="text-fallback__pre">' + (content || '(空文件)') + '</pre>' +
                '</div>';
        },

        /**
         * 错误状态
         */
        _viewError: function (root, message) {
            root.innerHTML =
                '<div class="error-state">' +
                '<div class="error-state__icon">&#9888;</div>' +
                '<div class="error-state__title">预览失败</div>' +
                '<div class="error-state__msg">' + (message || '未知错误') + '</div>' +
                '</div>';
        },

        /**
         * PowerPoint PPTX 预览
         */
        _viewPptx: function (root, filePath, fileName, query) {
            var self = this;
            root.innerHTML = '<div class="pptx-viewer__loading"><div class="pptx-spinner"></div><div>加载幻灯片...</div></div>';

            if (!global.MMFBBridge) {
                root.innerHTML = '<div class="pptx-viewer__error"><div class="pptx-viewer__error-icon">&#9888;</div><div>Bridge 未就绪</div></div>';
                return { destroy: function () {} };
            }

            global.MMFBBridge.api.getPreview(filePath).then(function (json) {
                var result = typeof json === 'string' ? JSON.parse(json) : json;
                if (result.error) {
                    self._viewError(root, result.error);
                    return;
                }
                if (global.MMFBPptxViewer) {
                    root.innerHTML = '';
                    new global.MMFBPptxViewer(root, result.data);
                } else {
                    self._viewError(root, 'PPTX Viewer 未加载');
                }
            }).catch(function (err) {
                self._viewError(root, '加载失败: ' + (err && err.message ? err.message : String(err)));
            });

            return { destroy: function () { root.innerHTML = ''; } };
        },

        /**
         * 不支持的格式
         */
        _viewUnsupported: function (root, filePath, fileName, fileExt) {
            root.innerHTML =
                '<div class="error-state">' +
                '<div class="error-state__icon">&#128190;</div>' +
                '<div class="error-state__title">暂不支持该格式</div>' +
                '<div class="error-state__msg">扩展名: ' + (fileExt || '未知') + '</div>' +
                '<div class="error-state__msg">文件: ' + fileName + '</div>' +
                '</div>';
            return { destroy: function () {} };
        }
    };

    global.MMFBPages = MMFBPages;

})(window);
