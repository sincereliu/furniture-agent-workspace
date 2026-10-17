"""网页端 AI 对话与本机大模型配置桥接。

职责边界（遵循 llm-runtime-boundary.md）：
- 本模块只负责 `structured_protocol` 与 `side_effect`：
  1. 读写本机大模型连接配置（`store/_llm_config.json`，支持本机已登录 OAuth CLI：`codex_cli` / `agy_cli`，
     以及标准 `openai_compatible` / `anthropic` API 接口）；
  2. 读写项目对话历史（`store/<project_id>/chat.json`）；
  3. 按项目当前阶段从磁盘读取对应 `SKILL.md` / `references/` 与项目结构化快照，组装上下文；
  4. 调用用户所选的大模型通道（本机 CLI 或 HTTP API），将模型返回的 `tool_calls` 原样交由
     `FurnitureToolSession.call()` 执行。
- 不在 Python 中解析自然语言意图、不维护关键词/同义词表、不补构造默认值、不直接读取用户私密 OAuth Token 文件。
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Callable, Mapping
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
import uuid

from .agent_tool_schema import openai_tools
from .agent_tools import FurnitureToolSession
from .workflow_orchestrator import FurnitureOrchestrator
from .workflow_store import JsonProjectStore

LLM_CONFIG_FILENAME = "_llm_config.json"
CHAT_HISTORY_FILENAME = "chat.json"
MAX_CHAT_HISTORY_MESSAGES = 40
MAX_TOOL_ROUNDS = 6
DEFAULT_TIMEOUT_SECONDS = 240

VALID_PROVIDERS = {
    "codex_cli",
    "agy_cli",
    "openai_compatible",
    "anthropic",
}
VALID_REASONING_EFFORTS = {
    "none",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
}
_AGY_EFFORT_SUFFIXES = ("low", "medium", "high")
_ANTHROPIC_THINKING_BUDGETS = {
    "low": 2048,
    "medium": 8192,
    "high": 16384,
    "max": 31999,
}


def _sync_agy_model_and_effort(model: str, effort: str) -> tuple[str, str]:
    """AGY CLI 的模型 ID 自带档位后缀（如 gemini-4-argon-high），将模型后缀与 --effort 同步。"""
    cleaned_model = str(model or "").strip()
    cleaned_effort = str(effort or "high").strip().lower()
    if cleaned_effort not in {"low", "medium", "high", "xhigh", "max"}:
        cleaned_effort = "high"

    for suffix in _AGY_EFFORT_SUFFIXES:
        token = f"-{suffix}"
        if cleaned_model.endswith(token):
            base_name = cleaned_model[: -len(token)]
            # gpt-oss-120b-medium 等仅单档位的模型保持原名
            if base_name.startswith(("gemini-", "claude-")):
                target_suffix = (
                    cleaned_effort
                    if cleaned_effort in _AGY_EFFORT_SUFFIXES
                    else "high"
                )
                return f"{base_name}-{target_suffix}", cleaned_effort
            break
    return cleaned_model, cleaned_effort

_CLI_STEP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "reply": {
            "type": "string",
            "description": "当无需再调用工具时，给用户的中文回复；若本步需要先调用工具可留空字符串",
        },
        "tool_calls": {
            "type": "array",
            "description": "本步需要调用的 furniture_* 工具列表；若无需调用工具则返回空数组 []",
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "工具名称，必须是 allowed_tools 中的合法工具名",
                    },
                    "arguments_json": {
                        "type": "string",
                        "description": "传给该工具的 JSON 对象字符串，如 '{\"project_id\":\"...\",\"stage\":\"layout_plan\"}'",
                    },
                },
                "required": ["name", "arguments_json"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["reply", "tool_calls"],
    "additionalProperties": False,
}

_LOCAL_NO_PROXY_OPENER = urllib_request.build_opener(
    urllib_request.ProxyHandler({})
)
_DEFAULT_OPENER = urllib_request.build_opener()


class WebChatError(RuntimeError):
    """网页对话调用或配置错误。"""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _llm_config_path(store_root: str | Path) -> Path:
    return Path(store_root) / LLM_CONFIG_FILENAME


def _chat_history_path(store_root: str | Path, project_id: str) -> Path:
    return JsonProjectStore(store_root).project_dir(project_id) / CHAT_HISTORY_FILENAME


def _mask_api_key(api_key: str) -> str:
    cleaned = api_key.strip()
    if not cleaned:
        return ""
    if len(cleaned) <= 8:
        return "*" * len(cleaned)
    return f"{cleaned[:4]}...{cleaned[-4:]}"


def _is_localhost_url(url: str) -> bool:
    try:
        parsed = urllib_parse.urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def _discover_codex_binary() -> str | None:
    """查找本机已安装的官方 Codex CLI 可执行文件（不读取任何认证文件）。"""
    on_path = shutil.which("codex")
    if on_path:
        return on_path
    try:
        codex_bin_root = Path.home() / "AppData" / "Local" / "OpenAI" / "Codex" / "bin"
        if codex_bin_root.is_dir():
            candidates = sorted(
                codex_bin_root.rglob("codex.exe"),
                key=lambda p: p.stat().st_mtime if p.exists() else 0,
                reverse=True,
            )
            if candidates:
                return str(candidates[0])
    except OSError:
        return None
    return None


def _discover_agy_binary() -> str | None:
    """查找本机已安装的官方 Antigravity (AGY / Gemini) CLI 可执行文件。"""
    on_path = shutil.which("agy")
    if on_path:
        return on_path
    try:
        local_agy = Path.home() / "AppData" / "Local" / "agy" / "bin" / "agy.EXE"
        if local_agy.is_file():
            return str(local_agy)
    except OSError:
        return None
    return None


def load_llm_config(store_root: str | Path) -> dict[str, str]:
    """读取本机大模型配置；若未落盘则优先自动选用本机已安装的 OAuth CLI。"""
    path = _llm_config_path(store_root)
    saved: dict[str, Any] = {}
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                saved = raw
        except (OSError, json.JSONDecodeError):
            saved = {}

    codex_bin = _discover_codex_binary()
    agy_bin = _discover_agy_binary()

    default_provider = "openai_compatible"
    default_model = ""
    if not saved and not os.environ.get("FURNITURE_LLM_PROVIDER"):
        if codex_bin:
            default_provider = "codex_cli"
            default_model = "gpt-6.1-sol"
        elif agy_bin:
            default_provider = "agy_cli"
            default_model = "gemini-3.8-flash-high"

    provider = str(
        saved.get("provider")
        or os.environ.get("FURNITURE_LLM_PROVIDER")
        or default_provider
    ).strip()
    if provider not in VALID_PROVIDERS:
        provider = default_provider

    if provider == "codex_cli":
        base_url = "local://codex-cli"
    elif provider == "agy_cli":
        base_url = "local://agy-cli"
    else:
        base_url = str(
            saved.get("base_url")
            or os.environ.get("FURNITURE_LLM_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or (
                "https://api.anthropic.com/v1"
                if provider == "anthropic"
                else "https://api.openai.com/v1"
            )
        ).strip()

    api_key = str(
        saved.get("api_key")
        or os.environ.get("FURNITURE_LLM_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or ""
    ).strip()

    fallback_model = (
        "gpt-6.1-sol"
        if provider == "codex_cli"
        else "gemini-3.8-flash-high"
        if provider == "agy_cli"
        else default_model
    )
    model = str(
        saved.get("model")
        or os.environ.get("FURNITURE_LLM_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or fallback_model
    ).strip()

    reasoning_effort = str(
        saved.get("reasoning_effort")
        or os.environ.get("FURNITURE_LLM_REASONING_EFFORT")
        or "high"
    ).strip().lower()
    if reasoning_effort not in VALID_REASONING_EFFORTS:
        reasoning_effort = "high"

    if provider == "agy_cli":
        model, reasoning_effort = _sync_agy_model_and_effort(model, reasoning_effort)

    return {
        "provider": provider,
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "reasoning_effort": reasoning_effort,
    }


def public_llm_config(store_root: str | Path) -> dict[str, Any]:
    """返回给前端页面的脱敏配置状态与本机 CLI 可用性。"""
    cfg = load_llm_config(store_root)
    provider = cfg["provider"]
    codex_available = _discover_codex_binary() is not None
    agy_available = _discover_agy_binary() is not None
    has_key = bool(cfg["api_key"])

    if provider == "codex_cli":
        configured = bool(codex_available and cfg["model"])
    elif provider == "agy_cli":
        configured = bool(agy_available and cfg["model"])
    else:
        configured = bool(
            cfg["base_url"]
            and cfg["model"]
            and (has_key or _is_localhost_url(cfg["base_url"]))
        )

    return {
        "provider": provider,
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "reasoning_effort": cfg["reasoning_effort"],
        "has_api_key": has_key,
        "api_key_masked": _mask_api_key(cfg["api_key"]),
        "configured": configured,
        "local_cli": {
            "codex_available": codex_available,
            "agy_available": agy_available,
        },
    }


def save_llm_config(
    store_root: str | Path,
    *,
    provider: str = "openai_compatible",
    base_url: str = "",
    model: str,
    reasoning_effort: str = "high",
    api_key: str | None = None,
    clear_api_key: bool = False,
) -> dict[str, Any]:
    """保存本机大模型配置到 `store/_llm_config.json`。"""
    normalized_provider = str(provider or "openai_compatible").strip()
    if normalized_provider not in VALID_PROVIDERS:
        raise ValueError(
            f"provider must be one of: {', '.join(sorted(VALID_PROVIDERS))}"
        )
    normalized_model = str(model or "").strip()
    if not normalized_model:
        raise ValueError("model must not be empty")
    normalized_effort = str(reasoning_effort or "high").strip().lower()
    if normalized_effort not in VALID_REASONING_EFFORTS:
        raise ValueError(
            f"reasoning_effort must be one of: {', '.join(sorted(VALID_REASONING_EFFORTS))}"
        )

    if normalized_provider == "codex_cli":
        normalized_url = "local://codex-cli"
    elif normalized_provider == "agy_cli":
        normalized_url = "local://agy-cli"
        normalized_model, normalized_effort = _sync_agy_model_and_effort(
            normalized_model, normalized_effort
        )
    else:
        normalized_url = str(base_url or "").strip()
        if not normalized_url:
            raise ValueError("base_url must not be empty")
        parsed = urllib_parse.urlparse(normalized_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be a valid http(s) URL")

    current = load_llm_config(store_root)
    if clear_api_key:
        final_key = ""
    elif api_key is not None and api_key.strip():
        final_key = api_key.strip()
    else:
        final_key = current["api_key"]

    root = Path(store_root)
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "provider": normalized_provider,
        "base_url": normalized_url,
        "model": normalized_model,
        "reasoning_effort": normalized_effort,
        "api_key": final_key,
        "updated_at": _utc_now_iso(),
    }
    _llm_config_path(root).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return public_llm_config(root)


def load_chat_history(store_root: str | Path, project_id: str) -> list[dict[str, Any]]:
    """读取项目的历史对话消息列表。"""
    path = _chat_history_path(store_root, project_id)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    messages = raw.get("messages") if isinstance(raw, dict) else None
    if not isinstance(messages, list):
        return []
    return [msg for msg in messages if isinstance(msg, dict)]


def save_chat_history(
    store_root: str | Path,
    project_id: str,
    messages: list[dict[str, Any]],
) -> None:
    """保存项目的历史对话消息列表。"""
    path = _chat_history_path(store_root, project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    trimmed = messages[-MAX_CHAT_HISTORY_MESSAGES:]
    payload = {
        "project_id": project_id,
        "updated_at": _utc_now_iso(),
        "messages": trimmed,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clear_chat_history(store_root: str | Path, project_id: str) -> None:
    """清空项目的历史对话消息。"""
    path = _chat_history_path(store_root, project_id)
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            pass


def _read_doc_if_exists(workspace_root: Path, relative_path: str) -> str:
    path = workspace_root / relative_path
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _stage_doc_paths(project_snapshot: Mapping[str, Any]) -> list[str]:
    """按当前阶段与下一阶段动态选择要挂载的领域 Skill 文档。"""
    docs: list[str] = [
        "domain/skills/cad-generated/references/agent-tool-contract.md",
        "domain/skills/layout-plan/SKILL.md",
        "domain/skills/layout-plan/references/spatial-layout-rules.md",
    ]
    current_stage = str(project_snapshot.get("current_stage") or "")
    next_stage = str(project_snapshot.get("next_stage") or "")
    approved = set(project_snapshot.get("approved_stages") or [])
    active = {current_stage, next_stage}

    if "layout_plan" in approved or "panel_plan" in active:
        docs.extend(
            [
                "domain/skills/panel-plan/SKILL.md",
                "domain/skills/panel-plan/references/panel-proposal-contract.md",
                "domain/skills/panel-plan/references/sheet-stock-catalog.md",
            ]
        )
    if "manufacture_plan" in active:
        docs.extend(
            [
                "domain/skills/manufacture-plan/SKILL.md",
                "domain/skills/manufacture-plan/references/manufacturing-rules.md",
            ]
        )
    if "feature_tree_planned" in active:
        docs.append("domain/skills/feature-tree/SKILL.md")
    if "cad_generated" in active:
        docs.append("domain/skills/cad-generated/TOOL.md")
    if "delivery_validated" in active:
        docs.append("domain/skills/delivery-validated/SKILL.md")
    return docs


def build_system_prompt(
    workspace_root: Path,
    project_snapshot: Mapping[str, Any],
) -> str:
    """将对应阶段的 SKILL.md 与当前项目快照拼装为 System Prompt。"""
    sections: list[str] = [
        "你是本仓库内置的家具智能体（Furniture Agent），正在网页工作台右侧与用户对话。",
        "你的所有项目写操作必须通过注册的 `furniture_*` 工具完成，严格遵守下述交互工具面与阶段技能规则。",
        f"当前正在操作的项目 ID 为：`{project_snapshot.get('id')}`（调用任何需要 `project_id` 的工具时必须传入该值）。",
        "请使用简洁、清晰的中文回答。当工具修改了布局或生成了板件草稿时，左侧 3D 视图会自动刷新，你可以在回复中提醒用户直接在左侧画面或点进单柜「板件规划」查看。",
    ]
    for rel_path in _stage_doc_paths(project_snapshot):
        content = _read_doc_if_exists(workspace_root, rel_path)
        if content:
            sections.append(f"--- 文档：{rel_path} ---\n{content}")

    snapshot_json = json.dumps(project_snapshot, ensure_ascii=False, indent=2)
    sections.append(f"--- 当前项目实时快照 ---\n```json\n{snapshot_json}\n```")
    return "\n\n".join(sections)


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
        "你只能通过返回符合 JSON Schema 的 `{ \"reply\": \"...\", \"tool_calls\": [...] }` 来回答用户或调用下方列出的 `furniture_*` 工具。",
        "- 如果需要调用工具推進状态（如 `furniture_confirm_stage`、`furniture_run_next`、`furniture_revise_layout` 等），请在 `tool_calls` 数组中填入 `{\"name\": \"工具名\", \"arguments_json\": \"JSON字符串\"}`，此时 `reply` 可留空字符串。",
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
    reply = str(parsed.get("reply") or "").strip()
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
    return {"content": reply, "tool_calls": normalized_calls}


def _call_codex_cli(
    config: Mapping[str, str],
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    binary = _discover_codex_binary()
    if not binary:
        raise WebChatError(
            "CODEX_CLI_NOT_FOUND",
            "未在本机找到 Codex CLI，请确认已安装 OpenAI Codex 或切换其他连接方式。",
            status_code=422,
        )
    prompt = _format_cli_prompt(messages, tools)
    temp_dir = Path(tempfile.mkdtemp(prefix="furniture_codex_"))
    schema_file = temp_dir / "step_schema.json"
    out_file = temp_dir / "step_out.json"
    try:
        schema_file.write_text(
            json.dumps(_CLI_STEP_SCHEMA, ensure_ascii=False),
            encoding="utf-8",
        )
        effort = str(config.get("reasoning_effort") or "high").strip().lower()
        if effort not in {"none", "minimal", "low", "medium", "high", "xhigh"}:
            effort = "high"
        cmd = [
            binary,
            "exec",
            "--ephemeral",
            "-s",
            "read-only",
            "--skip-git-repo-check",
            "--ignore-rules",
            "-m",
            config["model"],
            "--output-schema",
            str(schema_file),
            "-o",
            str(out_file),
        ]
        if effort != "none":
            cmd.extend(["-c", f'model_reasoning_effort="{effort}"'])
        cmd.append("-")
        proc = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        if proc.returncode != 0 and not out_file.is_file():
            detail = (proc.stderr or proc.stdout or "").strip()
            raise WebChatError(
                "CODEX_CLI_ERROR",
                f"本机 Codex CLI 执行失败（code {proc.returncode}）：{detail[:360]}",
                status_code=502,
            )
        raw_out = out_file.read_text(encoding="utf-8").strip() if out_file.is_file() else ""
        if not raw_out:
            raise WebChatError(
                "CODEX_EMPTY_OUTPUT",
                "本机 Codex CLI 未返回结果",
                status_code=502,
            )
        parsed = json.loads(raw_out)
        if not isinstance(parsed, dict):
            raise WebChatError("CODEX_INVALID_JSON", "Codex CLI 返回结构不是对象", status_code=502)
        return _normalize_cli_step_output(parsed)
    except subprocess.TimeoutExpired as exc:
        raise WebChatError(
            "CODEX_CLI_TIMEOUT",
            f"本机 Codex CLI 响应超时（>{DEFAULT_TIMEOUT_SECONDS}s）",
            status_code=504,
        ) from exc
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _call_agy_cli(
    config: Mapping[str, str],
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    binary = _discover_agy_binary()
    if not binary:
        raise WebChatError(
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
            raise WebChatError(
                "AGY_CLI_ERROR",
                f"本机 AGY CLI 执行失败（code {proc.returncode}）：{detail[:360]}",
                status_code=502,
            )
        outer = json.loads(stdout)
        if isinstance(outer, dict):
            structured = outer.get("structured_output")
            if isinstance(structured, dict):
                return _normalize_cli_step_output(structured)
            if isinstance(structured, str) and structured.strip():
                try:
                    inner = json.loads(structured)
                    if isinstance(inner, dict):
                        return _normalize_cli_step_output(inner)
                except json.JSONDecodeError:
                    pass
            resp_text = str(outer.get("response") or "").strip()
            for line in reversed(resp_text.splitlines()):
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        candidate = json.loads(line)
                        if isinstance(candidate, dict) and (
                            "tool_calls" in candidate or "reply" in candidate
                        ):
                            return _normalize_cli_step_output(candidate)
                    except json.JSONDecodeError:
                        continue
            return {"content": resp_text, "tool_calls": []}
        raise WebChatError("AGY_INVALID_OUTPUT", "AGY CLI 返回格式无法解析", status_code=502)
    except subprocess.TimeoutExpired as exc:
        raise WebChatError(
            "AGY_CLI_TIMEOUT",
            f"本机 AGY CLI 响应超时（>{DEFAULT_TIMEOUT_SECONDS}s）",
            status_code=504,
        ) from exc
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _resolve_chat_completions_url(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/chat/completions"):
        return trimmed
    for suffix in ("/v1", "/v1beta/openai", "/v4", "/compatible-mode/v1"):
        if trimmed.endswith(suffix):
            return f"{trimmed}/chat/completions"
    return f"{trimmed}/v1/chat/completions"


def _resolve_anthropic_messages_url(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/messages"):
        return trimmed
    if trimmed.endswith("/v1"):
        return f"{trimmed}/messages"
    return f"{trimmed}/v1/messages"


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
        raise WebChatError(
            "LLM_HTTP_ERROR",
            f"大模型接口返回 HTTP {exc.code}：{detail[:400]}",
            status_code=502,
        ) from exc
    except urllib_error.URLError as exc:
        raise WebChatError(
            "LLM_CONNECTION_ERROR",
            f"无法连接大模型接口（{url}）：{exc.reason}",
            status_code=502,
        ) from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WebChatError(
            "LLM_INVALID_JSON",
            f"大模型接口返回的不是合法 JSON：{raw[:200]}",
            status_code=502,
        ) from exc
    if not isinstance(parsed, dict):
        raise WebChatError(
            "LLM_INVALID_PAYLOAD",
            "大模型接口响应顶层不是 JSON 对象",
            status_code=502,
        )
    return parsed


def _call_openai_compatible(
    config: Mapping[str, str],
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
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
        raise WebChatError(
            "LLM_EMPTY_CHOICES",
            f"大模型未返回 choices：{json.dumps(data, ensure_ascii=False)[:300]}",
            status_code=502,
        )
    first = choices[0]
    message = first.get("message") if isinstance(first, dict) else None
    if not isinstance(message, dict):
        raise WebChatError("LLM_MISSING_MESSAGE", "大模型响应缺少 message 字段", status_code=502)
    content = str(message.get("content") or "").strip()
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
    return {"content": content, "tool_calls": normalized_calls}


def _call_anthropic(
    config: Mapping[str, str],
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    url = _resolve_anthropic_messages_url(config["base_url"])
    headers = {
        "x-api-key": config["api_key"],
        "anthropic-version": "2023-06-01",
    }
    system_parts: list[str] = []
    anth_messages: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        if role == "system":
            system_parts.append(str(msg.get("content") or ""))
        elif role == "user":
            anth_messages.append({"role": "user", "content": str(msg.get("content") or "")})
        elif role == "assistant":
            blocks: list[dict[str, Any]] = []
            if msg.get("content"):
                blocks.append({"type": "text", "text": str(msg["content"])})
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function") or {}
                try:
                    parsed_input = json.loads(str(fn.get("arguments") or "{}"))
                except json.JSONDecodeError:
                    parsed_input = {}
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.get("id"),
                        "name": fn.get("name"),
                        "input": parsed_input,
                    }
                )
            if blocks:
                anth_messages.append({"role": "assistant", "content": blocks})
        elif role == "tool":
            anth_messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.get("tool_call_id"),
                            "content": str(msg.get("content") or ""),
                        }
                    ],
                }
            )
    anth_tools = [
        {
            "name": t["function"]["name"],
            "description": t["function"].get("description", ""),
            "input_schema": t["function"].get("parameters", {"type": "object"}),
        }
        for t in tools
        if isinstance(t, dict) and isinstance(t.get("function"), dict)
    ]
    effort = str(config.get("reasoning_effort") or "none").strip().lower()
    thinking_budget = _ANTHROPIC_THINKING_BUDGETS.get(effort)
    payload: dict[str, Any] = {
        "model": config["model"],
        "max_tokens": (thinking_budget + 4096) if thinking_budget else 4096,
        "system": "\n\n".join(system_parts),
        "messages": anth_messages,
        "tools": anth_tools,
    }
    if thinking_budget:
        payload["thinking"] = {
            "type": "enabled",
            "budget_tokens": thinking_budget,
        }
    data = _http_post_json(url, headers, payload)
    content_blocks = data.get("content")
    if not isinstance(content_blocks, list):
        raise WebChatError("LLM_MISSING_CONTENT", "Anthropic 响应缺少 content 列表", status_code=502)
    texts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for block in content_blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            texts.append(str(block.get("text") or ""))
        elif btype == "tool_use":
            tool_calls.append(
                {
                    "id": str(block.get("id") or f"call_{len(tool_calls) + 1}"),
                    "type": "function",
                    "function": {
                        "name": str(block.get("name") or ""),
                        "arguments": json.dumps(block.get("input") or {}, ensure_ascii=False),
                    },
                }
            )
    return {"content": "\n".join(texts).strip(), "tool_calls": tool_calls}


def _default_llm_completion(
    config: Mapping[str, str],
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    provider = config.get("provider")
    if provider == "codex_cli":
        return _call_codex_cli(config, messages, tools)
    if provider == "agy_cli":
        return _call_agy_cli(config, messages, tools)
    if provider == "anthropic":
        return _call_anthropic(config, messages, tools)
    return _call_openai_compatible(config, messages, tools)


def get_project_chat_state(
    project_id: str,
    *,
    workspace_root: Path,
    store_root: Path,
) -> dict[str, Any]:
    """获取项目当前的对话历史、本机模型配置状态与项目阶段摘要。"""
    store = JsonProjectStore(store_root)
    orchestrator = FurnitureOrchestrator(
        workspace_root=workspace_root,
        project_store=store,
    )
    session = FurnitureToolSession(orchestrator)
    snap_res = session.call(
        "furniture_get_project",
        {"project_id": project_id, "include_view": True},
    )
    if not snap_res.get("ok"):
        err = snap_res.get("error") or {}
        raise ValueError(str(err.get("message") or f"project not found: {project_id}"))
    return {
        "project_id": project_id,
        "messages": load_chat_history(store_root, project_id),
        "llm": public_llm_config(store_root),
        "project": snap_res["project"],
    }


def send_project_chat_message(
    project_id: str,
    user_message: str,
    *,
    workspace_root: Path,
    store_root: Path,
    llm_caller: Callable[
        [Mapping[str, str], list[dict[str, Any]], list[dict[str, Any]]],
        dict[str, Any],
    ]
    | None = None,
) -> dict[str, Any]:
    """发送一条用户消息，执行大模型 Tool-Calling 闭环并持久化对话记录。"""
    text = str(user_message or "").strip()
    if not text:
        raise ValueError("message must not be empty")

    config = load_llm_config(store_root)
    provider = config["provider"]
    if provider in {"codex_cli", "agy_cli"}:
        if not config["model"]:
            raise WebChatError(
                "LLM_NOT_CONFIGURED",
                "尚未填写模型名称，请先在「模型设置」中确认模型名。",
                status_code=422,
            )
    else:
        if not config["base_url"] or not config["model"]:
            raise WebChatError(
                "LLM_NOT_CONFIGURED",
                "尚未配置大模型接口，请先点击右上角「模型设置」选择本机 OAuth CLI 或填写 API 配置。",
                status_code=422,
            )
        if not config["api_key"] and not _is_localhost_url(config["base_url"]):
            raise WebChatError(
                "LLM_API_KEY_MISSING",
                "尚未填写 API Key，或可在「模型设置」中切换为「本机 Codex / Gemini 登录态（免 API Key）」。",
                status_code=422,
            )

    store = JsonProjectStore(store_root)
    orchestrator = FurnitureOrchestrator(
        workspace_root=workspace_root,
        project_store=store,
    )
    session = FurnitureToolSession(orchestrator)
    initial = session.call(
        "furniture_get_project",
        {"project_id": project_id, "include_view": True},
    )
    if not initial.get("ok"):
        err = initial.get("error") or {}
        raise ValueError(str(err.get("message") or f"project not found: {project_id}"))

    project_snapshot = initial["project"]
    history = load_chat_history(store_root, project_id)
    system_prompt = build_system_prompt(workspace_root, project_snapshot)

    llm_messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt}
    ]
    for item in history[-16:]:
        role = item.get("role")
        content = str(item.get("content") or "")
        if role in {"user", "assistant"} and content:
            llm_messages.append({"role": role, "content": content})
    llm_messages.append({"role": "user", "content": text})

    tools = openai_tools()
    caller = llm_caller or _default_llm_completion
    tool_trace: list[dict[str, Any]] = []
    any_progressed = False
    final_reply = ""

    for _ in range(MAX_TOOL_ROUNDS):
        step = caller(config, llm_messages, tools)
        assistant_text = str(step.get("content") or "").strip()
        tool_calls = step.get("tool_calls") or []
        if not tool_calls:
            final_reply = assistant_text or "已完成处理。"
            break

        llm_messages.append(
            {
                "role": "assistant",
                "content": assistant_text,
                "tool_calls": tool_calls,
            }
        )
        for tc in tool_calls:
            fn = tc.get("function") or {}
            tool_name = str(fn.get("name") or "")
            raw_args = fn.get("arguments")
            try:
                parsed_args = (
                    json.loads(raw_args)
                    if isinstance(raw_args, str)
                    else dict(raw_args or {})
                )
            except json.JSONDecodeError:
                parsed_args = raw_args
            if isinstance(parsed_args, dict) and tool_name != "furniture_create_project":
                parsed_args.setdefault("project_id", project_id)
            tool_result = session.call(tool_name, parsed_args)
            ok = bool(tool_result.get("ok"))
            progressed = bool(tool_result.get("progressed"))
            if progressed:
                any_progressed = True
            trace_entry: dict[str, Any] = {
                "tool": tool_name,
                "ok": ok,
                "progressed": progressed,
            }
            if not ok and isinstance(tool_result.get("error"), dict):
                trace_entry["error"] = tool_result["error"]
            if isinstance(tool_result.get("handover"), dict):
                trace_entry["handover"] = tool_result["handover"].get("message")
            tool_trace.append(trace_entry)
            llm_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": str(tc.get("id") or ""),
                    "name": tool_name,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )
    else:
        final_reply = "工具连续调用达到上限，请确认当前状态后再继续。"

    latest_snap = session.call(
        "furniture_get_project",
        {"project_id": project_id, "include_view": True},
    )
    latest_project = latest_snap.get("project") or project_snapshot

    now_iso = _utc_now_iso()
    user_entry = {
        "id": f"msg_{uuid.uuid4().hex[:10]}",
        "role": "user",
        "content": text,
        "created_at": now_iso,
    }
    assistant_entry = {
        "id": f"msg_{uuid.uuid4().hex[:10]}",
        "role": "assistant",
        "content": final_reply,
        "created_at": _utc_now_iso(),
        "tool_trace": tool_trace,
    }
    updated_history = [*history, user_entry, assistant_entry]
    save_chat_history(store_root, project_id, updated_history)

    return {
        "ok": True,
        "project_id": project_id,
        "reply": final_reply,
        "tool_trace": tool_trace,
        "progressed": any_progressed,
        "messages": updated_history[-MAX_CHAT_HISTORY_MESSAGES:],
        "project": latest_project,
    }
