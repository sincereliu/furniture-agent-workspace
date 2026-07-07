"""开料优化器 — 将拆单后的板件清单优化到标准板材上

职责:
  ✅ 输入: List[PanelRecord]
  ✅ 输出: List[CuttingPlan] (每张板材的排样方案)
  ❌ 不关心五金/打孔（那是 panelizer 的职责）

算法: Guillotine Strip Packing (FFDH + 余料管理)
  1. 按材质/厚度分组
  2. 每组内按面积降序排列
  3. 对标准板材 (2440×1220mm) 执行条带填充
  4. 每块板件四周预留锯缝 (4mm)
  5. 输出每张板材的利用率、排样图、余料列表
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from furniture_schema.panel import PanelRecord


# ── 标准板材规格 ──────────────────────────────────────────────
DEFAULT_RAW_BOARD = {
    "name": "标准免漆板",
    "length_mm": 2440,  # 长边 (常为板材纹理方向)
    "width_mm": 1220,   # 短边
    "thickness_mm": 18,
}

DEFAULT_RAW_BOARDS: Dict[str, dict] = {
    "18mm免漆板": {"length_mm": 2440, "width_mm": 1220, "thickness_mm": 18},
    "9mm薄板":   {"length_mm": 2440, "width_mm": 1220, "thickness_mm": 9},
}

# 锯缝
SAW_KERF_MM = 4.0


# ── 数据结构 ──────────────────────────────────────────────────
@dataclass
class CutPiece:
    """单块开料后的板件记录"""
    label: str
    name: str
    original_length_mm: float
    original_width_mm: float
    cut_length_mm: float    # 含锯缝余量
    cut_width_mm: float     # 含锯缝余量
    x_mm: float = 0.0       # 在板材上的 X 坐标
    y_mm: float = 0.0       # 在板材上的 Y 坐标
    rotated: bool = False   # 是否旋转90度


@dataclass
class CuttingPlan:
    """单张板材的排样方案"""
    board_name: str
    board_length_mm: float
    board_width_mm: float
    board_thickness_mm: float
    pieces: List[CutPiece] = field(default_factory=list)
    used_area_mm2: float = 0.0
    total_area_mm2: float = 0.0
    waste_area_mm2: float = 0.0
    utilization_pct: float = 0.0


# ── 开料优化入口 ──────────────────────────────────────────────
def optimize_cutting(
    panels: List[PanelRecord],
    raw_boards: Dict[str, dict] | None = None,
    saw_kerf_mm: float = SAW_KERF_MM,
) -> List[CuttingPlan]:
    """将板件列表优化到标准板材上。

    Args:
        panels: 拆单后的板件清单
        raw_boards: 标准板材规格字典 {材质名: {length, width, thickness}}
        saw_kerf_mm: 锯缝宽度

    Returns:
        每张板材的排样方案列表
    """
    if raw_boards is None:
        raw_boards = DEFAULT_RAW_BOARDS

    # 1. 按材质分组
    groups: Dict[str, List[PanelRecord]] = {}
    for p in panels:
        material = p.material or "18mm免漆板"
        groups.setdefault(material, []).append(p)

    plans: List[CuttingPlan] = []

    for material, group in groups.items():
        board_spec = raw_boards.get(material, DEFAULT_RAW_BOARD)
        board_l = float(board_spec["length_mm"])
        board_w = float(board_spec["width_mm"])
        board_t = float(board_spec.get("thickness_mm", 18))

        # 2. 生成 CutPiece 列表（含锯缝）
        pieces = _panels_to_cut_pieces(group, saw_kerf_mm)

        # 3. 按面积降序排列
        pieces.sort(key=lambda cp: cp.cut_length_mm * cp.cut_width_mm, reverse=True)

        # 4. FFDH 排样
        group_plans = _ffdh_packing(pieces, board_l, board_w, material, board_t, saw_kerf_mm)
        plans.extend(group_plans)

    # 5. 计算利用率
    for plan in plans:
        plan.total_area_mm2 = plan.board_length_mm * plan.board_width_mm
        plan.used_area_mm2 = sum(
            p.original_length_mm * p.original_width_mm for p in plan.pieces
        )
        plan.waste_area_mm2 = plan.total_area_mm2 - plan.used_area_mm2
        plan.utilization_pct = round(
            plan.used_area_mm2 / plan.total_area_mm2 * 100, 1
        ) if plan.total_area_mm2 > 0 else 0.0

    return plans


# ── FFDH 条带填充 ────────────────────────────────────────────
def _ffdh_packing(
    pieces: List[CutPiece],
    board_length_mm: float,
    board_width_mm: float,
    material: str,
    board_thickness_mm: float,
    saw_kerf_mm: float,
) -> List[CuttingPlan]:
    """First-Fit Decreasing Height 条带优化排样。

    每张板材按宽度方向切条带，条带内按长度方向排板件。
    当当前条带放不下下一块板时，开启新条带。
    当板材放不下下一条带时，开启新板材。
    """
    plans: List[CuttingPlan] = []
    current_board_pieces: List[CutPiece] = []
    current_y = 0.0  # 当前条带的 Y 起点
    current_strip_height = 0.0  # 当前条带高度
    current_strip_x_end = 0.0  # 当前条带已用的 X 长度

    remaining = list(pieces)

    def _start_new_board():
        nonlocal current_y, current_strip_height, current_strip_x_end, current_board_pieces
        current_y = 0.0
        current_strip_height = 0.0
        current_strip_x_end = 0.0
        current_board_pieces = []

    _start_new_board()

    while remaining:
        placed = False
        for i, piece in enumerate(remaining):
            piece_len = piece.cut_length_mm
            piece_wid = piece.cut_width_mm

            # 尝试原方向
            for (pl, pw) in ((piece_len, piece_wid), (piece_wid, piece_len)):
                if pl == piece_len and pw == piece_wid:
                    rotated = False
                else:
                    rotated = True

                # 检查当前条带空间
                if current_strip_height == 0:
                    # 新条带
                    if current_y + pw <= board_width_mm and pl <= board_length_mm:
                        # 可以开启新条带
                        current_strip_height = pw
                        current_strip_x_end = 0
                        piece.x_mm = 0
                        piece.y_mm = current_y
                        piece.rotated = rotated
                        current_strip_x_end = pl
                        current_board_pieces.append(piece)
                        remaining.pop(i)
                        placed = True
                        break
                else:
                    # 现有条带
                    if pw <= current_strip_height and current_strip_x_end + pl <= board_length_mm:
                        piece.x_mm = current_strip_x_end
                        piece.y_mm = current_y
                        piece.rotated = rotated
                        current_strip_x_end += pl
                        current_board_pieces.append(piece)
                        remaining.pop(i)
                        placed = True
                        break

            if placed:
                break

        if not placed:
            # 当前条带排不下任何剩余板件，尝试新条带
            if current_strip_height > 0:
                current_y += current_strip_height + saw_kerf_mm
                current_strip_height = 0
                current_strip_x_end = 0
                # 检查是否还能开新条带
                if current_y < board_width_mm:
                    continue

            # 板材满，保存当前方案，开新板
            if current_board_pieces:
                plans.append(CuttingPlan(
                    board_name=f"{material} #{len(plans)+1}",
                    board_length_mm=board_length_mm,
                    board_width_mm=board_width_mm,
                    board_thickness_mm=board_thickness_mm,
                    pieces=list(current_board_pieces),
                ))
            _start_new_board()

    # 保存最后一张板材
    if current_board_pieces:
        plans.append(CuttingPlan(
            board_name=f"{material} #{len(plans)+1}",
            board_length_mm=board_length_mm,
            board_width_mm=board_width_mm,
            board_thickness_mm=board_thickness_mm,
            pieces=list(current_board_pieces),
        ))

    return plans


# ── 内部辅助 ─────────────────────────────────────────────────
def _panels_to_cut_pieces(
    panels: List[PanelRecord],
    saw_kerf_mm: float,
) -> List[CutPiece]:
    """将 PanelRecord 转为含锯缝的 CutPiece。
    注意：板件开料尺寸已考虑封边量，锯缝在此之上添加。
    """
    pieces: List[CutPiece] = []
    for p in panels:
        pieces.append(CutPiece(
            label=p.label,
            name=p.name,
            original_length_mm=p.length_mm,
            original_width_mm=p.width_mm,
            cut_length_mm=p.length_mm + saw_kerf_mm,
            cut_width_mm=p.width_mm + saw_kerf_mm,
        ))
    return pieces


# ── 开料报告输出 ────────────────────────────────────────────
@dataclass
class CutListReport:
    """开料清单报告"""
    plans: List[CuttingPlan]
    total_boards: int
    total_waste_area_m2: float
    overall_utilization_pct: float

    @classmethod
    def from_plans(cls, plans: List[CuttingPlan]) -> "CutListReport":
        total_boards = len(plans)
        total_waste = sum(p.waste_area_mm2 for p in plans)
        total_area = sum(p.total_area_mm2 for p in plans)
        overall = round(
            (1 - total_waste / total_area) * 100, 1
        ) if total_area > 0 else 0.0
        return cls(
            plans=plans,
            total_boards=total_boards,
            total_waste_area_m2=round(total_waste / 1_000_000, 4),
            overall_utilization_pct=overall,
        )


def format_cut_layout_ascii(plan: CuttingPlan, scale_cells: int = 40) -> str:
    """将单张板材排样转为 ASCII 可视化图。scale_cells=每格mm数"""
    cols = int(plan.board_length_mm / scale_cells) + 1
    rows = int(plan.board_width_mm / scale_cells) + 1
    grid = [[" " for _ in range(cols)] for _ in range(rows)]
    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    piece_map = {}

    for idx, piece in enumerate(plan.pieces):
        label = labels[idx % len(labels)]
        c_start = int(piece.x_mm / scale_cells)
        c_end = int((piece.x_mm + piece.original_length_mm) / scale_cells)
        r_start = int(piece.y_mm / scale_cells)
        r_end = int((piece.y_mm + piece.original_width_mm) / scale_cells)
        c_end = min(c_end, cols - 1)
        r_end = min(r_end, rows - 1)
        if c_start >= cols or r_start >= rows:
            continue
        for r in range(r_start, r_end):
            for c in range(c_start, c_end):
                if 0 <= r < rows and 0 <= c < cols:
                    grid[r][c] = label
        piece_map[label] = (piece, idx)

    board_l_cm = plan.board_length_mm / 10
    board_w_cm = plan.board_width_mm / 10
    divider = "─" * cols
    lines = []
    lines.append(f"┌{divider}┐  {plan.board_name}")
    lines.append(f"│ 尺寸: {board_l_cm:.0f}×{board_w_cm:.0f}cm (长{plan.board_length_mm:.0f}×宽{plan.board_width_mm:.0f}mm) │")
    lines.append(f"│ 利用率: {plan.utilization_pct}%, {len(plan.pieces)}块 │")
    lines.append(f"├{divider}┤")
    for r in range(rows - 1, -1, -1):
        line = "│" + "".join(grid[r]) + "│"
        lines.append(line)
    lines.append(f"└{divider}┘")
    lines.append("图例:")
    for label in sorted(piece_map.keys()):
        piece, _ = piece_map[label]
        rot = " [旋]" if piece.rotated else ""
        lines.append(f"  {label} = {piece.name} ({piece.original_length_mm:.0f}×{piece.original_width_mm:.0f}mm){rot}")
    return "\n".join(lines)


def render_cut_layout_png(plan: CuttingPlan, output_path: str | Path) -> Path:
    """用 matplotlib 生成板材排样 PNG 图。每个板件用不同颜色矩形标注。

    Args:
        plan: 单张板材排样方案
        output_path: 输出图片路径 (.png)

    Returns:
        输出文件路径
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from pathlib import Path as _Path

    output_path = _Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(14, 8))
    board_l = plan.board_length_mm
    board_w = plan.board_width_mm

    ax.set_xlim(0, board_l)
    ax.set_ylim(0, board_w)
    ax.set_aspect("equal")
    ax.set_xlabel(f"长度方向 (mm)  — 板材总长 {board_l:.0f}mm")
    ax.set_ylabel(f"宽度方向 (mm)  — 板材总宽 {board_w:.0f}mm")
    ax.set_title(
        f"{plan.board_name} | 利用率 {plan.utilization_pct}% | {len(plan.pieces)}块",
        fontsize=13, fontweight="bold",
    )
    ax.grid(True, alpha=0.3, linestyle="--")

    # 绘制板材外框
    board_rect = patches.Rectangle(
        (0, 0), board_l, board_w, fill=False, edgecolor="black", linewidth=2, linestyle="-",
    )
    ax.add_patch(board_rect)

    # 颜色映射
    colors = [
        "#4CAF50", "#2196F3", "#FF9800", "#9C27B0", "#F44336",
        "#00BCD4", "#FFEB3B", "#795548", "#607D8B", "#E91E63",
        "#3F51B5", "#009688", "#CDDC39", "#FF5722", "#673AB7",
    ]

    for idx, piece in enumerate(plan.pieces):
        color = colors[idx % len(colors)]
        rect = patches.Rectangle(
            (piece.x_mm, piece.y_mm),
            piece.original_length_mm,
            piece.original_width_mm,
            fill=True, facecolor=color, alpha=0.7, edgecolor="black", linewidth=1,
        )
        ax.add_patch(rect)

        # 标签
        center_x = piece.x_mm + piece.original_length_mm / 2
        center_y = piece.y_mm + piece.original_width_mm / 2
        label = f"{piece.name}\n{piece.original_length_mm:.0f}×{piece.original_width_mm:.0f}"

        fontsize = 7 if piece.original_length_mm < 400 else 8
        ax.text(
            center_x, center_y, label, ha="center", va="center",
            fontsize=fontsize, color="white", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="black", alpha=0.4),
        )

        # 旋转标记
        if piece.rotated:
            ax.text(
                piece.x_mm + 5, piece.y_mm + 10, "↻",
                fontsize=12, color="red", fontweight="bold",
            )

    plt.tight_layout()
    plt.savefig(str(output_path), dpi=150)
    plt.close(fig)
    return output_path


