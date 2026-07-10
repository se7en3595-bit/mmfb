"""Model3DHandler 单元测试

覆盖：
- 注册表匹配（glb/gltf/obj/stl/ply）
- 大小写不敏感
- 核心三角面片数据（手动构建 box）
- 空数据处理
- 错误处理（不存在的文件）
"""
import json
import os
import struct
import tempfile
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1].parent))

from mmfb.handlers.model3d_handler import Model3DHandler


def _create_ply_box(path):
    """通过 trimesh 创建一个单位 cube PLY 文件（中心在原点，体积=1）"""
    import trimesh
    mesh = trimesh.creation.box(extents=[1.0, 1.0, 1.0])
    mesh.export(path, encoding='ascii')


class TestModel3DHandlerRegistry(unittest.TestCase):
    """注册表匹配测试"""

    def test_can_handle_glb(self):
        self.assertTrue(Model3DHandler.can_handle("model.glb"))

    def test_can_handle_gltf(self):
        self.assertTrue(Model3DHandler.can_handle("model.gltf"))

    def test_can_handle_obj(self):
        self.assertTrue(Model3DHandler.can_handle("model.obj"))

    def test_can_handle_stl(self):
        self.assertTrue(Model3DHandler.can_handle("model.stl"))

    def test_can_handle_ply(self):
        self.assertTrue(Model3DHandler.can_handle("model.ply"))

    def test_case_insensitive(self):
        self.assertTrue(Model3DHandler.can_handle("model.GLB"))
        self.assertTrue(Model3DHandler.can_handle("model.GLTF"))
        self.assertTrue(Model3DHandler.can_handle("model.OBJ"))

    def test_rejects_other_formats(self):
        self.assertFalse(Model3DHandler.can_handle("model.pdf"))
        self.assertFalse(Model3DHandler.can_handle("model.md"))
        self.assertFalse(Model3DHandler.can_handle("model.zip"))
        self.assertFalse(Model3DHandler.can_handle("model.png"))

    def test_extensions_list_complete(self):
        exts = Model3DHandler.extensions
        self.assertIn(".glb", exts)
        self.assertIn(".gltf", exts)
        self.assertIn(".obj", exts)
        self.assertIn(".stl", exts)
        self.assertIn(".ply", exts)


class TestModel3DHandlerParsing(unittest.TestCase):
    """模型解析逻辑测试"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_ply_box_preview(self):
        """PLY box 解析：8 顶点 12 面"""
        ply_path = os.path.join(self.tmpdir, "box.ply")
        _create_ply_box(ply_path)

        handler = Model3DHandler(ply_path)
        result = handler.get_preview()

        self.assertIsNotNone(result)
        self.assertNotIn("error", result)
        data = result["data"]
        self.assertEqual(data["vertex_count"], 8)
        self.assertEqual(data["face_count"], 12)

    def test_ply_box_vertices_data(self):
        """顶点数据正确性"""
        ply_path = os.path.join(self.tmpdir, "box.ply")
        _create_ply_box(ply_path)

        handler = Model3DHandler(ply_path)
        result = handler.get_preview()
        data = result["data"]

        # vertices 应为 flat array (8 * 3 = 24)
        self.assertEqual(len(data["vertices"]), 24)
        # faces 应为 flat array (12 * 3 = 36)
        self.assertEqual(len(data["faces"]), 36)

    def test_ply_box_bounds(self):
        """边界框应为 [-0.5,-0.5,-0.5] 到 [0.5,0.5,0.5]（trimesh 默认 box 中心在原点）"""
        ply_path = os.path.join(self.tmpdir, "box.ply")
        _create_ply_box(ply_path)

        handler = Model3DHandler(ply_path)
        result = handler.get_preview()
        bounds = result["data"]["bounds"]

        self.assertAlmostEqual(bounds[0][0], -0.5, places=2)
        self.assertAlmostEqual(bounds[0][1], -0.5, places=2)
        self.assertAlmostEqual(bounds[0][2], -0.5, places=2)
        self.assertAlmostEqual(bounds[1][0], 0.5, places=2)
        self.assertAlmostEqual(bounds[1][1], 0.5, places=2)
        self.assertAlmostEqual(bounds[1][2], 0.5, places=2)

    def test_box_is_watertight(self):
        """闭合 box 应为 watertight"""
        ply_path = os.path.join(self.tmpdir, "box.ply")
        _create_ply_box(ply_path)

        handler = Model3DHandler(ply_path)
        result = handler.get_preview()
        self.assertTrue(result["data"]["is_watertight"])

    def test_box_has_positive_volume(self):
        """watertight box 应有正体积"""
        ply_path = os.path.join(self.tmpdir, "box.ply")
        _create_ply_box(ply_path)

        handler = Model3DHandler(ply_path)
        result = handler.get_preview()
        volume = result["data"]["volume"]
        self.assertIsNotNone(volume)
        self.assertGreater(volume, 0.0)

    def test_box_center_mass(self):
        """中心质量应接近 [0, 0, 0]（trimesh 默认 box 中心在原点）"""
        ply_path = os.path.join(self.tmpdir, "box.ply")
        _create_ply_box(ply_path)

        handler = Model3DHandler(ply_path)
        result = handler.get_preview()
        cm = result["data"]["center_mass"]
        self.assertIsNotNone(cm)
        self.assertAlmostEqual(cm[0], 0.0, places=1)
        self.assertAlmostEqual(cm[1], 0.0, places=1)
        self.assertAlmostEqual(cm[2], 0.0, places=1)

    def test_nonexistent_file(self):
        """不存在的文件应返回 error"""
        handler = Model3DHandler("/nonexistent/file.glb")
        result = handler.get_preview()
        self.assertIn("error", result)

    def test_empty_ply_file(self):
        """空 PLY 文件应返回 error"""
        empty_path = os.path.join(self.tmpdir, "empty.ply")
        with open(empty_path, 'w') as f:
            f.write("")
        handler = Model3DHandler(empty_path)
        result = handler.get_preview()
        self.assertIn("error", result)

    def test_editable_flag_false(self):
        """3D 模型不应标记为可编辑"""
        ply_path = os.path.join(self.tmpdir, "box.ply")
        _create_ply_box(ply_path)

        handler = Model3DHandler(ply_path)
        result = handler.get_preview()
        self.assertFalse(result["editable"])

    def test_get_edit_returns_none(self):
        ply_path = os.path.join(self.tmpdir, "box.ply")
        _create_ply_box(ply_path)

        handler = Model3DHandler(ply_path)
        self.assertIsNone(handler.get_edit())

    def test_template_name(self):
        ply_path = os.path.join(self.tmpdir, "box.ply")
        _create_ply_box(ply_path)

        handler = Model3DHandler(ply_path)
        result = handler.get_preview()
        self.assertEqual(result["template"], "model3d")

    def test_json_serializable(self):
        """结果可以 JSON 序列化"""
        ply_path = os.path.join(self.tmpdir, "box.ply")
        _create_ply_box(ply_path)

        handler = Model3DHandler(ply_path)
        result = handler.get_preview()
        json_str = json.dumps(result)
        self.assertIsInstance(json_str, str)


if __name__ == "__main__":
    unittest.main()
