from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_panel_planning.interior_structure import evaluate_interior


def _front(**overrides: object) -> dict:
    spec = {
        "width_mm": 1200,
        "door_count": 2,
        "margin_mm": 1.5,
        "side_thickness_mm": 18,
    }
    spec.update(overrides)
    return spec


class InteriorStructureTests(unittest.TestCase):
    def test_seven_doors_keep_a_3mm_gap_and_whole_millimeter_widths(self) -> None:
        report = evaluate_interior(
            _front(width_mm=2400, door_count=7, pairs=[[0, 1]])
        )

        self.assertFalse(report["blocked"])
        self.assertEqual(report["findings"], [])
        doors = report["doors"]
        self.assertEqual(doors["door_widths_mm"], [340, 340, 340, 340, 340, 340, 339])
        self.assertEqual(doors["gaps_mm"], [3, 3, 3, 3, 3, 3])
        self._assert_mm(doors["left_margin_mm"], 1.5)
        self._assert_mm(doors["right_margin_mm"], 1.5)

    def test_pairs_do_not_change_door_widths(self) -> None:
        paired = evaluate_interior(
            _front(width_mm=2400, door_count=7, pairs=[[5, 6]])
        )
        plain = evaluate_interior(_front(width_mm=2400, door_count=7))

        self.assertEqual(
            paired["doors"]["door_widths_mm"],
            plain["doors"]["door_widths_mm"],
        )
        self.assertEqual(paired["doors"]["gaps_mm"], plain["doors"]["gaps_mm"])

    def test_four_doors_give_the_extra_millimeters_to_the_left(self) -> None:
        report = evaluate_interior(_front(width_mm=1211, door_count=4))

        doors = report["doors"]
        self.assertEqual(doors["door_widths_mm"], [300, 300, 300, 299])
        self.assertEqual(doors["gaps_mm"], [3, 3, 3])

    def test_six_doors_leave_the_last_door_1mm_narrower(self) -> None:
        report = evaluate_interior(_front(width_mm=1511, door_count=6))

        doors = report["doors"]
        self.assertEqual(doors["door_widths_mm"], [249, 249, 249, 249, 249, 248])
        self.assertEqual(doors["gaps_mm"], [3, 3, 3, 3, 3])

    def test_submillimeter_width_stays_on_the_right_margin(self) -> None:
        report = evaluate_interior(_front(width_mm=1200.3, door_count=4))

        doors = report["doors"]
        self.assertEqual(doors["door_widths_mm"], [297, 297, 297, 297])
        self.assertEqual(doors["gaps_mm"], [3, 3, 3])
        self._assert_mm(doors["left_margin_mm"], 1.5)
        self._assert_mm(doors["right_margin_mm"], 1.8)

    def test_single_and_pair_divider_reports_intervals_and_clearances(self) -> None:
        report = evaluate_interior(
            _front(
                width_mm=1200,
                door_count=3,
                pairs=[[1, 2]],
                dividers=[
                    {
                        "id": "divider_1",
                        "seam_index": 0,
                        "thickness_mm": 18,
                    }
                ],
            )
        )

        self.assertFalse(report["blocked"])
        doors = report["doors"]
        self.assertEqual(doors["door_widths_mm"], [397, 397, 397])
        self._assert_mm(doors["seam_centers_mm"][0], 400)
        self._assert_mm(doors["seam_centers_mm"][1], 800)
        divider = report["dividers"][0]
        self._assert_mm(divider["anchor_mm"], 400)
        self._assert_mm(divider["start_mm"], 391)
        self._assert_mm(divider["end_mm"], 409)
        self.assertEqual(
            [cavity["clear_width_mm"] for cavity in report["cavities"]],
            [373, 773],
        )

    def test_thicker_divider_keeps_the_anchor_and_both_clearances_move(self) -> None:
        report = evaluate_interior(
            _front(
                width_mm=1200,
                door_count=3,
                pairs=[[1, 2]],
                dividers=[
                    {
                        "id": "divider_1",
                        "seam_index": 0,
                        "thickness_mm": 25,
                    }
                ],
            )
        )

        divider = report["dividers"][0]
        self._assert_mm(divider["anchor_mm"], 400)
        self._assert_mm(divider["start_mm"], 387.5)
        self._assert_mm(divider["end_mm"], 412.5)
        self.assertEqual(
            [cavity["clear_width_mm"] for cavity in report["cavities"]],
            [369.5, 769.5],
        )

    def test_face_anchor_is_that_face(self) -> None:
        left = evaluate_interior(
            _front(
                width_mm=1200,
                door_count=3,
                pairs=[[1, 2]],
                dividers=[
                    {
                        "id": "divider_1",
                        "seam_index": 0,
                        "seam_align": "left_face",
                        "thickness_mm": 18,
                    }
                ],
            )
        )
        right = evaluate_interior(
            _front(
                width_mm=1200,
                door_count=3,
                pairs=[[1, 2]],
                dividers=[
                    {
                        "id": "divider_1",
                        "seam_index": 0,
                        "seam_align": "right_face",
                        "thickness_mm": 18,
                    }
                ],
            )
        )

        left_divider = left["dividers"][0]
        self._assert_mm(left_divider["start_mm"], 400)
        self._assert_mm(left_divider["end_mm"], 418)
        right_divider = right["dividers"][0]
        self._assert_mm(right_divider["start_mm"], 382)
        self._assert_mm(right_divider["end_mm"], 400)

    def test_integer_two_door_width_matches_the_shared_margin_formula(self) -> None:
        report = evaluate_interior(_front(width_mm=1200, door_count=2))

        doors = report["doors"]
        self.assertEqual(doors["door_widths_mm"], [597, 597])
        self._assert_mm(doors["door_starts_mm"][0], 1.5)
        self._assert_mm(doors["door_starts_mm"][1], 601.5)
        self.assertEqual(doors["gaps_mm"], [3])

    def test_off_grid_width_keeps_whole_doors_and_grows_the_right_margin(self) -> None:
        report = evaluate_interior(_front(width_mm=1800.5, door_count=2))

        doors = report["doors"]
        self.assertEqual(doors["door_widths_mm"], [897, 897])
        self.assertEqual(doors["gaps_mm"], [3])
        self._assert_mm(doors["right_margin_mm"], 2.0)

    def test_one_door_puts_the_fraction_on_the_right_margin(self) -> None:
        report = evaluate_interior(_front(width_mm=800.25, door_count=1))

        doors = report["doors"]
        self.assertEqual(doors["door_widths_mm"], [797])
        self._assert_mm(doors["left_margin_mm"], 1.5)
        self._assert_mm(doors["right_margin_mm"], 1.75)
        self.assertEqual(doors["gaps_mm"], [])

    def test_divider_break_follows_thickness_and_segments_sum_to_the_span(self) -> None:
        span = {"id": "top", "start_mm": 18, "end_mm": 1182}
        thin = evaluate_interior(
            _front(
                width_mm=1200,
                door_count=3,
                pairs=[[1, 2]],
                dividers=[
                    {
                        "id": "divider_1",
                        "seam_index": 0,
                        "thickness_mm": 18,
                    }
                ],
                panels=[span],
                breaks=[{"panel_id": "top", "align_divider": "divider_1"}],
                min_segment_mm=80,
                min_segment_grade="confirmed",
            )
        )
        thick = evaluate_interior(
            _front(
                width_mm=1200,
                door_count=3,
                pairs=[[1, 2]],
                dividers=[
                    {
                        "id": "divider_1",
                        "seam_index": 0,
                        "thickness_mm": 25,
                    }
                ],
                panels=[span],
                breaks=[{"panel_id": "top", "align_divider": "divider_1"}],
                min_segment_mm=80,
                min_segment_grade="confirmed",
            )
        )

        self.assertFalse(thin["blocked"])
        self.assertEqual(thin["panels"][0]["segments_mm"], [373, 773])
        self.assertEqual(thin["panels"][0]["break_widths_mm"], [18])
        self.assertEqual(thick["panels"][0]["segments_mm"], [369.5, 769.5])
        self.assertEqual(thick["panels"][0]["break_widths_mm"], [25])
        for report in (thin, thick):
            panel = report["panels"][0]
            self._assert_mm(
                sum(panel["segments_mm"]) + sum(panel["break_widths_mm"]),
                1164,
            )

    def test_omitted_break_leaves_one_segment(self) -> None:
        report = evaluate_interior(
            _front(
                panels=[{"id": "kick", "start_mm": 18, "end_mm": 1182}],
                min_segment_mm=80,
                min_segment_grade="confirmed",
            )
        )

        self.assertEqual(report["panels"][0]["segments_mm"], [1164])
        self.assertEqual(report["panels"][0]["break_widths_mm"], [])
        self.assertFalse(report["blocked"])

    def test_overlapping_breaks_block_and_keep_the_numbers(self) -> None:
        report = evaluate_interior(
            _front(
                panels=[{"id": "top", "start_mm": 0, "end_mm": 1200}],
                breaks=[
                    {"panel_id": "top", "at_mm": 400, "width_mm": 18},
                    {"panel_id": "top", "at_mm": 410, "width_mm": 18},
                ],
                min_segment_mm=80,
                min_segment_grade="confirmed",
            )
        )

        self.assertTrue(report["blocked"])
        finding = self._finding(report, "break_overlap")
        self.assertEqual(finding["status"], "blocked")
        self.assertTrue(finding["proceed_loss"])
        self.assertTrue(finding["stop_loss"])

    def test_confirmed_short_segment_blocks_with_both_losses(self) -> None:
        report = evaluate_interior(
            _front(
                panels=[{"id": "top", "start_mm": 0, "end_mm": 1200}],
                breaks=[{"panel_id": "top", "at_mm": 60, "width_mm": 0}],
                min_segment_mm=80,
                min_segment_grade="confirmed",
            )
        )

        self.assertTrue(report["blocked"])
        finding = self._finding(report, "segment_short")
        self.assertEqual(finding["status"], "blocked")
        self.assertIn(60, [round(item) for item in report["panels"][0]["segments_mm"]])
        self.assertTrue(finding["proceed_loss"])
        self.assertTrue(finding["stop_loss"])

    def test_missing_min_segment_is_unjudged_and_not_blocked(self) -> None:
        report = evaluate_interior(
            _front(panels=[{"id": "top", "start_mm": 0, "end_mm": 1200}])
        )

        self.assertFalse(report["blocked"])
        finding = self._finding(report, "segment_unjudged")
        self.assertEqual(finding["status"], "unjudged")
        self.assertTrue(finding["proceed_loss"])
        self.assertTrue(finding["stop_loss"])
        self.assertEqual(report["panels"][0]["segments_mm"], [1200])

    def test_unknown_cavity_blocks_without_hiding_the_clearance(self) -> None:
        report = evaluate_interior(
            _front(
                width_mm=1200,
                door_count=3,
                pairs=[[1, 2]],
                dividers=[
                    {
                        "id": "divider_1",
                        "seam_index": 0,
                        "thickness_mm": 18,
                    }
                ],
                cavity_needs=[{"cavity_index": 0, "grade": "unknown"}],
            )
        )

        self.assertTrue(report["blocked"])
        self.assertEqual(report["cavities"][0]["clear_width_mm"], 373)
        self.assertEqual(report["cavities"][0]["status"], "blocked")
        self.assertEqual(report["cavities"][1]["status"], "ok")
        finding = self._finding(report, "cavity_unknown")
        self.assertTrue(finding["proceed_loss"])
        self.assertTrue(finding["stop_loss"])

    def test_typical_shortfall_is_an_assumption_and_confirmed_blocks(self) -> None:
        common = _front(
            width_mm=1200,
            door_count=3,
            pairs=[[1, 2]],
            dividers=[
                {
                    "id": "divider_1",
                    "seam_index": 0,
                    "thickness_mm": 18,
                }
            ],
        )
        typical = evaluate_interior(
            {
                **common,
                "cavity_needs": [
                    {
                        "cavity_index": 0,
                        "grade": "typical",
                        "min_clear_width_mm": 500,
                    }
                ],
            }
        )
        confirmed = evaluate_interior(
            {
                **common,
                "cavity_needs": [
                    {
                        "cavity_index": 0,
                        "grade": "confirmed",
                        "min_clear_width_mm": 500,
                    }
                ],
            }
        )

        self.assertFalse(typical["blocked"])
        self.assertEqual(typical["cavities"][0]["clear_width_mm"], 373)
        self.assertEqual(self._finding(typical, "cavity_fit")["status"], "assumption")
        self.assertTrue(confirmed["blocked"])
        self.assertEqual(confirmed["cavities"][0]["clear_width_mm"], 373)
        blocked = self._finding(confirmed, "cavity_fit")
        self.assertEqual(blocked["status"], "blocked")
        self.assertTrue(blocked["proceed_loss"])
        self.assertTrue(blocked["stop_loss"])

    def test_two_dividers_on_one_seam_block(self) -> None:
        report = evaluate_interior(
            _front(
                door_count=3,
                pairs=[[1, 2]],
                dividers=[
                    {
                        "id": "divider_1",
                        "seam_index": 0,
                        "thickness_mm": 18,
                    },
                    {
                        "id": "divider_2",
                        "seam_index": 0,
                        "thickness_mm": 18,
                    },
                ],
            )
        )

        self.assertTrue(report["blocked"])
        self.assertEqual(len(report["dividers"]), 2)
        self.assertEqual(self._finding(report, "divider_seam")["status"], "blocked")

    def test_caller_millimeters_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown interior spec fields"):
            evaluate_interior(_front(door_width_mm=400))

    def test_non_adjacent_pair_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "adjacent"):
            evaluate_interior(_front(door_count=4, pairs=[[0, 2]]))

    def _assert_mm(self, actual: float, expected: float) -> None:
        self.assertEqual(round(actual * 1000), round(expected * 1000))

    def _finding(self, report: dict, code: str) -> dict:
        matches = [item for item in report["findings"] if item["code"] == code]
        self.assertEqual(len(matches), 1, report["findings"])
        return matches[0]
