from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_design_intent.design_spec import FurnitureSpec
from furniture_feature_tree.feature_tree_builder import panels_to_feature_tree
from furniture_feature_tree.feature_tree_emitter import write_build123d_source
from furniture_layout.layout_pipeline import plan_layout
from furniture_manufacturing.manufacturing_bom import plan_manufacturing
from furniture_panel_planning.panel_planning import plan_panels


class BackGroovePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = FurnitureSpec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            shelf_count=0,
            n_doors=0,
        )
        self.layout = plan_layout(self.spec)
        self.placements = plan_panels(self.spec, self.layout)
        self.manufacturing = plan_manufacturing(self.spec, self.placements)
        self.feature_tree = panels_to_feature_tree(
            self.manufacturing.panels,
            self.manufacturing.operations,
            furniture_type=self.spec.furniture_type,
        )

    def test_layout_stage_contains_regions_not_panel_records(self) -> None:
        payload = asdict(self.layout)
        self.assertIn("internal_width", payload)
        self.assertNotIn("panels", payload)
        self.assertNotIn("placements", payload)

    def test_panel_stage_owns_back_and_toe_kick_dimensions(self) -> None:
        panels = {panel.id: panel for panel in self.placements}
        back = panels["back_panel"]
        self.assertEqual((back.size_x, back.size_y, back.size_z), (776.0, 9.0, 926.0))
        self.assertEqual((back.pos_x, back.pos_y, back.pos_z), (12.0, 18.0, 62.0))
        supports = [panel for panel in self.placements if panel.id.startswith("toe_kick_support_")]
        self.assertEqual(len(supports), 1)
        self.assertEqual((supports[0].pos_x, supports[0].size_y), (391.0, 513.0))

    def test_manufacturing_stage_owns_four_target_specific_grooves(self) -> None:
        operations = {operation.id: operation for operation in self.manufacturing.operations}
        self.assertEqual(
            set(operations),
            {
                "left_side_back_groove",
                "right_side_back_groove",
                "top_back_groove",
                "bottom_back_groove",
            },
        )
        self.assertEqual(operations["left_side_back_groove"].size_y, 10.0)
        self.assertEqual(operations["left_side_back_groove"].size_x, 6.0)

    def test_feature_tree_preserves_groove_cut_operations(self) -> None:
        self.assertEqual(self.feature_tree["schema_version"], 2)
        self.assertEqual(len(self.feature_tree["operations"]), 4)
        self.assertTrue(
            all(operation["type"] == "cut_box" for operation in self.feature_tree["operations"])
        )

    def test_emitted_build123d_geometry_subtracts_groove_volume(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_path = Path(temporary_directory) / "grooved_cabinet.py"
            write_build123d_source(self.feature_tree, source_path)
            module_spec = importlib.util.spec_from_file_location(
                "generated_grooved_cabinet",
                source_path,
            )
            assert module_spec is not None and module_spec.loader is not None
            module = importlib.util.module_from_spec(module_spec)
            module_spec.loader.exec_module(module)
            shape = module.gen_step()

        uncut_volume = sum(
            panel.size_x * panel.size_y * panel.size_z
            for panel in self.manufacturing.panels
        )
        removed_volume = sum(
            operation.size_x * operation.size_y * operation.size_z
            for operation in self.manufacturing.operations
        )
        self.assertAlmostEqual(shape.volume, uncut_volume - removed_volume, places=3)

    def test_invalid_groove_and_support_inputs_fail_before_layout(self) -> None:
        invalid_groove = FurnitureSpec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            groove_depth=19,
        )
        with self.assertRaisesRegex(ValueError, "groove_depth"):
            plan_layout(invalid_groove)

        invalid_supports = FurnitureSpec(
            furniture_type="floor_cabinet",
            width=100,
            depth=600,
            height=1000,
            board_thickness=18,
            toe_kick_support_count=4,
        )
        with self.assertRaisesRegex(ValueError, "toe_kick_support_count"):
            plan_layout(invalid_supports)

        with self.assertRaisesRegex(ValueError, "must be an integer"):
            FurnitureSpec.from_dict(
                {
                    "type": "floor_cabinet",
                    "toe_kick_support_count": "two",
                }
            )


if __name__ == "__main__":
    unittest.main()

