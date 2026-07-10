"""Traceable files produced from a project revision."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

from furniture.workflow_state import utc_now


@dataclass
class ArtifactRecord:
    kind: str
    path: str
    sha256: str
    size_bytes: int
    source_revision_id: str
    created_at: str = field(default_factory=utc_now)
    stale: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ArtifactManifest:
    source_revision_id: str
    artifacts: list[ArtifactRecord] = field(default_factory=list)

    def add_file(self, kind: str, path: str | Path, **metadata: Any) -> ArtifactRecord:
        resolved = Path(path).resolve()
        if not resolved.is_file():
            raise ValueError(f"artifact does not exist: {resolved}")
        content = resolved.read_bytes()
        record = ArtifactRecord(
            kind=kind,
            path=str(resolved),
            sha256=sha256(content).hexdigest(),
            size_bytes=len(content),
            source_revision_id=self.source_revision_id,
            metadata=metadata,
        )
        self.artifacts.append(record)
        return record

    def mark_stale(self) -> None:
        for artifact in self.artifacts:
            artifact.stale = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_revision_id": self.source_revision_id,
            "artifacts": [asdict(artifact) for artifact in self.artifacts],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArtifactManifest":
        return cls(
            source_revision_id=str(data["source_revision_id"]),
            artifacts=[ArtifactRecord(**item) for item in data.get("artifacts", [])],
        )
