from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_cad.cad_bridge import CadBridge
from furniture_layout.project_layout import ProjectLayout, single_cabinet_layout
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_store import JsonProjectStore


def first_cabinet_spec(output: dict) -> dict:
    return output["cabinets"][0]["spec"]


def cabinet_intent(*, furniture_category: str = "floor_cabinet") -> ProjectLayout:
    origin_z_mm = 2000.0 if furniture_category == "wall_cabinet" else None
    return single_cabinet_layout(
        furniture_category=furniture_category,
        origin_z_mm=origin_z_mm,
    )


def fake_orchestrator(
    temporary_root: Path,
    project_store: JsonProjectStore | None = None,
) -> FurnitureOrchestrator:
    launcher_path = temporary_root / "fake_gen.py"
    launcher_path.write_text(
        "\n".join(
            [
                "import json",
                "import sys",
                "from pathlib import Path",
                "source = Path(sys.argv[1])",
                "output = Path(sys.argv[sys.argv.index('--write') + 1])",
                "output.parent.mkdir(parents=True, exist_ok=True)",
                "output.write_text('STEP', encoding='utf-8')",
                "package = source.parent / '__cadgen__' / 'models' / source.name",
                "component = package / 'components' / 'fake.glb'",
                "component.parent.mkdir(parents=True, exist_ok=True)",
                "component.write_bytes(b'GLB')",
                "(package / 'assembly.json').write_text(json.dumps({'components': {'fake': {'glb': 'components/fake.glb'}}}), encoding='utf-8')",
                "print(json.dumps({'ok': True, 'packagePath': package.as_posix()}))",
            ]
        ),
        encoding="utf-8",
    )
    bridge = CadBridge(
        workspace_root=WORKSPACE_ROOT,
        python_executable=sys.executable,
        gen_launcher=launcher_path,
    )
    return FurnitureOrchestrator(
        workspace_root=WORKSPACE_ROOT,
        cad_bridge=bridge,
        project_store=project_store,
    )
