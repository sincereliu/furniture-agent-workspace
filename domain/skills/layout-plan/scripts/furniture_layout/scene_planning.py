"""Shared room planning: parse requests, place envelopes, admit geometry."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from .craft_catalog import CraftCatalog, MissingCraftData, load_craft_catalog
from .placement import place_items
from .scene import RoomModel, RoomScene, SpaceRequest, parse_item_specs, parse_space_requests
from .space_split import SpaceInfeasible, split_envelopes
from .validation import raise_unless_admitted


def plan_scene(
    room: Mapping[str, Any],
    items: list[Mapping[str, Any]],
    *,
    allow_empty: bool = False,
    craft_catalog: CraftCatalog | None = None,
) -> RoomScene:
    """规划一间房：**先展开空间，再摆放**。

    `rooms[].spaces[]` 是可选的输入侧来源（见 references/space-split-design.md）：
    每个空间由确定性求解器展开成若干单元包络，与显式给的 `items` 一起进摆放与校验。
    没有 `spaces` 时行为与以前**逐字节相同**（连目录都不读）。
    """
    room_model = RoomModel.from_dict(room)
    spaces = parse_space_requests(room.get("spaces"))
    # **谁说话算数**（设计稿 §十一）：
    #   钉住的单元 → 客户自己定的，照原样留着（它就是"这一台别动"）；
    #   没钉住的单元 → 由空间**重新解**出来，源里那份旧解丢掉（空间改了才重解得动）；
    #   与空间无关的显式件 → 原样留着。
    pinned_ids = {unit for space in spaces for unit in space.pinned}
    derived_ids = {f"{space.id}_u" for space in spaces}
    kept = [
        item
        for item in items
        if not any(str(item.get("id") or "").startswith(prefix) for prefix in derived_ids)
        or str(item.get("id") or "") in pinned_ids
    ]
    expanded: list[Mapping[str, Any]] = []
    if spaces:
        catalog = craft_catalog or load_craft_catalog()
        pinned_present = {
            str(item.get("id") or "") for item in kept if isinstance(item, Mapping)
        }
        for space in spaces:
            envelopes, _, _ = split_envelopes(space, catalog)
            expanded.extend(
                envelope
                for envelope in envelopes
                if str(envelope.get("id") or "") not in pinned_present
            )
    specs = parse_item_specs([*kept, *expanded], allow_empty=allow_empty)
    placed = place_items(room_model, specs)
    if any(item.placement.fill for item in placed):
        # **沿墙铺满走求解器**：老路子会给一个"3000 宽"的包络，那是做不出来的柜子
        # （板件阶段两扇门的上限是 900）。现在铺满也按工艺目录展开成合规单元；
        # 目录还缺档位时**停问**，并指出两条路（缩小空间 / 改用 spaces[] 走等分）。
        catalog = craft_catalog or load_craft_catalog()
        placed = _expand_fill_units(room_model, placed, catalog)
    scene = RoomScene(room=room_model, items=placed, spaces=spaces)
    raise_unless_admitted(scene)
    return scene


def _expand_fill_units(
    room: RoomModel, placed: tuple[Any, ...], catalog: CraftCatalog
) -> tuple[Any, ...]:
    """把 `fill: true` 的件换成"按目录展开出来的一组合规单元"。"""
    output: list[Any] = []
    for item in placed:
        if not item.placement.fill:
            output.append(item)
            continue
        if not item.kind:
            raise ValueError(
                f"这件沿墙铺满的 {item.id!r} 没说要做什么柜：在它上面写 kind"
                "（柜类，取 references/craft-catalog.yaml 的 families，"
                "例如 kitchen_base / wardrobe / sideboard）——"
                "铺满也要按目录展开成合规单元，代码不替它猜柜类。"
            )
        space = SpaceRequest(
            id=item.id,
            kind=item.kind,
            mode="wall",
            width_mm=float(item.width),
            host_wall=item.placement.host_wall,
            offset_mm=float(item.placement.offset_mm or 0.0),
            depth_mm=float(item.depth),
            height_mm=float(item.height),
            origin_z_mm=float(item.placement.origin_z_mm),
        )
        try:
            envelopes, _, _ = split_envelopes(space, catalog)
        except SpaceInfeasible as exc:
            raise SpaceInfeasible(
                exc.space_id,
                str(exc).split("：", 1)[-1],
                options=(
                    *exc.options,
                    f"或者把这一件写成 rooms[].spaces[]（id: {item.id}，kind: {item.kind}，"
                    "constraints: [split=equal]）——那才能显式走等分",
                ),
            ) from exc
        specs = parse_item_specs(list(envelopes), allow_empty=False)
        if not item.manufacture:
            # "这件不用做"要跟着单元走，否则铺满一展开就变成"都要做"。
            specs = tuple(
                replace(spec, manufacture=False) for spec in specs
            )
        output.extend(place_items(room, specs))
    return tuple(output)
