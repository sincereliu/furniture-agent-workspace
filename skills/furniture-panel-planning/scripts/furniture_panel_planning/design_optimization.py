"""Bounded multi-objective candidate generation for the panel-planning stage."""

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from itertools import product
import json
from math import isfinite
from typing import Any, Mapping

from furniture_layout.layout_planning import CabinetLayout

from .panel_pipeline import plan_panel_stage
from .panel_spec import PANEL_SPEC_FIELDS


SUPPORTED_OBJECTIVES = frozenset(
    {
        "material_volume_m3",
        "total_panel_area_m2",
        "negative_internal_volume_m3",
        "complexity_score",
    }
)


def _digest(value: Any) -> str:
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _normalize_domains(raw: Any) -> dict[str, list[Any]]:
    if not isinstance(raw, Mapping) or not raw:
        raise ValueError("optimization variables must be a non-empty object")
    domains: dict[str, list[Any]] = {}
    for name, values in raw.items():
        if name not in PANEL_SPEC_FIELDS:
            raise ValueError(f"optimization variable is not owned by panels_planned: {name}")
        if not isinstance(values, list) or not values:
            raise ValueError(f"optimization variable {name} requires a non-empty choices list")
        if len(values) > 50:
            raise ValueError(f"optimization variable {name} exceeds 50 choices")
        normalized: list[Any] = []
        for value in values:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if not isfinite(float(value)):
                    raise ValueError(f"optimization choice is not finite: {name}")
            elif not isinstance(value, str):
                raise ValueError(f"optimization choice must be numeric or text: {name}")
            if value not in normalized:
                normalized.append(value)
        domains[str(name)] = normalized
    return domains


def _metrics(output: Mapping[str, Any]) -> dict[str, float]:
    panels = output["panels"]
    structure = output["structure"]
    material_volume = sum(
        float(item["size_x"])
        * float(item["size_y"])
        * float(item["size_z"])
        * int(item.get("quantity", 1))
        for item in panels
    ) / 1_000_000_000.0
    total_area = sum(
        float(item["size_x"])
        * float(item["size_y"])
        * int(item.get("quantity", 1))
        for item in panels
    ) / 1_000_000.0
    internal_depth = float(structure["internal_y_end"]) - float(structure["internal_y_start"])
    internal_volume = (
        float(structure["internal_width"])
        * float(structure["internal_height"])
        * internal_depth
        / 1_000_000_000.0
    )
    back_penalty = {"groove": 2.0, "insert": 1.0, "cover": 1.5}.get(
        str(structure["back_mount"]), 2.0
    )
    return {
        "material_volume_m3": material_volume,
        "total_panel_area_m2": total_area,
        "negative_internal_volume_m3": -internal_volume,
        "complexity_score": float(len(panels)) + back_penalty,
        "internal_width_mm": float(structure["internal_width"]),
        "internal_height_mm": float(structure["internal_height"]),
        "internal_depth_mm": internal_depth,
        "internal_volume_m3": internal_volume,
    }


def _feasible(metrics: Mapping[str, float], constraints: Mapping[str, Any]) -> bool:
    checks = {
        "min_internal_width_mm": metrics["internal_width_mm"]
        >= float(constraints.get("min_internal_width_mm", float("-inf"))),
        "min_internal_height_mm": metrics["internal_height_mm"]
        >= float(constraints.get("min_internal_height_mm", float("-inf"))),
        "min_internal_depth_mm": metrics["internal_depth_mm"]
        >= float(constraints.get("min_internal_depth_mm", float("-inf"))),
        "max_material_volume_m3": metrics["material_volume_m3"]
        <= float(constraints.get("max_material_volume_m3", float("inf"))),
    }
    known = set(checks)
    unknown = sorted(set(constraints) - known)
    if unknown:
        raise ValueError("unsupported optimization constraints: " + ", ".join(unknown))
    return all(checks[name] for name in constraints)


def _dominates(a: Mapping[str, Any], b: Mapping[str, Any], objectives: list[str]) -> bool:
    a_values = [float(a["objectives"][name]) for name in objectives]
    b_values = [float(b["objectives"][name]) for name in objectives]
    return all(x <= y for x, y in zip(a_values, b_values)) and any(
        x < y for x, y in zip(a_values, b_values)
    )


def _pareto(candidates: list[dict[str, Any]], objectives: list[str]) -> list[dict[str, Any]]:
    front = [
        candidate
        for candidate in candidates
        if not any(
            other is not candidate and _dominates(other, candidate, objectives)
            for other in candidates
        )
    ]
    return sorted(
        front,
        key=lambda item: tuple(float(item["objectives"][name]) for name in objectives),
    )


