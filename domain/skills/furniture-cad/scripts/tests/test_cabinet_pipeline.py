from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_panel_planning.panel_spec import FurnitureSpec
from panel_fixtures import furniture_spec
from furniture_workflow.cabinet_pipeline import plan_cabinet


class CabinetPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = plan_cabinet(
            furniture_spec(
                furniture_type="floor_cabinet",
                width=800,
                height=1000,
                depth=600,
                shelf_count=4,
                n_doors=2,
            )
        )

    def test_floor_cabinet_uses_expected_coordinate_convention(self) -> None:
        placements = {placement.id: placement for placement in self.result.placements}

        left = placements["left_side_panel"]
        self.assertEqual((left.pos_x, left.pos_y, left.pos_z), (0.0, 0.0, 0.0))

        right = placements["right_side_panel"]
        self.assertEqual(right.pos_x, 800.0 - 18.0)

        self.assertEqual(placements["back_panel"].pos_y, 18.0)
        self.assertEqual(placements["bottom_panel"].pos_z, 50.0)

    def test_floor_cabinet_produces_panels_and_bom(self) -> None:
        self.assertEqual(len(self.result.panels), len(self.result.placements))
        self.assertEqual(self.result.bom.panel_count, len(self.result.panels))
        self.assertEqual(self.result.bom.furniture_name, "落地柜")
        self.assertEqual(self.result.bom.dimensions, "800×1000×600mm")
        self.assertGreater(self.result.bom.total_area_m2, 0)
        self.assertEqual(self.result.bom.readiness, "preliminary")

    def test_rejects_non_cabinet_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "executable canonical type"):
            plan_cabinet(
                furniture_spec(
                    furniture_type="wardrobe",
                    width=1200,
                    height=2000,
                    depth=600,
                )
            )


if __name__ == "__main__":
    unittest.main()
