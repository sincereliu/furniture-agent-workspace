"""工作流自己拼装的**逐柜**产物形状（板件与制造各自在自己包里定形状）。

板件阶段输出 `cabinets[]`（`furniture_panel_planning.cabinet_identity`）、制造阶段输出
`{"cabinets": [{"id", "bom"}]}`（`furniture_manufacturing.manufacturing_handoff`）都各有归属；
特征树这一层是**工作流**一台一台算出来再拼的，所以它的形状在这里定义：

```json
{"cabinets": [{"id": "cabinet_1", "tree": {…Feature Tree v2…}}, …]}
```

与上游 `cabinets[]` 一一对应、顺序一致。`primary_*` 只给逐柜改造之前的调用用（旧版 CAD 路径、
旁路分析）；逐柜路径请用 `cabinets_from_*`。
"""

from __future__ import annotations

from typing import Any, Mapping


def cabinets_from_feature_trees(output: Mapping[str, Any]) -> list[dict[str, Any]]:
    """特征树产物里的逐柜条目 `[{"id", "tree"}]`；形状不对就拒，不静默取第一棵。"""
    raw = output.get("cabinets")
    if not isinstance(raw, list) or not raw:
        raise ValueError("feature tree output requires cabinets")
    cabinets: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError("each feature tree cabinet must be an object")
        cabinet_id = item.get("id")
        if not isinstance(cabinet_id, str) or not cabinet_id:
            raise ValueError("each feature tree cabinet requires an id")
        if not isinstance(item.get("tree"), Mapping):
            raise ValueError(f"{cabinet_id} requires tree")
        cabinets.append({"id": cabinet_id, "tree": dict(item["tree"])})
    return cabinets


def cabinets_from_bridges(output: Mapping[str, Any]) -> list[dict[str, Any]]:
    """CAD 产物里的逐柜条目 `[{"id", "bridge"}]`；形状不对就拒，不静默取第一台。"""
    raw = output.get("cabinets")
    if not isinstance(raw, list) or not raw:
        raise ValueError("CAD output requires cabinets")
    cabinets: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError("each CAD cabinet must be an object")
        cabinet_id = item.get("id")
        if not isinstance(cabinet_id, str) or not cabinet_id:
            raise ValueError("each CAD cabinet requires an id")
        if not isinstance(item.get("bridge"), Mapping):
            raise ValueError(f"{cabinet_id} requires bridge")
        cabinets.append({"id": cabinet_id, "bridge": dict(item["bridge"])})
    return cabinets


__all__ = ["cabinets_from_bridges", "cabinets_from_feature_trees"]
