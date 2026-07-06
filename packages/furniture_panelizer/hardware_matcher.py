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

from furniture_schema.panel import PanelRecord


# ── 加载规格库 ──────────────────────────────────────────────
_CATALOG: Dict[str, Any] | None = None


def _load_catalog() -> Dict[str, Any]:
    global _CATALOG
    if _CATALOG is None:
        catalog_path = Path(__file__).resolve().parent / "hardware" / "catalog.yaml"
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
) -> List[Dict[str, Any]]:
    """为门板列表匹配合适的铰链型号和数量。

    Args:
        door_panels: 门板 PanelRecord 列表
        preferred_brand: 品牌偏好（如 "Blum", "DTC"），None 则用默认
        preferred_variant: 规格组偏好（如 "进口35mm杯全盖"），None 则自动匹配
        overlay: 盖法，full / half / inset
        angle: 铰链开启角度，默认 110

    Returns:
        [{brand, model, quantity, variant_group, drilling: [...]}, ...]
        每个门板返回一条记录
    """
    catalog = _load_catalog().get("hinges", {})
    if not catalog:
        return []

    results: List[Dict[str, Any]] = []
    # 导入放在这里避免循环依赖
    from furniture_panelizer.drilling_engine import calc_hinge_positions

    for panel in door_panels:
        door_h = panel.size_z  # 门高
        door_w = panel.size_x  # 门宽

        # 1. 找到匹配的铰链条目
        hinge_entry = _find_hinge_entry(
            catalog, overlay=overlay, angle=angle,
            preferred_variant=preferred_variant, preferred_brand=preferred_brand,
            door_width_mm=door_w,
        )

        if not hinge_entry:
            continue

        # 2. 确定品牌
        brand = _pick_brand(hinge_entry, preferred_brand)

        # 3. 计算孔位
        variant_group = hinge_entry["variant_group"]
        drilling = calc_hinge_positions(
            door_height_mm=door_h,
            door_width_mm=door_w,
            variant_group=variant_group,
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


# ── 内部辅助 ─────────────────────────────────────────────────
def _find_hinge_entry(
    catalog: Dict[str, Any],
    overlay: str,
    angle: int,
    preferred_variant: str | None,
    preferred_brand: str | None,
    door_width_mm: float,
) -> Dict[str, Any] | None:
    """从铰链规格库中找到最佳匹配条目。

    匹配优先级:
      1. 指定了 preferred_variant → 在该组中按 overlay + angle 找
      2. 指定了 preferred_brand → 找该品牌的第一个匹配
      3. 默认 → 国内标准 35mm 优先
    """
    # 收集所有候选项
    candidates: List[Dict[str, Any]] = []
    for key, entry in catalog.items():
        if entry.get("overlay") != overlay:
            continue
        if entry.get("angle") != angle:
            continue
        # 检查门宽限制
        max_w = entry.get("door_max_width_mm")
        if max_w and door_width_mm > max_w:
            continue
        candidates.append({"key": key, **entry})

    if not candidates:
        return None

    # 按规格组过滤
    if preferred_variant:
        filtered = [c for c in candidates if c["variant_group"] == preferred_variant]
        if filtered:
            candidates = filtered

    # 按品牌过滤
    if preferred_brand:
        for c in candidates:
            for b in c["brands"]:
                if b["name"] == preferred_brand:
                    return c

    # 默认：选第一个（国内优先策略隐含在 catalog 顺序中）
    return candidates[0] if candidates else None


def _pick_brand(entry: Dict[str, Any], preferred_brand: str | None) -> Dict[str, str]:
    """从铰链条目中选出目标品牌"""
    brands = entry.get("brands", [])
    if not brands:
        return {"name": "默认", "model": "N/A"}

    if preferred_brand:
        for b in brands:
            if b["name"] == preferred_brand:
                return b

    # 返回第一个（默认品牌）
    return brands[0]