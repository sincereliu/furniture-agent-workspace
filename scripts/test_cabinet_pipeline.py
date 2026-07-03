"""落地柜端到端验证脚本 — Planner → Panelizer → BOM"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保能找到所有包
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "packages"))

from furniture_schema.spec import FurnitureSpec
from furniture_planner.cabinet_planner import CabinetPlanner
from furniture_planner.templates.floor_cabinet import FloorCabinet
from furniture_panelizer.panelizer import panelize
from furniture_panelizer.bom import generate_bom_report, print_bom


def test_floor_cabinet():
    """测试落地柜完整流程"""
    print("=" * 60)
    print("  落地柜 端到端测试")
    print("=" * 60)

    # 1. 构造规格
    spec = FurnitureSpec(
        furniture_type="floor_cabinet",
        width=800,
        height=1000,
        depth=600,
    )
    print(f"\n规格: {spec.width:.0f}×{spec.height:.0f}×{spec.depth:.0f}mm")
    print(f"  板厚:{spec.board_thickness}mm 背板厚:{spec.back_thickness}mm 门板厚:{spec.door_thickness}mm")
    print(f"  踢脚线:{spec.toe_kick_height}mm 背板偏移:{spec.back_offset}mm")

    # 2. 规划
    planner = CabinetPlanner(spec)
    template = FloorCabinet(shelf_count=4, n_doors=2)
    template.build(planner)

    print(f"\n规划完成，共 {len(planner._placements)} 块板:")
    for i, p in enumerate(planner._placements, 1):
        print(
            f"  [{i:2d}] {p.id:25s} pos=({p.pos_x:6.0f},{p.pos_y:6.0f},{p.pos_z:6.0f}) "
            f"size=({p.size_x:6.0f},{p.size_y:6.0f},{p.size_z:6.0f}) "
            f"type={p.panel_type}"
        )

    # 3. 拆单
    panels = panelize(planner._placements)
    print(f"\n拆单完成，共 {len(panels)} 条 PanelRecord")

    # 4. 验证关键坐标（对照 panel-placement.md）
    print("\n--- 坐标验证 ---")
    checks = []
    # 左侧板: min=(0, 0, 0)
    left = planner._placements[0]
    checks.append(("左侧板 X=0", abs(left.pos_x) < 1e-6))
    checks.append(("左侧板 Y=0", abs(left.pos_y) < 1e-6))
    checks.append(("左侧板 Z=0", abs(left.pos_z) < 1e-6))
    # 右侧板: min=(W-T, 0, 0)
    right = planner._placements[1]
    expected_right_x = spec.width - spec.board_thickness
    checks.append(("右侧板 X=W-T", abs(right.pos_x - expected_right_x) < 1e-6))
    # 背板: Y = back_offset
    back = [p for p in planner._placements if p.id == "back_panel"][0]
    checks.append(("背板 Y=back_offset", abs(back.pos_y - spec.back_offset) < 1e-6))
    # 底板: Z = toe_kick_h
    bottom = [p for p in planner._placements if p.id == "bottom_panel"][0]
    checks.append(("底板 Z=toe_kick_h", abs(bottom.pos_z - spec.toe_kick_height) < 1e-6))

    all_pass = True
    for name, result in checks:
        status = "✓" if result else "✗ FAIL"
        if not result:
            all_pass = False
        print(f"  {status} {name}")

    # 5. BOM 输出
    report = generate_bom_report(
        "测试落地柜",
        f"{spec.width:.0f}×{spec.height:.0f}×{spec.depth:.0f}mm",
        panels,
    )
    print_bom(report)

    if all_pass:
        print("✓ 所有坐标验证通过")
    else:
        print("✗ 部分坐标验证失败")

    return all_pass


if __name__ == "__main__":
    success = test_floor_cabinet()
    sys.exit(0 if success else 1)