"""Plan a multi-item room scene and optionally generate envelope CAD."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from .cad import cad_from_output
from .placement import place_items
from .preview import render_preview
from .project_layout import ProjectLayout
from .scene import RoomModel, RoomScene, parse_item_specs
from .validation import validate_room_scene
from .viewer import render_viewer


def plan_room_scene(
    room: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Place every item, then emit preview and viewer for the scene."""
    room_model = RoomModel.from_dict(room)
    specs = parse_item_specs(items)
    placed = place_items(room_model, specs)
    scene = RoomScene(room=room_model, items=placed)
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


def generate_room_cad(
    output: Mapping[str, Any],
    *,
    workspace_root: str | Path,
    output_root: str | Path,
    cad_bridge: Any | None = None,
    artifact_id: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    report = validate_room_scene(output)
    if not report.passed:
        raise ValueError(
            "; ".join(issue.message for issue in report.issues)
        )
    cad = cad_from_output(
        output,
        workspace_root=workspace_root,
        output_root=output_root,
        cad_bridge=cad_bridge,
        artifact_id=artifact_id,
        force=force,
    )
    if cad.get("status") != "ok":
        raise ValueError(cad.get("message") or "room CAD generation failed")
    result = dict(output)
    result["cad"] = cad
    return result
