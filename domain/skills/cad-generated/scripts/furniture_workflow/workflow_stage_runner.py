"""run_next / run_until and stage execution for FurnitureOrchestrator."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from furniture_delivery_validation.validation import (
    ValidationReport,
    validate_delivery,
)
from furniture_feature_tree.feature_tree_builder import panels_to_feature_tree
from furniture_manufacturing.manufacturing_bom import plan_manufacturing
from furniture_panel_planning.panel_pipeline import plan_panel_stage

from .input_adapter import (
    manufacturing_stage_input,
    panel_stage_input,
)
from .workflow_artifact_writer import prepare_artifact_dir, write_artifacts
from .workflow_constants import RETRYABLE_STAGES, OrchestrationResult
from .workflow_project import Project, Revision, StageAttempt
from .workflow_state import STAGE_SEQUENCE, WorkflowStage, parse_stage, stage_index


class StageRunnerMixin:
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

    # retry_stage / select_stage_attempt live in RevisionOpsMixin, which wins the
    # MRO over this mixin; do not re-add copies here.

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
                    revision.layout,
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
            manufacturing = self._bom_from_revision(revision)
            try:
                feature_tree = panels_to_feature_tree(
                    manufacturing.panels,
                    manufacturing.operations,
                    furniture_category=manufacturing.furniture_category,
                    parameters={
                        "width": manufacturing.width,
                        "depth": manufacturing.depth,
                        "height": manufacturing.height,
                        "board_thickness": manufacturing.board_thickness,
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
            layout_sha256=revision.layout_sha256,
            inputs=deepcopy(dict(inputs)),
            output=deepcopy(output) if output is not None else None,
            passed=passed,
            error=error,
        )
        revision.attempts_for(stage).append(attempt)
        if attempt.passed:
            revision.selected_attempts[stage.value] = attempt.number
        return attempt
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
