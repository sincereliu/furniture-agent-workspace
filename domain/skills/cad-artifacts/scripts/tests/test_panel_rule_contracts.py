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
from furniture_panel_planning.panel_pipeline import plan_panel_cabinets, plan_panel_stage
from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.panel_rules import (
    resolve_toe_kick_support_count,
    toe_kick_support_clear_spacing,
)
from furniture_panel_planning.panel_spec import (
    FurnitureSpec,
    PANEL_PARAMETER_FIELDS,
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


if __name__ == "__main__":
    unittest.main()