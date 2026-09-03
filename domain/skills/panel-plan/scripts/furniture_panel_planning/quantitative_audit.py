"""Furniture-specific dimensional and uncertainty audit for panel-stage output."""

from __future__ import annotations

from math import isfinite, sqrt
from typing import Any, Mapping


_LINEAR_UNIT_TO_MM = {
    "mm": 1.0,
    "millimeter": 1.0,
    "millimetre": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "in": 25.4,
    "inch": 25.4,
}


def _unit_engine() -> tuple[Any | None, str]:
    try:
        from pint import UnitRegistry
    except ImportError:
        return None, "bounded-linear-conversion"
    return UnitRegistry(), "pint"


def _to_mm(value: Any, unit: str, registry: Any | None) -> float:
    number = float(value)
    normalized = str(unit).strip().lower()
    if registry is not None:
        return float((number * registry(normalized)).to("mm").magnitude)
    if normalized not in _LINEAR_UNIT_TO_MM:
        raise ValueError(
            f"unit {unit!r} requires Pint; bounded fallback supports: "
            + ", ".join(sorted(_LINEAR_UNIT_TO_MM))
        )
    return number * _LINEAR_UNIT_TO_MM[normalized]


def _standard_uncertainty_mm(
    record: Mapping[str, Any], registry: Any | None
) -> tuple[float, dict[str, Any]]:
    unit = str(record.get("unit", "mm"))
    stated = _to_mm(record.get("uncertainty", 0.0), unit, registry)
    if stated < 0 or not isfinite(stated):
        raise ValueError("uncertainty must be a finite non-negative number")
    kind = str(record.get("kind", "standard")).strip().lower()
    distribution = str(record.get("distribution", "normal")).strip().lower()
    divisor = 1.0
    if kind == "expanded":
        divisor = float(record.get("coverage_factor", 0.0))
        if divisor <= 0:
            raise ValueError("expanded uncertainty requires coverage_factor > 0")
    elif kind == "limit":
        divisors = {
            "rectangular": sqrt(3.0),
            "triangular": sqrt(6.0),
            "arcsine": sqrt(2.0),
        }
        if distribution not in divisors:
            raise ValueError(
                "limit uncertainty distribution must be rectangular, triangular, or arcsine"
            )
        divisor = divisors[distribution]
    elif kind != "standard":
        raise ValueError("uncertainty kind must be standard, expanded, or limit")
    dof = record.get("dof")
    if dof is not None and float(dof) <= 0:
        raise ValueError("degrees of freedom must be positive")
    standard = stated / divisor
    return standard, {
        "stated_uncertainty": stated,
        "standard_uncertainty_mm": standard,
        "kind": kind,
        "distribution": distribution,
        "dof": dof,
        "coverage_factor": record.get("coverage_factor"),
    }


