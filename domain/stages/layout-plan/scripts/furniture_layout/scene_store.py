"""One persisted format: validated placed geometry, without planning-source fallbacks."""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from .input_fields import fields
from .scene import RoomScene
from .validation import raise_unless_admitted

SCENES_DIRNAME = "room-scenes"
SCHEMA_VERSION = 1
SAFE_SCENE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def scene_path(scene_id: str, *, root: str | Path) -> Path:
    if not SAFE_SCENE_ID.fullmatch(scene_id):
        raise ValueError("scene_id may contain only letters, digits, '-' and '_'")
    directory = (Path(root) / SCENES_DIRNAME).resolve()
    path = (directory / f"{scene_id}.json").resolve()
    if not path.is_relative_to(directory):
        raise ValueError("scene path escapes its storage directory")
    return path


def scene_document(scene_id: str, scene: RoomScene) -> dict[str, Any]:
    if not scene.items:
        raise ValueError("room scene requires at least one item")
    raise_unless_admitted(scene)
    return {"schema_version": SCHEMA_VERSION, "scene_id": scene_id,
            "room": scene.room.to_dict(), "items": [item.to_dict() for item in scene.items]}


def save_scene(scene_id: str, scene: RoomScene, *, root: str | Path) -> Path:
    path = scene_path(scene_id, root=root)
    payload = scene_document(scene_id, scene)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_scene(scene_id: str, *, root: str | Path) -> RoomScene:
    path = scene_path(scene_id, root=root)
    if not path.is_file():
        raise FileNotFoundError(f"room scene not found: {scene_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("saved room scene must be an object")
    fields(data, {"schema_version", "scene_id", "room", "items"}, "saved room scene")
    if type(data.get("schema_version")) is not int or data["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported room scene schema_version")
    if data.get("scene_id") != scene_id:
        raise ValueError("saved room scene_id does not match the filename")
    scene = RoomScene.from_dict(data)
    if scene_document(scene_id, scene) != data:
        raise ValueError("saved scene must contain canonical placed geometry")
    return scene


def scene_exists(scene_id: str, *, root: str | Path) -> bool:
    try:
        return scene_path(scene_id, root=root).is_file()
    except ValueError:
        return False


def list_scene_ids(*, root: str | Path) -> list[str]:
    directory = Path(root) / SCENES_DIRNAME
    return sorted(path.stem for path in directory.glob("*.json") if SAFE_SCENE_ID.fullmatch(path.stem))
