from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from backlog_reconcile import reconcile_text, reconcile_workspace


SAMPLE = """\
# panel-plan

<!-- backlog-status:start -->
file_version: 1

## Open

- full-height-divider version 1 — one full-height divider

## Done

- (none)
<!-- backlog-status:end -->

## full-height-divider

Keep this note.
"""


class BacklogReconcileTests(unittest.TestCase):
    def test_open_item_stays_open_until_its_version_lands(self) -> None:
        updated = reconcile_text(SAMPLE, {"full-height-divider": 0})

        self.assertEqual(updated, SAMPLE)

    def test_landed_version_moves_the_item_out_of_open(self) -> None:
        updated = reconcile_text(SAMPLE, {"full-height-divider": 1})

        self.assertIn("file_version: 2", updated)
        self.assertIn("## Open\n\n- (none)\n", updated)
        self.assertIn(
            "## Done\n\n- full-height-divider version 1 — one full-height divider\n",
            updated,
        )
        self.assertIn("## full-height-divider\n\nKeep this note.\n", updated)

    def test_done_item_opens_again_when_the_landed_version_is_older(self) -> None:
        done = reconcile_text(SAMPLE, {"full-height-divider": 1})

        reopened = reconcile_text(done, {"full-height-divider": 0})

        self.assertIn("file_version: 3", reopened)
        self.assertIn(
            "- full-height-divider version 1 — one full-height divider",
            reopened.split("## Done")[0],
        )

    def test_workspace_without_backlog_is_left_alone(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            messages = reconcile_workspace(Path(temporary_directory))

        self.assertEqual(messages, [])


if __name__ == "__main__":
    unittest.main()
