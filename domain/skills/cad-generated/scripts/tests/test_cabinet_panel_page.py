"""布局页进入一台柜子的板件页：不要求整份布局已确认，也不写出板件。

板件确认前只有外形；确认后画的是**已确认冻结板件**的结构——页面的数据只从
`confirmed_panel_sha256` 那份文件来，不读运行中的候选。
"""

from __future__ import annotations

import asyncio
import json
import re
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
from furniture_layout.project_layout import ProjectLayout
from furniture_layout.room_page import render_draft_page
from furniture_panel_planning.cabinet_panel_page import panel_structure_view
from furniture_workflow.input_adapter import stage_inputs_from_spec
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_store import JsonProjectStore
from panel_fixtures import cabinet_data, panel_parameters
from furniture_orchestrator_test_support import layout_proposal


def cabinet_home() -> ProjectLayout:
    return ProjectLayout.from_source(
        {
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
                            "width": 1800,
                            "depth": 600,
                            "height": 2200,
                            "placement": {"mode": "wall", "host_wall": "north"},
                        },
                        {
                            "id": "bookcase",
                            "label": "书柜",
                            "category": "shelf",
                            "furniture_category": "floor_cabinet",
                            "manufacture": False,
                            "width": 900,
                            "depth": 350,
                            "height": 1800,
                            "placement": {"mode": "wall", "host_wall": "south"},
                        },
                    ],
                }
            ]
        }
    )


class CabinetPanelPageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = WORKSPACE_ROOT / "temp" / "test-cabinet-panel-page"
        if self.root.exists():
            shutil.rmtree(self.root)
        self.store = JsonProjectStore(self.root)
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT,
            project_store=self.store,
        )
        self._patch = mock.patch.object(server, "STORE_ROOT", self.root)
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)

    def test_unconfirmed_layout_opens_one_cabinet_and_refuses_the_other(self) -> None:
        project = self.orchestrator.create_project("家", cabinet_home())
        self.assertFalse(project.latest.layout.confirmed)
        revisions = len(project.revisions)

        page = asyncio.run(
            server.project_cabinet_panels(project.id, "wardrobe")
        ).body.decode("utf-8")
        self.assertIn("衣柜 · 板件", page)
        self.assertIn("1800 mm", page)
        self.assertIn("600 mm", page)
        self.assertIn("2200 mm", page)
        self.assertIn("回布局", page)
        self.assertIn("绿面是柜门这一面", page)
        self.assertIn("/vendor/three/0.186.0/three.module.js", page)
        self.assertIn('new EventSource("/api/preview/presence/stream")', page)
        self.assertNotIn('fetch("/api/preview/presence"', page)
        self.assertIn(f"room=bedroom", page)
        self.assertIn("item=wardrobe", page)
        self.assertNotIn("审查清单", page)
        self.assertEqual(len(self.store.load(project.id).revisions), revisions)
        self.assertFalse(self.store.load(project.id).latest.layout.confirmed)

        preview = asyncio.run(server.project_preview(project.id, _local())).body.decode("utf-8")
        self.assertIn(f'/api/project/{project.id}/cabinets', preview)
        self.assertIn("板件规划", preview)
        self.assertIn("这件只占位置", preview)
        self.assertIn("先保存外形", preview)

        draft = render_draft_page("draft", project.latest.layout.rooms[0])["html"]
        self.assertIn('const PANEL_URL_BASE="";', draft)

        with self.assertRaises(HTTPException) as kept:
            asyncio.run(server.project_cabinet_panels(project.id, "bookcase"))
        self.assertEqual(kept.exception.status_code, 422)
        self.assertEqual(kept.exception.detail, "这件只占位置")

        with self.assertRaises(HTTPException) as missing:
            asyncio.run(server.project_cabinet_panels(project.id, "missing"))
        self.assertEqual(missing.exception.status_code, 404)

        shared = asyncio.run(
            server.project_cabinet_panels(project.id, "wardrobe", mode="view")
        ).body.decode("utf-8")
        self.assertNotIn('id="shutdown-preview"', shared)
        self.assertIn("mode=view", shared)


