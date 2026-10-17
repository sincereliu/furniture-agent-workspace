"""一台柜子的板件页：有已确认冻结板件就画结构，没有就只画已保存的外形。

不读未保存的输入，不确认布局，不调用板件生成。结构取自冻结文件，
本模块只把它投影成能画的东西——不写任何状态。
"""

from __future__ import annotations

import json
import math
from html import escape
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode

from .assembly_tree import flatten_panels_for_handoff
from .grain_rules import (
    default_grain_axis,
    grain_axis_index,
    grain_axis_of,
)

#: 板件角色 → 页面上的**材质**。整台柜子只有两种材料：柜体一种木纹，门板白色纯色。
#: 角色仍然逐块带在数据里、列在清单里，只是不再各画一个颜色。
MATERIAL_WOOD = "wood"
MATERIAL_WHITE = "white"

MATERIALS: tuple[tuple[str, str], ...] = (
    (MATERIAL_WOOD, "柜体木纹"),
    (MATERIAL_WHITE, "门板白色"),
)

#: 白门的角色：门板与抽屉前脸。其余一律按柜体木纹画。
#: 判据用**角色**而不是分组，所以「归哪种材料」只有这一处定义。
_WHITE_ROLES = frozenset({"door", "drawer_front"})
_WHITE_TYPES = frozenset({"door", "drawer_front"})

_ASSEMBLY_KINDS = (
    ("carcass", "柜体"),
    ("base", "底座"),
    ("fronts", "门板"),
    ("drawers", "抽屉盒"),
)

# 顺纹方向的**默认值**在板件阶段自己的 `grain_rules.py`（那是板件的属性，会进冻结文件）。
# 这里只负责把它换算成「每个面怎么摆贴图」。别把那张表搬回来——页面模块不该是它的家。

#: 一张木纹图在真实世界里铺多长（毫米）。贴图重复次数按板件的实际尺寸算，
#: 尺寸不同的板才算得出同一套纹理比例。
GRAIN_CYCLE_MM = 220.0

#: 盒子几何每个面的 (u 轴, v 轴) 在**板件自己的尺寸**里的下标（x=0 / y=1 / z=2）。
#: u 是贴图横向、v 是贴图纵向。
#:
#: 这张表是**在页面上量出来的**，不是从 three.js 源码推的——推那一次推反了，
#: 侧板木纹由竖变横。可复现的量法：把木纹图画成「一条从左上到右下的对角线」，
#: 看它在板件上朝哪边斜（对角线不会和它转 90° 的样子混淆），再配上左右/等轴视图
#: 数一下横向与纵向的相邻像素差。量出来的结论就是下面这张表：三根轴的 v 分别落在
#: 柜体高(y)、柜体宽(z)、柜体高(y) 上。
_FACE_AXES: dict[str, tuple[int, int]] = {
    "px": (2, 1),
    "nx": (2, 1),
    "py": (0, 2),
    "ny": (0, 2),
    "pz": (0, 1),
    "nz": (0, 1),
}


def panel_grain_axis(panel: Mapping[str, Any]) -> str:
    """这块板的顺纹方向。

    板上带着就用板上的（那是它冻结时定下的属性，可能是这个订单特意改过的）；
    没带（旧冻结文件）按类型取默认。实现在板件阶段的 `grain_rules.py`。
    """
    return grain_axis_of(panel)


