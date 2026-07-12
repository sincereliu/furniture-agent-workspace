"""硬件匹配引擎 — 根据板件参数从规格库中选出具体型号和数量

职责:
  ✅ 输入: 板件列表 + 用户偏好 (brand, variant)
  ✅ 输出: 匹配后的硬件清单 (型号 + 数量 + 孔位)
  ❌ 不直接做孔位计算（委托 drilling_engine）
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from furniture_panel_planning.panel_models import PanelRecord


# ── 加载规格库 ──────────────────────────────────────────────
_CATALOG: Dict[str, Any] | None = None


def _load_catalog() -> Dict[str, Any]:
    global _CATALOG
    if _CATALOG is None:
        catalog_path = Path(__file__).resolve().parent / "hardware_catalog.yaml"
        with open(catalog_path, "r", encoding="utf-8") as f:
            _CATALOG = yaml.safe_load(f) or {}
    return _CATALOG


# ── 铰链匹配 ────────────────────────────────────────────────
def match_hinges(
    door_panels: List[PanelRecord],
    *,
    preferred_brand: str | None = None,
    preferred_variant: str | None = None,
    overlay: str = "full",
    angle: int = 100,
    system_holes: List[float] | None = None,
    shelf_positions: List[float] | None = None,
) -> List[Dict[str, Any]]:
    catalog = _load_catalog().get("hinges", {})
    if not catalog:
        return []

    results: List[Dict[str, Any]] = []
    from .manufacturing_drilling import calc_hinge_positions

    for panel in door_panels:
        door_h = panel.size_z
        door_w = panel.size_x

        hinge_entry = _find_hinge_entry(
            catalog, overlay=overlay, angle=angle,
            preferred_variant=preferred_variant, preferred_brand=preferred_brand,
            door_width_mm=door_w,
        )
        if not hinge_entry:
            continue

        brand = _pick_brand(hinge_entry, preferred_brand)
        variant_group = hinge_entry["variant_group"]
        drilling = calc_hinge_positions(
            door_height_mm=door_h,
            door_width_mm=door_w,
            variant_group=variant_group,
            system_holes=system_holes,
            shelf_positions=shelf_positions,
        )

        results.append({
            "panel_id": panel.label,
            "panel_name": panel.name,
            "brand": brand["name"],
            "model": brand["model"],
            "quantity": len(drilling),
            "variant_group": variant_group,
            "overlay": hinge_entry["overlay"],
            "angle": hinge_entry["angle"],
            "drilling": drilling,
        })

    return results


# ── 三合一公母配对 ──────────────────────────────────────────
def match_three_in_one(
    panels: List[PanelRecord],
    *,
    preferred_brand: str | None = None,
) -> List[Dict[str, Any]]:
    catalog = _load_catalog().get("three_in_one", {})
    if not catalog:
        return []

    entry = list(catalog.values())[0] if catalog else None
    if not entry:
        return []

    from .manufacturing_drilling import calc_system_32_holes

    female_panels = [p for p in panels if p.panel_type in ("side", "divider")]
    male_panels = [p for p in panels if p.panel_type in ("top", "bottom", "fixed_shelf")]

    brand = _pick_brand(entry, preferred_brand)
    ec = entry.get("eccentric_wheel", {})
    cr = entry.get("connecting_rod", {})
    pn = entry.get("pre_embedded_nut", {})

    female_holes_total = 0
    female_details: List[Dict[str, Any]] = []
    for p in female_panels:
        holes = calc_system_32_holes(p.drill_length)
        female_holes_total += len(holes)
        female_details.append({
            "panel_id": p.label,
            "panel_name": p.name,
            "hole_count": len(holes),
            "hole_positions_y_mm": holes,
            "panel_z_start_mm": p.pos_z,
        })

    male_total_end_holes = 0
    male_details: List[Dict[str, Any]] = []
    for p in male_panels:
        edge_holes = calc_system_32_holes(p.drill_length)
        male_total_end_holes += len(edge_holes) * 2
        male_details.append({
            "panel_id": p.label,
            "panel_name": p.name,
            "panel_z_mm": p.pos_z,
            "edge_hole_count": len(edge_holes),
            "hole_positions_on_edge_mm": edge_holes,
        })

    sets = female_holes_total

    return [{
        "type": "三合一",
        "brand": brand["name"],
        "model": brand["model"],
        "sets": sets,
        "female_holes_total": female_holes_total,
        "male_end_holes_total": male_total_end_holes,
        "female_details": female_details,
        "male_details": male_details,
        "eccentric_wheel": {
            "diameter_mm": ec.get("diameter_mm"),
            "hole_depth_mm": ec.get("hole_depth_mm"),
            "center_offset_from_edge_mm": ec.get("center_offset_from_edge_mm"),
        },
        "connecting_rod": {
            "diameter_mm": cr.get("diameter_mm"),
            "insertion_depth_mm": cr.get("insertion_depth_mm"),
        },
        "pre_embedded_nut": {
            "diameter_mm": pn.get("diameter_mm"),
            "depth_mm": pn.get("depth_mm"),
        },
    }]


# ── 活动层板连接件匹配 ──────────────────────────────────────
def match_shelf_connectors(
    panels: List[PanelRecord],
    *,
    connector_type: str = "二合一",
    preferred_brand: str | None = None,
) -> List[Dict[str, Any]]:
    catalog = _load_catalog().get("shelf_connectors", {})
    entry = catalog.get(connector_type) if catalog else None
    if not entry:
        return []

    from .manufacturing_drilling import calc_shelf_holes

    brand = _pick_brand(entry, preferred_brand)
    results: List[Dict[str, Any]] = []

    for p in panels:
        if p.panel_type != "movable_shelf":
            continue
        if p.drill_length <= 0:
            continue

        holes = calc_shelf_holes(p.drill_length)
        total_sets = len(holes) * 2

        results.append({
            "panel_id": p.label,
            "panel_name": p.name,
            "connector_type": connector_type,
            "brand": brand["name"],
            "model": brand["model"],
            "sets": total_sets,
            "hole_count_per_side": len(holes),
            "hole_positions_on_edge_mm": holes,
            "spec": entry.get("spec", {}),
        })

    return results


# ── 抽屉滑轨匹配 ──────────────────────────────────────────
def match_drawer_slides(
    drawer_depth_mm: float,
    drawer_width_mm: float,
    *,
    slide_type: str = "三节轨",
    preferred_brand: str | None = None,
) -> List[Dict[str, Any]]:
    """根据抽屉参数匹配滑轨型号和数量。

    Args:
        drawer_depth_mm: 抽屉深度（Y方向，决定滑轨长度）
        drawer_width_mm: 抽屉宽度（X方向，决定承重级别）
        slide_type: "三节轨" 或 "隐藏轨"
        preferred_brand: 品牌偏好

    Returns:
        [{brand, model, length_mm, quantity, load_rating, ...}]
    """
    catalog = _load_catalog().get("drawer_slides", {})
    entry = catalog.get(slide_type) if catalog else None
    if not entry:
        return []

    # 1. 匹配最近的标准长度（滑轨长度 ≤ 抽屉深度 - 50mm）
    standard_lengths = sorted(entry.get("standard_lengths_mm", []))
    if not standard_lengths:
        return []

    target_length = drawer_depth_mm - 50
    match_length = None
    for length in standard_lengths:
        if length <= target_length:
            match_length = length
        else:
            break

    if match_length is None:
        match_length = standard_lengths[0]  # 兜底最小号

    # 2. 承载级别
    load_rating = "30kg"
    if drawer_width_mm > 600:
        load_rating = "45kg"

    brand = _pick_brand(entry, preferred_brand)

    return [{
        "slide_type": slide_type,
        "brand": brand["name"],
        "model": brand["model"],
        "length_mm": match_length,
        "quantity": 2,  # 每抽左右各1
        "load_rating": load_rating,
        "mounting": entry.get("mounting", "侧装"),
        "gap_requirement_mm": entry.get("gap_requirement_mm", 12.5),
    }]


# ── 内部辅助 ─────────────────────────────────────────────────
def _find_hinge_entry(
    catalog: Dict[str, Any],
    overlay: str,
    angle: int,
    preferred_variant: str | None,
    preferred_brand: str | None,
    door_width_mm: float,
) -> Dict[str, Any] | None:
    candidates: List[Dict[str, Any]] = []
    for key, entry in catalog.items():
        if entry.get("overlay") != overlay:
            continue
        if entry.get("angle") != angle:
            continue
        max_w = entry.get("door_max_width_mm")
        if max_w and door_width_mm > max_w:
            continue
        candidates.append({"key": key, **entry})

    if not candidates:
        return None

    if preferred_variant:
        filtered = [c for c in candidates if c["variant_group"] == preferred_variant]
        if filtered:
            candidates = filtered

    if preferred_brand:
        for c in candidates:
            for b in c["brands"]:
                if b["name"] == preferred_brand:
                    return c

    return candidates[0] if candidates else None


def _pick_brand(entry: Dict[str, Any], preferred_brand: str | None) -> Dict[str, str]:
    brands = entry.get("brands", [])
    if not brands:
        return {"name": "默认", "model": "N/A"}

    if preferred_brand:
        for b in brands:
            if b["name"] == preferred_brand:
                return b

    return brands[0]
