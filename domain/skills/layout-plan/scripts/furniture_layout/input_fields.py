"""Read canonical structured fields; no aliases or inferred protocol values."""

from __future__ import annotations

from math import isfinite
from typing import Any, Mapping


def fields(data: Mapping[str, Any], allowed: set[str] | frozenset[str], path: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValueError(f"{path} does not support: " + ", ".join(unknown))


def number(data: Mapping[str, Any], key: str, *, default: float | None = None) -> float:
    value = data.get(key)
    if value is None:
        if default is not None:
            return default
        raise ValueError(f"missing numeric field: {key}")
    if isinstance(value, bool):
        raise ValueError(f"{key} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be numeric") from exc
    if not isfinite(result):
        raise ValueError(f"{key} must be finite")
    return result


def optional_number(data: Mapping[str, Any], key: str) -> float | None:
    return None if data.get(key) is None else number(data, key)


def text(data: Mapping[str, Any], key: str, *, default: str = "") -> str:
    value = data.get(key)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value.strip()


def boolean(data: Mapping[str, Any], key: str, *, default: bool = False) -> bool:
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def mapping(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be an object")
    return value