class CabinetStructurePageTests(unittest.TestCase):
    """布局确认、板件确认之后，板件页画的是冻结板件的结构。"""

    def setUp(self) -> None:
        self.root = WORKSPACE_ROOT / "temp" / "test-cabinet-structure-page"
        if self.root.exists():
            shutil.rmtree(self.root)
        self.store = JsonProjectStore(self.root)
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT,
            project_store=self.store,
        )
        self._patch = mock.patch.object(server, "STORE_ROOT", self.root)
        self._patch.start()
        self.addCleanup(self._patch.stop)
        self.addCleanup(
            lambda: shutil.rmtree(self.root, ignore_errors=True)
            if self.root.exists()
            else None
        )
        self.project = self.orchestrator.create_project(
            "结构页",
            layout_proposal(),
            stage_inputs=stage_inputs_from_spec(panel_parameters()),
        )
        self.orchestrator.confirm_layout(self.project)
        self.orchestrator.run_next(self.project)
        self.orchestrator.confirm_stage(self.project, "panel_plan")

    def page(self) -> str:
        return asyncio.run(
            server.project_cabinet_panels(self.project.id, "cabinet_1")
        ).body.decode("utf-8")

    def test_confirmed_panels_drive_a_structure_page(self) -> None:
        digest = self.project.latest.confirmed_panel_sha256
        self.assertIsNotNone(digest)
        self.assertTrue(self.store.panel_path(self.project.id, digest).is_file())

        page = self.page()
        self.assertIn("cabinet_1 · 柜体结构", page)
        self.assertIn("/layout-view/cabinet_structure.js", page)
        self.assertIn('id="cabinet-structure"', page)
        # 结构页不再退回外形盒子：盒视图那两句只属于未确认状态。
        self.assertNotIn("绿面是柜门这一面", page)
        self.assertNotIn("画在这个盒子上", page)

        payload = json.loads(page.split('id="cabinet-structure" type="application/json">')[1].split("</script>")[0])
        self.assertEqual(payload["envelope_mm"], {"width": 800.0, "depth": 600.0, "height": 1000.0})
        panels = {panel["id"]: panel for panel in payload["panels"]}
        self.assertIn("cabinet_1__left_side_panel", panels)
        self.assertIn("cabinet_1__left_door", panels)
        side = panels["cabinet_1__left_side_panel"]
        self.assertEqual(side["role"], "left_side_panel")
        self.assertEqual(side["assembly"], "carcass")
        self.assertEqual(side["material"], "wood")
        self.assertEqual(panels["cabinet_1__left_door"]["material"], "white")
        self.assertEqual(payload["n_doors"], 2)
        # 全柜只有两种材料，图例就是这两条；每块板都有材料。
        self.assertEqual(
            {item["material"] for item in payload["materials"]},
            {panel["material"] for panel in payload["panels"]},
        )
        self.assertEqual(sum(item["count"] for item in payload["materials"]), len(payload["panels"]))

    def test_structure_page_opens_shared_and_unknown_cabinet_is_not_frozen(self) -> None:
        shared = asyncio.run(
            server.project_cabinet_panels(self.project.id, "cabinet_1", mode="view")
        ).body.decode("utf-8")
        self.assertNotIn('id="shutdown-preview"', shared)
        self.assertIn("mode=view", shared)
        self.assertIn("cabinet_1 · 柜体结构", shared)

        # 布局改过、板件还没重跑：冻结文件里没有这台柜，页面回到外形并说明原因。
        project = self.store.load(self.project.id)
        structure, note = server.structure_for_panel_page(project, "cabinet_missing")
        self.assertIsNone(structure)
        self.assertIn("冻结板件里没有这台柜", note)
        with self.assertRaises(LookupError):
            server.confirmed_panel_structure(project, "cabinet_missing", store=self.store)

    def test_unconfirmed_panels_show_only_the_envelope_and_say_so(self) -> None:
        """板件阶段没确认过：结构页不出现，页面上说明还没确认。"""
        project = self.orchestrator.create_project(
            "未确认板件",
            layout_proposal(),
            stage_inputs=stage_inputs_from_spec(panel_parameters()),
        )
        self.orchestrator.confirm_layout(project)
        page = asyncio.run(
            server.project_cabinet_panels(project.id, "cabinet_1")
        ).body.decode("utf-8")
        self.assertNotIn('id="cabinet-structure"', page)
        self.assertIn("板件还没确认", page)
        self.assertIn("绿面是柜门这一面", page)

    def test_missing_frozen_file_says_the_panels_cannot_be_read(self) -> None:
        """已确认但冻结文件丢了：不装作"还没确认"，页面上直说读不出来。"""
        project = self.store.load(self.project.id)
        with mock.patch.object(
            JsonProjectStore,
            "panel_path",
            return_value=self.root / "panels" / "missing.json",
        ):
            structure, note = server.structure_for_panel_page(project, "cabinet_1")
        self.assertIsNone(structure)
        self.assertIn("读不出来", note)


