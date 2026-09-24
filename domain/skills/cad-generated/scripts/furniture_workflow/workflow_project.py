"""Project and revision aggregate roots for traceable furniture work."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from furniture_delivery_validation.validation import ValidationReport
from furniture_layout.project_layout import ProjectLayout

from .workflow_artifacts import ArtifactManifest
from .workflow_digest import stable_digest
from .workflow_state import WorkflowStage, WorkflowState, parse_stage, utc_now


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _stage_key(stage: str | WorkflowStage) -> str:
    return parse_stage(stage).value


def _remap_stage_keys(data: dict[str, Any]) -> dict[str, Any]:
    return {_stage_key(str(key)): value for key, value in data.items()}


@dataclass
class StageAttempt:
    """One planner execution against a frozen upstream checkpoint."""

    number: int
    stage: str
    layout_sha256: str
    inputs: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] | None = None
    passed: bool = False
    error: str | None = None
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "stage": self.stage,
            "layout_sha256": self.layout_sha256,
            "inputs": deepcopy(self.inputs),
            "output": deepcopy(self.output),
            "passed": self.passed,
            "error": self.error,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StageAttempt":
        return cls(
            number=int(data["number"]),
            stage=_stage_key(str(data["stage"])),
            layout_sha256=str(data["layout_sha256"]),
            inputs=deepcopy(dict(data.get("inputs") or {})),
            output=(
                deepcopy(data["output"])
                if isinstance(data.get("output"), dict)
                else None
            ),
            passed=bool(data.get("passed", False)),
            error=data.get("error"),
            created_at=str(data.get("created_at") or utc_now()),
        )


@dataclass
class Revision:
    number: int
    layout: ProjectLayout
    stage_inputs: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: _id("rev"))
    parent_revision_id: str | None = None
    created_at: str = field(default_factory=utc_now)
    workflow: WorkflowState = field(default_factory=WorkflowState)
    validations: list[ValidationReport] = field(default_factory=list)
    manifest: ArtifactManifest | None = None
    feature_tree: dict[str, Any] | None = None
    stage_outputs: dict[str, Any] = field(default_factory=dict)
    stage_analyses: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    approved_stages: list[str] = field(default_factory=list)
    stage_attempts: dict[str, list[StageAttempt]] = field(default_factory=dict)
    selected_attempts: dict[str, int] = field(default_factory=dict)
    confirmed_panel_sha256: str | None = None
    #: 每个已确认阶段**当时确认的是哪份内容**（阶段名 → 内容摘要）。
    #: 修订继承靠它回指"人真的为这份内容点过头"，见 workflow_inheritance.py。
    approved_digests: dict[str, str] = field(default_factory=dict)
    #: 这一版的哪些阶段沿用了更早那一版的内容（阶段名 → {sha256, from_revision, from_stage}）。
    #: `approved_stages` 的含义是"这份内容已被确认过"，不是"人在这一版又点了一次头"。
    inherited: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: 房间级确认：这一版里**人已经看过**的房间 id。布局检查点（`layout.confirmed`）是它的派生值——
    #: 所有房间都进过这个列表，整份布局才算确认。改一间只审一间。
    approved_rooms: list[str] = field(default_factory=list)
    #: 哪些房间的确认是**沿用**父修订的（房间 id → {sha256, from_revision}）：房间内容逐字节没变。
    inherited_rooms: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: **工作副本的撤销日志**：这一版还没有下游产物时，页面拖动能原地改它；每次改动记一条
    #: （改的是哪一件、改动前的旧值），用于撤销。**不是审计**——有下游产物时整条清空。
    #: 记旧值而不是"从头重放"，所以丢掉最旧的几条只意味着"撤不到那么远"，不会让撤销错位。
    working_ops: list[dict[str, Any]] = field(default_factory=list)

    def has_downstream_artifacts(self) -> bool:
        """已经有东西依赖这一版了吗？（除 `layout_plan` 之外的产物或尝试）

        这是**工作副本的边界**：没有下游产物时，改多少次都还是同一版（版号不变、内容可变）；
        一旦下游产出，再改就不是同一版了——那是新版的事。
        """
        key = WorkflowStage.LAYOUT_PLAN.value
        if any(stage != key for stage in self.stage_outputs):
            return True
        return any(attempts for attempts in self.stage_attempts.values())

    def close_working_copy(self, *, reason: str) -> bool:
        """关掉工作副本：清空撤销日志（版本本身不动、不冻结）。

        下游一产出就调它——那时"再改"已经不是同一版了，日志留着也没有意义。
        """
        if not self.working_ops:
            return False
        self.working_ops.clear()
        self.workflow.record(f"working copy closed ({reason})")
        return True

    def room_digest(self, room_id: str) -> str | None:
        """某一间房**内容**的摘要（房间定义 + 已摆放包络）；没有这间房返回 `None`。"""
        for scene in self.layout.rooms:
            if scene.room.id == room_id:
                return stable_digest(scene.to_dict())
        return None

    def approved_room_ids(self) -> set[str]:
        """已经审过的房间。

        老项目文件里没有 `approved_rooms`——那时 `layout.confirmed` 是唯一记号，
        它为真就等价于"每一间都审过了"。
        """
        if self.approved_rooms:
            return set(self.approved_rooms)
        if self.layout.confirmed:
            return {scene.room.id for scene in self.layout.rooms}
        return set()

    def pending_room_ids(self) -> list[str]:
        """还没审的房间，按布局顺序——"还差哪间"要能直接说出来。"""
        approved = self.approved_room_ids()
        return [
            scene.room.id
            for scene in self.layout.rooms
            if scene.room.id not in approved
        ]

    def confirmed_digest(self, stage: str | WorkflowStage) -> str | None:
        """这个阶段**已确认的那份内容**的摘要；没确认过就是 `None`。

        板件另有一条历史字段 `confirmed_panel_sha256`（下游按它读冻结板件），
        老项目文件里只有它、没有 `approved_digests`，所以这里做一次回退。
        """
        key = _stage_key(stage)
        digest = self.approved_digests.get(key)
        if digest is None and key == WorkflowStage.PANELS_PLANNED.value:
            digest = self.confirmed_panel_sha256
        return digest

    def __post_init__(self) -> None:
        if self.manifest is None:
            self.manifest = ArtifactManifest(source_revision_id=self.id)
        self.stage_outputs.setdefault(
            WorkflowStage.LAYOUT_PLAN.value,
            self.layout.to_dict(),
        )
        if self.feature_tree is not None:
            self.stage_outputs.setdefault(
                WorkflowStage.FEATURE_TREE_PLANNED.value,
                self.feature_tree,
            )

    def is_stage_approved(self, stage: WorkflowStage) -> bool:
        return stage.value in self.approved_stages

    def approve_stage(self, stage: WorkflowStage) -> None:
        if stage.value not in self.approved_stages:
            self.approved_stages.append(stage.value)

    def attempts_for(self, stage: str | WorkflowStage) -> list[StageAttempt]:
        key = _stage_key(stage)
        return self.stage_attempts.setdefault(key, [])

    def selected_attempt(self, stage: str | WorkflowStage) -> StageAttempt | None:
        key = _stage_key(stage)
        number = self.selected_attempts.get(key)
        if number is None:
            return None
        return next(
            (item for item in self.attempts_for(key) if item.number == number),
            None,
        )

    def latest_attempt(self, stage: str | WorkflowStage) -> StageAttempt | None:
        attempts = self.attempts_for(stage)
        return attempts[-1] if attempts else None

    @property
    def layout_sha256(self) -> str:
        return stable_digest(self.layout.to_dict())

    @property
    def panel_sha256(self) -> str | None:
        output = self.stage_outputs.get(WorkflowStage.PANELS_PLANNED.value)
        if not isinstance(output, dict):
            return None
        return stable_digest(output)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "number": self.number,
            "parent_revision_id": self.parent_revision_id,
            "created_at": self.created_at,
            "layout_sha256": self.layout_sha256,
            "panel_sha256": self.panel_sha256,
            "confirmed_panel_sha256": self.confirmed_panel_sha256,
            "layout": self.layout.to_dict(),
            "stage_inputs": self.stage_inputs,
            "workflow": self.workflow.to_dict(),
            "validations": [report.to_dict() for report in self.validations],
            "manifest": self.manifest.to_dict() if self.manifest else None,
            "feature_tree": self.feature_tree,
            "stage_outputs": self.stage_outputs,
            "stage_analyses": self.stage_analyses,
            "approved_stages": self.approved_stages,
            "approved_digests": dict(self.approved_digests),
            "inherited": deepcopy(self.inherited),
            "approved_rooms": list(self.approved_rooms),
            "inherited_rooms": deepcopy(self.inherited_rooms),
            "working_ops": deepcopy(self.working_ops),
            "stage_attempts": {
                stage: [item.to_dict() for item in attempts]
                for stage, attempts in self.stage_attempts.items()
            },
            "selected_attempts": dict(self.selected_attempts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Revision":
        raw_layout = data.get("layout")
        if not isinstance(raw_layout, dict):
            raise ValueError("revision requires layout")
        layout = ProjectLayout.from_dict(raw_layout)
        stage_inputs = data.get("stage_inputs")
        if not isinstance(stage_inputs, dict):
            stage_inputs = {}
        else:
            stage_inputs = deepcopy(stage_inputs)
        stage_outputs = _remap_stage_keys(deepcopy(dict(data.get("stage_outputs", {}))))
        validations: list[ValidationReport] = []
        for item in data.get("validations", []):
            payload = dict(item)
            payload["stage"] = _stage_key(str(payload["stage"]))
            validations.append(ValidationReport.from_dict(payload))
        return cls(
            id=str(data["id"]),
            number=int(data["number"]),
            parent_revision_id=data.get("parent_revision_id"),
            created_at=str(data["created_at"]),
            layout=layout,
            stage_inputs=stage_inputs,
            workflow=WorkflowState.from_dict(data["workflow"]),
            validations=validations,
            manifest=(
                ArtifactManifest.from_dict(data["manifest"])
                if data.get("manifest")
                else None
            ),
            feature_tree=data.get("feature_tree"),
            stage_outputs=stage_outputs,
            stage_analyses=_remap_stage_keys(
                {
                    str(stage): {
                        str(name): dict(record)
                        for name, record in dict(records).items()
                    }
                    for stage, records in dict(data.get("stage_analyses", {})).items()
                }
            ),
            approved_stages=[
                parse_stage(str(value)).value
                for value in data.get("approved_stages", [])
            ],
            stage_attempts=_remap_stage_keys(
                {
                    str(stage): [
                        StageAttempt.from_dict(item) for item in list(records)
                    ]
                    for stage, records in dict(data.get("stage_attempts", {})).items()
                }
            ),
            selected_attempts=_remap_stage_keys(
                {
                    str(stage): int(number)
                    for stage, number in dict(data.get("selected_attempts", {})).items()
                }
            ),
            confirmed_panel_sha256=(
                str(data["confirmed_panel_sha256"])
                if data.get("confirmed_panel_sha256")
                else None
            ),
            approved_digests={
                parse_stage(str(stage)).value: str(digest)
                for stage, digest in dict(data.get("approved_digests", {})).items()
            },
            inherited={
                parse_stage(str(stage)).value: dict(record)
                for stage, record in dict(data.get("inherited", {})).items()
            },
            approved_rooms=[str(room_id) for room_id in data.get("approved_rooms", [])],
            inherited_rooms={
                str(room_id): dict(record)
                for room_id, record in dict(data.get("inherited_rooms", {})).items()
            },
            working_ops=[dict(entry) for entry in data.get("working_ops", [])],
        )


@dataclass
class Project:
    name: str
    id: str = field(default_factory=lambda: _id("project"))
    created_at: str = field(default_factory=utc_now)
    revisions: list[Revision] = field(default_factory=list)

    @property
    def latest(self) -> Revision:
        if not self.revisions:
            raise ValueError("project has no revisions")
        return self.revisions[-1]

    def add_revision(
        self,
        layout: ProjectLayout,
        stage_inputs: dict[str, Any] | None = None,
    ) -> Revision:
        parent = self.revisions[-1] if self.revisions else None
        if parent and parent.manifest:
            parent.manifest.mark_stale()
        revision = Revision(
            number=len(self.revisions) + 1,
            layout=layout,
            stage_inputs=dict(stage_inputs or {}),
            parent_revision_id=parent.id if parent else None,
        )
        if parent is not None:
            _carry_room_approvals(parent, revision)
        self.revisions.append(revision)
        return revision

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "revisions": [revision.to_dict() for revision in self.revisions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            created_at=str(data["created_at"]),
            revisions=[Revision.from_dict(item) for item in data.get("revisions", [])],
        )


def _carry_room_approvals(parent: "Revision", revision: "Revision") -> None:
    """没动过的房间，确认跟着走。

    判据是**这一间的内容逐字节相同**（房间定义 + 摆放），与整份布局的摘要无关——
    改次卧不该让主卧重新审一遍。沿用要留痕（`inherited_rooms`），审计时能回指到真正点头的那一版；
    `approved_rooms` 只放"人看过"的房间，所以沿用的也算进去——它的含义是"这份内容已被确认过"。

    每间都审过（沿用的也算）时，**布局检查点当场成立**：调用方不必再让人点一次头。
    所以 `revise()` 到一个没有房间改动的布局时，下游可以直接往下走。
    留痕用房间级的 `inherited_rooms`（逐间的摘要 + 回指），不写阶段级 `inherited`——
    后者表示"这个阶段的产出整份沿用"，而这里的布局内容可能只是等价，别把两件事混起来。
    """
    approved = parent.approved_room_ids()
    if not approved:
        return
    for scene in revision.layout.rooms:
        room_id = scene.room.id
        if room_id not in approved or room_id in revision.approved_rooms:
            continue
        digest = stable_digest(scene.to_dict())
        if parent.room_digest(room_id) != digest:
            continue
        revision.approved_rooms.append(room_id)
        revision.inherited_rooms[room_id] = {
            "sha256": digest,
            "from_revision": parent.id,
        }
    if revision.pending_room_ids():
        return
    key = WorkflowStage.LAYOUT_PLAN.value
    revision.layout = revision.layout.confirm()
    revision.stage_outputs[key] = revision.layout.to_dict()
    revision.approved_digests[key] = stable_digest(revision.layout.to_dict())
    revision.approve_stage(WorkflowStage.LAYOUT_PLAN)
    revision.workflow.record(
        f"layout_plan carried {len(revision.inherited_rooms)} reviewed room(s) "
        f"from revision {parent.number}"
    )
