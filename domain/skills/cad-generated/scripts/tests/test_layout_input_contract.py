"""Canonical layout requests, stored geometry, and HTTP admission behavior."""

from __future__ import annotations

import asyncio
from copy import deepcopy
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from fastapi import HTTPException
from pydantic import ValidationError

from fake_request_support import local_request
from furniture_layout import room_http
from furniture_layout.layout_entry import plan_project_layout, plan_room_scene
from furniture_layout.project_edit import apply_layout_edit, room_scene_source
from furniture_layout.project_layout import ProjectLayout
from furniture_layout.room_page import render_viewer
from furniture_layout.scene import RoomScene
from furniture_layout.scene_edit import apply_edit
from furniture_layout.scene_planning import plan_scene


ROOM = {"id": "room", "width_mm": 4000, "depth_mm": 3000, "height_mm": 2800}
ITEM = {
    "id": "cabinet", "category": "cabinet", "furniture_category": "floor_cabinet",
    "width": 800, "depth": 500, "height": 1000,
    "placement": {"mode": "wall", "host_wall": "north", "offset_mm": 100},
}


class LayoutInputContractTests(unittest.TestCase):
    def test_canonical_room_and_project_plan_the_same_geometry(self) -> None:
        room = plan_room_scene(ROOM, [ITEM])
        project = plan_project_layout([{**ROOM, "items": [ITEM]}])
        self.assertEqual(project["rooms"][0], room)
        self.assertEqual(ProjectLayout.from_dict(project).to_dict(), project)

    def test_room_aliases_are_rejected_even_with_canonical_fields(self) -> None:
        for alias in ("room_id", "width", "depth", "height"):
            with self.subTest(alias=alias), self.assertRaisesRegex(ValueError, alias):
                plan_scene({**ROOM, alias: 1000}, [ITEM])

    def test_item_dimension_aliases_are_rejected(self) -> None:
        for alias in ("width_mm", "depth_mm", "height_mm"):
            with self.subTest(alias=alias), self.assertRaisesRegex(ValueError, alias):
                plan_scene(ROOM, [{**ITEM, alias: 1000}])

    def test_cabinet_kind_is_not_a_layout_field(self) -> None:
        with self.assertRaisesRegex(ValueError, "kind"):
            plan_scene(ROOM, [{**ITEM, "kind": "wardrobe"}])

    def test_legacy_spaces_field_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "spaces"):
            plan_scene({**ROOM, "spaces": [{"id": "north_run"}]}, [ITEM])

    def test_item_ids_must_be_usable_by_the_panel_stage(self) -> None:
        """家具 id 的形状卡在**入口**：板件阶段拿它拼板件编号。

        以前 `cabinet-1` 这种 id 能建项目、能过摆放检查、能确认，跑到板件才炸；
        所以入口（三个入口共用的 plan_scene）直接拒，并且报错点名是哪一件。
        """
        for bad in ("cabinet-1", "1cabinet", "cabinet__x", "柜子", "cabinet.1"):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "cabinet_1|id"):
                    plan_scene(ROOM, [{**ITEM, "id": bad}])
        # 合法形状照样过（含省略 id 时自动补的那个）。
        for good in ("cabinet_1", "Cabinet", "_cabinet", "cabinet1"):
            with self.subTest(good=good):
                self.assertEqual(plan_scene(ROOM, [{**ITEM, "id": good}]).items[0].id, good)
        self.assertEqual(plan_scene(ROOM, [{k: v for k, v in ITEM.items() if k != "id"}]).items[0].id, "item_1")
        # 空 id 照旧按"没给"处理（自动补 item_1），不因为这条校验改变既有行为。
        self.assertEqual(plan_scene(ROOM, [{**ITEM, "id": ""}]).items[0].id, "item_1")
        # 报错要指名道姓，不然一个项目里十几件没人知道改哪一件。
        with self.assertRaisesRegex(ValueError, r"items\[0\]\.id 'cabinet-1'"):
            plan_scene(ROOM, [{**ITEM, "id": "cabinet-1"}])
        # **只校验输入，不校验读取**：库里已有的旧 id 仍然打得开（靠一次性迁移改名）。
        legacy = plan_scene(ROOM, [ITEM]).to_dict()
        legacy["items"][0]["id"] = "cabinet-1"
        self.assertEqual(RoomScene.from_dict(legacy).items[0].id, "cabinet-1")

    def test_placement_aliases_are_rejected(self) -> None:
        for alias in (
            "wall", "offset", "x", "y", "z", "x_mm", "y_mm", "z_mm",
            "elevation_mm", "rotation", "rotation_deg",
        ):
            item = deepcopy(ITEM)
            item["placement"][alias] = 0
            with self.subTest(alias=alias), self.assertRaisesRegex(ValueError, alias):
                plan_scene(ROOM, [item])

    def test_mode_is_required_and_enums_are_exact(self) -> None:
        for placement in ({"host_wall": "north"}, {"mode": "WALL", "host_wall": "north"}):
            with self.subTest(placement=placement), self.assertRaisesRegex(ValueError, "mode"):
                plan_scene(ROOM, [{**ITEM, "placement": placement}])

    def test_openings_and_obstacles_require_canonical_fields(self) -> None:
        opening = {"id": "door", "kind": "door", "wall": "south", "width_mm": 900, "height_mm": 2100}
        obstacle = {"id": "column", "x_mm": 3000, "y_mm": 2000, "width_mm": 100, "depth_mm": 100, "height_mm": 2000}
        for field, entry, alias in (("openings", opening, "offset"), ("obstacles", obstacle, "x")):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, alias):
                plan_scene({**ROOM, field: [{**entry, alias: 0}]}, [ITEM])
        for kind in ("opening", "DOOR", ""):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "kind"):
                plan_scene({**ROOM, "openings": [{**opening, "kind": kind}]}, [ITEM])

    def test_invalid_flags_and_nonfinite_numbers_are_rejected(self) -> None:
        for value in (0, 1, "false", None):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "boolean"):
                plan_scene(ROOM, [{**ITEM, "manufacture": value}])
        for value in (0, 1, "true", None):
            item = deepcopy(ITEM)
            item["placement"]["fill"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "boolean"):
                plan_scene(ROOM, [item])
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "finite"):
                plan_scene(ROOM, [{**ITEM, "width": value}])

    def test_fill_cannot_hide_invalid_placement_fields(self) -> None:
        for placement in (
            {"mode": "free", "host_wall": "north", "fill": True},
            {"mode": "wall", "host_wall": "north", "origin_x_mm": 50, "fill": True},
        ):
            with self.subTest(placement=placement), self.assertRaises(ValueError):
                plan_scene(ROOM, [{**ITEM, "placement": placement}])

    def test_edit_source_contains_no_derived_geometry(self) -> None:
        layout = ProjectLayout.from_source({"rooms": [{**ROOM, "items": [ITEM]}]})
        source = room_scene_source(layout.rooms[0])
        self.assertEqual(source["items"][0]["placement"], {
            "mode": "wall", "host_wall": "north", "offset_mm": 100,
            "origin_z_mm": 0, "fill": False,
        })
        self.assertNotIn("footprint", source["items"][0])
        self.assertNotIn("clearances_mm", source["items"][0])
        self.assertEqual(plan_scene(source["room"], source["items"]), layout.rooms[0])
        edited = apply_layout_edit(layout, {"op": "move", "item_id": "cabinet", "offset_mm": 200})
        self.assertEqual(edited.rooms[0].items[0].footprint[0], (200, 0))
        self.assertEqual(layout.rooms[0].items[0].footprint[0], (100, 0))

    def test_stored_layout_requires_version_and_nested_room(self) -> None:
        output = plan_project_layout([{**ROOM, "items": [ITEM]}])
        for version in (None, "1", True, 999):
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, "schema_version"):
                ProjectLayout.from_dict({**output, "schema_version": version})
        flat_room = {**output["rooms"][0]["room"], "items": output["rooms"][0]["items"]}
        with self.assertRaisesRegex(ValueError, "room must be an object"):
            ProjectLayout.from_dict({**output, "rooms": [flat_room]})

    def test_saved_viewer_carries_canonical_geometry(self) -> None:
        scene = plan_scene(ROOM, [ITEM])
        viewer = render_viewer(scene)
        import json
        import re

        html = viewer["html"]
        payload = json.loads(re.search(r'<script id="scene-data" type="application/json">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(RoomScene.from_dict(payload), scene)
        self.assertIn("const READ_ONLY=true", html)
        self.assertNotIn("__SCENE_JSON__", html)


class LayoutHttpContractTests(unittest.TestCase):
    def test_nested_http_models_reject_aliases_and_missing_mode(self) -> None:
        invalid = [
            {"room": {**ROOM, "width": 4000}, "items": [ITEM]},
            {"room": ROOM, "items": [{**ITEM, "width_mm": 800}]},
            {"room": ROOM, "items": [{**ITEM, "placement": {"host_wall": "north"}}]},
            {"room": ROOM, "items": [{**ITEM, "manufacture": "false"}]},
        ]
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValidationError):
                room_http.RoomSceneRequest(**data)

    def test_http_fill_keeps_one_envelope_and_manufacturing_flags(self) -> None:
        """铺满走 HTTP：窄墙仍是这一台，宽度是空段，`manufacture: false` 照样带过去。"""
        item = deepcopy(ITEM)
        del item["width"]
        item["placement"]["fill"] = True
        item["manufacture"] = False
        narrow = {**ROOM, "width_mm": 900}
        response = asyncio.run(
            room_http.plan_room(room_http.RoomSceneRequest(room=narrow, items=[item]))
        )
        # 墙长 900、件从 100 起铺满 → 空段 800，宽度就是 800。
        self.assertEqual(response.items[0]["id"], "cabinet")
        self.assertEqual(response.items[0]["width"], 800)
        self.assertTrue(response.items[0]["placement"]["fill"])
        self.assertEqual(response.items[0]["furniture_category"], "floor_cabinet")
        self.assertIs(response.items[0]["manufacture"], False)

    def test_invalid_geometry_is_rejected_before_saving(self) -> None:
        item = {**ITEM, "width": 5000}
        request = room_http.RoomSceneSaveRequest(room=ROOM, items=[item])
        with (
            mock.patch.object(room_http, "may_edit", return_value=True),
            mock.patch.object(room_http, "save_scene_source") as save,
        ):
            with self.assertRaises(HTTPException) as rejected:
                asyncio.run(room_http.save_room_scene(request, local_request()))
            self.assertEqual(rejected.exception.status_code, 422)
            save.assert_not_called()


NORTH = {"id": "room", "width_mm": 4000, "depth_mm": 3000, "height_mm": 2800}


def _desk(offset: float) -> dict:
    return {
        "id": "desk",
        "category": "desk",
        "width": 1000,
        "depth": 500,
        "height": 850,
        "placement": {"mode": "wall", "host_wall": "north", "offset_mm": offset},
    }


def _fill(*, height: float = 2200, **placement) -> dict:
    return {
        "id": "run",
        "category": "wardrobe",
        "depth": 600,
        "height": height,
        "placement": {"mode": "wall", "host_wall": "north", "fill": True, **placement},
    }


def _named(layout: ProjectLayout, item_id: str):
    return next(item for item in layout.rooms[0].items if item.id == item_id)


class FillSpanEditTests(unittest.TestCase):
    def test_omitted_fill_offset_follows_the_longest_span(self) -> None:
        """北墙 4000，西端一台宽 1000 的书桌。铺满没写 offset_mm。

        书桌挪到 500：最长空段是 1500–4000，铺满宽 2500。
        书桌挪到 2000：最长空段改成 0–2000，铺满宽 2000。
        """
        layout = ProjectLayout.from_source(
            {"rooms": [{**NORTH, "items": [_desk(0), _fill()]}]}
        )
        run = _named(layout, "run")
        self.assertEqual((run.placement.offset_mm, run.width), (1000, 3000))
        self.assertFalse(run.placement.offset_given)
        source = run.to_source()["placement"]
        self.assertNotIn("offset_mm", source)
        self.assertNotIn("offset_given", source)

        beside = apply_layout_edit(
            layout, {"op": "move", "item_id": "desk", "offset_mm": 500}
        )
        run = _named(beside, "run")
        self.assertEqual((run.placement.offset_mm, run.width), (1500, 2500))
        self.assertFalse(run.placement.offset_given)

        across = apply_layout_edit(
            layout, {"op": "move", "item_id": "desk", "offset_mm": 2000}
        )
        run = _named(across, "run")
        self.assertEqual((run.placement.offset_mm, run.width), (0, 2000))
        self.assertFalse(run.placement.offset_given)
        self.assertEqual(_named(layout, "desk").placement.offset_mm, 0)

    def test_door_fill_start_is_recomputed_with_the_room(self) -> None:
        """门占北墙 0–900。铺满从 900 起、宽 3100。下一次请求不带着这个 900。

        再在 1200 放一台宽 1000 的柜子后，最长空段是 2200–4000。
        """
        room = {
            **NORTH,
            "openings": [{
                "id": "entry",
                "kind": "door",
                "wall": "north",
                "offset_mm": 0,
                "width_mm": 900,
                "height_mm": 2100,
            }],
        }
        scene = plan_scene(room, [_fill()])
        run = scene.items[0]
        self.assertEqual((run.placement.offset_mm, run.width), (900, 3100))
        self.assertFalse(run.placement.offset_given)
        source = run.to_source()
        self.assertNotIn("offset_mm", source["placement"])
        replanned = plan_scene(room, [source, _desk(1200)])
        run = next(item for item in replanned.items if item.id == "run")
        self.assertEqual((run.placement.offset_mm, run.width), (2200, 1800))
        self.assertFalse(run.placement.offset_given)

    def test_given_fill_offset_stays_on_its_span(self) -> None:
        """写了 offset_mm: 1000 的铺满，书桌挪开后仍从 1000 铺到所在空段的终点。

        书桌盖住 1000 时，这次编辑失败，原来的摆放不动。
        """
        layout = ProjectLayout.from_source(
            {"rooms": [{**NORTH, "items": [_desk(0), _fill(offset_mm=1000)]}]}
        )
        run = _named(layout, "run")
        self.assertTrue(run.placement.offset_given)
        self.assertEqual((run.placement.offset_mm, run.width), (1000, 3000))
        self.assertEqual(run.to_source()["placement"]["offset_mm"], 1000)
        self.assertNotIn("offset_given", run.to_source()["placement"])

        kept = apply_layout_edit(
            layout, {"op": "move", "item_id": "desk", "offset_mm": 1500}
        )
        run = _named(kept, "run")
        self.assertEqual((run.placement.offset_mm, run.width), (1000, 500))
        self.assertTrue(run.placement.offset_given)

        with self.assertRaisesRegex(ValueError, "fill offset_mm is not on a free span"):
            apply_layout_edit(
                layout, {"op": "move", "item_id": "desk", "offset_mm": 200}
            )
        self.assertEqual(_named(layout, "desk").placement.offset_mm, 0)
        self.assertEqual(_named(layout, "run").width, 3000)

    def test_explicit_zero_offset_is_given(self) -> None:
        """offset_mm: 0 算写了起点。书桌从 2500 挪到 500 后，铺满留在 0–500。"""
        layout = ProjectLayout.from_source(
            {"rooms": [{**NORTH, "items": [_desk(2500), _fill(offset_mm=0)]}]}
        )
        run = _named(layout, "run")
        self.assertTrue(run.placement.offset_given)
        self.assertEqual((run.placement.offset_mm, run.width), (0, 2500))
        moved = apply_layout_edit(
            layout, {"op": "move", "item_id": "desk", "offset_mm": 500}
        )
        run = _named(moved, "run")
        self.assertEqual((run.placement.offset_mm, run.width), (0, 500))
        self.assertTrue(run.placement.offset_given)

    def test_fill_edit_accepts_only_origin_z_on_both_paths(self) -> None:
        """吊柜铺满整面北墙。离地从 1400 改到 1600，宽度仍是 4000。

        项目编辑和房间编辑都拒绝改沿墙起点、朝向和宽度。
        """
        layout = ProjectLayout.from_source(
            {"rooms": [{**NORTH, "items": [_fill(height=700, origin_z_mm=1400)]}]}
        )
        run = _named(layout, "run")
        self.assertEqual(run.width, 4000)
        self.assertFalse(run.placement.offset_given)

        raised = apply_layout_edit(
            layout, {"op": "move", "item_id": "run", "origin_z_mm": 1600}
        )
        run = _named(raised, "run")
        self.assertEqual(run.placement.origin_z_mm, 1600)
        self.assertEqual(run.width, 4000)
        self.assertFalse(run.placement.offset_given)
        self.assertNotIn("offset_mm", run.to_source()["placement"])

        source = room_scene_source(layout.rooms[0])
        edited = apply_edit(
            source, {"op": "move", "item_id": "run", "origin_z_mm": 1600}
        )
        self.assertNotIn("offset_mm", edited["items"][0]["placement"])
        replanned = plan_scene(edited["room"], edited["items"])
        run = replanned.items[0]
        self.assertEqual((run.placement.origin_z_mm, run.width), (1600, 4000))
        self.assertFalse(run.placement.offset_given)

        refused = (
            {"op": "move", "item_id": "run", "offset_mm": 200},
            {
                "op": "rotate",
                "item_id": "run",
                "rotation_z_deg": 15,
                "mode": "free",
                "origin_x_mm": 100,
                "origin_y_mm": 100,
            },
            {"op": "resize", "item_id": "run", "width": 1000},
        )
        for op in refused:
            with self.subTest(path="room", op=op["op"]):
                with self.assertRaisesRegex(ValueError, "only origin_z_mm can change"):
                    apply_edit(source, op)
            with self.subTest(path="project", op=op["op"]):
                with self.assertRaisesRegex(ValueError, "only origin_z_mm can change"):
                    apply_layout_edit(layout, op)

    def test_saved_fill_without_offset_given_cannot_load(self) -> None:
        """铺满结果缺 offset_given 就打不开。靠墙和自由摆放的旧结果仍能打开。"""
        filled = plan_scene(NORTH, [_fill()]).to_dict()
        del filled["items"][0]["placement"]["offset_given"]
        with self.assertRaisesRegex(ValueError, "fill placement requires offset_given"):
            RoomScene.from_dict(filled)

        wall = plan_scene(NORTH, [ITEM]).to_dict()
        del wall["items"][0]["placement"]["offset_given"]
        self.assertTrue(RoomScene.from_dict(wall).items[0].placement.offset_given)

        free = plan_scene(NORTH, [{
            "id": "sofa",
            "category": "sofa",
            "width": 800,
            "depth": 800,
            "height": 800,
            "placement": {"mode": "free", "origin_x_mm": 1000, "origin_y_mm": 1000},
        }]).to_dict()
        del free["items"][0]["placement"]["offset_given"]
        self.assertFalse(RoomScene.from_dict(free).items[0].placement.offset_given)


if __name__ == "__main__":
    unittest.main()
