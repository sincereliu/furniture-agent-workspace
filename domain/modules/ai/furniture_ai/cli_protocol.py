"""CLI 结构化输出与兼容消息协议；工具名称和 Schema 由调用方提供。"""
from __future__ import annotations
import json
from typing import Any, Mapping
from urllib import parse as urllib_parse


_CLI_STEP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "thinking": {
            "type": "string",
            "description": "给用户看的简短进度摘要：本步正在检查或执行什么，不输出内部推理过程",
        },
        "reply": {
            "type": "string",
            "description": "当无需再调用工具时，给用户的中文回复；若本步需要先调用工具可留空字符串",
        },
        "tool_calls": {
            "type": "array",
            "description": "本步需要调用的已注册工具列表；若无需调用工具则返回空数组 []",
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "工具名称，必须是 allowed_tools 中的合法工具名",
                    },
                    "arguments_json": {
                        "type": "string",
                        "description": "传给该工具的 JSON 对象字符串",
                    },
                },
                "required": ["name", "arguments_json"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["thinking", "reply", "tool_calls"],
    "additionalProperties": False,
}


def _is_localhost_url(url: str) -> bool:
    try:
        parsed = urllib_parse.urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def _extract_thinking_tags(raw_text: str) -> tuple[str, str]:
    """从文本中分离 `<think>...</think>` 思考块与正文（确定性标签剥离）。"""
    text = str(raw_text or "").strip()
    thoughts: list[str] = []
    while "<think>" in text and "</think>" in text:
        start = text.find("<think>")
        end = text.find("</think>", start + 7)
        if end == -1:
            break
        thought_chunk = text[start + 7 : end].strip()
        if thought_chunk:
            thoughts.append(thought_chunk)
        text = (text[:start] + text[end + 8 :]).strip()
    return "\n\n".join(thoughts), text


def _extract_partial_json_string_field(raw_json: str, field_name: str) -> str:
    """从正在流式生成的 JSON 文本前缀中实时提取指定字符串字段（如 thinking / reply）的已生成内容。"""
    key_token = f'"{field_name}"'
    idx = raw_json.find(key_token)
    if idx == -1:
        return ""
    colon_idx = raw_json.find(":", idx + len(key_token))
    if colon_idx == -1:
        return ""
    pos = colon_idx + 1
    n = len(raw_json)
    while pos < n and raw_json[pos] in " \t\r\n":
        pos += 1
    if pos >= n or raw_json[pos] != '"':
        return ""
    pos += 1
    out: list[str] = []
    while pos < n:
        ch = raw_json[pos]
        if ch == '"':
            break
        if ch == "\\":
            pos += 1
            if pos >= n:
                break
            esc = raw_json[pos]
            if esc == "n":
                out.append("\n")
            elif esc == "r":
                out.append("\r")
            elif esc == "t":
                out.append("\t")
            elif esc in {'"', "\\", "/"}:
                out.append(esc)
            elif esc == "u" and pos + 4 < n:
                hex_part = raw_json[pos + 1 : pos + 5]
                try:
                    out.append(chr(int(hex_part, 16)))
                    pos += 4
                except ValueError:
                    out.append(esc)
            else:
                out.append(esc)
        else:
            out.append(ch)
        pos += 1
    return "".join(out).strip()


def _format_cli_prompt(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> str:
    """将对话历史与可用工具 Schema 组装为供本机 CLI 结构化输出的提示词。"""
    tool_specs = [
        t["function"]
        for t in tools
        if isinstance(t, dict) and isinstance(t.get("function"), dict)
    ]
    parts: list[str] = [
        "【重要执行要求】",
        "不要执行任何终端命令、不要直接读写磁盘文件。",
        "你只能通过返回符合 JSON Schema 的 `{ \"thinking\": \"...\", \"reply\": \"...\", \"tool_calls\": [...] }` 来回答用户或调用下方定义的工具。",
        "- 在 `thinking` 字段中提供简短的操作进度摘要，不输出内部推理过程。",
        "- 如果需要调用工具，请在 `tool_calls` 数组中填入 `{\"name\": \"工具名\", \"arguments_json\": \"JSON字符串\"}`，此时 `reply` 可留空字符串。",
        "- 如果工具已经执行完毕或当前只需回复用户，请将 `tool_calls` 设为空数组 `[]`，并在 `reply` 中填入给用户的中文回复。",
        f"\n--- 可用工具定义 (JSON Schema) ---\n{json.dumps(tool_specs, ensure_ascii=False)}",
        "\n--- 对话上下文与工具执行记录 ---",
    ]
    for msg in messages:
        role = msg.get("role")
        if role == "system":
            parts.append(f"[System]\n{msg.get('content', '')}")
        elif role == "user":
            parts.append(f"[User]\n{msg.get('content', '')}")
        elif role == "assistant":
            if msg.get("thinking"):
                parts.append(f"[Assistant Thinking]\n{msg['thinking']}")
            tcs = msg.get("tool_calls") or []
            if tcs:
                parts.append(f"[Assistant Tool Calls]\n{json.dumps(tcs, ensure_ascii=False)}")
            if msg.get("content"):
                parts.append(f"[Assistant]\n{msg['content']}")
        elif role == "tool":
            parts.append(
                f"[Tool Result: {msg.get('name')} (id={msg.get('tool_call_id')})]\n{msg.get('content', '')}"
            )
    return "\n\n".join(parts)


def _normalize_cli_step_output(parsed: Mapping[str, Any]) -> dict[str, Any]:
    thinking = str(parsed.get("thinking") or "").strip()
    raw_reply = str(parsed.get("reply") or "").strip()
    tag_thinking, reply = _extract_thinking_tags(raw_reply)
    if tag_thinking and tag_thinking not in thinking:
        thinking = f"{thinking}\n\n{tag_thinking}".strip() if thinking else tag_thinking
    raw_calls = parsed.get("tool_calls")
    normalized_calls: list[dict[str, Any]] = []
    if isinstance(raw_calls, list):
        for idx, tc in enumerate(raw_calls):
            if not isinstance(tc, dict):
                continue
            name = str(tc.get("name") or "").strip()
            if not name:
                continue
            args_str = str(tc.get("arguments_json") or "{}")
            normalized_calls.append(
                {
                    "id": f"cli_call_{idx + 1}",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": args_str,
                    },
                }
            )
    return {"thinking": thinking, "content": reply, "tool_calls": normalized_calls}
