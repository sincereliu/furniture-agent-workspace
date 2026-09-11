from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_manufacturing.connectors.base import HoleSpec
from furniture_manufacturing.features import (
    Feature,
    from_edge_banding,
    from_hole_spec,
    from_machining_operation,
)
from furniture_manufacturing.manufacturing_models import MachiningOperation


class FeatureContractTests(unittest.TestCase):
    def test_hole_spec_fits_feature_losslessly(self) -> None:
        """特征契约必须无损装下 HoleSpec 的全部 14 个字段。"""
        hole = HoleSpec(
            hole_type="three_in_one_cam",
            panel_label="left_side_panel",
            x_global=100.0,
            y_global=200.0,
            z_global=300.0,
            x_local=10.0,
            y_local=20.0,
            z_local=30.0,
            diameter=15.0,
            depth=12.0,
            direction="-z",
            is_face_hole=False,
            note="偏心轮孔",
            connection_id="left_side_panel→top_panel#0",
        )

        feature = from_hole_spec(hole)

        self.assertIsInstance(feature, Feature)
        self.assertEqual(feature.kind, "hole")
        self.assertEqual(feature.panel_label, hole.panel_label)
        self.assertEqual(feature.x_local, hole.x_local)
        self.assertEqual(feature.y_local, hole.y_local)
        self.assertEqual(feature.z_local, hole.z_local)
        self.assertEqual(feature.hole_type, hole.hole_type)
        self.assertEqual(feature.diameter, hole.diameter)
        self.assertEqual(feature.depth, hole.depth)
        self.assertEqual(feature.direction, hole.direction)
        self.assertEqual(feature.is_face_hole, hole.is_face_hole)
        self.assertEqual(feature.connection_id, hole.connection_id)
        self.assertEqual(feature.x_global, hole.x_global)
        self.assertEqual(feature.y_global, hole.y_global)
        self.assertEqual(feature.z_global, hole.z_global)
        self.assertEqual(feature.note, hole.note)

    def test_default_hole_spec_fits_feature_defaults(self) -> None:
        """空 HoleSpec 的默认值也要与 Feature 默认值一致。"""
        feature = from_hole_spec(HoleSpec())
        self.assertEqual(feature.kind, "hole")
        self.assertEqual(feature.is_face_hole, True)
        self.assertEqual(feature.direction, "+y")
        self.assertEqual(feature.connection_id, "")
        self.assertEqual(feature.panel_label, "")

    def test_machining_operation_fits_feature_losslessly(self) -> None:
        """槽（cut_box）加工指令必须无损装进 Feature（kind="groove"）。"""
        operation = MachiningOperation(
            id="left_side_back_groove",
            operation_type="cut_box",
            target_panel="left_side_panel",
            size_x=6.0,
            size_y=10.0,
            size_z=914.0,
            pos_x=12.0,
            pos_y=18.0,
            pos_z=0.0,
            note="左侧板背板槽",
        )
        feature = from_machining_operation(operation)
        self.assertEqual(feature.kind, "groove")
        self.assertEqual(feature.feature_id, operation.id)
        self.assertEqual(feature.panel_label, operation.target_panel)
        self.assertEqual(feature.size_x, operation.size_x)
        self.assertEqual(feature.size_y, operation.size_y)
        self.assertEqual(feature.size_z, operation.size_z)
        self.assertEqual(feature.x_global, operation.pos_x)
        self.assertEqual(feature.y_global, operation.pos_y)
        self.assertEqual(feature.z_global, operation.pos_z)
        self.assertEqual(feature.note, operation.note)

    def test_edge_banding_fits_feature_losslessly(self) -> None:
        """封边字典必须无损装进 Feature（kind="edge_band"）。"""
        features = from_edge_banding("left_side_panel", {"四边": "ABS 1.0mm同色"})
        self.assertEqual(len(features), 1)
        feature = features[0]
        self.assertEqual(feature.kind, "edge_band")
        self.assertEqual(feature.panel_label, "left_side_panel")
        self.assertEqual(feature.edges, "四边")
        self.assertEqual(feature.material, "ABS 1.0mm同色")

        # 空字典（入槽背板不封边）→ 空列表
        self.assertEqual(from_edge_banding("back_panel", {}), [])


if __name__ == "__main__":
    unittest.main()
