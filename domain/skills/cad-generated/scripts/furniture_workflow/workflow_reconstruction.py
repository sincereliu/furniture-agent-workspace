"""Rebuild pipeline snapshots from a Revision."""

from __future__ import annotations

import json
from typing import Any, Mapping

from furniture_cad.cad_bridge import BridgeResult
from furniture_delivery_validation.validation import ValidationReport
from furniture_manufacturing.connection_points import ConnectionPoint
from furniture_manufacturing.features import feature_from_dict
from furniture_manufacturing.manufacturing_bom import BOMReport
from furniture_manufacturing.manufacturing_handoff import (
    cabinets_from_manufacturing,
)
from furniture_manufacturing.manufacturing_models import (
    HardwareRecord,
    MachiningOperation,
    MaterialRecord,
    PanelRecord,
)
from furniture_panel_planning.cabinet_identity import handoffs_from_output
from furniture_panel_planning.panel_models import PanelPlacement
from furniture_panel_planning.panel_spec import FurnitureSpec
from furniture_panel_planning.structure_planning import CabinetStructure

from .cabinet_pipeline import CabinetPipelineResult
from .workflow_cabinets import cabinets_from_bridges
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
        return OrchestrationResult(
            project=project,
            revision=revision,
            cabinets=self._pipelines_from_revision(
                revision, project_id=project.id
            ),
            bridges=self._bridges_from_revision(revision),
        )

    def _pipelines_from_revision(
        self,
        revision: Revision,
        *,
        project_id: str | None = None,
    ) -> tuple[CabinetPipelineResult, ...]:
        """**逐柜**快照（板件 + 制造），一台柜一项；上游没齐就是空的。"""
        required = (
            WorkflowStage.PANELS_PLANNED.value,
            WorkflowStage.MANUFACTURING_PLANNED.value,
        )
        if not all(key in revision.stage_outputs for key in required):
            return ()
        boms = dict(self._cabinet_boms(revision))
        return tuple(
            CabinetPipelineResult(
                cabinet_id=cabinet_id,
                spec=spec,
                structure=CabinetStructure.from_spec(spec),
                placements=placements,
                panels=boms[cabinet_id].panels,
                bom=boms[cabinet_id],
            )
            for cabinet_id, spec, placements in self._cabinet_handoffs(
                revision, project_id=project_id
            )
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

    def _cabinet_handoffs(
        self,
        revision: Revision,
        *,
        project_id: str | None = None,
    ) -> list[tuple[str, FurnitureSpec, list[PanelPlacement]]]:
        """**逐柜**的 `(id, spec, 该柜的板件放置)`——制造阶段按它一台一台算。

        以前只取主柜（`_spec_from_revision` / `_placements_from_revision`），
        所以布局里摆了三台也只有一台有 BOM。
        """
        output = self._confirmed_panel_output(revision, project_id=project_id)
        handoffs = handoffs_from_output(output)
        return [
            (
                cabinet_id,
                FurnitureSpec.from_dict(spec),
                [PanelPlacement.from_dict(item) for item in panels],
            )
            for cabinet_id, spec, _, panels in handoffs
        ]

    @staticmethod
    def _cabinet_boms(revision: Revision) -> list[tuple[str, BOMReport]]:
        """**逐柜**的 `(id, BOM)`——特征树 / 逐柜产物按它一台一台做。"""
        output = revision.stage_outputs[WorkflowStage.MANUFACTURING_PLANNED.value]
        return [
            (entry["id"], ReconstructionMixin._bom_from_dict(entry["bom"]))
            for entry in cabinets_from_manufacturing(output)
        ]

    @staticmethod
    def _bom_from_dict(output: Mapping[str, Any]) -> BOMReport:
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
    def _bridges_from_revision(revision: Revision) -> tuple[BridgeResult, ...]:
        """**逐柜** CAD 结果；没跑过 CAD 就是空的。"""
        output = revision.stage_outputs.get(WorkflowStage.CAD_GENERATED.value)
        if not isinstance(output, Mapping):
            return ()
        return tuple(
            BridgeResult(**entry["bridge"])
            for entry in cabinets_from_bridges(output)
        )
