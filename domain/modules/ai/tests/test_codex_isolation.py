from __future__ import annotations

import asyncio
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_ROOT = WORKSPACE_ROOT / "domain/stages/cad-generated/scripts"
sys.path.insert(0, str(SCRIPT_ROOT))
from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from fastapi import HTTPException
from starlette.requests import Request
import server
from furniture_chat import http as chat_http
import furniture_ai as ai
from furniture_ai import isolation as codex_isolation, codex


class CodexIsolationTests(unittest.TestCase):
    def test_relocated_module_still_protects_the_actual_workspace(self):
        self.assertEqual(codex_isolation.WORKSPACE_ROOT, server.WORKSPACE_ROOT)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="codex-isolation-", dir=WORKSPACE_ROOT / "temp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_child_environment_does_not_reuse_parent_credentials_or_paths(self):
        source = {
            "PATH": "tools", "LOCALAPPDATA": "local", "CODEX_HOME": "app-home",
            "CODEX_SQLITE_HOME": "app-sqlite", "CODEX_ACCESS_TOKEN": "fake-access",
            "OPENAI_API_KEY": "fake-key", "OPENAI_BASE_URL": "https://example.invalid",
            "FURNITURE_LLM_API_KEY": "fake-furniture", "GEMINI_API_KEY": "fake-gemini",
            "ACCESS_TOKEN": "fake-external", "CODEX_THREAD_ID": "app-thread",
        }
        original = source.copy()
        home = self.root / "isolated"
        child = codex_isolation.isolated_environment(home, source)
        self.assertEqual(source, original)
        self.assertEqual(child["CODEX_HOME"], str(home))
        self.assertEqual(child["CODEX_SQLITE_HOME"], str(home))
        self.assertEqual(child["PATH"], "tools")
        self.assertFalse(any(value.startswith("fake-") for value in child.values()))
        self.assertNotIn("CODEX_THREAD_ID", child)

    def test_home_rejects_repository_app_home_and_parents(self):
        base = Path("C:/isolated-boundary-test")
        workspace = base / "repo"
        app = base / "app-home"
        for candidate in (workspace, workspace / "store", app, app / "nested", base):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                codex_isolation.validate_codex_home(candidate, workspace=workspace, app_home=app)
        candidate = base / "furniture"
        self.assertEqual(codex_isolation.validate_codex_home(candidate, workspace=workspace, app_home=app), candidate.resolve())

    def test_home_rejects_any_git_worktree(self):
        candidate = Path("C:/isolated-boundary-test/other-repo/state")
        marker = candidate.parent / ".git"
        with mock.patch.object(Path, "exists", lambda p: p == marker):
            with self.assertRaises(ValueError):
                codex_isolation.validate_codex_home(candidate, workspace=Path("C:/workspace"), app_home=Path("C:/app"))

    def test_packaged_app_localappdata_cannot_redirect_state_into_app_cache(self):
        profile = Path("C:/isolated-user-profile")
        with (
            mock.patch.object(Path, "home", return_value=profile),
            mock.patch.dict(os.environ, {"LOCALAPPDATA": "C:/AppPackage/LocalCache"}, clear=True),
        ):
            home = codex_isolation.isolated_codex_home()
        self.assertEqual(home, (profile / ".furniture-agent/codex-home").resolve())

    def test_process_options_pin_file_auth_cwd_logs_and_database(self):
        with mock.patch.object(codex_isolation, "isolated_codex_home", return_value=self.root):
            runtime, env, args = codex_isolation.isolated_process_options()
        self.assertEqual(runtime, self.root / "runtime")
        self.assertTrue(runtime.is_dir())
        self.assertEqual(env["CODEX_HOME"], str(self.root))
        overrides = dict(item.split("=", 1) for item in args[1::2])
        self.assertEqual(json.loads(overrides["cli_auth_credentials_store"]), "file")
        self.assertEqual(json.loads(overrides["sqlite_home"]), str(self.root))
        self.assertEqual(json.loads(overrides["log_dir"]), str(self.root / "log"))
        self.assertFalse(json.loads(overrides["check_for_update_on_startup"]))

    def test_spawn_uses_only_isolated_options_and_kills_owned_process(self):
        client = codex.CodexAppServerClient()
        proc = mock.Mock()
        proc.stdout, proc.stderr, proc.stdin = io.StringIO(), io.StringIO(), io.StringIO()
        proc.poll.return_value = None
        child = {"CODEX_HOME": str(self.root)}
        with (
            mock.patch.object(codex, "isolated_process_options", return_value=(self.root, child, ["-c", 'cli_auth_credentials_store="file"'])),
            mock.patch.object(codex.subprocess, "Popen", return_value=proc) as spawn,
            mock.patch.object(client, "_wait_for_response", return_value={}),
            mock.patch.object(client, "_verify_runtime_configuration") as verify,
        ):
            client._ensure_process("codex.exe")
            self.assertEqual(spawn.call_args.kwargs["env"], child)
            self.assertEqual(spawn.call_args.kwargs["cwd"], str(self.root))
            self.assertIn('cli_auth_credentials_store="file"', spawn.call_args.args[0])
            verify.assert_called_once_with(self.root)
            client._shutdown_process()
            proc.kill.assert_called_once()

    def test_effective_machine_config_cannot_override_isolation(self):
        client = codex.CodexAppServerClient()
        valid = {"cli_auth_credentials_store": "file", "sqlite_home": str(self.root), "log_dir": str(self.root / "log")}
        with mock.patch.object(client, "_send_rpc", return_value=1), mock.patch.object(client, "_wait_for_response", return_value={"config": valid}) as response:
            client._verify_runtime_configuration(self.root)
            for changed in ({"cli_auth_credentials_store": "keyring"}, {"sqlite_home": "C:/AppData"}, {"log_dir": "C:/AppLogs"}):
                response.return_value = {"config": {**valid, **changed}}
                with self.assertRaises(RuntimeError):
                    client._verify_runtime_configuration(self.root)

    def test_missing_isolated_auth_does_not_fall_back_to_app_login(self):
        client = codex.CodexAppServerClient()
        with (
            mock.patch.object(codex, "isolated_codex_home", return_value=self.root),
            mock.patch.object(client, "_ensure_process") as start,
            mock.patch.object(Path, "read_text", side_effect=AssertionError("must not read auth tokens")),
        ):
            state = client.authentication_state("codex.exe")
        self.assertEqual(state, {"authenticated": False, "status": "needs_login", "isolated": True})
        start.assert_not_called()

    def test_account_response_exposes_only_authentication_state(self):
        client = codex.CodexAppServerClient()
        with (
            mock.patch.object(client, "_send_rpc", return_value=1),
            mock.patch.object(client, "_wait_for_response", return_value={"account": {"type": "chatgpt", "email": "private@example.invalid", "accessToken": "fake-secret"}}),
        ):
            state = client._read_auth_state()
        self.assertEqual(set(state), {"authenticated", "status", "isolated"})
        self.assertTrue(state["authenticated"])
        self.assertNotIn("private", str(state))
        self.assertNotIn("secret", str(state))

    def login_client(self, url):
        client = codex.CodexAppServerClient()
        client._ensure_process = mock.Mock()
        client._read_auth_state = mock.Mock(return_value={"authenticated": False})
        client._send_rpc = mock.Mock(return_value=1)
        client._wait_for_response = mock.Mock(return_value={"authUrl": url})
        client._shutdown_process = mock.Mock()
        return client

    def test_login_reuses_pending_flow_without_saving_credentials_in_project(self):
        client = self.login_client("https://auth.openai.com/oauth/authorize?state=example")
        first = client.start_login("codex.exe")
        second = client.start_login("codex.exe")
        self.assertEqual(first["auth_url"], second["auth_url"])
        self.assertEqual(first["status"], "awaiting_login")
        self.assertEqual(client._send_rpc.call_count, 1)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_login_rejects_non_official_urls_and_redacts_errors(self):
        for url in ("javascript:alert(1)", "https://example.invalid/login", "https://private@auth.openai.com/login"):
            client = self.login_client(url)
            with self.subTest(url=url), self.assertRaises(ai.AIConnectionError) as ctx:
                client.start_login("codex.exe")
            self.assertNotIn(url, ctx.exception.message)
            client._shutdown_process.assert_called_once()
        client = self.login_client("")
        client._wait_for_response.side_effect = RuntimeError("fake-private-token")
        with self.assertRaises(ai.AIConnectionError) as ctx:
            client.start_login("codex.exe")
        self.assertNotIn("fake-private-token", ctx.exception.message)

    def test_codex_setting_does_not_copy_environment_api_key_into_store(self):
        with (
            mock.patch.dict(os.environ, {"OPENAI_API_KEY": "fake-environment-api-key"}),
            mock.patch.object(codex._CLIENT, "authentication_state", return_value={"authenticated": False, "status": "needs_login", "isolated": True}),
        ):
            result = ai.save_llm_config(self.root, provider="codex_cli", model="test-model")
        saved = json.loads((self.root / "_llm_config.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["api_key"], "")
        self.assertFalse(result["configured"])
        self.assertFalse(result["has_api_key"])

    @staticmethod
    def request(host="127.0.0.1:8765", client="127.0.0.1", origin=None):
        headers = [(b"host", host.encode())]
        if origin:
            headers.append((b"origin", origin.encode()))
        return Request({"type": "http", "scheme": "http", "method": "POST", "path": "/api/llm/codex/login", "query_string": b"", "headers": headers, "client": (client, 1234), "server": ("127.0.0.1", 8765)})

    def test_login_routes_reject_remote_clients_cross_origin_and_dns_rebinding(self):
        chat_http.require_local_codex_access(self.request(origin="http://127.0.0.1:8765"), server.may_edit)
        for req in (self.request(client="192.0.2.1"), self.request(host="attacker.invalid:8765"), self.request(origin="https://attacker.invalid"), self.request(origin="null")):
            with self.assertRaises(HTTPException) as ctx:
                chat_http.require_local_codex_access(req, server.may_edit)
            self.assertEqual(ctx.exception.status_code, 403)

    def test_login_status_response_cannot_be_cached(self):
        router = chat_http.create_router(
            workspace_root=WORKSPACE_ROOT,
            store_root=lambda: self.root,
            load_project=lambda project_id: None,
            may_edit=server.may_edit,
        )
        with mock.patch.object(ai, "codex_authentication_state", return_value={"authenticated": False, "status": "needs_login", "isolated": True}):
            endpoint = next(route.endpoint for route in router.routes if route.path == "/api/llm/codex/status")
            result = asyncio.run(endpoint(self.request()))
        self.assertEqual(result.headers["cache-control"], "no-store")
        self.assertEqual(set(json.loads(result.body)), {"authenticated", "status", "isolated"})


if __name__ == "__main__":
    unittest.main()
