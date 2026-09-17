"""Bounded stage_analyses side path for FurnitureOrchestrator."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Mapping

from furniture_manufacturing.production_simulation import simulate_production
from furniture_manufacturing.prototype_experiment import design_prototype_experiment
from furniture_manufacturing.test_statistics import analyze_prototype_results
from furniture_panel_planning.design_optimization import (
    materialize_optimization_candidate,
    optimize_panel_design,
)
from furniture_panel_planning.quantitative_audit import audit_panel_quantities

from .workflow_constants import (
    ANALYSIS_METHOD_SKILLS,
    ANALYSIS_STAGE_OWNERS,
    _stable_digest,
)
from .workflow_project import Project, Revision
from .workflow_state import WorkflowStage, utc_now


class AnalysisMixin:
    def run_stage_analysis(
        self,
        project: Project,
        analysis: str,
        config: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run one bounded side analysis without changing a stage checkpoint."""

        analysis_name = str(analysis).strip()
        if analysis_name not in ANALYSIS_STAGE_OWNERS:
            supported = ", ".join(sorted(ANALYSIS_STAGE_OWNERS))
            raise ValueError(f"unsupported stage analysis; use one of: {supported}")
        revision = project.latest
        source_stage = ANALYSIS_STAGE_OWNERS[analysis_name]
        source_output = self._stage_source_output(
            revision, source_stage, project_id=project.id
        )
        values = dict(config or {})
        dispatch: dict[str, Callable[[], dict[str, Any]]] = {
            "panel_unit_audit": lambda: audit_panel_quantities(
                source_output,
                values,
            ),
            "panel_optimization": lambda: optimize_panel_design(
                revision.layout,
                source_output,
                values,
            ),
            "prototype_experiment": lambda: design_prototype_experiment(
                source_output,
                values,
            ),
            "test_statistics": lambda: analyze_prototype_results(
                source_output,
                values,
            ),
            "production_simulation": lambda: simulate_production(
                source_output,
                values,
            ),
        }
        report = dispatch[analysis_name]()
        record = {
            "analysis": analysis_name,
            "method_skill": ANALYSIS_METHOD_SKILLS[analysis_name],
            "status": str(report.get("status", "completed")),
            "source_stage": source_stage.value,
            "source_revision_id": revision.id,
            "source_sha256": _stable_digest(source_output),
            "created_at": utc_now(),
            "report": deepcopy(report),
        }
        revision.stage_analyses.setdefault(source_stage.value, {})[
            analysis_name
        ] = record
        revision.workflow.record(
            f"{analysis_name} analysis recorded for {source_stage.value}"
        )
        return deepcopy(record)

    def apply_panel_optimization_candidate(
        self,
        project: Project,
        candidate_index: int,
    ) -> Revision:
        """Materialize an explicitly selected Pareto candidate as a new revision."""

        revision = project.latest
        stage = WorkflowStage.PANELS_PLANNED
        analyses = revision.stage_analyses.get(stage.value, {})
        record = analyses.get("panel_optimization")
        if not isinstance(record, Mapping):
            raise ValueError("run panel_optimization before selecting a candidate")
        source_output = self._confirmed_panel_output(
            revision, project_id=project.id
        )
        if record.get("source_revision_id") != revision.id or record.get(
            "source_sha256"
        ) != _stable_digest(source_output):
            raise ValueError("panel optimization is stale; run it again")
        report = record.get("report")
        candidates = report.get("candidates") if isinstance(report, Mapping) else None
        if not isinstance(candidates, list):
            raise ValueError("panel optimization has no selectable candidates")
        if isinstance(candidate_index, bool) or not 0 <= candidate_index < len(candidates):
            raise ValueError("candidate_index is outside the Pareto candidate list")
        selected = candidates[candidate_index]
        if not isinstance(selected, Mapping):
            raise ValueError("selected optimization candidate is invalid")
        output = materialize_optimization_candidate(
            revision.layout,
            selected,
        )
        if selected.get("stage_output_sha256") != _stable_digest(output):
            raise ValueError("selected candidate no longer materializes reproducibly")
        return self.revise_stage_output(project, stage, output)
