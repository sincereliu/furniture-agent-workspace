"""OpenAI-compatible furniture_* tool schema. No lifecycle execution."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from furniture_design_intent.design_intent import (
    EXECUTABLE_CATEGORIES,
    HANGING_MODES,
)

from .workflow_constants import RETRYABLE_STAGES
from .workflow_state import STAGE_SEQUENCE

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
_GET_KEYS = frozenset({"project_id", "include_view"})
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
_PANEL_VIEW_HINT = (
    "For panel_plan, current_view is the confirmation review "
    "(markdown or panel/contact tables), not the frozen cabinets tree."
)
_MANUFACTURING_STAGE_INPUT_HINT = (
    "For manufacture_plan, stage_input is {parameters: {...}, appearance?: {...}} "
    "or a flat parameters object. Known parameter keys: door_hinge_side "
    "(left|right, required for a single door), movable_shelf_connector "
    "(two_in_one|shelf_pin, required when movable shelves exist). "
    "appearance selects material per role: {carcass|door|back: "
    "{substrate, surface}} with keys from materials_catalog.yaml. "
    "edge_banding selects {material, thickness} from edge_banding_catalog.yaml."
)


def openai_tools() -> list[dict[str, Any]]:
    """OpenAI-compatible tool definitions. Other function-calling hosts map this."""
    return deepcopy(_OPENAI_TOOLS)


def tool_names() -> tuple[str, ...]:
    return TOOL_NAMES


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
                "allowed_tools, attempts, validation, and current_view. "
                f"{_PANEL_VIEW_HINT} "
                "Call this when you need state; do not infer a later stage."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "project_id": {"type": "string"},
                    "include_view": {
                        "type": "boolean",
                        "description": "Include current_view. Defaults to true.",
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
                f"Show current_view and wait. {_PANEL_VIEW_HINT} "
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
                "fail the whole revision. Show the new current_view and wait "
                f"for confirmation. {_PANEL_VIEW_HINT} "
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
