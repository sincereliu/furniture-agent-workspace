"""多扇门：一排放 n 扇，宽度与起点只从评估器的回报里取。

原来 `panel_spec` 拒 `n_doors > 2`，`_door_panels` 也只认 1/2 扇。现在整排门按
从左到右出件：一扇沿用 `single_door`、两扇沿用 `left_door`/`right_door`
（冻结文件与老测试都钉着这两个名字），三扇起用 `door_1…door_n`。
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

from furniture_panel_planning.construction_geometry import (
    door_interior_report,
    door_panel_boxes,
    interior_cavity_bounds,
)
from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.panel_spec import FurnitureSpec
from furniture_panel_planning.structure_planning import CabinetStructure
from furniture_panel_planning.validation_panels import validate_panels
from panel_fixtures import by_role, furniture_spec


def _door_only(**overrides) -> FurnitureSpec:
    values = {"shelves": [], "top_gap_mm": 0.0}
    values.update(overrides)
    return furniture_spec(**values)


def _doors(spec: FurnitureSpec) -> list:
    panels = plan_panels(spec, CabinetStructure.from_spec(spec))
    return sorted(
        (item for item in panels if item.panel_type == "door"),
        key=lambda item: item.pos_x,
    )


class MultiDoorTests(unittest.TestCase):
    def test_five_door_run_is_equal_slots_from_the_evaluator(self):
        spec = _door_only(width=2450.0, n_doors=5)
        boxes = door_panel_boxes(spec, CabinetStructure.from_spec(spec))
        self.assertEqual([box.panel_id for box in boxes],
                         ["door_1", "door_2", "door_3", "door_4", "door_5"])
        # 2450 / 5 = 490 槽，门 486？不——边距 1.5 两侧各让 1.5 → 490 − 3 = 487。
        self.assertEqual([box.size_x for box in boxes], [487.0] * 5)
        self.assertEqual(
            [box.pos_x for box in boxes],
            [1.5, 491.5, 981.5, 1471.5, 1961.5],
        )

    def test_door_geometry_is_exactly_the_evaluator_report(self):
        """1211/4 这类除不尽的宽度：板件阶段不能自己再算一套。"""
        for width, count in ((1211.0, 4), (2400.0, 7), (1511.0, 6)):
            with self.subTest(width=width, count=count):
                spec = _door_only(width=width, n_doors=count)
                report = door_interior_report(spec)["doors"]
                boxes = door_panel_boxes(spec, CabinetStructure.from_spec(spec))
                self.assertEqual(
                    [box.size_x for box in boxes],
                    [float(value) for value in report["door_widths_mm"]],
                )
                self.assertEqual(
                    [box.pos_x for box in boxes],
                    [float(value) for value in report["door_starts_mm"]],
                )

    def test_single_and_double_doors_keep_their_old_role_names(self):
        one = _door_only(n_doors=1)
        self.assertEqual([item.role for item in _doors(one)], ["single_door"])
        two = _door_only(n_doors=2)
        self.assertEqual(
            [item.role for item in _doors(two)], ["left_door", "right_door"]
        )
        self.assertEqual(
            [item.name for item in _doors(two)], ["左门板", "右门板"]
        )

    def test_five_doors_at_2500_take_three_dividers_on_seams(self):
        spec = _door_only(
            width=2500.0,
            n_doors=5,
            dividers=[
                {"seam_index": 1},
                {"seam_index": 2},
                {"seam_index": 3},
            ],
        )
        structure = CabinetStructure.from_spec(spec)
        panels = by_role(plan_panels(spec, structure))
        dividers = [panels[key] for key in ("divider_1", "divider_2", "divider_3")]
        # 缝 500 / 1000 / 1500 / 2000，取后三条。
        self.assertEqual(
            [box.pos_x for box in door_panel_boxes(spec, structure)], [1.5, 501.5, 1001.5, 1501.5, 2001.5]
        )
        self.assertEqual([item.pos_x for item in dividers], [991.0, 1491.0, 1991.0])
        self.assertEqual(
            [end - start for start, end in interior_cavity_bounds(spec, structure)],
            [973.0, 482.0, 482.0, 473.0],
        )

    def test_doors_are_no_longer_capped_at_two(self):
        spec = _door_only(width=2450.0, n_doors=5)
        self.assertEqual(len(_doors(spec)), 5)


class MultiDoorValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        # 五扇门要有物理含义：三块立板切成 1 对开 + 3 单开，单开的铰链侧逐扇给。
        self.spec = _door_only(
            width=2500.0,
            n_doors=5,
            dividers=[
                {"seam_index": 1},
                {"seam_index": 2},
                {"seam_index": 3},
            ],
            door_hinges=["left", "right", "right", "left", "right"],
        )
        self.structure = CabinetStructure.from_spec(self.spec)
        self.panels = plan_panels(self.spec, self.structure)

    def test_complete_multi_door_plan_has_no_issues(self):
        report = validate_panels(self.spec, self.structure, self.panels)
        self.assertEqual(report.issues, [])

    def test_missing_door_is_reported(self):
        without = [item for item in self.panels if item.role != "door_3"]
        report = validate_panels(self.spec, self.structure, without)
        codes = {issue.code for issue in report.issues}
        self.assertIn("DOOR_COUNT_MISMATCH", codes)

    def test_shifted_door_geometry_is_reported(self):
        moved = list(self.panels)
        for item in moved:
            if item.role == "door_3":
                item.pos_x += 5.0
        report = validate_panels(self.spec, self.structure, moved)
        codes = {issue.code for issue in report.issues}
        self.assertIn("DOOR_GEOMETRY_MISMATCH", codes)


if __name__ == "__main__":
    unittest.main()
