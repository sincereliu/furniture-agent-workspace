"""Exercise the feature switch in fresh interpreters, without AI dependencies."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_ROOT = WORKSPACE_ROOT / "domain/stages/cad-generated/scripts"


class WebChatFeatureTests(unittest.TestCase):
    def probe(self, code: str, *, enabled: str = "0") -> None:
        env = {**os.environ, "FURNITURE_WEB_CHAT": enabled, "FURNITURE_PREVIEW_BROWSER": "0"}
        result = subprocess.run(
            [sys.executable, "-c", f"import sys\nsys.path.insert(0, {str(Path(__file__).resolve().parent)!r})\n" + textwrap.dedent(code)],
            cwd=SCRIPTS_ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=45,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_disabled_server_starts_without_either_optional_package(self):
        self.probe('''
            import importlib.abc
            import sys
            from unittest import mock

            class NoAI(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname.split(".")[0] in {"furniture_ai", "furniture_chat"}:
                        raise AssertionError("disabled feature was imported: " + fullname)

            sys.meta_path.insert(0, NoAI())
            with mock.patch("subprocess.Popen", side_effect=AssertionError("unexpected process")):
                import server
                assert not server.WEB_CHAT_ENABLED
                paths = server.app.openapi()["paths"]
                assert "/api/llm/config" not in paths
                assert "/api/llm/codex/login" not in paths
                assert "/api/project/{project_id}/chat" not in paths
                assert "/api/project/{project_id}/layout" in paths
                assert "/api/project/{project_id}/cabinets/{cabinet_id}/panels" in paths
                assert not any(name.startswith(("furniture_ai", "furniture_chat")) for name in sys.modules)
        ''')

    def test_disabled_feature_keeps_core_generation_and_preview_working(self):
        self.probe('''
            import asyncio
            from pathlib import Path
            import sys
            import tempfile
            from unittest import mock
            import server
            sys.path.insert(0, str(Path("tests").resolve()))
            from asgi_test_support import request
            from panel_fixtures import cabinet_layout, panel_parameters
            from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
            from furniture_workflow.workflow_store import JsonProjectStore
            from furniture_workflow.workflow_state import WorkflowStage

            with tempfile.TemporaryDirectory(dir=server.WORKSPACE_ROOT / "temp") as temporary:
                server.STORE_ROOT = Path(temporary)
                store = JsonProjectStore(server.STORE_ROOT)
                orchestrator = FurnitureOrchestrator(workspace_root=server.WORKSPACE_ROOT, project_store=store)
                project = orchestrator.create_project("optional-feature-test", cabinet_layout())
                orchestrator.confirm_layout(project)
                result = orchestrator.run_next(project, stage_input={"parameters": panel_parameters()})
                assert result.revision.workflow.current == WorkflowStage.PANELS_PLANNED
                assert result.revision.latest_attempt(WorkflowStage.PANELS_PLANNED).passed

                async def check():
                    assert (await request(server.app, "/health")).status_code == 200
                    assert (await request(server.app, "/api/projects")).status_code == 200
                    assert (await request(server.app, f"/api/project/{project.id}/layout")).status_code == 200
                    preview = await request(server.app, f"/api/project/{project.id}/preview")
                    assert preview.status_code == 200
                    assert 'id="chat-panel"' not in preview.text
                    assert 'id="llm-modal"' not in preview.text
                    assert "/web-chat/" not in preview.text
                    assert "layout_chat.js" not in preview.text
                    assert "__PAGE_EXTENSION_" not in preview.text
                    assert "furniture_workflow.web_agent_chat" not in sys.modules
                    assert (await request(server.app, "/api/llm/config")).status_code == 404
                    assert (await request(server.app, "/api/llm/codex/login", method="POST")).status_code == 404
                    assert (await request(server.app, f"/api/project/{project.id}/chat", method="POST", payload={"message": "test"})).status_code == 404
                    assert (await request(server.app, "/web-chat/layout_chat.js")).status_code == 404

                with mock.patch("subprocess.Popen", side_effect=AssertionError("unexpected process")):
                    asyncio.run(check())
                assert not (server.STORE_ROOT / "_llm_config.json").exists()
                assert not (store.project_dir(project.id) / "chat.json").exists()
        ''')

    def test_invalid_switch_is_rejected_instead_of_silently_enabling_ai(self):
        self.probe('''
            try:
                import server
            except ValueError as exc:
                assert "FURNITURE_WEB_CHAT" in str(exc)
            else:
                raise AssertionError("invalid feature flag was accepted")
        ''', enabled="false")

    def test_enabled_routes_keep_the_host_access_gate(self):
        self.probe('''
            import asyncio
            from pathlib import Path
            import sys
            from unittest import mock
            import server
            from furniture_chat import http as chat_http
            sys.path.insert(0, str(Path("tests").resolve()))
            from asgi_test_support import request

            async def check():
                for method, path, payload in (
                    ("GET", "/api/llm/config", None),
                    ("POST", "/api/llm/config", {"model": "test-model"}),
                    ("GET", "/api/llm/codex/status", None),
                    ("POST", "/api/llm/codex/login", None),
                    ("GET", "/api/project/unknown/chat", None),
                    ("POST", "/api/project/unknown/chat", {"message": "test"}),
                    ("DELETE", "/api/project/unknown/chat", None),
                ):
                    response = await request(server.app, path, method=method, payload=payload, client="192.0.2.1")
                    assert response.status_code == 403, (method, path, response.status_code)

            with (
                mock.patch.object(chat_http.ai, "public_llm_config", side_effect=AssertionError("unexpected config access")),
                mock.patch.object(chat_http.ai, "save_llm_config", side_effect=AssertionError("unexpected config write")),
                mock.patch.object(chat_http.ai, "codex_authentication_state", side_effect=AssertionError("unexpected process")),
                mock.patch.object(chat_http.ai, "start_codex_login", side_effect=AssertionError("unexpected login")),
                mock.patch.object(chat_http, "get_project_chat_state", side_effect=AssertionError("unexpected project read")),
                mock.patch.object(chat_http, "send_project_chat_message", side_effect=AssertionError("unexpected model call")),
                mock.patch.object(chat_http, "clear_chat_history", side_effect=AssertionError("unexpected history write")),
            ):
                asyncio.run(check())
            assert chat_http.shutdown_connections in server.app.router.on_shutdown
            with mock.patch.object(chat_http.ai, "shutdown") as close:
                asyncio.run(chat_http.shutdown_connections())
                close.assert_called_once()
        ''', enabled="1")

    def test_enabled_feature_renders_and_serves_only_its_public_assets(self):
        self.probe('''
            import asyncio
            from pathlib import Path
            import sys
            import tempfile
            from unittest import mock
            import server
            from furniture_chat import http as chat_http
            sys.path.insert(0, str(Path("tests").resolve()))
            from asgi_test_support import request
            from panel_fixtures import cabinet_layout
            from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
            from furniture_workflow.workflow_store import JsonProjectStore

            with tempfile.TemporaryDirectory(dir=server.WORKSPACE_ROOT / "temp") as temporary:
                server.STORE_ROOT = Path(temporary)
                store = JsonProjectStore(server.STORE_ROOT)
                orchestrator = FurnitureOrchestrator(workspace_root=server.WORKSPACE_ROOT, project_store=store)
                project = orchestrator.create_project("enabled-feature-test", cabinet_layout())

                async def check():
                    preview = await request(server.app, f"/api/project/{project.id}/preview")
                    assert preview.status_code == 200
                    assert 'id="chat-panel"' in preview.text
                    assert 'id="llm-modal"' in preview.text
                    assert "/web-chat/layout_chat.js" in preview.text
                    assert ".chat-panel{" in preview.text
                    assert "/layout-view/layout_chat.js" not in preview.text
                    assert "__PAGE_EXTENSION_" not in preview.text
                    for path in ("/web-chat/layout_chat.js",):
                        response = await request(server.app, path)
                        assert response.status_code == 200, path
                        assert response.headers["cache-control"] == "no-store"
                    assert (await request(server.app, "/web-chat/conversation.py")).status_code == 404
                    assert (await request(server.app, "/layout-view/layout_chat.js")).status_code == 404
                    response = await request(server.app, "/api/llm/config")
                    assert response.status_code == 200
                    assert '"configured":false' in response.text

                with (
                    mock.patch.object(chat_http.ai, "public_llm_config", return_value={"configured": False}),
                    mock.patch("subprocess.Popen", side_effect=AssertionError("rendering started a process")),
                ):
                    asyncio.run(check())
        ''', enabled="1")


if __name__ == "__main__":
    unittest.main()
