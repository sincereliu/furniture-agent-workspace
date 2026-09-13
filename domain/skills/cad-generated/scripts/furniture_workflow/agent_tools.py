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

from furniture_design_intent.design_intent import (
    EXECUTABLE_CATEGORIES,
    HANGING_MODES,
    DesignIntent,
)

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


TOOL_CREATE_PROJECT = "furniture_create_project"
TOOL_GET_PROJECT = "furniture_get_project"
TOOL_CONFIRM_STAGE = "furniture_confirm_stage"
TOOL_RUN_NEXT = "furniture_run_next"
TOOL_RETRY_STAGE = "furniture_retry_stage"
TOOL_SELECT_ATTEMPT = "furniture_select_stage_attempt"
TOOL_REVISE_INTENT = "furniture_revise_intent"

TOOL_NAMES = (
    TOOL_CREATE_PROJECT,
    TOOL_GET_PROJECT,
    TOOL_CONFIRM_STAGE,
    TOOL_RUN_NEXT,
    TOOL_RETRY_STAGE,
    TOOL_SELECT_ATTEMPT,
    TOOL_REVISE_INTENT,
)

_STAGE_VALUES = tuple(stage.value for stage in STAGE_SEQUENCE)
_RETRYABLE_VALUES = tuple(stage.value for stage in RETRYABLE_STAGES)
_INTENT_FLAT_KEYS = ("width_mm", "depth_mm", "height_mm")
_CREATE_KEYS = frozenset(
    {
        "name",
        "furniture_category",
        "finished_envelope",
        "hanging_mode",
        "hanging_height_mm",
        *_INTENT_FLAT_KEYS,
    }
)
_REVISE_KEYS = frozenset({"project_id"}) | (_CREATE_KEYS - {"name"})
_ENVELOPE_KEYS = frozenset(_INTENT_FLAT_KEYS)
_GET_KEYS = frozenset({"project_id", "include_output"})
_CONFIRM_KEYS = frozenset({"project_id", "stage"})
_RUN_NEXT_KEYS = frozenset(
    {
        "project_id",
        "stage_input",
        "generate_cad",
        "output_root",
        "artifact_name",
        "force",
    }
)
_RETRY_KEYS = frozenset({"project_id", "stage", "stage_input"})
_SELECT_KEYS = frozenset({"project_id", "stage", "number"})
_DEFAULT_CAD_OUTPUT_ROOT = "generated"

_PANEL_STAGE_INPUT_HINT = (
    "For panel_plan, stage_input is the canonical construction object "
    "(or {parameters: {...}}). Required keys: n_doors, drawer_count, shelves, "
    "top_gap_mm, back_mount (groove|insert|cover), back_offset, back_rail_height, "
    "groove_depth, groove_clearance, front_face_margin, front_gap, "
    "toe_kick_height, toe_kick_reveal_front, toe_kick_reveal_back, "
    "toe_kick_support_count, drawer_side_clearance, drawer_layer_gap, "
    "drawer_back_clearance. Optional stock keys: board_thickness, back_thickness, "
    "door_thickness, drawer_bottom_thickness, drawer_back_thickness. "
    "Optional cabinet_id. Do not send furniture_category or envelope fields."
)
_PANEL_OUTPUT_HINT = (
    "For panel_plan, current_output is the confirmation review "
    "(markdown or panel/contact tables), not the frozen cabinets tree."
)
_MANUFACTURING_STAGE_INPUT_HINT = (
    "For manufacture_plan, stage_input is {parameters: {...}, appearance?: {...}} "
    "or a flat parameters object. Known parameter keys: door_hinge_side "
    "(left|right, required for a single door), movable_shelf_connector "
    "(two_in_one|shelf_pin, required when movable shelves exist)."
)


