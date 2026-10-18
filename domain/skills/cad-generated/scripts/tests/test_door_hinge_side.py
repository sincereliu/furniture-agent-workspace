"""门板铰链侧：板件阶段给值，制造阶段只读。

口径见 `domain/skills/panel-plan/references/door-hinge-side.md`：

- **对开腔**由几何决定（左 left、右 right），写反直接拒；
- **单开腔**必须由提案给，不给就留空——留空的门不能开门、也排不了铰链孔；
- 制造**不再按门序推导**：门板带什么就用什么，只有老冻结文件没带时才回退。
"""

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
from furniture_workflow.project_layout_edit import _resolve_door_hinges
from furniture_panel_planning.assembly_tree import flatten_panels_for_handoff
from furniture_panel_planning.construction_geometry import (
    door_hinge_sides,
    door_panel_boxes,
)
from furniture_panel_planning.panel_pipeline import plan_panel_stage
from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.panel_spec import FurnitureSpec, spec_payload
from furniture_panel_planning.structure_planning import CabinetStructure
from panel_fixtures import by_role, cabinet_envelope, furniture_spec, panel_parameters


def _spec(**overrides) -> FurnitureSpec:
    values = {"shelves": [], "top_gap_mm": 0.0}
    values.update(overrides)
    return furniture_spec(**values)


def _five_door(**overrides) -> FurnitureSpec:
    """2500 五门三立板 = 2 扇对开 + 3 扇单开。"""
    values = {
        "width": 2500.0,
        "n_doors": 5,
        "dividers": [
            {"seam_index": 1},
            {"seam_index": 2},
            {"seam_index": 3},
        ],
    }
    values.update(overrides)
    return _spec(**values)


class HingeDerivationTests(unittest.TestCase):
    def test_a_two_door_cavity_is_hinged_left_then_right(self):
        spec = _spec(n_doors=2)
        self.assertEqual(
            door_hinge_sides(spec, CabinetStructure.from_spec(spec)),
            ["left", "right"],
        )

    def test_single_door_cavities_stay_unknown_without_a_proposal_value(self):
        spec = _five_door()
        # 前两扇是对开（自动），后三扇各占一个单开腔（几何定不了）。
        self.assertEqual(
            door_hinge_sides(spec, CabinetStructure.from_spec(spec)),
            ["left", "right", "", "", ""],
        )

    def test_the_proposal_fills_the_single_door_cavities(self):
        spec = _five_door(door_hinges=["left", "right", "right", "left", "right"])
        self.assertEqual(
            door_hinge_sides(spec, CabinetStructure.from_spec(spec)),
            ["left", "right", "right", "left", "right"],
        )

    def test_a_pair_written_backwards_is_rejected(self):
        spec = _five_door(door_hinges=["right", "left", "left", "left", "left"])
        with self.assertRaises(ValueError) as caught:
            door_hinge_sides(spec, CabinetStructure.from_spec(spec))
        self.assertIn("left then right", str(caught.exception))

    def test_one_entry_per_door_is_required(self):
        with self.assertRaises(ValueError) as caught:
            _five_door(door_hinges=["left", "right"])
        self.assertIn("one entry per door", str(caught.exception))

    def test_only_left_and_right_are_accepted(self):
        with self.assertRaises(ValueError) as caught:
            _spec(n_doors=2, door_hinges=["left", "middle"])
        self.assertIn("door hinge must be one of", str(caught.exception))

    def test_door_boxes_carry_the_hinge_side(self):
        spec = _five_door(door_hinges=["left", "right", "left", "right", "left"])
        boxes = door_panel_boxes(spec, CabinetStructure.from_spec(spec))
        self.assertEqual(
            [box.door_hinge_side for box in boxes],
            ["left", "right", "left", "right", "left"],
        )


class HingeSerializationTests(unittest.TestCase):
    def test_door_hinges_stay_out_of_the_payload_when_not_given(self):
        self.assertNotIn("door_hinges", spec_payload(_spec(n_doors=2)))

    def test_door_hinges_round_trip_when_given(self):
        payload = spec_payload(_five_door(door_hinges=["left", "right", "left", "left", "left"]))
        self.assertEqual(
            payload["door_hinges"], ["left", "right", "left", "left", "left"]
        )
        restored = FurnitureSpec.from_dict(payload)
        self.assertEqual(restored.door_hinges, payload["door_hinges"])

    def test_frozen_panels_record_the_hinge_side_on_doors_only(self):
        output = plan_panel_stage(
            (cabinet_envelope(width=2500.0, height=2590.0),),
            panel_parameters(
                n_doors=5,
                toe_kick_height=80.0,
                shelves=[],
                top_gap_mm=0.0,
                door_hinges=["left", "right", "right", "left", "right"],
                dividers=[
                    {"seam_index": 1},
                    {"seam_index": 2},
                    {"seam_index": 3},
                ],
            ),
        )
        panels = flatten_panels_for_handoff(output["cabinets"][0])
        doors = [item for item in panels if item["panel_type"] == "door"]
        self.assertEqual(
            [item["door_hinge_side"] for item in doors],
            ["left", "right", "right", "left", "right"],
        )
        side = next(item for item in panels if item["role"] == "left_side_panel")
        self.assertNotIn("door_hinge_side", side)


