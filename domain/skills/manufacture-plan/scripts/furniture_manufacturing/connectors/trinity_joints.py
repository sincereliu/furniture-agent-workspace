"""三合一连接拓扑辅助：从制造接触判定母件/公件。"""

from typing import Any, Dict, Mapping, Set

from furniture_manufacturing.confirmed_panels import Contact
from furniture_manufacturing.manufacturing_models import PanelRecord


def joint_is_connected(joint: Contact) -> bool:
    """True when this stage resolved the contact as fixed."""
    return joint.connection == "on"


def _joints_of(panel: PanelRecord) -> list:
    """面板参与的所有制造接触。"""
    return list(panel.joints) if panel.joints else []


def _is_female(panel: PanelRecord) -> bool:
    """该板是否有面被其他板的端面顶着（面接触方 → 预埋螺母）。"""
    return any(j.bearing_id == panel.label for j in _joints_of(panel))


def _is_male(panel: PanelRecord) -> bool:
    """该板是否有端面顶着其他板的面（边接触方 → 连接杆+偏心轮）。"""
    return any(j.end_id == panel.label for j in _joints_of(panel))


def _end_panel(joint: Any, by_label: Mapping[str, PanelRecord] | None) -> PanelRecord | None:
    if not by_label:
        return None
    return by_label.get(joint.end_id)


def _end_has_cam(joint: Any, by_label: Mapping[str, PanelRecord] | None) -> bool:
    end = _end_panel(joint, by_label)
    return bool(end and end.cam_face)


def _trinity_female(
    panel: PanelRecord,
    by_label: Mapping[str, PanelRecord] | None = None,
) -> bool:
    """x 轴方向、带 cam 的面接触方（侧板/隔板）。

    优先从连接拓扑推导；无连接拓扑时退回 panel_type 判断。
    端面件必须有 cam_face，否则抽屉侧板等会被误判为三合一母件。
    """
    if panel.joints:
        lookup = dict(by_label or {})
        lookup.setdefault(panel.label, panel)
        return any(
            j.bearing_id == panel.label
            and j.face[1] == "x"
            and _end_has_cam(j, lookup)
            and joint_is_connected(j)
            for j in _joints_of(panel)
        )
    # fallback: no joint topology available
    return panel.panel_type in ("side", "divider")


def _trinity_male(
    panel: PanelRecord,
    by_label: Mapping[str, PanelRecord] | None = None,
) -> bool:
    """x 轴方向的边接触方（横板），端面在 x 轴且端面件有 cam_face。

    优先从连接拓扑推导；无连接拓扑时退回 panel_type 判断。
    """
    if panel.joints:
        lookup = dict(by_label or {})
        lookup.setdefault(panel.label, panel)
        return any(
            j.end_id == panel.label
            and j.edge_axis == "x"
            and _end_has_cam(j, lookup)
            and joint_is_connected(j)
            for j in _joints_of(panel)
        )
    # fallback: no joint topology available
    return panel.panel_type in ("top", "bottom", "fixed_shelf")


def _gather_joints(panels: list[PanelRecord]) -> list:
    """收集所有面板的连接拓扑（去重）。"""
    seen: Set[tuple] = set()
    result = []
    for p in panels:
        for j in _joints_of(p):
            key = (j.bearing_id, j.end_id)
            if key not in seen:
                seen.add(key)
                result.append(j)
    return result


def _trinity_joints(panels: list[PanelRecord]) -> list:
    """筛选三合一相关的连接（已解析为连接，且 x 轴、端面件有 cam_face）。"""
    by_label = {panel.label: panel for panel in panels}
    return [
        j for j in _gather_joints(panels)
        if joint_is_connected(j)
        and j.face[1] == "x"
        and j.edge_axis == "x"
        and _end_has_cam(j, by_label)
    ]


def _male_edge_signs(panel: PanelRecord) -> Set[int]:
    """male 面板的 x 轴端面连接方向（-1=左，+1=右）。

    优先从连接拓扑推导；无连接拓扑时返回两端。
    """
    if panel.joints:
        signs = {
            j.edge_sign for j in _joints_of(panel)
            if j.end_id == panel.label
            and j.edge_axis == "x"
            and joint_is_connected(j)
        }
        if signs:
            return signs
    # fallback: no joint topology → assume both ends
    return {-1, 1}


def _other_axis(a: str, t: str) -> str:
    """连接平面内除边轴 a 与 cam 面轴 t 之外的第三轴。"""
    for axis in ("x", "y", "z"):
        if axis != a and axis != t:
            return axis
    return "y"


def _is_trinity_joint(joint: Any, by_label: Dict[str, PanelRecord]) -> bool:
    """某 joint 是否用三合一五金固定。

    连不连只看已解析的 `connection`。轴方向和 cam_face 只回答用什么五金：
    抽屉盒内部 x/y 接触可用三合一；柜体结构三合一走 x 轴（侧板↔横板）。
    """
    if not joint_is_connected(joint):
        return False
    if not _end_has_cam(joint, by_label):
        return False
    female = by_label[joint.bearing_id]
    male = by_label[joint.end_id]
    if male.panel_type == "back":
        # 背板三合一（内嵌/外盖）由 BackMountConnector 负责，不在柜体三合一内
        return False
    if "drawer" in female.panel_type:
        return joint.edge_axis in ("x", "y")
    return joint.edge_axis == "x"

