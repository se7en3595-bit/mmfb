/**
 * MMFB Model3D Viewer - 3D 模型预览器
 *
 * 功能：
 *   - three.js 渲染顶点/面片数据
 *   - OrbitControls 轨道控制 (旋转/缩放/平移)
 *   - 网格/实体/线框三种显示模式
 *   - 显示模型信息 (面数/AABB/体积)
 *   - 自适应窗口尺寸
 */
(function (global) {
    'use strict';

    /**
     * MMFBModel3DViewer 构造函数
     * @param {HTMLElement} root - 容器元素
     * @param {object} data - Handler 返回的 data 对象
     */
    function MMFBModel3DViewer(root, data) {
        this._root = root;
        this._data = data;
        this._scene = null;
        this._camera = null;
        this._renderer = null;
        this._mesh = null;
        this._controls = null;
        this._animationId = null;
        this._displayMode = 'solid'; // solid | wireframe | grid
        this._initialized = false;

        this._init();
    }

    MMFBModel3DViewer.prototype._init = function () {
        var self = this;

        this._buildDom();
        this._loadThreeJS().then(function () {
            self._setupScene();
            self._buildMesh();
            self._startRenderLoop();
            self._bindEvents();
            self._initialized = true;
        }).catch(function (err) {
            self._root.innerHTML =
                '<div class="error-state">' +
                '<div class="error-state__icon">&#9888;</div>' +
                '<div class="error-state__title">3D 渲染器加载失败</div>' +
                '<div class="error-state__msg">' + (err && err.message ? err.message : String(err)) + '</div>' +
                '</div>';
        });
    };

    /**
     * 构建 DOM 结构
     */
    MMFBModel3DViewer.prototype._buildDom = function () {
        var data = this._data;
        var infoLine = this._buildInfoLine(data);

        this._root.innerHTML =
            '<div class="model3d-viewer">' +
            '<div class="model3d-toolbar">' +
            '<div class="model3d-toolbar__info">' + infoLine + '</div>' +
            '<div class="model3d-toolbar__modes">' +
            '<button class="model3d-btn model3d-btn--active" data-mode="solid">实体</button>' +
            '<button class="model3d-btn" data-mode="wireframe">线框</button>' +
            '<button class="model3d-btn" data-mode="grid">网格</button>' +
            '</div>' +
            '<div class="model3d-toolbar__actions">' +
            '<button class="model3d-btn model3d-btn--reset" data-action="reset">重置视角</button>' +
            '</div>' +
            '</div>' +
            '<div class="model3d-canvas-wrapper">' +
            '<canvas class="model3d-canvas"></canvas>' +
            '<div class="model3d-loading"><div class="model3d-loading__spinner"></div><div>正在构建场景...</div></div>' +
            '</div>' +
            '</div>';
    };

    /**
     * 构建模型信息行
     */
    MMFBModel3DViewer.prototype._buildInfoLine = function (data) {
        var parts = [];
        parts.push(data.file_name || '');
        if (data.vertex_count) {
            parts.push(data.vertex_count.toLocaleString() + ' 顶点');
        }
        if (data.face_count) {
            parts.push(data.face_count.toLocaleString() + ' 面');
        }
        if (data.is_watertight) {
            parts.push('闭合');
        }
        return parts.join(' &nbsp;&bull;&nbsp; ');
    };

    /**
     * 加载 three.js (内嵌 CDN 回退)
     */
    MMFBModel3DViewer.prototype._loadThreeJS = function () {
        var self = this;
        return new Promise(function (resolve, reject) {
            // three.js 通过内嵌打包引入，检查全局 THREE
            if (global.THREE) {
                resolve();
                return;
            }

            // 尝试从本地 libs 加载
            var script = document.createElement('script');
            script.src = 'libs/three.module.min.js';
            script.type = 'module';
            script.onload = function () {
                // 处理 ES module：three.js v0.160+ 为 ESM，需要 import map
                // 回退到 UMD 版本
                self._loadUMD().then(resolve).catch(reject);
            };
            script.onerror = function () {
                // CDN 回退 (仅本地离线模式的兜底)
                self._loadUMD().then(resolve).catch(reject);
            };
            // 由于 ESM 处理复杂，直接走 UMD 内嵌
            script.onerror();
        });
    };

    /**
     * 加载 UMD 版本三个关键类
     */
    MMFBModel3DViewer.prototype._loadUMD = function () {
        return new Promise(function (resolve, reject) {
            if (global.THREE) {
                resolve();
                return;
            }
            // 使用内联的轻量级 three.js 子集 (70KB) —— 实际项目中应替换为完整 three.js
            // 这里通过 qrc 资源注入或直接内嵌
            // 为简化，通过动态 script 加载本地资源
            var script = document.createElement('script');
            script.src = 'libs/three.min.js';
            script.onload = function () {
                if (global.THREE) {
                    resolve();
                } else {
                    reject(new Error('three.js 加载失败'));
                }
            };
            script.onerror = function () {
                reject(new Error('three.js not available (path: libs/three.min.js)'));
            };
            document.head.appendChild(script);
        });
    };

    /**
     * 创建场景
     */
    MMFBModel3DViewer.prototype._setupScene = function () {
        var canvas = this._root.querySelector('.model3d-canvas');
        var wrapper = this._root.querySelector('.model3d-canvas-wrapper');
        var width = wrapper.clientWidth || 800;
        var height = wrapper.clientHeight || 600;

        // 场景
        var scene = new THREE.Scene();
        scene.background = new THREE.Color(0xf5f0e8); // 暖纸色
        scene.fog = new THREE.Fog(0xf5f0e8, 10, 50);

        // 透视相机
        var camera = new THREE.PerspectiveCamera(45, width / height, 0.01, 1000);
        var data = this._data;
        var bounds = data.bounds || [[0, 0, 0], [1, 1, 1]];
        var bMin = bounds[0];
        var bMax = bounds[1];
        var cx = (bMin[0] + bMax[0]) / 2;
        var cy = (bMin[1] + bMax[1]) / 2;
        var cz = (bMin[2] + bMax[2]) / 2;
        var sizeX = Math.max(bMax[0] - bMin[0], 0.001);
        var sizeY = Math.max(bMax[1] - bMin[1], 0.001);
        var sizeZ = Math.max(bMax[2] - bMin[2], 0.001);
        var maxSize = Math.max(sizeX, sizeY, sizeZ);
        var dist = maxSize * 2.5;

        camera.position.set(cx + dist * 0.5, cy + dist * 0.4, cz + dist * 0.8);
        camera.lookAt(cx, cy, cz);

        // 渲染器
        var renderer = new THREE.WebGLRenderer({
            canvas: canvas,
            antialias: true,
            alpha: false,
        });
        renderer.setSize(width, height);
        renderer.setPixelRatio(global.devicePixelRatio || 1);
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.0;

        // 轨道控制
        var controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.08;
        controls.target.set(cx, cy, cz);
        controls.minDistance = maxSize * 0.1;
        controls.maxDistance = maxSize * 20;
        controls.update();

        // 灯光
        var ambientLight = new THREE.AmbientLight(0xfff8f0, 0.5);
        scene.add(ambientLight);

        var dirLight = new THREE.DirectionalLight(0xffffff, 1.0);
        dirLight.position.set(cx + dist, cy + dist, cz + dist);
        dirLight.castShadow = true;
        dirLight.shadow.mapSize.width = 1024;
        dirLight.shadow.mapSize.height = 1024;
        dirLight.shadow.camera.near = 0.1;
        dirLight.shadow.camera.far = dist * 10;
        scene.add(dirLight);

        var fillLight = new THREE.DirectionalLight(0xffeedd, 0.3);
        fillLight.position.set(cx - dist, cy - dist * 0.5, cz - dist);
        scene.add(fillLight);

        // 网格地面 (半透明)
        var gridHelper = new THREE.GridHelper(maxSize * 4, 20, 0xd4c5a9, 0xe8dcc8);
        gridHelper.position.set(cx, bMin[1] - maxSize * 0.01, cz);
        gridHelper.material.opacity = 0.4;
        gridHelper.material.transparent = true;
        scene.add(gridHelper);

        // 坐标轴
        var axesHelper = new THREE.AxesHelper(maxSize * 0.5);
        axesHelper.position.set(cx, bMin[1] - maxSize * 0.005, cz);
        scene.add(axesHelper);

        this._scene = scene;
        this._camera = camera;
        this._renderer = renderer;
        this._controls = controls;
        this._modelCenter = [cx, cy, cz];
        this._modelSize = maxSize;
    };

    /**
     * 从顶点/面片数据构建 mesh
     */
    MMFBModel3DViewer.prototype._buildMesh = function () {
        var data = this._data;
        var vertices = data.vertices || [];
        var faces = data.faces || [];
        var normals = data.normals || [];
        var hasNormals = data.has_normals && normals.length > 0;

        if (vertices.length === 0 || faces.length === 0) {
            return;
        }

        // 构建 BufferGeometry
        var geometry = new THREE.BufferGeometry();

        // 顶点 (flat array -> Float32Array)
        var positionArray = new Float32Array(vertices);
        geometry.setAttribute('position', new THREE.BufferAttribute(positionArray, 3));

        // 索引 (flat array -> Uint32Array)
        var indexArray = new Uint32Array(faces);
        geometry.setIndex(new THREE.BufferAttribute(indexArray, 1));

        // 法线
        if (hasNormals) {
            var normalArray = new Float32Array(normals);
            geometry.setAttribute('normal', new THREE.BufferAttribute(normalArray, 3));
        } else {
            geometry.computeVertexNormals();
        }

        // 实体材质 (暖色调 PBR)
        var solidMaterial = new THREE.MeshStandardMaterial({
            color: 0xd4a574,     // 暖铜色
            roughness: 0.6,
            metalness: 0.1,
            flatShading: false,
            side: THREE.DoubleSide,
        });

        // 线框材质
        var wireframeMaterial = new THREE.MeshBasicMaterial({
            color: 0x8b7355,     // 深暖色
            wireframe: true,
            transparent: true,
            opacity: 0.8,
        });

        // 网格模式材质 (半透明表面 + 网格线)
        var gridMaterial = new THREE.MeshStandardMaterial({
            color: 0xd4a574,
            roughness: 0.7,
            metalness: 0.0,
            wireframe: false,
            transparent: true,
            opacity: 0.85,
            side: THREE.DoubleSide,
        });

        // 创建 mesh (初始为实体模式)
        var mesh = new THREE.Mesh(geometry, solidMaterial);
        mesh.castShadow = true;
        mesh.receiveShadow = true;

        // 保存材质引用以切换模式
        mesh.userData.solidMaterial = solidMaterial;
        mesh.userData.wireframeMaterial = wireframeMaterial;
        mesh.userData.gridMaterial = gridMaterial;
        mesh.userData.solidWithEdges = null; // 延迟创建

        this._scene.add(mesh);
        this._mesh = mesh;

        // 隐藏加载动画
        var loading = this._root.querySelector('.model3d-loading');
        if (loading) {
            loading.style.display = 'none';
        }
    };

    /**
     * 切换显示模式
     */
    MMFBModel3DViewer.prototype._setDisplayMode = function (mode) {
        if (!this._mesh || this._displayMode === mode) {
            return;
        }

        this._displayMode = mode;
        var mesh = this._mesh;

        switch (mode) {
            case 'solid':
                mesh.material = mesh.userData.solidMaterial;
                if (mesh.userData.edgesLine) {
                    mesh.userData.edgesLine.visible = false;
                }
                break;
            case 'wireframe':
                mesh.material = mesh.userData.wireframeMaterial;
                if (mesh.userData.edgesLine) {
                    mesh.userData.edgesLine.visible = false;
                }
                break;
            case 'grid':
                mesh.material = mesh.userData.gridMaterial;
                // 添加边缘线
                if (!mesh.userData.edgesLine) {
                    var edges = new THREE.EdgesGeometry(mesh.geometry, 15);
                    var lineMat = new THREE.LineBasicMaterial({ color: 0x8b7355, transparent: true, opacity: 0.4 });
                    mesh.userData.edgesLine = new THREE.LineSegments(edges, lineMat);
                    mesh.add(mesh.userData.edgesLine);
                }
                mesh.userData.edgesLine.visible = true;
                break;
        }

        // 更新按钮状态
        var btns = this._root.querySelectorAll('.model3d-btn[data-mode]');
        for (var i = 0; i < btns.length; i++) {
            if (btns[i].getAttribute('data-mode') === mode) {
                btns[i].classList.add('model3d-btn--active');
            } else {
                btns[i].classList.remove('model3d-btn--active');
            }
        }
    };

    /**
     * 重置相机视角
     */
    MMFBModel3DViewer.prototype._resetCamera = function () {
        if (!this._camera || !this._controls) return;

        var cx = this._modelCenter[0];
        var cy = this._modelCenter[1];
        var cz = this._modelCenter[2];
        var dist = this._modelSize * 2.5;

        this._camera.position.set(cx + dist * 0.5, cy + dist * 0.4, cz + dist * 0.8);
        this._controls.target.set(cx, cy, cz);
        this._controls.update();
    };

    /**
     * 启动渲染循环
     */
    MMFBModel3DViewer.prototype._startRenderLoop = function () {
        var self = this;

        function animate() {
            self._animationId = requestAnimationFrame(animate);
            if (self._controls) self._controls.update();
            self._renderer.render(self._scene, self._camera);
        }

        animate();
    };

    /**
     * 绑定事件
     */
    MMFBModel3DViewer.prototype._bindEvents = function () {
        var self = this;

        // 按钮事件
        var btns = this._root.querySelectorAll('.model3d-btn[data-mode]');
        for (var i = 0; i < btns.length; i++) {
            (function (btn) {
                btn.addEventListener('click', function () {
                    var mode = btn.getAttribute('data-mode');
                    self._setDisplayMode(mode);
                });
            })(btns[i]);
        }

        // 重置视角
        var resetBtn = this._root.querySelector('.model3d-btn--reset');
        if (resetBtn) {
            resetBtn.addEventListener('click', function () {
                self._resetCamera();
            });
        }

        // 窗口 resize
        var resizeTimer = null;
        var onResize = function () {
            if (resizeTimer) return;
            resizeTimer = setTimeout(function () {
                resizeTimer = null;
                self._onResize();
            }, 150);
        };
        global.addEventListener('resize', onResize);

        // 保存引用供 destroy
        this._onResizeHandler = onResize;
    };

    /**
     * 窗口尺寸变化处理
     */
    MMFBModel3DViewer.prototype._onResize = function () {
        if (!this._camera || !this._renderer) return;

        var wrapper = this._root.querySelector('.model3d-canvas-wrapper');
        var width = wrapper.clientWidth || 800;
        var height = wrapper.clientHeight || 600;

        this._camera.aspect = width / height;
        this._camera.updateProjectionMatrix();
        this._renderer.setSize(width, height);
    };

    /**
     * 销毁
     */
    MMFBModel3DViewer.prototype.destroy = function () {
        if (this._animationId) {
            cancelAnimationFrame(this._animationId);
            this._animationId = null;
        }

        if (this._onResizeHandler) {
            global.removeEventListener('resize', this._onResizeHandler);
        }

        if (this._renderer) {
            this._renderer.dispose();
            this._renderer = null;
        }

        if (this._mesh) {
            if (this._mesh.geometry) this._mesh.geometry.dispose();
            if (this._mesh.userData.solidMaterial) this._mesh.userData.solidMaterial.dispose();
            if (this._mesh.userData.wireframeMaterial) this._mesh.userData.wireframeMaterial.dispose();
            if (this._mesh.userData.gridMaterial) this._mesh.userData.gridMaterial.dispose();
            this._mesh = null;
        }

        this._scene = null;
        this._camera = null;
        this._controls = null;
    };

    global.MMFBModel3DViewer = MMFBModel3DViewer;

})(window);
