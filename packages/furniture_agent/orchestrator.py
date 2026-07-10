"""Single deterministic orchestrator for the first cabinet vertical slice."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from cad_bridge.adapter import BridgeResult, CadBridge
from furniture_cad_emitter.cabinet_emitter import panels_to_feature_tree
from furniture_cad_emitter.emitter import write_build123d_source
from furniture_panelizer.bom import format_bom_markdown
from furniture_pipeline.cabinet import SUPPORTED_TYPES, CabinetPipelineResult, plan_cabinet
from furniture_schema.design_intent import DesignIntent
from furniture_schema.project import Project, Revision
from furniture_schema.spec import FurnitureSpec
from furniture_schema.validation import ValidationReport
from furniture_schema.workflow import WorkflowStage


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
            workspace_root or Path(__file__).resolve().parents[2]
        ).resolve()
        self.cad_bridge = cad_bridge or CadBridge(workspace_root=self.workspace_root)

    def create_project(self, name: str, intent: DesignIntent) -> Project:
        project = Project(name=name)
        project.add_revision(intent)
        return project

    def revise(self, project: Project, intent: DesignIntent) -> Revision:
        return project.add_revision(intent)

    def confirm_intent(self, project: Project) -> Revision:
        revision = project.latest
        revision.intent = revision.intent.confirm()
        revision.workflow.advance(WorkflowStage.INTENT_CONFIRMED, "intent confirmed")
        return revision

    def run(
        self,
        project: Project,
        *,
        output_root: str | Path | None = None,
        generate_cad: bool = False,
        force: bool = False,
    ) -> OrchestrationResult:
        revision = project.latest
        intent_report = self._validate_intent(revision.intent)
        revision.validations.append(intent_report)
        if not intent_report.passed:
            revision.workflow.fail("DesignIntent validation failed")
            return OrchestrationResult(project, revision, None)
        if not revision.intent.confirmed:
            revision.workflow.fail("DesignIntent must be confirmed before execution")
            return OrchestrationResult(project, revision, None)

        try:
            spec = self._to_spec(revision.intent)
            pipeline = plan_cabinet(spec)
            revision.workflow.advance(
                WorkflowStage.PANEL_PLANNED, "cabinet panels and BOM planned"
            )

            feature_tree = panels_to_feature_tree(
                pipeline.panels,
                furniture_type=spec.furniture_type,
                parameters={
                    "width": spec.width,
                    "depth": spec.depth,
                    "height": spec.height,
                    "board_thickness": spec.board_thickness,
                },
            )
            revision.feature_tree = feature_tree
            feature_report = self._validate_feature_tree(feature_tree)
            revision.validations.append(feature_report)
            if not feature_report.passed:
                revision.workflow.fail("Feature Tree validation failed")
                return OrchestrationResult(project, revision, pipeline)
            revision.workflow.advance(
                WorkflowStage.FEATURE_TREE_VALIDATED,
                "box-based Feature Tree v1 validated",
            )

            bridge_result = None
            if output_root is not None:
                artifact_dir = self._artifact_dir(output_root, project, revision)
                source_path, step_path = self._write_artifacts(
                    revision, pipeline, artifact_dir
                )
                revision.workflow.advance(
                    WorkflowStage.ARTIFACTS_GENERATED,
                    "planning artifacts generated",
                )
                if generate_cad:
                    bridge_result = self.cad_bridge.generate_from_source(
                        source_path, step_path, force=force
                    )
                    if bridge_result.status != "ok":
                        revision.workflow.fail(bridge_result.message)
                        return OrchestrationResult(project, revision, pipeline, bridge_result)
                    revision.manifest.add_file("step", bridge_result.step_path)
                    revision.manifest.add_file("viewer_topology", bridge_result.topology_path)

                artifact_report = self._validate_artifacts(revision)
                revision.validations.append(artifact_report)
                if artifact_report.passed:
                    revision.workflow.advance(
                        WorkflowStage.ARTIFACTS_VERIFIED,
                        "manifest files verified",
                    )
                else:
                    revision.workflow.fail("artifact validation failed")

            return OrchestrationResult(project, revision, pipeline, bridge_result)
        except (OSError, TypeError, ValueError) as exc:
            report = ValidationReport(stage="orchestration")
            report.add_error("ORCHESTRATION_FAILED", str(exc))
            revision.validations.append(report)
            revision.workflow.fail(str(exc))
            return OrchestrationResult(project, revision, None)

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
            from furniture_cad_emitter.emitter import _validate_feature_tree

            _validate_feature_tree(feature_tree)
        except ValueError as exc:
            report.add_error("INVALID_FEATURE_TREE", str(exc))
        return report

    def _artifact_dir(
        self, output_root: str | Path, project: Project, revision: Revision
    ) -> Path:
        root = Path(output_root)
        if not root.is_absolute():
            root = self.workspace_root / root
        path = root.resolve() / project.id / f"revision-{revision.number}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_artifacts(
        self,
        revision: Revision,
        pipeline: CabinetPipelineResult,
        artifact_dir: Path,
    ) -> tuple[Path, Path]:
        intent_path = artifact_dir / "design-intent.json"
        feature_tree_path = artifact_dir / "feature-tree.json"
        bom_path = artifact_dir / "bom.md"
        source_path = artifact_dir / "model.py"
        step_path = artifact_dir / "model.step"

        intent_path.write_text(
            json.dumps(revision.intent.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        feature_tree_path.write_text(
            json.dumps(revision.feature_tree, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        bom_path.write_text(format_bom_markdown(pipeline.bom), encoding="utf-8")
        write_build123d_source(revision.feature_tree or {}, source_path)

        revision.manifest.add_file("design_intent", intent_path)
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

