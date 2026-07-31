"""Furniture category and finished-envelope intent.

DesignIntent is deliberately small: it records only the cabinet family and
the customer-confirmed finished envelope.  Functional layout, construction,
manufacturing, CAD, and artifact choices belong to later stage contracts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any


SUPPORTED_TYPES = frozenset({"floor_cabinet", "wall_cabinet"})


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
    confirmed: bool = False
    schema_version: int = 2

    def validate(self) -> list[str]:
        errors = self.overall_size.validate()
        if not self.furniture_type.strip():
            errors.append("furniture_type is required")
        if self.schema_version != 2:
            errors.append(f"unsupported DesignIntent schema_version: {self.schema_version}")
        return errors

    def confirm(self) -> "DesignIntent":
        errors = self.validate()
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
                "DesignIntent only accepts furniture_type and overall_size; "
                "route later decisions through stage_inputs: "
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
            confirmed=bool(data.get("confirmed", False)),
            # Schema v1 carried downstream layout and construction fields.
            # Reading it into the current model intentionally drops those
            # fields; workflow project loading migrates them to stage_inputs.
            schema_version=(2 if legacy_schema else source_schema_version),
        )


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
