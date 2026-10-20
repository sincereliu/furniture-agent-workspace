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
    def test_live_workspace_uses_stages_ai_module_and_temp(self) -> None:
        self.assertEqual(find_violations(WORKSPACE_ROOT), [])

    def test_accepts_ai_module_but_does_not_open_arbitrary_module_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            ai = root / "domain/modules/ai/furniture_ai"
            ai.mkdir(parents=True)
            (ai / "service.py").write_text("pass\n", encoding="utf-8")
            self.assertEqual(find_violations(root), [])
            unrelated = root / "domain/modules/unrelated"
            unrelated.mkdir()
            (unrelated / "tool.py").write_text("pass\n", encoding="utf-8")
            self.assertEqual(find_violations(root), [
                "script outside allowed locations: domain/modules/unrelated/tool.py",
            ])

    def test_root_launcher_is_the_only_script_allowed_at_the_root(self) -> None:
        """根目录只放行那一个双击启动器；换一个名字或再加一个都要被拦住。"""
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "open_last_project.bat").write_text("@echo off\n", encoding="utf-8")
            self.assertEqual(find_violations(root), [])

            (root / "another_launcher.bat").write_text("@echo off\n", encoding="utf-8")
            violations = find_violations(root)

        self.assertEqual(
            violations, ["script outside allowed locations: another_launcher.bat"]
        )

    def test_accepts_stage_owned_script_and_rejects_unrelated_stage_script(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            stage_scripts = root / "domain" / "stages" / "layout-plan" / "scripts"
            stage_scripts.mkdir(parents=True)
            (stage_scripts / "layout.py").write_text("pass\n", encoding="utf-8")
            unrelated_scripts = root / "domain" / "stages" / "other-stage" / "scripts"
            unrelated_scripts.mkdir(parents=True)
            (unrelated_scripts / "tool.py").write_text("pass\n", encoding="utf-8")

            violations = find_violations(root)

        self.assertEqual(
            violations,
            ["script outside allowed locations: domain/stages/other-stage/scripts/tool.py"],
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
