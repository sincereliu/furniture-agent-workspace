"""Validation for the finished-envelope intent stage."""

from __future__ import annotations

from furniture_delivery_validation.validation import ValidationReport

from .design_intent import DesignIntent, EXECUTABLE_CATEGORIES


def validate_intent(intent: DesignIntent) -> ValidationReport:
    report = ValidationReport(stage="design_intent")
    intent_errors = intent.validate()
    for error in intent_errors:
        report.add_error("INVALID_INTENT", error)
    if intent.furniture_category not in EXECUTABLE_CATEGORIES:
        report.add_error(
            "UNSUPPORTED_FURNITURE_CATEGORY",
            f"supported vertical slice: {', '.join(sorted(EXECUTABLE_CATEGORIES))}",
            "furniture_category",
        )
    return report
