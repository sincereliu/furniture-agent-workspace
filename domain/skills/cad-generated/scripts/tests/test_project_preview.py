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
from fake_request_support import local_request, remote_request
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
        # 版本 = 布局**内容**摘要 + 确认位（不是"第几版"）：同一内容同一个值，改一毫米就变。
        self.assertEqual(document["version"], f"{project.latest.layout_sha256}:0")
        self.assertNotIn(document["revision_id"], document["version"])
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

    def test_preview_switches_rooms_with_chips_and_a_shareable_room_link(self) -> None:
        """房间切换是药丸不是下拉；切房间要写进地址栏 ?room=，链接能分享、能复现。"""
        project = self.orchestrator.create_project("家", home_layout(bed_offset_mm=200))
        html = asyncio.run(server.project_preview(project.id)).body.decode("utf-8")
        self.assertIn('<nav class="room-band" id="room-band" aria-label="房间切换" hidden></nav>', html)
        self.assertIn("function syncRoomBand()", html)
        self.assertIn('data-room-index="${index}"', html)
        self.assertIn('aria-pressed="${index===roomIndex}"', html)
        # 只有一间房时整条房间带藏掉，不留一个点了没反应的控件。
        self.assertIn("if(!rooms||rooms.length<2){band.hidden=true;return}", html)
        self.assertIn('deepLink.get("room")', html)
        self.assertIn('url.searchParams.set("room",entry.id)', html)
        self.assertIn("history.replaceState", html)
        self.assertNotIn("room-switch", html)

    def test_both_pages_carry_a_mode_badge(self) -> None:
        """每页自报身份：预览=只读预览·由对话更新，草稿=草稿·不影响项目。"""
        project = self.orchestrator.create_project("家", home_layout(bed_offset_mm=200))
        preview = asyncio.run(server.project_preview(project.id)).body.decode("utf-8")
        self.assertIn(
            '<p class="mode-badge" id="mode-badge">只读预览 · 由对话更新</p>', preview
        )
        self.assertNotIn("__MODE_BADGE__", preview)

    def test_share_mode_swaps_the_badge_and_drops_the_exit_button(self) -> None:
        """`?mode=view` = 分享形态：牌子换成"只读分享"、页面里根本没有「退出」。

        「退出」能停掉本机的预览服务，不能给拿到链接的人用，所以分享形态是
        **不生成**这个按钮，而不是生成后藏起来。
        """
        project = self.orchestrator.create_project("家", home_layout(bed_offset_mm=200))
        share = asyncio.run(server.project_preview(project.id, mode="view")).body.decode("utf-8")
        self.assertIn('<p class="mode-badge" id="mode-badge">只读分享 · 链接可转发</p>', share)
        self.assertNotIn('id="shutdown-preview"', share)
        self.assertIn('const SHARE_FORM=true', share)
        self.assertIn("只读分享：这一页只能看，位置由房主那边更新。", share)
        self._assert_body_class(share, "readonly share")
        # 不带参数仍是原来那一页：牌子、退出按钮、草稿页提示都在。
        normal = asyncio.run(server.project_preview(project.id)).body.decode("utf-8")
        self.assertIn('<p class="mode-badge" id="mode-badge">只读预览 · 由对话更新</p>', normal)
        self.assertIn('id="shutdown-preview"', normal)
        self.assertIn('const SHARE_FORM=false', normal)
        self._assert_body_class(normal, "readonly")

    def _assert_body_class(self, html: str, expected: str) -> None:
        self.assertIn(f'<body class="{expected}">', html)

    def test_share_link_is_a_plain_expression_not_a_permission(self) -> None:
        """分享链接只是地址栏表达：它没有任何办法绕过服务端的写权限。"""
        url = project_preview.preview_url("project_abc", mode="view")
        self.assertTrue(url.endswith("/api/project/project_abc/preview?mode=view"))
        self.assertEqual(
            project_preview.preview_url("project_abc"),
            "http://127.0.0.1:8000/api/project/project_abc/preview",
        )
        source = (SCRIPT_ROOT / "server.py").read_text(encoding="utf-8")
        # mode 只喂给渲染；判据函数连 mode 都拿不到，所以它不可能参与授权。
        self.assertIn("render_project_preview(project_id, document, mode=mode)", source)
        self.assertIn("def access_scope(request: Request) -> str:", source)
        self.assertIn("def may_edit(request: Request) -> bool:", source)

    def test_read_only_panel_arm_has_no_controls(self) -> None:
        """右栏是"一份模板两支"，只读那支不得含 input / button。

        注意：两支都在同一份 HTML 的 JS 源码里，所以只能断言分支内容，
        不能断言"整页源码里没有 class=\"num\""——那串在可编辑支里。
        """
        project = self.orchestrator.create_project("家", home_layout(bed_offset_mm=200))
        html = asyncio.run(server.project_preview(project.id)).body.decode("utf-8")
        self.assertIn("const READ_ONLY=true", html)
        readonly_gap = '<dt>${label}</dt><dd><span data-gap="${key}"></span> mm<span class="who" data-who="${key}"></span></dd>'
        self.assertIn(readonly_gap, html)
        self.assertNotIn("input", readonly_gap)
        self.assertNotIn("button", readonly_gap)
        # 朝向 / 离地 / 提示语也都是纯文字
        self.assertIn('<span data-field="rotation"></span>°<span class="who" data-front></span>', html)
        self.assertIn('<span data-field="height"></span> mm', html)
        self.assertIn("只读预览：位置由对话更新；要自己拖，用草稿页。", html)
        # 只读页不画编辑手柄：橙点/旋转环与蓝点都不生成，但"正面"绿箭头保留。
        self.assertIn(
            "if(READ_ONLY){state.handle=null;state.rotateRing=null;"
            "drawFrontArrow(item,project,pivot,radius);return}",
            html,
        )
        self.assertIn("if(READ_ONLY){state.heightHandle=null;return}", html)
        self.assertIn("function drawFrontArrow(item,project,pivot,radius)", html)
        self.assertNotIn("只读预览：位置由对话更新；要自己拖，用草稿页。", readonly_gap)

    def test_content_digest_has_one_implementation(self) -> None:
        """同一份内容只能有一个摘要：冻结哈希、分析血缘、交付校验必须同源。

        交付阶段（`furniture_delivery_validation`）按分层保留了自己的一份实现 ——
        阶段包不该反向依赖编排层 —— 所以这里用断言把两份钉在一起：值不同就红。
        """
        from furniture_delivery_validation import validation as delivery_validation
        from furniture_workflow import workflow_constants, workflow_digest
        from furniture_workflow.workflow_project import stable_digest

        payload = {"b": 1, "a": [2, 3], "文字": "值"}
        digests = {
            "workflow_digest": workflow_digest.stable_digest(payload),
            "workflow_constants": workflow_constants._stable_digest(payload),
            "workflow_project": stable_digest(payload),
            "delivery_validation": delivery_validation._stable_digest(payload),
        }
        self.assertEqual(len(set(digests.values())), 1, digests)

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
        class Dummy:
            should_exit = False

        server.app.state.preview_server = Dummy()
        self.addCleanup(lambda: delattr(server.app.state, "preview_server"))

        with self.assertRaises(HTTPException) as refused:
            asyncio.run(server.preview_shutdown(remote_request()))
        self.assertEqual(refused.exception.status_code, 403)
        self.assertFalse(server.app.state.preview_server.should_exit)

        async def stop_locally() -> dict:
            result = await server.preview_shutdown(local_request())
            await asyncio.sleep(0.4)
            return result

        accepted = asyncio.run(stop_locally())
        self.assertEqual(accepted["status"], "stopping")
        self.assertTrue(server.app.state.preview_server.should_exit)
        server.app.state.preview_server = None
        self.assertFalse(server.stop_preview_server())

    def test_write_permission_has_exactly_one_judgement(self) -> None:
        """写权限只有 `access_scope` 一个判据；停进程、落盘、出 CAD 共用它。

        这条盯的是形状而不是措辞：主机名白名单只该在判据里读一次，端点里若再出现一次
        `request.client.host` 比较，就是第二份判据——将来加"只读分享"时必然漏掉它。
        """
        self.assertEqual(server.access_scope(local_request()), server.ACCESS_LOCAL)
        self.assertEqual(server.access_scope(remote_request()), server.ACCESS_DENIED)
        self.assertTrue(server.may_edit(local_request()))
        self.assertFalse(server.may_edit(remote_request()))
        source = (SCRIPT_ROOT / "server.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("_LOCAL_HOSTS"), 2)  # 定义一次 + 判据里读一次
        self.assertEqual(source.count("if not may_edit(request):"), 5)  # 五个有副作用的端点
        endpoints = source.split("def may_edit")[1]
        self.assertNotIn("request.client.host", endpoints)


if __name__ == "__main__":
    unittest.main()
