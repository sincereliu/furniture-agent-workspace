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

from furniture_workflow import agent_tools
from furniture_workflow.agent_tools import (
    TOOL_CONFIRM_STAGE,
    TOOL_CREATE_PROJECT,
    TOOL_GET_PROJECT,
    TOOL_NAMES,
    TOOL_RETRY_STAGE,
    TOOL_REVISE_LAYOUT,
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

    def test_public_protocol_exports_exist(self) -> None:
        """Every name in __all__ must be defined; stale exports break import *."""
        source = (SCRIPT_ROOT / "furniture_workflow" / "agent_tools.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        exported: list[str] = []
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            ):
                exported = [str(value) for value in ast.literal_eval(node.value)]
        self.assertTrue(exported)
        for name in exported:
            with self.subTest(export=name):
                self.assertIsNotNone(
                    getattr(agent_tools, name, None),
                    f"__all__ lists {name}, but agent_tools does not define it",
                )

    def test_openai_tools_are_the_interactive_protocol_only(self) -> None:
        tools = openai_tools()
        names = [item["function"]["name"] for item in tools]
        self.assertEqual(tuple(names), TOOL_NAMES)
        blob = json.dumps(tools)
        self.assertNotIn("execute_spec", blob)
        self.assertNotIn("plan_cabinet", blob)
        self.assertNotIn("CadBridge", blob)
        self.assertNotIn("n_doors\":", blob.replace(" ", ""))
        self.assertNotIn("include_output", blob)
        self.assertNotIn("current_output", blob)
        self.assertNotIn("allowed_actions", blob)
        self.assertNotIn("waiting_for", blob)
        self.assertIn("include_view", blob)
        self.assertIn("current_view", blob)
        self.assertIn("allowed_tools", blob)
        for item in tools:
            parameters = item["function"]["parameters"]
            self.assertFalse(parameters.get("additionalProperties", True))
            self.assertEqual(item["type"], "function")

    def test_tool_module_does_not_import_planners_or_cad(self) -> None:
        path = SCRIPT_ROOT / "furniture_workflow" / "agent_tools.py"
        modules = imported_modules(path)
        self.assertIn("furniture_layout.project_layout", modules)
        self.assertTrue(
            any(name.endswith("workflow_orchestrator") for name in modules)
        )
        for forbidden in (
            "furniture_workflow.cabinet_pipeline",
            "furniture_panel_planning.panel_pipeline",
            "furniture_manufacturing.manufacturing_bom",
            "furniture_feature_tree.feature_tree_builder",
            "furniture_cad.cad_bridge",
            "furniture_layout.pipeline",
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
        self.assertTrue(created["progressed"])
        self.assertEqual(created["project"]["current_stage"], "layout_plan")
        self.assertEqual(created["project"]["required_tool"], TOOL_CONFIRM_STAGE)
        self.assertIn(TOOL_CONFIRM_STAGE, created["project"]["allowed_tools"])
        self.assertNotIn("advanced", created)
        self.assertNotIn("waiting_for", created["project"])
        self.assertNotIn("allowed_actions", created["project"])
        self.assertNotIn("current_output", created["project"])

        skipped = self.session.call(
            TOOL_RUN_NEXT,
            {"project_id": project_id, "stage_input": panel_parameters()},
        )
        self.assertFalse(skipped["ok"])
        self.assertEqual(skipped["error"]["code"], "STAGE_NOT_CONFIRMED")

        confirmed = self.session.call(
            TOOL_CONFIRM_STAGE,
            {"project_id": project_id, "stage": "layout_plan"},
        )
        self.assertTrue(confirmed["ok"], confirmed)
        self.assertTrue(confirmed["project"]["layout_confirmed"])
        self.assertEqual(confirmed["project"]["required_tool"], TOOL_RUN_NEXT)

        generated = self.session.call(
            TOOL_RUN_NEXT,
            {
                "project_id": project_id,
                "stage_input": panel_parameters(n_doors=2),
            },
        )
        self.assertTrue(generated["ok"], generated)
        self.assertTrue(generated["progressed"])
        self.assertEqual(generated["project"]["current_stage"], "panel_plan")
        self.assertFalse(generated["project"]["current_stage_approved"])
        self.assertEqual(generated["project"]["required_tool"], TOOL_CONFIRM_STAGE)
        self.assertEqual(
            generated["project"]["current_view"]["cabinets"][0]["n_doors"],
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
        intent_sha = first["project"]["layout_sha256"]
        second = self.session.call(
            TOOL_RETRY_STAGE,
            {
                "project_id": project_id,
                "stage": "panel_plan",
                "stage_input": panel_parameters(n_doors=1),
            },
        )
        self.assertTrue(second["ok"], second)
        self.assertEqual(second["project"]["layout_sha256"], intent_sha)
        self.assertEqual(len(second["project"]["attempts"]["panel_plan"]), 2)
        self.assertEqual(
            second["project"]["current_view"]["cabinets"][0]["n_doors"],
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
            selected["project"]["current_view"]["cabinets"][0]["n_doors"],
            2,
        )

    def test_failed_first_attempt_requires_retry_not_run_next(self) -> None:
        project_id = self._confirmed_intent()
        failed = self.session.call(
            TOOL_RUN_NEXT,
            {"project_id": project_id, "stage_input": {"n_doors": 2}},
        )
        self.assertTrue(failed["ok"], failed)
        self.assertEqual(failed["project"]["current_stage"], "layout_plan")
        self.assertTrue(failed["project"]["current_stage_approved"])
        self.assertFalse(failed["project"]["attempts"]["panel_plan"][0]["passed"])
        self.assertEqual(failed["project"]["required_tool"], TOOL_RETRY_STAGE)

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
            TOOL_REVISE_LAYOUT,
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
        self.assertEqual(revised["project"]["current_stage"], "layout_plan")
        self.assertFalse(revised["project"]["layout_confirmed"])
        self.assertEqual(
            revised["project"]["current_view"]["cad"]["units"][0]["furniture_category"],
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

    def test_size_only_shortcut_fit_uses_placeholder_room(self) -> None:
        created = self.session.call(
            TOOL_CREATE_PROJECT,
            {
                "name": "单件快捷",
                "furniture_category": "floor_cabinet",
                "width_mm": 800,
                "depth_mm": 600,
                "height_mm": 2000,
            },
        )
        self.assertTrue(created["ok"], created)

    def test_size_only_shortcut_asks_for_real_room_dimensions(self) -> None:
        """越界时点名占位房间并改问房间尺寸，不把虚构房间当作 caller 的输入。"""
        created = self.session.call(
            TOOL_CREATE_PROJECT,
            {
                "name": "放不进占位房间",
                "furniture_category": "floor_cabinet",
                "width_mm": 800,
                "depth_mm": 600,
                "height_mm": 5000,
            },
        )
        self.assertFalse(created["ok"])
        self.assertEqual(created["error"]["code"], "ROOM_DIMENSIONS_REQUIRED")
        self.assertIsNone(created["project"])
        self.assertIn("rooms[]", created["error"]["message"])

        explicit_rooms = self.session.call(
            TOOL_CREATE_PROJECT,
            {
                "name": "带真实房间",
                "rooms": [
                    {
                        "id": "room_a",
                        "name": "客厅",
                        "width_mm": 4000,
                        "depth_mm": 3000,
                        "height_mm": 5200,
                        "items": [
                            {
                                "id": "cabinet_1",
                                "category": "柜体",
                                "furniture_category": "floor_cabinet",
                                "width": 800,
                                "depth": 600,
                                "height": 5000,
                                "placement": {
                                    "mode": "wall",
                                    "host_wall": "north",
                                    "offset_mm": 0,
                                    "origin_z_mm": 0,
                                },
                            }
                        ],
                    }
                ],
            },
        )
        self.assertTrue(explicit_rooms["ok"], explicit_rooms)

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

        legacy_include = self.session.call(
            TOOL_GET_PROJECT,
            {"project_id": created["project"]["id"], "include_output": False},
        )
        self.assertFalse(legacy_include["ok"])
        self.assertEqual(legacy_include["error"]["code"], "UNKNOWN_ARGUMENT")

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
        output = generated["project"]["current_view"]
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
        self.assertIn("interior", frozen["cabinets"][0])
        self.assertNotIn("structure", frozen["cabinets"][0])
        self.assertNotIn("panels", frozen["cabinets"][0])
        self.assertIn("joints", frozen["cabinets"][0]["assemblies"]["carcass"])
        self.assertNotIn(
            "joints",
            frozen["cabinets"][0]["assemblies"]["carcass"]["panels"][0],
        )

    def test_include_view_false_omits_current_view(self) -> None:
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
            {"project_id": created["project"]["id"], "include_view": False},
        )
        self.assertTrue(summary["ok"])
        self.assertFalse(summary["progressed"])
        self.assertIsNone(summary["project"]["current_view"])

    def test_run_next_wraps_flat_manufacturing_stage_input(self) -> None:
        project_id = self._confirmed_panels(n_doors=1)
        generated = self.session.call(
            TOOL_RUN_NEXT,
            {
                "project_id": project_id,
                "stage_input": {
                    "door_hinge_side": "left",
                    "appearance": _appearance_valid(),
                },
            },
        )
        self.assertTrue(generated["ok"], generated)
        self.assertEqual(generated["project"]["current_stage"], "manufacture_plan")
        view = generated["project"]["current_view"]
        self.assertEqual(view["requested_options"]["door_hinge_side"], "left")
        self.assertEqual(view["appearance"], _appearance_valid())
        self.assertNotIn("appearance", view["requested_options"])

    def test_nested_manufacturing_stage_input_still_works(self) -> None:
        project_id = self._confirmed_panels(n_doors=1)
        generated = self.session.call(
            TOOL_RUN_NEXT,
            {
                "project_id": project_id,
                "stage_input": {
                    "parameters": {"door_hinge_side": "right"},
                    "appearance": _appearance_valid(),
                },
            },
        )
        self.assertTrue(generated["ok"], generated)
        view = generated["project"]["current_view"]
        self.assertEqual(view["requested_options"]["door_hinge_side"], "right")
        self.assertEqual(view["appearance"], _appearance_valid())

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

    def _confirmed_panels(self, **panel_overrides: object) -> str:
        project_id = self._confirmed_intent()
        generated = self.session.call(
            TOOL_RUN_NEXT,
            {
                "project_id": project_id,
                "stage_input": panel_parameters(**panel_overrides),
            },
        )
        self.assertTrue(generated["ok"], generated)
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
        from furniture_layout.project_layout import ProjectLayout, single_cabinet_layout

        project = orchestrator.create_project(
            "首次板件输入",
            single_cabinet_layout(furniture_category="floor_cabinet", width=800, depth=600, height=1000, confirmed=True),
        )
        orchestrator.confirm_stage(project)
        result = orchestrator.run_next(
            project,
            stage_input=panel_parameters(n_doors=1),
        )
        spec = result.revision.stage_outputs["panel_plan"]["cabinets"][0]["spec"]
        self.assertEqual(spec["n_doors"], 1)

    def test_run_next_wraps_flat_manufacturing_stage_input(self) -> None:
        from furniture_layout.project_layout import ProjectLayout, single_cabinet_layout

        orchestrator = FurnitureOrchestrator(workspace_root=WORKSPACE_ROOT)
        project = orchestrator.create_project(
            "扁平制造输入",
            single_cabinet_layout(furniture_category="floor_cabinet", width=800, depth=600, height=1000, confirmed=True),
        )
        orchestrator.confirm_stage(project)
        orchestrator.run_next(project, stage_input=panel_parameters(n_doors=1))
        orchestrator.confirm_stage(project)
        result = orchestrator.run_next(
            project,
            stage_input={
                "door_hinge_side": "left",
                "appearance": _appearance_valid(),
            },
        )
        stored = result.revision.stage_inputs["manufacturing"]
        self.assertEqual(stored["parameters"]["door_hinge_side"], "left")
        self.assertNotIn("door_hinge_side", stored)
        self.assertEqual(stored["appearance"], _appearance_valid())
        self.assertEqual(
            result.revision.stage_outputs["manufacture_plan"]["requested_options"][
                "door_hinge_side"
            ],
            "left",
        )


def _appearance_valid() -> dict[str, dict[str, str]]:
    return {
        "carcass": {
            "substrate": "particleboard",
            "surface": "white__soft_touch__plain",
        },
        "door": {
            "substrate": "particleboard",
            "surface": "oak__double_faced__grain",
        },
        "back": {
            "substrate": "particleboard",
            "surface": "white__double_faced__plain",
        },
    }


if __name__ == "__main__":
    unittest.main()