def audit_panel_quantities(
    panel_output: Mapping[str, Any],
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Audit units, finite geometry, derived clearances, and optional GUM inputs.

    The function never edits ``panel_output``. Unspecified uncertainty inputs are
    treated as unknown, not as zero, and no conformity decision is inferred.
    """

    config = dict(config or {})
    spec = panel_output.get("spec")
    structure = panel_output.get("structure")
    panels = panel_output.get("panels")
    if not isinstance(spec, Mapping) or not isinstance(structure, Mapping):
        raise ValueError("panel output requires spec and structure objects")
    if not isinstance(panels, list):
        raise ValueError("panel output requires a panels list")

    registry, engine = _unit_engine()
    issues: list[dict[str, str]] = []
    checked_dimensions = 0
    for namespace, values in (("spec", spec), ("structure", structure)):
        for name, raw in values.items():
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                continue
            checked_dimensions += 1
            value = float(raw)
            if not isfinite(value):
                issues.append(
                    {
                        "severity": "error",
                        "path": f"{namespace}.{name}",
                        "message": "dimension is not finite",
                    }
                )
    for index, raw_panel in enumerate(panels):
        if not isinstance(raw_panel, Mapping):
            issues.append(
                {
                    "severity": "error",
                    "path": f"panels[{index}]",
                    "message": "panel is not an object",
                }
            )
            continue
        for axis in ("size_x", "size_y", "size_z"):
            checked_dimensions += 1
            try:
                value = float(raw_panel[axis])
            except (KeyError, TypeError, ValueError):
                issues.append(
                    {
                        "severity": "error",
                        "path": f"panels[{index}].{axis}",
                        "message": "missing numeric dimension",
                    }
                )
                continue
            if not isfinite(value) or value <= 0:
                issues.append(
                    {
                        "severity": "error",
                        "path": f"panels[{index}].{axis}",
                        "message": "panel dimension must be finite and positive",
                    }
                )

    models = {
        "internal_width": (
            float(spec["width"]) - 2.0 * float(spec["board_thickness"]),
            {"width": 1.0, "board_thickness": -2.0},
        ),
        "internal_height": (
            float(spec["height"])
            - float(structure["toe_kick_height"])
            - 2.0 * float(spec["board_thickness"]),
            {"height": 1.0, "toe_kick_height": -1.0, "board_thickness": -2.0},
        ),
        "internal_depth": (
            float(structure["internal_y_end"]) - float(structure["internal_y_start"]),
            {
                "depth": 1.0,
                "door_thickness": -1.0,
                "door_hinge_gap": -1.0,
                "back_thickness": -1.0,
                **(
                    {"back_offset": -1.0}
                    if str(structure["back_mount"]) != "cover"
                    else {}
                ),
            },
        ),
    }
    for name, (expected, _) in models.items():
        actual_key = name if name != "internal_depth" else None
        if actual_key and abs(float(structure[actual_key]) - expected) > 1e-6:
            issues.append(
                {
                    "severity": "error",
                    "path": f"structure.{actual_key}",
                    "message": (
                        "derived clearance does not match its measurement model"
                    ),
                }
            )
        if expected <= 0:
            issues.append(
                {
                    "severity": "error",
                    "path": f"structure.{name}",
                    "message": "derived clearance is not positive",
                }
            )

    raw_uncertainties = config.get("uncertainties", {})
    if not isinstance(raw_uncertainties, Mapping):
        raise ValueError("uncertainties must be an object keyed by spec quantity")
    uncertainties: dict[str, float] = {}
    uncertainty_inputs: dict[str, Any] = {}
    for name, raw in raw_uncertainties.items():
        if name not in spec and name not in structure:
            raise ValueError(f"unknown uncertainty quantity: {name}")
        if not isinstance(raw, Mapping):
            raise ValueError(f"uncertainty input must be an object: {name}")
        standard, normalized = _standard_uncertainty_mm(raw, registry)
        uncertainties[str(name)] = standard
        uncertainty_inputs[str(name)] = normalized

    raw_coverage_factor = config.get("coverage_factor")
    coverage_factor = (
        float(raw_coverage_factor) if raw_coverage_factor is not None else None
    )
    if coverage_factor is not None and (
        coverage_factor <= 0 or not isfinite(coverage_factor)
    ):
        raise ValueError("coverage_factor must be finite and positive")
    measurement_models: list[dict[str, Any]] = []
    for name, (estimate, sensitivities) in models.items():
        used = {
            key: coefficient
            for key, coefficient in sensitivities.items()
            if key in uncertainties
        }
        combined = sqrt(
            sum((coefficient * uncertainties[key]) ** 2 for key, coefficient in used.items())
        ) if used else None
        variance_contributions = {
            key: (coefficient * uncertainties[key]) ** 2
            for key, coefficient in used.items()
        }
        measurement_models.append(
            {
                "name": name,
                "estimate_mm": estimate,
                "sensitivity_coefficients": sensitivities,
                "variance_contributions_mm2": variance_contributions,
                "standard_uncertainty_mm": combined,
                "expanded_uncertainty_mm": (
                    combined * coverage_factor
                    if combined is not None and coverage_factor is not None
                    else None
                ),
                "coverage_factor": (
                    coverage_factor if combined is not None else None
                ),
            }
        )

    return {
        "analysis": "panel_unit_audit",
        "status": "completed",
        "passed": not any(item["severity"] == "error" for item in issues),
        "engine": engine,
        "canonical_unit": "mm",
        "checked_dimensions": checked_dimensions,
        "uncertainty_inputs": uncertainty_inputs,
        "measurement_models": measurement_models,
        "issues": issues,
        "limitations": [
            "correlations are not inferred; supplied inputs are treated as independent",
            "no conformity decision is made without an explicit acceptance rule",
            "missing uncertainty inputs remain unknown rather than being treated as exact",
            "expanded uncertainty is omitted unless coverage_factor is explicitly supplied",
        ],
    }
