"""端到端家具生成脚本：规划 → 拆单 → BOM → FeatureTree → 源码 → STEP/GLB

用法:
  python scripts/generate_furniture.py examples/cabinet_basic.json --name my_cabinet --force
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")

# 确保 packages 在 sys.path 中
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "packages"))

from furniture_pipeline.cabinet import plan_cabinet
from furniture_schema.spec import FurnitureSpec
from furniture_cad_emitter.cabinet_emitter import panels_to_feature_tree
from furniture_cad_emitter.emitter import write_build123d_source
from furniture_panelizer.bom import format_bom_markdown
from cad_bridge.adapter import CadBridge


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="板式家具端到端生成：JSON spec → 拆单 → BOM → STEP/GLB"
    )
    parser.add_argument("spec", help="家具 JSON 规格文件路径")
    parser.add_argument("--name", help="输出名称（默认使用文件名）")
    parser.add_argument(
        "--output-root",
        default="generated",
        help="输出根目录（默认 generated）",
    )
    parser.add_argument("--force", action="store_true", help="强制重新生成 STEP")
    args = parser.parse_args()

    # ── 1. 读取并解析规格 ──
    spec_path = _workspace_path(args.spec)
    spec_data = json.loads(spec_path.read_text(encoding="utf-8"))
    fspec = FurnitureSpec.from_dict(spec_data)

    artifact_name = args.name or spec_path.stem
    if not SAFE_NAME.fullmatch(artifact_name):
        print(f"Error: 输出名称只能包含字母、数字、'-' 和 '_': {artifact_name}", file=sys.stderr)
        return 1

    output_root = _workspace_path(args.output_root)
    artifact_dir = output_root / artifact_name
    artifact_dir.mkdir(parents=True, exist_ok=True)

    # ── 2. 规划 → 拆单 → BOM ──
    print(f" 规划家具: {fspec.furniture_type} ({fspec.width:.0f}×{fspec.height:.0f}×{fspec.depth:.0f}mm)")
    result = plan_cabinet(fspec)
    print(f" 拆单完成: {result.bom.panel_count} 块板件")
    print(f" 五金件: {result.bom.hardware_item_count} 项")
    print(f" 总展开面积: {result.bom.total_area_m2:.4f} m²")

    # 保存 Feature Tree JSON
    feature_tree = panels_to_feature_tree(
        result.panels, furniture_type=fspec.furniture_type,
        parameters={
            "width": fspec.width, "depth": fspec.depth, "height": fspec.height,
            "board_thickness": fspec.board_thickness,
        },
    )
    feature_tree_path = artifact_dir / f"{artifact_name}.feature-tree.json"
    feature_tree_path.write_text(
        json.dumps(feature_tree, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f" Feature Tree → {feature_tree_path}")

    # 保存 BOM Markdown
    bom_path = artifact_dir / f"{artifact_name}.bom.md"
    bom_path.write_text(format_bom_markdown(result.bom), encoding="utf-8")
    print(f" BOM 报告 → {bom_path}")

    # ── 3. 生成 build123d 源码 → STEP/GLB ──
    source_path = artifact_dir / f"{artifact_name}.py"
    write_build123d_source(feature_tree, source_path)
    print(f" build123d 源码 → {source_path}")

    step_path = artifact_dir / f"{artifact_name}.step"
    bridge = CadBridge(workspace_root=WORKSPACE_ROOT)
    bridge_result = bridge.generate_from_source(source_path, step_path, force=args.force)

    print(f"\n{'='*60}")
    print(f"  CAD 生成结果: {bridge_result.status.upper()}")
    print(f"  {bridge_result.message}")
    if bridge_result.step_path:
        print(f"  STEP: {bridge_result.step_path}")
    if bridge_result.topology_path:
        print(f"  GLB:  {bridge_result.topology_path}")
    print(f"{'='*60}")

    return 0 if bridge_result.status == "ok" else 1


def _workspace_path(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = WORKSPACE_ROOT / candidate
    return candidate.resolve()


if __name__ == "__main__":
    raise SystemExit(main())