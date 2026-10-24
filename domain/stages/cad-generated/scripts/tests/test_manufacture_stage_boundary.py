"""制造阶段只消费已确认板件字典，特征树不再引用制造类型。"""

from __future__ import annotations

import sys
import unittest
from dataclasses import asdict
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_feature_tree.feature_tree_builder import panels_to_feature_tree
from furniture_manufacturing.confirmed_panels import (
    _CONSTRUCTION_FIELDS,
    _PANEL_REQUIRED,
    admit_construction,
    admit_panels,
)
from furniture_manufacturing.manufacturing_bom import plan_manufacturing
from furniture_manufacturing.manufacturing_edge_banding import FOUR_EDGE_TYPES
from furniture_panel_planning.assembly_tree import flatten_panels_for_handoff
from furniture_panel_planning.panel_pipeline import plan_panel_stage
from panel_fixtures import cabinet_envelope, panel_parameters


class ManufacturePanelContractTests(unittest.TestCase):
    def test_a_real_panel_plan_satisfies_the_manufacturing_copy(self) -> None:
        output = plan_panel_stage((cabinet_envelope(),), panel_parameters())
        cabinet = output["cabinets"][0]
        spec = cabinet["spec"]
        panels = flatten_panels_for_handoff(cabinet)

        missing_spec = [name for name in _CONSTRUCTION_FIELDS if name not in spec]
        self.assertEqual(missing_spec, [])
        for panel in panels:
            missing_panel = [name for name in _PANEL_REQUIRED if name not in panel]
            self.assertEqual(missing_panel, [], panel.get("id"))

        emitted = {item["panel_type"] for item in panels}
        self.assertTrue(emitted)
        self.assertLessEqual(emitted, set(FOUR_EDGE_TYPES))
        self.assertIn("door", emitted)
        self.assertIn("side", emitted)
        self.assertIn("back", emitted)

        doors = [item for item in panels if item["panel_type"] == "door"]
        self.assertEqual(
            sorted(item["door_hinge_side"] for item in doors),
            ["left", "right"],
        )

        admitted_spec = admit_construction(spec)
        admitted_panels = admit_panels(panels)
        self.assertEqual(admitted_spec.furniture_category, spec["furniture_category"])
        self.assertEqual(len(admitted_panels), len(panels))

        bom = plan_manufacturing(spec, panels)
        bom_doors = [item for item in bom.panels if item.panel_type == "door"]
        self.assertEqual(
            sorted(item.door_hinge_side for item in bom_doors),
            ["left", "right"],
        )

        from_objects = panels_to_feature_tree(bom.panels, bom.operations)
        from_dicts = panels_to_feature_tree(
            [asdict(panel) for panel in bom.panels],
            [asdict(operation) for operation in bom.operations],
        )
        self.assertEqual(from_objects["schema_version"], 2)
        self.assertEqual(
            [feature["id"] for feature in from_objects["features"]],
            [feature["id"] for feature in from_dicts["features"]],
        )
        self.assertEqual(len(from_dicts["operations"]), len(bom.operations))


if __name__ == "__main__":
    unittest.main()
