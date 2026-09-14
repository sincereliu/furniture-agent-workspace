from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from panel_fixtures import furniture_spec
from furniture_manufacturing.manufacturing_bom import (
    format_bom_markdown,
    plan_manufacturing,
)
from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.structure_planning import CabinetStructure


def _appearance():
    return {
        "carcass": {"substrate": "particleboard", "surface": "white__soft_touch__plain"},
        "door": {"substrate": "particleboard", "surface": "oak__double_faced__grain"},
        "back": {"substrate": "particleboard", "surface": "white__double_faced__plain"},
    }


class MaterialsBomTests(unittest.TestCase):
    def _bom(self):
        spec = furniture_spec(n_doors=2)
        placements = plan_panels(spec, CabinetStructure.from_spec(spec))
        return plan_manufacturing(spec, placements, appearance=_appearance())

    def test_materials_cover_three_categories(self) -> None:
        bom = self._bom()
        categories = {m.category for m in bom.materials}
        self.assertEqual(categories, {"substrate", "surface", "edge_banding"})

    def test_substrate_area_matches_total(self) -> None:
        bom = self._bom()
        substrate_total = sum(
            m.quantity for m in bom.materials if m.category == "substrate"
        )
        self.assertAlmostEqual(substrate_total, bom.total_area_m2)

    def test_surface_area_matches_total(self) -> None:
        bom = self._bom()
        surface_total = sum(
            m.quantity for m in bom.materials if m.category == "surface"
        )
        self.assertAlmostEqual(surface_total, bom.total_area_m2)

    def test_edge_banding_is_measured_in_meters(self) -> None:
        bom = self._bom()
        edges = [m for m in bom.materials if m.category == "edge_banding"]
        self.assertTrue(edges)
        self.assertTrue(all(m.unit == "m" for m in edges))
        self.assertTrue(all(m.quantity > 0 for m in edges))

    def test_edge_banding_spec_carries_width_and_color(self) -> None:
        bom = self._bom()
        specs = {m.spec for m in bom.materials if m.category == "edge_banding"}
        self.assertTrue(any("white" in s for s in specs))
        self.assertTrue(any("oak" in s for s in specs))
        self.assertTrue(all("18mm" in s for s in specs))

    def test_no_appearance_still_lists_edge_banding(self) -> None:
        spec = furniture_spec(n_doors=2)
        placements = plan_panels(spec, CabinetStructure.from_spec(spec))
        bom = plan_manufacturing(spec, placements)
        self.assertEqual({m.category for m in bom.materials}, {"edge_banding"})

    def test_markdown_has_material_section(self) -> None:
        bom = self._bom()
        markdown = format_bom_markdown(bom)
        self.assertIn("### 材料清单", markdown)
        self.assertIn("颗粒板", markdown)
        self.assertIn("ABS封边", markdown)


if __name__ == "__main__":
    unittest.main()
