"""决策台账：谁说的、我们翻译成什么、有没有被确认——以及工具面和页面看得见它。

这一层存在的理由：事实记录"结果"，`working_ops` 记录"改了什么"，两者都答不出
"这句话是谁说的"。所以这里盯四件事：只追加、不冒充谁、确认要指回被确认的那几条、
以及"谁改的"跟着改动一起落盘。
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

os.environ.setdefault("FURNITURE_PREVIEW_BROWSER", "0")

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_layout import room_page
from furniture_layout.open_preview import preview_page_data
from furniture_workflow import project_layout_edit as layout_edit
from furniture_workflow import workflow_decisions
from furniture_workflow.agent_tools import FurnitureToolSession
from furniture_workflow.workflow_lease import LeaseHeld, acquire, release, transfer
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_store import JsonProjectStore
from furniture_workflow.agent_tools import TOOL_CREATE_PROJECT, TOOL_RECORD_DECISION, TOOL_REVISE_LAYOUT
from furniture_workflow.agent_tool_schema import openai_tools

LAYOUT_PAGE = (
    WORKSPACE_ROOT
    / "domain"
    / "skills"
    / "layout-plan"
    / "scripts"
    / "furniture_layout"
)


def rooms() -> list[dict[str, object]]:
    return [
        {
            "id": "room_1",
            "name": "新房间",
            "width_mm": 3000,
            "depth_mm": 4000,
            "height_mm": 3500,
            "items": [
                {
                    "id": "cabinet_1",
                    "category": "cabinet",
                    "furniture_category": "floor_cabinet",
                    "width": 2400,
                    "depth": 600,
                    "height": 2700,
                    "placement": {
                        "mode": "wall",
                        "host_wall": "north",
                        "offset_mm": 300,
                    },
                }
            ],
        }
    ]


class DecisionLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = JsonProjectStore(self.temporary.name)
        self.session = FurnitureToolSession(
            FurnitureOrchestrator(
                workspace_root=WORKSPACE_ROOT,
                project_store=self.store,
            )
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _create(self, decisions: object = None) -> dict:
        arguments: dict[str, object] = {"name": "决策台账", "rooms": rooms()}
        if decisions is not None:
            arguments["decisions"] = decisions
        result = self.session.call(TOOL_CREATE_PROJECT, arguments)
        self.assertTrue(result["ok"], result.get("error"))
        return result

    def _revise(self, project_id: str, decisions: object) -> dict:
        return self.session.call(
            TOOL_REVISE_LAYOUT,
            {"project_id": project_id, "rooms": rooms(), "decisions": decisions},
        )

    def test_defaults_never_imply_the_customer_said_it(self) -> None:
        """缺省必须是"助手假设"：不写 speaker/status 就不许看起来像客户拍的板。"""
        result = self._create([{"utterance": "这面墙做满", "interpretation": "北墙通铺"}])
        entry = result["project"]["decisions"][0]
        self.assertEqual(entry["id"], "dec_1")
        self.assertEqual(entry["speaker"], "agent")
        self.assertEqual(entry["status"], "assumption")
        self.assertEqual(entry["revision_number"], 1)
        self.assertEqual(result["project"]["pending_decisions"], ["dec_1"])
        self.assertTrue(entry["at"])

    def test_only_the_customer_can_confirm(self) -> None:
        """助手不能自己点头——这是这套账存在的意义。"""
        result = self.session.call(
            TOOL_CREATE_PROJECT,
            {
                "name": "决策台账",
                "rooms": rooms(),
                "decisions": [
                    {
                        "utterance": "随便分几格",
                        "interpretation": "三格",
                        "status": "confirmed",
                    }
                ],
            },
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "INVALID_ARGUMENT")
        # 校验在动手之前：一个工程都不该留下。
        self.assertEqual(self.store.list_projects(), [])

    def test_confirmation_targets_the_assumption_it_settles(self) -> None:
        project_id = self._create(
            [{"utterance": "这面墙做满", "interpretation": "北墙通铺三格"}]
        )["project"]["id"]
        result = self._revise(
            project_id,
            [
                {
                    "utterance": "对，就这样",
                    "interpretation": "接受三格",
                    "speaker": "customer",
                    "status": "confirmed",
                    "targets": ["dec_1"],
                }
            ],
        )
        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual(result["project"]["pending_decisions"], [])
        self.assertEqual(len(result["project"]["decisions"]), 2)

    def test_customer_words_can_arrive_without_confirmation(self) -> None:
        """客户说了话，但我们的翻译还没被确认——两件事分开记，缺一不可。"""
        result = self._create(
            [
                {
                    "utterance": "能装就行",
                    "interpretation": "先按挂衣为主",
                    "speaker": "customer",
                }
            ]
        )
        entry = result["project"]["decisions"][0]
        self.assertEqual(entry["speaker"], "customer")
        self.assertEqual(entry["status"], "assumption")
        self.assertEqual(result["project"]["pending_decisions"], ["dec_1"])

    def test_relay_is_not_the_customer(self) -> None:
        result = self._create(
            [
                {
                    "utterance": "客户说柜子要做满墙",
                    "interpretation": "北墙通铺",
                    "speaker": "relay",
                }
            ]
        )
        self.assertEqual(result["project"]["decisions"][0]["speaker"], "relay")

    def test_unknown_field_and_bad_shapes_are_rejected(self) -> None:
        for decisions in (
            {"utterance": "一句话", "interpretation": "落点"},  # 不是列表
            [{"utterance": "一句话", "interpretation": "落点", "note": "别名"}],
            # 客户的话不能没有原话；助手自己的假设可以没有（见下一条测试）。
            [{"utterance": "", "interpretation": "落点", "speaker": "customer"}],
            [{"interpretation": "落点", "speaker": "relay"}],
            [{"utterance": "一句话"}],
            [{"utterance": "一句话", "interpretation": "落点", "speaker": "客户"}],
        ):
            result = self.session.call(
                TOOL_CREATE_PROJECT,
                {"name": "决策台账", "rooms": rooms(), "decisions": decisions},
            )
            self.assertFalse(result["ok"], decisions)
            self.assertEqual(result["error"]["code"], "INVALID_ARGUMENT")
        self.assertEqual(self.store.list_projects(), [])

    def test_agent_assumption_does_not_need_a_fake_quote(self) -> None:
        """助手替客户定的东西没有"原话"——不许为了凑字段编一句引语。"""
        result = self._create(
            [{"interpretation": "柜体靠北墙居中（客户没点哪面墙）"}]
        )
        entry = result["project"]["decisions"][0]
        self.assertEqual(entry["utterance"], "")
        self.assertEqual(entry["speaker"], "agent")
        self.assertEqual(result["project"]["pending_decisions"], ["dec_1"])

    def test_targets_must_exist_and_withdraw_must_name_them(self) -> None:
        project_id = self._create(
            [{"utterance": "先做三格", "interpretation": "三格"}]
        )["project"]["id"]
        missing = self._revise(
            project_id,
            [
                {
                    "utterance": "就这样",
                    "interpretation": "确认",
                    "speaker": "customer",
                    "status": "confirmed",
                    "targets": ["dec_9"],
                }
            ],
        )
        self.assertFalse(missing["ok"])
        self.assertEqual(missing["error"]["code"], "INVALID_ARGUMENT")
        empty_withdraw = self._revise(
            project_id,
            [
                {
                    "utterance": "算了",
                    "interpretation": "撤回",
                    "speaker": "customer",
                    "status": "withdrawn",
                }
            ],
        )
        self.assertFalse(empty_withdraw["ok"])
        self.assertEqual(empty_withdraw["error"]["code"], "INVALID_ARGUMENT")

    def test_withdrawn_assumption_stops_being_pending(self) -> None:
        project_id = self._create(
            [{"utterance": "先做三格", "interpretation": "三格"}]
        )["project"]["id"]
        result = self._revise(
            project_id,
            [
                {
                    "utterance": "算了，不要三格",
                    "interpretation": "撤回三格",
                    "speaker": "customer",
                    "status": "withdrawn",
                    "targets": ["dec_1"],
                }
            ],
        )
        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual(result["project"]["pending_decisions"], [])
        states = workflow_decisions.decision_states(result["project"]["decisions"])
        self.assertEqual(states["dec_1"], "withdrawn")

    def test_ledger_is_append_only_across_revisions(self) -> None:
        created = self._create(
            [{"utterance": "第一句", "interpretation": "第一条"}]
        )["project"]
        first = dict(created["decisions"][0])
        project_id = created["id"]
        revised = self._revise(
            project_id,
            [{"utterance": "第二句", "interpretation": "第二条"}],
        )
        self.assertTrue(revised["ok"], revised.get("error"))
        entries = revised["project"]["decisions"]
        self.assertEqual([entry["id"] for entry in entries], ["dec_1", "dec_2"])
        self.assertEqual(entries[0], first)  # 旧的一条一个字都没动
        self.assertEqual(entries[1]["revision_number"], 2)

    def test_ledger_survives_a_reload(self) -> None:
        project_id = self._create(
            [{"utterance": "这面墙做满", "interpretation": "北墙通铺"}]
        )["project"]["id"]
        reloaded = self.store.load(project_id)
        self.assertEqual(len(reloaded.decisions), 1)
        self.assertEqual(reloaded.decisions[0]["utterance"], "这面墙做满")

    def test_page_payload_carries_pending_assumptions(self) -> None:
        project_id = self._create(
            [{"utterance": "这面墙做满", "interpretation": "北墙通铺三格"}]
        )["project"]["id"]
        project = self.store.load(project_id)
        document = preview_page_data(project, store_root=self.store.root)
        self.assertEqual(document["decisions"]["total"], 1)
        pending = document["decisions"]["pending"]
        self.assertEqual(
            [(item["utterance"], item["interpretation"]) for item in pending],
            [("这面墙做满", "北墙通铺三格")],
        )
        # 页面得有一块牌子挂它，并且真的读 payload.decisions.pending。
        page = (LAYOUT_PAGE / "templates" / "room_page.html").read_text(encoding="utf-8")
        script = (LAYOUT_PAGE / "templates" / "room_page.js").read_text(encoding="utf-8")
        self.assertIn('id="basis-badge"', page)
        self.assertIn("function applyDecisions(payload)", script)
        self.assertIn("payload.decisions.pending", script)
        self.assertIn("applyDecisions(payload)", script)
        self.assertEqual(document["working"]["ops"], 0)

    def test_rendered_page_carries_the_assumption_badge(self) -> None:
        """整页组装也要带上牌子——JSON 字段对了、模板没挂上，等于没做。"""
        project_id = self._create(
            [{"utterance": "这面墙做满", "interpretation": "北墙通铺三格"}]
        )["project"]["id"]
        project = self.store.load(project_id)
        document = preview_page_data(project, store_root=self.store.root)
        html = room_page.render_project_page(project_id, document, read_only=False)
        self.assertIn('id="basis-badge"', html)
        self.assertIn("function applyDecisions(payload)", html)
        self.assertIn("助手假设 ", html)
        self.assertIn("待确认", html)

    def test_other_tools_do_not_accept_decisions(self) -> None:
        project_id = self._create()["project"]["id"]
        result = self.session.call(
            "furniture_get_project",
            {"project_id": project_id, "decisions": []},
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "UNKNOWN_ARGUMENT")

    def test_schema_offers_decisions_only_on_layout_writes(self) -> None:
        by_name = {
            tool["function"]["name"]: tool["function"]["parameters"]["properties"]
            for tool in openai_tools()
        }
        self.assertIn("decisions", by_name[TOOL_CREATE_PROJECT])
        self.assertIn("decisions", by_name[TOOL_REVISE_LAYOUT])
        self.assertNotIn("decisions", by_name["furniture_run_next"])
        self.assertNotIn("decisions", by_name["furniture_get_project"])
        self.assertNotIn("decisions", by_name["furniture_confirm_stage"])


class WorkingOpActorTests(unittest.TestCase):
    """改动日志要跟着"谁改的"一起落盘——不然三天后没人知道是谁拖的。"""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = JsonProjectStore(self.temporary.name)
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT,
            project_store=self.store,
        )
        self.session = FurnitureToolSession(self.orchestrator)
        self._switch = unittest.mock.patch.dict(
            os.environ, {layout_edit.LAYOUT_EDIT_ENV: "1"}
        )
        self._switch.start()
        self.addCleanup(self._switch.stop)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _edit(self, project_id: str, *, token: str | None, offset: int) -> dict:
        project = self.store.load(project_id)
        version = preview_page_data(project, store_root=self.store.root)["version"]
        return layout_edit.edit_project_layout(
            project,
            {"op": "move", "item_id": "cabinet_1", "offset_mm": offset},
            expected_version=version,
            workspace_root=WORKSPACE_ROOT,
            store_root=self.store.root,
            lease_token=token,
        )

    def test_page_edit_records_the_lease_holder(self) -> None:
        project_id = self.session.call(
            TOOL_CREATE_PROJECT, {"name": "谁改的", "rooms": rooms()}
        )["project"]["id"]
        lease = acquire(self.store.root, project_id, holder="page", label="窗口 a1b2")
        self._edit(project_id, token=lease.token, offset=400)
        entry = self.store.load(project_id).latest.working_ops[-1]
        self.assertEqual(
            entry["actor"],
            {"holder": "page", "label": "窗口 a1b2", "lease_id": lease.id},
        )

    def test_edit_without_a_lease_says_unknown_instead_of_guessing(self) -> None:
        project_id = self.session.call(
            TOOL_CREATE_PROJECT, {"name": "谁改的", "rooms": rooms()}
        )["project"]["id"]
        lease = acquire(self.store.root, project_id, holder="page", label="窗口 a1b2")
        release(self.store.root, project_id, token=lease.token)
        self._edit(project_id, token=None, offset=500)
        entry = self.store.load(project_id).latest.working_ops[-1]
        self.assertEqual(entry["actor"]["holder"], "unknown")
        self.assertEqual(entry["actor"]["label"], "")


class AssistantRecordDecisionTests(unittest.TestCase):
    """助手侧的入口：客户后来说了一句话，但还没到改布局的时候。"""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = JsonProjectStore(self.temporary.name)
        self.session = FurnitureToolSession(
            FurnitureOrchestrator(
                workspace_root=WORKSPACE_ROOT,
                project_store=self.store,
            )
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _create(self) -> dict:
        result = self.session.call(TOOL_CREATE_PROJECT, {"name": "记一句话", "rooms": rooms()})
        self.assertTrue(result["ok"], result.get("error"))
        return result["project"]

    def test_recording_a_line_does_not_touch_layout_or_stage(self) -> None:
        created = self._create()
        project_id = created["id"]
        result = self.session.call(
            TOOL_RECORD_DECISION,
            {
                "project_id": project_id,
                "decisions": [
                    {"utterance": "抽屉不要了", "interpretation": "去掉抽屉", "speaker": "customer"}
                ],
            },
        )
        self.assertTrue(result["ok"], result.get("error"))
        snapshot = result["project"]
        # 只记说法：不推进流程、不改版、不改布局。
        self.assertFalse(snapshot["progressed"] if "progressed" in snapshot else False)
        self.assertEqual(result["progressed"], False)
        self.assertEqual(snapshot["revision_number"], created["revision_number"])
        self.assertEqual(snapshot["layout_sha256"], created["layout_sha256"])
        self.assertEqual(snapshot["current_stage"], created["current_stage"])
        self.assertEqual(result["progressed"], False)
        entry = snapshot["decisions"][0]
        self.assertEqual(entry["speaker"], "customer")
        self.assertEqual(entry["status"], "assumption")
        self.assertEqual(entry["source"], "tool")
        # 谁记的这条：写动作前工具面接管了租约，所以是助手。
        self.assertEqual(entry["actor"]["holder"], "agent")
        self.assertIn(TOOL_RECORD_DECISION, snapshot["allowed_tools"])

    def test_decisions_are_required_and_unknown_keys_are_rejected(self) -> None:
        project_id = self._create()["id"]
        for payload in (
            {"project_id": project_id},
            {"project_id": project_id, "decisions": []},
            {"project_id": project_id, "decisions": [{"interpretation": "x"}], "note": "别名"},
        ):
            result = self.session.call(TOOL_RECORD_DECISION, payload)
            self.assertFalse(result["ok"], payload)
            self.assertEqual(result["error"]["code"], "UNKNOWN_ARGUMENT" if "note" in payload else "INVALID_ARGUMENT")


class PageDecisionTests(unittest.TestCase):
    """客户自己在页面上按「确认 / 划掉」：只追加，被表态的那条一个字不动。"""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = JsonProjectStore(self.temporary.name)
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT,
            project_store=self.store,
        )
        self.session = FurnitureToolSession(self.orchestrator)
        self._switch = unittest.mock.patch.dict(
            os.environ, {layout_edit.LAYOUT_EDIT_ENV: "1"}
        )
        self._switch.start()
        self.addCleanup(self._switch.stop)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _project(self) -> tuple[str, str]:
        """建一个带一条待确认假设的工程，返回 (project_id, lease_token)。"""
        project_id = self.session.call(
            TOOL_CREATE_PROJECT,
            {
                "name": "页面表态",
                "rooms": rooms(),
                "decisions": [{"interpretation": "柜体靠北墙居中（助手选的）"}],
            },
        )["project"]["id"]
        lease = acquire(self.store.root, project_id, holder="page", label="窗口 a1b2")
        return project_id, lease.token

    def _decide(self, project_id: str, token: str, action: str, target: str = "dec_1") -> dict:
        project = self.store.load(project_id)
        version = preview_page_data(project, store_root=self.store.root)["version"]
        return layout_edit.edit_project_decisions(
            project,
            action=action,
            target=target,
            expected_version=version,
            store_root=self.store.root,
            lease_token=token,
        )

    def test_confirm_settles_the_assumption_and_appends(self) -> None:
        project_id, token = self._project()
        document = self._decide(project_id, token, "confirm")
        self.assertEqual(pending_ids(document), [])
        self.assertEqual(document["decided"][0]["status"], "confirmed")
        # 页面按的按钮没有原话，措辞由服务端写死；谁按的从租约读。
        entry = self.store.load(project_id).decisions[-1]
        self.assertEqual(entry["source"], "page")
        self.assertEqual(entry["speaker"], "customer")
        self.assertEqual(entry["utterance"], "")
        self.assertEqual(entry["targets"], ["dec_1"])
        self.assertEqual(entry["actor"]["holder"], "page")
        self.assertEqual(entry["actor"]["label"], "窗口 a1b2")
        # 被确认的那条一个字没动。
        self.assertEqual(self.store.load(project_id).decisions[0]["status"], "assumption")

    def test_withdraw_also_settles_it(self) -> None:
        project_id, token = self._project()
        document = self._decide(project_id, token, "withdraw")
        self.assertEqual(pending_ids(document), [])
        states = workflow_decisions.decision_states(self.store.load(project_id).decisions)
        self.assertEqual(states["dec_1"], "withdrawn")

    def test_a_settled_assumption_cannot_be_decided_again(self) -> None:
        project_id, token = self._project()
        self._decide(project_id, token, "confirm")
        with self.assertRaises(ValueError) as ctx:
            self._decide(project_id, token, "withdraw")
        self.assertIn("already settled", str(ctx.exception))

    def test_unknown_target_and_stale_version_are_rejected(self) -> None:
        project_id, token = self._project()
        with self.assertRaises(ValueError):
            self._decide(project_id, token, "confirm", target="dec_9")
        project = self.store.load(project_id)
        with self.assertRaises(layout_edit.VersionConflict):
            layout_edit.edit_project_decisions(
                project,
                action="confirm",
                target="dec_1",
                expected_version="not-the-current-version",
                store_root=self.store.root,
                lease_token=token,
            )
        with self.assertRaises(ValueError):
            self._decide(project_id, token, "delete")

    def test_the_switch_and_the_lease_still_gate_it(self) -> None:
        project_id, token = self._project()
        with unittest.mock.patch.dict(os.environ, {layout_edit.LAYOUT_EDIT_ENV: "0"}):
            with self.assertRaises(layout_edit.LayoutEditDisabled):
                self._decide(project_id, token, "confirm")
        # 人（或另一个写者）把编辑权收回去之后，页面手上的 token 就作废了。
        transfer(self.store.root, project_id, to="agent", label="助手", reason="takeover")
        project = self.store.load(project_id)
        version = preview_page_data(project, store_root=self.store.root)["version"]
        with self.assertRaises(LeaseHeld):
            layout_edit.edit_project_decisions(
                project,
                action="confirm",
                target="dec_1",
                expected_version=version,
                store_root=self.store.root,
                lease_token=token,
            )

    def test_page_payload_carries_recent_changes_with_who_did_them(self) -> None:
        project_id, token = self._project()
        self._decide(project_id, token, "confirm")
        project = self.store.load(project_id)
        document = preview_page_data(project, store_root=self.store.root)
        self.assertIn("recent", document["working"])
        # 台账表态不是布局改动，所以 recent 只反映拖动这类 op；字段本身必须在。
        self.assertEqual(document["decisions"]["total"], 2)
        page = (LAYOUT_PAGE / "templates" / "room_page.html").read_text(encoding="utf-8")
        script = (LAYOUT_PAGE / "templates" / "room_page.js").read_text(encoding="utf-8")
        self.assertIn('id="basis-panel"', page)
        self.assertIn('data-basis="confirm"', script)
        self.assertIn('data-basis="withdraw"', script)
        self.assertIn("decideBasis(", script)


def pending_ids(document: dict) -> list[str]:
    """页面文档里的 pending 是**给人看的条目**，这里只要 id。"""
    return [entry["id"] for entry in document["decisions"]["pending"]]


class StaleAssumptionTests(unittest.TestCase):
    """客户的动作动了某一处 → 针对那一处还**待确认**的假设当场作废。

    实测撞到过：假设写"沿墙 300 居中"，柜子早被拖到 340，台账还挂着"待确认"——两边打架。
    规则要保守：只动待确认的、只动引用精确到 `对象.字段` 的、只动那个字段**真的变了**的。
    """

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = JsonProjectStore(self.temporary.name)
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT,
            project_store=self.store,
        )
        self.session = FurnitureToolSession(self.orchestrator)
        self._switch = unittest.mock.patch.dict(
            os.environ, {layout_edit.LAYOUT_EDIT_ENV: "1"}
        )
        self._switch.start()
        self.addCleanup(self._switch.stop)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _project(self, decisions: list[dict]) -> tuple[str, str]:
        project_id = self.session.call(
            TOOL_CREATE_PROJECT,
            {"name": "被动作动摇", "rooms": rooms(), "decisions": decisions},
        )["project"]["id"]
        lease = acquire(self.store.root, project_id, holder="page", label="窗口 a1b2")
        return project_id, lease.token

    def _drag(self, project_id: str, token: str, offset: float) -> dict:
        project = self.store.load(project_id)
        version = preview_page_data(project, store_root=self.store.root)["version"]
        return layout_edit.edit_project_layout(
            project,
            {"op": "move", "item_id": "cabinet_1", "offset_mm": offset},
            expected_version=version,
            workspace_root=WORKSPACE_ROOT,
            store_root=self.store.root,
            lease_token=token,
        )

    def test_dragging_the_same_field_retires_the_assumption(self) -> None:
        project_id, token = self._project(
            [
                {
                    "interpretation": "柜体沿北墙 300 居中（助手选的）",
                    "applies_to": ["cabinet_1.offset_mm"],
                }
            ]
        )
        document = self._drag(project_id, token, 448)
        self.assertEqual(pending_ids(document), [])
        self.assertEqual(len(document["withdrawn_decisions"]), 1)
        entry = self.store.load(project_id).decisions[-1]
        self.assertEqual(entry["status"], "withdrawn")
        self.assertEqual(entry["targets"], ["dec_1"])
        self.assertEqual(entry["source"], "page")
        self.assertEqual(entry["speaker"], "customer")
        self.assertEqual(entry["actor"]["label"], "窗口 a1b2")
        self.assertIn("cabinet_1.offset_mm 从 300 改成 448", entry["interpretation"])
        self.assertIn("自动作废", entry["interpretation"])

    def test_a_different_field_does_not_retire_it(self) -> None:
        project_id, token = self._project(
            [{"interpretation": "宽度按 2400", "applies_to": ["cabinet_1.width"]}]
        )
        document = self._drag(project_id, token, 500)
        self.assertEqual(pending_ids(document), ["dec_1"])
        self.assertNotIn("withdrawn_decisions", document)

    def test_object_level_reference_is_left_alone(self) -> None:
        """只写到对象级的假设太模糊——宁可不动作，也不误作废。"""
        project_id, token = self._project(
            [{"interpretation": "柜体靠北墙（助手选的）", "applies_to": ["cabinet_1"]}]
        )
        document = self._drag(project_id, token, 500)
        self.assertEqual(pending_ids(document), ["dec_1"])

    def test_confirmed_constraints_are_never_auto_withdrawn(self) -> None:
        """客户点过头的约束，代码不许替他改——那是"改主意"，要显式来。"""
        project_id, token = self._project(
            [
                {
                    "utterance": "沿墙摆 300",
                    "interpretation": "沿北墙 300",
                    "speaker": "customer",
                    "status": "confirmed",
                    "applies_to": ["cabinet_1.offset_mm"],
                }
            ]
        )
        document = self._drag(project_id, token, 448)
        states = workflow_decisions.decision_states(self.store.load(project_id).decisions)
        self.assertEqual(states["dec_1"], "confirmed")
        self.assertNotIn("withdrawn_decisions", document)

    def test_dragging_back_to_the_same_value_changes_nothing(self) -> None:
        project_id, token = self._project(
            [{"interpretation": "沿墙 300", "applies_to": ["cabinet_1.offset_mm"]}]
        )
        document = self._drag(project_id, token, 300)  # 和建项目时一样
        self.assertEqual(pending_ids(document), ["dec_1"])

    def test_assistant_revision_also_retires_stale_assumptions(self) -> None:
        """助手改布局也一样：动过同一处，假设就不能再挂着。"""
        project_id = self.session.call(
            TOOL_CREATE_PROJECT,
            {
                "name": "助手改",
                "rooms": rooms(),
                "decisions": [
                    {
                        "interpretation": "沿北墙 300 居中（助手选的）",
                        "applies_to": ["cabinet_1.offset_mm"],
                    }
                ],
            },
        )["project"]["id"]
        moved = rooms()
        moved[0]["items"][0]["placement"]["offset_mm"] = 500
        result = self.session.call(
            TOOL_REVISE_LAYOUT, {"project_id": project_id, "rooms": moved}
        )
        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual(result["project"]["pending_decisions"], [])
        entry = self.store.load(project_id).decisions[-1]
        self.assertEqual(entry["speaker"], "agent")
        self.assertEqual(entry["source"], "tool")
        self.assertIn("助手直接改了", entry["interpretation"])


class StaleRuleUnitTests(unittest.TestCase):
    """规则本身（纯函数）——不经过 HTTP 与租约也能钉住。"""

    def test_only_pending_precise_and_really_changed(self) -> None:
        entries = [
            {"id": "dec_1", "status": "assumption", "applies_to": ["cabinet_1.offset_mm"]},
            {"id": "dec_2", "status": "assumption", "applies_to": ["cabinet_1"]},
            {"id": "dec_3", "status": "confirmed", "applies_to": ["cabinet_1.offset_mm"]},
            {"id": "dec_4", "status": "assumption", "applies_to": ["cabinet_1.width"]},
        ]
        changes = {"cabinet_1": {"offset_mm": (300.0, 448.0)}}
        self.assertEqual(workflow_decisions.stale_pending_ids(entries, changes), ["dec_1"])
        self.assertEqual(
            workflow_decisions.parse_ref("cabinet_1.offset_mm"), ("cabinet_1", "offset_mm")
        )
        self.assertEqual(workflow_decisions.parse_ref("cabinet_1"), ("cabinet_1", None))

    def test_changed_fields_ignore_fill_and_equal_values(self) -> None:
        before = {"placement": {"mode": "wall", "fill": False, "offset_mm": 300.0}, "width": 2400.0}
        after = dict(before, placement={"mode": "wall", "fill": True, "offset_mm": 300.0})
        self.assertEqual(workflow_decisions.changed_item_fields(before, after), {})
        after = dict(
            before,
            placement={"mode": "wall", "fill": False, "offset_mm": 448.0},
            width=2300.0,
        )
        self.assertEqual(
            workflow_decisions.changed_item_fields(before, after),
            {"offset_mm": (300.0, 448.0), "width": (2400.0, 2300.0)},
        )

    def test_wording_lists_changes_and_summarises_the_rest(self) -> None:
        entries = [{"id": "dec_1", "status": "assumption", "applies_to": ["cabinet_1.offset_mm"]}]
        changes = {
            "cabinet_1": {
                "offset_mm": (300.0, 448.0),
                "width": (2400.0, 2300.0),
                "depth": (600.0, 620.0),
                "height": (2700.0, 2650.0),
            }
        }
        entry = workflow_decisions.auto_withdrawn_entries(entries, changes)[0]
        self.assertIn("cabinet_1.offset_mm 从 300 改成 448", entry["interpretation"])
        self.assertIn("等 4 处", entry["interpretation"])


if __name__ == "__main__":
    unittest.main()