def _grain_uv(grain_axis: str, size: Sequence[float]) -> dict[str, Any]:
    """顺纹轴 → **每个面**怎么铺这张木纹图（转多少、重复几次）。

    木纹在贴图上画成一条条横线，线的方向是贴图的 **u 轴**（横向）。所以要让纹路顺着
    柜体的某根轴走，就得让那根轴落在贴图的 u 上：**面的 u 轴不是顺纹轴时，把这个面转
    90°**。每个面单独判，不能整台柜子用一个旋转值——`px`（侧板大面）的 u 是柜体高、
    `py`（背板大面）的 u 是柜体宽，同一个「顺纹沿高」在两张面上要的旋转正好相反。
    这里用一个全局旋转值错过两次，症状是「修好侧板就坏背板」。

    顺纹轴是**板件的属性**（`grain_axis`），这个函数只负责换算成摆法。

    重复次数给的是（按贴图横向、纵向各铺几遍）。纹路画在贴图横向上、又是无方向噪声，
    所以两组数只决定纹理在板上的疏密，不影响横竖。
    """
    want = grain_axis_index(grain_axis)
    faces: dict[str, Any] = {}
    home = ""
    home_area = -1.0
    for face, (u, v) in _FACE_AXES.items():
        rotate = want is not None and u != want
        first, second = (u, v) if not rotate else (v, u)
        faces[face] = {
            "rotation": math.pi / 2 if rotate else 0.0,
            "repeat": [_grain_repeat(size[first]), _grain_repeat(size[second])],
        }
        area = abs(size[u]) * abs(size[v])
        if area > home_area:
            home, home_area = face, area
    #: `home` 是面积最大的那个面——不指着任何一块板的时候，整台柜子就按它铺。
    #: 转不转跟着那个面自己走，所以顺纹方向仍然由板件带的那根轴决定。
    return {
        "axis": grain_axis,
        "rotation": faces[home]["rotation"],
        "home": home,
        "faces": faces,
    }


def _grain_repeat(span_mm: float) -> float:
    """这根轴铺几遍。夹在 1–4.5 之间：太小看不出是木纹，太大就成了密条纹。"""
    return min(4.5, max(1.0, abs(span_mm) / GRAIN_CYCLE_MM))


def panel_material(panel: Mapping[str, Any]) -> str:
    """这块板用哪种材料画。先认角色，再认类型，默认柜体木纹。"""
    if str(panel.get("role") or "") in _WHITE_ROLES:
        return MATERIAL_WHITE
    if str(panel.get("panel_type") or "") in _WHITE_TYPES:
        return MATERIAL_WHITE
    return MATERIAL_WOOD


def panel_structure_view(cabinet: Mapping[str, Any]) -> dict[str, Any]:
    """一台柜子冻结结构 → 页面能画的对象（尺寸、位置、分组、装配）。

    尺寸与位置就是冻结文件里的数，不在这里再算一遍几何。没有 `assemblies`
    的旧结构视为空，不猜。
    """
    if not isinstance(cabinet, Mapping):
        raise ValueError("cabinet structure must be an object")
    cabinet_id = str(cabinet.get("id") or "").strip()
    if not cabinet_id:
        raise ValueError("cabinet structure requires id")
    spec = cabinet.get("spec")
    if not isinstance(spec, Mapping):
        raise ValueError(f"{cabinet_id} requires spec")
    interior = cabinet.get("interior")
    cavity = interior.get("cavity") if isinstance(interior, Mapping) else None
    assemblies = cabinet.get("assemblies")
    if not isinstance(assemblies, Mapping):
        raise ValueError(f"{cabinet_id} requires assemblies")

    kinds = _assembly_kinds(assemblies)
    panels = [_panel_view(item, kinds) for item in flatten_panels_for_handoff(cabinet)]
    shelves = spec.get("shelves") or []
    return {
        "cabinet_id": cabinet_id,
        "envelope_mm": {
            "width": _number(spec.get("width")),
            "depth": _number(spec.get("depth")),
            "height": _number(spec.get("height")),
        },
        "cavity_mm": {
            "width": _number(cavity.get("width")) if isinstance(cavity, Mapping) else None,
            "depth": _number(cavity.get("depth")) if isinstance(cavity, Mapping) else None,
            "height": _number(cavity.get("height")) if isinstance(cavity, Mapping) else None,
        },
        "thickness_mm": {
            "board": _number(spec.get("board_thickness")),
            "back": _number(spec.get("back_thickness")),
            "door": _number(spec.get("door_thickness")),
        },
        "back_mount": _back_mount(cabinet, spec),
        "n_doors": _count(spec.get("n_doors")),
        "drawer_count": _count(spec.get("drawer_count")),
        "shelf_count": len(shelves) if isinstance(shelves, Sequence) else 0,
        "toe_kick_height_mm": _number(spec.get("toe_kick_height")),
        "panels": panels,
        "materials": _materials(panels),
        "assemblies": [
            {"kind": kind, "label": label}
            for kind, label in _ASSEMBLY_KINDS
            if any(panel["assembly"] == kind for panel in panels)
        ],
    }


