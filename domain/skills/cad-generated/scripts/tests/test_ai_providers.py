from __future__ import annotations
import sys
import tempfile
import copy
import json
import subprocess
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

import furniture_ai as ai
from furniture_ai import agy, codex, discovery, openai_compatible, settings
from furniture_ai import load_llm_config, public_llm_config, save_llm_config


class CodexAppServerProtocolTests(unittest.TestCase):
    def test_close_releases_the_owned_process_and_is_idempotent(self):
        client = codex.CodexAppServerClient()
        proc = mock.Mock()
        proc.poll.return_value = None
        client._proc = proc
        client._binary = "codex.exe"
        client.close()
        client.close()
        proc.kill.assert_called_once()
        proc.wait.assert_called_once_with(timeout=5)
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            stream.close.assert_called_once()
        self.assertIsNone(client._proc)
        self.assertIsNone(client._binary)

    def test_pending_prewarm_cannot_restart_a_closed_connection(self):
        client = codex.CodexAppServerClient()
        with (
            mock.patch.object(codex.threading, "Thread") as thread,
            mock.patch.object(codex, "isolated_process_options") as options,
            mock.patch.object(codex.subprocess, "Popen") as spawn,
        ):
            client.prewarm_async("codex.exe", "test-model")
            pending = thread.call_args.kwargs["target"]
            client.close()
            pending()
        options.assert_not_called()
        spawn.assert_not_called()

    def client(self):
        client = codex.CodexAppServerClient()
        client._ensure_process = mock.Mock()
        client._start_thread = mock.Mock(side_effect=["thread-a", "thread-b"])
        client._wait_for_response = mock.Mock(return_value={"status": "unsubscribed"})
        client._read_auth_state = mock.Mock(return_value={"authenticated": True})
        client._shutdown_process = mock.Mock()
        return client

    def test_isolated_threads_ignore_stale_events_and_use_final_item(self):
        client = self.client()
        final = '{"thinking":"","reply":"完成","tool_calls":[]}'
        calls = []

        def send(method, params):
            calls.append((method, params))
            if method == "turn/start":
                thread_id = params["threadId"]
                client._msg_queue.put({"id": 1, "result": {"turn": {"id": "turn-current"}}})
                for thread, turn in (("old-thread", "turn-current"), (thread_id, "old-turn")):
                    client._msg_queue.put({"method": "turn/completed", "params": {"threadId": thread, "turn": {"id": turn, "status": "failed"}}})
                for item_id, text, phase in (("comment", "我会查看项目", "commentary"), ("answer", final, "final_answer")):
                    base = {"threadId": thread_id, "turnId": "turn-current"}
                    client._msg_queue.put({"method": "item/agentMessage/delta", "params": {**base, "itemId": item_id, "delta": text[:4]}})
                    client._msg_queue.put({"method": "item/completed", "params": {**base, "item": {"id": item_id, "type": "agentMessage", "text": text, "phase": phase}}})
                client._msg_queue.put({"method": "turn/completed", "params": {"threadId": thread_id, "turn": {"id": "turn-current", "status": "completed"}}})
            return 1

        client._send_rpc = send
        for _ in range(2):
            _, text = client.run_turn(binary="codex.exe", model="test-model", effort="none", prompt="test", timeout=1)
            self.assertEqual(text, final)
        self.assertEqual([p["threadId"] for m, p in calls if m == "turn/start"], ["thread-a", "thread-b"])
        self.assertEqual([p["effort"] for m, p in calls if m == "turn/start"], ["none", "none"])
        self.assertEqual(len([m for m, p in calls if m == "thread/unsubscribe"]), 2)
        client._shutdown_process.assert_not_called()

    def test_failed_and_interrupted_turns_reset_transport(self):
        for status in ("failed", "interrupted"):
            client = self.client()
            client._send_rpc = mock.Mock(return_value=1)
            client._msg_queue.put({"method": "turn/completed", "params": {"threadId": "thread-a", "turn": {"id": "turn", "status": status}}})
            with self.assertRaises(RuntimeError):
                client.run_turn(binary="codex.exe", model="test-model", effort="low", prompt="test", timeout=1)
            client._shutdown_process.assert_called_once()
            self.assertTrue(client._lock.acquire(blocking=False))
            client._lock.release()

    def test_timeout_and_startup_failure_release_transport(self):
        client = self.client()
        client._send_rpc = mock.Mock(return_value=1)
        with self.assertRaises(TimeoutError):
            client.run_turn(binary="codex.exe", model="test-model", effort="low", prompt="test", timeout=0)
        client._shutdown_process.assert_called_once()
        client._ensure_process.side_effect = OSError("cannot start")
        with self.assertRaises(OSError):
            client.run_turn(binary="codex.exe", model="test-model", effort="low", prompt="test", timeout=1)
        self.assertTrue(client._lock.acquire(blocking=False))
        client._lock.release()

    def test_unhandled_server_request_fails_without_hanging(self):
        client = self.client()
        client._send_rpc = mock.Mock(return_value=1)
        client._msg_queue.put({"id": 99, "method": "item/tool/call", "params": {"threadId": "thread-a"}})
        with self.assertRaises(RuntimeError):
            client.run_turn(binary="codex.exe", model="test-model", effort="low", prompt="test", timeout=1)
        client._shutdown_process.assert_called_once()

    def test_turn_requires_isolated_chatgpt_login(self):
        client = self.client()
        client._read_auth_state.return_value = {"authenticated": False}
        with self.assertRaises(ai.AIConnectionError) as ctx:
            client.run_turn(binary="codex.exe", model="test-model", effort="low", prompt="test", timeout=1)
        self.assertEqual(ctx.exception.code, "CODEX_LOGIN_REQUIRED")
        self.assertEqual(ctx.exception.status_code, 401)
        client._start_thread.assert_not_called()
        client._shutdown_process.assert_called_once()


