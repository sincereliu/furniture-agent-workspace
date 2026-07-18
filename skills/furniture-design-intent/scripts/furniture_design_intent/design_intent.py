"""Versioned user intent for a furniture project.

DesignIntent records what should be built.  It deliberately contains no panel
placements, manufacturing operations, CAD primitives, or artifact paths.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any


@dataclass(frozen=True)
class OverallSize:
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
    """Confirmed or draft source of truth for one project revision."""

    furniture_type: str
    overall_size: OverallSize
    purpose: str = ""
    layout: dict[str, Any] = field(default_factory=dict)
    appearance: dict[str, Any] = field(default_factory=dict)
    structure: dict[str, Any] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    assumptions: dict[str, str] = field(default_factory=dict)
    unresolved: list[str] = field(default_factory=list)
    confirmed: bool = False
    schema_version: int = 1

    def validate(self) -> list[str]:
        errors = self.overall_size.validate()
        if not self.furniture_type.strip():
            errors.append("furniture_type is required")
        if self.schema_version != 1:
            errors.append(f"unsupported DesignIntent schema_version: {self.schema_version}")
        return errors

    def confirm(self) -> "DesignIntent":
        if self.unresolved:
            raise ValueError("DesignIntent cannot be confirmed while unresolved decisions remain")
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
            purpose=str(data.get("purpose", "")),
            layout=dict(data.get("layout", {})),
            appearance=dict(data.get("appearance", {})),
            structure=dict(data.get("structure", {})),
            constraints=list(data.get("constraints", [])),
            assumptions=dict(data.get("assumptions", {})),
            unresolved=list(data.get("unresolved", [])),
            confirmed=bool(data.get("confirmed", False)),
            schema_version=int(data.get("schema_version", 1)),
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
