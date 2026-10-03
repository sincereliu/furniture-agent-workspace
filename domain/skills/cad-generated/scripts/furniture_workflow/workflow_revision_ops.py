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
from furniture_panel_planning.cabinet_identity import cabinets_from_output
from furniture_panel_planning.panel_pipeline import ENVELOPE_OWNED_FIELDS

from .workflow_constants import (
    EDITABLE_STAGE_OUTPUTS,
    RETRYABLE_STAGES,
    STAGE_INPUT_KEYS,
    OrchestrationResult,
)
from .workflow_decisions import append_decisions
from .workflow_digest import stable_digest
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
    """Wrap a flat parameters object; keep manufacturing appearance as a sibling.

    板件阶段还允许一个兄弟键 `cabinets`（**逐柜覆盖**）：平铺进来时不能把它当成一个参数
    塞进 `parameters`，否则它会变成柜体参数里一个不认识的字段。
    """
    payload = deepcopy(dict(stage_input))
    if "parameters" in payload:
        return payload
    if key == "panels":
        cabinets = payload.pop("cabinets", None)
        wrapped: dict[str, Any] = {"parameters": payload}
        if cabinets is not None:
            wrapped["cabinets"] = cabinets
        return wrapped
    if key == "manufacturing":
        cabinets = payload.pop("cabinets", None)
        appearance = payload.pop("appearance", None)
        wrapped = {"parameters": payload}
        if appearance is not None:
            wrapped["appearance"] = appearance
        if cabinets is not None:
            wrapped["cabinets"] = cabinets
        return wrapped
    return payload


class RevisionOpsMixin:
    def revise(self, project: Project, layout: ProjectLayout) -> Revision:
        """Start a new revision at stage 1; all parent artifacts become stale.

        新 Revision **带走父修订的 `stage_inputs`**：那些参数是柜体的构造意图
        （门数、层板、背板安装…），摆放/房间变了它们并没有变。清掉它们会让下一次
        `run_next()` 直接报 "panel proposal is incomplete"（见 references/backlog.md
        「已知缺口」第 1 条）——摆放级改动不该顺带丢掉柜体参数。
        内容对不上时下游仍会自己报错（层板间距填不满内部净空之类），那是准确得多的失败。
        """
        parent = project.revisions[-1] if project.revisions else None
        revision = project.add_revision(
            layout,
            stage_inputs=deepcopy(parent.stage_inputs) if parent else None,
        )
        self._persist(project)
        return revision

    def revise_layout(self, project: Project, layout: ProjectLayout) -> Revision:
        return self.revise(project, layout)

    def record_decisions(
        self,
        project: Project,
        admitted: list[dict[str, Any]],
        *,
        actor: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """把这次对话里的说法记进**项目台账**（只追加），有新增才落盘。

        台账挂在项目上而不是修订上：一句"客户说要通顶"不会因为换了版号就失效，
        跨修订也仍然要读得到。条目由调用方先过 `admit_decisions()`——
        校验必须在改项目之前完成，免得留下半成品。`actor` 由运行时给（谁记的这条）。
        """
        if not admitted:
            return []
        added = append_decisions(
            project.decisions,
            admitted,
            revision_number=project.latest.number,
            actor=actor,
        )
        self._persist(project)
        return added

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
            # 避免它们与 panels/operations 漂移。**逐柜**各算各的。
            output = {
                **output,
                "cabinets": [
                    self._recompute_manufactured_cabinet(entry)
                    for entry in output.get("cabinets", [])
                ],
            }
        revision.stage_outputs[changed_stage.value] = deepcopy(output)
        if changed_stage == WorkflowStage.PANELS_PLANNED:
            # 改过板件产物之后，把**每台柜**自己的 spec 写成**它自己**的逐柜覆盖——
            # 下一次规划才不会把第一台的参数套到所有柜上（旧做法就是这么错的）。
            panel_input = revision.stage_inputs.setdefault("panels", {})
            parameters = panel_input.setdefault("parameters", {})
            cabinets = panel_input.setdefault("cabinets", {})
            if isinstance(parameters, dict) and isinstance(cabinets, dict):
                for cabinet in cabinets_from_output(output):
                    cabinet_id = str(cabinet.get("id") or "")
                    spec = cabinet.get("spec")
                    if not cabinet_id or not isinstance(spec, Mapping):
                        continue
                    cabinets[cabinet_id] = {
                        key: value
                        for key, value in spec.items()
                        if key not in ENVELOPE_OWNED_FIELDS
                    }
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

    @staticmethod
    def _recompute_manufactured_cabinet(entry: Mapping[str, Any]) -> dict[str, Any]:
        """改过某台柜的板件/加工后，重算**这台柜**的派生快照（特征、连接点、材料）。

        逐柜各算各的：一台的板件改了不该动另一台的派生值。
        """
        bom = dict(entry.get("bom") or {})
        revised_panels = [
            PanelRecord.from_dict(item) for item in bom.get("panels", [])
        ]
        revised_operations = [
            MachiningOperation(**item) for item in bom.get("operations", [])
        ]
        features, connection_points = recompute_features(
            revised_panels, revised_operations
        )
        return {
            **entry,
            "bom": {
                **bom,
                "features": [asdict(feature) for feature in features],
                "connection_points": [asdict(point) for point in connection_points],
                "materials": [
                    asdict(record) for record in estimate_materials(revised_panels)
                ],
            },
        }

    def confirm_layout(self, project: Project) -> Revision:
        return self.confirm_stage(project, WorkflowStage.LAYOUT_PLAN)

    def confirm_room(self, project: Project, room_id: str) -> Revision:
        """审过一间房。**所有房间都审过，布局检查点才算确认。**

        改一间只审一间：未动过的房间，确认在 `add_revision()` 里就跟着走过来了
        （内容逐字节相同才沿用）。这里只补"人看过的那一间"。
        布局阶段没确认前，`workflow.current` 一直停在 `layout_plan`，下游不会跑。
        """
        revision = project.latest
        if revision.workflow.current != WorkflowStage.LAYOUT_PLAN:
            raise ValueError(
                "only the layout stage may be confirmed room by room: "
                f"{revision.workflow.current.value}"
            )
        if revision.is_stage_approved(WorkflowStage.LAYOUT_PLAN):
            raise ValueError("layout is already confirmed; nothing left to review")
        known = {scene.room.id for scene in revision.layout.rooms}
        if room_id not in known:
            raise ValueError(f"unknown room: {room_id}")
        if room_id not in revision.approved_rooms:
            revision.approved_rooms.append(room_id)
        revision.workflow.record(f"layout room reviewed: {room_id}")
        if not revision.pending_room_ids():
            return self.confirm_stage(project, WorkflowStage.LAYOUT_PLAN)
        self._persist(project)
        return revision

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
            # 整份确认 = 每间都算审过（一次确认全部，与房间级确认同一条路）。
            for room_id in revision.pending_room_ids():
                revision.approved_rooms.append(room_id)
            revision.layout = revision.layout.confirm()
            revision.stage_outputs[requested.value] = revision.layout.to_dict()
        if requested == WorkflowStage.PANELS_PLANNED:
            revision.confirmed_panel_sha256 = revision.panel_sha256
        # 记下"人确认的是哪一份内容"：修订继承靠这条回指真正的点头那一版。
        revision.approved_digests[requested.value] = stable_digest(
            revision.stage_outputs[requested.value]
        )

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
