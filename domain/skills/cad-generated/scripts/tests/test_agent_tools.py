from __future__ import annotations

import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_workflow.agent_tools import (
    TOOL_CONFIRM_STAGE,
    TOOL_CREATE_PROJECT,
    TOOL_GET_PROJECT,
    TOOL_NAMES,
    TOOL_RETRY_STAGE,
    TOOL_REVISE_INTENT,
    TOOL_RUN_NEXT,
    TOOL_SELECT_ATTEMPT,
    FurnitureToolSession,
    openai_tools,
)
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_state import STAGE_SEQUENCE, WorkflowStage
from furniture_workflow.workflow_store import JsonProjectStore
from panel_fixtures import panel_parameters


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    return names


class AgentToolSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = JsonProjectStore(self.temporary.name)
        self.session = FurnitureToolSession(
            FurnitureOrchestrator(
                workspace_root=WORKSPACE_ROOT,
                project_store=self.store,
            )
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_openai_tools_are_the_interactive_protocol_only(self) -> None:
        tools = openai_tools()
        names = [item["function"]["name"] for item in tools]
        self.assertEqual(tuple(names), TOOL_NAMES)
        blob = json.dumps(tools)
        self.assertNotIn("execute_spec", blob)
        self.assertNotIn("plan_cabinet", blob)
        self.assertNotIn("CadBridge", blob)
        self.assertNotIn("n_doors\":", blob.replace(" ", ""))
        for item in tools:
            parameters = item["function"]["parameters"]
            self.assertFalse(parameters.get("additionalProperties", True))
            self.assertEqual(item["type"], "function")

    def test_tool_module_does_not_import_planners_or_cad(self) -> None:
        path = SCRIPT_ROOT / "furniture_workflow" / "agent_tools.py"
        modules = imported_modules(path)
        self.assertIn("furniture_design_intent.design_intent", modules)
        self.assertTrue(
            any(name.endswith("workflow_orchestrator") for name in modules)
        )
        for forbidden in (
            "furniture_workflow.cabinet_pipeline",
            "furniture_panel_planning.panel_pipeline",
            "furniture_manufacturing.manufacturing_bom",
            "furniture_feature_tree.feature_tree_builder",
            "furniture_cad.cad_bridge",
            "furniture_layout.layout_pipeline",
        ):
            self.assertNotIn(forbidden, modules)

    def test_create_confirm_and_run_next_pause_after_panels(self) -> None:
        created = self.session.call(
            TOOL_CREATE_PROJECT,
            {
                "name": "工具面柜",
                "furniture_category": "floor_cabinet",
                "width_mm": 800,
                "depth_mm": 600,
                "height_mm": 1000,
            },
        )
        self.assertTrue(created["ok"], created)
        project_id = created["project"]["id"]
        self.assertEqual(created["project"]["current_stage"], "design_intent")
        self.assertEqual(created["project"]["waiting_for"], TOOL_CONFIRM_STAGE)
        self.assertIn(TOOL_CONFIRM_STAGE, created["project"]["allowed_actions"])

        skipped = self.session.call(
            TOOL_RUN_NEXT,
            {"project_id": project_id, "stage_input": panel_parameters()},
        )
        self.assertFalse(skipped["ok"])
        self.assertEqual(skipped["error"]["code"], "STAGE_NOT_CONFIRMED")

        confirmed = self.session.call(
            TOOL_CONFIRM_STAGE,
            {"project_id": project_id, "stage": "design_intent"},
        )
        self.assertTrue(confirmed["ok"], confirmed)
        self.assertTrue(confirmed["project"]["intent_confirmed"])
        self.assertEqual(confirmed["project"]["waiting_for"], TOOL_RUN_NEXT)

        generated = self.session.call(
            TOOL_RUN_NEXT,
            {
                "project_id": project_id,
                "stage_input": panel_parameters(n_doors=2),
            },
        )
        self.assertTrue(generated["ok"], generated)
        self.assertTrue(generated["advanced"])
        self.assertEqual(generated["project"]["current_stage"], "panel_plan")
        self.assertFalse(generated["project"]["current_stage_approved"])
        self.assertEqual(generated["project"]["waiting_for"], TOOL_CONFIRM_STAGE)
        self.assertEqual(
            generated["project"]["current_output"]["cabinets"][0]["n_doors"],
            2,
        )

        paused = self.session.call(TOOL_RUN_NEXT, {"project_id": project_id})
        self.assertFalse(paused["ok"])
        self.assertEqual(paused["error"]["code"], "STAGE_NOT_CONFIRMED")

    def test_retry_and_select_attempt_use_frozen_intent(self) -> None:
        project_id = self._confirmed_intent()
        first = self.session.call(
            TOOL_RUN_NEXT,
            {
                "project_id": project_id,
                "stage_input": panel_parameters(n_doors=2),
            },
        )
        intent_sha = first["project"]["intent_sha256"]
        second = self.session.call(
            TOOL_RETRY_STAGE,
            {
                "project_id": project_id,
                "stage": "panel_plan",
                "stage_input": panel_parameters(n_doors=1),
            },
        )
        self.assertTrue(second["ok"], second)
        self.assertEqual(second["project"]["intent_sha256"], intent_sha)
        self.assertEqual(len(second["project"]["attempts"]["panel_plan"]), 2)
        self.assertEqual(
            second["project"]["current_output"]["cabinets"][0]["n_doors"],
            1,
        )

        skipped = self.session.call(
            TOOL_RUN_NEXT,
            {"project_id": project_id, "stage_input": panel_parameters()},
        )
        self.assertFalse(skipped["ok"])
        self.assertEqual(skipped["error"]["code"], "STAGE_NOT_CONFIRMED")

        selected = self.session.call(
            TOOL_SELECT_ATTEMPT,
            {"project_id": project_id, "stage": "panel_plan", "number": 1},
        )
        self.assertTrue(selected["ok"], selected)
        self.assertEqual(
            selected["project"]["current_output"]["cabinets"][0]["n_doors"],
            2,
        )

    def test_failed_first_attempt_requires_retry_not_run_next(self) -> None:
        project_id = self._confirmed_intent()
        failed = self.session.call(
            TOOL_RUN_NEXT,
            {"project_id": project_id, "stage_input": {"n_doors": 2}},
        )
        self.assertTrue(failed["ok"], failed)
        self.assertEqual(failed["project"]["current_stage"], "design_intent")
        self.assertTrue(failed["project"]["current_stage_approved"])
        self.assertFalse(failed["project"]["attempts"]["panel_plan"][0]["passed"])
        self.assertEqual(failed["project"]["waiting_for"], TOOL_RETRY_STAGE)

        reused = self.session.call(
            TOOL_RUN_NEXT,
            {"project_id": project_id, "stage_input": panel_parameters()},
        )
        self.assertFalse(reused["ok"])
        self.assertEqual(reused["error"]["code"], "USE_RETRY_STAGE")

        recovered = self.session.call(
            TOOL_RETRY_STAGE,
            {
                "project_id": project_id,
                "stage": "panel_plan",
                "stage_input": panel_parameters(),
            },
        )
        self.assertTrue(recovered["ok"], recovered)
        self.assertEqual(recovered["project"]["current_stage"], "panel_plan")
        self.assertTrue(recovered["project"]["attempts"]["panel_plan"][1]["passed"])

    def test_revise_intent_starts_a_new_revision(self) -> None:
        project_id = self._confirmed_intent()
        self.session.call(
            TOOL_RUN_NEXT,
            {"project_id": project_id, "stage_input": panel_parameters()},
        )
        revised = self.session.call(
            TOOL_REVISE_INTENT,
            {
                "project_id": project_id,
                "furniture_category": "wall_cabinet",
                "width_mm": 900,
                "depth_mm": 350,
                "height_mm": 800,
                "hanging_mode": "flush_ceiling",
            },
        )
        self.assertTrue(revised["ok"], revised)
        self.assertEqual(revised["project"]["revision_number"], 2)
        self.assertEqual(revised["project"]["current_stage"], "design_intent")
        self.assertFalse(revised["project"]["intent_confirmed"])
        self.assertEqual(
            revised["project"]["current_output"]["furniture_category"],
            "wall_cabinet",
        )
        self.assertNotIn("panel_plan", revised["project"]["attempts"])

    def test_cad_requires_explicit_generate_cad(self) -> None:
        project_id = self._through_feature_tree()
        refused = self.session.call(TOOL_RUN_NEXT, {"project_id": project_id})
        self.assertFalse(refused["ok"])
        self.assertEqual(refused["error"]["code"], "CAD_REQUIRES_GENERATE_CAD")
        self.assertEqual(refused["project"]["current_stage"], "feature_tree_planned")
        self.assertTrue(refused["project"]["cad_generation_required"])

    def test_unknown_fields_and_legacy_aliases_are_rejected(self) -> None:
        alias = self.session.call(
            TOOL_CREATE_PROJECT,
            {
                "name": "别名",
                "furniture_category": "floor_cabinet",
                "furniture_type": "floor_cabinet",
                "width_mm": 800,
                "depth_mm": 600,
                "height_mm": 1000,
            },
        )
        self.assertFalse(alias["ok"])
        self.assertEqual(alias["error"]["code"], "UNKNOWN_ARGUMENT")

        created = self.session.call(
            TOOL_CREATE_PROJECT,
            {
                "name": "规范",
                "furniture_category": "floor_cabinet",
                "width_mm": 800,
                "depth_mm": 600,
                "height_mm": 1000,
            },
        )
        unknown_tool = self.session.call("execute_spec", {"project_id": created["project"]["id"]})
        self.assertFalse(unknown_tool["ok"])
        self.assertEqual(unknown_tool["error"]["code"], "UNKNOWN_TOOL")

        unknown_field = self.session.call(
            TOOL_GET_PROJECT,
            {"project_id": created["project"]["id"], "prompt": "做个柜子"},
        )
        self.assertFalse(unknown_field["ok"])
        self.assertEqual(unknown_field["error"]["code"], "UNKNOWN_ARGUMENT")

    def test_json_argument_string_and_store_reload(self) -> None:
        created = self.session.call(
            TOOL_CREATE_PROJECT,
            json.dumps(
                {
                    "name": "重载",
                    "furniture_category": "floor_cabinet",
                    "width_mm": 800,
                    "depth_mm": 600,
                    "height_mm": 1000,
                }
            ),
        )
        project_id = created["project"]["id"]
        reloaded = FurnitureToolSession(
            FurnitureOrchestrator(
                workspace_root=WORKSPACE_ROOT,
                project_store=self.store,
            )
        )
        loaded = reloaded.call(TOOL_GET_PROJECT, {"project_id": project_id})
        self.assertTrue(loaded["ok"], loaded)
        self.assertEqual(loaded["project"]["name"], "重载")
        self.assertEqual(loaded["project"]["stage_sequence"], [
            stage.value for stage in STAGE_SEQUENCE
        ])

    def test_panel_plan_snapshot_is_confirmation_review(self) -> None:
        project_id = self._confirmed_intent()
        generated = self.session.call(
            TOOL_RUN_NEXT,
            {
                "project_id": project_id,
                "stage_input": panel_parameters(n_doors=2),
            },
        )
        self.assertTrue(generated["ok"], generated)
        output = generated["project"]["current_output"]
        cabinet = output["cabinets"][0]
        self.assertIn("markdown", output)
        self.assertEqual(cabinet["n_doors"], 2)
        self.assertNotIn("spec", cabinet)
        self.assertNotIn("structure", cabinet)
        self.assertNotIn("joints", cabinet["panels"][0])
        self.assertNotIn("connection", cabinet["contacts"][0])
        self.assertIn("内部净空", output["markdown"])

        confirmed = self.session.call(
            TOOL_CONFIRM_STAGE,
            {"project_id": project_id, "stage": "panel_plan"},
        )
        self.assertTrue(confirmed["ok"], confirmed)
        digest = confirmed["project"]["confirmed_panel_sha256"]
        frozen = json.loads(
            self.store.panel_path(project_id, digest).read_text(encoding="utf-8")
        )
        self.assertEqual(set(frozen), {"cabinets"})
        self.assertIn("spec", frozen["cabinets"][0])
        self.assertIn("joints", frozen["cabinets"][0]["panels"][0])

    def test_include_output_false_omits_current_output(self) -> None:
        created = self.session.call(
            TOOL_CREATE_PROJECT,
            {
                "name": "摘要",
                "furniture_category": "floor_cabinet",
                "width_mm": 800,
                "depth_mm": 600,
                "height_mm": 1000,
            },
        )
        summary = self.session.call(
            TOOL_GET_PROJECT,
            {"project_id": created["project"]["id"], "include_output": False},
        )
        self.assertTrue(summary["ok"])
        self.assertIsNone(summary["project"]["current_output"])

    def _confirmed_intent(self) -> str:
        created = self.session.call(
            TOOL_CREATE_PROJECT,
            {
                "name": "已确认意图",
                "furniture_category": "floor_cabinet",
                "width_mm": 800,
                "depth_mm": 600,
                "height_mm": 1000,
            },
        )
        project_id = created["project"]["id"]
        confirmed = self.session.call(
            TOOL_CONFIRM_STAGE,
            {"project_id": project_id},
        )
        self.assertTrue(confirmed["ok"], confirmed)
        return project_id

    def _through_feature_tree(self) -> str:
        project_id = self._confirmed_intent()
        for stage_input in (panel_parameters(), None, None):
            payload: dict = {"project_id": project_id}
            if stage_input is not None:
                payload["stage_input"] = stage_input
            generated = self.session.call(TOOL_RUN_NEXT, payload)
            self.assertTrue(generated["ok"], generated)
            confirmed = self.session.call(
                TOOL_CONFIRM_STAGE,
                {"project_id": project_id},
            )
            self.assertTrue(confirmed["ok"], confirmed)
        latest = self.session.call(TOOL_GET_PROJECT, {"project_id": project_id})
        self.assertEqual(
            latest["project"]["current_stage"],
            WorkflowStage.FEATURE_TREE_PLANNED.value,
        )
        self.assertTrue(latest["project"]["current_stage_approved"])
        self.assertTrue(latest["project"]["cad_generation_required"])
        return project_id


class OrchestratorRunNextStageInputTests(unittest.TestCase):
    def test_run_next_accepts_first_panel_stage_input(self) -> None:
        orchestrator = FurnitureOrchestrator(workspace_root=WORKSPACE_ROOT)
        from furniture_design_intent.design_intent import DesignIntent, FinishedEnvelope

        project = orchestrator.create_project(
            "首次板件输入",
            DesignIntent(
                furniture_category="floor_cabinet",
                finished_envelope=FinishedEnvelope(800, 600, 1000),
            ),
        )
        orchestrator.confirm_stage(project)
        result = orchestrator.run_next(
            project,
            stage_input=panel_parameters(n_doors=1),
        )
        spec = result.revision.stage_outputs["panel_plan"]["cabinets"][0]["spec"]
        self.assertEqual(spec["n_doors"], 1)


if __name__ == "__main__":
    unittest.main()
