"""Manufacturing policy, machining operations, hardware, and BOM output."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, List, Mapping, Sequence

from .confirmed_panels import (
    ConfirmedConstruction,
    ConfirmedPanel,
    admit_construction,
    admit_panels,
)
from .panel_ids import index_by_role, qualify_panel_id
from .manufacturing_edge_banding import (
    DEFAULT_EDGE_BANDING_SELECTION,
    build_edge_banding,
)
from .edge_banding_catalog import material_keys, material_name, thickness_keys
from .connection_points import ConnectionPoint
from .connectors import ALL_CONNECTORS
from .features import (
    Feature,
    GrooveFeature,
    HoleFeature,
    from_edge_banding,
    from_hole_spec,
    from_machining_operation,
)
from .manufacturing_models import HardwareRecord, MachiningOperation, MaterialRecord, PanelRecord
from .materials_catalog import substrate_keys, surface_keys, substrate_name, surface_name


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
        "edge_banding",
    }
)

# appearance 按已确认板件的 material_role 选型
MATERIAL_ROLES = frozenset({"carcass", "door", "back"})


@dataclass
class BOMReport:
    furniture_name: str
    dimensions: str
    panels: list[PanelRecord]
    hardware: list[HardwareRecord]
    operations: list[MachiningOperation]
    materials: list[MaterialRecord] = field(default_factory=list)
    # 设计层回传（spec 原样带回）：feature-tree 等下游场景参数，保证 BOMReport 单一通道
    furniture_category: str = ""
    width: float = 0.0
    depth: float = 0.0
    height: float = 0.0
    board_thickness: float = 0.0
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
    placements: Sequence[ConfirmedPanel],
    single_door_side: str | None,
) -> dict[str, str | None]:
    """按门板 X 位置推导每块门板的铰链侧。

    单门：必须显式提供 door_hinge_side（left/right）；双门：左门=left、右门=right。
    铰链侧只在本阶段派生。
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
    """按面板类型写下每条接触的连不连。

    读入的接触只有几何。连不连只影响孔位与五金，写在本阶段自己的接触记录上。
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
) -> tuple[list[Feature], list[ConnectionPoint]]:
    """从连接件「按点产出」的 ConnectionPoint + 槽 + 封边派生 Feature 本源。

    连接点类连接件（三合一/背板）直接产出 ConnectionPoint（其 holes 即 HoleFeature）；
    其余连接件逐孔产出 HoleSpec → HoleFeature。槽/封边仍由 operations/edge_banding 派生。
    """
    connection_points: list[ConnectionPoint] = []
    hole_features: list[HoleFeature] = []
    for connector_cls in ALL_CONNECTORS:
        connector = connector_cls()
        if connector.produces_connection_points:
            points = connector.generate_connection_points(panels)
            connection_points.extend(points)
            for point in points:
                hole_features.extend(point.holes)
        else:
            hole_features.extend(
                from_hole_spec(hole)
                for hole in connector.generate_holes_for_panels(panels)
            )
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
    return features, connection_points


def recompute_features(
    panels: List[PanelRecord],
    operations: List[MachiningOperation],
) -> tuple[list[Feature], list[ConnectionPoint]]:
    """从（可能被修订过的）板件+槽重新派生 Feature + ConnectionPoint。

    供 `revise_stage_output` 在直接编辑制造输出后重算，保持
    features/connection_points 与 panels/operations 一致（避免持久化快照漂移）。
    """
    return _derive_features_and_points(panels, operations)


def _normalize_appearance(
    appearance: Mapping[str, Any] | None,
    placements: Sequence[ConfirmedPanel],
) -> dict[str, dict[str, str]]:
    """校验并规范化 appearance 选型（按 material_role）。

    严格准入，不做静默默认：
    - 空 appearance 表示不物化（返回空 dict）；
    - 角色键只能是 carcass/door/back；
    - 每个实际出现的 material_role 必须有对应选型，缺则报错；
    - 无对应板件的角色键报错（选型集合须与实际板件一致）；
    - 每份选型的 substrate/surface 键必须在材料目录里（查表）。
    """
    raw = dict(appearance or {})
    if not raw:
        return {}
    actual_roles = {placement.material_role for placement in placements}
    unknown = sorted(set(raw) - MATERIAL_ROLES)
    if unknown:
        raise ValueError(
            "appearance roles must be one of: "
            + ", ".join(sorted(MATERIAL_ROLES))
            + "; got: "
            + ", ".join(unknown)
        )
    missing = sorted(actual_roles - set(raw))
    if missing:
        raise ValueError(
            "appearance missing selection for material_role: " + ", ".join(missing)
        )
    extra = sorted(set(raw) - actual_roles)
    if extra:
        raise ValueError(
            "appearance has selection for absent material_role: " + ", ".join(extra)
        )
    valid_substrate = set(substrate_keys())
    valid_surface = set(surface_keys())
    normalized: dict[str, dict[str, str]] = {}
    for role, selection in raw.items():
        if not isinstance(selection, Mapping):
            raise ValueError(
                f"appearance[{role}] must be an object with 'substrate' and 'surface'"
            )
        substrate = selection.get("substrate")
        surface = selection.get("surface")
        if substrate not in valid_substrate:
            raise ValueError(
                f"appearance[{role}].substrate unknown: {substrate!r}; "
                "valid: " + ", ".join(sorted(valid_substrate))
            )
        if surface not in valid_surface:
            raise ValueError(
                f"appearance[{role}].surface unknown: {surface!r}; "
                "valid: " + ", ".join(sorted(valid_surface))
            )
        normalized[role] = {"substrate": substrate, "surface": surface}
    return normalized


def _normalize_edge_banding_selection(raw: Any) -> dict[str, str]:
    """校验封边选型 {material, thickness}，缺省用默认 abs/t1_0。

    键值必须命中封边皮目录（查表准入）；未知字段/键报错。
    """
    selection = dict(DEFAULT_EDGE_BANDING_SELECTION)
    if raw is None:
        return selection
    if not isinstance(raw, Mapping):
        raise ValueError(
            "edge_banding option must be an object with 'material' and 'thickness'"
        )
    unknown = sorted(set(raw) - {"material", "thickness"})
    if unknown:
        raise ValueError(
            "edge_banding option does not support: " + ", ".join(unknown)
        )
    material = raw.get("material")
    thickness = raw.get("thickness")
    if material is not None:
        if material not in material_keys():
            raise ValueError(
                f"edge_banding material unknown: {material!r}; "
                "valid: " + ", ".join(material_keys())
            )
        selection["material"] = material
    if thickness is not None:
        if thickness not in thickness_keys():
            raise ValueError(
                f"edge_banding thickness unknown: {thickness!r}; "
                "valid: " + ", ".join(thickness_keys())
            )
        selection["thickness"] = thickness
    return selection


def plan_manufacturing(
    spec: Any,
    placements: Sequence[Any],
    *,
    requested_options: Mapping[str, Any] | None = None,
    appearance: Mapping[str, Any] | None = None,
) -> BOMReport:
    """Apply materials and emit explicit machining operations.

    ``spec`` and ``placements`` may be confirmed-panel objects or mappings.
    Only the fields this stage machines are copied.
    """
    spec = admit_construction(spec)
    placements = admit_panels(placements)
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
    back_mount = spec.back_mount
    appearance_by_role = _normalize_appearance(appearance, placements)
    edge_banding_selection = _normalize_edge_banding_selection(
        options.get("edge_banding")
    )
    panels = [
        _manufacturing_panel(
            spec, back_mount, movable_shelf_connector,
            hinge_side_by_label.get(item.id), item,
            appearance_by_role.get(item.material_role),
            edge_banding_selection,
        )
        for item in placements
    ]
    _resolve_joint_connections(panels)
    operations = _back_groove_operations(spec, back_mount, placements)

    # ── 本源：连接件按点产出 ConnectionPoint + 逐孔 HoleFeature → Feature ──
    features, connection_points = _derive_features_and_points(panels, operations)

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
        materials=estimate_materials(panels),
        furniture_category=spec.furniture_category,
        width=spec.width,
        depth=spec.depth,
        height=spec.height,
        board_thickness=spec.board_thickness,
        total_area_m2=sum(panel.area_m2 for panel in panels),
        readiness="preliminary",
        requested_options=options,
        appearance=appearance_by_role,
        features=features,
        connection_points=connection_points,
    )


def _cam_face_for(placement: ConfirmedPanel) -> str | None:
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
    spec: ConfirmedConstruction,
    back_mount: str,
    movable_shelf_connector: str,
    door_hinge_side: str | None,
    placement: ConfirmedPanel,
    material_selection: Mapping[str, str] | None = None,
    edge_banding_selection: Mapping[str, str] | None = None,
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
    selection = material_selection or {}
    return PanelRecord(
        label=placement.id,
        name=placement.name,
        panel_type=placement.panel_type,
        material=material,
        substrate=selection.get("substrate", ""),
        surface=selection.get("surface", ""),
        thickness=thickness,
        length_mm=placement.size_x,
        width_mm=placement.size_y,
        size_x=placement.size_x,
        size_y=placement.size_y,
        size_z=placement.size_z,
        quantity=placement.quantity,
        drill_length=drill_length,
        edge_banding=_edge_banding_for(
            placement.panel_type, back_mount, thickness,
            selection.get("surface", ""), edge_banding_selection,
        ),
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


def _edge_banding_for(
    panel_type: str,
    back_mount: str,
    thickness: float,
    surface: str,
    selection: Mapping[str, str],
) -> dict:
    if panel_type == "back" and back_mount == "groove":
        return {}
    return build_edge_banding(
        panel_type, thickness=thickness, surface=surface, selection=selection
    )


def _back_groove_operations(
    spec: ConfirmedConstruction,
    back_mount: str,
    placements: Sequence[ConfirmedPanel],
) -> list[MachiningOperation]:
    if back_mount != "groove":
        return []
    operations: list[MachiningOperation] = []
    by_parent: dict[str, list[ConfirmedPanel]] = {}
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


def estimate_materials(panels: List[PanelRecord]) -> List[MaterialRecord]:
    """从板件派生材料 BOM：基材(m²) + 饰面(m²) + 封边皮(m)。

    与 estimate_hardware 对称：五金从 Feature/ConnectionPoint 派生，
    材料从 PanelRecord 的 substrate/surface/edge_banding 派生。
    封边皮长度按「四边」周长 2×(长+宽) 计量；非四边集合暂不计量。
    """
    substrate_by_key: dict[tuple, float] = {}
    surface_by_key: dict[str, float] = {}
    edge_by_key: dict[tuple, float] = {}

    for panel in panels:
        if panel.substrate:
            key = (panel.substrate, panel.thickness)
            substrate_by_key[key] = substrate_by_key.get(key, 0.0) + panel.area_m2
        if panel.surface:
            surface_by_key[panel.surface] = (
                surface_by_key.get(panel.surface, 0.0) + panel.area_m2
            )
        for edges, spec in panel.edge_banding.items():
            if not isinstance(spec, Mapping):
                raise ValueError("edge banding spec must be an object")
            if edges != "四边":
                continue
            perimeter_m = (
                2 * (panel.length_mm + panel.width_mm) * panel.quantity / 1000
            )
            key = (
                spec.get("material", ""),
                spec.get("thickness_mm", 0.0),
                spec.get("width_mm", 0.0),
                spec.get("color", ""),
            )
            edge_by_key[key] = edge_by_key.get(key, 0.0) + perimeter_m

    records: List[MaterialRecord] = []
    for (substrate, thickness), area in sorted(substrate_by_key.items()):
        records.append(
            MaterialRecord(
                category="substrate",
                key=substrate,
                name=substrate_name(substrate),
                spec=f"{thickness:g}mm",
                quantity=area,
                unit="m²",
            )
        )
    for surface, area in sorted(surface_by_key.items()):
        records.append(
            MaterialRecord(
                category="surface",
                key=surface,
                name=surface_name(surface),
                quantity=area,
                unit="m²",
            )
        )
    for (material, thickness_mm, width_mm, color), length_m in sorted(
        edge_by_key.items()
    ):
        spec = f"{thickness_mm:g}×{width_mm:g}mm"
        if color:
            spec += f" {color}"
        records.append(
            MaterialRecord(
                category="edge_banding",
                key=material,
                name=material_name(material),
                spec=spec,
                quantity=length_m,
                unit="m",
            )
        )
    return records


def _material_label(panel: PanelRecord) -> str:
    """板件材质显示名：基材 · 表面；未物化时占位。"""
    substrate = substrate_name(panel.substrate) if panel.substrate else ""
    surface = surface_name(panel.surface) if panel.surface else ""
    if substrate and surface:
        return f"{substrate} · {surface}"
    return substrate or surface or "—"


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
        "| 序号 | 名称 | 类型 | 材质 | 开料尺寸(mm) | 厚度 | 数量 | 封边 | 备注 |",
        "|------|------|------|------|-------------|------|------|------|------|",
    ]
    for index, panel in enumerate(report.panels, 1):
        lines.append(
            f"| {index} | {panel.name} | {panel.panel_type} | {_material_label(panel)} | "
            f"{panel.length_mm:.0f}×{panel.width_mm:.0f} | "
            f"{panel.thickness:.0f} | {panel.quantity} | "
            f"{panel.edge_banding_summary()} | {panel.note} |"
        )
    lines.extend(["", f"**总展开面积**: {report.total_area_m2:.4f} m²"])
    grooves = [
        feature for feature in report.features
        if isinstance(feature, GrooveFeature)
    ]
    if grooves:
        lines.extend(["", f"### 加工操作 ({len(grooves)} 项)", ""])
        for groove in grooves:
            lines.append(
                f"- {groove.note}: {groove.panel_label}, "
                f"{groove.size_x:g}×{groove.size_y:g}×{groove.size_z:g}mm"
            )
    if report.materials:
        lines.extend(["", f"### 材料清单 ({len(report.materials)} 项)", ""])
        for item in report.materials:
            spec = f" {item.spec}" if item.spec else ""
            lines.append(f"- {item.name}{spec} ×{item.quantity:.3f}{item.unit}")
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
