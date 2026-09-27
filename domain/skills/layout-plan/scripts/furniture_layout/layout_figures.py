"""给这套摆放配上每个房间的图，确认时核对图是不是刚算出来的。

房间外壳不在这里。
"""

from __future__ import annotations

from typing import Any, Mapping

from furniture_delivery_validation.validation import ValidationReport

from .room_svg import render_preview
from .project_layout import ProjectLayout
from .scene import RoomScene
from .validation import admit_scene
from .stored_room_page import render_viewer


def project_layout_dict(layout: ProjectLayout) -> dict[str, Any]:
    """检查点字典：几何，加上由它重建的预览和只读视图。

    项目文件和 `layout_sha256` 用的就是这个形状。
    """
    rooms: list[dict[str, Any]] = []
    for scene in layout.rooms:
        payload: dict[str, Any] = scene.to_dict()
        if scene.items:
            payload["preview"] = render_preview(scene)
            payload["viewer"] = render_viewer(scene)
        rooms.append(payload)
    return {
        "schema_version": layout.schema_version,
        "confirmed": layout.confirmed,
        "rooms": rooms,
        "cad": {"units": [unit.to_dict() for unit in layout.executable_units()]},
    }


def check_room_figures(output: Mapping[str, Any]) -> ValidationReport:
    """确认用：先再做一遍摆放准入，再核对 SVG 和只读页是不是当前几何画出的。"""
    report = ValidationReport(stage="layout_plan")
    try:
        scene = RoomScene.from_dict(output)
    except (KeyError, TypeError, ValueError) as exc:
        report.add_error("INVALID_ROOM_SCENE", str(exc), "items")
        return report

    report = admit_scene(scene)
    if not scene.items:
        return report

    raw_preview = output.get("preview")
    if not isinstance(raw_preview, Mapping):
        report.add_error("INVALID_LAYOUT_PREVIEW", "preview must be an object", "preview")
    elif dict(raw_preview) != render_preview(scene):
        report.add_error(
            "LAYOUT_PREVIEW_MISMATCH",
            "SVG preview must match the current room and furniture placement",
            "preview",
        )
    raw_viewer = output.get("viewer")
    if not isinstance(raw_viewer, Mapping):
        report.add_error("INVALID_LAYOUT_VIEWER", "viewer must be an object", "viewer")
    elif dict(raw_viewer) != render_viewer(scene):
        report.add_error(
            "LAYOUT_VIEWER_MISMATCH",
            "interactive viewer must match the current room and furniture placement",
            "viewer",
        )
    return report


def check_layout_figures(output: Mapping[str, Any]) -> ValidationReport:
    """确认用：整套房子的每一间都走 `check_room_figures`。"""
    report = ValidationReport(stage="layout_plan")
    try:
        layout = ProjectLayout.from_dict(output)
    except (KeyError, TypeError, ValueError) as exc:
        report.add_error("INVALID_PROJECT_LAYOUT", str(exc), "rooms")
        return report
    for message in layout.validate():
        report.add_error("INVALID_PROJECT_LAYOUT", message, "rooms")
    raw_rooms = output.get("rooms")
    if not isinstance(raw_rooms, list):
        return report
    for index, raw in enumerate(raw_rooms):
        if not isinstance(raw, Mapping):
            report.add_error(
                "INVALID_PROJECT_LAYOUT",
                f"rooms[{index}] must be an object",
                f"rooms[{index}]",
            )
            continue
        room_report = check_room_figures(raw)
        for issue in room_report.issues:
            path = f"rooms[{index}]"
            if issue.path:
                path = f"{path}.{issue.path}"
            report.add_error(issue.code, issue.message, path)
    return report
