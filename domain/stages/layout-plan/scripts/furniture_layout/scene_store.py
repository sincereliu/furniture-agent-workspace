"""房间场景的持久化。

只保存可编辑的「源」（`room + items`），**不保存派生结果**（摆放坐标、footprint、
净距、预览）——派生在读取时重算，保证场景只有一个真源。

场景存储独立于家具主流程：既不写入 `stage_outputs`，也不进入 `STAGE_SEQUENCE`。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

SCENES_DIRNAME = "room-scenes"
SAFE_SCENE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def scenes_root(root: str | Path) -> Path:
    """场景存储根目录（按需创建）。"""
    path = Path(root) / SCENES_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def scene_path(scene_id: str, *, root: str | Path) -> Path:
    """场景文件路径；id 非法即拒绝，避免越出存储目录。"""
    if not SAFE_SCENE_ID.fullmatch(scene_id):
        raise ValueError("scene_id may contain only letters, digits, '-' and '_'")
    return scenes_root(root) / f"{scene_id}.json"


def save_scene_source(
    scene_id: str,
    room: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]],
    *,
    root: str | Path,
) -> Path:
    """把场景的源写盘（房间定义 + 多件包络及其摆放请求）。"""
    if not items:
        raise ValueError("room scene requires at least one item")
    path = scene_path(scene_id, root=root)
    payload = {
        "scene_id": scene_id,
        "room": dict(room),
        "items": [dict(item) for item in items],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def load_scene_source(scene_id: str, *, root: str | Path) -> dict[str, Any]:
    """读取场景的源；文件缺失或结构损坏即失败，不静默返回空场景。"""
    path = scene_path(scene_id, root=root)
    if not path.exists():
        raise FileNotFoundError(f"room scene not found: {scene_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    room = data.get("room")
    items = data.get("items")
    if not isinstance(room, Mapping):
        raise ValueError(f"room scene {scene_id} has no room object")
    if not isinstance(items, list) or not items:
        raise ValueError(f"room scene {scene_id} has no items")
    return {"scene_id": scene_id, "room": dict(room), "items": list(items)}


def scene_exists(scene_id: str, *, root: str | Path) -> bool:
    try:
        return scene_path(scene_id, root=root).exists()
    except ValueError:
        return False


def list_scene_ids(*, root: str | Path) -> list[str]:
    """按字母序列出已保存的场景 id。"""
    return sorted(path.stem for path in scenes_root(root).glob("*.json"))
