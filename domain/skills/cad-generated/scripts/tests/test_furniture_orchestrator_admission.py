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


class FurnitureOrchestratorAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT,
            project_store=None,
        )
    def test_runtime_requires_llm_to_normalize_natural_language_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "furniture_category must be one of"):
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
        self.orchestrator.confirm_layout(project)
        revision = self.orchestrator.run_next(project).revision

        self.assertEqual(revision.workflow.current, WorkflowStage.LAYOUT_PLAN)
        self.assertTrue(revision.is_stage_approved(WorkflowStage.LAYOUT_PLAN))
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
            WorkflowStage.LAYOUT_PLAN,
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
            WorkflowStage.LAYOUT_PLAN,
        )
        self.assertFalse(
            result.revision.latest_attempt(WorkflowStage.PANELS_PLANNED).passed
        )
        self.assertIn(
            "must be numeric",
            result.revision.validations[-1].issues[0].message,
        )

    def test_unsupported_family_fails_before_layout_is_created(self) -> None:
        with self.assertRaisesRegex(ValueError, "furniture_category must be one of"):
            cabinet_intent(furniture_category="bed")

    def test_layout_from_spec_contains_only_category_and_envelope(self) -> None:
        request = {
            "furniture_category": "wall_cabinet",
            "width": 800,
            "depth": 350,
            "height": 900,
            "shelves": [{"shelf_type": "fixed", "gap_below_mm": None}],
            "top_gap_mm": 300,
            "back_mount": "cover",
        }
        layout = self.orchestrator.layout_from_spec(request)
        unit = layout.executable_units()[0]
        self.assertEqual(unit.width, 800)
        self.assertEqual(unit.depth, 350)
        self.assertEqual(unit.height, 900)
        self.assertEqual(
            set(layout.to_dict()),
            {"schema_version", "confirmed", "rooms", "cad"},
        )
        inputs = stage_inputs_from_spec(request)
        self.assertEqual(
            inputs["panels"]["parameters"]["shelves"],
            [{"shelf_type": "fixed", "gap_below_mm": None}],
        )
        self.assertEqual(inputs["panels"]["parameters"]["top_gap_mm"], 300)
        self.assertEqual(inputs["panels"]["parameters"]["back_mount"], "cover")

    def test_flat_request_routes_edge_banding_to_manufacturing(self) -> None:
        inputs = stage_inputs_from_spec(
            {
                "furniture_category": "floor_cabinet",
                "width": 800,
                "depth": 600,
                "height": 1000,
                "edge_banding": {"material": "abs", "thickness": "t1_0"},
            }
        )
        self.assertEqual(
            inputs["manufacturing"]["parameters"]["edge_banding"],
            {"material": "abs", "thickness": "t1_0"},
        )

    def test_flat_requests_reject_legacy_type_field(self) -> None:
        with self.assertRaisesRegex(ValueError, "must use furniture_category"):
            self.orchestrator.layout_from_spec(
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
            WorkflowStage.LAYOUT_PLAN,
        )
        self.assertFalse(
            result.revision.latest_attempt(WorkflowStage.PANELS_PLANNED).passed
        )
        self.assertIn(
            "at most 2 doors",
            result.revision.validations[-1].issues[0].message,
        )

    def test_layout_from_spec_maps_historical_envelope_names(self) -> None:
        layout = self.orchestrator.layout_from_spec(
            {
                "furniture_type": "wall_cabinet",
                "overall_size": {
                    "width_mm": 800,
                    "depth_mm": 350,
                    "height_mm": 900,
                },
                "mounting_height_mm": 1800,
            }
        )
        unit = layout.executable_units()[0]
        self.assertEqual(unit.furniture_category, "wall_cabinet")
        self.assertEqual(unit.height, 900)
        self.assertEqual(unit.origin_z_mm, 1800)

    def test_wall_cabinet_hanging_is_origin_z(self) -> None:
        free = single_cabinet_layout(
            furniture_category="wall_cabinet",
            width=800,
            depth=350,
            height=900,
            origin_z_mm=1800,
            confirmed=True,
        )
        self.assertEqual(free.executable_units()[0].origin_z_mm, 1800)
        flush = single_cabinet_layout(
            furniture_category="wall_cabinet",
            width=800,
            depth=350,
            height=900,
            confirmed=True,
        )
        self.assertGreater(flush.executable_units()[0].origin_z_mm, 0)

    def test_panel_stage_admits_complete_structured_parameters(self) -> None:
        project = self.orchestrator.create_project(
            "直接意图柜体",
            cabinet_intent(),
            stage_inputs=stage_inputs_from_spec(
                panel_parameters()
            ),
        )

        revision = self.orchestrator.confirm_layout(project)
        self.assertNotIn("structure", revision.stage_outputs["layout_plan"])
        with self.assertRaisesRegex(ValueError, "panel proposal is incomplete"):
            plan_panel_stage(panel_envelopes_from_layout(revision.layout), {})
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
