"""Turn a confirmed cabinet layout into physical panel placements."""

from __future__ import annotations

from furniture_design_intent.design_spec import (
    FurnitureSpec,
    resolve_toe_kick_support_count,
)
from furniture_layout.layout_planning import CabinetLayout

from .panel_models import PanelPlacement


def build_cabinet_panels(
    spec: FurnitureSpec,
    layout: CabinetLayout,
) -> list[PanelPlacement]:
    board = spec.board_thickness
    panels: list[PanelPlacement] = []

    panels.extend(
        [
            PanelPlacement(
                id="left_side_panel",
                name="左侧板",
                panel_type="side",
                size_x=board,
                size_y=layout.side_depth,
                size_z=layout.height,
                pos_y=layout.carcass_y_start,
                material_role="carcass",
                note=f"侧板，深{layout.side_depth:.0f}×高{layout.height:.0f}×厚{board:.0f}mm",
            ),
            PanelPlacement(
                id="right_side_panel",
                name="右侧板",
                panel_type="side",
                size_x=board,
                size_y=layout.side_depth,
                size_z=layout.height,
                pos_x=layout.width - board,
                pos_y=layout.carcass_y_start,
                material_role="carcass",
                depends_on=["left_side_panel"],
                note=f"侧板，深{layout.side_depth:.0f}×高{layout.height:.0f}×厚{board:.0f}mm",
            ),
            PanelPlacement(
                id="top_panel",
                name="顶板",
                panel_type="top",
                size_x=layout.internal_width,
                size_y=layout.side_depth,
                size_z=board,
                pos_x=layout.internal_x_start,
                pos_y=layout.carcass_y_start,
                pos_z=layout.height - board,
                material_role="carcass",
                depends_on=["left_side_panel", "right_side_panel"],
                note="夹在左右侧板之间",
            ),
            PanelPlacement(
                id="bottom_panel",
                name="底板",
                panel_type="bottom",
                size_x=layout.internal_width,
                size_y=layout.side_depth,
                size_z=board,
                pos_x=layout.internal_x_start,
                pos_y=layout.carcass_y_start,
                pos_z=layout.toe_kick_height,
                material_role="carcass",
                depends_on=["left_side_panel", "right_side_panel"],
                note="位于踢脚区域上方",
            ),
        ]
    )

    back_mount = layout.back_mount

    if back_mount == "groove":
        groove_depth = spec.groove_depth
        back_width = layout.internal_width + 2 * groove_depth
        back_height = layout.internal_height + 2 * groove_depth
        panels.append(
            PanelPlacement(
                id="back_panel",
                name="背板",
                panel_type="back",
                size_x=back_width,
                size_y=spec.back_thickness,
                size_z=back_height,
                pos_x=layout.internal_x_start - groove_depth,
                pos_y=layout.back_plane_y,
                pos_z=layout.internal_z_start - groove_depth,
                material_role="back",
                depends_on=[
                    "left_side_panel",
                    "right_side_panel",
                    "top_panel",
                    "bottom_panel",
                ],
                note=f"四边入槽{groove_depth:.0f}mm的成品背板",
            )
        )
        # back rails for groove-mounted back panels
        rail_h = spec.back_rail_height
        rail_count = int(layout.internal_height // 500)
        if rail_h > 0 and rail_count > 0:
            step = (layout.internal_height - rail_count * rail_h) / rail_count
            for i in range(rail_count):
                rail_z = layout.internal_z_start + step + i * (rail_h + step)
                panels.append(
                    PanelPlacement(
                        id=f"back_rail_{i + 1}",
                        name=f"背拉条{i + 1}",
                        panel_type="back_rail",
                        size_x=layout.internal_width,
                        size_y=board,
                        size_z=rail_h,
                        pos_x=layout.internal_x_start,
                        pos_y=layout.carcass_y_start,
                        pos_z=rail_z,
                        material_role="carcass",
                        depends_on=["left_side_panel", "right_side_panel"],
                        note=f"背板拉条，{rail_h:.0f}×{board:.0f}mm",
                    )
                )
    elif back_mount == "insert":
        panels.append(
            PanelPlacement(
                id="back_panel",
                name="背板",
                panel_type="back",
                size_x=layout.internal_width,
                size_y=spec.back_thickness,
                size_z=layout.internal_height,
                pos_x=layout.internal_x_start,
                pos_y=layout.back_plane_y,
                pos_z=layout.internal_z_start,
                material_role="back",
                depends_on=[
                    "left_side_panel",
                    "right_side_panel",
                    "top_panel",
                    "bottom_panel",
                ],
                note="内嵌背板，三合一连接",
            )
        )
    else:  # cover
        panels.append(
            PanelPlacement(
                id="back_panel",
                name="背板",
                panel_type="back",
                size_x=layout.width,
                size_y=spec.back_thickness,
                size_z=layout.height,
                pos_x=0.0,
                pos_y=0.0,
                pos_z=0.0,
                material_role="back",
                depends_on=[
                    "left_side_panel",
                    "right_side_panel",
                    "top_panel",
                    "bottom_panel",
                ],
                note="外盖背板，覆盖整个背面",
            )
        )

    if layout.toe_kick_height > 0:
        panels.extend(_toe_kick_panels(spec, layout))

    if layout.shelf_count > 0:
        layer_height = layout.internal_height / (layout.shelf_count + 1)
        shelf_depth = layout.internal_y_end - layout.internal_y_start
        for index in range(1, layout.shelf_count + 1):
            center_z = layout.internal_z_start + index * layer_height - board / 2
            panels.append(
                PanelPlacement(
                    id=f"shelf_z{center_z:.0f}",
                    name=f"层板({center_z:.0f}mm)",
                    panel_type="fixed_shelf",
                    size_x=layout.internal_width,
                    size_y=shelf_depth,
                    size_z=board,
                    pos_x=layout.internal_x_start,
                    pos_y=layout.internal_y_start,
                    pos_z=center_z - board / 2,
                    material_role="carcass",
                    depends_on=["left_side_panel", "right_side_panel"],
                    note="固定层板",
                )
            )

    panels.extend(_door_panels(spec, layout))
    return panels


def _toe_kick_panels(
    spec: FurnitureSpec,
    layout: CabinetLayout,
) -> list[PanelPlacement]:
    board = spec.board_thickness
    kick_width = layout.internal_width
    x = layout.internal_x_start
    rear = PanelPlacement(
        id="toe_kick_back",
        name="后踢脚板",
        panel_type="toe_kick",
        size_x=kick_width,
        size_y=board,
        size_z=layout.toe_kick_height,
        pos_x=x,
        pos_y=layout.toe_kick_rear_y,
        material_role="carcass",
        depends_on=["left_side_panel", "right_side_panel"],
    )
    front = PanelPlacement(
        id="toe_kick_front",
        name="前踢脚板",
        panel_type="toe_kick",
        size_x=kick_width,
        size_y=board,
        size_z=layout.toe_kick_height,
        pos_x=x,
        pos_y=layout.toe_kick_front_y - board,
        material_role="carcass",
        depends_on=["left_side_panel", "right_side_panel"],
    )
    panels = [rear, front]

    count = resolve_toe_kick_support_count(
        spec.toe_kick_support_count,
        layout.width,
    )
    if count == 0:
        return panels

    support_y = layout.toe_kick_rear_y + board
    support_depth = layout.toe_kick_front_y - board - support_y
    clear_gap = (kick_width - count * board) / (count + 1)
    for index in range(count):
        panels.append(
            PanelPlacement(
                id=f"toe_kick_support_{index + 1}",
                name=f"踢脚支撑{index + 1}",
                panel_type="toe_kick",
                size_x=board,
                size_y=support_depth,
                size_z=layout.toe_kick_height,
                pos_x=x + clear_gap + index * (board + clear_gap),
                pos_y=support_y,
                material_role="carcass",
                depends_on=["toe_kick_back", "toe_kick_front"],
            )
        )
    return panels


def _door_panels(
    spec: FurnitureSpec,
    layout: CabinetLayout,
) -> list[PanelPlacement]:
    count = layout.door_count
    if count <= 0:
        return []
    margin = spec.door_margin
    door_width = (layout.width - margin * 2 * count) / count
    door_height = layout.height - layout.toe_kick_height - margin * 2
    door_y = layout.carcass_y_end + spec.door_hinge_gap
    panels: list[PanelPlacement] = []
    for index in range(count):
        if count == 1:
            panel_id = "single_door"
            name = "门板"
            x = layout.width / 2 - door_width / 2
        elif count == 2:
            panel_id = "left_door" if index == 0 else "right_door"
            name = "左门板" if index == 0 else "右门板"
            x = margin if index == 0 else layout.width - margin - door_width
        else:
            panel_id = f"door_{index + 1}_door"
            name = f"门板{index + 1}"
            x = margin * (2 * (index + 1) - 1) + door_width * index
        panels.append(
            PanelPlacement(
                id=panel_id,
                name=name,
                panel_type="door",
                size_x=door_width,
                size_y=spec.door_thickness,
                size_z=door_height,
                pos_x=x,
                pos_y=door_y,
                pos_z=layout.toe_kick_height + margin,
                material_role="door",
                depends_on=["left_side_panel", "right_side_panel"],
                note=f"门板，{door_width:.0f}×{door_height:.0f}×{spec.door_thickness:.0f}mm",
            )
        )
    return panels

