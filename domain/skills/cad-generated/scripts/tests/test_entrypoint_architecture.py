from __future__ import annotations

import ast
import unittest
from pathlib import Path


SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]


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
        orchestrator = (
            SCRIPTS_ROOT / "furniture_workflow" / "workflow_orchestrator.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("def execute_spec(", orchestrator)
        self.assertNotIn("auto_confirm", orchestrator)

        server_modules = imported_modules(SCRIPTS_ROOT / "server.py")
        self.assertIn("furniture_workflow.workflow_orchestrator", server_modules)
        self.assertIn("furniture_layout.layout_pipeline", server_modules)
        self.assertNotIn("furniture_feature_tree.feature_tree_emitter", server_modules)
        self.assertNotIn("furniture_cad.cad_bridge", server_modules)
        server_text = (SCRIPTS_ROOT / "server.py").read_text(encoding="utf-8")
        self.assertNotIn("/api/plan-cabinet", server_text)
        self.assertNotIn("execute_spec", server_text)

        tool_modules = imported_modules(
            SCRIPTS_ROOT / "furniture_workflow" / "agent_tools.py"
        )
        self.assertIn("workflow_orchestrator", tool_modules)
        self.assertNotIn("cabinet_pipeline", tool_modules)
        self.assertNotIn("furniture_panel_planning.panel_pipeline", tool_modules)
        self.assertNotIn("furniture_cad.cad_bridge", tool_modules)

    def test_agent_routes_execution_through_the_orchestrator(self) -> None:
        agent_skill = (
            WORKSPACE_ROOT / ".agents" / "skills" / "furniture-agent" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("FurnitureOrchestrator", agent_skill)
        self.assertIn("FurnitureToolSession", agent_skill)
        self.assertIn("不得从 Agent 直接调用 `plan_cabinet()`", agent_skill)
        self.assertIn("generate_cad=True", agent_skill)
        self.assertNotIn("$cad-generated", agent_skill)
        self.assertNotIn("domain/skills/cad-generated/SKILL.md", agent_skill)


if __name__ == "__main__":
    unittest.main()
