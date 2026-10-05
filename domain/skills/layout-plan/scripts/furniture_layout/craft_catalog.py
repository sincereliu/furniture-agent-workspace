"""车间工艺目录（`references/craft-catalog.yaml`）的加载与准入。

**数据不是代码**：数字只住在那份 YAML 里（车间维护），这里只负责读、校验形状、
缺项时**说清缺什么**——绝不补默认值（缺就停问，不猜）。

为什么单独一层：拆分求解器要知道"这门宽上限是多少、踢脚多高、收口怎么扣"，
板件阶段也读同一批数字。两处都从这里取，谁也不许在代码里写死。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

DEFAULT_CATALOG_PATH = (
    Path(__file__).resolve().parents[2] / "references" / "craft-catalog.yaml"
)

#: 顶层必须有的键。缺一个就停问——不要拿"没约束"糊过去。
REQUIRED_KEYS = ("version", "door", "toe_kick_mm", "edge", "families")
FILLER_POLICIES = frozenset({"reserve_max", "reserve_typical"})
READINESS_KEYS = ("unit_widths_mm", "bays", "reach")


class MissingCraftData(ValueError):
    """目录里没有这个数——**停问**，不猜。

    消息里必须说清三件事：缺什么、给谁用、往哪一份文件的哪个键加。
    """

    def __init__(self, key: str, *, needed_by: str, hint: str = "") -> None:
        where = hint or "references/craft-catalog.yaml"
        super().__init__(
            f"工艺目录缺 {key}（{needed_by} 需要它）——请车间在 {where} 里补上；"
            "在此之前这一步只能停问，不猜。"
        )
        self.key = key


@dataclass(frozen=True)
class CraftCatalog:
    """一份加载并校验过的工艺目录。字段名与 YAML 对齐，取值已归一。"""

    version: str
    door_max_width_mm: float
    door_min_width_mm: float
    toe_kick_mm: float
    filler_allowance_mm: tuple[float, float]
    filler_policy: str
    families: Mapping[str, Mapping[str, Any]]
    raw: Mapping[str, Any]

    def family(self, kind: str) -> Mapping[str, Any]:
        """柜类条目。目录里没有这个柜类就停问（**代码不猜词**）。"""
        entry = self.families.get(kind)
        if entry is None:
            known = ", ".join(sorted(self.families)) or "（空）"
            raise MissingCraftData(
                f"families.{kind}",
                needed_by=f"柜类 {kind!r} 的门宽/进深/踢脚",
                hint=f"references/craft-catalog.yaml 的 families（现有：{known}）",
            )
        return entry

    def door_bounds(self, kind: str) -> tuple[float, float]:
        """这个柜类的门扇宽区间 `(min, max)`；柜类没给就用兜底区间。"""
        override = self.family(kind).get("door_width_mm")
        if override is None:
            return self.door_min_width_mm, self.door_max_width_mm
        low, high = _number_range(override, f"families.{kind}.door_width_mm")
        return low, high

    def recommended_depth_mm(self, kind: str) -> float:
        """这个柜类的进深（外形含门）。目录给的是常规值/区间，区间取常规端。"""
        entry = self.family(kind)
        value = entry.get("depth_mm")
        if value is None:
            raise MissingCraftData(
                f"families.{kind}.depth_mm",
                needed_by=f"{kind} 的柜体进深",
            )
        if isinstance(value, (list, tuple)):
            low, high = _number_range(value, f"families.{kind}.depth_mm")
            return high if self.filler_policy == "reserve_max" else low
        return float(value)

    def toe_kick_mm_for(self, kind: str) -> float:
        """这个柜类的踢脚高：柜类给了就用它，否则用全局默认。"""
        value = self.family(kind).get("toe_kick_mm", self.toe_kick_mm)
        if isinstance(value, (list, tuple)):
            low, high = _number_range(value, f"families.{kind}.toe_kick_mm")
            return high if self.filler_policy == "reserve_max" else low
        return float(value)

    def filler_mm(self, kind: str) -> float:
        """这一排要扣掉的收口量（净尺寸用）。

        收口条宽度**本身是现场值**；目录只给"允许区间 + 扣减策略"：
        `reserve_max` 按上限扣（最保险），`reserve_typical` 需要一个常规值——
        没有那个值就停问。
        """
        if self.filler_policy == "reserve_max":
            return self.filler_allowance_mm[1]
        typical = self.raw.get("edge", {}).get("filler_typical_mm")
        if typical is None:
            raise MissingCraftData(
                "edge.filler_typical_mm",
                needed_by="按常规值扣收口（filler_policy: reserve_typical）",
            )
        return float(typical)

    def missing_readiness_keys(self) -> tuple[str, ...]:
        """还没给的后续项（宽档、功能格净宽、可达性）——给停问话术用。"""
        return tuple(key for key in READINESS_KEYS if key not in self.raw)

    def envelope_height_mm(self, kind: str) -> float:
        """这个柜类的**柜体高度**（包络高，含踢脚）。

        - 目录给了 `height_mm` → 用它；
        - 地柜给了 `counter_height_mm`（台面完成面到地）+ `counter_thickness_mm`（常用台面厚）
          → **柜体高 = 台面高 − 台面厚**（目录自己注明"台面厚只用来推柜体高"）；
        - 都没有 → 停问（比如衣柜，得客户/空间给高度）。
        """
        entry = self.family(kind)
        if "height_mm" in entry:
            return _positive(entry["height_mm"], f"families.{kind}.height_mm")
        counter = entry.get("counter_height_mm")
        thickness = entry.get("counter_thickness_mm")
        if counter is not None and thickness is not None:
            height = _positive(counter, f"families.{kind}.counter_height_mm") - _positive(
                thickness, f"families.{kind}.counter_thickness_mm"
            )
            if height <= 0:
                raise ValueError(
                    f"craft catalog families.{kind}: 台面厚不能大于台面高"
                )
            return height
        raise MissingCraftData(
            f"families.{kind}.height_mm",
            needed_by=f"{kind} 的柜体高度（空间没给、目录也没有可推的台面高）",
        )


def load_craft_catalog(path: str | Path | None = None) -> CraftCatalog:
    """读并校验目录。形状不对**在加载时就拒**（负数、区间反了、档位不递增…）。"""
    import yaml  # 运行时可读的 YAML；依赖已在环境里

    catalog_path = Path(path) if path is not None else DEFAULT_CATALOG_PATH
    data = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError(f"craft catalog must be an object: {catalog_path}")
    unknown = sorted(set(data) - set(REQUIRED_KEYS) - set(READINESS_KEYS))
    if unknown:
        raise ValueError("craft catalog does not support: " + ", ".join(unknown))
    for key in REQUIRED_KEYS:
        if key not in data:
            raise ValueError(f"craft catalog requires: {key}")

    version = str(data["version"]).strip()
    if not version:
        raise ValueError("craft catalog version must not be empty")

    door = data["door"]
    if not isinstance(door, Mapping):
        raise ValueError("craft catalog door must be an object")
    door_max = _positive(door.get("max_width_mm"), "door.max_width_mm")
    door_min = _positive(door.get("min_width_mm"), "door.min_width_mm")
    if door_min > door_max:
        raise ValueError("door.min_width_mm must not exceed door.max_width_mm")

    toe_kick = _positive(data["toe_kick_mm"], "toe_kick_mm")
    edge = data["edge"]
    if not isinstance(edge, Mapping):
        raise ValueError("craft catalog edge must be an object")
    filler = _number_range(edge.get("filler_allowance_mm"), "edge.filler_allowance_mm")
    policy = str(edge.get("filler_policy", "")).strip()
    if policy not in FILLER_POLICIES:
        raise ValueError(
            "edge.filler_policy must be one of: " + ", ".join(sorted(FILLER_POLICIES))
        )
    families = data["families"]
    if not isinstance(families, Mapping) or not families:
        raise ValueError("craft catalog families must be a non-empty object")
    for name, entry in families.items():
        if not isinstance(entry, Mapping):
            raise ValueError(f"craft catalog families.{name} must be an object")
        if "door_width_mm" in entry:
            _number_range(entry["door_width_mm"], f"families.{name}.door_width_mm")
        if "depth_mm" in entry:
            value = entry["depth_mm"]
            if isinstance(value, (list, tuple)):
                _number_range(value, f"families.{name}.depth_mm")
            else:
                _positive(value, f"families.{name}.depth_mm")
        if "toe_kick_mm" in entry:
            value = entry["toe_kick_mm"]
            if isinstance(value, (list, tuple)):
                _number_range(value, f"families.{name}.toe_kick_mm")
            else:
                _positive(value, f"families.{name}.toe_kick_mm")
    for key in READINESS_KEYS:
        if key in data and not isinstance(data[key], (list, Mapping)):
            raise ValueError(f"craft catalog {key} must be a list or an object")

    return CraftCatalog(
        version=version,
        door_max_width_mm=door_max,
        door_min_width_mm=door_min,
        toe_kick_mm=toe_kick,
        filler_allowance_mm=filler,
        filler_policy=policy,
        families={str(name): dict(entry) for name, entry in families.items()},
        raw=dict(data),
    )


def _positive(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"craft catalog {where} must be a number")
    number = float(value)
    if not number > 0:
        raise ValueError(f"craft catalog {where} must be positive")
    return number


def _number_range(value: Any, where: str) -> tuple[float, float]:
    """两元区间：两个正数、升序。单个数按"只有一个档"处理。"""
    if isinstance(value, bool):
        raise ValueError(f"craft catalog {where} must be a number or a two-number list")
    if isinstance(value, (int, float)):
        number = _positive(value, where)
        return number, number
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"craft catalog {where} must be a two-number list")
    low = _positive(value[0], where)
    high = _positive(value[1], where)
    if low > high:
        raise ValueError(f"craft catalog {where} must be ascending")
    return low, high


__all__ = [
    "CraftCatalog",
    "DEFAULT_CATALOG_PATH",
    "MissingCraftData",
    "load_craft_catalog",
]
