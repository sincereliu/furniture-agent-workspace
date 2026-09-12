from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_manufacturing.connection_points import (
    ConnectionPoint,
    collect_connection_points,
    parse_connection_id,
)
from furniture_manufacturing.connectors.base import make_connection_id
from furniture_manufacturing.features import HoleFeature


class ConnectionPointContractTests(unittest.TestCase):
    def test_parse_connection_id_round_trips_make_connection_id(self) -> None:
        """connection_id 字符串必须确定性解析回结构字段（与 make 互为逆向）。"""
        for bearing, end, row in (
            ("left_side_panel", "top_panel", 0),
            ("right_side_panel", "bottom_panel", 1),
            ("cabinet2__left_side_panel", "cabinet2__top_panel", 2),
        ):
            conn_id = make_connection_id(bearing, end, row)
            self.assertEqual(
                parse_connection_id(conn_id),
                (bearing, end, row),
            )

    def test_collect_connection_points_groups_three_in_one(self) -> None:
        """一套三合一（轮/杆/螺母）按 connection_id 归为一个连接点实体。"""
        conn_id = make_connection_id("left_side_panel", "top_panel", 0)

        def hole(hole_type: str) -> HoleFeature:
            return HoleFeature(
                hole_type=hole_type,
                panel_label="left_side_panel",
                connection_id=conn_id,
            )

        points = collect_connection_points(
            [
                hole("three_in_one_cam"),
                hole("three_in_one_rod"),
                hole("three_in_one_nut"),
            ]
        )

        self.assertEqual(len(points), 1)
        point = points[0]
        self.assertIsInstance(point, ConnectionPoint)
        self.assertEqual(point.connection_id, conn_id)
        self.assertEqual(point.bearing_id, "left_side_panel")
        self.assertEqual(point.end_id, "top_panel")
        self.assertEqual(point.row_index, 0)
        self.assertEqual(
            len(point.holes_of_type("three_in_one_cam")), 1
        )
        self.assertEqual(
            len(point.holes_of_type("three_in_one_rod")), 1
        )
        self.assertEqual(
            len(point.holes_of_type("three_in_one_nut")), 1
        )

    def test_collect_connection_points_skips_unconnected_holes(self) -> None:
        """无 connection_id 的孔不构成连接点，被跳过。"""
        unconnected = HoleFeature(hole_type="shelf_pin", panel_label="shelf")
        connected = HoleFeature(
            hole_type="three_in_one_cam",
            panel_label="left_side_panel",
            connection_id=make_connection_id("left_side_panel", "top_panel", 0),
        )
        points = collect_connection_points([unconnected, connected])
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].connection_id, connected.connection_id)

    def test_connection_point_serialization_round_trips(self) -> None:
        """ConnectionPoint 必须能经 asdict → from_dict 无损往返。"""
        from dataclasses import asdict

        from furniture_manufacturing.connectors.base import HoleSpec
        from furniture_manufacturing.features import from_hole_spec

        conn_id = make_connection_id("left_side_panel", "top_panel", 0)
        holes = [
            from_hole_spec(
                HoleSpec(
                    hole_type=hole_type,
                    panel_label="left_side_panel",
                    connection_id=conn_id,
                )
            )
            for hole_type in (
                "three_in_one_cam",
                "three_in_one_rod",
                "three_in_one_nut",
            )
        ]
        point = collect_connection_points(holes)[0]
        self.assertEqual(ConnectionPoint.from_dict(asdict(point)), point)

    def test_connection_points_carry_owner(self) -> None:
        """plan_manufacturing 产出的连接点必须带 owner（归属连接件）。"""
        from furniture_manufacturing.manufacturing_bom import plan_manufacturing
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

        owners = {point.owner for point in bom.connection_points}
        self.assertIn("TrinityConnector", owners)
        self.assertIn("BackMountConnector", owners)
        self.assertTrue(all(point.owner for point in bom.connection_points))

    def test_planned_manufacturing_yields_complete_connection_points(self) -> None:
        """全流程产出的每个连接点都必须恰好 1 轮 + 1 杆 + 1 螺母。"""
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
            n_doors=2, back_mount="insert",
        )
        structure = CabinetStructure.from_spec(spec)
        placements = plan_panels(spec, structure)
        bom = plan_manufacturing(spec, placements)

        holes = [
            f for f in collect_features(bom)
            if isinstance(f, HoleFeature)
        ]
        points = collect_connection_points(holes)

        self.assertTrue(points)  # 柜体三合一 + 背板三合一
        for point in points:
            cam = len(point.holes_of_type("three_in_one_cam"))
            rod = len(point.holes_of_type("three_in_one_rod"))
            nut = len(point.holes_of_type("three_in_one_nut"))
            self.assertEqual(
                (cam, rod, nut),
                (1, 1, 1),
                f"连接点 {point.connection_id} 三件套不完整",
            )


if __name__ == "__main__":
    unittest.main()
