from __future__ import annotations

from copy import deepcopy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_cad.cad_bridge import CadBridge
from furniture_delivery_validation.validation import validate_delivery
from furniture_layout.project_layout import ProjectLayout, single_cabinet_layout
from furniture_workflow.input_adapter import stage_inputs_from_spec
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from workflow_test_support import confirm_through, confirm_until
from furniture_workflow.workflow_project import Project
from furniture_workflow.workflow_state import STAGE_SEQUENCE, WorkflowStage, parse_stage
from furniture_workflow.workflow_store import JsonProjectStore
from furniture_panel_planning.panel_pipeline import plan_panel_stage
from panel_fixtures import cabinet_data, panel_parameters
from furniture_orchestrator_test_support import (
    cabinet_intent,
    fake_orchestrator,
    first_cabinet_spec,
)


class FurnitureOrchestratorFreezeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT,
            project_store=None,
        )
    def test_project_store_round_trips_stage_outputs_and_approvals(self) -> None:
        result = confirm_through(self.orchestrator, 
            "可恢复项目",
            cabinet_data(),
            through_stage=WorkflowStage.FEATURE_TREE_PLANNED,
        )
        project = result.project

        with tempfile.TemporaryDirectory() as temporary_directory:
            store = JsonProjectStore(temporary_directory)
            store.save(project)
            restored = store.load(project.id)

        self.assertEqual(restored.id, project.id)
        self.assertEqual(restored.latest.stage_inputs, project.latest.stage_inputs)
        self.assertEqual(restored.latest.stage_outputs, project.latest.stage_outputs)
        self.assertEqual(restored.latest.approved_stages, project.latest.approved_stages)
        self.assertEqual(
            restored.latest.workflow.current,
            WorkflowStage.FEATURE_TREE_PLANNED,
        )

    def test_confirming_intent_freezes_json_and_panel_retries_reuse_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = JsonProjectStore(temporary_directory)
            orchestrator = FurnitureOrchestrator(
                workspace_root=WORKSPACE_ROOT,
                project_store=store,
            )
            project = orchestrator.create_project(
                "可重试柜体",
                cabinet_intent(),
                stage_inputs=stage_inputs_from_spec(panel_parameters(n_doors=2)),
            )
            orchestrator.confirm_layout(project)
            frozen_path = store.layout_path(
                project.id,
                project.latest.layout_sha256,
            )
            self.assertTrue(frozen_path.is_file())
            frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
            self.assertTrue(frozen["confirmed"])
            self.assertEqual(
                frozen["cad"]["units"][0]["furniture_category"],
                "floor_cabinet",
            )
            intent_sha = project.latest.layout_sha256

            first = orchestrator.run_next(project)
            self.assertEqual(
                first_cabinet_spec(first.revision.stage_outputs["panel_plan"])[
                    "n_doors"
                ],
                2,
            )
            second = orchestrator.retry_stage(
                project,
                WorkflowStage.PANELS_PLANNED,
                stage_input={"parameters": panel_parameters(n_doors=1)},
            )
            self.assertEqual(second.revision.id, first.revision.id)
            self.assertEqual(second.revision.layout_sha256, intent_sha)
            self.assertEqual(len(second.revision.attempts_for("panel_plan")), 2)
            self.assertEqual(
                first_cabinet_spec(second.revision.stage_outputs["panel_plan"])[
                    "n_doors"
                ],
                1,
            )
            self.assertFalse(
                second.revision.is_stage_approved(WorkflowStage.PANELS_PLANNED)
            )
            attempt_dir = store.attempt_dir(
                project.id,
                second.revision.id,
                "panel_plan",
                2,
            )
            self.assertTrue((attempt_dir / "output.json").is_file())

            orchestrator.select_stage_attempt(
                project,
                WorkflowStage.PANELS_PLANNED,
                1,
            )
            self.assertEqual(
                first_cabinet_spec(project.latest.stage_outputs["panel_plan"])[
                    "n_doors"
                ],
                2,
            )

    def test_confirming_panels_freezes_json_and_manufacturing_retries_reuse_it(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = JsonProjectStore(temporary_directory)
            orchestrator = FurnitureOrchestrator(
                workspace_root=WORKSPACE_ROOT,
                project_store=store,
            )
            project = orchestrator.create_project(
                "可复用板件",
                cabinet_intent(),
                stage_inputs=stage_inputs_from_spec(panel_parameters()),
            )
            orchestrator.confirm_layout(project)
            orchestrator.run_next(project)
            orchestrator.confirm_stage(project, WorkflowStage.PANELS_PLANNED)

            digest = project.latest.confirmed_panel_sha256
            self.assertIsNotNone(digest)
            self.assertEqual(project.latest.panel_sha256, digest)
            frozen_path = store.panel_path(project.id, digest)
            self.assertTrue(frozen_path.is_file())
            frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
            self.assertEqual(set(frozen), {"cabinets"})
            original_thickness = first_cabinet_spec(frozen)["board_thickness"]
            live_spec = first_cabinet_spec(
                project.latest.stage_outputs["panel_plan"]
            )
            live_spec["board_thickness"] = original_thickness + 81

            with patch(
                "furniture_workflow.workflow_stage_runner.plan_panel_stage"
            ) as plan_panels:
                first = orchestrator.run_next(project)
                plan_panels.assert_not_called()

            self.assertIn(
                "manufacture_plan",
                first.revision.stage_outputs,
            )
            bom_thicknesses = {
                panel["thickness"]
                for panel in first.revision.stage_outputs["manufacture_plan"][
                    "panels"
                ]
            }
            self.assertIn(original_thickness, bom_thicknesses)
            self.assertNotIn(original_thickness + 81, bom_thicknesses)

            with patch(
                "furniture_workflow.workflow_stage_runner.plan_panel_stage"
            ) as plan_panels:
                second = orchestrator.retry_stage(
                    project,
                    WorkflowStage.MANUFACTURING_PLANNED,
                    stage_input={"parameters": {"door_hinge_side": "left"}},
                )
                plan_panels.assert_not_called()

            self.assertEqual(second.revision.id, first.revision.id)
            self.assertEqual(second.revision.confirmed_panel_sha256, digest)
            self.assertEqual(
                len(second.revision.attempts_for("manufacture_plan")),
                2,
            )
            self.assertEqual(
                json.loads(frozen_path.read_text(encoding="utf-8")),
                frozen,
            )
            self.assertEqual(
                second.revision.stage_outputs["manufacture_plan"][
                    "requested_options"
                ].get("door_hinge_side"),
                "left",
            )

            frozen_path.unlink()
            with self.assertRaisesRegex(ValueError, "frozen panel plan is missing"):
                orchestrator.retry_stage(
                    project,
                    WorkflowStage.MANUFACTURING_PLANNED,
                )

    def test_cad_snapshot_writes_frozen_panel_not_mutated_live(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            store = JsonProjectStore(temporary_root / "store")
            orchestrator = fake_orchestrator(temporary_root, project_store=store)
            result = confirm_through(orchestrator, 
                "frozen-cad",
                cabinet_data(),
                through_stage=WorkflowStage.FEATURE_TREE_PLANNED,
                output_root=temporary_root / "outputs",
                artifact_name="frozen-cad",
            )
            digest = result.revision.confirmed_panel_sha256
            self.assertIsNotNone(digest)
            frozen = json.loads(
                store.panel_path(result.project.id, digest).read_text(
                    encoding="utf-8"
                )
            )
            original_thickness = first_cabinet_spec(frozen)["board_thickness"]
            first_cabinet_spec(
                result.revision.stage_outputs["panel_plan"]
            )["board_thickness"] = original_thickness + 81

            cad = orchestrator.run_next(
                result.project,
                output_root=temporary_root / "outputs",
                artifact_name="frozen-cad",
                generate_cad=True,
            )
            snapshot = json.loads(
                (
                    temporary_root
                    / "outputs"
                    / "frozen-cad"
                    / "frozen-cad.panel-plan.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(
                first_cabinet_spec(snapshot)["board_thickness"],
                original_thickness,
            )
            self.assertEqual(cad.bridge.status, "ok")

    def test_failed_panel_attempt_can_be_retried_without_new_intent(self) -> None:
        project = self.orchestrator.create_project(
            "失败后重试",
            cabinet_intent(),
            stage_inputs=stage_inputs_from_spec(
                {"structure": {"mystery_joint": "unknown"}}
            ),
        )
        self.orchestrator.confirm_layout(project)
        failed = self.orchestrator.run_next(project).revision
        self.assertEqual(failed.workflow.current, WorkflowStage.LAYOUT_PLAN)
        self.assertFalse(failed.latest_attempt("panel_plan").passed)

        recovered = self.orchestrator.retry_stage(
            project,
            WorkflowStage.PANELS_PLANNED,
            stage_input={"parameters": panel_parameters()},
        ).revision
        self.assertEqual(recovered.id, failed.id)
        self.assertEqual(recovered.workflow.current, WorkflowStage.PANELS_PLANNED)
        self.assertTrue(recovered.latest_attempt("panel_plan").passed)
        self.assertIn("panel_plan", recovered.stage_outputs)

    def test_new_intent_revision_does_not_keep_panel_attempts(self) -> None:
        project = self.orchestrator.create_project(
            "改意图",
            cabinet_intent(),
            stage_inputs=stage_inputs_from_spec(panel_parameters()),
        )
        self.orchestrator.confirm_layout(project)
        self.orchestrator.run_next(project)
        parent = project.latest
        self.assertTrue(parent.attempts_for("panel_plan"))

        revised = self.orchestrator.revise(
            project,
            single_cabinet_layout(furniture_category="floor_cabinet", width=900, depth=600, height=1000, confirmed=True),
        )
        self.assertEqual(revised.parent_revision_id, parent.id)
        self.assertEqual(revised.attempts_for("panel_plan"), [])
        self.assertNotIn("panel_plan", revised.stage_outputs)

    def test_legacy_panel_and_manufacture_stage_names_are_canonicalized(self) -> None:
        self.assertEqual(parse_stage("panels_planned"), WorkflowStage.PANELS_PLANNED)
        self.assertEqual(
            parse_stage("manufacturing_planned"),
            WorkflowStage.MANUFACTURING_PLANNED,
        )
        self.assertEqual(WorkflowStage.PANELS_PLANNED.value, "panel_plan")
        self.assertEqual(WorkflowStage.MANUFACTURING_PLANNED.value, "manufacture_plan")

        project = self.orchestrator.create_project(
            "旧阶段名",
            cabinet_intent(),
            stage_inputs=stage_inputs_from_spec(panel_parameters()),
        )
        self.orchestrator.confirm_layout(project)
        self.orchestrator.run_next(project)
        data = project.to_dict()
        revision_data = data["revisions"][0]
        outputs = revision_data["stage_outputs"]
        outputs["panels_planned"] = outputs.pop("panel_plan")
        revision_data["approved_stages"].append("panels_planned")
        revision_data["stage_attempts"]["panels_planned"] = (
            revision_data["stage_attempts"].pop("panel_plan")
        )
        loaded = Project.from_dict(data).latest
        self.assertIn("panel_plan", loaded.stage_outputs)
        self.assertNotIn("panels_planned", loaded.stage_outputs)
        self.assertIn("panel_plan", loaded.approved_stages)
        self.assertNotIn("panels_planned", loaded.approved_stages)
        self.assertIn("panel_plan", loaded.stage_attempts)
        self.assertTrue(loaded.attempts_for("panels_planned"))


if __name__ == "__main__":
    unittest.main()


if __name__ == "__main__":
    unittest.main()
