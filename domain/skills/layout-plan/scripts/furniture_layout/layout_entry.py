"""三个入口：建全屋摆放、建单间、写房间外壳。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from .room_shell import room_shell_from_output
from .layout_figures import check_room_figures, room_scene_dict
from .project_layout import ProjectLayout
from .scene_planning import plan_scene


def plan_room_scene(
    room: Mapping[str, Any],
    items: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Place every item, admit the placement, then emit preview and viewer."""
    return room_scene_dict(plan_scene(room, items))


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
