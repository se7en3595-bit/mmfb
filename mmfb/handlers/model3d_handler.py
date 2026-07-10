"""3D 模型格式处理器

职责：
1. 使用 trimesh 解析 OBJ / STL / PLY / GLB / GLTF 获取顶点/面片数据
2. 返回 JSON 供前端 three.js 渲染
3. 显示模型信息 (面数/AABB/体积等)

输出 JSON 结构：
{
    "vertices": [[x,y,z], ...],     # 顶点坐标 (flat array 每3个一组)
    "faces": [[i,j,k], ...],        # 面片索引 (flat array 每3个一组)
    "normals": [[x,y,z], ...],      # 顶点法线 (可选)
    "bounds": [[min_x,min_y,min_z], [max_x,max_y,max_z]],
    "face_count": int,
    "vertex_count": int,
    "is_watertight": bool,
    "volume": float | null,
    "center_mass": [x,y,z] | null
}

安全：
- 顶点数上限 50 万 (防止 JSON 爆炸)
- 全部内存操作，不落盘
"""
import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import trimesh

from mmfb.core.handler_base import BaseHandler


# 3D 模型扩展名
MODEL3D_EXTENSIONS: List[str] = [
    ".glb", ".gltf",
    ".obj",
    ".stl",
    ".ply",
]

# 顶点数上限 (防止 JSON 爆炸)
MAX_VERTICES = 500_000


class Model3DHandler(BaseHandler):
    """3D 模型处理器

    支持的扩展名：
        .glb, .gltf, .obj, .stl, .ply

    特性：
        - trimesh 解析，无额外依赖
        - 顶点数据上限 50 万
        - 输出顶点/面片/法线/BoundingBox/体积等
        - 面片自动转为三角形 (triangle)
    """

    extensions = MODEL3D_EXTENSIONS

    def get_preview(self) -> Optional[Dict[str, Any]]:
        """获取 3D 模型数据供前端渲染

        返回字典：
        - mime: model/gltf-binary 等
        - template: 'model3d'
        - data: 模型 JSON (vertices/faces/normals/bounds/统计信息)
        - editable: False
        """
        try:
            if not os.path.isfile(self.path):
                return self._error_result("file not found")

            file_size = os.path.getsize(self.path)
            if file_size == 0:
                return self._error_result("empty file")

            return self._parse_model(file_size)
        except Exception as e:
            return self._error_result(str(e))

    def get_edit(self) -> Optional[Dict[str, Any]]:
        """3D 模型不支持就地编辑"""
        return None

    def _parse_model(self, file_size: int) -> Dict[str, Any]:
        """解析 3D 模型文件"""
        try:
            # trimesh 自动处理加载
            mesh = trimesh.load(self.path, force='mesh')
        except Exception as e:
            return self._error_result(f"cannot load model: {e}")

        # 如果加载结果是一个 Scene，合并所有 mesh
        if isinstance(mesh, trimesh.Scene):
            meshes = list(mesh.geometry.values())
            if not meshes:
                return self._error_result("empty scene (no geometry)")
            mesh = trimesh.util.concatenate(meshes)

        if not isinstance(mesh, trimesh.Trimesh):
            return self._error_result("loaded object is not a Trimesh")

        # 顶点数据
        vertices = np.asarray(mesh.vertices, dtype=np.float32)
        faces = np.asarray(mesh.faces, dtype=np.int32)

        vertex_count = len(vertices)
        face_count = len(faces)

        if vertex_count == 0:
            return self._error_result("mesh has no vertices")

        # 顶点限制检查与下采样
        if vertex_count > MAX_VERTICES:
            # 按比例减少面片
            ratio = MAX_VERTICES / vertex_count
            target_faces = max(int(len(faces) * ratio), 1)
            # 使用 trimesh 的简化
            try:
                mesh = mesh.simplify_quadric_decimation(target_faces)
                vertices = np.asarray(mesh.vertices, dtype=np.float32)
                faces = np.asarray(mesh.faces, dtype=np.int32)
                vertex_count = len(vertices)
                face_count = len(faces)
            except Exception:
                # 简化失败则直接截取
                vertices = vertices[:MAX_VERTICES]
                vertex_count = MAX_VERTICES

        # 顶点法线 (如果 mesh 没有顶点法线则计算)
        try:
            normals = np.asarray(mesh.vertex_normals, dtype=np.float32)
            has_normals = len(normals) == vertex_count
        except Exception:
            has_normals = False
            normals = np.zeros_like(vertices)

        # 边界框
        bounds = mesh.bounds  # shape (2, 3)
        bounds_list = bounds.tolist()

        # 模型元信息
        try:
            is_watertight = bool(mesh.is_watertight)
        except Exception:
            is_watertight = False

        try:
            volume = float(mesh.volume) if mesh.is_watertight else None
        except Exception:
            volume = None

        try:
            center_mass = mesh.center_mass.tolist()
        except Exception:
            center_mass = None

        # 转为 Python list (JSON 可序列化)
        result = {
            "mime": self.get_mime(),
            "template": "model3d",
            "data": {
                "file_path": self.path,
                "file_name": Path(self.path).name,
                "file_size": file_size,
                "vertices": vertices.flatten().tolist(),
                "faces": faces.flatten().tolist(),
                "normals": normals.flatten().tolist() if has_normals else [],
                "has_normals": has_normals,
                "bounds": bounds_list,
                "vertex_count": vertex_count,
                "face_count": face_count,
                "is_watertight": is_watertight,
                "volume": volume,
                "center_mass": center_mass,
            },
            "editable": False,
        }

        return result

    def _error_result(self, error_msg: str) -> Dict[str, Any]:
        return {
            "mime": "application/octet-stream",
            "template": "model3d",
            "data": {
                "file_path": self.path,
                "file_name": Path(self.path).name,
                "file_size": 0,
                "vertices": [],
                "faces": [],
                "normals": [],
                "has_normals": False,
                "bounds": [[0, 0, 0], [0, 0, 0]],
                "vertex_count": 0,
                "face_count": 0,
                "is_watertight": False,
                "volume": None,
                "center_mass": None,
            },
            "editable": False,
            "error": error_msg,
        }
