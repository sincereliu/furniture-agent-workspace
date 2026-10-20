from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_layout.layout_entry import plan_room_scene
from furniture_layout.placement import place_items, ranges_overlap
from furniture_layout.placement_check import placement_issues, polygons_overlap
from furniture_layout.scene import RoomModel, RoomScene, parse_item_specs


ROOM = {
    "id": "room",
    "name": "摆放检查",
    "width_mm": 3000,
    "depth_mm": 2000,
    "height_mm": 2400,
}


def _scene(items: list[dict], room: dict | None = None) -> RoomScene:
    planned = plan_room_scene(room or ROOM, items)
    return RoomScene.from_dict({"room": planned["room"], "items": planned["items"]})


def _placed_scene(items: list[dict], room: dict | None = None) -> RoomScene:
    """Place without planner admission, so placement issues can be inspected."""
    room_model = RoomModel.from_dict(room or ROOM)
    placed = place_items(room_model, parse_item_specs(items))
    return RoomScene(room=room_model, items=placed)


def _box(x: float, y: float, width: float = 1000.0, depth: float = 500.0):
    return [(x, y), (x + width, y), (x + width, y + depth), (x, y + depth)]


class ContactIsAllowedTests(unittest.TestCase):
    """贴边放行：底面正面积重叠再加高度重叠才算干涉。编辑器里的 JS 判定与这里逐条对应。"""

    def test_shared_edge_is_not_an_overlap(self) -> None:
        self.assertFalse(polygons_overlap(_box(0, 0), _box(1000, 0)))

    def test_one_millimetre_overlap_is_an_overlap(self) -> None:
        self.assertTrue(polygons_overlap(_box(0, 0), _box(999, 0)))

    def test_tiny_gap_is_not_an_overlap(self) -> None:
        self.assertFalse(polygons_overlap(_box(0, 0), _box(1000.001, 0)))

    def test_rotated_square_touching_edge_to_edge(self) -> None:
        # a 400 square rotated 90 degrees about its own centre still just touches
        left = _box(0, 0, 400, 400)
        right = [(400, 0), (400, 400), (800, 400), (800, 0)]
        self.assertFalse(polygons_overlap(left, right))

    def test_overlap_is_symmetric(self) -> None:
        self.assertEqual(
            polygons_overlap(_box(0, 0), _box(999, 0)),
            polygons_overlap(_box(999, 0), _box(0, 0)),
        )

    def test_ranges_touching_end_to_end_do_not_overlap(self) -> None:
        self.assertFalse(ranges_overlap(0, 500, 500, 900))
        self.assertTrue(ranges_overlap(0, 500, 499, 900))


class SceneContactTests(unittest.TestCase):
    def test_items_flush_against_each_other_are_accepted(self) -> None:
        scene = _scene([
            {"id": "a", "label": "A", "category": "desk", "width": 1000, "depth": 500,
             "height": 750, "placement": {"mode": "free", "origin_x_mm": 0, "origin_y_mm": 0}},
            {"id": "b", "label": "B", "category": "desk", "width": 1000, "depth": 500,
             "height": 750, "placement": {"mode": "free", "origin_x_mm": 1000, "origin_y_mm": 0}},
        ])
        self.assertEqual(placement_issues(scene), {})

    def test_items_overlapping_by_one_millimetre_are_reported(self) -> None:
        items = [
            {"id": "a", "label": "A", "category": "desk", "width": 1000, "depth": 500,
             "height": 750, "placement": {"mode": "free", "origin_x_mm": 0, "origin_y_mm": 0}},
            {"id": "b", "label": "B", "category": "desk", "width": 1000, "depth": 500,
             "height": 750, "placement": {"mode": "free", "origin_x_mm": 999, "origin_y_mm": 0}},
        ]
        report = placement_issues(_placed_scene(items))
        self.assertIn("item:b", report["a"])
        self.assertIn("item:a", report["b"])
        with self.assertRaisesRegex(ValueError, "interferes with item"):
            plan_room_scene(ROOM, items)

    def test_items_touching_at_the_room_edge_are_accepted(self) -> None:
        scene = _scene([
            {"id": "a", "label": "A", "category": "desk", "width": 3000, "depth": 500,
             "height": 750, "placement": {"mode": "free", "origin_x_mm": 0, "origin_y_mm": 0}},
        ])
        self.assertEqual(placement_issues(scene), {})

    def test_wall_item_touching_an_opening_edge_is_accepted(self) -> None:
        room = dict(ROOM)
        room["openings"] = [
            {"id": "window", "kind": "window", "wall": "north", "offset_mm": 1000,
             "width_mm": 500, "sill_height_mm": 900, "height_mm": 1200},
        ]
        scene = _scene([
            {"id": "wardrobe", "label": "衣柜", "category": "wardrobe", "width": 1000,
             "depth": 600, "height": 2000,
             "placement": {"mode": "wall", "host_wall": "north"}},
        ], room)
        # 0..1000 is flush with the window span starting at 1000
        self.assertEqual(placement_issues(scene), {})

    def test_wall_item_wider_than_the_gap_packs_past_the_opening(self) -> None:
        """窗前只剩 1000。宽 1001 的柜子贴不进这段，就贴到窗后，不挡这扇窗。"""
        room = dict(ROOM)
        room["openings"] = [
            {"id": "window", "kind": "window", "wall": "north", "offset_mm": 1000,
             "width_mm": 500, "sill_height_mm": 900, "height_mm": 1200},
        ]
        items = [
            {"id": "wardrobe", "label": "衣柜", "category": "wardrobe", "width": 1001,
             "depth": 600, "height": 2000,
             "placement": {"mode": "wall", "host_wall": "north"}},
        ]
        scene = _placed_scene(items, room)
        self.assertEqual(scene.items[0].placement.origin_x_mm, 1500)
        self.assertEqual(placement_issues(scene), {})

    def test_wall_item_wider_than_every_free_span_does_not_fit(self) -> None:
        room = dict(ROOM)
        room["openings"] = [
            {"id": "window", "kind": "window", "wall": "north", "offset_mm": 1000,
             "width_mm": 500, "sill_height_mm": 900, "height_mm": 1200},
        ]
        items = [
            {"id": "wardrobe", "label": "衣柜", "category": "wardrobe", "width": 1600,
             "depth": 600, "height": 2000,
             "placement": {"mode": "wall", "host_wall": "north"}},
        ]
        with self.assertRaisesRegex(ValueError, "does not fit"):
            plan_room_scene(room, items)

    def test_a_free_envelope_across_an_opening_is_reported(self) -> None:
        room = dict(ROOM)
        room["openings"] = [
            {"id": "window", "kind": "window", "wall": "north", "offset_mm": 1000,
             "width_mm": 500, "sill_height_mm": 900, "height_mm": 1200},
        ]
        items = [
            {"id": "wardrobe", "label": "衣柜", "category": "wardrobe", "width": 400,
             "depth": 600, "height": 2000,
             "placement": {"mode": "free", "origin_x_mm": 800, "origin_y_mm": 0}},
        ]
        scene = _placed_scene(items, room)
        self.assertIn("opening:window", placement_issues(scene)["wardrobe"])
        with self.assertRaisesRegex(ValueError, "blocks window"):
            plan_room_scene(room, items)


if __name__ == "__main__":
    unittest.main()
