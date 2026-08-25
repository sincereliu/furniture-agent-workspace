"""Serializable stage entrypoint for construction and physical panels."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from furniture_design_intent.design_intent import DesignIntent

from .panel_planning import plan_panels
from .panel_spec import admit_panel_proposal, spec_sha256
from .structure_planning import CabinetStructure


def plan_panel_stage(
    intent: DesignIntent,
    options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    admitted = admit_panel_proposal(intent, options)
    spec = admitted.spec
    structure = CabinetStructure.from_spec(spec)
    panels = plan_panels(spec, structure)
    serialized_spec = asdict(spec)
    output = {
        "proposal_admission": {
            "schema_version": 1,
            "panel_profile": admitted.panel_profile,
            "explicit_fields": list(admitted.explicit_fields),
            "proposal_sha256": admitted.proposal_sha256,
            "spec_sha256": spec_sha256(serialized_spec),
        },
        "spec": serialized_spec,
        "structure": asdict(structure),
        "back_mount_resolution": {
            "requested": admitted.requested_back_mount,
            "effective": spec.back_mount,
        },
        "panels": [asdict(item) for item in panels],
    }
    # The stage producer is also an admission boundary for direct structured
    # callers. Orchestrator confirmation repeats this validation before any
    # downstream CAD, BOM, manufacturing, or side effect is allowed.
    from .validation import validate_panel_output

    report = validate_panel_output(intent, output)
    if not report.passed:
        raise ValueError(
            "; ".join(f"{issue.code}: {issue.message}" for issue in report.issues)
        )
    return output
