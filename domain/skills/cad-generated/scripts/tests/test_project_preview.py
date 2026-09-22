from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from fastapi import HTTPException


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

import server
from furniture_layout.project_layout import ProjectLayout
from furniture_workflow import project_preview
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_store import JsonProjectStore


def home_layout(*, bed_offset_mm: float) -> ProjectLayout:
    return ProjectLayout.from_source(
        {
            "rooms": [
                {
                    "id": "bedroom",
                    "name": "卧室",
                    "width_mm": 4200,
                    "depth_mm": 3600,
                    "height_mm": 2800,
                    "items": [
                        {
                            "id": "bed",
                            "label": "床",
                            "category": "bed",
                            "width": 1800,
                            "depth": 2000,
                            "height": 450,
                            "placement": {
                                "mode": "wall",
                                "host_wall": "north",
                                "offset_mm": bed_offset_mm,
                            },
                        }
                    ],
                },
                {
                    "id": "living",
                    "name": "客厅",
                    "width_mm": 5000,
                    "depth_mm": 4200,
                    "height_mm": 2800,
                    "items": [
                        {
                            "id": "sofa",
                            "label": "沙发",
                            "category": "sofa",
                            "width": 2200,
                            "depth": 900,
                            "height": 800,
                            "placement": {
                                "mode": "wall",
                                "host_wall": "south",
                                "offset_mm": 400,
                            },
                        }
                    ],
                },
            ]
        }
    )


class ProjectPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = WORKSPACE_ROOT / "temp" / "test-project-preview"
        if self.root.exists():
            shutil.rmtree(self.root)
        self.store = JsonProjectStore(self.root)
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT,
            project_store=self.store,
        )
        self._patch = mock.patch.object(server, "STORE_ROOT", self.root)
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)

    def test_missing_project_returns_404(self) -> None:
        with self.assertRaises(HTTPException) as missing:
            asyncio.run(server.project_layout("project_missing"))
        self.assertEqual(missing.exception.status_code, 404)
        with self.assertRaises(HTTPException) as preview:
            asyncio.run(server.project_preview("project_missing"))
        self.assertEqual(preview.exception.status_code, 404)

    def test_project_id_rejects_path_escape(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(server.project_layout("../store"))
        self.assertEqual(ctx.exception.status_code, 422)

    def test_layout_returns_placed_envelopes_without_viewer_markup(self) -> None:
        project = self.orchestrator.create_project("家", home_layout(bed_offset_mm=200))
        document = asyncio.run(server.project_layout(project.id))
        self.assertEqual(document["revision_number"], 1)
        self.assertFalse(document["layout_confirmed"])
        self.assertEqual(
            document["version"],
            f"{document['revision_id']}:1:0",
        )
        self.assertEqual([room["id"] for room in document["rooms"]], ["bedroom", "living"])
        bed = document["rooms"][0]["scene"]["items"][0]
        self.assertEqual(bed["id"], "bed")
        self.assertEqual(bed["placement"]["offset_mm"], 200)
        encoded = json.dumps(document)
        self.assertNotIn("viewer", encoded)
        self.assertNotIn("<svg", encoded)
        self.assertNotIn("text/html", encoded)

    def test_preview_embeds_first_room_and_polls_layout(self) -> None:
        project = self.orchestrator.create_project("家", home_layout(bed_offset_mm=200))
        response = asyncio.run(server.project_preview(project.id))
        html = response.body.decode("utf-8")
        self.assertEqual(response.media_type, "text/html")
        self.assertIn("<canvas", html)
        self.assertIn('"id":"bed"', html)
        self.assertIn('"offset_mm":200', html)
        self.assertIn("卧室", html)
        self.assertIn("客厅", html)
        self.assertIn("const READ_ONLY=true", html)
        self.assertIn(f'/api/project/{project.id}/layout', html)
        self.assertIn('id="shutdown-preview"', html)
        self.assertIn('fetch("/api/preview/shutdown"', html)
        self.assertIn('cache:"no-store"', html)
        self.assertIn("setInterval(pollLayout,1000)", html)
        self.assertIn("layoutVersionOf(payload)===layoutVersion", html)
        self.assertIn("drag||state.orbiting||state.panning", html)
        self.assertIn("if(READ_ONLY)return false", html)
        self.assertNotIn("__SCENE_JSON__", html)
        self.assertNotIn("__POLL_URL__", html)

    def test_preview_shows_room_axes_and_cursor_coordinates(self) -> None:
        """房间坐标要看得见：原点三轴（带总宽/总深/总高）+ 光标读数 + 右栏坐标行。"""
        project = self.orchestrator.create_project("家", home_layout(bed_offset_mm=200))
        html = asyncio.run(server.project_preview(project.id)).body.decode("utf-8")
        self.assertIn('id="coord"', html)
        self.assertIn("function drawOriginAxes(project)", html)
        self.assertIn("O (0,0,0)", html)
        self.assertIn("X 东 · 总宽", html)
        self.assertIn("Y 南 · 总深", html)
        self.assertIn("Z 上 · 总高", html)
        self.assertIn('data-field="coord"', html)
        self.assertIn("unprojectToGround(sx,sy)", html)
        # 右向量必须是 cross(up, forward)：反过来会让整幅画面左右镜像，前视把东墙画到左边。
        self.assertIn("cross([0,0,1],forward)", html)

    def test_revise_layout_changes_version_and_reread_position(self) -> None:
        project = self.orchestrator.create_project("家", home_layout(bed_offset_mm=200))
        before = asyncio.run(server.project_layout(project.id))
        self.orchestrator.revise_layout(project, home_layout(bed_offset_mm=800))
        after = asyncio.run(server.project_layout(project.id))
        self.assertEqual(after["revision_number"], 2)
        self.assertNotEqual(after["version"], before["version"])
        self.assertEqual(
            after["rooms"][0]["scene"]["items"][0]["placement"]["offset_mm"],
            800,
        )
        html = asyncio.run(server.project_preview(project.id)).body.decode("utf-8")
        self.assertIn('"offset_mm":800', html)
        self.assertNotIn('"offset_mm":200', html)

        self.orchestrator.confirm_stage(project, "layout_plan")
        confirmed = asyncio.run(server.project_layout(project.id))
        self.assertTrue(confirmed["layout_confirmed"])
        self.assertNotEqual(confirmed["version"], after["version"])
        self.assertEqual(
            confirmed["rooms"][0]["scene"]["items"][0]["placement"]["offset_mm"],
            800,
        )


class OpenProjectPreviewTests(unittest.TestCase):
    def test_local_opener_reaches_localhost_when_proxy_is_set(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                body = b'{"status":"ok"}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        with mock.patch.dict(
            os.environ,
            {
                "HTTP_PROXY": "http://127.0.0.1:10808",
                "HTTPS_PROXY": "http://127.0.0.1:10808",
            },
        ):
            with project_preview._LOCAL_OPENER.open(
                f"http://127.0.0.1:{port}/health",
                timeout=2,
            ) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(b"ok", response.read())
    def test_disabled_browser_does_not_open_or_start_a_server(self) -> None:
        with mock.patch.dict(os.environ, {"FURNITURE_PREVIEW_BROWSER": "0"}):
            with mock.patch.object(project_preview.webbrowser, "open") as opener:
                with mock.patch.object(
                    project_preview.subprocess, "Popen"
                ) as popen:
                    result = project_preview.open_project_preview(
                        "project_abc",
                        workspace_root=WORKSPACE_ROOT,
                    )
        opener.assert_not_called()
        popen.assert_not_called()
        self.assertFalse(result["opened"])
        self.assertEqual(
            result["url"],
            "http://127.0.0.1:8000/api/project/project_abc/preview",
        )

    def test_open_uses_the_server_that_is_already_up(self) -> None:
        with mock.patch.dict(os.environ, {"FURNITURE_PREVIEW_BROWSER": "1"}):
            with mock.patch.object(
                project_preview, "preview_server_is_up", return_value=True
            ):
                with mock.patch.object(
                    project_preview.subprocess, "Popen"
                ) as popen:
                    with mock.patch.object(
                        project_preview.webbrowser, "open", return_value=True
                    ) as opener:
                        result = project_preview.open_project_preview(
                            "project_abc",
                            workspace_root=WORKSPACE_ROOT,
                        )
        popen.assert_not_called()
        opener.assert_called_once_with(
            "http://127.0.0.1:8000/api/project/project_abc/preview",
            new=2,
        )
        self.assertTrue(result["opened"])

    def test_open_starts_the_server_when_it_is_down(self) -> None:
        checks = iter((False, True))
        with mock.patch.dict(os.environ, {"FURNITURE_PREVIEW_BROWSER": "1"}):
            with mock.patch.object(
                project_preview,
                "preview_server_is_up",
                side_effect=lambda: next(checks),
            ):
                with mock.patch.object(project_preview.subprocess, "Popen") as popen:
                    with mock.patch.object(
                        project_preview.webbrowser, "open", return_value=True
                    ) as opener:
                        with mock.patch.object(project_preview.time, "sleep"):
                            result = project_preview.open_project_preview(
                                "project_abc",
                                workspace_root=WORKSPACE_ROOT,
                            )
        popen.assert_called_once()
        command = popen.call_args.args[0]
        self.assertTrue(str(command[1]).endswith("server.py"))
        opener.assert_called_once()
        self.assertTrue(result["opened"])

    def test_shutdown_refuses_remote_and_stops_a_local_server(self) -> None:
        class Client:
            def __init__(self, host: str) -> None:
                self.host = host

        class Request:
            def __init__(self, host: str) -> None:
                self.client = Client(host)

        class Dummy:
            should_exit = False

        server.app.state.preview_server = Dummy()
        self.addCleanup(lambda: delattr(server.app.state, "preview_server"))

        with self.assertRaises(HTTPException) as refused:
            asyncio.run(server.preview_shutdown(Request("8.8.8.8")))
        self.assertEqual(refused.exception.status_code, 403)
        self.assertFalse(server.app.state.preview_server.should_exit)

        async def stop_locally() -> dict:
            result = await server.preview_shutdown(Request("127.0.0.1"))
            await asyncio.sleep(0.4)
            return result

        accepted = asyncio.run(stop_locally())
        self.assertEqual(accepted["status"], "stopping")
        self.assertTrue(server.app.state.preview_server.should_exit)
        server.app.state.preview_server = None
        self.assertFalse(server.stop_preview_server())


if __name__ == "__main__":
    unittest.main()
