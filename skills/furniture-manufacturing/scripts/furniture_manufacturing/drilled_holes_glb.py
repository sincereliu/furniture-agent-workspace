"""Generate a GLB file with colored hole markers for Viewer overlay.

Reads a drilled-holes JSON dict and exports colored flat disc markers as a
standalone .glb that can be opened alongside the STEP in the CAD Viewer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import build123d as bd


def export_drilled_holes_glb(
    drilled_holes: dict[str, Any],
    output_path: str | Path,
    *,
    marker_thickness: float = 2.0,
) -> Path:
    """Export hole markers as a GLB file.

    Each hole is rendered as a flat colored disc at its global position.
    Discs are Z-axis aligned (flat in XY plane) and moved to position —
    sufficient for visual hole identification in the CAD Viewer.

    Args:
        drilled_holes: dict from emit_drilled_holes()
        output_path: target .glb file path
        marker_thickness: thickness of the marker disc (keep small for
            visual clarity; the depth value from manufacturing is for CAM)
    """
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_markers: list[bd.Solid] = []

    for panel in drilled_holes.get("panels", []):
        for hole in panel.get("holes", []):
            diam = float(hole.get("diameter", 8))
            color_hex = hole.get("color", "#888888")
            x = float(hole.get("x", 0))
            y = float(hole.get("y", 0))
            z = float(hole.get("z", 0))

            radius = diam / 2.0
            cyl = bd.Cylinder(
                radius=radius,
                height=marker_thickness,
                align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER),
            )
            cyl.color = _hex_to_color(color_hex)
            cyl.label = hole.get("hole_type", "hole")
            cyl.move(bd.Location((x, y, z)))
            all_markers.append(cyl)

    if not all_markers:
        compound = bd.Compound()
    else:
        compound = bd.Compound(children=all_markers)
        compound.label = "drilled_holes"

    bd.export_gltf(compound, str(output_path), binary=True)
    return output_path


def load_drilled_holes_from_json(json_path: str | Path) -> dict[str, Any]:
    """Load a drilled-holes JSON file and return the dict."""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _hex_to_color(hex_str: str) -> bd.Color:
    """Convert '#RRGGBB' hex string to build123d Color, alpha=0.9 for overlay."""
    hex_str = hex_str.lstrip("#")
    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0
    return bd.Color(r, g, b, 0.9)