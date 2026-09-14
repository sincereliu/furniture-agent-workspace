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
from furniture_design_intent.design_intent import DesignIntent, FinishedEnvelope
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


class FurnitureOrchestratorAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT,
            project_store=None,
        )
    def test_runtime_requires_llm_to_normalize_natural_language_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "executable canonical category"):
            cabinet_intent(furniture_category="地柜").confirm()

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

        self.assertEqual(revision.workflow.current, WorkflowStage.DESIGN_INTENT)
        self.assertTrue(revision.is_stage_approved(WorkflowStage.DESIGN_INTENT))
        attempt = revision.latest_attempt(WorkflowStage.PANELS_PLANNED)
        self.assertIsNotNone(attempt)
        self.assertFalse(attempt.passed)
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
        result = confirm_through(self.orchestrator, 
            "外盖背板柜体",
            cabinet_data(
                back_mount="cover",
                groove_depth="unused",
                groove_clearance="unused",
                back_rail_height="unused",
            ),
            through_stage=WorkflowStage.PANELS_PLANNED,
        )
        self.assertEqual(
            result.revision.workflow.current,
            WorkflowStage.DESIGN_INTENT,
        )
        self.assertFalse(
            result.revision.latest_attempt(WorkflowStage.PANELS_PLANNED).passed
        )
        self.assertIn(
            "must be numeric",
            result.revision.validations[-1].issues[0].message,
        )

    def test_active_groove_parameters_are_validated_at_panel_stage(self) -> None:
        result = confirm_through(self.orchestrator, 
            "错误入槽参数柜体",
            cabinet_data(back_mount="groove", groove_depth="invalid"),
            through_stage=WorkflowStage.PANELS_PLANNED,
        )
        self.assertEqual(
            result.revision.workflow.current,
            WorkflowStage.DESIGN_INTENT,
        )
        self.assertFalse(
            result.revision.latest_attempt(WorkflowStage.PANELS_PLANNED).passed
        )
        self.assertIn(
            "must be numeric",
            result.revision.validations[-1].issues[0].message,
        )

    def test_unsupported_family_fails_at_design_intent_confirmation(self) -> None:
        project = self.orchestrator.create_project(
            "床", cabinet_intent(furniture_category="bed")
        )
        revision = self.orchestrator.confirm_intent(project)

        self.assertEqual(revision.workflow.current, WorkflowStage.FAILED)
        self.assertFalse(revision.validations[-1].passed)
        self.assertEqual(
            revision.validations[-1].issues[0].code,
            "UNSUPPORTED_FURNITURE_CATEGORY",
        )

    def test_intent_from_spec_contains_only_category_and_envelope(self) -> None:
        request = {
            "furniture_category": "wall_cabinet",
            "width": 800,
            "depth": 350,
            "height": 900,
            "shelves": [{"shelf_type": "fixed", "gap_below_mm": None}],
            "top_gap_mm": 300,
            "back_mount": "cover",
        }
        intent = self.orchestrator.intent_from_spec(request)
        self.assertEqual(intent.finished_envelope.width_mm, 800)
        self.assertEqual(intent.finished_envelope.depth_mm, 350)
        self.assertEqual(intent.finished_envelope.height_mm, 900)
        self.assertEqual(
            set(intent.to_dict()),
            {
                "furniture_category",
                "finished_envelope",
                "hanging_mode",
                "hanging_height_mm",
                "confirmed",
                "schema_version",
            },
        )
        inputs = stage_inputs_from_spec(request)
        self.assertEqual(
            inputs["panels"]["parameters"]["shelves"],
            [{"shelf_type": "fixed", "gap_below_mm": None}],
        )
        self.assertEqual(inputs["panels"]["parameters"]["top_gap_mm"], 300)
        self.assertEqual(inputs["panels"]["parameters"]["back_mount"], "cover")

    def test_flat_requests_reject_legacy_type_field(self) -> None:
        with self.assertRaisesRegex(ValueError, "must use furniture_category"):
            self.orchestrator.intent_from_spec(
                {
                    "type": "wall_cabinet",
                    "width": 800,
                    "depth": 350,
                    "height": 900,
                }
            )
        with self.assertRaisesRegex(ValueError, "must use furniture_category"):
            stage_inputs_from_spec(
                {
                    "type": "wall_cabinet",
                    "width": 800,
                    "depth": 350,
                    "height": 900,
                }
            )

    def test_three_door_request_fails_at_panel_admission(self) -> None:
        result = confirm_through(self.orchestrator, 
            "三门柜体",
            cabinet_data(n_doors=3, shelf_count=0),
            through_stage=WorkflowStage.PANELS_PLANNED,
        )

        self.assertEqual(
            result.revision.workflow.current,
            WorkflowStage.DESIGN_INTENT,
        )
        self.assertFalse(
            result.revision.latest_attempt(WorkflowStage.PANELS_PLANNED).passed
        )
        self.assertIn(
            "at most 2 doors",
            result.revision.validations[-1].issues[0].message,
        )

    def test_design_intent_loads_historical_field_names(self) -> None:
        intent = DesignIntent.from_dict(
            {
                "furniture_type": "wall_cabinet",
                "overall_size": {
                    "width_mm": 800,
                    "depth_mm": 350,
                    "height_mm": 900,
                },
                "mount_mode": "free_height",
                "mounting_height_mm": 1800,
                "schema_version": 2,
            }
        )
        self.assertEqual(intent.furniture_category, "wall_cabinet")
        self.assertEqual(intent.finished_envelope.height_mm, 900)
        self.assertEqual(intent.hanging_mode, "free_hanging_height")
        self.assertEqual(intent.hanging_height_mm, 1800)
        self.assertEqual(intent.schema_version, 3)
        self.assertEqual(
            set(intent.to_dict()),
            {
                "furniture_category",
                "finished_envelope",
                "hanging_mode",
                "hanging_height_mm",
                "confirmed",
                "schema_version",
            },
        )

    def test_design_intent_rejects_new_downstream_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "route later decisions"):
            DesignIntent.from_dict(
                {
                    "furniture_category": "floor_cabinet",
                    "finished_envelope": {
                        "width_mm": 800,
                        "depth_mm": 600,
                        "height_mm": 1000,
                    },
                    "structure": {"back_mount": "cover"},
                }
            )

    def test_wall_cabinet_intent_requires_hanging_mode_before_confirmation(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "hanging_mode"):
            DesignIntent(
                furniture_category="wall_cabinet",
                finished_envelope=FinishedEnvelope(800, 350, 900),
            ).confirm()

        with self.assertRaisesRegex(ValueError, "hanging_height_mm"):
            DesignIntent(
                furniture_category="wall_cabinet",
                finished_envelope=FinishedEnvelope(800, 350, 900),
                hanging_mode="free_hanging_height",
            ).confirm()

        free = DesignIntent(
            furniture_category="wall_cabinet",
            finished_envelope=FinishedEnvelope(800, 350, 900),
            hanging_mode="free_hanging_height",
            hanging_height_mm=1800,
        ).confirm()
        self.assertTrue(free.confirmed)
        self.assertEqual(free.to_dict()["hanging_height_mm"], 1800)

        flush = DesignIntent(
            furniture_category="wall_cabinet",
            finished_envelope=FinishedEnvelope(800, 350, 900),
            hanging_mode="flush_ceiling",
        ).confirm()
        self.assertTrue(flush.confirmed)
        self.assertIsNone(flush.hanging_height_mm)

        floor = DesignIntent(
            furniture_category="floor_cabinet",
            finished_envelope=FinishedEnvelope(800, 600, 1000),
        ).confirm()
        self.assertTrue(floor.confirmed)
        self.assertIsNone(floor.to_dict()["hanging_height_mm"])

        with self.assertRaisesRegex(ValueError, "hanging_mode"):
            DesignIntent(
                furniture_category="floor_cabinet",
                finished_envelope=FinishedEnvelope(800, 600, 1000),
                hanging_mode="free_hanging_height",
                hanging_height_mm=1800,
            ).confirm()
        with self.assertRaisesRegex(ValueError, "hanging_height_mm"):
            DesignIntent(
                furniture_category="floor_cabinet",
                finished_envelope=FinishedEnvelope(800, 600, 1000),
                hanging_height_mm=1800,
            ).confirm()

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
        panel_output = result.revision.stage_outputs["panel_plan"]
        self.assertEqual(first_cabinet_spec(panel_output)["board_thickness"], 18.0)
        self.assertEqual(first_cabinet_spec(panel_output)["back_mount"], "groove")
        self.assertEqual(
            panel_output["cabinets"][0]["interior"]["cavity"]["width"],
            764.0,
        )
        self.assertEqual(
            result.revision.selected_attempts["panel_plan"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
