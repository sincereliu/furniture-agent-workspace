"""Single deterministic orchestrator for the first cabinet vertical slice."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from furniture_cad.cad_bridge import CadBridge
from furniture_cad.validation import validate_cad
from furniture_delivery_validation.validation import ValidationReport
from furniture_design_intent.design_intent import DesignIntent
from furniture_design_intent.validation import validate_intent
from furniture_feature_tree.validation import validate_feature_tree
from furniture_manufacturing.validation import validate_manufacturing
from furniture_panel_planning.validation import validate_panel_output

from .input_adapter import intent_from_spec as translate_intent_from_spec
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
        intent: DesignIntent,
        *,
        stage_inputs: dict[str, Any] | None = None,
    ) -> Project:
        project = Project(name=name)
        project.add_revision(intent, stage_inputs=stage_inputs)
        self._persist(project)
        return project

    @staticmethod
    def intent_from_spec(spec: dict[str, Any]) -> DesignIntent:
        """Compatibility facade for the design-intent translation API."""
        return translate_intent_from_spec(spec)

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
        try:
            if stage == WorkflowStage.DESIGN_INTENT:
                return validate_intent(revision.intent)
            if stage == WorkflowStage.PANELS_PLANNED:
                return validate_panel_output(
                    revision.intent,
                    revision.stage_outputs[stage.value],
                )
            if stage == WorkflowStage.MANUFACTURING_PLANNED:
                return validate_manufacturing(
                    self._spec_from_revision(revision, project_id=project_id),
                    self._bom_from_revision(revision),
                    self._placements_from_revision(
                        revision, project_id=project_id
                    ),
                )
            if stage == WorkflowStage.FEATURE_TREE_PLANNED:
                return validate_feature_tree(revision.stage_outputs[stage.value])
            if stage == WorkflowStage.CAD_GENERATED:
                return validate_cad(self._bridge_from_revision(revision))
            if stage == WorkflowStage.DELIVERY_VALIDATED:
                report = ValidationReport(stage=stage.value)
                if not revision.stage_outputs[stage.value].get("passed", False):
                    report.add_error(
                        "DELIVERY_NOT_VALIDATED",
                        "delivery validation report did not pass",
                    )
                return report
        except (KeyError, TypeError, ValueError) as exc:
            report = ValidationReport(stage=stage.value)
            report.add_error("INVALID_STAGE_OUTPUT", str(exc))
            return report
        raise ValueError(f"unsupported validation stage: {stage.value}")
