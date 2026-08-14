"""Single deterministic orchestrator for the first cabinet vertical slice."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from furniture_cad.cad_bridge import BridgeResult, CadBridge
from furniture_cad.validation import validate_cad
from furniture_delivery_validation.validation import (
    ValidationReport,
    validate_delivery,
)
from furniture_design_intent.design_intent import DesignIntent
from furniture_design_intent.validation import validate_intent
from furniture_feature_tree.feature_tree_builder import panels_to_feature_tree
from furniture_feature_tree.validation import validate_feature_tree
from furniture_layout.layout_pipeline import plan_layout_stage
from furniture_layout.layout_planning import CabinetLayout
from furniture_layout.layout_spec import LayoutSpec
from furniture_layout.validation import validate_layout_output
from furniture_manufacturing.manufacturing_bom import (
    BOMReport,
    emit_drilled_holes,
    plan_manufacturing,
)
from furniture_manufacturing.manufacturing_models import (
    HardwareRecord,
    MachiningOperation,
    PanelRecord,
)
from furniture_manufacturing.production_simulation import simulate_production
from furniture_manufacturing.prototype_experiment import design_prototype_experiment
from furniture_manufacturing.test_statistics import analyze_prototype_results
from furniture_manufacturing.validation import validate_manufacturing
from furniture_panel_planning.design_optimization import (
    materialize_optimization_candidate,
    optimize_panel_design,
)
from furniture_panel_planning.panel_models import PanelPlacement
from furniture_panel_planning.panel_pipeline import plan_panel_stage
from furniture_panel_planning.panel_spec import FurnitureSpec
from furniture_panel_planning.quantitative_audit import audit_panel_quantities
from furniture_panel_planning.structure_planning import CabinetStructure
from furniture_panel_planning.validation import validate_panel_output

from .cabinet_pipeline import CabinetPipelineResult
from .input_adapter import (
    intent_from_spec as translate_intent_from_spec,
    layout_stage_input,
    manufacturing_stage_input,
    panel_stage_input,
    stage_inputs_from_spec,
)
from .workflow_artifact_writer import prepare_artifact_dir, write_artifacts
from .workflow_project import Project, Revision
from .workflow_state import (
    STAGE_SEQUENCE,
    WorkflowStage,
    WorkflowState,
    parse_stage,
    stage_index,
    utc_now,
)


EDITABLE_STAGE_OUTPUTS = {
    WorkflowStage.LAYOUT_PLANNED,
    WorkflowStage.PANELS_PLANNED,
    WorkflowStage.MANUFACTURING_PLANNED,
    WorkflowStage.FEATURE_TREE_PLANNED,
}

ANALYSIS_STAGE_OWNERS = {
    "panel_unit_audit": WorkflowStage.PANELS_PLANNED,
    "panel_optimization": WorkflowStage.PANELS_PLANNED,
    "prototype_experiment": WorkflowStage.MANUFACTURING_PLANNED,
    "test_statistics": WorkflowStage.MANUFACTURING_PLANNED,
    "production_simulation": WorkflowStage.MANUFACTURING_PLANNED,
}

ANALYSIS_METHOD_SKILLS = {
    "panel_unit_audit": "uncertainty-and-units",
    "panel_optimization": "pymoo",
    "prototype_experiment": "experimental-design",
    "test_statistics": "statistical-analysis",
    "production_simulation": "simpy",
}


def _stable_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class OrchestrationResult:
    project: Project
    revision: Revision
    pipeline: CabinetPipelineResult | None
    bridge: BridgeResult | None = None
    drilled_holes: dict[str, Any] | None = None


class FurnitureOrchestrator:
    """Own stage lifecycle while delegating each domain rule to its skill."""

    def __init__(
        self,
        workspace_root: str | Path | None = None,
        cad_bridge: CadBridge | None = None,
    ) -> None:
        self.workspace_root = Path(
            workspace_root or Path(__file__).resolve().parents[4]
        ).resolve()
        self.cad_bridge = cad_bridge or CadBridge(workspace_root=self.workspace_root)

    def create_project(
        self,
        name: str,
        intent: DesignIntent,
        *,
        stage_inputs: dict[str, Any] | None = None,
    ) -> Project:
        project = Project(name=name)
        project.add_revision(intent, stage_inputs=stage_inputs)
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
        """Create a revision from an edited stage-2..5 output."""
        changed_stage = parse_stage(stage)
        if changed_stage not in EDITABLE_STAGE_OUTPUTS:
            editable = ", ".join(item.value for item in EDITABLE_STAGE_OUTPUTS)
            raise ValueError(f"stage output is not directly editable; use one of: {editable}")

        parent = project.latest
        if changed_stage.value not in parent.stage_outputs:
            raise ValueError(f"stage has no output to revise: {changed_stage.value}")

        revision = project.add_revision(
            DesignIntent.from_dict(parent.intent.to_dict()),
            stage_inputs=deepcopy(parent.stage_inputs),
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
        if changed_stage == WorkflowStage.LAYOUT_PLANNED:
            revised_layout = output.get("layout", {})
            layout_input = revision.stage_inputs.setdefault("layout", {})
            parameters = layout_input.setdefault("parameters", {})
            if isinstance(revised_layout, dict) and isinstance(parameters, dict):
                if "shelf_count" in revised_layout:
                    parameters["shelf_count"] = revised_layout["shelf_count"]
                if "door_count" in revised_layout:
                    parameters["n_doors"] = revised_layout["door_count"]
        elif changed_stage == WorkflowStage.PANELS_PLANNED:
            revised_spec = output.get("spec", {})
            panel_input = revision.stage_inputs.setdefault("panels", {})
            parameters = panel_input.setdefault("parameters", {})
            if isinstance(revised_spec, dict) and isinstance(parameters, dict):
                for key, value in revised_spec.items():
                    if key in {
                        "furniture_type",
                        "width",
                        "depth",
                        "height",
                        "shelf_count",
                        "n_doors",
                    }:
                        continue
                    parameters[key] = value
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

    def run_stage_analysis(
        self,
        project: Project,
        analysis: str,
        config: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run one bounded side analysis without changing a stage checkpoint."""

        analysis_name = str(analysis).strip()
        if analysis_name not in ANALYSIS_STAGE_OWNERS:
            supported = ", ".join(sorted(ANALYSIS_STAGE_OWNERS))
            raise ValueError(f"unsupported stage analysis; use one of: {supported}")
        revision = project.latest
        source_stage = ANALYSIS_STAGE_OWNERS[analysis_name]
        source_output = revision.stage_outputs.get(source_stage.value)
        if not isinstance(source_output, dict):
            raise ValueError(
                f"analysis requires stage output: {source_stage.value}"
            )
        values = dict(config or {})
        dispatch: dict[str, Callable[[], dict[str, Any]]] = {
            "panel_unit_audit": lambda: audit_panel_quantities(
                source_output,
                values,
            ),
            "panel_optimization": lambda: optimize_panel_design(
                self._layout_from_revision(revision),
                source_output,
                values,
            ),
            "prototype_experiment": lambda: design_prototype_experiment(
                source_output,
                values,
            ),
            "test_statistics": lambda: analyze_prototype_results(
                source_output,
                values,
            ),
            "production_simulation": lambda: simulate_production(
                source_output,
                values,
            ),
        }
        report = dispatch[analysis_name]()
        record = {
            "analysis": analysis_name,
            "method_skill": ANALYSIS_METHOD_SKILLS[analysis_name],
            "status": str(report.get("status", "completed")),
            "source_stage": source_stage.value,
            "source_revision_id": revision.id,
            "source_sha256": _stable_digest(source_output),
            "created_at": utc_now(),
            "report": deepcopy(report),
        }
        revision.stage_analyses.setdefault(source_stage.value, {})[
            analysis_name
        ] = record
        revision.workflow.record(
            f"{analysis_name} analysis recorded for {source_stage.value}"
        )
        return deepcopy(record)

    def apply_panel_optimization_candidate(
        self,
        project: Project,
        candidate_index: int,
    ) -> Revision:
        """Materialize an explicitly selected Pareto candidate as a new revision."""

        revision = project.latest
        stage = WorkflowStage.PANELS_PLANNED
        analyses = revision.stage_analyses.get(stage.value, {})
        record = analyses.get("panel_optimization")
        if not isinstance(record, Mapping):
            raise ValueError("run panel_optimization before selecting a candidate")
        source_output = revision.stage_outputs.get(stage.value)
        if not isinstance(source_output, dict):
            raise ValueError("panels_planned output is unavailable")
        if record.get("source_revision_id") != revision.id or record.get(
            "source_sha256"
        ) != _stable_digest(source_output):
            raise ValueError("panel optimization is stale; run it again")
        report = record.get("report")
        candidates = report.get("candidates") if isinstance(report, Mapping) else None
        if not isinstance(candidates, list):
            raise ValueError("panel optimization has no selectable candidates")
        if isinstance(candidate_index, bool) or not 0 <= candidate_index < len(candidates):
            raise ValueError("candidate_index is outside the Pareto candidate list")
        selected = candidates[candidate_index]
        if not isinstance(selected, Mapping):
            raise ValueError("selected optimization candidate is invalid")
        output = materialize_optimization_candidate(
            self._layout_from_revision(revision),
            selected,
        )
        if selected.get("stage_output_sha256") != _stable_digest(output):
            raise ValueError("selected candidate no longer materializes reproducibly")
        return self.revise_stage_output(project, stage, output)

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
        """Run an explicit batch request through the same seven-stage workflow."""
        intent = self.intent_from_spec(spec)
        project = self.create_project(
            name,
            intent,
            stage_inputs=stage_inputs_from_spec(spec),
        )
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
        """Compatibility facade for the design-intent translation API."""
        return translate_intent_from_spec(spec)

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

        report = self._latest_stage_validation(revision, requested)
        if report is None:
            report = self._validate_stage_output(revision, requested)
            revision.validations.append(report)
        if not report.passed:
            revision.workflow.fail(f"{requested.value} validation failed")
            return revision

        if requested == WorkflowStage.DESIGN_INTENT:
            revision.intent = revision.intent.confirm()
            revision.stage_outputs[requested.value] = revision.intent.to_dict()

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
        attempted_stage: WorkflowStage | None = None
        try:
            while (
                revision.workflow.current != WorkflowStage.FAILED
                and stage_index(revision.workflow.current) < stage_index(target)
            ):
                current = revision.workflow.current
                if not revision.is_stage_approved(current):
                    break
                next_stage = STAGE_SEQUENCE[stage_index(current) + 1]
                attempted_stage = next_stage
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
            report = ValidationReport(
                stage=(attempted_stage.value if attempted_stage else "orchestration")
            )
            report.add_error("STAGE_EXECUTION_FAILED", str(exc))
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
        if stage == WorkflowStage.LAYOUT_PLANNED:
            stage_input = layout_stage_input(revision.stage_inputs)
            spec = self._layout_spec_from_revision(revision)
            output = plan_layout_stage(
                spec,
                room=stage_input.get("room"),
                placement=stage_input.get("placement"),
                furniture_label=project.name,
            )
            self._complete_stage(
                revision,
                stage,
                output,
                "cabinet envelope, clear regions, and layout counts planned",
            )
            return

        if stage == WorkflowStage.PANELS_PLANNED:
            stage_input = panel_stage_input(revision.stage_inputs)
            output = plan_panel_stage(
                self._layout_from_revision(revision),
                stage_input.get("parameters", {}),
            )
            self._complete_stage(
                revision,
                stage,
                output,
                "construction, exact clearances, and physical panels planned",
            )
            return

        if stage == WorkflowStage.MANUFACTURING_PLANNED:
            spec = self._spec_from_revision(revision)
            stage_input = manufacturing_stage_input(revision.stage_inputs)
            bom = plan_manufacturing(
                spec,
                self._placements_from_revision(revision),
                requested_options=stage_input.get("parameters", {}),
                appearance=stage_input.get("appearance", {}),
            )
            self._complete_stage(
                revision,
                stage,
                asdict(bom),
                "materials, hardware, and preliminary BOM planned",
            )
            return

        if stage == WorkflowStage.FEATURE_TREE_PLANNED:
            spec = self._spec_from_revision(revision)
            manufacturing = self._bom_from_revision(revision)
            feature_tree = panels_to_feature_tree(
                manufacturing.panels,
                manufacturing.operations,
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
                "Feature Tree v2 with target-specific machining cuts planned",
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
            artifact_dir = prepare_artifact_dir(
                self.workspace_root,
                output_root,
                project,
                revision,
                artifact_name=artifact_name,
            )
            source_path, step_path = write_artifacts(
                self.workspace_root,
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
                    revision.manifest.add_file(
                        "viewer_topology",
                        bridge.topology_path,
                        package_path=bridge.viewer_package_path,
                    )
            report = self._validate_stage_output(revision, stage)
            revision.validations.append(report)
            if not report.passed:
                revision.workflow.fail(bridge.message)
                return
            revision.workflow.advance(stage, "STEP and Viewer topology generated")
            return

        if stage == WorkflowStage.DELIVERY_VALIDATED:
            report = validate_delivery(
                revision.manifest,
                source_revision_id=revision.id,
                stage_outputs=revision.stage_outputs,
                approved_stages=revision.approved_stages,
                stage_validations=revision.validations,
                stage_analyses=revision.stage_analyses,
            )
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
        pipeline = self._pipeline_from_revision(revision)
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
    ) -> CabinetPipelineResult | None:
        required = (
            WorkflowStage.LAYOUT_PLANNED.value,
            WorkflowStage.PANELS_PLANNED.value,
            WorkflowStage.MANUFACTURING_PLANNED.value,
        )
        if not all(key in revision.stage_outputs for key in required):
            return None
        return CabinetPipelineResult(
            spec=self._spec_from_revision(revision),
            layout=self._layout_from_revision(revision),
            structure=self._structure_from_revision(revision),
            placements=self._placements_from_revision(revision),
            panels=self._panels_from_revision(revision),
            bom=self._bom_from_revision(revision),
        )

    @staticmethod
    def _layout_from_revision(revision: Revision) -> CabinetLayout:
        output = revision.stage_outputs[WorkflowStage.LAYOUT_PLANNED.value]
        return CabinetLayout(**output["layout"])

    @staticmethod
    def _spec_from_revision(revision: Revision) -> FurnitureSpec:
        output = revision.stage_outputs[WorkflowStage.PANELS_PLANNED.value]
        return FurnitureSpec(**output["spec"])

    @staticmethod
    def _structure_from_revision(revision: Revision) -> CabinetStructure:
        output = revision.stage_outputs[WorkflowStage.PANELS_PLANNED.value]
        return CabinetStructure(**output["structure"])

    @staticmethod
    def _layout_spec_from_revision(revision: Revision) -> LayoutSpec:
        stage_input = layout_stage_input(revision.stage_inputs)
        parameters = stage_input.get("parameters", {})
        if not isinstance(parameters, dict):
            raise ValueError("layout stage parameters must be an object")
        return LayoutSpec.from_intent(revision.intent, parameters)

    @staticmethod
    def _placements_from_revision(revision: Revision) -> list[PanelPlacement]:
        output = revision.stage_outputs[WorkflowStage.PANELS_PLANNED.value]
        return [
            PanelPlacement.from_dict(item) for item in output.get("panels", [])
        ]

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
            total_area_m2=float(output.get("total_area_m2", 0.0)),
            readiness=str(output.get("readiness", "preliminary")),
            requested_options=dict(output.get("requested_options", {})),
            appearance=dict(output.get("appearance", {})),
        )

    @staticmethod
    def _bridge_from_revision(revision: Revision) -> BridgeResult | None:
        output = revision.stage_outputs.get(WorkflowStage.CAD_GENERATED.value)
        return BridgeResult(**output) if output else None

    def _validate_stage_output(
        self,
        revision: Revision,
        stage: WorkflowStage,
    ) -> ValidationReport:
        try:
            if stage == WorkflowStage.DESIGN_INTENT:
                return validate_intent(revision.intent)
            if stage == WorkflowStage.LAYOUT_PLANNED:
                return validate_layout_output(
                    self._layout_spec_from_revision(revision),
                    revision.stage_outputs[stage.value],
                )
            if stage == WorkflowStage.PANELS_PLANNED:
                return validate_panel_output(
                    self._layout_from_revision(revision),
                    revision.stage_outputs[stage.value],
                )
            if stage == WorkflowStage.MANUFACTURING_PLANNED:
                return validate_manufacturing(
                    self._spec_from_revision(revision),
                    self._bom_from_revision(revision),
                    self._placements_from_revision(revision),
                )
            if stage == WorkflowStage.FEATURE_TREE_PLANNED:
                return validate_feature_tree(revision.stage_outputs[stage.value])
            if stage == WorkflowStage.CAD_GENERATED:
                return validate_cad(self._bridge_from_revision(revision))
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
