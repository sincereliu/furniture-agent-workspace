"""Serializable entrypoint for construction and physical panels."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping, Sequence

from .assembly_tree import build_cabinet_tree
from .cabinet_envelope import CabinetEnvelope
from .cabinet_identity import DEFAULT_CABINET_ID, admit_cabinet_id
from .panel_planning import plan_panels
from .panel_spec import FurnitureSpec
from .structure_planning import CabinetStructure


def plan_panel_stage(
    envelopes: Sequence[CabinetEnvelope | Mapping[str, Any]],
    options: Mapping[str, Any],
) -> dict[str, Any]:
    """Plan every admitted cabinet envelope.

    `options` 支持**逐柜参数**：

    ```json
    {"parameters": {…所有柜的底…}, "cabinets": {"cabinet_2": {…这台的覆盖字段…}}}
    ```

    覆盖是**逐字段**的（`{**共享, **这台}`），合起来必须是一份完整合法的提案——
    阶段验收照旧拒不合法的结果。身份（`cabinet_id`）与几何（柜类、宽深高）**只来自包络**，
    覆盖里写它们会被拒；覆盖里出现不认识的柜名也会被拒（不静默忽略）。
    """
    if isinstance(envelopes, (str, bytes)) or not isinstance(envelopes, Sequence):
        raise ValueError("panel planning requires a list of cabinet envelopes")
    units = tuple(CabinetEnvelope.from_mapping(item) for item in envelopes)
    if not units:
        raise ValueError("panel planning requires at least one cabinet envelope")
    if not isinstance(options, Mapping):
        raise ValueError("panel proposal must be an object")
    values = dict(options)
    parameters = values["parameters"] if "parameters" in values else values
    if not isinstance(parameters, Mapping):
        raise ValueError("panel proposal must be an object")
    shared = {
        key: value for key, value in dict(parameters).items() if key != "cabinet_id"
    }
    overrides = _cabinet_overrides(values.get("cabinets"), units)
    return plan_panel_cabinets(
        tuple(
            (
                unit,
                {**shared, **overrides.get(unit.id, {}), "cabinet_id": unit.id},
            )
            for unit in units
        )
    )


#: 身份与几何只来自包络，逐柜覆盖里不许再写一遍。
ENVELOPE_OWNED_FIELDS = frozenset(
    {"cabinet_id", "furniture_category", "width", "depth", "height"}
)


def _cabinet_overrides(
    raw: Any,
    units: Sequence[CabinetEnvelope],
) -> dict[str, dict[str, Any]]:
    """校验逐柜覆盖：柜名必须在包络里，字段不得越界。"""
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ValueError("panel proposal cabinets must be an object")
    known = {unit.id for unit in units}
    overrides: dict[str, dict[str, Any]] = {}
    for cabinet_id, override in raw.items():
        name = str(cabinet_id)
        if name not in known:
            raise ValueError(f"panel proposal has an unknown cabinet id: {name}")
        if not isinstance(override, Mapping):
            raise ValueError(f"panel proposal for {name} must be an object")
        forbidden = sorted(set(override) & ENVELOPE_OWNED_FIELDS)
        if forbidden:
            raise ValueError(
                f"panel proposal for {name} must not set envelope-owned fields: "
                + ", ".join(forbidden)
            )
        overrides[name] = dict(override)
    return overrides


def plan_panel_cabinets(
    requests: Sequence[tuple[CabinetEnvelope | Mapping[str, Any], Mapping[str, Any]]],
) -> dict[str, Any]:
    """Plan one or more cabinet instances with unique parent ids.

    Each request is (cabinet envelope, panel parameters). Optional
    ``cabinet_id`` is identity, not a construction field, and is popped
    before spec admission. Duplicate ids are rejected.
    """
    if not requests:
        raise ValueError("panel planning requires at least one cabinet request")
    cabinets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, (raw_envelope, options) in enumerate(requests, start=1):
        if not isinstance(options, Mapping):
            raise ValueError("panel proposal must be an object")
        unit = CabinetEnvelope.from_mapping(raw_envelope)
        values = dict(options)
        fallback = unit.id if unit.id else (
            DEFAULT_CABINET_ID if index == 1 else f"cabinet_{index}"
        )
        cabinet_id = admit_cabinet_id(values.pop("cabinet_id", None), fallback=fallback)
        if cabinet_id in seen:
            raise ValueError(f"duplicate cabinet_id: {cabinet_id}")
        seen.add(cabinet_id)
        requested_back_mount = values.get("back_mount")
        spec = FurnitureSpec.from_envelope(unit, values)
        structure = CabinetStructure.from_spec(spec)
        panels = plan_panels(spec, structure, cabinet_id=cabinet_id)
        assemblies, interior = build_cabinet_tree(
            cabinet_id, spec, structure, panels
        )
        cabinets.append(
            {
                "id": cabinet_id,
                "spec": asdict(spec),
                "interior": interior,
                "back_mount_resolution": {
                    "requested": requested_back_mount,
                    "effective": spec.back_mount,
                },
                "assemblies": assemblies,
            }
        )
    return {"cabinets": cabinets}
