"""页面改项目的写路径：布局 op，以及对一条决策表态。

契约（见 `references/runtime-contract.md`「页面写项目」段）：

- 一次请求只改一件、只改一处；校验不过就整体拒绝，**不落任何东西**。
- 必须带 `expected_version`（页面最近一次看到的 `version`）：对不上就拒绝，
  绝不拿旧画面去覆盖新内容。
- **工作副本**（方案 H）：这一版**还没有下游产物**时，改动**原地生效**——版号不变、内容摘要变，
  并往 `working_ops` 记一条（改动前的旧值 + 谁改的）供撤销与追溯。一旦有下游产物，再改就**追加新 Revision**：
  "已经有东西依赖这一版了，再改就不是同一版"。
- 原地改到某间房时，**那一间的确认作废**（内容变回了"没人看过"）——这正是"改一间只审一间"。
- 父修订的 `stage_inputs` 原样带走：那些是柜体构造意图（门数、层板、背板安装…），摆放变了它们没变。
- 默认关闭，靠 `FURNITURE_PROJECT_LAYOUT_EDIT=1` 灰度打开。从布局阶段的 `open_projects.py` 拉起本机预览进程时会把它设成 `1`。
- 页面上还能对**一条待确认的说法**表态（确认 / 划掉，`edit_project_decisions()`）：同一套门，
  另加"只能动还待确认的那一条"，措辞由服务端写死——页面递不进自由文本。见
  [决策台账设计](references/decision-log-design.md)。

几何部分不在这里：op 词表、白名单、重新摆放与准入校验都在
`furniture_layout/project_edit.py`（与房间场景编辑共用同一套）。
"""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from furniture_layout.project_edit import apply_layout_edit

from furniture_layout.open_preview import layout_version, preview_page_data
from .workflow_decisions import (
    admit_decisions,
    append_decisions,
    auto_withdrawn_entries,
    changed_item_fields,
    pending_decision_ids,
)
from .workflow_lease import check_write, read_lease
from .workflow_orchestrator import FurnitureOrchestrator
from .workflow_project import Project, Revision
from .workflow_state import WorkflowStage
from .workflow_store import JsonProjectStore

LAYOUT_EDIT_ENV = "FURNITURE_PROJECT_LAYOUT_EDIT"
#: 撤销日志的上限。超出丢**最旧的**——因为每条记的是旧值，丢最旧只意味着"撤不到那么远"。
WORKING_OP_LIMIT = 500
#: 页面上能对一条待确认说法做的两件事。措辞由服务端写死，页面只递动作与目标。
DECISION_ACTIONS = ("confirm", "withdraw")


def layout_edit_enabled() -> bool:
    """灰度开关：只有显式设成 `1` 才开。别的写法（`true` / `yes` / 空）都当关着。"""
    return os.environ.get(LAYOUT_EDIT_ENV) == "1"


class LayoutEditDisabled(RuntimeError):
    """灰度开关没开：这个部署不该接受页面写回。"""


class VersionConflict(RuntimeError):
    """页面手上的画面已经不是最新：不能拿它去覆盖。"""

    def __init__(self, current_version: str) -> None:
        super().__init__(f"layout changed; current version is {current_version}")
        self.current_version = current_version


