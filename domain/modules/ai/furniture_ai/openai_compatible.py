"""OpenAI 兼容 Chat Completions 的 HTTP 适配。"""
from __future__ import annotations
import json
from typing import Any, Callable, Mapping
from urllib import error as urllib_error
from urllib import request as urllib_request
from .contracts import AIConnectionError, DEFAULT_TIMEOUT_SECONDS
from .cli_protocol import _is_localhost_url, _extract_thinking_tags


_LOCAL_NO_PROXY_OPENER = urllib_request.build_opener(
    urllib_request.ProxyHandler({})
)


_DEFAULT_OPENER = urllib_request.build_opener()


def _resolve_chat_completions_url(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/chat/completions"):
        return trimmed
    for suffix in ("/v1", "/v1beta/openai", "/v4", "/compatible-mode/v1"):
        if trimmed.endswith(suffix):
            return f"{trimmed}/chat/completions"
    return f"{trimmed}/v1/chat/completions"


def _http_post_json(
    url: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib_request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    opener = _LOCAL_NO_PROXY_OPENER if _is_localhost_url(url) else _DEFAULT_OPENER
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = str(exc)
        raise AIConnectionError(
            "LLM_HTTP_ERROR",
            f"大模型接口返回 HTTP {exc.code}：{detail[:400]}",
            status_code=502,
        ) from exc
    except urllib_error.URLError as exc:
        raise AIConnectionError(
            "LLM_CONNECTION_ERROR",
            f"无法连接大模型接口（{url}）：{exc.reason}",
            status_code=502,
        ) from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AIConnectionError(
            "LLM_INVALID_JSON",
            f"大模型接口返回的不是合法 JSON：{raw[:200]}",
            status_code=502,
        ) from exc
    if not isinstance(parsed, dict):
        raise AIConnectionError(
            "LLM_INVALID_PAYLOAD",
            "大模型接口响应顶层不是 JSON 对象",
            status_code=502,
        )
    return parsed


def complete(
    config: Mapping[str, str],
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    *,
    on_thinking_delta: Callable[[str], None] | None = None,
    on_reply_delta: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    url = _resolve_chat_completions_url(config["base_url"])
    api_key = config["api_key"] or ("ollama" if _is_localhost_url(url) else "")
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload: dict[str, Any] = {
        "model": config["model"],
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
    }
    effort = str(config.get("reasoning_effort") or "none").strip().lower()
    if effort in {"minimal", "low", "medium", "high", "xhigh"}:
        payload["reasoning_effort"] = effort
    data = _http_post_json(url, headers, payload)
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AIConnectionError(
            "LLM_EMPTY_CHOICES",
            f"大模型未返回 choices：{json.dumps(data, ensure_ascii=False)[:300]}",
            status_code=502,
        )
    first = choices[0]
    message = first.get("message") if isinstance(first, dict) else None
    if not isinstance(message, dict):
        raise AIConnectionError("LLM_MISSING_MESSAGE", "大模型响应缺少 message 字段", status_code=502)
    raw_content = str(message.get("content") or "").strip()
    tag_thinking, content = _extract_thinking_tags(raw_content)
    native_reasoning = str(
        message.get("reasoning_content")
        or message.get("reasoning")
        or message.get("thought")
        or ""
    ).strip()
    thinking_parts = [p for p in (native_reasoning, tag_thinking) if p]
    thinking = "\n\n".join(thinking_parts)
    if on_thinking_delta and thinking:
        on_thinking_delta(thinking)
    if on_reply_delta and content:
        on_reply_delta(content)
    raw_tool_calls = message.get("tool_calls")
    normalized_calls: list[dict[str, Any]] = []
    if isinstance(raw_tool_calls, list):
        for idx, tc in enumerate(raw_tool_calls):
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function")
            if not isinstance(fn, dict):
                continue
            name = str(fn.get("name") or "").strip()
            if not name:
                continue
            call_id = str(tc.get("id") or f"call_{idx + 1}")
            arguments = fn.get("arguments")
            if isinstance(arguments, dict):
                arg_str = json.dumps(arguments, ensure_ascii=False)
            else:
                arg_str = str(arguments or "{}")
            normalized_calls.append(
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": arg_str},
                }
            )
    return {"thinking": thinking, "content": content, "tool_calls": normalized_calls}
