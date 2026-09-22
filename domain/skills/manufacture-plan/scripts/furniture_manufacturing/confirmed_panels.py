"""Read-only view of a confirmed panel plan.

Manufacturing copies the fields it machines and ignores every other key.
Contact geometry is copied without the historical ``connection`` flag;
this stage decides on/off itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping, Sequence


ADMITTED_BACK_MOUNTS = frozenset({"groove", "insert", "cover"})

_CONSTRUCTION_FIELDS = (
    "furniture_category",
    "width",
    "depth",
    "height",
    "board_thickness",
    "back_thickness",
    "door_thickness",
    "back_mount",
    "groove_depth",
    "groove_clearance",
    "back_offset",
)
_PANEL_REQUIRED = ("id", "name", "panel_type", "size_x", "size_y", "size_z")
_PANEL_DEFAULTS = {
    "pos_x": 0.0,
    "pos_y": 0.0,
    "pos_z": 0.0,
    "quantity": 1,
    "material_role": "carcass",
    "note": "",
    "depends_on": (),
    "door_overlay": None,
    "inner_face": "",
    "outer_face": "",
    "joints": (),
    "role": "",
    "parent_id": "",
}
_CONTACT_FIELDS = (
    "bearing_id",
    "end_id",
    "face",
    "edge_axis",
    "edge_sign",
    "end_z",
    "end_size_z",
)
_CONTACT_RECORD_FIELDS = frozenset(_CONTACT_FIELDS + ("connection",))


@dataclass(frozen=True)
class Contact:
    """One face-to-edge contact, plus the manufacturing on/off decision."""

    bearing_id: str
    end_id: str
    face: str
    edge_axis: str
    edge_sign: int
    end_z: float
    end_size_z: float = 0.0
    connection: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Contact":
        """Restore a manufacturing contact. ``connection`` is required."""
        if not isinstance(data, Mapping):
            raise ValueError("manufacturing contact must be an object")
        values = dict(data)
        unknown = sorted(set(values) - _CONTACT_RECORD_FIELDS)
        if unknown:
            raise ValueError(
                "manufacturing contact does not support: " + ", ".join(unknown)
            )
        missing = [
            name for name in (*_CONTACT_FIELDS, "connection") if name not in values
        ]
        if missing:
            raise ValueError(
                "manufacturing contact is missing: " + ", ".join(missing)
            )
        connection = values["connection"]
        if connection not in {"on", "off"}:
            raise ValueError("connection must be 'on' or 'off'")
        return _contact_from_values(values, connection)


@dataclass(frozen=True)
class ConfirmedConstruction:
    """Cabinet facts manufacturing machines, copied from a confirmed spec."""

    furniture_category: str
    width: float
    depth: float
    height: float
    board_thickness: float
    back_thickness: float
    door_thickness: float
    back_mount: str
    groove_depth: float
    groove_clearance: float
    back_offset: float


@dataclass(frozen=True)
class ConfirmedPanel:
    """One confirmed board: size, place, faces, and contact geometry."""

    id: str
    name: str
    panel_type: str
    size_x: float
    size_y: float
    size_z: float
    pos_x: float
    pos_y: float
    pos_z: float
    quantity: int
    material_role: str
    note: str
    depends_on: tuple[str, ...]
    door_overlay: str | None
    inner_face: str
    outer_face: str
    joints: tuple[Contact, ...]
    role: str
    parent_id: str


def admit_construction(spec: Any) -> ConfirmedConstruction:
    """Copy the construction facts this stage machines."""
    values = _read_fields(spec, _CONSTRUCTION_FIELDS)
    missing = [name for name in _CONSTRUCTION_FIELDS if name not in values]
    if missing:
        raise ValueError(
            "confirmed cabinet is missing: " + ", ".join(missing)
        )
    category = values["furniture_category"]
    if not isinstance(category, str) or not category.strip():
        raise ValueError("furniture_category must be a non-empty string")
    back_mount = values["back_mount"]
    if back_mount not in ADMITTED_BACK_MOUNTS:
        raise ValueError(
            "confirmed back_mount must be one of: "
            + ", ".join(sorted(ADMITTED_BACK_MOUNTS))
        )
    numbers = {
        name: _number(values[name], name)
        for name in (
            "width",
            "depth",
            "height",
            "board_thickness",
            "back_thickness",
            "door_thickness",
            "groove_depth",
            "groove_clearance",
            "back_offset",
        )
    }
    return ConfirmedConstruction(
        furniture_category=category.strip(),
        back_mount=back_mount,
        **numbers,
    )


def admit_panels(placements: Sequence[Any]) -> tuple[ConfirmedPanel, ...]:
    """Copy each confirmed board. Extra panel fields are ignored."""
    if isinstance(placements, (str, bytes)) or not isinstance(placements, Sequence):
        raise ValueError("confirmed panels must be a list")
    return tuple(_admit_panel(item) for item in placements)


def _admit_panel(source: Any) -> ConfirmedPanel:
    names = _PANEL_REQUIRED + tuple(_PANEL_DEFAULTS)
    values = _read_fields(source, names)
    missing = [name for name in _PANEL_REQUIRED if name not in values]
    if missing:
        raise ValueError("confirmed panel is missing: " + ", ".join(missing))
    for name, default in _PANEL_DEFAULTS.items():
        values.setdefault(name, default)
    panel_id = values["id"]
    if not isinstance(panel_id, str) or not panel_id.strip():
        raise ValueError("confirmed panel id must be a non-empty string")
    name = values["name"]
    panel_type = values["panel_type"]
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"{panel_id} name must be a non-empty string")
    if not isinstance(panel_type, str) or not panel_type.strip():
        raise ValueError(f"{panel_id} panel_type must be a non-empty string")
    raw_joints = values["joints"]
    if not isinstance(raw_joints, Sequence) or isinstance(raw_joints, (str, bytes)):
        raise ValueError(f"{panel_id} joints must be a list")
    depends = values["depends_on"]
    if not isinstance(depends, Sequence) or isinstance(depends, (str, bytes)):
        raise ValueError(f"{panel_id} depends_on must be a list")
    overlay = values["door_overlay"]
    if overlay is not None and not isinstance(overlay, str):
        raise ValueError(f"{panel_id} door_overlay must be a string or null")
    return ConfirmedPanel(
        id=panel_id.strip(),
        name=name,
        panel_type=panel_type,
        size_x=_number(values["size_x"], "size_x"),
        size_y=_number(values["size_y"], "size_y"),
        size_z=_number(values["size_z"], "size_z"),
        pos_x=_number(values["pos_x"], "pos_x"),
        pos_y=_number(values["pos_y"], "pos_y"),
        pos_z=_number(values["pos_z"], "pos_z"),
        quantity=_count(values["quantity"], "quantity"),
        material_role=str(values["material_role"]),
        note=str(values["note"]),
        depends_on=tuple(str(item) for item in depends),
        door_overlay=overlay,
        inner_face=str(values["inner_face"]),
        outer_face=str(values["outer_face"]),
        joints=tuple(contact_from_panel(item) for item in raw_joints),
        role=str(values["role"]),
        parent_id=str(values["parent_id"]),
    )


def contact_from_panel(source: Any) -> Contact:
    """Copy contact geometry. A historical connection flag is discarded."""
    values = _read_fields(source, _CONTACT_FIELDS)
    missing = [name for name in _CONTACT_FIELDS if name not in values]
    if missing:
        raise ValueError("confirmed contact is missing: " + ", ".join(missing))
    return _contact_from_values(values, "")


def _contact_from_values(values: Mapping[str, Any], connection: str) -> Contact:
    edge_sign = values["edge_sign"]
    if isinstance(edge_sign, bool) or not isinstance(edge_sign, int):
        raise ValueError("edge_sign must be an integer")
    return Contact(
        bearing_id=str(values["bearing_id"]),
        end_id=str(values["end_id"]),
        face=str(values["face"]),
        edge_axis=str(values["edge_axis"]),
        edge_sign=edge_sign,
        end_z=_number(values["end_z"], "end_z"),
        end_size_z=_number(values["end_size_z"], "end_size_z"),
        connection=connection,
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


def _count(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value
