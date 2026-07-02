from __future__ import annotations

import pprint
import re
from pathlib import Path
from typing import Any


VALID_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def write_build123d_source(
    feature_tree: dict[str, Any], source_path: str | Path
) -> Path:
    """Translate a box-based Feature Tree into a text-to-cad gen_step() source."""
    _validate_feature_tree(feature_tree)
    resolved_source = Path(source_path).resolve()
    resolved_source.parent.mkdir(parents=True, exist_ok=True)

    tree_literal = pprint.pformat(feature_tree, sort_dicts=False, width=100)
    source = f'''"""Generated from the furniture Feature Tree. Edit the intent, not this file."""

from build123d import Align, Box, Compound, Location


FEATURE_TREE = {tree_literal}


def _box(feature):
    size = feature["size"]
    position = feature["position"]
    shape = Box(
        size["x"],
        size["y"],
        size["z"],
        align=(Align.MIN, Align.MIN, Align.MIN),
    )
    shape.move(Location((position["x"], position["y"], position["z"])))
    shape.label = feature["id"]
    return shape


def gen_step():
    parts = [_box(feature) for feature in FEATURE_TREE["features"]]
    return Compound(children=parts, label=FEATURE_TREE["root"]["id"])
'''
    resolved_source.write_text(source, encoding="utf-8")
    return resolved_source


def _validate_feature_tree(feature_tree: dict[str, Any]) -> None:
    if feature_tree.get("schema_version") != 1:
        raise ValueError("Unsupported Feature Tree schema_version")

    features = feature_tree.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("Feature Tree must contain at least one feature")

    feature_ids: set[str] = set()
    for feature in features:
        feature_id = str(feature.get("id", ""))
        if not VALID_IDENTIFIER.fullmatch(feature_id):
            raise ValueError(f"Invalid feature id: {feature_id!r}")
        if feature_id in feature_ids:
            raise ValueError(f"Duplicate feature id: {feature_id}")
        feature_ids.add(feature_id)
        if feature.get("type") != "box":
            raise ValueError(f"Unsupported feature type for {feature_id}: {feature.get('type')!r}")
        _validate_xyz(feature.get("size"), f"{feature_id}.size", positive=True)
        _validate_xyz(feature.get("position"), f"{feature_id}.position", positive=False)

    root = feature_tree.get("root")
    if not isinstance(root, dict) or root.get("type") != "compound":
        raise ValueError("Feature Tree root must be a compound")
    root_id = str(root.get("id", ""))
    if not VALID_IDENTIFIER.fullmatch(root_id):
        raise ValueError(f"Invalid root id: {root_id!r}")
    if set(root.get("children", [])) != feature_ids:
        raise ValueError("Feature Tree root children must reference every feature exactly once")


def _validate_xyz(value: Any, field_name: str, *, positive: bool) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    for axis in ("x", "y", "z"):
        axis_value = value.get(axis)
        if isinstance(axis_value, bool) or not isinstance(axis_value, (int, float)):
            raise ValueError(f"{field_name}.{axis} must be numeric")
        if positive and axis_value <= 0:
            raise ValueError(f"{field_name}.{axis} must be greater than zero")
