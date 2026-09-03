from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from validate_workspace_layout import find_violations


class WorkspaceLayoutTests(unittest.TestCase):
    def test_live_workspace_uses_only_stage_skills_and_temp(self) -> None:
        self.assertEqual(find_violations(WORKSPACE_ROOT), [])

    def test_accepts_stage_owned_script_and_rejects_unrelated_skill_script(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            stage_scripts = root / "domain" / "skills" / "layout-plan" / "scripts"
            stage_scripts.mkdir(parents=True)
            (stage_scripts / "layout.py").write_text("pass\n", encoding="utf-8")
            unrelated_scripts = root / "domain" / "skills" / "other-skill" / "scripts"
            unrelated_scripts.mkdir(parents=True)
            (unrelated_scripts / "tool.py").write_text("pass\n", encoding="utf-8")

            violations = find_violations(root)

        self.assertEqual(
            violations,
            ["script outside allowed locations: domain/skills/other-skill/scripts/tool.py"],
        )

    def test_rejects_root_code_tree_and_generated_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "scripts").mkdir()
            (root / "generated").mkdir()
            (root / "generated" / "model.py").write_text("pass\n", encoding="utf-8")

            violations = find_violations(root)

        self.assertIn("forbidden top-level code tree: scripts/", violations)
        self.assertIn(
            "script outside allowed locations: generated/model.py", violations
        )


if __name__ == "__main__":
    unittest.main()
