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

    def test_http_fill_expands_and_keeps_manufacturing_flags(self) -> None:
        """铺满走 HTTP：窄墙落成一台合规单元，`manufacture: false` 照样带过去。

        而且**没写柜类就停问**——铺满也要按目录展开，代码不替它猜柜类。
        """
        item = deepcopy(ITEM)
        del item["width"]
        item["placement"]["fill"] = True
        item["manufacture"] = False
        narrow = {**ROOM, "width_mm": 900}
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(
                room_http.plan_room(room_http.RoomSceneRequest(room=narrow, items=[item]))
            )
        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn("没说要做什么柜", str(caught.exception.detail))
        item["kind"] = "wardrobe"
        response = asyncio.run(
            room_http.plan_room(room_http.RoomSceneRequest(room=narrow, items=[item]))
        )
        # 墙长 900、件从 100 起铺满 → 空段 800 → 净宽 800 − 收口 60 = 740。
        self.assertEqual(response.items[0]["id"], "cabinet_u1")
        self.assertEqual(response.items[0]["width"], 740)
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


if __name__ == "__main__":
    unittest.main()
