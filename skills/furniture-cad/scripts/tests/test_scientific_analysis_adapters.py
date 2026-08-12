from __future__ import annotations

from copy import deepcopy
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_delivery_validation.validation import validate_delivery
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_state import WorkflowStage
from furniture_workflow.workflow_store import JsonProjectStore


def cabinet_spec() -> dict[str, object]:
    return {
        "type": "floor_cabinet",
        "width": 800,
        "depth": 600,
        "height": 1000,
        "shelf_count": 2,
        "n_doors": 2,
    }


class ScientificAnalysisAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.orchestrator = FurnitureOrchestrator(workspace_root=WORKSPACE_ROOT)

    def _project_through(self, stage: WorkflowStage):
        return self.orchestrator.execute_spec(
            "科学分析测试柜",
            cabinet_spec(),
            through_stage=stage,
        ).project

    def test_unit_audit_is_side_evidence_and_persists(self) -> None:
        project = self._project_through(WorkflowStage.PANELS_PLANNED)
        before = deepcopy(project.latest.stage_outputs)

        record = self.orchestrator.run_stage_analysis(
            project,
            "panel_unit_audit",
            {
                "uncertainties": {
                    "width": {
                        "uncertainty": 0.5,
                        "unit": "mm",
                        "kind": "limit",
                        "distribution": "rectangular",
                    },
                    "board_thickness": {
                        "uncertainty": 0.1,
                        "unit": "mm",
                        "kind": "standard",
                    },
                }
            },
        )

        self.assertEqual(record["method_skill"], "uncertainty-and-units")
        self.assertTrue(record["report"]["passed"])
        self.assertEqual(project.latest.stage_outputs, before)
        self.assertIn(
            "panel_unit_audit",
            project.latest.stage_analyses[WorkflowStage.PANELS_PLANNED.value],
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            store = JsonProjectStore(temporary_directory)
            store.save(project)
            loaded = store.load(project.id)
        loaded_record = loaded.latest.stage_analyses[
            WorkflowStage.PANELS_PLANNED.value
        ]["panel_unit_audit"]
        self.assertEqual(loaded_record["source_sha256"], record["source_sha256"])

    def test_pareto_candidate_requires_explicit_new_revision(self) -> None:
        project = self._project_through(WorkflowStage.MANUFACTURING_PLANNED)
        parent = project.latest
        source_output = deepcopy(
            parent.stage_outputs[WorkflowStage.PANELS_PLANNED.value]
        )

        record = self.orchestrator.run_stage_analysis(
            project,
            "panel_optimization",
            {
                "engine": "auto",
                "variables": {"board_thickness": [15.0, 18.0]},
                "objectives": [
                    "material_volume_m3",
                    "negative_internal_volume_m3",
                ],
            },
        )

        self.assertEqual(record["method_skill"], "pymoo")
        self.assertEqual(record["report"]["status"], "completed")
        self.assertEqual(
            parent.stage_outputs[WorkflowStage.PANELS_PLANNED.value],
            source_output,
        )
        self.assertGreaterEqual(len(record["report"]["candidates"]), 1)

        revised = self.orchestrator.apply_panel_optimization_candidate(project, 0)
        self.assertNotEqual(revised.id, parent.id)
        self.assertEqual(revised.parent_revision_id, parent.id)
        self.assertIn(WorkflowStage.PANELS_PLANNED.value, revised.stage_outputs)
        self.assertNotIn(
            WorkflowStage.MANUFACTURING_PLANNED.value,
            revised.stage_outputs,
        )
        self.assertEqual(revised.stage_analyses, {})

    def test_experiment_statistics_and_production_are_manufacturing_evidence(self) -> None:
        project = self._project_through(WorkflowStage.MANUFACTURING_PLANNED)
        before = deepcopy(project.latest.stage_outputs)

        experiment = self.orchestrator.run_stage_analysis(
            project,
            "prototype_experiment",
            {
                "factors": {
                    "edge_band_temperature_c": [180, 200],
                    "feed_rate_m_min": [8, 12],
                },
                "responses": ["bond_strength_n"],
                "independent_unit": "test_panel",
                "replicates": 2,
                "blocks": ["day-1", "day-2"],
                "seed": 17,
            },
        )
        self.assertEqual(experiment["method_skill"], "experimental-design")
        self.assertEqual(experiment["report"]["run_count"], 8)

        statistics = self.orchestrator.run_stage_analysis(
            project,
            "test_statistics",
            {
                "records": [
                    {"process": "A", "strength": 10.0},
                    {"process": "A", "strength": 11.0},
                    {"process": "A", "strength": 10.5},
                    {"process": "B", "strength": 13.0},
                    {"process": "B", "strength": 12.5},
                    {"process": "B", "strength": 13.5},
                ],
                "group_field": "process",
                "value_field": "strength",
            },
        )
        self.assertEqual(statistics["method_skill"], "statistical-analysis")
        self.assertIn(statistics["status"], {"completed", "descriptive_only"})
        self.assertEqual(statistics["report"]["descriptives"]["A"]["n"], 3)

        production = self.orchestrator.run_stage_analysis(
            project,
            "production_simulation",
            {
                "resources": {
                    "cutting": 1,
                    "edge_banding": 1,
                    "drilling": 1,
                    "assembly": 1,
                },
                "routes": {
                    "*": [
                        {"resource": "cutting", "duration_min": 2.0},
                        {"resource": "edge_banding", "duration_min": 1.0},
                        {"resource": "drilling", "duration_min": 0.5},
                    ]
                },
                "assembly": {"resource": "assembly", "duration_min": 10.0},
                "replications": 3,
                "duration_cv": 0.1,
                "seed": 23,
            },
        )
        self.assertEqual(production["method_skill"], "simpy")
        self.assertEqual(production["status"], "completed")
        self.assertGreater(production["report"]["summary"]["mean_makespan_min"], 0)
        self.assertEqual(project.latest.stage_outputs, before)

    def test_delivery_reports_stale_analysis_hash(self) -> None:
        project = self._project_through(WorkflowStage.PANELS_PLANNED)
        revision = project.latest
        self.orchestrator.run_stage_analysis(project, "panel_unit_audit")
        revision.stage_outputs[WorkflowStage.PANELS_PLANNED.value]["spec"][
            "board_thickness"
        ] = 19.0

        report = validate_delivery(
            revision.manifest,
            source_revision_id=revision.id,
            stage_outputs=revision.stage_outputs,
            approved_stages=revision.approved_stages,
            stage_validations=revision.validations,
            stage_analyses=revision.stage_analyses,
        )
        self.assertIn(
            "ANALYSIS_SOURCE_HASH_MISMATCH",
            {issue.code for issue in report.issues},
        )


if __name__ == "__main__":
    unittest.main()
