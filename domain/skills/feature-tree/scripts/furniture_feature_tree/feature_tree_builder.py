"""Build an executable feature tree from confirmed manufacturing records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from furniture_manufacturing.manufacturing_models import MachiningOperation, PanelRecord


def panels_to_feature_tree(
    panels: list[PanelRecord],
    operations: list[MachiningOperation],
    furniture_type: str = "floor_cabinet",
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    features = [
        {
            "id": panel.label,
            "type": "box",
            "size": {"x": panel.size_x, "y": panel.size_y, "z": panel.size_z},
            "position": {"x": panel.pos_x, "y": panel.pos_y, "z": panel.pos_z},
            "depends_on": list(panel.depends_on),
            "tags": [panel.panel_type],
            "parent_id": panel.parent_id,
            "role": panel.role,
        }
        for panel in panels
    ]
    operation_nodes = [
        {
            "id": operation.id,
            "type": operation.operation_type,
            "target": operation.target_panel,
            "size": {
                "x": operation.size_x,
                "y": operation.size_y,
                "z": operation.size_z,
            },
            "position": {
                "x": operation.pos_x,
                "y": operation.pos_y,
                "z": operation.pos_z,
            },
            "depends_on": [operation.target_panel],
            "note": operation.note,
        }
        for operation in operations
    ]
    feature_ids = [feature["id"] for feature in features]
    cabinets: dict[str, list[str]] = {}
    for panel in panels:
        parent = panel.parent_id or f"{furniture_type}_assembly"
        cabinets.setdefault(parent, []).append(panel.label)
    cabinet_nodes = [
        {"id": cabinet_id, "type": "cabinet", "children": child_ids}
        for cabinet_id, child_ids in cabinets.items()
    ]
    if len(cabinet_nodes) == 1:
        root_id = cabinet_nodes[0]["id"]
    else:
        root_id = "scene"
    return {
        "schema_version": 2,
        "furniture_type": furniture_type,
        "units": "mm",
        "coordinate_system": {
            "origin": "lower-left-rear-ground-corner",
            "x": "left-to-right",
            "y": "rear-to-front",
            "z": "up",
        },
        "parameters": parameters or {},
        "features": features,
        "operations": operation_nodes,
        "cabinets": cabinet_nodes,
        "root": {
            "id": root_id,
            "type": "compound",
            "children": feature_ids,
        },
    }


def emit_panels_to_source(
    panels: list[PanelRecord],
    operations: list[MachiningOperation],
    source_path: str | Path,
    furniture_type: str = "floor_cabinet",
    parameters: dict[str, Any] | None = None,
) -> Path:
    from .feature_tree_emitter import write_build123d_source

    return write_build123d_source(
        panels_to_feature_tree(panels, operations, furniture_type, parameters),
        source_path,
    )
