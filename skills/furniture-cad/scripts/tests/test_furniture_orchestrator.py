from __future__ import annotations

from copy import deepcopy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_cad.cad_bridge import CadBridge
from furniture_delivery_validation.validation import validate_delivery
from furniture_design_intent.design_intent import DesignIntent, OverallSize
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_state import STAGE_SEQUENCE, WorkflowStage
from furniture_workflow.workflow_store import JsonProjectStore


def cabinet_intent(*, furniture_type: str = "floor_cabinet") -> DesignIntent:
    return DesignIntent(
        furniture_type=furniture_type,
        purpose="测试柜体七阶段工作流",
        overall_size=OverallSize(width_mm=800, depth_mm=600, height_mm=1000),
        layout={"shelf_count": 2, "n_doors": 2},
    )


def fake_orchestrator(temporary_root: Path) -> FurnitureOrchestrator:
    launcher_path = temporary_root / "fake_step.py"
    launcher_path.write_text(
        "\n".join(
            [
                "import sys",
                "from pathlib import Path",
                "output = Path(sys.argv[sys.argv.index('--output') + 1])",
                "output.parent.mkdir(parents=True, exist_ok=True)",
                "output.write_text('STEP', encoding='utf-8')",
                "output.with_name(f'.{output.name}.glb').write_bytes(b'GLB')",
            ]
        ),
        encoding="utf-8",
    )
    bridge = CadBridge(
        workspace_root=WORKSPACE_ROOT,
        python_executable=sys.executable,
        step_launcher=launcher_path,
    )
    return FurnitureOrchestrator(
        workspace_root=WORKSPACE_ROOT,
        cad_bridge=bridge,
    )


class FurnitureOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.orchestrator = FurnitureOrchestrator(workspace_root=WORKSPACE_ROOT)

    def test_interactive_workflow_pauses_at_every_stage(self) -> None:
        project = self.orchestrator.create_project("玄关柜", cabinet_intent())
        revision = project.latest

        self.assertEqual(revision.workflow.current, WorkflowStage.DESIGN_INTENT)
        self.assertEqual(
            set(revision.stage_outputs),
            {WorkflowStage.DESIGN_INTENT.value},
        )

        self.orchestrator.confirm_intent(project)
        for expected in STAGE_SEQUENCE[1:5]:
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
            {stage.value for stage in STAGE_SEQUENCE[:5]},
        )

    def test_revising_layout_invalidates_and_regenerates_downstream(self) -> None:
        result = self.orchestrator.execute_spec(
            "可修改柜体",
            {
                "type": "floor_cabinet",
                "width": 800,
                "depth": 600,
                "height": 1000,
                "shelf_count": 2,
                "n_doors": 2,
            },
            through_stage=WorkflowStage.FEATURE_TREE_PLANNED,
        )
        project = result.project
        parent = project.latest
        old_panel_output = deepcopy(
            parent.stage_outputs[WorkflowStage.PANELS_PLANNED.value]
        )
        edited_layout = deepcopy(
            parent.stage_outputs[WorkflowStage.LAYOUT_PLANNED.value]
        )
        edited_layout["layout"]["shelf_count"] = 1

        revised = self.orchestrator.revise_stage_output(
            project,
            WorkflowStage.LAYOUT_PLANNED,
            edited_layout,
        )

        self.assertEqual(revised.parent_revision_id, parent.id)
        self.assertEqual(
            set(revised.stage_outputs),
            {
                WorkflowStage.DESIGN_INTENT.value,
                WorkflowStage.LAYOUT_PLANNED.value,
            },
        )
        self.assertNotIn(
            WorkflowStage.FEATURE_TREE_PLANNED.value,
            revised.stage_outputs,
        )
        self.assertEqual(
            revised.approved_stages,
            [WorkflowStage.DESIGN_INTENT.value],
        )

        self.orchestrator.confirm_stage(project, WorkflowStage.LAYOUT_PLANNED)
        regenerated = self.orchestrator.run_until(
            project,
            WorkflowStage.FEATURE_TREE_PLANNED,
            auto_confirm=True,
        )

        new_panel_output = regenerated.revision.stage_outputs[
            WorkflowStage.PANELS_PLANNED.value
        ]
        self.assertNotEqual(new_panel_output, old_panel_output)
        self.assertIn(
            WorkflowStage.FEATURE_TREE_PLANNED.value,
            regenerated.revision.stage_outputs,
        )

    def test_named_batch_generation_records_all_seven_stages(self) -> None:
        artifact_name = f"orchestrator-test-{uuid4().hex}"
        source_dir = WORKSPACE_ROOT / "temp" / "cad-source" / artifact_name
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                temporary_root = Path(temporary_directory)
                orchestrator = fake_orchestrator(temporary_root)
                result = orchestrator.execute_spec(
                    artifact_name,
                    {
                        "type": "wall_cabinet",
                        "width": 800,
                        "depth": 350,
                        "height": 900,
                    },
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
                        "design_intent",
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
                    if artifact.kind == "design_intent"
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
        result = self.orchestrator.execute_spec(
            "加工验证",
            {
                "type": "floor_cabinet",
                "width": 800,
                "depth": 600,
                "height": 1000,
            },
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
        result = self.orchestrator.execute_spec(
            "制造状态验证",
            {
                "type": "floor_cabinet",
                "width": 800,
                "depth": 600,
                "height": 1000,
            },
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
                result = orchestrator.execute_spec(
                    artifact_name,
                    {
                        "type": "wall_cabinet",
                        "width": 800,
                        "depth": 350,
                        "height": 900,
                    },
                    output_root=temporary_root / "outputs",
                    artifact_name=artifact_name,
                    generate_cad=True,
                )
                parent = result.revision

                revised = orchestrator.revise(
                    result.project,
                    DesignIntent(
                        furniture_type="wall_cabinet",
                        overall_size=OverallSize(900, 350, 900),
                    ),
                )

                self.assertEqual(revised.parent_revision_id, parent.id)
                self.assertTrue(all(item.stale for item in parent.manifest.artifacts))
                self.assertEqual(
                    set(revised.stage_outputs),
                    {WorkflowStage.DESIGN_INTENT.value},
                )
        finally:
            shutil.rmtree(source_dir, ignore_errors=True)

    def test_unconfirmed_intent_pauses_without_executing_layout(self) -> None:
        project = self.orchestrator.create_project("未确认", cabinet_intent())
        result = self.orchestrator.run_until(
            project,
            WorkflowStage.FEATURE_TREE_PLANNED,
        )

        self.assertIsNone(result.pipeline)
        self.assertEqual(
            result.revision.workflow.current,
            WorkflowStage.DESIGN_INTENT,
        )
        self.assertNotIn(
            WorkflowStage.LAYOUT_PLANNED.value,
            result.revision.stage_outputs,
        )

    def test_draft_intent_preserves_null_dimensions_and_cannot_confirm(self) -> None:
        intent = DesignIntent.from_dict(
            {
                "furniture_type": "floor_cabinet",
                "overall_size": {
                    "width_mm": 800,
                    "depth_mm": None,
                    "height_mm": 1000,
                },
                "unresolved": ["depth_mm"],
            }
        )
        project = self.orchestrator.create_project("未完整柜体", intent)

        self.assertIsNone(
            project.latest.stage_outputs["design_intent"]["overall_size"]["depth_mm"]
        )
        revision = self.orchestrator.confirm_intent(project)

        self.assertEqual(revision.workflow.current, WorkflowStage.FAILED)
        issue_codes = {issue.code for issue in revision.validations[-1].issues}
        self.assertIn("INVALID_INTENT", issue_codes)
        self.assertIn("UNRESOLVED_DECISIONS", issue_codes)

    def test_unsupported_layout_decision_is_not_silently_discarded(self) -> None:
        intent = cabinet_intent()
        intent = DesignIntent.from_dict(
            {
                **intent.to_dict(),
                "layout": {
                    **intent.layout,
                    "drawer_count": 2,
                },
            }
        )
        project = self.orchestrator.create_project("带抽屉柜体", intent)

        revision = self.orchestrator.confirm_intent(project)

        self.assertEqual(revision.workflow.current, WorkflowStage.FAILED)
        self.assertIn(
            "UNSUPPORTED_LAYOUT_DECISION",
            {issue.code for issue in revision.validations[-1].issues},
        )

    def test_unsupported_family_fails_at_design_intent_confirmation(self) -> None:
        project = self.orchestrator.create_project(
            "床", cabinet_intent(furniture_type="bed")
        )
        revision = self.orchestrator.confirm_intent(project)

        self.assertEqual(revision.workflow.current, WorkflowStage.FAILED)
        self.assertFalse(revision.validations[-1].passed)
        self.assertEqual(
            revision.validations[-1].issues[0].code,
            "UNSUPPORTED_FURNITURE_TYPE",
        )

    def test_project_store_round_trips_stage_outputs_and_approvals(self) -> None:
        result = self.orchestrator.execute_spec(
            "可恢复项目",
            {"type": "floor_cabinet"},
            through_stage=WorkflowStage.FEATURE_TREE_PLANNED,
        )
        project = result.project

        with tempfile.TemporaryDirectory() as temporary_directory:
            store = JsonProjectStore(temporary_directory)
            store.save(project)
            restored = store.load(project.id)

        self.assertEqual(restored.id, project.id)
        self.assertEqual(restored.latest.stage_outputs, project.latest.stage_outputs)
        self.assertEqual(restored.latest.approved_stages, project.latest.approved_stages)
        self.assertEqual(
            restored.latest.workflow.current,
            WorkflowStage.FEATURE_TREE_PLANNED,
        )

    def test_intent_from_spec_preserves_category_dimension_defaults(self) -> None:
        intent = self.orchestrator.intent_from_spec({"type": "wall_cabinet"})

        self.assertEqual(intent.overall_size.width_mm, 800)
        self.assertEqual(intent.overall_size.depth_mm, 350)
        self.assertEqual(intent.overall_size.height_mm, 900)


if __name__ == "__main__":
    unittest.main()
