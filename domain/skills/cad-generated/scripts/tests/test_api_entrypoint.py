from __future__ import annotations

import asyncio
import re
import sys
import unittest
from pathlib import Path

from pydantic import ValidationError


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

import server


def bedroom_request(**overrides) -> server.RoomSceneRequest:
    payload = {
        "room": server.RoomRequest(
            id="bedroom",
            name="卧室",
            width_mm=4200,
            depth_mm=3600,
            height_mm=2800,
        ),
        "items": [
            server.SceneItemRequest(
                id="bed",
                label="床",
                category="bed",
                width=1800,
                depth=2000,
                height=450,
                placement=server.ItemPlacementRequest(
                    mode="wall",
                    host_wall="north",
                    offset_mm=1200,
                ),
            )
        ],
    }
    payload.update(overrides)
    return server.RoomSceneRequest(**payload)


class ApiEntrypointTests(unittest.TestCase):
    def test_room_scene_schema_rejects_unknown_fields(self) -> None:
        properties = server.RoomSceneRequest.model_json_schema()["properties"]
        self.assertIn("room", properties)
        self.assertIn("items", properties)
        self.assertNotIn("furniture_category", properties)
        openapi_schemas = server.app.openapi()["components"]["schemas"]
        self.assertIn("RoomSceneRequest", openapi_schemas)
        self.assertNotIn("CabinetRequest", openapi_schemas)
        self.assertNotIn("BOMResponse", openapi_schemas)
        paths = server.app.openapi()["paths"]
        self.assertIn("/api/plan-room", paths)
        self.assertIn("/api/plan-room/cad", paths)
        self.assertNotIn("/api/plan-layout", paths)
        self.assertNotIn("/api/plan-cabinet", paths)
        with self.assertRaises(ValidationError):
            server.RoomSceneRequest(
                room=server.RoomRequest(
                    id="bedroom",
                    name="卧室",
                    width_mm=4200,
                    depth_mm=3600,
                    height_mm=2800,
                ),
                items=[],
            )

    def test_plan_room_returns_items_preview_and_viewer(self) -> None:
        request = bedroom_request()
        response = asyncio.run(server.plan_room(request))
        self.assertEqual(response.room["name"], "卧室")
        self.assertEqual(response.items[0]["placement"]["rotation_z_deg"], 0)
        self.assertEqual(response.preview["media_type"], "image/svg+xml")
        self.assertEqual(response.preview["view_kind"], "perspective_envelope")
        self.assertIn("<svg", response.preview["svg"])
        self.assertEqual(response.viewer["media_type"], "text/html")
        self.assertIsNone(response.cad)

        svg_response = asyncio.run(server.plan_room_preview(request))
        self.assertEqual(svg_response.media_type, "image/svg+xml")
        self.assertIn(b"<svg", svg_response.body)

        viewer_response = asyncio.run(server.plan_room_viewer(request))
        self.assertEqual(viewer_response.media_type, "text/html")
        self.assertIn(b'<canvas id="scene"', viewer_response.body)
        self.assertIn(b'data-view="top"', viewer_response.body)

    def test_plan_room_rejects_missing_room_size(self) -> None:
        with self.assertRaises(ValidationError):
            server.RoomRequest(id="bedroom", name="卧室", depth_mm=3600, height_mm=2800)

    def test_runtime_contract_documents_every_api_path(self) -> None:
        """Every served API path is documented; no documented path is stale."""
        contract = (
            WORKSPACE_ROOT
            / "domain"
            / "skills"
            / "cad-generated"
            / "references"
            / "runtime-contract.md"
        ).read_text(encoding="utf-8")
        documented = set(
            re.findall(r"`(/api/[^`.]+)`", contract)
        )

        served = set(server.app.openapi()["paths"])
        # Liveness and the Swagger entry are served but are not scene contract.
        non_contract = {"/health", "/"}
        self.assertEqual(
            documented | non_contract,
            served,
            "runtime-contract.md must list every served path: "
            f"missing from contract {sorted(served - non_contract - documented)}, "
            f"stale in contract {sorted(documented - served)}",
        )


if __name__ == "__main__":
    unittest.main()