def edit_project_layout(
    project: Project,
    op: Mapping[str, Any],
    *,
    expected_version: str,
    workspace_root: str | Path,
    store_root: str | Path,
    lease_token: str | None = None,
) -> dict[str, Any]:
    """应用一次 op，返回新的布局文档。

    工作副本还开着（没有下游产物）就原地改；否则追加一个新 Revision。
    两者都先过**编辑租约**（同一个项目同一时刻只有一个写者）。

    抛：`LayoutEditDisabled`（开关关着）、`VersionConflict`（版本对不上）、
    `LeaseHeld`（编辑权在别人手里）、`ValueError`（op 不合法 / 找不到那一件 / 几何不通过）。
    """
    if not layout_edit_enabled():
        raise LayoutEditDisabled(f"{LAYOUT_EDIT_ENV} is not set to 1")
    check_write(store_root, project.id, token=lease_token)
    revision = project.latest
    current = layout_version(revision)
    if expected_version != current:
        raise VersionConflict(current)

    item_id = str(op.get("item_id") or "")
    before = _item_snapshot(revision, item_id)
    # 谁改的：从编辑租约读。读不出持有者就写 `unknown`——**不猜**。
    actor = _working_actor(store_root, project.id, lease_token)
    layout = apply_layout_edit(revision.layout, op)

    if revision.has_downstream_artifacts():
        # 已经有东西依赖这一版了：改它就等于改别人的依据 → 追加新版。
        _store_document(project, layout, workspace_root, store_root)
        # 触发新版的那一次改动也是新工作副本的第一步：同样进日志，否则它撤不回来。
        withdrawn: list[dict[str, Any]] = []
        if item_id and before is not None:
            _log_working_op(project.latest, op, item_id, before, actor)
            withdrawn = _auto_withdraw_stale(
                project, item_id, before, _item_snapshot(project.latest, item_id), actor
            )
            JsonProjectStore(store_root).save(project)
    else:
        _edit_in_place(revision, layout, op, item_id, before, actor)
        withdrawn = _auto_withdraw_stale(
            project, item_id, before, _item_snapshot(revision, item_id), actor
        )
        JsonProjectStore(store_root).save(project)
    document = preview_page_data(project, store_root=store_root)
    if withdrawn:
        document["withdrawn_decisions"] = withdrawn
    return document


def edit_project_decisions(
    project: Project,
    *,
    action: str,
    target: str,
    expected_version: str,
    store_root: str | Path,
    lease_token: str | None = None,
) -> dict[str, Any]:
    """页面上对一条**待确认**的说法表态：确认它，或者划掉它。

    和布局 op 同一套门（灰度开关 → 编辑租约 → 版本对得上），另加两条自己的规矩：

    - **只能动还待确认的那一条**：已经确认/撤回过的再表态就是"页面上的画面过期了"，
      直接拒绝并让它刷新——版本号管不到这件事（台账追加不改布局摘要）。
    - **措辞由服务端写**：页面递不进自由文本，所以页面上按的按钮**没有"原话"**
      （`source=page`），也就不存在"页面替客户编话"的余地。

    只追加：这条表态本身就是新的一条，被它确认/撤回的那条一个字不动。
    """
    if not layout_edit_enabled():
        raise LayoutEditDisabled(f"{LAYOUT_EDIT_ENV} is not set to 1")
    check_write(store_root, project.id, token=lease_token)
    revision = project.latest
    current = layout_version(revision)
    if expected_version != current:
        raise VersionConflict(current)
    if action not in DECISION_ACTIONS:
        raise ValueError(
            "action must be one of: " + ", ".join(DECISION_ACTIONS)
        )
    decision_id = str(target or "").strip()
    if not decision_id:
        raise ValueError("target is required")
    if not any(str(entry.get("id") or "") == decision_id for entry in project.decisions):
        raise ValueError(f"unknown decision: {decision_id}")
    if decision_id not in pending_decision_ids(project.decisions):
        raise ValueError(
            f"{decision_id} is already settled; refresh the page before deciding again"
        )
    admitted = admit_decisions(
        [
            {
                "interpretation": (
                    "客户在页面上确认了这条假设"
                    if action == "confirm"
                    else "客户在页面上划掉了这条假设"
                ),
                "speaker": "customer",
                "status": "confirmed" if action == "confirm" else "withdrawn",
                "targets": [decision_id],
                "source": "page",
            }
        ],
        existing_ids=[str(entry.get("id") or "") for entry in project.decisions],
    )
    added = append_decisions(
        project.decisions,
        admitted,
        revision_number=revision.number,
        actor=_working_actor(store_root, project.id, lease_token),
    )
    JsonProjectStore(store_root).save(project)
    document = preview_page_data(project, store_root=store_root)
    document["decided"] = added
    return document