def _panel_view(panel: Mapping[str, Any], kinds: Mapping[str, str]) -> dict[str, Any]:
    if not isinstance(panel, Mapping):
        raise ValueError("each panel must be an object")
    panel_id = str(panel.get("id") or "").strip()
    if not panel_id:
        raise ValueError("each panel requires id")
    assembly_id = str(panel.get("assembly_id") or "")
    assembly = kinds.get(assembly_id)
    if assembly is None:
        assembly = "drawers" if str(panel.get("panel_type", "")).startswith("drawer") else "carcass"
    size = [
        _number(panel.get("size_x")),
        _number(panel.get("size_y")),
        _number(panel.get("size_z")),
    ]
    # 顺纹轴是板件自己的属性；页面上要能看出哪几块是这个订单特意改过的。
    grain_axis = panel_grain_axis(panel)
    return {
        "id": panel_id,
        "name": str(panel.get("name") or panel_id),
        "role": str(panel.get("role") or ""),
        "panel_type": str(panel.get("panel_type") or ""),
        "assembly": assembly,
        "material": panel_material(panel),
        "material_role": str(panel.get("material_role") or ""),
        "size_mm": size,
        "pos_mm": [
            _number(panel.get("pos_x")),
            _number(panel.get("pos_y")),
            _number(panel.get("pos_z")),
        ],
        "grain": _grain_uv(grain_axis, size),
        #: 该类型的**默认**方向；和 `grain.axis` 不同就说明这块被改过（页面据此标记）。
        "grain_default": default_grain_axis(str(panel.get("panel_type") or "")),
        #: 六个面的 (u 轴, v 轴) 与换算口径（`panel_grain_uv()`），左右跟着投影走。
        "grain_axes": list(_FACE_AXES.items()),
        "grain_cycle_mm": GRAIN_CYCLE_MM,
        "inner_face": str(panel.get("inner_face") or ""),
        "outer_face": str(panel.get("outer_face") or ""),
        "depends_on": [str(item) for item in panel.get("depends_on") or []],
        "contact_count": len(panel.get("joints") or []),
    }


def _assembly_kinds(assemblies: Mapping[str, Any]) -> dict[str, str]:
    """装配 id → 种类。抽屉的盒体板件挂在抽屉自己的 id 上。"""
    kinds: dict[str, str] = {}
    for kind, label in _ASSEMBLY_KINDS:
        unit = assemblies.get(kind)
        if kind == "drawers":
            if not isinstance(unit, list):
                continue
            for drawer in unit:
                if isinstance(drawer, Mapping) and drawer.get("id"):
                    kinds[str(drawer["id"])] = kind
            continue
        if isinstance(unit, Mapping) and unit.get("id"):
            kinds[str(unit["id"])] = kind
    return kinds


def _materials(panels: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """图例：用到的材料、名字、块数。没用到的材料不出现。"""
    counted: dict[str, int] = {}
    for panel in panels:
        material = str(panel["material"])
        counted[material] = counted.get(material, 0) + 1
    return [
        {"material": material, "label": label, "count": counted[material]}
        for material, label in MATERIALS
        if counted.get(material)
    ]


def _back_mount(cabinet: Mapping[str, Any], spec: Mapping[str, Any]) -> dict[str, str]:
    resolution = cabinet.get("back_mount_resolution")
    if not isinstance(resolution, Mapping):
        resolution = {}
    effective = str(resolution.get("effective") or spec.get("back_mount") or "")
    requested = str(resolution.get("requested") or effective)
    return {"requested": requested, "effective": effective}


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"panel structure requires a number, got {value!r}")
    return float(value)


def _count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _json_for_script(payload: object) -> str:
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def _mm(value: float) -> str:
    number = float(value)
    rounded = round(number)
    if abs(number - rounded) < 1e-6:
        return str(int(rounded))
    return f"{number:.1f}"


