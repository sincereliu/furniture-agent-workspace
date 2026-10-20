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

from furniture_manufacturing.catalog_loader import UniqueKeyLoader
from furniture_manufacturing.edge_banding_catalog import (
    material_keys,
    material_name,
    thickness_keys,
    thickness_mm,
)


class EdgeBandingCatalogTests(unittest.TestCase):
    def test_material_keys(self) -> None:
        self.assertEqual(set(material_keys()), {"abs", "pvc", "laser"})

    def test_thickness_keys(self) -> None:
        self.assertEqual(set(thickness_keys()), {"t0_8", "t1_0", "t2_0"})

    def test_material_names(self) -> None:
        self.assertEqual(material_name("abs"), "ABS封边")
        self.assertEqual(material_name("laser"), "激光封边")

    def test_thickness_mm(self) -> None:
        self.assertEqual(thickness_mm("t1_0"), 1.0)
        self.assertEqual(thickness_mm("t2_0"), 2.0)

    def test_unknown_keys(self) -> None:
        self.assertEqual(material_name("no_such"), "")
        self.assertEqual(thickness_mm("no_such"), 0.0)

    def test_duplicate_keys_are_rejected(self) -> None:
        raw = "material:\n  abs: { name: ABS }\n  abs: { name: 重复 }\n"
        with self.assertRaises(ValueError):
            yaml.load(raw, Loader=UniqueKeyLoader)


if __name__ == "__main__":
    unittest.main()
