from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_manufacturing.manufacturing_bom import (
    default_joint_connection,
    plan_manufacturing,
)
from furniture_manufacturing.manufacturing_models import PanelRecord
from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.structure_planning import CabinetStructure
from panel_fixtures import furniture_spec


def _panel(label: str, panel_type: str) -> PanelRecord:
    return PanelRecord(
        label=label, name=label, panel_type=panel_type, material="18mm",
        thickness=18.0, length_mm=1.0, width_mm=1.0,
        size_x=1.0, size_y=1.0, size_z=1.0,
    )


class JointConnectionMigrationTests(unittest.TestCase):
    def test_default_joint_connection_rule_lives_in_manufacturing(self) -> None:
        side = _panel("side", "side")
        top = _panel("top", "top")
        back = _panel("back", "back")
        shelf = _panel("shelf", "fixed_shelf")
        rail = _panel("rail", "back_rail")
        self.assertEqual(default_joint_connection(side, top), "on")
        self.assertEqual(default_joint_connection(side, shelf), "on")
        self.assertEqual(default_joint_connection(back, shelf), "off")
        self.assertEqual(default_joint_connection(shelf, back), "off")
        self.assertEqual(default_joint_connection(rail, back), "off")
        self.assertEqual(default_joint_connection(back, rail), "off")

    def test_plan_manufacturing_resolves_connection_from_panel_types(self) -> None:
        spec = furniture_spec(
            furniture_category="floor_cabinet",
            width=800, depth=600, height=1000,
            n_doors=2, back_mount="groove",
        )
        structure = CabinetStructure.from_spec(spec)
        placements = plan_panels(spec, structure)
        bom = plan_manufacturing(spec, placements)
        by_label = {p.label: p for p in bom.panels}
        by_role = {p.role: p for p in bom.panels}

        back = by_role["back_panel"]
        shelf_joints = [
            j for j in back.joints
            if "fixed_shelf" in {
                by_label[j.bearing_id].panel_type,
                by_label[j.end_id].panel_type,
            }
        ]
        self.assertTrue(shelf_joints)
        self.assertTrue(all(j.connection == "off" for j in shelf_joints))

        side = by_role["left_side_panel"]
        top_joints = [
            j for j in side.joints
            if "top" in {
                by_label[j.bearing_id].panel_type,
                by_label[j.end_id].panel_type,
            }
        ]
        self.assertTrue(top_joints)
        self.assertTrue(all(j.connection == "on" for j in top_joints))


if __name__ == "__main__":
    unittest.main()