_PAGE_STYLE = """
:root{
  --ink:#0f172a;--muted:#64748b;--line:#dbe2ec;--accent:#4f46e5;--canvas:#eef1f6;
  font-family:Inter,"Microsoft YaHei",system-ui,-apple-system,"Segoe UI",sans-serif;
  color:var(--ink);
}
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{background:linear-gradient(180deg,#f7f9fc 0,#eef1f6 100%);padding:14px;display:flex;justify-content:center}
.app{width:min(1600px,100%);height:100%;display:grid;grid-template-rows:auto minmax(0,1fr);gap:12px}
.topbar{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap}
h1{margin:0;font-size:20px;font-weight:700}
.badge{margin:6px 0 0;display:inline-block;font-size:11.5px;font-weight:600;color:#475569;background:#f1f5f9;border:1px solid var(--line);border-radius:999px;padding:3px 10px}
.toolbar{display:flex;gap:8px;align-items:center}
.toolbar a,.toolbar button{appearance:none;border:1px solid var(--line);background:#fff;color:var(--ink);border-radius:8px;padding:7px 12px;font:inherit;font-size:12.5px;font-weight:700;text-decoration:none;cursor:pointer}
.toolbar a:hover,.toolbar button:hover{border-color:#94a3b8}
#shutdown-preview{color:#b91c1c}
.workspace{min-height:0;display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:12px}
.stage{position:relative;min-height:420px;background:var(--canvas);border:1px solid var(--line);border-radius:16px;overflow:hidden}
canvas{width:100%;height:100%;display:block;touch-action:none}
.overlay{position:absolute;z-index:3;display:flex;gap:8px;flex-wrap:wrap}
.tools{left:12px;top:12px;flex-direction:column;max-width:calc(100% - 24px)}
.panelbox{background:rgba(255,255,255,.94);border:1px solid var(--line);border-radius:11px;padding:7px;display:flex;gap:6px;flex-wrap:wrap;box-shadow:0 6px 18px rgba(15,23,42,.08)}
.panelbox .title{font-size:11px;font-weight:700;color:var(--muted);align-self:center;padding:0 4px}
.chip{appearance:none;border:1px solid var(--line);background:#fff;color:#334155;border-radius:8px;padding:5px 10px;font:inherit;font-size:12px;font-weight:600;cursor:pointer}
.chip:hover{border-color:#2563eb;color:#1d4ed8}
.chip[aria-pressed="true"]{background:#2563eb;border-color:#2563eb;color:#fff}
.slider{display:flex;align-items:center;gap:8px;font-size:12px;color:#334155;padding:2px 6px}
.slider input{width:120px}
/* 木纹调节：预设一行、滑杆一行，展开后占满 tools 那一列的宽度。 */
.grainbox{display:flex;flex-direction:column;gap:6px;width:100%;padding-top:2px}
.grainline{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.grainline .slider input[type=range]{width:90px}
.grainline input[type=color]{width:34px;height:22px;padding:0;border:1px solid var(--line);border-radius:5px;background:#fff;cursor:pointer}
.hint{left:12px;bottom:12px;background:rgba(255,255,255,.94);border:1px solid var(--line);border-radius:10px;padding:7px 11px;font-size:11.5px;color:#475569;max-width:60%}
.hint b{color:var(--ink)}
.legend{right:12px;bottom:12px;background:rgba(255,255,255,.94);border:1px solid var(--line);border-radius:10px;padding:8px 11px;font-size:11.5px;color:#475569;max-width:40%}
.legend ul{list-style:none;margin:0;padding:0;display:grid;gap:3px}
.legend li{display:flex;align-items:center;gap:6px}
.swatch{width:11px;height:11px;border-radius:3px;border:1px solid rgba(15,23,42,.25);flex:none}
.swatch.wood{background:repeating-linear-gradient(115deg,#c79a63 0 2px,#b98b52 2px 4px,#c99f6c 4px 7px)}
.swatch.white{background:linear-gradient(150deg,#ffffff,#e8eaee)}
/* 图例上的顺纹方向：跟画面一样，横纹转 90°，竖纹不转。 */
.swatch.across{background:repeating-linear-gradient(0deg,#c79a63 0 2px,#b98b52 2px 4px,#c99f6c 4px 7px)}
#hover{position:absolute;pointer-events:none;z-index:4;background:#0f172a;color:#fff;font-size:11px;padding:4px 8px;border-radius:6px;display:none;white-space:nowrap;transform:translate(10px,10px)}
aside{background:#fff;border:1px solid var(--line);border-radius:16px;padding:14px;overflow-y:auto;min-height:0}
aside h2{font-size:12.5px;margin:16px 0 8px;color:#334155}
aside h2:first-child{margin-top:0}
dl.kv{margin:0;display:grid;grid-template-columns:auto 1fr;gap:7px 12px;font-size:12.5px;font-variant-numeric:tabular-nums}
dl.kv dt{color:var(--muted)}
dl.kv dd{margin:0;font-weight:600}
.filters{display:flex;flex-wrap:wrap;gap:6px}
.filters label{display:flex;align-items:center;gap:5px;font-size:12px;border:1px solid var(--line);border-radius:999px;padding:3px 9px;cursor:pointer}
.filters input{margin:0}
table.list{width:100%;border-collapse:collapse;font-size:12px}
table.list th{position:sticky;top:0;background:#fff;text-align:left;color:var(--muted);font-weight:600;padding:6px 5px;border-bottom:1px solid var(--line);z-index:1}
table.list td{padding:5px;border-bottom:1px solid #eef2f7;vertical-align:top}
table.list tbody tr{cursor:pointer}
table.list tbody tr:hover td{background:#f8fafc}
table.list tbody tr[aria-selected="true"] td{background:#eef2ff}
.dot{width:9px;height:9px;border-radius:2px;border:1px solid rgba(15,23,42,.2);flex:none;display:inline-block;margin-right:6px}
.dot.wood{background:repeating-linear-gradient(115deg,#c79a63 0 2px,#b98b52 2px 4px,#c99f6c 4px 7px)}
.dot.white{background:linear-gradient(150deg,#ffffff,#e8eaee)}
.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.role{color:var(--muted);font-size:11px}
p{margin:12px 0 0;font-size:12.5px;line-height:1.6;color:var(--muted)}
.empty{border-left:3px solid #f59e0b;background:#fffbeb;border-radius:8px;padding:10px 12px;font-size:12.5px;line-height:1.7;color:#78350f}
#detail{border:1px solid var(--line);border-radius:11px;padding:10px 12px;margin-top:10px;background:#f8fafc}
#detail strong{display:block;font-size:13px;margin-bottom:6px}
/* 顺纹编辑：改的是板件属性、要重新冻结，所以和「调整木纹」那种只看效果的控件分开。 */
#grain-editor{margin-top:14px;border-top:1px solid var(--line);padding-top:10px}
#grain-editor h2{margin-top:0}
ul.grainpending{list-style:none;margin:8px 0;padding:0;display:grid;gap:4px;font-size:12px}
ul.grainpending li{display:flex;align-items:center;gap:6px;background:#eef2ff;border:1px solid #c7d2fe;border-radius:7px;padding:4px 8px}
ul.grainpending b{font-weight:600}
.grainactions{display:flex;gap:8px;margin-top:8px}
.chip.primary{background:#2563eb;border-color:#2563eb;color:#fff}
.chip.primary:disabled{background:#94a3b8;border-color:#94a3b8;cursor:default}
p.warn{color:#92400e;background:#fffbeb;border-left:3px solid #f59e0b;border-radius:6px;padding:8px 10px;margin-top:8px}
/* 详情里可点的「顺纹方向」：点一下换纹理。 */
.grainrow{cursor:pointer;border-bottom:1px dashed #94a3b8}
.grainrow:hover{color:#1d4ed8;border-bottom-color:#1d4ed8}
@media (max-width:1000px){.workspace{grid-template-columns:minmax(0,1fr)}}
"""


