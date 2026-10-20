"""顺纹方向：板件自己的一个属性，由板件阶段拥有。

以前这条规则写在板件**页**的渲染模块里（`cabinet_panel_page.py`），于是它只是"画的时候
算一下"，进不了数据、也改不了。但它决定的是「这块板顺纹沿柜体哪根轴」——开料、排版、
下料方向都要用它，所以是板件阶段的属性，就该跟尺寸、位置一样进冻结文件。

默认值只由**板件类型**决定，不看尺寸：常规柜里同样类型的板件顺纹方向是一致的。
"""

from __future__ import annotations

from typing import Any, Mapping

#: 顺纹方向：柜体坐标里的一根轴。`none` = 这块板不限纹理方向。
GRAIN_NONE = "none"
GRAIN_WIDTH = "x"
GRAIN_HEIGHT = "z"

#: 允许出现在板件上的取值。`none` 之外的 `y`（沿深）也是合法的——
#: 有些订单会特意要求顶板顺纹走深度（例如窄而深的台面），默认表里不用，但可以改。
GRAIN_AXES: tuple[str, ...] = ("x", "y", "z", GRAIN_NONE)

#: 板件类型 → 顺纹方向（默认）。常规柜子的口径：
#:
#: - 左右侧板、中立板、门板、抽面、背板 → **沿高 Z**（柜体立起来的那根方向）；
#: - 层板、顶板、底板、踢脚板 → **沿宽 X**（横着的那根方向）；
#: - 背拉条 → **不限**。
#:
#: 没列到的类型按沿高算：常规柜子里没点名的板件基本都是立着的侧向板件，
#: 沿高是里面错得最少的那个答案。
GRAIN_BY_TYPE: dict[str, str] = {
    "side": GRAIN_HEIGHT,
    "divider": GRAIN_HEIGHT,
    "door": GRAIN_HEIGHT,
    "drawer_front": GRAIN_HEIGHT,
    "drawer_side": GRAIN_HEIGHT,
    "drawer_back": GRAIN_HEIGHT,
    "back": GRAIN_HEIGHT,
    "fixed_shelf": GRAIN_WIDTH,
    "movable_shelf": GRAIN_WIDTH,
    "top": GRAIN_WIDTH,
    "bottom": GRAIN_WIDTH,
    "toe_kick": GRAIN_WIDTH,
    "back_rail": GRAIN_NONE,
}

#: 顺纹轴 → 板件尺寸里的下标（x=0 / y=1 / z=2）。
_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


def default_grain_axis(panel_type: str) -> str:
    """这块板默认的顺纹方向。改过一次之后，板件上带着的是改过的值。"""
    return GRAIN_BY_TYPE.get(str(panel_type or ""), GRAIN_HEIGHT)


def normalize_grain_axis(axis: Any, panel_type: str = "") -> str:
    """规整一个顺纹轴。空值/不认识的值退回该类型的默认，不顺从奇怪输入。"""
    text = str(axis or "").strip().lower()
    if text in GRAIN_AXES:
        return text
    if not text:
        return default_grain_axis(panel_type)
    raise ValueError(f"grain axis must be one of {', '.join(GRAIN_AXES)}, got {axis!r}")


def grain_axis_index(axis: str) -> int | None:
    """顺纹轴 → 尺寸下标；`不限` 返回 `None`（它不对应任何一根轴）。"""
    if axis == GRAIN_NONE:
        return None
    if axis not in _AXIS_INDEX:
        raise ValueError(f"grain axis must be one of {', '.join(GRAIN_AXES)}, got {axis!r}")
    return _AXIS_INDEX[axis]


def grain_axis_of(panel: Mapping[str, Any]) -> str:
    """读一块板的顺纹方向：板上带什么就是什么，没带（旧冻结文件）按类型取默认。"""
    if not isinstance(panel, Mapping):
        raise ValueError("panel must be an object")
    panel_type = str(panel.get("panel_type") or "")
    raw = panel.get("grain_axis")
    if raw is None or str(raw).strip() == "":
        return default_grain_axis(panel_type)
    return normalize_grain_axis(raw, panel_type)
