"""AGY CLI 的模型参数和结构化消息适配。"""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Callable, Mapping
from .contracts import AIConnectionError, DEFAULT_TIMEOUT_SECONDS
from .discovery import _discover_agy_binary
from .cli_protocol import _CLI_STEP_SCHEMA, _format_cli_prompt, _normalize_cli_step_output, _extract_thinking_tags


_AGY_EFFORT_SUFFIXES = ("low", "medium", "high")


def _sync_agy_model_and_effort(model: str, effort: str) -> tuple[str, str]:
    """AGY CLI 的 Gemini 模型 ID 自带档位后缀（如 gemini-4-argon-high），将模型后缀与 --effort 同步。"""
    cleaned_model = str(model or "").strip()
    cleaned_effort = str(effort or "high").strip().lower()
    if cleaned_effort not in {"low", "medium", "high", "xhigh", "max"}:
        cleaned_effort = "high"

    for suffix in _AGY_EFFORT_SUFFIXES:
        token = f"-{suffix}"
        if cleaned_model.endswith(token):
            base_name = cleaned_model[: -len(token)]
            if base_name.startswith("gemini-"):
                target_suffix = (
                    cleaned_effort
                    if cleaned_effort in _AGY_EFFORT_SUFFIXES
                    else "high"
                )
                return f"{base_name}-{target_suffix}", cleaned_effort
            break
    return cleaned_model, cleaned_effort


def complete(
    config: Mapping[str, str],
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    *,
    on_thinking_delta: Callable[[str], None] | None = None,
    on_reply_delta: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    binary = _discover_agy_binary()
    if not binary:
        raise AIConnectionError(
            "AGY_CLI_NOT_FOUND",
            "未在本机找到 AGY CLI，请确认已安装 Antigravity CLI 或切换其他连接方式。",
            status_code=422,
        )
    prompt = _format_cli_prompt(messages, tools)
    temp_dir = Path(tempfile.mkdtemp(prefix="furniture_agy_"))
    schema_file = temp_dir / "step_schema.json"
    try:
        schema_file.write_text(
            json.dumps(_CLI_STEP_SCHEMA, ensure_ascii=False),
            encoding="utf-8",
        )
        resolved_model, effort = _sync_agy_model_and_effort(
            config["model"],
            config.get("reasoning_effort") or "high",
        )
        cmd = [
            binary,
            "--print",
            "--input-format",
            "text",
            "--output-format",
            "json",
            "--disable-slash-commands",
            "--json-schema",
            str(schema_file),
            "--model",
            resolved_model,
            "--effort",
            effort,
        ]
        proc = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        stdout = (proc.stdout or "").strip()
        if proc.returncode != 0 and not stdout:
            detail = (proc.stderr or "").strip()
            raise AIConnectionError(
                "AGY_CLI_ERROR",
                f"本机 AGY CLI 执行失败（code {proc.returncode}）：{detail[:360]}",
                status_code=502,
            )
        outer = json.loads(stdout)
        if isinstance(outer, dict):
            structured = outer.get("structured_output")
            if isinstance(structured, dict):
                norm = _normalize_cli_step_output(structured)
                if on_thinking_delta and norm["thinking"]:
                    on_thinking_delta(norm["thinking"])
                if on_reply_delta and norm["content"]:
                    on_reply_delta(norm["content"])
                return norm
            if isinstance(structured, str) and structured.strip():
                try:
                    inner = json.loads(structured)
                    if isinstance(inner, dict):
                        norm = _normalize_cli_step_output(inner)
                        if on_thinking_delta and norm["thinking"]:
                            on_thinking_delta(norm["thinking"])
                        if on_reply_delta and norm["content"]:
                            on_reply_delta(norm["content"])
                        return norm
                except json.JSONDecodeError:
                    pass
            resp_text = str(outer.get("response") or "").strip()
            for line in reversed(resp_text.splitlines()):
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        candidate = json.loads(line)
                        if isinstance(candidate, dict) and (
                            "tool_calls" in candidate or "reply" in candidate or "thinking" in candidate
                        ):
                            norm = _normalize_cli_step_output(candidate)
                            if on_thinking_delta and norm["thinking"]:
                                on_thinking_delta(norm["thinking"])
                            if on_reply_delta and norm["content"]:
                                on_reply_delta(norm["content"])
                            return norm
                    except json.JSONDecodeError:
                        continue
            tag_thinking, clean_resp = _extract_thinking_tags(resp_text)
            if on_thinking_delta and tag_thinking:
                on_thinking_delta(tag_thinking)
            if on_reply_delta and clean_resp:
                on_reply_delta(clean_resp)
            return {"thinking": tag_thinking, "content": clean_resp, "tool_calls": []}
        raise AIConnectionError("AGY_INVALID_OUTPUT", "AGY CLI 返回格式无法解析", status_code=502)
    except subprocess.TimeoutExpired as exc:
        raise AIConnectionError(
            "AGY_CLI_TIMEOUT",
            f"本机 AGY CLI 响应超时（>{DEFAULT_TIMEOUT_SECONDS}s）",
            status_code=504,
        ) from exc
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
