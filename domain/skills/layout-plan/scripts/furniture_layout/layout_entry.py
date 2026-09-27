"""三个入口：建全屋摆放、建单间、写房间外壳。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from .room_shell import room_shell_from_output
from .layout_figures import check_room_figures
from .placement import place_items
from .room_svg import render_preview
from .project_layout import ProjectLayout
from .scene import RoomModel, RoomScene, parse_item_specs
from .validation import raise_unless_admitted
from .stored_room_page import render_viewer


def plan_scene(
    room: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]],
) -> RoomScene:
    """Place every item and admit the result; geometry only, no preview.

    项目布局的编辑走这里重算被改的那一间（见 `project_edit.py`）：场景源进来，
    摆放坐标、footprint、净距都是算出来的，所以改完不会留下过期的派生字段。
    """
    room_model = RoomModel.from_dict(room)
    specs = parse_item_specs(items)
    placed = place_items(room_model, specs)
    scene = RoomScene(room=room_model, items=placed)
    raise_unless_admitted(scene)
    return scene


def plan_room_scene(
    room: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Place every item, admit the placement, then emit preview and viewer."""
    scene = plan_scene(room, items)
    return {
        "room": scene.room.to_dict(),
        "items": [item.to_dict() for item in scene.items],
        "preview": render_preview(scene),
        "viewer": render_viewer(scene),
    }


def plan_project_layout(rooms: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Place every room in a home project and emit the layout checkpoint."""
    layout = ProjectLayout.from_source({"rooms": list(rooms)})
    return layout.to_dict()


def write_room_shell(
    output: Mapping[str, Any],
    *,
    workspace_root: str | Path,
    output_root: str | Path,
    cad_bridge: Any | None = None,
    artifact_id: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """核对这一间的图，然后写房间外壳 STEP。"""
    report = check_room_figures(output)
    if not report.passed:
        raise ValueError(
            "; ".join(issue.message for issue in report.issues)
        )
    shell = room_shell_from_output(
        output,
        workspace_root=workspace_root,
        output_root=output_root,
        cad_bridge=cad_bridge,
        artifact_id=artifact_id,
        force=force,
    )
    if shell.get("status") != "ok":
        raise ValueError(shell.get("message") or "room shell generation failed")
    result = dict(output)
    result["cad"] = shell
    return result
