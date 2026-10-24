"""生成并核对布局的展示投影；不参与项目保存、摘要或阶段确认。

房间外壳不在这里。
"""

from __future__ import annotations

from typing import Any, Mapping

from furniture_contracts.validation import ValidationReport

from .room_svg import render_preview
from .project_layout import ProjectLayout
from .scene import RoomScene
from .validation import admit_scene


def room_scene_dict(scene: RoomScene) -> dict[str, Any]:
    """Presentation projection; never used as project persistence or hash input."""
    payload = scene.to_dict()
    if scene.items:
        from furniture_web.room_page import render_viewer

        payload["preview"] = render_preview(scene)
        payload["viewer"] = render_viewer(scene)
    return payload


def project_layout_dict(layout: ProjectLayout) -> dict[str, Any]:
    """Display-only layout projection with current SVG and read-only pages."""
    return {**layout.to_dict(), "rooms": [room_scene_dict(scene) for scene in layout.rooms]}


def check_room_figures(output: Mapping[str, Any]) -> ValidationReport:
    """展示准入：核对摆放，以及 SVG 和只读页是否来自当前几何。"""
    report = ValidationReport(stage="layout_plan")
    try:
        scene = RoomScene.from_dict(output)
    except (KeyError, TypeError, ValueError) as exc:
        report.add_error("INVALID_ROOM_SCENE", str(exc), "items")
        return report

    report = admit_scene(scene)
    if not scene.items:
        return report

    from furniture_web.room_page import render_viewer

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
    """核对整套布局的展示投影，每间都走 `check_room_figures`。"""
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
