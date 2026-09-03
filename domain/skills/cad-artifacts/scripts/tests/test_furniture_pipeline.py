from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)


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
            SCRIPT_ROOT / "furniture_workflow" / "planner.py",
        )

    def test_rejects_unsupported_furniture_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "supported:"):
            self.planner.plan_furniture(
                {"type": "bed", "width": 2000, "depth": 2200, "height": 500}
            )


if __name__ == "__main__":
    unittest.main()
