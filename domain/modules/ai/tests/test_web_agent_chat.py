from __future__ import annotations

import shutil
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_ROOT = WORKSPACE_ROOT / "domain/stages/cad-generated/scripts"
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

import server
from furniture_layout.project_layout import ProjectLayout
from furniture_layout.room_page import render_project_page
from furniture_layout.open_preview import preview_page_data
from furniture_chat import conversation as web_agent_chat
from furniture_chat.page import page_extension
import furniture_ai as ai
from furniture_ai import codex, settings, cli_protocol
from furniture_chat.conversation import (
    WebChatError,
    clear_chat_history,
    get_project_chat_state,
    send_project_chat_message,
)
from furniture_ai import load_llm_config, public_llm_config, save_llm_config
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_store import JsonProjectStore


def _sample_layout() -> ProjectLayout:
    return ProjectLayout.from_source(
        {
            "rooms": [
                {
                    "id": "living",
                    "name": "客厅",
                    "width_mm": 4200,
                    "depth_mm": 3600,
                    "height_mm": 2800,
                    "items": [
                        {
                            "id": "tv_cabinet",
                            "label": "电视柜",
                            "category": "tv_cabinet",
                            "furniture_category": "floor_cabinet",
                            "width": 1800,
                            "depth": 450,
                            "height": 500,
                            "placement": {
                                "mode": "wall",
                                "host_wall": "north",
                            },
                        }
                    ],
                }
            ]
        }
    )


