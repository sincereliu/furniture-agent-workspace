"""设计意图阶段的验证逻辑。"""

from __future__ import annotations

from furniture_delivery_validation.validation import ValidationReport

from .design_intent import DesignIntent
from .design_spec import FurnitureSpec, SUPPORTED_TYPES, VALID_BACK_MOUNTS


EXECUTABLE_LAYOUT_FIELDS = frozenset(
    {
        "shelf_count",
        "n_doors",
        "toe_kick_height",
        "room",
        "placement",
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

INFORMATIONAL_CONSTRAINT = "informational"
EXECUTABLE_CONSTRAINT_TARGETS = frozenset(
    {
        "furniture_type",
        "overall_size.width_mm",
        "overall_size.depth_mm",
        "overall_size.height_mm",
        *(f"layout.{name}" for name in EXECUTABLE_LAYOUT_FIELDS),
        *(
            f"structure.{name}"
            for name in EXECUTABLE_STRUCTURE_FIELDS
            if name != "options"
        ),
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
    _validate_constraint_mappings(intent, report)
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
    for name in ("room", "placement"):
        value = intent.layout.get(name)
        if value is not None and not isinstance(value, dict):
            report.add_error(
                "INVALID_INTENT_VALUE",
                f"{name} must be an object",
                f"layout.{name}",
            )
    if report.passed and intent.furniture_type in SUPPORTED_TYPES:
        data = {
            "type": intent.furniture_type,
            "width": intent.overall_size.width_mm,
            "depth": intent.overall_size.depth_mm,
            "height": intent.overall_size.height_mm,
            **intent.structure,
            **intent.layout,
        }
        try:
            FurnitureSpec.from_dict(data)
        except (TypeError, ValueError) as exc:
            report.add_error(
                "INVALID_INTENT_VALUE",
                str(exc),
                "structure",
            )
    return report


def _validate_constraint_mappings(
    intent: DesignIntent,
    report: ValidationReport,
) -> None:
    constraints: set[str] = set()
    for index, constraint in enumerate(intent.constraints):
        if not isinstance(constraint, str) or not constraint.strip():
            report.add_error(
                "INVALID_CONSTRAINT",
                "constraints must contain non-empty strings",
                f"constraints[{index}]",
            )
            continue
        constraints.add(constraint)
        target = intent.constraint_mappings.get(constraint)
        if target is None:
            report.add_error(
                "UNCLASSIFIED_CONSTRAINT",
                "constraint must map to an executable intent field or be explicitly informational",
                f"constraints[{index}]",
            )
            continue
        if target == INFORMATIONAL_CONSTRAINT:
            continue
        if target not in EXECUTABLE_CONSTRAINT_TARGETS:
            report.add_error(
                "INVALID_CONSTRAINT_TARGET",
                f"constraint target is not executable: {target}",
                f"constraint_mappings.{constraint}",
            )
            continue
        if not _constraint_target_is_explicit(intent, target):
            report.add_error(
                "MISSING_CONSTRAINT_TARGET",
                f"constraint target must be explicit in DesignIntent: {target}",
                f"constraint_mappings.{constraint}",
            )

    stale_constraints = set(intent.constraint_mappings) - constraints
    for constraint in sorted(stale_constraints):
        report.add_error(
            "STALE_CONSTRAINT_MAPPING",
            "constraint mapping has no matching constraint",
            f"constraint_mappings.{constraint}",
        )


def _constraint_target_is_explicit(intent: DesignIntent, target: str) -> bool:
    if target == "furniture_type" or target.startswith("overall_size."):
        return True
    section, field = target.split(".", 1)
    values = intent.layout if section == "layout" else intent.structure
    return field in values
