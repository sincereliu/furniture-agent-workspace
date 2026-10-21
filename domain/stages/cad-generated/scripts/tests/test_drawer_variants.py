"""抽屉变体：组合准入、缺省不落盘、角色表与件数。

这一版（P1）只修通道：变体字段进来、组合合法性由表判、已物化的组合只有
「三节轨 + 盒体前板兼前脸 + 三条净空为 0」。所以这里钉三件事：

1. **缺省 = 今天**：不写变体字段时 spec 序列化里没有这些键，产出逐字节不变；
2. **没物化的组合不许进**：字段收了、几何没做的产物比报错更糟；
3. **件数从角色表来**：校验不再写死「每抽 5 块」，加变体只加一行数据。
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

from furniture_panel_planning.drawer_variants import (
    ALLOWED_VARIANTS,
    ROLES_BY_VARIANT,
    drawer_part_count,
    drawer_part_roles,
    material_role_of_role,
    panel_type_of_role,
)
from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.panel_spec import FurnitureSpec, spec_payload
from furniture_panel_planning.structure_planning import CabinetStructure
from furniture_panel_planning.validation import validate_panels
from panel_fixtures import furniture_spec

VARIANT_KEYS = (
    "drawer_runner",
    "drawer_face",
    "drawer_top_clearance",
    "drawer_bottom_clearance",
    "drawer_bottom_raise",
)


def drawer_cabinet(drawer_count: int = 3) -> FurnitureSpec:
    """整高抽屉区：抽屉占满内部净高，不要门也不要层板。"""
    return furniture_spec(
        furniture_category="floor_cabinet",
        width=800,
        depth=600,
        height=1000,
        n_doors=0,
        shelf_count=0,
        drawer_count=drawer_count,
    )


class DrawerVariantDefaultTests(unittest.TestCase):
    """缺省就是今天那套：三节轨 + 盒体前板兼前脸，而且不落盘。"""

    def test_defaults_are_todays_combination(self) -> None:
        spec = drawer_cabinet()
        self.assertEqual(spec.drawer_runner, "side_mount")
        self.assertEqual(spec.drawer_face, "box_face")
        self.assertEqual(spec.drawer_top_clearance, 0.0)
        self.assertEqual(spec.drawer_bottom_clearance, 0.0)
        self.assertEqual(spec.drawer_bottom_raise, 0.0)

    def test_default_variant_stays_out_of_the_payload(self) -> None:
        payload = spec_payload(drawer_cabinet())
        for key in VARIANT_KEYS:
            self.assertNotIn(key, payload)

    def test_old_frozen_spec_reads_back_with_defaults(self) -> None:
        payload = spec_payload(drawer_cabinet())
        restored = FurnitureSpec.from_dict(payload)
        self.assertEqual(restored.drawer_runner, "side_mount")
        self.assertEqual(restored.drawer_face, "box_face")
        # 读回来再写一遍仍然不落盘：序列化是幂等的。
        self.assertEqual(spec_payload(restored), payload)

    def test_unknown_variant_field_is_rejected(self) -> None:
        """还没物化的字段不悄悄收下——收下就等于假装做了。"""
        payload = spec_payload(drawer_cabinet())
        payload["drawer_nominal_width_mm"] = 300.0
        with self.assertRaisesRegex(ValueError, "does not support"):
            FurnitureSpec.from_dict(payload)


class DrawerVariantAdmissionTests(unittest.TestCase):
    """组合合法性（物理上不成立）与物化状态（还没做）分开报。"""

    def test_unknown_runner_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "drawer_runner must be one of"):
            furniture_spec(
                n_doors=0, shelf_count=0, drawer_count=3,
                drawer_runner="三节轨",
            )

    def test_unknown_face_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "drawer_face must be one of"):
            furniture_spec(
                n_doors=0, shelf_count=0, drawer_count=3,
                drawer_face="panel",
            )

    def test_metal_box_has_no_wooden_front_board(self) -> None:
        """骑马抽的左右侧板是五金，不存在「盒体前板兼前脸」这种组合。"""
        with self.assertRaisesRegex(ValueError, "no wooden front board"):
            furniture_spec(
                n_doors=0, shelf_count=0, drawer_count=3,
                drawer_runner="metal_box", drawer_face="box_face",
            )

    def test_unmaterialized_runner_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "not materialized yet"):
            furniture_spec(
                n_doors=0, shelf_count=0, drawer_count=3,
                drawer_runner="undermount",
            )

    def test_unmaterialized_face_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "not materialized yet"):
            furniture_spec(
                n_doors=0, shelf_count=0, drawer_count=3,
                drawer_face="applied",
            )

    def test_unmaterialized_clearances_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "clearances and bottom_raise"):
            furniture_spec(
                n_doors=0, shelf_count=0, drawer_count=3,
                drawer_top_clearance=3.0,
            )
        with self.assertRaisesRegex(ValueError, "clearances and bottom_raise"):
            furniture_spec(
                n_doors=0, shelf_count=0, drawer_count=3,
                drawer_bottom_raise=18.0,
            )

    def test_variant_fields_need_drawers(self) -> None:
        with self.assertRaisesRegex(ValueError, "require drawer_count > 0"):
            furniture_spec(drawer_runner="undermount")

    def test_negative_clearance_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            furniture_spec(
                n_doors=0, shelf_count=0, drawer_count=3,
                drawer_top_clearance=-1.0,
            )


class DrawerRoleTableTests(unittest.TestCase):
    """角色表是件数与板件类型的唯一来源。"""

    def test_part_counts_cover_every_allowed_variant(self) -> None:
        expected = {
            ("side_mount", "box_face"): 5,
            ("side_mount", "applied"): 6,
            ("undermount", "box_face"): 5,
            ("undermount", "applied"): 6,
            ("metal_box", "applied"): 3,
        }
        self.assertEqual(set(ROLES_BY_VARIANT), set(expected))
        for variant, count in expected.items():
            with self.subTest(variant=variant):
                self.assertEqual(drawer_part_count(*variant), count)

    def test_metal_box_drops_the_wooden_box_sides(self) -> None:
        roles = drawer_part_roles("metal_box", "applied")
        self.assertEqual(roles, ("face", "box_back", "box_bottom"))
        self.assertNotIn("box_side_l", roles)

    def test_applied_face_adds_one_part(self) -> None:
        without = drawer_part_roles("side_mount", "box_face")
        with_face = drawer_part_roles("side_mount", "applied")
        self.assertEqual(set(with_face) - set(without), {"face"})
        self.assertEqual(len(with_face), len(without) + 1)

    def test_roles_map_to_the_frozen_panel_type_vocabulary(self) -> None:
        known = {"drawer_face", "drawer_front", "drawer_side", "drawer_back", "drawer_bottom"}
        for roles in ALLOWED_VARIANTS:
            for role in drawer_part_roles(*roles):
                with self.subTest(role=role):
                    self.assertIn(panel_type_of_role(role), known)
        # 「盒体前板兼前脸」沿用旧词表 drawer_front：老冻结文件钉着它。
        self.assertEqual(panel_type_of_role("box_front"), "drawer_front")

    def test_only_the_visible_face_uses_door_material(self) -> None:
        self.assertEqual(material_role_of_role("face"), "door")
        for role in ("box_front", "box_side_l", "box_back", "box_bottom"):
            self.assertEqual(material_role_of_role(role), "carcass")

    def test_unknown_role_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown drawer role"):
            panel_type_of_role("drawer_lid")


class DrawerRoleTableValidationTests(unittest.TestCase):
    """校验跟着角色表走，而不是跟着常量 5 走。"""

    def test_generated_panels_match_the_role_table(self) -> None:
        spec = drawer_cabinet(3)
        placements = plan_panels(spec, CabinetStructure.from_spec(spec))
        drawer_panels = [p for p in placements if "drawer" in p.panel_type]
        self.assertEqual(len(drawer_panels), 3 * drawer_part_count("side_mount", "box_face"))
        self.assertEqual(
            {p.panel_type for p in drawer_panels},
            {"drawer_front", "drawer_side", "drawer_back", "drawer_bottom"},
        )

    def test_validation_passes_for_the_materialized_variant(self) -> None:
        spec = drawer_cabinet(3)
        structure = CabinetStructure.from_spec(spec)
        report = validate_panels(spec, structure, plan_panels(spec, structure))
        self.assertTrue(report.passed, [issue.code for issue in report.issues])

    def test_missing_panel_reports_the_table_driven_count(self) -> None:
        spec = drawer_cabinet(3)
        structure = CabinetStructure.from_spec(spec)
        placements = plan_panels(spec, structure)
        report = validate_panels(spec, structure, placements[:-1])
        codes = {issue.code for issue in report.issues}
        self.assertIn("DRAWER_PANEL_COUNT_MISMATCH", codes)


if __name__ == "__main__":
    unittest.main()
