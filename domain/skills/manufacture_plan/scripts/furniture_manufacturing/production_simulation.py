"""Bounded panel-level production simulation with optional SimPy execution."""

from __future__ import annotations

from importlib.metadata import version
from math import isfinite, log, sqrt
import random
from statistics import fmean, stdev
from typing import Any, Mapping


def _validate_config(
    manufacturing_output: Mapping[str, Any], config: Mapping[str, Any]
) -> tuple[dict[str, int], dict[str, list[dict[str, Any]]], dict[str, Any] | None]:
    raw_resources = config.get("resources")
    if not isinstance(raw_resources, Mapping) or not raw_resources:
        raise ValueError("resources must be a non-empty capacity object")
    resources: dict[str, int] = {}
    for name, raw_capacity in raw_resources.items():
        capacity = int(raw_capacity)
        if isinstance(raw_capacity, bool) or capacity < 1 or capacity > 1000:
            raise ValueError(f"resource capacity must be 1..1000: {name}")
        resources[str(name)] = capacity

    raw_routes = config.get("routes")
    if not isinstance(raw_routes, Mapping) or not raw_routes:
        raise ValueError("routes must be a non-empty object keyed by panel_type or *")
    routes: dict[str, list[dict[str, Any]]] = {}
    for panel_type, raw_steps in raw_routes.items():
        if not isinstance(raw_steps, list) or not raw_steps or len(raw_steps) > 50:
            raise ValueError(f"route {panel_type} requires 1..50 operations")
        steps: list[dict[str, Any]] = []
        for index, raw_step in enumerate(raw_steps):
            if not isinstance(raw_step, Mapping):
                raise ValueError(f"route {panel_type} operation {index} is not an object")
            resource = str(raw_step.get("resource", ""))
            duration = float(raw_step.get("duration_min", 0.0))
            if resource not in resources:
                raise ValueError(f"route {panel_type} uses unknown resource: {resource}")
            if duration <= 0 or not isfinite(duration):
                raise ValueError(f"route duration must be finite and positive: {panel_type}")
            steps.append({"resource": resource, "duration_min": duration})
        routes[str(panel_type)] = steps

    panels = manufacturing_output.get("panels")
    if not isinstance(panels, list) or not panels:
        raise ValueError("manufacturing output requires panels")
    entity_count = sum(int(item.get("quantity", 1)) for item in panels)
    max_entities = int(config.get("max_entities", 10_000))
    if entity_count > max_entities or not 1 <= max_entities <= 10_000:
        raise ValueError(f"panel entities exceed max_entities={max_entities}")
    total_operations = sum(
        int(item.get("quantity", 1))
        * len(routes.get(str(item.get("panel_type")), routes.get("*", [])))
        for item in panels
    )
    if total_operations > 200_000:
        raise ValueError("model exceeds the 200000-operation bound")
    for item in panels:
        if str(item.get("panel_type")) not in routes and "*" not in routes:
            raise ValueError(f"no route for panel type: {item.get('panel_type')}")

    raw_assembly = config.get("assembly")
    assembly: dict[str, Any] | None = None
    if raw_assembly is not None:
        if not isinstance(raw_assembly, Mapping):
            raise ValueError("assembly must be an object")
        resource = str(raw_assembly.get("resource", ""))
        duration = float(raw_assembly.get("duration_min", 0.0))
        if resource not in resources or duration <= 0 or not isfinite(duration):
            raise ValueError("assembly requires a known resource and positive duration_min")
        assembly = {"resource": resource, "duration_min": duration}
    return resources, routes, assembly


def _sample_duration(mean: float, cv: float, rng: random.Random) -> float:
    if cv == 0:
        return mean
    sigma = sqrt(log(1.0 + cv * cv))
    mu = log(mean) - sigma * sigma / 2.0
    return rng.lognormvariate(mu, sigma)


