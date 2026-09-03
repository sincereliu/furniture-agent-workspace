from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

import server
from panel_fixtures import cabinet_data


class ApiEntrypointTests(unittest.TestCase):
    def test_request_exposes_back_mount_and_toe_kick_controls(self) -> None:
        request = server.CabinetRequest(
            **cabinet_data(
                back_mount="groove",
                back_rail_height=80,
                groove_depth=8,
                groove_clearance=0.5,
                toe_kick_reveal_front=2,
                toe_kick_reveal_back=25,
                toe_kick_support_count=2,
                constraints=["背板必须入槽"],
                constraint_mappings={"背板必须入槽": "structure.back_mount"},
            ),
        )

        payload = request.model_dump(exclude_none=True)
        self.assertEqual(payload["back_mount"], "groove")
        self.assertEqual(payload["back_rail_height"], 80)
        self.assertEqual(payload["groove_depth"], 8)
        self.assertEqual(payload["groove_clearance"], 0.5)
        self.assertEqual(payload["toe_kick_support_count"], 2)
        self.assertEqual(
            payload["constraint_mappings"]["背板必须入槽"],
            "structure.back_mount",
        )

        properties = server.CabinetRequest.model_json_schema()["properties"]
        self.assertIn("back_mount", properties)
        self.assertIn("back_rail_height", properties)
        self.assertIn("constraint_mappings", properties)
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
                    **cabinet_data("wall_cabinet"),
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
                    **cabinet_data("wall_cabinet", back_thickness=18),
                )
            )
        )
        self.assertEqual(auto_insert.back_mount, "insert")

    def test_layout_endpoint_returns_room_position_and_svg_preview(self) -> None:
        request = server.CabinetRequest(
            type="floor_cabinet",
            width=1800,
            depth=600,
            height=2400,
            room=server.RoomRequest(
                id="bedroom",
                name="卧室",
                width_mm=4200,
                depth_mm=3600,
                height_mm=2800,
            ),
            placement=server.FurniturePlacementRequest(
                mode="wall",
                host_wall="west",
                offset_mm=300,
            ),
        )

        response = asyncio.run(server.plan_layout(request))

        self.assertEqual(response.room_placement["room"]["name"], "卧室")
        self.assertEqual(
            response.room_placement["placement"]["rotation_z_deg"],
            270,
        )
        self.assertEqual(response.preview["media_type"], "image/svg+xml")
        self.assertEqual(
            response.preview["view_kind"],
            "perspective_envelope",
        )
        self.assertIn("<svg", response.preview["svg"])
        self.assertEqual(response.viewer["media_type"], "text/html")
        self.assertEqual(
            response.viewer["view_kind"],
            "interactive_orbit_envelope",
        )

        svg_response = asyncio.run(server.plan_layout_preview(request))
        self.assertEqual(svg_response.media_type, "image/svg+xml")
        self.assertIn(b"<svg", svg_response.body)

        viewer_response = asyncio.run(server.plan_layout_viewer(request))
        self.assertEqual(viewer_response.media_type, "text/html")
        self.assertIn(b'<canvas id="scene"', viewer_response.body)
        self.assertIn(b'data-view="top"', viewer_response.body)

    def test_layout_endpoint_uses_default_bedroom_without_room_input(self) -> None:
        request = server.CabinetRequest(
            type="floor_cabinet",
            width=1600,
            depth=600,
            height=2400,
        )

        response = asyncio.run(server.plan_layout(request))

        self.assertEqual(
            response.layout_context,
            {
                "room_source": "default_bedroom",
                "placement_source": "default_north_wall_centered",
            },
        )
        self.assertEqual(
            response.room_placement["room"]["name"],
            "默认卧室（系统假设）",
        )
        self.assertEqual(
            response.room_placement["placement"]["origin_x_mm"],
            1300,
        )
        self.assertIn("<svg", response.preview["svg"])
        self.assertIn("pointermove", response.viewer["html"])

    def test_plan_endpoint_returns_each_back_mount_manufacturing_contract(
        self,
    ) -> None:
        # insert 出三合一；cover/groove 的螺钉为组装现场工艺：无螺钉五金、无螺钉孔
        contracts = {
            "groove": (9, None, set(), 4),
            "insert": (
                18,
                "三合一连接件（背板）",
                {
                    "three_in_one_cam",
                    "three_in_one_rod",
                    "three_in_one_nut",
                },
                0,
            ),
            "cover": (9, None, set(), 0),
        }
        screw_names = {"沉头木螺钉（外盖背板）", "沉头木螺钉（背拉条）"}
        screw_hole_types = {
            "cover_back_clearance",
            "cover_back_pilot",
            "back_rail_side_clearance",
            "back_rail_pilot",
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
                            **cabinet_data(
                                back_mount=back_mount,
                                back_thickness=back_thickness,
                                back_rail_height=80,
                                shelf_count=1,
                                n_doors=2,
                            ),
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

                if hardware_name is None:
                    self.assertFalse(
                        any(
                            item.name in screw_names
                            for item in response.hardware
                        )
                    )
                else:
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
                self.assertFalse(screw_hole_types & hole_types)
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
