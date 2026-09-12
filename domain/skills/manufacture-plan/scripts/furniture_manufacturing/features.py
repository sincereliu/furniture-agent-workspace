"""制造层特征契约（Feature）——判别联合。

把「每一处加工」统一成 Feature 的子类（继承关系，不是组成关系）：
- HoleFeature：打孔（HoleSpec）
- GrooveFeature：开槽（MachiningOperation 的 cut_box）
- EdgeBandFeature：封边（PanelRecord.edge_banding）

完整口径见 references/feature-contract.md。Feature/ConnectionPoint 是制造层的
**本源**：plan_manufacturing 先生成一次孔 → Feature + ConnectionPoint，再由它们
派生 BOM、校验与孔导出（collect_features 只读 bom.features，不再重新生成孔）。

类型判断用 isinstance(feature, HoleFeature) 取代 kind == "hole" 字符串判断；
`kind` 字段 + `feature_from_dict` 仅用于 JSON 往返（asdict → feature_from_dict）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:
    # 仅类型标注用；运行时靠鸭子类型读取 HoleSpec 字段，避免
    # features ↔ connectors（__init__ → trinity → features）循环导入。
    from furniture_manufacturing.connectors.base import HoleSpec

from furniture_manufacturing.manufacturing_models import MachiningOperation


@dataclass
class Feature:
    """一处加工特征（基类）：挂在某块板上的一个加工动作。

    只放三种加工共有的字段：宿主板 + 位置 + 备注。
    具体加工是子类（HoleFeature / GrooveFeature / EdgeBandFeature），
    各自携带自己的专属字段。
    """

    # 判别标签（仅序列化/JSON 往返用；运行时类型判断仍用 isinstance）
    kind: str = ""

    # 宿主板
    panel_label: str = ""

    # 几何：局部原生位置（板件参考系）
    x_local: float = 0.0
    y_local: float = 0.0
    z_local: float = 0.0

    # 派生：柜体坐标（迁移期保留，目标现算）
    x_global: float = 0.0
    y_global: float = 0.0
    z_global: float = 0.0

    # 备注（给人看）
    note: str = ""


@dataclass
class HoleFeature(Feature):
    """打孔：一个圆柱（位置 + 直径 + 深度 + 方向）。

    hole_type 经目录映射到五金材料，不存材料本身。
    """

    hole_type: str = ""
    diameter: float = 0.0
    depth: float = 0.0
    direction: str = "+y"
    is_face_hole: bool = True

    # 连接点引用（字符串，第三步升级为实体）
    connection_id: str = ""


@dataclass
class GrooveFeature(Feature):
    """开槽：一个盒子（位置 + 长/宽/深）。

    cut_box 只存柜体坐标（pos_x/y/z → x_global/y_global/z_global），
    局部坐标待后续派生（见 coordinate-naming.md）。
    """

    feature_id: str = ""  # 稳定 id，如 "left_side_back_groove"
    size_x: float = 0.0
    size_y: float = 0.0
    size_z: float = 0.0


@dataclass
class EdgeBandFeature(Feature):
    """封边：一条边（封哪条边 + 封边条材质）。"""

    edges: str = ""
    material: str = ""


def from_hole_spec(hole: HoleSpec) -> HoleFeature:
    """把现有 HoleSpec 无损装进 HoleFeature。"""
    return HoleFeature(
        kind="hole",
        panel_label=hole.panel_label,
        x_local=hole.x_local,
        y_local=hole.y_local,
        z_local=hole.z_local,
        hole_type=hole.hole_type,
        diameter=hole.diameter,
        depth=hole.depth,
        direction=hole.direction,
        is_face_hole=hole.is_face_hole,
        connection_id=hole.connection_id,
        x_global=hole.x_global,
        y_global=hole.y_global,
        z_global=hole.z_global,
        note=hole.note,
    )


def from_machining_operation(operation: MachiningOperation) -> GrooveFeature:
    """把槽（cut_box）加工指令无损装进 GrooveFeature。"""
    return GrooveFeature(
        kind="groove",
        panel_label=operation.target_panel,
        feature_id=operation.id,
        size_x=operation.size_x,
        size_y=operation.size_y,
        size_z=operation.size_z,
        x_global=operation.pos_x,
        y_global=operation.pos_y,
        z_global=operation.pos_z,
        note=operation.note,
    )


def from_edge_banding(
    panel_label: str,
    edge_banding: Mapping[str, str],
) -> list[EdgeBandFeature]:
    """把一块板的封边字典无损装进 EdgeBandFeature 列表。

    edge_banding 形如 {"四边": "ABS 1.0mm同色"}；每条封边 key 对应一个特征。
    空字典返回空列表（入槽背板等不封边）。
    """
    return [
        EdgeBandFeature(
            kind="edge",
            panel_label=panel_label,
            edges=edges,
            material=material,
        )
        for edges, material in edge_banding.items()
    ]


_FEATURE_BY_KIND = {
    "hole": HoleFeature,
    "groove": GrooveFeature,
    "edge": EdgeBandFeature,
}


def feature_from_dict(data: Mapping[str, object]) -> Feature:
    """按判别标签 `kind` 把序列化字典还原成对应 Feature 子类。

    与 `asdict` 互为逆向：`asdict(feature)` 携带 `kind`，这里据 `kind` 选子类
    实例化。运行时类型判断仍用 `isinstance`，不靠 `kind` 字符串。
    """
    kind = data.get("kind")
    cls = _FEATURE_BY_KIND.get(kind)
    if cls is None:
        raise ValueError(f"unknown feature kind: {kind!r}")
    return cls(**data)
