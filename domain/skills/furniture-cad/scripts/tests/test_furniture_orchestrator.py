from __future__ import annotations

from copy import deepcopy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_cad.cad_bridge import CadBridge
from furniture_delivery_validation.validation import validate_delivery
from furniture_design_intent.design_intent import DesignIntent, OverallSize
from furniture_workflow.input_adapter import stage_inputs_from_spec
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_project import Project
from furniture_workflow.workflow_state import STAGE_SEQUENCE, WorkflowStage
from furniture_workflow.workflow_store import JsonProjectStore
from furniture_panel_planning.panel_pipeline import plan_panel_stage
from panel_fixtures import cabinet_data, panel_parameters


def cabinet_intent(*, furniture_type: str = "floor_cabinet") -> DesignIntent:
    return DesignIntent(
        furniture_type=furniture_type,
        overall_size=OverallSize(width_mm=800, depth_mm=600, height_mm=1000),
    )


def fake_orchestrator(temporary_root: Path) -> FurnitureOrchestrator:
    launcher_path = temporary_root / "fake_gen.py"
    launcher_path.write_text(
        "\n".join(
            [
                "import json",
                "import sys",
                "from pathlib import Path",
                "source = Path(sys.argv[1])",
                "output = Path(sys.argv[sys.argv.index('--write') + 1])",
                "output.parent.mkdir(parents=True, exist_ok=True)",
                "output.write_text('STEP', encoding='utf-8')",
                "package = source.parent / '__cadgen__' / 'models' / source.name",
                "component = package / 'components' / 'fake.glb'",
                "component.parent.mkdir(parents=True, exist_ok=True)",
                "component.write_bytes(b'GLB')",
                "(package / 'assembly.json').write_text(json.dumps({'components': {'fake': {'glb': 'components/fake.glb'}}}), encoding='utf-8')",
                "print(json.dumps({'ok': True, 'packagePath': package.as_posix()}))",
            ]
        ),
        encoding="utf-8",
    )
    bridge = CadBridge(
        workspace_root=WORKSPACE_ROOT,
        python_executable=sys.executable,
        gen_launcher=launcher_path,
    )
    return FurnitureOrchestrator(
        workspace_root=WORKSPACE_ROOT,
        cad_bridge=bridge,
    )


class FurnitureOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.orchestrator = FurnitureOrchestrator(workspace_root=WORKSPACE_ROOT)

    def test_interactive_workflow_pauses_at_every_stage(self) -> None:
        project = self.orchestrator.create_project(
            "玄关柜",
            cabinet_intent(),
            stage_inputs=stage_inputs_from_spec(
                panel_parameters()
            ),
        )
        revision = project.latest

        self.assertEqual(revision.workflow.current, WorkflowStage.DESIGN_INTENT)
        self.assertEqual(
            set(revision.stage_outputs),
            {WorkflowStage.DESIGN_INTENT.value},
        )

        self.orchestrator.confirm_intent(project)
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

    def test_revising_panels_invalidates_and_regenerates_downstream(self) -> None:
        result = self.orchestrator.execute_spec(
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
            parent.intent,
            panel_parameters(shelf_count=1, n_doors=2),
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
                WorkflowStage.DESIGN_INTENT.value,
                WorkflowStage.PANELS_PLANNED.value,
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

        self.orchestrator.confirm_stage(project, WorkflowStage.PANELS_PLANNED)
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

    def test_revised_single_door_hinge_side_must_match_spec(self) -> None:
        result = self.orchestrator.execute_spec(
            "右铰单门柜",
            cabinet_data(n_doors=1, door_hinge_side="right"),
            through_stage=WorkflowStage.PANELS_PLANNED,
        )
        edited = deepcopy(
            result.revision.stage_outputs[WorkflowStage.PANELS_PLANNED.value]
        )
        door = next(
            panel for panel in edited["panels"] if panel["panel_type"] == "door"
        )
        door["door_hinge_side"] = "left"

        revision = self.orchestrator.revise_stage_output(
            result.project,
            WorkflowStage.PANELS_PLANNED,
            edited,
        )
        self.orchestrator.confirm_stage(
            result.project,
            WorkflowStage.PANELS_PLANNED,
        )

        self.assertEqual(revision.workflow.current, WorkflowStage.FAILED)
        self.assertIn(
            "DOOR_HINGE_SIDE_MISMATCH",
            {issue.code for issue in revision.validations[-1].issues},
        )

    def test_named_batch_generation_records_all_six_serial_stages(self) -> None:
        artifact_name = f"orchestrator-test-{uuid4().hex}"
        source_dir = WORKSPACE_ROOT / "temp" / "cad-source" / artifact_name
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                temporary_root = Path(temporary_directory)
                orchestrator = fake_orchestrator(temporary_root)
                result = orchestrator.execute_spec(
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
                        "design_intent",
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
        result = self.orchestrator.execute_spec(
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
                result = orchestrator.execute_spec(
                    artifact_name,
                    cabinet_data("wall_cabinet"),
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
                        mounting_height_mm=2000,
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

    def test_unconfirmed_intent_pauses_without_executing_panels(self) -> None:
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
            WorkflowStage.PANELS_PLANNED.value,
            result.revision.stage_outputs,
        )
        self.assertNotIn("layout_planned", result.revision.stage_outputs)

    def test_serial_workflow_skips_room_layout_even_when_context_is_supplied(self) -> None:
        result = self.orchestrator.execute_spec(
            "带房间信息的柜体",
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
            ),
            through_stage=WorkflowStage.PANELS_PLANNED,
        )

        self.assertEqual(
            result.revision.workflow.current,
            WorkflowStage.PANELS_PLANNED,
        )
        self.assertNotIn("layout_planned", result.revision.stage_outputs)
        self.assertIn("panels_planned", result.revision.stage_outputs)

    def test_draft_intent_preserves_null_dimensions_and_cannot_confirm(self) -> None:
        intent = DesignIntent.from_dict(
            {
                "furniture_type": "floor_cabinet",
                "overall_size": {
                    "width_mm": 800,
                    "depth_mm": None,
                    "height_mm": 1000,
                },
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

    def test_runtime_requires_llm_to_normalize_natural_language_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "executable canonical type"):
            cabinet_intent(furniture_type="地柜").confirm()

    def test_unsupported_layout_decision_is_rejected_by_independent_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "layout input only accepts"):
            stage_inputs_from_spec(
                {"layout": {"unsupported_layout_option": 2}}
            )

    def test_unsupported_structure_decision_fails_at_panel_stage(self) -> None:
        project = self.orchestrator.create_project(
            "未知连接柜体",
            cabinet_intent(),
            stage_inputs=stage_inputs_from_spec(
                {"structure": {"mystery_joint": "unknown"}}
            ),
        )
        self.orchestrator.confirm_intent(project)
        revision = self.orchestrator.run_next(project).revision

        self.assertEqual(revision.workflow.current, WorkflowStage.FAILED)
        self.assertIn("panel stage does not support", revision.validations[-1].issues[0].message)

    def test_unclassified_constraint_is_rejected_by_protocol_routing(self) -> None:
        with self.assertRaisesRegex(ValueError, "has no stage mapping"):
            stage_inputs_from_spec({"constraints": ["必须提供防倾倒固定"]})

    def test_constraints_require_explicit_executable_or_informational_destinations(
        self,
    ) -> None:
        inputs = stage_inputs_from_spec(
            {
                "back_mount": "cover",
                "constraints": ["背板必须外盖", "仅供卧室方案比较"],
                "constraint_mappings": {
                    "背板必须外盖": "structure.back_mount",
                    "仅供卧室方案比较": "informational",
                },
            }
        )
        self.assertEqual(
            inputs["panels"]["constraints"][0]["target"],
            "structure.back_mount",
        )
        self.assertEqual(inputs["informational_constraints"], ["仅供卧室方案比较"])

    def test_malformed_dormant_parameters_fail_structured_admission(self) -> None:
        result = self.orchestrator.execute_spec(
            "外盖背板柜体",
            cabinet_data(
                back_mount="cover",
                groove_depth="unused",
                groove_clearance="unused",
                back_rail_height="unused",
            ),
            through_stage=WorkflowStage.PANELS_PLANNED,
        )
        self.assertEqual(result.revision.workflow.current, WorkflowStage.FAILED)
        self.assertIn(
            "must be numeric",
            result.revision.validations[-1].issues[0].message,
        )

    def test_active_groove_parameters_are_validated_at_panel_stage(self) -> None:
        result = self.orchestrator.execute_spec(
            "错误入槽参数柜体",
            cabinet_data(back_mount="groove", groove_depth="invalid"),
            through_stage=WorkflowStage.PANELS_PLANNED,
        )
        self.assertEqual(result.revision.workflow.current, WorkflowStage.FAILED)
        self.assertIn(
            "must be numeric",
            result.revision.validations[-1].issues[0].message,
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

    def test_legacy_projects_migrate_only_recoverable_hinge_sides(self) -> None:
        payloads: list[tuple[dict, str | None]] = []
        for door_count, hinge_side in ((1, "right"), (2, None)):
            result = self.orchestrator.execute_spec(
                f"旧项目-{door_count}",
                cabinet_data(
                    n_doors=door_count,
                    door_hinge_side=hinge_side,
                ),
                through_stage=WorkflowStage.PANELS_PLANNED,
            )
            payload = deepcopy(result.project.to_dict())
            raw_revision = payload["revisions"][-1]
            raw_revision["stage_outputs"]["panels_planned"]["spec"].pop(
                "door_hinge_side"
            )
            raw_revision["stage_inputs"]["panels"]["parameters"].pop(
                "door_hinge_side"
            )
            if door_count == 2:
                for panel in raw_revision["stage_outputs"]["panels_planned"][
                    "panels"
                ]:
                    if panel["panel_type"] == "door":
                        panel.pop("door_hinge_side")
            payloads.append((payload, hinge_side))

        for payload, expected_side in payloads:
            with self.subTest(expected_side=expected_side):
                restored = Project.from_dict(payload)
                revision = restored.latest
                self.assertEqual(
                    revision.stage_outputs["panels_planned"]["spec"][
                        "door_hinge_side"
                    ],
                    expected_side,
                )
                self.assertEqual(
                    revision.stage_inputs["panels"]["parameters"][
                        "door_hinge_side"
                    ],
                    expected_side,
                )
                if expected_side is None:
                    migrated_doors = sorted(
                        (
                            panel
                            for panel in revision.stage_outputs["panels_planned"][
                                "panels"
                            ]
                            if panel["panel_type"] == "door"
                        ),
                        key=lambda panel: panel["pos_x"],
                    )
                    self.assertEqual(
                        [panel["door_hinge_side"] for panel in migrated_doors],
                        ["left", "right"],
                    )
                continued = self.orchestrator.run_next(restored)
                self.assertEqual(
                    continued.revision.workflow.current,
                    WorkflowStage.MANUFACTURING_PLANNED,
                )
                self.assertTrue(continued.revision.validations[-1].passed)

        invalid_single = deepcopy(payloads[0][0])
        invalid_door = next(
            panel
            for panel in invalid_single["revisions"][-1]["stage_outputs"][
                "panels_planned"
            ]["panels"]
            if panel["panel_type"] == "door"
        )
        invalid_door["door_hinge_side"] = None
        with self.assertRaisesRegex(ValueError, "explicit panel door_hinge_side"):
            Project.from_dict(invalid_single)

    def test_intent_from_spec_contains_only_category_and_envelope(self) -> None:
        request = {
            "type": "wall_cabinet",
            "width": 800,
            "depth": 350,
            "height": 900,
            "shelf_count": 1,
            "back_mount": "cover",
        }
        intent = self.orchestrator.intent_from_spec(request)
        self.assertEqual(intent.overall_size.width_mm, 800)
        self.assertEqual(intent.overall_size.depth_mm, 350)
        self.assertEqual(intent.overall_size.height_mm, 900)
        self.assertEqual(
            set(intent.to_dict()),
            {
                "furniture_type",
                "overall_size",
                "mounting_height_mm",
                "confirmed",
                "schema_version",
            },
        )
        inputs = stage_inputs_from_spec(request)
        self.assertEqual(inputs["panels"]["parameters"]["shelf_count"], 1)
        self.assertEqual(inputs["panels"]["parameters"]["back_mount"], "cover")

    def test_design_intent_rejects_new_downstream_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "route later decisions"):
            DesignIntent.from_dict(
                {
                    "furniture_type": "floor_cabinet",
                    "overall_size": {
                        "width_mm": 800,
                        "depth_mm": 600,
                        "height_mm": 1000,
                    },
                    "structure": {"back_mount": "cover"},
                }
            )

    def test_wall_cabinet_intent_requires_mounting_height_before_confirmation(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "mounting_height_mm"):
            DesignIntent(
                furniture_type="wall_cabinet",
                overall_size=OverallSize(800, 350, 900),
            ).confirm()

        confirmed = DesignIntent(
            furniture_type="wall_cabinet",
            overall_size=OverallSize(800, 350, 900),
            mounting_height_mm=1800,
        ).confirm()
        self.assertTrue(confirmed.confirmed)
        self.assertEqual(confirmed.to_dict()["mounting_height_mm"], 1800)

        floor = DesignIntent(
            furniture_type="floor_cabinet",
            overall_size=OverallSize(800, 600, 1000),
        ).confirm()
        self.assertTrue(floor.confirmed)
        self.assertIsNone(floor.to_dict()["mounting_height_mm"])

    def test_panel_stage_admits_complete_structured_parameters(self) -> None:
        project = self.orchestrator.create_project(
            "直接意图柜体",
            cabinet_intent(),
            stage_inputs=stage_inputs_from_spec(
                panel_parameters()
            ),
        )

        revision = self.orchestrator.confirm_intent(project)
        self.assertNotIn("structure", revision.stage_outputs["design_intent"])
        with self.assertRaisesRegex(ValueError, "panel proposal is incomplete"):
            plan_panel_stage(revision.intent, {})
        result = self.orchestrator.run_next(project)
        panel_output = result.revision.stage_outputs["panels_planned"]
        self.assertEqual(panel_output["spec"]["board_thickness"], 18.0)
        self.assertEqual(panel_output["structure"]["back_mount"], "groove")


if __name__ == "__main__":
    unittest.main()