def _run_simpy_replication(
    manufacturing_output: Mapping[str, Any],
    resources_config: Mapping[str, int],
    routes: Mapping[str, list[dict[str, Any]]],
    assembly: Mapping[str, Any] | None,
    *,
    seed: int,
    cv: float,
    max_time: float,
) -> dict[str, Any]:
    import simpy

    env = simpy.Environment()
    resources = {
        name: simpy.Resource(env, capacity=capacity)
        for name, capacity in resources_config.items()
    }
    busy = {name: 0.0 for name in resources}
    waits: list[float] = []
    completions: list[float] = []
    stream_seeds = {
        name: seed + 10_000 * (index + 1)
        for index, name in enumerate(sorted(resources))
    }
    rngs = {
        name: random.Random(stream_seed)
        for name, stream_seed in stream_seeds.items()
    }

    def panel_process(panel: Mapping[str, Any], entity_id: str):
        route = routes.get(str(panel.get("panel_type")), routes.get("*", []))
        for step in route:
            resource_name = step["resource"]
            requested_at = env.now
            with resources[resource_name].request() as request:
                yield request
                waits.append(env.now - requested_at)
                duration = _sample_duration(
                    float(step["duration_min"]),
                    cv,
                    rngs[resource_name],
                )
                busy[resource_name] += min(
                    duration,
                    max(0.0, max_time - env.now),
                )
                yield env.timeout(duration)
        completions.append(env.now)
        return entity_id

    panel_events = []
    for panel in manufacturing_output["panels"]:
        for item_index in range(int(panel.get("quantity", 1))):
            entity_id = f"{panel.get('label', panel.get('name', 'panel'))}:{item_index + 1}"
            panel_events.append(env.process(panel_process(panel, entity_id)))

    def complete_order():
        yield simpy.AllOf(env, panel_events)
        if assembly is not None:
            requested_at = env.now
            resource_name = str(assembly["resource"])
            with resources[resource_name].request() as request:
                yield request
                waits.append(env.now - requested_at)
                duration = _sample_duration(
                    float(assembly["duration_min"]),
                    cv,
                    rngs[resource_name],
                )
                busy[resource_name] += min(
                    duration,
                    max(0.0, max_time - env.now),
                )
                yield env.timeout(duration)
        return env.now

    order = env.process(complete_order())
    timeout = env.timeout(max_time)
    result = env.run(until=order | timeout)
    completed = order in result
    makespan = float(order.value) if completed else max_time
    return {
        "completed": completed,
        "makespan_min": makespan,
        "panel_entities": len(panel_events),
        "unfinished_entities": 0 if completed else len(panel_events) - len(completions),
        "total_wait_min": sum(waits),
        "mean_wait_min": fmean(waits) if waits else 0.0,
        "resource_utilization": {
            name: busy[name] / (resources_config[name] * makespan) if makespan else 0.0
            for name in resources
        },
        "seed": seed,
        "stream_seeds": stream_seeds,
    }


def _run_flowshop_fallback(
    manufacturing_output: Mapping[str, Any],
    resources_config: Mapping[str, int],
    routes: Mapping[str, list[dict[str, Any]]],
    assembly: Mapping[str, Any] | None,
) -> dict[str, Any]:
    available = {name: [0.0] * capacity for name, capacity in resources_config.items()}
    busy = {name: 0.0 for name in resources_config}
    waits: list[float] = []
    completions: list[float] = []
    entity_count = 0
    for panel in manufacturing_output["panels"]:
        route = routes.get(str(panel.get("panel_type")), routes.get("*", []))
        for _ in range(int(panel.get("quantity", 1))):
            entity_count += 1
            ready = 0.0
            for step in route:
                name = step["resource"]
                slot = min(range(len(available[name])), key=available[name].__getitem__)
                start = max(ready, available[name][slot])
                waits.append(start - ready)
                duration = float(step["duration_min"])
                ready = start + duration
                available[name][slot] = ready
                busy[name] += duration
            completions.append(ready)
    makespan = max(completions, default=0.0)
    if assembly is not None:
        name = str(assembly["resource"])
        slot = min(range(len(available[name])), key=available[name].__getitem__)
        start = max(makespan, available[name][slot])
        waits.append(start - makespan)
        duration = float(assembly["duration_min"])
        makespan = start + duration
        busy[name] += duration
    return {
        "completed": True,
        "makespan_min": makespan,
        "panel_entities": entity_count,
        "unfinished_entities": 0,
        "total_wait_min": sum(waits),
        "mean_wait_min": fmean(waits) if waits else 0.0,
        "resource_utilization": {
            name: busy[name] / (resources_config[name] * makespan) if makespan else 0.0
            for name in resources_config
        },
        "seed": None,
    }


