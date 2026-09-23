"""修订继承（待办第 1 项的落地）：判据、逐字节不变式、承认与留痕。

设计稿：`references/revision-inheritance-design.md`。三组测试：

1. **判据**（`envelope_set` / `envelope_diff`）：下游读到的五个字段变了没有，以及变在哪。
2. **逐字节不变式**（设计稿「边界 2」，最大风险是隐藏依赖）：改摆放/改房间 → 板件与制造
   输出哈希**必须不变**；改柜宽/柜类/柜数 → **必变**；改房间 → `fill` 件的宽度必变。
3. **承认与留痕**（R1/R2）：内容没变时新 Revision 直接沿用上一版的确认，并留下回指。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_layout.project_layout import ProjectLayout
from furniture_workflow.input_adapter import stage_inputs_from_spec
from furniture_workflow.workflow_digest import stable_digest
from furniture_workflow.workflow_inheritance import envelope_diff, envelope_set
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_state import WorkflowStage
from panel_fixtures import panel_parameters


def studio_layout(
    *,
    offset_mm: float = 0.0,
    width: float = 800.0,
    depth: float = 600.0,
    height: float = 1000.0,
    furniture_category: str = "floor_cabinet",
    room_width_mm: float = 4000.0,
    room_depth_mm: float = 3000.0,
    fill: bool = False,
    extra_items: list[dict] | None = None,
) -> ProjectLayout:
    """工作室房间 + 一个柜子：位置、房间尺寸、尺寸、类别都能单独动。"""
    item: dict = {
        "id": "cabinet_1",
        "label": "cabinet_1",
        "category": "wardrobe",
        "furniture_category": furniture_category,
        "depth": depth,
        "height": height,
        "placement": {
            "mode": "wall",
            "host_wall": "north",
            "offset_mm": offset_mm,
            "origin_z_mm": 2000.0 if furniture_category == "wall_cabinet" else 0.0,
        },
    }
    if fill:
        item["placement"]["fill"] = True
    else:
        item["width"] = width
    return ProjectLayout.from_source(
        {
            "rooms": [
                {
                    "id": "room",
                    "name": "房间",
                    "width_mm": room_width_mm,
                    "depth_mm": room_depth_mm,
                    "height_mm": 3200.0,
                    "items": [item, *(extra_items or [])],
                }
            ]
        }
    )


def second_cabinet(**overrides) -> dict:
    item = {
        "id": "cabinet_2",
        "label": "cabinet_2",
        "category": "wardrobe",
        "furniture_category": "floor_cabinet",
        "width": 600.0,
        "depth": 400.0,
        "height": 900.0,
        "placement": {
            "mode": "wall",
            "host_wall": "north",
            "offset_mm": 2000.0,
            "origin_z_mm": 0.0,
        },
    }
    item.update(overrides)
    return item


class EnvelopeJudgeTests(unittest.TestCase):
    """判据本身：只看下游真正读到的那五个字段。"""

    def test_placement_and_room_changes_do_not_change_the_envelope_set(self) -> None:
        base = studio_layout()
        moved = studio_layout(offset_mm=1400)
        bigger_room = studio_layout(room_width_mm=5200, room_depth_mm=4200)
        for other in (moved, bigger_room):
            diff = envelope_diff(base, other)
            self.assertTrue(diff["same"], diff)
            self.assertEqual(diff["changed"], [])
        self.assertEqual(envelope_set(base), envelope_set(moved))

    def test_size_category_and_count_changes_are_classified(self) -> None:
        base = studio_layout()
        self.assertEqual(envelope_diff(base, studio_layout(width=900))["resized"], ["cabinet_1"])
        self.assertEqual(
            envelope_diff(base, studio_layout(furniture_category="wall_cabinet"))[
                "recategorized"
            ],
            ["cabinet_1"],
        )
        added = envelope_diff(base, studio_layout(extra_items=[second_cabinet()]))
        self.assertEqual(added["added"], ["cabinet_2"])
        removed = envelope_diff(studio_layout(extra_items=[second_cabinet()]), base)
        self.assertEqual(removed["removed"], ["cabinet_2"])
        for diff in (added, removed):
            self.assertFalse(diff["same"])
            self.assertIn("cabinet_2", diff["changed"])

    def test_fill_item_width_follows_the_room(self) -> None:
        """设计稿的 `fill` 例外：房间一变，fill 件的宽度必变，判据必须说"变了"。

        注意跟的是**所在墙的长度**：北墙的长度就是房间的总宽。
        """
        narrow = studio_layout(fill=True, room_width_mm=4000)
        wide = studio_layout(fill=True, room_width_mm=5200)
        diff = envelope_diff(narrow, wide)
        self.assertFalse(diff["same"])
        self.assertEqual(diff["resized"], ["cabinet_1"])
        self.assertEqual(envelope_set(narrow)["cabinet_1"][1], 4000.0)
        self.assertEqual(envelope_set(wide)["cabinet_1"][1], 5200.0)


class ByteEqualityTests(unittest.TestCase):
    """边界 2：判据说"没变"，产物就必须逐字节没变；说"变了"，就必须真变。"""

    def setUp(self) -> None:
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT, project_store=None
        )

    def _panel_output(self, layout: ProjectLayout, **panel_overrides) -> dict:
        project = self.orchestrator.create_project(
            "不变式",
            layout,
            stage_inputs=stage_inputs_from_spec(panel_parameters(**panel_overrides)),
        )
        self.orchestrator.confirm_layout(project)
        self.orchestrator.run_next(project)
        output = project.latest.stage_outputs.get(WorkflowStage.PANELS_PLANNED.value)
        self.assertIsNotNone(output, "panel stage did not produce output")
        return output

    def test_placement_and_room_changes_keep_panel_output_identical(self) -> None:
        base = self._panel_output(studio_layout())
        self.assertEqual(
            stable_digest(self._panel_output(studio_layout(offset_mm=1400))),
            stable_digest(base),
        )
        self.assertEqual(
            stable_digest(
                self._panel_output(studio_layout(room_width_mm=5200, room_depth_mm=4200))
            ),
            stable_digest(base),
        )

    def test_size_category_and_count_changes_alter_panel_output(self) -> None:
        base = stable_digest(self._panel_output(studio_layout()))
        self.assertNotEqual(stable_digest(self._panel_output(studio_layout(width=900))), base)
        self.assertNotEqual(
            stable_digest(
                self._panel_output(
                    studio_layout(furniture_category="wall_cabinet"),
                    furniture_category="wall_cabinet",
                )
            ),
            base,
        )
        self.assertNotEqual(
            stable_digest(self._panel_output(studio_layout(extra_items=[second_cabinet()]))),
            base,
        )

    def test_room_change_moves_a_fill_item_and_alters_its_panels(self) -> None:
        """fill 件贴着北墙：房间变宽 → 它变宽 → 板件内容必变（所以判据不能粗判"房间变了可继承"）。"""
        narrow = stable_digest(self._panel_output(studio_layout(fill=True, room_width_mm=4000)))
        wide = stable_digest(self._panel_output(studio_layout(fill=True, room_width_mm=5200)))
        self.assertNotEqual(narrow, wide)


class InheritanceTests(unittest.TestCase):
    """R1 承认 + R2 留痕：内容没变就不让人再点一次头。"""

    def setUp(self) -> None:
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT, project_store=None
        )

    def _baseline(self, **layout_kwargs) -> tuple:
        """跑到"板件已确认"，返回 (project, 第一版, 板件摘要)。"""
        project = self.orchestrator.create_project(
            "继承",
            studio_layout(**layout_kwargs),
            stage_inputs=stage_inputs_from_spec(panel_parameters()),
        )
        self.orchestrator.confirm_layout(project)
        self.orchestrator.run_next(project)
        self.orchestrator.confirm_stage(project, "panel_plan")
        first = project.latest
        self.assertTrue(first.is_stage_approved(WorkflowStage.PANELS_PLANNED))
        return project, first, first.confirmed_panel_sha256

    def _revise_and_run_panels(self, project, **layout_kwargs):
        self.orchestrator.revise(project, studio_layout(**layout_kwargs))
        self.orchestrator.confirm_layout(project)
        self.orchestrator.run_next(project)
        return project.latest

    def test_placement_change_inherits_the_confirmed_panels(self) -> None:
        project, first, digest = self._baseline()
        revised = self._revise_and_run_panels(project, offset_mm=1200)

        self.assertEqual(revised.number, 2)
        self.assertTrue(revised.is_stage_approved(WorkflowStage.PANELS_PLANNED))
        self.assertEqual(revised.confirmed_panel_sha256, digest)
        self.assertEqual(
            revised.inherited["panel_plan"],
            {"sha256": digest, "from_revision": first.id, "from_stage": "panel_plan"},
        )
        self.assertEqual(revised.approved_digests["panel_plan"], digest)
        # 下游可以接着走：不需要人再确认一次板件。
        self.orchestrator.run_next(project)
        self.assertIn(
            WorkflowStage.MANUFACTURING_PLANNED.value, project.latest.stage_outputs
        )

    def test_inheritance_needs_an_earlier_confirmed_revision(self) -> None:
        """第一版没有可继承的对象：跑完板件仍然停在待确认，不能自己给自己点头。"""
        project = self.orchestrator.create_project(
            "首版",
            studio_layout(),
            stage_inputs=stage_inputs_from_spec(panel_parameters()),
        )
        self.orchestrator.confirm_layout(project)
        self.orchestrator.run_next(project)
        latest = project.latest
        self.assertFalse(latest.is_stage_approved(WorkflowStage.PANELS_PLANNED))
        self.assertIsNone(latest.confirmed_panel_sha256)
        self.assertEqual(latest.inherited, {})

    def test_resized_cabinet_is_not_inherited(self) -> None:
        project, _first, _digest = self._baseline()
        revised = self._revise_and_run_panels(project, width=900)
        self.assertFalse(revised.is_stage_approved(WorkflowStage.PANELS_PLANNED))
        self.assertIsNone(revised.confirmed_panel_sha256)
        self.assertEqual(revised.inherited, {})

    def test_room_change_still_inherits_for_a_sized_cabinet(self) -> None:
        """房间动了、柜体没动：板件内容不变，照样继承（这正是这次要省下的那次确认）。"""
        project, first, digest = self._baseline()
        revised = self._revise_and_run_panels(project, room_depth_mm=4200)
        self.assertTrue(revised.is_stage_approved(WorkflowStage.PANELS_PLANNED))
        self.assertEqual(revised.inherited["panel_plan"]["from_revision"], first.id)
        self.assertEqual(revised.confirmed_panel_sha256, digest)

    def test_inheritance_trail_survives_a_store_round_trip(self) -> None:
        import tempfile

        from furniture_workflow.workflow_store import JsonProjectStore

        project, first, digest = self._baseline()
        self._revise_and_run_panels(project, offset_mm=1200)
        with tempfile.TemporaryDirectory() as temporary:
            store = JsonProjectStore(temporary)
            store.save(project)
            restored = store.load(project.id)

        latest = restored.latest
        self.assertTrue(latest.is_stage_approved(WorkflowStage.PANELS_PLANNED))
        self.assertEqual(latest.approved_digests["panel_plan"], digest)
        self.assertEqual(latest.inherited["panel_plan"]["from_revision"], first.id)
        self.assertEqual(latest.confirmed_panel_sha256, digest)

    def test_snapshot_and_page_document_show_the_inheritance(self) -> None:
        """R3：沿用了哪一版必须看得见（工具面快照 + 页面文档），不能悄悄少做一步。"""
        from furniture_workflow.agent_tools import project_snapshot
        from furniture_workflow.project_preview import project_layout_document

        project, first, digest = self._baseline()
        revised = self._revise_and_run_panels(project, offset_mm=1200)

        snapshot = project_snapshot(project)
        self.assertEqual(snapshot["inherited_stages"], ["panel_plan"])
        self.assertEqual(
            snapshot["inherited"]["panel_plan"]["from_revision"], first.id
        )
        document = project_layout_document(project)
        self.assertEqual(document["inherited"]["panel_plan"]["sha256"], digest)
        self.assertEqual(revised.inherited["panel_plan"]["from_revision"], first.id)

    def test_inheritance_source_ignores_unapproved_content(self) -> None:
        """更早的版本里只是"算出来了、没人确认过"的内容不算数。"""
        from furniture_workflow.workflow_inheritance import inheritance_source

        project = self.orchestrator.create_project(
            "未确认不算数",
            studio_layout(),
            stage_inputs=stage_inputs_from_spec(panel_parameters()),
        )
        self.orchestrator.confirm_layout(project)
        self.orchestrator.run_next(project)
        first = project.latest
        digest = stable_digest(first.stage_outputs[WorkflowStage.PANELS_PLANNED.value])
        self.assertIsNone(
            inheritance_source(project, first, WorkflowStage.PANELS_PLANNED, digest)
        )


if __name__ == "__main__":
    unittest.main()
