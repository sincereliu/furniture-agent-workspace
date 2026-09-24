"""房间级确认（P4）：审一间只审一间，没动过的房间确认跟着走。

契约：布局检查点（`layout.confirmed`）是"每间都审过"的**派生值**——下游仍然只认这一个闸门，
所以 panel / 制造 / CAD 的契约一个字没改。改一间只审一间靠两条：
`Revision.approved_rooms`（人看过哪几间）与 `add_revision()` 里对**内容逐字节相同**的房间沿用确认。
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_layout.project_layout import ProjectLayout
from furniture_workflow.agent_tools import FurnitureToolSession, project_snapshot
from furniture_workflow.project_preview import project_layout_document
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_project import Project, Revision
from furniture_workflow.workflow_state import WorkflowStage
from furniture_workflow.workflow_store import JsonProjectStore


def room(room_id: str, *, offset_mm: float = 200.0, width_mm: float = 4000.0) -> dict:
    return {
        "id": room_id,
        "name": room_id,
        "width_mm": width_mm,
        "depth_mm": 3600.0,
        "height_mm": 2800.0,
        "items": [
            {
                "id": f"{room_id}-wardrobe",
                "label": "衣柜",
                "category": "wardrobe",
                "furniture_category": "floor_cabinet",
                "width": 1800.0,
                "depth": 600.0,
                "height": 2200.0,
                "placement": {
                    "mode": "wall",
                    "host_wall": "north",
                    "offset_mm": offset_mm,
                    "origin_z_mm": 0.0,
                },
            }
        ],
    }


def two_room_layout(
    *,
    bedroom_offset_mm: float = 200.0,
    living_offset_mm: float = 200.0,
) -> ProjectLayout:
    return ProjectLayout.from_source(
        {
            "rooms": [
                room("bedroom", offset_mm=bedroom_offset_mm),
                room("living", offset_mm=living_offset_mm),
            ]
        }
    )


class RoomLevelConfirmationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT, project_store=None
        )

    def _project(self, **kwargs) -> Project:
        return self.orchestrator.create_project("房间级确认", two_room_layout(**kwargs))

    def test_layout_is_confirmed_only_after_every_room_is_reviewed(self) -> None:
        project = self._project()
        revision = project.latest
        self.assertEqual(revision.pending_room_ids(), ["bedroom", "living"])
        self.assertFalse(revision.is_stage_approved(WorkflowStage.LAYOUT_PLAN))

        self.orchestrator.confirm_room(project, "bedroom")
        self.assertEqual(project.latest.pending_room_ids(), ["living"])
        self.assertFalse(project.latest.layout.confirmed)
        self.assertFalse(project.latest.is_stage_approved(WorkflowStage.LAYOUT_PLAN))
        # 还差一间，下游不许跑。
        self.orchestrator.run_next(project)
        self.assertNotIn(
            WorkflowStage.PANELS_PLANNED.value, project.latest.stage_outputs
        )

        self.orchestrator.confirm_room(project, "living")
        self.assertEqual(project.latest.pending_room_ids(), [])
        self.assertTrue(project.latest.layout.confirmed)
        self.assertTrue(project.latest.is_stage_approved(WorkflowStage.LAYOUT_PLAN))

    def test_confirm_stage_still_confirms_every_room_at_once(self) -> None:
        """整份确认这条老路保留：它等价于"每间都审过"。"""
        project = self._project()
        self.orchestrator.confirm_layout(project)
        revision = project.latest
        self.assertEqual(sorted(revision.approved_rooms), ["bedroom", "living"])
        self.assertTrue(revision.layout.confirmed)

    def test_reviewing_a_room_twice_is_harmless(self) -> None:
        project = self._project()
        self.orchestrator.confirm_room(project, "bedroom")
        self.orchestrator.confirm_room(project, "bedroom")
        self.assertEqual(project.latest.approved_rooms.count("bedroom"), 1)

    def test_unknown_room_is_refused(self) -> None:
        project = self._project()
        with self.assertRaises(ValueError):
            self.orchestrator.confirm_room(project, "kitchen")

    def test_room_review_is_refused_once_the_stage_moved_on(self) -> None:
        project = self._project()
        self.orchestrator.confirm_layout(project)
        with self.assertRaises(ValueError):
            self.orchestrator.confirm_room(project, "bedroom")
    def test_unchanged_room_keeps_its_review_in_the_next_revision(self) -> None:
        """P4 的收益：改客厅，卧室不用再审一遍。"""
        project = self._project()
        self.orchestrator.confirm_layout(project)
        first = project.latest

        self.orchestrator.revise(project, two_room_layout(living_offset_mm=1200))
        revised = project.latest
        self.assertEqual(revised.approved_rooms, ["bedroom"])
        self.assertEqual(revised.pending_room_ids(), ["living"])
        self.assertEqual(
            revised.inherited_rooms["bedroom"]["from_revision"], first.id
        )
        self.assertFalse(revised.layout.confirmed)

        self.orchestrator.confirm_room(project, "living")
        self.assertTrue(project.latest.layout.confirmed)

    def test_a_revision_with_no_room_changes_needs_no_review(self) -> None:
        """一间都没动：确认全部沿用，布局当场就是已确认，不需要人再点一次。"""
        project = self._project()
        self.orchestrator.confirm_layout(project)
        self.orchestrator.revise(project, two_room_layout())
        revised = project.latest
        self.assertEqual(sorted(revised.approved_rooms), ["bedroom", "living"])
        self.assertTrue(revised.layout.confirmed)
        self.assertTrue(revised.is_stage_approved(WorkflowStage.LAYOUT_PLAN))
        self.assertEqual(sorted(revised.inherited_rooms), ["bedroom", "living"])

    def test_another_rooms_edit_does_not_leak_a_review(self) -> None:
        """改客厅不能让客厅"沿用"自己的旧确认（内容变了）。"""
        project = self._project()
        self.orchestrator.confirm_layout(project)
        self.orchestrator.revise(project, two_room_layout(living_offset_mm=1200))
        self.assertNotIn("living", project.latest.inherited_rooms)
        self.assertNotIn("living", project.latest.approved_rooms)

    def test_old_revision_without_room_marks_reads_as_fully_reviewed(self) -> None:
        """老项目文件没有 `approved_rooms`：`confirmed: true` 等价于"每间都审过"。"""
        project = self._project()
        self.orchestrator.confirm_layout(project)
        payload = project.to_dict()
        for stored in payload["revisions"]:
            stored.pop("approved_rooms", None)
            stored.pop("inherited_rooms", None)
        restored = Project.from_dict(payload)
        revision = restored.latest
        self.assertTrue(revision.layout.confirmed)
        self.assertEqual(revision.pending_room_ids(), [])
        self.assertEqual(sorted(revision.approved_room_ids()), ["bedroom", "living"])

    def test_room_marks_survive_a_store_round_trip(self) -> None:
        project = self._project()
        self.orchestrator.confirm_layout(project)
        self.orchestrator.revise(project, two_room_layout(living_offset_mm=1200))
        with tempfile.TemporaryDirectory() as temporary:
            store = JsonProjectStore(temporary)
            store.save(project)
            restored = store.load(project.id)
        latest = restored.latest
        self.assertEqual(latest.approved_rooms, ["bedroom"])
        self.assertEqual(latest.pending_room_ids(), ["living"])
        self.assertEqual(
            latest.inherited_rooms["bedroom"]["from_revision"],
            project.revisions[0].id,
        )

    def test_snapshot_and_document_expose_room_reviews(self) -> None:
        project = self._project()
        self.orchestrator.confirm_room(project, "bedroom")
        snapshot = project_snapshot(project)
        self.assertEqual(snapshot["approved_rooms"], ["bedroom"])
        self.assertEqual(snapshot["pending_rooms"], ["living"])
        self.assertFalse(snapshot["layout_confirmed"])
        document = project_layout_document(project)
        flags = {entry["id"]: entry["approved"] for entry in document["rooms"]}
        self.assertEqual(flags, {"bedroom": True, "living": False})
        self.assertEqual(document["pending_rooms"], ["living"])

    def test_tool_surface_confirms_one_room(self) -> None:
        """工具面：`furniture_confirm_stage` 带 room_id 时只审那一间。"""
        store = JsonProjectStore(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, store.root, True)
        session = FurnitureToolSession(
            FurnitureOrchestrator(workspace_root=WORKSPACE_ROOT, project_store=store)
        )
        created = session.call(
            "furniture_create_project",
            {"name": "工具面", "rooms": [room("bedroom"), room("living")]},
        )
        self.assertTrue(created["ok"], created)
        project_id = created["project"]["id"]

        reviewed = session.call(
            "furniture_confirm_stage", {"project_id": project_id, "room_id": "bedroom"}
        )
        self.assertTrue(reviewed["ok"], reviewed)
        self.assertEqual(reviewed["project"]["pending_rooms"], ["living"])
        self.assertFalse(reviewed["project"]["layout_confirmed"])
        self.assertFalse(reviewed["progressed"])

        done = session.call(
            "furniture_confirm_stage", {"project_id": project_id, "room_id": "living"}
        )
        self.assertTrue(done["project"]["layout_confirmed"])
        self.assertTrue(done["project"]["current_stage_approved"])
        self.assertEqual(done["project"]["pending_rooms"], [])

    def test_tool_surface_refuses_room_id_for_other_stages(self) -> None:
        store = JsonProjectStore(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, store.root, True)
        session = FurnitureToolSession(
            FurnitureOrchestrator(workspace_root=WORKSPACE_ROOT, project_store=store)
        )
        created = session.call(
            "furniture_create_project",
            {"name": "工具面", "rooms": [room("bedroom")]},
        )
        project_id = created["project"]["id"]
        refused = session.call(
            "furniture_confirm_stage",
            {"project_id": project_id, "stage": "panel_plan", "room_id": "bedroom"},
        )
        self.assertFalse(refused["ok"])
        self.assertEqual(refused["error"]["code"], "INVALID_ARGUMENT")


class RoomDigestTests(unittest.TestCase):
    def test_room_digest_ignores_other_rooms(self) -> None:
        revision = Revision(number=1, layout=two_room_layout())
        before = revision.room_digest("bedroom")
        other = Revision(number=1, layout=two_room_layout(living_offset_mm=1200))
        self.assertEqual(other.room_digest("bedroom"), before)
        self.assertNotEqual(other.room_digest("living"), revision.room_digest("living"))
        self.assertIsNone(revision.room_digest("kitchen"))


if __name__ == "__main__":
    unittest.main()
