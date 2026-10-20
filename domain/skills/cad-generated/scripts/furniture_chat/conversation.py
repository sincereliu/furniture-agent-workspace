"""网页家具对话编排：项目上下文、历史、阶段和业务工具执行。

模型连接、独立登录及进程隔离由 furniture_ai 拥有。
本模块负责 structured_protocol / state / side_effect，不解析自然语言意图。
"""
from __future__ import annotations
from datetime import datetime, timezone
import copy
import json
from pathlib import Path
import threading
from typing import Any, Callable, Mapping
import uuid

import furniture_ai as ai
from furniture_ai import AIConnectionError as WebChatError
from furniture_workflow.agent_tool_schema import openai_tools
from furniture_workflow.agent_tools import FurnitureToolSession
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_store import JsonProjectStore


CHAT_HISTORY_FILENAME = "chat.json"


MAX_CHAT_HISTORY_MESSAGES = 40


MAX_TOOL_ROUNDS = 6


_ACTIVE_TURNS: dict[str, dict[str, Any]] = {}


_CHAT_BUSY: set[tuple[str, str]] = set()


_CHAT_GUARD = threading.Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _chat_history_path(store_root: str | Path, project_id: str) -> Path:
    return JsonProjectStore(store_root).project_dir(project_id) / CHAT_HISTORY_FILENAME


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
    key = (str(Path(store_root).resolve()), project_id)
    with _CHAT_GUARD:
        if key in _CHAT_BUSY:
            raise WebChatError("CHAT_BUSY", "当前对话正在执行，请完成后再清空。", 409)
        _clear_chat_history(store_root, project_id)


def _clear_chat_history(store_root: str | Path, project_id: str) -> None:
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


def _compact_project_snapshot_for_prompt(
    project_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    """剥离仅用于前端 3D/SVG 渲染的体积膨胀字段（current_view / viewer / preview），保留完整业务结构。"""
    compact = copy.deepcopy(dict(project_snapshot))
    compact.pop("current_view", None)
    layout = compact.get("layout")
    if isinstance(layout, dict):
        rooms = layout.get("rooms")
        if isinstance(rooms, list):
            for room_entry in rooms:
                if isinstance(room_entry, dict):
                    room_entry.pop("viewer", None)
                    room_entry.pop("preview", None)
    return compact


def _summarize_initial_snapshot_step(project_snapshot: Mapping[str, Any]) -> str:
    """生成确定性的项目快照核查摘要，使思考过程在请求发起瞬间即可实时展示第一步状态。"""
    cur_stage = str(project_snapshot.get("current_stage") or "layout_plan")
    next_stage = str(project_snapshot.get("next_stage") or "")
    approved = list(project_snapshot.get("approved_stages") or [])
    rooms_summary: list[str] = []
    layout = project_snapshot.get("layout")
    if isinstance(layout, dict) and isinstance(layout.get("rooms"), list):
        for r in layout["rooms"]:
            if not isinstance(r, dict):
                continue
            rm = r.get("room") or {}
            r_name = rm.get("name") or rm.get("id") or "房间"
            w = rm.get("width_mm")
            d = rm.get("depth_mm")
            items = r.get("items") or []
            item_names = [
                f"{it.get('name') or it.get('id')}({it.get('width_mm')}×{it.get('depth_mm')}×{it.get('height_mm')}mm)"
                for it in items
                if isinstance(it, dict)
            ]
            dim_str = f"{w}×{d}mm" if w and d else ""
            rooms_summary.append(
                f"{r_name}{dim_str}（家具 {len(item_names)} 件：{', '.join(item_names[:6])}）"
            )
    room_part = "；".join(rooms_summary) if rooms_summary else "已加载项目配置"
    approved_part = ",".join(approved) if approved else "无"
    next_part = f" → 下一阶段 {next_stage}" if next_stage else ""
    return f"已核查项目快照：当前阶段 {cur_stage}（已确认: {approved_part}{next_part}）；{room_part}。"


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
        "如需展示进度，在 `thinking` 字段提供简短的操作摘要，不输出内部推理过程。",
    ]
    for rel_path in _stage_doc_paths(project_snapshot):
        content = _read_doc_if_exists(workspace_root, rel_path)
        if content:
            sections.append(f"--- 文档：{rel_path} ---\n{content}")

    compact_snapshot = _compact_project_snapshot_for_prompt(project_snapshot)
    snapshot_json = json.dumps(compact_snapshot, ensure_ascii=False, indent=2)
    sections.append(f"--- 当前项目实时快照 ---\n```json\n{snapshot_json}\n```")
    return "\n\n".join(sections)


