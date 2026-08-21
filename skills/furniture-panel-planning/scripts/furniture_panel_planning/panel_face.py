"""PanelFace — semantic face directions for a single furniture panel.

Each panel in the cabinet has well-defined faces:
- inner_face: the face pointing into the cabinet interior
- outer_face: the face pointing out of the cabinet
- cam_face:   the face where the eccentric wheel is accessible (horizontal panels only)

Connectors use these semantic directions instead of guessing from panel position.
"""

from __future__ import annotations

from dataclasses import dataclass


def _negate(axis: str) -> str:
    """Flip a signed axis: "+x"→"-x", "-y"→"+y"."""
    if axis and axis[0] in "+-":
        return f"{'+' if axis[0] == '-' else '-'}{axis[1]}"
    return axis


@dataclass(frozen=True)
class PanelFace:
    """Semantic face directions for a single panel.

    Attributes
    ----------
    inner : str
        Direction (signed world axis) from the panel's interior toward the
        cabinet interior.  E.g. left side panel → "+x", right → "-x".
    outer : str
        Opposite of inner.
    cam : str or None
        Face where the eccentric wheel is installed and accessible for
        tightening.  Typically the bottom face of horizontal panels ("-z").
        None for vertical panels (side panels).
    """

    inner: str
    outer: str
    cam: str | None = None

    @property
    def nut_direction(self) -> str:
        """Direction to drill pre-embedded nut holes.

        Nut is installed from the inner face, drilling inward into the panel.
        So the drilling direction is opposite to the inner face.
        """
        return _negate(self.inner)

    @property
    def cup_direction(self) -> str:
        """Direction to drill hinge cup holes.

        Hinge cup is drilled from the inner face INTO the door panel, so the
        drilling direction is opposite to the inner face (direction 语义统一
        为钻入方向，见 coordinate-naming.md)。
        """
        return _negate(self.inner)

    @property
    def rod_direction(self) -> str:
        """Direction to drill connecting rod holes.

        Rod is inserted from the edge of the panel.  For the left edge of
        a horizontal panel, the rod goes +x into the panel.  For the right
        edge, it goes -x.  This is panel-edge-dependent, not face-dependent,
        so callers should prefer nut_direction / cam_direction for trinity.
        """
        return _negate(self.inner)

    @property
    def cam_direction(self) -> str:
        """Direction to drill eccentric wheel holes.

        Wheel is installed from the cam_face INTO the panel, so the drilling
        direction is opposite to the cam_face.  If cam_face is "-z", drilling
        goes into the panel in the +z direction.
        """
        if self.cam is None:
            return _negate(self.inner)  # fallback — shouldn't happen for horizontal panels
        return _negate(self.cam)