class ManufactureReadsHingeSideTests(unittest.TestCase):
    """制造不再推导：门板带什么就用什么。"""

    def _stage_cabinet(self, **overrides):
        output = plan_panel_stage(
            (cabinet_envelope(width=2500.0, height=2590.0),),
            panel_parameters(
                n_doors=5,
                toe_kick_height=80.0,
                shelves=[],
                top_gap_mm=0.0,
                dividers=[
                    {"seam_index": 1},
                    {"seam_index": 2},
                    {"seam_index": 3},
                ],
                **overrides,
            ),
        )
        cabinet = output["cabinets"][0]
        return FurnitureSpec.from_dict(cabinet["spec"]), flatten_panels_for_handoff(cabinet)

    def test_five_doors_reach_manufacturing(self):
        spec, panels = self._stage_cabinet(
            door_hinges=["left", "right", "right", "left", "right"],
        )
        bom = plan_manufacturing(spec, panels)
        doors = [item for item in bom.panels if item.panel_type == "door"]
        self.assertEqual(len(doors), 5)
        self.assertEqual(
            [item.door_hinge_side for item in doors],
            ["left", "right", "right", "left", "right"],
        )
        self.assertTrue(
            any("铰链" in item.name for item in bom.hardware),
            [item.name for item in bom.hardware],
        )

    def test_a_five_door_plan_without_hinge_sides_still_fails_loudly(self):
        """板件阶段只报警告；到底是谁没定，制造这边点名说清楚，不猜。"""
        spec, panels = self._stage_cabinet()
        with self.assertRaises(ValueError) as caught:
            plan_manufacturing(spec, panels)
        self.assertIn("door hinge side is not decided yet", str(caught.exception))

    def test_legacy_panels_without_the_field_still_derive(self):
        spec = furniture_spec(n_doors=2, shelves=[], top_gap_mm=0.0)
        placements = plan_panels(spec, CabinetStructure.from_spec(spec))
        legacy = []
        for item in placements:
            payload = {
                "id": item.id,
                "name": item.name,
                "panel_type": item.panel_type,
                "size_x": item.size_x,
                "size_y": item.size_y,
                "size_z": item.size_z,
                "pos_x": item.pos_x,
                "pos_y": item.pos_y,
                "pos_z": item.pos_z,
                "material_role": item.material_role,
                "role": item.role,
                "parent_id": item.parent_id,
                "depends_on": list(item.depends_on),
                "joints": [],
            }
            legacy.append(payload)
        bom = plan_manufacturing(spec, legacy)
        doors = {item.role: item.door_hinge_side for item in bom.panels if item.panel_type == "door"}
        self.assertEqual(doors, {"left_door": "left", "right_door": "right"})

    def test_legacy_single_door_still_needs_the_option(self):
        spec = furniture_spec(n_doors=1, shelves=[], top_gap_mm=0.0)
        placements = plan_panels(spec, CabinetStructure.from_spec(spec))
        legacy = []
        for item in placements:
            legacy.append({
                "id": item.id,
                "name": item.name,
                "panel_type": item.panel_type,
                "size_x": item.size_x,
                "size_y": item.size_y,
                "size_z": item.size_z,
                "pos_x": item.pos_x,
                "pos_y": item.pos_y,
                "pos_z": item.pos_z,
                "material_role": item.material_role,
                "role": item.role,
                "parent_id": item.parent_id,
                "depends_on": list(item.depends_on),
                "joints": [],
            })
        with self.assertRaises(ValueError) as caught:
            plan_manufacturing(spec, legacy)
        self.assertIn("single door", str(caught.exception))


class HingeChoiceTests(unittest.TestCase):
    """页面上「选左开/右开」走的那套判定（`_resolve_door_hinges`）。"""

    def _cabinet(self):
        output = plan_panel_stage(
            (cabinet_envelope(width=2500.0, height=2590.0),),
            panel_parameters(
                n_doors=5,
                toe_kick_height=80.0,
                shelves=[],
                top_gap_mm=0.0,
                dividers=[
                    {"seam_index": 1},
                    {"seam_index": 2},
                    {"seam_index": 3},
                ],
            ),
        )
        return output["cabinets"][0]

    def test_choosing_every_undecided_door_fills_the_run(self):
        cabinet = self._cabinet()
        result = _resolve_door_hinges(
            "cabinet_1",
            cabinet,
            {
                "cabinet_1__door_3": "right",
                "cabinet_1__door_4": "left",
                "cabinet_1__door_5": "right",
            },
        )
        self.assertEqual(
            result["door_hinges"], ["left", "right", "right", "left", "right"]
        )

    def test_leaving_one_undecided_is_refused(self):
        cabinet = self._cabinet()
        with self.assertRaises(ValueError) as caught:
            _resolve_door_hinges(
                "cabinet_1", cabinet, {"cabinet_1__door_3": "right"}
            )
        self.assertIn("still have no hinge side", str(caught.exception))

    def test_a_paired_door_cannot_be_flipped(self):
        cabinet = self._cabinet()
        with self.assertRaises(ValueError) as caught:
            _resolve_door_hinges(
                "cabinet_1",
                cabinet,
                {
                    "cabinet_1__door_1": "right",
                    "cabinet_1__door_3": "right",
                    "cabinet_1__door_4": "left",
                    "cabinet_1__door_5": "right",
                },
            )
        self.assertIn("cannot be changed", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
