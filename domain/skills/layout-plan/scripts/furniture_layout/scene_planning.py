"""Shared room planning: parse requests, place envelopes, admit geometry."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from .craft_catalog import CraftCatalog, load_craft_catalog
from .placement import place_items
from .scene import RoomModel, RoomScene, parse_item_specs
from .space_split import unit_widths
from .validation import raise_unless_admitted


def plan_scene(
    room: Mapping[str, Any],
    items: list[Mapping[str, Any]],
    *,
    allow_empty: bool = False,
    craft_catalog: CraftCatalog | None = None,
) -> RoomScene:
    """规划一间房：摆放，再把沿墙铺满拆成若干台。

    没有 `fill` 的输入不读工艺目录。铺满的墙按该柜类的门宽上限拆开，
    放得进一台就是一台，放不下就沿墙接成几台，宽度加起来等于这段空墙。
    """
    room_model = RoomModel.from_dict(room)
    specs = parse_item_specs(items, allow_empty=allow_empty)
    placed = place_items(room_model, specs)
    if any(item.placement.fill for item in placed):
        catalog = craft_catalog or load_craft_catalog()
        placed = _expand_fill_units(room_model, placed, catalog)
    scene = RoomScene(room=room_model, items=placed)
    raise_unless_admitted(scene)
    return scene


def _expand_fill_units(
    room: RoomModel, placed: tuple[Any, ...], catalog: CraftCatalog
) -> tuple[Any, ...]:
    """把 `fill: true` 的一件换成沿这段墙接开的若干台。"""
    output: list[Any] = []
    for item in placed:
        if not item.placement.fill:
            output.append(item)
            continue
        if not item.kind:
            raise ValueError(
                f"这件沿墙铺满的 {item.id!r} 没说要做什么柜：在它上面写 kind"
                "（柜类，取 references/craft-catalog.yaml 的 families，"
                "例如 kitchen_base / wardrobe / sideboard）。"
            )
        cap = 2 * catalog.door_bounds(item.kind)[1]
        widths = unit_widths(float(item.width), cap)
        offset = float(item.placement.offset_mm or 0.0)
        envelopes: list[dict[str, object]] = []
        for index, width in enumerate(widths, start=1):
            placement: dict[str, object] = {
                "mode": "wall",
                "host_wall": item.placement.host_wall,
                "offset_mm": offset,
            }
            if item.placement.origin_z_mm:
                placement["origin_z_mm"] = item.placement.origin_z_mm
            unit_id = f"{item.id}_u{index}"
            envelope: dict[str, object] = {
                "id": unit_id,
                "label": item.label if len(widths) == 1 else f"{item.label} {index}",
                "category": item.category,
                "width": width,
                "depth": item.depth,
                "height": item.height,
                "placement": placement,
            }
            if item.furniture_category:
                envelope["furniture_category"] = item.furniture_category
            envelopes.append(envelope)
            offset += width
        specs = parse_item_specs(envelopes, allow_empty=False)
        if not item.manufacture:
            specs = tuple(replace(spec, manufacture=False) for spec in specs)
        output.extend(place_items(room, specs))
    return tuple(output)
