"""导出柜柜六面钻 XML 文件（KDTPanelFormat）。

从 drilled-holes JSON 反推板件上的所有孔位和槽位，
生成与 guigui3 兼容的六面钻加工文件。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from xml.dom import minidom
from xml.etree import ElementTree as ET


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

        # 板件尺寸 (从 box 获取，由 pos+size 推算)
        box = panel.get("box", {})
        sx = float(box.get("x", 0))
        sy = float(box.get("y", 0))
        sz = float(box.get("z", 0))

        # 判断竖板/横板：竖板 Z 是高度 (面板面 = X-Z)，横板 Z 小(面板面 = X-Y)
        # 但 XML 坐标系中竖直孔在 X=宽方向, Y=长方向
        # guigui3 的 Length = 长(L) = 高度方向，Width = 宽(W) = 宽度方向
        # 我们的 drilled-holes JSON 坐标约定：
        #   - 侧板: size_x=18 (厚), size_y=深度, size_z=高度 → L=z=height, W=y=depth
        #   - 横板: size_x=宽度, size_y=深度, size_z=18 (厚) → L=x=width, W=y=depth

        panel_type = panel.get("panel_type", "")
        label = panel.get("label", "")

        # panel_type 通常不在 drilled-holes JSON 中，从 label 或 name 推断
        if not panel_type:
            name = panel.get("name", "").lower()
            if "侧板" in name or "立板" in name or "隔板" in name:
                panel_type = "side"
            elif "顶板" in name:
                panel_type = "top"
            elif "底板" in name:
                panel_type = "bottom"
            elif "层板" in name:
                panel_type = "fixed_shelf"
            elif "门板" in name or "门" in name:
                panel_type = "door"
            elif "背板" in name:
                panel_type = "back"
            elif "踢脚" in name:
                panel_type = "toe_kick"
            elif "拉条" in name:
                panel_type = "back_rail"

        if panel_type in ("side", "divider"):
            # 竖板：孔在侧板内侧面 (X-Z 平面)
            # guigui3 XML: Length=高度方向(Z), Width=深度方向(Y), Thickness=厚度(X)
            length = sz
            width_2d = sy
            thickness = sx
            map_fn = _side_panel_mapping
        elif panel_type == "door":
            # 门板同竖板（门板 Y=厚度）
            length = sz
            width_2d = sx
            thickness = sy
            map_fn = _side_panel_mapping
        elif panel_type in ("top", "bottom", "fixed_shelf", "movable_shelf"):
            # 横板：孔在顶/底面 (X-Y 平面)
            # guigui3 XML: Length=宽度方向(X), Width=深度方向(Y), Thickness=厚度(Z)
            length = sx
            width_2d = sy
            thickness = sz
            map_fn = _top_panel_mapping
        else:
            # 背板/背拉条/踢脚等默认处理
            length = sx
            width_2d = sy
            thickness = sz
            map_fn = _top_panel_mapping

        panel_xml = _make_panel_xml(
            name=panel_name,
            length=length,
            width_2d=width_2d,
            thickness=thickness,
            holes=panel.get("holes", []),
            slots=panel.get("slots", []),
            map_fn=map_fn,
        )

        file_path = out_dir / f"{plank_num}.xml"
        file_path.write_text(panel_xml, encoding="utf-8")
        paths.append(file_path)

    return paths


def _side_panel_mapping(hole: dict[str, Any]) -> tuple[float, float] | None:
    """侧板/门板：hole.z → XML X (板长/高度方向)，hole.y → XML Y (板宽/深度方向)。"""
    z = float(hole.get("z", 0))
    y = float(hole.get("y", 0))
    return (z, y)


def _top_panel_mapping(hole: dict[str, Any]) -> tuple[float, float] | None:
    """横板：hole.x → XML X (按板长宽度方向)，hole.y → XML Y (板宽方向)。"""
    x = float(hole.get("x", 0))
    y = float(hole.get("y", 0))
    return (x, y)


def _make_panel_xml(
    name: str,
    length: float,
    width_2d: float,
    thickness: float,
    holes: list[dict[str, Any]],
    slots: list[dict[str, Any]],
    map_fn,
) -> str:
    """构造一块板件的 KDTPanelFormat XML 字符串。"""
    root = ET.Element("KDTPanelFormat")

    panel_elem = ET.SubElement(root, "PANEL")
    _add_text(panel_elem, "PanelLength", str(length))
    _add_text(panel_elem, "PanelWidth", str(width_2d))
    _add_text(panel_elem, "PanelThickness", str(thickness))
    _add_text(panel_elem, "PanelName", name)

    params = ET.SubElement(root, "Params")
    ET.SubElement(params, "Param", Key="L", Value=str(length), Comment="板长")
    ET.SubElement(params, "Param", Key="W", Value=str(width_2d), Comment="板宽")
    ET.SubElement(params, "Param", Key="T", Value=str(thickness), Comment="板厚")

    # 面板轮廓
    outline = ET.SubElement(root, "PanelOutline")
    vertices = [
        (0, length), (0, 0), (width_2d, 0), (width_2d, length), (0, length), (0, length),
    ]
    for vx, vy in vertices:
        vt = ET.SubElement(outline, "Vertex")
        _add_text(vt, "X1", str(vx))
        _add_text(vt, "Y1", str(vy))

    # 孔位
    for hole in holes:
        mapped = map_fn(hole)
        if mapped is None:
            continue
        xml_x, xml_y = mapped
        diam = float(hole.get("diameter", 10))
        depth_2d = float(hole.get("depth", 11))

        cad = ET.SubElement(root, "CAD")
        _add_text(cad, "TypeNo", "1")
        _add_text(cad, "TypeName", "Vertical Hole")
        _add_text(cad, "X1", f"{xml_x:.1f}")
        _add_text(cad, "Y1", f"{xml_y:.1f}")
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
    return dom.toprettyxml(indent="    ")


def _add_text(parent: ET.Element, tag: str, text: str) -> ET.Element:
    elem = ET.SubElement(parent, tag)
    elem.text = text
    return elem