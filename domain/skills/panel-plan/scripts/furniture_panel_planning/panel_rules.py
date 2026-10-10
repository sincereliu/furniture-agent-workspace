"""Stage-owned rules for repeated cabinet panel members."""

from __future__ import annotations


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


def default_toe_kick_support_count(width: float, toe_kick_height: float) -> int:
    """Support count from finished width when a proposal omits it.

    ``width`` is the cabinet envelope width, not the internal width.
    A toe kick of zero has no supports. Otherwise a width below 600 mm
    has none, and every further 300 mm of finished width adds one:
    ``1 + floor((width - 600) / 300)``.
    """
    if toe_kick_height <= 0:
        return 0
    if width < 600:
        return 0
    return 1 + int((width - 600) // 300)


def even_shelf_gap(
    internal_height: float,
    shelf_count: int,
    board_thickness: float,
) -> float:
    """Equal opening above the top shelf and below every shelf."""
    if shelf_count < 1:
        raise ValueError("even shelf gaps require at least one shelf")
    gap = (internal_height - shelf_count * board_thickness) / (shelf_count + 1)
    if gap < 0:
        raise ValueError("even shelf gaps exceed the internal height")
    return gap
