from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(SCRIPT_ROOT))

from validate_workspace_layout import find_violations


class WorkspaceLayoutTests(unittest.TestCase):
    def test_live_workspace_uses_only_two_script_surfaces(self) -> None:
        self.assertEqual(find_violations(WORKSPACE_ROOT), [])

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
