"""制造阶段的输出契约：**每台柜一份 BOM**。

为什么单独一层：板件阶段早就支持"布局里有几台柜就有几个 `cabinets[]`"，
制造 / 特征树 / CAD / 交付以前只读 `cabinets[0]`（主柜）——拆成三台只有一台能走到车间。
这一层给出"逐柜读"的唯一入口，并拒绝被压扁成单份的形状。

形状（写进 `stage_outputs["manufacture_plan"]`）：

```json
{"cabinets": [{"id": "cabinet_1", "bom": {…BOMReport…}}, …]}
```

与板件阶段的 `cabinets[]` 一一对应、顺序一致。
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

_OUTPUT_FIELDS = frozenset({"cabinets"})


def cabinets_from_manufacturing(output: Mapping[str, Any]) -> list[dict[str, Any]]:
    """制造阶段产物里的逐柜条目 `[{"id", "bom"}]`；形状不对就拒，不静默取第一台。"""
    unknown = sorted(set(output) - _OUTPUT_FIELDS)
    if unknown:
        raise ValueError(
            "manufacture stage output does not support: " + ", ".join(unknown)
        )
    raw = output.get("cabinets")
    if not isinstance(raw, list) or not raw:
        raise ValueError("manufacture stage output requires cabinets")
    cabinets: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError("each manufactured cabinet must be an object")
        cabinet_id = item.get("id")
        if not isinstance(cabinet_id, str) or not cabinet_id:
            raise ValueError("each manufactured cabinet requires an id")
        if not isinstance(item.get("bom"), Mapping):
            raise ValueError(f"{cabinet_id} requires bom")
        cabinets.append({"id": cabinet_id, "bom": dict(item["bom"])})
    return cabinets


#: 就绪度从弱到强（与 `MANUFACTURING_READINESS_LABELS` 的顺序一致）。
READINESS_ORDER = ("preliminary", "accepted", "factory_ready")

_LIST_FIELDS = (
    "panels",
    "hardware",
    "operations",
    "materials",
    "features",
    "connection_points",
)


def merged_manufacturing_view(output: Mapping[str, Any]) -> dict[str, Any]:
    """把逐柜 BOM 合成**整份工程**的视图，给旁路分析（材料/工序总量按整份算）。

    - 各柜的 `panels` / `hardware` / `operations` / `materials` / `features` /
      `connection_points` 依次拼接——板件 id 已经带柜名前缀（`{cabinet_id}__{role}`），不会撞；
    - `readiness` 取**最弱**的那一台：一台还没定，整份就还不算定；
    - 柜间可能不同的字段（`furniture_name` / `dimensions` / 三个外形尺寸 / `board_thickness`）
      **不假装统一**，这里只带 `cabinet_count`，需要单台细节的读 `cabinets_from_manufacturing()`。

    这是**只读视图**，不写回任何阶段产物（`stage_analyses` 是证据，不是阶段事实）。
    """
    cabinets = cabinets_from_manufacturing(output)
    boms = [entry["bom"] for entry in cabinets]
    merged: dict[str, Any] = {
        "cabinet_count": len(cabinets),
        "readiness": weakest_readiness(
            [str(bom.get("readiness", READINESS_ORDER[0])) for bom in boms]
        ),
    }
    for field in _LIST_FIELDS:
        merged[field] = [
            item for bom in boms for item in bom.get(field, [])
        ]
    return merged


def weakest_readiness(values: Iterable[str]) -> str:
    """整份工程的就绪度 = **最弱**的那一台：一台还没定，整份就还不算定。

    认不出的状态按最弱处理（保守）：这里只做汇总，不替阶段验收下结论。
    """
    ranks = {value: index for index, value in enumerate(READINESS_ORDER)}
    weakest = READINESS_ORDER[-1]
    for value in values:
        text = str(value)
        rank = ranks.get(text, 0)
        if rank < ranks[weakest]:
            weakest = text if text in ranks else READINESS_ORDER[0]
    return weakest


__all__ = [
    "READINESS_ORDER",
    "cabinets_from_manufacturing",
    "merged_manufacturing_view",
    "weakest_readiness",
]
