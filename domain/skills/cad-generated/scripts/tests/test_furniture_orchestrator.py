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
from furniture_workflow.input_adapter import (
    panel_envelopes_from_layout,
    stage_inputs_from_spec,
)
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


class FurnitureOrchestratorLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT,
            project_store=None,
        )

    def test_interactive_workflow_pauses_at_every_stage(self) -> None:
        project = self.orchestrator.create_project(
            "玄关柜",
            cabinet_intent(),
            stage_inputs=stage_inputs_from_spec(
                panel_parameters()
            ),
        )
        revision = project.latest

        self.assertEqual(revision.workflow.current, WorkflowStage.LAYOUT_PLAN)
        self.assertEqual(
            set(revision.stage_outputs),
            {WorkflowStage.LAYOUT_PLAN.value},
        )

        self.orchestrator.confirm_layout(project)
        for expected in STAGE_SEQUENCE[1:4]:
            result = self.orchestrator.run_next(project)
            self.assertEqual(result.revision.workflow.current, expected)
            self.assertIn(expected.value, result.revision.stage_outputs)
            self.assertFalse(result.revision.is_stage_approved(expected))

            paused = self.orchestrator.run_next(project)
            self.assertEqual(paused.revision.workflow.current, expected)

            self.orchestrator.confirm_stage(project, expected)

        self.assertEqual(
            project.latest.workflow.current,
            WorkflowStage.FEATURE_TREE_PLANNED,
        )
        self.assertEqual(
            set(project.latest.stage_outputs),
            {stage.value for stage in STAGE_SEQUENCE[:4]},
        )

    def test_manufacturing_reads_cabinet_tree(self) -> None:
        project = self.orchestrator.create_project(
            "只读柜体树",
            cabinet_intent(),
            stage_inputs=stage_inputs_from_spec(panel_parameters()),
        )
        self.orchestrator.confirm_layout(project)
        result = self.orchestrator.run_next(project)
        panel_output = result.revision.stage_outputs[WorkflowStage.PANELS_PLANNED.value]
        self.assertEqual(set(panel_output), {"cabinets"})
        self.orchestrator.confirm_stage(project, WorkflowStage.PANELS_PLANNED)

        manufactured = self.orchestrator.run_next(project)
        self.assertIn(
            WorkflowStage.MANUFACTURING_PLANNED.value,
            manufactured.revision.stage_outputs,
        )
        bom_panels = manufactured.revision.stage_outputs[
            WorkflowStage.MANUFACTURING_PLANNED.value
        ]["panels"]
        self.assertTrue(bom_panels)
        self.assertEqual(
            bom_panels[0]["parent_id"],
            panel_output["cabinets"][0]["id"],
        )

    def test_revising_panels_invalidates_and_regenerates_downstream(self) -> None:
        result = confirm_through(self.orchestrator, 
            "可修改柜体",
            cabinet_data(shelf_count=2, n_doors=2),
            through_stage=WorkflowStage.FEATURE_TREE_PLANNED,
        )
        project = result.project
        parent = project.latest
        old_panel_output = deepcopy(
            parent.stage_outputs[WorkflowStage.PANELS_PLANNED.value]
        )
        edited_panels = plan_panel_stage(
            panel_envelopes_from_layout(parent.layout),
            panel_parameters(
                shelves=[{"shelf_type": "fixed", "gap_below_mm": None}],
                top_gap_mm=300,
                n_doors=2,
            ),
        )

        revised = self.orchestrator.revise_stage_output(
            project,
            WorkflowStage.PANELS_PLANNED,
            edited_panels,
        )

        self.assertEqual(revised.parent_revision_id, parent.id)
        self.assertEqual(
            set(revised.stage_outputs),
            {
                WorkflowStage.LAYOUT_PLAN.value,
                WorkflowStage.PANELS_PLANNED.value,
            },
        )
        self.assertNotIn(
            WorkflowStage.FEATURE_TREE_PLANNED.value,
            revised.stage_outputs,
        )
        self.assertEqual(
            revised.approved_stages,
            [WorkflowStage.LAYOUT_PLAN.value],
        )

        self.orchestrator.confirm_stage(project, WorkflowStage.PANELS_PLANNED)
        regenerated = confirm_until(
            self.orchestrator,
            project,
            through_stage=WorkflowStage.FEATURE_TREE_PLANNED,
        )

        new_panel_output = regenerated.revision.stage_outputs[
            WorkflowStage.PANELS_PLANNED.value
        ]
        self.assertNotEqual(new_panel_output, old_panel_output)
        self.assertIn(
            WorkflowStage.FEATURE_TREE_PLANNED.value,
            regenerated.revision.stage_outputs,
        )

    def test_confirmed_generation_records_all_six_serial_stages(self) -> None:
        artifact_name = f"orchestrator-test-{uuid4().hex}"
        source_dir = WORKSPACE_ROOT / "temp" / "cad-source" / artifact_name
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                temporary_root = Path(temporary_directory)
                orchestrator = fake_orchestrator(temporary_root)
                result = confirm_through(orchestrator, 
                    artifact_name,
                    cabinet_data("wall_cabinet"),
                    output_root=temporary_root / "outputs",
                    artifact_name=artifact_name,
                    generate_cad=True,
                )

                self.assertEqual(
                    result.revision.workflow.current,
                    WorkflowStage.DELIVERY_VALIDATED,
                )
                self.assertEqual(
                    set(result.revision.stage_outputs),
                    {stage.value for stage in STAGE_SEQUENCE},
                )
                self.assertEqual(
                    result.revision.approved_stages,
                    [stage.value for stage in STAGE_SEQUENCE],
                )
                self.assertTrue(all(report.passed for report in result.revision.validations))
                self.assertEqual(
                    [report.stage for report in result.revision.validations],
                    [stage.value for stage in STAGE_SEQUENCE],
                )
                artifact_kinds = {
                    artifact.kind for artifact in result.revision.manifest.artifacts
                }
                self.assertEqual(
                    artifact_kinds,
                    {
                        "layout_plan",
                        "panel_plan",
                        "manufacturing_plan",
                        "feature_tree",
                        "bom",
                        "drilled_holes",
                        "drilled_holes_glb",
                        "drilled_holes_step",
                        "drilled_holes_step_glb",
                        "six_side_drill_xml",
                        "cad_source",
                        "step",
                        "viewer_topology",
                    },
                )
                self.assertIsNotNone(result.pipeline)
                self.assertEqual(result.bridge.status, "ok")
                delivery_output = result.revision.stage_outputs[
                    WorkflowStage.DELIVERY_VALIDATED.value
                ]
                self.assertTrue(delivery_output["passed"])
                self.assertIn(
                    "MANUFACTURING_PRELIMINARY",
                    {
                        issue["code"]
                        for issue in delivery_output["issues"]
                    },
                )
                readiness_by_kind = {
                    artifact.kind: artifact.metadata.get("readiness")
                    for artifact in result.revision.manifest.artifacts
                    if artifact.kind in {"manufacturing_plan", "bom"}
                }
                self.assertEqual(
                    readiness_by_kind,
                    {
                        "manufacturing_plan": "preliminary",
                        "bom": "preliminary",
                    },
                )
                six_side_artifacts = [
                    artifact
                    for artifact in result.revision.manifest.artifacts
                    if artifact.kind == "six_side_drill_xml"
                ]
                self.assertEqual(
                    len(six_side_artifacts),
                    len(result.pipeline.panels),
                )
                self.assertTrue(
                    all(
                        artifact.metadata.get("panel_label")
                        and artifact.metadata.get("readiness") == "preliminary"
                        for artifact in six_side_artifacts
                    )
                )

                incomplete_lineage = validate_delivery(
                    result.revision.manifest,
                    source_revision_id=result.revision.id,
                    stage_outputs=result.revision.stage_outputs,
                    approved_stages=[],
                    stage_validations=[],
                )
                self.assertFalse(incomplete_lineage.passed)
                incomplete_codes = {
                    issue.code for issue in incomplete_lineage.issues
                }
                self.assertIn(
                    "UNAPPROVED_DELIVERY_SOURCE_STAGE",
                    incomplete_codes,
                )
                self.assertIn(
                    "MISSING_STAGE_VALIDATION",
                    incomplete_codes,
                )

                design_artifact = next(
                    artifact
                    for artifact in result.revision.manifest.artifacts
                    if artifact.kind == "layout_plan"
                )
                Path(design_artifact.path).write_text(
                    '{"tampered": true}',
                    encoding="utf-8",
                )
                tampered_report = validate_delivery(
                    result.revision.manifest,
                    source_revision_id=result.revision.id,
                )
                self.assertFalse(tampered_report.passed)
                self.assertIn(
                    "ARTIFACT_HASH_MISMATCH",
                    {issue.code for issue in tampered_report.issues},
                )
        finally:
            shutil.rmtree(source_dir, ignore_errors=True)

    def test_revised_manufacturing_operation_must_remain_inside_target_panel(self) -> None:
        result = confirm_through(self.orchestrator, 
            "加工验证",
            cabinet_data(),
            through_stage=WorkflowStage.MANUFACTURING_PLANNED,
        )
        edited = deepcopy(
            result.revision.stage_outputs[WorkflowStage.MANUFACTURING_PLANNED.value]
        )
        edited["operations"][0]["pos_x"] = -1
        revision = self.orchestrator.revise_stage_output(
            result.project,
            WorkflowStage.MANUFACTURING_PLANNED,
            edited,
        )

        self.orchestrator.confirm_stage(
            result.project,
            WorkflowStage.MANUFACTURING_PLANNED,
        )

        self.assertEqual(revision.workflow.current, WorkflowStage.FAILED)
        self.assertIn(
            "OPERATION_OUTSIDE_TARGET",
            {issue.code for issue in revision.validations[-1].issues},
        )

    def test_manufacturing_readiness_must_use_known_state(self) -> None:
        result = confirm_through(self.orchestrator, 
            "制造状态验证",
            cabinet_data(),
            through_stage=WorkflowStage.MANUFACTURING_PLANNED,
        )
        edited = deepcopy(
            result.revision.stage_outputs[
                WorkflowStage.MANUFACTURING_PLANNED.value
            ]
        )
        edited["readiness"] = "claimed_ready"
        revision = self.orchestrator.revise_stage_output(
            result.project,
            WorkflowStage.MANUFACTURING_PLANNED,
            edited,
        )

        self.orchestrator.confirm_stage(
            result.project,
            WorkflowStage.MANUFACTURING_PLANNED,
        )

        self.assertEqual(revision.workflow.current, WorkflowStage.FAILED)
        self.assertIn(
            "INVALID_MANUFACTURING_READINESS",
            {issue.code for issue in revision.validations[-1].issues},
        )

    def test_new_intent_revision_marks_parent_artifacts_stale(self) -> None:
        artifact_name = f"revision-test-{uuid4().hex}"
        source_dir = WORKSPACE_ROOT / "temp" / "cad-source" / artifact_name
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                temporary_root = Path(temporary_directory)
                orchestrator = fake_orchestrator(temporary_root)
                result = confirm_through(orchestrator, 
                    artifact_name,
                    cabinet_data("wall_cabinet"),
                    output_root=temporary_root / "outputs",
                    artifact_name=artifact_name,
                    generate_cad=True,
                )
                parent = result.revision

                revised = orchestrator.revise(
                    result.project,
                    single_cabinet_layout(furniture_category="wall_cabinet", width=900, depth=350, height=900, origin_z_mm=2000, confirmed=True),
                )

                self.assertEqual(revised.parent_revision_id, parent.id)
                self.assertTrue(all(item.stale for item in parent.manifest.artifacts))
                self.assertEqual(
                    set(revised.stage_outputs),
                    {WorkflowStage.LAYOUT_PLAN.value},
                )
        finally:
            shutil.rmtree(source_dir, ignore_errors=True)

    def test_unconfirmed_intent_pauses_without_executing_panels(self) -> None:
        project = self.orchestrator.create_project("未确认", cabinet_intent())
        result = self.orchestrator.run_until(
            project,
            WorkflowStage.FEATURE_TREE_PLANNED,
        )

        self.assertIsNone(result.pipeline)
        self.assertEqual(
            result.revision.workflow.current,
            WorkflowStage.LAYOUT_PLAN,
        )
        self.assertNotIn(
            WorkflowStage.PANELS_PLANNED.value,
            result.revision.stage_outputs,
        )
        self.assertNotIn("layout_planned", result.revision.stage_outputs)

    def test_furniture_spec_rejects_room_scene_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "room"):
            stage_inputs_from_spec(
                cabinet_data(
                    room={
                        "width_mm": 4200,
                        "depth_mm": 3600,
                        "height_mm": 2800,
                    },
                    placement={
                        "mode": "wall",
                        "host_wall": "north",
                        "offset_mm": 500,
                    },
                )
            )

    def test_missing_item_dimension_fails_before_layout_is_created(self) -> None:
        with self.assertRaisesRegex(ValueError, "width, depth and height"):
            self.orchestrator.layout_from_spec(
                {
                    "furniture_category": "floor_cabinet",
                    "width": 800,
                    "height": 1000,
                }
            )


if __name__ == "__main__":
    unittest.main()