def undo_layout_edit(
    project: Project,
    *,
    expected_version: str,
    workspace_root: str | Path,
    store_root: str | Path,
    steps: int = 1,
    lease_token: str | None = None,
) -> dict[str, Any]:
    """撤销工作副本上的最后 N 步（逐条恢复旧值）。

    只在**工作副本还开着**时可用（没有下游产物）。恢复失败整体拒绝——不留半改的状态。
    撤销本身也留一条事件：它会让"已经跟人说过"的内容变样，必须看得出来。
    """
    if not layout_edit_enabled():
        raise LayoutEditDisabled(f"{LAYOUT_EDIT_ENV} is not set to 1")
    check_write(store_root, project.id, token=lease_token)
    revision = project.latest
    current = layout_version(revision)
    if expected_version != current:
        raise VersionConflict(current)
    if revision.has_downstream_artifacts():
        raise ValueError("working copy is closed: downstream artifacts already exist")
    if steps < 1:
        raise ValueError("steps must be at least 1")
    if len(revision.working_ops) < steps:
        raise ValueError(
            f"only {len(revision.working_ops)} step(s) can be undone"
        )

    layout = revision.layout
    for entry in reversed(revision.working_ops[-steps:]):
        for restore_op in _restore_ops(entry):
            layout = apply_layout_edit(layout, restore_op)
    undone = revision.working_ops[-steps:]
    _edit_in_place(revision, layout, {"op": "undo", "item_id": ""}, None, None)
    del revision.working_ops[len(revision.working_ops) - steps:]
    revision.workflow.record(f"undo {steps} step(s) on the working copy")
    JsonProjectStore(store_root).save(project)
    document = preview_page_data(project, store_root=store_root)
    document["undone"] = undone
    return document


def _auto_withdraw_stale(
    project: Project,
    item_id: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    actor: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """客户的动作改了某一处 → 把**针对那一处**还待确认的假设当场作废。

    为什么要有它：动作是最强证据。手动拖过之后，台账里那条"沿墙 300 居中"还挂着"待确认"，
    两边就打架了（实测撞到过）。规则很保守——只动**还待确认**、且引用精确到 `对象.字段`、
    且那个字段**真的变了**的假设；客户已经点头过的约束一个字都不动（那是"改主意"，要显式来）。
    """
    if not item_id or before is None or after is None:
        return []
    changes = {item_id: changed_item_fields(before, after)}
    speaker = "customer" if (actor or {}).get("holder") == "page" else "agent"
    entries = auto_withdrawn_entries(
        project.decisions,
        changes,
        speaker=speaker,
        source="page" if speaker == "customer" else "tool",
    )
    if not entries:
        return []
    admitted = admit_decisions(
        entries,
        existing_ids=[str(entry.get("id") or "") for entry in project.decisions],
    )
    return append_decisions(
        project.decisions,
        admitted,
        revision_number=project.latest.number,
        actor=actor,
    )


def _store_document(
    project: Project,
    layout,
    workspace_root: str | Path,
    store_root: str | Path,
) -> None:
    orchestrator = FurnitureOrchestrator(
        workspace_root=workspace_root,
        project_store=JsonProjectStore(store_root),
    )
    orchestrator.revise(project, layout)


def _edit_in_place(
    revision: Revision,
    layout,
    op: Mapping[str, Any],
    item_id: str | None,
    before: dict[str, Any] | None,
    actor: Mapping[str, Any] | None = None,
) -> None:
    """把改动落到**这一版**上：内容变、版号不变，并处理确认作废与撤销日志。"""
    changed_rooms = _changed_room_ids(revision.layout, layout)
    revision.layout = layout
    revision.stage_outputs[WorkflowStage.LAYOUT_PLAN.value] = layout.to_dict()
    for room_id in changed_rooms:
        _revoke_room_review(revision, room_id)
    if item_id and before is not None:
        _log_working_op(revision, op, item_id, before, actor)


def _working_actor(
    store_root: str | Path,
    project_id: str,
    lease_token: str | None,
) -> dict[str, Any]:
    """这条改动是谁做的——从**编辑租约**读，读不出持有者就写 `unknown`。

    改动的动作本身是原始证据，所以"谁做的"必须跟着它一起落盘：
    之前的日志只记了"改了什么、改前是多少"，三天后没人知道是谁拖的。
    只有带对 token 的那位才算持有者；租约已过期（没人持有）时如实写 `unknown`。
    """
    lease = read_lease(store_root, project_id)
    if lease is None or not lease_token or lease.token != lease_token:
        return {"holder": "unknown", "label": "", "lease_id": ""}
    return {"holder": lease.holder, "label": lease.label, "lease_id": lease.id}


def _log_working_op(
    revision: Revision,
    op: Mapping[str, Any],
    item_id: str,
    before: dict[str, Any],
    actor: Mapping[str, Any] | None = None,
) -> None:
    revision.working_ops.append(
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "op": dict(op),
            "item_id": item_id,
            "before": before,
            "actor": dict(actor or {"holder": "unknown", "label": "", "lease_id": ""}),
        }
    )
    if len(revision.working_ops) > WORKING_OP_LIMIT:
        del revision.working_ops[: len(revision.working_ops) - WORKING_OP_LIMIT]


