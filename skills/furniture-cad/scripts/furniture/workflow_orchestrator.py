"""Single deterministic orchestrator for the first cabinet vertical slice."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from furniture.cad_bridge import BridgeResult, CadBridge
from furniture.feature_tree_builder import panels_to_feature_tree
from furniture.feature_tree_emitter import write_build123d_source
from furniture.manufacturing_bom import format_bom_markdown
from furniture.layout_pipeline import SUPPORTED_TYPES, CabinetPipelineResult, plan_cabinet
from furniture.design_intent import DesignIntent
from furniture.workflow_project import Project, Revision
from furniture.design_spec import FurnitureSpec
from furniture.validation import ValidationReport
from furniture.workflow_state import WorkflowStage


SAFE_ARTIFACT_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


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
        return project.add_revision(intent)

    def execute_spec(
        self,
        name: str,
        spec: dict[str, Any],
        *,
        output_root: str | Path | None = None,
        artifact_name: str | None = None,
        generate_cad: bool = False,
        force: bool = False,
    ) -> OrchestrationResult:
        """Run a confirmed one-shot CLI/API specification through this orchestrator.

        Interactive Agent work can continue to use create_project(),
        confirm_intent(), and run() separately. CLI and API requests are already
        explicit execution requests, so this convenience method confirms their
        normalized DesignIntent before running the same application workflow.
        """
        intent = self.intent_from_spec(spec)
        project = self.create_project(name, intent)
        self.confirm_intent(project)
        return self.run(
            project,
            output_root=output_root,
            artifact_name=artifact_name,
            generate_cad=generate_cad,
            force=force,
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
        revision = project.latest
        revision.intent = revision.intent.confirm()
        revision.workflow.advance(WorkflowStage.INTENT_CONFIRMED, "intent confirmed")
        return revision

    def run(
        self,
        project: Project,
        *,
        output_root: str | Path | None = None,
        artifact_name: str | None = None,
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
            feature_tree_path = artifact_dir / f"{artifact_name}.feature-tree.json"
            bom_path = artifact_dir / f"{artifact_name}.bom.md"
            source_key = artifact_name
            source_filename = f"{artifact_name}.py"
            step_filename = f"{artifact_name}.step"
        else:
            intent_path = artifact_dir / "design-intent.json"
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
