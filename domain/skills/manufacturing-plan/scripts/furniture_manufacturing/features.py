"""制造层特征契约（Feature）。

本模块是「特征」抽象的契约：把「每一处加工」统一成 Feature——
- kind="hole"：孔（HoleSpec），第一步落地；
- kind="groove"：槽（MachiningOperation 的 cut_box），第二步落地；
- kind="edge_band"：封边（PanelRecord.edge_banding），第二步落地。

完整口径见 references/feature-contract.md。当前只定义契约与转换函数，
不改变任何现有行为（校验/导出仍消费原始 HoleSpec / MachiningOperation / edge_banding）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from furniture_manufacturing.connectors.base import HoleSpec
from furniture_manufacturing.manufacturing_models import MachiningOperation

# 特征种类：一处加工动作的分类。
FEATURE_KIND_HOLE = "hole"
FEATURE_KIND_GROOVE = "groove"
FEATURE_KIND_EDGE_BAND = "edge_band"


@dataclass
class Feature:
    """一处加工特征：挂在某块板上的一个加工动作。

    公共字段：
    - kind：特征种类（hole/groove/edge_band）。
    - feature_id：稳定 id（槽有 "left_side_back_groove" 等；孔/封边可空）。
    - panel_label：宿主板。
    - 位置：x_local/y_local/z_local 是局部原生坐标（板件参考系）；
      x_global/y_global/z_global 是柜体坐标，属派生量，迁移期保留，
      目标改为现算（见 references/coordinate-naming.md）。

    孔专用（kind="hole"）：hole_type / diameter / depth / direction / is_face_hole /
    connection_id。hole_type 经目录映射到五金材料，不存材料本身。

    槽专用（kind="groove"）：size_x/y/z 为盒子尺寸（长/宽/深），position 用
    x_global/y_global/z_global（当前 cut_box 只存柜体坐标，局部坐标待派生）。

    封边专用（kind="edge_band"）：edges（封哪些边，如「四边」）+ material（封边条
    规格，如「ABS 1.0mm同色」）。
    """

    # 身份：种类 + 稳定 id + 宿主板
    kind: str = FEATURE_KIND_HOLE
    feature_id: str = ""
    panel_label: str = ""

    # 几何：局部原生位置（板件参考系）
    x_local: float = 0.0
    y_local: float = 0.0
    z_local: float = 0.0

    # 孔专用：孔型（经目录映射到五金材料，不存材料本身）+ 形状
    hole_type: str = ""
    diameter: float = 0.0
    depth: float = 0.0
    direction: str = "+y"
    is_face_hole: bool = True

    # 连接点引用（字符串，第三步升级为实体）
    connection_id: str = ""

    # 槽专用：盒子尺寸（长/宽/深）
    size_x: float = 0.0
    size_y: float = 0.0
    size_z: float = 0.0

    # 封边专用：封哪些边 + 封边条规格
    edges: str = ""
    material: str = ""

    # 派生：柜体坐标（迁移期保留，目标现算）
    x_global: float = 0.0
    y_global: float = 0.0
    z_global: float = 0.0

    # 备注（给人看）
    note: str = ""


def from_hole_spec(hole: HoleSpec) -> Feature:
    """把现有 HoleSpec 无损装进 Feature 契约（kind="hole"）。"""
    return Feature(
        kind=FEATURE_KIND_HOLE,
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


def from_machining_operation(operation: MachiningOperation) -> Feature:
    """把槽（cut_box）加工指令无损装进 Feature 契约（kind="groove"）。

    cut_box 只存柜体坐标（pos_x/y/z），局部坐标待后续派生（目标见
    coordinate-naming.md）。
    """
    return Feature(
        kind=FEATURE_KIND_GROOVE,
        feature_id=operation.id,
        panel_label=operation.target_panel,
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
) -> list[Feature]:
    """把一块板的封边字典无损装进 Feature 契约（kind="edge_band"）。

    edge_banding 形如 {"四边": "ABS 1.0mm同色"}；每条封边 key 对应一个 Feature。
    空字典返回空列表（入槽背板等不封边）。
    """
    return [
        Feature(
            kind=FEATURE_KIND_EDGE_BAND,
            panel_label=panel_label,
            edges=edges,
            material=material,
        )
        for edges, material in edge_banding.items()
    ]
