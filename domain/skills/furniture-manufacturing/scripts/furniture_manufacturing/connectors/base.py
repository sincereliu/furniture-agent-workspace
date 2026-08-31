"""五金连接件抽象基类。

提供所有连接件的公共接口：孔位描述、规则加载、BOM 生成。
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping
import yaml
from furniture_manufacturing.manufacturing_models import HardwareRecord, MachiningOperation, PanelRecord


def _opposite(axis: str) -> str:
    """反转带符号轴方向："+x"→"-x"，"-y"→"+y"。"""
    if not axis or axis[0] not in ("+", "-"):
        return "-x"
    return f"{'+' if axis[0] == '-' else '-'}{axis[1]}"


@dataclass
class HoleSpec:
    hole_type: str = ""
    panel_label: str = ""
    x_global: float = 0.0
    y_global: float = 0.0
    z_global: float = 0.0
    x_local: float = 0.0
    y_local: float = 0.0
    z_local: float = 0.0
    diameter: float = 0.0
    depth: float = 0.0
    direction: str = "+y"
    is_face_hole: bool = True  # True=板面钻孔(TypeNo=1), False=板边钻孔(TypeNo=2)
    note: str = ""


class Connector:
    name: str = ""
    hole_type_for_json: str = ""
    catalog_entry: str = ""
    rules_section: str | None = None
    # hole_type → {color, label, glb_group}；Viewer/GLB 图例由各 Connector 自声明派生
    hole_legend: Dict[str, Dict[str, str]] = {}
    _catalog_cache: Dict[str, Any] | None = None
    _rules_cache: Dict[str, Any] | None = None

    @staticmethod
    def _load_catalog() -> Dict[str, Any]:
        if Connector._catalog_cache is None:
            p = Path(__file__).resolve().parent.parent / "hardware_catalog.yaml"
            with open(p, encoding="utf-8") as f:
                Connector._catalog_cache = yaml.safe_load(f) or {}
        return Connector._catalog_cache

    @staticmethod
    def _load_rules() -> Dict[str, Any]:
        if Connector._rules_cache is None:
            p = Path(__file__).resolve().parent.parent / "hardware_rules.yaml"
            with open(p, encoding="utf-8") as f:
                Connector._rules_cache = yaml.safe_load(f) or {}
        return Connector._rules_cache

    @property
    def catalog(self) -> Dict[str, Any]:
        return self._load_catalog()

    @property
    def rules(self) -> Dict[str, Any]:
        return self._load_rules()

    def match(self, panels: List[PanelRecord]) -> Dict[str, Any]:
        raise NotImplementedError

    def generate_holes(self, panel: PanelRecord) -> List[HoleSpec]:
        raise NotImplementedError

    def generate_holes_for_panels(
        self,
        panels: List[PanelRecord],
    ) -> List[HoleSpec]:
        """Generate holes with the full assembly available when needed.

        Ordinary connectors remain panel-local. Assembly-aware connectors can
        override this method to emit matched holes on both mating panels.
        """
        return [
            hole
            for panel in panels
            for hole in self.generate_holes(panel)
        ]

    def boms(
        self,
        panels: List[PanelRecord],
        *,
        options: Mapping[str, Any] | None = None,
    ) -> List[HardwareRecord]:
        raise NotImplementedError

    def validate(
        self,
        report: Any,
        panels: List[PanelRecord],
        hardware: List[HardwareRecord],
        drilled: Dict[str, Any],
    ) -> None:
        """五金专属校验；默认 no-op，由各 Connector 覆盖。"""
        return None

    @staticmethod
    def resolve_brand(
        brands: List[Dict[str, Any]] | None,
        selection: str | None = None,
    ) -> Dict[str, Any]:
        """返回唯一/已确认的品牌；歧义时抛错，不静默取第一个。

        selection 为确认的品牌名；未提供时，目录恰好一个品牌才返回，
        多个品牌则要求显式选择（失败安全，避免代码替用户拍板）。
        """
        candidates = [b for b in (brands or []) if isinstance(b, dict)]
        if not candidates:
            return {"name": "默认", "model": "N/A"}
        if selection is not None:
            for brand in candidates:
                if brand.get("name") == selection:
                    return brand
            raise ValueError(
                f"selected brand {selection!r} is not in the catalog"
            )
        if len(candidates) == 1:
            return candidates[0]
        raise ValueError(
            "multiple brands are available; an explicit selection is required"
        )

    def machining_operations(self, panel: PanelRecord) -> List[MachiningOperation]:
        raise NotImplementedError
