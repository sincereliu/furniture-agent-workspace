"""修订继承：内容没变的下游产物不必让人再确认一次。

机制与取舍见 `references/revision-inheritance-design.md`。这里只做两件事：

1. **判据 `envelope_set` / `envelope_diff`**：把布局投影成"下游真正读到的那五个字段"
   （`id` / `furniture_category` / `width` / `depth` / `height`），用来向人解释这次到底改了什么。
   投影直接建在 `panel_envelopes_from_layout()` 上——**判据看的字段与板件读到的字段不可能分家**。
2. **承认的证据 `inheritance_source()`**：在更早的 Revision 里找"这份内容已经被确认过"的那一版。

一条重要取舍：**承认靠内容摘要逐字节比对，不靠判据推断**。
`envelope_set` 只用来解释，不用来决定"可以跳过重算"——重算本身是毫秒级，
而短路会把隐藏依赖的风险引进来（某阶段偷读了布局的其它字段，判据就会误判成"没变"）。
逐字节相同才继承，不同就重算，没有"大概没变"这种档位。
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from furniture_layout.project_layout import LayoutUnit, ProjectLayout

from .input_adapter import panel_envelopes_from_layout
from .workflow_digest import stable_digest
from .workflow_project import Project, Revision
from .workflow_state import WorkflowStage


#: 下游真正读到的字段——多于这个集合的任何东西都不该影响柜体内容。
ENVELOPE_FIELDS = ("furniture_category", "width", "depth", "height")


def envelope_set(layout: ProjectLayout) -> dict[str, tuple[Any, ...]]:
    """`{unit.id: (furniture_category, width, depth, height)}`，与顺序无关。

    先按落盘精度取整再比较：`599.9999` 与 `600` 是同一件东西，不该被当成"变了"。
    """
    units = _executable_units(layout)
    return {unit.id: (unit.furniture_category, *_rounded(unit)) for unit in units}


def envelope_diff(previous: ProjectLayout, current: ProjectLayout) -> dict[str, Any]:
    """两份布局的柜体差异，分类列出。

    `same=True` 表示**下游读到的内容没变**——房间、摆放、原点、旋转怎么动都不影响它。
    返回的每类都是 id 列表，按字母序，便于比较与展示。
    """
    before = envelope_set(previous)
    after = envelope_set(current)
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    resized: list[str] = []
    recategorized: list[str] = []
    for unit_id in sorted(set(before) & set(after)):
        if before[unit_id][0] != after[unit_id][0]:
            recategorized.append(unit_id)
        elif before[unit_id][1:] != after[unit_id][1:]:
            resized.append(unit_id)
    changed = sorted({*added, *removed, *resized, *recategorized})
    return {
        "same": not changed,
        "added": added,
        "removed": removed,
        "resized": resized,
        "recategorized": recategorized,
        "changed": changed,
    }


def inheritance_source(
    project: Project,
    revision: Revision,
    stage: str | WorkflowStage,
    digest: str,
) -> Revision | None:
    """哪一版**已经被确认过**的这个阶段，内容与 `digest` 完全相同。

    证据是"更早的 Revision 上该阶段已确认、且它的内容摘要就是这个值"——
    也就是"人真的为这份内容点过头"。找不到就返回 `None`（该重算、该重新确认）。
    """
    key = stage.value if isinstance(stage, WorkflowStage) else str(stage)
    for earlier in project.revisions:
        if earlier is revision or earlier.id == revision.id:
            continue
        if key not in earlier.approved_stages:
            continue
        if earlier.confirmed_digest(key) == digest:
            return earlier
    return None


def inherited_evidence(
    source: Revision,
    *,
    stage: str | WorkflowStage,
    digest: str,
) -> dict[str, Any]:
    """R2 留痕用的记录：内容摘要 + 真正点头的那一版。

    `approved_stages` 的语义是**「这份内容已被确认过」**，不是"人在这一版又点了一次头"；
    审计时靠这里的 `from_revision` 回指到真正点头的那一版。
    """
    key = stage.value if isinstance(stage, WorkflowStage) else str(stage)
    return {"sha256": digest, "from_revision": source.id, "from_stage": key}


def stage_digest(output: Mapping[str, Any]) -> str:
    """阶段产出的内容摘要——与 `Revision.panel_sha256` 同一套算法。"""
    return stable_digest(output)


def _executable_units(layout: ProjectLayout) -> Iterable[LayoutUnit]:
    """走 `panel_envelopes_from_layout` 的同一张投影表（它要求布局已确认）。

    未确认的布局同样要能算判据（页面上的草稿也得能解释"改了什么"），
    所以这里不经过那道确认检查，只借它的字段表。
    """
    if not isinstance(layout, ProjectLayout):
        raise ValueError("envelope_set requires a ProjectLayout")
    return layout.executable_units()


def _rounded(unit: LayoutUnit) -> tuple[float, float, float]:
    # 落盘精度就是毫米整数（placement 与尺寸本来就取整），比较前先归一。
    return (
        round(float(unit.width), 6),
        round(float(unit.depth), 6),
        round(float(unit.height), 6),
    )


__all__ = [
    "ENVELOPE_FIELDS",
    "envelope_diff",
    "envelope_set",
    "inheritance_source",
    "inherited_evidence",
    "panel_envelopes_from_layout",
    "stage_digest",
    "WorkflowStage",
]
