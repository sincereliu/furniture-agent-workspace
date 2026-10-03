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
        "layout_plan",
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
    "layout_plan",
    "panel_plan",
    "manufacture_plan",
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
    _validate_manufacturing_readiness(report, artifacts, stage_outputs)
    _validate_cabinet_coverage(report, artifacts, stage_outputs)

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
            artifact.kind in {"manufacturing_plan", "bom"}
            and artifact.metadata.get("readiness")
            and artifact.metadata.get("readiness") != manufacturing_readiness
            and not artifact.metadata.get("cabinet_id")
        ):
            # 柜级 BOM 的就绪度按**它自己那台**核对（见 `_validate_manufacturing_readiness`）；
            # 这里只管阶段级记录：它带的是"整份工程"的就绪度（最弱的那台）。
            report.add_error(
                "ARTIFACT_READINESS_MISMATCH",
                f"{artifact.kind} readiness does not match the manufacturing stage",
                artifact.kind,
            )
    return report


#: 每台规划过的柜都必须有的柜级产物种类（2026-10-02 之前，规划了三台
#: 只有一台有 STEP/钻孔文件也照样通过——逐柜后必须拦住）。
REQUIRED_CABINET_KINDS = ("step", "drilled_holes", "six_side_drill_xml")

#: 就绪度从弱到强；整份工程取最弱的那一台（一台没定，整份不算定）。
READINESS_ORDER = ("preliminary", "accepted", "factory_ready")

#: 制造与特征树产物是**逐柜**的：`{"cabinets": [{"id", "bom"|"tree"}]}`。
CABINET_STAGE_OUTPUTS = ("manufacture_plan", "feature_tree_planned")


def _planned_cabinets(
    stage_outputs: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """规划过的柜子（id + 那份 BOM），按制造产物的顺序。"""
    if stage_outputs is None:
        return []
    manufacturing = stage_outputs.get("manufacture_plan")
    if not isinstance(manufacturing, Mapping):
        return []
    raw = manufacturing.get("cabinets")
    if not isinstance(raw, list):
        return []
    return [
        {"id": str(item.get("id") or ""), "bom": dict(item.get("bom") or {})}
        for item in raw
        if isinstance(item, Mapping)
    ]


def _validate_cabinet_coverage(
    report: ValidationReport,
    artifacts: Sequence[Any],
    stage_outputs: Mapping[str, Any] | None,
) -> None:
    """逐柜齐全：每台规划过的柜都要有自己的 STEP / 钻孔 / 六面钻文件。"""
    cabinets = _planned_cabinets(stage_outputs)
    if not cabinets:
        return
    kinds_by_cabinet: dict[str, set[str]] = {item["id"]: set() for item in cabinets}
    for artifact in artifacts:
        cabinet_id = str(artifact.metadata.get("cabinet_id") or "")
        if cabinet_id in kinds_by_cabinet:
            kinds_by_cabinet[cabinet_id].add(artifact.kind)
    for item in cabinets:
        cabinet_id = item["id"]
        for kind in REQUIRED_CABINET_KINDS:
            if kind not in kinds_by_cabinet[cabinet_id]:
                report.add_error(
                    "MISSING_CABINET_ARTIFACT",
                    f"{cabinet_id}: no {kind} artifact for a planned cabinet",
                    f"{kind}.{cabinet_id}",
                )


def _validate_manufacturing_readiness(
    report: ValidationReport,
    artifacts: Sequence[Any],
    stage_outputs: Mapping[str, Any] | None,
) -> None:
    """就绪度：整份取最弱；柜级记录与它自己那份 BOM 对齐。"""
    cabinets = _planned_cabinets(stage_outputs)
    values = [str(item["bom"].get("readiness", READINESS_ORDER[0])) for item in cabinets]
    ranks = {value: index for index, value in enumerate(READINESS_ORDER)}
    weakest = READINESS_ORDER[-1]
    for value in values:
        if ranks.get(value, 0) < ranks[weakest]:
            weakest = value if value in ranks else READINESS_ORDER[0]
    if weakest == "preliminary":
        report.add_warning(
            "MANUFACTURING_PRELIMINARY",
            "manufacturing plan is still preliminary and is not factory-ready",
            "manufacture_plan.readiness",
        )
    by_cabinet = {item["id"]: item["bom"] for item in cabinets}
    for artifact in artifacts:
        if artifact.kind not in {"manufacturing_plan", "bom"}:
            continue
        cabinet_id = str(artifact.metadata.get("cabinet_id") or "")
        expected = (
            by_cabinet.get(cabinet_id, {}).get("readiness")
            if cabinet_id
            else weakest
        )
        if expected and artifact.metadata.get("readiness") != expected:
            report.add_error(
                "ARTIFACT_READINESS_MISMATCH",
                f"{artifact.kind} readiness does not match the manufacturing stage",
                artifact.kind,
            )


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
    """整份工程的制造就绪度 = **最弱**的那一台（逐柜产物的汇总）。"""
    cabinets = _planned_cabinets(stage_outputs)
    if not cabinets:
        return ""
    ranks = {value: index for index, value in enumerate(READINESS_ORDER)}
    weakest = READINESS_ORDER[-1]
    for item in cabinets:
        value = str(item["bom"].get("readiness", READINESS_ORDER[0]))
        if ranks.get(value, 0) < ranks[weakest]:
            weakest = value if value in ranks else READINESS_ORDER[0]
    return weakest
