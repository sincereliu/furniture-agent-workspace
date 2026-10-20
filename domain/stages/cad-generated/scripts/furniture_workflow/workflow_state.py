"""Workflow state for one immutable design revision."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowStage(str, Enum):
    LAYOUT_PLAN = "layout_plan"
    PANELS_PLANNED = "panel_plan"
    MANUFACTURING_PLANNED = "manufacture_plan"
    FEATURE_TREE_PLANNED = "feature_tree_planned"
    CAD_GENERATED = "cad_generated"
    DELIVERY_VALIDATED = "delivery_validated"
    FAILED = "failed"


STAGE_SEQUENCE: tuple[WorkflowStage, ...] = (
    WorkflowStage.LAYOUT_PLAN,
    WorkflowStage.PANELS_PLANNED,
    WorkflowStage.MANUFACTURING_PLANNED,
    WorkflowStage.FEATURE_TREE_PLANNED,
    WorkflowStage.CAD_GENERATED,
    WorkflowStage.DELIVERY_VALIDATED,
)

def parse_stage(value: str | WorkflowStage) -> WorkflowStage:
    if isinstance(value, WorkflowStage):
        return value
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
    current: WorkflowStage = WorkflowStage.LAYOUT_PLAN
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

    def move_to(self, stage: WorkflowStage, note: str = "") -> None:
        if self.current == WorkflowStage.FAILED:
            raise ValueError("failed workflow cannot move")
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
                stage=parse_stage(str(item["stage"])),
                timestamp=str(item["timestamp"]),
                note=str(item.get("note", "")),
            )
            for item in data.get("history", [])
        ]
        current = parse_stage(str(data["current"]))
        return cls(current=current, history=history)
