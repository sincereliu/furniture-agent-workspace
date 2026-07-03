from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = WORKSPACE_ROOT / "packages" / "cad_bridge" / "adapter.py"


def load_adapter_module():
    spec = importlib.util.spec_from_file_location("cad_bridge_adapter", ADAPTER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load CAD bridge module from {ADAPTER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CadBridgeTests(unittest.TestCase):
    def test_generates_step_and_topology_through_external_cli_contract(self) -> None:
        module = load_adapter_module()

        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            source_path = workspace / "generated" / "table.py"
            output_path = workspace / "generated" / "table.step"
            launcher_path = workspace / "fake_step.py"
            source_path.parent.mkdir(parents=True)
            source_path.write_text("def gen_step():\n    return None\n", encoding="utf-8")
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

            bridge = module.CadBridge(
                workspace_root=workspace,
                external_repo_root=workspace / "external" / "text-to-cad",
                python_executable=sys.executable,
                step_launcher=launcher_path,
            )
            result = bridge.generate_from_source(source_path, output_path)

            self.assertEqual(result.status, "ok")
            self.assertEqual(result.returncode, 0)
            self.assertTrue(output_path.is_file())
            self.assertTrue(output_path.with_name(".table.step.glb").is_file())

    def test_rejects_missing_source_before_launch(self) -> None:
        module = load_adapter_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            launcher_path = workspace / "fake_step.py"
            launcher_path.write_text("", encoding="utf-8")
            bridge = module.CadBridge(
                workspace_root=workspace,
                python_executable=sys.executable,
                step_launcher=launcher_path,
            )

            result = bridge.generate_from_source("missing.py")

            self.assertEqual(result.status, "failed")
            self.assertIn("CAD source file not found", result.message)


if __name__ == "__main__":
    unittest.main()
