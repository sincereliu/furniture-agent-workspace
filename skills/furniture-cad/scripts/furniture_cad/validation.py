"""Validation owned by the CAD-generation stage."""

from __future__ import annotations

from pathlib import Path

from furniture_delivery_validation.validation import ValidationReport

from .cad_bridge import BridgeResult


def validate_cad(bridge: BridgeResult | None) -> ValidationReport:
    report = ValidationReport(stage="cad_generated")
    if bridge is None:
        report.add_error("MISSING_CAD_RESULT", "CAD stage has no bridge result")
        return report
    if bridge.status != "ok":
        report.add_error("CAD_GENERATION_FAILED", bridge.message)
        return report
    for kind, path in (
        ("step", bridge.step_path),
        ("viewer_topology", bridge.topology_path),
    ):
        if not path or not Path(path).is_file():
            report.add_error(
                "MISSING_CAD_ARTIFACT",
                f"{kind} artifact is missing",
                kind,
            )
    return report
