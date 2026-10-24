from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

import run_tests


class TestRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for module, methods in {
            "test_runner_fixture_a": ("test_alpha", "test_beta"),
            "test_runner_fixture_b": ("test_gamma",),
        }.items():
            source = "import unittest\nclass Example(unittest.TestCase):\n"
            source += "".join(f"    def {name}(self): pass\n" for name in methods)
            (self.root / f"{module}.py").write_text(source, encoding="utf-8")
        self.addCleanup(self._clean_imports)
        self.enterContext(patch.object(run_tests, "TEST_ROOTS", (self.root,)))

    def _clean_imports(self) -> None:
        for name in list(sys.modules):
            if name.startswith("test_runner_fixture_"):
                del sys.modules[name]
        if str(self.root) in sys.path:
            sys.path.remove(str(self.root))

    def invoke(self, *args: str) -> tuple[int, str]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            try:
                status = run_tests.main(list(args))
            except SystemExit as error:
                status = error.code
        return status, output.getvalue()

    def test_multiple_patterns_are_unioned_without_running_duplicates(self) -> None:
        with patch.object(run_tests, "reconcile_workspace", return_value=[]):
            status, output = self.invoke(
                "-p", "test_runner_fixture_*.py", "-p", "test_runner_fixture_a.py",
            )
        self.assertEqual(status, 0, output)
        self.assertIn("ran 3, failed 0, errored 0", output)

    def test_name_filters_support_substrings_globs_and_or_semantics(self) -> None:
        status, output = self.invoke(
            "-p", "test_runner_fixture_*.py", "-k", "alpha",
            "-k", "*.Example.test_g*", "--list",
        )
        self.assertEqual(status, 0, output)
        self.assertIn("Selected 2 tests", output)
        self.assertIn("Example.test_alpha", output)
        self.assertIn("Example.test_gamma", output)
        self.assertNotIn("Example.test_beta", output)

    def test_listing_does_not_execute_cases_or_reconcile_backlog(self) -> None:
        with patch.object(run_tests, "reconcile_workspace") as reconcile:
            with patch.object(unittest.TextTestRunner, "run") as execute:
                status, output = self.invoke("--all", "--list")
        self.assertEqual(status, 0, output)
        self.assertIn("Selected 3 tests", output)
        reconcile.assert_not_called()
        execute.assert_not_called()

    def test_missing_selection_does_not_discover_or_run_everything(self) -> None:
        with patch.object(run_tests, "_suite") as discover:
            status, _ = self.invoke()
        self.assertEqual(status, 2)
        discover.assert_not_called()

    def test_all_cannot_silently_override_a_file_selection(self) -> None:
        status, _ = self.invoke("--all", "-p", "test_runner_fixture_a.py")
        self.assertEqual(status, 2)

    def test_empty_file_or_name_selection_is_an_error(self) -> None:
        for args in (
            ("-p", "test_runner_fixture_missing.py"),
            ("-p", "test_runner_fixture_a.py", "-k", "missing"),
        ):
            with self.subTest(args=args):
                status, output = self.invoke(*args)
                self.assertEqual(status, 2)
                self.assertIn("no tests matched", output)

    def test_unselected_broken_module_is_not_imported(self) -> None:
        (self.root / "test_runner_fixture_broken.py").write_text(
            "raise RuntimeError('broken fixture')\n", encoding="utf-8",
        )
        status, output = self.invoke("-p", "test_runner_fixture_a.py", "--list")
        self.assertEqual(status, 0, output)
        self.assertIn("Selected 2 tests", output)

    def test_import_failure_is_an_error_even_when_listing_with_a_name_filter(self) -> None:
        (self.root / "test_runner_fixture_broken.py").write_text(
            "raise RuntimeError('broken fixture')\n", encoding="utf-8",
        )
        status, output = self.invoke(
            "-p", "test_runner_fixture_broken.py", "-k", "missing", "--list",
        )
        self.assertEqual(status, 2)
        self.assertIn("broken fixture", output)

    def test_selected_failure_returns_nonzero(self) -> None:
        (self.root / "test_runner_fixture_fail.py").write_text(
            "import unittest\nclass Example(unittest.TestCase):\n"
            "    def test_failure(self): self.fail('intentional failure')\n",
            encoding="utf-8",
        )
        with patch.object(run_tests, "reconcile_workspace", return_value=[]):
            status, output = self.invoke("-p", "test_runner_fixture_fail.py")
        self.assertEqual(status, 1)
        self.assertIn("ran 1, failed 1, errored 0", output)


if __name__ == "__main__":
    unittest.main()
