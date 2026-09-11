"""Bounded statistics for already-collected furniture prototype measurements."""

from __future__ import annotations

from math import isfinite, sqrt
from statistics import fmean, stdev
from typing import Any, Mapping


def _descriptive(values: list[float]) -> dict[str, Any]:
    ordered = sorted(values)
    middle = len(ordered) // 2
    median = (
        ordered[middle]
        if len(ordered) % 2
        else (ordered[middle - 1] + ordered[middle]) / 2.0
    )
    return {
        "n": len(values),
        "mean": fmean(values),
        "sd": stdev(values) if len(values) > 1 else None,
        "median": median,
        "min": ordered[0],
        "max": ordered[-1],
    }


def _hedges_g(a: list[float], b: list[float]) -> float | None:
    if len(a) < 2 or len(b) < 2:
        return None
    pooled_df = len(a) + len(b) - 2
    pooled_variance = (
        (len(a) - 1) * stdev(a) ** 2 + (len(b) - 1) * stdev(b) ** 2
    ) / pooled_df
    if pooled_variance <= 0:
        return 0.0 if fmean(a) == fmean(b) else None
    d = (fmean(a) - fmean(b)) / sqrt(pooled_variance)
    correction = 1.0 - 3.0 / (4.0 * (len(a) + len(b)) - 9.0)
    return d * correction


def _hedges_g_standard_error(
    a: list[float],
    b: list[float],
    hedges_g: float | None,
) -> float | None:
    """Approximate large-sample standard error for standardized mean difference."""

    if hedges_g is None or len(a) < 2 or len(b) < 2:
        return None
    degrees_of_freedom = len(a) + len(b) - 2
    correction = 1.0 - 3.0 / (4.0 * (len(a) + len(b)) - 9.0)
    d = hedges_g / correction
    variance_d = (
        (len(a) + len(b)) / (len(a) * len(b))
        + d * d / (2.0 * degrees_of_freedom)
    )
    return correction * sqrt(variance_d)


def _finite_or_none(value: Any) -> float | None:
    result = float(value)
    return result if isfinite(result) else None


def analyze_prototype_results(
    manufacturing_output: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Analyze explicit records; never fabricate observations from a DOE plan."""

    records = config.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("records must be a non-empty list of collected observations")
    if len(records) > 100_000:
        raise ValueError("records exceed the 100000-row bound")
    group_field = str(config.get("group_field", "group")).strip()
    value_field = str(config.get("value_field", "value")).strip()
    if not group_field or not value_field:
        raise ValueError("group_field and value_field are required")
    alpha = float(config.get("alpha", 0.05))
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1")

    groups: dict[str, list[float]] = {}
    missing = 0
    for index, row in enumerate(records):
        if not isinstance(row, Mapping):
            raise ValueError(f"record {index} is not an object")
        group = row.get(group_field)
        raw_value = row.get(value_field)
        if group is None or raw_value is None or raw_value == "":
            missing += 1
            continue
        value = float(raw_value)
        if not isfinite(value):
            raise ValueError(f"record {index} has a non-finite value")
        groups.setdefault(str(group), []).append(value)
    if not groups:
        raise ValueError("no complete observations remain")

    report: dict[str, Any] = {
        "analysis": "test_statistics",
        "status": "descriptive_only",
        "engine": "python-statistics",
        "group_field": group_field,
        "value_field": value_field,
        "alpha": alpha,
        "missing_rows": missing,
        "descriptives": {name: _descriptive(values) for name, values in groups.items()},
        "assumption_checks": {},
        "inference": None,
        "source_summary": {
            "readiness": manufacturing_output.get("readiness", "preliminary"),
            "panel_count": len(manufacturing_output.get("panels", [])),
        },
        "limitations": [
            "analysis assumes each row is an independent unit unless the design says otherwise",
            "no missing-value imputation or outlier removal is performed",
            (
                "statistical significance does not automatically establish practical "
                "or manufacturing importance"
            ),
        ],
    }
    try:
        from scipy import stats
    except ImportError:
        report["limitations"].append("SciPy is unavailable; only descriptives were computed")
        return report

    report["engine"] = "scipy"
    for name, values in groups.items():
        if 3 <= len(values) <= 5000:
            result = stats.shapiro(values)
            report["assumption_checks"][f"shapiro:{name}"] = {
                "statistic": _finite_or_none(result.statistic),
                "p_value": _finite_or_none(result.pvalue),
            }
    group_values = list(groups.values())
    if len(groups) >= 2 and all(len(values) >= 2 for values in group_values):
        levene = stats.levene(*group_values, center="median")
        report["assumption_checks"]["levene"] = {
            "statistic": _finite_or_none(levene.statistic),
            "p_value": _finite_or_none(levene.pvalue),
        }

    if len(groups) == 2 and all(len(values) >= 2 for values in group_values):
        names = list(groups)
        a, b = group_values
        test = stats.ttest_ind(a, b, equal_var=False)
        va = stdev(a) ** 2 / len(a)
        vb = stdev(b) ** 2 / len(b)
        df = (va + vb) ** 2 / (
            va**2 / (len(a) - 1) + vb**2 / (len(b) - 1)
        ) if va + vb else float(len(a) + len(b) - 2)
        difference = fmean(a) - fmean(b)
        critical = float(stats.t.ppf(1.0 - alpha / 2.0, df))
        half_width = critical * sqrt(va + vb)
        hedges_g = _hedges_g(a, b)
        hedges_g_se = _hedges_g_standard_error(a, b, hedges_g)
        effect_critical = float(stats.norm.ppf(1.0 - alpha / 2.0))
        report["inference"] = {
            "test": "welch_t_test",
            "groups": names,
            "mean_difference": difference,
            "confidence_interval": [difference - half_width, difference + half_width],
            "confidence_level": 1.0 - alpha,
            "statistic": _finite_or_none(test.statistic),
            "degrees_of_freedom": df,
            "p_value": _finite_or_none(test.pvalue),
            "hedges_g": hedges_g,
            "hedges_g_confidence_interval": (
                [
                    hedges_g - effect_critical * hedges_g_se,
                    hedges_g + effect_critical * hedges_g_se,
                ]
                if hedges_g is not None and hedges_g_se is not None
                else None
            ),
            "effect_size_ci_method": "large-sample normal approximation",
        }
        report["status"] = "completed"
    elif len(groups) >= 3 and all(len(values) >= 2 for values in group_values):
        levene_p = report["assumption_checks"].get("levene", {}).get("p_value")
        if levene_p is not None and levene_p >= alpha:
            test = stats.f_oneway(*group_values)
            all_values = [value for values in group_values for value in values]
            grand = fmean(all_values)
            between = sum(len(values) * (fmean(values) - grand) ** 2 for values in group_values)
            total = sum((value - grand) ** 2 for value in all_values)
            report["inference"] = {
                "test": "one_way_anova",
                "statistic": _finite_or_none(test.statistic),
                "p_value": _finite_or_none(test.pvalue),
                "eta_squared": between / total if total else 0.0,
                "post_hoc": "not_run",
            }
            report["status"] = "completed"
        else:
            report["limitations"].append(
                "group variances are not homogeneous; one-way ANOVA was not run"
            )
    else:
        report["limitations"].append(
            "at least two observations per group are required for inference"
        )
    return report
