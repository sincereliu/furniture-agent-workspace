from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.panel_rules import (
    resolve_toe_kick_support_count,
    toe_kick_support_clear_spacing,
)
from furniture_panel_planning.panel_spec import resolve_shelf_gaps
from furniture_panel_planning.structure_planning import CabinetStructure
from panel_fixtures import furniture_spec


class PanelRuleContractTests(unittest.TestCase):
    def test_single_auto_shelf_gap_absorbs_remaining_internal_height(self) -> None:
        spec = furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            n_doors=2,
            shelves=[
                {"shelf_type": "fixed", "gap_below_mm": 200.0},
                {"shelf_type": "movable", "gap_below_mm": None},
                {"shelf_type": "fixed", "gap_below_mm": 150.0},
            ],
            top_gap_mm=100.0,
        )

        structure = CabinetStructure.from_spec(spec)
        self.assertEqual(
            resolve_shelf_gaps(spec, structure.internal_height),
            [200.0, 410.0, 150.0],
        )

    def test_toe_kick_support_rule_matches_reference_thresholds(self) -> None:
        self.assertEqual(resolve_toe_kick_support_count(None, 599.0), 0)
        self.assertEqual(resolve_toe_kick_support_count(None, 600.0), 1)
        self.assertEqual(resolve_toe_kick_support_count(None, 899.0), 1)
        self.assertEqual(resolve_toe_kick_support_count(None, 900.0), 2)
        self.assertEqual(
            toe_kick_support_clear_spacing(764.0, 1, 18.0),
            373.0,
        )

    def test_drawer_dimension_chain_matches_reference_sample(self) -> None:
        spec = furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            n_doors=0,
            shelf_count=0,
            drawer_count=3,
        )

        structure = CabinetStructure.from_spec(spec)
        placements = {panel.id: panel for panel in plan_panels(spec, structure)}

        front_bottom = placements["drawer_front_z68"]
        side_bottom = placements["drawer_side_L_z68"]
        bottom_bottom = placements["drawer_bottom_z68"]
        front_middle = placements["drawer_front_z374"]
        front_top = placements["drawer_front_z679"]
        support = placements["toe_kick_support_1"]

        self.assertEqual(
            (
                round(front_bottom.size_x, 3),
                round(front_bottom.size_y, 3),
                round(front_bottom.size_z, 3),
                round(front_bottom.pos_x, 3),
                round(front_bottom.pos_y, 3),
                round(front_bottom.pos_z, 3),
            ),
            (761.0, 18.0, 303.167, 19.5, 562.0, 68.0),
        )
        self.assertEqual(
            (
                round(side_bottom.size_x, 3),
                round(side_bottom.size_y, 3),
                round(side_bottom.size_z, 3),
                round(side_bottom.pos_x, 3),
                round(side_bottom.pos_y, 3),
                round(side_bottom.pos_z, 3),
            ),
            (18.0, 535.0, 267.167, 31.0, 27.0, 86.0),
        )
        self.assertEqual(
            (
                round(bottom_bottom.size_x, 3),
                round(bottom_bottom.size_y, 3),
                round(bottom_bottom.size_z, 3),
            ),
            (702.0, 517.0, 18.0),
        )
        self.assertEqual(
            (
                round(front_middle.pos_x, 3),
                round(front_middle.pos_y, 3),
                round(front_middle.pos_z, 3),
            ),
            (19.5, 562.0, 374.167),
        )
        self.assertEqual(
            (
                round(front_top.pos_x, 3),
                round(front_top.pos_y, 3),
                round(front_top.pos_z, 3),
            ),
            (19.5, 562.0, 678.833),
        )
        self.assertEqual(
            (
                round(support.size_x, 3),
                round(support.size_y, 3),
                round(support.size_z, 3),
                round(support.pos_x, 3),
                round(support.pos_y, 3),
                round(support.pos_z, 3),
            ),
            (18.0, 513.0, 50.0, 391.0, 48.0, 0.0),
        )


if __name__ == "__main__":
    unittest.main()