def _render_structure_page(
    *,
    project_id: str,
    label: str,
    structure: Mapping[str, Any],
    share: bool,
    back_href: str,
    shutdown: str,
    badge: str,
    expected_version: str = "",
) -> str:
    title = escape(f"{label} · 柜体结构")
    payload = _json_for_script(structure)
    legend = "".join(
        f'<li><span class="swatch {escape(str(item["material"]), quote=True)}"></span>'
        f'{escape(str(item["label"]))} <span class="num">×{int(item["count"])}</span></li>'
        for item in structure["materials"]
    )
    # 顺纹方向也画在图例上：竖纹不转、横纹转 90°，跟画面用的是同一条规则。
    legend += (
        '<li><span class="swatch wood"></span>顺纹沿高（侧板·门板·背板）</li>'
        '<li><span class="swatch across"></span>顺纹沿宽（层板·顶底·踢脚）</li>'
        '<li><span class="swatch wood"></span>背拉条不限方向</li>'
    )
    filters = "".join(
        f'<label><input type="checkbox" data-assembly="{escape(str(item["kind"]), quote=True)}" checked>'
        f'{escape(str(item["label"]))}</label>'
        for item in structure["assemblies"]
    )
    grain_editor = 'document.getElementById("grain-editor")' if expected_version else "null"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'">
