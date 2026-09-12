"""Project and revision aggregate roots for traceable furniture work."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any
from uuid import uuid4

from furniture_delivery_validation.validation import ValidationReport
from furniture_design_intent.design_intent import DesignIntent

from .workflow_artifacts import ArtifactManifest
from .workflow_state import WorkflowStage, WorkflowState, parse_stage, utc_now


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return sha256(encoded).hexdigest()


def _stage_key(stage: str | WorkflowStage) -> str:
    return stage.value if isinstance(stage, WorkflowStage) else str(stage)


@dataclass
class StageAttempt:
    """One planner execution against a frozen upstream checkpoint."""

    number: int
    stage: str
    intent_sha256: str
    inputs: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] | None = None
    passed: bool = False
    error: str | None = None
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "stage": self.stage,
            "intent_sha256": self.intent_sha256,
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
            stage=str(data["stage"]),
            intent_sha256=str(data["intent_sha256"]),
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
    intent: DesignIntent
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

    def __post_init__(self) -> None:
        if self.manifest is None:
            self.manifest = ArtifactManifest(source_revision_id=self.id)
        self.stage_outputs.setdefault(
            WorkflowStage.DESIGN_INTENT.value,
            self.intent.to_dict(),
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
    def intent_sha256(self) -> str:
        return _canonical_sha256(self.intent.to_dict())

    @property
    def panel_sha256(self) -> str | None:
        output = self.stage_outputs.get(WorkflowStage.PANELS_PLANNED.value)
        if not isinstance(output, dict):
            return None
        return _canonical_sha256(output)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "number": self.number,
            "parent_revision_id": self.parent_revision_id,
            "created_at": self.created_at,
            "intent_sha256": self.intent_sha256,
            "panel_sha256": self.panel_sha256,
            "confirmed_panel_sha256": self.confirmed_panel_sha256,
            "intent": self.intent.to_dict(),
            "stage_inputs": self.stage_inputs,
            "workflow": self.workflow.to_dict(),
            "validations": [report.to_dict() for report in self.validations],
            "manifest": self.manifest.to_dict() if self.manifest else None,
            "feature_tree": self.feature_tree,
            "stage_outputs": self.stage_outputs,
            "stage_analyses": self.stage_analyses,
            "approved_stages": self.approved_stages,
            "stage_attempts": {
                stage: [item.to_dict() for item in attempts]
                for stage, attempts in self.stage_attempts.items()
            },
            "selected_attempts": dict(self.selected_attempts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Revision":
        raw_intent = dict(data["intent"])
        stage_inputs = data.get("stage_inputs")
        if not isinstance(stage_inputs, dict):
            stage_inputs = _legacy_stage_inputs(raw_intent)
        else:
            stage_inputs = deepcopy(stage_inputs)
        stage_outputs = deepcopy(dict(data.get("stage_outputs", {})))
        return cls(
            id=str(data["id"]),
            number=int(data["number"]),
            parent_revision_id=data.get("parent_revision_id"),
            created_at=str(data["created_at"]),
            intent=DesignIntent.from_dict(raw_intent),
            stage_inputs=stage_inputs,
            workflow=WorkflowState.from_dict(data["workflow"]),
            validations=[
                ValidationReport.from_dict(item) for item in data.get("validations", [])
            ],
            manifest=(
                ArtifactManifest.from_dict(data["manifest"])
                if data.get("manifest")
                else None
            ),
            feature_tree=data.get("feature_tree"),
            stage_outputs=stage_outputs,
            stage_analyses={
                str(stage): {
                    str(name): dict(record)
                    for name, record in dict(records).items()
                }
                for stage, records in dict(data.get("stage_analyses", {})).items()
            },
            approved_stages=[
                parse_stage(str(value)).value
                for value in data.get("approved_stages", [])
            ],
            stage_attempts={
                str(stage): [
                    StageAttempt.from_dict(item) for item in list(records)
                ]
                for stage, records in dict(data.get("stage_attempts", {})).items()
            },
            selected_attempts={
                str(stage): int(number)
                for stage, number in dict(data.get("selected_attempts", {})).items()
            },
            confirmed_panel_sha256=(
                str(data["confirmed_panel_sha256"])
                if data.get("confirmed_panel_sha256")
                else None
            ),
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
        intent: DesignIntent,
        stage_inputs: dict[str, Any] | None = None,
    ) -> Revision:
        parent = self.revisions[-1] if self.revisions else None
        if parent and parent.manifest:
            parent.manifest.mark_stale()
        revision = Revision(
            number=len(self.revisions) + 1,
            intent=intent,
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


def _legacy_stage_inputs(raw_intent: dict[str, Any]) -> dict[str, Any]:
    """Move schema-v1 downstream fields out of DesignIntent when loading.

    Delete this whole compatibility path once schema-v1 persisted projects are no
    longer supported.
    """
    layout = dict(raw_intent.get("layout", {}))
    structure = dict(raw_intent.get("structure", {}))
    manufacturing_keys = {
        "options",
    }
    manufacturing = {
        key: structure.pop(key)
        for key in list(structure)
        if key in manufacturing_keys
    }
    room = layout.pop("room", None)
    placement = layout.pop("placement", None)
    # ``door_count`` is retained here only for loading historical layout-shaped
    # payloads into the canonical panel-stage ``n_doors`` input.
    for key in ("n_doors", "door_count"):
        if key in layout:
            structure[key] = layout.pop(key)
    result: dict[str, Any] = {
        "layout": {
            "room": room,
            "placement": placement,
        },
        "panels": {"parameters": structure},
        "manufacturing": {
            "parameters": manufacturing,
            "appearance": dict(raw_intent.get("appearance", {})),
        },
    }
    purpose = str(raw_intent.get("purpose", "")).strip()
    if purpose:
        result["layout"]["purpose"] = purpose
    if layout:
        result["layout"]["legacy_parameters"] = layout
    constraints = list(raw_intent.get("constraints", []))
    mappings = dict(raw_intent.get("constraint_mappings", {}))
    for constraint in constraints:
        target = str(mappings.get(constraint, "informational"))
        record = {"text": constraint, "target": target}
        if target.startswith("layout."):
            field = target.split(".", 1)[1]
            if field in {"n_doors", "door_count"}:
                result["panels"].setdefault("constraints", []).append(record)
            else:
                result["layout"].setdefault("constraints", []).append(record)
        elif target.startswith("structure."):
            result["panels"].setdefault("constraints", []).append(record)
        elif target == "informational":
            result.setdefault("informational_constraints", []).append(constraint)
        else:
            result.setdefault("envelope_constraints", []).append(record)
    return result
