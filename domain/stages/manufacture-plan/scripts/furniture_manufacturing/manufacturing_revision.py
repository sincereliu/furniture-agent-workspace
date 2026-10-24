"""Rebuild every derived manufacturing record after an explicit BOM edit."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from .manufacturing_bom import (
    BOMReport,
    estimate_hardware,
    estimate_materials,
    recompute_features,
)


def revise_bom(output: Mapping[str, Any]) -> dict[str, Any]:
    """Panels and operations are edited facts; their derived snapshots stay aligned."""
    bom = BOMReport.from_dict(output)
    bom.features, bom.connection_points = recompute_features(bom.panels, bom.operations)
    bom.hardware = estimate_hardware(
        bom.panels,
        options=bom.requested_options.get("options", {}),
        features=bom.features,
        connection_points=bom.connection_points,
    )
    bom.materials = estimate_materials(bom.panels)
    bom.total_area_m2 = sum(panel.area_m2 for panel in bom.panels)
    return asdict(bom)
