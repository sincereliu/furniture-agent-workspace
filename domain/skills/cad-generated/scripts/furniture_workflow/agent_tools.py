"""Provider-agnostic function-calling surface for interactive furniture work.

Hosts register ``openai_tools()`` and dispatch with ``FurnitureToolSession.call``.
This adapter only admits canonical structured fields and Orchestrator lifecycle
operations. It does not parse natural language, fill construction defaults,
auto-confirm stages, or expose ``CadBridge``.
"""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Mapping

from furniture_layout.project_layout import (
    DEFAULT_STUDIO_DEPTH_MM,
    DEFAULT_STUDIO_HEIGHT_MM,
    DEFAULT_STUDIO_WIDTH_MM,
    ProjectLayout,
)

from .agent_tool_schema import (
    TOOL_CONFIRM_STAGE,
    TOOL_CREATE_PROJECT,
    TOOL_GET_PROJECT,
    TOOL_NAMES,
    TOOL_RETRY_STAGE,
    TOOL_REVISE_LAYOUT,
    TOOL_RUN_NEXT,
    TOOL_SELECT_ATTEMPT,
    _CONFIRM_KEYS,
    _CREATE_KEYS,
    _DEFAULT_CAD_OUTPUT_ROOT,
    _ENVELOPE_KEYS,
    _GET_KEYS,
    _INTENT_FLAT_KEYS,
    _RETRYABLE_VALUES,
    _STAGE_VALUES,
    _RETRY_KEYS,
    _REVISE_KEYS,
    _RUN_NEXT_KEYS,
    _SELECT_KEYS,
    openai_tools,
    tool_names,
)
from .project_preview import open_project_preview
from .workflow_orchestrator import (
    RETRYABLE_STAGES,
    FurnitureOrchestrator,
)
from .workflow_project import Project, Revision
from .workflow_state import (
    STAGE_SEQUENCE,
    WorkflowStage,
    parse_stage,
    stage_index,
)