def simulate_production(
    manufacturing_output: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Run bounded independent replications or an explicit deterministic fallback."""

    resources, routes, assembly = _validate_config(manufacturing_output, config)
    replications = int(config.get("replications", 20))
    if not 1 <= replications <= 500:
        raise ValueError("replications must be between 1 and 500")
    base_seed = int(config.get("seed", 42))
    cv = float(config.get("duration_cv", 0.0))
    max_time = float(config.get("max_time_min", 1_000_000.0))
    if not 0 <= cv <= 2 or max_time <= 0 or not isfinite(max_time):
        raise ValueError("duration_cv must be 0..2 and max_time_min must be positive")
    try:
        import simpy  # noqa: F401
    except ImportError:
        if bool(config.get("require_simpy", False)):
            return {
                "analysis": "production_simulation",
                "status": "unavailable",
                "engine": "simpy",
                "reason": "SimPy is not installed; install the furniture-analysis extra",
            }
        runs = [_run_flowshop_fallback(manufacturing_output, resources, routes, assembly)]
        engine = "bounded-deterministic-flowshop-fallback"
        limitations = [
            "SimPy was unavailable; the fallback uses deterministic FIFO flow-shop scheduling",
            "duration variability and independent-replication uncertainty were not evaluated",
        ]
    else:
        runs = [
            _run_simpy_replication(
                manufacturing_output,
                resources,
                routes,
                assembly,
                seed=base_seed + index,
                cv=cv,
                max_time=max_time,
            )
            for index in range(replications)
        ]
        engine = f"simpy-{version('simpy')}"
        limitations = [
            "results are implications of the declared routes, capacities, and duration model",
            "simulation contrasts are not causal evidence about the real factory",
        ]
    makespans = [float(item["makespan_min"]) for item in runs]
    summary: dict[str, Any] = {
        "mean_makespan_min": fmean(makespans),
        "min_makespan_min": min(makespans),
        "max_makespan_min": max(makespans),
        "sd_makespan_min": stdev(makespans) if len(makespans) > 1 else None,
        "completed_replications": sum(bool(item["completed"]) for item in runs),
    }
    if len(makespans) > 1:
        try:
            from scipy import stats
        except ImportError:
            limitations.append("SciPy was unavailable; no Student-t interval was computed")
        else:
            critical = float(stats.t.ppf(0.975, len(makespans) - 1))
            half_width = critical * stdev(makespans) / sqrt(len(makespans))
            summary["mean_makespan_95pct_ci_min"] = [
                summary["mean_makespan_min"] - half_width,
                summary["mean_makespan_min"] + half_width,
            ]
    return {
        "analysis": "production_simulation",
        "status": "completed",
        "engine": engine,
        "time_unit": "minute",
        "resources": resources,
        "routes": routes,
        "assembly": assembly,
        "duration_cv": cv if engine.startswith("simpy") else 0.0,
        "replications": len(runs),
        "base_seed": base_seed if engine.startswith("simpy") else None,
        "seed_manifest": (
            [
                {
                    "replication": index + 1,
                    "replication_seed": item["seed"],
                    "stream_seeds": item.get("stream_seeds", {}),
                }
                for index, item in enumerate(runs)
            ]
            if engine.startswith("simpy")
            else []
        ),
        "summary": summary,
        "runs": runs,
        "limitations": limitations,
    }
