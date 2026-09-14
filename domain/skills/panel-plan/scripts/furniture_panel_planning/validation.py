"""Validation owned by the panel-planning stage."""

from __future__ import annotations

from typing import Any, Mapping

from furniture_delivery_validation.validation import ValidationReport
from furniture_design_intent.design_intent import DesignIntent

from .assembly_tree import (
    CABINET_OUTPUT_FIELDS,
    flatten_panels_for_handoff,
)
from .cabinet_identity import cabinets_from_output
from .panel_models import PanelPlacement
from .panel_spec import FurnitureSpec, resolve_back_mount
from .structure_planning import CabinetStructure
from .validation_cabinet import (
    _validate_assembly_tree,
    _validate_cabinet_membership,
    validate_structure,
)
from .validation_panels import validate_panels

def validate_panel_output(
    confirmed_intent: DesignIntent,
    output: Mapping[str, Any],
) -> ValidationReport:
    """Validate the complete construction-and-panels stage checkpoint."""
    report = ValidationReport(stage="panel_plan")
    try:
        cabinets = cabinets_from_output(output)
        cabinet_ids = [str(item.get("id", "")) for item in cabinets]
        if any(not item for item in cabinet_ids):
            raise ValueError("each cabinet requires an id")
        if len(set(cabinet_ids)) != len(cabinet_ids):
            raise ValueError("cabinet ids must be unique")
        parsed: list[tuple[str, FurnitureSpec, CabinetStructure, list[PanelPlacement], Mapping[str, Any]]] = []
        for cabinet in cabinets:
            unknown = sorted(set(cabinet) - CABINET_OUTPUT_FIELDS)
            if unknown:
                raise ValueError(
                    f"{cabinet.get('id')} does not support: " + ", ".join(unknown)
                )
            raw_spec = cabinet.get("spec")
            if not isinstance(raw_spec, Mapping):
                raise ValueError(f"{cabinet.get('id')} requires spec")
            if not isinstance(cabinet.get("interior"), Mapping):
                raise ValueError(f"{cabinet.get('id')} requires interior")
            spec = FurnitureSpec.from_dict(raw_spec)
            raw_panels = flatten_panels_for_handoff(cabinet)
            parsed.append(
                (
                    str(cabinet["id"]),
                    spec,
                    CabinetStructure.from_spec(spec),
                    [PanelPlacement.from_dict(item) for item in raw_panels],
                    cabinet,
                )
            )
    except (TypeError, ValueError, KeyError) as exc:
        report.add_error("INVALID_PANEL_STAGE_OUTPUT", str(exc))
        return report

    seen_ids: set[str] = set()
    for cabinet_id, spec, structure, panels, cabinet in parsed:
        report.issues.extend(
            _validate_cabinet_membership(cabinet_id, panels, seen_ids).issues
        )
        report.issues.extend(
            _validate_assembly_tree(cabinet_id, spec, structure, cabinet, panels).issues
        )
        report.issues.extend(
            validate_structure(confirmed_intent, spec, structure).issues
        )
        report.issues.extend(validate_panels(spec, structure, panels).issues)
        resolution = cabinet.get("back_mount_resolution")
        if not isinstance(resolution, Mapping):
            report.add_error(
                "MISSING_BACK_MOUNT_RESOLUTION",
                f"{cabinet_id} must show requested and effective back mount",
                "back_mount_resolution",
            )
            continue
        try:
            expected_mount = resolve_back_mount(resolution.get("requested"))
        except ValueError as exc:
            report.add_error(
                "INVALID_BACK_MOUNT_RESOLUTION",
                str(exc),
                "back_mount_resolution.requested",
            )
        else:
            if (
                resolution.get("effective") != spec.back_mount
                or expected_mount != spec.back_mount
            ):
                report.add_error(
                    "BACK_MOUNT_RESOLUTION_MISMATCH",
                    f"{cabinet_id} requested/effective back mount must match the admitted spec",
                    "back_mount_resolution",
                )
    return report

