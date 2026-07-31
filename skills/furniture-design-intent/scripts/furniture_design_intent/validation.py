"""设计意图阶段的验证逻辑。"""

from __future__ import annotations

from furniture_delivery_validation.validation import ValidationReport

from .design_intent import DesignIntent
from .design_spec import SUPPORTED_TYPES, VALID_BACK_MOUNTS


EXECUTABLE_LAYOUT_FIELDS = frozenset(
    {
        "shelf_count",
        "n_doors",
        "toe_kick_height",
    }
)

EXECUTABLE_STRUCTURE_FIELDS = frozenset(
    {
        "board_thickness",
        "back_thickness",
        "door_thickness",
        "back_offset",
        "door_margin",
        "door_hinge_gap",
        "groove_depth",
        "groove_clearance",
        "toe_kick_reveal_front",
        "toe_kick_reveal_back",
        "toe_kick_support_count",
        "back_mount",
        "back_rail_height",
        "hinge_brand",
        "hinge_variant",
        "hinge_overlay",
        "hinge_angle",
        "options",
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
    unsupported_structure_fields = sorted(
        set(intent.structure) - EXECUTABLE_STRUCTURE_FIELDS
    )
    if intent.furniture_type in SUPPORTED_TYPES and unsupported_structure_fields:
        report.add_error(
            "UNSUPPORTED_STRUCTURE_DECISION",
            "current cabinet runtime does not execute: "
            + ", ".join(unsupported_structure_fields),
            "structure",
        )
    for name in ("board_thickness", "back_thickness", "door_thickness"):
        value = intent.structure.get(name)
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or value <= 0
        ):
            report.add_error(
                "INVALID_INTENT_VALUE",
                f"{name} must be a positive number",
                f"structure.{name}",
            )
    back_mount = intent.structure.get("back_mount")
    if back_mount is not None and str(back_mount).strip().lower() not in VALID_BACK_MOUNTS:
        report.add_error(
            "INVALID_INTENT_VALUE",
            "back_mount must be one of: "
            + ", ".join(sorted(VALID_BACK_MOUNTS)),
            "structure.back_mount",
        )
    for name in ("shelf_count", "n_doors"):
        value = intent.layout.get(name)
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
        ):
            report.add_error(
                "INVALID_INTENT_VALUE",
                f"{name} must be a non-negative integer",
                f"layout.{name}",
            )
    return report
