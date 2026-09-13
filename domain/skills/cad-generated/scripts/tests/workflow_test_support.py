"""Test-only helper: drive the interactive confirm / run_next loop.

Not a product entry. Production callers use FurnitureToolSession or the
Orchestrator stage methods and must confirm each checkpoint themselves.
"""

from __future__ import annotations

from typing import Any

from furniture_workflow.input_adapter import stage_inputs_from_spec
from furniture_workflow.workflow_orchestrator import (
    FurnitureOrchestrator,
    OrchestrationResult,
)
from furniture_workflow.workflow_project import Project
from furniture_workflow.workflow_state import (
    STAGE_SEQUENCE,
    WorkflowStage,
    parse_stage,
    stage_index,
)


def confirm_through(
    orchestrator: FurnitureOrchestrator,
    name: str,
    spec: dict[str, Any],
    *,
    through_stage: str | WorkflowStage | None = None,
    output_root: str | None = None,
    artifact_name: str | None = None,
    generate_cad: bool = False,
    force: bool = False,
) -> OrchestrationResult:
    intent = orchestrator.intent_from_spec(spec)
    project = orchestrator.create_project(
        name,
        intent,
        stage_inputs=stage_inputs_from_spec(spec),
    )
    return confirm_until(
        orchestrator,
        project,
        through_stage=through_stage,
        output_root=output_root,
        artifact_name=artifact_name,
        generate_cad=generate_cad,
        force=force,
    )


def confirm_until(
    orchestrator: FurnitureOrchestrator,
    project: Project,
    *,
    through_stage: str | WorkflowStage | None = None,
    output_root: str | None = None,
    artifact_name: str | None = None,
    generate_cad: bool = False,
    force: bool = False,
) -> OrchestrationResult:
    target = parse_stage(through_stage) if through_stage else (
        WorkflowStage.DELIVERY_VALIDATED
        if generate_cad
        else WorkflowStage.MANUFACTURING_PLANNED
    )
    while True:
        revision = project.latest
        current = revision.workflow.current
        if current == WorkflowStage.FAILED or current not in STAGE_SEQUENCE:
            break
        if not revision.is_stage_approved(current):
            if current.value not in revision.stage_outputs:
                break
            orchestrator.confirm_stage(project, current)
            revision = project.latest
            if (
                revision.workflow.current == WorkflowStage.FAILED
                or not revision.is_stage_approved(current)
            ):
                break
            current = revision.workflow.current
        if stage_index(current) >= stage_index(target):
            break
        next_stage = STAGE_SEQUENCE[stage_index(current) + 1]
        cad = next_stage == WorkflowStage.CAD_GENERATED
        orchestrator.run_next(
            project,
            output_root=output_root if cad else None,
            artifact_name=artifact_name if cad else None,
            generate_cad=cad,
            force=force if cad else False,
        )
        revision = project.latest
        attempt = revision.latest_attempt(next_stage)
        if attempt is not None and not attempt.passed:
            break
    return orchestrator._result(project)