class AIProviderBoundaryTests(unittest.TestCase):
    def test_package_import_needs_no_furniture_runtime_and_starts_no_process(self):
        script = """
import sys
from unittest import mock
sys.path.insert(0, sys.argv[1])
with mock.patch('subprocess.Popen', side_effect=AssertionError('import started a process')):
    import furniture_ai
assert not any(name == 'server' or name.startswith((
    'furniture_workflow', 'furniture_layout', 'furniture_panel_planning',
    'furniture_manufacturing', 'furniture_cad',
)) for name in sys.modules)
assert callable(furniture_ai.complete)
"""
        result = subprocess.run([sys.executable, "-I", "-c", script, str(SCRIPT_ROOT)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_provider_dispatch_passes_opaque_tools_and_preserves_input(self):
        messages = [{"role": "user", "content": "example"}]
        tools = [{"type": "function", "function": {"name": "lookup_weather", "parameters": {"type": "object"}}}]
        expected = {"content": "", "tool_calls": [{"function": {"name": "lookup_weather", "arguments": '{"location":"example"}'}}]}
        for provider, module in (("codex_cli", codex), ("agy_cli", agy), ("openai_compatible", openai_compatible)):
            config = {"provider": provider, "model": "example"}
            before = copy.deepcopy((config, messages, tools))
            progress = mock.Mock()
            with mock.patch.object(module, "complete", return_value=expected) as complete:
                result = ai.complete(config, messages, tools, on_reply_delta=progress)
            self.assertIs(result, expected)
            self.assertEqual(complete.call_args.args, (config, messages, tools))
            self.assertIs(complete.call_args.kwargs["on_reply_delta"], progress)
            self.assertEqual((config, messages, tools), before)

    def test_codex_adapter_normalizes_non_furniture_tool_call(self):
        output = {"thinking": "检查位置", "reply": "", "tool_calls": [{"name": "lookup_weather", "arguments_json": '{"location":"example"}'}]}
        with (
            mock.patch.object(codex, "_discover_codex_binary", return_value="codex.exe"),
            mock.patch.object(codex._CLIENT, "run_turn", return_value=("", json.dumps(output))),
        ):
            result = codex.complete({"model": "example", "reasoning_effort": "low"}, [], [])
        self.assertEqual(result["tool_calls"][0]["function"], {"name": "lookup_weather", "arguments": '{"location":"example"}'})

    def test_compatible_adapter_normalizes_arguments_and_progress(self):
        response = {"choices": [{"message": {"content": "结果", "tool_calls": [{"id": "call_1", "function": {"name": "lookup_weather", "arguments": {"location": "example"}}}]}}]}
        progress = mock.Mock()
        with mock.patch.object(openai_compatible, "_http_post_json", return_value=response) as post:
            result = ai.complete({"provider": "openai_compatible", "base_url": "http://127.0.0.1:11434/v1", "model": "example", "api_key": ""}, [], [], on_reply_delta=progress)
        self.assertEqual(post.call_args.args[0], "http://127.0.0.1:11434/v1/chat/completions")
        self.assertEqual(json.loads(result["tool_calls"][0]["function"]["arguments"]), {"location": "example"})
        progress.assert_called_once_with("结果")

    def test_agy_adapter_normalizes_structured_output(self):
        with tempfile.TemporaryDirectory(prefix="ai-agy-", dir=WORKSPACE_ROOT / "temp") as directory:
            output = {"structured_output": {"thinking": "", "reply": "结果", "tool_calls": []}}
            with (
                mock.patch.object(agy, "_discover_agy_binary", return_value="agy.exe"),
                mock.patch.object(agy.tempfile, "mkdtemp", return_value=directory),
                mock.patch.object(agy.subprocess, "run", return_value=mock.Mock(returncode=0, stdout=json.dumps(output), stderr="")) as run,
            ):
                result = ai.complete({"provider": "agy_cli", "model": "gemini-example-high", "reasoning_effort": "low"}, [], [])
            self.assertIn("gemini-example-low", run.call_args.args[0])
        self.assertEqual(result, {"thinking": "", "content": "结果", "tool_calls": []})

    def test_missing_codex_reports_public_error_without_starting_login(self):
        with mock.patch.object(discovery, "_discover_codex_binary", return_value=None), mock.patch.object(codex._CLIENT, "start_login") as login:
            with self.assertRaises(ai.AIConnectionError) as ctx:
                ai.start_codex_login()
            self.assertEqual(ctx.exception.code, "CODEX_CLI_NOT_FOUND")
            self.assertEqual(ctx.exception.status_code, 422)
            login.assert_not_called()


class AISettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai-settings-", dir=WORKSPACE_ROOT / "temp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        patch = mock.patch.object(codex._CLIENT, "authentication_state", return_value={"authenticated": True, "status": "authenticated", "isolated": True})
        patch.start()
        self.addCleanup(patch.stop)

    def test_llm_config_saves_masks_and_preserves_existing_key(self) -> None:
        with (
            mock.patch.dict("os.environ", {}, clear=True),
            mock.patch.object(settings, "_discover_codex_binary", return_value=None),
            mock.patch.object(settings, "_discover_agy_binary", return_value=None),
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
            mock.patch.object(settings, "_discover_codex_binary", return_value="C:/bin/codex.exe"),
            mock.patch.object(settings, "_discover_agy_binary", return_value="C:/bin/agy.exe"),
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


    def test_codex_errors_do_not_silently_retry_with_exec(self) -> None:
        for failure, code in ((TimeoutError("timeout"), "CODEX_CLI_TIMEOUT"), (RuntimeError("login required"), "CODEX_CLI_ERROR")):
            with (
                mock.patch.object(codex, "_discover_codex_binary", return_value="codex.exe"),
                mock.patch.object(codex._CLIENT, "run_turn", side_effect=failure),
                mock.patch.object(codex.subprocess, "run") as fallback,
            ):
                with self.assertRaises(ai.AIConnectionError) as ctx:
                    codex.complete({"model": "gpt-6.1-sol", "reasoning_effort": "high"}, [], [])
                self.assertEqual(ctx.exception.code, code)
                fallback.assert_not_called()



if __name__ == "__main__":
    unittest.main()