class StructureViewerDirectionTests(unittest.TestCase):
    """结构页的视角方向：正面必须在门那一面。

    换算关系是 `世界 = (柜X, 柜Z, -柜Y)`，所以柜体 +Y（门那一面）在世界里是 **-Z**。
    这两句话写反的时候，人看到的现象是「门板没画出来」——实际是镜头站到了背板后面。
    """

    MODULE = (
        WORKSPACE_ROOT
        / "domain/skills/layout-plan/scripts/furniture_layout/static/cabinet_structure.js"
    )

    def views(self) -> dict[str, list[float]]:
        source = self.MODULE.read_text(encoding="utf-8")
        block = source.split("const VIEWS = {", 1)[1].split("};", 1)[0]
        views: dict[str, list[float]] = {}
        for line in block.splitlines():
            if ":" not in line or "[" not in line:
                continue
            name, _, raw = line.partition(":")
            values = re.findall(r"-?\d+(?:\.\d+)?", raw)
            if len(values) == 3:
                views[name.strip()] = [float(value) for value in values]
        return views

    def test_front_stands_where_the_doors_are_and_back_is_the_other_side(self) -> None:
        views = self.views()
        self.assertEqual(
            set(views), {"iso", "front", "back", "left", "right", "top"}
        )
        # 世界 Z 越大越靠背板那一侧：正面必须取 -Z，背面必须取 +Z。
        self.assertLess(views["front"][2], 0, "正面要站在世界 -Z（门那一侧）")
        self.assertGreater(views["back"][2], 0, "背面要站在世界 +Z")
        # 站在门前看，柜体 +X 在人右手边：左侧从 -X 看、右侧从 +X 看。
        self.assertLess(views["left"][0], 0, "左侧要从 -X 看")
        self.assertGreater(views["right"][0], 0, "右侧要从 +X 看")
        # 顶视要站在上方。
        self.assertGreater(views["top"][1], 0, "顶视要站在上方")
        # 等轴要能看见门那一面。
        self.assertLess(views["iso"][2], 0, "等轴也要在门那一侧")

    def test_camera_distance_is_computed_from_the_frame_not_a_constant(self) -> None:
        source = self.MODULE.read_text(encoding="utf-8")
        self.assertIn("fitDistanceFor(direction, canvasAspect)", source)
        self.assertIn("Math.max(aspect, MIN_ASPECT)", source)


class PanelStructureViewTests(unittest.TestCase):
    """结构投影只搬冻结文件里的数，不重算几何，材料按角色分。"""

    def test_projection_copies_geometry_and_assigns_materials(self) -> None:
        frozen = json.loads(
            (
                WORKSPACE_ROOT
                / "store"
                / "project_a3731afe65d34a3faa78d21799ecccf7"
                / "panels"
                / "3cf7428c9be3ab60890cb064a4aba7aa00ed85456c0546292f54cb1074c649d0.json"
            ).read_text(encoding="utf-8")
        )
        view = panel_structure_view(frozen["cabinets"][0])
        self.assertEqual(view["cabinet_id"], "cabinet_1")
        self.assertEqual(view["envelope_mm"]["width"], 800.0)
        panels = {panel["role"]: panel for panel in view["panels"]}
        self.assertEqual(panels["left_side_panel"]["size_mm"], [18.0, 580.0, 900.0])
        self.assertEqual(panels["left_side_panel"]["pos_mm"], [0.0, 0.0, 0.0])
        # 两种材料：门与抽屉前脸白色，其余柜体木纹。
        self.assertEqual(panels["left_door"]["material"], "white")
        self.assertEqual(panels["right_door"]["material"], "white")
        for role in (
            "left_side_panel",
            "top_panel",
            "bottom_panel",
            "back_panel",
            "back_rail_1",
            "shelf_z614",
            "toe_kick_front",
        ):
            self.assertEqual(panels[role]["material"], "wood", role)
        self.assertEqual(
            {item["material"] for item in view["materials"]},
            {"wood", "white"},
        )


def _local():
    from fake_request_support import local_request

    return local_request()


if __name__ == "__main__":
    unittest.main()
