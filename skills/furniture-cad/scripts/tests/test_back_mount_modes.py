from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_design_intent.design_spec import FurnitureSpec
from furniture_layout.layout_pipeline import plan_layout
from furniture_manufacturing.manufacturing_bom import plan_manufacturing
from furniture_panel_planning.panel_planning import plan_panels
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_state import WorkflowStage


class BackMountModeTests(unittest.TestCase):
    def _spec(self, back_mount: str) -> FurnitureSpec:
        return FurnitureSpec(
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
                placements = plan_panels(spec, layout)
                panels = {panel.id: panel for panel in placements}
                carcass_y_start, carcass_y_end, internal_y_start = expected

                self.assertEqual(layout.carcass_y_start, carcass_y_start)
                self.assertEqual(layout.carcass_y_end, carcass_y_end)
                self.assertEqual(
                    layout.side_depth,
                    carcass_y_end - carcass_y_start,
                )
                self.assertEqual(layout.internal_y_start, internal_y_start)
                self.assertEqual(layout.internal_y_end, carcass_y_end)

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
                    self.assertEqual(layout.toe_kick_rear_y, 39.0)
                    self.assertEqual(layout.toe_kick_front_y, 579.0)
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
                    {
                        "type": spec.furniture_type,
                        "width": spec.width,
                        "depth": spec.depth,
                        "height": spec.height,
                        "back_mount": spec.back_mount,
                        "back_thickness": spec.back_thickness,
                        "shelf_count": spec.shelf_count,
                        "n_doors": spec.n_doors,
                    },
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
            plan_layout(self._spec("unsupported"))

        with self.assertRaisesRegex(ValueError, "cover back mount"):
            plan_layout(
                FurnitureSpec(
                    furniture_type="floor_cabinet",
                    width=800,
                    depth=25,
                    height=1000,
                    back_mount="cover",
                )
            )

        with self.assertRaisesRegex(ValueError, "inserted back"):
            plan_layout(
                FurnitureSpec(
                    furniture_type="floor_cabinet",
                    width=800,
                    depth=600,
                    height=1000,
                    back_mount="insert",
                    back_thickness=18,
                    back_offset=570,
                )
            )

        with self.assertRaisesRegex(ValueError, "back_rail_height"):
            plan_layout(
                FurnitureSpec(
                    furniture_type="floor_cabinet",
                    width=800,
                    depth=600,
                    height=600,
                    back_mount="groove",
                    back_rail_height=600,
                )
            )

    def test_panel_validation_rejects_cover_overlap(self) -> None:
        orchestrator = FurnitureOrchestrator(workspace_root=WORKSPACE_ROOT)
        spec = self._spec("cover")
        layout = plan_layout(spec)
        placements = plan_panels(spec, layout)

        self.assertTrue(
            orchestrator._validate_panels(spec, layout, placements).passed
        )

        overlapping = [
            replace(panel, pos_y=0.0)
            if panel.id == "left_side_panel"
            else panel
            for panel in placements
        ]
        report = orchestrator._validate_panels(spec, layout, overlapping)
        issue_codes = {issue.code for issue in report.issues}

        self.assertFalse(report.passed)
        self.assertIn("CARCASS_DEPTH_MISMATCH", issue_codes)
        self.assertIn("COVER_BACK_OVERLAP", issue_codes)


if __name__ == "__main__":
    unittest.main()
