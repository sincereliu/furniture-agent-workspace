"""Codex App Server 的独立登录、进程生命周期和模型通信。"""
from __future__ import annotations
import atexit
from collections import deque
import json
from pathlib import Path
import queue
import subprocess
import threading
import time
from typing import Any, Callable, Mapping
from urllib import parse as urllib_parse
from .contracts import AIConnectionError, DEFAULT_TIMEOUT_SECONDS, VALID_REASONING_EFFORTS
from .discovery import _discover_codex_binary
from .isolation import isolated_codex_home, isolated_process_options
from .cli_protocol import _CLI_STEP_SCHEMA, _format_cli_prompt, _extract_partial_json_string_field, _normalize_cli_step_output


class CodexAppServerClient:
    """常驻 Codex App Server 客户端；复用进程，每次调用隔离会话。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._closed = threading.Event()
        self._proc: subprocess.Popen[str] | None = None
        self._binary: str | None = None
        self._msg_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._next_id = 1
        self._stderr: deque[str] = deque(maxlen=12)
        self._authenticated = False
        self._auth_error = False
        self._login_url: str | None = None

    def _public_auth_state(self) -> dict[str, Any]:
        return {
            "authenticated": self._authenticated,
            "status": (
                "authenticated" if self._authenticated else
                "awaiting_login" if self._login_url else
                "error" if self._auth_error else "needs_login"
            ),
            "isolated": True,
        }

    def _read_auth_state(self) -> dict[str, Any]:
        req_id = self._send_rpc("account/read", {"refreshToken": False})
        result = self._wait_for_response(req_id, timeout=10)
        self._authenticated = (result.get("account") or {}).get("type") == "chatgpt"
        self._auth_error = False
        if self._authenticated:
            self._login_url = None
        return self._public_auth_state()

    def authentication_state(self, binary: str | None) -> dict[str, Any]:
        # Do not hold the web server or polling behind a running inference turn.
        if not binary:
            return {"authenticated": False, "status": "unavailable", "isolated": True}
        if not self._lock.acquire(blocking=False):
            return self._public_auth_state()
        try:
            home = isolated_codex_home()
            if self._proc is None and not (home / "auth.json").is_file():
                return {"authenticated": False, "status": "needs_login", "isolated": True}
            self._ensure_process(binary)
            return self._read_auth_state()
        except (OSError, ValueError, RuntimeError, TimeoutError):
            self._shutdown_process()
            self._auth_error = True
            return self._public_auth_state()
        finally:
            self._lock.release()

    def start_login(self, binary: str) -> dict[str, Any]:
        if not self._lock.acquire(blocking=False):
            raise AIConnectionError("CODEX_BUSY", "Codex 正在执行任务，请完成后再登录。", 409)
        try:
            self._ensure_process(binary)
            state = self._read_auth_state()
            if state["authenticated"]:
                return state
            if not self._login_url:
                req_id = self._send_rpc("account/login/start", {"type": "chatgpt"})
                result = self._wait_for_response(req_id, timeout=15)
                url = str(result.get("authUrl") or "")
                parsed = urllib_parse.urlparse(url)
                if parsed.scheme != "https" or parsed.hostname not in {"auth.openai.com", "chatgpt.com"} or parsed.username or parsed.password:
                    raise RuntimeError("invalid Codex login URL")
                self._login_url = url
            return {**self._public_auth_state(), "auth_url": self._login_url}
        except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
            self._shutdown_process()
            raise AIConnectionError("CODEX_LOGIN_FAILED", "无法启动独立 Codex 登录，请检查本机 Codex 和网络。", 502) from exc
        finally:
            self._lock.release()

    def _ensure_process(self, binary: str) -> None:
        if self._closed.is_set():
            raise RuntimeError("Codex connection has been closed")
        if (
            self._proc is not None
            and self._proc.poll() is None
            and self._binary == binary
        ):
            return
        self._shutdown_process()
        runtime_dir, child_env, overrides = isolated_process_options()
        cmd = [
            binary,
            *overrides,
            "--disable",
            "apps",
            "--disable",
            "connectors",
            "--disable",
            "js_repl",
            "--disable",
            "plugins",
            "--disable",
            "shell_tool",
            "--disable",
            "shell_snapshot",
            "--disable",
            "memories",
            "--disable",
            "multi_agent",
            "app-server",
            "--listen",
            "stdio://",
        ]
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            cwd=str(runtime_dir),
            env=child_env,
        )
        self._binary = binary
        # Reader threads keep their own queue: an old process cannot contaminate a restart.
        self._msg_queue = queue.Queue()
        self._stderr = deque(maxlen=12)
        message_queue = self._msg_queue
        stderr_lines = self._stderr

        proc_ref = self._proc

        def _reader() -> None:
            stdout = proc_ref.stdout
            if stdout is None:
                return
            for line in stdout:
                s = line.strip()
                if not s:
                    continue
                try:
                    obj = json.loads(s)
                    if isinstance(obj, dict):
                        method = obj.get("method")
                        params = obj.get("params") or {}
                        if self._proc is not proc_ref:
                            continue
                        if method == "account/updated":
                            self._authenticated = params.get("authMode") == "chatgpt"
                            if self._authenticated:
                                self._login_url = None
                        elif method == "account/login/completed":
                            self._login_url = None
                            self._auth_error = not bool(params.get("success"))
                        message_queue.put(obj)
                except json.JSONDecodeError:
                    pass

        def _stderr_reader() -> None:
            if proc_ref.stderr is not None:
                for line in proc_ref.stderr:
                    stderr_lines.append(line.strip())

        threading.Thread(target=_reader, daemon=True).start()
        threading.Thread(target=_stderr_reader, daemon=True).start()
        init_id = self._send_rpc(
            "initialize",
            {
                "clientInfo": {"name": "furniture-web", "version": "1.0.0"},
                "capabilities": {},
            },
        )
        self._wait_for_response(init_id, timeout=15.0)
        self._send_notification("initialized", {})
        self._verify_runtime_configuration(Path(child_env["CODEX_HOME"]))

    def _verify_runtime_configuration(self, home: Path) -> None:
        # Managed machine settings can override CLI flags. Refuse to run if the
        # effective state paths or credential store break the isolation contract.
        req_id = self._send_rpc("config/read", {"includeLayers": False})
        result = self._wait_for_response(req_id, timeout=10)
        config = result.get("config") or {}
        if (
            config.get("cli_auth_credentials_store") != "file"
            or Path(str(config.get("sqlite_home") or "")).resolve() != home.resolve()
            or Path(str(config.get("log_dir") or "")).resolve() != (home / "log").resolve()
        ):
            raise RuntimeError("Codex 生效配置未满足独立数据目录约束，已拒绝启动。")

    def close(self) -> None:
        """Stop the owned process and prevent pending prewarm work from reopening it."""
        self._closed.set()
        with self._lock:
            self._shutdown_process()

    def _shutdown_process(self) -> None:
        proc, self._proc = self._proc, None
        self._binary = None
        self._authenticated = False
        self._login_url = None
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.kill()
                proc.wait(timeout=5)
            except OSError:
                pass
            except subprocess.TimeoutExpired:
                pass
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream is not None:
                    stream.close()

    def _send_rpc(self, method: str, params: Mapping[str, Any]) -> int:
        assert self._proc is not None and self._proc.stdin is not None
        req_id = self._next_id
        self._next_id += 1
        line = json.dumps({"id": req_id, "method": method, "params": params}, ensure_ascii=False)
        self._proc.stdin.write(line + "\n")
        self._proc.stdin.flush()
        return req_id

    def _send_notification(self, method: str, params: Mapping[str, Any]) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        line = json.dumps({"method": method, "params": params}, ensure_ascii=False)
        self._proc.stdin.write(line + "\n")
        self._proc.stdin.flush()

    def _wait_for_response(self, req_id: int, timeout: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = max(0.05, deadline - time.monotonic())
            try:
                msg = self._msg_queue.get(timeout=min(remaining, 0.5))
            except queue.Empty:
                if self._proc is None or self._proc.poll() is not None:
                    raise RuntimeError("Codex App Server 已退出，请检查独立运行环境。")
                continue
            if msg.get("id") == req_id:
                if "error" in msg:
                    raise RuntimeError(str(msg["error"]))
                return dict(msg.get("result") or {})
        raise TimeoutError(f"codex app-server RPC {req_id} timed out")

    def _start_thread(self, model: str) -> str:
        # The caller already supplies full history and the live snapshot. Never reuse
        # a model-level conversation across projects, cleared chats or tool rounds.
        req_id = self._send_rpc(
            "thread/start",
            {
                "model": model,
                "ephemeral": True,
                "sandbox": "read-only",
                "approvalPolicy": "never",
                "config": {"project_doc_max_bytes": 0, "web_search": "disabled"},
            },
        )
        res = self._wait_for_response(req_id, timeout=15.0)
        thread_obj = res.get("thread") or {}
        thread_id = str(thread_obj.get("id") or "")
        if not thread_id:
            raise RuntimeError("codex app-server did not return thread.id")
        return thread_id

    def prewarm_async(self, binary: str, model: str) -> None:
        """后台预热常驻进程与首个连接。"""
        def _task() -> None:
            if not self._lock.acquire(blocking=False):
                return
            try:
                self._ensure_process(binary)
            except Exception:
                self._shutdown_process()
            finally:
                self._lock.release()

        threading.Thread(target=_task, daemon=True).start()

    def run_turn(
        self,
        *,
        binary: str,
        model: str,
        effort: str,
        prompt: str,
        output_schema: Mapping[str, Any] | None = None,
        on_reasoning_delta: Callable[[str], None] | None = None,
        on_text_delta: Callable[[str], None] | None = None,
        timeout: float = float(DEFAULT_TIMEOUT_SECONDS),
    ) -> tuple[str, str]:
        if not self._lock.acquire(timeout=timeout):
            raise TimeoutError("Codex 正在处理其他请求，请稍后重试")
        try:
            self._ensure_process(binary)
            if not self._read_auth_state()["authenticated"]:
                raise AIConnectionError("CODEX_LOGIN_REQUIRED", "请先在模型设置中单独登录家具项目的 Codex。", 401)
            thread_id = self._start_thread(model)
            turn_params: dict[str, Any] = {
                "threadId": thread_id,
                "input": [{"type": "text", "text": prompt}],
                "model": model,
            }
            if effort:
                turn_params["effort"] = effort
            if output_schema is not None:
                turn_params["outputSchema"] = dict(output_schema)

            req_id = self._send_rpc("turn/start", turn_params)
            agent_chunks: list[str] = []
            reasoning_chunks: list[str] = []
            item_text: dict[str, str] = {}
            final_text: str | None = None
            turn_id: str | None = None
            deadline = time.monotonic() + timeout

            while time.monotonic() < deadline:
                remaining = max(0.05, deadline - time.monotonic())
                try:
                    msg = self._msg_queue.get(timeout=min(remaining, 0.5))
                except queue.Empty:
                    if self._proc is None or self._proc.poll() is not None:
                        raise RuntimeError("codex app-server exited during turn")
                    continue

                if msg.get("method") and "id" in msg:
                    raise RuntimeError(f"不支持 Codex 反向请求：{msg['method']}")
                if msg.get("id") == req_id:
                    if "error" in msg:
                        raise RuntimeError("Codex 拒绝开始本次请求，请检查登录状态和模型设置。")
                    turn_id = str(((msg.get("result") or {}).get("turn") or {}).get("id") or "")
                    continue

                method = str(msg.get("method") or "")
                params = msg.get("params") or {}
                if params.get("threadId") != thread_id:
                    continue
                event_turn_id = params.get("turnId") or (params.get("turn") or {}).get("id")
                if turn_id and event_turn_id != turn_id:
                    continue
                if method == "item/agentMessage/delta":
                    delta = str(params.get("delta") or "")
                    if delta:
                        item_id = str(params.get("itemId") or "")
                        item_text[item_id] = item_text.get(item_id, "") + delta
                        if on_text_delta is not None:
                            on_text_delta(item_text[item_id])
                elif method == "item/reasoning/summaryTextDelta":
                    delta = str(params.get("delta") or "")
                    if delta:
                        reasoning_chunks.append(delta)
                        if on_reasoning_delta is not None:
                            on_reasoning_delta("".join(reasoning_chunks))
                elif method == "item/completed":
                    item = params.get("item") or {}
                    if item.get("type") == "agentMessage":
                        txt = str(item.get("text") or "")
                        if txt:
                            agent_chunks.append(txt)
                            if item.get("phase") == "final_answer":
                                final_text = txt
                elif method == "turn/completed":
                    turn = params.get("turn") or {}
                    status = str(turn.get("status") or "")
                    if status != "completed":
                        err = turn.get("error") or {}
                        raise RuntimeError(f"Codex 请求未完成（{status}），请检查登录状态、额度和网络。")
                    break
            else:
                raise TimeoutError(f"codex app-server turn timed out (>{timeout}s)")

            # Completed items are authoritative; commentary must not prefix JSON.
            text = final_text or (agent_chunks[-1] if agent_chunks else "".join(item_text.values()))
            req_id = self._send_rpc("thread/unsubscribe", {"threadId": thread_id})
            self._wait_for_response(req_id, timeout=10)
            return "".join(reasoning_chunks).strip(), text.strip()
        except Exception:
            # Drop both process and queue on any protocol failure or timeout.
            self._shutdown_process()
            raise
        finally:
            self._lock.release()


_CLIENT = CodexAppServerClient()
atexit.register(_CLIENT.close)


def complete(
    config: Mapping[str, str],
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    *,
    on_thinking_delta: Callable[[str], None] | None = None,
    on_reply_delta: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    binary = _discover_codex_binary()
    if not binary:
        raise AIConnectionError(
            "CODEX_CLI_NOT_FOUND",
            "未在本机找到 Codex CLI，请确认已安装 OpenAI Codex 或切换其他连接方式。",
            status_code=422,
        )
    prompt = _format_cli_prompt(messages, tools)
    effort = str(config.get("reasoning_effort") or "high").strip().lower()
    if effort not in VALID_REASONING_EFFORTS:
        effort = "high"

    def _handle_json_stream(accumulated_json: str) -> None:
        if on_thinking_delta is not None:
            summary = _extract_partial_json_string_field(accumulated_json, "thinking")
            if summary:
                on_thinking_delta(summary)
        if on_reply_delta is not None:
            reply = _extract_partial_json_string_field(accumulated_json, "reply")
            if reply:
                on_reply_delta(reply)

    try:
        _, raw_out = _CLIENT.run_turn(
            binary=binary,
            model=config["model"],
            effort=effort,
            prompt=prompt,
            output_schema=_CLI_STEP_SCHEMA,
            on_text_delta=_handle_json_stream,
            timeout=float(DEFAULT_TIMEOUT_SECONDS),
        )
    except AIConnectionError:
        raise
    except TimeoutError as exc:
        raise AIConnectionError(
            "CODEX_CLI_TIMEOUT", "本机 Codex 响应超时，请稍后重试。", status_code=504,
        ) from exc
    except (OSError, RuntimeError) as exc:
        raise AIConnectionError(
            "CODEX_CLI_ERROR",
            "本机 Codex 连接失败，请检查家具项目的独立登录、模型设置和网络。",
            status_code=502,
        ) from exc
    if not raw_out:
        raise AIConnectionError("CODEX_EMPTY_OUTPUT", "本机 Codex 未返回结果", status_code=502)
    try:
        parsed = json.loads(raw_out)
    except json.JSONDecodeError as exc:
        raise AIConnectionError("CODEX_INVALID_JSON", "Codex 返回无效 JSON", status_code=502) from exc
    if not isinstance(parsed, dict):
        raise AIConnectionError("CODEX_INVALID_JSON", "Codex 返回结构不是对象", status_code=502)
    if (
        not isinstance(parsed.get("thinking"), str)
        or not isinstance(parsed.get("reply"), str)
        or not isinstance(parsed.get("tool_calls"), list)
        or any(
            not isinstance(call, dict)
            or not isinstance(call.get("name"), str)
            or not isinstance(call.get("arguments_json"), str)
            for call in parsed.get("tool_calls", [])
        )
    ):
        raise AIConnectionError("CODEX_INVALID_JSON", "Codex 返回结构不符合对话协议", status_code=502)
    return _normalize_cli_step_output(parsed)
