"""Furniture category and finished-envelope intent.

DesignIntent is deliberately small: it records only the cabinet family and
the customer-confirmed finished envelope.  Functional layout, construction,
manufacturing, CAD, and artifact choices belong to later stage contracts.

Chinese skill terms map to these English names:

- 家具类别 → furniture_category
- 成品外包络 → finished_envelope
- 宽/深/高 → width_mm / depth_mm / height_mm
- 挂装方式 → hanging_mode
- 挂高（底边离地高度） → hanging_height_mm
- 自由挂高 → free_hanging_height
- 贴顶/到顶 → flush_ceiling
- 地柜/落地 → floor_cabinet
- 吊柜/上墙 → wall_cabinet
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any


SCHEMA_VERSION = 3
EXECUTABLE_CATEGORIES = frozenset({"floor_cabinet", "wall_cabinet"})
HANGING_MODES = frozenset({"free_hanging_height", "flush_ceiling"})


@dataclass(frozen=True)
class FinishedEnvelope:
    """成品外包络（草稿可空）。"""

    width_mm: float | None
    depth_mm: float | None
    height_mm: float | None

    def validate(self) -> list[str]:
        errors: list[str] = []
        for name, value in asdict(self).items():
            if value is None:
                errors.append(
                    f"finished_envelope.{name} must be provided before confirmation"
                )
            elif isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"finished_envelope.{name} must be numeric")
            elif value <= 0:
                errors.append(f"finished_envelope.{name} must be greater than zero")
        return errors


@dataclass(frozen=True)
class DesignIntent:
    """One revision's customer-confirmed finished-envelope source of truth."""

    furniture_category: str
    finished_envelope: FinishedEnvelope
    # 挂装方式：free_hanging_height（自由挂高，需 hanging_height_mm）/
    # flush_ceiling（贴顶到顶，无需数字）。仅吊柜有意义，地柜为 None。
    hanging_mode: str | None = None
    # 自由挂高时吊柜底边离地高度；贴顶或地柜无此义，默认 None。
    hanging_height_mm: float | None = None
    confirmed: bool = False
    schema_version: int = SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors = self.finished_envelope.validate()
        errors.extend(
            _hanging_errors(
                self.furniture_category, self.hanging_mode, self.hanging_height_mm
            )
        )
        if not self.furniture_category.strip():
            errors.append("furniture_category is required")
        if self.schema_version != SCHEMA_VERSION:
            errors.append(
                f"unsupported DesignIntent schema_version: {self.schema_version}"
            )
        return errors

    def confirm(self) -> "DesignIntent":
        errors = self.validate()
        if self.furniture_category not in EXECUTABLE_CATEGORIES:
            errors.append(
                "furniture_category must be an executable canonical category: "
                + ", ".join(sorted(EXECUTABLE_CATEGORIES))
            )
        if errors:
            raise ValueError("; ".join(errors))
        return replace(self, confirmed=True)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["finished_envelope"] = {
            "width_mm": _optional_float_value(self.finished_envelope.width_mm),
            "depth_mm": _optional_float_value(self.finished_envelope.depth_mm),
            "height_mm": _optional_float_value(self.finished_envelope.height_mm),
        }
        data["hanging_height_mm"] = _optional_float_value(self.hanging_height_mm)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DesignIntent":
        source = dict(data)
        source_schema_version = int(source.get("schema_version", SCHEMA_VERSION))
        legacy_schema = source_schema_version == 1
        downstream_fields = {
            "purpose",
            "layout",
            "appearance",
            "structure",
            "constraints",
            "constraint_mappings",
            "assumptions",
            "unresolved",
        }
        populated_downstream = sorted(
            key for key in downstream_fields if source.get(key)
        )
        if populated_downstream and not legacy_schema:
            raise ValueError(
                "DesignIntent only accepts furniture_category, finished_envelope, "
                "hanging_mode, and hanging_height_mm; route later decisions "
                "through stage_inputs: "
                + ", ".join(populated_downstream)
            )
        furniture_category = str(
            _canonical_value(
                source, "furniture_category", ("furniture_type", "type")
            )
            or ""
        ).strip().lower()
        envelope = _canonical_value(
            source, "finished_envelope", ("overall_size",)
        ) or {}
        if not isinstance(envelope, dict):
            raise ValueError("finished_envelope must be an object")
        hanging_mode = _canonical_value(source, "hanging_mode", ("mount_mode",))
        if hanging_mode is not None:
            hanging_mode = str(hanging_mode).strip().lower()
            if hanging_mode == "free_height":
                hanging_mode = "free_hanging_height"
        hanging_height_mm = _canonical_value(
            source, "hanging_height_mm", ("mounting_height_mm",)
        )
        return cls(
            furniture_category=furniture_category,
            finished_envelope=FinishedEnvelope(
                width_mm=_parse_optional_float(
                    envelope.get("width_mm", source.get("width")),
                    "finished_envelope.width_mm",
                ),
                depth_mm=_parse_optional_float(
                    envelope.get("depth_mm", source.get("depth")),
                    "finished_envelope.depth_mm",
                ),
                height_mm=_parse_optional_float(
                    envelope.get("height_mm", source.get("height")),
                    "finished_envelope.height_mm",
                ),
            ),
            hanging_mode=hanging_mode,
            hanging_height_mm=_parse_optional_float(
                hanging_height_mm,
                "hanging_height_mm",
            ),
            confirmed=bool(source.get("confirmed", False)),
            # Schema v1 carried downstream layout and construction fields.
            # Reading it into the current model intentionally drops those
            # fields; workflow project loading migrates them to stage_inputs.
            # Schema v2 used furniture_type/overall_size/mount_mode names.
            schema_version=SCHEMA_VERSION,
        )


def _hanging_errors(
    furniture_category: str,
    hanging_mode: str | None,
    hanging_height_mm: float | None,
) -> list[str]:
    """Confirmation-time rules for hanging fields on the finished envelope."""
    if furniture_category != "wall_cabinet":
        errors: list[str] = []
        if hanging_mode is not None:
            errors.append(
                "hanging_mode must be null unless furniture_category is wall_cabinet"
            )
        if hanging_height_mm is not None:
            errors.append(
                "hanging_height_mm must be null unless furniture_category is wall_cabinet"
            )
        return errors
    if hanging_mode not in HANGING_MODES:
        return [
            "hanging_mode must be 'free_hanging_height' or 'flush_ceiling' "
            "for a wall cabinet"
        ]
    if hanging_mode == "flush_ceiling":
        return []
    # free_hanging_height：必须给正数底边离地高度。
    if hanging_height_mm is None:
        return [
            "hanging_height_mm must be provided before confirmation "
            "for a free-hanging-height wall cabinet"
        ]
    if isinstance(hanging_height_mm, bool) or not isinstance(
        hanging_height_mm, (int, float)
    ):
        return ["hanging_height_mm must be numeric or null"]
    if hanging_height_mm <= 0:
        return [
            "hanging_height_mm must be greater than zero "
            "for a free-hanging-height wall cabinet"
        ]
    return []


def _canonical_value(
    data: dict[str, Any],
    canonical: str,
    aliases: tuple[str, ...],
) -> Any:
    """Prefer the canonical key; accept historical aliases when loading."""
    present = [canonical] if canonical in data else []
    present.extend(alias for alias in aliases if alias in data)
    if not present:
        return None
    first = data[present[0]]
    for key in present[1:]:
        if data[key] != first:
            raise ValueError(f"{canonical} and {key} must match")
    return first


def _optional_float_value(value: float | None) -> float | None:
    return None if value is None else float(value)


def _parse_optional_float(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric or null")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric or null") from exc
