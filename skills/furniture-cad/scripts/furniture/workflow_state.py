"""Workflow state for one immutable design revision."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowStage(str, Enum):
    DRAFT_INTENT = "draft_intent"
    INTENT_CONFIRMED = "intent_confirmed"
    PANEL_PLANNED = "panel_planned"
    FEATURE_TREE_VALIDATED = "feature_tree_validated"
    ARTIFACTS_GENERATED = "artifacts_generated"
    ARTIFACTS_VERIFIED = "artifacts_verified"
    FAILED = "failed"


@dataclass(frozen=True)
class WorkflowEvent:
    stage: WorkflowStage
    timestamp: str
    note: str = ""


@dataclass
class WorkflowState:
    current: WorkflowStage = WorkflowStage.DRAFT_INTENT
    history: list[WorkflowEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.history:
            self.history.append(WorkflowEvent(self.current, utc_now(), "revision created"))

    def advance(self, stage: WorkflowStage, note: str = "") -> None:
        if self.current == WorkflowStage.FAILED:
            raise ValueError("failed workflow cannot advance")
        self.current = stage
        self.history.append(WorkflowEvent(stage, utc_now(), note))

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
                stage=WorkflowStage(item["stage"]),
                timestamp=str(item["timestamp"]),
                note=str(item.get("note", "")),
            )
            for item in data.get("history", [])
        ]
        return cls(current=WorkflowStage(data["current"]), history=history)