<title>{title}</title>
<style>{_PAGE_STYLE}</style>
</head>
<body>
<main class="app" aria-label="{title}">
  <header class="topbar">
    <div>
      <h1>{title}</h1>
      <p class="badge">{escape(badge)}</p>
    </div>
    <nav class="toolbar">
      <a href="{escape(back_href, quote=True)}">回布局</a>
      {shutdown}
    </nav>
  </header>
  <div class="workspace">
    <section class="stage">
      <canvas id="scene" aria-label="这台柜子已确认的板件结构。拖动转动，滚轮缩放，点板件看尺寸与顺纹方向。"></canvas>
      <div class="overlay tools">
        <div class="panelbox">
          <span class="title">视角</span>
          <button type="button" class="chip" data-view="iso" aria-pressed="true">等轴</button>
          <button type="button" class="chip" data-view="front" aria-pressed="false">正面（门）</button>
          <button type="button" class="chip" data-view="back" aria-pressed="false">背面</button>
          <button type="button" class="chip" data-view="left" aria-pressed="false">左侧</button>
          <button type="button" class="chip" data-view="right" aria-pressed="false">右侧</button>
          <button type="button" class="chip" data-view="top" aria-pressed="false">顶视</button>
        </div>
        <div class="panelbox">
          <span class="title">显示</span>
          <button type="button" class="chip" id="toggle-doors" aria-pressed="true">门板/抽屉面</button>
          <button type="button" class="chip" id="toggle-back" aria-pressed="true">背板</button>
          <button type="button" class="chip" id="toggle-wire" aria-pressed="false">透视门板</button>
          <span class="slider">拆开 <input type="range" id="explode" min="0" max="100" value="0" step="1"></span>
        </div>
      </div>
      <div class="overlay hint"><b>点板件</b>只选中（不改任何东西）· <b>拖动</b>转动 · <b>滚轮</b>缩放。要改纹理，选中后在右侧详情的<b>顺纹方向</b>上点一下：竖纹 ⇄ 横纹。</div>
      <div class="overlay legend"><ul>{legend}</ul></div>
      <div id="hover"></div>
    </section>
    <aside>
      <!-- 选中一块板之后，「详情」要立刻看得见：放在板件清单**上面**，
           不然它落在清单下面、要滚动才看得到（点了一行却像没反应）。 -->
      <div id="detail" hidden></div>
      <!-- 这块是「这一页上还没落盘的改动」，不是顺纹专用的：以后别的板件属性也从这里改、
           一起冻结，所以按钮叫「保存并冻结」而不是「保存顺纹」。没有放弃按钮——再点一次
           就切回去了。 -->
      <div id="grain-editor" hidden>
        <h2>待保存的改动</h2>
        <ul class="grainpending" id="grain-pending"></ul>
        <div class="grainactions">
          <button type="button" class="chip primary" id="grain-save">保存并冻结</button>
        </div>
        <p class="warn">保存会落一个新版本、重新冻结板件，并按规矩作废下游（制造 / BOM / CAD / 交付）——改了板件的属性，那些产物就不再对应当前的板件。</p>
        <p id="grain-status"></p>
      </div>
      <h2>外形与构造</h2>
      <dl class="kv" id="summary"></dl>
      <h2>按装配筛选</h2>
      <div class="filters">{filters}</div>
      <h2>板件（<span id="panel-count">0</span>）</h2>
      <table class="list">
        <thead><tr><th>板件</th><th class="num">尺寸 mm</th><th class="num">位置 mm</th></tr></thead>
        <tbody id="panel-rows"></tbody>
      </table>
      <p>位置是板件原点（左后下角）在柜体坐标里的毫米数。颜色区分材料：柜体木纹，门板白色。选中一块板后，详情里的<b>顺纹方向</b>可以点：<b>竖纹 ⇄ 横纹</b>；改过的在上面列出来，点「保存并冻结」才落盘。</p>
    </aside>
  </div>
