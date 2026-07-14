"""Manufacturing-stage edge-banding policy."""

from __future__ import annotations

from typing import Dict


DEFAULT_EDGE_RULES: Dict[str, Dict[str, str]] = {
    "side": {"四边": "ABS 1.0mm同色"},
    "top": {"四边": "ABS 1.0mm同色"},
    "bottom": {"四边": "ABS 1.0mm同色"},
    "fixed_shelf": {"四边": "ABS 1.0mm同色"},
    "movable_shelf": {"四边": "ABS 1.0mm同色"},
    "divider": {"四边": "ABS 1.0mm同色"},
    "toe_kick": {"四边": "ABS 1.0mm同色"},
    "door": {"四边": "ABS 1.0mm同色"},
    "back": {},
}


def get_edge_banding(
    panel_type: str,
    rules: Dict[str, Dict[str, str]] | None = None,
) -> Dict[str, str]:
    return dict((rules or DEFAULT_EDGE_RULES).get(panel_type, {}))