def _select_front(
    candidates: list[dict[str, Any]],
    objectives: list[str],
    requested_engine: str,
) -> tuple[list[dict[str, Any]], str, str | None]:
    if requested_engine not in {"auto", "exact", "pymoo"}:
        raise ValueError("engine must be auto, exact, or pymoo")
    if requested_engine in {"auto", "pymoo"} and candidates:
        try:
            import numpy as np
            from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting
        except ImportError:
            if requested_engine == "pymoo":
                return [], "pymoo", (
                    "pymoo is not installed; install the furniture-analysis extra"
                )
        else:
            objective_matrix = np.asarray(
                [
                    [float(item["objectives"][name]) for name in objectives]
                    for item in candidates
                ],
                dtype=float,
            )
            indexes = NonDominatedSorting().do(
                objective_matrix,
                only_non_dominated_front=True,
            )
            front = [candidates[int(index)] for index in indexes]
            return (
                sorted(
                    front,
                    key=lambda item: tuple(
                        float(item["objectives"][name]) for name in objectives
                    ),
                ),
                "pymoo-non-dominated-sorting",
                None,
            )
    return _pareto(candidates, objectives), "exact-discrete-pareto", None


def optimize_panel_design(
    layout: CabinetLayout,
    panel_output: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Generate bounded Pareto candidates without mutating confirmed output."""

    domains = _normalize_domains(config.get("variables"))
    objectives = [
        str(item)
        for item in config.get(
            "objectives",
            ["material_volume_m3", "negative_internal_volume_m3"],
        )
    ]
    unknown_objectives = sorted(set(objectives) - SUPPORTED_OBJECTIVES)
    if unknown_objectives or not objectives:
        raise ValueError("unsupported or empty objectives: " + ", ".join(unknown_objectives))
    constraints = config.get("constraints", {})
    if not isinstance(constraints, Mapping):
        raise ValueError("constraints must be an object")
    max_evaluations = int(config.get("max_evaluations", 10_000))
    if not 1 <= max_evaluations <= 10_000:
        raise ValueError("max_evaluations must be between 1 and 10000")
    combination_count = 1
    for values in domains.values():
        combination_count *= len(values)
    if combination_count > max_evaluations:
        raise ValueError(
            f"choice grid has {combination_count} combinations, above "
            f"max_evaluations={max_evaluations}"
        )

    base_spec = panel_output.get("spec")
    if not isinstance(base_spec, Mapping):
        raise ValueError("panel output requires a spec object")
    base_options = {
        name: base_spec[name]
        for name in PANEL_SPEC_FIELDS
        if name in base_spec
    }
    names = list(domains)
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for values in product(*(domains[name] for name in names)):
        changes = dict(zip(names, values))
        options = {**base_options, **changes}
        try:
            output = plan_panel_stage(layout, options)
            metrics = _metrics(output)
        except (KeyError, TypeError, ValueError) as exc:
            rejected.append({"parameters": changes, "reason": str(exc)})
            continue
        if not _feasible(metrics, constraints):
            rejected.append({"parameters": changes, "reason": "constraint violation"})
            continue
        candidates.append(
            {
                "parameters": changes,
                "resolved_parameters": {
                    name: output["spec"][name]
                    for name in PANEL_SPEC_FIELDS
                    if name in output["spec"]
                },
                "objectives": {name: metrics[name] for name in objectives},
                "metrics": metrics,
                "stage_output_sha256": _digest(output),
            }
        )

    front, engine, unavailable_reason = _select_front(
        candidates,
        objectives,
        str(config.get("engine", "auto")).strip().lower(),
    )
    max_candidates = int(config.get("max_candidates", 25))
    if not 1 <= max_candidates <= 100:
        raise ValueError("max_candidates must be between 1 and 100")
    result = {
        "analysis": "panel_optimization",
        "status": "unavailable" if unavailable_reason else "completed",
        "engine": engine,
        "upstream_method": (
            "bounded exhaustive evaluation followed by non-dominated sorting"
        ),
        "source_panel_output_sha256": _digest(panel_output),
        "objectives": objectives,
        "constraints": dict(constraints),
        "evaluated": combination_count,
        "feasible": len(candidates),
        "rejected": rejected[:25],
        "pareto_candidate_count": len(front),
        "candidates": front[:max_candidates],
        "truncated": len(front) > max_candidates,
        "application_rule": (
            "materialize the selected parameters, then call "
            "revise_stage_output(); never overwrite the source stage"
        ),
    }
    if unavailable_reason:
        result["reason"] = unavailable_reason
    return result


def materialize_optimization_candidate(
    layout: CabinetLayout,
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    parameters = candidate.get("resolved_parameters")
    if not isinstance(parameters, Mapping):
        raise ValueError("candidate requires resolved_parameters")
    return plan_panel_stage(layout, parameters)
