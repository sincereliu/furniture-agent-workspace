"""Generate a dependency-free SVG floor-plan preview for stage 2."""

from __future__ import annotations

from html import escape
from math import cos, radians, sin

from .layout_planning import CabinetLayout
from .room_planning import RoomOpening, RoomPlacementPlan


PREVIEW_WIDTH_PX = 960
PREVIEW_HEIGHT_PX = 720
PREVIEW_MARGIN_PX = 92


def render_layout_preview(
    plan: RoomPlacementPlan,
    layout: CabinetLayout,
) -> dict[str, object]:
    room = plan.room
    drawing_width = PREVIEW_WIDTH_PX - 2 * PREVIEW_MARGIN_PX
    drawing_height = PREVIEW_HEIGHT_PX - 2 * PREVIEW_MARGIN_PX
    scale = min(
        drawing_width / room.width_mm,
        drawing_height / room.depth_mm,
    )
    room_width_px = room.width_mm * scale
    room_depth_px = room.depth_mm * scale
    left = (PREVIEW_WIDTH_PX - room_width_px) / 2
    top = (PREVIEW_HEIGHT_PX - room_depth_px) / 2

    def screen(point: tuple[float, float]) -> tuple[float, float]:
        return (
            left + point[0] * scale,
            top + (room.depth_mm - point[1]) * scale,
        )

    svg: list[str] = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{PREVIEW_WIDTH_PX}" height="{PREVIEW_HEIGHT_PX}" '
            f'viewBox="0 0 {PREVIEW_WIDTH_PX} {PREVIEW_HEIGHT_PX}" '
            f'role="img" aria-labelledby="title desc">'
        ),
        f"<title id=\"title\">{escape(room.name)}家具布局预览</title>",
        (
            f'<desc id="desc">{escape(plan.furniture_label)}位于'
            f'{escape(plan.placement.host_wall or "房间内")}，'
            f'原点 ({plan.placement.origin_x_mm:g}, '
            f'{plan.placement.origin_y_mm:g}, '
            f'{plan.placement.origin_z_mm:g}) 毫米。</desc>'
        ),
        "<defs>",
        (
            '<pattern id="grid" width="20" height="20" '
            'patternUnits="userSpaceOnUse">'
        ),
        '<path d="M 20 0 L 0 0 0 20" fill="none" stroke="#dbe4ee" stroke-width="1"/>',
        "</pattern>",
        (
            '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">'
            '<feDropShadow dx="0" dy="4" stdDeviation="5" '
            'flood-color="#0f172a" flood-opacity="0.18"/></filter>'
        ),
        "</defs>",
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        (
            f'<rect x="{left:.3f}" y="{top:.3f}" width="{room_width_px:.3f}" '
            f'height="{room_depth_px:.3f}" fill="url(#grid)" '
            'stroke="#0f172a" stroke-width="5"/>'
        ),
    ]

    for obstacle in room.obstacles:
        obstacle_left, obstacle_bottom = screen(
            (obstacle.x_mm, obstacle.y_mm + obstacle.depth_mm)
        )
        svg.extend(
            [
                (
                    f'<rect x="{obstacle_left:.3f}" y="{obstacle_bottom:.3f}" '
                    f'width="{obstacle.width_mm * scale:.3f}" '
                    f'height="{obstacle.depth_mm * scale:.3f}" '
                    'fill="#fecaca" stroke="#b91c1c" stroke-width="2"/>'
                ),
                (
                    f'<text x="{obstacle_left + 6:.3f}" '
                    f'y="{obstacle_bottom + 18:.3f}" '
                    'font-family="sans-serif" font-size="13" fill="#7f1d1d">'
                    f'{escape(obstacle.kind)}</text>'
                ),
            ]
        )

    for opening in room.openings:
        start, end = _opening_segment(room.width_mm, room.depth_mm, opening)
        start_x, start_y = screen(start)
        end_x, end_y = screen(end)
        svg.append(
            (
                f'<line x1="{start_x:.3f}" y1="{start_y:.3f}" '
                f'x2="{end_x:.3f}" y2="{end_y:.3f}" '
                'stroke="#06b6d4" stroke-width="10" stroke-linecap="butt"/>'
            )
        )

    footprint_points = [screen(point) for point in plan.furniture_footprint]
    point_text = " ".join(f"{x:.3f},{y:.3f}" for x, y in footprint_points)
    svg.append(
        (
            f'<polygon points="{point_text}" fill="#2563eb" fill-opacity="0.78" '
            'stroke="#1e3a8a" stroke-width="3" filter="url(#shadow)"/>'
        )
    )

    centroid_x = sum(point[0] for point in footprint_points) / 4
    centroid_y = sum(point[1] for point in footprint_points) / 4
    svg.extend(
        [
            (
                f'<text x="{centroid_x:.3f}" y="{centroid_y - 5:.3f}" '
                'text-anchor="middle" font-family="sans-serif" '
                'font-size="18" font-weight="700" fill="white">'
                f'{escape(plan.furniture_label)}</text>'
            ),
            (
                f'<text x="{centroid_x:.3f}" y="{centroid_y + 18:.3f}" '
                'text-anchor="middle" font-family="sans-serif" '
                'font-size="13" fill="#dbeafe">'
                f'{layout.width:g} × {layout.depth:g} mm</text>'
            ),
        ]
    )

    angle = radians(plan.placement.rotation_z_deg)
    front_dx = -sin(angle)
    front_dy = cos(angle)
    arrow_length = min(54.0, max(28.0, layout.depth * scale * 0.45))
    arrow_end_x = centroid_x + front_dx * arrow_length
    arrow_end_y = centroid_y - front_dy * arrow_length
    svg.extend(
        [
            (
                f'<line x1="{centroid_x:.3f}" y1="{centroid_y:.3f}" '
                f'x2="{arrow_end_x:.3f}" y2="{arrow_end_y:.3f}" '
                'stroke="white" stroke-width="3"/>'
            ),
            (
                f'<circle cx="{arrow_end_x:.3f}" cy="{arrow_end_y:.3f}" '
                'r="5" fill="white"/>'
            ),
        ]
    )

    svg.extend(
        [
            (
                f'<text x="{left:.3f}" y="{top - 34:.3f}" '
                'font-family="sans-serif" font-size="24" font-weight="700" '
                f'fill="#0f172a">{escape(room.name)}</text>'
            ),
            (
                f'<text x="{left:.3f}" y="{top - 10:.3f}" '
                'font-family="sans-serif" font-size="14" fill="#475569">'
                f'{room.width_mm:g} × {room.depth_mm:g} × '
                f'{room.height_mm:g} mm · 蓝色为家具 · 红色为障碍物 · 青色为门窗'
                "</text>"
            ),
            (
                f'<text x="{left + room_width_px + 22:.3f}" '
                f'y="{top + 18:.3f}" font-family="sans-serif" '
                'font-size="14" font-weight="700" fill="#0f172a">N ↑</text>'
            ),
            (
                f'<text x="{left:.3f}" y="{top + room_depth_px + 34:.3f}" '
                'font-family="sans-serif" font-size="14" fill="#334155">'
                f'位置：{escape(plan.placement.host_wall or "自由摆放")} · '
                f'旋转 {plan.placement.rotation_z_deg:g}° · '
                f'标高 {plan.placement.origin_z_mm:g} mm</text>'
            ),
            "</svg>",
        ]
    )
    return {
        "media_type": "image/svg+xml",
        "width_px": PREVIEW_WIDTH_PX,
        "height_px": PREVIEW_HEIGHT_PX,
        "alt_text": (
            f"{plan.furniture_label}在{room.name}中的平面位置："
            f"原点 ({plan.placement.origin_x_mm:g}, "
            f"{plan.placement.origin_y_mm:g}, "
            f"{plan.placement.origin_z_mm:g}) mm，"
            f"旋转 {plan.placement.rotation_z_deg:g}°"
        ),
        "svg": "".join(svg),
    }


def _opening_segment(
    room_width: float,
    room_depth: float,
    opening: RoomOpening,
) -> tuple[tuple[float, float], tuple[float, float]]:
    start = opening.offset_mm
    end = opening.offset_mm + opening.width_mm
    return {
        "south": ((start, 0.0), (end, 0.0)),
        "east": ((room_width, start), (room_width, end)),
        "north": (
            (room_width - start, room_depth),
            (room_width - end, room_depth),
        ),
        "west": (
            (0.0, room_depth - start),
            (0.0, room_depth - end),
        ),
    }.get(opening.wall, ((0.0, 0.0), (0.0, 0.0)))
