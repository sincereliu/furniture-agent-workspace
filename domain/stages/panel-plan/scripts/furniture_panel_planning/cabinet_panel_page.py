"""把一台柜子的板件结构投影成页面能画的数据。

页面 HTML 在网页模块 furniture_web.panel_page。这里不确认布局，不生成门和层板，不写状态。
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .assembly_tree import flatten_panels_for_handoff
from .construction_geometry import door_hinge_locks
from .grain_rules import (
    default_grain_axis,
    grain_axis_index,
    grain_axis_of,
)
from .panel_spec import FurnitureSpec
from .structure_planning import CabinetStructure

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
    locked = _door_hinge_locks(cabinet, spec)
    panels = [
        _panel_view(item, kinds, locked) for item in flatten_panels_for_handoff(cabinet)
    ]
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


def _panel_view(
    panel: Mapping[str, Any],
    kinds: Mapping[str, str],
    hinge_locked: frozenset[str] = frozenset(),
) -> dict[str, Any]:
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
        #: 门板往哪条竖边开。空 = 还没定（单开腔没给），页面上这扇门不转，并给「左开/右开」两个选择。
        "hinge_side": str(panel.get("door_hinge_side") or ""),
        #: 对开腔里的门：铰链侧被几何定死，页面上不给改，只显示结果。
        "hinge_locked": panel_id in hinge_locked,
    }


def _door_hinge_locks(
    cabinet: Mapping[str, Any],
    spec: Mapping[str, Any],
) -> frozenset[str]:
    """对开腔里的门 id——它们的铰链侧由几何决定，页面上不给单独改。

    腔怎么切**不在页面里算**：直接用板件阶段的 `construction_geometry.door_hinge_locks()`，
    免得"被中立板切开的内空"在页面和板件各有一份、哪天漂了都不知道。
    这里算出来只是为了把按钮关掉，免得让人点了才被拒；真正的裁决在保存时
    （`project_layout_edit._resolve_door_hinges`）。
    """
    cabinet_id = str(cabinet.get("id") or "")
    try:
        admitted = FurnitureSpec.from_dict(dict(spec))
        structure = CabinetStructure.from_spec(admitted)
        locks = door_hinge_locks(admitted, structure)
    except (TypeError, ValueError):
        # 冻结文件读不动时宁可都让人改，也别因为算不出来把按钮全锁死。
        return frozenset()
    return frozenset(
        f"{cabinet_id}__{role}" for role, locked in locks.items() if locked
    )


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
