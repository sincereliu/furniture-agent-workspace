"""Manufacturing-stage edge-banding policy."""

from __future__ import annotations

from typing import Dict, Mapping

from .edge_banding_catalog import thickness_mm

# 默认封边选型（= 历史「ABS 1.0mm」）；可经 requested_options.edge_banding 覆盖
DEFAULT_EDGE_BANDING_SELECTION = {"material": "abs", "thickness": "t1_0"}

# 封四边的面板类型（背板入槽不封边由调用方按 back_mount 处理）
FOUR_EDGE_TYPES = frozenset(
    {
        "side", "top", "bottom", "fixed_shelf", "movable_shelf", "divider",
        "toe_kick", "door", "back", "back_rail",
        "drawer_front", "drawer_side", "drawer_back", "drawer_bottom",
    }
)


def build_edge_banding(
    panel_type: str,
    *,
    thickness: float,
    surface: str,
    selection: Mapping[str, str] | None = None,
) -> Dict[str, Dict]:
    """构造一块板的结构化封边：封哪些边 + 封边条规格（选型 + 派生）。

    派生：宽度 = 板件厚度；颜色 = surface 的 color 段（同色）。
    非四边类型返回空字典（不封边）。
    """
    if panel_type not in FOUR_EDGE_TYPES:
        return {}
    sel = dict(DEFAULT_EDGE_BANDING_SELECTION)
    sel.update(selection or {})
    spec = {
        "material": sel.get("material", "abs"),
        "thickness_mm": thickness_mm(sel.get("thickness", "t1_0")),
        "width_mm": thickness,
        "color": surface.split("__")[0] if surface else "",
    }
    return {"四边": spec}
