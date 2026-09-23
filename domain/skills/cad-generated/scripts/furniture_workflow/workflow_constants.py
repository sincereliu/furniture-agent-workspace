"""Orchestrator constants and result type."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from furniture_cad.cad_bridge import BridgeResult

from .cabinet_pipeline import CabinetPipelineResult
from .workflow_digest import stable_digest as _stable_digest
from .workflow_project import Project, Revision
from .workflow_state import WorkflowStage


EDITABLE_STAGE_OUTPUTS = {
    WorkflowStage.PANELS_PLANNED,
    WorkflowStage.MANUFACTURING_PLANNED,
    WorkflowStage.FEATURE_TREE_PLANNED,
}
RETRYABLE_STAGES = EDITABLE_STAGE_OUTPUTS
STAGE_INPUT_KEYS = {
    WorkflowStage.PANELS_PLANNED: "panels",
    WorkflowStage.MANUFACTURING_PLANNED: "manufacturing",
}

ANALYSIS_STAGE_OWNERS = {
    "panel_unit_audit": WorkflowStage.PANELS_PLANNED,
    "panel_optimization": WorkflowStage.PANELS_PLANNED,
    "prototype_experiment": WorkflowStage.MANUFACTURING_PLANNED,
    "test_statistics": WorkflowStage.MANUFACTURING_PLANNED,
    "production_simulation": WorkflowStage.MANUFACTURING_PLANNED,
}

ANALYSIS_METHOD_SKILLS = {
    "panel_unit_audit": "uncertainty-and-units",
    "panel_optimization": "pymoo",
    "prototype_experiment": "experimental-design",
    "test_statistics": "statistical-analysis",
    "production_simulation": "simpy",
}


@dataclass(frozen=True)
class OrchestrationResult:
    project: Project
    revision: Revision
    pipeline: CabinetPipelineResult | None
    bridge: BridgeResult | None = None
    drilled_holes: dict[str, Any] | None = None
