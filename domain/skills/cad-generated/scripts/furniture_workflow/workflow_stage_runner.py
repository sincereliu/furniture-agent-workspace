"""run_next / run_until and stage execution for FurnitureOrchestrator."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from furniture_contracts.validation import ValidationReport
from furniture_delivery_validation.validation import validate_delivery
from furniture_panel_planning.panel_pipeline import plan_panel_stage

from .input_adapter import (
    manufacturing_stage_input,
    panel_envelopes_from_layout,
    panel_stage_input,
)
from .workflow_artifact_writer import prepare_artifact_dir, write_artifacts
from .workflow_constants import RETRYABLE_STAGES, OrchestrationResult
from .workflow_inheritance import (
    inheritance_source,
    inherited_evidence,
    stage_digest,
)
from .workflow_project import Project, Revision, StageAttempt
from .workflow_stage_planning import feature_trees_from, plan_every_cabinet
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
        return self.run_until(
            project,
            STAGE_SEQUENCE[current_index + 1],
            output_root=output_root,
            artifact_name=artifact_name,
            generate_cad=generate_cad,
            force=force,
        )

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
        """Execute at most one stage toward a target; keep every checkpoint."""
        target = parse_stage(target_stage)
        revision = project.latest
        attempted_stage: WorkflowStage | None = None
        try:
            current = revision.workflow.current
            if (
                current != WorkflowStage.FAILED
                and stage_index(current) < stage_index(target)
                and revision.is_stage_approved(current)
            ):
                next_stage = STAGE_SEQUENCE[stage_index(current) + 1]
                has_attempt = (
                    next_stage in RETRYABLE_STAGES
                    and revision.attempts_for(next_stage)
                )
                if not has_attempt:
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
                # 整份阶段输入都传下去：`{"parameters": …共享…, "cabinets": {…逐柜覆盖…}}`。
                # 只取 `parameters` 会把逐柜覆盖丢掉。
                output = plan_panel_stage(
                    panel_envelopes_from_layout(revision.layout),
                    stage_input,
                )
            except (TypeError, ValueError) as exc:
                self._fail_retryable_stage(revision, stage, stage_input, str(exc))
                return
            self._complete_retryable_stage(
                project,
                revision,
                stage,
                output,
                stage_input,
                "construction, exact clearances, and physical panels planned",
            )
            return

        if stage == WorkflowStage.MANUFACTURING_PLANNED:
            stage_input = manufacturing_stage_input(revision.stage_inputs)
            # 读输入放在 try 外（与改前一致）：冻结的板件缺失这类**输入**问题要直接抛出来，
            # 而不是记成"这次计划失败了"。
            handoffs = self._cabinet_handoffs(revision, project_id=project.id)
            try:
                output = plan_every_cabinet(handoffs, stage_input)
            except (TypeError, ValueError) as exc:
                self._fail_retryable_stage(revision, stage, stage_input, str(exc))
                return
            self._complete_retryable_stage(
                project,
                revision,
                stage,
                output,
                stage_input,
                f"materials, hardware, and preliminary BOM planned for "
                f"{len(output['cabinets'])} cabinet(s)",
            )
            return

        if stage == WorkflowStage.FEATURE_TREE_PLANNED:
            boms = self._cabinet_boms(revision)
            try:
                feature_trees = feature_trees_from(boms)
            except (TypeError, ValueError) as exc:
                self._fail_retryable_stage(revision, stage, {}, str(exc))
                return
            self._complete_retryable_stage(
                project,
                revision,
                stage,
                feature_trees,
                {},
                f"Feature Tree v2 with target-specific machining cuts planned for "
                f"{len(feature_trees['cabinets'])} cabinet(s)",
            )
            return

        if stage == WorkflowStage.CAD_GENERATED:
            if output_root is None:
                raise ValueError("CAD generation requires output_root")
            if not generate_cad:
                raise ValueError("CAD generation requires generate_cad=True")
            pipelines = self._pipelines_from_revision(
                revision, project_id=project.id
            )
            if not pipelines:
                raise ValueError("manufacturing stage must exist before CAD generation")
            artifact_dir = prepare_artifact_dir(
                self.workspace_root,
                output_root,
                project,
                revision,
                artifact_name=artifact_name,
            )
            plans = write_artifacts(
                self.workspace_root,
                revision,
                pipelines,
                artifact_dir,
                artifact_name=artifact_name,
                panel_output=self._confirmed_panel_output(
                    revision, project_id=project.id
                ),
            )
            # **逐柜**生成：每一台各自一个 CAD 源文件与一份 STEP。
            # 为什么不做"一个进程连做几台"：实测**更慢**（两台柜 20.1 秒 vs 9.3 秒）——
            # viewer 拓扑的导出必须待在刚建完模型的那个进程里（热内核约 1.4 秒/台，
            # 长进程里同样三台要 6.7 秒/台）。数据记在 TOOL.md 与未落地需求里。
            cabinets: list[dict[str, Any]] = []
            failures: list[str] = []
            for plan in plans:
                bridge = self.cad_bridge.generate_from_source(
                    plan["source_path"],
                    plan["step_path"],
                    force=force,
                )
                cabinets.append({"id": plan["id"], "bridge": asdict(bridge)})
                if bridge.status != "ok":
                    failures.append(f"{plan['id']}: {bridge.message}")
                    continue
                if bridge.step_path:
                    revision.manifest.add_file(
                        "step", bridge.step_path, cabinet_id=plan["id"]
                    )
                if bridge.topology_path:
                    revision.manifest.add_file(
                        "viewer_topology",
                        bridge.topology_path,
                        package_path=bridge.viewer_package_path,
                        cabinet_id=plan["id"],
                    )
            revision.stage_outputs[stage.value] = {"cabinets": cabinets}
            report = self._validate_stage_output(
                revision, stage, project_id=project.id
            )
            revision.validations.append(report)
            if not report.passed:
                revision.workflow.fail(
                    "; ".join(failures) or "CAD validation failed"
                )
                return
            revision.workflow.advance(
                stage,
                f"STEP and Viewer topology generated for {len(cabinets)} cabinet(s)",
            )
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
        project: Project,
        revision: Revision,
        stage: WorkflowStage,
        output: dict[str, Any],
        inputs: dict[str, Any],
        note: str,
    ) -> None:
        revision.stage_outputs[stage.value] = deepcopy(output)
        report = self._validate_stage_output(
            revision, stage, project_id=project.id
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
            else:
                revision.stage_outputs[stage.value] = deepcopy(selected.output)
            revision.workflow.record(
                f"{stage.value} attempt {attempt.number} failed"
            )
            return
        revision.workflow.advance(stage, note)
        # 下游一产出，工作副本就关门：再改已经不是同一版了，撤销日志留着也没有意义。
        revision.close_working_copy(reason=f"{stage.value} produced")
        self._inherit_settled_stage(project, revision, stage, output)

    def _inherit_settled_stage(
        self,
        project: Project,
        revision: Revision,
        stage: WorkflowStage,
        output: Mapping[str, Any],
    ) -> None:
        """内容没变就不让人再确认一次（修订继承 R1/R2）。

        判据是**逐字节相同**：更早的 Revision 上这个阶段已确认，且确认的就是这份内容。
        命中就地把本阶段记为已确认，并留下 `inherited` 回指——不改任何产物、不跳过重算。
        重算是毫秒级，真正的代价是让人再点一次头（见 references/revision-inheritance-design.md）。
        """
        digest = stage_digest(output)
        source = inheritance_source(project, revision, stage, digest)
        if source is None:
            return
        revision.inherited[stage.value] = inherited_evidence(
            source, stage=stage, digest=digest
        )
        if stage == WorkflowStage.PANELS_PLANNED:
            revision.confirmed_panel_sha256 = digest
        revision.approved_digests[stage.value] = digest
        revision.approve_stage(stage)
        revision.workflow.record(
            f"{stage.value} inherited from revision {source.number} (same content)"
        )

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