def get_project_chat_state(
    project_id: str,
    *,
    workspace_root: Path,
    store_root: Path,
) -> dict[str, Any]:
    """获取项目当前的对话历史、本机模型配置状态、执行中思考轨迹与项目阶段摘要。"""
    store = JsonProjectStore(store_root)
    orchestrator = FurnitureOrchestrator(
        workspace_root=workspace_root,
        project_store=store,
    )
    session = FurnitureToolSession(orchestrator)
    # 轮询与初始化状态仅需项目阶段与房间元数据，不生成 180KB 的 3D 几何视图以保证 <2ms 极速响应
    snap_res = session.call(
        "furniture_get_project",
        {"project_id": project_id, "include_view": False},
    )
    if not snap_res.get("ok"):
        err = snap_res.get("error") or {}
        raise ValueError(str(err.get("message") or f"project not found: {project_id}"))

    llm_info = ai.public_llm_config(store_root)
    ai.prewarm_llm(llm_info)

    return {
        "project_id": project_id,
        "messages": load_chat_history(store_root, project_id),
        "llm": llm_info,
        "project": snap_res["project"],
        "active_turn": _ACTIVE_TURNS.get(project_id),
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
    """同一项目的聊天写入串行化，避免重复执行和覆盖历史。"""
    key = (str(Path(store_root).resolve()), project_id)
    with _CHAT_GUARD:
        if key in _CHAT_BUSY:
            raise WebChatError("CHAT_BUSY", "当前项目正在处理上一条消息，请稍后重试。", 409)
        _CHAT_BUSY.add(key)
    try:
        return _send_project_chat_message(
            project_id, user_message, workspace_root=workspace_root,
            store_root=store_root, llm_caller=llm_caller,
        )
    finally:
        with _CHAT_GUARD:
            _CHAT_BUSY.discard(key)


def _send_project_chat_message(
    project_id: str,
    user_message: str,
    *,
    workspace_root: Path,
    store_root: Path,
    llm_caller: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """发送一条用户消息，执行大模型 Tool-Calling 闭环并持久化对话与思考记录。"""
    text = str(user_message or "").strip()
    if not text:
        raise ValueError("message must not be empty")

    config = ai.load_llm_config(store_root)
    ai.validate_connection_config(config)

    store = JsonProjectStore(store_root)
    orchestrator = FurnitureOrchestrator(
        workspace_root=workspace_root,
        project_store=store,
    )
    session = FurnitureToolSession(orchestrator)
    initial = session.call(
        "furniture_get_project",
        {"project_id": project_id, "include_view": False},
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
    tool_trace: list[dict[str, Any]] = []
    thinking_steps: list[str] = []
    any_progressed = False
    final_reply = ""

    # 当使用真实大模型时，立即写入第一步快照核查结果，使前端在 0.2s 内即可展示 Step 1
    if llm_caller is None:
        snapshot_step = _summarize_initial_snapshot_step(project_snapshot)
        if snapshot_step:
            thinking_steps.append(snapshot_step)

    _ACTIVE_TURNS[project_id] = {
        "user_message": text,
        "round": 1,
        "status": "正在流式思考与分析方案…",
        "thinking_steps": list(thinking_steps),
        "live_thinking": "",
        "live_reply": "",
        "tool_trace": [],
        "started_at": _utc_now_iso(),
    }

    def _on_live_thinking(chunk_text: str) -> None:
        turn_state = _ACTIVE_TURNS.get(project_id)
        if turn_state is not None:
            turn_state["live_thinking"] = chunk_text
            turn_state["status"] = "正在实时推理思考中…"

    def _on_live_reply(chunk_text: str) -> None:
        turn_state = _ACTIVE_TURNS.get(project_id)
        if turn_state is not None:
            turn_state["live_reply"] = chunk_text
            turn_state["status"] = "思考完成，正在流式生成回复…"

    try:
        for round_idx in range(1, MAX_TOOL_ROUNDS + 1):
            # A previous tool may have confirmed/revised a stage. Supply the current
            # snapshot and its stage documents before the next model completion.
            current = session.call("furniture_get_project", {"project_id": project_id, "include_view": False})
            if current.get("ok"):
                project_snapshot = current["project"]
                llm_messages[0]["content"] = build_system_prompt(workspace_root, project_snapshot)
            tools = [t for t in openai_tools() if t["function"]["name"] in project_snapshot.get("allowed_tools", [])]
            _ACTIVE_TURNS[project_id]["round"] = round_idx
            _ACTIVE_TURNS[project_id]["live_thinking"] = ""
            _ACTIVE_TURNS[project_id]["live_reply"] = ""
            _ACTIVE_TURNS[project_id]["status"] = (
                "正在思考与分析方案…"
                if round_idx == 1
                else f"第 {round_idx} 步：正在根据工具结果继续推理…"
            )

            if llm_caller is not None:
                step = llm_caller(config, llm_messages, tools)
            else:
                step = ai.complete(
                    config,
                    llm_messages,
                    tools,
                    on_thinking_delta=_on_live_thinking,
                    on_reply_delta=_on_live_reply,
                )

            _ACTIVE_TURNS[project_id]["live_thinking"] = ""
            step_thinking = str(step.get("thinking") or "").strip()
            assistant_text = str(step.get("content") or "").strip()
            tool_calls = step.get("tool_calls") or []

            if tool_calls and assistant_text and assistant_text not in step_thinking:
                step_thinking = (
                    f"{step_thinking}\n{assistant_text}".strip()
                    if step_thinking
                    else assistant_text
                )
            if step_thinking:
                thinking_steps.append(step_thinking)
                _ACTIVE_TURNS[project_id]["thinking_steps"] = list(thinking_steps)

            if not tool_calls:
                final_reply = assistant_text or "已完成处理。"
                break

            llm_messages.append(
                {
                    "role": "assistant",
                    "thinking": step_thinking,
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
                # This endpoint is scoped to the page's project. A model cannot
                # create another project or mutate a different one through it.
                scope_error = None
                if not isinstance(parsed_args, dict):
                    scope_error = "工具参数必须是 JSON 对象。"
                elif parsed_args.get("project_id", project_id) != project_id:
                    scope_error = "当前聊天只能操作当前项目。"
                elif tool_name == "furniture_create_project":
                    scope_error = "当前聊天不能新建其他项目。"
                else:
                    parsed_args["project_id"] = project_id
                    current = session.call("furniture_get_project", {"project_id": project_id, "include_view": False})
                    if tool_name not in (current.get("project") or {}).get("allowed_tools", []):
                        scope_error = "该工具不在当前阶段的 allowed_tools 中。"
                _ACTIVE_TURNS[project_id]["status"] = f"正在执行工具 {tool_name}…"
                tool_result = (
                    {"ok": False, "progressed": False, "error": {"code": "CHAT_TOOL_NOT_ALLOWED", "message": scope_error}}
                    if scope_error else session.call(tool_name, parsed_args)
                )
                ok = bool(tool_result.get("ok"))
                progressed = bool(tool_result.get("progressed"))
                if progressed:
                    any_progressed = True
                display_args = (
                    {k: v for k, v in parsed_args.items() if k != "project_id"}
                    if isinstance(parsed_args, dict)
                    else parsed_args
                )
                trace_entry: dict[str, Any] = {
                    "round": round_idx,
                    "tool": tool_name,
                    "arguments": display_args,
                    "ok": ok,
                    "progressed": progressed,
                }
                if not ok and isinstance(tool_result.get("error"), dict):
                    trace_entry["error"] = tool_result["error"]
                if isinstance(tool_result.get("handover"), dict):
                    trace_entry["handover"] = tool_result["handover"].get("message")
                tool_trace.append(trace_entry)
                _ACTIVE_TURNS[project_id]["tool_trace"] = list(tool_trace)
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
    except Exception as exc:
        # Tools may already have changed the project. Keep their receipts even if
        # a later completion fails; never invite an invisible duplicate operation.
        failure_message = exc.message if isinstance(exc, WebChatError) else "对话执行失败，请检查项目当前状态。"
        save_chat_history(store_root, project_id, [
            *history,
            {"id": f"msg_{uuid.uuid4().hex[:10]}", "role": "user", "content": text, "created_at": _utc_now_iso()},
            {
                "id": f"msg_{uuid.uuid4().hex[:10]}", "role": "assistant",
                "content": failure_message, "created_at": _utc_now_iso(),
                "tool_trace": tool_trace, "thinking_steps": thinking_steps,
                "error": {"code": exc.code if isinstance(exc, WebChatError) else "CHAT_EXECUTION_ERROR"},
            },
        ])
        raise
    finally:
        _ACTIVE_TURNS.pop(project_id, None)

    latest_snap = session.call(
        "furniture_get_project",
        {"project_id": project_id, "include_view": True},
    )
    latest_project = latest_snap.get("project") or project_snapshot
    combined_thinking = "\n\n".join(thinking_steps)

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
        "thinking": combined_thinking,
        "thinking_steps": thinking_steps,
        "content": final_reply,
        "created_at": _utc_now_iso(),
        "tool_trace": tool_trace,
    }
    updated_history = [*history, user_entry, assistant_entry]
    save_chat_history(store_root, project_id, updated_history)

    return {
        "ok": True,
        "project_id": project_id,
        "thinking": combined_thinking,
        "thinking_steps": thinking_steps,
        "reply": final_reply,
        "tool_trace": tool_trace,
        "progressed": any_progressed,
        "messages": updated_history[-MAX_CHAT_HISTORY_MESSAGES:],
        "project": latest_project,
    }
