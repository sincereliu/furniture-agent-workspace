"""Single deterministic orchestrator for the first cabinet vertical slice."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from furniture_cad.cad_bridge import BridgeResult, CadBridge
from furniture_cad.validation import validate_cad
from furniture_delivery_validation.validation import (
    ValidationReport,
    validate_delivery,
)
from furniture_design_intent.design_intent import DesignIntent
from furniture_design_intent.validation import validate_intent
from furniture_feature_tree.feature_tree_builder import panels_to_feature_tree
from furniture_feature_tree.validation import validate_feature_tree
from furniture_manufacturing.connection_points import ConnectionPoint
from furniture_manufacturing.features import feature_from_dict
from furniture_manufacturing.manufacturing_bom import (
    BOMReport,
    emit_drilled_holes,
    plan_manufacturing,
    recompute_features,
)
from furniture_manufacturing.manufacturing_models import (
    HardwareRecord,
    MachiningOperation,
    PanelRecord,
)
from furniture_manufacturing.production_simulation import simulate_production
from furniture_manufacturing.prototype_experiment import design_prototype_experiment
from furniture_manufacturing.test_statistics import analyze_prototype_results
from furniture_manufacturing.validation import validate_manufacturing
from furniture_panel_planning.cabinet_identity import (
    primary_cabinet,
    require_primary_handoff,
)
from furniture_panel_planning.design_optimization import (
    materialize_optimization_candidate,
    optimize_panel_design,
)
from furniture_panel_planning.panel_models import PanelPlacement
from furniture_panel_planning.panel_pipeline import plan_panel_stage
from furniture_panel_planning.panel_spec import FurnitureSpec
from furniture_panel_planning.quantitative_audit import audit_panel_quantities
from furniture_panel_planning.structure_planning import CabinetStructure
from furniture_panel_planning.validation import validate_panel_output

from .cabinet_pipeline import CabinetPipelineResult
from .input_adapter import (
    intent_from_spec as translate_intent_from_spec,
    manufacturing_stage_input,
    panel_stage_input,
)
from .workflow_artifact_writer import prepare_artifact_dir, write_artifacts
from .workflow_project import Project, Revision, StageAttempt
from .workflow_state import (
    STAGE_SEQUENCE,
    WorkflowStage,
    WorkflowState,
    parse_stage,
    stage_index,
    utc_now,
)
from .workflow_store import JsonProjectStore


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


def _stable_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class OrchestrationResult:
    project: Project
    revision: Revision
    pipeline: CabinetPipelineResult | None
    bridge: BridgeResult | None = None
    drilled_holes: dict[str, Any] | None = None


class FurnitureOrchestrator:
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

    def revise(self, project: Project, intent: DesignIntent) -> Revision:
        """Start a new revision at stage 1; all parent artifacts become stale."""
        revision = project.add_revision(intent)
        self._persist(project)
        return revision

    def revise_stage_output(
        self,
        project: Project,
        stage: str | WorkflowStage,
        output: dict[str, Any],
    ) -> Revision:
        """Create a revision from an edited serial planning-stage output."""
        changed_stage = parse_stage(stage)
        if changed_stage not in EDITABLE_STAGE_OUTPUTS:
            editable = ", ".join(item.value for item in EDITABLE_STAGE_OUTPUTS)
            raise ValueError(f"stage output is not directly editable; use one of: {editable}")

        parent = project.latest
        if changed_stage.value not in parent.stage_outputs:
            raise ValueError(f"stage has no output to revise: {changed_stage.value}")

        revision = project.add_revision(
            DesignIntent.from_dict(parent.intent.to_dict()),
            stage_inputs=deepcopy(parent.stage_inputs),
        )
        revision.stage_outputs = {
            key: deepcopy(value)
            for key, value in parent.stage_outputs.items()
            if parse_stage(key) in STAGE_SEQUENCE
            and stage_index(parse_stage(key)) < stage_index(changed_stage)
        }
        revision.stage_outputs[WorkflowStage.DESIGN_INTENT.value] = (
            revision.intent.to_dict()
        )
        if changed_stage == WorkflowStage.MANUFACTURING_PLANNED:
            # 直接编辑制造输出后，重算派生快照（features/connection_points），
            # 避免它们与 panels/operations 漂移。
            revised_panels = [
                PanelRecord.from_dict(item)
                for item in output.get("panels", [])
            ]
            revised_operations = [
                MachiningOperation(**item)
                for item in output.get("operations", [])
            ]
            features, connection_points = recompute_features(
                revised_panels, revised_operations
            )
            output = {
                **output,
                "features": [asdict(feature) for feature in features],
                "connection_points": [
                    asdict(point) for point in connection_points
                ],
            }
        revision.stage_outputs[changed_stage.value] = deepcopy(output)
        if changed_stage == WorkflowStage.PANELS_PLANNED:
            revised_spec = primary_cabinet(output).get("spec", {})
            panel_input = revision.stage_inputs.setdefault("panels", {})
            parameters = panel_input.setdefault("parameters", {})
            if isinstance(revised_spec, dict) and isinstance(parameters, dict):
                for key, value in revised_spec.items():
                    if key in {
                        "furniture_category",
                        "width",
                        "depth",
                        "height",
                    }:
                        continue
                    parameters[key] = value
        revision.approved_stages = [
            value
            for value in parent.approved_stages
            if parse_stage(value) in STAGE_SEQUENCE
            and stage_index(parse_stage(value)) < stage_index(changed_stage)
        ]
        revision.workflow = WorkflowState()
        if changed_stage != WorkflowStage.DESIGN_INTENT:
            revision.workflow.advance(
                changed_stage,
                f"{changed_stage.value} revised; downstream outputs invalidated",
            )
        if changed_stage == WorkflowStage.FEATURE_TREE_PLANNED:
            revision.feature_tree = deepcopy(output)
        revision.stage_attempts[changed_stage.value] = [
            StageAttempt(
                number=1,
                stage=changed_stage.value,
                intent_sha256=revision.intent_sha256,
                inputs=deepcopy(self._stage_input_for(revision, changed_stage)),
                output=deepcopy(output),
                passed=True,
            )
        ]
        revision.selected_attempts[changed_stage.value] = 1
        if stage_index(changed_stage) > stage_index(WorkflowStage.PANELS_PLANNED):
            revision.confirmed_panel_sha256 = parent.confirmed_panel_sha256
        self._persist(project)
        return revision

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
                revision.intent,
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
            revision.intent,
            selected,
        )
        if selected.get("stage_output_sha256") != _stable_digest(output):
            raise ValueError("selected candidate no longer materializes reproducibly")
        return self.revise_stage_output(project, stage, output)

    @staticmethod
    def intent_from_spec(spec: dict[str, Any]) -> DesignIntent:
        """Compatibility facade for the design-intent translation API."""
        return translate_intent_from_spec(spec)

    def confirm_intent(self, project: Project) -> Revision:
        return self.confirm_stage(project, WorkflowStage.DESIGN_INTENT)

    def confirm_stage(
        self,
        project: Project,
        stage: str | WorkflowStage | None = None,
    ) -> Revision:
        """Approve the current stage so the next stage may execute."""
        revision = project.latest
        current = revision.workflow.current
        requested = parse_stage(stage) if stage is not None else current
        if current == WorkflowStage.FAILED:
            raise ValueError("failed revision must be replaced with a new revision")
        if requested != current:
            raise ValueError(
                f"only the current stage may be confirmed: {current.value}"
            )
        if requested.value not in revision.stage_outputs:
            raise ValueError(f"current stage has no output: {requested.value}")

        report = self._latest_stage_validation(revision, requested)
        if report is None or not report.passed:
            report = self._validate_stage_output(
                revision, requested, project_id=project.id
            )
            revision.validations.append(report)
        if not report.passed:
            revision.workflow.fail(f"{requested.value} validation failed")
            self._persist(project)
            return revision

        if requested == WorkflowStage.DESIGN_INTENT:
            revision.intent = revision.intent.confirm()
            revision.stage_outputs[requested.value] = revision.intent.to_dict()
        if requested == WorkflowStage.PANELS_PLANNED:
            revision.confirmed_panel_sha256 = revision.panel_sha256

        revision.approve_stage(requested)
        revision.workflow.record(f"{requested.value} confirmed")
        self._persist(project)
        return revision

    def run_next(
        self,
        project: Project,
        *,
        stage_input: Mapping[str, Any] | None = None,
        output_root: str | Path | None = None,
        artifact_name: str | None = None,
        generate_cad: bool = False,
        force: bool = False,
    ) -> OrchestrationResult:
        """Execute exactly one stage after the current confirmed checkpoint."""
        revision = project.latest
        if revision.workflow.current == WorkflowStage.FAILED:
            return self._result(project)
        current_index = stage_index(revision.workflow.current)
        if current_index == len(STAGE_SEQUENCE) - 1:
            return self._result(project)
        if stage_input:
            if not revision.is_stage_approved(revision.workflow.current):
                raise ValueError(
                    "stage_input requires the current stage to be confirmed"
                )
            next_stage = STAGE_SEQUENCE[current_index + 1]
            self._apply_retry_input(revision, next_stage, stage_input)
        result = self.run_until(
            project,
            STAGE_SEQUENCE[current_index + 1],
            output_root=output_root,
            artifact_name=artifact_name,
            generate_cad=generate_cad,
            force=force,
        )
        self._persist(project)
        return result

    def retry_stage(
        self,
        project: Project,
        stage: str | WorkflowStage,
        *,
        stage_input: dict[str, Any] | None = None,
        output_root: str | Path | None = None,
        artifact_name: str | None = None,
        generate_cad: bool = False,
        force: bool = False,
    ) -> OrchestrationResult:
        """Re-run a planning stage against the frozen confirmed intent."""
        revision = project.latest
        if revision.workflow.current == WorkflowStage.FAILED:
            raise ValueError("failed revision must be replaced with a new revision")
        requested = parse_stage(stage)
        if requested not in RETRYABLE_STAGES:
            retryable = ", ".join(item.value for item in RETRYABLE_STAGES)
            raise ValueError(f"stage is not retryable; use one of: {retryable}")
        predecessor = STAGE_SEQUENCE[stage_index(requested) - 1]
        if not revision.is_stage_approved(predecessor):
            raise ValueError(
                f"retry requires confirmed predecessor: {predecessor.value}"
            )
        if stage_input is not None:
            self._apply_retry_input(revision, requested, stage_input)
        if (
            revision.is_stage_approved(requested)
            or stage_index(revision.workflow.current) > stage_index(requested)
        ):
            self._invalidate_from(revision, requested)
        self._execute_stage(
            project,
            revision,
            requested,
            output_root=output_root,
            artifact_name=artifact_name,
            generate_cad=generate_cad,
            force=force,
        )
        self._persist(project)
        return self._result(project)

    def select_stage_attempt(
        self,
        project: Project,
        stage: str | WorkflowStage,
        number: int,
    ) -> Revision:
        """Promote a passed attempt to the current unconfirmed candidate."""
        revision = project.latest
        if revision.workflow.current == WorkflowStage.FAILED:
            raise ValueError("failed revision must be replaced with a new revision")
        requested = parse_stage(stage)
        if requested not in RETRYABLE_STAGES:
            retryable = ", ".join(item.value for item in RETRYABLE_STAGES)
            raise ValueError(f"stage is not retryable; use one of: {retryable}")
        attempt = next(
            (
                item
                for item in revision.attempts_for(requested)
                if item.number == number
            ),
            None,
        )
        if attempt is None:
            raise ValueError(f"stage has no attempt {number}: {requested.value}")
        if not attempt.passed or attempt.output is None:
            raise ValueError("cannot select a failed attempt")
        if attempt.intent_sha256 != revision.intent_sha256:
            raise ValueError("attempt does not match the frozen intent")
        if (
            revision.is_stage_approved(requested)
            or stage_index(revision.workflow.current) > stage_index(requested)
        ):
            self._invalidate_from(revision, requested)
        revision.selected_attempts[requested.value] = attempt.number
        revision.stage_outputs[requested.value] = deepcopy(attempt.output)
        if requested == WorkflowStage.FEATURE_TREE_PLANNED:
            revision.feature_tree = deepcopy(attempt.output)
        if revision.workflow.current != requested:
            revision.workflow.move_to(
                requested,
                f"{requested.value} attempt {attempt.number} selected",
            )
        else:
            revision.workflow.record(
                f"{requested.value} attempt {attempt.number} selected"
            )
        self._persist(project)
        return revision

    def run_until(
        self,
        project: Project,
        target_stage: str | WorkflowStage,
        *,
        output_root: str | Path | None = None,
        artifact_name: str | None = None,
        generate_cad: bool = False,
        force: bool = False,
    ) -> OrchestrationResult:
        """Run toward a target, pausing at the first unconfirmed stage."""
        target = parse_stage(target_stage)
        revision = project.latest
        attempted_stage: WorkflowStage | None = None
        try:
            while (
                revision.workflow.current != WorkflowStage.FAILED
                and stage_index(revision.workflow.current) < stage_index(target)
            ):
                current = revision.workflow.current
                if not revision.is_stage_approved(current):
                    break
                next_stage = STAGE_SEQUENCE[stage_index(current) + 1]
                if (
                    next_stage in RETRYABLE_STAGES
                    and revision.attempts_for(next_stage)
                ):
                    break
                attempted_stage = next_stage
                self._execute_stage(
                    project,
                    revision,
                    next_stage,
                    output_root=output_root,
                    artifact_name=artifact_name,
                    generate_cad=generate_cad,
                    force=force,
                )
                if revision.workflow.current == WorkflowStage.FAILED:
                    break
                latest_attempt = revision.latest_attempt(next_stage)
                if latest_attempt is not None and not latest_attempt.passed:
                    break
                break

            self._persist(project)
            return self._result(project)
        except (OSError, TypeError, ValueError) as exc:
            report = ValidationReport(
                stage=(attempted_stage.value if attempted_stage else "orchestration")
            )
            report.add_error("STAGE_EXECUTION_FAILED", str(exc))
            revision.validations.append(report)
            if attempted_stage in RETRYABLE_STAGES:
                self._record_attempt(
                    revision,
                    attempted_stage,
                    inputs=self._stage_input_for(revision, attempted_stage),
                    error=str(exc),
                )
                revision.workflow.record(
                    f"{attempted_stage.value} attempt failed"
                )
                self._persist(project)
                return self._result(project)
            revision.workflow.fail(str(exc))
            self._persist(project)
            return self._result(project)

    def _execute_stage(
        self,
        project: Project,
        revision: Revision,
        stage: WorkflowStage,
        *,
        output_root: str | Path | None,
        artifact_name: str | None,
        generate_cad: bool,
        force: bool,
    ) -> None:
        if stage == WorkflowStage.PANELS_PLANNED:
            stage_input = panel_stage_input(revision.stage_inputs)
            try:
                output = plan_panel_stage(
                    revision.intent,
                    stage_input.get("parameters", {}),
                )
            except (TypeError, ValueError) as exc:
                self._fail_retryable_stage(revision, stage, stage_input, str(exc))
                return
            self._complete_retryable_stage(
                revision,
                stage,
                output,
                stage_input,
                "construction, exact clearances, and physical panels planned",
                project_id=project.id,
            )
            return

        if stage == WorkflowStage.MANUFACTURING_PLANNED:
            spec = self._spec_from_revision(revision, project_id=project.id)
            stage_input = manufacturing_stage_input(revision.stage_inputs)
            try:
                bom = plan_manufacturing(
                    spec,
                    self._placements_from_revision(revision, project_id=project.id),
                    requested_options=stage_input.get("parameters", {}),
                    appearance=stage_input.get("appearance", {}),
                )
            except (TypeError, ValueError) as exc:
                self._fail_retryable_stage(revision, stage, stage_input, str(exc))
                return
            self._complete_retryable_stage(
                revision,
                stage,
                asdict(bom),
                stage_input,
                "materials, hardware, and preliminary BOM planned",
                project_id=project.id,
            )
            return

        if stage == WorkflowStage.FEATURE_TREE_PLANNED:
            spec = self._spec_from_revision(revision, project_id=project.id)
            manufacturing = self._bom_from_revision(revision)
            try:
                feature_tree = panels_to_feature_tree(
                    manufacturing.panels,
                    manufacturing.operations,
                    furniture_category=spec.furniture_category,
                    parameters={
                        "width": spec.width,
                        "depth": spec.depth,
                        "height": spec.height,
                        "board_thickness": spec.board_thickness,
                    },
                )
            except (TypeError, ValueError) as exc:
                self._fail_retryable_stage(revision, stage, {}, str(exc))
                return
            self._complete_retryable_stage(
                revision,
                stage,
                feature_tree,
                {},
                "Feature Tree v2 with target-specific machining cuts planned",
                project_id=project.id,
            )
            return

        if stage == WorkflowStage.CAD_GENERATED:
            if output_root is None:
                raise ValueError("CAD generation requires output_root")
            if not generate_cad:
                raise ValueError("CAD generation requires generate_cad=True")
            pipeline = self._pipeline_from_revision(
                revision, project_id=project.id
            )
            if pipeline is None:
                raise ValueError("manufacturing stage must exist before CAD generation")
            artifact_dir = prepare_artifact_dir(
                self.workspace_root,
                output_root,
                project,
                revision,
                artifact_name=artifact_name,
            )
            source_path, step_path = write_artifacts(
                self.workspace_root,
                revision,
                pipeline,
                artifact_dir,
                artifact_name=artifact_name,
                panel_output=self._confirmed_panel_output(
                    revision, project_id=project.id
                ),
            )
            bridge = self.cad_bridge.generate_from_source(
                source_path,
                step_path,
                force=force,
            )
            revision.stage_outputs[stage.value] = asdict(bridge)
            if bridge.status == "ok":
                if bridge.step_path:
                    revision.manifest.add_file("step", bridge.step_path)
                if bridge.topology_path:
                    revision.manifest.add_file(
                        "viewer_topology",
                        bridge.topology_path,
                        package_path=bridge.viewer_package_path,
                    )
            report = self._validate_stage_output(
                revision, stage, project_id=project.id
            )
            revision.validations.append(report)
            if not report.passed:
                revision.workflow.fail(bridge.message)
                return
            revision.workflow.advance(stage, "STEP and Viewer topology generated")
            return

        if stage == WorkflowStage.DELIVERY_VALIDATED:
            report = validate_delivery(
                revision.manifest,
                source_revision_id=revision.id,
                stage_outputs=self._resolved_stage_outputs(
                    revision, project_id=project.id
                ),
                approved_stages=revision.approved_stages,
                stage_validations=revision.validations,
                stage_analyses=revision.stage_analyses,
            )
            revision.stage_outputs[stage.value] = report.to_dict()
            revision.validations.append(report)
            if not report.passed:
                revision.workflow.fail("delivery validation failed")
                return
            revision.workflow.advance(stage, "delivery artifacts verified")
            return

        raise ValueError(f"stage is not executable: {stage.value}")

    def _complete_retryable_stage(
        self,
        revision: Revision,
        stage: WorkflowStage,
        output: dict[str, Any],
        inputs: dict[str, Any],
        note: str,
        *,
        project_id: str | None = None,
    ) -> None:
        revision.stage_outputs[stage.value] = deepcopy(output)
        report = self._validate_stage_output(
            revision, stage, project_id=project_id
        )
        revision.validations.append(report)
        attempt = self._record_attempt(
            revision,
            stage,
            inputs=inputs,
            output=output,
            report=report,
        )
        if not attempt.passed:
            selected = revision.selected_attempt(stage)
            if selected is None or selected.output is None:
                revision.stage_outputs.pop(stage.value, None)
                if stage == WorkflowStage.FEATURE_TREE_PLANNED:
                    revision.feature_tree = None
            else:
                revision.stage_outputs[stage.value] = deepcopy(selected.output)
                if stage == WorkflowStage.FEATURE_TREE_PLANNED:
                    revision.feature_tree = deepcopy(selected.output)
            revision.workflow.record(
                f"{stage.value} attempt {attempt.number} failed"
            )
            return
        if stage == WorkflowStage.FEATURE_TREE_PLANNED:
            revision.feature_tree = deepcopy(output)
        revision.workflow.advance(stage, note)

    def _fail_retryable_stage(
        self,
        revision: Revision,
        stage: WorkflowStage,
        inputs: dict[str, Any],
        error: str,
    ) -> None:
        report = ValidationReport(stage=stage.value)
        report.add_error("STAGE_EXECUTION_FAILED", error)
        revision.validations.append(report)
        attempt = self._record_attempt(
            revision,
            stage,
            inputs=inputs,
            error=error,
        )
        revision.workflow.record(
            f"{stage.value} attempt {attempt.number} failed"
        )

    def _record_attempt(
        self,
        revision: Revision,
        stage: WorkflowStage,
        *,
        inputs: Mapping[str, Any],
        output: dict[str, Any] | None = None,
        error: str | None = None,
        report: ValidationReport | None = None,
    ) -> StageAttempt:
        passed = error is None and (report is None or report.passed)
        if not passed and error is None and report is not None:
            error = "; ".join(issue.message for issue in report.issues)
        attempt = StageAttempt(
            number=len(revision.attempts_for(stage)) + 1,
            stage=stage.value,
            intent_sha256=revision.intent_sha256,
            inputs=deepcopy(dict(inputs)),
            output=deepcopy(output) if output is not None else None,
            passed=passed,
            error=error,
        )
        revision.attempts_for(stage).append(attempt)
        if attempt.passed:
            revision.selected_attempts[stage.value] = attempt.number
        return attempt

    def _invalidate_from(self, revision: Revision, stage: WorkflowStage) -> None:
        index = stage_index(stage)
        revision.approved_stages = [
            value
            for value in revision.approved_stages
            if parse_stage(value) in STAGE_SEQUENCE
            and stage_index(parse_stage(value)) < index
        ]
        revision.stage_outputs = {
            key: value
            for key, value in revision.stage_outputs.items()
            if parse_stage(key) not in STAGE_SEQUENCE
            or stage_index(parse_stage(key)) < index
        }
        revision.stage_attempts = {
            key: value
            for key, value in revision.stage_attempts.items()
            if parse_stage(key) not in STAGE_SEQUENCE
            or stage_index(parse_stage(key)) < index
            or key == stage.value
        }
        revision.selected_attempts = {
            key: value
            for key, value in revision.selected_attempts.items()
            if key in revision.stage_attempts and key != stage.value
        }
        if index <= stage_index(WorkflowStage.PANELS_PLANNED):
            revision.confirmed_panel_sha256 = None
        if index <= stage_index(WorkflowStage.FEATURE_TREE_PLANNED):
            revision.feature_tree = None
        predecessor = STAGE_SEQUENCE[index - 1]
        if (
            revision.workflow.current != WorkflowStage.FAILED
            and (
                revision.workflow.current not in STAGE_SEQUENCE
                or stage_index(revision.workflow.current) >= index
            )
        ):
            revision.workflow.move_to(
                predecessor,
                f"{stage.value} retry; downstream outputs invalidated",
            )

    def _apply_retry_input(
        self,
        revision: Revision,
        stage: WorkflowStage,
        stage_input: Mapping[str, Any],
    ) -> None:
        key = STAGE_INPUT_KEYS.get(stage)
        if key is None:
            raise ValueError(f"stage does not accept retry inputs: {stage.value}")
        payload = deepcopy(dict(stage_input))
        if key == "panels" and "parameters" not in payload:
            payload = {"parameters": payload}
        revision.stage_inputs[key] = payload

    def _stage_input_for(
        self,
        revision: Revision,
        stage: WorkflowStage,
    ) -> dict[str, Any]:
        if stage == WorkflowStage.PANELS_PLANNED:
            return panel_stage_input(revision.stage_inputs)
        if stage == WorkflowStage.MANUFACTURING_PLANNED:
            return manufacturing_stage_input(revision.stage_inputs)
        return {}

    def _persist(self, project: Project) -> None:
        if self.project_store is None:
            return
        self.project_store.save(project)

    @staticmethod
    def _latest_stage_validation(
        revision: Revision,
        stage: WorkflowStage,
    ) -> ValidationReport | None:
        return next(
            (
                report
                for report in reversed(revision.validations)
                if report.stage == stage.value
            ),
            None,
        )

    def _result(self, project: Project) -> OrchestrationResult:
        revision = project.latest
        pipeline = self._pipeline_from_revision(
            revision, project_id=project.id
        )
        return OrchestrationResult(
            project=project,
            revision=revision,
            pipeline=pipeline,
            bridge=self._bridge_from_revision(revision),
            drilled_holes=(
                emit_drilled_holes(pipeline.bom)
                if pipeline is not None
                else None
            ),
        )

    def _pipeline_from_revision(
        self,
        revision: Revision,
        *,
        project_id: str | None = None,
    ) -> CabinetPipelineResult | None:
        required = (
            WorkflowStage.PANELS_PLANNED.value,
            WorkflowStage.MANUFACTURING_PLANNED.value,
        )
        if not all(key in revision.stage_outputs for key in required):
            return None
        return CabinetPipelineResult(
            spec=self._spec_from_revision(revision, project_id=project_id),
            structure=self._structure_from_revision(
                revision, project_id=project_id
            ),
            placements=self._placements_from_revision(
                revision, project_id=project_id
            ),
            panels=self._panels_from_revision(revision),
            bom=self._bom_from_revision(revision),
        )

    def _resolved_stage_outputs(
        self,
        revision: Revision,
        *,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        outputs = dict(revision.stage_outputs)
        if WorkflowStage.PANELS_PLANNED.value in outputs:
            outputs[WorkflowStage.PANELS_PLANNED.value] = (
                self._confirmed_panel_output(revision, project_id=project_id)
            )
        return outputs

    def _stage_source_output(
        self,
        revision: Revision,
        stage: WorkflowStage,
        *,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        if stage == WorkflowStage.PANELS_PLANNED:
            return self._confirmed_panel_output(revision, project_id=project_id)
        output = revision.stage_outputs.get(stage.value)
        if not isinstance(output, dict):
            raise ValueError(f"stage output is required: {stage.value}")
        return output

    def _confirmed_panel_output(
        self,
        revision: Revision,
        *,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        live = revision.stage_outputs.get(WorkflowStage.PANELS_PLANNED.value)
        if not isinstance(live, dict):
            raise ValueError("panel_plan output is required")
        digest = revision.confirmed_panel_sha256
        if self.project_store is None or not project_id or not digest:
            return live
        path = self.project_store.panel_path(project_id, digest)
        if not path.is_file():
            raise ValueError(f"frozen panel plan is missing: {path}")
        frozen = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(frozen, dict):
            raise ValueError("frozen panel plan must be an object")
        return frozen

    def _spec_from_revision(
        self,
        revision: Revision,
        *,
        project_id: str | None = None,
    ) -> FurnitureSpec:
        spec, _, _ = require_primary_handoff(
            self._confirmed_panel_output(revision, project_id=project_id)
        )
        return FurnitureSpec.from_dict(spec)

    def _structure_from_revision(
        self,
        revision: Revision,
        *,
        project_id: str | None = None,
    ) -> CabinetStructure:
        _, structure, _ = require_primary_handoff(
            self._confirmed_panel_output(revision, project_id=project_id)
        )
        return CabinetStructure.from_dict(structure)

    def _placements_from_revision(
        self,
        revision: Revision,
        *,
        project_id: str | None = None,
    ) -> list[PanelPlacement]:
        _, _, panels = require_primary_handoff(
            self._confirmed_panel_output(revision, project_id=project_id)
        )
        return [PanelPlacement.from_dict(item) for item in panels]

    @staticmethod
    def _panels_from_revision(revision: Revision) -> list[PanelRecord]:
        output = revision.stage_outputs[WorkflowStage.MANUFACTURING_PLANNED.value]
        return [PanelRecord.from_dict(item) for item in output.get("panels", [])]

    @staticmethod
    def _bom_from_revision(revision: Revision) -> BOMReport:
        output = revision.stage_outputs[WorkflowStage.MANUFACTURING_PLANNED.value]
        return BOMReport(
            furniture_name=str(output["furniture_name"]),
            dimensions=str(output["dimensions"]),
            panels=[PanelRecord.from_dict(item) for item in output.get("panels", [])],
            hardware=[HardwareRecord(**item) for item in output.get("hardware", [])],
            operations=[
                MachiningOperation(**item) for item in output.get("operations", [])
            ],
            total_area_m2=float(output.get("total_area_m2", 0.0)),
            readiness=str(output.get("readiness", "preliminary")),
            requested_options=dict(output.get("requested_options", {})),
            appearance=dict(output.get("appearance", {})),
            features=[
                feature_from_dict(item) for item in output.get("features", [])
            ],
            connection_points=[
                ConnectionPoint.from_dict(item)
                for item in output.get("connection_points", [])
            ],
        )

    @staticmethod
    def _bridge_from_revision(revision: Revision) -> BridgeResult | None:
        output = revision.stage_outputs.get(WorkflowStage.CAD_GENERATED.value)
        return BridgeResult(**output) if output else None

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
