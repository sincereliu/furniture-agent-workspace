"""设计意图阶段的验证逻辑。"""

from __future__ import annotations

from furniture_delivery_validation.validation import ValidationReport

from .design_intent import DesignIntent
from .design_spec import SUPPORTED_TYPES
from .translation import spec_from_intent


EXECUTABLE_LAYOUT_FIELDS = frozenset(
    {
        "shelf_count",
        "n_doors",
        "toe_kick_height",
    }
)


def validate_intent(intent: DesignIntent) -> ValidationReport:
    report = ValidationReport(stage="design_intent")
    intent_errors = intent.validate()
    for error in intent_errors:
        report.add_error("INVALID_INTENT", error)
    if intent.furniture_type not in SUPPORTED_TYPES:
        report.add_error(
            "UNSUPPORTED_FURNITURE_TYPE",
            f"supported vertical slice: {', '.join(sorted(SUPPORTED_TYPES))}",
            "furniture_type",
        )
    if intent.unresolved:
        report.add_error(
            "UNRESOLVED_DECISIONS",
            "DesignIntent still contains unresolved decisions",
            "unresolved",
        )
    unsupported_layout_fields = sorted(
        set(intent.layout) - EXECUTABLE_LAYOUT_FIELDS
    )
    if intent.furniture_type in SUPPORTED_TYPES and unsupported_layout_fields:
        report.add_error(
            "UNSUPPORTED_LAYOUT_DECISION",
            "current cabinet layout runtime does not execute: "
            + ", ".join(unsupported_layout_fields),
            "layout",
        )
    if (
        intent.furniture_type in SUPPORTED_TYPES
        and not intent_errors
        and not unsupported_layout_fields
    ):
        for error in spec_from_intent(intent).validation_errors():
            report.add_error("INVALID_CABINET_SPEC", error, "structure")
    return report
