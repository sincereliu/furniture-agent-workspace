"""Shared results keep their saved shape and historical import identities."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths()

from furniture_contracts.digest import stable_digest
from furniture_contracts.validation import (
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)
from furniture_delivery_validation import validation as delivery_validation
from furniture_workflow import workflow_digest


class SharedValidationTests(unittest.TestCase):
    def test_saved_report_round_trips_without_changing_its_shape(self) -> None:
        payload = {
            "stage": "panel_plan",
            "passed": False,
            "created_at": "2026-10-19T00:00:00+00:00",
            "issues": [
                {"code": "SIZE", "message": "尺寸不合法", "severity": "error", "path": "cabinets[1]"},
                {"code": "REVIEW", "message": "检查饰面", "severity": "warning", "path": ""},
                {"code": "SOURCE", "message": "冻结输入", "severity": "info", "path": "layout"},
            ],
        }
        report = ValidationReport.from_dict(payload)
        self.assertEqual(report.to_dict(), payload)
        self.assertIsInstance(report.issues[0].severity, ValidationSeverity)

    def test_only_errors_prevent_a_stage_from_passing(self) -> None:
        report = ValidationReport(stage="manufacture_plan")
        self.assertTrue(report.passed)
        report.add_warning("PRELIMINARY", "待接受")
        report.issues.append(ValidationIssue("SOURCE", "冻结输入", ValidationSeverity.INFO))
        self.assertTrue(report.passed)
        report.add_error("MISSING_PANEL", "缺少板件", "cabinets[1]")
        self.assertFalse(report.passed)
        self.assertEqual(report.to_dict()["issues"][-1]["path"], "cabinets[1]")

    def test_old_delivery_imports_use_the_shared_types(self) -> None:
        self.assertIs(delivery_validation.ValidationReport, ValidationReport)
        self.assertIs(delivery_validation.ValidationIssue, ValidationIssue)
        self.assertIs(delivery_validation.ValidationSeverity, ValidationSeverity)

    def test_unrecognized_saved_severity_is_still_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ValidationReport.from_dict({
                "stage": "panel_plan",
                "created_at": "2026-10-19T00:00:00+00:00",
                "issues": [{"code": "BAD", "message": "bad", "severity": "unknown"}],
            })


class SharedDigestTests(unittest.TestCase):
    def test_empty_object_keeps_the_existing_canonical_hash(self) -> None:
        self.assertEqual(
            stable_digest({}),
            "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        )

    def test_object_key_order_does_not_change_content_identity(self) -> None:
        self.assertEqual(
            stable_digest({"文字": "值", "b": 1, "a": [2, 3]}),
            stable_digest({"a": [2, 3], "b": 1, "文字": "值"}),
        )
        self.assertNotEqual(stable_digest([2, 3]), stable_digest([3, 2]))

    def test_old_digest_imports_share_the_same_function(self) -> None:
        self.assertIs(workflow_digest.stable_digest, stable_digest)
        self.assertIs(delivery_validation._stable_digest, stable_digest)


if __name__ == "__main__":
    unittest.main()
