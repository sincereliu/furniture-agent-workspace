"""中立板（最小一刀）：缝定锚、按腔分段、两张大面接端面。

口径见 `references/interior-structure-contract.md` 与
`references/panel-definition-rules.md`。这里只验算出来的毫米、拒绝条件和序列化。
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_panel_planning.assembly_tree import flatten_panels_for_handoff
from furniture_panel_planning.cabinet_identity import panel_role
from furniture_panel_planning.construction_geometry import (
    back_panel_boxes,
    divider_panel_boxes,
    interior_cavity_bounds,
    shelf_panel_boxes,
)
from furniture_panel_planning.panel_pipeline import plan_panel_stage
from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.panel_spec import FurnitureSpec, spec_payload
from furniture_panel_planning.structure_planning import CabinetStructure
from furniture_panel_planning.validation_panels import validate_panels
from panel_fixtures import by_role, cabinet_envelope, furniture_spec, panel_parameters


def _spec_with_divider(seam_align: str | None = None, **overrides) -> FurnitureSpec:
    """两扇门 + 一条缝上的中立板 → 两个单开腔，所以铰链侧要逐扇给。"""
    divider = {"seam_index": 0}
    if seam_align is not None:
        divider["seam_align"] = seam_align
    values = {"door_hinges": ["left", "right"]}
    values.update(overrides)
    return furniture_spec(dividers=[divider], **values)


class DividerGeometryTests(unittest.TestCase):
    """800×1000×600、两扇门、4 层板：中立板站在内部净空正中。"""

    def test_divider_geometry_matches_the_reference_case(self):
        spec = _spec_with_divider()
        structure = CabinetStructure.from_spec(spec)
        boxes = divider_panel_boxes(spec, structure)
        self.assertEqual(len(boxes), 1)
        box = boxes[0]
        self.assertEqual(box.panel_id, "divider_1")
        # 18 厚、深 580（通到柜背，不是只到内空前沿）、高 914，
        # 站在底板上表面 (z=68)、柜背 (y=0)。
        self.assertEqual(box.geometry, (18.0, 580.0, 914.0, 391.0, 0.0, 68.0))

    def test_cavity_bounds_split_at_the_seam(self):
        spec = _spec_with_divider()
        structure = CabinetStructure.from_spec(spec)
        self.assertEqual(
            interior_cavity_bounds(spec, structure),
            [(18.0, 391.0), (409.0, 782.0)],
        )
        self.assertEqual([end - start for start, end in
                          interior_cavity_bounds(spec, structure)], [373.0, 373.0])

    def test_seam_align_moves_the_divider_relative_to_the_seam(self):
        structure = CabinetStructure.from_spec(_spec_with_divider())
        expected = {
            "center": (391.0, 409.0),
            "left_face": (400.0, 418.0),
            "right_face": (382.0, 400.0),
        }
        for align, (start, end) in expected.items():
            with self.subTest(align=align):
                box = divider_panel_boxes(_spec_with_divider(align), structure)[0]
                self.assertAlmostEqual(box.pos_x, start)
                self.assertAlmostEqual(box.pos_x + box.size_x, end)

    def test_shelves_are_split_per_cavity_only_when_a_divider_exists(self):
        without = furniture_spec()
        structure = CabinetStructure.from_spec(without)
        plain = shelf_panel_boxes(without, structure)
        self.assertEqual(len(plain), 4)
        self.assertTrue(all(box.panel_id.startswith("shelf_z") for box in plain))
        self.assertTrue(
            all(box.size_x == structure.internal_width for box in plain)
        )

        with_divider = _spec_with_divider()
        split = shelf_panel_boxes(with_divider, structure)
        self.assertEqual(len(split), 8)
        self.assertEqual(
            [box.panel_id.rsplit("_z", 1)[0] for box in split],
            ["shelf_c1", "shelf_c2"] * 4,
        )
        self.assertTrue(all(box.size_x == 373.0 for box in split))

    def test_segmented_shelves_carry_their_cavity_in_the_name(self):
        spec = _spec_with_divider()
        panels = by_role(plan_panels(spec, CabinetStructure.from_spec(spec)))
        self.assertEqual(panels["shelf_c1_z805"].name, "层板(腔1·805mm)")
        self.assertEqual(panels["shelf_c2_z805"].name, "层板(腔2·805mm)")
        plain = furniture_spec()
        single = by_role(plan_panels(plain, CabinetStructure.from_spec(plain)))
        self.assertEqual(single["shelf_z805"].name, "层板(805mm)")

    def test_divider_is_shelved_half_way_between_both_cavities(self):
        spec = _spec_with_divider()
        structure = CabinetStructure.from_spec(spec)
        panels = by_role(plan_panels(spec, structure))
        divider = panels["divider_1"]
        self.assertEqual(divider.panel_type, "divider")
        self.assertEqual(divider.inner_face, "+x")
        self.assertEqual(divider.outer_face, "-x")
        # 少一张就不是"两张朝柜内的大面"了。
        self.assertEqual(divider.bearing_faces, ["-x"])
        self.assertEqual(divider.grain_axis, "z")


class DividerContactTests(unittest.TestCase):
    def test_divider_bears_on_shelves_from_both_sides(self):
        spec = _spec_with_divider()
        structure = CabinetStructure.from_spec(spec)
        divider = by_role(plan_panels(spec, structure))["divider_1"]
        bearing = [joint for joint in divider.joints if joint.bearing_id.endswith("divider_1")]
        faces = {joint.face for joint in bearing}
        self.assertEqual(faces, {"+x", "-x"})
        left = [j for j in bearing if j.face == "-x"]
        right = [j for j in bearing if j.face == "+x"]
        self.assertTrue(left and right)
        self.assertTrue(all("_c1_" in joint.end_id for joint in left))
        self.assertTrue(all("_c2_" in joint.end_id for joint in right))
        # 中立板的端面还顶在顶板、底板、背板上。
        ends = {joint.end_id.rsplit("__", 1)[-1] for joint in divider.joints}
        self.assertIn("divider_1", ends)


class DividerAdmissionTests(unittest.TestCase):
    def test_a_divider_needs_an_inner_seam(self):
        with self.assertRaises(ValueError) as caught:
            furniture_spec(n_doors=1, dividers=[{"seam_index": 0}])
        self.assertIn("at least 2 doors", str(caught.exception))

    def test_a_drawer_zone_cannot_take_a_divider(self):
        with self.assertRaises(ValueError) as caught:
            furniture_spec(
                n_doors=0, drawer_count=1, shelves=[],
                dividers=[{"seam_index": 0}],
            )
        self.assertIn("cannot take a divider", str(caught.exception))

    def test_two_dividers_on_one_seam_are_blocked(self):
        spec = furniture_spec(
            dividers=[{"seam_index": 0}, {"seam_index": 0}],
        )
        with self.assertRaises(ValueError) as caught:
            divider_panel_boxes(spec, CabinetStructure.from_spec(spec))
        self.assertIn("divider layout is blocked", str(caught.exception))

    def test_divider_seam_index_must_be_an_inner_seam(self):
        spec = furniture_spec(dividers=[{"seam_index": 1}])
        with self.assertRaises(ValueError) as caught:
            divider_panel_boxes(spec, CabinetStructure.from_spec(spec))
        self.assertIn("outside the inner seams", str(caught.exception))

    def test_divider_entries_reject_unknown_keys(self):
        for entry, key in (
            ({"seam_index": 0, "thickness_mm": 18}, "thickness_mm"),
            ({"id": "d1"}, "id"),
        ):
            with self.subTest(entry=entry):
                with self.assertRaises(ValueError) as caught:
                    furniture_spec(dividers=[entry])
                self.assertIn(key, str(caught.exception))

    def test_divider_align_must_be_a_known_value(self):
        with self.assertRaises(ValueError) as caught:
            furniture_spec(dividers=[{"seam_index": 0, "seam_align": "middle"}])
        self.assertIn("seam_align", str(caught.exception))


class DividerSerializationTests(unittest.TestCase):
    def test_spec_payload_omits_an_empty_dividers_key(self):
        self.assertNotIn("dividers", spec_payload(furniture_spec()))
        self.assertEqual(
            spec_payload(_spec_with_divider())["dividers"],
            [{"seam_index": 0, "seam_align": "center"}],
        )

    def test_serialized_spec_without_dividers_still_loads(self):
        payload = spec_payload(furniture_spec())
        payload.pop("dividers", None)
        restored = FurnitureSpec.from_dict(payload)
        self.assertEqual(restored.dividers, [])
        self.assertEqual(spec_payload(restored), payload)

    def test_serialized_spec_with_dividers_round_trips(self):
        payload = spec_payload(_spec_with_divider("left_face"))
        self.assertEqual(payload["dividers"], [{"seam_index": 0, "seam_align": "left_face"}])
        restored = FurnitureSpec.from_dict(payload)
        self.assertEqual(restored.dividers[0].seam_index, 0)
        self.assertEqual(restored.dividers[0].seam_align, "left_face")
        self.assertEqual(spec_payload(restored), payload)

    def test_divider_payload_records_both_bearing_faces(self):
        output = plan_panel_stage(
            (cabinet_envelope(),),
            panel_parameters(dividers=[{"seam_index": 0}]),
        )
        panels = flatten_panels_for_handoff(output["cabinets"][0])
        divider = next(item for item in panels if item["role"] == "divider_1")
        self.assertEqual(divider["bearing_faces"], ["-x"])
        # 常规板不落这个键，老工程的产出逐字节不变。
        side = next(item for item in panels if item["role"] == "left_side_panel")
        self.assertNotIn("bearing_faces", side)


class BackPanelSplitTests(unittest.TestCase):
    """背板跟着立板分腔：每腔一块，夹在侧板与中立板之间。

    立板通到柜背，背板不能从立板背后通过；每腔那块的两条竖边分别落进侧板或
    立板的背板槽里。
    """

    def test_groove_back_is_cut_once_per_cavity(self):
        spec = _spec_with_divider()
        structure = CabinetStructure.from_spec(spec)
        boxes = back_panel_boxes(spec, structure)
        self.assertEqual([box.panel_id for box in boxes],
                         ["back_panel_1", "back_panel_2"])
        # 两侧各入槽 6：左块 12→397、右块 403→788，中间留出立板的 18 减两个槽深。
        self.assertEqual([box.geometry for box in boxes], [
            (385.0, 9.0, 926.0, 12.0, 18.0, 62.0),
            (385.0, 9.0, 926.0, 403.0, 18.0, 62.0),
        ])

    def test_insert_back_has_no_groove_allowance(self):
        spec = _spec_with_divider(back_mount="insert")
        structure = CabinetStructure.from_spec(spec)
        boxes = back_panel_boxes(spec, structure)
        self.assertEqual([box.geometry for box in boxes], [
            (373.0, 18.0, 914.0, 18.0, 18.0, 68.0),
            (373.0, 18.0, 914.0, 409.0, 18.0, 68.0),
        ])

    def test_cover_back_stays_one_piece(self):
        spec = _spec_with_divider(back_mount="cover")
        structure = CabinetStructure.from_spec(spec)
        boxes = back_panel_boxes(spec, structure)
        self.assertEqual([box.panel_id for box in boxes], ["back_panel"])
        self.assertEqual(boxes[0].geometry, (800.0, 9.0, 1000.0, 0.0, 0.0, 0.0))

    def test_no_divider_keeps_the_old_single_piece(self):
        spec = furniture_spec()
        structure = CabinetStructure.from_spec(spec)
        boxes = back_panel_boxes(spec, structure)
        self.assertEqual([box.panel_id for box in boxes], ["back_panel"])
        self.assertEqual(boxes[0].size_x, structure.internal_width + 12.0)

    def test_panel_stage_emits_one_named_piece_per_cavity(self):
        spec = _spec_with_divider()
        panels = by_role(plan_panels(spec, CabinetStructure.from_spec(spec)))
        self.assertEqual(
            [panels[key].name for key in ("back_panel_1", "back_panel_2")],
            ["背板1", "背板2"],
        )
        # 每块都夹在侧板与中立板之间（或侧板/立板与顶底板）之间。
        self.assertEqual(
            [panel_role(item) for item in panels["back_panel_1"].depends_on],
            ["left_side_panel", "divider_1", "top_panel", "bottom_panel"],
        )
        self.assertEqual(
            [panel_role(item) for item in panels["back_panel_2"].depends_on],
            ["divider_1", "right_side_panel", "top_panel", "bottom_panel"],
        )

    def test_back_rails_are_cut_per_cavity(self):
        spec = _spec_with_divider()
        panels = by_role(plan_panels(spec, CabinetStructure.from_spec(spec)))
        rails = sorted(
            (item for item in panels.values() if item.panel_type == "back_rail"),
            key=lambda item: item.pos_x,
        )
        # 内空高 914 → 每腔一根拉条；拉条钉在腔里，不穿过立板，宽度就是腔宽。
        self.assertEqual([item.role for item in rails],
                         ["back_rail_c1_1", "back_rail_c2_1"])
        self.assertEqual([item.size_x for item in rails], [373.0, 373.0])
        self.assertEqual([item.name for item in rails],
                         ["背拉条(腔1·1)", "背拉条(腔2·1)"])
        self.assertEqual(
            [item.pos_x for item in rails], [18.0, 409.0],
        )

    def test_validation_reports_a_missing_piece(self):
        spec = _spec_with_divider()
        structure = CabinetStructure.from_spec(spec)
        panels = plan_panels(spec, structure)
        without = [
            item for item in panels if panel_role(item.id) != "back_panel_2"
        ]
        report = validate_panels(spec, structure, without)
        self.assertIn("BACK_PANEL_COUNT_MISMATCH",
                      {issue.code for issue in report.issues})

    def test_validation_reports_a_back_spanning_behind_the_divider(self):
        spec = _spec_with_divider()
        structure = CabinetStructure.from_spec(spec)
        panels = plan_panels(spec, structure)
        # 把右边那块推回去 20mm：它就骑到立板背后去了。
        moved = [
            replace(item, pos_x=item.pos_x - 20.0)
            if panel_role(item.id) == "back_panel_2"
            else item
            for item in panels
        ]
        report = validate_panels(spec, structure, moved)
        self.assertIn("BACK_PANEL_SPAN_MISMATCH",
                      {issue.code for issue in report.issues})

    def test_a_complete_split_plan_has_no_back_issues(self):
        spec = _spec_with_divider()
        structure = CabinetStructure.from_spec(spec)
        report = validate_panels(spec, structure, plan_panels(spec, structure))
        self.assertEqual(report.issues, [])


class DividerOutputValidationTests(unittest.TestCase):
    def test_missing_divider_panel_is_reported(self):
        spec = _spec_with_divider()
        structure = CabinetStructure.from_spec(spec)
        panels = plan_panels(spec, structure)
        without = [item for item in panels if item.panel_type != "divider"]
        report = validate_panels(spec, structure, without)
        codes = {issue.code for issue in report.issues}
        self.assertIn("DIVIDER_PANEL_COUNT_MISMATCH", codes)

    def test_a_complete_plan_has_no_divider_issues(self):
        spec = _spec_with_divider()
        structure = CabinetStructure.from_spec(spec)
        report = validate_panels(spec, structure, plan_panels(spec, structure))
        self.assertEqual(report.issues, [])


if __name__ == "__main__":
    unittest.main()
