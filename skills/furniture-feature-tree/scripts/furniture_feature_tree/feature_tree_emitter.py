"""Emit build123d source for panel boxes and target-specific cut operations."""

from __future__ import annotations

import pprint
import re
from pathlib import Path
from typing import Any


VALID_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def write_build123d_source(
    feature_tree: dict[str, Any], source_path: str | Path
) -> Path:
    _validate_feature_tree(feature_tree)
    resolved_source = Path(source_path).resolve()
    resolved_source.parent.mkdir(parents=True, exist_ok=True)
    tree_literal = pprint.pformat(
        _sanitize_for_source(feature_tree), sort_dicts=False, width=100
    )
    source = f'''"""Generated from the furniture Feature Tree. Edit the intent, not this file."""

from build123d import Align, Box, Compound, Location


FEATURE_TREE = {tree_literal}


def _box(node):
    size = node["size"]
    position = node["position"]
    shape = Box(
        size["x"],
        size["y"],
        size["z"],
        align=(Align.MIN, Align.MIN, Align.MIN),
    )
    shape.move(Location((position["x"], position["y"], position["z"])))
    return shape


def gen_step():
    operations_by_target = {{}}
    for operation in FEATURE_TREE.get("operations", []):
        operations_by_target.setdefault(operation["target"], []).append(operation)

    parts = []
    for feature in FEATURE_TREE["features"]:
        shape = _box(feature)
        for operation in operations_by_target.get(feature["id"], []):
            if operation["type"] == "cut_box":
                shape = shape - _box(operation)
        shape.label = feature["id"]
        parts.append(shape)
    return Compound(children=parts, label=FEATURE_TREE["root"]["id"])
'''
    resolved_source.write_text(source, encoding="utf-8")
    return resolved_source


def _validate_feature_tree(feature_tree: dict[str, Any]) -> None:
    if feature_tree.get("schema_version") != 2:
        raise ValueError("Unsupported Feature Tree schema_version")
    features = feature_tree.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("Feature Tree must contain at least one feature")

    feature_ids: set[str] = set()
    feature_by_id: dict[str, dict[str, Any]] = {}
    for feature in features:
        feature_id = str(feature.get("id", ""))
        _validate_identifier(feature_id, "feature")
        if feature_id in feature_ids:
            raise ValueError(f"Duplicate feature id: {feature_id}")
        feature_ids.add(feature_id)
        feature_by_id[feature_id] = feature
        if feature.get("type") != "box":
            raise ValueError(
                f"Unsupported feature type for {feature_id}: {feature.get('type')!r}"
            )
        _validate_xyz(feature.get("size"), f"{feature_id}.size", positive=True)
        _validate_xyz(feature.get("position"), f"{feature_id}.position", positive=False)
        for dependency in feature.get("depends_on", []):
            if dependency not in feature_ids and dependency not in {
                item.get("id") for item in features
            }:
                raise ValueError(f"Unknown dependency for {feature_id}: {dependency}")

    operation_ids: set[str] = set()
    for operation in feature_tree.get("operations", []):
        operation_id = str(operation.get("id", ""))
        _validate_identifier(operation_id, "operation")
        if operation_id in operation_ids or operation_id in feature_ids:
            raise ValueError(f"Duplicate operation id: {operation_id}")
        operation_ids.add(operation_id)
        if operation.get("type") != "cut_box":
            raise ValueError(
                f"Unsupported operation type for {operation_id}: {operation.get('type')!r}"
            )
        target = str(operation.get("target", ""))
        if target not in feature_by_id:
            raise ValueError(f"Unknown operation target for {operation_id}: {target}")
        _validate_xyz(operation.get("size"), f"{operation_id}.size", positive=True)
        _validate_xyz(operation.get("position"), f"{operation_id}.position", positive=False)
        _validate_operation_bounds(operation, feature_by_id[target])

    root = feature_tree.get("root")
    if not isinstance(root, dict) or root.get("type") != "compound":
        raise ValueError("Feature Tree root must be a compound")
    root_id = str(root.get("id", ""))
    _validate_identifier(root_id, "root")
    if set(root.get("children", [])) != feature_ids:
        raise ValueError("Feature Tree root children must reference every feature exactly once")


def _validate_identifier(value: str, kind: str) -> None:
    if not VALID_IDENTIFIER.fullmatch(value):
        raise ValueError(f"Invalid {kind} id: {value!r}")


def _validate_operation_bounds(
    operation: dict[str, Any], target: dict[str, Any]
) -> None:
    tolerance = 1e-6
    for axis in ("x", "y", "z"):
        operation_start = float(operation["position"][axis])
        operation_end = operation_start + float(operation["size"][axis])
        target_start = float(target["position"][axis])
        target_end = target_start + float(target["size"][axis])
        if operation_start < target_start - tolerance or operation_end > target_end + tolerance:
            raise ValueError(
                f"{operation['id']} exceeds target {target['id']} on {axis.upper()}"
            )


def _validate_xyz(value: Any, field_name: str, *, positive: bool) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    for axis in ("x", "y", "z"):
        axis_value = value.get(axis)
        if isinstance(axis_value, bool) or not isinstance(axis_value, (int, float)):
            raise ValueError(f"{field_name}.{axis} must be numeric")
        if positive and axis_value <= 0:
            raise ValueError(f"{field_name}.{axis} must be greater than zero")


def _sanitize_for_source(obj: Any) -> Any:
    """Recursively replace non-ASCII strings so the emitted source is ASCII-safe."""
    if isinstance(obj, str):
        try:
            obj.encode("ascii")
        except UnicodeEncodeError:
            return obj.encode("ascii", errors="replace").decode("ascii")
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_source(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_source(item) for item in obj]
    return obj
