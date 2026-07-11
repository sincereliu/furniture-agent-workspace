"""Workflow state for one immutable design revision."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowStage(str, Enum):
    DESIGN_INTENT = "design_intent"
    LAYOUT_PLANNED = "layout_planned"
    PANELS_PLANNED = "panels_planned"
    MANUFACTURING_PLANNED = "manufacturing_planned"
    FEATURE_TREE_PLANNED = "feature_tree_planned"
    CAD_GENERATED = "cad_generated"
    DELIVERY_VALIDATED = "delivery_validated"
    FAILED = "failed"

    # Compatibility aliases for project files and callers created before the
    # seven-stage workflow became explicit.
    DRAFT_INTENT = DESIGN_INTENT
    INTENT_CONFIRMED = DESIGN_INTENT
    PANEL_PLANNED = PANELS_PLANNED
    FEATURE_TREE_VALIDATED = FEATURE_TREE_PLANNED
    ARTIFACTS_GENERATED = CAD_GENERATED
    ARTIFACTS_VERIFIED = DELIVERY_VALIDATED


STAGE_SEQUENCE: tuple[WorkflowStage, ...] = (
    WorkflowStage.DESIGN_INTENT,
    WorkflowStage.LAYOUT_PLANNED,
    WorkflowStage.PANELS_PLANNED,
    WorkflowStage.MANUFACTURING_PLANNED,
    WorkflowStage.FEATURE_TREE_PLANNED,
    WorkflowStage.CAD_GENERATED,
    WorkflowStage.DELIVERY_VALIDATED,
)

LEGACY_STAGE_VALUES = {
    "draft_intent": WorkflowStage.DESIGN_INTENT,
    "intent_confirmed": WorkflowStage.DESIGN_INTENT,
    "panel_planned": WorkflowStage.PANELS_PLANNED,
    "feature_tree_validated": WorkflowStage.FEATURE_TREE_PLANNED,
    "artifacts_generated": WorkflowStage.CAD_GENERATED,
    "artifacts_verified": WorkflowStage.DELIVERY_VALIDATED,
}


def parse_stage(value: str | WorkflowStage) -> WorkflowStage:
    if isinstance(value, WorkflowStage):
        return value
    if value in LEGACY_STAGE_VALUES:
        return LEGACY_STAGE_VALUES[value]
    return WorkflowStage(value)


def stage_index(stage: WorkflowStage) -> int:
    if stage == WorkflowStage.FAILED:
        raise ValueError("failed is not a runnable workflow stage")
    return STAGE_SEQUENCE.index(stage)


@dataclass(frozen=True)
class WorkflowEvent:
    stage: WorkflowStage
    timestamp: str
    note: str = ""


@dataclass
class WorkflowState:
    current: WorkflowStage = WorkflowStage.DESIGN_INTENT
    history: list[WorkflowEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.history:
            self.history.append(WorkflowEvent(self.current, utc_now(), "revision created"))

    def advance(self, stage: WorkflowStage, note: str = "") -> None:
        if self.current == WorkflowStage.FAILED:
            raise ValueError("failed workflow cannot advance")
        if stage != WorkflowStage.FAILED and stage_index(stage) < stage_index(self.current):
            raise ValueError(
                f"workflow cannot move backward from {self.current.value} to {stage.value}"
            )
        self.current = stage
        self.history.append(WorkflowEvent(stage, utc_now(), note))

    def record(self, note: str) -> None:
        self.history.append(WorkflowEvent(self.current, utc_now(), note))

    def fail(self, note: str) -> None:
        self.current = WorkflowStage.FAILED
        self.history.append(WorkflowEvent(WorkflowStage.FAILED, utc_now(), note))

    def to_dict(self) -> dict[str, Any]:
        return {
            "current": self.current.value,
            "history": [
                {**asdict(event), "stage": event.stage.value} for event in self.history
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowState":
        history = [
            WorkflowEvent(
                stage=parse_stage(str(item["stage"])),
                timestamp=str(item["timestamp"]),
                note=str(item.get("note", "")),
            )
            for item in data.get("history", [])
        ]
        return cls(current=parse_stage(str(data["current"])), history=history)
