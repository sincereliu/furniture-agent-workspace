"""导出柜柜六面钻 XML 文件（KDTPanelFormat）。

从 drilled-holes JSON 反推板件上的所有孔位和槽位，
生成与 guigui3 兼容的六面钻加工文件。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from xml.dom import minidom
from xml.etree import ElementTree as ET


# ---------------------------------------------------------------------------
# 设备配置
# ---------------------------------------------------------------------------

def _load_device_config() -> dict[str, Any]:
    """加载 six_side_drill_guigui.yaml 中的 panel_placement 映射。"""
    p = Path(__file__).resolve().parent / "devices" / "six_side_drill_guigui.yaml"
    with open(p, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg.get("panel_placement", {})


def _resolve_placement(
    panel_type: str,
) -> dict[str, str]:
    """根据 panel_type 返回对应的 placement 规则。

    未匹配到具体类型时回退到 default。
    """
    placement = _load_device_config()
    if panel_type in ("divider",):
        panel_type = "side"
    if panel_type in ("top", "bottom", "fixed_shelf", "movable_shelf"):
        panel_type = "horizontal"
    return placement.get(panel_type, placement.get("default", {}))


def _box_value(box: dict[str, Any], key: str) -> float:
    return float(box.get(key, 0))


def _hole_value(hole: dict[str, Any], local_key: str, global_key: str) -> float:
    """优先取 local_*，回退到全局坐标。"""
    return float(hole.get(local_key, hole.get(global_key, 0)))


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def drill_json_to_xml_files(
    json_path: str | Path,
    output_dir: str | Path,
) -> list[Path]:
    """读取 drilled-holes JSON 并逐板件导出六面钻 XML。

    参数:
        json_path: drilled-holes.json 路径
        output_dir: 输出目录

    返回:
        生成的 XML 文件路径列表
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    paths: list[Path] = []
    for panel in data.get("panels", []):
        panel_name = panel.get("name", panel.get("label", "unknown"))
        plank_num = panel.get("label", "unknown")

        # 板件尺寸 (从 box 获取)
        box = panel.get("box", {})

        # 类型推断
        panel_type = _infer_panel_type(panel)

        # 设备配置映射
        placement = _resolve_placement(panel_type)

        # 六面钻坐标: 根据 panel_type 从 box 的三轴映射到机床 X/Y 轴
        sixd_x = _box_value(box, placement.get("sixd_x_from_box", "x"))
        sixd_y = _box_value(box, placement.get("sixd_y_from_box", "z"))

        # 板厚轴 = 剩余未被使用的那根轴
        used_axes = {placement.get("sixd_x_from_box", "x"), placement.get("sixd_y_from_box", "z")}
        all_axes = {"x", "y", "z"}
        sixd_z_axis = (all_axes - used_axes).pop()
        sixd_z = _box_value(box, sixd_z_axis)

        # X1/Y1 映射键
        x1_key = placement.get("x1_from_hole", "local_x")
        y1_key = placement.get("y1_from_hole", "local_y")

        panel_xml = _make_panel_xml(
            name=panel_name,
            sixd_x=sixd_x,
            sixd_y=sixd_y,
            sixd_z=sixd_z,
            holes=panel.get("holes", []),
            slots=panel.get("slots", []),
            x1_key=x1_key,
            y1_key=y1_key,
        )

        file_path = out_dir / f"{plank_num}.xml"
        file_path.write_text(panel_xml, encoding="utf-8")
        paths.append(file_path)

    return paths


# ---------------------------------------------------------------------------
# 面板类型推断
# ---------------------------------------------------------------------------

def _infer_panel_type(panel: dict[str, Any]) -> str:
    """从 panel name/label 推断面板类型。"""
    panel_type = panel.get("panel_type", "")
    if panel_type:
        return panel_type
    name = panel.get("name", "").lower()
    if "侧板" in name or "立板" in name or "隔板" in name:
        return "side"
    elif "顶板" in name:
        return "top"
    elif "底板" in name:
        return "bottom"
    elif "层板" in name:
        return "fixed_shelf"
    elif "门板" in name or "门" in name:
        return "door"
    elif "背板" in name:
        return "back"
    elif "踢脚" in name and "支撑" in name:
        return "side"
    elif "踢脚" in name:
        return "toe_kick"
    elif "拉条" in name:
        return "back_rail"
    return "default"


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _quadrant(direction: str) -> str:
    """根据钻孔方向返回柜柜 Quadrant（1-4）。"""
    return {"+x": "1", "-x": "2", "+y": "3", "-y": "4"}.get(direction, "1")


