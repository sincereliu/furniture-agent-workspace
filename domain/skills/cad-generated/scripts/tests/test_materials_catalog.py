from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

import yaml

from furniture_manufacturing.materials_catalog import (
    _UniqueKeyLoader,
    substrate_keys,
    substrate_name,
    surface_keys,
    surface_name,
)


class MaterialsCatalogTests(unittest.TestCase):
    def test_substrate_keys(self) -> None:
        self.assertEqual(set(substrate_keys()), {"particleboard", "eco_board"})

    def test_surface_keys_count(self) -> None:
        self.assertEqual(len(surface_keys()), 8)

    def test_substrate_names(self) -> None:
        self.assertEqual(substrate_name("particleboard"), "颗粒板")
        self.assertEqual(substrate_name("eco_board"), "生态板")

    def test_surface_names(self) -> None:
        self.assertEqual(surface_name("white__soft_touch__plain"), "肤感白")
        self.assertEqual(surface_name("oak__double_faced__grain"), "双饰面橡木纹")

    def test_unknown_keys_return_empty_name(self) -> None:
        self.assertEqual(surface_name("no_such"), "")
        self.assertEqual(substrate_name("no_such"), "")

    def test_duplicate_keys_are_rejected(self) -> None:
        raw = (
            "substrate:\n"
            "  particleboard: { name: 颗粒板 }\n"
            "  particleboard: { name: 重复 }\n"
        )
        with self.assertRaises(ValueError):
            yaml.load(raw, Loader=_UniqueKeyLoader)


if __name__ == "__main__":
    unittest.main()
