"""Furniture category and finished-envelope intent.

DesignIntent is deliberately small: it records only the cabinet family and
the customer-confirmed finished envelope.  Functional layout, construction,
manufacturing, CAD, and artifact choices belong to later stage contracts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any


SUPPORTED_TYPES = frozenset({"floor_cabinet", "wall_cabinet"})
MOUNT_MODES = frozenset({"free_height", "flush_ceiling"})


@dataclass(frozen=True)
class OverallSize:
    """整体尺寸（草稿可空）。"""
    width_mm: float | None
    depth_mm: float | None
    height_mm: float | None

    def validate(self) -> list[str]:
        errors: list[str] = []
        for name, value in asdict(self).items():
            if value is None:
                errors.append(
                    f"overall_size.{name} must be provided before confirmation"
                )
            elif isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"overall_size.{name} must be numeric")
            elif value <= 0:
                errors.append(f"overall_size.{name} must be greater than zero")
        return errors


@dataclass(frozen=True)
class DesignIntent:
    """One revision's customer-confirmed finished-envelope source of truth."""

    furniture_type: str
    overall_size: OverallSize
    # 挂装方式：free_height（自由挂高，需 mounting_height_mm）/
    # flush_ceiling（贴顶到顶，无需数字）。仅吊柜有意义，地柜为 None。
    mount_mode: str | None = None
    # 自由挂高时吊柜底边离地高度；贴顶或地柜无此义，默认 None。
    mounting_height_mm: float | None = None
    confirmed: bool = False
    schema_version: int = 2

    def validate(self) -> list[str]:
        errors = self.overall_size.validate()
        errors.extend(
            _mounting_errors(
                self.furniture_type, self.mount_mode, self.mounting_height_mm
            )
        )
        if not self.furniture_type.strip():
            errors.append("furniture_type is required")
        if self.schema_version != 2:
            errors.append(f"unsupported DesignIntent schema_version: {self.schema_version}")
        return errors

    def confirm(self) -> "DesignIntent":
        errors = self.validate()
        if self.furniture_type not in SUPPORTED_TYPES:
            errors.append(
                "furniture_type must be an executable canonical type: "
                + ", ".join(sorted(SUPPORTED_TYPES))
            )
        if errors:
            raise ValueError("; ".join(errors))
        return replace(self, confirmed=True)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["overall_size"] = {
            "width_mm": _optional_float_value(self.overall_size.width_mm),
            "depth_mm": _optional_float_value(self.overall_size.depth_mm),
            "height_mm": _optional_float_value(self.overall_size.height_mm),
        }
        data["mounting_height_mm"] = _optional_float_value(self.mounting_height_mm)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DesignIntent":
        source_schema_version = int(data.get("schema_version", 2))
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
            key for key in downstream_fields if data.get(key)
        )
        if populated_downstream and not legacy_schema:
            raise ValueError(
                "DesignIntent only accepts furniture_type, overall_size, "
                "mount_mode, and mounting_height_mm; route later decisions "
                "through stage_inputs: "
                + ", ".join(populated_downstream)
            )
        size = data.get("overall_size", {})
        return cls(
            furniture_type=str(data.get("furniture_type", data.get("type", ""))).strip().lower(),
            overall_size=OverallSize(
                width_mm=_parse_optional_float(
                    size.get("width_mm", data.get("width")),
                    "overall_size.width_mm",
                ),
                depth_mm=_parse_optional_float(
                    size.get("depth_mm", data.get("depth")),
                    "overall_size.depth_mm",
                ),
                height_mm=_parse_optional_float(
                    size.get("height_mm", data.get("height")),
                    "overall_size.height_mm",
                ),
            ),
            mount_mode=data.get("mount_mode"),
            mounting_height_mm=_parse_optional_float(
                data.get("mounting_height_mm"),
                "mounting_height_mm",
            ),
            confirmed=bool(data.get("confirmed", False)),
            # Schema v1 carried downstream layout and construction fields.
            # Reading it into the current model intentionally drops those
            # fields; workflow project loading migrates them to stage_inputs.
            schema_version=(2 if legacy_schema else source_schema_version),
        )


def _mounting_errors(
    furniture_type: str,
    mount_mode: str | None,
    mounting_height_mm: float | None,
) -> list[str]:
    """Confirmation-time rules for a wall cabinet's mounting intent."""
    if furniture_type != "wall_cabinet":
        return []
    if mount_mode not in MOUNT_MODES:
        return [
            "mount_mode must be 'free_height' or 'flush_ceiling' "
            "for a wall cabinet"
        ]
    if mount_mode == "flush_ceiling":
        return []
    # free_height：必须给正数底边离地高度。
    if mounting_height_mm is None:
        return [
            "mounting_height_mm must be provided before confirmation "
            "for a free-height wall cabinet"
        ]
    if isinstance(mounting_height_mm, bool) or not isinstance(
        mounting_height_mm, (int, float)
    ):
        return ["mounting_height_mm must be numeric or null"]
    if mounting_height_mm <= 0:
        return [
            "mounting_height_mm must be greater than zero "
            "for a free-height wall cabinet"
        ]
    return []


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
