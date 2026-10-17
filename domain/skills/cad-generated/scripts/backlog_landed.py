"""Versions of local backlog items the program has already landed.

``0`` means not landed. A local item stays open while its own version is
higher than the number here. When the work lands, set this number to that
item version in the same change, then run ``backlog_reconcile.py``.
"""

from __future__ import annotations


LANDED_VERSIONS: dict[str, dict[str, int]] = {
    "panel-plan.md": {
        "full-height-divider": 0,
        "half-height-divider": 0,
        "door-rows": 0,
        "pair-grouping": 0,
        "multi-door-cases": 0,
    },
    "layout-plan.md": {
        "drag-snap": 0,
        "opening-edits": 0,
        "preview-draft-switch": 0,
        "room-merge": 0,
        "cabinet-id-check": 1,
        "overhead-camera": 1,
        "wall-fill": 1,
        "page-writes-project": 1,
        "page-identity": 1,
        "share-view-mode": 1,
        "content-digest": 1,
        "readonly-preview-chrome": 1,
        "view-controls": 1,
        "camera-mirror": 1,
        "origin-axes": 1,
    },
    "manufacture-plan.md": {
        "connection-points": 0,
        "cover-cam": 0,
        "full-drawer": 0,
        "appearance-sync": 0,
        "flat-dimensions": 0,
        "back-cam-types": 1,
    },
    "cad-generated.md": {
        "content-addressed-reuse": 0,
        "decision-log-followups": 0,
        "room-confirm": 0,
        "edit-page-polish": 0,
        "share-token": 0,
        "panel-replay": 0,
        "downstream-per-cabinet": 1,
        "per-cabinet-parameters": 1,
        "decision-log-core": 1,
        "revision-inheritance": 1,
        "revise-keeps-inputs": 1,
        "no-legacy-migration": 1,
    },
}
