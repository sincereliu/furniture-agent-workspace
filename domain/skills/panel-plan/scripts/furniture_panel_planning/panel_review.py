"""Confirmation review derived from panel_plan cabinets.

The checkpoint fact remains ``cabinets[]``. This module projects a smaller
view for interactive confirmation: envelope, clearance, one row per panel,
and each contact once. It does not decide connection on/off.
"""

from __future__ import annotations

from typing import Any, Mapping

from .assembly_tree import flatten_panels_for_handoff, iter_assembly_joints
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
    interior = cabinet.get("interior")
    if not isinstance(spec, Mapping):
        raise ValueError(f"{cabinet_id} requires spec")
    if not isinstance(interior, Mapping):
        raise ValueError(f"{cabinet_id} requires interior")
    cavity = interior.get("cavity")
    if not isinstance(cavity, Mapping):
        raise ValueError(f"{cabinet_id} requires interior.cavity")
    panels = flatten_panels_for_handoff(cabinet)
    contacts = _unique_contacts(iter_assembly_joints(cabinet))
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
            "width": cavity["width"],
            "depth": cavity["depth"],
            "height": cavity["height"],
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
        "divider_count": sum(
            1 for item in panels if item.get("panel_type") == "divider"
        ),
        "toe_kick_height_mm": spec["toe_kick_height"],
        "panels": [_review_panel(item) for item in panels],
        "contacts": contacts,
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


def _unique_contacts(joints: list[Any]) -> list[dict[str, Any]]:
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
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
        f"外形尺寸 {_triple(envelope, 'width', 'depth', 'height')} mm",
        f"内部净空 {_triple(clearance, 'width', 'depth', 'height')} mm",
        back_line,
        (
            f"料厚 柜体板 {_format_mm(thickness['board'])} / "
            f"背板 {_format_mm(thickness['back'])} / "
            f"门 {_format_mm(thickness['door'])}"
        ),
        (
            f"门 {cabinet['n_doors']} · 抽屉 {cabinet['drawer_count']} · "
            f"层板 {cabinet['shelf_count']} · 踢脚 "
            f"{_format_mm(cabinet['toe_kick_height_mm'])} mm"
            + (
                f" · 中立板 {cabinet['divider_count']}"
                if cabinet.get("divider_count")
                else ""
            )
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
                "| 大面 | 端面 | 大面方向 |",
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


def format_interior_review_markdown(
    report: Mapping[str, Any],
    *,
    title: str = "柜内结构评估",
) -> str:
    """把 `evaluate_interior` 的回报整理成给人核对的清单（腔 / 缝 / 段 / findings）。

    **这是评估结果，不是已物化的板件**——标题底下就写明，免得读的人当成板件表。
    评估器只算**宽度方向**：腔高、腔深由层板与用途规则另算，这里不编。
    凑整口径保持中立：某条缝不等于 2×边距就标"吸收凑整零头"，左右边距不等就标
    "零头在边距"——A/B 两种口径都显示得出来。
    """
    if not isinstance(report, Mapping):
        raise ValueError("interior review requires the evaluator report")
    doors = report.get("doors")
    if not isinstance(doors, Mapping):
        raise ValueError("interior review requires doors")

    widths = [float(value) for value in doors.get("door_widths_mm", ())]
    gaps = [float(value) for value in doors.get("gaps_mm", ())]
    centers = [float(value) for value in doors.get("seam_centers_mm", ())]
    left = float(doors.get("left_margin_mm", 0.0))
    right = float(doors.get("right_margin_mm", 0.0))
    base_gap = 2 * left

    lines = [f"# {title}", "", "**评估结果：毫米按当前板厚算好，还没写进板件。**", ""]
    pairs = doors.get("pairs") or []
    pair_text = "、".join(f"{a}–{b}" for a, b in pairs)
    lines.append(
        f"正面 {len(widths)} 扇门 · 每扇 "
        + " / ".join(_format_mm(width) for width in widths)
        + (f" · 成对门 {pair_text}（从左起 0 开始）" if pair_text else " · 无成对门")
    )
    if centers:
        bits = []
        for index, center in enumerate(centers):
            gap = gaps[index] if index < len(gaps) else base_gap
            mark = "" if abs(gap - base_gap) < 1e-9 else " ← 吸收凑整零头"
            bits.append(f"缝 {_format_mm(center)}（{_format_mm(gap)}）{mark}")
        lines.append("　　" + " · ".join(bits))
    else:
        lines.append("　　无内缝（单扇门）")
    note = "" if abs(left - right) < 1e-9 else " ← 零头在边距"
    lines.append(f"　　边距 左 {_format_mm(left)} / 右 {_format_mm(right)}{note}")

    lines.extend(["", "## 中立板", ""])
    dividers = report.get("dividers") or []
    if dividers:
        lines.extend(["| 中立板 | 对齐 | 锚 mm | 区间 mm |", "| --- | --- | --- | --- |"])
        for divider in dividers:
            lines.append(
                f"| {divider.get('id')} | 缝 {divider.get('seam_index')}"
                f"（{divider.get('seam_align')}） | {_format_mm(divider.get('anchor_mm'))} | "
                f"{_format_mm(divider.get('start_mm'))}~{_format_mm(divider.get('end_mm'))} |"
            )
    else:
        lines.append("无")

    lines.extend(["", "## 腔（净宽；腔高与腔深由层板、用途规则另算）", ""])
    cavities = report.get("cavities") or []
    if cavities:
        lines.extend(["| 腔 | 净宽 mm | 判定 |", "| --- | --- | --- |"])
        for cavity in cavities:
            lines.append(
                f"| {cavity.get('index')} | {_format_mm(cavity.get('clear_width_mm'))} | "
                f"{cavity.get('status')} |"
            )
    else:
        lines.append("无")

    lines.extend(["", "## 分段", ""])
    panels = report.get("panels") or []
    if panels:
        lines.extend(["| 板 | 段数 | 各段长 mm | 断口宽 mm |", "| --- | --- | --- | --- |"])
        for panel in panels:
            segments = [float(value) for value in panel.get("segments_mm", ())]
            breaks = [float(value) for value in panel.get("break_widths_mm", ())]
            break_text = " / ".join(_format_mm(value) for value in breaks) if breaks else "—"
            lines.append(
                f"| {panel.get('id')} | {len(segments)} | "
                + " / ".join(_format_mm(value) for value in segments)
                + f" | {break_text} |"
            )
    else:
        lines.append("无")

    lines.extend(["", "## findings", ""])
    findings = report.get("findings") or []
    if findings:
        for finding in findings:
            lines.append(
                f"- **{finding.get('status')}** {finding.get('code')}：{finding.get('message')}"
            )
            lines.append(f"  - 继续的损失：{finding.get('proceed_loss')}")
            lines.append(f"  - 停下的损失：{finding.get('stop_loss')}")
    else:
        lines.append("无")
    lines.extend([
        "",
        f"总体：{'blocked（先别下料）' if report.get('blocked') else '没有 blocked'}",
    ])
    return "\n".join(lines)