</main>
<script id="cabinet-structure" type="application/json">{payload}</script>
<script type="importmap">
{{"imports":{{"three":"/vendor/three/0.186.0/three.module.js"}}}}
</script>
<script type="module">
import {{ mountCabinetStructure }} from "/layout-view/cabinet_structure.js";
// 挂到 window 上，方便在控制台核对：`page.__test`。
const page = mountCabinetStructure({{
  canvas: document.getElementById("scene"),
  payload: JSON.parse(document.getElementById("cabinet-structure").textContent),
  hover: document.getElementById("hover"),
  summary: document.getElementById("summary"),
  count: document.getElementById("panel-count"),
  rows: document.getElementById("panel-rows"),
  detail: document.getElementById("detail"),
  filters: document.querySelectorAll("[data-assembly]"),
  viewButtons: document.querySelectorAll("[data-view]"),
  toggles: {{
    doors: document.getElementById("toggle-doors"),
    back: document.getElementById("toggle-back"),
    wire: document.getElementById("toggle-wire"),
    explode: document.getElementById("explode"),
  }},
  grainSave: {{
    url: "/api/project/{escape(project_id, quote=True)}/cabinets/{escape(str(structure["cabinet_id"]), quote=True)}/grain",
    version: {json.dumps(expected_version)},
    editor: {grain_editor},
    pending: document.getElementById("grain-pending"),
    save: document.getElementById("grain-save"),
    status: document.getElementById("grain-status"),
  }},
}});
window.page = page;
function pulse(){{
  fetch("/api/preview/presence", {{method:"POST", cache:"no-store", keepalive:true}}).catch(()=>{{}});
}}
pulse();
setInterval(pulse, 1000);
const shutdownButton = document.getElementById("shutdown-preview");
if (shutdownButton) {{
  shutdownButton.addEventListener("click", async () => {{
    shutdownButton.disabled = true;
    try {{ await fetch("/api/preview/shutdown", {{method:"POST", cache:"no-store"}}); }} catch (error) {{}}
  }});
}}
</script>
</body>
</html>
"""


def _render_envelope_page(
    *,
    cabinet: Mapping[str, Any],
    stage_note: str = "",
    share: bool,
    back_href: str,
    shutdown: str,
) -> str:
    """还没有板件结构：只画布局里已经保存的外形。"""
    label = str(cabinet.get("label") or cabinet["id"])
    width = _mm(float(cabinet["width"]))
    depth = _mm(float(cabinet["depth"]))
    height = _mm(float(cabinet["height"]))
    geometry = _json_for_script(
        {
            "width": float(cabinet["width"]),
            "depth": float(cabinet["depth"]),
            "height": float(cabinet["height"]),
        }
    )
    note = (
        stage_note
        or "这台柜子的板件还没确认：页上只有布局里已经保存的外形。"
        "生成板件后，这里会换成能转、能拆开看的结构。"
    )
    badge = "只读分享 · 链接可转发" if share else "这一台的外形 · 尺寸在布局里改"
    title = escape(f"{label} · 板件")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'">
<title>{title}</title>
<style>{_PAGE_STYLE}</style>
</head>
<body>
<main class="app" aria-label="{title}">
  <header class="topbar">
    <div>
      <h1>{title}</h1>
      <p class="badge">{escape(badge)}</p>
    </div>
    <nav class="toolbar">
      <a href="{escape(back_href, quote=True)}">回布局</a>
      {shutdown}
    </nav>
  </header>
  <div class="workspace">
    <section class="stage">
      <canvas id="scene" aria-label="这一台柜子的外形。绿面是正面。拖动可转动。"></canvas>
    </section>
    <aside>
      <h2>外形</h2>
      <dl class="kv">
        <dt>宽</dt><dd>{width} mm</dd>
        <dt>深</dt><dd>{depth} mm</dd>
        <dt>高</dt><dd>{height} mm</dd>
      </dl>
      <p class="empty">{escape(note)}</p>
      <p>这三个数是布局里已经保存的外形。要改，回布局页改完再进来。</p>
      <p>绿面是柜门这一面。</p>
    </aside>
  </div>
</main>
<script id="cabinet" type="application/json">{geometry}</script>
<script type="importmap">
{{"imports":{{"three":"/vendor/three/0.186.0/three.module.js"}}}}
</script>
<script type="module">
import * as THREE from "three";
import {{ OrbitControls }} from "/vendor/three/0.186.0/OrbitControls.js";
const cabinet = JSON.parse(document.getElementById("cabinet").textContent);
const canvas = document.getElementById("scene");
const renderer = new THREE.WebGLRenderer({{canvas, antialias:true}});
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xeef1f6);
const camera = new THREE.PerspectiveCamera(40, 1, 1, 100000);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
const width = cabinet.width, depth = cabinet.depth, height = cabinet.height;
const body = new THREE.Mesh(
  new THREE.BoxGeometry(width, height, depth),
  new THREE.MeshStandardMaterial({{color:0x8ea9e8, roughness:0.72}})
);
body.position.y = height / 2;
scene.add(body);
const front = new THREE.Mesh(
  new THREE.PlaneGeometry(width, height),
  new THREE.MeshBasicMaterial({{color:0x047857, transparent:true, opacity:0.45, side:THREE.DoubleSide}})
);
front.position.set(0, height / 2, depth / 2 + 1);
scene.add(front);
scene.add(new THREE.AmbientLight(0xffffff, 0.75));
const sun = new THREE.DirectionalLight(0xffffff, 1.1);
sun.position.set(width, height * 2, depth * 2);
scene.add(sun);
const radius = Math.hypot(width, height, depth);
camera.position.set(width * 0.35, height * 0.72, radius * 0.95);
controls.target.set(0, height * 0.45, 0);
controls.update();
function frame(){{
  const w = canvas.clientWidth || 960;
  const h = canvas.clientHeight || 640;
  renderer.setSize(w, h, false);
  camera.aspect = w / Math.max(h, 1);
  camera.updateProjectionMatrix();
}}
function draw(){{
  frame();
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(draw);
}}
draw();
new EventSource("/api/preview/presence/stream");
const shutdownButton = document.getElementById("shutdown-preview");
if (shutdownButton) {{
  shutdownButton.addEventListener("click", async () => {{
    shutdownButton.disabled = true;
    try {{ await fetch("/api/preview/shutdown", {{method:"POST", cache:"no-store"}}); }} catch (error) {{}}
  }});
}}
</script>
</body>
</html>
"""


