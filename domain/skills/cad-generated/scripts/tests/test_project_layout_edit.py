"""页面写项目布局（P3）：`POST /api/project/{id}/layout/edit` 的契约。

盯四件事：
1. 成功 = **新 Revision + 未确认布局**，位置真的落进 store（不是只改了内存）。
2. 版本对不上 / 几何不通过 / op 不合法 → 整体拒绝，一个 Revision 都不留。
3. 门：本机来源（`may_edit`）+ 灰度开关，任何一道不过都不落盘。
4. op 词表来自 `scene_edit`，这里不再写第二份白名单。
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

from fastapi import HTTPException

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

import server
from fake_request_support import local_request, remote_request
from furniture_layout.project_edit import apply_layout_edit
from furniture_layout.project_layout import ProjectLayout
from furniture_workflow import project_layout_edit as layout_edit
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_store import JsonProjectStore

PANEL_INPUT = {
    "panels": {
        "parameters": {"n_doors": 2, "shelves": [{"height_mm": 900}]},
    },
    "manufacturing": {"parameters": {"edge_banding": "abs"}},
}


def layout_source(
    *,
    wardrobe_origin: tuple[float, float] = (200.0, 200.0),
    fill: bool = False,
) -> dict:
    wardrobe_placement: dict = {
        "mode": "free",
        "origin_x_mm": wardrobe_origin[0],
        "origin_y_mm": wardrobe_origin[1],
        "rotation_z_deg": 0,
    }
    if fill:
        wardrobe_placement = {
            "mode": "wall",
            "host_wall": "north",
            "offset_mm": 0,
            "fill": True,
        }
    return {
        "rooms": [
            {
                "id": "bedroom",
                "name": "卧室",
                "width_mm": 4000,
                "depth_mm": 3600,
                "height_mm": 2800,
                "items": [
                    {
                        "id": "wardrobe",
                        "label": "衣柜",
                        "category": "wardrobe",
                        "furniture_category": "floor_cabinet",
                        "depth": 600,
                        "height": 2200,
                        "placement": wardrobe_placement,
                        **({} if fill else {"width": 1800.0}),
                    },
                    {
                        "id": "desk",
                        "label": "书桌",
                        "category": "desk",
                        "furniture_category": "floor_cabinet",
                        "width": 1200,
                        "depth": 600,
                        "height": 750,
                        "placement": {
                            "mode": "free",
                            "origin_x_mm": 2600,
                            "origin_y_mm": 2600,
                            "rotation_z_deg": 0,
                        },
                    },
                ],
            },
            {
                "id": "living",
                "name": "客厅",
                "width_mm": 5000,
                "depth_mm": 4000,
                "height_mm": 2800,
                "items": [
                    {
                        "id": "bookshelf",
                        "label": "书柜",
                        "category": "bookshelf",
                        "furniture_category": "floor_cabinet",
                        "width": 900,
                        "depth": 350,
                        "height": 2000,
                        "placement": {
                            "mode": "free",
                            "origin_x_mm": 300,
                            "origin_y_mm": 300,
                            "rotation_z_deg": 0,
                        },
                    }
                ],
            },
        ]
    }


class ProjectLayoutEditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = WORKSPACE_ROOT / "temp" / "test-project-layout-edit"
        if self.root.exists():
            shutil.rmtree(self.root)
        self.store = JsonProjectStore(self.root)
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT,
            project_store=self.store,
        )
        self._store_patch = mock.patch.object(server, "STORE_ROOT", self.root)
        self._store_patch.start()
        self.addCleanup(self._store_patch.stop)
        self._switch = mock.patch.dict(os.environ, {layout_edit.LAYOUT_EDIT_ENV: "1"})
        self._switch.start()
        self.addCleanup(self._switch.stop)
        self.addCleanup(lambda: shutil.rmtree(self.root, ignore_errors=True))

    # ---- 工具 ----

    def _project(self, **kwargs):
        layout = ProjectLayout.from_source(layout_source(**kwargs))
        return self.orchestrator.create_project(
            "家", layout, stage_inputs=json.loads(json.dumps(PANEL_INPUT))
        )

    def _document(self, project_id: str) -> dict:
        return asyncio.run(server.project_layout(project_id))

    def _edit(self, project_id: str, request, **payload):
        body = server.ProjectLayoutEditRequest(**payload)
        return asyncio.run(
            server.edit_project_layout_endpoint(project_id, body, request)
        )

    def _item(self, document: dict, room_id: str, item_id: str) -> dict:
        room = next(room for room in document["rooms"] if room["id"] == room_id)
        return next(item for item in room["scene"]["items"] if item["id"] == item_id)

    # ---- 成功路径 ----

    def test_move_lands_as_a_new_unconfirmed_revision(self) -> None:
        project = self._project()
        before = self._document(project.id)

        after = self._edit(
            project.id,
            local_request(),
            op="move",
            item_id="wardrobe",
            origin_x_mm=600,
            origin_y_mm=400,
            expected_version=before["version"],
        )

        self.assertEqual(after["revision_number"], 2)
        self.assertNotEqual(after["version"], before["version"])
        self.assertFalse(after["layout_confirmed"])
        moved = self._item(after, "bedroom", "wardrobe")["placement"]
        self.assertEqual((moved["origin_x_mm"], moved["origin_y_mm"]), (600, 400))
        # 别的房间与别的件一个字都没动。
        self.assertEqual(
            self._item(after, "bedroom", "desk")["placement"]["origin_x_mm"], 2600
        )
        self.assertEqual(
            self._item(after, "living", "bookshelf")["placement"]["origin_x_mm"], 300
        )
        # 真落进 store 了：换一个 store 实例从磁盘读回来还是新位置。
        reloaded = self._document(project.id)
        self.assertEqual(reloaded["revision_number"], 2)
        self.assertEqual(
            self._item(reloaded, "bedroom", "wardrobe")["placement"]["origin_x_mm"], 600
        )

    def test_new_revision_keeps_the_cabinet_stage_inputs(self) -> None:
        """摆放变了，柜体参数没变：新 Revision 必须带走 stage_inputs。

        否则下一次 `run_next()` 会报 "panel proposal is incomplete"（backlog 已知缺口 1）。
        """
        project = self._project()
        before = self._document(project.id)
        self._edit(
            project.id,
            local_request(),
            op="move",
            item_id="desk",
            origin_x_mm=2400,
            origin_y_mm=1000,
            expected_version=before["version"],
        )
        stored = self.store.load(project.id)
        self.assertEqual(stored.latest.number, 2)
        self.assertEqual(stored.latest.stage_inputs, PANEL_INPUT)

    def test_edit_never_inherits_the_confirmed_flag(self) -> None:
        """确认过的布局被改过之后必须重新确认：新布局不能继承那个确认位。"""
        project = self._project()
        self.orchestrator.confirm_stage(project, "layout_plan")
        confirmed = self._document(project.id)
        self.assertTrue(confirmed["layout_confirmed"])

        after = self._edit(
            project.id,
            local_request(),
            op="resize",
            item_id="wardrobe",
            width=2000,
            expected_version=confirmed["version"],
        )
        self.assertEqual(after["revision_number"], 2)
        self.assertFalse(after["layout_confirmed"])
        self.assertEqual(self._item(after, "bedroom", "wardrobe")["width"], 2000)
        # 未确认的布局不写冻结文件：不能伪造一份"已确认"的布局。
        frozen = list((self.root / project.id / "layouts").glob("*.json"))
        self.assertEqual(len(frozen), 1)
        self.assertNotIn(
            stored_layout_digest(frozen[0]),
            [after["version"].split(":")[0]],
        )

    def test_rotate_switches_a_wall_item_to_free_in_one_op(self) -> None:
        """墙摆的朝向由墙派生，转不动；一次 op 里改成自由摆放并给出坐标即可。"""
        project = self._project()
        before = self._document(project.id)
        after = self._edit(
            project.id,
            local_request(),
            op="rotate",
            item_id="desk",
            rotation_z_deg=90,
            mode="free",
            origin_x_mm=2400,
            origin_y_mm=1000,
            expected_version=before["version"],
        )
        placement = self._item(after, "bedroom", "desk")["placement"]
        self.assertEqual(placement["rotation_z_deg"], 90)

    # ---- 拒绝路径：任何一条都不许留 Revision ----

    def test_stale_version_is_refused_and_nothing_is_written(self) -> None:
        project = self._project()
        before = self._document(project.id)
        with self.assertRaises(HTTPException) as ctx:
            self._edit(
                project.id,
                local_request(),
                op="move",
                item_id="wardrobe",
                origin_x_mm=600,
                expected_version="0" * 64 + ":0",
            )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail["current_version"], before["version"])
        self.assertEqual(self._document(project.id)["revision_number"], 1)

    def test_geometry_failure_is_refused_and_nothing_is_written(self) -> None:
        project = self._project()
        before = self._document(project.id)
        with self.assertRaises(HTTPException) as ctx:
            self._edit(
                project.id,
                local_request(),
                op="move",
                item_id="wardrobe",
                origin_x_mm=3900,  # 1800 宽的柜子放到 x=3900：出房间
                expected_version=before["version"],
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("inside the room", str(ctx.exception.detail))
        self.assertEqual(self._document(project.id)["revision_number"], 1)

    def test_unknown_item_is_refused(self) -> None:
        project = self._project()
        before = self._document(project.id)
        with self.assertRaises(HTTPException) as ctx:
            self._edit(
                project.id,
                local_request(),
                op="move",
                item_id="sofa",
                origin_x_mm=100,
                expected_version=before["version"],
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("unknown item", str(ctx.exception.detail))

    def test_op_whitelist_comes_from_scene_edit(self) -> None:
        """字段白名单只有 scene_edit 一份：这里不该出现第二套判断。"""
        project = self._project()
        before = self._document(project.id)
        with self.assertRaises(HTTPException) as ctx:
            self._edit(
                project.id,
                local_request(),
                op="move",
                item_id="wardrobe",
                origin_x_mm=600,
                rotation_z_deg=90,
                expected_version=before["version"],
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("move does not support: rotation_z_deg", str(ctx.exception.detail))

    def test_fill_item_refuses_placement_edits(self) -> None:
        """fill 件的宽与偏移由墙上的空段算出来，改它会被重算覆盖——直接说不行。"""
        project = self._project(fill=True)
        before = self._document(project.id)
        with self.assertRaises(HTTPException) as ctx:
            self._edit(
                project.id,
                local_request(),
                op="move",
                item_id="wardrobe",
                offset_mm=500,
                expected_version=before["version"],
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("fill unit", str(ctx.exception.detail))
        self.assertEqual(self._document(project.id)["revision_number"], 1)

    # ---- 门：本机来源 + 灰度开关 ----

    def test_remote_caller_is_refused_before_anything_else(self) -> None:
        project = self._project()
        before = self._document(project.id)
        with self.assertRaises(HTTPException) as ctx:
            self._edit(
                project.id,
                remote_request(),
                op="move",
                item_id="wardrobe",
                origin_x_mm=600,
                expected_version=before["version"],
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(self._document(project.id)["revision_number"], 1)

    def test_gray_switch_off_refuses_even_a_local_edit(self) -> None:
        project = self._project()
        before = self._document(project.id)
        with mock.patch.dict(os.environ, {layout_edit.LAYOUT_EDIT_ENV: ""}):
            with self.assertRaises(HTTPException) as ctx:
                self._edit(
                    project.id,
                    local_request(),
                    op="move",
                    item_id="wardrobe",
                    origin_x_mm=600,
                    expected_version=before["version"],
                )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn(layout_edit.LAYOUT_EDIT_ENV, str(ctx.exception.detail))
        self.assertEqual(self._document(project.id)["revision_number"], 1)

    def test_switch_accepts_only_the_exact_value(self) -> None:
        for value in ("", "0", "true", "yes", "TRUE"):
            with mock.patch.dict(os.environ, {layout_edit.LAYOUT_EDIT_ENV: value}):
                self.assertFalse(layout_edit.layout_edit_enabled(), value)
        with mock.patch.dict(os.environ, {layout_edit.LAYOUT_EDIT_ENV: "1"}):
            self.assertTrue(layout_edit.layout_edit_enabled())

    # ---- 纯函数那一层 ----

    def test_apply_layout_edit_does_not_touch_the_input_layout(self) -> None:
        layout = ProjectLayout.from_source(layout_source())
        edited = apply_layout_edit(
            layout, {"op": "move", "item_id": "wardrobe", "origin_x_mm": 900}
        )
        self.assertIsNot(edited, layout)
        original = layout.rooms[0].items[0].placement
        self.assertEqual((original.origin_x_mm, original.origin_y_mm), (200, 200))
        self.assertEqual(edited.rooms[0].items[0].placement.origin_x_mm, 900)
        self.assertFalse(edited.confirmed)

    def test_replanned_scene_has_no_stale_derived_geometry(self) -> None:
        """改完重算：footprint 与净距必须跟着走，不能留下上一版的派生值。"""
        layout = ProjectLayout.from_source(layout_source())
        edited = apply_layout_edit(
            layout, {"op": "move", "item_id": "wardrobe", "origin_x_mm": 900}
        )
        item = next(
            item for item in edited.rooms[0].items if item.id == "wardrobe"
        )
        xs = [x for x, _ in item.footprint]
        self.assertEqual(min(xs), 900)
        self.assertEqual(item.clearances_mm["west"], 900)


def stored_layout_digest(path: Path) -> str:
    from furniture_workflow.workflow_digest import stable_digest

    return stable_digest(json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
