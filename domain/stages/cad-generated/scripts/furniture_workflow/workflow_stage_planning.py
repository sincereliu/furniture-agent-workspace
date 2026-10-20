"""Stateless per-cabinet manufacturing and feature-tree conversions.

Cabinet identity, ordering, and overrides come from structured stage inputs.
This module does not advance stages, record attempts, or persist projects.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from furniture_feature_tree.feature_tree_builder import panels_to_feature_tree
from furniture_manufacturing.manufacturing_bom import plan_manufacturing


def _cabinet_option_overrides(
    raw: Any, planned_ids: list[str]
) -> dict[str, dict[str, Any]]:
    """校验制造阶段的逐柜选项：柜名必须认识、只认 `parameters` / `appearance`。

    不认识的柜名直接拒（不静默忽略）——否则"给 2 号柜设的铰链方向"会悄悄丢掉，
    再跑到制造阶段才炸（实测撞到过：单门没给铰链方向）。
    """
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ValueError("manufacturing stage cabinets must be an object")
    known = set(planned_ids)
    overrides: dict[str, dict[str, Any]] = {}
    for cabinet_id, override in raw.items():
        name = str(cabinet_id)
        if name not in known:
            raise ValueError(f"manufacturing stage has an unknown cabinet id: {name}")
        if not isinstance(override, Mapping):
            raise ValueError(f"manufacturing options for {name} must be an object")
        unknown = sorted(set(override) - {"parameters", "appearance"})
        if unknown:
            raise ValueError(
                f"manufacturing options for {name} do not support: "
                + ", ".join(unknown)
            )
        for part in ("parameters", "appearance"):
            if part in override and not isinstance(override[part], Mapping):
                raise ValueError(f"manufacturing {part} for {name} must be an object")
        overrides[name] = dict(override)
    return overrides


def plan_every_cabinet(
    handoffs: list[tuple[str, Any, list[Any]]],
    stage_input: Mapping[str, Any],
) -> dict[str, Any]:
    """**逐柜**做制造计划：布局里有几台，就出几份 BOM。

    以前只对主柜算一次，所以拆成三台只有一台能走到车间。柜的**身份与顺序**
    都来自板件阶段（布局决定的），这里不挑、不排、不漏。

    **逐柜选项**：`stage_input["cabinets"][柜名]` 可以覆盖 `parameters` / `appearance`——
    铰链方向、活动层板连接方式这些本来就是**按柜**定的（一台单门、一台双门时，
    共享一份 `door_hinge_side` 根本表达不了：实测撞到过）。
    """
    shared_options = dict(stage_input.get("parameters", {}))
    shared_appearance = dict(stage_input.get("appearance", {}))
    overrides = _cabinet_option_overrides(
        stage_input.get("cabinets"), [cabinet_id for cabinet_id, _, _ in handoffs]
    )
    cabinets = []
    for cabinet_id, spec, placements in handoffs:
        override = overrides.get(cabinet_id, {})
        bom = plan_manufacturing(
            spec,
            placements,
            requested_options={
                **shared_options,
                **dict(override.get("parameters", {})),
            },
            appearance={
                **shared_appearance,
                **dict(override.get("appearance", {})),
            },
        )
        cabinets.append({"id": cabinet_id, "bom": asdict(bom)})
    return {"cabinets": cabinets}

def feature_trees_from(boms: list[tuple[str, Any]]) -> dict[str, Any]:
    """**逐柜**出特征树，与制造产物一一对应、顺序一致。"""
    cabinets = []
    for cabinet_id, bom in boms:
        tree = panels_to_feature_tree(
            bom.panels,
            bom.operations,
            furniture_category=bom.furniture_category,
            parameters={
                "width": bom.width,
                "depth": bom.depth,
                "height": bom.height,
                "board_thickness": bom.board_thickness,
            },
        )
        cabinets.append({"id": cabinet_id, "tree": tree})
    return {"cabinets": cabinets}