def format_cut_list_markdown(report: CutListReport) -> str:
    """格式化为 Markdown 开料清单"""
    lines = []
    lines.append("## 开料清单")
    lines.append("")
    lines.append(f"板材总数: **{report.total_boards} 张**")
    lines.append(f"总废料面积: **{report.total_waste_area_m2} m²**")
    lines.append(f"综合利用率: **{report.overall_utilization_pct}%**")
    lines.append("")

    for i, plan in enumerate(report.plans, 1):
        lines.append(f"### 板材 {i}: {plan.board_name}")
        lines.append(
            f"尺寸: {plan.board_length_mm:.0f}×{plan.board_width_mm:.0f}mm | "
            f"利用率: {plan.utilization_pct}%"
        )
        lines.append("")
        lines.append("| 序号 | 名称 | 开料尺寸(mm) | 排样位置(x,y) | 旋转 |")
        lines.append("|------|------|-------------|---------------|------|")
        for j, piece in enumerate(plan.pieces, 1):
            rot = "是" if piece.rotated else "否"
            lines.append(
                f"| {j} | {piece.name} | "
                f"{piece.original_length_mm:.0f}×{piece.original_width_mm:.0f} | "
                f"({piece.x_mm:.0f}, {piece.y_mm:.0f}) | {rot} |"
            )
        lines.append("")

    return "\n".join(lines)