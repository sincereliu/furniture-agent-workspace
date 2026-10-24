"""Run explicitly selected tests with the stage packages on sys.path.

The test modules bootstrap their own imports through ``runtime_paths``; this
script supplies stage/module test directories and discovery parameters, so a
checkout can run focused tests or request the whole suite with --all.
"""

from __future__ import annotations

import argparse
import os
import sys
import unittest
from pathlib import Path

# Creating a project opens a browser. Tests must not.
os.environ["FURNITURE_PREVIEW_BROWSER"] = "0"


SCRIPT_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_ROOT.parents[3]
TESTS_ROOT = SCRIPT_ROOT / "tests"

sys.path.insert(0, str(SCRIPT_ROOT))

from backlog_reconcile import reconcile_workspace
from runtime_paths import (
    AI_MODULE_RELATIVE_ROOT,
    bootstrap_runtime_paths,
    stage_script_roots,
)

TEST_ROOTS = (
    *(root / "tests" for root in stage_script_roots(WORKSPACE_ROOT)
      if (root / "tests").is_dir()),
    WORKSPACE_ROOT / AI_MODULE_RELATIVE_ROOT / "tests",
)


def _suite(
    pattern: str | list[str], name_patterns: list[str] | None = None,
) -> unittest.TestSuite:
    bootstrap_runtime_paths(WORKSPACE_ROOT)
    for tests_root in TEST_ROOTS:
        if str(tests_root) not in sys.path:
            sys.path.insert(0, str(tests_root))
    patterns = [pattern] if isinstance(pattern, str) else pattern
    cases: dict[str, unittest.TestCase] = {}
    for tests_root in TEST_ROOTS:
        for module_pattern in patterns:
            loader = unittest.TestLoader()
            loader.testNamePatterns = name_patterns
            discovered = loader.discover(
                str(tests_root), pattern=module_pattern, top_level_dir=str(tests_root),
            )
            if loader.errors:
                raise ImportError("\n".join(loader.errors))
            for case in _flatten(discovered):
                cases.setdefault(case.id(), case)
    return unittest.TestSuite(cases.values())


def _flatten(suite: unittest.TestSuite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _flatten(item)
        elif item is not None:
            yield item


def _test_id(test: unittest.TestCase) -> str:
    test_id = test.id()
    marker = ".tests."
    index = test_id.find(marker)
    if index >= 0:
        return test_id[index + len(marker):]
    return test_id


def _unique(cases) -> list[str]:
    """Keep report order while collapsing a case reported more than once."""
    seen: dict[str, None] = {}
    for case in cases:
        seen.setdefault(_test_id(case), None)
    return list(seen)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run stage integration tests and independent AI module tests."
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="also list every case that did not fail, error, or skip",
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--pattern",
        "-p",
        action="append",
        help="test module glob; repeat -p to select several files",
    )
    selection.add_argument(
        "--all", action="store_true", help="explicitly request the whole Python suite",
    )
    parser.add_argument(
        "-k", action="append", default=[], metavar="NAME",
        help="case-sensitive test ID substring or * glob; repeated -k values are ORed",
    )
    parser.add_argument(
        "--list", action="store_true", dest="list_only",
        help="list selected test IDs without running tests or reconciling backlog",
    )
    args = parser.parse_args(argv)

    name_patterns = [name if "*" in name else f"*{name}*" for name in args.k]
    try:
        suite = _suite(args.pattern or "test_*.py", name_patterns or None)
    except ImportError as error:
        parser.error(str(error))
    # unittest discards each executed case from the suite, so snapshot first.
    all_ids = [_test_id(test) for test in _flatten(suite)]
    if not all_ids:
        parser.error("no tests matched; check -p / -k (use --list to preview selection)")
    print(f"Selected {len(all_ids)} tests in {len(TEST_ROOTS)} test roots", flush=True)
    if args.list_only:
        for test_id in all_ids:
            print(f"  {test_id}")
        return 0

    repo_root = SCRIPT_ROOT.parents[4]
    for message in reconcile_workspace(repo_root):
        print(message, flush=True)
        if message.startswith("error:"):
            return 1

    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)

    error_ids = _unique(case for case, _ in result.errors)
    failed_ids = _unique(case for case, _ in result.failures)
    skipped_ids = _unique(case for case, _ in result.skipped)
    unexpected_ids = _unique(result.unexpectedSuccesses)
    broken = (
        set(error_ids) | set(failed_ids) | set(skipped_ids) | set(unexpected_ids)
    )
    healthy = [test_id for test_id in all_ids if test_id not in broken]

    if args.verbose:
        print("\nnot failed, errored, or skipped:")
        for test_id in healthy:
            print(f"  PASS {test_id}")

    if skipped_ids:
        print("\nskipped:")
        for test_id in skipped_ids:
            print(f"  SKIP {test_id}")

    if failed_ids:
        print("\nfailed:")
        for test_id in failed_ids:
            print(f"  FAIL {test_id}")

    if error_ids:
        print("\nerrors:")
        for test_id in error_ids:
            print(f"  ERROR {test_id}")

    if unexpected_ids:
        print(
            "\nunexpected pass (a known gap closed - update the gap's record, "
            "e.g. backlog/<stage>.md, set its landed version, and drop its expectedFailure marker):"
        )
        for test_id in unexpected_ids:
            print(f"  UNEXPECTED-PASS {test_id}")

    # A case that fails in both the test body and tearDown is reported twice,
    # so count unique cases rather than raw report entries.
    print(
        f"\nran {result.testsRun}, failed {len(failed_ids)}, "
        f"errored {len(error_ids)}, skipped {len(skipped_ids)}, "
        f"unexpectedly passed {len(unexpected_ids)}, "
        f"of {len(all_ids)} discovered"
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
