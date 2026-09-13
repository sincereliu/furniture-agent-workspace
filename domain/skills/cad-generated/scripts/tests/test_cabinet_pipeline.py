from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_manufacturing.manufacturing_bom import plan_manufacturing
from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.structure_planning import CabinetStructure
from panel_fixtures import by_role, furniture_spec


class CabinetStageCompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = furniture_spec(
            furniture_category="floor_cabinet",
            width=800,
            height=1000,
            depth=600,
            shelf_count=4,
            n_doors=2,
        )
        self.structure = CabinetStructure.from_spec(self.spec)
        self.placements = plan_panels(self.spec, self.structure)
        self.bom = plan_manufacturing(self.spec, self.placements)

    def test_floor_cabinet_uses_expected_coordinate_convention(self) -> None:
        placements = by_role(self.placements)

        left = placements["left_side_panel"]
        self.assertEqual((left.pos_x, left.pos_y, left.pos_z), (0.0, 0.0, 0.0))

        right = placements["right_side_panel"]
        self.assertEqual(right.pos_x, 800.0 - 18.0)

        self.assertEqual(placements["back_panel"].pos_y, 18.0)
        self.assertEqual(placements["bottom_panel"].pos_z, 50.0)

    def test_floor_cabinet_produces_panels_and_bom(self) -> None:
        self.assertEqual(len(self.bom.panels), len(self.placements))
        self.assertEqual(self.bom.panel_count, len(self.bom.panels))
        self.assertEqual(self.bom.furniture_name, "落地柜")
        self.assertEqual(self.bom.dimensions, "800×1000×600mm")
        self.assertGreater(self.bom.total_area_m2, 0)
        self.assertEqual(self.bom.readiness, "preliminary")

    def test_rejects_non_cabinet_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "executable canonical category"):
            furniture_spec(
                furniture_category="wardrobe",
                width=1200,
                height=2000,
                depth=600,
            )


if __name__ == "__main__":
    unittest.main()
