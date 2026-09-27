from __future__ import annotations

import ast
import unittest
from pathlib import Path


SCRIPTS_ROOT = Path(__file__).resolve().parents[1]


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }


class EntrypointArchitectureTests(unittest.TestCase):
    def test_serial_entrypoints_only_import_the_application_orchestrator(self) -> None:
        self.assertFalse((SCRIPTS_ROOT / "generate_furniture.py").exists())
        self.assertFalse(
            (SCRIPTS_ROOT / "furniture_workflow" / "planner.py").exists()
        )
        orchestrator = (
            SCRIPTS_ROOT / "furniture_workflow" / "workflow_orchestrator.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("def execute_spec(", orchestrator)
        self.assertNotIn("auto_confirm", orchestrator)
        pipeline = (
            SCRIPTS_ROOT / "furniture_workflow" / "cabinet_pipeline.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("def plan_cabinet(", pipeline)
        self.assertIn("class CabinetPipelineResult", pipeline)

        server_modules = imported_modules(SCRIPTS_ROOT / "server.py")
        self.assertIn("furniture_layout", server_modules)
        self.assertNotIn("furniture_workflow.workflow_orchestrator", server_modules)
        self.assertNotIn("furniture_feature_tree.feature_tree_emitter", server_modules)
        self.assertNotIn("furniture_cad.cad_bridge", server_modules)
        # 页面写项目（P3）走 workflow 侧门面：门面才驱动 orchestrator，HTTP 层不自己开。
        layout_edit_modules = imported_modules(
            SCRIPTS_ROOT / "furniture_workflow" / "project_layout_edit.py"
        )
        self.assertIn("workflow_orchestrator", layout_edit_modules)
        self.assertIn("furniture_layout.project_edit", layout_edit_modules)
        server_text = (SCRIPTS_ROOT / "server.py").read_text(encoding="utf-8")
        self.assertNotIn("/api/plan-cabinet", server_text)
        self.assertNotIn("/api/plan-layout", server_text)
        self.assertNotIn("execute_spec", server_text)
        room_http = (
            SCRIPTS_ROOT.parents[1]
            / "layout-plan"
            / "scripts"
            / "furniture_layout"
            / "room_http.py"
        ).read_text(encoding="utf-8")
        self.assertIn("/api/plan-room", room_http)
        self.assertIn("include_router(room_http.router)", server_text)
        self.assertIn(
            "furniture_layout.pipeline",
            imported_modules(
                SCRIPTS_ROOT.parents[1]
                / "layout-plan"
                / "scripts"
                / "furniture_layout"
                / "room_http.py"
            ),
        )

        tool_modules = imported_modules(
            SCRIPTS_ROOT / "furniture_workflow" / "agent_tools.py"
        )
        self.assertIn("workflow_orchestrator", tool_modules)
        self.assertNotIn("cabinet_pipeline", tool_modules)
        self.assertNotIn("furniture_panel_planning.panel_pipeline", tool_modules)
        self.assertNotIn("furniture_cad.cad_bridge", tool_modules)


if __name__ == "__main__":
    unittest.main()