def render_cabinet_panel_page(
    project_id: str,
    cabinet: Mapping[str, Any],
    *,
    share: bool = False,
    structure: Mapping[str, Any] | None = None,
    stage_note: str = "",
    expected_version: str = "",
) -> str:
    """这一台的板件页。

    `structure` 是板件结构的投影（`panel_structure_view()` 的结果，来自已确认冻结板件或
    当前待确认候选板件）。给了就画结构，没给只画外形——**页面不自己去读冻结文件，也不替
    板件阶段生成**。`stage_note` 在无结构时说明原因，在有结构（如待确认草稿）时作为徽章提示。

    `expected_version` 是这份**已确认板件**画面的版本号（`open_preview.panel_version()`），
    交给页面在「保存并冻结」时带回去：服务端据此拒绝拿过期画面覆盖新内容。
    只读分享（`share`）或待确认草稿不给它，那一页也不开放顺纹保存入口。
    """
    back_query = {"room": cabinet["room_id"], "item": cabinet["id"]}
    if share:
        back_query["mode"] = "view"
    back_href = (
        f"/api/project/{escape(project_id, quote=True)}/preview?"
        f"{urlencode(back_query)}"
    )
    shutdown = "" if share else '<button type="button" id="shutdown-preview">退出</button>'
    label = str(cabinet.get("label") or cabinet["id"])
    if structure is None:
        return _render_envelope_page(
            cabinet=cabinet,
            stage_note=stage_note,
            share=share,
            back_href=back_href,
            shutdown=shutdown,
        )
    badge = (
        "只读分享 · 链接可转发"
        if share
        else (
            stage_note
            or "已确认冻结板件 · 点板件看尺寸，点「顺纹方向」可改；透视看内部"
        )
    )
    return _render_structure_page(
        project_id=project_id,
        label=label,
        structure=structure,
        share=share,
        back_href=back_href,
        shutdown=shutdown,
        badge=badge,
        expected_version=expected_version,
    )
