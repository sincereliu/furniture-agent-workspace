from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

import server


class ApiEntrypointTests(unittest.TestCase):
    def test_request_exposes_back_mount_and_toe_kick_controls(self) -> None:
        request = server.CabinetRequest(
            type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            back_mount="groove",
            back_rail_height=80,
            groove_depth=8,
            groove_clearance=0.5,
            toe_kick_reveal_front=2,
            toe_kick_reveal_back=25,
            toe_kick_support_count=2,
        )

        payload = request.model_dump(exclude_none=True)
        self.assertEqual(payload["back_mount"], "groove")
        self.assertEqual(payload["back_rail_height"], 80)
        self.assertEqual(payload["groove_depth"], 8)
        self.assertEqual(payload["groove_clearance"], 0.5)
        self.assertEqual(payload["toe_kick_support_count"], 2)

        properties = server.CabinetRequest.model_json_schema()["properties"]
        self.assertIn("back_mount", properties)
        self.assertIn("back_rail_height", properties)
        openapi_schemas = server.app.openapi()["components"]["schemas"]
        self.assertIn(
            "back_mount",
            openapi_schemas["CabinetRequest"]["properties"],
        )
        for response_field in (
            "readiness",
            "back_mount",
            "hardware",
            "operations",
            "hole_color_legend",
            "drilled_holes",
        ):
            self.assertIn(
                response_field,
                openapi_schemas["BOMResponse"]["properties"],
            )

        with self.assertRaises(ValueError):
            server.CabinetRequest(
                type="floor_cabinet",
                width=800,
                depth=600,
                height=1000,
                back_mount="unsupported",
            )

    def test_plan_endpoint_runs_through_the_application_workflow(self) -> None:
        response = asyncio.run(
            server.plan_cabinet(
                server.CabinetRequest(
                    type="wall_cabinet",
                    width=800,
                    depth=350,
                    height=900,
                )
            )
        )

        self.assertEqual(response.furniture_name, "吊柜")
        self.assertEqual(response.readiness, "preliminary")
        self.assertEqual(response.back_mount, "groove")
        self.assertGreater(response.panel_count, 0)

        auto_insert = asyncio.run(
            server.plan_cabinet(
                server.CabinetRequest(
                    type="wall_cabinet",
                    width=800,
                    depth=350,
                    height=900,
                    back_mount="auto",
                    back_thickness=18,
                )
            )
        )
        self.assertEqual(auto_insert.back_mount, "insert")

    def test_plan_endpoint_returns_each_back_mount_manufacturing_contract(
        self,
    ) -> None:
        contracts = {
            "groove": (
                9,
                "沉头木螺钉（背拉条）",
                {"back_rail_side_clearance", "back_rail_pilot"},
                4,
            ),
            "insert": (
                18,
                "三合一连接件（内嵌背板）",
                {
                    "back_insert_cam",
                    "back_insert_rod",
                    "back_insert_pre_nut",
                },
                0,
            ),
            "cover": (
                9,
                "沉头木螺钉（外盖背板）",
                {"cover_back_clearance", "cover_back_pilot"},
                0,
            ),
        }

        for back_mount, (
            back_thickness,
            hardware_name,
            required_holes,
            expected_operation_count,
        ) in contracts.items():
            with self.subTest(back_mount=back_mount):
                response = asyncio.run(
                    server.plan_cabinet(
                        server.CabinetRequest(
                            type="floor_cabinet",
                            width=800,
                            depth=600,
                            height=1000,
                            back_mount=back_mount,
                            back_thickness=back_thickness,
                            back_rail_height=80,
                            shelf_count=1,
                            n_doors=2,
                        )
                    )
                )

                self.assertEqual(response.back_mount, back_mount)
                self.assertEqual(
                    {panel.back_mount for panel in response.panels},
                    {back_mount},
                )
                back = next(
                    panel
                    for panel in response.panels
                    if panel.panel_type == "back"
                )
                self.assertEqual(
                    back.edge_banding,
                    {}
                    if back_mount == "groove"
                    else {"四边": "ABS 1.0mm同色"},
                )

                hardware = next(
                    item
                    for item in response.hardware
                    if item.name == hardware_name
                )
                self.assertGreater(hardware.quantity, 0)
                self.assertIn("投产前确认", hardware.note)
                self.assertTrue(hardware.drilling)

                hole_types = {
                    hole.hole_type
                    for panel in response.drilled_holes
                    for hole in panel.holes
                }
                self.assertTrue(required_holes.issubset(hole_types))
                self.assertEqual(
                    len(response.operations),
                    expected_operation_count,
                )
                if back_mount == "groove":
                    rails = [
                        panel
                        for panel in response.panels
                        if panel.panel_type == "back_rail"
                    ]
                    self.assertTrue(rails)
                    self.assertTrue(
                        all(panel.size_z == 80 for panel in rails)
                    )


if __name__ == "__main__":
    unittest.main()
