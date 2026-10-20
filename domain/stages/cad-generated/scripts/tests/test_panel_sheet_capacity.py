"""板幅：板件的两个平面尺寸必须进得去车间那档板。

两档料：1220×2440（工艺卡默认）与 1220×2745。哪一档决定"做不做得出来"，
所以它随板件冻结进 spec（`sheet_width_mm` / `sheet_length_mm`），再由
`_validate_sheet_capacity` 逐块判。旋转不改变结果：`min ≤ 宽` 且 `max ≤ 长`。
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

from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.panel_spec import FurnitureSpec, spec_payload
from furniture_panel_planning.structure_planning import CabinetStructure
from furniture_panel_planning.validation_panels import validate_panels
from panel_fixtures import (
    by_role,
    cabinet_envelope,
    furniture_spec,
    panel_parameters,
)

DIVIDERS = [{"seam_index": 1}, {"seam_index": 2}, {"seam_index": 3}]
HINGES = ["left", "right", "right", "left", "right"]


def _codes(spec: FurnitureSpec, panels=None) -> set[str]:
    structure = CabinetStructure.from_spec(spec)
    if panels is None:
        panels = plan_panels(spec, structure)
    return {issue.code for issue in validate_panels(spec, structure, panels).issues}


class SheetStockAdmissionTests(unittest.TestCase):
    def test_the_process_card_defaults_to_1220x2440(self):
        spec = furniture_spec()
        self.assertEqual((spec.sheet_width_mm, spec.sheet_length_mm), (1220.0, 2440.0))

    def test_an_omitted_sheet_is_expanded_at_admission(self):
        params = panel_parameters()
        params.pop("sheet_width_mm")
        params.pop("sheet_length_mm")
        spec = FurnitureSpec.from_envelope(cabinet_envelope(), params)
        self.assertEqual((spec.sheet_width_mm, spec.sheet_length_mm), (1220.0, 2440.0))

    def test_half_a_sheet_is_rejected(self):
        params = panel_parameters()
        params.pop("sheet_length_mm")
        with self.assertRaisesRegex(ValueError, "must be given together"):
            FurnitureSpec.from_envelope(cabinet_envelope(), params)

    def test_only_the_catalog_pairs_are_admitted(self):
        with self.assertRaisesRegex(ValueError, "sheet size must be one of"):
            furniture_spec(sheet_length_mm=3000.0)
        spec = furniture_spec(sheet_width_mm=1220.0, sheet_length_mm=2745.0)
        self.assertEqual(spec.sheet_length_mm, 2745.0)

    def test_an_old_frozen_spec_without_a_sheet_reads_the_process_card(self):
        # 板幅是后加的字段：老冻结文件没写，读回来按工艺卡默认，不改写文件。
        payload = spec_payload(furniture_spec())
        payload.pop("sheet_width_mm")
        payload.pop("sheet_length_mm")
        restored = FurnitureSpec.from_dict(payload)
        self.assertEqual(
            (restored.sheet_width_mm, restored.sheet_length_mm), (1220.0, 2440.0)
        )


class SheetCapacityTests(unittest.TestCase):
    def test_a_short_wall_cabinet_fits_the_default_sheet(self):
        spec = furniture_spec(furniture_category="wall_cabinet", width=900,
                              depth=350, height=700)
        self.assertNotIn("PANEL_EXCEEDS_SHEET", _codes(spec))

    def test_a_2500_wide_cabinet_does_not_fit_the_short_sheet(self):
        spec = furniture_spec(
            width=2500.0, n_doors=5, dividers=DIVIDERS, door_hinges=HINGES,
        )
        structure = CabinetStructure.from_spec(spec)
        panels = plan_panels(spec, structure)
        issues = validate_panels(spec, structure, panels).issues
        overflowing = {
            issue.path for issue in issues if issue.code == "PANEL_EXCEEDS_SHEET"
        }
        # 顶底板 2464 长，2440 的板切不出来（踢脚板同样是通长的）。
        self.assertIn("cabinet_1__top_panel", overflowing)
        self.assertIn("cabinet_1__bottom_panel", overflowing)
        # 背板已经按中立板打断，不再超尺。
        self.assertFalse(
            any("back_panel" in path for path in overflowing), overflowing
        )
        self.assertEqual(
            [panel.size_x for panel in panels if panel.panel_type == "back"],
            [985.0, 494.0, 494.0, 485.0],
        )

    def test_the_same_cabinet_fits_the_long_sheet(self):
        spec = furniture_spec(
            width=2500.0, n_doors=5, dividers=DIVIDERS, door_hinges=HINGES,
            sheet_length_mm=2745.0,
        )
        self.assertNotIn("PANEL_EXCEEDS_SHEET", _codes(spec))

    def test_one_wide_cavity_still_overflows_the_back(self):
        # 2000 宽、2000 高、不加立板：背面只有一块 1988×1926，两边都超过板宽 1220。
        spec = furniture_spec(width=2000.0, height=2000.0, n_doors=2,
                              sheet_length_mm=2745.0)
        structure = CabinetStructure.from_spec(spec)
        panels = plan_panels(spec, structure)
        issues = validate_panels(spec, structure, panels).issues
        back_issues = [
            issue for issue in issues
            if issue.code == "PANEL_EXCEEDS_SHEET" and issue.path.endswith("back_panel")
        ]
        self.assertEqual(len(back_issues), 1)
        self.assertIn("加中立板", back_issues[0].message)

    def test_adding_the_divider_fixes_that_back(self):
        spec = furniture_spec(width=2000.0, height=2000.0, n_doors=2,
                              dividers=[{"seam_index": 0}],
                              door_hinges=["left", "right"],
                              sheet_length_mm=2745.0)
        self.assertNotIn("PANEL_EXCEEDS_SHEET", _codes(spec))

    def test_a_cover_back_is_not_split_so_it_keeps_overflowing(self):
        spec = furniture_spec(
            width=1500.0, height=2000.0, n_doors=2, back_mount="cover",
        )
        structure = CabinetStructure.from_spec(spec)
        panels = plan_panels(spec, structure)
        backs = [panel for panel in panels if panel.panel_type == "back"]
        self.assertEqual(len(backs), 1)
        issues = validate_panels(spec, structure, panels).issues
        back_issues = [
            issue for issue in issues
            if issue.code == "PANEL_EXCEEDS_SHEET" and issue.path.endswith("back_panel")
        ]
        self.assertEqual(len(back_issues), 1)
        self.assertIn("外盖背板", back_issues[0].message)


if __name__ == "__main__":
    unittest.main()
