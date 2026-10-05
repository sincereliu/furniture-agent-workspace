"""空间 → 单元：拆分求解器（设计稿见 `references/space-split-design.md` 第四节）。

**它做什么**：把一块空间（"北墙这 2400 做衣柜"）变成 N 个**可制造的单元包络**——
每个单元都能过板件阶段的门数与拓扑上限，并给出 `n_doors` 建议、一句解释、代价提示。

**它不做什么**：不猜柜类词表、不替客户决定通顶与否、不按柜型编默认分格。
目录里没有的数字一律**停问**（`MissingCraftData`），不拿默认值糊过去。

**现在能做到哪一步**（目录数据说话）：
- 净尺寸（扣收口）✓；门扇上限 → 单元宽度上限 ✓；一条空间 → 一台合规单元 ✓；
- 需要**拆分**的空间（净宽超过两扇门的上限）：目录还缺"标准单元宽档 / 功能格最小净宽"，
  所以**停问**，并把可行区间说清——而不是悄悄给一个 3000 宽的包络
  （今天 `fill` 就是这么给的，那是做不出来的柜子）。

**确定性**：同一（空间，约束，目录版本）逐字节同一结果；目录版本记进结果的
`catalog_version`（可追溯），**不进下游摘要**（见设计稿第 4 节第 8 步）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil, isfinite
from typing import Any, Mapping

from .craft_catalog import CraftCatalog, MissingCraftData
from .scene import SpaceRequest

#: 与设计稿第 4 节第 2 步一致：单元宽度上限 = 门扇上限 × 门数（不含边距项）。
OPENING_STYLES = frozenset({"swing", "sliding", "lift"})


@dataclass(frozen=True)
class SplitUnit:
    """一台可制造的单元（展开进 `rooms[].items[]`）。

    `bay`是**功能标签**（挂长衣/叠放/…），现在只有"整柜"一种；`seq` 管显示顺序，
    与 id 解耦（id 只增不改，见设计稿第三节）。
    """

    id: str
    seq: int
    width_mm: float
    depth_mm: float
    height_mm: float
    origin_z_mm: float
    n_doors: int
    bay: str = "whole"
    catalog_version: str = ""


@dataclass(frozen=True)
class SplitResult:
    space_id: str
    units: tuple[SplitUnit, ...]
    catalog_version: str
    notes: tuple[str, ...] = ()
    costs: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = field(default_factory=tuple)

    @property
    def width_total_mm(self) -> float:
        return sum(unit.width_mm for unit in self.units)


class SpaceInfeasible(ValueError):
    """这块空间按目录做不出来——**停问**，并给出可行的说法。"""

    def __init__(self, space_id: str, message: str, *, options: tuple[str, ...] = ()) -> None:
        detail = message
        if options:
            detail += "；可行的做法：" + "；".join(options)
        super().__init__(f"空间 {space_id} 做不出来：{detail}")
        self.space_id = space_id
        self.options = options


def net_width_mm(space: SpaceRequest, catalog: CraftCatalog) -> float:
    """第 1 步：净尺寸。扣掉现场收口（宽度是现场值，目录只给区间与扣减策略）。"""
    filler = filler_for(space, catalog)
    net = float(space.width_mm) - filler
    if not isfinite(net) or net <= 0:
        raise SpaceInfeasible(
            space.id,
            f"扣掉收口 {filler:g} 之后净宽只剩 {net:g}，放不下任何柜子",
            options=("把这块空间加宽", "换更窄的收口做法（现场确认后写在 constraints.filler_mm）"),
        )
    return net


def filler_for(space: SpaceRequest, catalog: CraftCatalog) -> float:
    """这一排实际扣多少收口：客户/现场给了就用它，否则按目录的扣减策略。"""
    for constraint in space.constraints:
        text = constraint.strip()
        if text.startswith("filler_mm="):
            raw = text.split("=", 1)[1].strip()
            try:
                value = float(raw)
            except ValueError as exc:
                raise ValueError(
                    f"constraint filler_mm must be a number: {constraint!r}"
                ) from exc
            if not isfinite(value) or value < 0:
                raise ValueError(f"constraint filler_mm must be >= 0: {constraint!r}")
            return value
    return catalog.filler_mm(space.kind)


def door_count_for(width_mm: float, catalog: CraftCatalog, kind: str) -> int:
    """这一格能做几扇平开门（1 或 2）：按这个柜类的门扇上限取最多能做的门数。

    板件阶段的拓扑上限就是 2 扇，所以这里不给 3。
    """
    _, door_max = catalog.door_bounds(kind)
    if door_max <= 0:
        raise MissingCraftData(
            f"families.{kind}.door_width_mm", needed_by="算一格能做几扇门"
        )
    if width_mm <= door_max:
        return 1
    if width_mm <= 2 * door_max:
        return 2
    return 0  # 两扇也不够：必须拆


def opening_style_for(space: SpaceRequest) -> str:
    """开门方式：客户/助手写在约束里（`opening=swing|sliding|lift`），默认平开。

    **代码不猜**——`sliding` / `lift` 今天还没有对应的分格口径，遇到了就停问。
    """
    for constraint in space.constraints:
        text = constraint.strip()
        if text.startswith("opening="):
            style = text.split("=", 1)[1].strip()
            if style not in OPENING_STYLES:
                raise ValueError(
                    "constraint opening must be one of: "
                    + ", ".join(sorted(OPENING_STYLES))
                )
            return style
    return "swing"


def functional_bays(space: SpaceRequest, catalog: CraftCatalog) -> tuple[str, ...]:
    """第 3 步：从约束推出功能格清单。

    功能格的**净宽下限**住在目录的 `bays` 里；目录没有这一项就停问——
    绝不按柜型替它编一个宽度。
    """
    requested = tuple(
        constraint.split("=", 1)[1].strip()
        for constraint in space.constraints
        if constraint.strip().startswith("bay=")
    )
    if not requested:
        return ()
    bays = catalog.raw.get("bays")
    if not isinstance(bays, dict) or not bays:
        raise MissingCraftData(
            "bays",
            needed_by=f"空间 {space.id} 要求的功能格（{'、'.join(requested)}）",
        )
    unknown = [name for name in requested if name not in bays]
    if unknown:
        raise MissingCraftData(
            f"bays.{unknown[0]}",
            needed_by=f"空间 {space.id} 要求的功能格",
            hint="references/craft-catalog.yaml 的 bays（现有："
            + "、".join(sorted(bays))
            + "）",
        )
    return requested


def split_requested(space: SpaceRequest) -> str:
    """拆分口径：`split=equal` 才按等分；没写就是"没有档位就不拆"（默认停问）。

    **这是口径选择，不是缺省值**：车间还没给标准单元宽档，代码不替它编档位，
    也不默认等分——客户/助手明说"先按等分给一版"才走这条路。
    """
    for constraint in space.constraints:
        text = constraint.strip()
        if text.startswith("split="):
            value = text.split("=", 1)[1].strip()
            if value != "equal":
                raise ValueError(f"constraint split must be equal: {constraint!r}")
            return value
    return ""


def split_space(
    space: SpaceRequest,
    catalog: CraftCatalog,
) -> SplitResult:
    """把一块空间解成 N 个单元。不可行或数据不全 → 抛错（停问）。"""
    style = opening_style_for(space)
    if style != "swing":
        raise MissingCraftData(
            f"families.{space.kind}.opening={style}",
            needed_by="推拉门 / 上翻门的单元宽度口径",
            hint="references/craft-catalog.yaml（今天只定了平开门口径）",
        )
    net = net_width_mm(space, catalog)
    bays = functional_bays(space, catalog)
    kind_entry = catalog.family(space.kind)
    depth = float(space.depth_mm or catalog.recommended_depth_mm(space.kind))
    origin_z = float(space.origin_z_mm)
    height = (
        float(space.height_mm)
        if space.height_mm is not None
        else catalog.envelope_height_mm(space.kind)
    )

    # 第 2 步：先定门 → 单元宽度上限。
    doors = door_count_for(net, catalog, space.kind)
    if doors == 0:
        _, door_max = catalog.door_bounds(space.kind)
        width_cap = 2 * door_max
        filler = filler_for(space, catalog)
        missing = catalog.missing_readiness_keys()
        if split_requested(space) != "equal":
            raise SpaceInfeasible(
                space.id,
                f"净宽 {net:g}（空间 {space.width_mm:g} − 收口 {filler:g}）"
                f"超过「两扇平开门」的上限 {width_cap:g}"
                + (
                    "，而目录还没有标准单元宽档（unit_widths_mm）/ "
                    "功能格最小净宽（bays），拆不出对齐档位的格"
                    if "unit_widths_mm" in missing or "bays" in missing
                    else "，需要拆成更多格"
                ),
                options=(
                    "把这块空间缩短到 %g 以内" % width_cap,
                    "在空间约束里写 split=equal，我按等分先给一版"
                    "（会标成助手假设：宽度还没和车间档位对齐）",
                    "等车间给标准单元宽档与功能格最小净宽后自动拆分",
                    "人工指定每一格的宽度（那属于钉住的单元）",
                ),
            )
        return _split_equally(space, catalog, net, kind_entry)

    notes = [
        f"净宽 {net:g} = 空间 {space.width_mm:g} − 收口 {filler_for(space, catalog):g}",
        f"{doors} 扇平开门（门扇上限 {catalog.door_bounds(space.kind)[1]:g}）",
    ]
    costs: list[str] = []
    if bays:
        notes.append("功能格：" + "、".join(bays))
    assumptions: list[str] = []
    if space.depth_mm is None:
        assumptions.append(f"进深取目录常规值 {depth:g}")
    if space.height_mm is None:
        assumptions.append(f"高度取 {height:g}")

    unit = SplitUnit(
        id=f"{space.id}_u1",
        seq=1,
        width_mm=net,
        depth_mm=depth,
        height_mm=height,
        origin_z_mm=origin_z,
        n_doors=doors,
        catalog_version=catalog.version,
    )
    door_min = catalog.door_bounds(space.kind)[0]
    per_door = net / doors
    if per_door < door_min:
        costs.append(
            f"每扇门只有 {per_door:.0f}，低于常规下限 {door_min:g}——"
            "要么把这排做窄些，要么按单扇门做"
        )
    return SplitResult(
        space_id=space.id,
        units=(unit,),
        catalog_version=catalog.version,
        notes=tuple(notes),
        costs=tuple(costs),
        assumptions=tuple(assumptions),
    )


def _split_equally(
    space: SpaceRequest,
    catalog: CraftCatalog,
    net: float,
    kind_entry: Mapping[str, Any],
) -> SplitResult:
    """按**等分**拆（只在空间明写 `split=equal` 时走这条）。

    为什么要有它：车间还没给标准单元宽档，代码不替它编档位；但客户可能就想要一版能看的
    方案。等分是**确定性**的（满足硬约束"每格 ≤ 两扇门上限"），但它**不是**车间要的档位——
    所以结果里必须带一条助手假设，提醒"宽度还没和车间档位对齐"。
    """
    _, door_max = catalog.door_bounds(space.kind)
    width_cap = 2 * door_max
    count = int(ceil(net / width_cap))
    if count < 1:
        count = 1
    base = int(net // count)
    widths = [float(base)] * count
    # 余量集中在**远端那一格**（设计稿 §四 第 5 步）。
    widths[-1] = net - base * (count - 1)
    depth = float(space.depth_mm or catalog.recommended_depth_mm(space.kind))
    height = (
        float(space.height_mm)
        if space.height_mm is not None
        else catalog.envelope_height_mm(space.kind)
    )
    door_min = catalog.door_bounds(space.kind)[0]
    units: list[SplitUnit] = []
    offset = float(space.offset_mm or 0.0)
    costs: list[str] = []
    for index, width in enumerate(widths, start=1):
        doors = door_count_for(width, catalog, space.kind)
        if doors == 0:
            raise SpaceInfeasible(
                space.id,
                f"等分出来的第 {index} 格 {width:g} 仍超过两扇门的上限 {width_cap:g}",
                options=("把这块空间缩短", "人工指定每一格的宽度"),
            )
        per_door = width / doors
        if per_door < door_min:
            costs.append(
                f"第 {index} 格每扇门 {per_door:.0f}，低于常规下限 {door_min:g}"
            )
        units.append(
            SplitUnit(
                id=f"{space.id}_u{index}",
                seq=index,
                width_mm=width,
                depth_mm=depth,
                height_mm=height,
                origin_z_mm=float(space.origin_z_mm),
                n_doors=doors,
                catalog_version=catalog.version,
            )
        )
        offset += width
    filler = filler_for(space, catalog)
    return SplitResult(
        space_id=space.id,
        units=tuple(units),
        catalog_version=catalog.version,
        notes=(
            f"净宽 {net:g} = 空间 {space.width_mm:g} − 收口 {filler:g}",
            f"按等分拆成 {count} 格："
            + "、".join(f"{width:g}" for width in widths),
            f"余量集中在远端那一格（第 {count} 格）",
        ),
        costs=tuple(costs),
        assumptions=(
            "目录还没有标准单元宽档，先按等分给——宽度还没和车间档位对齐",
        ),
    )


def split_envelopes(
    space: SpaceRequest,
    catalog: CraftCatalog,
) -> tuple[dict[str, object], tuple[str, ...], tuple[str, ...]]:
    """给布局入口用的一层：单元包络（进 `items[]`）+ 解释 + 代价提示。"""
    result = split_space(space, catalog)
    envelopes: list[dict[str, object]] = []
    for unit in result.units:
        placement: dict[str, object] = {"mode": space.mode}
        if space.mode == "wall":
            placement["host_wall"] = space.host_wall
            placement["offset_mm"] = float(space.offset_mm or 0.0)
        else:
            # 自由空间：单元落在空间自己的落脚点上（没有坐标就说不清在哪）。
            placement["origin_x_mm"] = float(space.origin_x_mm or 0.0)
            placement["origin_y_mm"] = float(space.origin_y_mm or 0.0)
        if unit.origin_z_mm:
            placement["origin_z_mm"] = unit.origin_z_mm
        envelopes.append(
            {
                "id": unit.id,
                "label": unit.id,
                "category": "柜体",
                "furniture_category": "floor_cabinet",
                "width": unit.width_mm,
                "depth": unit.depth_mm,
                "height": unit.height_mm,
                "placement": placement,
            }
        )
    return tuple(envelopes), result.notes, result.costs


def next_unit_index(existing_ids: list[str], space_id: str) -> int:
    """下一个可用序号：`{space_id}_u{n}`，**只增不改、不复用**（设计稿第三节）。

    插入一格不能让别的单元换 id；删掉的号也不回收。
    """
    prefix = f"{space_id}_u"
    used = []
    for existing in existing_ids:
        if existing.startswith(prefix):
            suffix = existing[len(prefix) :]
            if suffix.isdigit():
                used.append(int(suffix))
    return max(used, default=0) + 1


__all__ = [
    "SpaceInfeasible",
    "SplitResult",
    "SplitUnit",
    "door_count_for",
    "filler_for",
    "functional_bays",
    "net_width_mm",
    "next_unit_index",
    "opening_style_for",
    "split_envelopes",
    "split_space",
]
