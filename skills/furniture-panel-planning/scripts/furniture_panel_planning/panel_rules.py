"""Stage-owned rules for repeated cabinet panel members."""

from __future__ import annotations


def resolve_toe_kick_support_count(
    explicit: int | None,
    cabinet_width: float,
) -> int:
    """Return an explicit count or calculate one when the proposal used null."""
    if explicit is not None:
        return explicit
    if cabinet_width < 600:
        return 0
    return 1 + int((cabinet_width - 600) // 300)


def toe_kick_support_clear_spacing(
    internal_width: float,
    support_count: int,
    board_thickness: float,
) -> float:
    """Return equal clear spacing between supports and both side panels."""
    return (
        internal_width - support_count * board_thickness
    ) / (support_count + 1)


def resolve_back_rail_count(
    back_mount: str,
    internal_height: float,
    back_rail_height: float,
) -> int:
    """Return the repository back-rail count for a grooved back."""
    if (
        back_mount != "groove"
        or internal_height <= 0
        or back_rail_height <= 0
    ):
        return 0
    return int(internal_height // 500)


def back_rail_clear_spacing(
    internal_height: float,
    rail_count: int,
    rail_height: float,
) -> float:
    """Return the solver's equal clear spacing for back rails."""
    if rail_count <= 0:
        return internal_height
    return (
        internal_height - rail_count * rail_height
    ) / rail_count
