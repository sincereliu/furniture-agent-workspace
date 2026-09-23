"""Content digest: the one implementation of "is this the same content?".

Used as a content identity across the workflow (frozen layout/panel file names,
``layout_sha256`` / ``panel_sha256``, analysis lineage, side-by-side comparison
in tests). Two copies with different JSON separators would give two digests for
the same payload — exactly the kind of drift that is painful to trace later, so
there is deliberately only this one.
"""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any


def stable_digest(value: Any) -> str:
    """sha256 over canonical JSON: key-sorted, compact separators, UTF-8.

    Canonical form matters more than the algorithm: the same content must always
    produce the same value, whatever order the caller built it in.
    """
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()
