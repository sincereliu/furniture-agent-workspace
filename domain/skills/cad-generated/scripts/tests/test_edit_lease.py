"""编辑租约（P5）：同一时刻只有一个写者，且人永远抢得回来。

契约见 `references/runtime-contract.md`「编辑租约」段。四组：

1. **租约本身**：申请 / 续租 / 被别人持有 / TTL 过期 / 释放 / 强制收回。
2. **对写的约束**：别人持有时写被拒（423）；空闲或自己的 token 放行。
3. **人的授权**：`handover_to_agent()` = 人把活交给助手 → 显式转移 + 能被页面看见。
4. **看得见**：布局文档与工具面快照都带租约，页面据此显示「助手正在处理」。
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from fastapi import HTTPException

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

import server
from fake_request_support import lease_request, local_request, remote_request
from furniture_layout.project_layout import ProjectLayout
from furniture_workflow.agent_tools import FurnitureToolSession, project_snapshot
from furniture_workflow.project_preview import project_layout_document
from furniture_workflow.project_layout_edit import edit_project_layout
from furniture_workflow.workflow_lease import (
    HOLDER_AGENT,
    HOLDER_PAGE,
    LEASE_TTL_SECONDS,
    LeaseHeld,
    LeaseLost,
    acquire,
    check_write,
    handover_to_agent,
    read_lease,
    release,
    transfer,
)
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_store import JsonProjectStore


def layout_source(offset_mm: float = 200.0) -> dict:
    return {
        "rooms": [
            {
                "id": "bedroom",
                "name": "卧室",
                "width_mm": 4000,
                "depth_mm": 3600,
                "height_mm": 2800,
                "items": [
                    {
                        "id": "wardrobe",
                        "label": "衣柜",
                        "category": "wardrobe",
                        "furniture_category": "floor_cabinet",
                        "width": 1800,
                        "depth": 600,
                        "height": 2200,
                        "placement": {
                            "mode": "free",
                            "origin_x_mm": offset_mm,
                            "origin_y_mm": 200,
                            "rotation_z_deg": 0,
                        },
                    }
                ],
            }
        ]
    }


class LeaseMechanicsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        self.project_id = "project_demo"

    def test_acquire_then_renew_with_the_same_token(self) -> None:
        first = acquire(self.root, self.project_id, holder=HOLDER_PAGE, label="窗口 A")
        again = acquire(
            self.root,
            self.project_id,
            holder=HOLDER_PAGE,
            label="窗口 A",
            token=first.token,
        )
        self.assertEqual(again.token, first.token)
        self.assertGreater(again.expires_in(), 0)
        self.assertEqual(again.history[-1]["action"], "renew")

    def test_a_second_window_is_refused_while_the_first_holds_it(self) -> None:
        first = acquire(self.root, self.project_id, holder=HOLDER_PAGE, label="窗口 A")
        with self.assertRaises(LeaseHeld) as ctx:
            acquire(self.root, self.project_id, holder=HOLDER_PAGE, label="窗口 B")
        self.assertEqual(ctx.exception.lease.token, first.token)
        self.assertIn("窗口 A", str(ctx.exception))

    def test_lease_expires_without_a_heartbeat(self) -> None:
        """没人续租就掉线：关标签页、崩溃、断网都不用管。"""
        acquired = acquire(
            self.root, self.project_id, holder=HOLDER_PAGE, label="窗口 A"
        )
        later = time.time() + LEASE_TTL_SECONDS + 1
        self.assertIsNone(read_lease(self.root, self.project_id, now=later))
        # 空位可以被别人拿走，而且不必带旧 token。
        taken = acquire(
            self.root, self.project_id, holder=HOLDER_PAGE, label="窗口 B", now=later
        )
        self.assertNotEqual(taken.token, acquired.token)

    def test_release_frees_the_slot(self) -> None:
        acquired = acquire(self.root, self.project_id, holder=HOLDER_AGENT, label="助手")
        self.assertTrue(release(self.root, self.project_id, token=acquired.token))
        self.assertIsNone(read_lease(self.root, self.project_id))
        # 释放后别人立刻能拿。
        acquire(self.root, self.project_id, holder=HOLDER_PAGE, label="窗口 A")

    def test_release_with_a_foreign_token_is_refused(self) -> None:
        acquire(self.root, self.project_id, holder=HOLDER_AGENT, label="助手")
        with self.assertRaises(LeaseLost):
            release(self.root, self.project_id, token="lease_someone_else")

    def test_takeover_is_always_possible(self) -> None:
        """强制收回：人永远抢得回来，租约不是用来把主人关在门外的。"""
        held = acquire(self.root, self.project_id, holder=HOLDER_AGENT, label="助手")
        mine = transfer(
            self.root, self.project_id, to=HOLDER_PAGE, label="窗口 A", reason="takeover"
        )
        self.assertNotEqual(mine.token, held.token)
        self.assertEqual(read_lease(self.root, self.project_id).holder, HOLDER_PAGE)
        self.assertEqual(mine.history[-1]["action"], "transfer:takeover")

    def test_check_write_only_lets_the_holder_through(self) -> None:
        self.assertIsNone(check_write(self.root, self.project_id))  # 空闲
        held = acquire(self.root, self.project_id, holder=HOLDER_PAGE, label="窗口 A")
        self.assertIsNotNone(check_write(self.root, self.project_id, token=held.token))
        with self.assertRaises(LeaseHeld):
            check_write(self.root, self.project_id)  # 没带 token
        with self.assertRaises(LeaseHeld):
            check_write(self.root, self.project_id, token="lease_other")

    def test_handover_reports_whether_a_handover_happened(self) -> None:
        """助手接管时要说得出"这是我抢过来的"——人要知道页面被切成只读了。"""
        acquire(self.root, self.project_id, holder=HOLDER_PAGE, label="窗口 A")
        lease, took_over = handover_to_agent(self.root, self.project_id)
        self.assertTrue(took_over)
        self.assertEqual(lease.holder, HOLDER_AGENT)
        # 已经是助手的：再调只是续租，不重复报"刚接管"。
        again, took_over_again = handover_to_agent(self.root, self.project_id)
        self.assertFalse(took_over_again)
        self.assertEqual(again.token, lease.token)
        # 空闲时接管不算"从人手里抢"。
        release(self.root, self.project_id, token=lease.token)
        _fresh, took_over_when_free = handover_to_agent(self.root, self.project_id)
        self.assertFalse(took_over_when_free)


class LeaseHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        self.store = JsonProjectStore(self.root)
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT, project_store=self.store
        )
        self.project = self.orchestrator.create_project(
            "租约", ProjectLayout.from_source(layout_source())
        )
        self._store_patch = mock.patch.object(server, "STORE_ROOT", self.root)
        self._store_patch.start()
        self.addCleanup(self._store_patch.stop)

    def test_acquire_renew_and_conflict_status_codes(self) -> None:
        first = asyncio.run(
            server.acquire_edit_lease(
                self.project.id,
                server.EditLeaseRequest(holder="page", label="窗口 A"),
                local_request(),
            )
        )
        self.assertEqual(first["holder"], "page")
        self.assertTrue(first["token"])

        renewed = asyncio.run(
            server.acquire_edit_lease(
                self.project.id,
                server.EditLeaseRequest(
                    holder="page", label="窗口 A", token=first["token"]
                ),
                local_request(),
            )
        )
        self.assertEqual(renewed["token"], first["token"])

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                server.acquire_edit_lease(
                    self.project.id,
                    server.EditLeaseRequest(holder="page", label="窗口 B"),
                    local_request(),
                )
            )
        self.assertEqual(ctx.exception.status_code, 423)
        self.assertEqual(ctx.exception.detail["holder"], "page")
        self.assertIn("expires_in", ctx.exception.detail)

    def test_lease_endpoints_are_local_only(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                server.acquire_edit_lease(
                    self.project.id,
                    server.EditLeaseRequest(holder="page"),
                    remote_request(),
                )
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_lease_on_a_missing_project_is_404(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                server.acquire_edit_lease(
                    "project_absent",
                    server.EditLeaseRequest(holder="page"),
                    local_request(),
                )
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_takeover_endpoint_hands_it_back_to_the_page(self) -> None:
        handover_to_agent(self.root, self.project.id)
        mine = asyncio.run(
            server.takeover_edit_lease(
                self.project.id,
                server.EditLeaseRequest(holder="page", label="窗口 A"),
                local_request(),
            )
        )
        self.assertEqual(mine["holder"], "page")
        self.assertEqual(read_lease(self.root, self.project.id).holder, "page")

    def test_release_endpoint_uses_the_token_header(self) -> None:
        acquired = acquire(self.root, self.project.id, holder="page", label="窗口 A")
        result = asyncio.run(
            server.release_edit_lease(self.project.id, lease_request(acquired.token))
        )
        self.assertTrue(result["released"])
        self.assertIsNone(read_lease(self.root, self.project.id))


class LeaseGuardsTheWriteTests(unittest.TestCase):
    """租约真的挡住了写：这是它存在的唯一理由。"""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        self.store = JsonProjectStore(self.root)
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT, project_store=self.store
        )
        self.project = self.orchestrator.create_project(
            "租约写", ProjectLayout.from_source(layout_source())
        )
        self._store_patch = mock.patch.object(server, "STORE_ROOT", self.root)
        self._store_patch.start()
        self.addCleanup(self._store_patch.stop)
        self._switch = mock.patch.dict(
            "os.environ", {"FURNITURE_PROJECT_LAYOUT_EDIT": "1"}
        )
        self._switch.start()
        self.addCleanup(self._switch.stop)

    def _version(self) -> str:
        return asyncio.run(server.project_layout(self.project.id))["version"]

    def _edit(self, request, **overrides):
        payload = {
            "op": "move",
            "item_id": "wardrobe",
            "origin_x_mm": 600,
            "expected_version": self._version(),
        }
        payload.update(overrides)
        return asyncio.run(
            server.edit_project_layout_endpoint(
                self.project.id,
                server.ProjectLayoutEditRequest(**payload),
                request,
            )
        )

    def test_page_holding_the_lease_blocks_the_agent(self) -> None:
        """助手直接调门面（不走 HTTP）也得让路——这一层就是为此存在的。"""
        held = acquire(self.root, self.project.id, holder="page", label="窗口 A")
        with self.assertRaises(LeaseHeld):
            edit_project_layout(
                self.store.load(self.project.id),
                {"op": "move", "item_id": "wardrobe", "origin_x_mm": 600},
                expected_version=self._version(),
                workspace_root=WORKSPACE_ROOT,
                store_root=self.root,
            )
        # 页面拿着自己的 token 写，放行（工作副本原地改）。
        after = self._edit(lease_request(held.token))
        self.assertEqual(after["working"]["ops"], 1)

    def test_a_page_without_the_token_gets_423(self) -> None:
        """页面没带 token（或带着旧 token）→ 423，而不是静默写进去。"""
        acquire(self.root, self.project.id, holder="page", label="窗口 A")
        with self.assertRaises(HTTPException) as ctx:
            self._edit(local_request())
        self.assertEqual(ctx.exception.status_code, 423)
        self.assertEqual(ctx.exception.detail["holder"], "page")

    def test_agent_holding_the_lease_blocks_a_stale_page(self) -> None:
        handover_to_agent(self.root, self.project.id)
        with self.assertRaises(HTTPException) as ctx:
            self._edit(local_request())  # 页面没带 token
        self.assertEqual(ctx.exception.status_code, 423)
        self.assertEqual(ctx.exception.detail["holder"], "agent")

    def test_a_free_lease_does_not_block_anything(self) -> None:
        # 还没有下游产物 → 工作副本原地改，版号不变。
        after = self._edit(local_request())
        self.assertEqual(after["revision_number"], 1)
        self.assertTrue(after["working"]["open"])

    def test_after_takeover_the_page_can_write_again(self) -> None:
        handover_to_agent(self.root, self.project.id)
        mine = asyncio.run(
            server.takeover_edit_lease(
                self.project.id,
                server.EditLeaseRequest(holder="page", label="窗口 A"),
                local_request(),
            )
        )
        after = self._edit(lease_request(mine["token"]))
        self.assertEqual(after["working"]["ops"], 1)
        self.assertEqual(after["rooms"][0]["scene"]["items"][0]["placement"]["origin_x_mm"], 600)


class LeaseIsVisibleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        self.store = JsonProjectStore(self.root)
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT, project_store=self.store
        )
        self.project = self.orchestrator.create_project(
            "看得见", ProjectLayout.from_source(layout_source())
        )
        self._store_patch = mock.patch.object(server, "STORE_ROOT", self.root)
        self._store_patch.start()
        self.addCleanup(self._store_patch.stop)

    def test_layout_document_carries_the_lease_snapshot(self) -> None:
        """页面每秒轮询这个文档——"助手正在处理"不需要再多发一个请求。"""
        document = asyncio.run(server.project_layout(self.project.id))
        self.assertIsNone(document["lease"])
        handover_to_agent(self.root, self.project.id, label="助手")
        document = asyncio.run(server.project_layout(self.project.id))
        self.assertEqual(document["lease"]["holder"], "agent")
        self.assertGreater(document["lease"]["expires_in"], 0)
        # 对外快照不含 token：别人不需要你的凭据。
        self.assertNotIn("token", document["lease"])

    def test_snapshot_shows_the_lease_without_the_token(self) -> None:
        acquire(self.root, self.project.id, holder="page", label="窗口 A")
        snapshot = project_snapshot(self.project, store=self.store)
        self.assertEqual(snapshot["lease"]["holder"], "page")
        self.assertEqual(snapshot["lease"]["label"], "窗口 A")
        self.assertNotIn("token", snapshot["lease"])

    def test_document_without_store_root_still_works(self) -> None:
        document = project_layout_document(self.project)
        self.assertIsNone(document["lease"])

    def test_tool_calls_hand_over_and_say_so(self) -> None:
        """人把活交给助手 = 授权让出：工具面自己接管，并把这件事报出来。"""
        acquire(self.root, self.project.id, holder="page", label="窗口 A")
        session = FurnitureToolSession(
            FurnitureOrchestrator(
                workspace_root=WORKSPACE_ROOT, project_store=self.store
            )
        )
        result = session.call("furniture_get_project", {"project_id": self.project.id})
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["project"]["lease"]["holder"], "page")

        result = session.call(
            "furniture_confirm_stage", {"project_id": self.project.id}
        )
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["handover"]["taken_over"])
        self.assertIn("只读", result["handover"]["message"])
        self.assertEqual(read_lease(self.root, self.project.id).holder, HOLDER_AGENT)

    def test_read_only_tool_calls_do_not_hand_over(self) -> None:
        acquire(self.root, self.project.id, holder="page", label="窗口 A")
        session = FurnitureToolSession(
            FurnitureOrchestrator(
                workspace_root=WORKSPACE_ROOT, project_store=self.store
            )
        )
        result = session.call("furniture_get_project", {"project_id": self.project.id})
        self.assertIsNone(result.get("handover"))
        self.assertEqual(read_lease(self.root, self.project.id).holder, HOLDER_PAGE)


class LeaseFileTests(unittest.TestCase):
    def test_lease_payload_is_json_on_disk_next_to_the_project(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        acquired = acquire(root, "project_demo", holder="agent", label="助手")
        path = root / "project_demo" / "edit-lease.json"
        self.assertTrue(path.is_file())
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["token"], acquired.token)
        self.assertEqual(payload["holder"], "agent")
        self.assertTrue(payload["history"])


if __name__ == "__main__":
    unittest.main()
