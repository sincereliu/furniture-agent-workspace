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
from furniture_manufacturing.features import from_edge_banding
from furniture_manufacturing.manufacturing_bom import plan_manufacturing
from furniture_manufacturing.manufacturing_edge_banding import build_edge_banding
from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.structure_planning import CabinetStructure


class EdgeBandingTests(unittest.TestCase):
    def test_build_derives_width_and_color(self) -> None:
        spec = build_edge_banding("side", thickness=18.0, surface="white__soft_touch__plain")
        self.assertEqual(list(spec.keys()), ["四边"])
        band = spec["四边"]
        self.assertEqual(band["material"], "abs")
        self.assertEqual(band["thickness_mm"], 1.0)
        self.assertEqual(band["width_mm"], 18.0)
        self.assertEqual(band["color"], "white")

    def test_build_derives_oak_color(self) -> None:
        spec = build_edge_banding("door", thickness=18.0, surface="oak__double_faced__grain")
        self.assertEqual(spec["四边"]["color"], "oak")

    def test_selection_overrides_default(self) -> None:
        spec = build_edge_banding(
            "side",
            thickness=18.0,
            surface="white__soft_touch__plain",
            selection={"material": "laser", "thickness": "t2_0"},
        )
        band = spec["四边"]
        self.assertEqual(band["material"], "laser")
        self.assertEqual(band["thickness_mm"], 2.0)

    def test_unknown_material_is_rejected(self) -> None:
        spec = furniture_spec()
        placements = plan_panels(spec, CabinetStructure.from_spec(spec))
        with self.assertRaisesRegex(ValueError, "material unknown"):
            plan_manufacturing(
                spec, placements,
                requested_options={"edge_banding": {"material": "wood"}},
            )

    def test_unknown_thickness_is_rejected(self) -> None:
        spec = furniture_spec()
        placements = plan_panels(spec, CabinetStructure.from_spec(spec))
        with self.assertRaisesRegex(ValueError, "thickness unknown"):
            plan_manufacturing(
                spec, placements,
                requested_options={"edge_banding": {"thickness": "t5_0"}},
            )

    def test_groove_back_panel_has_no_edge_banding(self) -> None:
        spec = furniture_spec(back_mount="groove")
        placements = plan_panels(spec, CabinetStructure.from_spec(spec))
        bom = plan_manufacturing(spec, placements)
        back = next(p for p in bom.panels if p.panel_type == "back")
        self.assertEqual(back.edge_banding, {})

    def test_from_edge_banding_structured(self) -> None:
        features = from_edge_banding(
            "side",
            {"四边": {"material": "abs", "thickness_mm": 1.0, "width_mm": 18.0, "color": "white"}},
        )
        self.assertEqual(len(features), 1)
        feature = features[0]
        self.assertEqual(feature.edges, "四边")
        self.assertEqual(feature.material, "abs")
        self.assertEqual(feature.thickness_mm, 1.0)
        self.assertEqual(feature.width_mm, 18.0)
        self.assertEqual(feature.color, "white")


if __name__ == "__main__":
    unittest.main()
