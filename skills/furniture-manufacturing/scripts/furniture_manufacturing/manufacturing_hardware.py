"""Hardware matching — drawer slides (other hardware handled by Connectors)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .manufacturing_models import PanelRecord


_CATALOG: Dict[str, Any] | None = None


def _load_catalog() -> Dict[str, Any]:
    global _CATALOG
    if _CATALOG is None:
        catalog_path = Path(__file__).resolve().parent / "hardware_catalog.yaml"
        with open(catalog_path, "r", encoding="utf-8") as f:
            _CATALOG = yaml.safe_load(f) or {}
    return _CATALOG


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


def _pick_brand(entry: Dict[str, Any], preferred_brand: str | None) -> Dict[str, str]:
    brands = entry.get("brands", [])
    if not brands:
        return {"name": "默认", "model": "N/A"}

    if preferred_brand:
        for b in brands:
            if b["name"] == preferred_brand:
                return b

    return brands[0]