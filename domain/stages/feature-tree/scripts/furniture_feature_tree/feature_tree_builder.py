"""Build an executable feature tree from confirmed manufacturing records.

Copies the fields this stage models. Manufacturing types are not imported.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any, Mapping, Sequence


_PANEL_REQUIRED = ("label", "panel_type", "size_x", "size_y", "size_z")
_PANEL_DEFAULTS = {
    "pos_x": 0.0,
    "pos_y": 0.0,
    "pos_z": 0.0,
    "depends_on": (),
    "parent_id": "",
    "role": "",
}
_OPERATION_REQUIRED = (
    "id",
    "operation_type",
    "target_panel",
    "size_x",
    "size_y",
    "size_z",
    "pos_x",
    "pos_y",
    "pos_z",
)
_OPERATION_DEFAULTS = {"note": ""}


@dataclass(frozen=True)
class _Panel:
    label: str
    panel_type: str
    size_x: float
    size_y: float
    size_z: float
    pos_x: float
    pos_y: float
    pos_z: float
    depends_on: tuple[str, ...]
    parent_id: str
    role: str


@dataclass(frozen=True)
class _Operation:
    id: str
    operation_type: str
    target_panel: str
    size_x: float
    size_y: float
    size_z: float
    pos_x: float
    pos_y: float
    pos_z: float
    note: str


def panels_to_feature_tree(
    panels: Sequence[Any],
    operations: Sequence[Any],
    furniture_category: str = "floor_cabinet",
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Turn confirmed boards and machining ops into a Feature Tree v2 dict."""
    admitted_panels = tuple(_admit_panel(item) for item in _as_sequence(panels, "panels"))
    admitted_operations = tuple(
        _admit_operation(item) for item in _as_sequence(operations, "operations")
    )
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
        for panel in admitted_panels
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
        for operation in admitted_operations
    ]
    feature_ids = [feature["id"] for feature in features]
    cabinets: dict[str, list[str]] = {}
    for panel in admitted_panels:
        parent = panel.parent_id or f"{furniture_category}_assembly"
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
        "furniture_category": furniture_category,
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
    panels: Sequence[Any],
    operations: Sequence[Any],
    source_path: str | Path,
    furniture_category: str = "floor_cabinet",
    parameters: dict[str, Any] | None = None,
) -> Path:
    from .feature_tree_emitter import write_build123d_source

    return write_build123d_source(
        panels_to_feature_tree(panels, operations, furniture_category, parameters),
        source_path,
    )


def _as_sequence(value: Any, name: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{name} must be a list")
    return value


def _admit_panel(source: Any) -> _Panel:
    values = _read_fields(source, _PANEL_REQUIRED + tuple(_PANEL_DEFAULTS))
    missing = [name for name in _PANEL_REQUIRED if name not in values]
    if missing:
        raise ValueError("feature tree panel is missing: " + ", ".join(missing))
    for name, default in _PANEL_DEFAULTS.items():
        values.setdefault(name, default)
    label = values["label"]
    panel_type = values["panel_type"]
    if not isinstance(label, str) or not label.strip():
        raise ValueError("feature tree panel label must be a non-empty string")
    if not isinstance(panel_type, str) or not panel_type.strip():
        raise ValueError(f"{label} panel_type must be a non-empty string")
    depends = values["depends_on"]
    if isinstance(depends, (str, bytes)) or not isinstance(depends, Sequence):
        raise ValueError(f"{label} depends_on must be a list")
    return _Panel(
        label=label.strip(),
        panel_type=panel_type.strip(),
        size_x=_number(values["size_x"], "size_x"),
        size_y=_number(values["size_y"], "size_y"),
        size_z=_number(values["size_z"], "size_z"),
        pos_x=_number(values["pos_x"], "pos_x"),
        pos_y=_number(values["pos_y"], "pos_y"),
        pos_z=_number(values["pos_z"], "pos_z"),
        depends_on=tuple(str(item) for item in depends),
        parent_id=str(values["parent_id"]),
        role=str(values["role"]),
    )


def _admit_operation(source: Any) -> _Operation:
    values = _read_fields(source, _OPERATION_REQUIRED + tuple(_OPERATION_DEFAULTS))
    missing = [name for name in _OPERATION_REQUIRED if name not in values]
    if missing:
        raise ValueError("feature tree operation is missing: " + ", ".join(missing))
    for name, default in _OPERATION_DEFAULTS.items():
        values.setdefault(name, default)
    operation_id = values["id"]
    operation_type = values["operation_type"]
    target = values["target_panel"]
    if not isinstance(operation_id, str) or not operation_id.strip():
        raise ValueError("feature tree operation id must be a non-empty string")
    if not isinstance(operation_type, str) or not operation_type.strip():
        raise ValueError(f"{operation_id} operation_type must be a non-empty string")
    if not isinstance(target, str) or not target.strip():
        raise ValueError(f"{operation_id} target_panel must be a non-empty string")
    return _Operation(
        id=operation_id.strip(),
        operation_type=operation_type.strip(),
        target_panel=target.strip(),
        size_x=_number(values["size_x"], "size_x"),
        size_y=_number(values["size_y"], "size_y"),
        size_z=_number(values["size_z"], "size_z"),
        pos_x=_number(values["pos_x"], "pos_x"),
        pos_y=_number(values["pos_y"], "pos_y"),
        pos_z=_number(values["pos_z"], "pos_z"),
        note=str(values["note"]),
    )


def _read_fields(source: Any, names: Sequence[str]) -> dict[str, Any]:
    if isinstance(source, Mapping):
        return {name: source[name] for name in names if name in source}
    values: dict[str, Any] = {}
    for name in names:
        if hasattr(source, name):
            values[name] = getattr(source, name)
    return values


def _number(value: Any, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
    ):
        raise ValueError(f"{name} must be a finite number")
    return float(value)