class WebAgentChatTests(unittest.TestCase):
    def setUp(self) -> None:
        prewarm_patch = mock.patch.object(codex._CLIENT, "prewarm_async")
        self.prewarm = prewarm_patch.start()
        self.addCleanup(prewarm_patch.stop)
        auth_patch = mock.patch.object(codex._CLIENT, "authentication_state", return_value={"authenticated": True, "status": "authenticated", "isolated": True})
        self.auth_state = auth_patch.start()
        self.addCleanup(auth_patch.stop)
        self.root = WORKSPACE_ROOT / "temp" / "test-web-agent-chat"
        if self.root.exists():
            shutil.rmtree(self.root)
        self.store = JsonProjectStore(self.root)
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT,
            project_store=self.store,
        )

    def tearDown(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)



    def test_chat_turn_executes_tool_calls_and_persists_history(self) -> None:
        project = self.orchestrator.create_project("客厅", _sample_layout())
        save_llm_config(
            self.root,
            provider="codex_cli",
            base_url="",
            model="gpt-6.1-sol",
        )

        rounds = iter(
            [
                {
                    "thinking": "用户确认客厅布局满意，当前处于 layout_plan 待确认状态，应调用 furniture_confirm_stage。",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "furniture_confirm_stage",
                                "arguments": '{"stage": "layout_plan"}',
                            },
                        }
                    ],
                },
                {
                    "thinking": "layout_plan 已确认完成，现在向用户反馈可以进入板件规划。",
                    "content": "已为您确认当前客厅布局，可以继续生成板件。",
                    "tool_calls": [],
                },
            ]
        )

        result = send_project_chat_message(
            project.id,
            "布局满意，帮我确认布局",
            workspace_root=WORKSPACE_ROOT,
            store_root=self.root,
            llm_caller=lambda cfg, msgs, tools: next(rounds),
        )
        self.assertTrue(result["ok"])
        self.assertTrue(result["progressed"])
        self.assertEqual(len(result["thinking_steps"]), 2)
        self.assertIn("furniture_confirm_stage", result["thinking"])
        self.assertEqual(len(result["tool_trace"]), 1)
        self.assertEqual(result["tool_trace"][0]["tool"], "furniture_confirm_stage")
        self.assertEqual(result["tool_trace"][0]["arguments"], {"stage": "layout_plan"})
        self.assertTrue(result["tool_trace"][0]["ok"])
        self.assertIn("layout_plan", result["project"]["approved_stages"])

        state = get_project_chat_state(
            project.id,
            workspace_root=WORKSPACE_ROOT,
            store_root=self.root,
        )
        self.assertEqual(len(state["messages"]), 2)
        self.assertEqual(state["messages"][0]["role"], "user")
        self.assertEqual(state["messages"][1]["role"], "assistant")
        self.assertIn("已为您确认", state["messages"][1]["content"])
        self.assertEqual(len(state["messages"][1]["thinking_steps"]), 2)
        self.assertIn("furniture_confirm_stage", state["messages"][1]["thinking"])

        normalized = cli_protocol._normalize_cli_step_output(
            {
                "thinking": "先核对尺寸",
                "reply": "<think>补充思考</think>这是最终答复",
                "tool_calls": [],
            }
        )
        self.assertEqual(normalized["content"], "这是最终答复")
        self.assertIn("先核对尺寸", normalized["thinking"])
        self.assertIn("补充思考", normalized["thinking"])

        clear_chat_history(self.root, project.id)
        after_clear = get_project_chat_state(
            project.id,
            workspace_root=WORKSPACE_ROOT,
            store_root=self.root,
        )
        self.assertEqual(after_clear["messages"], [])

    def test_chat_requires_configured_llm(self) -> None:
        project = self.orchestrator.create_project("客厅", _sample_layout())
        with (
            mock.patch.dict("os.environ", {}, clear=True),
            mock.patch.object(settings, "_discover_codex_binary", return_value=None),
            mock.patch.object(settings, "_discover_agy_binary", return_value=None),
        ):
            with self.assertRaises(WebChatError) as ctx:
                send_project_chat_message(
                    project.id,
                    "你好",
                    workspace_root=WORKSPACE_ROOT,
                    store_root=self.root,
                )
            self.assertEqual(ctx.exception.code, "LLM_NOT_CONFIGURED")

    def test_chat_rejects_other_projects_and_refreshes_stage_context(self) -> None:
        project = self.orchestrator.create_project("当前", _sample_layout())
        other = self.orchestrator.create_project("另一个", _sample_layout())
        save_llm_config(self.root, provider="codex_cli", base_url="", model="gpt-6.1-sol")
        seen = []

        def call(cfg, messages, tools):
            seen.append(messages[0]["content"])
            if len(seen) == 1:
                self.assertNotIn("furniture_create_project", [t["function"]["name"] for t in tools])
                return {"tool_calls": [
                    {"id": "wrong", "function": {"name": "furniture_confirm_stage", "arguments": json.dumps({"project_id": other.id, "stage": "layout_plan"})}},
                    {"id": "right", "function": {"name": "furniture_confirm_stage", "arguments": '{"stage":"layout_plan"}'}},
                ]}
            # Inspect protocol state rather than the prompt's prose.
            snapshot = json.loads(messages[0]["content"].rsplit("```json\n", 1)[1].split("```", 1)[0])
            self.assertIn("layout_plan", snapshot["approved_stages"])
            return {"content": "已确认", "tool_calls": []}

        result = send_project_chat_message(project.id, "确认当前布局", workspace_root=WORKSPACE_ROOT, store_root=self.root, llm_caller=call)
        self.assertFalse(result["tool_trace"][0]["ok"])
        self.assertTrue(result["tool_trace"][1]["ok"])
        self.assertFalse(self.store.load(other.id).latest.approved_stages)

    def test_chat_busy_blocks_duplicate_messages_and_clear(self) -> None:
        project = self.orchestrator.create_project("客厅", _sample_layout())
        save_llm_config(self.root, provider="codex_cli", base_url="", model="gpt-6.1-sol")

        def call(*args):
            for action in (
                lambda: send_project_chat_message(project.id, "再次发送", workspace_root=WORKSPACE_ROOT, store_root=self.root, llm_caller=call),
                lambda: clear_chat_history(self.root, project.id),
            ):
                with self.assertRaises(WebChatError) as ctx:
                    action()
                self.assertEqual(ctx.exception.status_code, 409)
            return {"content": "完成", "tool_calls": []}

        send_project_chat_message(project.id, "你好", workspace_root=WORKSPACE_ROOT, store_root=self.root, llm_caller=call)
        clear_chat_history(self.root, project.id)
        self.assertEqual(web_agent_chat.load_chat_history(self.root, project.id), [])

    def test_failure_after_tool_keeps_receipt_and_releases_chat(self) -> None:
        project = self.orchestrator.create_project("客厅", _sample_layout())
        save_llm_config(self.root, provider="codex_cli", base_url="", model="gpt-6.1-sol")
        call = mock.Mock(side_effect=[
            {"tool_calls": [{"id": "confirm", "function": {"name": "furniture_confirm_stage", "arguments": '{"stage":"layout_plan"}'}}]},
            WebChatError("CODEX_CLI_ERROR", "连接中断", 502),
        ])
        with self.assertRaises(WebChatError):
            send_project_chat_message(project.id, "确认布局", workspace_root=WORKSPACE_ROOT, store_root=self.root, llm_caller=call)
        history = web_agent_chat.load_chat_history(self.root, project.id)
        self.assertEqual(len(history), 2)
        self.assertTrue(history[-1]["tool_trace"][0]["ok"])
        self.assertIn("layout_plan", self.store.load(project.id).latest.approved_stages)
        self.assertNotIn(project.id, web_agent_chat._ACTIVE_TURNS)
        result = send_project_chat_message(project.id, "再看状态", workspace_root=WORKSPACE_ROOT, store_root=self.root, llm_caller=lambda *a: {"content": "完成"})
        self.assertTrue(result["ok"])


    def test_real_completion_path_calls_codex_once_per_round(self) -> None:
        project = self.orchestrator.create_project("客厅", _sample_layout())
        save_llm_config(self.root, provider="codex_cli", base_url="", model="gpt-6.1-sol")
        with mock.patch.object(codex._CLIENT, "run_turn", return_value=("", '{"thinking":"","reply":"你好","tool_calls":[]}')) as turn:
            result = send_project_chat_message(project.id, "你好", workspace_root=WORKSPACE_ROOT, store_root=self.root)
        self.assertEqual(result["reply"], "你好")
        self.assertEqual(turn.call_count, 1)

    def test_project_page_embeds_chat_panel_only_for_local_editable_mode(self) -> None:
        project = self.orchestrator.create_project("客厅", _sample_layout())
        doc = preview_page_data(project, store_root=self.root)

        extension = page_extension(project.id)
        base_html = render_project_page(project.id, doc, mode=None, read_only=False)
        self.assertNotIn('id="chat-panel"', base_html)
        self.assertNotIn("/web-chat/", base_html)
        local_html = render_project_page(project.id, doc, mode=None, read_only=False, page_extension=extension)
        self.assertIn('id="chat-panel"', local_html)
        self.assertIn('id="llm-modal"', local_html)
        self.assertIn(f'"chatUrl": "/api/project/{project.id}/chat"', local_html)
        self.assertIn('"llmConfigUrl": "/api/llm/config"', local_html)
        self.assertIn(".chat-panel{", local_html)

        share_html = render_project_page(project.id, doc, mode="view", read_only=True, page_extension=extension)
        read_only_html = render_project_page(project.id, doc, read_only=True, page_extension=extension)
        for html in (share_html, read_only_html):
            self.assertNotIn('id="chat-panel"', html)
            self.assertNotIn('id="llm-modal"', html)
            self.assertNotIn("/web-chat/", html)
            self.assertNotIn("/api/llm/", html)

    def test_server_endpoints_are_registered_in_openapi(self) -> None:
        paths = server.app.openapi()["paths"]
        self.assertIn("/api/llm/config", paths)
        self.assertIn("/api/project/{project_id}/chat", paths)


if __name__ == "__main__":
    unittest.main()
