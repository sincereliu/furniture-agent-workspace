"""抽屉滑轨系统的几何规则：抽芯档、后缝下限、轨腔高度、格高与上下间隙。

这里只有**查表**：给定滑轨系统与格高，输出该用多少上下间隙、盒深取哪一档。
没有任何"按柜型猜"的分支，也没有随柜体变化的默认毫米——数值都是车间口径，随板件冻结。

口径来源：references/drawer-runner-rules.md。
"""

from __future__ import annotations

from math import floor
from typing import Any

RUNNER_SIDE_MOUNT = "side_mount"
RUNNER_UNDERMOUNT = "undermount"
RUNNERS: tuple[str, ...] = (RUNNER_SIDE_MOUNT, RUNNER_UNDERMOUNT)
DEFAULT_RUNNER = RUNNER_SIDE_MOUNT

#: 抽屉区贴哪一头：贴柜内底面，或贴顶板下表面。
DRAWER_ANCHOR_BOTTOM = "bottom"
DRAWER_ANCHOR_TOP = "top"
DRAWER_ANCHORS: tuple[str, ...] = (DRAWER_ANCHOR_BOTTOM, DRAWER_ANCHOR_TOP)

#: 盒高按 10 取整（车间口径）。
BOX_HEIGHT_STEP_MM = 10.0

#: 每个滑轨系统的车间口径。
#:
#: - `depth_ladder_mm`：抽芯深度档（不含抽面），盒深必须落在档上；
#: - `min_rear_clearance_mm`：抽屉背板外表面到柜背的下限，**必须严格大于**；
#: - `side_clearance_mm`：抽盒与柜体的**每侧**间隙，省略提案时按它展开；
#: - `bottom_raise_mm`：底板底面到盒体底面的距离（托底轨藏轨用）；
#: - `cell_gaps`：格高 → (下间隙, 上间隙)，左开右闭、按顺序匹配；超出最后一档用
#:   `gaps_above_max`；
#: - `min_cell_mm`：低于此值报"空间过低"（警告，不拦）；
#: - `max_cell_mm`：高于此值报"空间过高"（警告，不拦），`None` 表示不设上限。
PROFILES: dict[str, dict[str, Any]] = {
    RUNNER_SIDE_MOUNT: {
        "label": "三节轨",
        "depth_ladder_mm": (200.0, 250.0, 300.0, 350.0, 400.0, 450.0, 500.0),
        "side_clearance_mm": 13.0,
        "min_rear_clearance_mm": 0.0,
        "bottom_raise_mm": 0.0,
        "cell_gaps": (
            (130.0, 10.0, 10.0),
            (220.0, 10.0, 20.0),
            (260.0, 20.0, 20.0),
        ),
        "gaps_above_max": (20.0, 20.0),
        "min_cell_mm": 70.0,
        "max_cell_mm": 260.0,
    },
    RUNNER_UNDERMOUNT: {
        "label": "托底轨",
        "depth_ladder_mm": (240.0, 290.0, 340.0, 390.0, 440.0, 490.0),
        "side_clearance_mm": 6.5,
        "min_rear_clearance_mm": 10.0,
        "bottom_raise_mm": 11.0,
        "cell_gaps": (
            (220.0, 20.0, 10.0),
        ),
        "gaps_above_max": (20.0, 20.0),
        "min_cell_mm": 80.0,
        "max_cell_mm": None,
    },
}


def admit_runner(value: Any) -> str:
    """规范滑轨系统枚举。只认规范名，不做同义词。"""
    text = str(value if value is not None else DEFAULT_RUNNER).strip()
    if text not in PROFILES:
        raise ValueError("drawer_runner must be one of: " + ", ".join(RUNNERS))
    return text


def admit_anchor(value: Any) -> str:
    """规范抽屉区贴哪一头。只认规范名，不做同义词。"""
    text = str(value if value is not None else DRAWER_ANCHOR_BOTTOM).strip()
    if text not in DRAWER_ANCHORS:
        raise ValueError("drawer_anchor must be one of: " + ", ".join(DRAWER_ANCHORS))
    return text


def profile(runner: str) -> dict[str, Any]:
    try:
        return PROFILES[runner]
    except KeyError as exc:
        raise ValueError(f"unknown drawer_runner: {runner}") from exc


def min_rear_clearance(runner: str) -> float:
    """后缝下限（实际后缝必须严格大于这个值）。"""
    return float(profile(runner)["min_rear_clearance_mm"])


def side_clearance(runner: str) -> float:
    """抽盒与柜体的每侧间隙（省略提案时按它展开）。"""
    return float(profile(runner)["side_clearance_mm"])


def bottom_raise(runner: str) -> float:
    """底板底面到盒体底面的距离。"""
    return float(profile(runner)["bottom_raise_mm"])


def depth_ladder(runner: str) -> tuple[float, ...]:
    return tuple(profile(runner)["depth_ladder_mm"])


def runner_label(runner: str) -> str:
    return str(profile(runner)["label"])


def cell_gaps(runner: str, cell_height: float) -> tuple[float, float]:
    """格高 → (下间隙, 上间隙)。超出最后一档时按 `gaps_above_max`。"""
    item = profile(runner)
    for upper_bound, lower, upper in item["cell_gaps"]:
        if cell_height <= float(upper_bound):
            return float(lower), float(upper)
    lower, upper = item["gaps_above_max"]
    return float(lower), float(upper)


def cell_warnings(runner: str, cell_height: float) -> list[dict[str, str]]:
    """格高落在车间经验区间之外时的提示（警告，不拦确认）。"""
    item = profile(runner)
    label = runner_label(runner)
    warnings: list[dict[str, str]] = []
    min_cell = float(item["min_cell_mm"])
    if cell_height < min_cell:
        warnings.append(
            {
                "code": "DRAWER_CELL_TOO_LOW",
                "message": (
                    f"{label}：格高 {cell_height:g}mm 低于 {min_cell:g}mm，空间过低；"
                    "请加大空间或改做法"
                ),
            }
        )
    max_cell = item["max_cell_mm"]
    if max_cell is not None and cell_height > float(max_cell):
        warnings.append(
            {
                "code": "DRAWER_CELL_TOO_HIGH",
                "message": (
                    f"{label}：格高 {cell_height:g}mm 超过 {float(max_cell):g}mm，"
                    "空间过高；建议分两抽或改做法"
                ),
            }
        )
    return warnings


def floor_to_step(value: float, step: float = BOX_HEIGHT_STEP_MM) -> float:
    """向下取到 step 的整倍数（盒高按 10 取整）。"""
    return floor(value / step) * step


def drawer_panels_per_instance(front_board: bool = True) -> int:
    """一抽出几块板：抽面 + 左右侧板 + 背板 + 底板（+ 前板）。

    前板可能有、可能没有：没有时抽面直接当盒体前墙。
    """
    return 6 if front_board else 5


def pick_box_depth(runner: str, available_depth: float, rear_clearance: float) -> float:
    """在抽芯档里取能满足后缝要求的最深一档。

    `available_depth` = 内深 − 前部占用；`rear_clearance` = 提案给的最小后缝要求。
    实际后缝是**结果**（可装深度 − 盒深），必须严格大于该系统的下限。
    """
    limit = max(float(rear_clearance), min_rear_clearance(runner))
    fits = [
        value for value in depth_ladder(runner)
        if available_depth - value > limit
    ]
    if not fits:
        raise ValueError(
            f"{runner_label(runner)}：内深减前部占用后 {available_depth:g}mm，"
            f"放不下任何一档抽芯（需要后缝 > {limit:g}mm）；请加大柜深或改做法"
        )
    return max(fits)
