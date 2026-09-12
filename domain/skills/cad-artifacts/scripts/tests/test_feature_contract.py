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
    EdgeBandFeature,
    Feature,
    GrooveFeature,
    HoleFeature,
    from_edge_banding,
    from_hole_spec,
    from_machining_operation,
)
from furniture_manufacturing.manufacturing_models import MachiningOperation


class FeatureContractTests(unittest.TestCase):
    def test_hole_spec_fits_feature_losslessly(self) -> None:
        """HoleFeature 必须无损装下 HoleSpec 的全部字段。"""
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

        self.assertIsInstance(feature, HoleFeature)
        self.assertIsInstance(feature, Feature)  # 也是基类
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
        """空 HoleSpec 的默认值也要与 HoleFeature 默认值一致。"""
        feature = from_hole_spec(HoleSpec())
        self.assertIsInstance(feature, HoleFeature)
        self.assertEqual(feature.is_face_hole, True)
        self.assertEqual(feature.direction, "+y")
        self.assertEqual(feature.connection_id, "")
        self.assertEqual(feature.panel_label, "")

    def test_machining_operation_fits_feature_losslessly(self) -> None:
        """槽（cut_box）加工指令必须无损装进 GrooveFeature。"""
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
        self.assertIsInstance(feature, GrooveFeature)
        self.assertIsInstance(feature, Feature)
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
        """封边字典必须无损装进 EdgeBandFeature。"""
        features = from_edge_banding("left_side_panel", {"四边": "ABS 1.0mm同色"})
        self.assertEqual(len(features), 1)
        feature = features[0]
        self.assertIsInstance(feature, EdgeBandFeature)
        self.assertIsInstance(feature, Feature)
        self.assertEqual(feature.panel_label, "left_side_panel")
        self.assertEqual(feature.edges, "四边")
        self.assertEqual(feature.material, "ABS 1.0mm同色")

        # 空字典（入槽背板不封边）→ 空列表
        self.assertEqual(from_edge_banding("back_panel", {}), [])

    def test_kinds_are_distinct_subclasses(self) -> None:
        """三种加工是三个不同的子类，互不混同。"""
        hole = from_hole_spec(HoleSpec())
        groove = from_machining_operation(
            MachiningOperation(
                id="g", operation_type="cut_box", target_panel="p",
                size_x=1, size_y=1, size_z=1, pos_x=0, pos_y=0, pos_z=0,
            )
        )
        edge = from_edge_banding("p", {"四边": "ABS"})[0]

        self.assertIsInstance(hole, HoleFeature)
        self.assertNotIsInstance(hole, GrooveFeature)
        self.assertNotIsInstance(hole, EdgeBandFeature)

        self.assertIsInstance(groove, GrooveFeature)
        self.assertNotIsInstance(groove, HoleFeature)

        self.assertIsInstance(edge, EdgeBandFeature)
        self.assertNotIsInstance(edge, HoleFeature)

    def test_feature_serialization_round_trips(self) -> None:
        """Feature 必须能经 asdict → feature_from_dict 无损往返（kind 判别）。"""
        from dataclasses import asdict

        from furniture_manufacturing.features import feature_from_dict

        samples = [
            from_hole_spec(
                HoleSpec(
                    hole_type="three_in_one_cam",
                    panel_label="left_side_panel",
                    x_global=1.0, y_global=2.0, z_global=3.0,
                    x_local=0.1, y_local=0.2, z_local=0.3,
                    diameter=12.0, depth=13.5, direction="-z",
                    is_face_hole=True, note="轮",
                    connection_id="left_side_panel→top_panel#0",
                )
            ),
            from_machining_operation(
                MachiningOperation(
                    id="g", operation_type="cut_box", target_panel="p",
                    size_x=6, size_y=10, size_z=914,
                    pos_x=1, pos_y=2, pos_z=3,
                )
            ),
            from_edge_banding("p", {"四边": "ABS 1.0mm同色"})[0],
        ]
        for feature in samples:
            self.assertEqual(feature_from_dict(asdict(feature)), feature)

    def test_bom_report_features_serialize_round_trip(self) -> None:
        """BOMReport 的 features/connection_points 字段必须能经 asdict 无损往返。"""
        from dataclasses import asdict

        from furniture_manufacturing.connection_points import ConnectionPoint
        from furniture_manufacturing.features import feature_from_dict
        from furniture_manufacturing.manufacturing_bom import (
            plan_manufacturing,
        )
        from furniture_panel_planning.panel_planning import plan_panels
        from furniture_panel_planning.structure_planning import CabinetStructure
        from panel_fixtures import furniture_spec

        spec = furniture_spec(
            furniture_category="floor_cabinet",
            width=800, depth=600, height=1000,
            n_doors=2, back_mount="insert",
        )
        structure = CabinetStructure.from_spec(spec)
        placements = plan_panels(spec, structure)
        bom = plan_manufacturing(spec, placements)

        data = asdict(bom)
        restored_features = [
            feature_from_dict(item) for item in data["features"]
        ]
        restored_points = [
            ConnectionPoint.from_dict(item)
            for item in data["connection_points"]
        ]
        self.assertEqual(restored_features, bom.features)
        self.assertEqual(restored_points, bom.connection_points)

    def test_collect_features_unifies_three_kinds(self) -> None:
        """collect_features 把孔/槽/封边统一成一个 Feature 列表。"""
        from furniture_manufacturing.manufacturing_bom import (
            collect_features,
            plan_manufacturing,
        )
        from furniture_panel_planning.panel_planning import plan_panels
        from furniture_panel_planning.structure_planning import CabinetStructure
        from panel_fixtures import furniture_spec

        spec = furniture_spec(
            furniture_category="floor_cabinet",
            width=800, depth=600, height=1000,
            n_doors=2, back_mount="groove",
        )
        structure = CabinetStructure.from_spec(spec)
        placements = plan_panels(spec, structure)
        bom = plan_manufacturing(spec, placements)

        features = collect_features(bom)

        holes = [f for f in features if isinstance(f, HoleFeature)]
        grooves = [f for f in features if isinstance(f, GrooveFeature)]
        edges = [f for f in features if isinstance(f, EdgeBandFeature)]

        self.assertTrue(holes)     # 三合一 + 铰链孔
        self.assertTrue(grooves)   # 背板槽（back_mount=groove → 4 条 cut_box）
        self.assertTrue(edges)     # 封边


if __name__ == "__main__":
    unittest.main()
