"""OpenAI-compatible furniture_* tool schema. No lifecycle execution."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .workflow_constants import RETRYABLE_STAGES
from .workflow_state import STAGE_SEQUENCE

TOOL_CREATE_PROJECT = "furniture_create_project"
TOOL_GET_PROJECT = "furniture_get_project"
TOOL_CONFIRM_STAGE = "furniture_confirm_stage"
TOOL_RUN_NEXT = "furniture_run_next"
TOOL_RETRY_STAGE = "furniture_retry_stage"
TOOL_SELECT_ATTEMPT = "furniture_select_stage_attempt"
TOOL_REVISE_LAYOUT = "furniture_revise_layout"
TOOL_RECORD_DECISION = "furniture_record_decision"

TOOL_NAMES = (
    TOOL_CREATE_PROJECT,
    TOOL_GET_PROJECT,
    TOOL_CONFIRM_STAGE,
    TOOL_RUN_NEXT,
    TOOL_RETRY_STAGE,
    TOOL_SELECT_ATTEMPT,
    TOOL_REVISE_LAYOUT,
    TOOL_RECORD_DECISION,
)

_STAGE_VALUES = tuple(stage.value for stage in STAGE_SEQUENCE)
_RETRYABLE_VALUES = tuple(stage.value for stage in RETRYABLE_STAGES)
_CREATE_KEYS = frozenset({"name", "rooms", "decisions"})
_REVISE_KEYS = frozenset({"project_id", "rooms", "decisions"})
_RECORD_DECISION_KEYS = frozenset({"project_id", "decisions"})
_GET_KEYS = frozenset({"project_id", "include_view"})
_CONFIRM_KEYS = frozenset({"project_id", "stage", "room_id"})
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
    "or a flat parameters object (appearance may sit beside the flat keys). "
    "Known parameter keys: door_hinge_side "
    "(left|right, required for a single door), movable_shelf_connector "
    "(two_in_one|shelf_pin, required when movable shelves exist), "
    "edge_banding ({material, thickness} from edge_banding_catalog.yaml). "
    "appearance selects material per role: {carcass|door|back: "
    "{substrate, surface}} with keys from materials_catalog.yaml."
)

_DECISIONS_PROPERTY = {
    "type": "array",
    "items": {"type": "object"},
    "description": (
        "What the customer actually said that shaped this layout, recorded in the "
        "customer's own words. Each entry is {utterance, interpretation, speaker?, "
        "status?, targets?, applies_to?}: utterance keeps the original words "
        "(required when speaker is customer/relay — never invent a quote for an "
        "assumption of your own), interpretation is what we made of them. Defaults "
        "are speaker=agent and status=assumption — only write speaker=customer for "
        "words the customer said, and status=confirmed when the customer accepted it "
        "(targets names the assumption ids it settles; only customer/relay may "
        "confirm). Append-only: never rewrite an earlier entry, append a new one. "
        "Optional; omit when there is nothing new from the customer."
    ),
}


def openai_tools() -> list[dict[str, Any]]:
    """OpenAI-compatible tool definitions. Other function-calling hosts map this."""
    return deepcopy(_OPENAI_TOOLS)


def tool_names() -> tuple[str, ...]:
    return TOOL_NAMES


_STAGE_LIST_TEXT = ", ".join(_STAGE_VALUES)
_RETRYABLE_TEXT = ", ".join(_RETRYABLE_VALUES)

_OPENAI_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": TOOL_CREATE_PROJECT,
            "description": (
                "Start a home furniture project at layout_plan. Require rooms[] "
                "with explicit room dimensions and furniture envelopes. Room doors/windows "
                "belong in rooms[].openings[] (kind=door|window). Do not send "
                "cabinet n_doors, shelves, thickness, or hardware. After create, "
                "confirm layout before generating later stages. Optional decisions "
                "records what the customer said (append-only). Serial stages: "
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
                    "rooms": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "object"},
                        "description": (
                            "Rooms in the home project, each with items[] and "
                            "optional openings[] for room doors and windows. "
                            "A whole wall of cabinets is one wall item with "
                            "placement.fill true. Its width is the longest free "
                            "span of that wall, or the free span touching a named "
                            "end when placement.against is set. Fixed wall cabinets "
                            "name host_wall and width. placement.against maps an "
                            "end (east, south, west, or north) to wall or another "
                            "item id: wall reaches the side wall, an id stops "
                            "against that cabinet. Omitted ends pack into the "
                            "earliest free span. This stage does not take an "
                            "along-wall offset. Do not split that envelope "
                            "by door width or interior bays."
                        ),
                    },
                    "decisions": deepcopy(_DECISIONS_PROPERTY),
                },
                "required": ["name", "rooms"],
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
                "Freezes layout_plan or panel_plan JSON when those stages "
                "are confirmed. Cannot skip ahead. Optional stage must equal "
                "the current stage. For layout_plan you may pass room_id to "
                "review one room at a time: the layout checkpoint is confirmed "
                "only after every room has been reviewed (rooms that did not "
                "change keep their review automatically)."
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
                    "room_id": {
                        "type": "string",
                        "description": (
                            "layout_plan only: review this one room instead of "
                            "the whole layout"
                        ),
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
            "name": TOOL_REVISE_LAYOUT,
            "description": (
                "Replace the home layout and start a new revision at layout_plan. "
                "Downstream attempts become stale. Use this for room or envelope "
                "changes, not for retrying panels or manufacturing. Optional decisions "
                "records what the customer just said (append-only)."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "project_id": {"type": "string"},
                    "rooms": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "object"},
                    },
                    "decisions": deepcopy(_DECISIONS_PROPERTY),
                },
                "required": ["project_id", "rooms"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOL_RECORD_DECISION,
            "description": (
                "Record what the customer said, without changing the layout or the "
                "stage. Use it when the customer says something that matters but does "
                "not need a layout revision yet (a preference, a rejection, a "
                "confirmation of an earlier assumption). Append-only, same entry shape "
                "and same defaults as the decisions argument of "
                f"{TOOL_CREATE_PROJECT}/{TOOL_REVISE_LAYOUT}. Does not advance the flow."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "project_id": {"type": "string"},
                    "decisions": {
                        **deepcopy(_DECISIONS_PROPERTY),
                        "minItems": 1,
                        "description": (
                            "One or more entries to append. Same shape as elsewhere: "
                            "{utterance, interpretation, speaker?, status?, targets?, "
                            "applies_to?}. Defaults are speaker=agent and "
                            "status=assumption; only customer/relay may confirm, and "
                            "speaker=customer requires the customer's own words."
                        ),
                    },
                },
                "required": ["project_id", "decisions"],
            },
        },
    },
]
