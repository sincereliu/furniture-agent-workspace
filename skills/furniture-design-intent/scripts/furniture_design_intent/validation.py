"""Validation owned by the design-intent stage."""

from __future__ import annotations

from furniture_delivery_validation.validation import ValidationReport

from .design_intent import DesignIntent
from .design_spec import SUPPORTED_TYPES
from .translation import spec_from_intent


def validate_intent(intent: DesignIntent) -> ValidationReport:
    report = ValidationReport(stage="design_intent")
    for error in intent.validate():
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
    if intent.furniture_type in SUPPORTED_TYPES:
        for error in spec_from_intent(intent).validation_errors():
            report.add_error("INVALID_CABINET_SPEC", error, "structure")
    return report
