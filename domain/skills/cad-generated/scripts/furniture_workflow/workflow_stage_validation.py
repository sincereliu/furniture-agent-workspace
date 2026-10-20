"""Validate stage outputs without owning lifecycle or persistence.

Only manufacturing needs frozen-panel access; the caller supplies that reader
so validators never depend on the application orchestrator.
"""

from __future__ import annotations

from typing import Any, Callable

from furniture_cad.cad_bridge import BridgeResult
from furniture_cad.validation import validate_cad
from furniture_contracts.validation import (
    ValidationReport,
    ValidationSeverity,
)
from furniture_layout.layout_figures import check_layout_figures
from furniture_feature_tree.validation import validate_feature_tree
from furniture_manufacturing.manufacturing_handoff import (
    cabinets_from_manufacturing,
)
from furniture_manufacturing.validation import validate_manufacturing
from furniture_panel_planning.validation import validate_panel_output

from .input_adapter import panel_envelopes_from_layout
from .workflow_cabinets import cabinets_from_bridges, cabinets_from_feature_trees
from .workflow_project import Revision
from .workflow_state import WorkflowStage


def _validate_every_cabinet(
    stage: WorkflowStage,
    revision: Revision,
    handoffs: list[tuple[str, Any, list[Any]]],
    boms: list[tuple[str, Any]],
) -> ValidationReport:
    """**逐柜**验收制造计划：每台柜都按它自己的 spec / 板件验一遍。

    一台不合格就整阶段不合格——不许"主柜过了就算过"。问题里点名是哪一台。
    """
    report = ValidationReport(stage=stage.value)
    handoffs_by_id = {
        cabinet_id: (spec, placements)
        for cabinet_id, spec, placements in handoffs
    }
    for cabinet_id, bom in boms:
        spec, placements = handoffs_by_id[cabinet_id]
        _merge_issues(
            report, cabinet_id, validate_manufacturing(spec, bom, placements)
        )
    return report

def _validate_every_tree(
    stage: WorkflowStage, revision: Revision
) -> ValidationReport:
    """**逐柜**验收特征树，与制造产物一一对应；问题里点名是哪一台。"""
    report = ValidationReport(stage=stage.value)
    for entry in cabinets_from_feature_trees(
        revision.stage_outputs[stage.value]
    ):
        _merge_issues(
            report, entry["id"], validate_feature_tree(entry["tree"])
        )
    return report

def _merge_issues(
    report: ValidationReport,
    cabinet_id: str,
    cabinet_report: ValidationReport,
) -> None:
    for issue in cabinet_report.issues:
        message = f"{cabinet_id}: {issue.message}"
        if issue.severity == ValidationSeverity.WARNING:
            report.add_warning(issue.code, message, issue.path)
        else:
            report.add_error(issue.code, message, issue.path)

def _validate_every_bridge(
    stage: WorkflowStage, revision: Revision
) -> ValidationReport:
    """**逐柜**验收 CAD，并且要求"规划过的每一台都在里面"。

    少了哪一台、哪一台失败，问题里都要点名——不然又会出现"三台只有一台到车间、
    交付照样通过"。
    """
    report = ValidationReport(stage=stage.value)
    entries = cabinets_from_bridges(revision.stage_outputs[stage.value])
    planned = [
        entry["id"]
        for entry in cabinets_from_manufacturing(
            revision.stage_outputs[WorkflowStage.MANUFACTURING_PLANNED.value]
        )
    ]
    produced = [entry["id"] for entry in entries]
    for cabinet_id in planned:
        if cabinet_id not in produced:
            report.add_error(
                "MISSING_CABINET_CAD",
                f"{cabinet_id}: no CAD result for a planned cabinet",
            )
    for entry in entries:
        _merge_issues(
            report,
            entry["id"],
            validate_cad(BridgeResult(**entry["bridge"])),
        )
    return report

def validate_stage_output(
    revision: Revision,
    stage: WorkflowStage,
    *,
    load_handoffs: Callable[[], list[tuple[str, Any, list[Any]]]],
    load_boms: Callable[[], list[tuple[str, Any]]],
) -> ValidationReport:
    try:
        if stage == WorkflowStage.LAYOUT_PLAN:
            return check_layout_figures(revision.layout.to_dict())
        if stage == WorkflowStage.PANELS_PLANNED:
            return validate_panel_output(
                panel_envelopes_from_layout(revision.layout),
                revision.stage_outputs[stage.value],
            )
        if stage == WorkflowStage.MANUFACTURING_PLANNED:
            return _validate_every_cabinet(stage, revision, load_handoffs(), load_boms())
        if stage == WorkflowStage.FEATURE_TREE_PLANNED:
            return _validate_every_tree(stage, revision)
        if stage == WorkflowStage.CAD_GENERATED:
            return _validate_every_bridge(stage, revision)
        if stage == WorkflowStage.DELIVERY_VALIDATED:
            report = ValidationReport(stage=stage.value)
            if not revision.stage_outputs[stage.value].get("passed", False):
                report.add_error(
                    "DELIVERY_NOT_VALIDATED",
                    "delivery validation report did not pass",
                )
            return report
    except (KeyError, TypeError, ValueError) as exc:
        report = ValidationReport(stage=stage.value)
        report.add_error("INVALID_STAGE_OUTPUT", str(exc))
        return report
    raise ValueError(f"unsupported validation stage: {stage.value}")
