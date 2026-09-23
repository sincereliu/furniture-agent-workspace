"""Project and revision aggregate roots for traceable furniture work."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from furniture_delivery_validation.validation import ValidationReport
from furniture_layout.project_layout import ProjectLayout

from .workflow_artifacts import ArtifactManifest
from .workflow_digest import stable_digest
from .workflow_state import WorkflowStage, WorkflowState, parse_stage, utc_now


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _stage_key(stage: str | WorkflowStage) -> str:
    return parse_stage(stage).value


def _remap_stage_keys(data: dict[str, Any]) -> dict[str, Any]:
    return {_stage_key(str(key)): value for key, value in data.items()}


@dataclass
class StageAttempt:
    """One planner execution against a frozen upstream checkpoint."""

    number: int
    stage: str
    layout_sha256: str
    inputs: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] | None = None
    passed: bool = False
    error: str | None = None
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "stage": self.stage,
            "layout_sha256": self.layout_sha256,
            "inputs": deepcopy(self.inputs),
            "output": deepcopy(self.output),
            "passed": self.passed,
            "error": self.error,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StageAttempt":
        return cls(
            number=int(data["number"]),
            stage=_stage_key(str(data["stage"])),
            layout_sha256=str(data["layout_sha256"]),
            inputs=deepcopy(dict(data.get("inputs") or {})),
            output=(
                deepcopy(data["output"])
                if isinstance(data.get("output"), dict)
                else None
            ),
            passed=bool(data.get("passed", False)),
            error=data.get("error"),
            created_at=str(data.get("created_at") or utc_now()),
        )


@dataclass
class Revision:
    number: int
    layout: ProjectLayout
    stage_inputs: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: _id("rev"))
    parent_revision_id: str | None = None
    created_at: str = field(default_factory=utc_now)
    workflow: WorkflowState = field(default_factory=WorkflowState)
    validations: list[ValidationReport] = field(default_factory=list)
    manifest: ArtifactManifest | None = None
    feature_tree: dict[str, Any] | None = None
    stage_outputs: dict[str, Any] = field(default_factory=dict)
    stage_analyses: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    approved_stages: list[str] = field(default_factory=list)
    stage_attempts: dict[str, list[StageAttempt]] = field(default_factory=dict)
    selected_attempts: dict[str, int] = field(default_factory=dict)
    confirmed_panel_sha256: str | None = None
    #: 每个已确认阶段**当时确认的是哪份内容**（阶段名 → 内容摘要）。
    #: 修订继承靠它回指"人真的为这份内容点过头"，见 workflow_inheritance.py。
    approved_digests: dict[str, str] = field(default_factory=dict)
    #: 这一版的哪些阶段沿用了更早那一版的内容（阶段名 → {sha256, from_revision, from_stage}）。
    #: `approved_stages` 的含义是"这份内容已被确认过"，不是"人在这一版又点了一次头"。
    inherited: dict[str, dict[str, Any]] = field(default_factory=dict)

    def confirmed_digest(self, stage: str | WorkflowStage) -> str | None:
        """这个阶段**已确认的那份内容**的摘要；没确认过就是 `None`。

        板件另有一条历史字段 `confirmed_panel_sha256`（下游按它读冻结板件），
        老项目文件里只有它、没有 `approved_digests`，所以这里做一次回退。
        """
        key = _stage_key(stage)
        digest = self.approved_digests.get(key)
        if digest is None and key == WorkflowStage.PANELS_PLANNED.value:
            digest = self.confirmed_panel_sha256
        return digest

    def __post_init__(self) -> None:
        if self.manifest is None:
            self.manifest = ArtifactManifest(source_revision_id=self.id)
        self.stage_outputs.setdefault(
            WorkflowStage.LAYOUT_PLAN.value,
            self.layout.to_dict(),
        )
        if self.feature_tree is not None:
            self.stage_outputs.setdefault(
                WorkflowStage.FEATURE_TREE_PLANNED.value,
                self.feature_tree,
            )

    def is_stage_approved(self, stage: WorkflowStage) -> bool:
        return stage.value in self.approved_stages

    def approve_stage(self, stage: WorkflowStage) -> None:
        if stage.value not in self.approved_stages:
            self.approved_stages.append(stage.value)

    def attempts_for(self, stage: str | WorkflowStage) -> list[StageAttempt]:
        key = _stage_key(stage)
        return self.stage_attempts.setdefault(key, [])

    def selected_attempt(self, stage: str | WorkflowStage) -> StageAttempt | None:
        key = _stage_key(stage)
        number = self.selected_attempts.get(key)
        if number is None:
            return None
        return next(
            (item for item in self.attempts_for(key) if item.number == number),
            None,
        )

    def latest_attempt(self, stage: str | WorkflowStage) -> StageAttempt | None:
        attempts = self.attempts_for(stage)
        return attempts[-1] if attempts else None

    @property
    def layout_sha256(self) -> str:
        return stable_digest(self.layout.to_dict())

    @property
    def panel_sha256(self) -> str | None:
        output = self.stage_outputs.get(WorkflowStage.PANELS_PLANNED.value)
        if not isinstance(output, dict):
            return None
        return stable_digest(output)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "number": self.number,
            "parent_revision_id": self.parent_revision_id,
            "created_at": self.created_at,
            "layout_sha256": self.layout_sha256,
            "panel_sha256": self.panel_sha256,
            "confirmed_panel_sha256": self.confirmed_panel_sha256,
            "layout": self.layout.to_dict(),
            "stage_inputs": self.stage_inputs,
            "workflow": self.workflow.to_dict(),
            "validations": [report.to_dict() for report in self.validations],
            "manifest": self.manifest.to_dict() if self.manifest else None,
            "feature_tree": self.feature_tree,
            "stage_outputs": self.stage_outputs,
            "stage_analyses": self.stage_analyses,
            "approved_stages": self.approved_stages,
            "approved_digests": dict(self.approved_digests),
            "inherited": deepcopy(self.inherited),
            "stage_attempts": {
                stage: [item.to_dict() for item in attempts]
                for stage, attempts in self.stage_attempts.items()
            },
            "selected_attempts": dict(self.selected_attempts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Revision":
        raw_layout = data.get("layout")
        if not isinstance(raw_layout, dict):
            raise ValueError("revision requires layout")
        layout = ProjectLayout.from_dict(raw_layout)
        stage_inputs = data.get("stage_inputs")
        if not isinstance(stage_inputs, dict):
            stage_inputs = {}
        else:
            stage_inputs = deepcopy(stage_inputs)
        stage_outputs = _remap_stage_keys(deepcopy(dict(data.get("stage_outputs", {}))))
        validations: list[ValidationReport] = []
        for item in data.get("validations", []):
            payload = dict(item)
            payload["stage"] = _stage_key(str(payload["stage"]))
            validations.append(ValidationReport.from_dict(payload))
        return cls(
            id=str(data["id"]),
            number=int(data["number"]),
            parent_revision_id=data.get("parent_revision_id"),
            created_at=str(data["created_at"]),
            layout=layout,
            stage_inputs=stage_inputs,
            workflow=WorkflowState.from_dict(data["workflow"]),
            validations=validations,
            manifest=(
                ArtifactManifest.from_dict(data["manifest"])
                if data.get("manifest")
                else None
            ),
            feature_tree=data.get("feature_tree"),
            stage_outputs=stage_outputs,
            stage_analyses=_remap_stage_keys(
                {
                    str(stage): {
                        str(name): dict(record)
                        for name, record in dict(records).items()
                    }
                    for stage, records in dict(data.get("stage_analyses", {})).items()
                }
            ),
            approved_stages=[
                parse_stage(str(value)).value
                for value in data.get("approved_stages", [])
            ],
            stage_attempts=_remap_stage_keys(
                {
                    str(stage): [
                        StageAttempt.from_dict(item) for item in list(records)
                    ]
                    for stage, records in dict(data.get("stage_attempts", {})).items()
                }
            ),
            selected_attempts=_remap_stage_keys(
                {
                    str(stage): int(number)
                    for stage, number in dict(data.get("selected_attempts", {})).items()
                }
            ),
            confirmed_panel_sha256=(
                str(data["confirmed_panel_sha256"])
                if data.get("confirmed_panel_sha256")
                else None
            ),
            approved_digests={
                parse_stage(str(stage)).value: str(digest)
                for stage, digest in dict(data.get("approved_digests", {})).items()
            },
            inherited={
                parse_stage(str(stage)).value: dict(record)
                for stage, record in dict(data.get("inherited", {})).items()
            },
        )


@dataclass
class Project:
    name: str
    id: str = field(default_factory=lambda: _id("project"))
    created_at: str = field(default_factory=utc_now)
    revisions: list[Revision] = field(default_factory=list)

    @property
    def latest(self) -> Revision:
        if not self.revisions:
            raise ValueError("project has no revisions")
        return self.revisions[-1]

    def add_revision(
        self,
        layout: ProjectLayout,
        stage_inputs: dict[str, Any] | None = None,
    ) -> Revision:
        parent = self.revisions[-1] if self.revisions else None
        if parent and parent.manifest:
            parent.manifest.mark_stale()
        revision = Revision(
            number=len(self.revisions) + 1,
            layout=layout,
            stage_inputs=dict(stage_inputs or {}),
            parent_revision_id=parent.id if parent else None,
        )
        self.revisions.append(revision)
        return revision

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "revisions": [revision.to_dict() for revision in self.revisions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            created_at=str(data["created_at"]),
            revisions=[Revision.from_dict(item) for item in data.get("revisions", [])],
        )
