"""Structured validation results shared by every workflow layer."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Sequence


REQUIRED_DELIVERY_KINDS = frozenset(
    {
        "design_intent",
        "panel_plan",
        "manufacturing_plan",
        "feature_tree",
        "bom",
        "drilled_holes",
        "drilled_holes_glb",
        "drilled_holes_step",
        "drilled_holes_step_glb",
        "six_side_drill_xml",
        "cad_source",
        "step",
        "viewer_topology",
    }
)

PRE_DELIVERY_STAGES = (
    "design_intent",
    "panels_planned",
    "manufacturing_planned",
    "feature_tree_planned",
    "cad_generated",
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
    stage_outputs: Mapping[str, Any] | None = None,
    approved_stages: Sequence[str] | None = None,
    stage_validations: Sequence[ValidationReport] | None = None,
    stage_analyses: Mapping[str, Any] | None = None,
) -> ValidationReport:
    """Validate checkpoint lineage plus artifact existence and integrity."""
    report = ValidationReport(stage="delivery_validated")
    _validate_checkpoint_lineage(
        report,
        stage_outputs=stage_outputs,
        approved_stages=approved_stages,
        stage_validations=stage_validations,
    )
    _validate_analysis_lineage(
        report,
        source_revision_id=source_revision_id,
        stage_outputs=stage_outputs,
        stage_analyses=stage_analyses,
    )
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

    manufacturing_readiness = _manufacturing_readiness(stage_outputs)
    if manufacturing_readiness == "preliminary":
        report.add_warning(
            "MANUFACTURING_PRELIMINARY",
            "manufacturing plan is still preliminary and is not factory-ready",
            "manufacturing_planned.readiness",
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
        if (
            manufacturing_readiness
            and artifact.kind in {"manufacturing_plan", "bom"}
            and artifact.metadata.get("readiness") != manufacturing_readiness
        ):
            report.add_error(
                "ARTIFACT_READINESS_MISMATCH",
                f"{artifact.kind} readiness does not match the manufacturing stage",
                artifact.kind,
            )
    return report


def _stable_digest(value: Any) -> str:
    import json

    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def _validate_analysis_lineage(
    report: ValidationReport,
    *,
    source_revision_id: str,
    stage_outputs: Mapping[str, Any] | None,
    stage_analyses: Mapping[str, Any] | None,
) -> None:
    if not stage_analyses:
        return
    for stage, raw_records in stage_analyses.items():
        if not isinstance(raw_records, Mapping):
            report.add_error(
                "INVALID_STAGE_ANALYSES",
                f"analysis records for {stage} must be an object",
                f"stage_analyses.{stage}",
            )
            continue
        source_output = stage_outputs.get(stage) if stage_outputs else None
        if source_output is None:
            report.add_error(
                "ANALYSIS_SOURCE_STAGE_MISSING",
                f"analysis source stage is missing: {stage}",
                f"stage_analyses.{stage}",
            )
            continue
        expected_digest = _stable_digest(source_output)
        for name, raw_record in raw_records.items():
            path = f"stage_analyses.{stage}.{name}"
            if not isinstance(raw_record, Mapping):
                report.add_error(
                    "INVALID_STAGE_ANALYSIS",
                    f"analysis record must be an object: {name}",
                    path,
                )
                continue
            if raw_record.get("source_revision_id") != source_revision_id:
                report.add_error(
                    "ANALYSIS_REVISION_MISMATCH",
                    f"analysis belongs to another revision: {name}",
                    path,
                )
            if raw_record.get("source_stage") != stage:
                report.add_error(
                    "ANALYSIS_STAGE_MISMATCH",
                    f"analysis source stage does not match its container: {name}",
                    path,
                )
            if raw_record.get("source_sha256") != expected_digest:
                report.add_error(
                    "ANALYSIS_SOURCE_HASH_MISMATCH",
                    f"analysis no longer matches its source stage: {name}",
                    path,
                )
            status = str(raw_record.get("status", ""))
            if status in {"unavailable", "descriptive_only"}:
                report.add_warning(
                    "ANALYSIS_INCOMPLETE",
                    f"optional analysis is {status}: {name}",
                    path,
                )


def _validate_checkpoint_lineage(
    report: ValidationReport,
    *,
    stage_outputs: Mapping[str, Any] | None,
    approved_stages: Sequence[str] | None,
    stage_validations: Sequence[ValidationReport] | None,
) -> None:
    if stage_outputs is not None:
        for stage in PRE_DELIVERY_STAGES:
            if stage not in stage_outputs:
                report.add_error(
                    "MISSING_STAGE_OUTPUT",
                    f"current revision is missing stage output: {stage}",
                    stage,
                )

    if approved_stages is not None:
        approved = set(approved_stages)
        for stage in PRE_DELIVERY_STAGES:
            if stage not in approved:
                report.add_error(
                    "UNAPPROVED_DELIVERY_SOURCE_STAGE",
                    f"delivery source stage is not approved: {stage}",
                    stage,
                )

    if stage_validations is not None:
        latest_by_stage: dict[str, ValidationReport] = {}
        for validation in stage_validations:
            latest_by_stage[validation.stage] = validation
        for stage in PRE_DELIVERY_STAGES:
            validation = latest_by_stage.get(stage)
            if validation is None:
                report.add_error(
                    "MISSING_STAGE_VALIDATION",
                    f"current revision has no validation report for: {stage}",
                    stage,
                )
            elif not validation.passed:
                report.add_error(
                    "FAILED_STAGE_VALIDATION",
                    f"current revision has a failed validation report for: {stage}",
                    stage,
                )


def _manufacturing_readiness(
    stage_outputs: Mapping[str, Any] | None,
) -> str:
    if stage_outputs is None:
        return ""
    manufacturing = stage_outputs.get("manufacturing_planned")
    if not isinstance(manufacturing, Mapping):
        return ""
    return str(manufacturing.get("readiness", "preliminary"))
