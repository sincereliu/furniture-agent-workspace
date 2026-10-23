from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import threading
import time
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
from fake_request_support import FakeRequest, local_request, remote_request
from furniture_layout.project_layout import ProjectLayout
from furniture_layout import open_preview
from furniture_layout.layout_events import (
    iter_layout_events,
    layout_file_stamp,
    notice_for_change,
    pin_page_lease,
    project_layout_events,
    same_lease_renewal,
)
from furniture_workflow.workflow_lease import (
    LEASE_TTL_SECONDS,
    acquire,
    hold_connection,
    read_lease,
    release_if_unchanged,
)
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_store import JsonProjectStore


def home_layout(*, bed_origin_z_mm: float) -> ProjectLayout:
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
                                "origin_z_mm": bed_origin_z_mm,
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
            asyncio.run(server.project_preview("project_missing", local_request()))
        self.assertEqual(preview.exception.status_code, 404)

    def test_project_id_rejects_path_escape(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(server.project_layout("../store"))
        self.assertEqual(ctx.exception.status_code, 422)

    def test_layout_returns_placed_envelopes_without_viewer_markup(self) -> None:
        project = self.orchestrator.create_project("家", home_layout(bed_origin_z_mm=200))
        document = asyncio.run(server.project_layout(project.id))
        self.assertEqual(document["revision_number"], 1)
        self.assertFalse(document["layout_confirmed"])
        # 版本 = 布局**内容**摘要 + 确认位（不是"第几版"）：同一内容同一个值，改一毫米就变。
        self.assertEqual(document["version"], f"{project.latest.layout_sha256}:0")
        self.assertNotIn(document["revision_id"], document["version"])
        self.assertEqual([room["id"] for room in document["rooms"]], ["bedroom", "living"])
        bed = document["rooms"][0]["scene"]["items"][0]
        self.assertEqual(bed["id"], "bed")
        self.assertEqual(bed["placement"]["origin_z_mm"], 200)
        encoded = json.dumps(document)
        self.assertNotIn("viewer", encoded)
        self.assertNotIn("<svg", encoded)
        self.assertNotIn("text/html", encoded)

    def test_preview_embeds_first_room_and_watches_layout_events(self) -> None:
        project = self.orchestrator.create_project("家", home_layout(bed_origin_z_mm=200))
        response = asyncio.run(
            server.project_preview(project.id, remote_request())
        )
        html = response.body.decode("utf-8")
        self.assertEqual(response.media_type, "text/html")
        self.assertIn("<canvas", html)
        self.assertIn('"id":"bed"', html)
        self.assertIn('"origin_z_mm":200', html)
        self.assertIn("卧室", html)
        self.assertIn("客厅", html)
        # 非本机来源 → 只读页（能不能编辑由服务端按权限渲染，不看 URL 参数）。
        self.assertIn("const READ_ONLY=true", html)
        self.assertIn(f'/api/project/{project.id}/layout', html)
        self.assertIn('id="shutdown-preview"', html)
        self.assertIn('fetch("/api/preview/shutdown"', html)
        self.assertIn('cache:"no-store"', html)
        self.assertIn('new EventSource(LAYOUT_URL+"/events"+query)', html)
        self.assertNotIn("POLL_URL", html)
        self.assertNotIn("setInterval(pollLayout,1000)", html)
        self.assertNotIn("typeof EventSource", html)
        self.assertNotIn('fetch("/api/preview/presence"', html)
        self.assertIn('from "/layout-view/layout_persistence.js"', html)
        self.assertIn("drag||state.orbiting||state.panning", html)
        self.assertIn("if(READ_ONLY)return false", html)
        self.assertNotIn("__SCENE_JSON__", html)
        self.assertNotIn("__POLL_URL__", html)
        self.assertNotIn("__PRESENCE__", html)
        self.assertNotIn("__LAYOUT_URL__", html)

    def test_layout_events_push_when_a_watched_file_changes(self) -> None:
        project = self.orchestrator.create_project("家", home_layout(bed_origin_z_mm=200))
        stamp = layout_file_stamp(self.root, project.id)
        first = notice_for_change(self.root, project.id, None, stamp)
        assert first is not None
        self.assertEqual(first["version"], f"{project.latest.layout_sha256}:0")
        self.assertNotIn("rooms", first)
        self.assertIsNone(notice_for_change(self.root, project.id, stamp, stamp))

        acquire(self.root, project.id, holder="agent", label="助手")
        leased = layout_file_stamp(self.root, project.id)
        lease_only = notice_for_change(self.root, project.id, stamp, leased)
        assert lease_only is not None
        self.assertEqual(set(lease_only), {"lease"})
        self.assertEqual(lease_only["lease"]["holder"], "agent")
        self.assertNotIn("token", lease_only["lease"])

        self.store.save(project)
        rewritten = layout_file_stamp(self.root, project.id)
        again = notice_for_change(self.root, project.id, leased, rewritten)
        assert again is not None
        self.assertEqual(again["version"], first["version"])
        self.assertNotIn("rooms", again)

        async def one_event(request):
            response = await project_layout_events(project.id, request)
            self.assertEqual(response.media_type, "text/event-stream")
            self.assertEqual(response.headers["cache-control"], "no-store")
            iterator = response.body_iterator
            try:
                chunk = await iterator.__anext__()
            finally:
                await iterator.aclose()
            if isinstance(chunk, bytes):
                chunk = chunk.decode("utf-8")
            self.assertTrue(str(chunk).startswith("data: "))
            return json.loads(str(chunk).removeprefix("data: ").strip())

        server.app.state.preview_presence_at = None
        remote_payload = asyncio.run(one_event(remote_request()))
        self.assertEqual(remote_payload["version"], first["version"])
        self.assertNotIn("rooms", remote_payload)
        self.assertIsNone(server.app.state.preview_presence_at)

        before = time.monotonic()
        local_payload = asyncio.run(one_event(local_request()))
        self.assertEqual(local_payload["version"], first["version"])
        self.assertGreaterEqual(server.app.state.preview_presence_at, before)

        async def follow_file() -> None:
            seen: list[str] = []
            stream = iter_layout_events(project.id, local_request(), interval=0.05)

            async def collect() -> None:
                async for chunk in stream:
                    seen.append(str(chunk))

            task = asyncio.create_task(collect())
            await asyncio.sleep(0.18)
            self.assertEqual(len(seen), 1)
            self.store.save(project)
            await asyncio.sleep(0.35)
            self.assertGreaterEqual(len(seen), 2)
            payload = json.loads(seen[-1].removeprefix("data: ").strip())
            self.assertEqual(payload["version"], first["version"])
            self.assertNotIn("rooms", payload)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        asyncio.run(follow_file())

        with self.assertRaises(HTTPException) as missing:
            asyncio.run(project_layout_events("project_missing", local_request()))
        self.assertEqual(missing.exception.status_code, 404)
        with self.assertRaises(HTTPException) as escaped:
            asyncio.run(project_layout_events("../store", local_request()))
        self.assertEqual(escaped.exception.status_code, 422)

    def test_open_connection_pins_its_lease_once_and_releases_on_close(self) -> None:
        project = self.orchestrator.create_project("家", home_layout(bed_origin_z_mm=200))
        lease = acquire(self.root, project.id, holder="page", label="窗口")
        self.assertEqual(pin_page_lease(self.root, project.id, "not-a-lease"), ("", ""))
        token, until = hold_connection(self.root, project.id, lease.id)
        self.assertEqual(token, lease.token)
        pinned = read_lease(self.root, project.id)
        assert pinned is not None
        self.assertEqual(pinned.id, lease.id)
        self.assertEqual(pinned.expires_at, until)
        self.assertGreater(pinned.expires_in(), LEASE_TTL_SECONDS)
        self.assertEqual(hold_connection(self.root, project.id, lease.id), ("", ""))
        self.assertEqual(read_lease(self.root, project.id).expires_at, until)
        self.assertFalse(
            release_if_unchanged(
                self.root, project.id, token=token, expires_at="someone-else-wrote-this"
            )
        )
        self.assertIsNotNone(read_lease(self.root, project.id))
        self.assertTrue(same_lease_renewal({"lease": pinned.snapshot()}, (lease.id, "page")))
        self.assertFalse(
            same_lease_renewal(
                {"lease": pinned.snapshot(), "version": "x"},
                (lease.id, "page"),
            )
        )
        self.assertTrue(
            release_if_unchanged(self.root, project.id, token=token, expires_at=until)
        )
        self.assertIsNone(read_lease(self.root, project.id))

        fresh = acquire(self.root, project.id, holder="page", label="窗口")

        class Closed(FakeRequest):
            def __init__(self) -> None:
                super().__init__()
                self.query_params = {"lease_id": fresh.id}

            def is_disconnected(self) -> bool:
                return True

        async def close_immediately() -> None:
            async for _chunk in iter_layout_events(project.id, Closed(), interval=0.05):
                pass

        asyncio.run(close_immediately())
        self.assertIsNone(read_lease(self.root, project.id))
        self.assertEqual(server.app.state.preview_page_count, 0)

    def test_local_preview_is_rendered_editable(self) -> None:
        """本机来源 → 可编辑页：写入地址、租约、工作副本状态都在；只读那支不再出现。"""
        project = self.orchestrator.create_project("家", home_layout(bed_origin_z_mm=200))
        html = asyncio.run(
            server.project_preview(project.id, local_request())
        ).body.decode("utf-8")
        self.assertIn("const READ_ONLY=false", html)
        self.assertIn(f'"/api/project/{project.id}/layout/edit"', html)
        self.assertIn(f'"/api/project/{project.id}/layout/undo"', html)
        self.assertIn('<p class="mode-badge" id="mode-badge">可直接拖动', html)
        self.assertIn("function applyWorking(payload)", html)
        self.assertIn("第 ${payload.revision_number} 版", html)
        self.assertIn("layoutPersistence.write(op)", html)
        self.assertIn("const IDLE_YIELD_SECONDS=300", html)
        self.assertIn("function armIdle()", html)
        self.assertIn("?lease_id=", html)
        self.assertNotIn("heartbeatLease", html)
        self.assertNotIn("setInterval(", html)

    def test_preview_shows_room_axes_and_cursor_coordinates(self) -> None:
        """房间坐标要看得见：原点三轴（带总宽/总深/总高）+ 光标读数 + 右栏坐标行。"""
        project = self.orchestrator.create_project("家", home_layout(bed_origin_z_mm=200))
        html = asyncio.run(server.project_preview(project.id, local_request())).body.decode("utf-8")
        self.assertIn('id="coord"', html)
        self.assertIn("mountLayout", html)
        self.assertIn('data-field="coord"', html)
        self.assertIn("unprojectToGround(sx,sy)", html)
        scene_path = (
            WORKSPACE_ROOT
            / "domain"
            / "modules"
            / "web"
            / "furniture_web"
            / "static"
            / "layout_scene.js"
        )
        scene_js = scene_path.read_text(encoding="utf-8")
        # 场景引用同源的房间轴与标注；数值行为由 frame_check.mjs 检查。
        self.assertIn('./layout_annotations.js', scene_js)
        self.assertTrue(scene_path.with_name("layout_annotations.js").is_file())

    def test_preview_switches_rooms_with_chips_and_a_shareable_room_link(self) -> None:
        """房间切换是药丸不是下拉；切房间要写进地址栏 ?room=，链接能分享、能复现。"""
        project = self.orchestrator.create_project("家", home_layout(bed_origin_z_mm=200))
        html = asyncio.run(server.project_preview(project.id, local_request())).body.decode("utf-8")
        self.assertIn('<nav class="room-band" id="room-band" aria-label="房间切换" hidden></nav>', html)
        self.assertIn("function syncRoomBand()", html)
        self.assertIn('data-room-index="${index}"', html)
        self.assertIn("aria-pressed", html)
        # 还没审过的房间在药丸上带记号：改一间只审一间，要看得见还差哪间。
        self.assertIn('data-pending="true"', html)
        self.assertIn("· 待审", html)
        # 只有一间房时整条房间带藏掉，不留一个点了没反应的控件。
        self.assertIn("if(!rooms||rooms.length<2){band.hidden=true;return}", html)
        self.assertIn('deepLink.get("room")', html)
        self.assertIn('url.searchParams.set("room",entry.id)', html)
        self.assertIn("history.replaceState", html)
        self.assertNotIn("room-switch", html)

    def test_both_pages_carry_a_mode_badge(self) -> None:
        """每页自报身份：可编辑=可直接拖动，只读（非本机）=只读预览，草稿=草稿·不影响项目。"""
        project = self.orchestrator.create_project("家", home_layout(bed_origin_z_mm=200))
        editable = asyncio.run(
            server.project_preview(project.id, local_request())
        ).body.decode("utf-8")
        self.assertIn('<p class="mode-badge" id="mode-badge">可直接拖动', editable)
        self.assertNotIn("__MODE_BADGE__", editable)
        readonly = asyncio.run(
            server.project_preview(project.id, remote_request())
        ).body.decode("utf-8")
        self.assertIn(
            '<p class="mode-badge" id="mode-badge">只读预览 · 由对话更新</p>', readonly
        )

    def test_share_mode_swaps_the_badge_and_drops_the_exit_button(self) -> None:
        """`?mode=view` = 分享形态：牌子换成"只读分享"、页面里根本没有「退出」。

        「退出」能停掉本机的预览服务，不能给拿到链接的人用，所以分享形态是
        **不生成**这个按钮，而不是生成后藏起来。分享形态在本机也强制只读。
        """
        project = self.orchestrator.create_project("家", home_layout(bed_origin_z_mm=200))
        share = asyncio.run(
            server.project_preview(project.id, local_request(), mode="view")
        ).body.decode("utf-8")
        self.assertIn('<p class="mode-badge" id="mode-badge">只读分享 · 链接可转发</p>', share)
        self.assertNotIn('id="shutdown-preview"', share)
        self.assertIn('const SHARE_FORM=true', share)
        self.assertIn("const READ_ONLY=true", share)  # 本机 + ?mode=view 也是只读
        self.assertIn("只读分享：这一页只能看，位置由房主那边更新。", share)
        self._assert_body_class(share, "readonly share")
        # 不带参数、本机来源：可编辑页，退出按钮在。
        normal = asyncio.run(
            server.project_preview(project.id, local_request())
        ).body.decode("utf-8")
        self.assertIn('id="shutdown-preview"', normal)
        self.assertIn('const SHARE_FORM=false', normal)
        self.assertIn("const READ_ONLY=false", normal)
        self._assert_body_class(normal, "")

    def _assert_body_class(self, html: str, expected: str) -> None:
        self.assertIn(f'<body class="{expected}">', html)

    def test_share_link_is_a_plain_expression_not_a_permission(self) -> None:
        """分享链接只是地址栏表达：它没有任何办法绕过服务端的写权限。"""
        url = open_preview.preview_url("project_abc", mode="view")
        self.assertTrue(url.endswith("/api/project/project_abc/preview?mode=view"))
        self.assertEqual(
            open_preview.preview_url("project_abc"),
            "http://127.0.0.1:8000/api/project/project_abc/preview",
        )
        source = (SCRIPT_ROOT / "server.py").read_text(encoding="utf-8")
        # 只读与否由服务端按权限算；判据函数连 mode 都拿不到，所以它不可能参与授权。
        self.assertIn('read_only = mode == "view" or not may_edit(request)', source)
        self.assertIn("read_only=read_only", source)
        self.assertIn("def access_scope(request: Request) -> str:", source)
        self.assertIn("def may_edit(request: Request) -> bool:", source)

    def test_read_only_panel_arm_has_no_controls(self) -> None:
        """右栏是"一份模板两支"，只读那支不得含 input / button。

        注意：两支都在同一份 HTML 的 JS 源码里，所以只能断言分支内容，
        不能断言"整页源码里没有 class=\"num\""——那串在可编辑支里。
        """
        project = self.orchestrator.create_project("家", home_layout(bed_origin_z_mm=200))
        html = asyncio.run(
            server.project_preview(project.id, remote_request())
        ).body.decode("utf-8")
        self.assertIn("const READ_ONLY=true", html)
        readonly_gap = '<dt>${label}</dt><dd><span data-gap="${key}"></span> mm<span class="who" data-who="${key}"></span></dd>'
        self.assertIn(readonly_gap, html)
        self.assertNotIn("input", readonly_gap)
        self.assertNotIn("button", readonly_gap)
        # 朝向 / 离地 / 提示语也都是纯文字
        self.assertIn('<span data-field="rotation"></span>°<span class="who" data-front></span>', html)
        self.assertIn('<span data-field="height"></span> mm', html)
        self.assertIn("只读预览：位置由对话更新；要自己拖，用草稿页。", html)
        scene_js = (
            WORKSPACE_ROOT
            / "domain"
            / "modules"
            / "web"
            / "furniture_web"
            / "static"
            / "layout_scene.js"
        ).read_text(encoding="utf-8")
        handle_block = scene_js.split("if (!readOnly)", 1)[1]
        self.assertIn('kind: "rotate"', handle_block)
        self.assertIn('kind: "height"', handle_block)
        self.assertLess(scene_js.index("0x047857"), scene_js.index("if (!readOnly)"))
        self.assertNotIn("只读预览：位置由对话更新；要自己拖，用草稿页。", readonly_gap)

    def test_content_digest_has_one_implementation(self) -> None:
        """同一份内容只能有一个摘要：冻结哈希、分析血缘、交付校验必须同源。

        交付与工作流都使用无阶段依赖的公共实现，旧导入入口继续兼容。
        """
        from furniture_delivery_validation import validation as delivery_validation
        from furniture_contracts.digest import stable_digest as shared_digest
        from furniture_workflow import workflow_constants, workflow_digest
        from furniture_workflow.workflow_project import stable_digest

        payload = {"b": 1, "a": [2, 3], "文字": "值"}
        digests = {
            "shared": shared_digest(payload),
            "workflow_digest": workflow_digest.stable_digest(payload),
            "workflow_constants": workflow_constants._stable_digest(payload),
            "workflow_project": stable_digest(payload),
            "delivery_validation": delivery_validation._stable_digest(payload),
        }
        self.assertEqual(len(set(digests.values())), 1, digests)

    def test_revise_layout_changes_version_and_reread_position(self) -> None:
        project = self.orchestrator.create_project("家", home_layout(bed_origin_z_mm=200))
        before = asyncio.run(server.project_layout(project.id))
        self.orchestrator.revise_layout(project, home_layout(bed_origin_z_mm=800))
        after = asyncio.run(server.project_layout(project.id))
        self.assertEqual(after["revision_number"], 2)
        self.assertNotEqual(after["version"], before["version"])
        self.assertEqual(
            after["rooms"][0]["scene"]["items"][0]["placement"]["origin_z_mm"],
            800,
        )
        html = asyncio.run(server.project_preview(project.id, local_request())).body.decode("utf-8")
        self.assertIn('"origin_z_mm":800', html)
        self.assertNotIn('"origin_z_mm":200', html)

        self.orchestrator.confirm_stage(project, "layout_plan")
        confirmed = asyncio.run(server.project_layout(project.id))
        self.assertTrue(confirmed["layout_confirmed"])
        self.assertNotEqual(confirmed["version"], after["version"])
        self.assertEqual(
            confirmed["rooms"][0]["scene"]["items"][0]["placement"]["origin_z_mm"],
            800,
        )

    def test_project_list_shows_openable_and_unavailable_projects(self) -> None:
        ready = self.orchestrator.create_project("张家卧室", home_layout(bed_origin_z_mm=200))
        self.orchestrator.confirm_stage(ready, "layout_plan")
        pending = self.orchestrator.create_project("工作室", home_layout(bed_origin_z_mm=400))
        broken = self.root / "broken"
        broken.mkdir()
        (broken / "project.json").write_text("{", encoding="utf-8")
        mismatched = self.root / "mismatch"
        mismatched.mkdir()
        (mismatched / "project.json").write_text(
            json.dumps(
                {
                    "id": "other",
                    "name": "错位",
                    "created_at": "2020-01-01T00:00:00+00:00",
                    "revisions": [],
                }
            ),
            encoding="utf-8",
        )

        listed = self.store.list_projects()
        self.assertEqual([row["id"] for row in listed], [pending.id, ready.id])
        self.assertEqual(listed[0]["name"], "工作室")
        self.assertFalse(listed[0]["layout_confirmed"])
        self.assertEqual(listed[1]["name"], "张家卧室")
        self.assertTrue(listed[1]["layout_confirmed"])
        inspected = self.store.inspect_projects()
        self.assertEqual(
            [row["availability"] for row in inspected],
            ["ready", "ready", "unavailable", "unavailable"],
        )
        self.assertEqual(inspected[0]["room_count"], 2)
        self.assertEqual(inspected[0]["item_count"], 2)

        page = asyncio.run(server.project_index()).body.decode("utf-8")
        self.assertIn("已保存的工程", page)
        server_source = (SCRIPT_ROOT / "server.py").read_text(encoding="utf-8")
        self.assertNotIn("<h2 id=\"projects-heading\">已保存的工程</h2>", server_source)
        self.assertIn("furniture_web.project_list", server_source)
        self.assertIn("关掉最后一页后，预览服务会自己停", page)
        self.assertIn('new EventSource("/api/preview/presence/stream")', page)
        self.assertNotIn("setInterval(pulsePreview", page)
        self.assertIn('id="project-search"', page)
        self.assertIn("张家卧室", page)
        self.assertIn("工作室", page)
        self.assertIn("布局已确认", page)
        self.assertIn("布局待确认", page)
        self.assertIn(f"/api/project/{ready.id}/preview", page)
        self.assertIn("错位", page)
        self.assertIn("broken", page)
        self.assertNotIn("/api/project/mismatch/preview", page)
        self.assertNotIn("/api/project/broken/preview", page)

        payload = asyncio.run(server.project_index_json())
        self.assertEqual(
            [row["name"] for row in payload["projects"]],
            ["工作室", "张家卧室", "错位", "broken"],
        )

    def test_old_project_does_not_expire_but_unsupported_layout_cannot_open(self) -> None:
        old = self.orchestrator.create_project("旧工程", home_layout(bed_origin_z_mm=200))
        old.created_at = "2020-01-01T00:00:00+00:00"
        self.store.save(old)
        self.assertEqual(self.store.inspect_projects()[0]["availability"], "ready")

        file = self.store.project_dir(old.id) / "project.json"
        payload = json.loads(file.read_text(encoding="utf-8"))
        payload["revisions"][-1]["layout"]["schema_version"] = 999
        file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        row = self.store.inspect_projects()[0]
        self.assertEqual(row["availability"], "incompatible")
        self.assertIn("格式不兼容", asyncio.run(server.project_index()).body.decode("utf-8"))
        with self.assertRaises(HTTPException) as blocked:
            asyncio.run(server.project_preview(old.id, local_request()))
        self.assertEqual(blocked.exception.status_code, 422)

    def test_project_missing_layout_is_unavailable(self) -> None:
        project = self.orchestrator.create_project("缺布局的项目", home_layout(bed_origin_z_mm=200))
        file = self.store.project_dir(project.id) / "project.json"
        payload = json.loads(file.read_text(encoding="utf-8"))
        del payload["revisions"][-1]["layout"]
        file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "requires layout"):
            self.store.load(project.id)
        row = self.store.inspect_projects()[0]
        self.assertEqual(row["name"], "缺布局的项目")
        self.assertEqual(row["availability"], "unavailable")
        page = asyncio.run(server.project_index()).body.decode("utf-8")
        self.assertIn("缺布局的项目", page)
        self.assertIn('id="unavailable-projects"', page)
        self.assertNotIn(f"/api/project/{project.id}/preview", page)
        with self.assertRaises(HTTPException) as blocked:
            asyncio.run(server.project_preview(project.id, local_request()))
        self.assertEqual(blocked.exception.status_code, 422)

    def test_editable_preview_can_type_width_depth_height(self) -> None:
        project = self.orchestrator.create_project("家", home_layout(bed_origin_z_mm=200))
        html = asyncio.run(
            server.project_preview(project.id, local_request())
        ).body.decode("utf-8")
        self.assertIn('data-size="width"', html)
        self.assertIn('data-size="depth"', html)
        self.assertIn('data-size="height"', html)
        self.assertIn("沿墙铺满，宽度由墙算出", html)
        self.assertIn("这一版布局给板件用", html)
        self.assertIn('href="/projects"', html)
        self.assertIn("function setSize(", html)
        self.assertNotIn('fetch("/api/preview/presence"', html)

    def test_closed_preview_page_is_what_stops_the_server(self) -> None:
        grace = server.PRESENCE_GRACE_SECONDS
        self.assertFalse(server.preview_should_stop(None, 100))
        # 还没到宽限期：不算"页面都关了"
        self.assertFalse(server.preview_should_stop(90, 90 + grace - 0.1))
        # 过了宽限期：最后一页确实走了
        self.assertTrue(server.preview_should_stop(90, 90 + grace))
        # 还有页面连着：到点也不停
        self.assertFalse(server.preview_should_stop(90, 90 + grace, pages=1))
        # 宽限期要够人手开浏览器：起服务到页面发出第一次 presence 之间的余量
        self.assertGreaterEqual(grace, 10.0)
        with self.assertRaises(HTTPException) as remote:
            asyncio.run(server.preview_presence(remote_request()))
        self.assertEqual(remote.exception.status_code, 403)
        before = time.monotonic()
        body = asyncio.run(server.preview_presence(local_request()))
        self.assertEqual(body["status"], "ok")
        self.assertGreaterEqual(server.app.state.preview_presence_at, before)
        server.app.state.preview_page_count = 0

        async def one_open_comment():
            chunks = []
            async for chunk in server.iter_preview_presence(local_request()):
                chunks.append(chunk)
            return chunks

        self.assertEqual(asyncio.run(one_open_comment()), [": open\n\n"])
        self.assertEqual(server.app.state.preview_page_count, 0)

    def test_local_server_entry_enables_edit_and_opens_the_list(self) -> None:
        with mock.patch.dict(os.environ, {"FURNITURE_PREVIEW_BROWSER": "1"}):
            os.environ.pop(server.LAYOUT_EDIT_ENV, None)
            server.enable_local_layout_edit()
            self.assertEqual(os.environ.get(server.LAYOUT_EDIT_ENV), "1")
            with (
                mock.patch.object(server, "preview_server_is_up", return_value=True),
                mock.patch.object(server.webbrowser, "open", return_value=True) as opened,
            ):
                server.open_project_list_when_ready()
            opened.assert_called_once_with("http://127.0.0.1:8000/projects", new=2)
        with mock.patch.dict(os.environ, {"FURNITURE_PREVIEW_BROWSER": "0"}):
            with mock.patch.object(server.webbrowser, "open") as opened:
                server.open_project_list_when_ready()
            opened.assert_not_called()


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
            with open_preview._LOCAL_OPENER.open(
                f"http://127.0.0.1:{port}/health",
                timeout=2,
            ) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(b"ok", response.read())
    def test_disabled_browser_does_not_open_or_start_a_server(self) -> None:
        with mock.patch.dict(os.environ, {"FURNITURE_PREVIEW_BROWSER": "0"}):
            with mock.patch.object(open_preview.webbrowser, "open") as opener:
                with mock.patch.object(
                    open_preview.subprocess, "Popen"
                ) as popen:
                    result = open_preview.open_project_preview(
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
                open_preview, "preview_server_is_up", return_value=True
            ):
                with mock.patch.object(
                    open_preview.subprocess, "Popen"
                ) as popen:
                    with mock.patch.object(
                        open_preview.webbrowser, "open", return_value=True
                    ) as opener:
                        result = open_preview.open_project_preview(
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
                open_preview,
                "preview_server_is_up",
                side_effect=lambda: next(checks),
            ):
                with mock.patch.object(
                    open_preview, "_start_preview_process"
                ) as start:
                    with mock.patch.object(
                        open_preview.webbrowser, "open", return_value=True
                    ) as opener:
                        with mock.patch.object(open_preview.time, "sleep"):
                            result = open_preview.open_project_preview(
                                "project_abc",
                                workspace_root=WORKSPACE_ROOT,
                            )
        start.assert_called_once()
        command = start.call_args.args[0]
        self.assertTrue(str(command[1]).endswith("open_projects.py"))
        self.assertIn("--no-browser", command)
        opener.assert_called_once()
        self.assertTrue(result["opened"])

    def test_home_url(self) -> None:
        self.assertEqual(open_preview.home_url(), "http://127.0.0.1:8000/")

    def test_open_home_preview(self) -> None:
        with mock.patch.dict(os.environ, {"FURNITURE_PREVIEW_BROWSER": "1"}):
            with mock.patch.object(
                open_preview, "preview_server_is_up", return_value=True
            ):
                with mock.patch.object(
                    open_preview.webbrowser, "open", return_value=True
                ) as opener:
                    result = open_preview.open_home_preview(
                        workspace_root=WORKSPACE_ROOT,
                    )
        opener.assert_called_once_with("http://127.0.0.1:8000/", new=2)
        self.assertTrue(result["opened"])

    def test_windows_preview_spawn_is_created_by_wmi(self) -> None:
        """命令结束就杀掉子进程的作业留不住预览服务，所以 Windows 走 WMI。"""
        with mock.patch.object(open_preview.sys, "platform", "win32"):
            with mock.patch.object(open_preview.subprocess, "run") as run:
                run.return_value = mock.Mock(returncode=0, stderr="", stdout="")
                open_preview._start_preview_process(
                    [r"C:\venv\python.exe", r"C:\repo\open_projects.py"],
                    r"C:\repo",
                )
        run.assert_called_once()
        argv = run.call_args.args[0]
        self.assertEqual(argv[0], "powershell.exe")
        self.assertIn("Win32_Process", argv[-1])
        env = run.call_args.kwargs["env"]
        self.assertIn("open_projects.py", env["FURNITURE_PREVIEW_COMMAND"])
        self.assertEqual(env["FURNITURE_PREVIEW_CWD"], r"C:\repo")

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

    def test_room_page_drag_follows_the_item_and_sends_its_mode(self) -> None:
        """拖动换算按**家具脚下**的比例，而且摆放模式一律显式发。

        旧算法用"光标射线的地面交点"：抓在家具上半身时那条射线打到地面已在很远处，
        几个像素就能换出好几米（实测一次拖动把 2.4m 的柜子从北墙甩到 y=2777）。
        换算本身在 static/layout_drag.js 里由 drag_check.mjs 断言，这里盯的是页面用没用它、
        以及 mode 有没有显式发——不显式发，服务端会按它那边的旧模式解释这次 op。
        """
        script = (
            WORKSPACE_ROOT
            / "domain"
            / "modules"
            / "web"
            / "furniture_web"
            / "templates"
            / "room_page.js"
        ).read_text(encoding="utf-8")
        self.assertIn('from "/layout-view/layout_drag.js"', script)
        self.assertIn("groundDragDelta(", script)
        # 贴回墙边要认回"靠墙"，否则离开过墙面的件只能顶在墙上不动。
        self.assertIn("wallSnap(", script)
        self.assertIn('op.mode="wall"', script)
        self.assertIn('op.mode="free"', script)

    def test_room_page_shows_the_ledger_and_the_change_log(self) -> None:
        """页面上要看得见"哪几条是助手替你定的"，也要看得见"谁改的、改了什么"。"""
        page = (
            WORKSPACE_ROOT
            / "domain"
            / "modules"
            / "web"
            / "furniture_web"
            / "templates"
            / "room_page.html"
        ).read_text(encoding="utf-8")
        script = (
            WORKSPACE_ROOT
            / "domain"
            / "modules"
            / "web"
            / "furniture_web"
            / "templates"
            / "room_page.js"
        ).read_text(encoding="utf-8")
        self.assertIn('id="basis-badge"', page)
        self.assertIn('id="working-panel"', page)
        # `hidden` 必须真的能藏住：牌子自己设了 display，会盖掉浏览器默认的
        # `[hidden]{display:none}`——划过假设之后就会留一个空气泡。
        self.assertIn("[hidden]{display:none", page)
        self.assertIn("localTime(", script)
        self.assertIn("点开确认", script)
        self.assertIn("toggleWorkingPanel", script)
        self.assertIn("describeActor", script)
        # 时间按看页面这台机器的本地时间显示：日志里存的是 UTC，
        # 直接切字符串就会显示 UTC（"时间不对"就是这么来的）。
        self.assertEqual(script.count("localTime("), 3)  # 定义一次 + 牌子悬停 + 面板列表
        self.assertEqual(script.count('.replace("T"," ").slice(0,16)'), 1)  # 只留兜底那一处

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
        room_http = (
            WORKSPACE_ROOT
            / "domain"
            / "stages"
            / "layout-plan"
            / "scripts"
            / "furniture_layout"
            / "room_http.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(source.count("_LOCAL_HOSTS"), 2)  # 定义一次 + 判据里读一次
        # 数一遍"每个写端点都走同一道门"：端点加一个，这里就加一。
        # （板件属性保存合并了顺纹与铰链侧，核心端点仍是 13；
        # 本机大模型配置与项目 AI 对话另有 5 个端点，位于独立功能包。）
        chat_http = (WORKSPACE_ROOT / "domain/modules/ai/furniture_chat/http.py").read_text(encoding="utf-8")
        self.assertEqual(
            source.count("if not may_edit(request):")
            + room_http.count("if not may_edit(request):")
            + chat_http.count("if not may_edit(request):"),
            18,
        )
        self.assertNotIn("def access_scope", room_http)
        self.assertNotIn("request.client.host", chat_http)
        endpoints = source.split("def may_edit")[1]
        self.assertNotIn("request.client.host", endpoints)


class LayoutViewStaticTests(unittest.TestCase):
    def test_layout_view_serves_the_scene_and_the_layout_solver(self) -> None:
        from furniture_web.integration import layout_view

        scene, scene_stat = layout_view.lookup_path("layout_scene.js")
        solver, solver_stat = layout_view.lookup_path("layout_solver.js")
        drag, drag_stat = layout_view.lookup_path("layout_drag.js")
        _missing, missing_stat = layout_view.lookup_path("does-not-exist.js")
        self.assertIn("modules/web", scene.replace("\\", "/"))
        self.assertIsNotNone(scene_stat)
        self.assertIn("layout-plan", solver.replace("\\", "/"))
        self.assertIsNotNone(solver_stat)
        self.assertIn("layout-plan", drag.replace("\\", "/"))
        self.assertIsNotNone(drag_stat)
        self.assertIsNone(missing_stat)


if __name__ == "__main__":
    unittest.main()
