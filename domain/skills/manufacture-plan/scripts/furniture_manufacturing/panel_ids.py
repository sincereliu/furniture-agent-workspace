"""Qualified ids on a confirmed panel handoff.

Frozen boards use ``{cabinet_id}__{role}``. Manufacturing reads that
separator to recover a role or rebuild a target id.
"""

from __future__ import annotations

from typing import Any


PANEL_ID_SEPARATOR = "__"
DEFAULT_CABINET_ID = "cabinet_1"


def qualify_panel_id(cabinet_id: str, role: str) -> str:
    """Return the board id for a cabinet-local role."""
    if not role:
        raise ValueError("panel role is required")
    if role.startswith(f"{cabinet_id}{PANEL_ID_SEPARATOR}"):
        return role
    if PANEL_ID_SEPARATOR in role:
        return role
    return f"{cabinet_id}{PANEL_ID_SEPARATOR}{role}"


def panel_role(panel_id: str) -> str:
    """Return the cabinet-local role from a qualified id."""
    if PANEL_ID_SEPARATOR in panel_id:
        return panel_id.split(PANEL_ID_SEPARATOR, 1)[1]
    return panel_id


def panel_cabinet_id(panel_id: str) -> str | None:
    """Return the cabinet id prefix, or None when the id is already a role."""
    if PANEL_ID_SEPARATOR not in panel_id:
        return None
    return panel_id.split(PANEL_ID_SEPARATOR, 1)[0]


def index_by_role(
    items: Any,
    *,
    parent_id: str | None = None,
) -> dict[str, Any]:
    """Index boards by cabinet-local role, optionally within one parent."""
    indexed: dict[str, Any] = {}
    for item in items:
        item_parent = getattr(item, "parent_id", "") or ""
        if parent_id is not None and item_parent and item_parent != parent_id:
            continue
        role = getattr(item, "role", "") or panel_role(
            getattr(item, "id", None) or getattr(item, "label", "")
        )
        indexed[role] = item
    return indexed
