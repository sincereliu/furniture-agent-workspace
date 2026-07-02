from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FurniturePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.planner = load_module(
            "test_furniture_planner",
            WORKSPACE_ROOT / "packages" / "furniture-planner" / "planner.py",
        )
        cls.emitter = load_module(
            "test_furniture_emitter",
            WORKSPACE_ROOT / "packages" / "furniture-cad-emitter" / "emitter.py",
        )

    def test_table_plan_uses_lower_left_rear_ground_origin(self) -> None:
        tree = self.planner.plan_furniture(
            {"type": "table", "width": 1200, "depth": 700, "height": 750}
        )

        features = {feature["id"]: feature for feature in tree["features"]}
        self.assertEqual(
            tree["coordinate_system"]["origin"],
            "lower-left-rear-ground-corner",
        )
        self.assertEqual(features["table_top"]["position"], {"x": 0.0, "y": 0.0, "z": 720.0})
        self.assertEqual(
            features["leg_back_right"]["position"],
            {"x": 1090.0, "y": 50.0, "z": 0.0},
        )
        self.assertEqual(
            features["leg_front_right"]["position"],
            {"x": 1090.0, "y": 590.0, "z": 0.0},
        )
        self.assertEqual(len(features), 5)

    def test_emitter_writes_gen_step_source(self) -> None:
        tree = self.planner.plan_furniture(
            {"type": "table", "width": 1200, "depth": 700, "height": 750}
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_path = Path(temporary_directory) / "table.py"
            self.emitter.write_build123d_source(tree, source_path)
            source = source_path.read_text(encoding="utf-8")

            compile(source, str(source_path), "exec")
            self.assertIn("def gen_step():", source)
            self.assertIn("Compound(children=parts", source)

    def test_rejects_unsupported_furniture_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "supports 'table'"):
            self.planner.plan_furniture(
                {"type": "bed", "width": 2000, "depth": 2200, "height": 500}
            )


if __name__ == "__main__":
    unittest.main()