def _item_snapshot(revision: Revision, item_id: str) -> dict[str, Any] | None:
    """改动前那一件的旧值（够用来恢复：摆放 + 尺寸）。"""
    for scene in revision.layout.rooms:
        for item in scene.items:
            if item.id == item_id:
                return {
                    "placement": item.placement.to_dict(),
                    "width": item.width,
                    "depth": item.depth,
                    "height": item.height,
                }
    return None


def _restore_ops(entry: Mapping[str, Any]) -> list[dict[str, Any]]:
    """把一条日志还原成能喂给 `apply_layout_edit` 的 op（最多三条：摆放 + 朝向 + 尺寸）。"""
    item_id = str(entry.get("item_id") or "")
    before = dict(entry.get("before") or {})
    placement = dict(before.get("placement") or {})
    ops: list[dict[str, Any]] = []
    if placement:
        if placement.get("mode") == "wall":
            ops.append(
                {
                    "op": "move",
                    "item_id": item_id,
                    "host_wall": placement.get("host_wall"),
                    "offset_mm": placement.get("offset_mm"),
                    "origin_z_mm": placement.get("origin_z_mm") or 0,
                }
            )
        else:
            ops.append(
                {
                    "op": "move",
                    "item_id": item_id,
                    "mode": "free",
                    "origin_x_mm": placement.get("origin_x_mm"),
                    "origin_y_mm": placement.get("origin_y_mm"),
                    "origin_z_mm": placement.get("origin_z_mm") or 0,
                }
            )
            ops.append(
                {
                    "op": "rotate",
                    "item_id": item_id,
                    "mode": "free",
                    "origin_x_mm": placement.get("origin_x_mm"),
                    "origin_y_mm": placement.get("origin_y_mm"),
                    "rotation_z_deg": placement.get("rotation_z_deg") or 0,
                }
            )
    sizes = {
        key: before[key]
        for key in ("width", "depth", "height")
        if before.get(key) is not None
    }
    if sizes:
        ops.append({"op": "resize", "item_id": item_id, **sizes})
    return ops


def _changed_room_ids(before_layout, after_layout) -> list[str]:
    """哪些房间的内容变了（逐字节比较）——变了的那些，确认作废。"""
    changed: list[str] = []
    after = {scene.room.id: scene for scene in after_layout.rooms}
    for scene in before_layout.rooms:
        other = after.get(scene.room.id)
        if other is None or other.to_dict() != scene.to_dict():
            changed.append(scene.room.id)
    return changed


def _revoke_room_review(revision: Revision, room_id: str) -> None:
    """撤回这一间的确认：内容变了，"人看过"就不再成立。

    全审齐才成立的布局检查点跟着退回未确认——包括 `approved_stages` 与内容摘要记号，
    不能让"已确认"挂在一份改过的内容上。
    """
    if room_id in revision.approved_rooms:
        revision.approved_rooms.remove(room_id)
    revision.inherited_rooms.pop(room_id, None)
    key = WorkflowStage.LAYOUT_PLAN.value
    if revision.pending_room_ids():
        revision.layout = replace(revision.layout, confirmed=False)
        revision.stage_outputs[key] = revision.layout.to_dict()
        if key in revision.approved_stages:
            revision.approved_stages.remove(key)
        revision.approved_digests.pop(key, None)
