"""沿墙铺满：一段墙长拆成若干台，宽度加起来等于这段墙。

工艺目录仍是数据：读得到、校验得住、缺项说得清。
铺墙只用该柜类的门宽上限，不扣收口。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_layout.craft_catalog import (
    DEFAULT_CATALOG_PATH,
    MissingCraftData,
    load_craft_catalog,
)
from furniture_layout.scene_planning import plan_scene
from furniture_layout.space_split import unit_widths


def room(width_mm: float) -> dict:
    return {
        "id": "room",
        "name": "衣帽间",
        "width_mm": width_mm,
        "depth_mm": 3000,
        "height_mm": 3200,
    }


def fill_item(**overrides) -> dict:
    item = {
        "id": "wardrobe_run",
        "label": "衣柜",
        "category": "wardrobe",
        "furniture_category": "floor_cabinet",
        "kind": "wardrobe",
        "depth": 600,
        "height": 2400,
        "placement": {
            "mode": "wall",
            "host_wall": "north",
            "offset_mm": 0,
            "fill": True,
        },
    }
    placement = overrides.pop("placement", None)
    item.update(overrides)
    if placement is not None:
        item["placement"] = {**item["placement"], **placement}
    return item


class CraftCatalogTests(unittest.TestCase):
    """目录是数据：读得到、校验得住、缺项说得清。"""

    def setUp(self) -> None:
        self.catalog = load_craft_catalog()

    def test_real_catalog_carries_the_workshop_numbers(self) -> None:
        self.assertEqual(self.catalog.version, "draft-2026-10-02")
        self.assertEqual(self.catalog.door_bounds("wardrobe"), (300.0, 450.0))
        self.assertEqual(self.catalog.door_bounds("kitchen_base"), (400.0, 450.0))
        self.assertEqual(self.catalog.door_bounds("sideboard"), (350.0, 400.0))
        self.assertEqual(self.catalog.recommended_depth_mm("wardrobe"), 600.0)
        self.assertEqual(self.catalog.recommended_depth_mm("sideboard"), 350.0)
        self.assertEqual(self.catalog.toe_kick_mm_for("kitchen_base"), 100.0)
        self.assertEqual(self.catalog.toe_kick_mm_for("wardrobe"), 50.0)
        # 厨房：柜体高 = 台面完成面 830 − 常用台面厚 15。
        self.assertEqual(self.catalog.envelope_height_mm("kitchen_base"), 815.0)
        # 收口策略默认按上限记。铺墙不拿它扣宽度。
        self.assertEqual(self.catalog.filler_policy, "reserve_max")
        self.assertEqual(self.catalog.filler_mm("wardrobe"), 60.0)
        # 还没给的三项，要能报出来。
        self.assertEqual(
            self.catalog.missing_readiness_keys(),
            ("unit_widths_mm", "bays", "reach"),
        )

    def test_unknown_family_stops_and_asks(self) -> None:
        with self.assertRaises(MissingCraftData) as caught:
            self.catalog.family("tv_wall")
        self.assertIn("families.tv_wall", str(caught.exception))
        self.assertIn("wardrobe", str(caught.exception), "要说清现有柜类")

    def test_broken_catalogs_are_rejected_at_load(self) -> None:
        source = DEFAULT_CATALOG_PATH.read_text(encoding="utf-8")
        cases = {
            "区间反了": source.replace("[300, 450]", "[450, 300]", 1),
            "负数": source.replace("max_width_mm: 450", "max_width_mm: -450", 1),
            "未知键": source.replace("version:", "version_x:", 1) + "\nversion: draft\n",
            "策略不认识": source.replace("filler_policy: reserve_max", "filler_policy: guess", 1),
        }
        for label, text in cases.items():
            with self.subTest(case=label), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "craft-catalog.yaml"
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_craft_catalog(path)

    def test_missing_typical_filler_stops_and_asks(self) -> None:
        source = DEFAULT_CATALOG_PATH.read_text(encoding="utf-8").replace(
            "filler_policy: reserve_max", "filler_policy: reserve_typical", 1
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "craft-catalog.yaml"
            path.write_text(source, encoding="utf-8")
            catalog = load_craft_catalog(path)
            with self.assertRaises(MissingCraftData) as caught:
                catalog.filler_mm("wardrobe")
            self.assertIn("filler_typical_mm", str(caught.exception))


class UnitWidthTests(unittest.TestCase):
    def test_a_span_inside_the_cap_stays_one_unit(self) -> None:
        self.assertEqual(unit_widths(800, 900), (800.0,))
        self.assertEqual(unit_widths(900, 900), (900.0,))

    def test_integer_spans_put_extra_millimeters_on_the_far_units(self) -> None:
        self.assertEqual(unit_widths(1600, 900), (800.0, 800.0))
        self.assertEqual(unit_widths(2400, 900), (800.0, 800.0, 800.0))
        self.assertEqual(unit_widths(2200, 900), (733.0, 733.0, 734.0))
        self.assertEqual(unit_widths(5, 2), (1.0, 2.0, 2.0))

    def test_a_fractional_span_is_shared_equally(self) -> None:
        self.assertEqual(unit_widths(100.5, 40), (33.5, 33.5, 33.5))

    def test_bad_numbers_are_rejected(self) -> None:
        for span, cap in ((True, 900), (0, 900), (-1, 900), (float("nan"), 900)):
            with self.subTest(span=span), self.assertRaisesRegex(ValueError, "wall span"):
                unit_widths(span, cap)
        for span, cap in ((100, True), (100, 0), (100, float("inf"))):
            with self.subTest(cap=cap), self.assertRaisesRegex(ValueError, "unit width cap"):
                unit_widths(span, cap)


class WallFillTests(unittest.TestCase):
    def test_a_short_wall_is_one_cabinet_the_full_span_wide(self) -> None:
        scene = plan_scene(room(800), [fill_item()])
        self.assertEqual([item.id for item in scene.items], ["wardrobe_run_u1"])
        self.assertEqual(scene.items[0].width, 800.0)
        self.assertEqual(scene.items[0].label, "衣柜")
        self.assertEqual(scene.items[0].placement.offset_mm, 0.0)
        self.assertFalse(scene.items[0].placement.fill)
        self.assertIsNone(scene.items[0].kind)
        self.assertEqual(scene.items[0].furniture_category, "floor_cabinet")

    def test_two_cabinets_sit_end_to_end(self) -> None:
        scene = plan_scene(room(1600), [fill_item()])
        self.assertEqual([item.width for item in scene.items], [800.0, 800.0])
        self.assertEqual(
            [item.placement.offset_mm for item in scene.items],
            [0.0, 800.0],
        )

    def test_a_2400_wardrobe_wall_is_three_cabinets_with_no_filler_gap(self) -> None:
        scene = plan_scene(room(2400), [fill_item()])
        self.assertEqual(
            [item.id for item in scene.items],
            ["wardrobe_run_u1", "wardrobe_run_u2", "wardrobe_run_u3"],
        )
        self.assertEqual([item.width for item in scene.items], [800.0, 800.0, 800.0])
        self.assertEqual(
            [item.placement.offset_mm for item in scene.items],
            [0.0, 800.0, 1600.0],
        )
        self.assertEqual(sum(item.width for item in scene.items), 2400.0)
        self.assertEqual(
            [item.label for item in scene.items],
            ["衣柜 1", "衣柜 2", "衣柜 3"],
        )

    def test_a_span_that_starts_mid_wall_still_runs_forward(self) -> None:
        scene = plan_scene(room(2600), [fill_item(placement={"offset_mm": 200})])
        self.assertEqual([item.width for item in scene.items], [800.0, 800.0, 800.0])
        self.assertEqual(
            [item.placement.offset_mm for item in scene.items],
            [200.0, 1000.0, 1800.0],
        )

    def test_the_remainder_goes_to_the_far_cabinet(self) -> None:
        scene = plan_scene(room(2200), [fill_item()])
        self.assertEqual([item.width for item in scene.items], [733.0, 733.0, 734.0])
        self.assertEqual(
            [item.placement.offset_mm for item in scene.items],
            [0.0, 733.0, 1466.0],
        )
        self.assertEqual(sum(item.width for item in scene.items), 2200.0)

    def test_a_fill_without_a_kind_stops_and_asks(self) -> None:
        item = fill_item()
        del item["kind"]
        with self.assertRaisesRegex(ValueError, "没说要做什么柜"):
            plan_scene(room(800), [item])

    def test_manufacture_and_category_are_copied_onto_each_unit(self) -> None:
        scene = plan_scene(room(1600), [fill_item(manufacture=False)])
        self.assertEqual(len(scene.items), 2)
        for item in scene.items:
            self.assertFalse(item.manufacture)
            self.assertEqual(item.furniture_category, "floor_cabinet")
            self.assertEqual(item.depth, 600.0)
            self.assertEqual(item.height, 2400.0)

    def test_a_wall_cabinet_keeps_its_category_and_height_off_the_floor(self) -> None:
        scene = plan_scene(
            room(700),
            [
                fill_item(
                    furniture_category="wall_cabinet",
                    kind="sideboard",
                    depth=350,
                    height=800,
                    placement={"origin_z_mm": 1600},
                )
            ],
        )
        unit = scene.items[0]
        self.assertEqual(unit.id, "wardrobe_run_u1")
        self.assertEqual(unit.furniture_category, "wall_cabinet")
        self.assertEqual(unit.width, 700.0)
        self.assertEqual(unit.placement.origin_z_mm, 1600.0)
        self.assertIsNone(unit.kind)

    def test_a_room_without_fill_does_not_load_the_catalog(self) -> None:
        item = {
            "id": "desk",
            "category": "desk",
            "width": 1200,
            "depth": 600,
            "height": 750,
            "placement": {"mode": "free", "origin_x_mm": 100, "origin_y_mm": 100},
        }
        with mock.patch(
            "furniture_layout.scene_planning.load_craft_catalog",
            side_effect=AssertionError("catalog"),
        ):
            scene = plan_scene(room(4000), [item])
        self.assertEqual(scene.items[0].id, "desk")

    def test_a_saved_room_that_still_has_spaces_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "spaces"):
            plan_scene({**room(4000), "spaces": [{"id": "north_run"}]}, [fill_item()])


if __name__ == "__main__":
    unittest.main()
