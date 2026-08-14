from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
ADAPTER_PATH = SCRIPT_ROOT / "furniture_cad" / "cad_bridge.py"


def load_adapter_module():
    spec = importlib.util.spec_from_file_location("furniture_cad_bridge", ADAPTER_PATH)
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
            source_path = workspace / "generated" / "cabinet.step.py"
            output_path = workspace / "generated" / "cabinet.step"
            launcher_path = workspace / "fake_gen.py"
            source_path.parent.mkdir(parents=True)
            source_path.write_text("def gen_step():\n    return None\n", encoding="utf-8")
            launcher_path.write_text(
                "\n".join(
                    [
                        "import json",
                        "import sys",
                        "from pathlib import Path",
                        "assert '--json' in sys.argv",
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

            bridge = module.CadBridge(
                workspace_root=workspace,
                external_repo_root=workspace / "external" / "text-to-cad",
                python_executable=sys.executable,
                gen_launcher=launcher_path,
            )
            result = bridge.generate_from_source(source_path, output_path)

            self.assertEqual(result.status, "ok")
            self.assertEqual(result.returncode, 0)
            self.assertTrue(output_path.is_file())
            package_path = source_path.parent / "__cadgen__" / "models" / source_path.name
            self.assertEqual(Path(result.viewer_package_path), package_path)
            self.assertEqual(Path(result.topology_path), package_path / "assembly.json")
            self.assertTrue((package_path / "components" / "fake.glb").is_file())

    def test_default_launcher_is_current_gen_entrypoint(self) -> None:
        module = load_adapter_module()
        bridge = module.CadBridge(workspace_root=WORKSPACE_ROOT)

        expected = (
            WORKSPACE_ROOT
            / "external"
            / "text-to-cad"
            / "skills"
            / "cad"
            / "scripts"
            / "gen"
        ).resolve()
        self.assertEqual(bridge.gen_launcher, expected)
        self.assertTrue((bridge.gen_launcher / "__main__.py").is_file())
        self.assertEqual(
            bridge._default_step_output(Path("cabinet.step.py")),
            Path("cabinet.step"),
        )

    def test_rejects_missing_source_before_launch(self) -> None:
        module = load_adapter_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            launcher_path = workspace / "fake_gen.py"
            launcher_path.write_text("", encoding="utf-8")
            bridge = module.CadBridge(
                workspace_root=workspace,
                python_executable=sys.executable,
                gen_launcher=launcher_path,
            )

            result = bridge.generate_from_source("missing.py")

            self.assertEqual(result.status, "failed")
            self.assertIn("CAD source file not found", result.message)


if __name__ == "__main__":
    unittest.main()
