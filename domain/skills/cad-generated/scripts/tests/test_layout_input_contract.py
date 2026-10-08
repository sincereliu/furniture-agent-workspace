"""Canonical layout requests, stored geometry, and HTTP admission behavior."""

from __future__ import annotations

import asyncio
from copy import deepcopy
import itertools
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
            _cabinet("east_cab", host_wall="east", width=900, depth=550, against={"south": {"kind": "item", "id": "south_cab"}}),
            _cabinet("south_cab", host_wall="south", width=800, against={"east": {"kind": "wall"}}),
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
        self.assertEqual(source["against"], {"east": {"kind": "wall"}})
        self.assertNotIn("origin_x_mm", source)
        self.assertEqual(
            east.to_source()["placement"]["against"],
            {"south": {"kind": "item", "id": "south_cab"}},
        )
        again = plan_scene(ROOM, [item.to_source() for item in scene.items])
        self.assertEqual(
            next(item for item in again.items if item.id == "east_cab").placement.origin_y_mm,
            1500,
        )

    def test_an_earlier_ordinary_cabinet_does_not_take_the_claimed_corner(self) -> None:
        """普通柜子写在前面，也不会抢走已经声明贴墙的那一头。"""
        scene = plan_scene(ROOM, [
            _cabinet("desk", host_wall="south", width=600, depth=500, height=750),
            _cabinet("south_cab", host_wall="south", width=800, against={"east": {"kind": "wall"}}),
        ])
        south = next(item for item in scene.items if item.id == "south_cab")
        desk = next(item for item in scene.items if item.id == "desk")
        self.assertEqual(south.placement.origin_x_mm, 4000)
        self.assertEqual(desk.placement.origin_x_mm, 3200)

    def test_naming_a_cabinet_puts_this_end_against_that_cabinet(self) -> None:
        """北墙：后写的 A 在西头。B 的西头写着贴 A，所以 B 排在 A 东侧。"""
        scene = plan_scene(ROOM, [
            _cabinet("b_cab", host_wall="north", width=700, against={"west": {"kind": "item", "id": "a_cab"}}),
            _cabinet("a_cab", host_wall="north", width=800),
        ])
        placed = {item.id: item for item in scene.items}
        self.assertEqual(placed["a_cab"].placement.origin_x_mm, 0)
        self.assertEqual(placed["b_cab"].placement.origin_x_mm, 800)

    def test_two_cabinets_cannot_share_one_item_end_at_the_same_height(self) -> None:
        """两台在同一段高度上抢同一个贴靠位时，报清是哪两台、该怎么改。

        以前这种输入要等到摆放时才以 `does not fit` 被拒——读起来像"墙不够长"，
        而真正的修法是改引用（另一台改成贴前一台，或换到目标柜的另一侧）。

        高度**不**重叠是允许的：落地柜与吊柜可以共用同一台的同一个侧面（一上一下）。
        """
        shared_end = {"west": {"kind": "item", "id": "a"}}
        with self.assertRaisesRegex(ValueError, "'b' and 'c' both stop against 'a'"):
            plan_scene(ROOM, [
                _cabinet("a", host_wall="north", against={"west": {"kind": "wall"}}),
                _cabinet("b", host_wall="north", width=600, against=shared_end),
                _cabinet("c", host_wall="north", width=600, against=shared_end),
            ])
        # 一上一下：a 是高柜，b 落地、c 吊柜，都贴 a 的东侧 → 允许，且都在 a 的东面。
        scene = plan_scene(ROOM, [
            _cabinet("a", host_wall="north", height=2400, against={"west": {"kind": "wall"}}),
            _cabinet("b", host_wall="north", width=600, height=800, against=shared_end),
            _cabinet("c", host_wall="north", width=600, height=800, origin_z_mm=1600,
                     against=shared_end),
        ])
        placed = {item.id: item for item in scene.items}
        self.assertEqual(placed["b"].placement.origin_x_mm, 800)
        self.assertEqual(placed["c"].placement.origin_x_mm, 800)
        self.assertEqual((placed["b"].placement.origin_z_mm, placed["c"].placement.origin_z_mm),
                         (0, 1600))

    def test_declared_ends_do_not_depend_on_list_order(self) -> None:
        """三台链式：清单顺序怎么打乱，声明过的位置都一模一样。

        这是"家具只能顺时针一个一个生成"的正面对照，也是那段摆放循环存在的理由：
        它得能在依赖没就绪时回头再来一轮。把循环换成"一趟 + 多等一轮"（现有两台
        用例拦不住那种退化），三台反序就会炸——这条会先红。
        """
        chain = [
            _cabinet("b", host_wall="north", width=700,
                     against={"west": {"kind": "item", "id": "a"}}),
            _cabinet("c", host_wall="north", width=600,
                     against={"west": {"kind": "item", "id": "b"}}),
            _cabinet("a", host_wall="north", width=800,
                     against={"west": {"kind": "wall"}}),
        ]

        def snapshot(items: list[dict]) -> tuple:
            scene = plan_scene(ROOM, items)
            return tuple(sorted(
                (item.id, item.width, item.placement.origin_x_mm)
                for item in scene.items
            ))

        results = {snapshot(list(order)) for order in itertools.permutations(chain)}
        self.assertEqual(len(results), 1, "声明过的柜子不该跟着清单顺序换位置")
        self.assertEqual(snapshot(chain), snapshot(chain), "同一份输入重跑也必须一样")
        placed = {item.id: item for item in plan_scene(ROOM, chain).items}
        self.assertEqual(
            (placed["a"].placement.origin_x_mm, placed["a"].width), (0, 800)
        )
        self.assertEqual(placed["b"].placement.origin_x_mm, 800, "b 紧贴 a")
        self.assertEqual(placed["c"].placement.origin_x_mm, 1500, "c 紧贴 b")

    def test_a_longer_declared_chain_ignores_list_order_too(self) -> None:
        """链更长时同样顺序无关（抽几种顺序，不做全排列）。

        完全反序那一组是"最坏情况"：要转 6 轮才摆得完。
        """
        def specs() -> dict[str, dict]:
            table: dict[str, dict] = {}
            for index in range(6):
                item_id = f"c{index + 1}"
                against = (
                    {"west": {"kind": "wall"}}
                    if index == 0
                    else {"west": {"kind": "item", "id": f"c{index}"}}
                )
                table[item_id] = _cabinet(
                    item_id, host_wall="north", width=600, against=against
                )
            return table

        table = specs()
        orders = (
            ["c1", "c2", "c3", "c4", "c5", "c6"],      # 正序
            ["c6", "c5", "c4", "c3", "c2", "c1"],      # 完全反序（最坏）
            ["c3", "c1", "c5", "c2", "c6", "c4"],      # 打乱
            ["c2", "c6", "c4", "c1", "c3", "c5"],      # 再打乱
        )
        results = {
            tuple(sorted(
                (item.id, item.placement.origin_x_mm)
                for item in plan_scene(ROOM, [table[key] for key in order]).items
            ))
            for order in orders
        }
        self.assertEqual(len(results), 1, "链更长时也必须与清单顺序无关")
        placed = {
            item.id: item.placement.origin_x_mm
            for item in plan_scene(ROOM, list(table.values())).items
        }
        self.assertEqual(
            [placed[f"c{index}"] for index in range(1, 7)],
            [0, 600, 1200, 1800, 2400, 3000],
        )

    def test_ordinary_cabinets_still_follow_the_list_order(self) -> None:
        """没写 `against` 的一头仍按清单顺序占最早空段：别把"顺序无关"推过头。

        上面两条守的是"声明过的免疫顺序"；这条守的是另一侧——普通件的既有行为。
        两条一起，才把那条界线钉住。
        """
        first = plan_scene(ROOM, [
            _cabinet("p1", host_wall="north", width=500),
            _cabinet("p2", host_wall="north", width=700),
        ])
        swapped = plan_scene(ROOM, [
            _cabinet("p2", host_wall="north", width=700),
            _cabinet("p1", host_wall="north", width=500),
        ])
        placed = {item.id: item.placement.origin_x_mm for item in first.items}
        self.assertEqual((placed["p1"], placed["p2"]), (0, 500))
        swapped_placed = {item.id: item.placement.origin_x_mm for item in swapped.items}
        self.assertEqual((swapped_placed["p2"], swapped_placed["p1"]), (0, 700))

    def test_floor_and_hanging_cabinets_can_claim_the_same_corner(self) -> None:
        """落地柜和吊柜高度不重叠，可以同时把东头写成贴墙。高度一重叠就拒绝。"""
        scene = plan_scene(ROOM, [
            _cabinet("base", host_wall="south", height=800, against={"east": {"kind": "wall"}}),
            _cabinet(
                "hang", host_wall="south", height=700, origin_z_mm=1600,
                against={"east": {"kind": "wall"}},
            ),
        ])
        placed = {item.id: item for item in scene.items}
        self.assertEqual(placed["base"].placement.origin_z_mm, 0)
        self.assertEqual(placed["hang"].placement.origin_z_mm, 1600)
        self.assertEqual(placed["base"].placement.origin_x_mm, 4000)
        self.assertEqual(placed["hang"].placement.origin_x_mm, 4000)
        with self.assertRaisesRegex(ValueError, "southeast corner"):
            plan_scene(ROOM, [
                _cabinet("base", host_wall="south", height=800, against={"east": {"kind": "wall"}}),
                _cabinet(
                    "hang", host_wall="south", height=700, origin_z_mm=400,
                    against={"east": {"kind": "wall"}},
                ),
            ])

    def test_one_corner_allows_only_one_cabinet_to_reach_the_wall(self) -> None:
        with self.assertRaisesRegex(ValueError, "southeast corner"):
            plan_scene(ROOM, [
                _cabinet("south_cab", host_wall="south", against={"east": {"kind": "wall"}}),
                _cabinet("east_cab", host_wall="east", against={"south": {"kind": "wall"}}),
            ])

    def test_cabinets_that_only_name_each_other_fail(self) -> None:
        with self.assertRaisesRegex(ValueError, "against cycle"):
            plan_scene(ROOM, [
                _cabinet("south_cab", host_wall="south", against={"east": {"kind": "item", "id": "east_cab"}}),
                _cabinet("east_cab", host_wall="east", against={"south": {"kind": "item", "id": "south_cab"}}),
            ])

    def test_against_only_accepts_the_two_ends_of_the_host_wall(self) -> None:
        with self.assertRaisesRegex(ValueError, "only allows east and west"):
            plan_scene(ROOM, [
                _cabinet("south_cab", host_wall="south", against={"north": {"kind": "wall"}}),
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
                    "against": {"east": {"kind": "wall"}},
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
                _cabinet("north_cab", host_wall="north", width=800, against={"west": {"kind": "wall"}}),
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
                origin_z_mm=1400, fill=True, against={"west": {"kind": "wall"}},
            ),
        ])
        run = touching.items[0]
        self.assertEqual((run.placement.origin_x_mm, run.width), (0, 1800))
        east_end = plan_scene(room, [
            _cabinet(
                "run", host_wall="north", width=None, height=700,
                origin_z_mm=1400, fill=True, against={"east": {"kind": "wall"}},
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
                _cabinet("south_cab", host_wall="south", height=800, against={"east": {"kind": "wall"}}),
                _cabinet(
                    "east_cab", host_wall="east", width=900, depth=550,
                    height=700, origin_z_mm=1600, against={"south": {"kind": "item", "id": "south_cab"}},
                ),
            ])

    def test_both_ends_on_the_wall_must_match_the_width(self) -> None:
        with self.assertRaisesRegex(ValueError, "width does not match"):
            plan_scene(ROOM, [
                _cabinet(
                    "south_cab", host_wall="south", width=800,
                    against={"east": {"kind": "wall"}, "west": {"kind": "wall"}},
                ),
            ])

    def test_explicit_item_named_wall_survives_storage_and_replanning(self) -> None:
        """wall 可作为家具 id，后写的目标也先摆；保存后仍贴家具而非贴墙。"""
        scene = plan_scene(ROOM, [
            _cabinet("b", host_wall="north", width=600,
                     against={"west": {"kind": "item", "id": "wall"}}),
            _cabinet("wall", host_wall="north", width=800,
                     against={"west": {"kind": "wall"}}),
        ])
        placed = {item.id: item for item in scene.items}
        self.assertEqual(placed["wall"].placement.origin_x_mm, 0)
        self.assertEqual(placed["b"].placement.origin_x_mm, 800)
        saved = scene.to_dict()
        restored = RoomScene.from_dict(saved)
        self.assertEqual(restored.to_dict(), saved)
        source = room_scene_source(restored)
        self.assertEqual(
            source["items"][0]["placement"]["against"],
            {"west": {"kind": "item", "id": "wall"}},
        )
        self.assertEqual(plan_scene(source["room"], source["items"]).to_dict(), saved)

    def test_string_targets_are_rejected_by_direct_http_and_edit_inputs(self) -> None:
        source = room_scene_source(plan_scene(ROOM, [ITEM]))
        for target in ("wall", "cabinet_b"):
            with self.subTest(target=target):
                against = {"west": target}
                placement = {"mode": "wall", "host_wall": "north", "against": against}
                with self.assertRaisesRegex(ValueError, "placement.against.west must be"):
                    plan_scene(ROOM, [{**ITEM, "placement": placement}])
                with self.assertRaises(ValidationError):
                    room_http.ItemPlacementRequest.model_validate(placement)
                edited = apply_edit(source, {
                    "op": "move", "item_id": ITEM["id"],
                    "origin_z_mm": 100, "against": against,
                })
                with self.assertRaisesRegex(ValueError, "placement.against.west must be"):
                    plan_scene(edited["room"], edited["items"])

    def test_wall_target_is_distinct_from_an_item_with_the_same_name(self) -> None:
        scene = plan_scene(ROOM, [
            _cabinet("wall", host_wall="north", width=800, height=800),
            _cabinet("b", host_wall="north", width=600, height=700,
                     origin_z_mm=1600, against={"west": {"kind": "wall"}}),
        ])
        self.assertEqual(scene.items[1].placement.origin_x_mm, 0)
        self.assertEqual(
            scene.items[1].to_source()["placement"]["against"],
            {"west": {"kind": "wall"}},
        )

    def test_saved_string_targets_are_rejected(self) -> None:
        scene = plan_scene(ROOM, [ITEM])
        layout = ProjectLayout.from_source({"rooms": [{**ROOM, "items": [ITEM]}]})
        for target in ("wall", "cabinet_b"):
            with self.subTest(target=target):
                saved_scene = scene.to_dict()
                saved_scene["items"][0]["placement"]["against"] = {"west": target}
                with self.assertRaisesRegex(ValueError, "placement.against.west must be"):
                    RoomScene.from_dict(saved_scene)
                saved_layout = layout.to_dict()
                saved_layout["rooms"][0]["items"][0]["placement"]["against"] = {"west": target}
                with self.assertRaisesRegex(ValueError, "placement.against.west must be"):
                    ProjectLayout.from_dict(saved_layout)

    def test_invalid_explicit_targets_fail_at_direct_and_http_inputs(self) -> None:
        for target in (
            {}, {"id": "a"}, {"kind": "cabinet", "id": "a"},
            {"kind": "wall", "id": "a"}, {"kind": "wall", "extra": True},
            {"kind": "item"}, {"kind": "item", "id": None},
            {"kind": "item", "id": 3}, {"kind": "item", "id": ""},
            {"kind": "item", "id": "a-b"}, {"kind": "item", "id": "a__b"},
            {"kind": "item", "id": "a", "extra": True}, False, 7, [],
        ):
            with self.subTest(target=target):
                placement = {"mode": "wall", "host_wall": "north",
                             "against": {"west": target}}
                with self.assertRaises(ValueError):
                    plan_scene(ROOM, [{**ITEM, "placement": placement}])
                with self.assertRaises(ValidationError):
                    room_http.ItemPlacementRequest.model_validate(placement)

    def test_explicit_items_reject_unknown_self_and_cyclic_references(self) -> None:
        for target, error in (("missing", "unknown item"), ("b", "names itself")):
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, error):
                plan_scene(ROOM, [
                    _cabinet("b", host_wall="north",
                             against={"west": {"kind": "item", "id": target}}),
                ])
        with self.assertRaisesRegex(ValueError, "against cycle"):
            plan_scene(ROOM, [
                _cabinet("a", host_wall="north",
                         against={"west": {"kind": "item", "id": "b"}}),
                _cabinet("b", host_wall="north",
                         against={"west": {"kind": "item", "id": "a"}}),
            ])

    def test_explicit_wall_targets_obey_corner_and_fill_rules(self) -> None:
        with self.assertRaisesRegex(ValueError, "southeast corner"):
            plan_scene(ROOM, [
                _cabinet("a", host_wall="south", against={"east": {"kind": "wall"}}),
                _cabinet("b", host_wall="east", against={"south": {"kind": "wall"}}),
            ])
        scene = plan_scene(ROOM, [
            _cabinet("b", host_wall="north", width=None, fill=True,
                     against={"west": {"kind": "item", "id": "wall"}}),
            _cabinet("wall", host_wall="north", width=800),
        ])
        fill = next(item for item in scene.items if item.id == "b")
        self.assertEqual((fill.placement.origin_x_mm, fill.width), (800, 3200))
        with self.assertRaisesRegex(ValueError, "cannot stop against a fill"):
            plan_scene(ROOM, [
                _cabinet("b", host_wall="north", width=600,
                         against={"west": {"kind": "item", "id": "wall"}}),
                _cabinet("wall", host_wall="north", width=None, fill=True),
            ])

    def test_edit_keeps_against_until_the_cabinet_leaves_that_wall(self) -> None:
        scene = plan_scene(ROOM, [
            _cabinet("south_cab", host_wall="south", against={"east": {"kind": "wall"}}),
        ])
        source = room_scene_source(scene)
        raised = apply_edit(source, {"op": "move", "item_id": "south_cab", "origin_z_mm": 100})
        self.assertEqual(raised["items"][0]["placement"]["against"], {"east": {"kind": "wall"}})
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
            "against": {"east": {"kind": "wall"}},
        })
        dumped = placement.model_dump(exclude_none=True)
        self.assertEqual(dumped["against"], {"east": {"kind": "wall"}})
        explicit = room_http.ItemPlacementRequest.model_validate({
            "mode": "wall", "host_wall": "north",
            "against": {"west": {"kind": "item", "id": "wall"},
                        "east": {"kind": "wall"}},
        })
        self.assertEqual(explicit.model_dump(exclude_none=True)["against"], {
            "west": {"kind": "item", "id": "wall"}, "east": {"kind": "wall"},
        })
        http_item = room_http.SceneItemRequest.model_validate(_cabinet(
            "b", host_wall="north", width=600,
            against={"west": {"kind": "item", "id": "wall"}},
        )).model_dump(exclude_none=True)
        scene = plan_scene(ROOM, [http_item, _cabinet("wall", host_wall="north", width=800)])
        self.assertEqual(scene.items[0].placement.origin_x_mm, 800)
        with self.assertRaises(ValidationError):
            room_http.ItemPlacementRequest.model_validate({
                "mode": "wall",
                "host_wall": "south",
                "against": {"front": {"kind": "wall"}},
            })


if __name__ == "__main__":
    unittest.main()
