"""Deterministic orchestrator for the project furniture stages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from furniture_cad.cad_bridge import CadBridge
from furniture_contracts.validation import ValidationReport
from furniture_layout.project_layout import ProjectLayout

from .workflow_analyses import AnalysisMixin
from .workflow_constants import (
    ANALYSIS_METHOD_SKILLS,
    ANALYSIS_STAGE_OWNERS,
    EDITABLE_STAGE_OUTPUTS,
    RETRYABLE_STAGES,
    STAGE_INPUT_KEYS,
    OrchestrationResult,
    _stable_digest,
)
from .workflow_project import Project, Revision
from .workflow_reconstruction import ReconstructionMixin
from .workflow_revision_ops import RevisionOpsMixin
from .workflow_stage_runner import StageRunnerMixin
from .workflow_stage_validation import validate_stage_output
from .workflow_state import WorkflowStage
from .workflow_store import JsonProjectStore


class FurnitureOrchestrator(
    RevisionOpsMixin,
    StageRunnerMixin,
    AnalysisMixin,
    ReconstructionMixin,
):
    """Own stage lifecycle while delegating each domain rule to its skill."""

    def __init__(
        self,
        workspace_root: str | Path | None = None,
        cad_bridge: CadBridge | None = None,
        project_store: JsonProjectStore | None = None,
    ) -> None:
        self.workspace_root = Path(
            workspace_root or Path(__file__).resolve().parents[5]
        ).resolve()
        self.cad_bridge = cad_bridge or CadBridge(workspace_root=self.workspace_root)
        self.project_store = project_store

    def create_project(
        self,
        name: str,
        layout: ProjectLayout,
        *,
        stage_inputs: dict[str, Any] | None = None,
    ) -> Project:
        project = Project(name=name)
        project.add_revision(layout, stage_inputs=stage_inputs)
        self._persist(project)
        return project

    def _persist(self, project: Project) -> None:
        if self.project_store is None:
            return
        self.project_store.save(project)

    def _validate_stage_output(
        self,
        revision: Revision,
        stage: WorkflowStage,
        *,
        project_id: str | None = None,
    ) -> ValidationReport:
        return validate_stage_output(
            revision,
            stage,
            load_handoffs=lambda: self._cabinet_handoffs(
                revision, project_id=project_id
            ),
            load_boms=lambda: self._cabinet_boms(revision),
        )
