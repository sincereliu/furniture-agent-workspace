"""抽屉滑轨系统：抽芯档、后缝下限、轨腔与"格高 → 上下间隙"。

三件事在这里钉住：

1. **盒高由格高给**：盒高 = 格高 − 下间隙 − 上间隙，按 10 取整，余量进上间隙；
2. **盒深取抽芯档**：盒深必须落在档上，后缝是结果（可装深度 − 盒深）；
3. **口径按滑轨系统查表**：三节轨与托底轨的间隙、档位、轨腔高度各不相同；
   格高落在经验区间之外只警告，不拦确认。

口径见 references/drawer-runner-rules.md。
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
    drawer_cell_report,
    drawer_panel_boxes,
)
from furniture_panel_planning.drawer_variants import (
    cell_gaps,
    cell_warnings,
    min_rear_clearance,
    pick_box_depth,
)
from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.panel_spec import FurnitureSpec, spec_payload
from furniture_panel_planning.structure_planning import CabinetStructure
from furniture_panel_planning.validation import validate_panels
from panel_fixtures import cabinet_envelope, furniture_spec, panel_parameters


def drawer_cabinet(
    drawer_count: int = 3, runner: str = "side_mount", **overrides
) -> FurnitureSpec:
    """抽屉区：默认占满内部净高，不要门也不要层板。

    后缝默认给 20（三节轨要求 > 0、托底轨 > 10）：这是提案值，不是代码默认。
    """
    values = {"drawer_back_clearance": 20.0, **overrides}
    return furniture_spec(
        furniture_category="floor_cabinet",
        width=800,
        depth=600,
        height=1000,
        n_doors=0,
        shelf_count=0,
        drawer_count=drawer_count,
        drawer_runner=runner,
        **values,
    )


def boxes_by_type(spec: FurnitureSpec) -> dict[str, list]:
    structure = CabinetStructure.from_spec(spec)
    grouped: dict[str, list] = {}
    for box in drawer_panel_boxes(spec, structure):
        grouped.setdefault(box.panel_id.split("_z")[0], []).append(box)
    return grouped


class DrawerRunnerAdmissionTests(unittest.TestCase):
    """滑轨系统只有两个值，缺省不落盘。"""

    def test_default_runner_is_side_mount_and_stays_out_of_the_payload(self) -> None:
        spec = drawer_cabinet()
        self.assertEqual(spec.drawer_runner, "side_mount")
        self.assertNotIn("drawer_runner", spec_payload(spec))

    def test_old_frozen_spec_reads_back_as_side_mount(self) -> None:
        payload = spec_payload(drawer_cabinet())
        restored = FurnitureSpec.from_dict(payload)
        self.assertEqual(restored.drawer_runner, "side_mount")

    def test_explicit_runner_is_serialized(self) -> None:
        spec = drawer_cabinet(runner="undermount")
        self.assertEqual(spec_payload(spec)["drawer_runner"], "undermount")

    def test_synonym_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "drawer_runner must be one of"):
            drawer_cabinet(runner="三节轨")

    def test_runner_without_drawers_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "require drawer_count > 0"):
            furniture_spec(drawer_runner="undermount")

    def test_front_board_choice_is_serialized_only_when_off(self) -> None:
        self.assertNotIn("drawer_front_board", spec_payload(drawer_cabinet()))
        self.assertFalse(
            spec_payload(drawer_cabinet(drawer_front_board=False))["drawer_front_board"]
        )

    def test_old_frozen_spec_reads_back_with_a_front_board(self) -> None:
        payload = spec_payload(drawer_cabinet())
        payload.pop("drawer_front_board", None)
        self.assertTrue(FurnitureSpec.from_dict(payload).drawer_front_board)

    def test_front_board_must_be_boolean(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be true or false"):
            drawer_cabinet(drawer_front_board="false")


class DrawerSideClearanceTests(unittest.TestCase):
    """每侧间隙是滑轨系统的车间口径：省略按系统展开，显式值保持。"""

    def _proposal(self, **overrides):
        params = panel_parameters(
            n_doors=0, drawer_count=2, drawer_back_clearance=20.0
        )
        params.pop("drawer_side_clearance", None)
        params.update(overrides)
        return params

    def test_omitted_clearance_follows_the_runner(self) -> None:
        flat = FurnitureSpec.from_envelope(cabinet_envelope(), self._proposal())
        self.assertEqual(flat.drawer_side_clearance, 13.0)
        under = FurnitureSpec.from_envelope(
            cabinet_envelope(), self._proposal(drawer_runner="undermount")
        )
        self.assertEqual(under.drawer_side_clearance, 6.5)

    def test_explicit_clearance_is_kept(self) -> None:
        spec = FurnitureSpec.from_envelope(
            cabinet_envelope(), {**self._proposal(), "drawer_side_clearance": 8.0}
        )
        self.assertEqual(spec.drawer_side_clearance, 8.0)


class DrawerRearClearanceTests(unittest.TestCase):
    """后缝下限按滑轨系统给：三节轨 > 0、托底轨 > 10。"""

    def test_side_mount_requires_a_positive_rear_clearance(self) -> None:
        with self.assertRaisesRegex(ValueError, "必须大于 0mm"):
            drawer_cabinet(drawer_back_clearance=0.0)

    def test_undermount_requires_more_than_ten(self) -> None:
        with self.assertRaisesRegex(ValueError, "必须大于 10mm"):
            drawer_cabinet(runner="undermount", drawer_back_clearance=10.0)

    def test_limits_are_exposed_for_both_runners(self) -> None:
        self.assertEqual(min_rear_clearance("side_mount"), 0.0)
        self.assertEqual(min_rear_clearance("undermount"), 10.0)


class DrawerCellGapTests(unittest.TestCase):
    """格高 → (下间隙, 上间隙)：区间左开右闭，超出上限按 20/20。"""

    def test_side_mount_bands(self) -> None:
        self.assertEqual(cell_gaps("side_mount", 70.0), (10.0, 10.0))
        self.assertEqual(cell_gaps("side_mount", 130.0), (10.0, 10.0))
        self.assertEqual(cell_gaps("side_mount", 130.5), (10.0, 20.0))
        self.assertEqual(cell_gaps("side_mount", 220.0), (10.0, 20.0))
        self.assertEqual(cell_gaps("side_mount", 220.5), (20.0, 20.0))
        self.assertEqual(cell_gaps("side_mount", 260.0), (20.0, 20.0))
        # 超过上限仍是 20/20，但会报警告
        self.assertEqual(cell_gaps("side_mount", 300.0), (20.0, 20.0))

    def test_undermount_bands(self) -> None:
        self.assertEqual(cell_gaps("undermount", 200.0), (20.0, 10.0))
        self.assertEqual(cell_gaps("undermount", 220.0), (20.0, 10.0))
        self.assertEqual(cell_gaps("undermount", 220.5), (20.0, 20.0))

    def test_cell_warnings_are_not_blocking(self) -> None:
        self.assertEqual(
            [w["code"] for w in cell_warnings("side_mount", 65.0)],
            ["DRAWER_CELL_TOO_LOW"],
        )
        self.assertEqual(
            [w["code"] for w in cell_warnings("side_mount", 300.0)],
            ["DRAWER_CELL_TOO_HIGH"],
        )
        self.assertEqual(
            cell_warnings("undermount", 75.0)[0]["code"], "DRAWER_CELL_TOO_LOW"
        )
        # 托底轨没有格高上限
        self.assertEqual(cell_warnings("undermount", 900.0), [])


class DrawerClearHeightTests(unittest.TestCase):
    """抽屉区可以只占一段净高：给净高 + 贴底/贴顶。"""

    def test_omitted_clear_height_still_fills_the_cavity(self) -> None:
        spec = drawer_cabinet(3)
        structure = CabinetStructure.from_spec(spec)
        cell = drawer_cell_report(spec, structure)
        self.assertAlmostEqual(cell["zone_height"], structure.internal_height, places=6)
        self.assertAlmostEqual(cell["zone_start"], structure.internal_z_start, places=6)

    def test_clear_height_at_the_bottom(self) -> None:
        spec = drawer_cabinet(1, drawer_clear_height_mm=200.0)
        structure = CabinetStructure.from_spec(spec)
        cell = drawer_cell_report(spec, structure)
        self.assertEqual(cell["zone_height"], 200.0)
        self.assertEqual(cell["cell_height"], 200.0)
        self.assertEqual(cell["box_height"], 170.0)  # 200 − 10 − 20
        self.assertAlmostEqual(cell["zone_start"], structure.internal_z_start, places=6)
        boxes = boxes_by_type(spec)
        side = boxes["drawer_side_L"][0]
        self.assertAlmostEqual(side.pos_z, structure.internal_z_start + 10.0, places=6)

    def test_clear_height_at_the_top(self) -> None:
        spec = drawer_cabinet(1, drawer_clear_height_mm=200.0, drawer_anchor="top")
        structure = CabinetStructure.from_spec(spec)
        cell = drawer_cell_report(spec, structure)
        self.assertAlmostEqual(
            cell["zone_start"], structure.internal_z_end - 200.0, places=6
        )
        boxes = boxes_by_type(spec)
        side = boxes["drawer_side_L"][0]
        self.assertAlmostEqual(
            side.pos_z, structure.internal_z_end - 200.0 + 10.0, places=6
        )
        face = boxes["drawer_front"][0]
        self.assertAlmostEqual(
            face.pos_z, structure.internal_z_end - 200.0, places=6
        )

    def test_clear_height_splits_into_equal_cells(self) -> None:
        spec = drawer_cabinet(2, drawer_clear_height_mm=400.0)
        structure = CabinetStructure.from_spec(spec)
        cell = drawer_cell_report(spec, structure)
        self.assertEqual(cell["cell_height"], 200.0)
        self.assertEqual(cell["box_height"], 170.0)

    def test_clear_height_beyond_the_cavity_is_rejected(self) -> None:
        spec = drawer_cabinet(1, drawer_clear_height_mm=2000.0)
        structure = CabinetStructure.from_spec(spec)
        with self.assertRaisesRegex(ValueError, "exceeds the internal height"):
            plan_panels(spec, structure)

    def test_anchor_without_clear_height_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "drawer_anchor requires"):
            drawer_cabinet(1, drawer_anchor="top")

    def test_clear_height_without_drawers_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "require drawer_count > 0"):
            furniture_spec(drawer_clear_height_mm=200.0)

    def test_clear_height_must_be_positive(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be a positive number"):
            drawer_cabinet(1, drawer_clear_height_mm=0.0)

    def test_unknown_anchor_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "drawer_anchor must be one of"):
            drawer_cabinet(1, drawer_clear_height_mm=200.0, drawer_anchor="middle")


class DrawerBoxChainTests(unittest.TestCase):
    """盒高、盒深、轨腔都从格高与档位来。"""

    def test_box_height_is_ten_millimetre_step(self) -> None:
        spec = drawer_cabinet(3)
        cell = drawer_cell_report(spec, CabinetStructure.from_spec(spec))
        self.assertAlmostEqual(cell["cell_height"], 914.0 / 3, places=6)
        self.assertEqual(cell["box_height"] % 10, 0)
        self.assertEqual(cell["box_height"], 260.0)
        # 取整余量进上间隙：上间隙 = 规范值 + 余量
        self.assertAlmostEqual(
            cell["upper_gap"],
            cell["cell_height"] - cell["lower_gap"] - cell["box_height"],
            places=6,
        )

    def test_box_depth_comes_from_the_ladder(self) -> None:
        spec = drawer_cabinet(3)
        cell = drawer_cell_report(spec, CabinetStructure.from_spec(spec))
        self.assertEqual(cell["box_depth"], 500.0)  # 三节轨档：200/250/.../500
        # 后缝是结果：可装深度 535 − 盒深 500 = 35 > 要求 20
        self.assertAlmostEqual(cell["rear_clearance"], 35.0, places=6)

        under_spec = drawer_cabinet(3, runner="undermount")
        under = drawer_cell_report(under_spec, CabinetStructure.from_spec(under_spec))
        self.assertEqual(under["box_depth"], 490.0)  # 托底轨档：240/290/.../490
        self.assertAlmostEqual(under["rear_clearance"], 45.0, places=6)

    def test_pick_box_depth_requires_the_rear_clearance(self) -> None:
        with self.assertRaisesRegex(ValueError, "放不下任何一档抽芯"):
            pick_box_depth("side_mount", 190.0, 20.0)

    def test_undermount_raises_the_bottom_panel(self) -> None:
        spec = drawer_cabinet(2, runner="undermount")
        grouped = boxes_by_type(spec)
        side = grouped["drawer_side_L"][0]
        bottom = grouped["drawer_bottom"][0]
        self.assertAlmostEqual(bottom.pos_z, side.pos_z + 11.0, places=6)
        # 三节轨不抬：底板与侧板同底
        flat = boxes_by_type(drawer_cabinet(2))
        self.assertAlmostEqual(
            flat["drawer_bottom"][0].pos_z, flat["drawer_side_L"][0].pos_z, places=6
        )

    def test_box_height_is_shorter_than_the_cell(self) -> None:
        """盒体不再占满空间：上下都留了间隙。"""
        spec = drawer_cabinet(3)
        structure = CabinetStructure.from_spec(spec)
        cell = drawer_cell_report(spec, structure)
        side = boxes_by_type(spec)["drawer_side_L"][0]
        self.assertAlmostEqual(
            side.pos_z, structure.internal_z_start + cell["lower_gap"], places=6
        )
        self.assertAlmostEqual(side.size_z, cell["box_height"], places=6)
        self.assertLess(side.size_z, cell["cell_height"])

    def test_three_drawers_in_a_tall_cabinet_warns(self) -> None:
        spec = drawer_cabinet(3)
        structure = CabinetStructure.from_spec(spec)
        report = validate_panels(spec, structure, plan_panels(spec, structure))
        self.assertIn("DRAWER_CELL_TOO_HIGH", {issue.code for issue in report.issues})
        self.assertTrue(report.passed, "格高超出经验区间只警告，不拦确认")

    def test_four_drawers_stay_inside_the_band(self) -> None:
        spec = drawer_cabinet(4)
        structure = CabinetStructure.from_spec(spec)
        report = validate_panels(spec, structure, plan_panels(spec, structure))
        self.assertNotIn("DRAWER_CELL_TOO_HIGH", {issue.code for issue in report.issues})
        self.assertEqual(
            drawer_cell_report(spec, structure)["box_height"] % 10, 0
        )


if __name__ == "__main__":
    unittest.main()
