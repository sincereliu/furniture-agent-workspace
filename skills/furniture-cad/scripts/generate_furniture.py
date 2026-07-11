"""端到端家具生成脚本：规划 → 拆单 → BOM → FeatureTree → 源码 → STEP/GLB

用法（从仓库根目录运行）:
  python skills/furniture-cad/scripts/generate_furniture.py examples/cabinet_basic.json --name my_cabinet --force
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]

# skill 自带 furniture 运行包，不依赖仓库根目录的 packages/。
sys.path.insert(0, str(SCRIPT_ROOT))

from furniture.workflow_orchestrator import FurnitureOrchestrator


def main(
    argv: list[str] | None = None,
    *,
    orchestrator: FurnitureOrchestrator | None = None,
) -> int:
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
    args = parser.parse_args(argv)

    # CLI 只负责协议适配；完整执行顺序统一由 FurnitureOrchestrator 控制。
    spec_path = _workspace_path(args.spec)
    spec_data = json.loads(spec_path.read_text(encoding="utf-8"))
    artifact_name = args.name or spec_path.stem

    try:
        application = orchestrator or FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT
        )
        orchestration = application.execute_spec(
            artifact_name,
            spec_data,
            output_root=args.output_root,
            artifact_name=artifact_name,
            generate_cad=True,
            force=args.force,
        )
    except (OSError, TypeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if orchestration.pipeline is None or orchestration.bridge is None:
        for report in orchestration.revision.validations:
            for issue in report.issues:
                print(f"Error [{issue.code}]: {issue.message}", file=sys.stderr)
        return 1

    pipeline = orchestration.pipeline
    fspec = pipeline.spec
    print(
        f" 规划家具: {fspec.furniture_type} "
        f"({fspec.width:.0f}×{fspec.height:.0f}×{fspec.depth:.0f}mm)"
    )
    print(f" 拆单完成: {pipeline.bom.panel_count} 块板件")
    print(f" 五金件: {pipeline.bom.hardware_item_count} 项")
    print(f" 总展开面积: {pipeline.bom.total_area_m2:.4f} m²")

    for kind, label in (
        ("design_intent", "设计意图"),
        ("feature_tree", "Feature Tree"),
        ("bom", "BOM 报告"),
        ("cad_source", "build123d 源码"),
    ):
        artifact = next(
            item
            for item in orchestration.revision.manifest.artifacts
            if item.kind == kind
        )
        print(f" {label} → {artifact.path}")

    bridge_result = orchestration.bridge

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
