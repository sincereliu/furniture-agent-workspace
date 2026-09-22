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
from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.structure_planning import CabinetStructure
from panel_fixtures import by_role, furniture_spec


class CabinetStageCompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = furniture_spec(
            furniture_category="floor_cabinet",
            width=800,
            height=1000,
            depth=600,
            shelf_count=4,
            n_doors=2,
        )
        self.structure = CabinetStructure.from_spec(self.spec)
        self.placements = plan_panels(self.spec, self.structure)
        self.bom = plan_manufacturing(self.spec, self.placements)

    def test_floor_cabinet_uses_expected_coordinate_convention(self) -> None:
        placements = by_role(self.placements)

        left = placements["left_side_panel"]
        self.assertEqual((left.pos_x, left.pos_y, left.pos_z), (0.0, 0.0, 0.0))

        right = placements["right_side_panel"]
        self.assertEqual(right.pos_x, 800.0 - 18.0)

        self.assertEqual(placements["back_panel"].pos_y, 18.0)
        self.assertEqual(placements["bottom_panel"].pos_z, 50.0)

    def test_floor_cabinet_produces_panels_and_bom(self) -> None:
        self.assertEqual(len(self.bom.panels), len(self.placements))
        self.assertEqual(self.bom.panel_count, len(self.bom.panels))
        self.assertEqual(self.bom.furniture_name, "落地柜")
        self.assertEqual(self.bom.dimensions, "800×1000×600mm")
        self.assertGreater(self.bom.total_area_m2, 0)
        self.assertEqual(self.bom.readiness, "preliminary")

    def test_rejects_non_cabinet_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "executable canonical category"):
            furniture_spec(
                furniture_category="wardrobe",
                width=1200,
                height=2000,
                depth=600,
            )

    @unittest.expectedFailure
    def test_length_width_are_flat_dimensions_not_world_axes(self) -> None:
        """已知缺口（「发现 A」）的自动提醒，条目在 manufacture-plan/backlog.md。

        length_mm/width_mm 目前固定取世界坐标 size_x/size_y，板厚方向落在 X 或 Y
        的板件会把板厚当成开料尺寸。缺口修好时本测试转为 unexpected success、
        套件转红 —— 那是信号：去 backlog.md 把该条目移入「已落地」。
        """
        panels = by_role(self.bom.panels)

        side = panels["left_side_panel"]
        self.assertEqual(side.size_x, 18.0)  # 世界 X 轴是板厚方向
        self.assertEqual(
            (side.length_mm, side.width_mm),
            (side.size_y, side.size_z),  # 期望：取自板件平面
        )

        back = panels["back_panel"]
        self.assertEqual(back.size_y, 9.0)  # 世界 Y 轴是板厚方向
        self.assertEqual(
            (back.length_mm, back.width_mm),
            (back.size_x, back.size_z),
        )


if __name__ == "__main__":
    unittest.main()
