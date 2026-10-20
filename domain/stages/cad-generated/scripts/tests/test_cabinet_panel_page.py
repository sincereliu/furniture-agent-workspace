"""布局页进入一台柜子的板件页：不要求整份布局已确认，也不写出板件。

板件确认前只有外形；确认后画的是**已确认冻结板件**的结构——页面的数据只从
`confirmed_panel_sha256` 那份文件来，不读运行中的候选。
"""

from __future__ import annotations

import asyncio
import json
import math
import os
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
from furniture_layout.open_preview import layout_version, panel_version
from furniture_layout.project_layout import ProjectLayout
from furniture_web.room_page import render_draft_page
from furniture_panel_planning.panel_pipeline import plan_panel_stage
from furniture_panel_planning.assembly_tree import flatten_panels_for_handoff
from furniture_panel_planning.cabinet_panel_page import (
    _FACE_AXES,
    _grain_uv as grain_uv,
    panel_grain_axis as grain_axis,
    panel_structure_view,
)
from furniture_workflow.input_adapter import stage_inputs_from_spec
from furniture_workflow.project_layout_edit import (
    LAYOUT_EDIT_ENV,
    VersionConflict,
    save_cabinet_panel_edits,
)
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_store import JsonProjectStore
from panel_fixtures import cabinet_data, cabinet_envelope, panel_parameters
from furniture_orchestrator_test_support import layout_proposal

def _fixture_cabinet() -> dict:
    """独立的 800×600×900 双门柜样例，不依赖开发机的 Project Store。"""
    output = plan_panel_stage(
        [cabinet_envelope(height=900)],
        {"parameters": panel_parameters(
            shelves=[
                {"shelf_type": "fixed", "gap_below_mm": 419},
                {"shelf_type": "fixed", "gap_below_mm": 100},
            ],
            top_gap_mm=259,
        )},
    )
    return json.loads(json.dumps(output))["cabinets"][0]


