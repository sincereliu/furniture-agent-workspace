from __future__ import annotations

from typing import Any


def plan_furniture(spec: dict[str, Any]) -> dict[str, Any]:
    """统一入口：根据 furniture_type 路由到柜体规划器。

    支持的类型: floor_cabinet / wall_cabinet
    返回标准 Feature Tree dict，兼容 emitter 和 pipeline 测试。
    """
    furniture_type = str(spec.get("furniture_type", "")).strip().lower()

    if furniture_type in ("floor_cabinet", "wall_cabinet"):
        return _plan_cabinet(spec, furniture_type)

    raise ValueError(
        f"Unsupported furniture type {furniture_type!r}; "
        f"supported: floor_cabinet, wall_cabinet."
    )


def _plan_cabinet(spec: dict[str, Any], furniture_type: str) -> dict[str, Any]:
    """委托给 pipeline + emitter，返回 Feature Tree dict。"""
    from furniture_feature_tree.feature_tree_builder import panels_to_feature_tree
    from furniture_panel_planning.panel_spec import FurnitureSpec

    from .cabinet_pipeline import plan_cabinet

    fspec = FurnitureSpec.from_dict(spec)
    result = plan_cabinet(fspec)

    return panels_to_feature_tree(
        result.panels,
        furniture_type=furniture_type,
        parameters={
            "width": fspec.width,
            "depth": fspec.depth,
            "height": fspec.height,
            "board_thickness": fspec.board_thickness,
        },
    )
