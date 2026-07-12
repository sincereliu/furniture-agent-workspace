"""Single deterministic orchestrator for the first cabinet vertical slice."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Any

from furniture.cad_bridge import BridgeResult, CadBridge
from furniture.feature_tree_builder import panels_to_feature_tree
from furniture.feature_tree_emitter import write_build123d_source
from furniture.manufacturing_bom import BOMReport, format_bom_markdown
from furniture.manufacturing_models import HardwareRecord
from furniture.layout_pipeline import (
    SUPPORTED_TYPES,
    CabinetPipelineResult,
    plan_layout,
    plan_manufacturing,
    plan_panels,
)
from furniture.panel_models import PanelPlacement, PanelRecord
from furniture.design_intent import DesignIntent
from furniture.workflow_project import Project, Revision
from furniture.design_spec import FurnitureSpec
from furniture.validation import ValidationReport
from furniture.workflow_state import (
    STAGE_SEQUENCE,
    WorkflowStage,
    WorkflowState,
    parse_stage,
    stage_index,
)


SAFE_ARTIFACT_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
EDITABLE_STAGE_OUTPUTS = {
    WorkflowStage.LAYOUT_PLANNED,
    WorkflowStage.PANELS_PLANNED,
    WorkflowStage.MANUFACTURING_PLANNED,
    WorkflowStage.FEATURE_TREE_PLANNED,
}


@dataclass(frozen=True)
class OrchestrationResult:
    project: Project
    revision: Revision
    pipeline: CabinetPipelineResult | None
    bridge: BridgeResult | None = None


class FurnitureOrchestrator:
    """Own workflow state while delegating domain work to existing packages."""

    def __init__(
        self,
        workspace_root: str | Path | None = None,
        cad_bridge: CadBridge | None = None,
    ) -> None:
        self.workspace_root = Path(
            workspace_root or Path(__file__).resolve().parents[4]
        ).resolve()
        self.cad_bridge = cad_bridge or CadBridge(workspace_root=self.workspace_root)

    def create_project(self, name: str, intent: DesignIntent) -> Project:
        project = Project(name=name)
        project.add_revision(intent)
        return project

    def revise(self, project: Project, intent: DesignIntent) -> Revision:
        """Start a new revision at stage 1; all parent artifacts become stale."""
        return project.add_revision(intent)

    def revise_stage_output(
        self,
        project: Project,
        stage: str | WorkflowStage,
        output: dict[str, Any],
    ) -> Revision:
        """Create a revision from an edited stage-2..5 output.

        Only confirmed upstream outputs are copied. The edited stage must be
        confirmed again, and every downstream stage is deliberately absent so
        it will be regenerated from the changed source of truth.
        """
        changed_stage = parse_stage(stage)
        if changed_stage not in EDITABLE_STAGE_OUTPUTS:
            editable = ", ".join(item.value for item in EDITABLE_STAGE_OUTPUTS)
            raise ValueError(f"stage output is not directly editable; use one of: {editable}")

        parent = project.latest
        if changed_stage.value not in parent.stage_outputs:
            raise ValueError(f"stage has no output to revise: {changed_stage.value}")

        revision = project.add_revision(
            DesignIntent.from_dict(parent.intent.to_dict())
        )
        revision.stage_outputs = {
            key: deepcopy(value)
            for key, value in parent.stage_outputs.items()
            if stage_index(parse_stage(key)) < stage_index(changed_stage)
        }
        revision.stage_outputs[WorkflowStage.DESIGN_INTENT.value] = (
            revision.intent.to_dict()
        )
        revision.stage_outputs[changed_stage.value] = deepcopy(output)
        revision.approved_stages = [
            value
            for value in parent.approved_stages
            if stage_index(parse_stage(value)) < stage_index(changed_stage)
        ]
        revision.workflow = WorkflowState()
        if changed_stage != WorkflowStage.DESIGN_INTENT:
            revision.workflow.advance(
                changed_stage,
                f"{changed_stage.value} revised; downstream outputs invalidated",
            )
        if changed_stage == WorkflowStage.FEATURE_TREE_PLANNED:
            revision.feature_tree = deepcopy(output)
        return revision

    def execute_spec(
        self,
        name: str,
        spec: dict[str, Any],
        *,
        output_root: str | Path | None = None,
        artifact_name: str | None = None,
        generate_cad: bool = False,
        force: bool = False,
        through_stage: str | WorkflowStage | None = None,
    ) -> OrchestrationResult:
        """Run an explicit batch request through the same seven-stage workflow.

        Interactive Agent work must use confirm_stage() + run_next() so every
        stage remains visible. CLI/API batch requests may use this method to
        auto-confirm successful intermediate stages without creating a second
        execution path.
        """
        intent = self.intent_from_spec(spec)
        project = self.create_project(name, intent)
        self.confirm_intent(project)
        target = parse_stage(through_stage) if through_stage else (
            WorkflowStage.DELIVERY_VALIDATED
            if generate_cad
            else WorkflowStage.MANUFACTURING_PLANNED
        )
        return self.run_until(
            project,
            target,
            output_root=output_root,
            artifact_name=artifact_name,
            generate_cad=generate_cad,
            force=force,
            auto_confirm=True,
        )

    @staticmethod
    def intent_from_spec(spec: dict[str, Any]) -> DesignIntent:
        """Convert the maintained flat executable JSON into a DesignIntent."""
        data = dict(spec)
        furniture_type = str(
            data.get("type", data.get("furniture_type", ""))
        ).strip().lower()
        size = data.get("overall_size", {})
        normalized_spec = FurnitureSpec.from_dict({**data, "type": furniture_type})

        def dimension(nested_key: str, flat_key: str, fallback: float) -> Any:
            value = size.get(nested_key, data.get(flat_key))
            return fallback if value is None else value

        layout = dict(data.get("layout", {}))
        for key in ("shelf_count", "n_doors", "toe_kick_height"):
            if key in data:
                layout[key] = data[key]

        structure = dict(data.get("structure", {}))
        reserved = {
            "type",
            "furniture_type",
            "width",
            "depth",
            "height",
            "overall_size",
            "purpose",
            "layout",
            "appearance",
            "structure",
            "constraints",
            "assumptions",
            "unresolved",
            "confirmed",
            "schema_version",
            "shelf_count",
            "n_doors",
            "toe_kick_height",
        }
        for key, value in data.items():
            if key not in reserved:
                structure[key] = value

        return DesignIntent.from_dict(
            {
                "furniture_type": furniture_type,
                "overall_size": {
                    "width_mm": dimension(
                        "width_mm", "width", normalized_spec.width
                    ),
                    "depth_mm": dimension(
                        "depth_mm", "depth", normalized_spec.depth
                    ),
                    "height_mm": dimension(
                        "height_mm", "height", normalized_spec.height
                    ),
                },
                "purpose": data.get("purpose", ""),
                "layout": layout,
                "appearance": data.get("appearance", {}),
                "structure": structure,
                "constraints": data.get("constraints", []),
                "assumptions": data.get("assumptions", {}),
                "unresolved": data.get("unresolved", []),
                "schema_version": data.get("schema_version", 1),
            }
        )

    def confirm_intent(self, project: Project) -> Revision:
        return self.confirm_stage(project, WorkflowStage.DESIGN_INTENT)

    def confirm_stage(
        self,
        project: Project,
        stage: str | WorkflowStage | None = None,
    ) -> Revision:
        """Approve the current stage so the next stage may execute."""
        revision = project.latest
        current = revision.workflow.current
        requested = parse_stage(stage) if stage is not None else current
        if current == WorkflowStage.FAILED:
            raise ValueError("failed revision must be replaced with a new revision")
        if requested != current:
            raise ValueError(
                f"only the current stage may be confirmed: {current.value}"
            )
        if requested.value not in revision.stage_outputs:
            raise ValueError(f"current stage has no output: {requested.value}")

        if requested == WorkflowStage.DESIGN_INTENT:
            revision.intent = revision.intent.confirm()
            revision.stage_outputs[requested.value] = revision.intent.to_dict()

        report = self._validate_stage_output(revision, requested)
        revision.validations.append(report)
        if not report.passed:
            revision.workflow.fail(f"{requested.value} validation failed")
            return revision

        revision.approve_stage(requested)
        revision.workflow.record(f"{requested.value} confirmed")
        return revision

    def run_next(
        self,
        project: Project,
        *,
        output_root: str | Path | None = None,
        artifact_name: str | None = None,
        generate_cad: bool = False,
        force: bool = False,
    ) -> OrchestrationResult:
        """Execute exactly one stage after the current confirmed checkpoint."""
        revision = project.latest
        if revision.workflow.current == WorkflowStage.FAILED:
            return self._result(project)
        current_index = stage_index(revision.workflow.current)
        if current_index == len(STAGE_SEQUENCE) - 1:
            return self._result(project)
        return self.run_until(
            project,
            STAGE_SEQUENCE[current_index + 1],
            output_root=output_root,
            artifact_name=artifact_name,
            generate_cad=generate_cad,
            force=force,
            auto_confirm=False,
        )

    def run(
        self,
        project: Project,
        *,
        output_root: str | Path | None = None,
        artifact_name: str | None = None,
        generate_cad: bool = False,
        force: bool = False,
        through_stage: str | WorkflowStage | None = None,
        auto_confirm: bool = False,
    ) -> OrchestrationResult:
        target = parse_stage(through_stage) if through_stage else (
            WorkflowStage.DELIVERY_VALIDATED
            if generate_cad
            else WorkflowStage.FEATURE_TREE_PLANNED
        )
        return self.run_until(
            project,
            target,
            output_root=output_root,
            artifact_name=artifact_name,
            generate_cad=generate_cad,
            force=force,
            auto_confirm=auto_confirm,
        )

    def run_until(
        self,
        project: Project,
        target_stage: str | WorkflowStage,
        *,
        output_root: str | Path | None = None,
        artifact_name: str | None = None,
        generate_cad: bool = False,
        force: bool = False,
        auto_confirm: bool = False,
    ) -> OrchestrationResult:
        """Run toward a target, pausing at the first unconfirmed stage by default."""
        target = parse_stage(target_stage)
        revision = project.latest
        try:
            while (
                revision.workflow.current != WorkflowStage.FAILED
                and stage_index(revision.workflow.current) < stage_index(target)
            ):
                current = revision.workflow.current
                if not revision.is_stage_approved(current):
                    break
                next_stage = STAGE_SEQUENCE[stage_index(current) + 1]
                self._execute_stage(
                    project,
                    revision,
                    next_stage,
                    output_root=output_root,
                    artifact_name=artifact_name,
                    generate_cad=generate_cad,
                    force=force,
                )
                if revision.workflow.current == WorkflowStage.FAILED:
                    break
                if auto_confirm:
                    self.confirm_stage(project, next_stage)
                else:
                    break

            if (
                auto_confirm
                and revision.workflow.current == target
                and not revision.is_stage_approved(target)
            ):
                self.confirm_stage(project, target)
            return self._result(project)
        except (OSError, TypeError, ValueError) as exc:
            report = ValidationReport(stage="orchestration")
            report.add_error("ORCHESTRATION_FAILED", str(exc))
            revision.validations.append(report)
            revision.workflow.fail(str(exc))
            return self._result(project)

    def _execute_stage(
        self,
        project: Project,
        revision: Revision,
        stage: WorkflowStage,
        *,
        output_root: str | Path | None,
        artifact_name: str | None,
        generate_cad: bool,
        force: bool,
    ) -> None:
        spec = self._to_spec(revision.intent)

        if stage == WorkflowStage.LAYOUT_PLANNED:
            output = {
                "placements": [asdict(item) for item in plan_layout(spec)],
            }
            self._complete_stage(
                revision,
                stage,
                output,
                "layout placements planned",
            )
            return

        if stage == WorkflowStage.PANELS_PLANNED:
            panels = plan_panels(self._placements_from_revision(revision))
            self._complete_stage(
                revision,
                stage,
                {"panels": [asdict(item) for item in panels]},
                "manufacturing panel records planned",
            )
            return

        if stage == WorkflowStage.MANUFACTURING_PLANNED:
            bom = plan_manufacturing(spec, self._panels_from_revision(revision))
            self._complete_stage(
                revision,
                stage,
                asdict(bom),
                "materials, hardware, and preliminary BOM planned",
            )
            return

        if stage == WorkflowStage.FEATURE_TREE_PLANNED:
            panels = self._panels_from_revision(revision)
            feature_tree = panels_to_feature_tree(
                panels,
                furniture_type=spec.furniture_type,
                parameters={
                    "width": spec.width,
                    "depth": spec.depth,
                    "height": spec.height,
                    "board_thickness": spec.board_thickness,
                },
            )
            revision.feature_tree = feature_tree
            self._complete_stage(
                revision,
                stage,
                feature_tree,
                "box-based Feature Tree v1 planned",
            )
            return

        if stage == WorkflowStage.CAD_GENERATED:
            if output_root is None:
                raise ValueError("CAD generation requires output_root")
            if not generate_cad:
                raise ValueError("CAD generation requires generate_cad=True")
            pipeline = self._pipeline_from_revision(revision)
            if pipeline is None:
                raise ValueError("manufacturing stage must exist before CAD generation")
            artifact_dir = self._artifact_dir(
                output_root,
                project,
                revision,
                artifact_name=artifact_name,
            )
            source_path, step_path = self._write_artifacts(
                revision,
                pipeline,
                artifact_dir,
                artifact_name=artifact_name,
            )
            bridge = self.cad_bridge.generate_from_source(
                source_path,
                step_path,
                force=force,
            )
            revision.stage_outputs[stage.value] = asdict(bridge)
            if bridge.status == "ok":
                if bridge.step_path:
                    revision.manifest.add_file("step", bridge.step_path)
                if bridge.topology_path:
                    revision.manifest.add_file("viewer_topology", bridge.topology_path)
            report = self._validate_stage_output(revision, stage)
            revision.validations.append(report)
            if not report.passed:
                revision.workflow.fail(bridge.message)
                return
            revision.workflow.advance(stage, "STEP and Viewer topology generated")
            return

        if stage == WorkflowStage.DELIVERY_VALIDATED:
            report = self._validate_artifacts(revision)
            revision.stage_outputs[stage.value] = report.to_dict()
            revision.validations.append(report)
            if not report.passed:
                revision.workflow.fail("delivery validation failed")
                return
            revision.workflow.advance(stage, "delivery artifacts verified")
            return

        raise ValueError(f"stage is not executable: {stage.value}")

    def _complete_stage(
        self,
        revision: Revision,
        stage: WorkflowStage,
        output: dict[str, Any],
        note: str,
    ) -> None:
        revision.stage_outputs[stage.value] = deepcopy(output)
        report = self._validate_stage_output(revision, stage)
        revision.validations.append(report)
        if not report.passed:
            revision.workflow.fail(f"{stage.value} validation failed")
            return
        revision.workflow.advance(stage, note)

    def _result(self, project: Project) -> OrchestrationResult:
        revision = project.latest
        return OrchestrationResult(
            project=project,
            revision=revision,
            pipeline=self._pipeline_from_revision(revision),
            bridge=self._bridge_from_revision(revision),
        )

    def _pipeline_from_revision(
        self,
        revision: Revision,
    ) -> CabinetPipelineResult | None:
        required = (
            WorkflowStage.LAYOUT_PLANNED.value,
            WorkflowStage.PANELS_PLANNED.value,
            WorkflowStage.MANUFACTURING_PLANNED.value,
        )
        if not all(key in revision.stage_outputs for key in required):
            return None
        return CabinetPipelineResult(
            spec=self._to_spec(revision.intent),
            placements=self._placements_from_revision(revision),
            panels=self._panels_from_revision(revision),
            bom=self._bom_from_revision(revision),
        )

    def _placements_from_revision(self, revision: Revision) -> list[PanelPlacement]:
        output = revision.stage_outputs[WorkflowStage.LAYOUT_PLANNED.value]
        return [PanelPlacement(**item) for item in output.get("placements", [])]

    def _panels_from_revision(self, revision: Revision) -> list[PanelRecord]:
        output = revision.stage_outputs[WorkflowStage.PANELS_PLANNED.value]
        return [PanelRecord(**item) for item in output.get("panels", [])]

    def _bom_from_revision(self, revision: Revision) -> BOMReport:
        output = revision.stage_outputs[WorkflowStage.MANUFACTURING_PLANNED.value]
        return BOMReport(
            furniture_name=str(output["furniture_name"]),
            dimensions=str(output["dimensions"]),
            panels=[PanelRecord(**item) for item in output.get("panels", [])],
            hardware=[HardwareRecord(**item) for item in output.get("hardware", [])],
            total_area_m2=float(output.get("total_area_m2", 0.0)),
        )

    def _bridge_from_revision(self, revision: Revision) -> BridgeResult | None:
        output = revision.stage_outputs.get(WorkflowStage.CAD_GENERATED.value)
        return BridgeResult(**output) if output else None

    def _validate_stage_output(
        self,
        revision: Revision,
        stage: WorkflowStage,
    ) -> ValidationReport:
        try:
            if stage == WorkflowStage.DESIGN_INTENT:
                return self._validate_intent(revision.intent)
            if stage == WorkflowStage.LAYOUT_PLANNED:
                return self._validate_layout(
                    self._to_spec(revision.intent),
                    self._placements_from_revision(revision),
                )
            if stage == WorkflowStage.PANELS_PLANNED:
                return self._validate_panels(self._panels_from_revision(revision))
            if stage == WorkflowStage.MANUFACTURING_PLANNED:
                return self._validate_manufacturing(
                    self._bom_from_revision(revision),
                    self._panels_from_revision(revision),
                )
            if stage == WorkflowStage.FEATURE_TREE_PLANNED:
                return self._validate_feature_tree(
                    revision.stage_outputs[stage.value]
                )
            if stage == WorkflowStage.CAD_GENERATED:
                return self._validate_cad(self._bridge_from_revision(revision))
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

    def _validate_layout(
        self,
        spec: FurnitureSpec,
        placements: list[PanelPlacement],
    ) -> ValidationReport:
        report = ValidationReport(stage=WorkflowStage.LAYOUT_PLANNED.value)
        if not placements:
            report.add_error("EMPTY_LAYOUT", "layout contains no placements")
            return report
        ids = {item.id for item in placements}
        for item in placements:
            for axis, size, position, limit in (
                ("x", item.size_x, item.pos_x, spec.width),
                ("y", item.size_y, item.pos_y, spec.depth),
                ("z", item.size_z, item.pos_z, spec.height),
            ):
                if size <= 0:
                    report.add_error(
                        "NON_POSITIVE_LAYOUT_SIZE",
                        f"{item.id}.{axis} size must be positive",
                        item.id,
                    )
                if position < -1e-6 or position + size > limit + 1e-6:
                    report.add_error(
                        "LAYOUT_OUTSIDE_ENVELOPE",
                        f"{item.id} exceeds the {axis.upper()} envelope",
                        item.id,
                    )
            for dependency in item.depends_on:
                if dependency not in ids:
                    report.add_error(
                        "UNKNOWN_LAYOUT_DEPENDENCY",
                        f"{item.id} depends on unknown placement {dependency}",
                        item.id,
                    )
        return report

    def _validate_panels(self, panels: list[PanelRecord]) -> ValidationReport:
        report = ValidationReport(stage=WorkflowStage.PANELS_PLANNED.value)
        if not panels:
            report.add_error("EMPTY_PANEL_PLAN", "panel plan contains no panels")
            return report
        for panel in panels:
            if panel.quantity <= 0:
                report.add_error(
                    "INVALID_PANEL_QUANTITY",
                    f"{panel.label} quantity must be positive",
                    panel.label,
                )
            if min(panel.length_mm, panel.width_mm, panel.thickness) <= 0:
                report.add_error(
                    "NON_POSITIVE_PANEL_SIZE",
                    f"{panel.label} has a non-positive manufacturing size",
                    panel.label,
                )
        return report

    def _validate_manufacturing(
        self,
        bom: BOMReport,
        panels: list[PanelRecord],
    ) -> ValidationReport:
        report = ValidationReport(stage=WorkflowStage.MANUFACTURING_PLANNED.value)
        if bom.panel_count != len(panels):
            report.add_error(
                "BOM_PANEL_MISMATCH",
                "BOM panel count does not match the confirmed panel plan",
            )
        if bom.total_area_m2 <= 0:
            report.add_error("INVALID_BOM_AREA", "BOM total area must be positive")
        for item in bom.hardware:
            if item.quantity < 0:
                report.add_error(
                    "INVALID_HARDWARE_QUANTITY",
                    f"{item.name} quantity cannot be negative",
                    item.name,
                )
        return report

    def _validate_cad(self, bridge: BridgeResult | None) -> ValidationReport:
        report = ValidationReport(stage=WorkflowStage.CAD_GENERATED.value)
        if bridge is None:
            report.add_error("MISSING_CAD_RESULT", "CAD stage has no bridge result")
            return report
        if bridge.status != "ok":
            report.add_error("CAD_GENERATION_FAILED", bridge.message)
            return report
        for kind, path in (
            ("step", bridge.step_path),
            ("viewer_topology", bridge.topology_path),
        ):
            if not path or not Path(path).is_file():
                report.add_error(
                    "MISSING_CAD_ARTIFACT",
                    f"{kind} artifact is missing",
                    kind,
                )
        return report

    def _validate_intent(self, intent: DesignIntent) -> ValidationReport:
        report = ValidationReport(stage="design_intent")
        for error in intent.validate():
            report.add_error("INVALID_INTENT", error)
        if intent.furniture_type not in SUPPORTED_TYPES:
            report.add_error(
                "UNSUPPORTED_FURNITURE_TYPE",
                f"supported vertical slice: {', '.join(sorted(SUPPORTED_TYPES))}",
                "furniture_type",
            )
        if intent.unresolved:
            report.add_error(
                "UNRESOLVED_DECISIONS",
                "DesignIntent still contains unresolved decisions",
                "unresolved",
            )
        return report

    def _to_spec(self, intent: DesignIntent) -> FurnitureSpec:
        data: dict[str, Any] = {
            "type": intent.furniture_type,
            "width": intent.overall_size.width_mm,
            "depth": intent.overall_size.depth_mm,
            "height": intent.overall_size.height_mm,
        }
        data.update(intent.structure)
        data.update(intent.layout)
        return FurnitureSpec.from_dict(data)

    def _validate_feature_tree(self, feature_tree: dict[str, Any]) -> ValidationReport:
        report = ValidationReport(stage="feature_tree")
        try:
            from furniture.feature_tree_emitter import _validate_feature_tree

            _validate_feature_tree(feature_tree)
        except ValueError as exc:
            report.add_error("INVALID_FEATURE_TREE", str(exc))
        return report

    def _artifact_dir(
        self,
        output_root: str | Path,
        project: Project,
        revision: Revision,
        *,
        artifact_name: str | None = None,
    ) -> Path:
        root = Path(output_root)
        if not root.is_absolute():
            root = self.workspace_root / root
        if artifact_name is not None:
            if not SAFE_ARTIFACT_NAME.fullmatch(artifact_name):
                raise ValueError(
                    "artifact_name may contain only letters, digits, '-' and '_'"
                )
            path = root.resolve() / artifact_name
        else:
            path = root.resolve() / project.id / f"revision-{revision.number}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_artifacts(
        self,
        revision: Revision,
        pipeline: CabinetPipelineResult,
        artifact_dir: Path,
        *,
        artifact_name: str | None = None,
    ) -> tuple[Path, Path]:
        if artifact_name:
            intent_path = artifact_dir / f"{artifact_name}.design-intent.json"
            layout_path = artifact_dir / f"{artifact_name}.layout-plan.json"
            panel_path = artifact_dir / f"{artifact_name}.panel-plan.json"
            manufacturing_path = artifact_dir / f"{artifact_name}.manufacturing-plan.json"
            feature_tree_path = artifact_dir / f"{artifact_name}.feature-tree.json"
            bom_path = artifact_dir / f"{artifact_name}.bom.md"
            source_key = artifact_name
            source_filename = f"{artifact_name}.py"
            step_filename = f"{artifact_name}.step"
        else:
            intent_path = artifact_dir / "design-intent.json"
            layout_path = artifact_dir / "layout-plan.json"
            panel_path = artifact_dir / "panel-plan.json"
            manufacturing_path = artifact_dir / "manufacturing-plan.json"
            feature_tree_path = artifact_dir / "feature-tree.json"
            bom_path = artifact_dir / "bom.md"
            source_key = revision.id
            source_filename = "model.py"
            step_filename = "model.step"

        source_dir = self.workspace_root / "temp" / "cad-source" / source_key
        source_dir.mkdir(parents=True, exist_ok=True)
        source_path = source_dir / source_filename
        step_path = artifact_dir / step_filename

        intent_path.write_text(
            json.dumps(revision.intent.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        layout_path.write_text(
            json.dumps(
                revision.stage_outputs[WorkflowStage.LAYOUT_PLANNED.value],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        panel_path.write_text(
            json.dumps(
                revision.stage_outputs[WorkflowStage.PANELS_PLANNED.value],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        manufacturing_path.write_text(
            json.dumps(
                revision.stage_outputs[WorkflowStage.MANUFACTURING_PLANNED.value],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        feature_tree_path.write_text(
            json.dumps(revision.feature_tree, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        bom_path.write_text(format_bom_markdown(pipeline.bom), encoding="utf-8")
        write_build123d_source(revision.feature_tree or {}, source_path)

        revision.manifest.add_file("design_intent", intent_path)
        revision.manifest.add_file("layout_plan", layout_path)
        revision.manifest.add_file("panel_plan", panel_path)
        revision.manifest.add_file(
            "manufacturing_plan",
            manufacturing_path,
            readiness="preliminary",
        )
        revision.manifest.add_file("feature_tree", feature_tree_path)
        revision.manifest.add_file("bom", bom_path, readiness="preliminary")
        revision.manifest.add_file("cad_source", source_path, derived=True)
        return source_path, step_path

    def _validate_artifacts(self, revision: Revision) -> ValidationReport:
        report = ValidationReport(stage="artifacts")
        for artifact in revision.manifest.artifacts:
            path = Path(artifact.path)
            if not path.is_file() or path.stat().st_size == 0:
                report.add_error("MISSING_ARTIFACT", artifact.path)
        return report
