from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(SCRIPT_ROOT))

import generate_furniture
from furniture.cad_bridge import CadBridge
from furniture.workflow_orchestrator import FurnitureOrchestrator


class CliEntrypointTests(unittest.TestCase):
    def test_cli_delegates_full_generation_to_injected_orchestrator(self) -> None:
        artifact_name = f"cli-test-{uuid4().hex}"
        source_dir = WORKSPACE_ROOT / "temp" / "cad-source" / artifact_name
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                temporary_root = Path(temporary_directory)
                spec_path = temporary_root / "cabinet.json"
                spec_path.write_text(
                    json.dumps(
                        {
                            "type": "wall_cabinet",
                            "width": 800,
                            "depth": 350,
                            "height": 900,
                        }
                    ),
                    encoding="utf-8",
                )
                launcher_path = temporary_root / "fake_step.py"
                launcher_path.write_text(
                    "\n".join(
                        [
                            "import sys",
                            "from pathlib import Path",
                            "output = Path(sys.argv[sys.argv.index('--output') + 1])",
                            "output.parent.mkdir(parents=True, exist_ok=True)",
                            "output.write_text('STEP', encoding='utf-8')",
                            "output.with_name(f'.{output.name}.glb').write_bytes(b'GLB')",
                        ]
                    ),
                    encoding="utf-8",
                )
                bridge = CadBridge(
                    workspace_root=WORKSPACE_ROOT,
                    python_executable=sys.executable,
                    step_launcher=launcher_path,
                )
                orchestrator = FurnitureOrchestrator(
                    workspace_root=WORKSPACE_ROOT,
                    cad_bridge=bridge,
                )

                with redirect_stdout(StringIO()):
                    exit_code = generate_furniture.main(
                        [
                            str(spec_path),
                            "--name",
                            artifact_name,
                            "--output-root",
                            str(temporary_root / "outputs"),
                        ],
                        orchestrator=orchestrator,
                    )

                artifact_dir = temporary_root / "outputs" / artifact_name
                self.assertEqual(exit_code, 0)
                self.assertTrue((artifact_dir / f"{artifact_name}.step").is_file())
                self.assertTrue(
                    (artifact_dir / f"{artifact_name}.feature-tree.json").is_file()
                )
        finally:
            shutil.rmtree(source_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
