"""Layout-stage planning for supported cabinet families."""

from __future__ import annotations

from furniture_design_intent.design_spec import FurnitureSpec, SUPPORTED_TYPES

from .layout_planning import CabinetLayout


def plan_layout(spec: FurnitureSpec) -> CabinetLayout:
    """Stage 2: resolve cabinet envelope, clear regions, and layout counts."""
    if spec.furniture_type not in SUPPORTED_TYPES:
        supported = ", ".join(sorted(SUPPORTED_TYPES))
        raise ValueError(
            f"Unsupported cabinet type: {spec.furniture_type!r}; supported: {supported}"
        )
    errors = spec.validation_errors()
    if errors:
        raise ValueError("; ".join(errors))
    return CabinetLayout.from_spec(spec)
