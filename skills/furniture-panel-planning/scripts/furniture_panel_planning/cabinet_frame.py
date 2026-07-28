"""CabinetFrame — converts semantic cabinet directions into world axes.

A two-axis definition (front + top) resolves all six semantic faces via the
right-hand rule.  This is the single point of truth for cabinet orientation;
every downstream subsystem (panel placement, connectors, feature tree,
six-side drill) reads faces from here instead of hardcoding world axes.

Examples
--------
Standard floor cabinet:
    frame = CabinetFrame(front="+y", top="+z")   → right="+x"

Top-down tatami (front viewed from above, body lying on floor):
    frame = CabinetFrame(front="+z", top="-y")    → right="+x"
"""

from __future__ import annotations

from dataclasses import dataclass


def _negate(axis: str) -> str:
    """Flip a signed axis: "+x"→"-x", "-y"→"+y"."""
    if axis[0] == "+":
        return f"-{axis[1]}"
    return f"+{axis[1]}"


def _cross(axis_a: str, axis_b: str) -> str:
    """Right-hand cross product of two signed world axes.

    Uses the convention: x=width, y=depth, z=height.

    (cross "+y", "+z") → "+x"  (front × top = right)
    (cross "+z", "+x") → "+y"
    (cross "+x", "+y") → "+z"
    """
    axes = {a[1] for a in (axis_a, axis_b)}
    if {"x", "y"} <= axes:
        return "+z" if _sign_positive(axis_a, axis_b, "z") else "-z"
    if {"y", "z"} <= axes:
        return "+x" if _sign_positive(axis_a, axis_b, "x") else "-x"
    # {"z", "x"}
    return "+y" if _sign_positive(axis_a, axis_b, "y") else "-y"


def _sign_positive(first: str, second: str, target: str) -> bool:
    """Return True when (first × second) . target > 0 using the RHR table.

    +x × +y = +z,   +y × +z = +x,   +z × +x = +y
    +y × +x = -z,   +z × +y = -x,   +x × +z = -y
    Negating either input negates the result.
    """
    # Expand signs into ±1 for sign arithmetic
    s1 = 1 if first[0] == "+" else -1
    s2 = 1 if second[0] == "+" else -1
    a, b = first[1], second[1]
    # result sign = s1 * s2 * positive_cycle_sign
    cycle = {
        ("x", "y"): ("+z", 1), ("y", "z"): ("+x", 1), ("z", "x"): ("+y", 1),
        ("y", "x"): ("-z", -1), ("z", "y"): ("-x", -1), ("x", "z"): ("-y", -1),
    }
    _, outcome = cycle[(a, b)]
    return (s1 * s2 * outcome) > 0


@dataclass(frozen=True)
class CabinetFrame:
    """Maps semantic cabinet directions ("front", "top", ...) to world axes.

    Provide exactly two of {front, top, right} and the rest are derived via
    the right-hand rule.  The standard constructor takes front + top.

    Attributes
    ----------
    front : str
        The world axis toward which the cabinet front (door face) points.
    top : str
        The world axis toward which the cabinet top points.
    back, bottom, right, left : str
        Derived from front × top.
    """

    front: str = "+y"
    top: str = "+z"

    def __post_init__(self) -> None:
        if not (
            self.front.startswith(("+", "-"))
            and self.top.startswith(("+", "-"))
            and self.front[1] in "xyz"
            and self.top[1] in "xyz"
            and self.front[1] != self.top[1]
        ):
            raise ValueError(
                f"Invalid CabinetFrame: front={self.front}, top={self.top}. "
                f"Must be signed axes (±x, ±y, ±z) on different cardinal axes."
            )

    @property
    def back(self) -> str:
        return _negate(self.front)

    @property
    def bottom(self) -> str:
        return _negate(self.top)

    @property
    def right(self) -> str:
        return _cross(self.front, self.top)

    @property
    def left(self) -> str:
        return _negate(self.right)

    def axis_char(self, signed_axis: str) -> str:
        """Return the axis letter (x/y/z) without sign."""
        return signed_axis[1]
