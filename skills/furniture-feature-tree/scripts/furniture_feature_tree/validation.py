"""Validation owned by the feature-tree-planning stage."""

from __future__ import annotations

from typing import Any

from furniture_delivery_validation.validation import ValidationReport

from .feature_tree_emitter import validate_feature_tree as validate_feature_tree_contract


def validate_feature_tree(feature_tree: dict[str, Any]) -> ValidationReport:
    report = ValidationReport(stage="feature_tree_planned")
    try:
        validate_feature_tree_contract(feature_tree)
    except ValueError as exc:
        report.add_error("INVALID_FEATURE_TREE", str(exc))
    return report
