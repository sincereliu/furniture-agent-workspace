"""Furniture prototype experiment schedules derived from DOE principles."""

from __future__ import annotations

from itertools import product
import random
from typing import Any, Mapping


def _factor_domains(raw: Any) -> dict[str, list[Any]]:
    if not isinstance(raw, Mapping) or not raw:
        raise ValueError("factors must be a non-empty object")
    factors: dict[str, list[Any]] = {}
    for name, levels in raw.items():
        if not isinstance(levels, list) or len(levels) < 2:
            raise ValueError(f"factor {name} requires at least two levels")
        if len(levels) > 12:
            raise ValueError(f"factor {name} exceeds 12 levels")
        if len({repr(value) for value in levels}) != len(levels):
            raise ValueError(f"factor {name} contains duplicate levels")
        factors[str(name)] = list(levels)
    return factors


def design_prototype_experiment(
    manufacturing_output: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a seeded full-factorial schedule with explicit replicate level."""

    factors = _factor_domains(config.get("factors"))
    responses = config.get("responses")
    if not isinstance(responses, list) or not responses or not all(
        isinstance(item, str) and item.strip() for item in responses
    ):
        raise ValueError("responses must be a non-empty list of names")
    independent_unit = str(config.get("independent_unit", "")).strip()
    if not independent_unit:
        raise ValueError("independent_unit is required to prevent pseudoreplication")
    replicates = int(config.get("replicates", 1))
    if not 1 <= replicates <= 100:
        raise ValueError("replicates must be between 1 and 100")
    seed = int(config.get("seed", 42))
    if not 0 <= seed <= 2**63 - 1:
        raise ValueError("seed must be between 0 and 2**63-1")
    raw_blocks = config.get("blocks", ["block-1"])
    if not isinstance(raw_blocks, list) or not raw_blocks:
        raise ValueError("blocks must be a non-empty list")
    blocks = [str(item).strip() for item in raw_blocks]
    if any(not item for item in blocks) or len(set(blocks)) != len(blocks):
        raise ValueError("blocks must contain unique non-empty names")

    factor_names = list(factors)
    combinations = list(product(*(factors[name] for name in factor_names)))
    total_runs = len(combinations) * replicates
    max_runs = int(config.get("max_runs", 10_000))
    if not 1 <= max_runs <= 10_000 or total_runs > max_runs:
        raise ValueError(f"experiment has {total_runs} runs, above max_runs={max_runs}")

    rows: list[dict[str, Any]] = []
    for replicate in range(1, replicates + 1):
        for combination in combinations:
            rows.append(
                {
                    "replicate": replicate,
                    **dict(zip(factor_names, combination)),
                }
            )
    rng = random.Random(seed)
    rng.shuffle(rows)
    for index, row in enumerate(rows, start=1):
        row["run_order"] = index
        row["block"] = blocks[(index - 1) % len(blocks)]
        row["independent_unit_id"] = f"{independent_unit}-{index:04d}"

    return {
        "analysis": "prototype_experiment",
        "status": "completed",
        "engine": "seeded-full-factorial",
        "design": "full_factorial",
        "independent_unit": independent_unit,
        "factors": factors,
        "responses": [str(item) for item in responses],
        "n_factor_combinations": len(combinations),
        "run_count": total_runs,
        "replicates": replicates,
        "blocks": blocks,
        "seed": seed,
        "runs": rows,
        "source_summary": {
            "panel_count": len(manufacturing_output.get("panels", [])),
            "readiness": manufacturing_output.get("readiness", "preliminary"),
        },
        "limitations": [
            "sample size adequacy is not inferred from the requested replicate count",
            (
                "blocking labels are balanced by run order; the user must confirm "
                "they represent real nuisance factors"
            ),
            "repeated measurements on one independent unit are not additional replicates",
        ],
    }
