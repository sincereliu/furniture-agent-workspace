"""Confirmation review derived from panel_plan cabinets.

The checkpoint fact remains ``cabinets[]``. This module projects a smaller
view for interactive confirmation: envelope, clearance, one row per panel,
and each contact once. It does not decide connection on/off.
"""

from __future__ import annotations

from typing import Any, Mapping

from .cabinet_identity import cabinets_from_output


_CONTACT_KEY_FIELDS = ("bearing_id", "end_id", "face", "edge_axis", "edge_sign")


def panel_review_from_output(output: Mapping[str, Any]) -> dict[str, Any]:
    """Return the confirmation view for a valid ``cabinets[]`` stage output."""
    review_cabinets = [_review_cabinet(item) for item in cabinets_from_output(output)]
    review = {"cabinets": review_cabinets}
    review["markdown"] = format_panel_review_markdown(review)
    return review


def format_panel_review_markdown(review: Mapping[str, Any]) -> str:
    """Render the confirmation view as tables a host can show as-is."""
    cabinets = review.get("cabinets")
    if not isinstance(cabinets, list) or not cabinets:
        raise ValueError("panel review requires cabinets")
    blocks = [_cabinet_markdown(item) for item in cabinets]
    return "\n\n".join(blocks)


def _review_cabinet(cabinet: Mapping[str, Any]) -> dict[str, Any]:
    cabinet_id = str(cabinet.get("id") or "").strip()
    if not cabinet_id:
        raise ValueError("cabinet requires id")
    spec = cabinet.get("spec")
    structure = cabinet.get("structure")
    panels = cabinet.get("panels")
    if not isinstance(spec, Mapping):
        raise ValueError(f"{cabinet_id} requires spec")
    if not isinstance(structure, Mapping):
        raise ValueError(f"{cabinet_id} requires structure")
    if not isinstance(panels, list):
        raise ValueError(f"{cabinet_id} requires panels")
    resolution = cabinet.get("back_mount_resolution")
    if not isinstance(resolution, Mapping):
        resolution = {}
    effective = resolution.get("effective", spec.get("back_mount"))
    requested = resolution.get("requested", effective)
    shelves = spec.get("shelves") or []
    if not isinstance(shelves, list):
        raise ValueError(f"{cabinet_id} shelves must be a list")
    return {
        "id": cabinet_id,
        "furniture_category": spec["furniture_category"],
        "envelope_mm": {
            "width": spec["width"],
            "depth": spec["depth"],
            "height": spec["height"],
        },
        "internal_clearance_mm": {
            "width": structure["internal_width"],
            "depth": structure["internal_y_end"] - structure["internal_y_start"],
            "height": structure["internal_height"],
        },
        "back_mount": {
            "requested": requested,
            "effective": effective,
        },
        "thickness_mm": {
            "board": spec["board_thickness"],
            "back": spec["back_thickness"],
            "door": spec["door_thickness"],
        },
        "n_doors": spec["n_doors"],
        "drawer_count": spec["drawer_count"],
        "shelf_count": len(shelves),
        "toe_kick_height_mm": spec["toe_kick_height"],
        "panels": [_review_panel(item) for item in panels],
        "contacts": _unique_contacts(panels),
    }


def _review_panel(panel: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(panel, Mapping):
        raise ValueError("each panel must be an object")
    return {
        "parent_id": panel["parent_id"],
        "role": panel["role"],
        "name": panel["name"],
        "panel_type": panel["panel_type"],
        "size_mm": {
            "x": panel["size_x"],
            "y": panel["size_y"],
            "z": panel["size_z"],
        },
        "pos_mm": {
            "x": panel["pos_x"],
            "y": panel["pos_y"],
            "z": panel["pos_z"],
        },
    }


def _unique_contacts(panels: list[Any]) -> list[dict[str, Any]]:
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for panel in panels:
        if not isinstance(panel, Mapping):
            raise ValueError("each panel must be an object")
        joints = panel.get("joints") or []
        if not isinstance(joints, list):
            raise ValueError(f"{panel.get('id', 'panel')} joints must be a list")
        for joint in joints:
            if not isinstance(joint, Mapping):
                raise ValueError("each contact must be an object")
            contact = {field: joint[field] for field in _CONTACT_KEY_FIELDS}
            unique[tuple(contact[field] for field in _CONTACT_KEY_FIELDS)] = contact
    return [unique[key] for key in sorted(unique)]


def _cabinet_markdown(cabinet: Mapping[str, Any]) -> str:
    envelope = cabinet["envelope_mm"]
    clearance = cabinet["internal_clearance_mm"]
    thickness = cabinet["thickness_mm"]
    back_mount = cabinet["back_mount"]
    effective = back_mount["effective"]
    requested = back_mount["requested"]
    back_line = f"背板 {effective}"
    if requested != effective:
        back_line += f"（请求 {requested}）"
    lines = [
        f"## {cabinet['id']}（{cabinet['furniture_category']}）",
        "",
        f"外包络 {_triple(envelope, 'width', 'depth', 'height')} mm",
        f"内部净空 {_triple(clearance, 'width', 'depth', 'height')} mm",
        back_line,
        (
            f"料厚 料板 {_format_mm(thickness['board'])} / "
            f"背板 {_format_mm(thickness['back'])} / "
            f"门 {_format_mm(thickness['door'])}"
        ),
        (
            f"门 {cabinet['n_doors']} · 抽屉 {cabinet['drawer_count']} · "
            f"层板 {cabinet['shelf_count']} · 踢脚 "
            f"{_format_mm(cabinet['toe_kick_height_mm'])} mm"
        ),
        "",
        f"### 板件（{len(cabinet['panels'])}）",
        "",
        "| 所属柜 | 角色 | 名称 | 类型 | 尺寸 mm | 位置 mm |",
        "|--------|------|------|------|---------|---------|",
    ]
    for panel in cabinet["panels"]:
        size = panel["size_mm"]
        pos = panel["pos_mm"]
        lines.append(
            f"| {panel['parent_id']} | {panel['role']} | {panel['name']} | "
            f"{panel['panel_type']} | {_triple(size, 'x', 'y', 'z')} | "
            f"({_format_mm(pos['x'])}, {_format_mm(pos['y'])}, {_format_mm(pos['z'])}) |"
        )
    contacts = cabinet["contacts"]
    names = {
        f"{panel['parent_id']}__{panel['role']}": panel["name"]
        for panel in cabinet["panels"]
    }
    lines.extend(["", f"### 接触（{len(contacts)}）", ""])
    if contacts:
        lines.extend(
            [
                "| 承面 | 端面 | 承面方向 |",
                "|------|------|----------|",
            ]
        )
        for contact in contacts:
            bearing = names.get(contact["bearing_id"], contact["bearing_id"])
            end = names.get(contact["end_id"], contact["end_id"])
            lines.append(f"| {bearing} | {end} | {contact['face']} |")
    else:
        lines.append("无")
    return "\n".join(lines)


def _triple(values: Mapping[str, Any], first: str, second: str, third: str) -> str:
    return (
        f"{_format_mm(values[first])} × {_format_mm(values[second])} × "
        f"{_format_mm(values[third])}"
    )


def _format_mm(value: Any) -> str:
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.3f}".rstrip("0").rstrip(".")
