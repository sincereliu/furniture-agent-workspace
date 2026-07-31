"""Project and revision aggregate roots for traceable furniture work."""

from __future__ import annotations

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
    approved_stages: list[str] = field(default_factory=list)

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

    @property
    def intent_sha256(self) -> str:
        encoded = json.dumps(
            self.intent.to_dict(), ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
        return sha256(encoded).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "number": self.number,
            "parent_revision_id": self.parent_revision_id,
            "created_at": self.created_at,
            "intent_sha256": self.intent_sha256,
            "intent": self.intent.to_dict(),
            "stage_inputs": self.stage_inputs,
            "workflow": self.workflow.to_dict(),
            "validations": [report.to_dict() for report in self.validations],
            "manifest": self.manifest.to_dict() if self.manifest else None,
            "feature_tree": self.feature_tree,
            "stage_outputs": self.stage_outputs,
            "approved_stages": self.approved_stages,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Revision":
        raw_intent = dict(data["intent"])
        stage_inputs = data.get("stage_inputs")
        if not isinstance(stage_inputs, dict):
            stage_inputs = _legacy_stage_inputs(raw_intent)
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
            stage_outputs=dict(data.get("stage_outputs", {})),
            approved_stages=[
                parse_stage(str(value)).value
                for value in data.get("approved_stages", [])
            ],
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
    """Move schema-v1 downstream fields out of DesignIntent when loading."""
    layout = dict(raw_intent.get("layout", {}))
    structure = dict(raw_intent.get("structure", {}))
    manufacturing_keys = {
        "hinge_brand",
        "hinge_variant",
        "hinge_overlay",
        "hinge_angle",
        "options",
    }
    manufacturing = {
        key: structure.pop(key)
        for key in list(structure)
        if key in manufacturing_keys
    }
    room = layout.pop("room", None)
    placement = layout.pop("placement", None)
    result: dict[str, Any] = {
        "layout": {
            "parameters": layout,
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
    constraints = list(raw_intent.get("constraints", []))
    mappings = dict(raw_intent.get("constraint_mappings", {}))
    for constraint in constraints:
        target = str(mappings.get(constraint, "informational"))
        record = {"text": constraint, "target": target}
        if target.startswith("layout."):
            result["layout"].setdefault("constraints", []).append(record)
        elif target.startswith("structure."):
            result["panels"].setdefault("constraints", []).append(record)
        elif target == "informational":
            result.setdefault("informational_constraints", []).append(constraint)
        else:
            result.setdefault("envelope_constraints", []).append(record)
    return result
