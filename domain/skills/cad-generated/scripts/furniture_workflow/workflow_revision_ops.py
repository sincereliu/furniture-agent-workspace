"""Confirm, freeze, retry, and revise operations for FurnitureOrchestrator."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from typing import Any, Mapping

from furniture_layout.project_layout import ProjectLayout
from furniture_manufacturing.manufacturing_bom import (
    estimate_materials,
    recompute_features,
)
from furniture_manufacturing.manufacturing_models import (
    MachiningOperation,
    PanelRecord,
)
from furniture_panel_planning.cabinet_identity import primary_cabinet

from .workflow_constants import (
    EDITABLE_STAGE_OUTPUTS,
    RETRYABLE_STAGES,
    STAGE_INPUT_KEYS,
    OrchestrationResult,
)
from .workflow_project import Project, Revision, StageAttempt
from .workflow_state import (
    STAGE_SEQUENCE,
    WorkflowStage,
    WorkflowState,
    parse_stage,
    stage_index,
)


def _canonicalize_stage_input(
    key: str, stage_input: Mapping[str, Any]
) -> dict[str, Any]:
    """Wrap a flat parameters object; keep manufacturing appearance as a sibling."""
    payload = deepcopy(dict(stage_input))
    if "parameters" in payload:
        return payload
    if key == "panels":
        return {"parameters": payload}
    if key == "manufacturing":
        appearance = payload.pop("appearance", None)
        wrapped = {"parameters": payload}
        if appearance is not None:
            wrapped["appearance"] = appearance
        return wrapped
    return payload


class RevisionOpsMixin:
    def revise(self, project: Project, layout: ProjectLayout) -> Revision:
        """Start a new revision at stage 1; all parent artifacts become stale."""
        revision = project.add_revision(layout)
        self._persist(project)
        return revision

    def revise_layout(self, project: Project, layout: ProjectLayout) -> Revision:
        return self.revise(project, layout)

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
            ProjectLayout.from_dict(parent.layout.to_dict()),
            stage_inputs=deepcopy(parent.stage_inputs),
        )
        revision.stage_outputs = {
            key: deepcopy(value)
            for key, value in parent.stage_outputs.items()
            if parse_stage(key) in STAGE_SEQUENCE
            and stage_index(parse_stage(key)) < stage_index(changed_stage)
        }
        revision.stage_outputs[WorkflowStage.LAYOUT_PLAN.value] = (
            revision.layout.to_dict()
        )
        if changed_stage == WorkflowStage.MANUFACTURING_PLANNED:
            # 直接编辑制造输出后，重算派生快照（features/connection_points/materials），
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
                "materials": [
                    asdict(record) for record in estimate_materials(revised_panels)
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
        if changed_stage != WorkflowStage.LAYOUT_PLAN:
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
                layout_sha256=revision.layout_sha256,
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

    def confirm_intent(self, project: Project) -> Revision:
        return self.confirm_stage(project, WorkflowStage.LAYOUT_PLAN)

    def confirm_layout(self, project: Project) -> Revision:
        return self.confirm_stage(project, WorkflowStage.LAYOUT_PLAN)

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

        if requested == WorkflowStage.LAYOUT_PLAN:
            revision.layout = revision.layout.confirm()
            revision.stage_outputs[requested.value] = revision.layout.to_dict()
        if requested == WorkflowStage.PANELS_PLANNED:
            revision.confirmed_panel_sha256 = revision.panel_sha256

        revision.approve_stage(requested)
        revision.workflow.record(f"{requested.value} confirmed")
        self._persist(project)
        return revision

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
        if attempt.layout_sha256 != revision.layout_sha256:
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
        revision.stage_inputs[key] = _canonicalize_stage_input(key, stage_input)
