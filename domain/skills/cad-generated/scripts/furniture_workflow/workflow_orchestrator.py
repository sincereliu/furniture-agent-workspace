"""Deterministic orchestrator for the project furniture stages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from furniture_cad.cad_bridge import BridgeResult, CadBridge
from furniture_cad.validation import validate_cad
from furniture_delivery_validation.validation import (
    ValidationReport,
    ValidationSeverity,
)
from furniture_layout.project_layout import ProjectLayout
from furniture_layout.layout_figures import check_layout_figures
from furniture_feature_tree.validation import validate_feature_tree
from furniture_manufacturing.manufacturing_handoff import (
    cabinets_from_manufacturing,
)
from furniture_manufacturing.validation import validate_manufacturing
from furniture_panel_planning.validation import validate_panel_output

from .input_adapter import panel_envelopes_from_layout
from .workflow_analyses import AnalysisMixin
from .workflow_cabinets import cabinets_from_bridges, cabinets_from_feature_trees
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

    def _validate_every_cabinet(
        self,
        stage: WorkflowStage,
        revision: Revision,
        *,
        project_id: str | None = None,
    ) -> ValidationReport:
        """**逐柜**验收制造计划：每台柜都按它自己的 spec / 板件验一遍。

        一台不合格就整阶段不合格——不许"主柜过了就算过"。问题里点名是哪一台。
        """
        report = ValidationReport(stage=stage.value)
        handoffs = {
            cabinet_id: (spec, placements)
            for cabinet_id, spec, placements in self._cabinet_handoffs(
                revision, project_id=project_id
            )
        }
        for cabinet_id, bom in self._cabinet_boms(revision):
            spec, placements = handoffs[cabinet_id]
            self._merge_issues(
                report, cabinet_id, validate_manufacturing(spec, bom, placements)
            )
        return report

    def _validate_every_tree(
        self, stage: WorkflowStage, revision: Revision
    ) -> ValidationReport:
        """**逐柜**验收特征树，与制造产物一一对应；问题里点名是哪一台。"""
        report = ValidationReport(stage=stage.value)
        for entry in cabinets_from_feature_trees(
            revision.stage_outputs[stage.value]
        ):
            self._merge_issues(
                report, entry["id"], validate_feature_tree(entry["tree"])
            )
        return report

    @staticmethod
    def _merge_issues(
        report: ValidationReport,
        cabinet_id: str,
        cabinet_report: ValidationReport,
    ) -> None:
        for issue in cabinet_report.issues:
            message = f"{cabinet_id}: {issue.message}"
            if issue.severity == ValidationSeverity.WARNING:
                report.add_warning(issue.code, message, issue.path)
            else:
                report.add_error(issue.code, message, issue.path)

    def _validate_every_bridge(
        self, stage: WorkflowStage, revision: Revision
    ) -> ValidationReport:
        """**逐柜**验收 CAD，并且要求"规划过的每一台都在里面"。

        少了哪一台、哪一台失败，问题里都要点名——不然又会出现"三台只有一台到车间、
        交付照样通过"。
        """
        report = ValidationReport(stage=stage.value)
        entries = cabinets_from_bridges(revision.stage_outputs[stage.value])
        planned = [
            entry["id"]
            for entry in cabinets_from_manufacturing(
                revision.stage_outputs[WorkflowStage.MANUFACTURING_PLANNED.value]
            )
        ]
        produced = [entry["id"] for entry in entries]
        for cabinet_id in planned:
            if cabinet_id not in produced:
                report.add_error(
                    "MISSING_CABINET_CAD",
                    f"{cabinet_id}: no CAD result for a planned cabinet",
                )
        for entry in entries:
            self._merge_issues(
                report,
                entry["id"],
                validate_cad(BridgeResult(**entry["bridge"])),
            )
        return report

    def _validate_stage_output(
        self,
        revision: Revision,
        stage: WorkflowStage,
        *,
        project_id: str | None = None,
    ) -> ValidationReport:
        try:
            if stage == WorkflowStage.LAYOUT_PLAN:
                return check_layout_figures(revision.layout.to_dict())
            if stage == WorkflowStage.PANELS_PLANNED:
                return validate_panel_output(
                    panel_envelopes_from_layout(revision.layout),
                    revision.stage_outputs[stage.value],
                )
            if stage == WorkflowStage.MANUFACTURING_PLANNED:
                return self._validate_every_cabinet(
                    stage,
                    revision,
                    project_id=project_id,
                )
            if stage == WorkflowStage.FEATURE_TREE_PLANNED:
                return self._validate_every_tree(stage, revision)
            if stage == WorkflowStage.CAD_GENERATED:
                return self._validate_every_bridge(stage, revision)
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
