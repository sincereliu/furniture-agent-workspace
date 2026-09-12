from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_design_intent.design_intent import DesignIntent, FinishedEnvelope
from furniture_panel_planning.cabinet_identity import panel_role
from furniture_panel_planning.construction_geometry import (
    drawer_panel_boxes,
    toe_kick_support_boxes,
)
from furniture_panel_planning.cabinet_identity import require_primary_handoff
from furniture_panel_planning.joint_topology import PanelJoint
from furniture_panel_planning.panel_pipeline import plan_panel_cabinets, plan_panel_stage
from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.panel_rules import (
    toe_kick_support_clear_spacing,
)
from furniture_panel_planning.panel_spec import (
    FurnitureSpec,
    PANEL_PARAMETER_FIELDS,
    PANEL_STOCK_FIELDS,
    resolve_shelf_gaps,
)
from furniture_panel_planning.structure_planning import CabinetStructure
from furniture_workflow.input_adapter import MANUFACTURING_SPEC_FIELDS
from panel_fixtures import by_role, furniture_spec, panel_parameters


class PanelRuleContractTests(unittest.TestCase):
    def test_single_auto_shelf_gap_absorbs_remaining_internal_height(self) -> None:
        spec = furniture_spec(
            furniture_category="floor_cabinet",
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

    def test_toe_kick_support_count_must_be_explicit(self) -> None:
        self.assertEqual(
            toe_kick_support_clear_spacing(764.0, 1, 18.0),
            373.0,
        )
        intent = DesignIntent(
            furniture_category="floor_cabinet",
            finished_envelope=FinishedEnvelope(800, 600, 1000),
            confirmed=True,
        )
        params = panel_parameters()
        params["toe_kick_support_count"] = None
        with self.assertRaisesRegex(ValueError, "toe_kick_support_count"):
            FurnitureSpec.from_intent(intent, params)

    def test_drawer_dimension_chain_matches_reference_sample(self) -> None:
        spec = furniture_spec(
            furniture_category="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            n_doors=0,
            shelf_count=0,
            drawer_count=3,
        )

        structure = CabinetStructure.from_spec(spec)
        placements = by_role(plan_panels(spec, structure))

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

        expected_front = next(
            box for box in drawer_panel_boxes(spec, structure)
            if box.panel_id == "drawer_front_z68"
        )
        expected_support = toe_kick_support_boxes(spec, structure)[0]
        self.assertEqual(
            tuple(round(value, 3) for value in expected_front.geometry),
            (761.0, 18.0, 303.167, 19.5, 562.0, 68.0),
        )
        self.assertEqual(
            tuple(round(value, 3) for value in expected_support.geometry),
            (18.0, 513.0, 50.0, 391.0, 48.0, 0.0),
        )

    def test_two_cabinets_qualify_panel_ids_under_distinct_parents(self) -> None:
        spec = furniture_spec()
        structure = CabinetStructure.from_spec(spec)
        first = plan_panels(spec, structure, cabinet_id="cab_a")
        second = plan_panels(spec, structure, cabinet_id="cab_b")
        self.assertTrue(all(panel.parent_id == "cab_a" for panel in first))
        self.assertTrue(all(panel.parent_id == "cab_b" for panel in second))
        self.assertEqual({panel.role for panel in first}, {panel.role for panel in second})
        self.assertFalse({panel.id for panel in first} & {panel.id for panel in second})
        self.assertTrue(all(panel.id.startswith("cab_a__") for panel in first))
        self.assertIn("left_side_panel", {panel.role for panel in first})

        intent = DesignIntent(
            furniture_category="floor_cabinet",
            finished_envelope=FinishedEnvelope(800, 600, 1000),
            confirmed=True,
        )
        output = plan_panel_cabinets(
            (
                (intent, {**panel_parameters(), "cabinet_id": "cab_a"}),
                (intent, {**panel_parameters(), "cabinet_id": "cab_b"}),
            )
        )
        self.assertEqual(set(output), {"cabinets"})
        self.assertEqual([item["id"] for item in output["cabinets"]], ["cab_a", "cab_b"])
        roles_a = {panel_role(item["id"]) for item in output["cabinets"][0]["panels"]}
        roles_b = {panel_role(item["id"]) for item in output["cabinets"][1]["panels"]}
        self.assertEqual(roles_a, roles_b)
        ids_a = {item["id"] for item in output["cabinets"][0]["panels"]}
        ids_b = {item["id"] for item in output["cabinets"][1]["panels"]}
        self.assertFalse(ids_a & ids_b)

    def test_shelf_entries_require_shelf_type(self) -> None:
        with self.assertRaises(ValueError):
            furniture_spec(
                shelves=[{"type": "fixed", "gap_below_mm": 100.0}],
                top_gap_mm=100.0,
            )

    def test_panel_runtime_rejects_historical_field_names(self) -> None:
        spec = furniture_spec(n_doors=2)
        payload = spec.__dict__.copy()
        payload["furniture_type"] = payload["furniture_category"]
        with self.assertRaisesRegex(ValueError, "does not support"):
            FurnitureSpec.from_dict(payload)
        payload = spec.__dict__.copy()
        payload["type"] = payload["furniture_category"]
        with self.assertRaisesRegex(ValueError, "does not support"):
            FurnitureSpec.from_dict(payload)
        payload = spec.__dict__.copy()
        payload["door_margin"] = payload["front_face_margin"]
        with self.assertRaisesRegex(ValueError, "does not support"):
            FurnitureSpec.from_dict(payload)
        payload = spec.__dict__.copy()
        payload["movable_shelf_connector"] = "two_in_one"
        with self.assertRaisesRegex(ValueError, "does not support"):
            FurnitureSpec.from_dict(payload)
        payload = spec.__dict__.copy()
        payload["door_hinge_side"] = "left"
        with self.assertRaisesRegex(ValueError, "does not support"):
            FurnitureSpec.from_dict(payload)

        structure = CabinetStructure.from_spec(spec)
        structure_payload = structure.__dict__.copy()
        structure_payload["door_count"] = structure_payload.pop("n_doors")
        with self.assertRaises(TypeError):
            CabinetStructure.from_dict(structure_payload)
        structure_payload = structure.__dict__.copy()
        structure_payload["furniture_type"] = structure_payload["furniture_category"]
        with self.assertRaises(TypeError):
            CabinetStructure.from_dict(structure_payload)

        intent = DesignIntent(
            furniture_category="floor_cabinet",
            finished_envelope=FinishedEnvelope(800, 600, 1000),
            confirmed=True,
        )
        params = panel_parameters()
        params["door_margin"] = params.pop("front_face_margin")
        with self.assertRaisesRegex(ValueError, "does not support"):
            FurnitureSpec.from_intent(intent, params)
        params = panel_parameters()
        params["back_mount"] = "auto"
        with self.assertRaisesRegex(ValueError, "back_mount"):
            FurnitureSpec.from_intent(intent, params)
        params = panel_parameters()
        params["shelves"] = [{"shelf_type": "fixed", "gap_below_mm": "auto"}]
        params["top_gap_mm"] = 100.0
        with self.assertRaises(ValueError):
            FurnitureSpec.from_intent(intent, params)

    def test_sheet_stock_process_card_expands_omitted_fields(self) -> None:
        intent = DesignIntent(
            furniture_category="floor_cabinet",
            finished_envelope=FinishedEnvelope(800, 600, 1000),
            confirmed=True,
        )
        params = panel_parameters()
        for name in PANEL_STOCK_FIELDS:
            params.pop(name)
        spec = FurnitureSpec.from_intent(intent, params)
        self.assertEqual(spec.board_thickness, 18.0)
        self.assertEqual(spec.back_thickness, 9.0)
        self.assertEqual(spec.door_thickness, 18.0)
        self.assertEqual(spec.drawer_bottom_thickness, 18.0)
        self.assertEqual(spec.drawer_back_thickness, 18.0)

    def test_sheet_stock_carcass_22_binds_box_and_keeps_back_at_9(self) -> None:
        spec = furniture_spec(board_thickness=22)
        self.assertEqual(spec.board_thickness, 22.0)
        self.assertEqual(spec.door_thickness, 22.0)
        self.assertEqual(spec.back_thickness, 9.0)
        self.assertEqual(spec.drawer_bottom_thickness, 22.0)
        self.assertEqual(spec.drawer_back_thickness, 22.0)
        structure = CabinetStructure.from_spec(spec)
        panels = by_role(plan_panels(spec, structure))
        self.assertEqual(panels["left_side_panel"].size_x, 22.0)
        back = next(
            panel for panel in panels.values() if panel.material_role == "back"
        )
        self.assertEqual(back.size_y, 9.0)

    def test_sheet_stock_door_may_be_22_when_carcass_is_18(self) -> None:
        spec = furniture_spec(door_thickness=22)
        self.assertEqual(spec.board_thickness, 18.0)
        self.assertEqual(spec.door_thickness, 22.0)
        doors = [
            panel
            for panel in plan_panels(spec, CabinetStructure.from_spec(spec))
            if panel.material_role == "door"
        ]
        self.assertTrue(doors)
        self.assertTrue(
            all(min(panel.size_x, panel.size_y, panel.size_z) == 22.0 for panel in doors)
        )

    def test_sheet_stock_insert_back_follows_carcass_stock(self) -> None:
        spec = furniture_spec(back_mount="insert")
        self.assertEqual(spec.back_thickness, 18.0)
        spec = furniture_spec(back_mount="insert", board_thickness=22)
        self.assertEqual(spec.back_thickness, 22.0)
        with self.assertRaisesRegex(ValueError, "back_thickness must be 22"):
            furniture_spec(back_mount="insert", board_thickness=22, back_thickness=9)

    def test_sheet_stock_rejects_values_outside_catalog(self) -> None:
        with self.assertRaisesRegex(ValueError, "board_thickness must be one of"):
            furniture_spec(board_thickness=16)
        with self.assertRaisesRegex(ValueError, "back_thickness must be 9"):
            furniture_spec(back_thickness=18)
        intent = DesignIntent(
            furniture_category="floor_cabinet",
            finished_envelope=FinishedEnvelope(800, 600, 1000),
            confirmed=True,
        )
        params = panel_parameters(board_thickness=22, drawer_bottom_thickness=18)
        with self.assertRaisesRegex(ValueError, "drawer_bottom_thickness must equal"):
            FurnitureSpec.from_intent(intent, params)

    def test_proposal_contract_complete_fields_match_runtime(self) -> None:
        contract = (
            WORKSPACE_ROOT
            / "domain"
            / "skills"
            / "panel-plan"
            / "references"
            / "panel-proposal-contract.md"
        ).read_text(encoding="utf-8")
        match = re.search(
            r"^## 完整字段\r?\n(?P<body>.*?)(?=^## )",
            contract,
            flags=re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(match, "panel-proposal-contract.md missing ## 完整字段")
        listed = set(re.findall(r"`([a-z][a-z0-9_]*)`", match.group("body")))
        self.assertEqual(listed, PANEL_PARAMETER_FIELDS | {"cabinet_id"})
        self.assertTrue(listed.isdisjoint(MANUFACTURING_SPEC_FIELDS))

    def test_panel_output_is_only_cabinets(self) -> None:
        intent = DesignIntent(
            furniture_category="floor_cabinet",
            finished_envelope=FinishedEnvelope(800, 600, 1000),
            confirmed=True,
        )
        output = plan_panel_stage(intent, panel_parameters())
        self.assertEqual(set(output), {"cabinets"})
        spec, structure, panels = require_primary_handoff(output)
        self.assertEqual(spec["board_thickness"], 18.0)
        self.assertIn("internal_width", structure)
        self.assertTrue(panels)

        with self.assertRaisesRegex(ValueError, "requires cabinets"):
            require_primary_handoff({})
        with self.assertRaisesRegex(ValueError, "does not support"):
            require_primary_handoff(
                {
                    "cabinets": output["cabinets"],
                    "spec": spec,
                    "panels": panels,
                }
            )

    def test_contact_output_uses_bearing_and_end_ids(self) -> None:
        intent = DesignIntent(
            furniture_category="floor_cabinet",
            finished_envelope=FinishedEnvelope(800, 600, 1000),
            confirmed=True,
        )
        output = plan_panel_stage(intent, panel_parameters())
        contacts = [
            joint
            for panel in output["cabinets"][0]["panels"]
            for joint in panel["joints"]
        ]
        self.assertTrue(contacts)
        for joint in contacts:
            self.assertIn("bearing_id", joint)
            self.assertIn("end_id", joint)
            self.assertNotIn("female_id", joint)
            self.assertNotIn("male_id", joint)
            restored = PanelJoint.from_dict(joint)
            self.assertEqual(restored.bearing_id, joint["bearing_id"])
            self.assertEqual(restored.end_id, joint["end_id"])

        with self.assertRaisesRegex(ValueError, "female_id"):
            PanelJoint.from_dict(
                {
                    "female_id": "cabinet_1__left_side_panel",
                    "male_id": "cabinet_1__top_panel",
                    "face": "+x",
                    "edge_axis": "x",
                    "edge_sign": -1,
                    "end_z": 991.0,
                }
            )


if __name__ == "__main__":
    unittest.main()