from __future__ import annotations

import ast
import unittest
from pathlib import Path


SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }


class EntrypointArchitectureTests(unittest.TestCase):
    def test_cli_and_api_only_import_the_application_orchestrator(self) -> None:
        for filename in ("generate_furniture.py", "server.py"):
            modules = imported_modules(SCRIPTS_ROOT / filename)
            self.assertIn("furniture.workflow_orchestrator", modules)
            self.assertNotIn("furniture.layout_pipeline", modules)
            self.assertNotIn("furniture.feature_tree_emitter", modules)
            self.assertNotIn("furniture.cad_bridge", modules)

    def test_agent_routes_execution_through_the_orchestrator(self) -> None:
        agent_skill = (
            WORKSPACE_ROOT / ".agents" / "skills" / "furniture-agent" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("FurnitureOrchestrator", agent_skill)
        self.assertIn("不得从 Agent 直接调用 `plan_cabinet()`", agent_skill)


if __name__ == "__main__":
    unittest.main()
