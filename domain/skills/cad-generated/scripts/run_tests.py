"""Run the whole integration test suite with the stage packages on sys.path.

The test modules bootstrap their own imports through ``runtime_paths``; this
script only supplies the shared test directory and discovery parameters, so a
checkout can run every test with one documented command.
"""

from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_ROOT.parents[3]
TESTS_ROOT = SCRIPT_ROOT / "tests"

sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths


def _suite(pattern: str) -> unittest.TestSuite:
    bootstrap_runtime_paths(WORKSPACE_ROOT)
    if str(TESTS_ROOT) not in sys.path:
        sys.path.insert(0, str(TESTS_ROOT))
    return unittest.TestLoader().discover(
        str(TESTS_ROOT),
        pattern=pattern,
        top_level_dir=str(TESTS_ROOT),
    )


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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run every test under cad-generated/scripts/tests."
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="also list every case that did not fail, error, or skip",
    )
    parser.add_argument(
        "--pattern",
        "-p",
        default="test_*.py",
        help="glob for a single test module, e.g. -p test_panel_rule_contracts.py",
    )
    args = parser.parse_args()

    suite = _suite(args.pattern)
    # unittest discards each executed case from the suite, so snapshot first.
    all_ids = [_test_id(test) for test in _flatten(suite)]
    print(f"Discovered {len(all_ids)} tests in {TESTS_ROOT}", flush=True)

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
            "e.g. references/backlog.md, and drop its expectedFailure marker):"
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
