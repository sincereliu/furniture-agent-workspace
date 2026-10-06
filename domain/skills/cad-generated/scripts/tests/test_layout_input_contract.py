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
    "placement": {"mode": "wall", "host_wall": "north"},
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
            "mode": "wall", "host_wall": "north",
            "origin_z_mm": 0, "fill": False,
        })
        self.assertNotIn("footprint", source["items"][0])
        self.assertNotIn("clearances_mm", source["items"][0])
        self.assertEqual(plan_scene(source["room"], source["items"]), layout.rooms[0])
        self.assertEqual(layout.rooms[0].items[0].footprint[0], (0, 0))
        edited = apply_layout_edit(
            layout, {"op": "move", "item_id": "cabinet", "host_wall": "east"}
        )
        self.assertEqual(edited.rooms[0].items[0].footprint[0], (4000, 0))
        self.assertEqual(layout.rooms[0].items[0].footprint[0], (0, 0))

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
        self.assertEqual(response.items[0]["id"], "cabinet")
        self.assertEqual(response.items[0]["width"], 900)
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


def _desk() -> dict:
    return {
        "id": "desk",
        "category": "desk",
        "width": 1000,
        "depth": 500,
        "height": 850,
        "placement": {"mode": "wall", "host_wall": "north"},
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
    def test_fixed_cabinet_packs_and_fill_takes_the_remainder(self) -> None:
        """北墙 4000。宽 1000 的书桌贴在墙头。铺满占剩下的 3000。

        书桌加宽到 1500 后，铺满改贴到 1500，宽 2500。原来的布局不动。
        """
        layout = ProjectLayout.from_source(
            {"rooms": [{**NORTH, "items": [_desk(), _fill()]}]}
        )
        desk = _named(layout, "desk")
        run = _named(layout, "run")
        self.assertEqual((desk.placement.origin_x_mm, desk.width), (0, 1000))
        self.assertEqual((run.placement.origin_x_mm, run.width), (1000, 3000))
        source = run.to_source()["placement"]
        self.assertNotIn("origin_x_mm", source)
        self.assertNotIn("offset_mm", source)

        wider = apply_layout_edit(
            layout, {"op": "resize", "item_id": "desk", "width": 1500}
        )
        run = _named(wider, "run")
        self.assertEqual((_named(wider, "desk").width, run.placement.origin_x_mm, run.width), (1500, 1500, 2500))
        self.assertEqual(_named(layout, "desk").width, 1000)

    def test_door_and_neighbor_leave_the_longest_span(self) -> None:
        """门占北墙 0–900。铺满从 900 起、宽 3100。下一次请求不带着这个起点。

        再放一台宽 1000 的柜子：门后的空段才放得下，它贴在 900。
        铺满改占 1900–4000。
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
        self.assertEqual((run.placement.origin_x_mm, run.width), (900, 3100))
        source = run.to_source()
        self.assertNotIn("origin_x_mm", source["placement"])
        self.assertNotIn("offset_mm", source["placement"])
        replanned = plan_scene(room, [source, _desk()])
        desk = next(item for item in replanned.items if item.id == "desk")
        run = next(item for item in replanned.items if item.id == "run")
        self.assertEqual((desk.placement.origin_x_mm, desk.width), (900, 1000))
        self.assertEqual((run.placement.origin_x_mm, run.width), (1900, 2100))

    def test_cabinet_offset_is_rejected(self) -> None:
        """柜子不收沿墙偏移。写在普通靠墙柜或铺满柜上都会被拒绝。"""
        for key, value in (("offset_mm", 0), ("offset_given", False)):
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, key):
                    plan_scene(NORTH, [{
                        **_desk(),
                        "placement": {**_desk()["placement"], key: value},
                    }])
                with self.assertRaisesRegex(ValueError, key):
                    plan_scene(NORTH, [_fill(**{key: value})])

    def test_fill_edit_accepts_only_origin_z_on_both_paths(self) -> None:
        """吊柜铺满整面北墙。离地从 1400 改到 1600，宽度仍是 4000。

        项目编辑和房间编辑都拒绝改沿墙起点、朝向和宽度。
        """
        layout = ProjectLayout.from_source(
            {"rooms": [{**NORTH, "items": [_fill(height=700, origin_z_mm=1400)]}]}
        )
        run = _named(layout, "run")
        self.assertEqual(run.width, 4000)
        self.assertNotIn("offset_mm", run.to_source()["placement"])
        self.assertNotIn("offset_given", run.to_source()["placement"])

        raised = apply_layout_edit(
            layout, {"op": "move", "item_id": "run", "origin_z_mm": 1600}
        )
        run = _named(raised, "run")
        self.assertEqual(run.placement.origin_z_mm, 1600)
        self.assertEqual(run.width, 4000)
        self.assertNotIn("offset_mm", run.to_source()["placement"])
        self.assertNotIn("offset_given", run.to_source()["placement"])

        source = room_scene_source(layout.rooms[0])
        edited = apply_edit(
            source, {"op": "move", "item_id": "run", "origin_z_mm": 1600}
        )
        self.assertNotIn("offset_mm", edited["items"][0]["placement"])
        replanned = plan_scene(edited["room"], edited["items"])
        run = replanned.items[0]
        self.assertEqual((run.placement.origin_z_mm, run.width), (1600, 4000))
        self.assertNotIn("offset_mm", run.to_source()["placement"])
        self.assertNotIn("offset_given", run.to_source()["placement"])

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

    def test_saved_scenes_load_without_an_along_wall_offset(self) -> None:
        """铺满、靠墙和自由摆放的结果都不带沿墙偏移，照样能打开。"""
        filled = plan_scene(NORTH, [_fill()]).to_dict()
        self.assertNotIn("offset_mm", filled["items"][0]["placement"])
        self.assertNotIn("offset_given", filled["items"][0]["placement"])
        self.assertEqual(RoomScene.from_dict(filled).items[0].id, "run")

        wall = plan_scene(NORTH, [ITEM]).to_dict()
        self.assertNotIn("offset_mm", wall["items"][0]["placement"])
        self.assertEqual(RoomScene.from_dict(wall).items[0].placement.host_wall, "north")

        free = plan_scene(NORTH, [{
            "id": "sofa",
            "category": "sofa",
            "width": 800,
            "depth": 800,
            "height": 800,
            "placement": {"mode": "free", "origin_x_mm": 1000, "origin_y_mm": 1000},
        }]).to_dict()
        self.assertEqual(RoomScene.from_dict(free).items[0].placement.mode, "free")

    def test_saved_placement_rejects_an_along_wall_offset(self) -> None:
        """结果里如果还写着沿墙偏移，就打不开。"""
        filled = plan_scene(NORTH, [_fill()]).to_dict()
        for key, value in (("offset_mm", 0), ("offset_given", False)):
            payload = deepcopy(filled)
            payload["items"][0]["placement"][key] = value
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, key):
                    RoomScene.from_dict(payload)


def _cabinet(
    item_id: str,
    *,
    host_wall: str,
    width: float | None = 800,
    depth: float = 600,
    height: float = 2100,
    origin_z_mm: float = 0,
    against: dict | None = None,
    fill: bool = False,
) -> dict:
    placement: dict = {"mode": "wall", "host_wall": host_wall, "origin_z_mm": origin_z_mm}
    if fill:
        placement["fill"] = True
    if against is not None:
        placement["against"] = against
    item = {
        "id": item_id,
        "category": "cabinet",
        "furniture_category": "floor_cabinet",
        "depth": depth,
        "height": height,
        "placement": placement,
    }
    if width is not None:
        item["width"] = width
    return item


class AgainstEndTests(unittest.TestCase):
    def test_south_cabinet_reaches_the_corner_and_east_cabinet_stops_against_it(self) -> None:
        """东南角由南墙柜子到底。东墙柜子的南头停在它的侧面，不占这个角。

        房间 4000×3000。南柜宽 800、深 600，东头贴东墙。
        东柜宽 900、深 550，南头贴着南柜，沿墙起点是 3000−600−900。
        """
        scene = plan_scene(ROOM, [
            _cabinet("east_cab", host_wall="east", width=900, depth=550, against={"south": "south_cab"}),
            _cabinet("south_cab", host_wall="south", width=800, against={"east": "wall"}),
        ])
        south = next(item for item in scene.items if item.id == "south_cab")
        east = next(item for item in scene.items if item.id == "east_cab")
        self.assertEqual(
            (south.placement.origin_x_mm, south.placement.origin_y_mm, south.placement.rotation_z_deg),
            (4000, 3000, 180),
        )
        self.assertEqual(
            (east.placement.origin_x_mm, east.placement.origin_y_mm, east.placement.rotation_z_deg),
            (4000, 1500, 90),
        )
        source = south.to_source()["placement"]
        self.assertEqual(source["against"], {"east": "wall"})
        self.assertNotIn("origin_x_mm", source)
        self.assertEqual(east.to_source()["placement"]["against"], {"south": "south_cab"})
        again = plan_scene(ROOM, [item.to_source() for item in scene.items])
        self.assertEqual(
            next(item for item in again.items if item.id == "east_cab").placement.origin_y_mm,
            1500,
        )

    def test_an_earlier_ordinary_cabinet_does_not_take_the_claimed_corner(self) -> None:
        """普通柜子写在前面，也不会抢走已经声明贴墙的那一头。"""
        scene = plan_scene(ROOM, [
            _cabinet("desk", host_wall="south", width=600, depth=500, height=750),
            _cabinet("south_cab", host_wall="south", width=800, against={"east": "wall"}),
        ])
        south = next(item for item in scene.items if item.id == "south_cab")
        desk = next(item for item in scene.items if item.id == "desk")
        self.assertEqual(south.placement.origin_x_mm, 4000)
        self.assertEqual(desk.placement.origin_x_mm, 3200)

    def test_naming_a_cabinet_puts_this_end_against_that_cabinet(self) -> None:
        """北墙：后写的 A 在西头。B 的西头写着贴 A，所以 B 排在 A 东侧。"""
        scene = plan_scene(ROOM, [
            _cabinet("b_cab", host_wall="north", width=700, against={"west": "a_cab"}),
            _cabinet("a_cab", host_wall="north", width=800),
        ])
        placed = {item.id: item for item in scene.items}
        self.assertEqual(placed["a_cab"].placement.origin_x_mm, 0)
        self.assertEqual(placed["b_cab"].placement.origin_x_mm, 800)

    def test_floor_and_hanging_cabinets_can_claim_the_same_corner(self) -> None:
        """落地柜和吊柜高度不重叠，可以同时把东头写成贴墙。高度一重叠就拒绝。"""
        scene = plan_scene(ROOM, [
            _cabinet("base", host_wall="south", height=800, against={"east": "wall"}),
            _cabinet(
                "hang", host_wall="south", height=700, origin_z_mm=1600,
                against={"east": "wall"},
            ),
        ])
        placed = {item.id: item for item in scene.items}
        self.assertEqual(placed["base"].placement.origin_z_mm, 0)
        self.assertEqual(placed["hang"].placement.origin_z_mm, 1600)
        self.assertEqual(placed["base"].placement.origin_x_mm, 4000)
        self.assertEqual(placed["hang"].placement.origin_x_mm, 4000)
        with self.assertRaisesRegex(ValueError, "southeast corner"):
            plan_scene(ROOM, [
                _cabinet("base", host_wall="south", height=800, against={"east": "wall"}),
                _cabinet(
                    "hang", host_wall="south", height=700, origin_z_mm=400,
                    against={"east": "wall"},
                ),
            ])

    def test_one_corner_allows_only_one_cabinet_to_reach_the_wall(self) -> None:
        with self.assertRaisesRegex(ValueError, "southeast corner"):
            plan_scene(ROOM, [
                _cabinet("south_cab", host_wall="south", against={"east": "wall"}),
                _cabinet("east_cab", host_wall="east", against={"south": "wall"}),
            ])

    def test_cabinets_that_only_name_each_other_fail(self) -> None:
        with self.assertRaisesRegex(ValueError, "against cycle"):
            plan_scene(ROOM, [
                _cabinet("south_cab", host_wall="south", against={"east": "east_cab"}),
                _cabinet("east_cab", host_wall="east", against={"south": "south_cab"}),
            ])

    def test_against_only_accepts_the_two_ends_of_the_host_wall(self) -> None:
        with self.assertRaisesRegex(ValueError, "only allows east and west"):
            plan_scene(ROOM, [
                _cabinet("south_cab", host_wall="south", against={"north": "wall"}),
            ])

    def test_free_placement_rejects_against(self) -> None:
        with self.assertRaisesRegex(ValueError, "free placement cannot define against"):
            plan_scene(ROOM, [{
                "id": "sofa",
                "category": "sofa",
                "width": 800,
                "depth": 800,
                "height": 800,
                "placement": {
                    "mode": "free",
                    "origin_x_mm": 1000,
                    "origin_y_mm": 1000,
                    "against": {"east": "wall"},
                },
            }])

    def test_a_claimed_end_does_not_slide_past_an_opening(self) -> None:
        room = {
            **ROOM,
            "openings": [{
                "id": "entry",
                "kind": "door",
                "wall": "north",
                "offset_mm": 0,
                "width_mm": 900,
                "height_mm": 2100,
            }],
        }
        with self.assertRaisesRegex(ValueError, "does not fit"):
            plan_scene(room, [
                _cabinet("north_cab", host_wall="north", width=800, against={"west": "wall"}),
            ])

    def test_fill_takes_the_span_touching_the_named_end(self) -> None:
        """北墙被 1800–2000 的洞口切开。贴西头的铺满占 0–1800，不拿更长的东段。"""
        room = {
            **ROOM,
            "openings": [{
                "id": "window",
                "kind": "window",
                "wall": "north",
                "offset_mm": 1800,
                "width_mm": 200,
                "height_mm": 1200,
                "sill_height_mm": 900,
            }],
        }
        touching = plan_scene(room, [
            _cabinet(
                "run", host_wall="north", width=None, height=700,
                origin_z_mm=1400, fill=True, against={"west": "wall"},
            ),
        ])
        run = touching.items[0]
        self.assertEqual((run.placement.origin_x_mm, run.width), (0, 1800))
        east_end = plan_scene(room, [
            _cabinet(
                "run", host_wall="north", width=None, height=700,
                origin_z_mm=1400, fill=True, against={"east": "wall"},
            ),
        ])
        self.assertEqual(
            (east_end.items[0].placement.origin_x_mm, east_end.items[0].width),
            (2000, 2000),
        )
        longest = plan_scene(room, [
            _cabinet(
                "run", host_wall="north", width=None, height=700,
                origin_z_mm=1400, fill=True,
            ),
        ])
        self.assertEqual(
            (longest.items[0].placement.origin_x_mm, longest.items[0].width),
            (2000, 2000),
        )

    def test_heights_that_do_not_overlap_do_not_meet(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not meet"):
            plan_scene(ROOM, [
                _cabinet("south_cab", host_wall="south", height=800, against={"east": "wall"}),
                _cabinet(
                    "east_cab", host_wall="east", width=900, depth=550,
                    height=700, origin_z_mm=1600, against={"south": "south_cab"},
                ),
            ])

    def test_both_ends_on_the_wall_must_match_the_width(self) -> None:
        with self.assertRaisesRegex(ValueError, "width does not match"):
            plan_scene(ROOM, [
                _cabinet(
                    "south_cab", host_wall="south", width=800,
                    against={"east": "wall", "west": "wall"},
                ),
            ])

    def test_edit_keeps_against_until_the_cabinet_leaves_that_wall(self) -> None:
        scene = plan_scene(ROOM, [
            _cabinet("south_cab", host_wall="south", against={"east": "wall"}),
        ])
        source = room_scene_source(scene)
        raised = apply_edit(source, {"op": "move", "item_id": "south_cab", "origin_z_mm": 100})
        self.assertEqual(raised["items"][0]["placement"]["against"], {"east": "wall"})
        replanned = plan_scene(raised["room"], raised["items"])
        self.assertEqual(replanned.items[0].placement.origin_x_mm, 4000)

        freed = apply_edit(source, {
            "op": "move",
            "item_id": "south_cab",
            "mode": "free",
            "origin_x_mm": 500,
            "origin_y_mm": 500,
        })
        self.assertNotIn("against", freed["items"][0]["placement"])

        moved = apply_edit(source, {
            "op": "move",
            "item_id": "south_cab",
            "host_wall": "north",
        })
        self.assertNotIn("against", moved["items"][0]["placement"])

    def test_http_placement_accepts_against_ends(self) -> None:
        placement = room_http.ItemPlacementRequest.model_validate({
            "mode": "wall",
            "host_wall": "south",
            "against": {"east": "wall"},
        })
        dumped = placement.model_dump(exclude_none=True)
        self.assertEqual(dumped["against"], {"east": "wall"})
        with self.assertRaises(ValidationError):
            room_http.ItemPlacementRequest.model_validate({
                "mode": "wall",
                "host_wall": "south",
                "against": {"front": "wall"},
            })


if __name__ == "__main__":
    unittest.main()
