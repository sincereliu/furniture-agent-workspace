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
        self.assertNotIn("BOMResponse", openapi_schemas)
        paths = server.app.openapi()["paths"]
        self.assertNotIn("/api/plan-cabinet", paths)

        with self.assertRaises(ValueError):
            server.CabinetRequest(
                furniture_category="floor_cabinet",
                width=800,
                depth=600,
                height=1000,
                back_mount="unsupported",
            )

    def test_request_requires_canonical_furniture_category(self) -> None:
        canonical = server.CabinetRequest(
            furniture_category="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
        )

        self.assertEqual(
            canonical.model_dump(exclude_none=True)["furniture_category"],
            "floor_cabinet",
        )
        properties = server.CabinetRequest.model_json_schema()["properties"]
        self.assertIn("furniture_category", properties)
        self.assertNotIn("type", properties)
        with self.assertRaises(ValueError):
            server.CabinetRequest(
                type="floor_cabinet",
                width=800,
                depth=600,
                height=1000,
            )

    def test_layout_endpoint_returns_room_position_and_svg_preview(self) -> None:
        request = server.CabinetRequest(
            furniture_category="floor_cabinet",
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
            furniture_category="floor_cabinet",
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


if __name__ == "__main__":
    unittest.main()
