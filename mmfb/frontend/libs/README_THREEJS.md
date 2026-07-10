# Three.js 依赖说明

Model3D Viewer 需要以下前端库：

## three.min.js
- 来源: https://unpkg.com/three@0.160.0/build/three.min.js
- 或: https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js
- 大小: ~600 KB
- needs: OrbitControls (可选，已在 model3d_viewer.js 中手工实现精简版轨道控制)

## 安装方法
下载并放置到此目录:
```
mmfb/frontend/libs/three.min.js
```

注: model3d_viewer.js 中的 three.js 调用使用了以下 THREE 命名空间:
- THREE.Scene
- THREE.PerspectiveCamera
- THREE.WebGLRenderer
- THREE.OrbitControls
- THREE.AmbientLight
- THREE.DirectionalLight
- THREE.GridHelper
- THREE.AxesHelper
- THREE.BufferGeometry
- THREE.BufferAttribute
- THREE.MeshStandardMaterial
- THREE.MeshBasicMaterial
- THREE.Mesh
- THREE.EdgesGeometry
- THREE.LineBasicMaterial
- THREE.LineSegments
- THREE.Color
- THREE.Fog
- THREE.PCFSoftShadowMap
- THREE.ACESFilmicToneMapping
- THREE.DoubleSide

若 three.min.js 未加载或无 OrbitControls，Model3D Viewer 会回退显示错误状态。
