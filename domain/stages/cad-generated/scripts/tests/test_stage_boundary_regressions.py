"""Behavioral regressions for stage ownership, handoff coverage and layout identity."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))
from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_layout.layout_figures import project_layout_dict
from furniture_manufacturing.manufacturing_bom import BOMReport, emit_drilled_holes, plan_manufacturing
from furniture_manufacturing.manufacturing_revision import revise_bom
from furniture_manufacturing.validation import validate_manufacturing
from furniture_panel_planning.assembly_tree import iter_assembly_panels
from furniture_panel_planning.panel_edit import edit_cabinet_panels
from furniture_panel_planning.panel_pipeline import plan_panel_stage
from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.structure_planning import CabinetStructure
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_state import WorkflowStage
from furniture_workflow.workflow_store import JsonProjectStore
from panel_fixtures import cabinet_data, cabinet_envelope, furniture_spec, panel_parameters
from test_multi_cabinet_downstream import two_cabinet_spec
from workflow_test_support import confirm_through


class ManufacturingRevisionTests(unittest.TestCase):
    def test_brand_option_normalization_is_shared_by_planning_revision_and_validation(self):
        spec = furniture_spec(width=500)
        placements = plan_panels(spec, CabinetStructure.from_spec(spec))
        for options in (None, [], 42):
            with self.subTest(options=options):
                bom = plan_manufacturing(spec, placements, requested_options={"options": options})
                self.assertTrue(validate_manufacturing(spec, bom, placements).passed)
                revised = BOMReport.from_dict(revise_bom(asdict(bom)))
                self.assertEqual(bom.hardware, revised.hardware)

    def test_connector_edit_updates_bom_holes_and_persisted_records_together(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JsonProjectStore(temporary)
            orchestrator = FurnitureOrchestrator(project_store=store)
            result = confirm_through(orchestrator, "revise", cabinet_data(
                width=500,
                shelves=[{"shelf_type": "movable", "gap_below_mm": None}],
                top_gap_mm=100.0,
            ))
            edited = deepcopy(result.revision.stage_outputs["manufacture_plan"])
            old_hardware = deepcopy(edited["cabinets"][0]["bom"]["hardware"])
            bom = edited["cabinets"][0]["bom"]
            bom["requested_options"]["movable_shelf_connector"] = "shelf_pin"
            for panel in bom["panels"]:
                if panel["panel_type"] == "movable_shelf":
                    panel["movable_shelf_connector"] = "shelf_pin"
            bom["total_area_m2"] = -1
            revision = orchestrator.revise_stage_output(
                result.project, WorkflowStage.MANUFACTURING_PLANNED, edited
            )
            orchestrator.confirm_stage(result.project)
            self.assertTrue(revision.is_stage_approved(WorkflowStage.MANUFACTURING_PLANNED))
            reloaded = store.load(result.project.id)
            restored = BOMReport.from_dict(
                reloaded.latest.stage_outputs["manufacture_plan"]["cabinets"][0]["bom"]
            )
            self.assertIn("层板托", {item.name for item in restored.hardware})
            self.assertNotIn("二合一连接件", {item.name for item in restored.hardware})
            self.assertAlmostEqual(restored.total_area_m2, sum(p.area_m2 for p in restored.panels))
            drilled = emit_drilled_holes(restored)
            hole_types = {hole["hole_type"] for panel in drilled["panels"] for hole in panel["holes"]}
            self.assertIn("shelf_pin", hole_types)
            self.assertNotIn("two_in_one_cam", hole_types)
            self.assertEqual(BOMReport.from_dict(asdict(restored)), restored)
            _, spec, placements = orchestrator._cabinet_handoffs(
                reloaded.latest, project_id=reloaded.id
            )[0]
            restored.hardware = BOMReport.from_dict({**asdict(restored), "hardware": old_hardware}).hardware
            report = validate_manufacturing(spec, restored, placements)
            self.assertIn("HARDWARE_SNAPSHOT_MISMATCH", {i.code for i in report.issues})


class CabinetCoverageTests(unittest.TestCase):
    def test_partial_duplicate_reordered_and_unknown_cabinets_cannot_be_confirmed(self):
        orchestrator = FurnitureOrchestrator()
        result = confirm_through(
            orchestrator, "two cabinets", two_cabinet_spec(),
            through_stage=WorkflowStage.FEATURE_TREE_PLANNED,
        )
        for stage in (WorkflowStage.MANUFACTURING_PLANNED, WorkflowStage.FEATURE_TREE_PLANNED):
            original = result.revision.stage_outputs[stage.value]
            for kind in ("missing", "duplicate", "reordered", "unknown"):
                with self.subTest(stage=stage.value, kind=kind):
                    project = deepcopy(result.project)
                    edited = deepcopy(original)
                    entries = edited["cabinets"]
                    if kind == "missing":
                        entries.pop()
                    elif kind == "duplicate":
                        entries[1] = deepcopy(entries[0])
                    elif kind == "reordered":
                        entries.reverse()
                    else:
                        entries[1]["id"] = "unknown_cabinet"
                    revision = orchestrator.revise_stage_output(project, stage, edited)
                    orchestrator.confirm_stage(project, stage)
                    self.assertFalse(revision.is_stage_approved(stage))
                    self.assertEqual(revision.workflow.current, WorkflowStage.FAILED)
                    self.assertIn("CABINET_COVERAGE_MISMATCH", {
                        issue.code for issue in revision.validations[-1].issues
                    })


class LayoutContentIdentityTests(unittest.TestCase):
    def test_web_changes_do_not_change_hash_confirmation_or_frozen_layout(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JsonProjectStore(temporary)
            orchestrator = FurnitureOrchestrator(project_store=store)
            from furniture_layout.project_layout import ProjectLayout
            layout = ProjectLayout.from_source({"rooms": cabinet_data()["rooms"]})
            project = orchestrator.create_project("layout", layout)
            revision = project.latest
            before = revision.layout_sha256
            with mock.patch("furniture_web.room_page._room_page_src", return_value="/layout-view/new.js?v=123"):
                view = project_layout_dict(layout)
                self.assertIn("/layout-view/new.js?v=123", view["rooms"][0]["viewer"]["html"])
                self.assertEqual(before, revision.layout_sha256)
            with mock.patch("furniture_web.room_page.render_viewer", side_effect=AssertionError("web unavailable")):
                orchestrator.confirm_layout(project)
                frozen_hash = revision.layout_sha256
                store.save(project)
                reloaded = store.load(project.id)
                self.assertEqual(reloaded.latest.layout_sha256, frozen_hash)
                self.assertTrue(reloaded.latest.is_stage_approved(WorkflowStage.LAYOUT_PLAN))
                payload = json.loads(store.layout_path(project.id, frozen_hash).read_text(encoding="utf-8"))
                self.assertEqual(payload, reloaded.latest.layout.to_dict())
                self.assertNotIn("viewer", payload["rooms"][0])
                self.assertNotIn("preview", payload["rooms"][0])

    def test_layout_serialization_runs_without_importing_web(self):
        code = '''
import sys
from furniture_layout.project_layout import ProjectLayout
layout = ProjectLayout.from_source({"rooms": [{"id": "r", "width_mm": 3000,
    "depth_mm": 3000, "height_mm": 2800, "items": []}]})
layout.to_dict()
assert not any(name.startswith("furniture_web") for name in sys.modules)
'''
        env = {**os.environ, "PYTHONPATH": os.pathsep.join((
            str(WORKSPACE_ROOT / "domain/stages/layout-plan/scripts"),
            str(SCRIPT_ROOT),
        ))}
        result = subprocess.run([sys.executable, "-c", code], env=env,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


class PanelEditOwnershipTests(unittest.TestCase):
    def test_stage_edit_is_pure_and_checks_the_complete_batch(self):
        output = plan_panel_stage([cabinet_envelope()], panel_parameters())
        before = deepcopy(output)
        panels = iter_assembly_panels(output["cabinets"][0])
        panel_id = panels[0]["id"]
        edited = edit_cabinet_panels(output, "cabinet_1", axes={panel_id: "y"})
        self.assertEqual(output, before)
        self.assertEqual(edited.panels, (panel_id,))
        changed = {p["id"]: p for p in iter_assembly_panels(edited.output["cabinets"][0])}
        self.assertEqual(changed[panel_id]["grain_axis"], "y")
        with self.assertRaises(ValueError):
            edit_cabinet_panels(output, "cabinet_1", axes={panel_id: "y", "missing": "z"})
        self.assertEqual(output, before)


class StageTestDiscoveryTests(unittest.TestCase):
    def test_stage_local_tests_are_reached_by_the_shared_runner(self):
        import run_tests

        local_root = WORKSPACE_ROOT / "domain/stages/layout-plan/scripts/tests"
        for pattern in ("test_edit_position_stability.py", "test_wall_detach_rotation.py"):
            with self.subTest(pattern=pattern):
                expected = unittest.TestLoader().discover(
                    str(local_root), pattern=pattern, top_level_dir=str(local_root)
                )
                expected_ids = {case.id() for case in run_tests._flatten(expected)}
                discovered_ids = {case.id() for case in run_tests._flatten(run_tests._suite(pattern))}
                self.assertTrue(expected_ids)
                self.assertEqual(discovered_ids, expected_ids)


if __name__ == "__main__":
    unittest.main()
