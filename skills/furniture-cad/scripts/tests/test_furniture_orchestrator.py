from __future__ import annotations

import sys
import shutil
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(SCRIPT_ROOT))

from furniture.cad_bridge import CadBridge
from furniture.workflow_orchestrator import FurnitureOrchestrator
from furniture.workflow_store import JsonProjectStore
from furniture.design_intent import DesignIntent, OverallSize
from furniture.workflow_state import WorkflowStage


def cabinet_intent(*, furniture_type: str = "floor_cabinet") -> DesignIntent:
    return DesignIntent(
        furniture_type=furniture_type,
        purpose="测试柜体纵向切片",
        overall_size=OverallSize(width_mm=800, depth_mm=600, height_mm=1000),
        layout={"shelf_count": 2, "n_doors": 2},
    )


class FurnitureOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.orchestrator = FurnitureOrchestrator(workspace_root=WORKSPACE_ROOT)

    def test_confirmed_floor_cabinet_runs_and_tracks_artifacts(self) -> None:
        project = self.orchestrator.create_project("玄关柜", cabinet_intent())
        self.orchestrator.confirm_intent(project)

        with tempfile.TemporaryDirectory() as temporary_directory:
            result = self.orchestrator.run(project, output_root=temporary_directory)

            self.assertIsNotNone(result.pipeline)
            self.assertEqual(
                result.revision.workflow.current,
                WorkflowStage.ARTIFACTS_VERIFIED,
            )
            self.assertTrue(all(report.passed for report in result.revision.validations))
            self.assertEqual(
                {artifact.kind for artifact in result.revision.manifest.artifacts},
                {"design_intent", "feature_tree", "bom", "cad_source"},
            )
            cad_source = next(
                artifact
                for artifact in result.revision.manifest.artifacts
                if artifact.kind == "cad_source"
            )
            self.addCleanup(
                shutil.rmtree,
                Path(cad_source.path).parent,
                ignore_errors=True,
            )
            self.assertTrue(
                Path(cad_source.path).is_relative_to(
                    WORKSPACE_ROOT / "temp" / "cad-source"
                )
            )
            self.assertFalse(any(Path(temporary_directory).rglob("*.py")))

    def test_execute_spec_is_the_named_one_shot_entry(self) -> None:
        artifact_name = f"orchestrator-test-{uuid4().hex}"
        source_dir = WORKSPACE_ROOT / "temp" / "cad-source" / artifact_name
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                result = self.orchestrator.execute_spec(
                    artifact_name,
                    {
                        "type": "floor_cabinet",
                        "width": 900,
                        "depth": 500,
                        "height": 1100,
                        "board_thickness": 20,
                        "shelf_count": 3,
                        "n_doors": 1,
                    },
                    output_root=temporary_directory,
                    artifact_name=artifact_name,
                )

                self.assertIsNotNone(result.pipeline)
                self.assertTrue(result.revision.intent.confirmed)
                self.assertEqual(result.pipeline.spec.board_thickness, 20)
                self.assertEqual(result.pipeline.spec.shelf_count, 3)
                self.assertEqual(result.pipeline.spec.n_doors, 1)
                artifact_paths = {
                    artifact.kind: Path(artifact.path)
                    for artifact in result.revision.manifest.artifacts
                }
                self.assertEqual(
                    artifact_paths["feature_tree"].name,
                    f"{artifact_name}.feature-tree.json",
                )
                self.assertEqual(
                    artifact_paths["bom"].name,
                    f"{artifact_name}.bom.md",
                )
                self.assertTrue(artifact_paths["cad_source"].is_relative_to(source_dir))
        finally:
            shutil.rmtree(source_dir, ignore_errors=True)

    def test_intent_from_spec_preserves_category_dimension_defaults(self) -> None:
        intent = self.orchestrator.intent_from_spec({"type": "wall_cabinet"})

        self.assertEqual(intent.overall_size.width_mm, 800)
        self.assertEqual(intent.overall_size.depth_mm, 350)
        self.assertEqual(intent.overall_size.height_mm, 900)

    def test_new_revision_marks_previous_artifacts_stale(self) -> None:
        project = self.orchestrator.create_project(
            "吊柜", cabinet_intent(furniture_type="wall_cabinet")
        )
        self.orchestrator.confirm_intent(project)
        with tempfile.TemporaryDirectory() as temporary_directory:
            self.orchestrator.run(project, output_root=temporary_directory)
            old_revision = project.latest
            old_source = next(
                artifact
                for artifact in old_revision.manifest.artifacts
                if artifact.kind == "cad_source"
            )
            self.addCleanup(
                shutil.rmtree,
                Path(old_source.path).parent,
                ignore_errors=True,
            )
            self.orchestrator.revise(
                project,
                DesignIntent(
                    furniture_type="wall_cabinet",
                    overall_size=OverallSize(900, 350, 900),
                ),
            )

            self.assertEqual(project.latest.number, 2)
            self.assertEqual(project.latest.parent_revision_id, old_revision.id)
            self.assertTrue(all(item.stale for item in old_revision.manifest.artifacts))

    def test_unconfirmed_intent_does_not_execute(self) -> None:
        project = self.orchestrator.create_project("未确认", cabinet_intent())
        result = self.orchestrator.run(project)

        self.assertIsNone(result.pipeline)
        self.assertEqual(result.revision.workflow.current, WorkflowStage.FAILED)

    def test_unsupported_family_is_reported_without_calling_pipeline(self) -> None:
        project = self.orchestrator.create_project(
            "床", cabinet_intent(furniture_type="bed")
        )
        self.orchestrator.confirm_intent(project)
        result = self.orchestrator.run(project)

        self.assertIsNone(result.pipeline)
        self.assertFalse(result.revision.validations[0].passed)
        self.assertEqual(
            result.revision.validations[0].issues[0].code,
            "UNSUPPORTED_FURNITURE_TYPE",
        )

    def test_project_round_trips_through_json_store(self) -> None:
        project = self.orchestrator.create_project("可恢复项目", cabinet_intent())
        self.orchestrator.confirm_intent(project)
        self.orchestrator.run(project)

        with tempfile.TemporaryDirectory() as temporary_directory:
            store = JsonProjectStore(temporary_directory)
            store.save(project)
            restored = store.load(project.id)

        self.assertEqual(restored.id, project.id)
        self.assertEqual(restored.latest.intent_sha256, project.latest.intent_sha256)
        self.assertEqual(
            restored.latest.workflow.current,
            WorkflowStage.FEATURE_TREE_VALIDATED,
        )

    def test_wall_cabinet_runs_through_cad_bridge_and_manifest(self) -> None:
        project = self.orchestrator.create_project(
            "完整吊柜", cabinet_intent(furniture_type="wall_cabinet")
        )
        self.orchestrator.confirm_intent(project)

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
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
            orchestrator = FurnitureOrchestrator(
                workspace_root=WORKSPACE_ROOT,
                cad_bridge=bridge,
            )
            result = orchestrator.run(
                project,
                output_root=temporary_root,
                generate_cad=True,
            )
            cad_source = next(
                artifact
                for artifact in result.revision.manifest.artifacts
                if artifact.kind == "cad_source"
            )
            self.addCleanup(
                shutil.rmtree,
                Path(cad_source.path).parent,
                ignore_errors=True,
            )

            self.assertEqual(result.bridge.status, "ok")
            self.assertEqual(
                result.revision.workflow.current,
                WorkflowStage.ARTIFACTS_VERIFIED,
            )
            self.assertIn(
                "step", {artifact.kind for artifact in result.revision.manifest.artifacts}
            )
            self.assertIn(
                "viewer_topology",
                {artifact.kind for artifact in result.revision.manifest.artifacts},
            )


if __name__ == "__main__":
    unittest.main()
