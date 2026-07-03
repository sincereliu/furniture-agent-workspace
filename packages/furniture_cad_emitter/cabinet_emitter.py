"""柜体 Emitter — 将 PanelRecord 列表转为 build123d 源码文件。

流程: List[PanelRecord] → Feature Tree dict → build123d .py 源码 → Bridge → .step + .glb

与现有的 emitter.py 配合使用：
  - emitter.py 的 write_build123d_source() 接收 Feature Tree dict
  - 本模块负责 PanelRecord → Feature Tree 的转换
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from furniture_schema.panel import PanelRecord


def panels_to_feature_tree(
    panels: List[PanelRecord],
    furniture_type: str = "floor_cabinet",
    parameters: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """将 PanelRecord 列表转换为 Feature Tree dict。

    Feature Tree 格式与现有 emitter.py 兼容：
    {
        "schema_version": 1,
        "furniture_type": "floor_cabinet",
        "coordinate_system": {...},
        "parameters": {...},
        "features": [
            {
                "id": "left_side_panel",
                "type": "box",
                "size": {"x": 18, "y": 580, "z": 1000},
                "position": {"x": 0, "y": 0, "z": 0},
                "depends_on": [],
            },
            ...
        ],
        "root": {
            "id": "cabinet_assembly",
            "type": "compound",
            "children": [...]
        }
    }

    Args:
        panels: 拆单后的 PanelRecord 列表
        furniture_type: 家具类型标签
        parameters: 可选参数字典（如包含 width/depth/height）

    Returns:
        标准 Feature Tree dict
    """
    features = []
    for panel in panels:
        feature = {
            "id": panel.label,
            "type": "box",
            "size": {"x": panel.size_x, "y": panel.size_y, "z": panel.size_z},
            "position": {"x": panel.pos_x, "y": panel.pos_y, "z": panel.pos_z},
            "depends_on": [],
        }
        features.append(feature)

    feature_ids = [f["id"] for f in features]

    return {
        "schema_version": 1,
        "furniture_type": furniture_type,
        "units": "mm",
        "coordinate_system": {
            "origin": "lower-left-rear-ground-corner",
            "x": "left-to-right",
            "y": "rear-to-front",
            "z": "up",
        },
        "parameters": parameters or {},
        "features": features,
        "root": {
            "id": f"{furniture_type}_assembly",
            "type": "compound",
            "children": feature_ids,
        },
    }


def emit_panels_to_source(
    panels: List[PanelRecord],
    source_path: str | Path,
    furniture_type: str = "floor_cabinet",
    parameters: Dict[str, Any] | None = None,
) -> Path:
    """将 PanelRecord 列表直接写入 build123d 源码文件。

    这绕过了 emitter.py，直接生成可被 Bridge 消费的 .py 文件。

    Args:
        panels: 拆单后的 PanelRecord 列表
        source_path: 输出 .py 文件路径
        furniture_type: 家具类型标签
        parameters: 可选参数字典

    Returns:
        写入后的 Path 对象
    """
    feature_tree = panels_to_feature_tree(panels, furniture_type, parameters)

    from furniture_cad_emitter.emitter import write_build123d_source

    return write_build123d_source(feature_tree, source_path)