class ToolProtocolError(ValueError):
    """Structured protocol error with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

class FurnitureToolSession:
    """Stateful dispatcher: project_id in, JSON snapshot out."""

    def __init__(self, orchestrator: FurnitureOrchestrator) -> None:
        self.orchestrator = orchestrator
        self._projects: dict[str, Project] = {}

    def call(
        self,
        name: str,
        arguments: Mapping[str, Any] | str | None = None,
    ) -> dict[str, Any]:
        tool = str(name or "").strip()
        project: Project | None = None
        try:
            payload = _parse_arguments(arguments)
            if tool == TOOL_CREATE_PROJECT:
                project = self._create_project(payload)
                result = self._ok(
                    tool, project, include_view=True, progressed=True
                )
                result["preview"] = open_project_preview(
                    project.id,
                    workspace_root=self.orchestrator.workspace_root,
                )
                return result
            if tool not in TOOL_NAMES:
                raise ToolProtocolError(
                    "UNKNOWN_TOOL",
                    f"unknown tool: {tool}; use one of: {', '.join(TOOL_NAMES)}",
                )
            project_id = _require_string(payload.get("project_id"), "project_id")
            project = self._load_project(project_id)
            if tool == TOOL_GET_PROJECT:
                _reject_unknown_keys(payload, _GET_KEYS)
                include_view = _optional_bool(
                    payload.get("include_view"),
                    "include_view",
                    default=True,
                )
                return self._ok(tool, project, include_view=include_view)
            if tool == TOOL_CONFIRM_STAGE:
                return self._confirm_stage(project, payload)
            if tool == TOOL_RUN_NEXT:
                return self._run_next(project, payload)
            if tool == TOOL_RETRY_STAGE:
                return self._retry_stage(project, payload)
            if tool == TOOL_SELECT_ATTEMPT:
                return self._select_attempt(project, payload)
            if tool == TOOL_REVISE_LAYOUT:
                return self._revise_layout(project, payload)
            raise ToolProtocolError("UNKNOWN_TOOL", f"unknown tool: {tool}")
        except ToolProtocolError as exc:
            return self._error(tool, exc.code, exc.message, project=project)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return self._error(tool, "INVALID_ARGUMENT", str(exc), project=project)

    def _create_project(self, payload: dict[str, Any]) -> Project:
        _reject_unknown_keys(payload, _CREATE_KEYS)
        name = _require_string(payload.get("name"), "name")
        layout = _layout_from_payload(payload)
        project = self.orchestrator.create_project(name, layout)
        self._projects[project.id] = project
        return project

    def _confirm_stage(
        self, project: Project, payload: dict[str, Any]
    ) -> dict[str, Any]:
        _reject_unknown_keys(payload, _CONFIRM_KEYS)
        revision = project.latest
        _reject_failed(revision)
        requested = payload.get("stage")
        stage = (
            _require_serial_stage(requested)
            if requested is not None
            else revision.workflow.current
        )
        before = revision.workflow.current
        self.orchestrator.confirm_stage(project, stage)
        self._remember(project)
        return self._ok(
            TOOL_CONFIRM_STAGE,
            project,
            progressed=project.latest.workflow.current != before
            or project.latest.is_stage_approved(stage),
        )

    def _run_next(self, project: Project, payload: dict[str, Any]) -> dict[str, Any]:
        _reject_unknown_keys(payload, _RUN_NEXT_KEYS)
        revision = project.latest
        _reject_failed(revision)
        current = _require_current_serial_stage(revision)
        if not revision.is_stage_approved(current):
            raise ToolProtocolError(
                "STAGE_NOT_CONFIRMED",
                f"confirm {current.value} before generating the next stage",
            )
        current_index = stage_index(current)
        if current_index == len(STAGE_SEQUENCE) - 1:
            raise ToolProtocolError(
                "WORKFLOW_COMPLETE",
                "delivery_validated is the last serial stage",
            )
        next_stage = STAGE_SEQUENCE[current_index + 1]
        if next_stage in RETRYABLE_STAGES and revision.attempts_for(next_stage):
            raise ToolProtocolError(
                "USE_RETRY_STAGE",
                f"{next_stage.value} already has attempts; call {TOOL_RETRY_STAGE}",
            )
        generate_cad = _optional_bool(payload.get("generate_cad"), "generate_cad")
        output_root, artifact_name, force = _cad_options(
            payload, next_stage, generate_cad
        )
        stage_input = _optional_object(payload.get("stage_input"), "stage_input")
        before = current
        self.orchestrator.run_next(
            project,
            stage_input=stage_input,
            output_root=output_root,
            artifact_name=artifact_name,
            generate_cad=generate_cad,
            force=force,
        )
        self._remember(project)
        return self._ok(
            TOOL_RUN_NEXT,
            project,
            progressed=project.latest.workflow.current != before,
        )

    def _retry_stage(
        self, project: Project, payload: dict[str, Any]
    ) -> dict[str, Any]:
        _reject_unknown_keys(payload, _RETRY_KEYS)
        revision = project.latest
        _reject_failed(revision)
        stage = _require_retryable_stage(payload.get("stage"))
        stage_input = _optional_object(payload.get("stage_input"), "stage_input")
        before = revision.workflow.current
        self.orchestrator.retry_stage(
            project,
            stage,
            stage_input=stage_input,
        )
        self._remember(project)
        return self._ok(
            TOOL_RETRY_STAGE,
            project,
            progressed=project.latest.workflow.current != before,
        )

    def _select_attempt(
        self, project: Project, payload: dict[str, Any]
    ) -> dict[str, Any]:
        _reject_unknown_keys(payload, _SELECT_KEYS)
        _reject_failed(project.latest)
        stage = _require_retryable_stage(payload.get("stage"))
        number = _require_int(payload.get("number"), "number")
        self.orchestrator.select_stage_attempt(project, stage, number)
        self._remember(project)
        return self._ok(TOOL_SELECT_ATTEMPT, project)

    def _revise_layout(
        self, project: Project, payload: dict[str, Any]
    ) -> dict[str, Any]:
        _reject_unknown_keys(payload, _REVISE_KEYS)
        layout = _layout_from_payload(payload)
        self.orchestrator.revise(project, layout)
        self._remember(project)
        return self._ok(TOOL_REVISE_LAYOUT, project, progressed=True)

    def _load_project(self, project_id: str) -> Project:
        store = self.orchestrator.project_store
        if store is not None:
            try:
                project = store.load(project_id)
            except ValueError as exc:
                raise ToolProtocolError("PROJECT_NOT_FOUND", str(exc)) from exc
            self._projects[project_id] = project
            return project
        project = self._projects.get(project_id)
        if project is None:
            raise ToolProtocolError(
                "PROJECT_NOT_FOUND",
                f"project not found: {project_id}",
            )
        return project

    def _remember(self, project: Project) -> None:
        self._projects[project.id] = project

    def _ok(
        self,
        tool: str,
        project: Project,
        *,
        include_view: bool = True,
        progressed: bool = False,
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "tool": tool,
            "error": None,
            "progressed": progressed,
            "project": project_snapshot(project, include_view=include_view),
        }

    def _error(
        self,
        tool: str,
        code: str,
        message: str,
        project: Project | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "tool": tool or "",
            "error": {"code": code, "message": message},
            "progressed": False,
            "project": (
                project_snapshot(project, include_view=False)
                if project is not None
                else None
            ),
        }


def project_snapshot(
    project: Project,
    *,
    include_view: bool = True,
) -> dict[str, Any]:
    revision = project.latest
    current = revision.workflow.current
    serial = current if current in STAGE_SEQUENCE else None
    next_stage = None
    if serial is not None and revision.is_stage_approved(serial):
        index = stage_index(serial)
        if index < len(STAGE_SEQUENCE) - 1:
            next_stage = STAGE_SEQUENCE[index + 1]
    current_view = None
    if include_view and serial is not None:
        output = revision.stage_outputs.get(serial.value)
        if output is not None and serial == WorkflowStage.PANELS_PLANNED:
            from furniture_panel_planning.panel_review import panel_review_from_output

            current_view = panel_review_from_output(output)
        elif output is not None:
            current_view = deepcopy(output)
    validation = _latest_validation(revision, serial)
    return {
        "id": project.id,
        "name": project.name,
        "revision_id": revision.id,
        "revision_number": revision.number,
        "parent_revision_id": revision.parent_revision_id,
        "failed": current == WorkflowStage.FAILED,
        "current_stage": current.value,
        "current_stage_approved": (
            serial is not None and revision.is_stage_approved(serial)
        ),
        "approved_stages": list(revision.approved_stages),
        # 哪些阶段沿用了更早那一版的内容（内容逐字节相同，所以免掉再确认一次）。
        # 让人看得见"系统少做了一步"，而不是悄悄少做：R3，见 revision-inheritance-design.md。
        "inherited": deepcopy(revision.inherited),
        "inherited_stages": sorted(revision.inherited),
        "next_stage": next_stage.value if next_stage is not None else None,
        "layout": deepcopy(revision.layout.to_dict()),
        "layout_confirmed": bool(revision.layout.confirmed),
        "layout_sha256": revision.layout_sha256,
        "confirmed_panel_sha256": revision.confirmed_panel_sha256,
        "allowed_tools": allowed_tools(revision),
        "required_tool": required_tool(revision),
        "cad_generation_required": next_stage == WorkflowStage.CAD_GENERATED,
        "selected_attempts": dict(revision.selected_attempts),
        "attempts": _attempt_summaries(revision),
        "current_validation": validation,
        "current_view": current_view,
        "stage_sequence": list(_STAGE_VALUES),
    }


def allowed_tools(revision: Revision) -> list[str]:
    tools = [TOOL_GET_PROJECT, TOOL_REVISE_LAYOUT]
    current = revision.workflow.current
    if current == WorkflowStage.FAILED or current not in STAGE_SEQUENCE:
        return tools
    if not revision.is_stage_approved(current):
        if current.value in revision.stage_outputs:
            tools.append(TOOL_CONFIRM_STAGE)
        if current in RETRYABLE_STAGES:
            tools.append(TOOL_RETRY_STAGE)
            if _has_passed_attempt(revision, current):
                tools.append(TOOL_SELECT_ATTEMPT)
        return tools
    index = stage_index(current)
    if index == len(STAGE_SEQUENCE) - 1:
        return tools
    next_stage = STAGE_SEQUENCE[index + 1]
    if next_stage in RETRYABLE_STAGES and revision.attempts_for(next_stage):
        tools.append(TOOL_RETRY_STAGE)
        if _has_passed_attempt(revision, next_stage):
            tools.append(TOOL_SELECT_ATTEMPT)
    else:
        tools.append(TOOL_RUN_NEXT)
    return tools


def required_tool(revision: Revision) -> str | None:
    current = revision.workflow.current
    if current == WorkflowStage.FAILED or current not in STAGE_SEQUENCE:
        return TOOL_REVISE_LAYOUT
    if not revision.is_stage_approved(current):
        if current.value in revision.stage_outputs:
            return TOOL_CONFIRM_STAGE
        if current in RETRYABLE_STAGES:
            return TOOL_RETRY_STAGE
        return TOOL_CONFIRM_STAGE
    index = stage_index(current)
    if index == len(STAGE_SEQUENCE) - 1:
        return None
    next_stage = STAGE_SEQUENCE[index + 1]
    if next_stage in RETRYABLE_STAGES and revision.attempts_for(next_stage):
        return TOOL_RETRY_STAGE
    return TOOL_RUN_NEXT


def _has_passed_attempt(revision: Revision, stage: WorkflowStage) -> bool:
    return any(item.passed for item in revision.attempts_for(stage))


def _attempt_summaries(revision: Revision) -> dict[str, list[dict[str, Any]]]:
    summaries: dict[str, list[dict[str, Any]]] = {}
    for stage, attempts in revision.stage_attempts.items():
        summaries[stage] = [
            {
                "number": item.number,
                "passed": item.passed,
                "error": item.error,
                "created_at": item.created_at,
            }
            for item in attempts
        ]
    return summaries


def _latest_validation(
    revision: Revision,
    stage: WorkflowStage | None,
) -> dict[str, Any] | None:
    if stage is None:
        return None
    for report in reversed(revision.validations):
        if report.stage == stage.value:
            return deepcopy(report.to_dict())
    return None


def _layout_from_payload(payload: Mapping[str, Any]) -> ProjectLayout:
    rooms = payload.get("rooms")
    if rooms is not None:
        if not isinstance(rooms, list) or not rooms:
            raise ToolProtocolError(
                "INVALID_ARGUMENT",
                "rooms must be a non-empty list",
            )
        try:
            return ProjectLayout.from_source({"rooms": rooms})
        except (TypeError, ValueError) as exc:
            raise ToolProtocolError("INVALID_ARGUMENT", str(exc)) from exc
    category = payload.get("furniture_category")
    if not isinstance(category, str) or not category.strip():
        raise ToolProtocolError(
            "INVALID_ARGUMENT",
            "rooms or furniture_category is required",
        )
    envelope = payload.get("finished_envelope")
    if envelope is None:
        envelope_data: dict[str, Any] = {}
    elif isinstance(envelope, Mapping):
        _reject_unknown_keys(dict(envelope), _ENVELOPE_KEYS, prefix="finished_envelope")
        envelope_data = dict(envelope)
    else:
        raise ToolProtocolError(
            "INVALID_ARGUMENT",
            "finished_envelope must be an object",
        )
    for key in _INTENT_FLAT_KEYS:
        if key not in payload:
            continue
        if key in envelope_data and envelope_data[key] != payload[key]:
            raise ToolProtocolError(
                "INVALID_ARGUMENT",
                f"{key} conflicts with finished_envelope.{key}",
            )
        envelope_data[key] = payload[key]
    from furniture_workflow.input_adapter import layout_from_spec

    try:
        return layout_from_spec(
            {
                "furniture_category": category.strip(),
                "finished_envelope": {
                    key: envelope_data.get(key) for key in _INTENT_FLAT_KEYS
                },
                "origin_z_mm": payload.get("origin_z_mm"),
                "hanging_mode": payload.get("hanging_mode"),
                "hanging_height_mm": payload.get("hanging_height_mm"),
            }
        )
    except (TypeError, ValueError) as exc:
        _raise_layout_shortcut_error(str(exc))


def _raise_layout_shortcut_error(message: str) -> None:
    """Stop and ask for real room dimensions when the placeholder room rejects the cabinet.

    The shortcut validates against ``single_cabinet_layout``'s placeholder studio
    room. When the cabinet cannot fit that placeholder, the only useful next step
    is a real room; reporting the raw geometry error would name a room the caller
    never supplied.
    """
    if "inside the room" not in message:
        raise ToolProtocolError("INVALID_ARGUMENT", message)
    raise ToolProtocolError(
        "ROOM_DIMENSIONS_REQUIRED",
        "cabinet does not fit the placeholder room used by the size-only shortcut "
        f"({DEFAULT_STUDIO_WIDTH_MM:g}x{DEFAULT_STUDIO_DEPTH_MM:g}"
        f"x{DEFAULT_STUDIO_HEIGHT_MM:g} mm); provide rooms[] with the real room "
        "dimensions",
    )


def _cad_options(
    payload: Mapping[str, Any],
    stage: WorkflowStage,
    generate_cad: bool,
) -> tuple[str | None, str | None, bool]:
    output_root = payload.get("output_root")
    artifact_name = payload.get("artifact_name")
    force = _optional_bool(payload.get("force"), "force")
    if artifact_name is not None:
        artifact_name = _require_string(artifact_name, "artifact_name")
    if stage == WorkflowStage.CAD_GENERATED:
        if not generate_cad:
            raise ToolProtocolError(
                "CAD_REQUIRES_GENERATE_CAD",
                "cad_generated requires generate_cad=true",
            )
        if output_root is None:
            output_root = _DEFAULT_CAD_OUTPUT_ROOT
        else:
            output_root = _require_string(output_root, "output_root")
        return output_root, artifact_name, force
    if generate_cad:
        raise ToolProtocolError(
            "INVALID_ARGUMENT",
            "generate_cad is only valid when the next stage is cad_generated",
        )
    if output_root is not None or artifact_name is not None:
        raise ToolProtocolError(
            "INVALID_ARGUMENT",
            "output_root and artifact_name are only valid for cad_generated",
        )
    return None, None, False


def _parse_arguments(
    arguments: Mapping[str, Any] | str | None,
) -> dict[str, Any]:
    if arguments is None:
        return {}
    if isinstance(arguments, str):
        try:
            loaded = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise ToolProtocolError(
                "INVALID_ARGUMENT",
                f"arguments is not valid JSON: {exc.msg}",
            ) from exc
        if not isinstance(loaded, dict):
            raise ToolProtocolError(
                "INVALID_ARGUMENT",
                "arguments JSON must be an object",
            )
        return loaded
    if isinstance(arguments, Mapping):
        return dict(arguments)
    raise ToolProtocolError("INVALID_ARGUMENT", "arguments must be an object or JSON")


def _reject_unknown_keys(
    payload: Mapping[str, Any],
    allowed: frozenset[str],
    *,
    prefix: str | None = None,
) -> None:
    unknown = sorted(set(payload) - allowed)
    if not unknown:
        return
    where = f"{prefix}." if prefix else ""
    raise ToolProtocolError(
        "UNKNOWN_ARGUMENT",
        "unknown field: " + ", ".join(where + key for key in unknown),
    )


def _reject_failed(revision: Revision) -> None:
    if revision.workflow.current == WorkflowStage.FAILED:
        raise ToolProtocolError(
            "FAILED_REVISION",
            "failed revision must be replaced with furniture_revise_layout",
        )


def _require_current_serial_stage(revision: Revision) -> WorkflowStage:
    current = revision.workflow.current
    if current not in STAGE_SEQUENCE:
        raise ToolProtocolError(
            "INVALID_ARGUMENT",
            f"current stage is not serial: {current.value}",
        )
    return current


def _require_serial_stage(value: Any) -> WorkflowStage:
    stage = _parse_requested_stage(value)
    if stage not in STAGE_SEQUENCE:
        raise ToolProtocolError(
            "INVALID_ARGUMENT",
            f"stage must be one of: {', '.join(_STAGE_VALUES)}",
        )
    return stage


def _require_retryable_stage(value: Any) -> WorkflowStage:
    stage = _parse_requested_stage(value)
    if stage not in RETRYABLE_STAGES:
        raise ToolProtocolError(
            "INVALID_ARGUMENT",
            "stage is not retryable; use one of: " + ", ".join(_RETRYABLE_VALUES),
        )
    return stage


def _parse_requested_stage(value: Any) -> WorkflowStage:
    if not isinstance(value, str) or not value.strip():
        raise ToolProtocolError("INVALID_ARGUMENT", "stage is required")
    try:
        return parse_stage(value.strip())
    except ValueError as exc:
        raise ToolProtocolError("INVALID_ARGUMENT", str(exc)) from exc


def _require_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolProtocolError("INVALID_ARGUMENT", f"{name} must be a non-empty string")
    return value.strip()


def _require_int(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ToolProtocolError("INVALID_ARGUMENT", f"{name} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ToolProtocolError("INVALID_ARGUMENT", f"{name} must be an integer")


def _optional_bool(value: Any, name: str, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise ToolProtocolError("INVALID_ARGUMENT", f"{name} must be a boolean")


def _optional_object(value: Any, name: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return dict(value)
    raise ToolProtocolError("INVALID_ARGUMENT", f"{name} must be an object")



# Public protocol surface stays on this module.
__all__ = [
    "FurnitureToolSession",
    "TOOL_CONFIRM_STAGE",
    "TOOL_CREATE_PROJECT",
    "TOOL_GET_PROJECT",
    "TOOL_NAMES",
    "TOOL_RETRY_STAGE",
    "TOOL_REVISE_LAYOUT",
    "TOOL_RUN_NEXT",
    "TOOL_SELECT_ATTEMPT",
    "ToolProtocolError",
    "allowed_tools",
    "openai_tools",
    "project_snapshot",
    "tool_names",
    "required_tool",
]
