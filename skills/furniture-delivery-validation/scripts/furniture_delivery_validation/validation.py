"""Structured validation results shared by every workflow layer."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any


REQUIRED_DELIVERY_KINDS = frozenset(
    {
        "design_intent",
        "layout_plan",
        "panel_plan",
        "manufacturing_plan",
        "feature_tree",
        "bom",
        "drilled_holes",
        "drilled_holes_glb",
        "cad_source",
        "step",
        "viewer_topology",
    }
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    path: str = ""


@dataclass
class ValidationReport:
    stage: str
    issues: list[ValidationIssue] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now)

    @property
    def passed(self) -> bool:
        return not any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)

    def add_error(self, code: str, message: str, path: str = "") -> None:
        self.issues.append(ValidationIssue(code, message, ValidationSeverity.ERROR, path))

    def add_warning(self, code: str, message: str, path: str = "") -> None:
        self.issues.append(ValidationIssue(code, message, ValidationSeverity.WARNING, path))

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "passed": self.passed,
            "created_at": self.created_at,
            "issues": [
                {**asdict(issue), "severity": issue.severity.value} for issue in self.issues
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationReport":
        return cls(
            stage=str(data["stage"]),
            created_at=str(data["created_at"]),
            issues=[
                ValidationIssue(
                    code=str(item["code"]),
                    message=str(item["message"]),
                    severity=ValidationSeverity(item["severity"]),
                    path=str(item.get("path", "")),
                )
                for item in data.get("issues", [])
            ],
        )


def validate_delivery(
    manifest: Any,
    *,
    source_revision_id: str,
) -> ValidationReport:
    """Validate artifact existence, integrity, lineage, and readiness."""
    report = ValidationReport(stage="delivery_validated")
    if manifest is None:
        report.add_error("MISSING_MANIFEST", "delivery has no artifact manifest")
        return report
    if manifest.source_revision_id != source_revision_id:
        report.add_error(
            "MANIFEST_REVISION_MISMATCH",
            "artifact manifest does not belong to the current revision",
            "manifest",
        )

    artifacts = list(manifest.artifacts)
    kinds = {artifact.kind for artifact in artifacts}
    for kind in sorted(REQUIRED_DELIVERY_KINDS - kinds):
        report.add_error(
            "MISSING_REQUIRED_ARTIFACT",
            f"required delivery artifact is missing: {kind}",
            kind,
        )

    for artifact in artifacts:
        path = Path(artifact.path)
        if artifact.source_revision_id != source_revision_id:
            report.add_error(
                "ARTIFACT_REVISION_MISMATCH",
                f"{artifact.kind} belongs to another revision",
                artifact.kind,
            )
        if artifact.stale:
            report.add_error(
                "STALE_ARTIFACT",
                f"{artifact.kind} is marked stale",
                artifact.kind,
            )
        if not path.is_file():
            report.add_error(
                "MISSING_ARTIFACT",
                artifact.path,
                artifact.kind,
            )
            continue
        content = path.read_bytes()
        if not content:
            report.add_error(
                "EMPTY_ARTIFACT",
                artifact.path,
                artifact.kind,
            )
            continue
        if len(content) != artifact.size_bytes:
            report.add_error(
                "ARTIFACT_SIZE_MISMATCH",
                f"{artifact.kind} size no longer matches its manifest",
                artifact.kind,
            )
        if sha256(content).hexdigest() != artifact.sha256:
            report.add_error(
                "ARTIFACT_HASH_MISMATCH",
                f"{artifact.kind} content no longer matches its manifest",
                artifact.kind,
            )
    return report
