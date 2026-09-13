"""Manufacturing policy, machining operations, hardware, and BOM output."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, List, Mapping

from furniture_panel_planning.cabinet_identity import index_by_role, qualify_panel_id
from furniture_panel_planning.panel_spec import FurnitureSpec, resolve_back_mount
from furniture_panel_planning.panel_models import PanelPlacement

from .manufacturing_edge_banding import get_edge_banding
from .connection_points import ConnectionPoint, collect_connection_points
from .connectors import ALL_CONNECTORS
from .features import (
    Feature,
    HoleFeature,
    from_edge_banding,
    from_hole_spec,
    from_machining_operation,
)
from .manufacturing_models import HardwareRecord, MachiningOperation, PanelRecord


FURNITURE_NAMES = {
    "floor_cabinet": "落地柜",
    "wall_cabinet": "吊柜",
}

VALID_MANUFACTURING_READINESS = frozenset(
    {
        "preliminary",
        "accepted",
        "factory_ready",
    }
)

MANUFACTURING_READINESS_LABELS = {
    "preliminary": "暂定，软件默认值待确认",
    "accepted": "方案已接受，仍需工厂工艺核对",
    "factory_ready": "工厂已确认可投产",
}

VALID_MOVABLE_SHELF_CONNECTORS = frozenset({"two_in_one", "shelf_pin"})
VALID_DOOR_HINGE_SIDES = frozenset({"left", "right"})

MANUFACTURING_OPTION_FIELDS = frozenset(
    {
        "options",
        "movable_shelf_connector",
        "door_hinge_side",
    }
)


@dataclass
class BOMReport:
    furniture_name: str
    dimensions: str
    panels: list[PanelRecord]
    hardware: list[HardwareRecord]
    operations: list[MachiningOperation]
    total_area_m2: float = 0.0
    readiness: str = "preliminary"
    requested_options: dict[str, Any] = field(default_factory=dict)
    appearance: dict[str, Any] = field(default_factory=dict)
    # 本源：每一处加工（孔/槽/封边）与配对孔打包的连接点。BOM/校验/导出由它们派生。
    features: list[Feature] = field(default_factory=list)
    connection_points: list[ConnectionPoint] = field(default_factory=list)

    @property
    def panel_count(self) -> int:
        return len(self.panels)

    @property
    def hardware_item_count(self) -> int:
        return len(self.hardware)


def _is_drawer_panel(panel: PanelRecord) -> bool:
    return "drawer" in panel.panel_type


def default_joint_connection(female: PanelRecord, male: PanelRecord) -> str:
    """制造层解析连不连：抽屉跨装配接触不固定；背板↔固定层板/背拉条不固定。"""
    if _is_drawer_panel(female) != _is_drawer_panel(male):
        return "off"
    types = {female.panel_type, male.panel_type}
    if types == {"back", "fixed_shelf"} or types == {"back", "back_rail"}:
        return "off"
    return "on"


def _derive_door_hinge_sides(
    placements: list[PanelPlacement],
    single_door_side: str | None,
) -> dict[str, str | None]:
    """按门板 X 位置推导每块门板的铰链侧。

    单门：必须显式提供 door_hinge_side（left/right）；双门：左门=left、右门=right。
    panel-plan 不再携带 door_hinge_side，这里由制造层派生。
    """
    doors = sorted(
        (p for p in placements if p.panel_type == "door"),
        key=lambda p: (p.pos_x, p.id),
    )
    if not doors:
        return {}
    if len(doors) == 1:
        if single_door_side not in VALID_DOOR_HINGE_SIDES:
            raise ValueError(
                "door_hinge_side must be 'left' or 'right' for a single door"
            )
        return {doors[0].id: single_door_side}
    if len(doors) == 2:
        return {doors[0].id: "left", doors[1].id: "right"}
    raise ValueError("door_hinge_side derivation supports at most 2 doors")


def _resolve_joint_connections(panels: list[PanelRecord]) -> None:
    """在制造层按面板类型重解析每条接触的连不连（原在 panel-plan 解析）。

    panel-plan 只产接触拓扑（bearing_id/end_id/face/edge）；连不连是制造层关注点
    （只影响孔位与五金，不影响面板几何），故在此重解析并写回每个 PanelRecord。
    """
    by_label = {panel.label: panel for panel in panels}
    for panel in panels:
        resolved = []
        for joint in panel.joints:
            female = by_label.get(joint.bearing_id)
            male = by_label.get(joint.end_id)
            connection = (
                default_joint_connection(female, male)
                if female is not None and male is not None
                else "on"
            )
            resolved.append(replace(joint, connection=connection))
        panel.joints = resolved


def _derive_features_and_points(
    panels: List[PanelRecord],
    operations: List[MachiningOperation],
    holes_by_connector: Mapping[Any, list],
) -> tuple[list[Feature], list[ConnectionPoint]]:
    """从「生成一次」的孔 + 槽 + 封边派生 Feature 与 ConnectionPoint 本源。"""
    hole_features = [
        from_hole_spec(hole)
        for holes in holes_by_connector.values()
        for hole in holes
    ]
    groove_features = [
        from_machining_operation(operation)
        for operation in operations
        if operation.operation_type == "cut_box"
    ]
    edge_features = [
        edge_feature
        for panel in panels
        for edge_feature in from_edge_banding(panel.label, panel.edge_banding)
    ]
    features = hole_features + groove_features + edge_features
    connection_points: list[ConnectionPoint] = []
    for connector_cls, holes in holes_by_connector.items():
        connection_points.extend(
            collect_connection_points(
                [from_hole_spec(hole) for hole in holes],
                owner=connector_cls.__name__,
            )
        )
    return features, connection_points


def recompute_features(
    panels: List[PanelRecord],
    operations: List[MachiningOperation],
) -> tuple[list[Feature], list[ConnectionPoint]]:
    """从（可能被修订过的）板件+槽重新派生 Feature + ConnectionPoint。

    供 `revise_stage_output` 在直接编辑制造输出后重算，保持
    features/connection_points 与 panels/operations 一致（避免持久化快照漂移）。
    """
    holes_by_connector = {
        connector_cls: connector_cls().generate_holes_for_panels(panels)
        for connector_cls in ALL_CONNECTORS
    }
    return _derive_features_and_points(panels, operations, holes_by_connector)


def plan_manufacturing(
    spec: FurnitureSpec,
    placements: list[PanelPlacement],
    *,
    requested_options: Mapping[str, Any] | None = None,
    appearance: Mapping[str, Any] | None = None,
) -> BOMReport:
    """Stage 4: apply materials and emit explicit machining operations."""
    options = dict(requested_options or {})
    unknown = sorted(set(options) - MANUFACTURING_OPTION_FIELDS)
    if unknown:
        raise ValueError(
            "manufacturing stage does not support: " + ", ".join(unknown)
        )
    movable_shelf_connector = options.get("movable_shelf_connector", "")
    if movable_shelf_connector not in VALID_MOVABLE_SHELF_CONNECTORS:
        has_movable = any(item.panel_type == "movable_shelf" for item in placements)
        if has_movable:
            raise ValueError(
                "movable_shelf_connector must be 'two_in_one' or 'shelf_pin' "
                "when movable shelves exist"
            )
        movable_shelf_connector = ""
    door_hinge_side = options.get("door_hinge_side")
    hinge_side_by_label = _derive_door_hinge_sides(placements, door_hinge_side)
    back_mount = resolve_back_mount(spec.back_mount)
    panels = [
        _manufacturing_panel(
            spec, back_mount, movable_shelf_connector,
            hinge_side_by_label.get(item.id), item,
        )
        for item in placements
    ]
    _resolve_joint_connections(panels)
    operations = _back_groove_operations(spec, back_mount, placements)

    # ── 本源：生成一次孔 → Feature + ConnectionPoint ──
    holes_by_connector = {
        connector_cls: connector_cls().generate_holes_for_panels(panels)
        for connector_cls in ALL_CONNECTORS
    }
    features, connection_points = _derive_features_and_points(
        panels, operations, holes_by_connector
    )

    dimensions = f"{spec.width:.0f}×{spec.height:.0f}×{spec.depth:.0f}mm"
    connector_options = options.get("options", {})
    if not isinstance(connector_options, Mapping):
        connector_options = {}
    return BOMReport(
        furniture_name=FURNITURE_NAMES.get(
            spec.furniture_category, spec.furniture_category
        ),
        dimensions=dimensions,
        panels=panels,
        hardware=estimate_hardware(
            panels,
            options=connector_options,
            connection_points=connection_points,
            features=features,
        ),
        operations=operations,
        total_area_m2=sum(panel.area_m2 for panel in panels),
        readiness="preliminary",
        requested_options=options,
        appearance=dict(appearance or {}),
        features=features,
        connection_points=connection_points,
    )


def _cam_face_for(placement: PanelPlacement) -> str | None:
    """Which face manufacturing operates the eccentric cam from.

    Horizontal carcass boards use the world-down face of the board.
    Drawer box sides, back and bottom use the outer face.
    """
    panel_type = placement.panel_type
    if panel_type in ("top", "fixed_shelf"):
        return placement.inner_face or None
    if panel_type == "bottom":
        return placement.outer_face or None
    if panel_type in ("drawer_side", "drawer_back", "drawer_bottom"):
        return placement.outer_face or None
    return None


def _manufacturing_panel(
    spec: FurnitureSpec,
    back_mount: str,
    movable_shelf_connector: str,
    door_hinge_side: str | None,
    placement: PanelPlacement,
) -> PanelRecord:
    if placement.material_role == "back":
        material = f"{spec.back_thickness:g}mm背板"
        thickness = spec.back_thickness
    elif placement.material_role == "door":
        material = f"{spec.door_thickness:g}mm门板"
        thickness = spec.door_thickness
    else:
        material = f"{spec.board_thickness:g}mm柜体板"
        thickness = spec.board_thickness
    drill_length = 0.0
    # 优先从连接拓扑推导排钻孔方向
    joints = placement.joints
    if joints:
        for j in joints:
            if j.bearing_id == placement.id:
                # female（侧板等）：inner_face 在 x/y 轴 → 高度方向排钻
                face_axis = j.face[1] if len(j.face) >= 2 else ""
                if face_axis in ("x", "y"):
                    drill_length = placement.size_z
                    break
            if j.end_id == placement.id:
                # male（横板等）：端面在 x 轴 → 宽度方向排钻
                if j.edge_axis == "x":
                    drill_length = placement.size_x
                    break
    # fallback：无连接拓扑时退回 panel_type 判断
    if drill_length == 0.0:
        if placement.panel_type in ("side", "divider"):
            drill_length = placement.size_z
        elif placement.panel_type in ("top", "bottom", "fixed_shelf", "movable_shelf"):
            drill_length = placement.size_x
        elif placement.panel_type == "door":
            drill_length = placement.size_z
    return PanelRecord(
        label=placement.id,
        name=placement.name,
        panel_type=placement.panel_type,
        material=material,
        thickness=thickness,
        length_mm=placement.size_x,
        width_mm=placement.size_y,
        size_x=placement.size_x,
        size_y=placement.size_y,
        size_z=placement.size_z,
        quantity=placement.quantity,
        drill_length=drill_length,
        edge_banding=_edge_banding_for(placement.panel_type, back_mount),
        note=placement.note,
        pos_x=placement.pos_x,
        pos_y=placement.pos_y,
        pos_z=placement.pos_z,
        depends_on=list(placement.depends_on),
        door_hinge_side=door_hinge_side,
        door_overlay=placement.door_overlay,
        back_mount=back_mount,
        movable_shelf_connector=movable_shelf_connector,
        inner_face=placement.inner_face,
        outer_face=placement.outer_face,
        cam_face=_cam_face_for(placement),
        joints=list(placement.joints),
        role=placement.role,
        parent_id=placement.parent_id,
    )


def _edge_banding_for(panel_type: str, back_mount: str) -> dict[str, str]:
    if panel_type == "back" and back_mount == "groove":
        return {}
    return get_edge_banding(panel_type)


def _back_groove_operations(
    spec: FurnitureSpec,
    back_mount: str,
    placements: list[PanelPlacement],
) -> list[MachiningOperation]:
    if back_mount != "groove":
        return []
    operations: list[MachiningOperation] = []
    by_parent: dict[str, list[PanelPlacement]] = {}
    for panel in placements:
        by_parent.setdefault(panel.parent_id or "", []).append(panel)
    required = {"left_side_panel", "right_side_panel", "top_panel", "bottom_panel", "back_panel"}
    board = spec.board_thickness
    depth = spec.groove_depth
    groove_width = spec.back_thickness + spec.groove_clearance
    groove_y = spec.back_offset
    common = {"operation_type": "cut_box", "size_y": groove_width, "pos_y": groove_y}
    for cabinet_id, cabinet_panels in by_parent.items():
        by_role = index_by_role(cabinet_panels, parent_id=cabinet_id or None)
        if not required.issubset(by_role):
            continue
        back = by_role["back_panel"]
        prefix = f"{cabinet_id}__" if cabinet_id else ""

        def _target(role: str) -> str:
            return qualify_panel_id(cabinet_id, role) if cabinet_id else role

        operations.extend(
            [
                MachiningOperation(
                    id=f"{prefix}left_side_back_groove",
                    target_panel=_target("left_side_panel"),
                    size_x=depth,
                    size_z=back.size_z,
                    pos_x=board - depth,
                    pos_z=back.pos_z,
                    note="左侧板背板槽",
                    **common,
                ),
                MachiningOperation(
                    id=f"{prefix}right_side_back_groove",
                    target_panel=_target("right_side_panel"),
                    size_x=depth,
                    size_z=back.size_z,
                    pos_x=spec.width - board,
                    pos_z=back.pos_z,
                    note="右侧板背板槽",
                    **common,
                ),
                MachiningOperation(
                    id=f"{prefix}top_back_groove",
                    target_panel=_target("top_panel"),
                    size_x=spec.width - 2 * board,
                    size_z=depth,
                    pos_x=board,
                    pos_z=spec.height - board,
                    note="顶板背板槽",
                    **common,
                ),
                MachiningOperation(
                    id=f"{prefix}bottom_back_groove",
                    target_panel=_target("bottom_panel"),
                    size_x=spec.width - 2 * board,
                    size_z=depth,
                    pos_x=board,
                    pos_z=by_role["bottom_panel"].pos_z + board - depth,
                    note="底板背板槽",
                    **common,
                ),
            ]
        )
    return operations


def estimate_hardware(
    panels: List[PanelRecord],
    *,
    options: Mapping[str, Any] | None = None,
    connection_points: list[ConnectionPoint] | None = None,
    features: list[Feature] | None = None,
) -> List[HardwareRecord]:
    """从 Feature + ConnectionPoint 派生五金 BOM。

    features/connection_points 由 plan_manufacturing 生成一次（Feature/ConnectionPoint
    本源）；缺省时各连接件自行重推导，保持独立调用可用。
    """
    hardware: List[HardwareRecord] = []
    for connector_cls in ALL_CONNECTORS:
        connector = connector_cls()
        hardware.extend(
            connector.boms(
                panels,
                options=options,
                connection_points=connection_points,
                features=features,
            )
        )
    return hardware


def format_bom_markdown(report: BOMReport) -> str:
    lines = [
        f"## 拆单报告 - {report.furniture_name}",
        "",
        f"外形尺寸: **{report.dimensions}**",
        f"制造状态: **{report.readiness}** — "
        f"{MANUFACTURING_READINESS_LABELS.get(report.readiness, '未知状态')}",
        "",
        f"### 板件清单 ({report.panel_count} 块)",
        "",
        "| 序号 | 名称 | 类型 | 开料尺寸(mm) | 厚度 | 数量 | 封边 | 备注 |",
        "|------|------|------|-------------|------|------|------|------|",
    ]
    for index, panel in enumerate(report.panels, 1):
        lines.append(
            f"| {index} | {panel.name} | {panel.panel_type} | "
            f"{panel.length_mm:.0f}×{panel.width_mm:.0f} | "
            f"{panel.thickness:.0f} | {panel.quantity} | "
            f"{panel.edge_banding_summary()} | {panel.note} |"
        )
    lines.extend(["", f"**总展开面积**: {report.total_area_m2:.4f} m²"])
    if report.operations:
        lines.extend(["", f"### 加工操作 ({len(report.operations)} 项)", ""])
        for operation in report.operations:
            lines.append(
                f"- {operation.note}: {operation.target_panel}, "
                f"{operation.size_x:g}×{operation.size_y:g}×{operation.size_z:g}mm"
            )
    if report.hardware:
        lines.extend(["", f"### 五金清单 ({len(report.hardware)} 项)", ""])
        for item in report.hardware:
            note = f"；{item.note}" if item.note else ""
            lines.append(
                f"- {item.name} {item.spec} ×{item.quantity}{item.unit}{note}"
            )
    return "\n".join(lines)


def _build_color_legend() -> Dict[str, Dict[str, str]]:
    """孔型图例：由各 Connector 的 hole_legend 自声明派生。"""
    legend: Dict[str, Dict[str, str]] = {
        # 背板槽是 cut_box 加工操作，非五金孔，留在制造阶段（不随 Connector 下沉）
        "back_groove": {"color": "#FFD700", "label": "背板槽"},
    }
    for connector_cls in ALL_CONNECTORS:
        for hole_type, meta in connector_cls.hole_legend.items():
            legend[hole_type] = {"color": meta["color"], "label": meta["label"]}
    return legend


_COLOR_LEGEND = _build_color_legend()


def collect_features(bom: BOMReport) -> list[Feature]:
    """返回 BOMReport 承载的 Feature 本源（不再重新生成孔）。

    Feature/ConnectionPoint 由 plan_manufacturing 生成一次，BOM/校验/导出
    都从它派生；这里只读不生成。
    """
    return list(bom.features)


def emit_drilled_holes(bom: BOMReport) -> dict:
    """Generate a per-panel hole summary for Viewer overlay.

    Uses collect_features to produce a unified Feature list, then serializes
    HoleFeature records (global + local coordinates) grouped by panel label.
    """
    panel_holes: dict[str, list[dict]] = {}

    for feature in collect_features(bom):
        if not isinstance(feature, HoleFeature):
            continue
        panel_holes.setdefault(feature.panel_label, []).append({
            "hole_type": feature.hole_type,
            "color": _COLOR_LEGEND.get(feature.hole_type, {}).get("color", "#888888"),
            "x": round(feature.x_global, 2),
            "y": round(feature.y_global, 2),
            "z": round(feature.z_global, 2),
            "local_x": round(feature.x_local, 2),
            "local_y": round(feature.y_local, 2),
            "local_z": round(feature.z_local, 2),
            "diameter": feature.diameter,
            "depth": feature.depth,
            "direction": feature.direction,
            "is_face_hole": feature.is_face_hole,
            "note": feature.note,
            "connection_id": feature.connection_id,
        })

    panels_out = []
    for panel in bom.panels:
        entry: dict = {
            "label": panel.label,
            "name": panel.name,
            "panel_type": panel.panel_type,
            "box": {
                "x": panel.size_x, "y": panel.size_y, "z": panel.size_z,
                "pos_x": panel.pos_x, "pos_y": panel.pos_y, "pos_z": panel.pos_z,
            },
            "holes": panel_holes.get(panel.label, []),
        }
        panels_out.append(entry)

    return {
        "furniture_name": bom.furniture_name,
        "dimensions": bom.dimensions,
        "color_legend": _COLOR_LEGEND,
        "panels": panels_out,
    }
