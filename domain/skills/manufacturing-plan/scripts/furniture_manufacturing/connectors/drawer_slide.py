"""抽屉滑轨连接件 — 抽屉滑轨五金匹配与 BOM。

滑轨螺钉安装属组装现场工艺，不生成孔位（与 cover/groove 螺钉一致）。
滑轨长度由**抽屉自身深度**决定，承重由**抽屉宽度**决定——尺寸取自抽屉
板件，不依赖柜体面板猜测。

抽屉板件契约（详见 references/drawer-component-design.md）：
- panel_type 含 "drawer"（如 drawer_front / drawer_side / drawer_bottom）；
- label 形如 "drawer_<角色>_<实例后缀>"，实例 key = label 最后一个
  "_" 分段（沿用动态板件命名，如 shelf_z999 → z999）；
- 每抽左右各 1 副，数量 = 2 × 抽屉实例数。
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from furniture_manufacturing.connectors.base import Connector, HoleSpec
from furniture_manufacturing.manufacturing_models import (
    HardwareRecord,
    MachiningOperation,
    PanelRecord,
)


class DrawerSlideConnector(Connector):
    """抽屉滑轨连接件：按抽屉实例匹配滑轨型号与数量。

    单一默认滑轨类型（三节轨侧装，与铰链精简为单一默认同思路）；
    隐藏轨/品牌选择待抽屉组件落地后由确认选择（options）注入。
    """

    name = "抽屉滑轨"
    hole_type_for_json = "drawer_slide"
    catalog_entry = "drawer_slides"
    rules_section = None

    # 默认滑轨类型与品牌（显式默认，非静默取 brands[0]）
    slide_type = "三节轨"
    default_brand: str = "默认"

    @staticmethod
    def _is_drawer_panel(panel: PanelRecord) -> bool:
        return "drawer" in panel.panel_type

    @staticmethod
    def _instance_key(panel: PanelRecord) -> str:
        """抽屉实例标识 = label 最后一个 "_" 分段（位置后缀）。

        约定：drawer_side_z300 / drawer_front_z300 同属抽屉 z300。
        无后缀（如 drawer_side）时以 label 自身为 key。
        """
        parts = panel.label.split("_")
        return parts[-1] if len(parts) >= 2 else panel.label

    def match(self, panels: List[PanelRecord]) -> Dict[str, Any]:
        drawer_panels = [p for p in panels if self._is_drawer_panel(p)]
        by_instance: Dict[str, List[PanelRecord]] = {}
        for panel in drawer_panels:
            by_instance.setdefault(self._instance_key(panel), []).append(panel)
        return {
            "drawers": drawer_panels,
            "instances": by_instance,
        }

    def generate_holes(self, panel: PanelRecord) -> List[HoleSpec]:
        # 滑轨螺钉为组装现场工艺，不生成孔位
        return []

    def boms(
        self,
        panels: List[PanelRecord],
        *,
        options: Mapping[str, Any] | None = None,
    ) -> List[HardwareRecord]:
        matched = self.match(panels)
        instances = matched["instances"]
        if not instances:
            return []

        opts = (options or {}).get(self.catalog_entry, {})
        opts = dict(opts) if isinstance(opts, Mapping) else {}

        # 每个抽屉实例算一副（左右各 1）；不同规格（长度/承重）分条记录
        per_spec: Dict[tuple, int] = {}
        for instance_panels in instances.values():
            depth = max(p.size_y for p in instance_panels)
            width = max(p.size_x for p in instance_panels)
            slide = self._match_slide(depth, width, opts)
            if not slide:
                continue
            key = (
                slide["brand"],
                slide["model"],
                slide["length_mm"],
                slide["load_rating"],
            )
            per_spec[key] = per_spec.get(key, 0) + 2

        records: List[HardwareRecord] = []
        for (brand, model, length, load), quantity in sorted(per_spec.items()):
            records.append(HardwareRecord(
                name=self.name,
                spec=f"{brand} {model} {length}mm {load}",
                quantity=quantity,
                unit="副",
                brand=brand,
                model=model,
                note="每抽左右各 1，投产前确认",
            ))
        return records

    def _match_slide(
        self,
        depth_mm: float,
        width_mm: float,
        opts: Dict[str, Any],
    ) -> Dict[str, Any]:
        """按抽屉深度匹配标准长度、按宽度定承重、选品牌。"""
        catalog = self.catalog.get(self.catalog_entry, {})
        entry = catalog.get(opts.get("variant", self.slide_type)) if catalog else None
        if not entry:
            return {}

        # 滑轨长度 ≤ 抽屉深度 − 50mm（尾部间隙）
        standard_lengths = sorted(entry.get("standard_lengths_mm", []))
        if not standard_lengths:
            return {}
        target_length = depth_mm - 50
        match_length = next(
            (length for length in reversed(standard_lengths) if length <= target_length),
            standard_lengths[0],  # 兜底最小号
        )

        # 承重级别
        load_rating = "45kg" if width_mm > 600 else "30kg"
        brand = self._pick_brand(entry, opts.get("brand"))

        return {
            "slide_type": self.slide_type,
            "brand": brand["name"],
            "model": brand["model"],
            "length_mm": match_length,
            "load_rating": load_rating,
            "mounting": entry.get("mounting", "侧装"),
            "gap_requirement_mm": entry.get("gap_requirement_mm", 12.5),
        }

    def _pick_brand(
        self,
        entry: Dict[str, Any],
        selection: str | None = None,
    ) -> Dict[str, str]:
        """按确认选择/显式默认解析品牌；歧义时抛错，不静默取第一个。"""
        return self.resolve_brand(
            entry.get("brands", []),
            selection or self.default_brand,
        )

    def machining_operations(self, panel: PanelRecord) -> List[MachiningOperation]:
        # 滑轨无柜体加工指令
        return []
