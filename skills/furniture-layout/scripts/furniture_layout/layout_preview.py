"""Generate a dependency-free SVG 3D envelope preview for stage 2."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from math import radians, sqrt, tan
from typing import Iterable

from .layout_planning import CabinetLayout
from .room_planning import RoomOpening, RoomPlacementPlan


PREVIEW_WIDTH_PX = 960
PREVIEW_HEIGHT_PX = 720
DRAWING_LEFT_PX = 76
DRAWING_RIGHT_PX = 884
DRAWING_TOP_PX = 118
DRAWING_BOTTOM_PX = 590

Point3D = tuple[float, float, float]
Point2D = tuple[float, float]
Vector3D = tuple[float, float, float]


@dataclass(frozen=True)
class PerspectiveProjector:
    camera: Point3D
    right: Vector3D
    up: Vector3D
    forward: Vector3D
    focal_length: float
    scale: float
    offset_x: float
    offset_y: float

    def camera_coordinates(self, point: Point3D) -> Point3D:
        relative = _subtract(point, self.camera)
        return (
            _dot(relative, self.right),
            _dot(relative, self.up),
            _dot(relative, self.forward),
        )

    def depth(self, point: Point3D) -> float:
        return self.camera_coordinates(point)[2]

    def raw(self, point: Point3D) -> Point2D:
        camera_x, camera_y, depth = self.camera_coordinates(point)
        if depth <= 1e-6:
            raise ValueError("preview point is behind the perspective camera")
        return (
            self.focal_length * camera_x / depth,
            -self.focal_length * camera_y / depth,
        )

    def __call__(self, point: Point3D) -> Point2D:
        raw_x, raw_y = self.raw(point)
        return (
            self.offset_x + raw_x * self.scale,
            self.offset_y + raw_y * self.scale,
        )


def render_layout_preview(
    plan: RoomPlacementPlan,
    layout: CabinetLayout,
) -> dict[str, object]:
    """Render a transparent room volume and opaque furniture envelope."""
    room = plan.room
    project = _build_projector(
        room.width_mm,
        room.depth_mm,
        room.height_mm,
    )
    room_corners = _room_corners(
        room.width_mm,
        room.depth_mm,
        room.height_mm,
    )

    svg: list[str] = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{PREVIEW_WIDTH_PX}" height="{PREVIEW_HEIGHT_PX}" '
            f'viewBox="0 0 {PREVIEW_WIDTH_PX} {PREVIEW_HEIGHT_PX}" '
            f'role="img" aria-labelledby="title desc">'
        ),
        (
            f'<title id="title">{escape(room.name)}家具透视三维包络预览'
            "</title>"
        ),
        (
            f'<desc id="desc">{escape(plan.furniture_label)}在'
            f'{escape(room.name)}中的透视三维占位；房间为透明包络，'
            "蓝色不透明长方体为家具成品包络。</desc>"
        ),
        "<defs>",
        (
            '<linearGradient id="room-floor" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0%" stop-color="#e2e8f0" stop-opacity="0.18"/>'
            '<stop offset="100%" stop-color="#cbd5e1" stop-opacity="0.34"/>'
            "</linearGradient>"
        ),
        (
            '<linearGradient id="furniture-top" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0%" stop-color="#93c5fd"/>'
            '<stop offset="100%" stop-color="#3b82f6"/>'
            "</linearGradient>"
        ),
        (
            '<filter id="solid-shadow" x="-30%" y="-30%" '
            'width="170%" height="180%">'
            '<feDropShadow dx="0" dy="8" stdDeviation="8" '
            'flood-color="#0f172a" flood-opacity="0.28"/>'
            "</filter>"
        ),
        "</defs>",
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        (
            '<text x="76" y="48" font-family="sans-serif" font-size="25" '
            f'font-weight="700" fill="#0f172a">{escape(room.name)}</text>'
        ),
        (
            '<text x="76" y="74" font-family="sans-serif" font-size="14" '
            f'fill="#475569">{room.width_mm:g} × {room.depth_mm:g} × '
            f'{room.height_mm:g} mm · 透明为房间 · 蓝色为家具包络'
            " · 红色为障碍物 · 青色为门窗</text>"
        ),
    ]

    _append_room_background(svg, room_corners, project)

    for opening in room.openings:
        points = _opening_face(
            room.width_mm,
            room.depth_mm,
            opening,
        )
        svg.extend(
            [
                _polygon(
                    points,
                    project,
                    fill="#22d3ee",
                    fill_opacity=0.42,
                    stroke="#0891b2",
                    stroke_width=2.0,
                ),
                _face_label(
                    points,
                    project,
                    opening.kind,
                    color="#155e75",
                ),
            ]
        )

    # Draw the transparent room wireframe before solid envelopes so furniture
    # correctly occludes room edges that pass behind it.
    _append_room_foreground(svg, room_corners, project)

    obstacle_boxes: list[tuple[float, list[str]]] = []
    for obstacle in room.obstacles:
        obstacle_footprint = (
            (obstacle.x_mm, obstacle.y_mm),
            (obstacle.x_mm + obstacle.width_mm, obstacle.y_mm),
            (
                obstacle.x_mm + obstacle.width_mm,
                obstacle.y_mm + obstacle.depth_mm,
            ),
            (obstacle.x_mm, obstacle.y_mm + obstacle.depth_mm),
        )
        obstacle_svg, sort_depth = _render_solid_box(
            footprint=obstacle_footprint,
            z_start=obstacle.z_mm,
            z_end=obstacle.z_mm + obstacle.height_mm,
            project=project,
            side_colors=("#dc2626", "#ef4444", "#b91c1c", "#f87171"),
            top_fill="#fca5a5",
            stroke="#991b1b",
            label=obstacle.kind,
            label_color="#7f1d1d",
            shadow=False,
        )
        obstacle_boxes.append((sort_depth, obstacle_svg))

    furniture_svg, furniture_sort_depth = _render_solid_box(
        footprint=plan.furniture_footprint,
        z_start=plan.placement.origin_z_mm,
        z_end=plan.placement.origin_z_mm + layout.height,
        project=project,
        side_colors=("#1d4ed8", "#2563eb", "#1e40af", "#3b82f6"),
        top_fill="url(#furniture-top)",
        stroke="#1e3a8a",
        label=plan.furniture_label,
        label_color="white",
        shadow=True,
    )

    solid_boxes = obstacle_boxes + [
        (furniture_sort_depth, furniture_svg)
    ]
    for _, box_svg in sorted(
        solid_boxes,
        key=lambda item: item[0],
        reverse=True,
    ):
        svg.extend(box_svg)

    _append_axis_indicator(svg)

    placement_label = _placement_label(plan)
    svg.extend(
        [
            (
                '<rect x="76" y="620" width="808" height="66" rx="12" '
                'fill="white" stroke="#dbe4ee"/>'
            ),
            (
                '<text x="94" y="646" font-family="sans-serif" '
                'font-size="14" font-weight="700" fill="#0f172a">'
                f'{escape(plan.furniture_label)} · '
                f'{layout.width:g} × {layout.depth:g} × {layout.height:g} mm'
                "</text>"
            ),
            (
                '<text x="94" y="671" font-family="sans-serif" '
                'font-size="13" fill="#475569">'
                f'{escape(placement_label)} · '
                f'原点 ({plan.placement.origin_x_mm:g}, '
                f'{plan.placement.origin_y_mm:g}, '
                f'{plan.placement.origin_z_mm:g}) mm'
                "</text>"
            ),
            "</svg>",
        ]
    )
    return {
        "media_type": "image/svg+xml",
        "view_kind": "perspective_envelope",
        "width_px": PREVIEW_WIDTH_PX,
        "height_px": PREVIEW_HEIGHT_PX,
        "alt_text": (
            f"{plan.furniture_label}在{room.name}中的透视三维包络位置："
            f"房间透明，家具为不透明长方体；原点 "
            f"({plan.placement.origin_x_mm:g}, "
            f"{plan.placement.origin_y_mm:g}, "
            f"{plan.placement.origin_z_mm:g}) mm，"
            f"旋转 {plan.placement.rotation_z_deg:g}°"
        ),
        "svg": "".join(svg),
    }


def _build_projector(
    room_width: float,
    room_depth: float,
    room_height: float,
) -> PerspectiveProjector:
    """Fit a true perspective camera view into the fixed SVG viewport."""
    camera = (
        room_width * 1.20,
        -room_depth * 0.72,
        room_height * 1.18,
    )
    target = (
        room_width * 0.48,
        room_depth * 0.52,
        room_height * 0.38,
    )
    forward = _normalize(_subtract(target, camera))
    right = _normalize(_cross(forward, (0.0, 0.0, 1.0)))
    up = _normalize(_cross(right, forward))
    prototype = PerspectiveProjector(
        camera=camera,
        right=right,
        up=up,
        forward=forward,
        focal_length=1.0 / tan(radians(50.0) / 2.0),
        scale=1.0,
        offset_x=0.0,
        offset_y=0.0,
    )
    raw_points = [
        prototype.raw(point)
        for point in _room_corners(room_width, room_depth, room_height)
    ]
    min_x = min(point[0] for point in raw_points)
    max_x = max(point[0] for point in raw_points)
    min_y = min(point[1] for point in raw_points)
    max_y = max(point[1] for point in raw_points)
    raw_width = max(max_x - min_x, 1.0)
    raw_height = max(max_y - min_y, 1.0)
    scale = min(
        (DRAWING_RIGHT_PX - DRAWING_LEFT_PX) / raw_width,
        (DRAWING_BOTTOM_PX - DRAWING_TOP_PX) / raw_height,
    )
    raw_center_x = (min_x + max_x) / 2.0
    raw_center_y = (min_y + max_y) / 2.0
    return PerspectiveProjector(
        camera=camera,
        right=right,
        up=up,
        forward=forward,
        focal_length=prototype.focal_length,
        scale=scale,
        offset_x=(DRAWING_LEFT_PX + DRAWING_RIGHT_PX) / 2.0
        - raw_center_x * scale,
        offset_y=(DRAWING_TOP_PX + DRAWING_BOTTOM_PX) / 2.0
        - raw_center_y * scale,
    )


def _room_corners(
    width: float,
    depth: float,
    height: float,
) -> tuple[Point3D, ...]:
    return (
        (0.0, 0.0, 0.0),
        (width, 0.0, 0.0),
        (width, depth, 0.0),
        (0.0, depth, 0.0),
        (0.0, 0.0, height),
        (width, 0.0, height),
        (width, depth, height),
        (0.0, depth, height),
    )


def _append_room_background(
    svg: list[str],
    corners: tuple[Point3D, ...],
    project: PerspectiveProjector,
) -> None:
    bottom = corners[:4]
    top = corners[4:]
    svg.extend(
        [
            _polygon(
                bottom,
                project,
                fill="url(#room-floor)",
                stroke="#94a3b8",
                stroke_width=1.4,
            ),
            _polygon(
                (bottom[2], bottom[3], top[3], top[2]),
                project,
                fill="#bae6fd",
                fill_opacity=0.11,
                stroke="#94a3b8",
                stroke_width=1.2,
            ),
            _polygon(
                (bottom[1], bottom[2], top[2], top[1]),
                project,
                fill="#cbd5e1",
                fill_opacity=0.10,
                stroke="#94a3b8",
                stroke_width=1.2,
            ),
            _polygon(
                top,
                project,
                fill="#e0f2fe",
                fill_opacity=0.04,
                stroke="#94a3b8",
                stroke_width=1.2,
                stroke_dasharray="7 6",
            ),
        ]
    )


def _append_room_foreground(
    svg: list[str],
    corners: tuple[Point3D, ...],
    project: PerspectiveProjector,
) -> None:
    edge_pairs = (
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    )
    for start_index, end_index in edge_pairs:
        start = project(corners[start_index])
        end = project(corners[end_index])
        hidden = (start_index, end_index) in {
            (2, 3),
            (6, 7),
            (2, 6),
            (3, 7),
        }
        svg.append(
            (
                f'<line x1="{start[0]:.3f}" y1="{start[1]:.3f}" '
                f'x2="{end[0]:.3f}" y2="{end[1]:.3f}" '
                'stroke="#475569" '
                f'stroke-width="{1.4 if hidden else 2.2}" '
                f'stroke-opacity="{0.55 if hidden else 0.82}"'
                f'{" stroke-dasharray=\"7 6\"" if hidden else ""}/>'
            )
        )


def _render_solid_box(
    *,
    footprint: Iterable[tuple[float, float]],
    z_start: float,
    z_end: float,
    project: PerspectiveProjector,
    side_colors: tuple[str, str, str, str],
    top_fill: str,
    stroke: str,
    label: str,
    label_color: str,
    shadow: bool,
) -> tuple[list[str], float]:
    base = tuple((x, y, z_start) for x, y in footprint)
    top = tuple((x, y, z_end) for x, y in footprint)
    if len(base) != 4:
        raise ValueError("solid box footprint must contain four points")

    faces: list[
        tuple[float, tuple[Point3D, ...], str, float, str]
    ] = []
    for index in range(4):
        next_index = (index + 1) % 4
        face = (
            base[index],
            base[next_index],
            top[next_index],
            top[index],
        )
        if _face_visible(face, project.camera):
            average_depth = sum(project.depth(point) for point in face) / 4.0
            faces.append(
                (average_depth, face, side_colors[index], 2.2, "")
            )

    if _face_visible(top, project.camera):
        top_attributes = ' filter="url(#solid-shadow)"' if shadow else ""
        faces.append(
            (
                sum(project.depth(point) for point in top) / 4.0,
                top,
                top_fill,
                2.4,
                top_attributes,
            )
        )

    rendered: list[str] = []
    for _, face, fill, stroke_width, extra_attributes in sorted(
        faces,
        key=lambda item: item[0],
        reverse=True,
    ):
        rendered.append(
            _polygon(
                face,
                project,
                fill=fill,
                stroke=stroke,
                stroke_width=stroke_width,
                extra_attributes=extra_attributes,
            )
        )

    label_point = project(
        (
            sum(point[0] for point in top) / 4.0,
            sum(point[1] for point in top) / 4.0,
            (z_start + z_end) / 2.0,
        )
    )
    rendered.extend(
        [
            (
                f'<text x="{label_point[0]:.3f}" y="{label_point[1]:.3f}" '
                'text-anchor="middle" dominant-baseline="middle" '
                'font-family="sans-serif" font-size="16" font-weight="700" '
                f'fill="{label_color}" paint-order="stroke" '
                f'stroke="{stroke}" stroke-width="0.8">'
                f"{escape(label)}</text>"
            ),
        ]
    )
    sort_depth = sum(
        project.depth(point) for point in (*base, *top)
    ) / 8.0
    return rendered, sort_depth


def _face_visible(
    face: tuple[Point3D, ...],
    camera: Point3D,
) -> bool:
    first_edge = _subtract(face[1], face[0])
    second_edge = _subtract(face[2], face[1])
    normal = _cross(first_edge, second_edge)
    centroid = (
        sum(point[0] for point in face) / len(face),
        sum(point[1] for point in face) / len(face),
        sum(point[2] for point in face) / len(face),
    )
    return _dot(normal, _subtract(camera, centroid)) > 1e-6


def _opening_face(
    room_width: float,
    room_depth: float,
    opening: RoomOpening,
) -> tuple[Point3D, ...]:
    start = opening.offset_mm
    end = opening.offset_mm + opening.width_mm
    z_start = opening.sill_height_mm
    z_end = z_start + opening.height_mm
    if opening.wall == "north":
        return (
            (start, 0.0, z_start),
            (end, 0.0, z_start),
            (end, 0.0, z_end),
            (start, 0.0, z_end),
        )
    if opening.wall == "east":
        return (
            (room_width, start, z_start),
            (room_width, end, z_start),
            (room_width, end, z_end),
            (room_width, start, z_end),
        )
    if opening.wall == "south":
        return (
            (room_width - start, room_depth, z_start),
            (room_width - end, room_depth, z_start),
            (room_width - end, room_depth, z_end),
            (room_width - start, room_depth, z_end),
        )
    return (
        (0.0, room_depth - start, z_start),
        (0.0, room_depth - end, z_start),
        (0.0, room_depth - end, z_end),
        (0.0, room_depth - start, z_end),
    )


def _face_label(
    points: Iterable[Point3D],
    project: PerspectiveProjector,
    label: str,
    *,
    color: str,
) -> str:
    projected = [project(point) for point in points]
    center_x = sum(point[0] for point in projected) / len(projected)
    center_y = sum(point[1] for point in projected) / len(projected)
    return (
        f'<text x="{center_x:.3f}" y="{center_y:.3f}" '
        'text-anchor="middle" dominant-baseline="middle" '
        'font-family="sans-serif" font-size="11" font-weight="700" '
        f'fill="{color}">{escape(label)}</text>'
    )


def _polygon(
    points: Iterable[Point3D],
    project: PerspectiveProjector,
    *,
    fill: str,
    stroke: str,
    stroke_width: float,
    fill_opacity: float | None = None,
    stroke_dasharray: str | None = None,
    extra_attributes: str = "",
) -> str:
    point_text = " ".join(
        f"{screen_x:.3f},{screen_y:.3f}"
        for screen_x, screen_y in (project(point) for point in points)
    )
    opacity_attribute = (
        "" if fill_opacity is None else f' fill-opacity="{fill_opacity:g}"'
    )
    dash_attribute = (
        ""
        if stroke_dasharray is None
        else f' stroke-dasharray="{stroke_dasharray}"'
    )
    return (
        f'<polygon points="{point_text}" fill="{fill}"'
        f'{opacity_attribute} stroke="{stroke}" '
        f'stroke-width="{stroke_width:g}"{dash_attribute}'
        f"{extra_attributes}/>"
    )


def _placement_label(plan: RoomPlacementPlan) -> str:
    wall_names = {
        "south": "南墙",
        "east": "东墙",
        "north": "北墙",
        "west": "西墙",
    }
    position = wall_names.get(
        plan.placement.host_wall or "",
        "自由摆放",
    )
    return (
        f"位置：{position} · 旋转 {plan.placement.rotation_z_deg:g}°"
        f" · 标高 {plan.placement.origin_z_mm:g} mm"
    )


def _subtract(first: Point3D, second: Point3D) -> Vector3D:
    return (
        first[0] - second[0],
        first[1] - second[1],
        first[2] - second[2],
    )


def _dot(first: Vector3D, second: Vector3D) -> float:
    return (
        first[0] * second[0]
        + first[1] * second[1]
        + first[2] * second[2]
    )


def _cross(first: Vector3D, second: Vector3D) -> Vector3D:
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def _normalize(vector: Vector3D) -> Vector3D:
    length = sqrt(_dot(vector, vector))
    if length <= 1e-9:
        raise ValueError("perspective camera vector must be non-zero")
    return (
        vector[0] / length,
        vector[1] / length,
        vector[2] / length,
    )


def _append_axis_indicator(svg: list[str]) -> None:
    origin_x = 828.0
    origin_y = 548.0
    axes = (
        (origin_x + 38, origin_y + 13, "#dc2626", "X"),
        (origin_x - 34, origin_y + 13, "#16a34a", "Y"),
        (origin_x, origin_y - 43, "#2563eb", "Z"),
    )
    for end_x, end_y, color, label in axes:
        svg.extend(
            [
                (
                    f'<line x1="{origin_x:g}" y1="{origin_y:g}" '
                    f'x2="{end_x:g}" y2="{end_y:g}" stroke="{color}" '
                    'stroke-width="3" stroke-linecap="round"/>'
                ),
                (
                    f'<circle cx="{end_x:g}" cy="{end_y:g}" r="4" '
                    f'fill="{color}"/>'
                ),
                (
                    f'<text x="{end_x + 7:g}" y="{end_y + 4:g}" '
                    'font-family="sans-serif" font-size="12" '
                    f'font-weight="700" fill="{color}">{label}</text>'
                ),
            ]
        )
