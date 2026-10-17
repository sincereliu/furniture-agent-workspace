from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

import server
from furniture_layout.project_layout import ProjectLayout
from furniture_layout.room_page import render_project_page
from furniture_layout.open_preview import preview_page_data
from furniture_workflow import web_agent_chat
from furniture_workflow.web_agent_chat import (
    WebChatError,
    clear_chat_history,
    get_project_chat_state,
    load_llm_config,
    public_llm_config,
    save_llm_config,
    send_project_chat_message,
)
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

    def test_llm_config_saves_masks_and_preserves_existing_key(self) -> None:
        with (
            mock.patch.dict("os.environ", {}, clear=True),
            mock.patch.object(web_agent_chat, "_discover_codex_binary", return_value=None),
            mock.patch.object(web_agent_chat, "_discover_agy_binary", return_value=None),
        ):
            initial = public_llm_config(self.root)
            self.assertFalse(initial["configured"])
            self.assertFalse(initial["has_api_key"])

            saved = save_llm_config(
                self.root,
                provider="openai_compatible",
                base_url="https://api.deepseek.com/v1",
                model="deepseek-chat",
                api_key="sk-secret1234567890",
            )
            self.assertTrue(saved["configured"])
            self.assertTrue(saved["has_api_key"])
            self.assertEqual(saved["api_key_masked"], "sk-s...7890")
            self.assertNotIn("sk-secret1234567890", str(saved))

            # 留空 api_key 更新模型名时保留原密钥
            updated = save_llm_config(
                self.root,
                provider="openai_compatible",
                base_url="https://api.deepseek.com/v1",
                model="deepseek-reasoner",
                api_key=None,
            )
            self.assertEqual(updated["model"], "deepseek-reasoner")
            self.assertEqual(load_llm_config(self.root)["api_key"], "sk-secret1234567890")

    def test_local_oauth_cli_modes_do_not_require_api_key(self) -> None:
        with (
            mock.patch.object(web_agent_chat, "_discover_codex_binary", return_value="C:/bin/codex.exe"),
            mock.patch.object(web_agent_chat, "_discover_agy_binary", return_value="C:/bin/agy.exe"),
        ):
            auto_cfg = public_llm_config(self.root)
            self.assertTrue(auto_cfg["configured"])
            self.assertEqual(auto_cfg["provider"], "codex_cli")
            self.assertEqual(auto_cfg["model"], "gpt-6.1-sol")
            self.assertEqual(auto_cfg["reasoning_effort"], "high")

            agy_cfg = save_llm_config(
                self.root,
                provider="agy_cli",
                base_url="",
                model="gemini-3.8-flash-high",
                reasoning_effort="low",
            )
            self.assertTrue(agy_cfg["configured"])
            self.assertEqual(agy_cfg["provider"], "agy_cli")
            self.assertEqual(agy_cfg["base_url"], "local://agy-cli")
            self.assertEqual(agy_cfg["model"], "gemini-3.8-flash-low")
            self.assertEqual(agy_cfg["reasoning_effort"], "low")

            agy_max = save_llm_config(
                self.root,
                provider="agy_cli",
                base_url="",
                model="gemini-4-argon-low",
                reasoning_effort="max",
            )
            self.assertEqual(agy_max["model"], "gemini-4-argon-high")
            self.assertEqual(agy_max["reasoning_effort"], "max")

            codex_minimal = save_llm_config(
                self.root,
                provider="codex_cli",
                base_url="",
                model="gpt-6.1-sol",
                reasoning_effort="minimal",
            )
            self.assertEqual(codex_minimal["reasoning_effort"], "minimal")

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
        self.assertEqual(len(result["tool_trace"]), 1)
        self.assertEqual(result["tool_trace"][0]["tool"], "furniture_confirm_stage")
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
            mock.patch.object(web_agent_chat, "_discover_codex_binary", return_value=None),
            mock.patch.object(web_agent_chat, "_discover_agy_binary", return_value=None),
        ):
            with self.assertRaises(WebChatError) as ctx:
                send_project_chat_message(
                    project.id,
                    "你好",
                    workspace_root=WORKSPACE_ROOT,
                    store_root=self.root,
                )
            self.assertEqual(ctx.exception.code, "LLM_NOT_CONFIGURED")

    def test_project_page_embeds_chat_panel_only_for_local_editable_mode(self) -> None:
        project = self.orchestrator.create_project("客厅", _sample_layout())
        doc = preview_page_data(project, store_root=self.root)

        local_html = render_project_page(project.id, doc, mode=None, read_only=False)
        self.assertIn('id="chat-panel"', local_html)
        self.assertIn('id="llm-modal"', local_html)
        self.assertIn(f'"chat_url":"/api/project/{project.id}/chat"', local_html)
        self.assertIn('"llm_config_url":"/api/llm/config"', local_html)

        share_html = render_project_page(project.id, doc, mode="view", read_only=True)
        self.assertIn('"chat_url":""', share_html)
        self.assertIn('"llm_config_url":""', share_html)

    def test_server_endpoints_are_registered_in_openapi(self) -> None:
        paths = server.app.openapi()["paths"]
        self.assertIn("/api/llm/config", paths)
        self.assertIn("/api/project/{project_id}/chat", paths)


if __name__ == "__main__":
    unittest.main()
