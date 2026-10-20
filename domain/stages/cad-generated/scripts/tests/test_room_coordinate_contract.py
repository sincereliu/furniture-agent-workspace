"""Fix the furniture-local origin, ordered footprint, and room-space pose contract."""

from __future__ import annotations

import sys
import unittest
from math import hypot
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_layout.placement import place_items
from furniture_layout.scene import PlacedItem, RoomModel, parse_item_specs


ROOM = RoomModel.from_dict({
    "id": "coordinate-contract",
    "width_mm": 6000,
    "depth_mm": 5000,
    "height_mm": 3000,
})


def _placed(placement: dict, *, width: float = 1200, depth: float = 500,
            height: float = 1700) -> PlacedItem:
    specs = parse_item_specs([{
        "id": "cabinet", "category": "cabinet",
        "width": width, "depth": depth, "height": height,
        "placement": placement,
    }])
    return place_items(ROOM, specs)[0]


def _free(angle: float = 0, *, x: float = 2000, y: float = 1800) -> dict:
    return {
        "mode": "free", "origin_x_mm": x, "origin_y_mm": y,
        "origin_z_mm": 300, "rotation_z_deg": angle,
    }


class RoomCoordinateContractTests(unittest.TestCase):
    def test_local_origin_is_the_translated_bottom_corner(self) -> None:
        item = _placed(_free())
        self.assertEqual(item.footprint, (
            (2000, 1800), (3200, 1800), (3200, 2300), (2000, 2300),
        ))
        self.assertEqual(item.placement.origin_z_mm, 300)
        self.assertEqual(item.z_end, 2000)
        self.assertEqual(item.clearances_mm["floor"], 300)
        self.assertEqual(item.clearances_mm["ceiling"], 1000)
        self.assertEqual((item.width, item.depth, item.height), (1200, 500, 1700))

    def test_positive_rotation_turns_room_x_toward_room_y(self) -> None:
        cases = {
            90: ((2000, 1800), (2000, 3000), (1500, 3000), (1500, 1800)),
            180: ((2000, 1800), (800, 1800), (800, 1300), (2000, 1300)),
            270: ((2000, 1800), (2000, 600), (2500, 600), (2500, 1800)),
            -90: ((2000, 1800), (2000, 600), (2500, 600), (2500, 1800)),
            360: ((2000, 1800), (3200, 1800), (3200, 2300), (2000, 2300)),
        }
        for angle, expected in cases.items():
            with self.subTest(angle=angle):
                item = _placed(_free(angle))
                self.assertEqual(item.footprint, expected)
                self.assertEqual(item.placement.rotation_z_deg, angle)
                self.assertEqual(item.z_end, 2000)

    def test_arbitrary_rotation_preserves_local_width_and_depth_edges(self) -> None:
        item = _placed(_free(30))
        self.assertEqual(item.footprint, (
            (2000, 1800), (3039.230485, 2400),
            (2789.230485, 2833.012702), (1750, 2233.012702),
        ))
        p0, p1, p2, p3 = item.footprint
        self.assertAlmostEqual(hypot(p1[0] - p0[0], p1[1] - p0[1]), 1200, places=5)
        self.assertAlmostEqual(hypot(p3[0] - p0[0], p3[1] - p0[1]), 500, places=5)
        self.assertAlmostEqual(hypot(p2[0] - p3[0], p2[1] - p3[1]), 1200, places=5)

    def test_wall_back_edge_touches_host_and_front_points_into_room(self) -> None:
        cases = {
            "north": (0, ((0, 0), (1200, 0), (1200, 500), (0, 500)), (0, 500)),
            "east": (90, ((6000, 0), (6000, 1200), (5500, 1200), (5500, 0)), (-500, 0)),
            "south": (180, ((6000, 5000), (4800, 5000), (4800, 4500), (6000, 4500)), (0, -500)),
            "west": (270, ((0, 5000), (0, 3800), (500, 3800), (500, 5000)), (500, 0)),
        }
        for wall, (angle, expected, front_direction) in cases.items():
            with self.subTest(wall=wall):
                item = _placed({
                    "mode": "wall", "host_wall": wall, "origin_z_mm": 300,
                })
                self.assertEqual(item.footprint, expected)
                self.assertEqual(item.placement.rotation_z_deg, angle)
                self.assertEqual((item.placement.origin_x_mm, item.placement.origin_y_mm), expected[0])
                p0, p1, p2, p3 = item.footprint
                direction = tuple((p2[i] + p3[i] - p0[i] - p1[i]) / 2 for i in range(2))
                self.assertEqual(direction, front_direction)

    def test_same_cube_occupancy_keeps_distinct_origin_and_front(self) -> None:
        original = _placed(_free(), width=600, depth=600, height=600)
        rotated = _placed(_free(90, x=2600), width=600, depth=600, height=600)
        self.assertEqual(set(original.footprint), set(rotated.footprint))
        self.assertEqual(original.footprint, (
            (2000, 1800), (2600, 1800), (2600, 2400), (2000, 2400),
        ))
        self.assertEqual(rotated.footprint, (
            (2600, 1800), (2600, 2400), (2000, 2400), (2000, 1800),
        ))
        self.assertNotEqual(original.placement, rotated.placement)
        self.assertNotEqual(
            (original.footprint[3], original.footprint[2]),
            (rotated.footprint[3], rotated.footprint[2]),
        )
        for item in (original, rotated):
            self.assertEqual(PlacedItem.from_dict(item.to_dict()), item)

    def test_serialization_preserves_ordered_points_and_pose(self) -> None:
        for angle in (0, 90, 30):
            with self.subTest(angle=angle):
                item = _placed(_free(angle))
                payload = item.to_dict()
                self.assertEqual(payload["footprint"], [
                    {"x_mm": x, "y_mm": y} for x, y in item.footprint
                ])
                restored = PlacedItem.from_dict(payload)
                self.assertEqual(restored, item)
                self.assertEqual(restored.to_dict(), payload)


if __name__ == "__main__":
    unittest.main()
