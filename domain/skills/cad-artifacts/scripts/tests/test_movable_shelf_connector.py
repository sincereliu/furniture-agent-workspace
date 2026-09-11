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
from panel_fixtures import furniture_spec


def _movable_shelf_spec():
    return furniture_spec(
        furniture_category="floor_cabinet",
        width=800,
        depth=600,
        height=1000,
        n_doors=2,
        shelves=[{"shelf_type": "movable", "gap_below_mm": None}],
        top_gap_mm=100.0,
    )


class MovableShelfConnectorMigrationTests(unittest.TestCase):
    def _placements(self, spec):
        structure = CabinetStructure.from_spec(spec)
        return plan_panels(spec, structure)

    def test_spec_no_longer_carries_movable_shelf_connector(self) -> None:
        spec = _movable_shelf_spec()
        self.assertFalse(hasattr(spec, "movable_shelf_connector"))

    def test_movable_shelf_connector_is_required_when_movable_shelves_exist(self) -> None:
        spec = _movable_shelf_spec()
        placements = self._placements(spec)
        with self.assertRaisesRegex(ValueError, "movable_shelf_connector"):
            plan_manufacturing(spec, placements)

    def test_two_in_one_and_shelf_pin_select_different_hardware(self) -> None:
        spec = _movable_shelf_spec()
        placements = self._placements(spec)
        two = plan_manufacturing(
            spec,
            placements,
            requested_options={"movable_shelf_connector": "two_in_one"},
        )
        pin = plan_manufacturing(
            spec,
            placements,
            requested_options={"movable_shelf_connector": "shelf_pin"},
        )

        two_names = {h.name for h in two.hardware}
        pin_names = {h.name for h in pin.hardware}
        self.assertIn("二合一连接件", two_names)
        self.assertNotIn("隔板钉", two_names)
        self.assertIn("隔板钉", pin_names)
        self.assertNotIn("二合一连接件", pin_names)

    def test_option_is_stamped_onto_movable_shelf_panels(self) -> None:
        spec = _movable_shelf_spec()
        placements = self._placements(spec)
        two = plan_manufacturing(
            spec,
            placements,
            requested_options={"movable_shelf_connector": "two_in_one"},
        )
        stamped = {
            p.movable_shelf_connector
            for p in two.panels
            if p.panel_type == "movable_shelf"
        }
        self.assertEqual(stamped, {"two_in_one"})


if __name__ == "__main__":
    unittest.main()
