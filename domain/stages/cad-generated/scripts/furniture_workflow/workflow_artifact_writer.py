"""Write traceable cross-stage artifacts without owning workflow decisions.

**逐柜**：一个工程里有几台柜，就出几套柜级文件（BOM、STEP 源码、钻孔、六面钻 XML），
manifest 的每条柜级记录都带 `cabinet_id`。阶段级文件（布局 / 板件 / 制造 / 特征树 JSON）
仍然是每版一份——它们本身就是逐柜形状（`{"cabinets": [...]}`）。
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

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
from furniture_manufacturing.manufacturing_handoff import weakest_readiness

from .cabinet_pipeline import CabinetPipelineResult
from .workflow_cabinets import cabinets_from_feature_trees
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
    pipelines: Sequence[CabinetPipelineResult],
    artifact_dir: Path,
    *,
    artifact_name: str | None = None,
    panel_output: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """写出这一版的所有产物，返回**逐柜**的 `{"id", "source_path", "step_path"}`。

    柜级文件按柜名区分（`bom.<cabinet_id>.md`、`<cabinet_id>.step`、
    `<cabinet_id>.drilled-holes.*`）；六面钻 XML 落在同一个 `六面钻文件/` 里，
    文件名已经带柜名前缀（`{cabinet_id}__{role}.xml`）。
    """
    stage_stem = artifact_name or ""
    if artifact_name:
        source_key = artifact_name
    else:
        source_key = revision.id
    source_dir = Path(workspace_root) / "temp" / "cad-source" / source_key
    source_dir.mkdir(parents=True, exist_ok=True)

    readiness = weakest_readiness(
        [pipeline.bom.readiness for pipeline in pipelines]
    )
    _write_stage_files(
        revision,
        artifact_dir,
        stage_stem,
        panel_output=panel_output,
        readiness=readiness,
    )

    trees = {
        entry["id"]: entry["tree"]
        for entry in cabinets_from_feature_trees(
            revision.stage_outputs[WorkflowStage.FEATURE_TREE_PLANNED.value]
        )
    }
    plans: list[dict[str, Any]] = []
    for pipeline in pipelines:
        cabinet_id = pipeline.cabinet_id
        if cabinet_id not in trees:
            raise ValueError(f"feature tree is missing for cabinet: {cabinet_id}")
        plans.append(
            _write_cabinet_files(
                revision,
                pipeline,
                trees[cabinet_id],
                artifact_dir,
                source_dir,
                stem=artifact_name,
            )
        )
    return plans


def _write_stage_files(
    revision: Revision,
    artifact_dir: Path,
    stem: str,
    *,
    panel_output: dict[str, Any] | None,
    readiness: str,
) -> None:
    """阶段级文件：每版一份（内容本身就是逐柜形状）。"""
    prefix = f"{stem}." if stem else ""
    panels = (
        panel_output
        if panel_output is not None
        else revision.stage_outputs[WorkflowStage.PANELS_PLANNED.value]
    )
    _dump(artifact_dir / f"{prefix}layout-plan.json", revision.layout.to_dict())
    _dump(artifact_dir / f"{prefix}panel-plan.json", panels)
    _dump(
        artifact_dir / f"{prefix}manufacture-plan.json",
        revision.stage_outputs[WorkflowStage.MANUFACTURING_PLANNED.value],
    )
    _dump(
        artifact_dir / f"{prefix}feature-tree.json",
        revision.stage_outputs[WorkflowStage.FEATURE_TREE_PLANNED.value],
    )
    revision.manifest.add_file("layout_plan", artifact_dir / f"{prefix}layout-plan.json")
    revision.manifest.add_file("panel_plan", artifact_dir / f"{prefix}panel-plan.json")
    revision.manifest.add_file(
        "manufacturing_plan",
        artifact_dir / f"{prefix}manufacture-plan.json",
        readiness=readiness,
    )
    revision.manifest.add_file(
        "feature_tree",
        artifact_dir / f"{prefix}feature-tree.json",
    )


def _write_cabinet_files(
    revision: Revision,
    pipeline: CabinetPipelineResult,
    tree: Mapping[str, Any],
    artifact_dir: Path,
    source_dir: Path,
    *,
    stem: str | None,
) -> dict[str, Any]:
    """柜级文件：BOM、CAD 源码、钻孔（JSON/GLB/STEP）、六面钻 XML。"""
    cabinet_id = pipeline.cabinet_id
    prefix = f"{stem}." if stem else ""
    readiness = pipeline.bom.readiness

    bom_path = artifact_dir / f"{prefix}bom.{cabinet_id}.md"
    bom_path.write_text(format_bom_markdown(pipeline.bom), encoding="utf-8")
    revision.manifest.add_file(
        "bom", bom_path, cabinet_id=cabinet_id, readiness=readiness
    )

    source_path = source_dir / f"{cabinet_id}.step.py"
    step_path = artifact_dir / f"{prefix}{cabinet_id}.step"
    write_build123d_source(dict(tree), source_path, step_path=step_path)
    revision.manifest.add_file(
        "cad_source", source_path, derived=True, cabinet_id=cabinet_id
    )

    drilled_data = emit_drilled_holes(pipeline.bom)
    drilled_json_path = artifact_dir / f"{prefix}{cabinet_id}.drilled-holes.json"
    drilled_glb_path = artifact_dir / f"{prefix}{cabinet_id}.drilled-holes.glb"
    drilled_step_path = artifact_dir / f"{prefix}{cabinet_id}.drilled-holes.step"
    _dump(drilled_json_path, drilled_data)
    export_drilled_holes_glb(drilled_data, drilled_glb_path)
    export_drilled_holes_step(drilled_data, drilled_step_path)
    drilled_step_glb_path = Path(f"{drilled_step_path}.glb")
    for kind, path in (
        ("drilled_holes", drilled_json_path),
        ("drilled_holes_glb", drilled_glb_path),
        ("drilled_holes_step", drilled_step_path),
        ("drilled_holes_step_glb", drilled_step_glb_path),
    ):
        revision.manifest.add_file(
            kind, path, derived=True, cabinet_id=cabinet_id, readiness=readiness
        )

    for drilled_xml_path in drill_json_to_xml_files(
        drilled_json_path, artifact_dir / "六面钻文件"
    ):
        revision.manifest.add_file(
            "six_side_drill_xml",
            drilled_xml_path,
            derived=True,
            cabinet_id=cabinet_id,
            panel_label=drilled_xml_path.stem,
            readiness=readiness,
        )
    return {"id": cabinet_id, "source_path": source_path, "step_path": step_path}


def _dump(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
