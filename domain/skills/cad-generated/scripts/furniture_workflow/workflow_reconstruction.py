"""Rebuild pipeline snapshots from a Revision."""

from __future__ import annotations

import json
from typing import Any

from furniture_cad.cad_bridge import BridgeResult
from furniture_delivery_validation.validation import ValidationReport
from furniture_manufacturing.connection_points import ConnectionPoint
from furniture_manufacturing.features import feature_from_dict
from furniture_manufacturing.manufacturing_bom import BOMReport, emit_drilled_holes
from furniture_manufacturing.manufacturing_models import (
    HardwareRecord,
    MachiningOperation,
    MaterialRecord,
    PanelRecord,
)
from furniture_panel_planning.cabinet_identity import require_primary_handoff
from furniture_panel_planning.panel_models import PanelPlacement
from furniture_panel_planning.panel_spec import FurnitureSpec
from furniture_panel_planning.structure_planning import CabinetStructure

from .cabinet_pipeline import CabinetPipelineResult
from .workflow_constants import OrchestrationResult
from .workflow_project import Project, Revision
from .workflow_state import WorkflowStage


class ReconstructionMixin:
    @staticmethod
    def _latest_stage_validation(
        revision: Revision,
        stage: WorkflowStage,
    ) -> ValidationReport | None:
        return next(
            (
                report
                for report in reversed(revision.validations)
                if report.stage == stage.value
            ),
            None,
        )

    def _result(self, project: Project) -> OrchestrationResult:
        revision = project.latest
        pipeline = self._pipeline_from_revision(
            revision, project_id=project.id
        )
        return OrchestrationResult(
            project=project,
            revision=revision,
            pipeline=pipeline,
            bridge=self._bridge_from_revision(revision),
            drilled_holes=(
                emit_drilled_holes(pipeline.bom)
                if pipeline is not None
                else None
            ),
        )

    def _pipeline_from_revision(
        self,
        revision: Revision,
        *,
        project_id: str | None = None,
    ) -> CabinetPipelineResult | None:
        required = (
            WorkflowStage.PANELS_PLANNED.value,
            WorkflowStage.MANUFACTURING_PLANNED.value,
        )
        if not all(key in revision.stage_outputs for key in required):
            return None
        return CabinetPipelineResult(
            spec=self._spec_from_revision(revision, project_id=project_id),
            structure=self._structure_from_revision(
                revision, project_id=project_id
            ),
            placements=self._placements_from_revision(
                revision, project_id=project_id
            ),
            panels=self._panels_from_revision(revision),
            bom=self._bom_from_revision(revision),
        )

    def _resolved_stage_outputs(
        self,
        revision: Revision,
        *,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        outputs = dict(revision.stage_outputs)
        if WorkflowStage.PANELS_PLANNED.value in outputs:
            outputs[WorkflowStage.PANELS_PLANNED.value] = (
                self._confirmed_panel_output(revision, project_id=project_id)
            )
        return outputs

    def _stage_source_output(
        self,
        revision: Revision,
        stage: WorkflowStage,
        *,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        if stage == WorkflowStage.PANELS_PLANNED:
            return self._confirmed_panel_output(revision, project_id=project_id)
        output = revision.stage_outputs.get(stage.value)
        if not isinstance(output, dict):
            raise ValueError(f"stage output is required: {stage.value}")
        return output

    def _confirmed_panel_output(
        self,
        revision: Revision,
        *,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        live = revision.stage_outputs.get(WorkflowStage.PANELS_PLANNED.value)
        if not isinstance(live, dict):
            raise ValueError("panel_plan output is required")
        digest = revision.confirmed_panel_sha256
        if self.project_store is None or not project_id or not digest:
            return live
        path = self.project_store.panel_path(project_id, digest)
        if not path.is_file():
            raise ValueError(f"frozen panel plan is missing: {path}")
        frozen = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(frozen, dict):
            raise ValueError("frozen panel plan must be an object")
        return frozen

    def _spec_from_revision(
        self,
        revision: Revision,
        *,
        project_id: str | None = None,
    ) -> FurnitureSpec:
        spec, _, _ = require_primary_handoff(
            self._confirmed_panel_output(revision, project_id=project_id)
        )
        return FurnitureSpec.from_dict(spec)

    def _structure_from_revision(
        self,
        revision: Revision,
        *,
        project_id: str | None = None,
    ) -> CabinetStructure:
        _, structure, _ = require_primary_handoff(
            self._confirmed_panel_output(revision, project_id=project_id)
        )
        return CabinetStructure.from_dict(structure)

    def _placements_from_revision(
        self,
        revision: Revision,
        *,
        project_id: str | None = None,
    ) -> list[PanelPlacement]:
        _, _, panels = require_primary_handoff(
            self._confirmed_panel_output(revision, project_id=project_id)
        )
        return [PanelPlacement.from_dict(item) for item in panels]

    @staticmethod
    def _panels_from_revision(revision: Revision) -> list[PanelRecord]:
        output = revision.stage_outputs[WorkflowStage.MANUFACTURING_PLANNED.value]
        return [PanelRecord.from_dict(item) for item in output.get("panels", [])]

    @staticmethod
    def _bom_from_revision(revision: Revision) -> BOMReport:
        output = revision.stage_outputs[WorkflowStage.MANUFACTURING_PLANNED.value]
        return BOMReport(
            furniture_name=str(output["furniture_name"]),
            dimensions=str(output["dimensions"]),
            panels=[PanelRecord.from_dict(item) for item in output.get("panels", [])],
            hardware=[HardwareRecord(**item) for item in output.get("hardware", [])],
            operations=[
                MachiningOperation(**item) for item in output.get("operations", [])
            ],
            materials=[
                MaterialRecord(**item) for item in output.get("materials", [])
            ],
            furniture_category=str(output.get("furniture_category", "")),
            width=float(output.get("width", 0.0)),
            depth=float(output.get("depth", 0.0)),
            height=float(output.get("height", 0.0)),
            board_thickness=float(output.get("board_thickness", 0.0)),
            total_area_m2=float(output.get("total_area_m2", 0.0)),
            readiness=str(output.get("readiness", "preliminary")),
            requested_options=dict(output.get("requested_options", {})),
            appearance=dict(output.get("appearance", {})),
            features=[
                feature_from_dict(item) for item in output.get("features", [])
            ],
            connection_points=[
                ConnectionPoint.from_dict(item)
                for item in output.get("connection_points", [])
            ],
        )

    @staticmethod
    def _bridge_from_revision(revision: Revision) -> BridgeResult | None:
        output = revision.stage_outputs.get(WorkflowStage.CAD_GENERATED.value)
        return BridgeResult(**output) if output else None
