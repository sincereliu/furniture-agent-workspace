from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan furniture, emit build123d source, and generate STEP via text-to-cad."
    )
    parser.add_argument("spec", help="Path to a furniture JSON specification.")
    parser.add_argument(
        "--name",
        help="Artifact name. Defaults to the specification filename stem.",
    )
    parser.add_argument(
        "--output-root",
        default="generated",
        help="Workspace-relative or absolute artifact root. Default: generated",
    )
    parser.add_argument("--force", action="store_true", help="Force STEP regeneration.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    spec_path = _workspace_path(args.spec)
    spec_data = json.loads(spec_path.read_text(encoding="utf-8"))

    artifact_name = args.name or spec_path.stem
    if not SAFE_NAME.fullmatch(artifact_name):
        raise ValueError("Artifact name may contain only letters, numbers, '-' and '_'.")

    output_root = _workspace_path(args.output_root)
    artifact_dir = output_root / artifact_name
    artifact_dir.mkdir(parents=True, exist_ok=True)

    planner = load_module(
        "furniture_planner",
        WORKSPACE_ROOT / "packages" / "furniture-planner" / "planner.py",
    )
    emitter = load_module(
        "furniture_cad_emitter",
        WORKSPACE_ROOT / "packages" / "furniture-cad-emitter" / "emitter.py",
    )
    bridge_module = load_module(
        "furniture_cad_bridge",
        WORKSPACE_ROOT / "packages" / "cad-bridge" / "adapter.py",
    )

    feature_tree = planner.plan_furniture(spec_data)
    intent_path = artifact_dir / f"{artifact_name}.intent.json"
    feature_tree_path = artifact_dir / f"{artifact_name}.feature-tree.json"
    source_path = artifact_dir / f"{artifact_name}.py"
    step_path = artifact_dir / f"{artifact_name}.step"

    intent_path.write_text(
        json.dumps(spec_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    feature_tree_path.write_text(
        json.dumps(feature_tree, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    emitter.write_build123d_source(feature_tree, source_path)

    bridge = bridge_module.CadBridge(workspace_root=WORKSPACE_ROOT)
    result = bridge.generate_from_source(source_path, step_path, force=args.force)
    payload = {
        "intent_path": str(intent_path),
        "feature_tree_path": str(feature_tree_path),
        **asdict(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.status == "ok" else 1


def _workspace_path(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = WORKSPACE_ROOT / candidate
    return candidate.resolve()


if __name__ == "__main__":
    raise SystemExit(main())
