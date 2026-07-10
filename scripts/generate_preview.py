"""生成落地柜 STEP 预览 — 完整流水线: Planner → Panelizer → Emitter → Bridge"""

from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "packages"))

from furniture.feature_tree_builder import panels_to_feature_tree
from furniture.layout_pipeline import plan_cabinet
from furniture.design_spec import FurnitureSpec


def main():
    # 1. 规格: 1200×600×800mm 落地柜 4层板 2门板
    spec = FurnitureSpec(
        furniture_type="floor_cabinet",
        width=1200,
        height=800,
        depth=600,
        shelf_count=4,
        n_doors=2,
    )

    print(f"规格: {spec.width:.0f}×{spec.height:.0f}×{spec.depth:.0f}mm")
    print(f"板厚: {spec.board_thickness}mm  层板: 4  门板: 2")

    # 2. 规划、拆单和 BOM
    pipeline_result = plan_cabinet(spec)
    print(f"\n规划完成: {len(pipeline_result.placements)} 块板")
    print(f"拆单完成: {len(pipeline_result.panels)} 条 PanelRecord")

    # 3. 转换为 Feature Tree
    feature_tree = panels_to_feature_tree(
        pipeline_result.panels,
        furniture_type="floor_cabinet",
        parameters={
            "width": spec.width,
            "height": spec.height,
            "depth": spec.depth,
            "board_thickness": spec.board_thickness,
        },
    )
    print(f"Feature Tree 构造完成")

    # 4. 生成 build123d 源码文件
    from furniture.feature_tree_emitter import write_build123d_source

    output_dir = WORKSPACE_ROOT / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    source_path = output_dir / "floor_cabinet_preview.py"
    write_build123d_source(feature_tree, source_path)
    print(f"build123d 源码: {source_path}")

    # 5. 通过 Bridge 生成 STEP + GLB
    from furniture.cad_bridge import CadBridge

    bridge = CadBridge()
    result = bridge.generate_from_source(source_path)
    print(f"\nBridge 结果: status={result.status}")
    print(f"  STEP: {result.step_path}")
    print(f"  GLB:  {result.topology_path}")
    if result.stderr:
        print(f"  stderr:\n{result.stderr[:500]}")

    if result.status != "ok":
        print(f"\n错误: {result.message}")
        sys.exit(1)

    print(f"\n✓ 预览文件已生成")
    print(f"  STEP: {result.step_path}")
    print(f"  GLB:  {result.topology_path}")


if __name__ == "__main__":
    main()