class ToolProtocolError(ValueError):
    """Structured protocol error with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def openai_tools() -> list[dict[str, Any]]:
    """OpenAI-compatible tool definitions. Other function-calling hosts map this."""
    return deepcopy(_OPENAI_TOOLS)


def tool_names() -> tuple[str, ...]:
    return TOOL_NAMES


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
                return self._ok(tool, project, include_output=True, advanced=True)
            if tool not in TOOL_NAMES:
                raise ToolProtocolError(
                    "UNKNOWN_TOOL",
                    f"unknown tool: {tool}; use one of: {', '.join(TOOL_NAMES)}",
                )
            project_id = _require_string(payload.get("project_id"), "project_id")
            project = self._load_project(project_id)
            if tool == TOOL_GET_PROJECT:
                _reject_unknown_keys(payload, _GET_KEYS)
                include_output = _optional_bool(
                    payload.get("include_output"),
                    "include_output",
                    default=True,
                )
                return self._ok(tool, project, include_output=include_output)
            if tool == TOOL_CONFIRM_STAGE:
                return self._confirm_stage(project, payload)
            if tool == TOOL_RUN_NEXT:
                return self._run_next(project, payload)
            if tool == TOOL_RETRY_STAGE:
                return self._retry_stage(project, payload)
            if tool == TOOL_SELECT_ATTEMPT:
                return self._select_attempt(project, payload)
            if tool == TOOL_REVISE_INTENT:
                return self._revise_intent(project, payload)
            raise ToolProtocolError("UNKNOWN_TOOL", f"unknown tool: {tool}")
        except ToolProtocolError as exc:
            return self._error(tool, exc.code, exc.message, project=project)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return self._error(tool, "INVALID_ARGUMENT", str(exc), project=project)

    def _create_project(self, payload: dict[str, Any]) -> Project:
        _reject_unknown_keys(payload, _CREATE_KEYS)
        name = _require_string(payload.get("name"), "name")
        intent = _intent_from_payload(payload)
        project = self.orchestrator.create_project(name, intent)
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
            advanced=project.latest.workflow.current != before
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
            advanced=project.latest.workflow.current != before,
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
            advanced=project.latest.workflow.current != before,
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

    def _revise_intent(
        self, project: Project, payload: dict[str, Any]
    ) -> dict[str, Any]:
        _reject_unknown_keys(payload, _REVISE_KEYS)
        intent = _intent_from_payload(payload)
        self.orchestrator.revise(project, intent)
        self._remember(project)
        return self._ok(TOOL_REVISE_INTENT, project, advanced=True)

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
        include_output: bool = True,
        advanced: bool = False,
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "tool": tool,
            "error": None,
            "advanced": advanced,
            "project": project_snapshot(project, include_output=include_output),
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
            "advanced": False,
            "project": (
                project_snapshot(project, include_output=False)
                if project is not None
                else None
            ),
        }


def project_snapshot(
    project: Project,
    *,
    include_output: bool = True,
) -> dict[str, Any]:
    revision = project.latest
    current = revision.workflow.current
    serial = current if current in STAGE_SEQUENCE else None
    next_stage = None
    if serial is not None and revision.is_stage_approved(serial):
        index = stage_index(serial)
        if index < len(STAGE_SEQUENCE) - 1:
            next_stage = STAGE_SEQUENCE[index + 1]
    current_output = None
    if include_output and serial is not None:
        output = revision.stage_outputs.get(serial.value)
        if output is not None and serial == WorkflowStage.PANELS_PLANNED:
            from furniture_panel_planning.panel_review import panel_review_from_output

            current_output = panel_review_from_output(output)
        elif output is not None:
            current_output = deepcopy(output)
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
        "next_stage": next_stage.value if next_stage is not None else None,
        "intent": deepcopy(revision.intent.to_dict()),
        "intent_confirmed": bool(revision.intent.confirmed),
        "intent_sha256": revision.intent_sha256,
        "confirmed_panel_sha256": revision.confirmed_panel_sha256,
        "allowed_actions": allowed_actions(revision),
        "waiting_for": waiting_for(revision),
        "cad_generation_required": next_stage == WorkflowStage.CAD_GENERATED,
        "selected_attempts": dict(revision.selected_attempts),
        "attempts": _attempt_summaries(revision),
        "current_validation": validation,
        "current_output": current_output,
        "stage_sequence": list(_STAGE_VALUES),
    }


def allowed_actions(revision: Revision) -> list[str]:
    actions = [TOOL_GET_PROJECT, TOOL_REVISE_INTENT]
    current = revision.workflow.current
    if current == WorkflowStage.FAILED or current not in STAGE_SEQUENCE:
        return actions
    if not revision.is_stage_approved(current):
        if current.value in revision.stage_outputs:
            actions.append(TOOL_CONFIRM_STAGE)
        if current in RETRYABLE_STAGES:
            actions.append(TOOL_RETRY_STAGE)
            if _has_passed_attempt(revision, current):
                actions.append(TOOL_SELECT_ATTEMPT)
        return actions
    index = stage_index(current)
    if index == len(STAGE_SEQUENCE) - 1:
        return actions
    next_stage = STAGE_SEQUENCE[index + 1]
    if next_stage in RETRYABLE_STAGES and revision.attempts_for(next_stage):
        actions.append(TOOL_RETRY_STAGE)
        if _has_passed_attempt(revision, next_stage):
            actions.append(TOOL_SELECT_ATTEMPT)
    else:
        actions.append(TOOL_RUN_NEXT)
    return actions


def waiting_for(revision: Revision) -> str | None:
    current = revision.workflow.current
    if current == WorkflowStage.FAILED or current not in STAGE_SEQUENCE:
        return TOOL_REVISE_INTENT
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


def _intent_from_payload(payload: Mapping[str, Any]) -> DesignIntent:
    category = payload.get("furniture_category")
    if not isinstance(category, str) or not category.strip():
        raise ToolProtocolError(
            "INVALID_ARGUMENT",
            "furniture_category is required",
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
    hanging_mode = payload.get("hanging_mode")
    if hanging_mode is not None:
        if not isinstance(hanging_mode, str) or hanging_mode not in HANGING_MODES:
            allowed = ", ".join(sorted(HANGING_MODES))
            raise ToolProtocolError(
                "INVALID_ARGUMENT",
                f"hanging_mode must be one of: {allowed}",
            )
    data: dict[str, Any] = {
        "furniture_category": category.strip(),
        "finished_envelope": {
            key: envelope_data.get(key) for key in _INTENT_FLAT_KEYS
        },
        "hanging_mode": hanging_mode,
        "hanging_height_mm": payload.get("hanging_height_mm"),
    }
    return DesignIntent.from_dict(data)


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
            "failed revision must be replaced with furniture_revise_intent",
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


_STAGE_LIST_TEXT = ", ".join(_STAGE_VALUES)
_EXECUTABLE_TEXT = ", ".join(sorted(EXECUTABLE_CATEGORIES))
_RETRYABLE_TEXT = ", ".join(_RETRYABLE_VALUES)

_OPENAI_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": TOOL_CREATE_PROJECT,
            "description": (
                "Start a furniture project at design_intent. Accepts only "
                f"canonical category ({_EXECUTABLE_TEXT} are executable) and "
                "finished envelope in mm. Do not send doors, shelves, thickness, "
                "hardware, room, or CAD fields. After create, confirm the intent "
                "before generating later stages. Serial stages: "
                f"{_STAGE_LIST_TEXT}."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Human-readable project name.",
                    },
                    "furniture_category": {
                        "type": "string",
                        "description": (
                            "Canonical category. Executable values: "
                            f"{_EXECUTABLE_TEXT}. Other values stay a draft "
                            "and cannot be confirmed."
                        ),
                    },
                    "width_mm": {"type": ["number", "null"]},
                    "depth_mm": {"type": ["number", "null"]},
                    "height_mm": {"type": ["number", "null"]},
                    "finished_envelope": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "width_mm": {"type": ["number", "null"]},
                            "depth_mm": {"type": ["number", "null"]},
                            "height_mm": {"type": ["number", "null"]},
                        },
                    },
                    "hanging_mode": {
                        "type": "string",
                        "enum": sorted(HANGING_MODES),
                        "description": "Required for wall_cabinet; omit for floor_cabinet.",
                    },
                    "hanging_height_mm": {
                        "type": ["number", "null"],
                        "description": (
                            "Bottom-edge height from floor; required when "
                            "hanging_mode is free_hanging_height."
                        ),
                    },
                },
                "required": ["name", "furniture_category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_GET_PROJECT,
            "description": (
                "Return the current revision snapshot: stage, approvals, "
                "allowed_actions, attempts, validation, and current_output. "
                f"{_PANEL_OUTPUT_HINT} "
                "Call this when you need state; do not infer a later stage."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "project_id": {"type": "string"},
                    "include_output": {
                        "type": "boolean",
                        "description": "Include current_output. Defaults to true.",
                    },
                },
                "required": ["project_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_CONFIRM_STAGE,
            "description": (
                "Confirm the current checkpoint after the user accepts it. "
                "Freezes design_intent or panel_plan JSON when those stages "
                "are confirmed. Cannot skip ahead. Optional stage must equal "
                "the current stage."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "project_id": {"type": "string"},
                    "stage": {
                        "type": "string",
                        "enum": list(_STAGE_VALUES),
                    },
                },
                "required": ["project_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_RUN_NEXT,
            "description": (
                "Generate the next serial stage once, without auto-confirm. "
                "Requires the current stage to be confirmed. If that next stage "
                f"already has attempts, call {TOOL_RETRY_STAGE} instead. "
                "Entering cad_generated requires generate_cad=true. "
                f"Show current_output and wait. {_PANEL_OUTPUT_HINT} "
                f"{_PANEL_STAGE_INPUT_HINT} {_MANUFACTURING_STAGE_INPUT_HINT}"
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "project_id": {"type": "string"},
                    "stage_input": {
                        "type": "object",
                        "description": (
                            "Canonical input for the next stage. Feature tree, "
                            "CAD, and delivery do not accept stage_input."
                        ),
                    },
                    "generate_cad": {
                        "type": "boolean",
                        "description": "Must be true to enter cad_generated.",
                    },
                    "output_root": {
                        "type": "string",
                        "description": (
                            "CAD output root relative to the workspace. "
                            f"Defaults to {_DEFAULT_CAD_OUTPUT_ROOT} when "
                            "generate_cad is true."
                        ),
                    },
                    "artifact_name": {"type": "string"},
                    "force": {"type": "boolean"},
                },
                "required": ["project_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_RETRY_STAGE,
            "description": (
                "Re-run a planning stage against the frozen confirmed upstream. "
                f"Retryable stages: {_RETRYABLE_TEXT}. Failed attempts do not "
                "fail the whole revision. Show the new current_output and wait "
                f"for confirmation. {_PANEL_OUTPUT_HINT} "
                f"{_PANEL_STAGE_INPUT_HINT} "
                f"{_MANUFACTURING_STAGE_INPUT_HINT}"
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "project_id": {"type": "string"},
                    "stage": {
                        "type": "string",
                        "enum": list(_RETRYABLE_VALUES),
                    },
                    "stage_input": {"type": "object"},
                },
                "required": ["project_id", "stage"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_SELECT_ATTEMPT,
            "description": (
                "Promote a passed attempt to the current unconfirmed candidate, "
                f"then wait for {TOOL_CONFIRM_STAGE}."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "project_id": {"type": "string"},
                    "stage": {
                        "type": "string",
                        "enum": list(_RETRYABLE_VALUES),
                    },
                    "number": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Attempt number from the snapshot.",
                    },
                },
                "required": ["project_id", "stage", "number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_REVISE_INTENT,
            "description": (
                "Replace design intent and start a new revision at design_intent. "
                "Downstream attempts become stale. Use this for category or "
                "envelope changes, not for retrying panels or manufacturing."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "project_id": {"type": "string"},
                    "furniture_category": {"type": "string"},
                    "width_mm": {"type": ["number", "null"]},
                    "depth_mm": {"type": ["number", "null"]},
                    "height_mm": {"type": ["number", "null"]},
                    "finished_envelope": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "width_mm": {"type": ["number", "null"]},
                            "depth_mm": {"type": ["number", "null"]},
                            "height_mm": {"type": ["number", "null"]},
                        },
                    },
                    "hanging_mode": {
                        "type": "string",
                        "enum": sorted(HANGING_MODES),
                    },
                    "hanging_height_mm": {"type": ["number", "null"]},
                },
                "required": ["project_id", "furniture_category"],
            },
        },
    },
]
