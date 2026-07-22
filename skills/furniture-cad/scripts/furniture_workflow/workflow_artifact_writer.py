"""Write traceable cross-stage artifacts without owning workflow decisions."""

from __future__ import annotations

import json
from pathlib import Path
import re

from furniture_feature_tree.feature_tree_emitter import write_build123d_source
from furniture_manufacturing.drilled_holes_glb import (
    export_drilled_holes_glb,
    export_drilled_holes_step,
)
from furniture_manufacturing.export_six_side_drill import drill_json_to_xml_files
from furniture_manufacturing.manufacturing_bom import (
    emit_drilled_holes,
    format_bom_markdown,
)

from .cabinet_pipeline import CabinetPipelineResult
from .workflow_project import Project, Revision
from .workflow_state import WorkflowStage


SAFE_ARTIFACT_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


def prepare_artifact_dir(
    workspace_root: str | Path,
    output_root: str | Path,
    project: Project,
    revision: Revision,
    *,
    artifact_name: str | None = None,
) -> Path:
    root = Path(output_root)
    if not root.is_absolute():
        root = Path(workspace_root) / root
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


def write_artifacts(
    workspace_root: str | Path,
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

    source_dir = Path(workspace_root) / "temp" / "cad-source" / source_key
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

    if artifact_name:
        drilled_json_path = artifact_dir / f"{artifact_name}.drilled-holes.json"
        drilled_glb_path = artifact_dir / f"{artifact_name}.drilled-holes.glb"
        drilled_step_path = artifact_dir / f"{artifact_name}.drilled-holes.step"
    else:
        drilled_json_path = artifact_dir / "drilled-holes.json"
        drilled_glb_path = artifact_dir / "drilled-holes.glb"
        drilled_step_path = artifact_dir / "drilled-holes.step"
    drilled_data = emit_drilled_holes(pipeline.bom)
    drilled_json_path.write_text(
        json.dumps(drilled_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    export_drilled_holes_glb(drilled_data, drilled_glb_path)
    export_drilled_holes_step(drilled_data, drilled_step_path)
    # 导出柜柜六面钻 XML 文件
    drilled_xml_dir = artifact_dir / "六面钻文件"
    drill_json_to_xml_files(drilled_json_path, drilled_xml_dir)

    revision.manifest.add_file("design_intent", intent_path)
    revision.manifest.add_file("layout_plan", layout_path)
    revision.manifest.add_file("panel_plan", panel_path)
    revision.manifest.add_file(
        "manufacturing_plan",
        manufacturing_path,
        readiness=pipeline.bom.readiness,
    )
    revision.manifest.add_file("feature_tree", feature_tree_path)
    revision.manifest.add_file(
        "bom",
        bom_path,
        readiness=pipeline.bom.readiness,
    )
    revision.manifest.add_file("drilled_holes", drilled_json_path)
    revision.manifest.add_file("drilled_holes_glb", drilled_glb_path, derived=True)
    revision.manifest.add_file("drilled_holes_step", drilled_step_path, derived=True)
    revision.manifest.add_file("cad_source", source_path, derived=True)
    return source_path, step_path
