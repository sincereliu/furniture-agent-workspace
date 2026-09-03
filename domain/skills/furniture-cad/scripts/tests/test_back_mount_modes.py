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

from furniture_panel_planning.panel_spec import FurnitureSpec
from panel_fixtures import cabinet_data, furniture_spec
from furniture_layout.layout_pipeline import plan_layout
from furniture_layout.validation import validate_layout
from furniture_manufacturing.manufacturing_bom import (
    emit_drilled_holes,
    plan_manufacturing,
)
from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.structure_planning import CabinetStructure
from furniture_panel_planning.validation import validate_panels, validate_structure
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_state import WorkflowStage


class BackMountModeTests(unittest.TestCase):
    def _spec(self, back_mount: str) -> FurnitureSpec:
        return furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            back_mount=back_mount,
            back_thickness=18 if back_mount == "insert" else 9,
            shelf_count=1,
            n_doors=2,
        )

    def test_all_modes_preserve_the_finished_depth_envelope(self) -> None:
        expected_layouts = {
            "groove": (0.0, 580.0, 27.0),
            "insert": (0.0, 580.0, 36.0),
            "cover": (9.0, 580.0, 9.0),
        }

        for back_mount, expected in expected_layouts.items():
            with self.subTest(back_mount=back_mount):
                spec = self._spec(back_mount)
                layout = plan_layout(spec)
                structure = CabinetStructure.from_spec(spec)
                placements = plan_panels(spec, layout)
                panels = {panel.id: panel for panel in placements}
                carcass_y_start, carcass_y_end, internal_y_start = expected

                self.assertEqual(structure.carcass_y_start, carcass_y_start)
                self.assertEqual(structure.carcass_y_end, carcass_y_end)
                self.assertEqual(
                    structure.side_depth,
                    carcass_y_end - carcass_y_start,
                )
                self.assertEqual(structure.internal_y_start, internal_y_start)
                self.assertEqual(structure.internal_y_end, carcass_y_end)

                for panel_id in (
                    "left_side_panel",
                    "right_side_panel",
                    "top_panel",
                    "bottom_panel",
                ):
                    panel = panels[panel_id]
                    self.assertEqual(panel.pos_y, carcass_y_start)
                    self.assertEqual(panel.pos_y + panel.size_y, carcass_y_end)

                shelf = next(
                    panel
                    for panel in placements
                    if panel.panel_type == "fixed_shelf"
                )
                self.assertEqual(shelf.pos_y, internal_y_start)
                self.assertEqual(shelf.pos_y + shelf.size_y, carcass_y_end)

                doors = [
                    panel for panel in placements if panel.panel_type == "door"
                ]
                self.assertTrue(doors)
                self.assertTrue(
                    all(
                        door.pos_y + door.size_y == spec.depth
                        for door in doors
                    )
                )

                back = panels["back_panel"]
                if back_mount == "cover":
                    self.assertEqual(
                        (back.pos_y, back.size_y),
                        (0.0, spec.back_thickness),
                    )
                    self.assertEqual(
                        back.pos_y + back.size_y,
                        panels["left_side_panel"].pos_y,
                    )
                    self.assertEqual(structure.toe_kick_rear_y, 39.0)
                    self.assertEqual(structure.toe_kick_front_y, 579.0)
                else:
                    self.assertEqual(back.pos_y, spec.back_offset)

    def test_all_modes_pass_through_manufacturing_validation(self) -> None:
        orchestrator = FurnitureOrchestrator(workspace_root=WORKSPACE_ROOT)
        expected_groove_ids = {
            "left_side_back_groove",
            "right_side_back_groove",
            "top_back_groove",
            "bottom_back_groove",
        }

        for back_mount in ("groove", "insert", "cover"):
            with self.subTest(back_mount=back_mount):
                spec = self._spec(back_mount)
                result = orchestrator.execute_spec(
                    f"{back_mount}-back",
                    cabinet_data(
                        spec.furniture_type,
                        width=spec.width,
                        depth=spec.depth,
                        height=spec.height,
                        back_mount=spec.back_mount,
                        back_thickness=spec.back_thickness,
                        shelves=[{"shelf_type": s.shelf_type, "gap_below_mm": s.gap_below_mm} for s in spec.shelves],
                        top_gap_mm=spec.top_gap_mm,
                        n_doors=spec.n_doors,
                    ),
                    through_stage=WorkflowStage.MANUFACTURING_PLANNED,
                )

                self.assertEqual(
                    result.revision.workflow.current,
                    WorkflowStage.MANUFACTURING_PLANNED,
                )
                manufacturing_reports = [
                    report
                    for report in result.revision.validations
                    if report.stage == WorkflowStage.MANUFACTURING_PLANNED.value
                ]
                self.assertTrue(manufacturing_reports)
                self.assertTrue(
                    all(report.passed for report in manufacturing_reports)
                )

                operations = result.revision.stage_outputs[
                    WorkflowStage.MANUFACTURING_PLANNED.value
                ]["operations"]
                operation_ids = {operation["id"] for operation in operations}
                if back_mount == "groove":
                    self.assertEqual(operation_ids, expected_groove_ids)
                else:
                    self.assertEqual(operation_ids, set())

    def test_all_modes_emit_mount_specific_manufacturing_semantics(self) -> None:
        # insert 有三合一五金与成对孔；cover/groove 的螺钉为组装现场工艺，无五金无孔
        insert_contract = (
            "三合一连接件（背板）",
            ("three_in_one_cam", "three_in_one_rod", "three_in_one_nut"),
        )
        screw_names = {"沉头木螺钉（外盖背板）", "沉头木螺钉（背拉条）"}
        screw_hole_types = {
            "cover_back_clearance",
            "cover_back_pilot",
            "back_rail_side_clearance",
            "back_rail_pilot",
        }

        for back_mount in ("insert", "cover", "groove"):
            with self.subTest(back_mount=back_mount):
                spec = self._spec(back_mount)
                layout = plan_layout(spec)
                placements = plan_panels(spec, layout)
                bom = plan_manufacturing(spec, placements)
                panels = {panel.label: panel for panel in bom.panels}

                self.assertEqual(
                    panels["back_panel"].edge_banding,
                    {}
                    if back_mount == "groove"
                    else {"四边": "ABS 1.0mm同色"},
                )
                self.assertEqual(
                    {panel.back_mount for panel in bom.panels},
                    {back_mount},
                )
                for rail in (
                    panel
                    for panel in bom.panels
                    if panel.panel_type == "back_rail"
                ):
                    self.assertEqual(
                        rail.edge_banding,
                        {"四边": "ABS 1.0mm同色"},
                    )

                drilled = emit_drilled_holes(bom)
                holes = [
                    hole
                    for panel in drilled["panels"]
                    for hole in panel["holes"]
                ]

                if back_mount == "insert":
                    hardware_name, required_holes = insert_contract
                    hardware = next(
                        item
                        for item in bom.hardware
                        if item.name == hardware_name
                    )
                    self.assertGreater(hardware.quantity, 0)
                    self.assertIn("投产前确认", hardware.note)
                    # 背板三合一与柜体三合一统一为 three_in_one_*，靠 connection_id 区分：
                    # 只统计背板连接点（connection_id 含 back_panel）的孔。
                    back_holes = [
                        hole
                        for hole in holes
                        if "back_panel" in (hole.get("connection_id") or "")
                    ]
                    counts = {
                        hole_type: sum(
                            hole["hole_type"] == hole_type for hole in back_holes
                        )
                        for hole_type in required_holes
                    }
                    self.assertEqual(set(counts.values()), {hardware.quantity})
                    self.assertTrue(back_holes)
                else:
                    # cover/groove 的螺钉为组装现场工艺，不出五金、不出孔
                    self.assertFalse(
                        any(item.name in screw_names for item in bom.hardware)
                    )
                    self.assertFalse(
                        any(
                            hole["hole_type"] in screw_hole_types
                            for hole in holes
                        )
                    )

                for panel in drilled["panels"]:
                    box = panel["box"]
                    for hole in panel["holes"]:
                        for local_key, size_key in (
                            ("local_x", "x"),
                            ("local_y", "y"),
                            ("local_z", "z"),
                        ):
                            self.assertGreaterEqual(
                                hole[local_key],
                                -1e-6,
                            )
                            self.assertLessEqual(
                                hole[local_key],
                                box[size_key] + 1e-6,
                            )

    def test_mount_specific_validation_ignores_unused_groove_fields(self) -> None:
        for back_mount in ("insert", "cover"):
            with self.subTest(back_mount=back_mount):
                spec = self._spec(back_mount)
                spec.groove_depth = 100
                spec.groove_clearance = -10
                if back_mount == "cover":
                    spec.back_offset = -100
                plan_layout(spec)

        with self.assertRaisesRegex(ValueError, "back_mount"):
            invalid = self._spec("unsupported")
            plan_panels(invalid, plan_layout(invalid))

        cover_spec = furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=25,
            height=1000,
            back_mount="cover",
        )
        cover_layout = plan_layout(cover_spec)
        cover_report = validate_structure(
            cover_layout,
            cover_spec,
            CabinetStructure.from_spec(cover_spec),
        )
        self.assertFalse(cover_report.passed)
        self.assertIn(
            "NON_POSITIVE_INTERNAL_CLEARANCE",
            {issue.code for issue in cover_report.issues},
        )

        insert_spec = furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            back_mount="insert",
            back_thickness=18,
            back_offset=570,
        )
        insert_layout = plan_layout(insert_spec)
        insert_report = validate_structure(
            insert_layout,
            insert_spec,
            CabinetStructure.from_spec(insert_spec),
        )
        self.assertFalse(insert_report.passed)
        self.assertIn(
            "NON_POSITIVE_INTERNAL_CLEARANCE",
            {issue.code for issue in insert_report.issues},
        )

        rail_spec = furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            back_mount="groove",
            back_rail_height=1000,
        )
        rail_layout = plan_layout(rail_spec)
        rail_report = validate_panels(
            rail_spec,
            rail_layout,
            plan_panels(rail_spec, rail_layout),
        )
        self.assertFalse(rail_report.passed)
        self.assertIn(
            "NON_POSITIVE_BACK_RAIL_SPACING",
            {issue.code for issue in rail_report.issues},
        )

    def test_panel_validation_rejects_cover_overlap(self) -> None:
        spec = self._spec("cover")
        layout = plan_layout(spec)
        placements = plan_panels(spec, layout)

        self.assertTrue(validate_panels(spec, layout, placements).passed)

        overlapping = [
            replace(panel, pos_y=0.0)
            if panel.id == "left_side_panel"
            else panel
            for panel in placements
        ]
        report = validate_panels(spec, layout, overlapping)
        issue_codes = {issue.code for issue in report.issues}

        self.assertFalse(report.passed)
        self.assertIn("CARCASS_DEPTH_MISMATCH", issue_codes)
        self.assertIn("COVER_BACK_OVERLAP", issue_codes)


if __name__ == "__main__":
    unittest.main()
