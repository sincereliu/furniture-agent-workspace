"""Emit a cadgen room-and-envelope model and run CadBridge."""

from __future__ import annotations

import json
import pprint
from pathlib import Path
from typing import Any, Mapping

from .scene import RoomOpening, RoomScene


WALL_THICKNESS_MM = 100.0


def scene_to_cad_tree(scene: RoomScene) -> dict[str, Any]:
    room = scene.room
    thickness = WALL_THICKNESS_MM
    features: list[dict[str, Any]] = [
        {
            "id": "floor",
            "size": {"x": room.width_mm, "y": room.depth_mm, "z": thickness},
            "position": {"x": 0.0, "y": 0.0, "z": -thickness},
            "rotation_z_deg": 0.0,
        },
        {
            "id": "wall_north",
            "size": {"x": room.width_mm, "y": thickness, "z": room.height_mm},
            "position": {"x": 0.0, "y": -thickness, "z": 0.0},
            "rotation_z_deg": 0.0,
        },
        {
            "id": "wall_south",
            "size": {"x": room.width_mm, "y": thickness, "z": room.height_mm},
            "position": {"x": 0.0, "y": room.depth_mm, "z": 0.0},
            "rotation_z_deg": 0.0,
        },
        {
            "id": "wall_west",
            "size": {"x": thickness, "y": room.depth_mm, "z": room.height_mm},
            "position": {"x": -thickness, "y": 0.0, "z": 0.0},
            "rotation_z_deg": 0.0,
        },
        {
            "id": "wall_east",
            "size": {"x": thickness, "y": room.depth_mm, "z": room.height_mm},
            "position": {"x": room.width_mm, "y": 0.0, "z": 0.0},
            "rotation_z_deg": 0.0,
        },
    ]
    operations = [
        _opening_cut(room.width_mm, room.depth_mm, opening, thickness)
        for opening in room.openings
    ]
    for obstacle in room.obstacles:
        features.append(
            {
                "id": obstacle.id,
                "size": {
                    "x": obstacle.width_mm,
                    "y": obstacle.depth_mm,
                    "z": obstacle.height_mm,
                },
                "position": {
                    "x": obstacle.x_mm,
                    "y": obstacle.y_mm,
                    "z": obstacle.z_mm,
                },
                "rotation_z_deg": 0.0,
            }
        )
    for item in scene.items:
        features.append(
            {
                "id": item.id,
                "size": {"x": item.width, "y": item.depth, "z": item.height},
                "position": {
                    "x": item.placement.origin_x_mm,
                    "y": item.placement.origin_y_mm,
                    "z": item.placement.origin_z_mm,
                },
                "rotation_z_deg": item.placement.rotation_z_deg,
            }
        )
    return {
        "root": {"id": room.id},
        "features": features,
        "operations": operations,
    }


def write_room_cad_source(
    scene: RoomScene,
    source_path: str | Path,
    *,
    step_path: str | Path | None = None,
) -> Path:
    resolved_source = Path(source_path).resolve()
    resolved_source.parent.mkdir(parents=True, exist_ok=True)
    tree_literal = pprint.pformat(
        scene_to_cad_tree(scene),
        sort_dicts=False,
        width=100,
    )
    step_decorator = "@step"
    if step_path is not None:
        out_literal = json.dumps(Path(step_path).resolve().as_posix())
        step_decorator = f"@step(out={out_literal})"
    source = f'''"""Generated room envelope layout. Edit the scene, not this file."""

from cadgen import build123d as bd
from cadgen import step


SCENE = {tree_literal}


def _box(node):
    size = node["size"]
    position = node["position"]
    rotation_z_deg = float(node.get("rotation_z_deg") or 0.0)
    shape = bd.Box(
        size["x"],
        size["y"],
        size["z"],
        align=(bd.Align.MIN, bd.Align.MIN, bd.Align.MIN),
    )
    shape.move(bd.Location((position["x"], position["y"], position["z"]), (0, 0, rotation_z_deg)))
    return shape


def gen_step():
    operations_by_target = {{}}
    for operation in SCENE.get("operations", []):
        operations_by_target.setdefault(operation["target"], []).append(operation)

    parts = []
    for feature in SCENE["features"]:
        shape = _box(feature)
        for operation in operations_by_target.get(feature["id"], []):
            if operation["type"] == "cut_box":
                shape = shape - _box(operation)
        shape.label = feature["id"]
        parts.append(shape)
    return bd.Compound(children=parts, label=SCENE["root"]["id"])


{step_decorator}
def model():
    return gen_step()


if __name__ == "__main__":
    model()
'''
    resolved_source.write_text(source, encoding="utf-8")
    return resolved_source


def generate_room_cad(
    scene: RoomScene,
    *,
    workspace_root: str | Path,
    output_root: str | Path,
    cad_bridge: Any | None = None,
    artifact_id: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    workspace = Path(workspace_root).resolve()
    output = Path(output_root)
    if not output.is_absolute():
        output = workspace / output
    name = artifact_id or scene.room.id or "room"
    source_path = workspace / "temp" / "cad-source" / f"layout-{name}" / "model.step.py"
    step_path = output / "layout" / name / "room.step"
    write_room_cad_source(scene, source_path, step_path=step_path)
    bridge = cad_bridge
    if bridge is None:
        from furniture_cad.cad_bridge import CadBridge

        bridge = CadBridge(workspace_root=workspace)
    result = bridge.generate_from_source(source_path, step_path, force=force)
    return {
        "source_path": str(source_path),
        "step_path": result.step_path,
        "topology_path": result.topology_path,
        "viewer_package_path": result.viewer_package_path,
        "status": result.status,
        "message": result.message,
    }


def _opening_cut(
    room_width: float,
    room_depth: float,
    opening: RoomOpening,
    thickness: float,
) -> dict[str, Any]:
    if opening.wall == "north":
        position = {
            "x": opening.offset_mm,
            "y": -thickness,
            "z": opening.sill_height_mm,
        }
        size = {"x": opening.width_mm, "y": thickness, "z": opening.height_mm}
    elif opening.wall == "east":
        position = {
            "x": room_width,
            "y": opening.offset_mm,
            "z": opening.sill_height_mm,
        }
        size = {"x": thickness, "y": opening.width_mm, "z": opening.height_mm}
    elif opening.wall == "south":
        position = {
            "x": room_width - opening.offset_mm - opening.width_mm,
            "y": room_depth,
            "z": opening.sill_height_mm,
        }
        size = {"x": opening.width_mm, "y": thickness, "z": opening.height_mm}
    else:
        position = {
            "x": -thickness,
            "y": room_depth - opening.offset_mm - opening.width_mm,
            "z": opening.sill_height_mm,
        }
        size = {"x": thickness, "y": opening.width_mm, "z": opening.height_mm}
    return {
        "type": "cut_box",
        "target": f"wall_{opening.wall}",
        "size": size,
        "position": position,
        "rotation_z_deg": 0.0,
    }


def cad_from_output(
    output: Mapping[str, Any],
    *,
    workspace_root: str | Path,
    output_root: str | Path,
    cad_bridge: Any | None = None,
    artifact_id: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    return generate_room_cad(
        RoomScene.from_dict(output),
        workspace_root=workspace_root,
        output_root=output_root,
        cad_bridge=cad_bridge,
        artifact_id=artifact_id,
        force=force,
    )