def _z1_for_direction(
    direction: str,
    hole: dict[str, Any],
) -> float:
    """计算水平孔在板厚方向的 Z1 坐标。"""
    if direction in ("+x", "-x"):
        return float(hole.get("local_z", 0))
    elif direction in ("+y", "-y"):
        return float(hole.get("local_x", 0))
    return 0.0


def _flush_xml(text: str) -> str:
    """移除 XML 声明行，与柜柜输出格式一致。"""
    lines = text.splitlines(keepends=True)
    if lines and lines[0].startswith("<?xml"):
        return "".join(lines[1:])
    return text


# ---------------------------------------------------------------------------
# XML 构造
# ---------------------------------------------------------------------------

def _make_panel_xml(
    name: str,
    sixd_x: float,
    sixd_y: float,
    sixd_z: float,
    holes: list[dict[str, Any]],
    slots: list[dict[str, Any]],
    x1_key: str,
    y1_key: str,
) -> str:
    """构造一块板件的 KDTPanelFormat XML 字符串。

    sixd_x = PanelLength（机床 X 轴方向尺寸）
    sixd_y = PanelWidth （机床 Y 轴方向尺寸）
    sixd_z = PanelThickness（板厚，机床 Z 轴）
    x1_key / y1_key = 从 hole dict 取 X1/Y1 坐标的 key
    """
    root = ET.Element("KDTPanelFormat")

    panel_elem = ET.SubElement(root, "PANEL")
    _add_text(panel_elem, "PanelLength", str(sixd_x))
    _add_text(panel_elem, "PanelWidth", str(sixd_y))
    _add_text(panel_elem, "PanelThickness", str(sixd_z))
    _add_text(panel_elem, "PanelName", name)

    # 柜柜 Params: L/W 与 PanelLength/PanelWidth 交换
    # L(板长) = PanelWidth(sixd_y), W(板宽) = PanelLength(sixd_x)
    params = ET.SubElement(panel_elem, "Params")
    ET.SubElement(params, "Param", Key="L", Value=str(sixd_y), Comment="板长")
    ET.SubElement(params, "Param", Key="W", Value=str(sixd_x), Comment="板宽")
    ET.SubElement(params, "Param", Key="T", Value=str(sixd_z), Comment="板厚")

    outline = ET.SubElement(panel_elem, "PanelOutline")
    vertices = [
        (0, sixd_y), (0, 0), (sixd_x, 0), (sixd_x, sixd_y),
        (0, sixd_y), (0, sixd_y),
    ]
    for vx, vy in vertices:
        vt = ET.SubElement(outline, "Vertex")
        _add_text(vt, "X1", str(vx))
        _add_text(vt, "Y1", str(vy))

    # 孔位
    for hole in holes:
        xml_x = _hole_value(hole, x1_key, x1_key)
        xml_y = _hole_value(hole, y1_key, y1_key)
        diam = float(hole.get("diameter", 10))
        depth_2d = float(hole.get("depth", 11))
        direction = hole.get("direction", "+z")

        # 从孔自身属性读取：is_face_hole → TypeNo=1(Vertical), 否则 TypeNo=2(Horizontal)
        if hole.get("is_face_hole", True):
            type_no = "1"
            type_name = "Vertical Hole"
        else:
            type_no = "2"
            type_name = "Horizontal Hole"

        cad = ET.SubElement(root, "CAD")
        _add_text(cad, "TypeNo", type_no)
        _add_text(cad, "TypeName", type_name)
        _add_text(cad, "X1", f"{xml_x:.1f}")
        _add_text(cad, "Y1", f"{xml_y:.1f}")
        if type_no == "2":
            z1 = _z1_for_direction(direction, hole)
            _add_text(cad, "Z1", f"{z1:.2f}")
            _add_text(cad, "Quadrant", _quadrant(direction))
            _add_text(cad, "IntervalZ", "0.00")
        _add_text(cad, "Depth", f"{depth_2d:.1f}")
        _add_text(cad, "Diameter", f"{diam:.1f}")
        _add_text(cad, "Enable", "1")
        _add_text(cad, "HoleNo", "1")
        _add_text(cad, "IntervalX", "0.00")
        _add_text(cad, "IntervalY", "0.00")

    # 槽位
    for slot in slots:
        # 槽在 drilled-holes JSON 中尚未存槽位
        # TODO: 当 emit_drilled_holes 含槽位后实现
        pass

    _rough = ET.tostring(root, encoding="unicode")
    dom = minidom.parseString(_rough)
    return _flush_xml(dom.toprettyxml(indent="    "))


def _add_text(parent: ET.Element, tag: str, text: str) -> ET.Element:
    elem = ET.SubElement(parent, tag)
    elem.text = text
    return elem