def _grain_repeat_for_test(span_mm: float) -> float:
    """与 `cabinet_panel_page._grain_repeat()` 同一个夹取口径，避免测试里循环论证。"""
    return min(4.5, max(1.0, abs(span_mm) / 220.0))


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
            server.project_cabinet_panels(project.id, "wardrobe", _local())
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
            asyncio.run(server.project_cabinet_panels(project.id, "bookcase", _local()))
        self.assertEqual(kept.exception.status_code, 422)
        self.assertEqual(kept.exception.detail, "这件只占位置")

        with self.assertRaises(HTTPException) as missing:
            asyncio.run(server.project_cabinet_panels(project.id, "missing", _local()))
        self.assertEqual(missing.exception.status_code, 404)

        shared = asyncio.run(
            server.project_cabinet_panels(project.id, "wardrobe", _local(), mode="view")
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
            server.project_cabinet_panels(self.project.id, "cabinet_1", _local())
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
        # 双门由几何定铰链侧：左 left、右 right，页面据此绕竖边开门。
        self.assertEqual(panels["cabinet_1__left_door"]["hinge_side"], "left")
        self.assertEqual(panels["cabinet_1__right_door"]["hinge_side"], "right")
        self.assertEqual(panels["cabinet_1__left_side_panel"]["hinge_side"], "")
        self.assertIn('id="open"', page)
        # 全柜只有两种材料，图例就是这两条；每块板都有材料。
        self.assertEqual(
            {item["material"] for item in payload["materials"]},
            {panel["material"] for panel in payload["panels"]},
        )
        self.assertEqual(sum(item["count"] for item in payload["materials"]), len(payload["panels"]))

    def test_structure_page_carries_the_grain_direction_and_says_it_on_the_page(self) -> None:
        page = self.page()
        payload = json.loads(page.split('id="cabinet-structure" type="application/json">')[1].split("</script>")[0])
        panels = {panel["role"]: panel for panel in payload["panels"]}
        # 页面把方向数据带上来了，而且和板件类型对得上。
        self.assertEqual(panels["left_side_panel"]["grain"]["axis"], "z")
        self.assertEqual(panels["back_rail_1"]["grain"]["axis"], "none")
        # 这台柜的 fixture 没有层板，横纹就拿踢脚板核对（同样是沿宽）。
        self.assertEqual(panels["toe_kick_front"]["grain"]["axis"], "x")
        for panel in payload["panels"]:
            self.assertIn("home", panel["grain"])
            self.assertEqual(
                set(panel["grain"]["faces"]), {"px", "nx", "py", "ny", "pz", "nz"}
            )
        # 门板也带方向（材料是白色、没有那张木纹图，方向数据仍然说说它是沿高的）。
        self.assertEqual(panels["left_door"]["grain"]["axis"], "z")
        self.assertIn("顺纹沿高", page)
        self.assertIn("顺纹沿宽", page)

    def test_page_has_no_texture_appearance_controls(self) -> None:
        """页面上**不留**纹理外观那些控件（预设 / 纹路 / 粗细 / 深浅 / 底色 / 复位）。

        那些只能看效果，对下单没用；真正要改的是每块板的纹路方向。留着它们会让
        「改纹理」这件事看起来像在调样式，反而找不到该点的地方（改过一版就是这样）。
        外观现在是代码里的常量（`GRAIN_TONE` 等），不是可调项。
        """
        page = self.page()
        for marker in (
            'id="grain-toggle"',
            'id="grain-controls"',
            "data-grain-preset",
            'id="grain-tone"',
            'id="grain-lines"',
            'id="grain-width"',
            'id="grain-ink"',
            'id="grain-reset"',
            "grainControls:",
        ):
            self.assertNotIn(marker, page)
        source = (
            WORKSPACE_ROOT
            / "domain/modules/web/furniture_web/static/cabinet_structure.js"
        ).read_text(encoding="utf-8")
        for gone in ("GRAIN_PRESETS", "function setGrain", "normalizeGrain", "grainControls"):
            self.assertNotIn(gone, source)

    def test_grain_editor_is_wired_for_local_editors(self) -> None:
        """页面上要能点：保存按钮 + 「待保存」清单，都交给渲染模块。"""
        page = self.page()
        for marker in (
            'id="grain-editor"',
            'id="grain-pending"',
            'id="grain-save">保存并冻结',
            'id="grain-status"',
            "待保存的改动",
            "panelSave: {",
            "window.page = page",
        ):
            self.assertIn(marker, page)
        # 保存的是这一页所有的改动，不是顺纹专用；也没有放弃按钮。
        self.assertNotIn("grain-discard", page)
        self.assertNotIn("保存并重新冻结", page)

    def test_grain_editor_only_for_local_editors(self) -> None:
        """「保存顺纹」写的是工程：只读分享那一页不给版本号，也就不用谈保存。

        版本号是服务端渲染进去的（`panelSave.version`）——页面拿不到它就带不回
        `expected_version`，服务端也就会拒。所以"不给入口"和"不给版本"是同一件事。
        """
        shared = asyncio.run(
            server.project_cabinet_panels(self.project.id, "cabinet_1", _local(), mode="view")
        ).body.decode("utf-8")
        self.assertIn('version: ""', shared)
        self.assertIn("window.page = page", shared)
        self.assertNotIn('id="shutdown-preview"', shared)

    def test_structure_page_opens_shared_and_unknown_cabinet_is_not_frozen(self) -> None:
        shared = asyncio.run(
            server.project_cabinet_panels(self.project.id, "cabinet_1", _local(), mode="view")
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
        """还没生成板件时：结构页不出现，页面上说明还没确认。"""
        project = self.orchestrator.create_project(
            "未确认板件",
            layout_proposal(),
            stage_inputs=stage_inputs_from_spec(panel_parameters()),
        )
        self.orchestrator.confirm_layout(project)
        page = asyncio.run(
            server.project_cabinet_panels(project.id, "cabinet_1", _local())
        ).body.decode("utf-8")
        self.assertNotIn('id="cabinet-structure"', page)
        self.assertIn("板件还没确认", page)
        self.assertIn("绿面是柜门这一面", page)

    def test_candidate_panels_show_structure_draft_before_confirmation(self) -> None:
        """板件已生成候选但尚未确认：显示 3D 结构草稿供审查，但不开放顺纹保存。"""
        project = self.orchestrator.create_project(
            "待确认板件草稿",
            layout_proposal(),
            stage_inputs=stage_inputs_from_spec(panel_parameters()),
        )
        self.orchestrator.confirm_layout(project)
        self.orchestrator.run_next(project)
        page = asyncio.run(
            server.project_cabinet_panels(project.id, "cabinet_1", _local())
        ).body.decode("utf-8")
        self.assertIn("cabinet_1 · 柜体结构", page)
        self.assertIn('id="cabinet-structure"', page)
        self.assertIn("待确认板件草稿", page)
        self.assertIn('version: ""', page)
        self.assertIn("editor: null", page)

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
    """结构页的视角方向：正面必须在门那一面，左右必须和数据的 X 对得上。

    换算关系是 `世界 = (柜宽 − 柜X, 柜Z, -柜Y)`：

    - 柜体 +Y（门那一面）在世界里是 **-Z**，所以正面站 -Z、背面站 +Z。写反的时候，
      人看到的现象是「门板没画出来」——实际是镜头站到了背板后面。
    - x 那次**镜像**是必须的：站在门前看，右手系里柜体 +X 必然落在人的**左手边**，
      而数据把低 X 叫 `left_side_panel`。不镜像的话整台柜子在页面上左右反——
      左侧板画在右边，`hinge_side="left"` 的门开到右边（实测踩过）。
      镜像之后**低 X ＝ 屏幕左侧**，于是「左侧」= 从 +X 看、「右侧」= 从 -X 看。
    """

    MODULE = (
        WORKSPACE_ROOT
        / "domain/modules/web/furniture_web/static/cabinet_structure.js"
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
        # 世界 x 是镜像过的（低 X 在 +X 一侧）：左侧从 +X 看、右侧从 -X 看。
        self.assertGreater(views["left"][0], 0, "左侧要从 +X 看（世界 x 镜像过）")
        self.assertLess(views["right"][0], 0, "右侧要从 -X 看")
        # 顶视要站在上方。
        self.assertGreater(views["top"][1], 0, "顶视要站在上方")
        # 等轴要能看见门那一面。
        self.assertLess(views["iso"][2], 0, "等轴也要在门那一侧")

    def test_panel_x_is_mirrored_so_low_x_lands_on_the_screen_left(self) -> None:
        """低 X 是数据里的「左」，必须落在屏幕左侧——否则门会开反。"""
        source = self.MODULE.read_text(encoding="utf-8")
        self.assertIn("width - (px + sx / 2)", source)
        self.assertIn("new THREE.Vector3(width - x, z, -y)", source)

    def test_panels_do_not_flicker(self) -> None:
        """板件接缝面是共面的：双面渲染 + 描边线贴面 + 近平面太近，都会转起来闪。"""
        source = self.MODULE.read_text(encoding="utf-8")
        self.assertNotIn("THREE.DoubleSide", source)
        self.assertIn("polygonOffset", source)
        self.assertIn("camera.near = Math.max(1, distance / 1000)", source)

    def test_camera_distance_is_computed_from_the_frame_not_a_constant(self) -> None:
        source = self.MODULE.read_text(encoding="utf-8")
        self.assertIn("fitDistanceFor(direction, canvasAspect)", source)
        self.assertIn("Math.max(aspect, MIN_ASPECT)", source)


class StructureViewerFieldTests(unittest.TestCase):
    """渲染模块只准读投影真给了的字段。

    `panel.group` 就是反例：payload 里从来没有这个字段，而 `isFrontPanel`/`isSuppressed`
    都按它判断，于是「门板」「背板」两个开关和透视全接在 `undefined` 上——按了没反应，
    而且没有报错，看页面的人只会以为功能坏了。这类错只能靠对着投影的字段名盯住。
    """

    MODULE = StructureViewerDirectionTests.MODULE

    def source(self) -> str:
        return self.MODULE.read_text(encoding="utf-8")

    def test_viewer_does_not_read_a_group_field(self) -> None:
        source = self.source()
        # 注释里还会提到 `panel.group` 这个反例，所以只查**代码里**的读取。
        self.assertNotIn("panel.group ", source)
        self.assertNotIn("panel.group)", source)
        self.assertNotIn("panel.group === ", source)
        # 板件种类只认 `panel_type`，装配只认 `assembly`。
        self.assertIn("panel.panel_type", source)
        self.assertIn("panel.assembly", source)

    def test_grain_repeat_is_taken_from_the_panel_not_a_constant(self) -> None:
        source = self.source()
        # 旋转与重复次数都来自投影；以前是「长边 / 220」在渲染端现算的，那条已删。
        self.assertIn("panel.grain.rotation", source)
        self.assertIn("record.grainFaces[record.homeFace]", source)
        self.assertNotIn("along / 220", source)
        # 重复次数改的是那张贴图：悬停时 `material.map` 会被摘掉，不能用它当条件。
        self.assertIn("record.woodMap.repeat.fromArray", source)
        self.assertNotIn("record.material.map.repeat.fromArray", source)

    def test_wood_grain_is_drawn_along_the_texture_u_axis(self) -> None:
        """木纹画的轴：侧板是竖纹还是横纹，全看这一句。

        `px`/`nx` 面的 u 是柜体高，所以纹路必须画成「y 固定、x 一路延伸」的折线。
        写成「x 固定、y 一路延伸」看着也像竖线，但上了板件就是横纹——侧板一片横条
        （实测踩过）。画面上的方向只能靠量，代码里就靠这条钉住。
        """
        source = self.source()
        self.assertIn("context.moveTo(-10,", source)  # 从左边进画布，线沿 u 轴
        self.assertNotIn("context.moveTo(x + (Math.random() - 0.5) * 2, -10)", source)
        # 线不能太密：一个循环里最多几十道，密到 1 道/mm 就糊成一片、方向也看不出来。
        lines = int(re.search(r"const GRAIN_LINES = (\d+);", source).group(1))
        self.assertLessEqual(lines, 40)
        self.assertGreaterEqual(lines, 4)

    def test_grain_is_seeded_so_a_page_always_draws_the_same_texture(self) -> None:
        """纹理必须可复现：同一个种子画同一张图，否则两次截图对不上（调试时吃过这个亏）。"""
        source = self.source()
        self.assertIn("const random = makeRandom(GRAIN_SEED);", source)
        self.assertIn("const GRAIN_SEED = 20261016;", source)
        # 画纹理的那段里不能再出现裸的 `Math.random()`。
        paint = source.split("function paintGrain(", 1)[1].split("\n}", 1)[0]
        self.assertNotIn("Math.random", paint)

    def test_texture_appearance_is_constants_not_options(self) -> None:
        """外观是常量：没有可调项、没有预设、地址栏也不收纹理参数。"""
        source = self.source()
        for constant in (
            "const GRAIN_LINES =",
            "const GRAIN_TONE =",
            "const GRAIN_WIDTH =",
            "const GRAIN_DARK_INK =",
            "const GRAIN_LIGHT_INK =",
            "const GRAIN_DARK_SHARE =",
            "const GRAIN_JITTER =",
            "const GRAIN_SEED =",
        ):
            self.assertIn(constant, source)
        for gone in ("GRAIN_DEFAULTS", "GRAIN_PRESETS", "normalizeGrain", 'query.get("grain")'):
            self.assertNotIn(gone, source)

    def test_direction_toggle_is_vertical_or_horizontal_only(self) -> None:
        """页面只给「竖纹 / 横纹」两种说法，点一次换一次，不给四根轴让人自己认。

        判据是板件大面的**长短边**：竖纹 = 顺长边、横纹 = 顺短边。不用"它是不是柜体高"
        是因为水平放的板（顶板 / 层板 / 底板 / 踢脚）大面在水平面里，两根轴都不落在柜体高上，
        那样判对它们没有意义；而长边口径正好复现出那张默认表——侧板 580×1000、顶板 764×580、
        背板 776×926 的长边分别是高、宽、高，所以「默认 = 竖纹」对每一类板都成立。
        """
        source = self.source()
        self.assertIn("function toggleGrainDirection(panelId)", source)
        self.assertIn(
            'const next = grainDirectionOf(panel) === "vertical" ? "horizontal" : "vertical";',
            source,
        )
        self.assertIn("function grainPlaneAxes(panel)", source)
        self.assertIn("? { long: first.axis, short: second.axis }", source)
        self.assertIn('const GRAIN_DIRECTION_LABEL = { vertical: "竖纹", horizontal: "横纹" };', source)

    def test_toggling_repeatedly_keeps_working(self) -> None:
        """点第一次换过去，**再点一次要能换回来**。

        这一条是被咬过的：`applyGrainAxis` 原来会把 `panel.grain.axis` 覆盖成新值，
        于是第二次点击算出来的"下一个方向"还是同一个——现象就是"只能切一次，再点没反应"。
        修法是那个值一个字都不动，当前方向一律由 `grainAxisOf()` 决定。
        """
        source = self.source()
        apply_body = source.split("function applyGrainAxis(panel)", 1)[1].split("\n  }", 1)[0]
        self.assertNotIn("panel.grain.axis =", apply_body)
        self.assertIn("const axis = grainAxisOf(panel);", apply_body)
        # 当前方向来自「攒过的改动」，而不是板件上那个原值。
        self.assertIn(
            "return edit ? edit.axis : panel.grain.axis;",
            source.split("function grainAxisOf(panel)", 1)[1].split("\n  }", 1)[0],
        )

    def test_highlight_keeps_the_wood_texture(self) -> None:
        """选中 / 悬停**不许**把纹理摘掉——摘掉就看不见纹理方向了。

        原来 `paint()` 把 `map` 设成 `null` 并整块涂纯色，于是点一块板（正好是"翻纹理"
        那一下）看到的是纯蓝，现象就是「只有文字变了、纹理没变」。现在高亮只加自发光 +
        换描边颜色，贴图一直挂着。
        """
        source = self.source()
        paint = source.split("function paint()", 1)[1].split("\n  }", 1)[0]
        self.assertIn("record.material.map = isWhitePanel(panel) ? null : record.woodMap;", paint)
        self.assertNotIn("highlighted || isWhitePanel(panel) ? null", paint)
        self.assertIn("record.material.color.setHex(record.baseColor);", paint)
        # 高亮的三档里都别再出现 `color`（那是"整块换纯色"的老做法）。
        look = source.split("const LOOK = {", 1)[1].split("};", 1)[0]
        self.assertNotIn("color:", look)

    def test_clicking_a_panel_only_selects_it(self) -> None:
        """点板件**只选中**，绝不改数据。

        点选是最常用的动作，把"改纹理"挂在它上面太容易误伤（点着看尺寸就把订单改了）。
        改纹理只能从详情里的「顺纹方向」那一行点——那是个明确的动作。
        """
        source = self.source()
        click = source.split('canvas.addEventListener("pointerup"', 1)[1].split("});", 1)[0]
        self.assertIn("select(found ? found.panel.id : null);", click)
        self.assertNotIn("toggleGrainDirection", click)
        self.assertNotIn("grainEdits", click)

    def test_detail_row_is_what_changes_the_texture(self) -> None:
        """切换挂在详情那一行：点它，文字和纹理同时变。"""
        source = self.source()
        detail = source.split("function renderDetail(panel)", 1)[1].split("\n  }", 1)[0]
        self.assertIn("grainrow", detail)
        self.assertIn("button.addEventListener(\"click\", () => toggleGrainDirection(panel.id));", detail)
        # 只读分享那一页（没有编辑入口）不给点。
        self.assertIn("if (panelSave.editor && direction) {", detail)

    def test_save_block_is_not_grain_specific(self) -> None:
        """「保存并冻结」是这一页通用的落盘动作，不是顺纹专用，也没有放弃按钮。

        攒下的改动以后不止顺纹一种，按钮和标题都不能写死成"保存顺纹"；
        想撤销就直接再点一次切回去，不需要单独的放弃按钮。
        """
        source = self.source()
        self.assertIn("async function saveChanges()", source)
        self.assertNotIn("function discardGrain", source)
        self.assertNotIn("saveGrain", source)


class PanelGrainDirectionTests(unittest.TestCase):
    """顺纹方向：常规柜子的口径，按板件类型定，不信尺寸。

    口径是开发者给的：侧板 / 门板 / 抽面 / 背板沿高（Z）、层板 / 顶板 / 底板 / 踢脚板
    沿宽（X）、背拉条不限。这张表错了，画面上就是「层板长了一身竖纹」这种错。
    """

    EXPECTED = {
        "side": "z",
        "door": "z",
        "drawer_front": "z",
        "back": "z",
        "fixed_shelf": "x",
        "movable_shelf": "x",
        "top": "x",
        "bottom": "x",
        "toe_kick": "x",
        "back_rail": "none",
    }

    def test_rule_table_assigns_the_agreed_axis(self) -> None:
        for panel_type, axis in self.EXPECTED.items():
            self.assertEqual(
                grain_axis({"panel_type": panel_type}),
                axis,
                f"{panel_type} 的顺纹方向应是 {axis}",
            )

    def test_unknown_type_falls_back_to_the_height_axis(self) -> None:
        # 没点名的新类型：常规柜里立着的板件最多，沿高是错得最少的那一个答案。
        self.assertEqual(grain_axis({"panel_type": "something_new"}), "z")
        self.assertEqual(grain_axis({}), "z")

    def test_every_panel_of_a_real_cabinet_gets_a_known_axis(self) -> None:
        view = panel_structure_view(_fixture_cabinet())
        self.assertEqual(len(view["panels"]), 13)
        for panel in view["panels"]:
            grain = panel["grain"]
            self.assertIn(grain["axis"], {"x", "z", "none"}, panel["id"])
            # 木纹在图上沿纵向画，所以顺纹只能落在贴图的某一根轴上：不转，或者转 90°。
            self.assertIn(grain["rotation"], (0.0, math.pi / 2), panel["id"])

    def test_projection_keeps_the_rule_table_promise(self) -> None:
        """冻结的一台柜：逐块对一遍方向，顺带把「哪个面转 90°」钉住。"""
        panels = {panel["panel_type"] + "|" + panel["role"]: panel for panel in panel_structure_view(_fixture_cabinet())["panels"]}
        for key, panel in panels.items():
            axis = self.EXPECTED[panel["panel_type"]]
            grain = panel["grain"]
            self.assertEqual(grain["axis"], axis, key)
            want = {"x": 0, "y": 1, "z": 2}.get(axis)
            for face, (u, v) in _FACE_AXES.items():
                # 「面的 u 轴不是顺纹轴」时才转 90°：转完 u 才落到顺纹轴上。
                expected = math.pi / 2 if want is not None and u != want else 0.0
                self.assertEqual(grain["faces"][face]["rotation"], expected, f"{key} {face}")
                # 转 90° 时贴图横向管 v 轴，重复次数也要跟着换位。
                pair = (u, v) if expected == 0.0 else (v, u)
                self.assertEqual(
                    grain["faces"][face]["repeat"],
                    [_grain_repeat_for_test(panel["size_mm"][pair[0]]), _grain_repeat_for_test(panel["size_mm"][pair[1]])],
                    f"{key} {face}",
                )

    def test_rotation_is_decided_per_face_not_per_panel(self) -> None:
        """同一个「顺纹沿高」，在侧板大面和背板大面上要的旋转**相反**。

        这是踩了两轮的坑：用一个全局旋转值，修好侧板就坏背板、修好背板又坏侧板。
        原因是 `px`（侧板大面）的 u 是柜体高、`py`（背板大面）的 u 是柜体宽，
        所以两张面围绕 u/v 的需求正好相反。谁把这里改回「一个值管全柜」，
        下面两条断言会同时红——它们本来就是一对。
        """
        side = grain_uv("z", [18.0, 580.0, 1000.0])   # 侧板：沿高
        back = grain_uv("z", [776.0, 9.0, 926.0])     # 背板：也沿高
        self.assertEqual(side["faces"]["px"]["rotation"], 0.0)
        self.assertEqual(back["faces"]["py"]["rotation"], math.pi / 2)
        # 顺纹沿宽的板件在 pz（顶底 / 层板大面）上不转；`px` 是它的窄边，转不转都不影响观感。
        shelf = grain_uv("x", [764.0, 553.0, 18.0])
        self.assertEqual(shelf["faces"]["pz"]["rotation"], 0.0)
        # 每个面转完之后，**顺纹轴真的落在贴图横向上**——只对「顺纹轴在那张面里」的面成立。
        # 侧板的 pz 是 18mm 窄边，顺纹沿高，高根本不在这张面里，那条不变式对它没意义。
        for grain in (side, back, shelf):
            want = {"x": 0, "z": 2}[grain["axis"]]
            home = grain["home"]
            u = _FACE_AXES[home][0]
            rotated = grain["faces"][home]["rotation"] != 0.0
            self.assertEqual(
                (_FACE_AXES[home][1] if rotated else u), want,
                f"{grain['axis']} 的 {home} 面顺纹没落在贴图横向",
            )

    def test_face_axes_map_v_onto_height_or_width_never_thickness(self) -> None:
        """六个面的 (u, v) 必须落在每块板自己的「高」或「宽」上，不能落进厚度里。

        这张表错过一次：按 three.js 源码推成 `px: (z, y)`，宣称侧板的 v 沿柜体深，
        结果侧板木纹翻成横的。源码推导靠不住，**页面上量出来**的才是准的：用「一条从
        左上到右下的对角线」做贴图，看它在板件上朝哪边斜（对角线不会和它转 90° 的样子
        混淆）——量出来 `px`/`nx` 的 v 是柜体高。
        """
        self.assertEqual(_FACE_AXES["px"], (2, 1))  # u 沿高(z)，v 沿深(y)
        self.assertEqual(_FACE_AXES["nx"], (2, 1))
        self.assertEqual(_FACE_AXES["py"], (0, 2))  # u 沿宽(x)，v 沿深(z)
        self.assertEqual(_FACE_AXES["ny"], (0, 2))
        self.assertEqual(_FACE_AXES["pz"], (0, 1))  # u 沿宽(x)，v 沿高(y)
        self.assertEqual(_FACE_AXES["nz"], (0, 1))
        # 窄边（侧板 18mm 厚的端面）本来就会落到厚度上，那是几何决定的，不是缺陷；
        # 要紧的是**大面**上纹路走对轴——上面两条 + repeat 的用例已经把大面钉住了。

    def test_repeat_is_counted_along_the_axis_after_the_rotation(self) -> None:
        """转 90° 之后每根轴上铺几遍。数写死，免得循环论证。

        侧板 18×580×1000（顺纹沿高）：
        - `px`（u 就是高）不转 → `[1000/220, 580/220] = [4.5, 2.636]`；
        - `py`（u 是宽，转 90° 让 u 变高）→ `[1000/220, 18/220] = [4.5, 1.0]`。
        背板 776×9×926：`py` 转 90° → `[926/220, 776/220] = [4.209, 3.527]`。

        转 90° 的面拿的是「顺纹轴 × 另一根轴」，不是「u × v」；不转的面才是 u × v。
        这两组数只决定纹理在板上的疏密（图上画的是无方向噪声），但差太多会看出拉伸。
        """
        side = grain_uv("z", [18.0, 580.0, 1000.0])
        self.assertEqual(side["faces"]["px"]["rotation"], 0.0)
        self.assertEqual(side["faces"]["px"]["repeat"], [4.5, 2.6363636363636362])
        self.assertEqual(side["faces"]["py"]["rotation"], math.pi / 2)
        self.assertEqual(side["faces"]["py"]["repeat"], [4.5, 1.0])
        back = grain_uv("z", [776.0, 9.0, 926.0])
        self.assertEqual(back["faces"]["py"]["rotation"], math.pi / 2)
        self.assertEqual(back["faces"]["py"]["repeat"], [4.209090909090909, 3.5272727272727273])
        # 顺纹沿宽时同一个面不转：两组数按 u × v 走，跟转过的不同。
        unrotated = grain_uv("x", [776.0, 9.0, 926.0])
        self.assertEqual(unrotated["faces"]["py"]["rotation"], 0.0)
        self.assertNotEqual(
            back["faces"]["py"]["repeat"],
            unrotated["faces"]["py"]["repeat"],
        )


class PanelStructureViewTests(unittest.TestCase):
    """结构投影只搬冻结文件里的数，不重算几何，材料按角色分。"""

    def test_projection_copies_geometry_and_assigns_materials(self) -> None:
        view = panel_structure_view(_fixture_cabinet())
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


class CabinetGrainSaveTests(unittest.TestCase):
    """顺纹方向是**板件的属性**：按订单改它，然后随板件一起重新冻结。

    这里走的是真正的写路径（`save_cabinet_panel_edits` → revise → 重新确认 → 落盘），
    不是页面上的临时调整。所以要点有两个：改了真的进冻结文件；改动会按规矩作废下游。
    """

    def setUp(self) -> None:
        self.root = WORKSPACE_ROOT / "temp" / "test-cabinet-grain-save"
        if self.root.exists():
            shutil.rmtree(self.root)
        self.store = JsonProjectStore(self.root)
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT,
            project_store=self.store,
        )
        # 页面写项目默认关闭，靠灰度开关打开（和布局编辑同一个开关）。
        self._switch = mock.patch.dict(os.environ, {LAYOUT_EDIT_ENV: "1"})
        self._switch.start()
        self.addCleanup(self._switch.stop)
        # 页面读冻结文件走 server.STORE_ROOT，指到这个用例自己的临时库。
        self._store_root = mock.patch.object(server, "STORE_ROOT", self.root)
        self._store_root.start()
        self.addCleanup(self._store_root.stop)
        self.addCleanup(
            lambda: shutil.rmtree(self.root, ignore_errors=True)
            if self.root.exists()
            else None
        )
        self.project = self.orchestrator.create_project(
            "顺纹",
            layout_proposal(),
            stage_inputs=stage_inputs_from_spec(panel_parameters()),
        )
        self.orchestrator.confirm_layout(self.project)
        self.orchestrator.run_next(self.project)
        self.orchestrator.confirm_stage(self.project, "panel_plan")

    def save(self, axes: dict[str, str], **kwargs):
        return save_cabinet_panel_edits(
            self.project,
            "cabinet_1",
            axes=axes,
            expected_version=kwargs.pop("expected_version", panel_version(self.project.latest)),
            workspace_root=WORKSPACE_ROOT,
            store_root=self.root,
            **kwargs,
        )

    def frozen_panels(self) -> dict[str, dict]:
        digest = self.project.latest.confirmed_panel_sha256
        frozen = json.loads(self.store.panel_path(self.project.id, digest).read_text(encoding="utf-8"))
        return {panel["id"]: panel for panel in flatten_panels_for_handoff(frozen["cabinets"][0])}

    def test_saving_grain_rewrites_the_frozen_panels(self) -> None:
        before = self.frozen_panels()
        top = before["cabinet_1__top_panel"]
        self.assertEqual(top["grain_axis"], "x")  # 顶板默认沿宽
        old_digest = self.project.latest.confirmed_panel_sha256
        old_revision = self.project.latest.number

        result = self.save({top["id"]: "y"})

        self.assertEqual(result["panels"], [top["id"]])
        # 新修订 + 新冻结摘要：不是原地改一份已经被确认的东西。
        self.assertGreater(self.project.latest.number, old_revision)
        self.assertNotEqual(self.project.latest.confirmed_panel_sha256, old_digest)
        self.assertEqual(result["confirmed_panel_sha256"], self.project.latest.confirmed_panel_sha256)
        # 改过的板件带着新方向；没动的板件一个字没变。
        after = self.frozen_panels()
        self.assertEqual(after[top["id"]]["grain_axis"], "y")
        for panel_id, panel in before.items():
            self.assertEqual(
                {k: v for k, v in after[panel_id].items() if k != "grain_axis"},
                {k: v for k, v in panel.items() if k != "grain_axis"},
                panel_id,
            )

    def test_changed_grain_shows_up_on_the_panel_page(self) -> None:
        self.save({"cabinet_1__top_panel": "y"})
        structure, note = server.structure_for_panel_page(self.project, "cabinet_1")
        self.assertEqual(note, "")
        top = next(p for p in structure["panels"] if p["id"] == "cabinet_1__top_panel")
        self.assertEqual(top["grain"]["axis"], "y")
        # 页面要能看出这块是这个订单特意改过的（默认是 x）。
        self.assertEqual(top["grain_default"], "x")

    def test_untouched_panels_report_their_default(self) -> None:
        structure, _ = server.structure_for_panel_page(self.project, "cabinet_1")
        for panel in structure["panels"]:
            self.assertEqual(
                panel["grain"]["axis"], panel["grain_default"], panel["id"]
            )

    def test_saving_invalidates_downstream_stages(self) -> None:
        """改板件属性 = 制造 / BOM / CAD 的依据变了，它们的产物必须被作废。"""
        self.orchestrator.run_next(self.project)  # 跑出制造产物
        self.assertTrue(self.project.latest.stage_outputs)
        self.save({"cabinet_1__top_panel": "y"})
        outputs = self.project.latest.stage_outputs
        self.assertIn("panel_plan", outputs)
        self.assertNotIn("manufacture_plan", outputs)

    def test_every_rejection_leaves_the_project_untouched(self) -> None:
        """校验不过就整体拒绝，不落任何东西——和布局编辑同一条规矩。"""
        digest = self.project.latest.confirmed_panel_sha256
        revision = self.project.latest.number

        def unchanged() -> None:
            self.assertEqual(self.project.latest.confirmed_panel_sha256, digest)
            self.assertEqual(self.project.latest.number, revision)

        with self.assertRaises(ValueError) as missing_panel:
            self.save({"cabinet_1__nope": "y"})
        self.assertIn("no such panel", str(missing_panel.exception))
        unchanged()

        with self.assertRaises(ValueError) as bad_axis:
            self.save({"cabinet_1__top_panel": "w"})
        self.assertIn("grain axis", str(bad_axis.exception))
        unchanged()

        with self.assertRaises(ValueError) as missing_cabinet:
            self.save_cabinet("cabinet_missing", {"cabinet_1__top_panel": "y"})
        self.assertIn("no such cabinet", str(missing_cabinet.exception))
        unchanged()

        with self.assertRaises(ValueError) as empty:
            self.save({})
        self.assertIn("nothing to change", str(empty.exception))
        unchanged()

        with self.assertRaises(VersionConflict):
            self.save({"cabinet_1__top_panel": "y"}, expected_version="stale")
        unchanged()

    def save_cabinet(self, cabinet_id: str, axes: dict[str, str]):
        return save_cabinet_panel_edits(
            self.project,
            cabinet_id,
            axes=axes,
            expected_version=panel_version(self.project.latest),
            workspace_root=WORKSPACE_ROOT,
            store_root=self.root,
        )

    def test_version_guard_watches_the_panels_not_the_layout(self) -> None:
        """版本号必须是**板件**版本：改完顺纹之后旧版本号就该失效。

        这里用 `layout_version()` 错过一次：改的只有板件，布局摘要一个字不变，
        于是保存完版本号照旧，旧画面重放照样通过——"版本对不上就拒"这道门等于没有。
        """
        layout_before = layout_version(self.project.latest)
        panel_before = panel_version(self.project.latest)
        self.assertNotEqual(panel_before, "")

        self.save({"cabinet_1__top_panel": "y"})

        # 布局没变（这是问题的根源），板件版本必须变。
        self.assertEqual(layout_version(self.project.latest), layout_before)
        self.assertNotEqual(panel_version(self.project.latest), panel_before)
        # 拿旧版本号重放：必须被拒。
        with self.assertRaises(VersionConflict):
            self.save({"cabinet_1__top_panel": "x"}, expected_version=panel_before)
        # 拿当前版本号：正常通过。
        self.save({"cabinet_1__top_panel": "x"})


class CabinetHingeSaveTests(unittest.TestCase):
    """门板铰链侧也能从页面上改：`save_cabinet_panel_edits(hinges=…)` → 重新冻结。

    这台柜用一块**中立板**切成两个单开腔——正是"铰链侧定不下来、要人给"的形状。
    所以它冻出来的时候门板不带铰链侧（板件阶段只报警告），再由这条写路径补上。
    """

    def setUp(self) -> None:
        self.root = WORKSPACE_ROOT / "temp" / "test-cabinet-hinge-save"
        if self.root.exists():
            shutil.rmtree(self.root)
        self.store = JsonProjectStore(self.root)
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT,
            project_store=self.store,
        )
        self._switch = mock.patch.dict(os.environ, {LAYOUT_EDIT_ENV: "1"})
        self._switch.start()
        self.addCleanup(self._switch.stop)
        self._store_root = mock.patch.object(server, "STORE_ROOT", self.root)
        self._store_root.start()
        self.addCleanup(self._store_root.stop)
        self.addCleanup(
            lambda: shutil.rmtree(self.root, ignore_errors=True)
            if self.root.exists()
            else None
        )
        self.project = self.orchestrator.create_project(
            "铰链侧",
            layout_proposal(),
            stage_inputs=stage_inputs_from_spec(
                panel_parameters(dividers=[{"seam_index": 0}])
            ),
        )
        self.orchestrator.confirm_layout(self.project)
        self.orchestrator.run_next(self.project)
        self.orchestrator.confirm_stage(self.project, "panel_plan")

    def frozen_cabinet(self) -> dict:
        digest = self.project.latest.confirmed_panel_sha256
        frozen = json.loads(
            self.store.panel_path(self.project.id, digest).read_text(encoding="utf-8")
        )
        return frozen["cabinets"][0]

    def hinges(self) -> dict[str, str | None]:
        return {
            panel["role"]: panel.get("door_hinge_side")
            for panel in flatten_panels_for_handoff(self.frozen_cabinet())
            if panel["panel_type"] == "door"
        }

    def save(self, hinges: dict[str, str], **kwargs):
        return save_cabinet_panel_edits(
            self.project,
            "cabinet_1",
            hinges=hinges,
            expected_version=kwargs.pop(
                "expected_version", panel_version(self.project.latest)
            ),
            workspace_root=WORKSPACE_ROOT,
            store_root=self.root,
            **kwargs,
        )

    def test_two_single_door_cavities_start_undecided(self):
        # 中立板把双门柜切成两个单开腔：谁都没法从几何推出来。
        self.assertEqual(self.hinges(), {"left_door": None, "right_door": None})

    def test_choosing_both_hinges_refreezes_the_panels(self):
        old_digest = self.project.latest.confirmed_panel_sha256
        old_revision = self.project.latest.number

        result = self.save(
            {"cabinet_1__left_door": "left", "cabinet_1__right_door": "right"}
        )

        self.assertGreater(self.project.latest.number, old_revision)
        self.assertNotEqual(self.project.latest.confirmed_panel_sha256, old_digest)
        self.assertEqual(
            result["door_hinges"],
            {"cabinet_1__left_door": "left", "cabinet_1__right_door": "right"},
        )
        self.assertEqual(
            self.hinges(), {"left_door": "left", "right_door": "right"}
        )
        # 冻结文件里的 spec 也要跟上：门板上的值和 spec 的 door_hinges 不能各说各话。
        cabinet = self.frozen_cabinet()
        self.assertEqual(cabinet["spec"]["door_hinges"], ["left", "right"])
        self.assertEqual(
            [p.get("door_hinge_side") for p in flatten_panels_for_handoff(cabinet)
             if p["panel_type"] == "door"],
            ["left", "right"],
        )

    def test_leaving_one_undecided_is_refused(self):
        digest = self.project.latest.confirmed_panel_sha256
        with self.assertRaises(ValueError) as caught:
            self.save({"cabinet_1__left_door": "left"})
        self.assertIn("still have no hinge side", str(caught.exception))
        self.assertEqual(self.project.latest.confirmed_panel_sha256, digest)

    def test_the_endpoint_refuses_a_body_with_nothing_to_change(self):
        """空提交要在**进门处**就拒，别白跑一趟 revise。"""
        from fastapi import HTTPException

        request = server.CabinetPanelEditRequest(expected_version="v"), _local()
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(
                server.save_cabinet_panel_edits_endpoint(
                    "p", "c", *request
                )
            )
        self.assertEqual(caught.exception.status_code, 422)


def _local():
    from fake_request_support import local_request

    return local_request()


if __name__ == "__main__":
    unittest.main()
