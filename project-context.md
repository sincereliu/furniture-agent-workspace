This file is a merged representation of a subset of the codebase, containing files not matching ignore patterns, combined into a single document by Repomix.

# File Summary

## Purpose
This file contains a packed representation of a subset of the repository's contents that is considered the most important context.
It is designed to be easily consumable by AI systems for analysis, code review,
or other automated processes.

## File Format
The content is organized as follows:
1. This summary section
2. Repository information
3. Directory structure
4. Repository files (if enabled)
5. Multiple file entries, each consisting of:
  a. A header with the file path (## File: path/to/file)
  b. The full contents of the file in a code block

## Usage Guidelines
- This file should be treated as read-only. Any changes should be made to the
  original repository files, not this packed version.
- When processing this file, use the file path to distinguish
  between different files in the repository.
- Be aware that this file may contain sensitive information. Handle it with
  the same level of security as you would the original repository.

## Notes
- Some files may have been excluded based on .gitignore rules and Repomix's configuration
- Binary files are not included in this packed representation. Please refer to the Repository Structure section for a complete list of file paths, including binary files
- Files matching these patterns are excluded: .venv, venv, __pycache__, *.log, dist, build, external, generated, temp
- Files matching patterns in .gitignore are excluded
- Files matching default ignore patterns are excluded
- Files are sorted by Git change count (files with more changes are at the bottom)

# Directory Structure
````
.agents/
  skills/
    furniture-agent/
      agents/
        openai.yaml
      references/
        llm-runtime-boundary.md
      SKILL.md
domain/
  skills/
    furniture-cad/
      agents/
        openai.yaml
      references/
        runtime-contract.md
      scripts/
        furniture_cad/
          __init__.py
          cad_bridge.py
          validation.py
        furniture_workflow/
          __init__.py
          cabinet_pipeline.py
          input_adapter.py
          planner.py
          workflow_artifact_writer.py
          workflow_artifacts.py
          workflow_orchestrator.py
          workflow_project.py
          workflow_state.py
          workflow_store.py
        tests/
          panel_fixtures.py
          test_api_entrypoint.py
          test_back_groove_pipeline.py
          test_back_mount_modes.py
          test_cabinet_pipeline.py
          test_cad_bridge.py
          test_cli_entrypoint.py
          test_entrypoint_architecture.py
          test_furniture_orchestrator.py
          test_furniture_pipeline.py
          test_recent_manufacturing_patches.py
          test_room_layout_preview.py
          test_scientific_analysis_adapters.py
          test_skill_architecture.py
          test_workspace_layout.py
        generate_furniture.py
        README.md
        runtime_paths.py
        server.py
        validate_workspace_layout.py
      SKILL.md
    furniture-delivery-validation/
      agents/
        openai.yaml
      references/
        delivery-checklist.md
      scripts/
        furniture_delivery_validation/
          __init__.py
          validation.py
      SKILL.md
    furniture-design-intent/
      agents/
        openai.yaml
      references/
        intake/
          catalog.yaml
        intent-capture-rules.md
      scripts/
        furniture_design_intent/
          __init__.py
          design_intent.py
          validation.py
      SKILL.md
    furniture-feature-tree/
      agents/
        openai.yaml
      references/
        feature-tree-rules.md
      scripts/
        furniture_feature_tree/
          __init__.py
          feature_tree_builder.py
          feature_tree_emitter.py
          validation.py
      SKILL.md
    furniture-layout/
      agents/
        openai.yaml
      references/
        spatial-layout-rules.md
      scripts/
        furniture_layout/
          __init__.py
          layout_pipeline.py
          layout_planning.py
          layout_preview.py
          layout_spec.py
          layout_viewer.py
          room_planning.py
          validation.py
      SKILL.md
    furniture-manufacturing/
      agents/
        openai.yaml
      references/
        connection-point-design.md
        coordinate-naming.md
        drawer-component-design.md
        hardware-machining-reference.md
        manufacturing-rules.md
        runtime-map.md
        six-side-drill-export.md
      scripts/
        furniture_manufacturing/
          connectors/
            __init__.py
            back_mount.py
            base.py
            drawer_slide.py
            hinge.py
            shelf.py
            trinity.py
          devices/
            six_side_drill_guigui.yaml
          __init__.py
          drilled_holes_glb.py
          export_six_side_drill.py
          hardware_catalog.yaml
          hardware_rules.yaml
          hole_validator.py
          manufacturing_bom.py
          manufacturing_edge_banding.py
          manufacturing_models.py
          production_simulation.py
          prototype_experiment.py
          test_statistics.py
          validation.py
      SKILL.md
    furniture-panel-planning/
      agents/
        openai.yaml
      references/
        cabinet-topologies/
          floor_cabinet.yaml
          wall_cabinet.yaml
        back-construction-rules.md
        panel-definition-rules.md
      scripts/
        furniture_panel_planning/
          __init__.py
          cabinet_frame.py
          cabinet_panel_planner.py
          design_optimization.py
          joint_topology.py
          panel_face.py
          panel_models.py
          panel_pipeline.py
          panel_planning.py
          panel_rules.py
          panel_spec.py
          quantitative_audit.py
          structure_planning.py
          topology_solver.py
          validation.py
      SKILL.md
.gitignore
.gitmodules
.node-version
AGENTS.md
CHANGELOG.md
pyproject.toml
README.md
````

# Files

## File: domain/skills/furniture-cad/agents/openai.yaml
````yaml
interface:
  display_name: "家具 CAD 生成"
  short_description: "由已确认特征树生成 STEP 与 Viewer 拓扑"
  default_prompt: "使用 $furniture-cad 生成当前阶段 CAD，展示结果后暂停。"
````

## File: domain/skills/furniture-cad/scripts/furniture_cad/__init__.py
````python
"""CAD-generation stage runtime."""
````

## File: domain/skills/furniture-cad/scripts/furniture_cad/validation.py
````python
"""Validation owned by the CAD-generation stage."""

from __future__ import annotations

from pathlib import Path

from furniture_delivery_validation.validation import ValidationReport

from .cad_bridge import BridgeResult


def validate_cad(bridge: BridgeResult | None) -> ValidationReport:
    report = ValidationReport(stage="cad_generated")
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
    if not bridge.viewer_package_path or not Path(bridge.viewer_package_path).is_dir():
        report.add_error(
            "MISSING_CAD_ARTIFACT",
            "viewer package directory is missing",
            "viewer_package",
        )
    return report
````

## File: domain/skills/furniture-cad/scripts/furniture_workflow/__init__.py
````python
"""Shared workflow state and the single furniture application orchestrator."""
````

## File: domain/skills/furniture-cad/scripts/furniture_workflow/cabinet_pipeline.py
````python
"""Stateless compatibility facade that composes stage-owned planners."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from furniture_design_intent.design_intent import SUPPORTED_TYPES
from furniture_manufacturing.manufacturing_bom import BOMReport, plan_manufacturing
from furniture_manufacturing.manufacturing_models import PanelRecord
from furniture_panel_planning.panel_models import PanelPlacement
from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.panel_spec import FurnitureSpec
from furniture_panel_planning.structure_planning import CabinetStructure


@dataclass(frozen=True)
class CabinetPipelineResult:
    spec: FurnitureSpec
    structure: CabinetStructure
    placements: list[PanelPlacement]
    panels: list[PanelRecord]
    bom: BOMReport


def plan_cabinet(spec: FurnitureSpec) -> CabinetPipelineResult:
    """Compose panel and manufacturing planning without room placement."""
    normalized = FurnitureSpec.from_dict(asdict(spec))
    if normalized.furniture_type not in SUPPORTED_TYPES:
        supported = ", ".join(sorted(SUPPORTED_TYPES))
        raise ValueError(
            f"Unsupported cabinet type: {normalized.furniture_type!r}; supported: {supported}"
        )
    structure = CabinetStructure.from_spec(normalized)
    placements = plan_panels(normalized, structure)
    bom = plan_manufacturing(normalized, placements)
    return CabinetPipelineResult(
        spec=normalized,
        structure=structure,
        placements=placements,
        panels=bom.panels,
        bom=bom,
    )
````

## File: domain/skills/furniture-cad/scripts/furniture_workflow/planner.py
````python
from __future__ import annotations

from typing import Any


def plan_furniture(spec: dict[str, Any]) -> dict[str, Any]:
    """统一入口：根据 type 路由到柜体规划器。

    支持的类型: floor_cabinet / wall_cabinet
    返回标准 Feature Tree dict，兼容 emitter 和 pipeline 测试。
    """
    furniture_type = str(spec.get("type", "")).strip().lower()

    if furniture_type in ("floor_cabinet", "wall_cabinet"):
        return _plan_cabinet(spec, furniture_type)

    raise ValueError(
        f"Unsupported furniture type {furniture_type!r}; "
        f"supported: floor_cabinet, wall_cabinet."
    )


def _plan_cabinet(spec: dict[str, Any], furniture_type: str) -> dict[str, Any]:
    """委托给 pipeline + emitter，返回 Feature Tree dict。"""
    from furniture_feature_tree.feature_tree_builder import panels_to_feature_tree
    from furniture_panel_planning.panel_spec import FurnitureSpec

    from .cabinet_pipeline import plan_cabinet

    fspec = FurnitureSpec.from_dict(spec)
    result = plan_cabinet(fspec)

    return panels_to_feature_tree(
        result.panels,
        furniture_type=furniture_type,
        parameters={
            "width": fspec.width,
            "depth": fspec.depth,
            "height": fspec.height,
            "board_thickness": fspec.board_thickness,
        },
    )
````

## File: domain/skills/furniture-cad/scripts/furniture_workflow/workflow_artifact_writer.py
````python
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
        panel_path = artifact_dir / f"{artifact_name}.panel-plan.json"
        manufacturing_path = artifact_dir / f"{artifact_name}.manufacturing-plan.json"
        feature_tree_path = artifact_dir / f"{artifact_name}.feature-tree.json"
        bom_path = artifact_dir / f"{artifact_name}.bom.md"
        source_key = artifact_name
        source_filename = f"{artifact_name}.step.py"
        step_filename = f"{artifact_name}.step"
    else:
        intent_path = artifact_dir / "design-intent.json"
        panel_path = artifact_dir / "panel-plan.json"
        manufacturing_path = artifact_dir / "manufacturing-plan.json"
        feature_tree_path = artifact_dir / "feature-tree.json"
        bom_path = artifact_dir / "bom.md"
        source_key = revision.id
        source_filename = "model.step.py"
        step_filename = "model.step"

    source_dir = Path(workspace_root) / "temp" / "cad-source" / source_key
    source_dir.mkdir(parents=True, exist_ok=True)
    source_path = source_dir / source_filename
    step_path = artifact_dir / step_filename

    intent_path.write_text(
        json.dumps(revision.intent.to_dict(), ensure_ascii=False, indent=2),
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
    drilled_step_glb_path = Path(f"{drilled_step_path}.glb")
    drilled_xml_dir = artifact_dir / "六面钻文件"
    drilled_xml_paths = drill_json_to_xml_files(
        drilled_json_path,
        drilled_xml_dir,
    )

    revision.manifest.add_file("design_intent", intent_path)
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
    revision.manifest.add_file(
        "drilled_holes_step_glb",
        drilled_step_glb_path,
        derived=True,
    )
    for drilled_xml_path in drilled_xml_paths:
        revision.manifest.add_file(
            "six_side_drill_xml",
            drilled_xml_path,
            derived=True,
            panel_label=drilled_xml_path.stem,
            readiness=pipeline.bom.readiness,
        )
    revision.manifest.add_file("cad_source", source_path, derived=True)
    return source_path, step_path
````

## File: domain/skills/furniture-cad/scripts/furniture_workflow/workflow_artifacts.py
````python
"""Traceable files produced from a project revision."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

from .workflow_state import utc_now


@dataclass
class ArtifactRecord:
    kind: str
    path: str
    sha256: str
    size_bytes: int
    source_revision_id: str
    created_at: str = field(default_factory=utc_now)
    stale: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ArtifactManifest:
    source_revision_id: str
    artifacts: list[ArtifactRecord] = field(default_factory=list)

    def add_file(self, kind: str, path: str | Path, **metadata: Any) -> ArtifactRecord:
        resolved = Path(path).resolve()
        if not resolved.is_file():
            raise ValueError(f"artifact does not exist: {resolved}")
        content = resolved.read_bytes()
        record = ArtifactRecord(
            kind=kind,
            path=str(resolved),
            sha256=sha256(content).hexdigest(),
            size_bytes=len(content),
            source_revision_id=self.source_revision_id,
            metadata=metadata,
        )
        self.artifacts.append(record)
        return record

    def mark_stale(self) -> None:
        for artifact in self.artifacts:
            artifact.stale = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_revision_id": self.source_revision_id,
            "artifacts": [asdict(artifact) for artifact in self.artifacts],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArtifactManifest":
        return cls(
            source_revision_id=str(data["source_revision_id"]),
            artifacts=[ArtifactRecord(**item) for item in data.get("artifacts", [])],
        )
````

## File: domain/skills/furniture-cad/scripts/furniture_workflow/workflow_state.py
````python
"""Workflow state for one immutable design revision."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowStage(str, Enum):
    DESIGN_INTENT = "design_intent"
    # ``layout_planned`` is retained as a persisted/API compatibility value.
    # It is an independent room-placement workflow, not a serial furniture
    # generation checkpoint.
    LAYOUT_PLANNED = "layout_planned"
    PANELS_PLANNED = "panels_planned"
    MANUFACTURING_PLANNED = "manufacturing_planned"
    FEATURE_TREE_PLANNED = "feature_tree_planned"
    CAD_GENERATED = "cad_generated"
    DELIVERY_VALIDATED = "delivery_validated"
    FAILED = "failed"

    # Compatibility aliases for project files and callers created before the
    # staged workflow became explicit.
    DRAFT_INTENT = DESIGN_INTENT
    INTENT_CONFIRMED = DESIGN_INTENT
    PANEL_PLANNED = PANELS_PLANNED
    FEATURE_TREE_VALIDATED = FEATURE_TREE_PLANNED
    ARTIFACTS_GENERATED = CAD_GENERATED
    ARTIFACTS_VERIFIED = DELIVERY_VALIDATED


STAGE_SEQUENCE: tuple[WorkflowStage, ...] = (
    WorkflowStage.DESIGN_INTENT,
    WorkflowStage.PANELS_PLANNED,
    WorkflowStage.MANUFACTURING_PLANNED,
    WorkflowStage.FEATURE_TREE_PLANNED,
    WorkflowStage.CAD_GENERATED,
    WorkflowStage.DELIVERY_VALIDATED,
)

LEGACY_STAGE_VALUES = {
    "draft_intent": WorkflowStage.DESIGN_INTENT,
    "intent_confirmed": WorkflowStage.DESIGN_INTENT,
    "panel_planned": WorkflowStage.PANELS_PLANNED,
    "feature_tree_validated": WorkflowStage.FEATURE_TREE_PLANNED,
    "artifacts_generated": WorkflowStage.CAD_GENERATED,
    "artifacts_verified": WorkflowStage.DELIVERY_VALIDATED,
}


def parse_stage(value: str | WorkflowStage) -> WorkflowStage:
    if isinstance(value, WorkflowStage):
        return value
    if value in LEGACY_STAGE_VALUES:
        return LEGACY_STAGE_VALUES[value]
    return WorkflowStage(value)


def stage_index(stage: WorkflowStage) -> int:
    if stage == WorkflowStage.FAILED:
        raise ValueError("failed is not a runnable workflow stage")
    if stage == WorkflowStage.LAYOUT_PLANNED:
        raise ValueError(
            "layout_planned is independent and is not part of the serial workflow"
        )
    return STAGE_SEQUENCE.index(stage)


@dataclass(frozen=True)
class WorkflowEvent:
    stage: WorkflowStage
    timestamp: str
    note: str = ""


@dataclass
class WorkflowState:
    current: WorkflowStage = WorkflowStage.DESIGN_INTENT
    history: list[WorkflowEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.history:
            self.history.append(WorkflowEvent(self.current, utc_now(), "revision created"))

    def advance(self, stage: WorkflowStage, note: str = "") -> None:
        if self.current == WorkflowStage.FAILED:
            raise ValueError("failed workflow cannot advance")
        if stage != WorkflowStage.FAILED and stage_index(stage) < stage_index(self.current):
            raise ValueError(
                f"workflow cannot move backward from {self.current.value} to {stage.value}"
            )
        self.current = stage
        self.history.append(WorkflowEvent(stage, utc_now(), note))

    def record(self, note: str) -> None:
        self.history.append(WorkflowEvent(self.current, utc_now(), note))

    def fail(self, note: str) -> None:
        self.current = WorkflowStage.FAILED
        self.history.append(WorkflowEvent(WorkflowStage.FAILED, utc_now(), note))

    def to_dict(self) -> dict[str, Any]:
        return {
            "current": self.current.value,
            "history": [
                {**asdict(event), "stage": event.stage.value} for event in self.history
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowState":
        history = [
            WorkflowEvent(
                stage=parse_stage(str(item["stage"])),
                timestamp=str(item["timestamp"]),
                note=str(item.get("note", "")),
            )
            for item in data.get("history", [])
        ]
        current = parse_stage(str(data["current"]))
        # Schema versions that placed room layout between intent and panels
        # resume at the last serial checkpoint before that retired dependency.
        if current == WorkflowStage.LAYOUT_PLANNED:
            current = WorkflowStage.DESIGN_INTENT
        return cls(current=current, history=history)
````

## File: domain/skills/furniture-cad/scripts/furniture_workflow/workflow_store.py
````python
"""Small JSON persistence adapter for Project/Revision aggregates."""

from __future__ import annotations

import json
from pathlib import Path

from .workflow_project import Project


class JsonProjectStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def save(self, project: Project) -> Path:
        project_dir = self.root / project.id
        project_dir.mkdir(parents=True, exist_ok=True)
        path = project_dir / "project.json"
        temporary_path = project_dir / "project.json.tmp"
        temporary_path.write_text(
            json.dumps(project.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(path)
        return path

    def load(self, project_id: str) -> Project:
        path = self.root / project_id / "project.json"
        if not path.is_file():
            raise ValueError(f"project not found: {project_id}")
        return Project.from_dict(json.loads(path.read_text(encoding="utf-8")))
````

## File: domain/skills/furniture-delivery-validation/agents/openai.yaml
````yaml
interface:
  display_name: "家具交付验证"
  short_description: "验证当前 Revision 检查点谱系与文件完整性"
  default_prompt: "使用 $furniture-delivery-validation 验证当前家具交付；未执行的 STEP 几何或 Viewer 审查须标为未验证。"
````

## File: domain/skills/furniture-delivery-validation/references/delivery-checklist.md
````markdown
# 交付验证清单

回答“当前 Revision 的交付文件是否完整且可追溯？”；区分内置自动验证、上游阶段验证和外部几何审查。

## 内置自动硬关卡

1. 当前 Revision 必须包含并确认 `design_intent`、`panels_planned`、`manufacturing_planned`、`feature_tree_planned`、`cad_generated` 五个串联前置阶段，且每阶段最近一份 `ValidationReport` 通过。独立房间布局不在交付谱系中。
2. Manifest 与每个 Artifact 的 `source_revision_id` 必须等于当前 Revision；任何 `stale` 产物均失败。
3. 必需产物种类齐全，文件存在、非空，实时大小与 SHA-256 和 Manifest 一致；
   孔位 JSON/GLB/STEP、STEP Viewer 侧车和逐板六面钻 XML 均须登记。
4. `manufacturing_plan` 与 `bom` 的 Manifest `readiness` 必须等于 `manufacturing_planned.readiness`。
5. `readiness=preliminary` 只产生警告：文件可以完整交付，但不得称为工厂已确认或可直接投产。
6. 六面钻 XML 的 Manifest 记录携带板件标识和制造 `readiness`；哈希完整只
   证明文件未被篡改，不证明机床坐标已经过工厂首件确认。

## 已由上游阶段负责的语义关卡

- 意图完整性和可执行类别归 `design_intent` 验证。
- 成品外包络归 `design_intent` 验证；精确净空、背板模式、区域边界、板件标识、尺寸、位置、依赖和背板几何归 `panels_planned` 验证。
- BOM、封边、解析后的 `back_mount`、`groove` 四条槽以及“背板五金数量与主孔、配合孔数量一致”归 `manufacturing_planned` 验证。
- Feature Tree 标识、依赖、目标和切削包络归 `feature_tree_planned` 验证。
- STEP 与 Viewer 拓扑是否由 CAD Bridge 成功生成归 `cad_generated` 验证。

交付阶段核对这些验证属于当前 Revision 且已通过，不复制或重写各阶段算法。

## 不属于内置通过条件

- `validate_delivery()` 不导入 STEP、不测量几何、不生成快照，也不执行 Viewer 人工审查。
- 需要 STEP 导入、几何尺寸、快照证据时，实际调用 `external/text-to-cad/skills/cad/SKILL.md`。
- 需要可视化审查或链接时，实际调用 `external/text-to-cad/skills/cad-viewer/SKILL.md`。
- 未执行上述外部步骤时，只能报告“未验证”，不得从文件存在或哈希一致推断几何正确。

## 报告边界

- 只报告实际运行/存在的命令、验证和产物。
- `delivery_validated.passed=true` 表示检查点谱系与文件完整性通过，不自动表示几何审查通过或制造状态达到 `factory_ready`。
- 未达到 `factory_ready` 前，不得称 BOM、封边、五金或裁切清单可直接投产。
````

## File: domain/skills/furniture-delivery-validation/scripts/furniture_delivery_validation/__init__.py
````python
"""Delivery-validation stage runtime."""
````

## File: domain/skills/furniture-delivery-validation/scripts/furniture_delivery_validation/validation.py
````python
"""Structured validation results shared by every workflow layer."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Sequence


REQUIRED_DELIVERY_KINDS = frozenset(
    {
        "design_intent",
        "panel_plan",
        "manufacturing_plan",
        "feature_tree",
        "bom",
        "drilled_holes",
        "drilled_holes_glb",
        "drilled_holes_step",
        "drilled_holes_step_glb",
        "six_side_drill_xml",
        "cad_source",
        "step",
        "viewer_topology",
    }
)

PRE_DELIVERY_STAGES = (
    "design_intent",
    "panels_planned",
    "manufacturing_planned",
    "feature_tree_planned",
    "cad_generated",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    path: str = ""


@dataclass
class ValidationReport:
    stage: str
    issues: list[ValidationIssue] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now)

    @property
    def passed(self) -> bool:
        return not any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)

    def add_error(self, code: str, message: str, path: str = "") -> None:
        self.issues.append(ValidationIssue(code, message, ValidationSeverity.ERROR, path))

    def add_warning(self, code: str, message: str, path: str = "") -> None:
        self.issues.append(ValidationIssue(code, message, ValidationSeverity.WARNING, path))

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "passed": self.passed,
            "created_at": self.created_at,
            "issues": [
                {**asdict(issue), "severity": issue.severity.value} for issue in self.issues
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationReport":
        return cls(
            stage=str(data["stage"]),
            created_at=str(data["created_at"]),
            issues=[
                ValidationIssue(
                    code=str(item["code"]),
                    message=str(item["message"]),
                    severity=ValidationSeverity(item["severity"]),
                    path=str(item.get("path", "")),
                )
                for item in data.get("issues", [])
            ],
        )


def validate_delivery(
    manifest: Any,
    *,
    source_revision_id: str,
    stage_outputs: Mapping[str, Any] | None = None,
    approved_stages: Sequence[str] | None = None,
    stage_validations: Sequence[ValidationReport] | None = None,
    stage_analyses: Mapping[str, Any] | None = None,
) -> ValidationReport:
    """Validate checkpoint lineage plus artifact existence and integrity."""
    report = ValidationReport(stage="delivery_validated")
    _validate_checkpoint_lineage(
        report,
        stage_outputs=stage_outputs,
        approved_stages=approved_stages,
        stage_validations=stage_validations,
    )
    _validate_analysis_lineage(
        report,
        source_revision_id=source_revision_id,
        stage_outputs=stage_outputs,
        stage_analyses=stage_analyses,
    )
    if manifest is None:
        report.add_error("MISSING_MANIFEST", "delivery has no artifact manifest")
        return report
    if manifest.source_revision_id != source_revision_id:
        report.add_error(
            "MANIFEST_REVISION_MISMATCH",
            "artifact manifest does not belong to the current revision",
            "manifest",
        )

    artifacts = list(manifest.artifacts)
    kinds = {artifact.kind for artifact in artifacts}
    for kind in sorted(REQUIRED_DELIVERY_KINDS - kinds):
        report.add_error(
            "MISSING_REQUIRED_ARTIFACT",
            f"required delivery artifact is missing: {kind}",
            kind,
        )

    manufacturing_readiness = _manufacturing_readiness(stage_outputs)
    if manufacturing_readiness == "preliminary":
        report.add_warning(
            "MANUFACTURING_PRELIMINARY",
            "manufacturing plan is still preliminary and is not factory-ready",
            "manufacturing_planned.readiness",
        )

    for artifact in artifacts:
        path = Path(artifact.path)
        if artifact.source_revision_id != source_revision_id:
            report.add_error(
                "ARTIFACT_REVISION_MISMATCH",
                f"{artifact.kind} belongs to another revision",
                artifact.kind,
            )
        if artifact.stale:
            report.add_error(
                "STALE_ARTIFACT",
                f"{artifact.kind} is marked stale",
                artifact.kind,
            )
        if not path.is_file():
            report.add_error(
                "MISSING_ARTIFACT",
                artifact.path,
                artifact.kind,
            )
            continue
        content = path.read_bytes()
        if not content:
            report.add_error(
                "EMPTY_ARTIFACT",
                artifact.path,
                artifact.kind,
            )
            continue
        if len(content) != artifact.size_bytes:
            report.add_error(
                "ARTIFACT_SIZE_MISMATCH",
                f"{artifact.kind} size no longer matches its manifest",
                artifact.kind,
            )
        if sha256(content).hexdigest() != artifact.sha256:
            report.add_error(
                "ARTIFACT_HASH_MISMATCH",
                f"{artifact.kind} content no longer matches its manifest",
                artifact.kind,
            )
        if (
            manufacturing_readiness
            and artifact.kind in {"manufacturing_plan", "bom"}
            and artifact.metadata.get("readiness") != manufacturing_readiness
        ):
            report.add_error(
                "ARTIFACT_READINESS_MISMATCH",
                f"{artifact.kind} readiness does not match the manufacturing stage",
                artifact.kind,
            )
    return report


def _stable_digest(value: Any) -> str:
    import json

    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def _validate_analysis_lineage(
    report: ValidationReport,
    *,
    source_revision_id: str,
    stage_outputs: Mapping[str, Any] | None,
    stage_analyses: Mapping[str, Any] | None,
) -> None:
    if not stage_analyses:
        return
    for stage, raw_records in stage_analyses.items():
        if not isinstance(raw_records, Mapping):
            report.add_error(
                "INVALID_STAGE_ANALYSES",
                f"analysis records for {stage} must be an object",
                f"stage_analyses.{stage}",
            )
            continue
        source_output = stage_outputs.get(stage) if stage_outputs else None
        if source_output is None:
            report.add_error(
                "ANALYSIS_SOURCE_STAGE_MISSING",
                f"analysis source stage is missing: {stage}",
                f"stage_analyses.{stage}",
            )
            continue
        expected_digest = _stable_digest(source_output)
        for name, raw_record in raw_records.items():
            path = f"stage_analyses.{stage}.{name}"
            if not isinstance(raw_record, Mapping):
                report.add_error(
                    "INVALID_STAGE_ANALYSIS",
                    f"analysis record must be an object: {name}",
                    path,
                )
                continue
            if raw_record.get("source_revision_id") != source_revision_id:
                report.add_error(
                    "ANALYSIS_REVISION_MISMATCH",
                    f"analysis belongs to another revision: {name}",
                    path,
                )
            if raw_record.get("source_stage") != stage:
                report.add_error(
                    "ANALYSIS_STAGE_MISMATCH",
                    f"analysis source stage does not match its container: {name}",
                    path,
                )
            if raw_record.get("source_sha256") != expected_digest:
                report.add_error(
                    "ANALYSIS_SOURCE_HASH_MISMATCH",
                    f"analysis no longer matches its source stage: {name}",
                    path,
                )
            status = str(raw_record.get("status", ""))
            if status in {"unavailable", "descriptive_only"}:
                report.add_warning(
                    "ANALYSIS_INCOMPLETE",
                    f"optional analysis is {status}: {name}",
                    path,
                )


def _validate_checkpoint_lineage(
    report: ValidationReport,
    *,
    stage_outputs: Mapping[str, Any] | None,
    approved_stages: Sequence[str] | None,
    stage_validations: Sequence[ValidationReport] | None,
) -> None:
    if stage_outputs is not None:
        for stage in PRE_DELIVERY_STAGES:
            if stage not in stage_outputs:
                report.add_error(
                    "MISSING_STAGE_OUTPUT",
                    f"current revision is missing stage output: {stage}",
                    stage,
                )

    if approved_stages is not None:
        approved = set(approved_stages)
        for stage in PRE_DELIVERY_STAGES:
            if stage not in approved:
                report.add_error(
                    "UNAPPROVED_DELIVERY_SOURCE_STAGE",
                    f"delivery source stage is not approved: {stage}",
                    stage,
                )

    if stage_validations is not None:
        latest_by_stage: dict[str, ValidationReport] = {}
        for validation in stage_validations:
            latest_by_stage[validation.stage] = validation
        for stage in PRE_DELIVERY_STAGES:
            validation = latest_by_stage.get(stage)
            if validation is None:
                report.add_error(
                    "MISSING_STAGE_VALIDATION",
                    f"current revision has no validation report for: {stage}",
                    stage,
                )
            elif not validation.passed:
                report.add_error(
                    "FAILED_STAGE_VALIDATION",
                    f"current revision has a failed validation report for: {stage}",
                    stage,
                )


def _manufacturing_readiness(
    stage_outputs: Mapping[str, Any] | None,
) -> str:
    if stage_outputs is None:
        return ""
    manufacturing = stage_outputs.get("manufacturing_planned")
    if not isinstance(manufacturing, Mapping):
        return ""
    return str(manufacturing.get("readiness", "preliminary"))
````

## File: domain/skills/furniture-delivery-validation/SKILL.md
````markdown
---
name: furniture-delivery-validation
description: 用于 delivery_validated 阶段。当用户说"检查一下产物""验证完整性""校验文件""确认交付"时触发。验证当前 Revision 的前置检查点、产物谱系、文件存在性、大小和 SHA-256，并区分外部几何审查。
---

# 家具交付验证

阶段：`delivery_validated`

## 工作流

1. 要求 `cad_generated` 已确认且产物来自当前 Revision。
2. 读取 [交付验证清单](references/delivery-checklist.md) 和 `../furniture-cad/references/runtime-contract.md`。
3. 用 `FurnitureOrchestrator.run_next()` 调用 `scripts/furniture_delivery_validation/validation.py`，要求前五个串联阶段在当前 Revision 中均有输出、已确认且最近验证通过，再检查必需产物、存在性、非空、大小、SHA-256、stale 状态和 Revision 谱系。独立房间布局不属于交付前置检查点。
4. `manufacturing_planned.readiness` 必须与 manufacturing-plan/BOM 清单元数据一致；仍为 `preliminary` 时报告警告，交付完整不等于可直接投产。
5. 若当前 Revision 有 `stage_analyses`，验证每条记录的 Revision、来源阶段及 `source_sha256`；`unavailable`/`descriptive_only` 只作警告，不把旁路分析变成必需交付物。
6. 展示 `stage_outputs.delivery_validated` 后暂停；不得把未执行的 STEP 几何测量、快照或 Viewer 人工审查写成已通过。

## 边界

- 运行时在 `scripts/furniture_delivery_validation/`；`ValidationReport` 与交付规则归本包，Orchestrator 只触发、保存和推进状态。
- 内置 `delivery_validated` 只证明检查点谱系和文件完整性，不重新计算前置阶段业务语义，也不解析 STEP 几何。
- STEP 导入、几何测量或快照仅在实际调用 `external/text-to-cad/skills/cad/SKILL.md` 后单独报告。
- 可视化审查和链接仅在实际调用 `external/text-to-cad/skills/cad-viewer/SKILL.md` 后单独报告。
- 只报告实测验证和实存产物，不手改派生文件。
````

## File: domain/skills/furniture-design-intent/agents/openai.yaml
````yaml
interface:
  display_name: "家具设计意图"
  short_description: "确认家具类别与成品外包络"
  default_prompt: "使用 $furniture-design-intent 只整理并确认家具类别和宽深高外包络；不要提前询问布局、结构或制造细节。"
````

## File: domain/skills/furniture-design-intent/scripts/furniture_design_intent/__init__.py
````python
"""设计意图阶段运行时模块。"""
````

## File: domain/skills/furniture-design-intent/scripts/furniture_design_intent/validation.py
````python
"""Validation for the finished-envelope intent stage."""

from __future__ import annotations

from furniture_delivery_validation.validation import ValidationReport

from .design_intent import DesignIntent, SUPPORTED_TYPES


def validate_intent(intent: DesignIntent) -> ValidationReport:
    report = ValidationReport(stage="design_intent")
    intent_errors = intent.validate()
    for error in intent_errors:
        report.add_error("INVALID_INTENT", error)
    if intent.furniture_type not in SUPPORTED_TYPES:
        report.add_error(
            "UNSUPPORTED_FURNITURE_TYPE",
            f"supported vertical slice: {', '.join(sorted(SUPPORTED_TYPES))}",
            "furniture_type",
        )
    return report
````

## File: domain/skills/furniture-feature-tree/agents/openai.yaml
````yaml
interface:
  display_name: "家具特征树规划"
  short_description: "将制造策略转为可审查的建模特征树"
  default_prompt: "使用 $furniture-feature-tree 规划已确认方案的特征树。"
````

## File: domain/skills/furniture-feature-tree/references/feature-tree-rules.md
````markdown
# 特征树建模规则

回答“部件如何建模？”；位于板件和制造后，只负责特征标识、依赖、参数来源和装配结构。

## 建模职责

- 将语义部件转为稳定命名特征，保留包络、格位、开口等依赖。
- 制造注释可作元数据但不等于加工批准；描述“建模什么”，不描述 CAD API 调用。

## 可执行操作集

- Feature Tree v2：部件用 `box`；减料用 `cut_box`，其 `target` 指向已有板件。
- `cut_box` 来自已确认制造策略且完全位于目标包络；制造阶段是加工合法性的主责任点，本阶段仍须防御性复核目标与包络。根节点只装配加工后的板件，不含工具体。

## 背板模式映射

- `groove`：背板/背拉条为独立 `box`，四条槽转为定向 `cut_box`。
- `insert`：内嵌背板为独立 `box`，无槽；`cover`：全盖背板为独立 `box`，柜体从其前侧开始，无槽。
- 三合一、螺钉、铰链等圆孔用 drilled-holes 表达，不伪装成 `cut_box`。

## 边界

- 可描述当前运行时未覆盖的建模语义，但可执行性由工作区流水线判断。
- 不定义意图、布局、板件规则、制造公差、命令、路径、STEP 或验证；不得绕过规划器手写一次性 CAD 源码。
````

## File: domain/skills/furniture-feature-tree/scripts/furniture_feature_tree/__init__.py
````python
"""Feature-tree stage runtime."""
````

## File: domain/skills/furniture-feature-tree/scripts/furniture_feature_tree/feature_tree_builder.py
````python
"""Build an executable feature tree from confirmed manufacturing records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from furniture_manufacturing.manufacturing_models import MachiningOperation, PanelRecord


def panels_to_feature_tree(
    panels: list[PanelRecord],
    operations: list[MachiningOperation],
    furniture_type: str = "floor_cabinet",
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    features = [
        {
            "id": panel.label,
            "type": "box",
            "size": {"x": panel.size_x, "y": panel.size_y, "z": panel.size_z},
            "position": {"x": panel.pos_x, "y": panel.pos_y, "z": panel.pos_z},
            "depends_on": list(panel.depends_on),
            "tags": [panel.panel_type],
        }
        for panel in panels
    ]
    operation_nodes = [
        {
            "id": operation.id,
            "type": operation.operation_type,
            "target": operation.target_panel,
            "size": {
                "x": operation.size_x,
                "y": operation.size_y,
                "z": operation.size_z,
            },
            "position": {
                "x": operation.pos_x,
                "y": operation.pos_y,
                "z": operation.pos_z,
            },
            "depends_on": [operation.target_panel],
            "note": operation.note,
        }
        for operation in operations
    ]
    feature_ids = [feature["id"] for feature in features]
    return {
        "schema_version": 2,
        "furniture_type": furniture_type,
        "units": "mm",
        "coordinate_system": {
            "origin": "lower-left-rear-ground-corner",
            "x": "left-to-right",
            "y": "rear-to-front",
            "z": "up",
        },
        "parameters": parameters or {},
        "features": features,
        "operations": operation_nodes,
        "root": {
            "id": f"{furniture_type}_assembly",
            "type": "compound",
            "children": feature_ids,
        },
    }


def emit_panels_to_source(
    panels: list[PanelRecord],
    operations: list[MachiningOperation],
    source_path: str | Path,
    furniture_type: str = "floor_cabinet",
    parameters: dict[str, Any] | None = None,
) -> Path:
    from .feature_tree_emitter import write_build123d_source

    return write_build123d_source(
        panels_to_feature_tree(panels, operations, furniture_type, parameters),
        source_path,
    )
````

## File: domain/skills/furniture-feature-tree/scripts/furniture_feature_tree/feature_tree_emitter.py
````python
"""Emit build123d source for panel boxes and target-specific cut operations."""

from __future__ import annotations

import pprint
import re
from pathlib import Path
from typing import Any


VALID_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def write_build123d_source(
    feature_tree: dict[str, Any], source_path: str | Path
) -> Path:
    validate_feature_tree(feature_tree)
    resolved_source = Path(source_path).resolve()
    resolved_source.parent.mkdir(parents=True, exist_ok=True)
    tree_literal = pprint.pformat(
        _sanitize_for_source(feature_tree), sort_dicts=False, width=100
    )
    source = f'''"""Generated from the furniture Feature Tree. Edit the intent, not this file."""

from build123d import Align, Box, Compound, Location


FEATURE_TREE = {tree_literal}


def _box(node):
    size = node["size"]
    position = node["position"]
    shape = Box(
        size["x"],
        size["y"],
        size["z"],
        align=(Align.MIN, Align.MIN, Align.MIN),
    )
    shape.move(Location((position["x"], position["y"], position["z"])))
    return shape


def gen_step():
    operations_by_target = {{}}
    for operation in FEATURE_TREE.get("operations", []):
        operations_by_target.setdefault(operation["target"], []).append(operation)

    parts = []
    for feature in FEATURE_TREE["features"]:
        shape = _box(feature)
        for operation in operations_by_target.get(feature["id"], []):
            if operation["type"] == "cut_box":
                shape = shape - _box(operation)
        shape.label = feature["id"]
        parts.append(shape)
    return Compound(children=parts, label=FEATURE_TREE["root"]["id"])
'''
    resolved_source.write_text(source, encoding="utf-8")
    return resolved_source


def validate_feature_tree(feature_tree: dict[str, Any]) -> None:
    if feature_tree.get("schema_version") != 2:
        raise ValueError("Unsupported Feature Tree schema_version")
    features = feature_tree.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("Feature Tree must contain at least one feature")

    feature_ids: set[str] = set()
    feature_by_id: dict[str, dict[str, Any]] = {}
    for feature in features:
        feature_id = str(feature.get("id", ""))
        _validate_identifier(feature_id, "feature")
        if feature_id in feature_ids:
            raise ValueError(f"Duplicate feature id: {feature_id}")
        feature_ids.add(feature_id)
        feature_by_id[feature_id] = feature
        if feature.get("type") != "box":
            raise ValueError(
                f"Unsupported feature type for {feature_id}: {feature.get('type')!r}"
            )
        _validate_xyz(feature.get("size"), f"{feature_id}.size", positive=True)
        _validate_xyz(feature.get("position"), f"{feature_id}.position", positive=False)
        for dependency in feature.get("depends_on", []):
            if dependency not in feature_ids and dependency not in {
                item.get("id") for item in features
            }:
                raise ValueError(f"Unknown dependency for {feature_id}: {dependency}")

    operation_ids: set[str] = set()
    for operation in feature_tree.get("operations", []):
        operation_id = str(operation.get("id", ""))
        _validate_identifier(operation_id, "operation")
        if operation_id in operation_ids or operation_id in feature_ids:
            raise ValueError(f"Duplicate operation id: {operation_id}")
        operation_ids.add(operation_id)
        if operation.get("type") != "cut_box":
            raise ValueError(
                f"Unsupported operation type for {operation_id}: {operation.get('type')!r}"
            )
        target = str(operation.get("target", ""))
        if target not in feature_by_id:
            raise ValueError(f"Unknown operation target for {operation_id}: {target}")
        _validate_xyz(operation.get("size"), f"{operation_id}.size", positive=True)
        _validate_xyz(operation.get("position"), f"{operation_id}.position", positive=False)
        _validate_operation_bounds(operation, feature_by_id[target])

    root = feature_tree.get("root")
    if not isinstance(root, dict) or root.get("type") != "compound":
        raise ValueError("Feature Tree root must be a compound")
    root_id = str(root.get("id", ""))
    _validate_identifier(root_id, "root")
    if set(root.get("children", [])) != feature_ids:
        raise ValueError("Feature Tree root children must reference every feature exactly once")


# Compatibility for callers created before validation became a public stage API.
_validate_feature_tree = validate_feature_tree


def _validate_identifier(value: str, kind: str) -> None:
    if not VALID_IDENTIFIER.fullmatch(value):
        raise ValueError(f"Invalid {kind} id: {value!r}")


def _validate_operation_bounds(
    operation: dict[str, Any], target: dict[str, Any]
) -> None:
    tolerance = 1e-6
    for axis in ("x", "y", "z"):
        operation_start = float(operation["position"][axis])
        operation_end = operation_start + float(operation["size"][axis])
        target_start = float(target["position"][axis])
        target_end = target_start + float(target["size"][axis])
        if operation_start < target_start - tolerance or operation_end > target_end + tolerance:
            raise ValueError(
                f"{operation['id']} exceeds target {target['id']} on {axis.upper()}"
            )


def _validate_xyz(value: Any, field_name: str, *, positive: bool) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    for axis in ("x", "y", "z"):
        axis_value = value.get(axis)
        if isinstance(axis_value, bool) or not isinstance(axis_value, (int, float)):
            raise ValueError(f"{field_name}.{axis} must be numeric")
        if positive and axis_value <= 0:
            raise ValueError(f"{field_name}.{axis} must be greater than zero")


def _sanitize_for_source(obj: Any) -> Any:
    """Recursively replace non-ASCII strings so the emitted source is ASCII-safe."""
    if isinstance(obj, str):
        try:
            obj.encode("ascii")
        except UnicodeEncodeError:
            return obj.encode("ascii", errors="replace").decode("ascii")
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_source(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_source(item) for item in obj]
    return obj
````

## File: domain/skills/furniture-feature-tree/scripts/furniture_feature_tree/validation.py
````python
"""Validation owned by the feature-tree-planning stage."""

from __future__ import annotations

from typing import Any

from furniture_delivery_validation.validation import ValidationReport

from .feature_tree_emitter import validate_feature_tree as validate_feature_tree_contract


def validate_feature_tree(feature_tree: dict[str, Any]) -> ValidationReport:
    report = ValidationReport(stage="feature_tree_planned")
    try:
        validate_feature_tree_contract(feature_tree)
    except ValueError as exc:
        report.add_error("INVALID_FEATURE_TREE", str(exc))
    return report
````

## File: domain/skills/furniture-feature-tree/SKILL.md
````markdown
---
name: furniture-feature-tree
description: 用于 feature_tree_planned 阶段。当用户说"建模顺序""哪个部件先做""槽怎么切""背板槽位置"时触发。将已确认制造策略转为可审查的部件、依赖、顺序和 CAD 建模语义，不生成几何。
---

# 家具特征树规划

阶段：`feature_tree_planned`

## 工作流

1. 要求设计意图、板件和制造策略均已确认；独立房间布局不是前置条件。
2. 按 [特征树建模规则](references/feature-tree-rules.md) 转换建模职责、依赖和顺序。
3. Feature Tree v2 用 `box` 表示板件，用带 `target` 的 `cut_box` 表示切削；制造阶段负责槽包络的主校验，本阶段对目标存在性和切削包络做防御性复核。
4. 仅 `groove` 的四条背板槽转为 `cut_box`；`insert/cover` 连接孔和背拉条端孔保留为 drilled-holes，不伪装成方盒切削。
5. 用 `FurnitureOrchestrator.run_next()` 生成；`scripts/furniture_feature_tree/validation.py` 调用公开 `validate_feature_tree()` 校验。
6. 展示 `stage_outputs.feature_tree_planned` 后暂停，不生成 CAD。

## 边界

- 运行时在 `scripts/furniture_feature_tree/`。
- 修改特征树时使用 `revise_stage_output()`，使本阶段及下游失效。
- 不直调发射器、CAD Bridge、外部 CAD CLI，也不定义第二套格式或运行时。
````

## File: domain/skills/furniture-layout/agents/openai.yaml
````yaml
interface:
  display_name: "家具布局规划"
  short_description: "计算柜体包络、房间位置、碰撞和 SVG 预览"
  default_prompt: "仅在用户明确要求摆放图时使用 $furniture-layout，根据家具外包络规划房间定位并展示预览；遇到越界、门窗遮挡或障碍物碰撞时停止。门数、层板数和结构决策直接交给板件规划，不把本技能作为家具生成前置步骤。"
````

## File: domain/skills/furniture-layout/scripts/furniture_layout/__init__.py
````python
"""Layout-planning stage runtime."""
````

## File: domain/skills/furniture-layout/scripts/furniture_layout/layout_preview.py
````python
"""Generate a dependency-free SVG preview for independent room placement."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from math import radians, sqrt, tan
from typing import Iterable

from .layout_planning import CabinetLayout
from .room_planning import RoomOpening, RoomPlacementPlan


PREVIEW_WIDTH_PX = 960
PREVIEW_HEIGHT_PX = 720
DRAWING_LEFT_PX = 76
DRAWING_RIGHT_PX = 884
DRAWING_TOP_PX = 118
DRAWING_BOTTOM_PX = 590

Point3D = tuple[float, float, float]
Point2D = tuple[float, float]
Vector3D = tuple[float, float, float]


@dataclass(frozen=True)
class PerspectiveProjector:
    camera: Point3D
    right: Vector3D
    up: Vector3D
    forward: Vector3D
    focal_length: float
    scale: float
    offset_x: float
    offset_y: float

    def camera_coordinates(self, point: Point3D) -> Point3D:
        relative = _subtract(point, self.camera)
        return (
            _dot(relative, self.right),
            _dot(relative, self.up),
            _dot(relative, self.forward),
        )

    def depth(self, point: Point3D) -> float:
        return self.camera_coordinates(point)[2]

    def raw(self, point: Point3D) -> Point2D:
        camera_x, camera_y, depth = self.camera_coordinates(point)
        if depth <= 1e-6:
            raise ValueError("preview point is behind the perspective camera")
        return (
            self.focal_length * camera_x / depth,
            -self.focal_length * camera_y / depth,
        )

    def __call__(self, point: Point3D) -> Point2D:
        raw_x, raw_y = self.raw(point)
        return (
            self.offset_x + raw_x * self.scale,
            self.offset_y + raw_y * self.scale,
        )


def render_layout_preview(
    plan: RoomPlacementPlan,
    layout: CabinetLayout,
) -> dict[str, object]:
    """Render a transparent room volume and opaque furniture envelope."""
    room = plan.room
    project = _build_projector(
        room.width_mm,
        room.depth_mm,
        room.height_mm,
    )
    room_corners = _room_corners(
        room.width_mm,
        room.depth_mm,
        room.height_mm,
    )

    svg: list[str] = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{PREVIEW_WIDTH_PX}" height="{PREVIEW_HEIGHT_PX}" '
            f'viewBox="0 0 {PREVIEW_WIDTH_PX} {PREVIEW_HEIGHT_PX}" '
            f'role="img" aria-labelledby="title desc">'
        ),
        (
            f'<title id="title">{escape(room.name)}家具透视三维包络预览'
            "</title>"
        ),
        (
            f'<desc id="desc">{escape(plan.furniture_label)}在'
            f'{escape(room.name)}中的透视三维占位；房间为透明包络，'
            "蓝色不透明长方体为家具成品包络。</desc>"
        ),
        "<defs>",
        (
            '<linearGradient id="room-floor" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0%" stop-color="#e2e8f0" stop-opacity="0.18"/>'
            '<stop offset="100%" stop-color="#cbd5e1" stop-opacity="0.34"/>'
            "</linearGradient>"
        ),
        (
            '<linearGradient id="furniture-top" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0%" stop-color="#93c5fd"/>'
            '<stop offset="100%" stop-color="#3b82f6"/>'
            "</linearGradient>"
        ),
        (
            '<filter id="solid-shadow" x="-30%" y="-30%" '
            'width="170%" height="180%">'
            '<feDropShadow dx="0" dy="8" stdDeviation="8" '
            'flood-color="#0f172a" flood-opacity="0.28"/>'
            "</filter>"
        ),
        "</defs>",
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        (
            '<text x="76" y="48" font-family="sans-serif" font-size="25" '
            f'font-weight="700" fill="#0f172a">{escape(room.name)}</text>'
        ),
        (
            '<text x="76" y="74" font-family="sans-serif" font-size="14" '
            f'fill="#475569">{room.width_mm:g} × {room.depth_mm:g} × '
            f'{room.height_mm:g} mm · 透明为房间 · 蓝色为家具包络'
            " · 红色为障碍物 · 青色为门窗</text>"
        ),
    ]

    _append_room_background(svg, room_corners, project)

    for opening in room.openings:
        points = _opening_face(
            room.width_mm,
            room.depth_mm,
            opening,
        )
        svg.extend(
            [
                _polygon(
                    points,
                    project,
                    fill="#22d3ee",
                    fill_opacity=0.42,
                    stroke="#0891b2",
                    stroke_width=2.0,
                ),
                _face_label(
                    points,
                    project,
                    opening.kind,
                    color="#155e75",
                ),
            ]
        )

    # Draw the transparent room wireframe before solid envelopes so furniture
    # correctly occludes room edges that pass behind it.
    _append_room_foreground(svg, room_corners, project)

    obstacle_boxes: list[tuple[float, list[str]]] = []
    for obstacle in room.obstacles:
        obstacle_footprint = (
            (obstacle.x_mm, obstacle.y_mm),
            (obstacle.x_mm + obstacle.width_mm, obstacle.y_mm),
            (
                obstacle.x_mm + obstacle.width_mm,
                obstacle.y_mm + obstacle.depth_mm,
            ),
            (obstacle.x_mm, obstacle.y_mm + obstacle.depth_mm),
        )
        obstacle_svg, sort_depth = _render_solid_box(
            footprint=obstacle_footprint,
            z_start=obstacle.z_mm,
            z_end=obstacle.z_mm + obstacle.height_mm,
            project=project,
            side_colors=("#dc2626", "#ef4444", "#b91c1c", "#f87171"),
            top_fill="#fca5a5",
            stroke="#991b1b",
            label=obstacle.kind,
            label_color="#7f1d1d",
            shadow=False,
        )
        obstacle_boxes.append((sort_depth, obstacle_svg))

    furniture_svg, furniture_sort_depth = _render_solid_box(
        footprint=plan.furniture_footprint,
        z_start=plan.placement.origin_z_mm,
        z_end=plan.placement.origin_z_mm + layout.height,
        project=project,
        side_colors=("#1d4ed8", "#2563eb", "#1e40af", "#3b82f6"),
        top_fill="url(#furniture-top)",
        stroke="#1e3a8a",
        label=plan.furniture_label,
        label_color="white",
        shadow=True,
    )

    solid_boxes = obstacle_boxes + [
        (furniture_sort_depth, furniture_svg)
    ]
    for _, box_svg in sorted(
        solid_boxes,
        key=lambda item: item[0],
        reverse=True,
    ):
        svg.extend(box_svg)

    _append_axis_indicator(svg)

    placement_label = _placement_label(plan)
    svg.extend(
        [
            (
                '<rect x="76" y="620" width="808" height="66" rx="12" '
                'fill="white" stroke="#dbe4ee"/>'
            ),
            (
                '<text x="94" y="646" font-family="sans-serif" '
                'font-size="14" font-weight="700" fill="#0f172a">'
                f'{escape(plan.furniture_label)} · '
                f'{layout.width:g} × {layout.depth:g} × {layout.height:g} mm'
                "</text>"
            ),
            (
                '<text x="94" y="671" font-family="sans-serif" '
                'font-size="13" fill="#475569">'
                f'{escape(placement_label)} · '
                f'原点 ({plan.placement.origin_x_mm:g}, '
                f'{plan.placement.origin_y_mm:g}, '
                f'{plan.placement.origin_z_mm:g}) mm'
                "</text>"
            ),
            "</svg>",
        ]
    )
    return {
        "media_type": "image/svg+xml",
        "view_kind": "perspective_envelope",
        "width_px": PREVIEW_WIDTH_PX,
        "height_px": PREVIEW_HEIGHT_PX,
        "alt_text": (
            f"{plan.furniture_label}在{room.name}中的透视三维包络位置："
            f"房间透明，家具为不透明长方体；原点 "
            f"({plan.placement.origin_x_mm:g}, "
            f"{plan.placement.origin_y_mm:g}, "
            f"{plan.placement.origin_z_mm:g}) mm，"
            f"旋转 {plan.placement.rotation_z_deg:g}°"
        ),
        "svg": "".join(svg),
    }


def _build_projector(
    room_width: float,
    room_depth: float,
    room_height: float,
) -> PerspectiveProjector:
    """Fit a true perspective camera view into the fixed SVG viewport."""
    camera = (
        room_width * 1.20,
        -room_depth * 0.72,
        room_height * 1.18,
    )
    target = (
        room_width * 0.48,
        room_depth * 0.52,
        room_height * 0.38,
    )
    forward = _normalize(_subtract(target, camera))
    right = _normalize(_cross(forward, (0.0, 0.0, 1.0)))
    up = _normalize(_cross(right, forward))
    prototype = PerspectiveProjector(
        camera=camera,
        right=right,
        up=up,
        forward=forward,
        focal_length=1.0 / tan(radians(50.0) / 2.0),
        scale=1.0,
        offset_x=0.0,
        offset_y=0.0,
    )
    raw_points = [
        prototype.raw(point)
        for point in _room_corners(room_width, room_depth, room_height)
    ]
    min_x = min(point[0] for point in raw_points)
    max_x = max(point[0] for point in raw_points)
    min_y = min(point[1] for point in raw_points)
    max_y = max(point[1] for point in raw_points)
    raw_width = max(max_x - min_x, 1.0)
    raw_height = max(max_y - min_y, 1.0)
    scale = min(
        (DRAWING_RIGHT_PX - DRAWING_LEFT_PX) / raw_width,
        (DRAWING_BOTTOM_PX - DRAWING_TOP_PX) / raw_height,
    )
    raw_center_x = (min_x + max_x) / 2.0
    raw_center_y = (min_y + max_y) / 2.0
    return PerspectiveProjector(
        camera=camera,
        right=right,
        up=up,
        forward=forward,
        focal_length=prototype.focal_length,
        scale=scale,
        offset_x=(DRAWING_LEFT_PX + DRAWING_RIGHT_PX) / 2.0
        - raw_center_x * scale,
        offset_y=(DRAWING_TOP_PX + DRAWING_BOTTOM_PX) / 2.0
        - raw_center_y * scale,
    )


def _room_corners(
    width: float,
    depth: float,
    height: float,
) -> tuple[Point3D, ...]:
    return (
        (0.0, 0.0, 0.0),
        (width, 0.0, 0.0),
        (width, depth, 0.0),
        (0.0, depth, 0.0),
        (0.0, 0.0, height),
        (width, 0.0, height),
        (width, depth, height),
        (0.0, depth, height),
    )


def _append_room_background(
    svg: list[str],
    corners: tuple[Point3D, ...],
    project: PerspectiveProjector,
) -> None:
    bottom = corners[:4]
    top = corners[4:]
    svg.extend(
        [
            _polygon(
                bottom,
                project,
                fill="url(#room-floor)",
                stroke="#94a3b8",
                stroke_width=1.4,
            ),
            _polygon(
                (bottom[2], bottom[3], top[3], top[2]),
                project,
                fill="#bae6fd",
                fill_opacity=0.11,
                stroke="#94a3b8",
                stroke_width=1.2,
            ),
            _polygon(
                (bottom[1], bottom[2], top[2], top[1]),
                project,
                fill="#cbd5e1",
                fill_opacity=0.10,
                stroke="#94a3b8",
                stroke_width=1.2,
            ),
            _polygon(
                top,
                project,
                fill="#e0f2fe",
                fill_opacity=0.04,
                stroke="#94a3b8",
                stroke_width=1.2,
                stroke_dasharray="7 6",
            ),
        ]
    )


def _append_room_foreground(
    svg: list[str],
    corners: tuple[Point3D, ...],
    project: PerspectiveProjector,
) -> None:
    edge_pairs = (
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    )
    for start_index, end_index in edge_pairs:
        start = project(corners[start_index])
        end = project(corners[end_index])
        hidden = (start_index, end_index) in {
            (2, 3),
            (6, 7),
            (2, 6),
            (3, 7),
        }
        svg.append(
            (
                f'<line x1="{start[0]:.3f}" y1="{start[1]:.3f}" '
                f'x2="{end[0]:.3f}" y2="{end[1]:.3f}" '
                'stroke="#475569" '
                f'stroke-width="{1.4 if hidden else 2.2}" '
                f'stroke-opacity="{0.55 if hidden else 0.82}"'
                f'{" stroke-dasharray=\"7 6\"" if hidden else ""}/>'
            )
        )


def _render_solid_box(
    *,
    footprint: Iterable[tuple[float, float]],
    z_start: float,
    z_end: float,
    project: PerspectiveProjector,
    side_colors: tuple[str, str, str, str],
    top_fill: str,
    stroke: str,
    label: str,
    label_color: str,
    shadow: bool,
) -> tuple[list[str], float]:
    base = tuple((x, y, z_start) for x, y in footprint)
    top = tuple((x, y, z_end) for x, y in footprint)
    if len(base) != 4:
        raise ValueError("solid box footprint must contain four points")

    faces: list[
        tuple[float, tuple[Point3D, ...], str, float, str]
    ] = []
    for index in range(4):
        next_index = (index + 1) % 4
        face = (
            base[index],
            base[next_index],
            top[next_index],
            top[index],
        )
        if _face_visible(face, project.camera):
            average_depth = sum(project.depth(point) for point in face) / 4.0
            faces.append(
                (average_depth, face, side_colors[index], 2.2, "")
            )

    if _face_visible(top, project.camera):
        top_attributes = ' filter="url(#solid-shadow)"' if shadow else ""
        faces.append(
            (
                sum(project.depth(point) for point in top) / 4.0,
                top,
                top_fill,
                2.4,
                top_attributes,
            )
        )

    rendered: list[str] = []
    for _, face, fill, stroke_width, extra_attributes in sorted(
        faces,
        key=lambda item: item[0],
        reverse=True,
    ):
        rendered.append(
            _polygon(
                face,
                project,
                fill=fill,
                stroke=stroke,
                stroke_width=stroke_width,
                extra_attributes=extra_attributes,
            )
        )

    label_point = project(
        (
            sum(point[0] for point in top) / 4.0,
            sum(point[1] for point in top) / 4.0,
            (z_start + z_end) / 2.0,
        )
    )
    rendered.extend(
        [
            (
                f'<text x="{label_point[0]:.3f}" y="{label_point[1]:.3f}" '
                'text-anchor="middle" dominant-baseline="middle" '
                'font-family="sans-serif" font-size="16" font-weight="700" '
                f'fill="{label_color}" paint-order="stroke" '
                f'stroke="{stroke}" stroke-width="0.8">'
                f"{escape(label)}</text>"
            ),
        ]
    )
    sort_depth = sum(
        project.depth(point) for point in (*base, *top)
    ) / 8.0
    return rendered, sort_depth


def _face_visible(
    face: tuple[Point3D, ...],
    camera: Point3D,
) -> bool:
    first_edge = _subtract(face[1], face[0])
    second_edge = _subtract(face[2], face[1])
    normal = _cross(first_edge, second_edge)
    centroid = (
        sum(point[0] for point in face) / len(face),
        sum(point[1] for point in face) / len(face),
        sum(point[2] for point in face) / len(face),
    )
    return _dot(normal, _subtract(camera, centroid)) > 1e-6


def _opening_face(
    room_width: float,
    room_depth: float,
    opening: RoomOpening,
) -> tuple[Point3D, ...]:
    start = opening.offset_mm
    end = opening.offset_mm + opening.width_mm
    z_start = opening.sill_height_mm
    z_end = z_start + opening.height_mm
    if opening.wall == "north":
        return (
            (start, 0.0, z_start),
            (end, 0.0, z_start),
            (end, 0.0, z_end),
            (start, 0.0, z_end),
        )
    if opening.wall == "east":
        return (
            (room_width, start, z_start),
            (room_width, end, z_start),
            (room_width, end, z_end),
            (room_width, start, z_end),
        )
    if opening.wall == "south":
        return (
            (room_width - start, room_depth, z_start),
            (room_width - end, room_depth, z_start),
            (room_width - end, room_depth, z_end),
            (room_width - start, room_depth, z_end),
        )
    return (
        (0.0, room_depth - start, z_start),
        (0.0, room_depth - end, z_start),
        (0.0, room_depth - end, z_end),
        (0.0, room_depth - start, z_end),
    )


def _face_label(
    points: Iterable[Point3D],
    project: PerspectiveProjector,
    label: str,
    *,
    color: str,
) -> str:
    projected = [project(point) for point in points]
    center_x = sum(point[0] for point in projected) / len(projected)
    center_y = sum(point[1] for point in projected) / len(projected)
    return (
        f'<text x="{center_x:.3f}" y="{center_y:.3f}" '
        'text-anchor="middle" dominant-baseline="middle" '
        'font-family="sans-serif" font-size="11" font-weight="700" '
        f'fill="{color}">{escape(label)}</text>'
    )


def _polygon(
    points: Iterable[Point3D],
    project: PerspectiveProjector,
    *,
    fill: str,
    stroke: str,
    stroke_width: float,
    fill_opacity: float | None = None,
    stroke_dasharray: str | None = None,
    extra_attributes: str = "",
) -> str:
    point_text = " ".join(
        f"{screen_x:.3f},{screen_y:.3f}"
        for screen_x, screen_y in (project(point) for point in points)
    )
    opacity_attribute = (
        "" if fill_opacity is None else f' fill-opacity="{fill_opacity:g}"'
    )
    dash_attribute = (
        ""
        if stroke_dasharray is None
        else f' stroke-dasharray="{stroke_dasharray}"'
    )
    return (
        f'<polygon points="{point_text}" fill="{fill}"'
        f'{opacity_attribute} stroke="{stroke}" '
        f'stroke-width="{stroke_width:g}"{dash_attribute}'
        f"{extra_attributes}/>"
    )


def _placement_label(plan: RoomPlacementPlan) -> str:
    wall_names = {
        "south": "南墙",
        "east": "东墙",
        "north": "北墙",
        "west": "西墙",
    }
    position = wall_names.get(
        plan.placement.host_wall or "",
        "自由摆放",
    )
    return (
        f"位置：{position} · 旋转 {plan.placement.rotation_z_deg:g}°"
        f" · 标高 {plan.placement.origin_z_mm:g} mm"
    )


def _subtract(first: Point3D, second: Point3D) -> Vector3D:
    return (
        first[0] - second[0],
        first[1] - second[1],
        first[2] - second[2],
    )


def _dot(first: Vector3D, second: Vector3D) -> float:
    return (
        first[0] * second[0]
        + first[1] * second[1]
        + first[2] * second[2]
    )


def _cross(first: Vector3D, second: Vector3D) -> Vector3D:
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def _normalize(vector: Vector3D) -> Vector3D:
    length = sqrt(_dot(vector, vector))
    if length <= 1e-9:
        raise ValueError("perspective camera vector must be non-zero")
    return (
        vector[0] / length,
        vector[1] / length,
        vector[2] / length,
    )


def _append_axis_indicator(svg: list[str]) -> None:
    origin_x = 828.0
    origin_y = 548.0
    axes = (
        (origin_x + 38, origin_y + 13, "#dc2626", "X"),
        (origin_x - 34, origin_y + 13, "#16a34a", "Y"),
        (origin_x, origin_y - 43, "#2563eb", "Z"),
    )
    for end_x, end_y, color, label in axes:
        svg.extend(
            [
                (
                    f'<line x1="{origin_x:g}" y1="{origin_y:g}" '
                    f'x2="{end_x:g}" y2="{end_y:g}" stroke="{color}" '
                    'stroke-width="3" stroke-linecap="round"/>'
                ),
                (
                    f'<circle cx="{end_x:g}" cy="{end_y:g}" r="4" '
                    f'fill="{color}"/>'
                ),
                (
                    f'<text x="{end_x + 7:g}" y="{end_y + 4:g}" '
                    'font-family="sans-serif" font-size="12" '
                    f'font-weight="700" fill="{color}">{label}</text>'
                ),
            ]
        )
````

## File: domain/skills/furniture-layout/scripts/furniture_layout/layout_viewer.py
````python
"""Generate a self-contained orbit viewer for independent room placement."""

from __future__ import annotations

from html import escape
import json

from .layout_planning import CabinetLayout
from .room_planning import RoomPlacementPlan


VIEWER_WIDTH_PX = 960
VIEWER_HEIGHT_PX = 720


def render_layout_viewer(
    plan: RoomPlacementPlan,
    layout: CabinetLayout,
) -> dict[str, object]:
    """Return deterministic HTML that renders the current layout interactively."""
    scene = {
        "room": plan.room.to_dict(),
        "furniture": {
            "label": plan.furniture_label,
            "footprint": [list(point) for point in plan.furniture_footprint],
            "z_start": plan.placement.origin_z_mm,
            "z_end": plan.placement.origin_z_mm + layout.height,
            "dimensions": [layout.width, layout.depth, layout.height],
        },
        "obstacles": [
            {
                "label": obstacle.kind,
                "footprint": [list(point) for point in obstacle.footprint],
                "z_start": obstacle.z_mm,
                "z_end": obstacle.z_mm + obstacle.height_mm,
            }
            for obstacle in plan.room.obstacles
        ],
        "openings": [opening.to_dict() for opening in plan.room.openings],
    }
    scene_json = (
        json.dumps(scene, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    html = (
        _VIEWER_HTML.replace("__SCENE_JSON__", scene_json)
        .replace("__ROOM_NAME__", escape(plan.room.name, quote=True))
        .replace("__FURNITURE_LABEL__", escape(plan.furniture_label, quote=True))
    )
    return {
        "media_type": "text/html",
        "view_kind": "interactive_orbit_envelope",
        "width_px": VIEWER_WIDTH_PX,
        "height_px": VIEWER_HEIGHT_PX,
        "controls": [
            "drag_orbit",
            "wheel_zoom",
            "perspective",
            "front",
            "left",
            "right",
            "top",
            "reset",
        ],
        "alt_text": (
            f"{plan.furniture_label}在{plan.room.name}中的可旋转三维包络；"
            "拖拽旋转、滚轮缩放，并可选择正视、左右视图和俯视"
        ),
        "html": html,
    }


_VIEWER_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<title>__ROOM_NAME__ · __FURNITURE_LABEL__ · 互动布局预览</title>
<style>
:root{font-family:Inter,"Microsoft YaHei",system-ui,sans-serif;color:#0f172a;background:#eef2f7}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;padding:16px}
.viewer{width:min(960px,100%);background:#f8fafc;border:1px solid #cbd5e1;border-radius:18px;box-shadow:0 18px 50px rgba(15,23,42,.16);overflow:hidden}
header{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:16px 18px 12px;background:#fff;border-bottom:1px solid #e2e8f0}
h1{font-size:18px;margin:0 0 4px}.hint{font-size:12px;color:#64748b;margin:0}
.toolbar{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:7px}
button{appearance:none;border:1px solid #cbd5e1;background:#fff;color:#334155;border-radius:9px;padding:7px 10px;font:inherit;font-size:12px;font-weight:600;cursor:pointer}
button:hover,button:focus-visible{border-color:#2563eb;color:#1d4ed8;outline:none}
button[aria-pressed="true"]{background:#2563eb;border-color:#2563eb;color:#fff}
.stage{position:relative;background:radial-gradient(circle at 50% 38%,#fff 0,#f1f5f9 58%,#e2e8f0 100%)}
canvas{display:block;width:100%;height:auto;touch-action:none;cursor:grab}
canvas.dragging{cursor:grabbing}
.badge{position:absolute;left:16px;bottom:14px;padding:7px 10px;border-radius:9px;background:rgba(255,255,255,.88);border:1px solid rgba(203,213,225,.9);font-size:12px;color:#475569;backdrop-filter:blur(6px)}
footer{display:flex;justify-content:space-between;gap:16px;padding:10px 18px 13px;background:#fff;border-top:1px solid #e2e8f0;font-size:12px;color:#64748b}
@media(max-width:760px){header{align-items:flex-start;flex-direction:column}.toolbar{justify-content:flex-start}button{padding:8px 11px}}
</style>
</head>
<body>
<main class="viewer" aria-label="可旋转家具布局预览">
  <header>
    <div><h1>__ROOM_NAME__ · __FURNITURE_LABEL__</h1><p class="hint">拖拽旋转 · 滚轮缩放 · 选择标准视角</p></div>
    <nav class="toolbar" aria-label="视角选择">
      <button type="button" data-view="perspective" aria-pressed="true">透视</button>
      <button type="button" data-view="front" aria-pressed="false">正视</button>
      <button type="button" data-view="left" aria-pressed="false">左视</button>
      <button type="button" data-view="right" aria-pressed="false">右视</button>
      <button type="button" data-view="top" aria-pressed="false">俯视</button>
      <button type="button" data-view="reset" aria-pressed="false">重置</button>
    </nav>
  </header>
  <section class="stage">
    <canvas id="scene" width="960" height="600" aria-label="透明房间与不透明家具包络"></canvas>
    <div class="badge" id="status">透视视角</div>
  </section>
  <footer><span>透明线框：房间</span><span>蓝色实体：家具包络</span><span>红色实体：障碍物</span></footer>
</main>
<script id="scene-data" type="application/json">__SCENE_JSON__</script>
<script>
(()=>{
"use strict";
const scene=JSON.parse(document.getElementById("scene-data").textContent);
const canvas=document.getElementById("scene"),ctx=canvas.getContext("2d"),status=document.getElementById("status");
const W=canvas.width,H=canvas.height,room=scene.room;
const target=[room.width_mm/2,room.depth_mm/2,room.height_mm*.42];
const diagonal=Math.hypot(room.width_mm,room.depth_mm,room.height_mm);
const defaults={yaw:-Math.PI/4,pitch:.48,distance:diagonal*1.65};
const state={...defaults,dragging:false,lastX:0,lastY:0,active:"perspective"};
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const sub=(a,b)=>[a[0]-b[0],a[1]-b[1],a[2]-b[2]];
const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const norm=a=>{const n=Math.hypot(...a)||1;return a.map(v=>v/n)};
const midpoint=pts=>pts[0].map((_,i)=>pts.reduce((s,p)=>s+p[i],0)/pts.length);
function camera(){
  const cp=Math.cos(state.pitch),sp=Math.sin(state.pitch),cy=Math.cos(state.yaw),sy=Math.sin(state.yaw);
  const position=[target[0]+state.distance*cp*cy,target[1]+state.distance*cp*sy,target[2]+state.distance*sp];
  const forward=norm(sub(target,position)),right=norm(cross(forward,[0,0,1])),up=norm(cross(right,forward));
  return{position,forward,right,up};
}
function projector(cam){
  const focal=H/(2*Math.tan(48*Math.PI/360));
  return point=>{const rel=sub(point,cam.position),depth=dot(rel,cam.forward);return{x:W/2+dot(rel,cam.right)/depth*focal,y:H/2-dot(rel,cam.up)/depth*focal,depth}};
}
function roomVertices(){const w=room.width_mm,d=room.depth_mm,h=room.height_mm;return[[0,0,0],[w,0,0],[w,d,0],[0,d,0],[0,0,h],[w,0,h],[w,d,h],[0,d,h]]}
function boxVertices(box){const b=box.footprint.map(p=>[p[0],p[1],box.z_start]),t=box.footprint.map(p=>[p[0],p[1],box.z_end]);return[...b,...t]}
const boxFaces=[[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]];
const roomFaces=[[0,1,2,3],[4,7,6,5],[0,4,5,1],[1,5,6,2],[2,6,7,3],[3,7,4,0]];
const roomEdges=[[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
function visible(face,verts,cam){const a=verts[face[0]],b=verts[face[1]],c=verts[face[2]],normal=cross(sub(b,a),sub(c,b));return dot(normal,sub(cam.position,midpoint(face.map(i=>verts[i]))))>0}
function path(points){ctx.beginPath();ctx.moveTo(points[0].x,points[0].y);for(const p of points.slice(1))ctx.lineTo(p.x,p.y);ctx.closePath()}
function openingPoints(o){const s=o.offset_mm,e=s+o.width_mm,z0=o.sill_height_mm,z1=z0+o.height_mm,w=room.width_mm,d=room.depth_mm;if(o.wall==="north")return[[s,0,z0],[e,0,z0],[e,0,z1],[s,0,z1]];if(o.wall==="east")return[[w,s,z0],[w,e,z0],[w,e,z1],[w,s,z1]];if(o.wall==="south")return[[w-s,d,z0],[w-e,d,z0],[w-e,d,z1],[w-s,d,z1]];return[[0,d-s,z0],[0,d-e,z0],[0,d-e,z1],[0,d-s,z1]]}
function drawRoom(project,cam){
  const verts=roomVertices(),faces=roomFaces.map(face=>({face,depth:face.reduce((s,i)=>s+project(verts[i]).depth,0)/face.length})).sort((a,b)=>b.depth-a.depth);
  for(const item of faces){const pts=item.face.map(i=>project(verts[i]));path(pts);ctx.fillStyle="rgba(186,230,253,.055)";ctx.fill()}
  for(const opening of scene.openings){const pts=openingPoints(opening).map(project);path(pts);ctx.fillStyle="rgba(34,211,238,.34)";ctx.fill();ctx.strokeStyle="rgba(8,145,178,.8)";ctx.lineWidth=2;ctx.stroke()}
  ctx.strokeStyle="rgba(71,85,105,.72)";ctx.lineWidth=1.6;for(const edge of roomEdges){const a=project(verts[edge[0]]),b=project(verts[edge[1]]);ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke()}
}
function solidFaces(box,kind,project,cam){
  const verts=boxVertices(box),palette=kind==="furniture"?["#1e40af","#60a5fa","#1d4ed8","#2563eb","#1e3a8a","#3b82f6"]:["#991b1b","#fca5a5","#b91c1c","#dc2626","#7f1d1d","#ef4444"];
  return boxFaces.filter(face=>visible(face,verts,cam)).map((face,index)=>({points:face.map(i=>project(verts[i])),depth:face.reduce((s,i)=>s+project(verts[i]).depth,0)/face.length,fill:palette[boxFaces.indexOf(face)],stroke:kind==="furniture"?"#172554":"#7f1d1d"}))
}
function drawSolids(project,cam){
  const entries=[...scene.obstacles.map(box=>({box,kind:"obstacle"})),{box:scene.furniture,kind:"furniture"}],faces=[];
  for(const entry of entries)faces.push(...solidFaces(entry.box,entry.kind,project,cam));
  faces.sort((a,b)=>b.depth-a.depth);for(const face of faces){path(face.points);ctx.fillStyle=face.fill;ctx.fill();ctx.strokeStyle=face.stroke;ctx.lineWidth=2;ctx.stroke()}
  const f=scene.furniture,c=[f.footprint.reduce((s,p)=>s+p[0],0)/4,f.footprint.reduce((s,p)=>s+p[1],0)/4,(f.z_start+f.z_end)/2],p=project(c);ctx.font="700 16px Microsoft YaHei, sans-serif";ctx.textAlign="center";ctx.textBaseline="middle";ctx.lineWidth=4;ctx.strokeStyle="rgba(30,58,138,.9)";ctx.strokeText(f.label,p.x,p.y);ctx.fillStyle="#fff";ctx.fillText(f.label,p.x,p.y)
}
function drawAxis(){const x=W-88,y=H-58,axes=[[36,12,"#dc2626","X"],[-31,12,"#16a34a","Y"],[0,-39,"#2563eb","Z"]];ctx.lineWidth=3;ctx.font="700 12px sans-serif";for(const [dx,dy,color,label] of axes){ctx.strokeStyle=color;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+dx,y+dy);ctx.stroke();ctx.fillStyle=color;ctx.beginPath();ctx.arc(x+dx,y+dy,4,0,Math.PI*2);ctx.fill();ctx.fillText(label,x+dx+8,y+dy+4)}}
function render(){ctx.clearRect(0,0,W,H);const gradient=ctx.createRadialGradient(W*.5,H*.38,20,W*.5,H*.42,W*.72);gradient.addColorStop(0,"#fff");gradient.addColorStop(1,"#e8eef5");ctx.fillStyle=gradient;ctx.fillRect(0,0,W,H);const cam=camera(),project=projector(cam);drawRoom(project,cam);drawSolids(project,cam);drawAxis()}
function activate(name){state.active=name;document.querySelectorAll("[data-view]").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.view===name)));const labels={perspective:"透视视角",front:"正视图",left:"左视图",right:"右视图",top:"俯视图",reset:"透视视角"};status.textContent=labels[name]||"自由视角"}
function setView(name){if(name==="reset"||name==="perspective")Object.assign(state,defaults);if(name==="front")Object.assign(state,{yaw:-Math.PI/2,pitch:.04,distance:diagonal*1.72});if(name==="left")Object.assign(state,{yaw:Math.PI,pitch:.08,distance:diagonal*1.72});if(name==="right")Object.assign(state,{yaw:0,pitch:.08,distance:diagonal*1.72});if(name==="top")Object.assign(state,{yaw:-Math.PI/2,pitch:1.48,distance:diagonal*1.82});activate(name==="reset"?"perspective":name);render()}
canvas.addEventListener("pointerdown",e=>{state.dragging=true;state.lastX=e.clientX;state.lastY=e.clientY;canvas.setPointerCapture(e.pointerId);canvas.classList.add("dragging")});
canvas.addEventListener("pointermove",e=>{if(!state.dragging)return;const dx=e.clientX-state.lastX,dy=e.clientY-state.lastY;state.lastX=e.clientX;state.lastY=e.clientY;state.yaw-=dx*.008;state.pitch=clamp(state.pitch+dy*.006,-1.42,1.48);activate("free");status.textContent="自由视角";render()});
canvas.addEventListener("pointerup",e=>{state.dragging=false;canvas.releasePointerCapture(e.pointerId);canvas.classList.remove("dragging")});
canvas.addEventListener("pointercancel",()=>{state.dragging=false;canvas.classList.remove("dragging")});
canvas.addEventListener("wheel",e=>{e.preventDefault();state.distance=clamp(state.distance*Math.exp(e.deltaY*.001),diagonal*.72,diagonal*3.4);activate("free");status.textContent="自由视角";render()},{passive:false});
document.querySelectorAll("[data-view]").forEach(button=>button.addEventListener("click",()=>setView(button.dataset.view)));
window.addEventListener("keydown",e=>{if(e.key.toLowerCase()==="r")setView("reset")});
render();
})();
</script>
</body>
</html>
"""
````

## File: domain/skills/furniture-layout/scripts/furniture_layout/room_planning.py
````python
"""Room-aware furniture placement for the layout-planning checkpoint."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, isfinite, radians, sin
from typing import Any, Iterable, Mapping

from .layout_planning import CabinetLayout


WALLS = frozenset({"south", "east", "north", "west"})
PLACEMENT_MODES = frozenset({"wall", "free"})
EPSILON = 1e-6


def _number(data: Mapping[str, Any], *keys: str, default: float | None = None) -> float:
    for key in keys:
        if key in data and data[key] is not None:
            value = data[key]
            if isinstance(value, bool):
                raise ValueError(f"{key} must be numeric")
            try:
                return float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} must be numeric") from exc
    if default is not None:
        return float(default)
    raise ValueError(f"missing numeric field: {keys[0]}")


def _optional_number(data: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key in data and data[key] is not None:
            return _number(data, key)
    return None


def _text(data: Mapping[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        if key in data and data[key] is not None:
            return str(data[key]).strip()
    return default


@dataclass(frozen=True)
class RoomOpening:
    id: str
    kind: str
    wall: str
    offset_mm: float
    width_mm: float
    height_mm: float
    sill_height_mm: float = 0.0

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, index: int = 0) -> "RoomOpening":
        if not isinstance(data, Mapping):
            raise ValueError(f"room.openings[{index}] must be an object")
        return cls(
            id=_text(data, "id") or f"opening_{index + 1}",
            kind=(_text(data, "kind") or "opening").lower(),
            wall=_text(data, "wall", default="").lower(),
            offset_mm=_number(data, "offset_mm", "offset", default=0.0),
            width_mm=_number(data, "width_mm", "width"),
            height_mm=_number(data, "height_mm", "height"),
            sill_height_mm=_number(
                data,
                "sill_height_mm",
                "sill_height",
                default=0.0,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "wall": self.wall,
            "offset_mm": self.offset_mm,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "sill_height_mm": self.sill_height_mm,
        }


@dataclass(frozen=True)
class RoomObstacle:
    id: str
    kind: str
    x_mm: float
    y_mm: float
    z_mm: float
    width_mm: float
    depth_mm: float
    height_mm: float

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, index: int = 0) -> "RoomObstacle":
        if not isinstance(data, Mapping):
            raise ValueError(f"room.obstacles[{index}] must be an object")
        return cls(
            id=_text(data, "id") or f"obstacle_{index + 1}",
            kind=(_text(data, "kind") or "obstacle").lower(),
            x_mm=_number(data, "x_mm", "x", default=0.0),
            y_mm=_number(data, "y_mm", "y", default=0.0),
            z_mm=_number(data, "z_mm", "z", default=0.0),
            width_mm=_number(data, "width_mm", "width"),
            depth_mm=_number(data, "depth_mm", "depth"),
            height_mm=_number(data, "height_mm", "height"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
            "z_mm": self.z_mm,
            "width_mm": self.width_mm,
            "depth_mm": self.depth_mm,
            "height_mm": self.height_mm,
        }

    @property
    def footprint(self) -> tuple[tuple[float, float], ...]:
        return (
            (self.x_mm, self.y_mm),
            (self.x_mm + self.width_mm, self.y_mm),
            (self.x_mm + self.width_mm, self.y_mm + self.depth_mm),
            (self.x_mm, self.y_mm + self.depth_mm),
        )


@dataclass(frozen=True)
class RoomModel:
    id: str
    name: str
    width_mm: float
    depth_mm: float
    height_mm: float
    openings: tuple[RoomOpening, ...] = ()
    obstacles: tuple[RoomObstacle, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RoomModel":
        if not isinstance(data, Mapping):
            raise ValueError("room must be an object")
        raw_openings = data.get("openings", [])
        raw_obstacles = data.get("obstacles", [])
        if not isinstance(raw_openings, list):
            raise ValueError("room.openings must be a list")
        if not isinstance(raw_obstacles, list):
            raise ValueError("room.obstacles must be a list")
        return cls(
            id=_text(data, "id", "room_id") or "room",
            name=_text(data, "name") or "房间",
            width_mm=_number(data, "width_mm", "width"),
            depth_mm=_number(data, "depth_mm", "depth"),
            height_mm=_number(data, "height_mm", "height"),
            openings=tuple(
                RoomOpening.from_dict(item, index=index)
                for index, item in enumerate(raw_openings)
            ),
            obstacles=tuple(
                RoomObstacle.from_dict(item, index=index)
                for index, item in enumerate(raw_obstacles)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "width_mm": self.width_mm,
            "depth_mm": self.depth_mm,
            "height_mm": self.height_mm,
            "openings": [item.to_dict() for item in self.openings],
            "obstacles": [item.to_dict() for item in self.obstacles],
        }

    def wall_length(self, wall: str) -> float:
        return self.width_mm if wall in {"south", "north"} else self.depth_mm


@dataclass(frozen=True)
class PlacementRequest:
    mode: str
    host_wall: str | None
    offset_mm: float | None
    origin_x_mm: float | None
    origin_y_mm: float | None
    origin_z_mm: float
    rotation_z_deg: float | None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PlacementRequest":
        if not isinstance(data, Mapping):
            raise ValueError("placement must be an object")
        host_wall = _text(data, "host_wall", "wall", default="").lower() or None
        explicit_mode = _text(data, "mode", default="").lower()
        mode = explicit_mode or ("wall" if host_wall else "free")
        return cls(
            mode=mode,
            host_wall=host_wall,
            offset_mm=_optional_number(data, "offset_mm", "offset"),
            origin_x_mm=_optional_number(data, "origin_x_mm", "x_mm", "x"),
            origin_y_mm=_optional_number(data, "origin_y_mm", "y_mm", "y"),
            origin_z_mm=_number(
                data,
                "origin_z_mm",
                "elevation_mm",
                "z_mm",
                "z",
                default=0.0,
            ),
            rotation_z_deg=_optional_number(
                data,
                "rotation_z_deg",
                "rotation_deg",
                "rotation",
            ),
        )


@dataclass(frozen=True)
class ResolvedPlacement:
    mode: str
    host_wall: str | None
    offset_mm: float | None
    origin_x_mm: float
    origin_y_mm: float
    origin_z_mm: float
    rotation_z_deg: float

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ResolvedPlacement":
        return cls(
            mode=_text(data, "mode", default="free").lower(),
            host_wall=_text(data, "host_wall", default="").lower() or None,
            offset_mm=_optional_number(data, "offset_mm"),
            origin_x_mm=_number(data, "origin_x_mm"),
            origin_y_mm=_number(data, "origin_y_mm"),
            origin_z_mm=_number(data, "origin_z_mm", default=0.0),
            rotation_z_deg=_number(data, "rotation_z_deg", default=0.0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "host_wall": self.host_wall,
            "offset_mm": self.offset_mm,
            "origin_x_mm": self.origin_x_mm,
            "origin_y_mm": self.origin_y_mm,
            "origin_z_mm": self.origin_z_mm,
            "rotation_z_deg": self.rotation_z_deg,
        }


@dataclass(frozen=True)
class RoomPlacementPlan:
    furniture_label: str
    room: RoomModel
    placement: ResolvedPlacement
    furniture_footprint: tuple[tuple[float, float], ...]
    clearances_mm: dict[str, float]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RoomPlacementPlan":
        raw_footprint = data.get("furniture_footprint", [])
        if not isinstance(raw_footprint, list) or len(raw_footprint) != 4:
            raise ValueError("room_placement.furniture_footprint must contain 4 points")
        footprint: list[tuple[float, float]] = []
        for index, point in enumerate(raw_footprint):
            if not isinstance(point, Mapping):
                raise ValueError(
                    f"room_placement.furniture_footprint[{index}] must be an object"
                )
            footprint.append(
                (
                    _number(point, "x_mm"),
                    _number(point, "y_mm"),
                )
            )
        raw_clearances = data.get("clearances_mm", {})
        if not isinstance(raw_clearances, Mapping):
            raise ValueError("room_placement.clearances_mm must be an object")
        return cls(
            furniture_label=_text(
                data,
                "furniture_label",
                default="家具",
            ),
            room=RoomModel.from_dict(_mapping(data, "room")),
            placement=ResolvedPlacement.from_dict(_mapping(data, "placement")),
            furniture_footprint=tuple(footprint),
            clearances_mm={
                direction: _number(raw_clearances, direction)
                for direction in (
                    "west",
                    "east",
                    "south",
                    "north",
                    "floor",
                    "ceiling",
                )
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "furniture_label": self.furniture_label,
            "room": self.room.to_dict(),
            "placement": self.placement.to_dict(),
            "furniture_footprint": [
                {"x_mm": x, "y_mm": y} for x, y in self.furniture_footprint
            ],
            "clearances_mm": dict(self.clearances_mm),
        }


def _mapping(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be an object")
    return value


def resolve_placement(
    room: RoomModel,
    request: PlacementRequest,
) -> ResolvedPlacement:
    """Resolve wall-relative or free placement to a room-space transform."""
    if request.mode not in PLACEMENT_MODES:
        raise ValueError(
            "placement.mode must be one of: " + ", ".join(sorted(PLACEMENT_MODES))
        )
    if request.mode == "free":
        if request.origin_x_mm is None or request.origin_y_mm is None:
            raise ValueError(
                "free placement requires origin_x_mm and origin_y_mm"
            )
        if request.host_wall is not None or request.offset_mm is not None:
            raise ValueError(
                "free placement cannot define host_wall or offset_mm"
            )
        return ResolvedPlacement(
            mode="free",
            host_wall=None,
            offset_mm=None,
            origin_x_mm=request.origin_x_mm,
            origin_y_mm=request.origin_y_mm,
            origin_z_mm=request.origin_z_mm,
            rotation_z_deg=request.rotation_z_deg or 0.0,
        )

    wall = request.host_wall
    if wall not in WALLS:
        raise ValueError(
            "wall placement requires host_wall: "
            + ", ".join(sorted(WALLS))
        )
    if request.origin_x_mm is not None or request.origin_y_mm is not None:
        raise ValueError(
            "wall placement derives its origin; use offset_mm instead of x/y"
        )
    expected_rotation = {
        "south": 180.0,
        "east": 90.0,
        "north": 0.0,
        "west": 270.0,
    }[wall]
    if (
        request.rotation_z_deg is not None
        and abs((request.rotation_z_deg - expected_rotation) % 360.0) > EPSILON
    ):
        raise ValueError(
            f"wall placement rotation is derived as {expected_rotation:g} degrees"
        )
    offset = request.offset_mm or 0.0
    origin = {
        "north": (offset, 0.0),
        "east": (room.width_mm, offset),
        "south": (room.width_mm - offset, room.depth_mm),
        "west": (0.0, room.depth_mm - offset),
    }[wall]
    return ResolvedPlacement(
        mode="wall",
        host_wall=wall,
        offset_mm=offset,
        origin_x_mm=origin[0],
        origin_y_mm=origin[1],
        origin_z_mm=request.origin_z_mm,
        rotation_z_deg=expected_rotation,
    )


def furniture_footprint(
    layout: CabinetLayout,
    placement: ResolvedPlacement,
) -> tuple[tuple[float, float], ...]:
    angle = radians(placement.rotation_z_deg)
    cos_angle = cos(angle)
    sin_angle = sin(angle)

    def transform(x: float, y: float) -> tuple[float, float]:
        world_x = placement.origin_x_mm + x * cos_angle - y * sin_angle
        world_y = placement.origin_y_mm + x * sin_angle + y * cos_angle
        return (_clean(world_x), _clean(world_y))

    return tuple(
        transform(x, y)
        for x, y in (
            (0.0, 0.0),
            (layout.width, 0.0),
            (layout.width, layout.depth),
            (0.0, layout.depth),
        )
    )


def build_room_placement(
    layout: CabinetLayout,
    room: RoomModel,
    placement: ResolvedPlacement,
    *,
    furniture_label: str,
) -> RoomPlacementPlan:
    footprint = furniture_footprint(layout, placement)
    xs = [point[0] for point in footprint]
    ys = [point[1] for point in footprint]
    return RoomPlacementPlan(
        furniture_label=furniture_label or layout.furniture_type,
        room=room,
        placement=placement,
        furniture_footprint=footprint,
        clearances_mm={
            "west": _clean(min(xs)),
            "east": _clean(room.width_mm - max(xs)),
            "south": _clean(room.depth_mm - max(ys)),
            "north": _clean(min(ys)),
            "floor": _clean(placement.origin_z_mm),
            "ceiling": _clean(
                room.height_mm - placement.origin_z_mm - layout.height
            ),
        },
    )


def plan_room_placement(
    layout: CabinetLayout,
    room_data: Mapping[str, Any],
    placement_data: Mapping[str, Any],
    *,
    furniture_label: str,
) -> RoomPlacementPlan:
    room = RoomModel.from_dict(room_data)
    if not all(
        isfinite(value) and value > 0
        for value in (room.width_mm, room.depth_mm, room.height_mm)
    ):
        raise ValueError("room width, depth, and height must be positive finite numbers")
    placement = resolve_placement(room, PlacementRequest.from_dict(placement_data))
    if not all(
        isfinite(value)
        for value in (
            placement.origin_x_mm,
            placement.origin_y_mm,
            placement.origin_z_mm,
            placement.rotation_z_deg,
        )
    ):
        raise ValueError("placement transform values must be finite")
    return build_room_placement(
        layout,
        room,
        placement,
        furniture_label=furniture_label,
    )


def obstacle_collisions(
    plan: RoomPlacementPlan,
    layout: CabinetLayout,
) -> tuple[RoomObstacle, ...]:
    furniture_z_start = plan.placement.origin_z_mm
    furniture_z_end = furniture_z_start + layout.height
    collisions: list[RoomObstacle] = []
    for obstacle in plan.room.obstacles:
        vertical_overlap = _ranges_overlap(
            furniture_z_start,
            furniture_z_end,
            obstacle.z_mm,
            obstacle.z_mm + obstacle.height_mm,
        )
        if vertical_overlap and polygons_overlap(
            plan.furniture_footprint,
            obstacle.footprint,
        ):
            collisions.append(obstacle)
    return tuple(collisions)


def opening_collisions(
    plan: RoomPlacementPlan,
    layout: CabinetLayout,
) -> tuple[RoomOpening, ...]:
    furniture_z_start = plan.placement.origin_z_mm
    furniture_z_end = furniture_z_start + layout.height
    collisions: list[RoomOpening] = []
    for opening in plan.room.openings:
        furniture_span = _footprint_span_on_wall(plan, opening.wall)
        if furniture_span is None:
            continue
        furniture_start, furniture_end = furniture_span
        if _ranges_overlap(
            furniture_start,
            furniture_end,
            opening.offset_mm,
            opening.offset_mm + opening.width_mm,
        ) and _ranges_overlap(
            furniture_z_start,
            furniture_z_end,
            opening.sill_height_mm,
            opening.sill_height_mm + opening.height_mm,
        ):
            collisions.append(opening)
    return tuple(collisions)


def _footprint_span_on_wall(
    plan: RoomPlacementPlan,
    wall: str,
) -> tuple[float, float] | None:
    xs = [point[0] for point in plan.furniture_footprint]
    ys = [point[1] for point in plan.furniture_footprint]
    if wall == "north" and min(ys) <= EPSILON:
        return (min(xs), max(xs))
    if wall == "east" and max(xs) >= plan.room.width_mm - EPSILON:
        return (min(ys), max(ys))
    if wall == "south" and max(ys) >= plan.room.depth_mm - EPSILON:
        return (
            plan.room.width_mm - max(xs),
            plan.room.width_mm - min(xs),
        )
    if wall == "west" and min(xs) <= EPSILON:
        return (
            plan.room.depth_mm - max(ys),
            plan.room.depth_mm - min(ys),
        )
    return None


def polygons_overlap(
    first: Iterable[tuple[float, float]],
    second: Iterable[tuple[float, float]],
) -> bool:
    """Return True for positive-area overlap; touching edges are allowed."""
    polygon_a = tuple(first)
    polygon_b = tuple(second)
    for polygon in (polygon_a, polygon_b):
        for index, point in enumerate(polygon):
            next_point = polygon[(index + 1) % len(polygon)]
            edge = (next_point[0] - point[0], next_point[1] - point[1])
            axis = (-edge[1], edge[0])
            projection_a = [
                candidate[0] * axis[0] + candidate[1] * axis[1]
                for candidate in polygon_a
            ]
            projection_b = [
                candidate[0] * axis[0] + candidate[1] * axis[1]
                for candidate in polygon_b
            ]
            if (
                max(projection_a) <= min(projection_b) + EPSILON
                or max(projection_b) <= min(projection_a) + EPSILON
            ):
                return False
    return True


def _ranges_overlap(
    first_start: float,
    first_end: float,
    second_start: float,
    second_end: float,
) -> bool:
    return min(first_end, second_end) > max(first_start, second_start) + EPSILON


def _clean(value: float) -> float:
    return 0.0 if abs(value) < EPSILON else round(value, 6)
````

## File: domain/skills/furniture-manufacturing/agents/openai.yaml
````yaml
interface:
  display_name: "家具制造策略"
  short_description: "规划材料、封边、连接、孔位和 BOM"
  default_prompt: "使用 $furniture-manufacturing 规划已确认板件的制造策略。"
````

## File: domain/skills/furniture-manufacturing/references/coordinate-naming.md
````markdown
# 坐标命名约定

回答"一个坐标量属于谁、相对谁"的命名规范。这是跨阶段的全局约定
（制造阶段为主，板件规划/布局/CAD/交付验证消费），用于消除 `global`/`local`
这类词在"柜体 vs 世界"上的歧义。

## 三层坐标（参考系）

| 层 | 参考系（原点） | 说明 |
|----|---------------|------|
| 板件 panel | 板件左后下角 | 制造/加工的天然参考 |
| 柜体 cabinet | 柜体左后下角 | 装配对齐的参考 |
| 世界 world | 房间/世界原点 | 房间级渲染/碰撞 |

相邻层的位置是**原生存储**，隔层的绝对位置是**派生现算**：
`world = cabinet_world ∘ panel_cabinet ∘ hole`。

## 命名规则：`对象_参考系_轴`

- 用**参考系实体名**做第二段（panel/cabinet/world），而不是 global/local；
- 相邻层**省参考系**，隔层**必须写参考系**；
- 实体位置一律指其**原点**。

## 命名表

| 量 | 命名 | 存储 | 说明 |
|----|------|------|------|
| 孔相对板件 | `hole_x` / `hole_y` / `hole_z` | ✅ 存 | 相邻层，省参考系（孔天然在板件上） |
| 孔相对柜体 | `hole_cabinet_x` / … | ✅ 存 | 装配对齐用 |
| 板件相对柜体 | `panel_cabinet_x` / … | ✅ 存 | 约定 = 板件**原点**在柜体坐标 |
| 板件相对世界 | `panel_world_x` / … | ❌ 派生 | `= cabinet_world ∘ panel_cabinet` |
| 柜体相对世界 | `cabinet_world_x` / … | ✅ 存 | layout 摆放 |

## 三条规则

1. **相邻层省前缀**：`hole_x` 不必写 `hole_panel_x`——孔天然在板件上。
2. **隔层写参考系**：`hole_cabinet_x` 必须写 `cabinet`，否则无法与 `hole_x` 区分。
3. **实体位置加 origin 约定**：`panel_cabinet_x` 指板件**原点**（左后下角），
   不指中心或包围盒；如需其它点须显式命名（如 `panel_center_cabinet_x`）。

## 圆心与方向约定

- **`hole_*` 是圆心，不是"孔原点"**：孔是圆柱体，其位置 = **入口面圆心**
  （钻头进入的那一面的圆心），不是几何中心、不是孔底。
- **`direction` 统一为"钻入深入方向（往板内）"**：从约定入口面指向板内。
  入口面由 `is_face_hole` + 语义面（inner/cam/端面）确定；通孔入口面由工艺规则指定。
  （✅ 已统一：铰链杯孔/偏心轮孔存钻入方向 = 语义面反向；螺母/杆/背板/层板本就是钻入方向。）

## 现状 → 目标映射

| 现字段（有误导） | 目标字段 | 参考系 |
|-----------------|---------|--------|
| `x_local/y_local/z_local` | `hole_x/hole_y/hole_z` | 板件 |
| `x_global/y_global/z_global` | `hole_cabinet_x/…` | 柜体 |
| `pos_x/pos_y/pos_z` | `panel_cabinet_x/…` | 柜体（板件原点） |
| （无字段，现算） | `panel_world_x/…` | 世界（派生） |
| layout 摆放 origin | `cabinet_world_x/…` | 世界 |

**`global` 一词废弃**：旧代码里 `x_global` 实为"柜体坐标"，新命名一律用
`cabinet` 表柜体、`world` 表世界，不再使用 `global`。

## 迁移策略

- **搭车改，不单独改**：纯重构零功能收益，不为此单独动字段。
- 搭车时机（满足任一即顺带改）：
  1. P3 完整局部坐标化（三合一/背板也"局部为真源"时，赋值代码本就重写）；
  2. `direction` 语义统一（面朝向 → 钻入方向）；
  3. 2.5D 内核替换（`to_global` 变成含旋转的真变换时，world 才有实际载体）。
- 动手前必须先定**改到哪个层级**：
  Python 字段名 / `drilled-holes.json` 的 key / 跨阶段字段（cabinet_world），
  三者成本与波及面不同。
````

## File: domain/skills/furniture-manufacturing/references/drawer-component-design.md
````markdown
# 抽屉组件级实体需求（记录）

状态：**首版已实施（20260822，整高抽屉区 + 无面板 + 三节轨）**；
完整抽屉组件（门+抽屉混合区、托底轨、有面板）仍为待评审需求。
来源：2026-08 抽屉滑轨 Connector 化（档 A）与抽屉组件（档 B）讨论。

## 背景

抽屉本质是**子装配组件**，不是散板：

- 有自己的板件集合（前板/左右侧板/后板/底板，可选抽屉面板）、盒体拓扑、五金（滑轨、拉手）；
- 尺寸链只有作为组件才自然：抽屉宽 = 柜体开口宽 − 2×滑轨安装余量 − 公差；抽屉深 = 柜体深 − 背板 − 前间隙；抽屉高 = 可用高 ÷ 层数 − 层间间距；
- 滑轨长度由抽屉**自身深度**决定、承重由抽屉宽度决定——因此不能从柜体面板"猜"；
- 完整抽屉构成：左侧板、右侧板、前板、后板、底板 + 可选抽屉面板。

## 两个正交变体轴（数据化，不建类层次）

| 轴 | 取值 | 影响 |
|----|------|------|
| 滑轨类型 | 三节轨（侧装）/ 托底轨（底装） | 让位间隙（13.0 / 12.7）、侧板高度、前板高度关系 |
| 前脸形态 | 无面板 / 有面板 | 是否额外生成抽屉面板及其安装方式（组装现场工艺） |

变体差异是"数值+布尔"，放 profile 数据；**首版只落地一个组合**（三节轨 + 无面板），
加变体 = 加数据不改代码。

## 现状（20260822 档 A + 档 B 首版后）

- ✅ 档 A：`DrawerSlideConnector` 按契约出滑轨 BOM，`manufacturing_hardware.py` 死代码已删除；
- ✅ 档 B 首版：`FurnitureSpec.drawer_count` 走板件提案确定性准入，layout 不感知；
  `floor_cabinet.yaml` 声明 `internals.drawers` 整高抽屉拓扑；`topology_solver._drawer_panels`
  生成 5 板/抽屉（前/左/右/后/底）；整高抽屉与门/层板冲突在准入前拒绝，不再静默忽略；封边规则补齐；
  layout 死字段 `drawer_count` 的测试样例已换名（drawer_count 现在是合法面板输入，不再适合当"未知字段"例子）；
- ✅ 抽屉几何净空的单一真源 = 已确认 `FurnitureSpec.drawer_side_clearance`；
  `hardware_catalog.yaml` 的 `gap_requirement_mm` 属于制造阶段候选五金规格，必须与已确认净空兼容，板件规划不再跨阶段读取制造目录。

## 契约（板件规划已遵守，滑轨 Connector 自动生效）

1. **panel_type 命名**：抽屉板件 `panel_type` 含 `"drawer"`（`drawer_front` / `drawer_side` / `drawer_back` / `drawer_bottom`）。
2. **尺寸来源**：抽屉深度 = 抽屉板件 `size_y` 最大值（侧板携带），宽度 = `size_x` 最大值（前板携带）——取自抽屉板件自身。
3. **实例粒度**：抽屉板件 `label` = `drawer_<角色>_<实例后缀>`，实例 key = label 最后一个 `"_"` 分段（如 `drawer_front_z68` → `z68`）；数量 = 每抽 1 副（左右各 1）× 抽屉实例数。
4. **连接方式**：抽屉盒**默认三合一**（全屋定制主流做法；木销+胶为少数）。已确认方案（20260822 实施，值待投产确认）：
   - **底板 ↔ 侧板**（x 轴，2 侧）：male=底板，cam_face=`-z`（偏心轮在**底板下面**，抽屉外部操作）；female=侧板（预埋螺母）。
   - **底板前端 ↔ 前板 / 底板后端 ↔ 背板**（y 轴）：male=底板（cam 仍在 `-z`）；female=前板/背板。
   - **前板 ↔ 侧板**（y 轴）：无面板时前板比侧板宽 → female=**前板**，male=**侧板**（杆+轮），cam_face=`±x`（侧板**外侧面**，抽屉外部操作）。
   - **背板 ↔ 侧板**（x 轴）：背板在侧板之间 → female=**侧板**，male=**背板**，cam_face=`-y`（背板**外侧面**，抽屉外部操作）。
   - 实现：`TrinityConnector` 已泛化为**连接驱动、轴无关**（边轴 x/y、cam 面任意宽面、连接排沿第三轴）；抽屉子装配内部 x/y 轴接触均为连接，柜体仅 x 轴（背板 y 向接触不是连接）；同时修正柜体层板连接"螺母/杆前排错位 27mm"（螺母按 male 跨度对齐）。
   - 每个抽屉 8 个连接 × 2 排 = 16 套三合一（4 底板 + 2 背板 + 2 侧板前连接）。

## 首版尺寸链（`_drawer_panels`，值待投产确认）

- 每层净高 `band_h` = 内部净高 ÷ `drawer_count`；
- 前板：高 = `band_h − drawer_layer_gap`；宽 = 内部宽 − 2×`door_margin`；厚 = 已确认柜体板厚；
- 盒体宽 = 内部宽 − 2×`drawer_side_clearance`；
- 盒体深 = 内部深 − 前板厚 − `drawer_back_clearance`（须 ≥0）；
- 盒体高 = 前板高 − 2×`front_overlap`；
- `front_overlap` 按抽屉位置派生：**底抽 18（全盖底板）；顶/中间 0**；
  将来门+抽屉混合区按上方构造推导：**共盖层板 9 / 顶板盖 0**；
- 抽屉板厚：分别使用已准入的 `drawer_bottom_thickness/drawer_back_thickness`。

## 需求（待评审）

1. **抽屉组件物化完善**（板件规划阶段）：完整抽屉子拓扑 + 尺寸链 + 装配偏移。
2. **门+抽屉混合区**（底部抽屉区 + 上部开门）：开口分区、门高↔铰链联动、抽屉前板与门对位。
3. **变体落地**：托底轨 profile（让位 12.7、底装结构）、有面板（覆盖/内嵌安装，组装现场工艺）。
4. **Layout `drawer_count`**：保持不感知（面板阶段 options 路径）；如未来需要布局级抽屉分区再启用。
5. **校验**：滑轨长度 ≤ 抽屉深度 − 50mm；安装余量不超开口。

## 实施建议

- 首版已按"正交参数 + profile"实现，变体只加数据不改代码；
- 与 `connection-point-design.md` 同属"组件/实体层"演进：系统需要"柜体之下、板件之上"的中间实体层，届时所有 Connector 的输入形态统一适配（面板 → 面板+组件）。

## 关联

- 连接点级实体需求：`references/connection-point-design.md`
- 五金参数位置：`SKILL.md`（`hardware_catalog.yaml` 的 `drawer_slides` 段）
````

## File: domain/skills/furniture-manufacturing/references/hardware-machining-reference.md
````markdown
# 五金与加工参照资料

> ⚠️ **存档资料，暂不纳入当前计划。**
> 仅在对话中明确提到「对照外部五金/加工类目」时，才读取本资料并启动对照工作。

来源：`D:\Program Files\guigui3`（柜柜 5.0.0.4）。

## 一、五金/连接件全集（`caches\libraries\tdat\connector\`，51 个 .jd）

| 类别 | 连接件 |
|------|--------|
| 三合一 | TrinityConnector、TrinityWithDowel(+Helper)、CCompConnector、CustomConnector、CustomConnectorComponent、CustomConnectorImpl、CustomConnectorComponentGenerator、CustomConnectorLayout |
| 铰链 | DefaultHinge、CCompHinge、Hinge、HingeHelper、FrameDoorHinge、NoneHinge |
| 二合一 | Con2In1Lock、Invisible2In1(+Helper) |
| 隐藏连接件 | QRInvisible、MDYInvisible、HKInvisible、LKInvisible、GuiRenYiInvisible、InvisiblePartV2(Style1/2 + Helper) |
| 木榫 | Dowel |
| 滑轨 | Slide、SlideHelper、KJLSliderHole |
| 拉米诺 Lamello | LamelloParts、LamelloPartsStyle1~5、LamelloPartsHelper |
| 钉 | Nail、PlateNail、GlassLaminateNail |
| 槽/孔生成 | ConSlot、SlotGenerator、HoleGenerator、ConHandleSideSlot |
| 锁孔 | DrawerLockHole、DoorLockHole、LockHole、LockHolePrivate、LockHoleHelper |

## 二、生产/组件对象全集（`caches\libraries\tdat\production\`，27 个 .jd）

- 柜体：PanelProduction、PlankProduction、SingleDoorProduction、SlideDoorProduction、DrawerProduction、SlideProduction
- 功能五金：HandleProduction、FreeHandleProduction、FootPlateProduction(踢脚板)、ClothesHookProduction(挂衣钩)、HangerProduction(挂衣架)、PantsRackProduction(裤架)、PierGlassProduction(穿衣镜)、RebounderProduction(反弹器)、RomaProduction(罗马柱)、RailingProduction(栏杆)、WLineBottomProduction、WtopLineProduction(顶/底线)
- 玻璃/定制：GlassProduction、GlassLaminateProduction、CustomHardwareProduction、CircularCornerProduction(圆角)、CCompProduction、MatPanelProduction

## 三、加工语义词汇表（`caches\clients\BFZ\technology\MachineDictionary.json`）

外部拆单软件用「位置 + 动作 + 条件」描述加工，词汇如下：

- **位置类**：`margin_back`(距后)、`margin_front`(距前)、`margin_up`(距上)、`margin_down`(距下)、`margin_left`(距左)、`margin_right`(距右)、`margin_side`(距边=距前或后)、`spacing`(间隔)、`move_front/back/up/down/left/right`(向前/后/上/下/左/右运动)
- **动作类**：`length_slot`(拉槽长)、`depth_hole`(打孔深)、`knife_change`(换刀)、`knife_lift`(提刀)、`count`(放一个)
- **条件类**：`depth_lessThan`(深度<)、`depth_greaterThan`(深度>)

## 四、形状定义格式（`caches\clients\BFZ\materials\shapes\*.js`）

JSON 顶点轮廓：`{b, x, y}` 描述 2D 轮廓（`b` 为贝塞尔/圆弧标志），`props` 存尺寸参数，`vertex`/`extras` 存主轮廓与凹槽轮廓。是截面造型，非打孔逻辑。

## 五、报告模板字段（`base\reports\打印标签.xml`）

客户、订单、板件、房间、板号、材质、成品尺寸、**侧孔信息**，带条形码。

## 六、无法读取的部分

`.jd` 文件为二进制（read 报 binary file，hex 查看受沙箱限制），核心打孔生成逻辑（孔位/直径/深度/配合关系）在 .jd 内，无法直接读取。

## 启动条件

仅在明确提到「对照外部五金/加工类目」时启动，读取本资料并开展五金类目/打孔规则的对照工作。
````

## File: domain/skills/furniture-manufacturing/references/six-side-drill-export.md
````markdown
# 六面钻 XML 导出（KDTPanelFormat）

回答"如何把已确认孔位导出给柜柜六面钻机床加工"。本子流程仅在用户明确要求出六面钻/机床加工文件时读取，不进入制造方案主流程。

## 契约

- 由 `scripts/furniture_manufacturing/export_six_side_drill.py` + `devices/six_side_drill_guigui.yaml` 完成。
- 从 `drilled-holes.json` 反推板件和孔位，逐板生成 `KDTPanelFormat` XML。
- 槽位尚无设备侧数据契约；输入包含槽位时明确拒绝，避免静默漏加工。

## 坐标与设备映射

- 机床坐标 X=PanelLength, Y=PanelWidth, Z=PanelThickness。
- 设备映射 yaml 按面板类型定义 `sixd_x_from_box`/`sixd_y_from_box`（机床轴）和 `x1_from_hole`/`y1_from_hole`/`z1_from_hole`（局部坐标→机床坐标）。
- 水平孔方向须从世界轴转换为机床轴后再确定 Quadrant。
- 导出层从 `HoleSpec.is_face_hole` 直接读取 TypeNo，不再从世界坐标推导：`True` → TypeNo=1 垂直孔，`False` → TypeNo=2 水平孔。

## 板件轮廓

- `PanelOutline` 顶点严格按 `(0, sixd_y) → (0, 0) → (sixd_x, 0) → (sixd_x, sixd_y)` 逆时针闭合。

## 关联

- 孔位数据源：`manufacturing_bom.py` 的 `emit_drilled_holes()` 把结构化 `panel_type` 写入 `drilled-holes.json` 每块板。
- 产物登记：CAD 阶段 `workflow_artifact_writer.py` 调用 `drill_json_to_xml_files()` 写 `六面钻文件/<panel>.xml`，并登记为 manifest `six_side_drill_xml`。
````

## File: domain/skills/furniture-manufacturing/scripts/furniture_manufacturing/devices/six_side_drill_guigui.yaml
````yaml
# 六面钻设备配置 — 柜柜 guigui3 兼容格式
# 六面钻坐标: 机床 X轴 = PanelLength, Y轴 = PanelWidth, Z轴 = PanelThickness
# 柜柜 Params 恒等规则: Params.L ≡ PanelWidth(Y), Params.W ≡ PanelLength(X)

panel_placement:
  side:           # 侧板/立板/隔板/踢脚支撑 — 板面 Y-Z (板厚方向=X)
    sixd_x_from_box: y    # PanelLength (机床X轴) ← box.y (深度), 孔在深度方向的位置
    sixd_y_from_box: z    # PanelWidth  (机床Y轴) ← box.z (高度), 孔在高度方向的位置
    x1_from_hole: local_y
    y1_from_hole: local_z
    z1_from_hole: local_x
  door:           # 门板 — 板面 X-Z (板厚方向=Y)
    sixd_x_from_box: z    # PanelLength (机床X轴) ← box.z (门高 = 高度方向)
    sixd_y_from_box: x    # PanelWidth  (机床Y轴) ← box.x (门宽 = 宽度方向)
    x1_from_hole: local_z
    y1_from_hole: local_x
    z1_from_hole: local_y
  horizontal:     # 顶板/底板/层板 — 板面 X-Y (板厚方向=Z)
    sixd_x_from_box: y    # PanelLength (机床X轴) ← box.y (深度方向)
    sixd_y_from_box: x    # PanelWidth  (机床Y轴) ← box.x (宽度方向)
    x1_from_hole: local_y
    y1_from_hole: local_x
    z1_from_hole: local_z
  toe_kick:       # 踢脚板 — 板面 X-Z (板厚方向=Y)
    sixd_x_from_box: x    # PanelLength (机床X轴) ← box.x (宽度方向)
    sixd_y_from_box: z    # PanelWidth  (机床Y轴) ← box.z (高度方向)
    x1_from_hole: local_x
    y1_from_hole: local_z
    z1_from_hole: local_y
  default:        # 背板/背拉条等 — 板面 X-Z (板厚方向=Y)
    sixd_x_from_box: x
    sixd_y_from_box: z
    x1_from_hole: local_x
    y1_from_hole: local_z
    z1_from_hole: local_y
````

## File: domain/skills/furniture-manufacturing/scripts/furniture_manufacturing/__init__.py
````python
"""Manufacturing-planning stage runtime."""
````

## File: domain/skills/furniture-manufacturing/scripts/furniture_manufacturing/export_six_side_drill.py
````python
"""导出柜柜六面钻 XML 文件（KDTPanelFormat）。

从 drilled-holes JSON 反推板件上的孔位，
生成与 guigui3 兼容的六面钻加工文件。

槽位尚无设备侧数据契约；输入包含槽位时明确拒绝，避免静默漏加工。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from xml.dom import minidom
from xml.etree import ElementTree as ET


# ---------------------------------------------------------------------------
# 设备配置
# ---------------------------------------------------------------------------

def _load_device_config() -> dict[str, Any]:
    """加载 six_side_drill_guigui.yaml 中的 panel_placement 映射。"""
    p = Path(__file__).resolve().parent / "devices" / "six_side_drill_guigui.yaml"
    with open(p, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg.get("panel_placement", {})


def _resolve_placement(
    panel_type: str,
) -> dict[str, str]:
    """根据 panel_type 返回对应的 placement 规则。

    未匹配到具体类型时回退到 default。
    """
    placement = _load_device_config()
    if panel_type in ("divider",):
        panel_type = "side"
    if panel_type in ("top", "bottom", "fixed_shelf", "movable_shelf"):
        panel_type = "horizontal"
    return placement.get(panel_type, placement.get("default", {}))


def _box_value(box: dict[str, Any], key: str) -> float:
    return float(box.get(key, 0))


def _hole_value(hole: dict[str, Any], local_key: str) -> float:
    """Read a required panel-local hole coordinate."""
    if local_key not in hole:
        raise ValueError(f"hole is missing required coordinate {local_key!r}")
    return float(hole[local_key])


def _localize_holes(
    holes: list[dict[str, Any]],
    box: dict[str, Any],
) -> list[dict[str, Any]]:
    """Fill missing local coordinates from global coordinates and panel origin."""
    localized: list[dict[str, Any]] = []
    for hole in holes:
        item = dict(hole)
        for axis in ("x", "y", "z"):
            local_key = f"local_{axis}"
            if local_key in item:
                continue
            if axis not in item:
                raise ValueError(
                    f"hole is missing both {local_key!r} and global {axis!r}"
                )
            item[local_key] = float(item[axis]) - float(
                box.get(f"pos_{axis}", 0)
            )
        localized.append(item)
    return localized


def _machine_axes(placement: dict[str, str]) -> tuple[str, str, str]:
    """Resolve and validate the box axes mapped to machine X/Y/Z."""
    sixd_x_axis = placement.get("sixd_x_from_box", "x")
    sixd_y_axis = placement.get("sixd_y_from_box", "z")
    valid_axes = {"x", "y", "z"}
    if sixd_x_axis not in valid_axes or sixd_y_axis not in valid_axes:
        raise ValueError("six-side drill placement uses an unknown box axis")
    if sixd_x_axis == sixd_y_axis:
        raise ValueError("six-side drill X/Y axes must use different box axes")
    sixd_z_axis = (valid_axes - {sixd_x_axis, sixd_y_axis}).pop()
    return sixd_x_axis, sixd_y_axis, sixd_z_axis


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def drill_json_to_xml_files(
    json_path: str | Path,
    output_dir: str | Path,
) -> list[Path]:
    """读取 drilled-holes JSON 并逐板件导出六面钻 XML。

    参数:
        json_path: drilled-holes.json 路径
        output_dir: 输出目录

    返回:
        生成的 XML 文件路径列表
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    paths: list[Path] = []
    for panel in data.get("panels", []):
        panel_name = panel.get("name", panel.get("label", "unknown"))
        plank_num = panel.get("label", "unknown")

        # 板件尺寸 (从 box 获取)
        box = panel.get("box", {})

        # 类型推断
        panel_type = _infer_panel_type(panel)

        # 设备配置映射
        placement = _resolve_placement(panel_type)

        # 六面钻坐标: 根据 panel_type 从 box 的三轴映射到机床 X/Y/Z 轴
        sixd_x_axis, sixd_y_axis, sixd_z_axis = _machine_axes(placement)
        sixd_x = _box_value(box, sixd_x_axis)
        sixd_y = _box_value(box, sixd_y_axis)
        sixd_z = _box_value(box, sixd_z_axis)
        if min(sixd_x, sixd_y, sixd_z) <= 0:
            raise ValueError(
                f"panel {plank_num!r} has non-positive six-side drill dimensions"
            )

        # 机床 X/Y/Z 局部坐标映射键
        x1_key = placement.get("x1_from_hole", "local_x")
        y1_key = placement.get("y1_from_hole", "local_y")
        z1_key = placement.get("z1_from_hole", f"local_{sixd_z_axis}")

        panel_xml = _make_panel_xml(
            name=panel_name,
            sixd_x=sixd_x,
            sixd_y=sixd_y,
            sixd_z=sixd_z,
            holes=_localize_holes(panel.get("holes", []), box),
            slots=panel.get("slots", []),
            x1_key=x1_key,
            y1_key=y1_key,
            z1_key=z1_key,
            machine_x_axis=sixd_x_axis,
            machine_y_axis=sixd_y_axis,
        )

        file_path = out_dir / f"{plank_num}.xml"
        file_path.write_text(panel_xml, encoding="utf-8")
        paths.append(file_path)

    return paths


# ---------------------------------------------------------------------------
# 面板类型推断
# ---------------------------------------------------------------------------

def _infer_panel_type(panel: dict[str, Any]) -> str:
    """从 panel name/label 推断面板类型。"""
    panel_type = panel.get("panel_type", "")
    if panel_type:
        return panel_type
    name = panel.get("name", "").lower()
    if "侧板" in name or "立板" in name or "隔板" in name:
        return "side"
    elif "顶板" in name:
        return "top"
    elif "底板" in name:
        return "bottom"
    elif "层板" in name:
        return "fixed_shelf"
    elif "门板" in name or "门" in name:
        return "door"
    elif "背板" in name:
        return "back"
    elif "踢脚" in name and "支撑" in name:
        return "side"
    elif "踢脚" in name:
        return "toe_kick"
    elif "拉条" in name:
        return "back_rail"
    return "default"


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _machine_direction(
    direction: str,
    machine_x_axis: str,
    machine_y_axis: str,
) -> str:
    """Transform a signed world direction into the panel's machine X/Y axes."""
    if len(direction) != 2 or direction[0] not in "+-":
        raise ValueError(f"invalid hole direction: {direction!r}")
    sign, world_axis = direction
    if world_axis == machine_x_axis:
        return f"{sign}x"
    if world_axis == machine_y_axis:
        return f"{sign}y"
    raise ValueError(
        f"edge-hole direction {direction!r} points through panel thickness"
    )


def _quadrant(machine_direction: str) -> str:
    """根据机床方向返回柜柜 Quadrant（1-4）。"""
    quadrants = {"+x": "1", "-x": "2", "+y": "3", "-y": "4"}
    try:
        return quadrants[machine_direction]
    except KeyError as exc:
        raise ValueError(
            f"unsupported machine hole direction: {machine_direction!r}"
        ) from exc


def _flush_xml(text: str) -> str:
    """移除 XML 声明行，与柜柜输出格式一致。"""
    lines = text.splitlines(keepends=True)
    if lines and lines[0].startswith("<?xml"):
        return "".join(lines[1:])
    return text


# ---------------------------------------------------------------------------
# XML 构造
# ---------------------------------------------------------------------------

def _make_panel_xml(
    name: str,
    sixd_x: float,
    sixd_y: float,
    sixd_z: float,
    holes: list[dict[str, Any]],
    slots: list[dict[str, Any]],
    x1_key: str,
    y1_key: str,
    z1_key: str,
    machine_x_axis: str,
    machine_y_axis: str,
) -> str:
    """构造一块板件的 KDTPanelFormat XML 字符串。

    sixd_x = PanelLength（机床 X 轴方向尺寸）
    sixd_y = PanelWidth （机床 Y 轴方向尺寸）
    sixd_z = PanelThickness（板厚，机床 Z 轴）
    x1_key / y1_key / z1_key = 从 hole dict 取机床 X/Y/Z 坐标的 key
    """
    root = ET.Element("KDTPanelFormat")

    panel_elem = ET.SubElement(root, "PANEL")
    _add_text(panel_elem, "PanelLength", str(sixd_x))
    _add_text(panel_elem, "PanelWidth", str(sixd_y))
    _add_text(panel_elem, "PanelThickness", str(sixd_z))
    _add_text(panel_elem, "PanelName", name)

    # 柜柜 Params: L/W 与 PanelLength/PanelWidth 交换
    # L(板长) = PanelWidth(sixd_y), W(板宽) = PanelLength(sixd_x)
    params = ET.SubElement(panel_elem, "Params")
    ET.SubElement(params, "Param", Key="L", Value=str(sixd_y), Comment="板长")
    ET.SubElement(params, "Param", Key="W", Value=str(sixd_x), Comment="板宽")
    ET.SubElement(params, "Param", Key="T", Value=str(sixd_z), Comment="板厚")

    outline = ET.SubElement(panel_elem, "PanelOutline")
    vertices = [
        (0, sixd_y),
        (0, 0),
        (sixd_x, 0),
        (sixd_x, sixd_y),
        (0, sixd_y),
    ]
    for vx, vy in vertices:
        vt = ET.SubElement(outline, "Vertex")
        _add_text(vt, "X1", str(vx))
        _add_text(vt, "Y1", str(vy))

    # 孔位
    for hole in holes:
        xml_x = _hole_value(hole, x1_key)
        xml_y = _hole_value(hole, y1_key)
        diam = float(hole.get("diameter", 10))
        depth_2d = float(hole.get("depth", 11))
        direction = hole.get("direction", "+z")

        # 从孔自身属性读取：is_face_hole → TypeNo=1(Vertical), 否则 TypeNo=2(Horizontal)
        if hole.get("is_face_hole", True):
            type_no = "1"
            type_name = "Vertical Hole"
        else:
            type_no = "2"
            type_name = "Horizontal Hole"

        cad = ET.SubElement(root, "CAD")
        _add_text(cad, "TypeNo", type_no)
        _add_text(cad, "TypeName", type_name)
        _add_text(cad, "X1", f"{xml_x:.1f}")
        _add_text(cad, "Y1", f"{xml_y:.1f}")
        if type_no == "2":
            z1 = _hole_value(hole, z1_key)
            machine_direction = _machine_direction(
                direction,
                machine_x_axis,
                machine_y_axis,
            )
            _add_text(cad, "Z1", f"{z1:.2f}")
            _add_text(cad, "Quadrant", _quadrant(machine_direction))
            _add_text(cad, "IntervalZ", "0.00")
        _add_text(cad, "Depth", f"{depth_2d:.1f}")
        _add_text(cad, "Diameter", f"{diam:.1f}")
        _add_text(cad, "Enable", "1")
        _add_text(cad, "HoleNo", "1")
        _add_text(cad, "IntervalX", "0.00")
        _add_text(cad, "IntervalY", "0.00")

    if slots:
        raise ValueError(
            "six-side drill slot export is not implemented; refusing to omit slots"
        )

    _rough = ET.tostring(root, encoding="unicode")
    dom = minidom.parseString(_rough)
    return _flush_xml(dom.toprettyxml(indent="    "))


def _add_text(parent: ET.Element, tag: str, text: str) -> ET.Element:
    elem = ET.SubElement(parent, tag)
    elem.text = text
    return elem
````

## File: domain/skills/furniture-manufacturing/scripts/furniture_manufacturing/hole_validator.py
````python
"""孔位校验器 — 深度校验 + 边界检测 + 空间干涉检测。"""

from __future__ import annotations

import math
import warnings as _warnings
from typing import List

import numpy as np

from furniture_manufacturing.connectors.base import HoleSpec
from furniture_manufacturing.manufacturing_models import PanelRecord


class HoleValidationError(Exception):
    """孔位校验失败。"""


# ── 深度校验 ──────────────────────────────────────────────────

def _panel_size_along(panel: PanelRecord, direction: str) -> float:
    """打孔方向上的板件尺寸。

    面钻孔沿板厚方向（如侧板 ±x → size_x 即板厚）；
    端面钻孔沿板内方向（如横板连接杆 ±x → size_x 即板宽）。
    """
    axis = direction[1] if len(direction) >= 2 else "z"
    return {
        "x": panel.size_x,
        "y": panel.size_y,
        "z": panel.size_z,
    }.get(axis, panel.thickness)


def validate_hole_depth(hole: HoleSpec, panel: PanelRecord) -> None:
    """检查孔深度 ≤ 打孔方向上的板件尺寸。

    深度与打孔方向的板件尺寸比较，而非一律与板厚比较：
    端面钻入的连接杆/预孔沿板内方向走，深度可大于板厚。
    连接杆孔超限时发出警告而非报错（杆将穿入相邻板预埋螺母）。
    """
    limit = _panel_size_along(panel, hole.direction)
    if hole.depth <= limit:
        return

    if "连接杆" in hole.note:
        _warnings.warn(
            f"[三合一] {panel.label} 连接杆孔深 {hole.depth}mm > "
            f"打孔方向尺寸 {limit}mm, 杆将穿入相邻板预埋螺母。"
        )
        return

    raise HoleValidationError(
        f"{panel.label} 孔深 {hole.depth}mm > 打孔方向尺寸 {limit}mm: "
        f"{hole.note} (类型={hole.hole_type}, 方向={hole.direction}, 局部="
        f"({hole.x_local:.1f},{hole.y_local:.1f},{hole.z_local:.1f}))"
    )


# ── 边界检测 ──────────────────────────────────────────────────

def validate_hole_bounds(hole: HoleSpec, panel: PanelRecord) -> None:
    """检查孔位在板件边界内（含孔半径 margin）。"""
    r = hole.diameter / 2.0
    x, y, z = hole.x_local, hole.y_local, hole.z_local
    sx, sy, sz = panel.size_x, panel.size_y, panel.size_z

    def _in_range(v: float, size: float, margin: float) -> bool:
        return -margin <= v <= size + margin

    if not (_in_range(x, sx, r) and _in_range(y, sy, r) and _in_range(z, sz, r)):
        raise HoleValidationError(
            f"{panel.label} {hole.note}: 孔中心({x:.1f},{y:.1f},{z:.1f}) "
            f"超出板件 [{sx:.1f}×{sy:.1f}×{sz:.1f}], 半径={r:.1f}"
        )


# ── 干涉检测 ──────────────────────────────────────────────────

def _hole_cylinders_collide(
    h1: HoleSpec, h2: HoleSpec, safety_gap: float = 3.0,
) -> bool:
    """检查同方向平行孔是否干涉（开口间距）。

    正交孔（如三合一连接杆孔与偏心轮孔）是设计上的配合关系，
    不做空间球包围判定，避免把正常配合误报为干涉。
    """
    if h1.direction != h2.direction:
        return False
    p1 = np.array([h1.x_local, h1.y_local, h1.z_local])
    p2 = np.array([h2.x_local, h2.y_local, h2.z_local])

    # 同方向: 投影到垂直平面检查 2D 中心距
    axis_map = {"x": (1, 2), "y": (0, 2), "z": (0, 1)}
    dir_axis = h1.direction[1]
    axes = axis_map.get(dir_axis, (0, 1))
    dist_2d = math.sqrt(
        (p1[axes[0]] - p2[axes[0]]) ** 2
        + (p1[axes[1]] - p2[axes[1]]) ** 2
    )
    min_dist = (h1.diameter + h2.diameter) / 2.0 + safety_gap
    return dist_2d < min_dist


def validate_holes_no_interference(
    holes: List[HoleSpec],
    panel: PanelRecord,
    safety_gap: float = 3.0,
) -> None:
    """检查同一板件上的孔位是否有空间干涉。"""
    n = len(holes)
    for i in range(n):
        for j in range(i + 1, n):
            h1, h2 = holes[i], holes[j]
            if _hole_cylinders_collide(h1, h2, safety_gap):
                raise HoleValidationError(
                    f"{panel.label} 孔位干涉: {h1.note}({h1.x_local:.1f},"
                    f"{h1.y_local:.1f},{h1.z_local:.1f}) ↔ "
                    f"{h2.note}({h2.x_local:.1f},{h2.y_local:.1f},{h2.z_local:.1f})"
                )


# ── 批量校验 ──────────────────────────────────────────────────

def validate_all_holes(
    holes: List[HoleSpec],
    panel: PanelRecord,
    safety_gap: float = 3.0,
) -> List[str]:
    """对单块板件的全部孔位执行所有校验, 返回警告列表。"""
    warns: List[str] = []
    for hole in holes:
        try:
            validate_hole_depth(hole, panel)
        except HoleValidationError as e:
            warns.append(str(e))
        try:
            validate_hole_bounds(hole, panel)
        except HoleValidationError as e:
            warns.append(str(e))
    try:
        validate_holes_no_interference(holes, panel, safety_gap)
    except HoleValidationError as e:
        warns.append(str(e))
    return warns
````

## File: domain/skills/furniture-manufacturing/scripts/furniture_manufacturing/manufacturing_edge_banding.py
````python
"""Manufacturing-stage edge-banding policy."""

from __future__ import annotations

from typing import Dict


DEFAULT_EDGE_RULES: Dict[str, Dict[str, str]] = {
    "side": {"四边": "ABS 1.0mm同色"},
    "top": {"四边": "ABS 1.0mm同色"},
    "bottom": {"四边": "ABS 1.0mm同色"},
    "fixed_shelf": {"四边": "ABS 1.0mm同色"},
    "movable_shelf": {"四边": "ABS 1.0mm同色"},
    "divider": {"四边": "ABS 1.0mm同色"},
    "toe_kick": {"四边": "ABS 1.0mm同色"},
    "door": {"四边": "ABS 1.0mm同色"},
    "back": {"四边": "ABS 1.0mm同色"},
    "back_rail": {"四边": "ABS 1.0mm同色"},
    "drawer_front": {"四边": "ABS 1.0mm同色"},
    "drawer_side": {"四边": "ABS 1.0mm同色"},
    "drawer_back": {"四边": "ABS 1.0mm同色"},
    "drawer_bottom": {"四边": "ABS 1.0mm同色"},
}


def get_edge_banding(
    panel_type: str,
    rules: Dict[str, Dict[str, str]] | None = None,
) -> Dict[str, str]:
    return dict((rules or DEFAULT_EDGE_RULES).get(panel_type, {}))
````

## File: domain/skills/furniture-manufacturing/scripts/furniture_manufacturing/production_simulation.py
````python
"""Bounded panel-level production simulation with optional SimPy execution."""

from __future__ import annotations

from importlib.metadata import version
from math import isfinite, log, sqrt
import random
from statistics import fmean, stdev
from typing import Any, Mapping


def _validate_config(
    manufacturing_output: Mapping[str, Any], config: Mapping[str, Any]
) -> tuple[dict[str, int], dict[str, list[dict[str, Any]]], dict[str, Any] | None]:
    raw_resources = config.get("resources")
    if not isinstance(raw_resources, Mapping) or not raw_resources:
        raise ValueError("resources must be a non-empty capacity object")
    resources: dict[str, int] = {}
    for name, raw_capacity in raw_resources.items():
        capacity = int(raw_capacity)
        if isinstance(raw_capacity, bool) or capacity < 1 or capacity > 1000:
            raise ValueError(f"resource capacity must be 1..1000: {name}")
        resources[str(name)] = capacity

    raw_routes = config.get("routes")
    if not isinstance(raw_routes, Mapping) or not raw_routes:
        raise ValueError("routes must be a non-empty object keyed by panel_type or *")
    routes: dict[str, list[dict[str, Any]]] = {}
    for panel_type, raw_steps in raw_routes.items():
        if not isinstance(raw_steps, list) or not raw_steps or len(raw_steps) > 50:
            raise ValueError(f"route {panel_type} requires 1..50 operations")
        steps: list[dict[str, Any]] = []
        for index, raw_step in enumerate(raw_steps):
            if not isinstance(raw_step, Mapping):
                raise ValueError(f"route {panel_type} operation {index} is not an object")
            resource = str(raw_step.get("resource", ""))
            duration = float(raw_step.get("duration_min", 0.0))
            if resource not in resources:
                raise ValueError(f"route {panel_type} uses unknown resource: {resource}")
            if duration <= 0 or not isfinite(duration):
                raise ValueError(f"route duration must be finite and positive: {panel_type}")
            steps.append({"resource": resource, "duration_min": duration})
        routes[str(panel_type)] = steps

    panels = manufacturing_output.get("panels")
    if not isinstance(panels, list) or not panels:
        raise ValueError("manufacturing output requires panels")
    entity_count = sum(int(item.get("quantity", 1)) for item in panels)
    max_entities = int(config.get("max_entities", 10_000))
    if entity_count > max_entities or not 1 <= max_entities <= 10_000:
        raise ValueError(f"panel entities exceed max_entities={max_entities}")
    total_operations = sum(
        int(item.get("quantity", 1))
        * len(routes.get(str(item.get("panel_type")), routes.get("*", [])))
        for item in panels
    )
    if total_operations > 200_000:
        raise ValueError("model exceeds the 200000-operation bound")
    for item in panels:
        if str(item.get("panel_type")) not in routes and "*" not in routes:
            raise ValueError(f"no route for panel type: {item.get('panel_type')}")

    raw_assembly = config.get("assembly")
    assembly: dict[str, Any] | None = None
    if raw_assembly is not None:
        if not isinstance(raw_assembly, Mapping):
            raise ValueError("assembly must be an object")
        resource = str(raw_assembly.get("resource", ""))
        duration = float(raw_assembly.get("duration_min", 0.0))
        if resource not in resources or duration <= 0 or not isfinite(duration):
            raise ValueError("assembly requires a known resource and positive duration_min")
        assembly = {"resource": resource, "duration_min": duration}
    return resources, routes, assembly


def _sample_duration(mean: float, cv: float, rng: random.Random) -> float:
    if cv == 0:
        return mean
    sigma = sqrt(log(1.0 + cv * cv))
    mu = log(mean) - sigma * sigma / 2.0
    return rng.lognormvariate(mu, sigma)


def _run_simpy_replication(
    manufacturing_output: Mapping[str, Any],
    resources_config: Mapping[str, int],
    routes: Mapping[str, list[dict[str, Any]]],
    assembly: Mapping[str, Any] | None,
    *,
    seed: int,
    cv: float,
    max_time: float,
) -> dict[str, Any]:
    import simpy

    env = simpy.Environment()
    resources = {
        name: simpy.Resource(env, capacity=capacity)
        for name, capacity in resources_config.items()
    }
    busy = {name: 0.0 for name in resources}
    waits: list[float] = []
    completions: list[float] = []
    stream_seeds = {
        name: seed + 10_000 * (index + 1)
        for index, name in enumerate(sorted(resources))
    }
    rngs = {
        name: random.Random(stream_seed)
        for name, stream_seed in stream_seeds.items()
    }

    def panel_process(panel: Mapping[str, Any], entity_id: str):
        route = routes.get(str(panel.get("panel_type")), routes.get("*", []))
        for step in route:
            resource_name = step["resource"]
            requested_at = env.now
            with resources[resource_name].request() as request:
                yield request
                waits.append(env.now - requested_at)
                duration = _sample_duration(
                    float(step["duration_min"]),
                    cv,
                    rngs[resource_name],
                )
                busy[resource_name] += min(
                    duration,
                    max(0.0, max_time - env.now),
                )
                yield env.timeout(duration)
        completions.append(env.now)
        return entity_id

    panel_events = []
    for panel in manufacturing_output["panels"]:
        for item_index in range(int(panel.get("quantity", 1))):
            entity_id = f"{panel.get('label', panel.get('name', 'panel'))}:{item_index + 1}"
            panel_events.append(env.process(panel_process(panel, entity_id)))

    def complete_order():
        yield simpy.AllOf(env, panel_events)
        if assembly is not None:
            requested_at = env.now
            resource_name = str(assembly["resource"])
            with resources[resource_name].request() as request:
                yield request
                waits.append(env.now - requested_at)
                duration = _sample_duration(
                    float(assembly["duration_min"]),
                    cv,
                    rngs[resource_name],
                )
                busy[resource_name] += min(
                    duration,
                    max(0.0, max_time - env.now),
                )
                yield env.timeout(duration)
        return env.now

    order = env.process(complete_order())
    timeout = env.timeout(max_time)
    result = env.run(until=order | timeout)
    completed = order in result
    makespan = float(order.value) if completed else max_time
    return {
        "completed": completed,
        "makespan_min": makespan,
        "panel_entities": len(panel_events),
        "unfinished_entities": 0 if completed else len(panel_events) - len(completions),
        "total_wait_min": sum(waits),
        "mean_wait_min": fmean(waits) if waits else 0.0,
        "resource_utilization": {
            name: busy[name] / (resources_config[name] * makespan) if makespan else 0.0
            for name in resources
        },
        "seed": seed,
        "stream_seeds": stream_seeds,
    }


def _run_flowshop_fallback(
    manufacturing_output: Mapping[str, Any],
    resources_config: Mapping[str, int],
    routes: Mapping[str, list[dict[str, Any]]],
    assembly: Mapping[str, Any] | None,
) -> dict[str, Any]:
    available = {name: [0.0] * capacity for name, capacity in resources_config.items()}
    busy = {name: 0.0 for name in resources_config}
    waits: list[float] = []
    completions: list[float] = []
    entity_count = 0
    for panel in manufacturing_output["panels"]:
        route = routes.get(str(panel.get("panel_type")), routes.get("*", []))
        for _ in range(int(panel.get("quantity", 1))):
            entity_count += 1
            ready = 0.0
            for step in route:
                name = step["resource"]
                slot = min(range(len(available[name])), key=available[name].__getitem__)
                start = max(ready, available[name][slot])
                waits.append(start - ready)
                duration = float(step["duration_min"])
                ready = start + duration
                available[name][slot] = ready
                busy[name] += duration
            completions.append(ready)
    makespan = max(completions, default=0.0)
    if assembly is not None:
        name = str(assembly["resource"])
        slot = min(range(len(available[name])), key=available[name].__getitem__)
        start = max(makespan, available[name][slot])
        waits.append(start - makespan)
        duration = float(assembly["duration_min"])
        makespan = start + duration
        busy[name] += duration
    return {
        "completed": True,
        "makespan_min": makespan,
        "panel_entities": entity_count,
        "unfinished_entities": 0,
        "total_wait_min": sum(waits),
        "mean_wait_min": fmean(waits) if waits else 0.0,
        "resource_utilization": {
            name: busy[name] / (resources_config[name] * makespan) if makespan else 0.0
            for name in resources_config
        },
        "seed": None,
    }


def simulate_production(
    manufacturing_output: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Run bounded independent replications or an explicit deterministic fallback."""

    resources, routes, assembly = _validate_config(manufacturing_output, config)
    replications = int(config.get("replications", 20))
    if not 1 <= replications <= 500:
        raise ValueError("replications must be between 1 and 500")
    base_seed = int(config.get("seed", 42))
    cv = float(config.get("duration_cv", 0.0))
    max_time = float(config.get("max_time_min", 1_000_000.0))
    if not 0 <= cv <= 2 or max_time <= 0 or not isfinite(max_time):
        raise ValueError("duration_cv must be 0..2 and max_time_min must be positive")
    try:
        import simpy  # noqa: F401
    except ImportError:
        if bool(config.get("require_simpy", False)):
            return {
                "analysis": "production_simulation",
                "status": "unavailable",
                "engine": "simpy",
                "reason": "SimPy is not installed; install the furniture-analysis extra",
            }
        runs = [_run_flowshop_fallback(manufacturing_output, resources, routes, assembly)]
        engine = "bounded-deterministic-flowshop-fallback"
        limitations = [
            "SimPy was unavailable; the fallback uses deterministic FIFO flow-shop scheduling",
            "duration variability and independent-replication uncertainty were not evaluated",
        ]
    else:
        runs = [
            _run_simpy_replication(
                manufacturing_output,
                resources,
                routes,
                assembly,
                seed=base_seed + index,
                cv=cv,
                max_time=max_time,
            )
            for index in range(replications)
        ]
        engine = f"simpy-{version('simpy')}"
        limitations = [
            "results are implications of the declared routes, capacities, and duration model",
            "simulation contrasts are not causal evidence about the real factory",
        ]
    makespans = [float(item["makespan_min"]) for item in runs]
    summary: dict[str, Any] = {
        "mean_makespan_min": fmean(makespans),
        "min_makespan_min": min(makespans),
        "max_makespan_min": max(makespans),
        "sd_makespan_min": stdev(makespans) if len(makespans) > 1 else None,
        "completed_replications": sum(bool(item["completed"]) for item in runs),
    }
    if len(makespans) > 1:
        try:
            from scipy import stats
        except ImportError:
            limitations.append("SciPy was unavailable; no Student-t interval was computed")
        else:
            critical = float(stats.t.ppf(0.975, len(makespans) - 1))
            half_width = critical * stdev(makespans) / sqrt(len(makespans))
            summary["mean_makespan_95pct_ci_min"] = [
                summary["mean_makespan_min"] - half_width,
                summary["mean_makespan_min"] + half_width,
            ]
    return {
        "analysis": "production_simulation",
        "status": "completed",
        "engine": engine,
        "time_unit": "minute",
        "resources": resources,
        "routes": routes,
        "assembly": assembly,
        "duration_cv": cv if engine.startswith("simpy") else 0.0,
        "replications": len(runs),
        "base_seed": base_seed if engine.startswith("simpy") else None,
        "seed_manifest": (
            [
                {
                    "replication": index + 1,
                    "replication_seed": item["seed"],
                    "stream_seeds": item.get("stream_seeds", {}),
                }
                for index, item in enumerate(runs)
            ]
            if engine.startswith("simpy")
            else []
        ),
        "summary": summary,
        "runs": runs,
        "limitations": limitations,
    }
````

## File: domain/skills/furniture-manufacturing/scripts/furniture_manufacturing/prototype_experiment.py
````python
"""Furniture prototype experiment schedules derived from DOE principles."""

from __future__ import annotations

from itertools import product
import random
from typing import Any, Mapping


def _factor_domains(raw: Any) -> dict[str, list[Any]]:
    if not isinstance(raw, Mapping) or not raw:
        raise ValueError("factors must be a non-empty object")
    factors: dict[str, list[Any]] = {}
    for name, levels in raw.items():
        if not isinstance(levels, list) or len(levels) < 2:
            raise ValueError(f"factor {name} requires at least two levels")
        if len(levels) > 12:
            raise ValueError(f"factor {name} exceeds 12 levels")
        if len({repr(value) for value in levels}) != len(levels):
            raise ValueError(f"factor {name} contains duplicate levels")
        factors[str(name)] = list(levels)
    return factors


def design_prototype_experiment(
    manufacturing_output: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a seeded full-factorial schedule with explicit replicate level."""

    factors = _factor_domains(config.get("factors"))
    responses = config.get("responses")
    if not isinstance(responses, list) or not responses or not all(
        isinstance(item, str) and item.strip() for item in responses
    ):
        raise ValueError("responses must be a non-empty list of names")
    independent_unit = str(config.get("independent_unit", "")).strip()
    if not independent_unit:
        raise ValueError("independent_unit is required to prevent pseudoreplication")
    replicates = int(config.get("replicates", 1))
    if not 1 <= replicates <= 100:
        raise ValueError("replicates must be between 1 and 100")
    seed = int(config.get("seed", 42))
    if not 0 <= seed <= 2**63 - 1:
        raise ValueError("seed must be between 0 and 2**63-1")
    raw_blocks = config.get("blocks", ["block-1"])
    if not isinstance(raw_blocks, list) or not raw_blocks:
        raise ValueError("blocks must be a non-empty list")
    blocks = [str(item).strip() for item in raw_blocks]
    if any(not item for item in blocks) or len(set(blocks)) != len(blocks):
        raise ValueError("blocks must contain unique non-empty names")

    factor_names = list(factors)
    combinations = list(product(*(factors[name] for name in factor_names)))
    total_runs = len(combinations) * replicates
    max_runs = int(config.get("max_runs", 10_000))
    if not 1 <= max_runs <= 10_000 or total_runs > max_runs:
        raise ValueError(f"experiment has {total_runs} runs, above max_runs={max_runs}")

    rows: list[dict[str, Any]] = []
    for replicate in range(1, replicates + 1):
        for combination in combinations:
            rows.append(
                {
                    "replicate": replicate,
                    **dict(zip(factor_names, combination)),
                }
            )
    rng = random.Random(seed)
    rng.shuffle(rows)
    for index, row in enumerate(rows, start=1):
        row["run_order"] = index
        row["block"] = blocks[(index - 1) % len(blocks)]
        row["independent_unit_id"] = f"{independent_unit}-{index:04d}"

    return {
        "analysis": "prototype_experiment",
        "status": "completed",
        "engine": "seeded-full-factorial",
        "design": "full_factorial",
        "independent_unit": independent_unit,
        "factors": factors,
        "responses": [str(item) for item in responses],
        "n_factor_combinations": len(combinations),
        "run_count": total_runs,
        "replicates": replicates,
        "blocks": blocks,
        "seed": seed,
        "runs": rows,
        "source_summary": {
            "panel_count": len(manufacturing_output.get("panels", [])),
            "readiness": manufacturing_output.get("readiness", "preliminary"),
        },
        "limitations": [
            "sample size adequacy is not inferred from the requested replicate count",
            (
                "blocking labels are balanced by run order; the user must confirm "
                "they represent real nuisance factors"
            ),
            "repeated measurements on one independent unit are not additional replicates",
        ],
    }
````

## File: domain/skills/furniture-manufacturing/scripts/furniture_manufacturing/test_statistics.py
````python
"""Bounded statistics for already-collected furniture prototype measurements."""

from __future__ import annotations

from math import isfinite, sqrt
from statistics import fmean, stdev
from typing import Any, Mapping


def _descriptive(values: list[float]) -> dict[str, Any]:
    ordered = sorted(values)
    middle = len(ordered) // 2
    median = (
        ordered[middle]
        if len(ordered) % 2
        else (ordered[middle - 1] + ordered[middle]) / 2.0
    )
    return {
        "n": len(values),
        "mean": fmean(values),
        "sd": stdev(values) if len(values) > 1 else None,
        "median": median,
        "min": ordered[0],
        "max": ordered[-1],
    }


def _hedges_g(a: list[float], b: list[float]) -> float | None:
    if len(a) < 2 or len(b) < 2:
        return None
    pooled_df = len(a) + len(b) - 2
    pooled_variance = (
        (len(a) - 1) * stdev(a) ** 2 + (len(b) - 1) * stdev(b) ** 2
    ) / pooled_df
    if pooled_variance <= 0:
        return 0.0 if fmean(a) == fmean(b) else None
    d = (fmean(a) - fmean(b)) / sqrt(pooled_variance)
    correction = 1.0 - 3.0 / (4.0 * (len(a) + len(b)) - 9.0)
    return d * correction


def _hedges_g_standard_error(
    a: list[float],
    b: list[float],
    hedges_g: float | None,
) -> float | None:
    """Approximate large-sample standard error for standardized mean difference."""

    if hedges_g is None or len(a) < 2 or len(b) < 2:
        return None
    degrees_of_freedom = len(a) + len(b) - 2
    correction = 1.0 - 3.0 / (4.0 * (len(a) + len(b)) - 9.0)
    d = hedges_g / correction
    variance_d = (
        (len(a) + len(b)) / (len(a) * len(b))
        + d * d / (2.0 * degrees_of_freedom)
    )
    return correction * sqrt(variance_d)


def _finite_or_none(value: Any) -> float | None:
    result = float(value)
    return result if isfinite(result) else None


def analyze_prototype_results(
    manufacturing_output: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Analyze explicit records; never fabricate observations from a DOE plan."""

    records = config.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("records must be a non-empty list of collected observations")
    if len(records) > 100_000:
        raise ValueError("records exceed the 100000-row bound")
    group_field = str(config.get("group_field", "group")).strip()
    value_field = str(config.get("value_field", "value")).strip()
    if not group_field or not value_field:
        raise ValueError("group_field and value_field are required")
    alpha = float(config.get("alpha", 0.05))
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1")

    groups: dict[str, list[float]] = {}
    missing = 0
    for index, row in enumerate(records):
        if not isinstance(row, Mapping):
            raise ValueError(f"record {index} is not an object")
        group = row.get(group_field)
        raw_value = row.get(value_field)
        if group is None or raw_value is None or raw_value == "":
            missing += 1
            continue
        value = float(raw_value)
        if not isfinite(value):
            raise ValueError(f"record {index} has a non-finite value")
        groups.setdefault(str(group), []).append(value)
    if not groups:
        raise ValueError("no complete observations remain")

    report: dict[str, Any] = {
        "analysis": "test_statistics",
        "status": "descriptive_only",
        "engine": "python-statistics",
        "group_field": group_field,
        "value_field": value_field,
        "alpha": alpha,
        "missing_rows": missing,
        "descriptives": {name: _descriptive(values) for name, values in groups.items()},
        "assumption_checks": {},
        "inference": None,
        "source_summary": {
            "readiness": manufacturing_output.get("readiness", "preliminary"),
            "panel_count": len(manufacturing_output.get("panels", [])),
        },
        "limitations": [
            "analysis assumes each row is an independent unit unless the design says otherwise",
            "no missing-value imputation or outlier removal is performed",
            (
                "statistical significance does not automatically establish practical "
                "or manufacturing importance"
            ),
        ],
    }
    try:
        from scipy import stats
    except ImportError:
        report["limitations"].append("SciPy is unavailable; only descriptives were computed")
        return report

    report["engine"] = "scipy"
    for name, values in groups.items():
        if 3 <= len(values) <= 5000:
            result = stats.shapiro(values)
            report["assumption_checks"][f"shapiro:{name}"] = {
                "statistic": _finite_or_none(result.statistic),
                "p_value": _finite_or_none(result.pvalue),
            }
    group_values = list(groups.values())
    if len(groups) >= 2 and all(len(values) >= 2 for values in group_values):
        levene = stats.levene(*group_values, center="median")
        report["assumption_checks"]["levene"] = {
            "statistic": _finite_or_none(levene.statistic),
            "p_value": _finite_or_none(levene.pvalue),
        }

    if len(groups) == 2 and all(len(values) >= 2 for values in group_values):
        names = list(groups)
        a, b = group_values
        test = stats.ttest_ind(a, b, equal_var=False)
        va = stdev(a) ** 2 / len(a)
        vb = stdev(b) ** 2 / len(b)
        df = (va + vb) ** 2 / (
            va**2 / (len(a) - 1) + vb**2 / (len(b) - 1)
        ) if va + vb else float(len(a) + len(b) - 2)
        difference = fmean(a) - fmean(b)
        critical = float(stats.t.ppf(1.0 - alpha / 2.0, df))
        half_width = critical * sqrt(va + vb)
        hedges_g = _hedges_g(a, b)
        hedges_g_se = _hedges_g_standard_error(a, b, hedges_g)
        effect_critical = float(stats.norm.ppf(1.0 - alpha / 2.0))
        report["inference"] = {
            "test": "welch_t_test",
            "groups": names,
            "mean_difference": difference,
            "confidence_interval": [difference - half_width, difference + half_width],
            "confidence_level": 1.0 - alpha,
            "statistic": _finite_or_none(test.statistic),
            "degrees_of_freedom": df,
            "p_value": _finite_or_none(test.pvalue),
            "hedges_g": hedges_g,
            "hedges_g_confidence_interval": (
                [
                    hedges_g - effect_critical * hedges_g_se,
                    hedges_g + effect_critical * hedges_g_se,
                ]
                if hedges_g is not None and hedges_g_se is not None
                else None
            ),
            "effect_size_ci_method": "large-sample normal approximation",
        }
        report["status"] = "completed"
    elif len(groups) >= 3 and all(len(values) >= 2 for values in group_values):
        levene_p = report["assumption_checks"].get("levene", {}).get("p_value")
        if levene_p is not None and levene_p >= alpha:
            test = stats.f_oneway(*group_values)
            all_values = [value for values in group_values for value in values]
            grand = fmean(all_values)
            between = sum(len(values) * (fmean(values) - grand) ** 2 for values in group_values)
            total = sum((value - grand) ** 2 for value in all_values)
            report["inference"] = {
                "test": "one_way_anova",
                "statistic": _finite_or_none(test.statistic),
                "p_value": _finite_or_none(test.pvalue),
                "eta_squared": between / total if total else 0.0,
                "post_hoc": "not_run",
            }
            report["status"] = "completed"
        else:
            report["limitations"].append(
                "group variances are not homogeneous; one-way ANOVA was not run"
            )
    else:
        report["limitations"].append(
            "at least two observations per group are required for inference"
        )
    return report
````

## File: domain/skills/furniture-manufacturing/SKILL.md
````markdown
---
name: furniture-manufacturing
description: 用于 manufacturing_planned 阶段。当用户说"用什么五金""三合一连接件""铰链怎么装""封边怎么做""出BOM清单""打孔位置"时触发。根据已确认板件制定材料、封边、连接、五金、孔位和 BOM，不构造特征树或 CAD。
---

# 家具制造策略

阶段：`manufacturing_planned`

## 工作流

1. 检查前置：`design_intent` 与 `panels_planned` 均已确认；独立 `furniture-layout` 结果不是前置条件。
2. 由 LLM 根据完整上下文理解制造需求，提出整份策略草案，并把未明确的假设逐项列出给用户确认。策略覆盖：
   - 材料：类别、等级、厚度、纹理、可见面、饰面；
   - 封边：封哪些边、封边厚度及余量；
   - 连接：螺钉、木榫、偏心件（三合一/二合一）、槽/企口、胶合；
   - 五金：铰链、滑轨、拉手、层板托、固定、防倾倒及荷载；
   - 公差/净空：门缝、安装/设备缝隙、地墙不平、安全余量。
   口径见 [制造规则](references/manufacturing-rules.md)；不做关键词识别、同义词映射或开放方案排序。
3. 五金变体与打孔参数以 `scripts/furniture_manufacturing/hardware_catalog.yaml`、`hardware_rules.yaml` 为准：LLM 只选变体并把数值假设标为待确认，不硬编码或猜测参数。
4. 把选定策略交 `FurnitureOrchestrator.run_next()` 生成确定性结果（孔位、封边、槽、BOM），由运行时校验；展示整套制造方案，暂停等待用户确认。
5. 整份方案用 `readiness=preliminary/accepted/factory_ready` 表示接受程度，默认 `preliminary`；未经用户明确接受不得升 `accepted`，未经工厂确认不得升 `factory_ready`。

## 关键规则

- 材料厚度、单门/标准双门的铰链侧 `door_hinge_side` 均来自已确认的 `panels_planned` 输出，不从意图重建或硬编码覆盖；旧数据缺省时才按门板位置回退。
- 三合一在高度方向按系统 32 排钻分布、深度方向前后双排；铰链孔、背板槽与背板连接、封边的精确口径见 [制造规则](references/manufacturing-rules.md)。
- 入槽背板不封边；其余背板及背拉条四边封边；cover 外盖螺钉与 groove 背拉条螺钉属组装现场工艺，不生成孔位与五金。
- `readiness` 作用于整份方案/BOM，不伪装成每条五金或封边记录均已单独审批。

## 子流程（按触发词加载，不进主流程）

| 用户提到 | 读取/调用 |
|---------|----------|
| 对照外部五金/加工类目、打孔 | `references/hardware-machining-reference.md` |
| 六面钻、机床加工、导 XML | `references/six-side-drill-export.md` |
| 样件、承重、连接件或涂装对比试验 | `../../external/scientific-agent-skills/skills/experimental-design/SKILL.md` + `prototype_experiment.py` |
| 分析已采集试验数据 | `../../external/scientific-agent-skills/skills/statistical-analysis/SKILL.md` + `test_statistics.py` |
| 板件加工路线、共享设备、齐套装配、工位排队、交期 | `../../external/scientific-agent-skills/skills/simpy/SKILL.md` + `production_simulation.py` |

## 边界

- 运行时在 `scripts/furniture_manufacturing/`；代码契约与演进中需求见 [运行时映射](references/runtime-map.md)。
- 修改制造策略时使用 `revise_stage_output()`，使本阶段及下游失效。
- 不发射特征树、不调用 CAD Bridge、不手改派生产物。
- 试验、统计和生产仿真写入 `stage_analyses.manufacturing_planned`，只提供证据或候选；它们不自动提升 `readiness`，不直接修改 BOM，也不构成现实工厂因果结论。
````

## File: domain/skills/furniture-panel-planning/agents/openai.yaml
````yaml
interface:
  display_name: "家具板件规划"
  short_description: "确认结构、净空、背板并生成实体板件"
  default_prompt: "使用 $furniture-panel-planning 从已确认外包络理解并提议层板、门、抽屉、板厚、背板、踢脚和净空方案；展示假设，经确定性代码准入后生成可审查板件，不要求房间摆放图。"
````

## File: domain/skills/furniture-panel-planning/references/back-construction-rules.md
````markdown
# 背板结构规则

回答“成品外包络确认后，柜体采用什么背板结构，以及由此得到哪些精确结构尺寸？”；本文件是背板设计的唯一规则中心。

## 阶段输入

- `back_mount`：规范值为 `auto/groove/insert/cover`；必须由提案显式给出，不存在运行时缺省模式。
- `board_thickness/back_thickness/door_thickness`。
- `back_offset/door_margin/door_hinge_gap`。
- `groove_depth/groove_clearance/back_rail_height`。

这些值可在完整 CLI/API 请求中提前提交，但只保存在 `stage_inputs.panels.parameters`，直到客户确认设计意图后才物化为板件阶段 `FurnitureSpec`。

## 模式解析

- `groove/insert/cover` 保持显式选择。
- 显式 `auto`：`back_thickness < board_thickness` 时解析为 `groove`，否则为 `insert`。这是用户确认后调用的确定性公式，不是代码自行选择结构方案。
- 输出必须同时展示 `back_mount_resolution.requested/effective`；下游只消费有效模式。
- `groove_depth/groove_clearance/back_rail_height` 只在有效模式为 `groove` 时参与几何；其他模式仍要求它们是合法规范数值，但不因数值范围与入槽加工关系而阻塞。

## 精确结构

- 柜体前端统一预留 `door_thickness + door_hinge_gap`，所有板件保持在已确认成品深度内。
- `groove/insert`：柜体从 `Y=0` 开始，背板基准为 `back_offset`，内部 Y 起点为 `back_offset + back_thickness`。
- `cover`：背板位于 `Y=0`，柜体从 `Y=back_thickness` 开始，背板不得与柜体重叠。
- 内部 X/Z 范围由成品外包络、柜体板厚和踢脚高度计算；所有净宽、净高、净深必须为正。

## 背板与背拉条

- `groove`：背板宽高为内部净宽/净高各加 `2×groove_depth`；仅此模式生成背拉条。
- `insert`：背板为内部净宽×内部净高，位于 `back_offset`。
- `cover`：背板为成品宽×成品高，覆盖整个背面。
- 背拉条数量、尺寸、位置和净距属于本阶段；实际槽包络、连接、封边和孔位属于制造阶段。
````

## File: domain/skills/furniture-panel-planning/scripts/furniture_panel_planning/__init__.py
````python
"""Panel-planning stage runtime."""
````

## File: domain/skills/furniture-panel-planning/scripts/furniture_panel_planning/cabinet_frame.py
````python
"""CabinetFrame — converts semantic cabinet directions into world axes.

A two-axis definition (front + top) resolves all six semantic faces via the
right-hand rule.  This is the single point of truth for cabinet orientation;
every downstream subsystem (panel placement, connectors, feature tree,
six-side drill) reads faces from here instead of hardcoding world axes.

Examples
--------
Standard floor cabinet:
    frame = CabinetFrame(front="+y", top="+z")   → right="+x"

Top-down tatami (front viewed from above, body lying on floor):
    frame = CabinetFrame(front="+z", top="-y")    → right="+x"
"""

from __future__ import annotations

from dataclasses import dataclass


def _negate(axis: str) -> str:
    """Flip a signed axis: "+x"→"-x", "-y"→"+y"."""
    if axis[0] == "+":
        return f"-{axis[1]}"
    return f"+{axis[1]}"


def _cross(axis_a: str, axis_b: str) -> str:
    """Right-hand cross product of two signed world axes.

    Uses the convention: x=width, y=depth, z=height.

    (cross "+y", "+z") → "+x"  (front × top = right)
    (cross "+z", "+x") → "+y"
    (cross "+x", "+y") → "+z"
    """
    axes = {a[1] for a in (axis_a, axis_b)}
    if {"x", "y"} <= axes:
        return "+z" if _sign_positive(axis_a, axis_b, "z") else "-z"
    if {"y", "z"} <= axes:
        return "+x" if _sign_positive(axis_a, axis_b, "x") else "-x"
    # {"z", "x"}
    return "+y" if _sign_positive(axis_a, axis_b, "y") else "-y"


def _sign_positive(first: str, second: str, target: str) -> bool:
    """Return True when (first × second) . target > 0 using the RHR table.

    +x × +y = +z,   +y × +z = +x,   +z × +x = +y
    +y × +x = -z,   +z × +y = -x,   +x × +z = -y
    Negating either input negates the result.
    """
    # Expand signs into ±1 for sign arithmetic
    s1 = 1 if first[0] == "+" else -1
    s2 = 1 if second[0] == "+" else -1
    a, b = first[1], second[1]
    # result sign = s1 * s2 * positive_cycle_sign
    cycle = {
        ("x", "y"): ("+z", 1), ("y", "z"): ("+x", 1), ("z", "x"): ("+y", 1),
        ("y", "x"): ("-z", -1), ("z", "y"): ("-x", -1), ("x", "z"): ("-y", -1),
    }
    _, outcome = cycle[(a, b)]
    return (s1 * s2 * outcome) > 0


@dataclass(frozen=True)
class CabinetFrame:
    """Maps semantic cabinet directions ("front", "top", ...) to world axes.

    Provide exactly two of {front, top, right} and the rest are derived via
    the right-hand rule.  The standard constructor takes front + top.

    Attributes
    ----------
    front : str
        The world axis toward which the cabinet front (door face) points.
    top : str
        The world axis toward which the cabinet top points.
    back, bottom, right, left : str
        Derived from front × top.
    """

    front: str = "+y"
    top: str = "+z"

    def __post_init__(self) -> None:
        if not (
            self.front.startswith(("+", "-"))
            and self.top.startswith(("+", "-"))
            and self.front[1] in "xyz"
            and self.top[1] in "xyz"
            and self.front[1] != self.top[1]
        ):
            raise ValueError(
                f"Invalid CabinetFrame: front={self.front}, top={self.top}. "
                f"Must be signed axes (±x, ±y, ±z) on different cardinal axes."
            )

    @property
    def back(self) -> str:
        return _negate(self.front)

    @property
    def bottom(self) -> str:
        return _negate(self.top)

    @property
    def right(self) -> str:
        return _cross(self.front, self.top)

    @property
    def left(self) -> str:
        return _negate(self.right)

    def axis_char(self, signed_axis: str) -> str:
        """Return the axis letter (x/y/z) without sign."""
        return signed_axis[1]
````

## File: domain/skills/furniture-panel-planning/scripts/furniture_panel_planning/cabinet_panel_planner.py
````python
"""Turn a confirmed cabinet layout into physical panel placements.

Now delegates to the topology solver instead of hardcoding panel positions.
The topology YAML defines what panels exist and their semantic faces;
the solver computes exact positions, sizes, and face directions.
"""

from __future__ import annotations

from .panel_models import PanelPlacement
from .panel_spec import FurnitureSpec
from .structure_planning import CabinetStructure
from .topology_solver import solve_panel_placements


def build_cabinet_panels(
    spec: FurnitureSpec,
    layout: CabinetStructure,
) -> list[PanelPlacement]:
    """Stage 3: create physical panel roles, sizes, and placements.

    Delegates to the universal topology solver.  All panel positions,
    dimensions, and face directions are computed from the topology YAML
    for the spec's furniture type.
    """
    return solve_panel_placements(spec, layout)
````

## File: domain/skills/furniture-panel-planning/scripts/furniture_panel_planning/design_optimization.py
````python
"""Bounded multi-objective candidate generation for the panel-planning stage."""

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from itertools import product
import json
from math import isfinite
from typing import Any, Mapping

from furniture_design_intent.design_intent import DesignIntent

from .panel_pipeline import plan_panel_stage
from .panel_spec import PANEL_PARAMETER_FIELDS


SUPPORTED_OBJECTIVES = frozenset(
    {
        "material_volume_m3",
        "total_panel_area_m2",
        "negative_internal_volume_m3",
        "complexity_score",
    }
)


def _digest(value: Any) -> str:
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _normalize_domains(raw: Any) -> dict[str, list[Any]]:
    if not isinstance(raw, Mapping) or not raw:
        raise ValueError("optimization variables must be a non-empty object")
    domains: dict[str, list[Any]] = {}
    for name, values in raw.items():
        if name not in PANEL_PARAMETER_FIELDS:
            raise ValueError(f"optimization variable is not owned by panels_planned: {name}")
        if not isinstance(values, list) or not values:
            raise ValueError(f"optimization variable {name} requires a non-empty choices list")
        if len(values) > 50:
            raise ValueError(f"optimization variable {name} exceeds 50 choices")
        normalized: list[Any] = []
        for value in values:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if not isfinite(float(value)):
                    raise ValueError(f"optimization choice is not finite: {name}")
            elif not isinstance(value, str):
                raise ValueError(f"optimization choice must be numeric or text: {name}")
            if value not in normalized:
                normalized.append(value)
        domains[str(name)] = normalized
    return domains


def _metrics(output: Mapping[str, Any]) -> dict[str, float]:
    panels = output["panels"]
    structure = output["structure"]
    material_volume = sum(
        float(item["size_x"])
        * float(item["size_y"])
        * float(item["size_z"])
        * int(item.get("quantity", 1))
        for item in panels
    ) / 1_000_000_000.0
    total_area = sum(
        float(item["size_x"])
        * float(item["size_y"])
        * int(item.get("quantity", 1))
        for item in panels
    ) / 1_000_000.0
    internal_depth = float(structure["internal_y_end"]) - float(structure["internal_y_start"])
    internal_volume = (
        float(structure["internal_width"])
        * float(structure["internal_height"])
        * internal_depth
        / 1_000_000_000.0
    )
    back_penalty = {"groove": 2.0, "insert": 1.0, "cover": 1.5}.get(
        str(structure["back_mount"]), 2.0
    )
    return {
        "material_volume_m3": material_volume,
        "total_panel_area_m2": total_area,
        "negative_internal_volume_m3": -internal_volume,
        "complexity_score": float(len(panels)) + back_penalty,
        "internal_width_mm": float(structure["internal_width"]),
        "internal_height_mm": float(structure["internal_height"]),
        "internal_depth_mm": internal_depth,
        "internal_volume_m3": internal_volume,
    }


def _feasible(metrics: Mapping[str, float], constraints: Mapping[str, Any]) -> bool:
    checks = {
        "min_internal_width_mm": metrics["internal_width_mm"]
        >= float(constraints.get("min_internal_width_mm", float("-inf"))),
        "min_internal_height_mm": metrics["internal_height_mm"]
        >= float(constraints.get("min_internal_height_mm", float("-inf"))),
        "min_internal_depth_mm": metrics["internal_depth_mm"]
        >= float(constraints.get("min_internal_depth_mm", float("-inf"))),
        "max_material_volume_m3": metrics["material_volume_m3"]
        <= float(constraints.get("max_material_volume_m3", float("inf"))),
    }
    known = set(checks)
    unknown = sorted(set(constraints) - known)
    if unknown:
        raise ValueError("unsupported optimization constraints: " + ", ".join(unknown))
    return all(checks[name] for name in constraints)


def _dominates(a: Mapping[str, Any], b: Mapping[str, Any], objectives: list[str]) -> bool:
    a_values = [float(a["objectives"][name]) for name in objectives]
    b_values = [float(b["objectives"][name]) for name in objectives]
    return all(x <= y for x, y in zip(a_values, b_values)) and any(
        x < y for x, y in zip(a_values, b_values)
    )


def _pareto(candidates: list[dict[str, Any]], objectives: list[str]) -> list[dict[str, Any]]:
    front = [
        candidate
        for candidate in candidates
        if not any(
            other is not candidate and _dominates(other, candidate, objectives)
            for other in candidates
        )
    ]
    return sorted(
        front,
        key=lambda item: tuple(float(item["objectives"][name]) for name in objectives),
    )


def _select_front(
    candidates: list[dict[str, Any]],
    objectives: list[str],
    requested_engine: str,
) -> tuple[list[dict[str, Any]], str, str | None]:
    if requested_engine not in {"auto", "exact", "pymoo"}:
        raise ValueError("engine must be auto, exact, or pymoo")
    if requested_engine in {"auto", "pymoo"} and candidates:
        try:
            import numpy as np
            from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting
        except ImportError:
            if requested_engine == "pymoo":
                return [], "pymoo", (
                    "pymoo is not installed; install the furniture-analysis extra"
                )
        else:
            objective_matrix = np.asarray(
                [
                    [float(item["objectives"][name]) for name in objectives]
                    for item in candidates
                ],
                dtype=float,
            )
            indexes = NonDominatedSorting().do(
                objective_matrix,
                only_non_dominated_front=True,
            )
            front = [candidates[int(index)] for index in indexes]
            return (
                sorted(
                    front,
                    key=lambda item: tuple(
                        float(item["objectives"][name]) for name in objectives
                    ),
                ),
                "pymoo-non-dominated-sorting",
                None,
            )
    return _pareto(candidates, objectives), "exact-discrete-pareto", None


def optimize_panel_design(
    intent: DesignIntent,
    panel_output: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Generate bounded Pareto candidates without mutating confirmed output."""

    domains = _normalize_domains(config.get("variables"))
    raw_objectives = config.get("objectives")
    if not isinstance(raw_objectives, list) or not raw_objectives:
        raise ValueError("optimization objectives must be an explicit non-empty list")
    objectives = [str(item) for item in raw_objectives]
    unknown_objectives = sorted(set(objectives) - SUPPORTED_OBJECTIVES)
    if unknown_objectives or not objectives:
        raise ValueError("unsupported or empty objectives: " + ", ".join(unknown_objectives))
    constraints = config.get("constraints", {})
    if not isinstance(constraints, Mapping):
        raise ValueError("constraints must be an object")
    max_evaluations = int(config.get("max_evaluations", 10_000))
    if not 1 <= max_evaluations <= 10_000:
        raise ValueError("max_evaluations must be between 1 and 10000")
    combination_count = 1
    for values in domains.values():
        combination_count *= len(values)
    if combination_count > max_evaluations:
        raise ValueError(
            f"choice grid has {combination_count} combinations, above "
            f"max_evaluations={max_evaluations}"
        )

    base_spec = panel_output.get("spec")
    if not isinstance(base_spec, Mapping):
        raise ValueError("panel output requires a spec object")
    base_options = {
        name: base_spec[name]
        for name in PANEL_PARAMETER_FIELDS
        if name in base_spec
    }
    names = list(domains)
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for values in product(*(domains[name] for name in names)):
        changes = dict(zip(names, values))
        options = {**base_options, **changes}
        try:
            output = plan_panel_stage(intent, options)
            metrics = _metrics(output)
        except (KeyError, TypeError, ValueError) as exc:
            rejected.append({"parameters": changes, "reason": str(exc)})
            continue
        if not _feasible(metrics, constraints):
            rejected.append({"parameters": changes, "reason": "constraint violation"})
            continue
        candidates.append(
            {
                "parameters": changes,
                "resolved_parameters": {
                    name: output["spec"][name]
                    for name in PANEL_PARAMETER_FIELDS
                    if name in output["spec"]
                },
                "objectives": {name: metrics[name] for name in objectives},
                "metrics": metrics,
                "stage_output_sha256": _digest(output),
            }
        )

    front, engine, unavailable_reason = _select_front(
        candidates,
        objectives,
        str(config.get("engine", "auto")).strip().lower(),
    )
    max_candidates = int(config.get("max_candidates", 25))
    if not 1 <= max_candidates <= 100:
        raise ValueError("max_candidates must be between 1 and 100")
    result = {
        "analysis": "panel_optimization",
        "status": "unavailable" if unavailable_reason else "completed",
        "engine": engine,
        "upstream_method": (
            "bounded exhaustive evaluation followed by non-dominated sorting"
        ),
        "source_panel_output_sha256": _digest(panel_output),
        "objectives": objectives,
        "constraints": dict(constraints),
        "evaluated": combination_count,
        "feasible": len(candidates),
        "rejected": rejected[:25],
        "pareto_candidate_count": len(front),
        "candidates": front[:max_candidates],
        "truncated": len(front) > max_candidates,
        "application_rule": (
            "materialize the selected parameters, then call "
            "revise_stage_output(); never overwrite the source stage"
        ),
    }
    if unavailable_reason:
        result["reason"] = unavailable_reason
    return result


def materialize_optimization_candidate(
    intent: DesignIntent,
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    parameters = candidate.get("resolved_parameters")
    if not isinstance(parameters, Mapping):
        raise ValueError("candidate requires resolved_parameters")
    return plan_panel_stage(intent, parameters)
````

## File: domain/skills/furniture-panel-planning/scripts/furniture_panel_planning/joint_topology.py
````python
"""连接拓扑 — 板件之间的面-边邻接关系。

不依赖板件名称（"side"/"top" 等），只根据几何位置 + 语义面
推导出哪块板的哪个面碰到了哪块板的哪个端面。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .panel_models import PanelPlacement


@dataclass(frozen=True)
class PanelJoint:
    """一条面-边邻接：female 的面碰 male 的端面。

    对于三合一连接件：
    - female（面接触方）→ 预埋螺母孔
    - male  （边接触方）→ 连接杆孔 + 偏心轮孔
    """

    female_id: str   # 面板 ID（面被接触的那块板）
    male_id: str     # 面板 ID（端面顶住面的那块板）
    face: str        # female 的哪个语义面被接触（inner_face 的值，如 "+x"）
    edge_axis: str   # male 的端面所在轴（"x"/"y"/"z"）
    edge_sign: int   # male 的端面方向：+1=轴正端，-1=轴负端
    male_z: float    # male 面板厚度中心线的 Z 坐标（几何基准，非五金孔位）
    male_has_cam: bool = False  # male 是否有 cam_face（三合一标志）
    male_cam_face: str | None = None  # male 的偏心轮安装面（"+z"/"-z"）
    male_size_z: float = 0.0           # male 在 z 方向的尺寸（横板=板厚）


# ── 容差 ──────────────────────────────────────────────────────────
_SNAP_TOLERANCE = 0.5  # mm，面板端面与另一块板面的对齐容差


def _overlap(a_min: float, a_max: float, b_min: float, b_max: float) -> bool:
    """两个区间是否有交集（含容差）。"""
    return a_max > b_min - _SNAP_TOLERANCE and b_max > a_min - _SNAP_TOLERANCE


def _face_position(panel: PanelPlacement, face_dir: str) -> float:
    """面板某个语义面在世界坐标系中的位置。

    face_dir 如 "+x"→面板 x 最大值，"-x"→面板 x 最小值。
    """
    if face_dir == "+x":
        return panel.pos_x + panel.size_x
    if face_dir == "-x":
        return panel.pos_x
    if face_dir == "+y":
        return panel.pos_y + panel.size_y
    if face_dir == "-y":
        return panel.pos_y
    if face_dir == "+z":
        return panel.pos_z + panel.size_z
    if face_dir == "-z":
        return panel.pos_z
    return 0.0


def _axis_char(face_dir: str) -> str:
    """如 "+x" → "x"。"""
    return face_dir[1] if len(face_dir) >= 2 else ""


def _axis_sign(face_dir: str) -> int:
    """如 "+x" → +1。"""
    return 1 if face_dir.startswith("+") else -1


def _axis_range(panel: PanelPlacement, axis: str) -> tuple[float, float]:
    """面板在指定轴上的区间 [min, max]。"""
    if axis == "x":
        return (panel.pos_x, panel.pos_x + panel.size_x)
    if axis == "y":
        return (panel.pos_y, panel.pos_y + panel.size_y)
    return (panel.pos_z, panel.pos_z + panel.size_z)


def compute_joints(placements: Sequence[PanelPlacement]) -> list[PanelJoint]:
    """从板件列表推导所有面-边邻接。

    对每块有 inner_face 的板（female 候选），
    找出所有端面顶在该面上的板（male 候选）。
    """
    joints: list[PanelJoint] = []
    candidates = [p for p in placements if p.inner_face]

    def _is_drawer(panel: PanelPlacement) -> bool:
        return "drawer" in panel.panel_type

    for female in candidates:
        face_dir = female.inner_face
        face_axis = _axis_char(face_dir)
        face_pos = _face_position(female, face_dir)

        # 待检查的轴线（female 面法向之外的另外两轴）
        other_axes = [a for a in ("x", "y", "z") if a != face_axis]

        for male in placements:
            if male.id == female.id:
                continue
            # 抽屉是滑动子装配：抽屉↔柜体的接触（如抽屉侧板贴柜体侧板、
            # 抽屉前板底边搁柜体底板）不是连接，排除跨装配 joint。
            if _is_drawer(female) != _is_drawer(male):
                continue
            # male 必须在这个面上有端面才可能接触
            male_min, male_max = _axis_range(male, face_axis)

            if not (
                abs(male_min - face_pos) <= _SNAP_TOLERANCE
                or abs(male_max - face_pos) <= _SNAP_TOLERANCE
            ):
                continue

            # 另外两个轴必须重叠
            overlap_all = True
            for axis in other_axes:
                f_min, f_max = _axis_range(female, axis)
                m_min, m_max = _axis_range(male, axis)
                if not _overlap(f_min, f_max, m_min, m_max):
                    overlap_all = False
                    break

            if not overlap_all:
                continue

            # 确定 male 的端面方向
            if abs(male_min - face_pos) <= _SNAP_TOLERANCE:
                edge_sign = -1
            else:
                edge_sign = +1

            joints.append(
                PanelJoint(
                    female_id=female.id,
                    male_id=male.id,
                    face=face_dir,
                    edge_axis=face_axis,
                    edge_sign=edge_sign,
                    male_z=male.pos_z + male.size_z / 2.0,  # 几何基准：厚度中心线 Z
                    male_has_cam=bool(male.cam_face),  # 有 cam_face 才是三合一
                    male_cam_face=male.cam_face,  # 偏心轮安装面，manufacturing 用于算连接杆轴线高度
                    male_size_z=male.size_z,       # male 在 z 方向的尺寸（横板=板厚）
                )
            )

    return joints


def is_female(panel_id: str, joints: Sequence[PanelJoint]) -> bool:
    """该板是否是某个连接的 female（面接触方）。"""
    return any(j.female_id == panel_id for j in joints)


def is_male(panel_id: str, joints: Sequence[PanelJoint]) -> bool:
    """该板是否是某个连接的 male（边接触方）。"""
    return any(j.male_id == panel_id for j in joints)


def female_joints(panel_id: str, joints: Sequence[PanelJoint]) -> list[PanelJoint]:
    """该板作为 female 参与的所有连接。"""
    return [j for j in joints if j.female_id == panel_id]


def male_joints(panel_id: str, joints: Sequence[PanelJoint]) -> list[PanelJoint]:
    """该板作为 male 参与的所有连接。"""
    return [j for j in joints if j.male_id == panel_id]
````

## File: domain/skills/furniture-panel-planning/scripts/furniture_panel_planning/panel_face.py
````python
"""PanelFace — semantic face directions for a single furniture panel.

Each panel in the cabinet has well-defined faces:
- inner_face: the face pointing into the cabinet interior
- outer_face: the face pointing out of the cabinet
- cam_face:   the face where the eccentric wheel is accessible (horizontal panels only)

Connectors use these semantic directions instead of guessing from panel position.
"""

from __future__ import annotations

from dataclasses import dataclass


def _negate(axis: str) -> str:
    """Flip a signed axis: "+x"→"-x", "-y"→"+y"."""
    if axis and axis[0] in "+-":
        return f"{'+' if axis[0] == '-' else '-'}{axis[1]}"
    return axis


@dataclass(frozen=True)
class PanelFace:
    """Semantic face directions for a single panel.

    Attributes
    ----------
    inner : str
        Direction (signed world axis) from the panel's interior toward the
        cabinet interior.  E.g. left side panel → "+x", right → "-x".
    outer : str
        Opposite of inner.
    cam : str or None
        Face where the eccentric wheel is installed and accessible for
        tightening.  Typically the bottom face of horizontal panels ("-z").
        None for vertical panels (side panels).
    """

    inner: str
    outer: str
    cam: str | None = None

    @property
    def nut_direction(self) -> str:
        """Direction to drill pre-embedded nut holes.

        Nut is installed from the inner face, drilling inward into the panel.
        So the drilling direction is opposite to the inner face.
        """
        return _negate(self.inner)

    @property
    def cup_direction(self) -> str:
        """Direction to drill hinge cup holes.

        Hinge cup is drilled from the inner face INTO the door panel, so the
        drilling direction is opposite to the inner face (direction 语义统一
        为钻入方向，见 coordinate-naming.md)。
        """
        return _negate(self.inner)

    @property
    def rod_direction(self) -> str:
        """Direction to drill connecting rod holes.

        Rod is inserted from the edge of the panel.  For the left edge of
        a horizontal panel, the rod goes +x into the panel.  For the right
        edge, it goes -x.  This is panel-edge-dependent, not face-dependent,
        so callers should prefer nut_direction / cam_direction for trinity.
        """
        return _negate(self.inner)

    @property
    def cam_direction(self) -> str:
        """Direction to drill eccentric wheel holes.

        Wheel is installed from the cam_face INTO the panel, so the drilling
        direction is opposite to the cam_face.  If cam_face is "-z", drilling
        goes into the panel in the +z direction.
        """
        if self.cam is None:
            return _negate(self.inner)  # fallback — shouldn't happen for horizontal panels
        return _negate(self.cam)
````

## File: domain/skills/furniture-panel-planning/scripts/furniture_panel_planning/panel_models.py
````python
"""Semantic panel contracts owned by the panels_planned stage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass
class PanelPlacement:
    """One physical panel with final size and assembly placement."""

    id: str
    name: str
    panel_type: str
    size_x: float
    size_y: float
    size_z: float
    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0
    quantity: int = 1
    material_role: str = "carcass"
    orientation: str = "xyz"
    depends_on: list[str] = field(default_factory=list)
    note: str = ""
    door_hinge_side: str | None = None   # "left" / "right", only for door panels
    door_overlay: str | None = None      # "full" / "half" / "inset", only for door panels
    inner_face: str = ""                 # panel face pointing toward cabinet interior
    outer_face: str = ""                 # panel face pointing toward cabinet exterior
    cam_face: str | None = None          # eccentric wheel accessible face, e.g. "-z"
    joints: list = field(default_factory=list)  # list[PanelJoint], populated after solve

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PanelPlacement":
        """Restore nested joint contracts after a stage-output JSON round trip."""

        from .joint_topology import PanelJoint

        values = dict(data)
        raw_joints = values.get("joints", [])
        if not isinstance(raw_joints, list):
            raise ValueError("panel joints must be a list")
        values["joints"] = [
            item if isinstance(item, PanelJoint) else PanelJoint(**item)
            for item in raw_joints
        ]
        return cls(**values)
````

## File: domain/skills/furniture-panel-planning/scripts/furniture_panel_planning/panel_pipeline.py
````python
"""Serializable entrypoint for construction and physical panels."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from furniture_design_intent.design_intent import DesignIntent

from .panel_planning import plan_panels
from .panel_spec import FurnitureSpec
from .structure_planning import CabinetStructure


def plan_panel_stage(
    intent: DesignIntent,
    options: Mapping[str, Any],
) -> dict[str, Any]:
    requested_back_mount = options.get("back_mount") if isinstance(options, Mapping) else None
    spec = FurnitureSpec.from_intent(intent, options)
    structure = CabinetStructure.from_spec(spec)
    panels = plan_panels(spec, structure)
    return {
        "spec": asdict(spec),
        "structure": asdict(structure),
        "back_mount_resolution": {
            "requested": requested_back_mount,
            "effective": spec.back_mount,
        },
        "panels": [asdict(item) for item in panels],
    }
````

## File: domain/skills/furniture-panel-planning/scripts/furniture_panel_planning/panel_rules.py
````python
"""Stage-owned rules for repeated cabinet panel members."""

from __future__ import annotations


def resolve_toe_kick_support_count(
    explicit: int | None,
    cabinet_width: float,
) -> int:
    """Return an explicit count or calculate one when the proposal used null."""
    if explicit is not None:
        return explicit
    if cabinet_width < 600:
        return 0
    return 1 + int((cabinet_width - 600) // 300)


def toe_kick_support_clear_spacing(
    internal_width: float,
    support_count: int,
    board_thickness: float,
) -> float:
    """Return equal clear spacing between supports and both side panels."""
    return (
        internal_width - support_count * board_thickness
    ) / (support_count + 1)


def resolve_back_rail_count(
    back_mount: str,
    internal_height: float,
    back_rail_height: float,
) -> int:
    """Return the repository back-rail count for a grooved back."""
    if (
        back_mount != "groove"
        or internal_height <= 0
        or back_rail_height <= 0
    ):
        return 0
    return int(internal_height // 500)


def back_rail_clear_spacing(
    internal_height: float,
    rail_count: int,
    rail_height: float,
) -> float:
    """Return the solver's equal clear spacing for back rails."""
    if rail_count <= 0:
        return internal_height
    return (
        internal_height - rail_count * rail_height
    ) / rail_count


def resolve_door_hinge_side(
    door_count: int,
    door_index: int,
    single_door_side: str | None,
) -> str | None:
    """Return the admitted hinge side for one door in left-to-right order."""
    if door_index < 0 or door_index >= door_count:
        raise ValueError("door_index must identify an existing door")
    if door_count == 1:
        return single_door_side
    if door_count == 2:
        return "left" if door_index == 0 else "right"
    return None
````

## File: domain/skills/furniture-panel-planning/scripts/furniture_panel_planning/quantitative_audit.py
````python
"""Furniture-specific dimensional and uncertainty audit for panel-stage output."""

from __future__ import annotations

from math import isfinite, sqrt
from typing import Any, Mapping


_LINEAR_UNIT_TO_MM = {
    "mm": 1.0,
    "millimeter": 1.0,
    "millimetre": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "in": 25.4,
    "inch": 25.4,
}


def _unit_engine() -> tuple[Any | None, str]:
    try:
        from pint import UnitRegistry
    except ImportError:
        return None, "bounded-linear-conversion"
    return UnitRegistry(), "pint"


def _to_mm(value: Any, unit: str, registry: Any | None) -> float:
    number = float(value)
    normalized = str(unit).strip().lower()
    if registry is not None:
        return float((number * registry(normalized)).to("mm").magnitude)
    if normalized not in _LINEAR_UNIT_TO_MM:
        raise ValueError(
            f"unit {unit!r} requires Pint; bounded fallback supports: "
            + ", ".join(sorted(_LINEAR_UNIT_TO_MM))
        )
    return number * _LINEAR_UNIT_TO_MM[normalized]


def _standard_uncertainty_mm(
    record: Mapping[str, Any], registry: Any | None
) -> tuple[float, dict[str, Any]]:
    unit = str(record.get("unit", "mm"))
    stated = _to_mm(record.get("uncertainty", 0.0), unit, registry)
    if stated < 0 or not isfinite(stated):
        raise ValueError("uncertainty must be a finite non-negative number")
    kind = str(record.get("kind", "standard")).strip().lower()
    distribution = str(record.get("distribution", "normal")).strip().lower()
    divisor = 1.0
    if kind == "expanded":
        divisor = float(record.get("coverage_factor", 0.0))
        if divisor <= 0:
            raise ValueError("expanded uncertainty requires coverage_factor > 0")
    elif kind == "limit":
        divisors = {
            "rectangular": sqrt(3.0),
            "triangular": sqrt(6.0),
            "arcsine": sqrt(2.0),
        }
        if distribution not in divisors:
            raise ValueError(
                "limit uncertainty distribution must be rectangular, triangular, or arcsine"
            )
        divisor = divisors[distribution]
    elif kind != "standard":
        raise ValueError("uncertainty kind must be standard, expanded, or limit")
    dof = record.get("dof")
    if dof is not None and float(dof) <= 0:
        raise ValueError("degrees of freedom must be positive")
    standard = stated / divisor
    return standard, {
        "stated_uncertainty": stated,
        "standard_uncertainty_mm": standard,
        "kind": kind,
        "distribution": distribution,
        "dof": dof,
        "coverage_factor": record.get("coverage_factor"),
    }


def audit_panel_quantities(
    panel_output: Mapping[str, Any],
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Audit units, finite geometry, derived clearances, and optional GUM inputs.

    The function never edits ``panel_output``. Unspecified uncertainty inputs are
    treated as unknown, not as zero, and no conformity decision is inferred.
    """

    config = dict(config or {})
    spec = panel_output.get("spec")
    structure = panel_output.get("structure")
    panels = panel_output.get("panels")
    if not isinstance(spec, Mapping) or not isinstance(structure, Mapping):
        raise ValueError("panel output requires spec and structure objects")
    if not isinstance(panels, list):
        raise ValueError("panel output requires a panels list")

    registry, engine = _unit_engine()
    issues: list[dict[str, str]] = []
    checked_dimensions = 0
    for namespace, values in (("spec", spec), ("structure", structure)):
        for name, raw in values.items():
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                continue
            checked_dimensions += 1
            value = float(raw)
            if not isfinite(value):
                issues.append(
                    {
                        "severity": "error",
                        "path": f"{namespace}.{name}",
                        "message": "dimension is not finite",
                    }
                )
    for index, raw_panel in enumerate(panels):
        if not isinstance(raw_panel, Mapping):
            issues.append(
                {
                    "severity": "error",
                    "path": f"panels[{index}]",
                    "message": "panel is not an object",
                }
            )
            continue
        for axis in ("size_x", "size_y", "size_z"):
            checked_dimensions += 1
            try:
                value = float(raw_panel[axis])
            except (KeyError, TypeError, ValueError):
                issues.append(
                    {
                        "severity": "error",
                        "path": f"panels[{index}].{axis}",
                        "message": "missing numeric dimension",
                    }
                )
                continue
            if not isfinite(value) or value <= 0:
                issues.append(
                    {
                        "severity": "error",
                        "path": f"panels[{index}].{axis}",
                        "message": "panel dimension must be finite and positive",
                    }
                )

    models = {
        "internal_width": (
            float(spec["width"]) - 2.0 * float(spec["board_thickness"]),
            {"width": 1.0, "board_thickness": -2.0},
        ),
        "internal_height": (
            float(spec["height"])
            - float(structure["toe_kick_height"])
            - 2.0 * float(spec["board_thickness"]),
            {"height": 1.0, "toe_kick_height": -1.0, "board_thickness": -2.0},
        ),
        "internal_depth": (
            float(structure["internal_y_end"]) - float(structure["internal_y_start"]),
            {
                "depth": 1.0,
                "door_thickness": -1.0,
                "door_hinge_gap": -1.0,
                "back_thickness": -1.0,
                **(
                    {"back_offset": -1.0}
                    if str(structure["back_mount"]) != "cover"
                    else {}
                ),
            },
        ),
    }
    for name, (expected, _) in models.items():
        actual_key = name if name != "internal_depth" else None
        if actual_key and abs(float(structure[actual_key]) - expected) > 1e-6:
            issues.append(
                {
                    "severity": "error",
                    "path": f"structure.{actual_key}",
                    "message": (
                        "derived clearance does not match its measurement model"
                    ),
                }
            )
        if expected <= 0:
            issues.append(
                {
                    "severity": "error",
                    "path": f"structure.{name}",
                    "message": "derived clearance is not positive",
                }
            )

    raw_uncertainties = config.get("uncertainties", {})
    if not isinstance(raw_uncertainties, Mapping):
        raise ValueError("uncertainties must be an object keyed by spec quantity")
    uncertainties: dict[str, float] = {}
    uncertainty_inputs: dict[str, Any] = {}
    for name, raw in raw_uncertainties.items():
        if name not in spec and name not in structure:
            raise ValueError(f"unknown uncertainty quantity: {name}")
        if not isinstance(raw, Mapping):
            raise ValueError(f"uncertainty input must be an object: {name}")
        standard, normalized = _standard_uncertainty_mm(raw, registry)
        uncertainties[str(name)] = standard
        uncertainty_inputs[str(name)] = normalized

    raw_coverage_factor = config.get("coverage_factor")
    coverage_factor = (
        float(raw_coverage_factor) if raw_coverage_factor is not None else None
    )
    if coverage_factor is not None and (
        coverage_factor <= 0 or not isfinite(coverage_factor)
    ):
        raise ValueError("coverage_factor must be finite and positive")
    measurement_models: list[dict[str, Any]] = []
    for name, (estimate, sensitivities) in models.items():
        used = {
            key: coefficient
            for key, coefficient in sensitivities.items()
            if key in uncertainties
        }
        combined = sqrt(
            sum((coefficient * uncertainties[key]) ** 2 for key, coefficient in used.items())
        ) if used else None
        variance_contributions = {
            key: (coefficient * uncertainties[key]) ** 2
            for key, coefficient in used.items()
        }
        measurement_models.append(
            {
                "name": name,
                "estimate_mm": estimate,
                "sensitivity_coefficients": sensitivities,
                "variance_contributions_mm2": variance_contributions,
                "standard_uncertainty_mm": combined,
                "expanded_uncertainty_mm": (
                    combined * coverage_factor
                    if combined is not None and coverage_factor is not None
                    else None
                ),
                "coverage_factor": (
                    coverage_factor if combined is not None else None
                ),
            }
        )

    return {
        "analysis": "panel_unit_audit",
        "status": "completed",
        "passed": not any(item["severity"] == "error" for item in issues),
        "engine": engine,
        "canonical_unit": "mm",
        "checked_dimensions": checked_dimensions,
        "uncertainty_inputs": uncertainty_inputs,
        "measurement_models": measurement_models,
        "issues": issues,
        "limitations": [
            "correlations are not inferred; supplied inputs are treated as independent",
            "no conformity decision is made without an explicit acceptance rule",
            "missing uncertainty inputs remain unknown rather than being treated as exact",
            "expanded uncertainty is omitted unless coverage_factor is explicitly supplied",
        ],
    }
````

## File: domain/skills/furniture-panel-planning/scripts/furniture_panel_planning/validation.py
````python
"""Validation owned by the panel-planning stage."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from furniture_delivery_validation.validation import ValidationReport
from furniture_design_intent.design_intent import DesignIntent

from .panel_models import PanelPlacement
from .panel_spec import FurnitureSpec, resolve_back_mount
from .panel_rules import (
    back_rail_clear_spacing,
    resolve_back_rail_count,
    resolve_door_hinge_side,
    resolve_toe_kick_support_count,
    toe_kick_support_clear_spacing,
)
from .structure_planning import CabinetStructure


def validate_panel_output(
    confirmed_intent: DesignIntent,
    output: Mapping[str, Any],
) -> ValidationReport:
    """Validate the complete construction-and-panels stage checkpoint."""
    report = ValidationReport(stage="panels_planned")
    try:
        raw_spec = output.get("spec")
        raw_structure = output.get("structure")
        raw_panels = output.get("panels")
        if not isinstance(raw_spec, Mapping):
            raise ValueError("panel stage output requires spec")
        if not isinstance(raw_structure, Mapping):
            raise ValueError("panel stage output requires structure")
        if not isinstance(raw_panels, list):
            raise ValueError("panel stage output requires panels")
        spec = FurnitureSpec.from_dict(raw_spec)
        structure = CabinetStructure(**raw_structure)
        panels = [PanelPlacement.from_dict(item) for item in raw_panels]
    except (TypeError, ValueError) as exc:
        report.add_error("INVALID_PANEL_STAGE_OUTPUT", str(exc))
        return report

    structure_report = validate_structure(confirmed_intent, spec, structure)
    panel_report = validate_panels(spec, structure, panels)
    report.issues.extend(structure_report.issues)
    report.issues.extend(panel_report.issues)

    resolution = output.get("back_mount_resolution")
    if not isinstance(resolution, Mapping):
        report.add_error(
            "MISSING_BACK_MOUNT_RESOLUTION",
            "panel stage must show requested and effective back mount",
            "back_mount_resolution",
        )
    else:
        try:
            expected_mount = resolve_back_mount(
                resolution.get("requested"),
                spec.back_thickness,
                spec.board_thickness,
            )
        except ValueError as exc:
            report.add_error(
                "INVALID_BACK_MOUNT_RESOLUTION",
                str(exc),
                "back_mount_resolution.requested",
            )
        else:
            if (
                resolution.get("effective") != spec.back_mount
                or expected_mount != spec.back_mount
            ):
                report.add_error(
                    "BACK_MOUNT_RESOLUTION_MISMATCH",
                    "requested/effective back mount must match the admitted spec",
                    "back_mount_resolution",
                )
    return report


def validate_structure(
    confirmed_intent: DesignIntent | Any,
    spec: FurnitureSpec,
    structure: CabinetStructure,
) -> ValidationReport:
    """Validate exact geometry against the confirmed finished envelope."""
    report = ValidationReport(stage="panels_planned")
    if isinstance(confirmed_intent, DesignIntent):
        confirmed = (
            confirmed_intent.furniture_type,
            confirmed_intent.overall_size.width_mm,
            confirmed_intent.overall_size.depth_mm,
            confirmed_intent.overall_size.height_mm,
        )
    else:
        # Compatibility for direct callers that previously passed the retired
        # serial CabinetLayout checkpoint.
        confirmed = (
            getattr(confirmed_intent, "furniture_type", None),
            getattr(confirmed_intent, "width", None),
            getattr(confirmed_intent, "depth", None),
            getattr(confirmed_intent, "height", None),
        )
    if (
        spec.furniture_type,
        spec.width,
        spec.depth,
        spec.height,
    ) != confirmed:
        report.add_error(
            "PANEL_SPEC_INTENT_MISMATCH",
            "panel construction must preserve the confirmed finished envelope",
        )

    for name in ("board_thickness", "back_thickness", "door_thickness"):
        if getattr(spec, name) <= 0:
            report.add_error(
                "INVALID_PANEL_THICKNESS",
                f"{name} must be positive",
                name,
            )
    for name in (
        "toe_kick_height",
        "back_offset",
        "door_margin",
        "door_hinge_gap",
        "toe_kick_reveal_front",
        "toe_kick_reveal_back",
    ):
        if getattr(spec, name) < 0:
            report.add_error(
                "INVALID_PANEL_INPUT",
                f"{name} cannot be negative",
                name,
            )
    if spec.back_mount == "groove":
        if spec.groove_depth <= 0:
            report.add_error(
                "INVALID_GROOVE_DEPTH",
                "groove_depth must be positive",
                "groove_depth",
            )
        if spec.groove_clearance < 0:
            report.add_error(
                "INVALID_GROOVE_CLEARANCE",
                "groove_clearance cannot be negative",
                "groove_clearance",
            )
    if spec.back_rail_height < 0:
        report.add_error(
            "INVALID_BACK_RAIL_HEIGHT",
            "back_rail_height cannot be negative",
            "back_rail_height",
        )

    expected = CabinetStructure.from_spec(spec)
    if asdict(structure) != asdict(expected):
        report.add_error(
            "STRUCTURE_GEOMETRY_MISMATCH",
            "exact structure must be derived from the confirmed panel spec",
            "structure",
        )
    if min(
        structure.internal_width,
        structure.internal_height,
        structure.side_depth,
        structure.internal_y_end - structure.internal_y_start,
    ) <= 0:
        report.add_error(
            "NON_POSITIVE_INTERNAL_CLEARANCE",
            "panel construction leaves no positive internal clearance",
            "structure",
        )
    if not (
        0 <= structure.internal_x_start < structure.internal_x_end <= structure.width
        and 0 <= structure.internal_z_start < structure.internal_z_end <= structure.height
        and 0 <= structure.carcass_y_start < structure.carcass_y_end <= structure.depth
        and structure.carcass_y_start
        <= structure.internal_y_start
        < structure.internal_y_end
        <= structure.carcass_y_end
        and 0 <= structure.back_plane_y < structure.internal_y_start
    ):
        report.add_error(
            "STRUCTURE_REGION_OUTSIDE_ENVELOPE",
            "construction regions must stay inside the finished envelope",
            "structure",
        )
    if structure.toe_kick_height > 0 and not (
        structure.carcass_y_start
        <= structure.toe_kick_rear_y
        < structure.toe_kick_front_y
        <= structure.carcass_y_end
    ):
        report.add_error(
            "INVALID_TOE_KICK_REGION",
            "toe-kick region must have positive depth inside the cabinet",
            "structure",
        )
    return report


def validate_panels(
    spec: FurnitureSpec,
    layout: CabinetStructure | Any,
    panels: list[PanelPlacement],
) -> ValidationReport:
    report = ValidationReport(stage="panels_planned")
    if not isinstance(layout, CabinetStructure):
        spec = FurnitureSpec.from_dict(asdict(spec))
        layout = CabinetStructure.from_spec(spec)
    if not panels:
        report.add_error("EMPTY_PANEL_PLAN", "panel plan contains no panels")
        return report
    ids = {item.id for item in panels}
    if len(ids) != len(panels):
        report.add_error("DUPLICATE_PANEL_ID", "panel ids must be unique")
    panel_by_id = {item.id: item for item in panels}
    doors = sorted(
        (item for item in panels if item.panel_type == "door"),
        key=lambda item: (item.pos_x, item.id),
    )
    if len(doors) != spec.n_doors:
        report.add_error(
            "DOOR_COUNT_MISMATCH",
            "generated door count must match the admitted panel specification",
            "n_doors",
        )
    else:
        for index, door in enumerate(doors):
            expected_hinge_side = resolve_door_hinge_side(
                spec.n_doors,
                index,
                spec.door_hinge_side,
            )
            if door.door_hinge_side != expected_hinge_side:
                report.add_error(
                    "DOOR_HINGE_SIDE_MISMATCH",
                    f"{door.id} hinge side must match the admitted door topology",
                    door.id,
                )
    for item in panels:
        if item.quantity <= 0:
            report.add_error(
                "INVALID_PANEL_QUANTITY",
                f"{item.id} quantity must be positive",
                item.id,
            )
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
    carcass_ids = {
        "left_side_panel",
        "right_side_panel",
        "top_panel",
        "bottom_panel",
    }
    for panel_id in sorted(carcass_ids):
        panel = panel_by_id.get(panel_id)
        if panel is None:
            report.add_error(
                "MISSING_CARCASS_PANEL",
                f"panel plan is missing {panel_id}",
                panel_id,
            )
            continue
        if (
            abs(panel.pos_y - layout.carcass_y_start) > 1e-6
            or abs(panel.pos_y + panel.size_y - layout.carcass_y_end) > 1e-6
        ):
            report.add_error(
                "CARCASS_DEPTH_MISMATCH",
                f"{panel_id} must span the confirmed carcass depth",
                panel_id,
            )

    back = panel_by_id.get("back_panel")
    if back is None:
        report.add_error(
            "MISSING_BACK_PANEL",
            "supported cabinet panel plan requires a back panel",
            "back_panel",
        )
    else:
        if layout.back_mount == "groove":
            expected_back = (
                layout.internal_x_start - spec.groove_depth,
                layout.back_plane_y,
                layout.internal_z_start - spec.groove_depth,
                layout.internal_width + 2 * spec.groove_depth,
                spec.back_thickness,
                layout.internal_height + 2 * spec.groove_depth,
            )
        elif layout.back_mount == "insert":
            expected_back = (
                layout.internal_x_start,
                layout.back_plane_y,
                layout.internal_z_start,
                layout.internal_width,
                spec.back_thickness,
                layout.internal_height,
            )
        else:
            expected_back = (
                0.0,
                0.0,
                0.0,
                layout.width,
                spec.back_thickness,
                layout.height,
            )
        actual_back = (
            back.pos_x,
            back.pos_y,
            back.pos_z,
            back.size_x,
            back.size_y,
            back.size_z,
        )
        if any(
            abs(actual - expected) > 1e-6
            for actual, expected in zip(actual_back, expected_back)
        ):
            report.add_error(
                "BACK_MOUNT_GEOMETRY_MISMATCH",
                "back panel geometry does not match the confirmed mount mode",
                "back_panel",
            )
        if layout.back_mount == "cover":
            back_front_y = back.pos_y + back.size_y
            if any(
                panel_by_id[panel_id].pos_y < back_front_y - 1e-6
                for panel_id in carcass_ids
                if panel_id in panel_by_id
            ):
                report.add_error(
                    "COVER_BACK_OVERLAP",
                    "cover back must end before the cabinet carcass starts",
                    "back_panel",
                )

    support_panels = [
        item
        for item in panels
        if item.id.startswith("toe_kick_support_")
    ]
    expected_support_count = (
        resolve_toe_kick_support_count(
            spec.toe_kick_support_count,
            layout.width,
        )
        if layout.toe_kick_height > 0
        else 0
    )
    if expected_support_count < 0:
        report.add_error(
            "INVALID_TOE_KICK_SUPPORT_COUNT",
            "toe-kick support count cannot be negative",
            "toe_kick_support_count",
        )
    if len(support_panels) != max(expected_support_count, 0):
        report.add_error(
            "TOE_KICK_SUPPORT_COUNT_MISMATCH",
            "generated toe-kick support count does not match the panel rule",
            "toe_kick_support_count",
        )
    if expected_support_count > 0 and toe_kick_support_clear_spacing(
        layout.internal_width,
        expected_support_count,
        spec.board_thickness,
    ) <= 0:
        report.add_error(
            "NON_POSITIVE_TOE_KICK_SUPPORT_SPACING",
            "toe-kick supports leave no positive clear spacing",
            "toe_kick_support_count",
        )

    rail_panels = [
        item for item in panels if item.panel_type == "back_rail"
    ]
    expected_rail_count = resolve_back_rail_count(
        layout.back_mount,
        layout.internal_height,
        spec.back_rail_height,
    )
    if spec.back_rail_height < 0:
        report.add_error(
            "INVALID_BACK_RAIL_HEIGHT",
            "back_rail_height cannot be negative",
            "back_rail_height",
        )
    if len(rail_panels) != expected_rail_count:
        report.add_error(
            "BACK_RAIL_COUNT_MISMATCH",
            "generated back-rail count does not match the panel rule",
            "back_rail",
        )
    if expected_rail_count > 0 and back_rail_clear_spacing(
        layout.internal_height,
        expected_rail_count,
        spec.back_rail_height,
    ) <= 0:
        report.add_error(
            "NON_POSITIVE_BACK_RAIL_SPACING",
            "back rails leave no positive clear spacing",
            "back_rail",
        )

    for item in panels:
        if item.panel_type in ("fixed_shelf", "movable_shelf") and (
            abs(item.pos_y - layout.internal_y_start) > 1e-6
            or abs(item.pos_y + item.size_y - layout.internal_y_end) > 1e-6
        ):
            report.add_error(
                "INTERNAL_DEPTH_MISMATCH",
                f"{item.id} must span the confirmed internal depth",
                item.id,
            )
        if item.panel_type == "door" and abs(
            item.pos_y + item.size_y - spec.depth
        ) > 1e-6:
            report.add_error(
                "DOOR_DEPTH_MISMATCH",
                f"{item.id} must end at the finished depth",
                item.id,
            )
    return report
````

## File: .gitignore
````
# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
*.so

# Environments
.venv/
venv/
env/
ENV/
.python-version

# Testing
.pytest_cache/
.coverage
htmlcov/

# Build / packaging
build/
dist/
*.egg-info/

# IDE
.vscode/
.idea/

# Local data
.env
.env.*
*.log

# Generated artifacts
generated/*
output/
store/
tmp/
temp/*
````

## File: .gitmodules
````
[submodule "external/text-to-cad"]
	path = external/text-to-cad
	url = https://github.com/earthtojake/text-to-cad
[submodule "external/scientific-agent-skills"]
	path = external/scientific-agent-skills
	url = https://github.com/K-Dense-AI/scientific-agent-skills.git
````

## File: .node-version
````
22.23.2
````

## File: pyproject.toml
````toml
[project]
name = "furniture-agent-workspace"
version = "0.1.0"
description = "Furniture agent workspace scaffold"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn>=0.30",
]

[project.optional-dependencies]
furniture-analysis = [
    "pint==0.25.3",
    "uncertainties==3.2.3",
    "pymoo==0.6.1.6",
    "pandas>=2.0",
    "pyDOE3>=1.0",
    "scipy>=1.11",
    "simpy==4.1.2",
]

[tool.setuptools]
packages = []
````

## File: .agents/skills/furniture-agent/references/llm-runtime-boundary.md
````markdown
# LLM 与运行时边界

适用于创建、修改和审查所有 `domain/skills/furniture-*` 及家具工作流代码。

## 总原则

**LLM 提案，代码准入。**

- LLM 理解开放语言、提出草稿、解释假设，并把可选择结果交给用户确认。
- 代码只接收规范化结构，保证可执行性、一致性和失败安全。
- “代码可实现”不是把逻辑放入代码的理由；只有确定性执行需求才是理由。

## 所有权

归 LLM：

- 同义表达、语义分类、上下文消歧和置信不足时的追问。
- 审美、用途、偏好等开放判断，以及多个合理候选之间的推荐。
- 把用户叙述整理为阶段草稿；模糊默认值只能作为待确认建议。
- 面向用户的解释、假设展示和下一步问题选择。

归运行时代码：

- 规范字段、Schema、允许的规范枚举和阶段字段所有权。
- 数值、单位、几何、公差、碰撞、数量关系和制造不变量。
- 阶段状态、确认、Revision、谱系、持久化和下游失效。
- CAD、BOM、文件、API 等确定性转换或有副作用的操作。
- 不经过 LLM 的结构化 CLI/API 契约；只接受已规范化值。

归 Skill 指令或参考资料：

- LLM 做判断所需的领域口径、非穷举语义示例和追问标准。
- 阶段边界、用户可见检查点、何时停止以及何时需要确认。
- 说明性目录可以列规范值和语义示例，但运行时代码不得把示例变成别名或关键词匹配器。

## 写代码前的判定

对每个准备新增的函数、分支、映射表、默认值或解析器依次检查：

1. 它是否直接解释自然语言、关键词、同义词或模糊偏好？是则默认归 LLM。
2. 它是否只是从多个合理方案中选一个，而且用户能在执行前确认？是则归 LLM 提案。
3. 相同的规范化输入是否必须稳定地产生相同结果？是则可以归代码。
4. 判断错误是否会造成非法状态、错误几何、加工/BOM 错误或外部副作用？是则必须由代码兜底。
5. 裸 CLI/API 是否必须在没有 LLM 时执行？是则代码只实现并验证明确的结构化协议，不补做自然语言理解。

无法明确回答第 3、4 或 5 项的运行时逻辑，不新增到 `scripts/`；把决策标准写入所属 Skill。

## 默认禁止的运行时实现

- 自然语言别名、同义词、关键词或正则分类表。
- 用字符串包含、模糊评分或启发式规则猜测用户意图。
- 在代码里决定追问话术、审美偏好或开放方案优先级。
- 在上游阶段静默物化下游默认值。
- 为一个 LLM 可直接完成的一次性判断增加加载器、注册表或框架。

确有结构化协议兼容、安全或离线批处理要求时可以例外，但必须在所属 Skill 中说明输入契约、停止条件和不用 LLM 的原因，并用行为测试覆盖。

## 完成前边界审计

1. 查看本次 `domain/skills/furniture-*` 的差异，列出新增或扩大的分支、映射、默认值和解析器。
2. 给每项标注一个代码理由：`schema`、`validation`、`calculation`、`state`、`side_effect` 或 `structured_protocol`。
3. 没有上述理由的逻辑移到 `SKILL.md`/`references/`，或删除。
4. 检查代码中是否出现自然语言示例的复制、精确别名匹配或上游阶段的下游决策。
5. 测试客观行为与不变量，不测试提示词的固定措辞。
6. 交付时简要报告：LLM 负责什么、代码保留什么、是否存在例外。

自动化测试只能保证这份规则存在并可发现，不能可靠判断一段业务逻辑是否应归 LLM；语义审计不得省略。
````

## File: domain/skills/furniture-cad/scripts/furniture_cad/cad_bridge.py
````python
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class BridgeResult:
    status: str
    message: str
    source_path: Optional[str] = None
    step_path: Optional[str] = None
    topology_path: Optional[str] = None
    viewer_package_path: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    returncode: Optional[int] = None


class CadBridge:
    """Invoke the external text-to-cad STEP CLI from the owning workspace."""

    def __init__(
        self,
        workspace_root: Optional[str | Path] = None,
        external_repo_root: Optional[str | Path] = None,
        python_executable: Optional[str | Path] = None,
        gen_launcher: Optional[str | Path] = None,
        timeout_seconds: int = 300,
    ) -> None:
        default_workspace_root = Path(__file__).resolve().parents[5]
        self.workspace_root = Path(workspace_root or default_workspace_root).resolve()
        self.external_repo_root = Path(
            external_repo_root
            or self.workspace_root / "external" / "text-to-cad"
        ).resolve()

        default_python = (
            self.workspace_root / ".venv" / "Scripts" / "python.exe"
            if sys.platform == "win32"
            else self.workspace_root / ".venv" / "bin" / "python"
        )
        self.python_executable = Path(python_executable or default_python).resolve()
        self.gen_launcher = Path(
            gen_launcher
            or self.external_repo_root / "skills" / "cad" / "scripts" / "gen"
        ).resolve()
        self.timeout_seconds = timeout_seconds

    def generate_from_source(
        self,
        source_path: str | Path,
        output_path: Optional[str | Path] = None,
        *,
        force: bool = False,
    ) -> BridgeResult:
        """Generate STEP and a component Viewer package from a gen_step() source."""
        resolved_source = self._workspace_path(source_path)
        resolved_output = self._workspace_path(
            output_path
            if output_path is not None
            else self._default_step_output(resolved_source)
        )
        viewer_package_path = self._expected_viewer_package(resolved_source)
        topology_path = viewer_package_path / "assembly.json"

        configuration_error = self._configuration_error(resolved_source, resolved_output)
        if configuration_error:
            return BridgeResult(
                status="failed",
                message=configuration_error,
                source_path=str(resolved_source),
                step_path=str(resolved_output),
                topology_path=str(topology_path),
                viewer_package_path=str(viewer_package_path),
            )

        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        command = [
            str(self.python_executable),
            str(self.gen_launcher),
            resolved_source.as_posix(),
            "--write",
            resolved_output.as_posix(),
            "--json",
        ]
        if force:
            command.append("--force")

        try:
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return BridgeResult(
                status="failed",
                message=f"Unable to execute text-to-cad STEP generation: {exc}",
                source_path=str(resolved_source),
                step_path=str(resolved_output),
                topology_path=str(topology_path),
                viewer_package_path=str(viewer_package_path),
            )

        payload, payload_error = self._generation_payload(completed.stdout)
        if payload is not None:
            viewer_package_path = self._workspace_path(str(payload["packagePath"]))
            topology_path = viewer_package_path / "assembly.json"

        missing_artifacts = [
            path
            for path in (resolved_output, topology_path)
            if not path.is_file() or path.stat().st_size == 0
        ]
        viewer_package_error = self._viewer_package_error(viewer_package_path)
        if (
            completed.returncode == 0
            and payload_error is None
            and not missing_artifacts
            and viewer_package_error is None
        ):
            return BridgeResult(
                status="ok",
                message="text-to-cad generated STEP and component Viewer package.",
                source_path=str(resolved_source),
                step_path=str(resolved_output),
                topology_path=str(topology_path),
                viewer_package_path=str(viewer_package_path),
                stdout=completed.stdout,
                stderr=completed.stderr,
                returncode=completed.returncode,
            )

        details: list[str] = []
        if completed.returncode != 0:
            details.append("text-to-cad scripts/gen returned a non-zero exit code")
        if payload_error:
            details.append(payload_error)
        if missing_artifacts:
            details.append(
                "Missing or empty artifacts: "
                + ", ".join(str(path) for path in missing_artifacts)
            )
        if viewer_package_error:
            details.append(viewer_package_error)
        return BridgeResult(
            status="failed",
            message="; ".join(details),
            source_path=str(resolved_source),
            step_path=str(resolved_output),
            topology_path=str(topology_path),
            viewer_package_path=str(viewer_package_path),
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
        )

    def _workspace_path(self, path: str | Path) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.workspace_root / candidate
        return candidate.resolve()

    @staticmethod
    def _expected_viewer_package(source_path: Path) -> Path:
        return (
            source_path.parent
            / "__cadgen__"
            / "models"
            / source_path.name
        ).resolve()

    @staticmethod
    def _default_step_output(source_path: Path) -> Path:
        if source_path.name.lower().endswith(".step.py"):
            return source_path.with_suffix("")
        return source_path.with_suffix(".step")

    @staticmethod
    def _generation_payload(stdout: str) -> tuple[dict[str, object] | None, str | None]:
        for line in reversed(stdout.splitlines()):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("ok") is not True:
                return None, "text-to-cad scripts/gen reported an unsuccessful result"
            package_path = payload.get("packagePath")
            if not isinstance(package_path, str) or not package_path.strip():
                return None, "text-to-cad scripts/gen did not report packagePath"
            return payload, None
        return None, "text-to-cad scripts/gen did not emit a JSON result"

    @staticmethod
    def _viewer_package_error(package_path: Path) -> str | None:
        descriptor_path = package_path / "assembly.json"
        if not descriptor_path.is_file() or descriptor_path.stat().st_size == 0:
            return f"Viewer package descriptor is missing or empty: {descriptor_path}"
        try:
            descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return f"Viewer package descriptor is invalid: {exc}"
        components = descriptor.get("components") if isinstance(descriptor, dict) else None
        if not isinstance(components, dict) or not components:
            return f"Viewer package has no components: {descriptor_path}"
        package_root = package_path.resolve()
        for component in components.values():
            glb_ref = component.get("glb") if isinstance(component, dict) else None
            if not isinstance(glb_ref, str) or not glb_ref:
                return f"Viewer package contains a component without a GLB reference: {descriptor_path}"
            component_path = (package_path / glb_ref).resolve()
            try:
                component_path.relative_to(package_root)
            except ValueError:
                return f"Viewer package component escapes the package directory: {glb_ref}"
            if not component_path.is_file() or component_path.stat().st_size == 0:
                return f"Viewer package component is missing or empty: {component_path}"
        return None

    def _configuration_error(self, source_path: Path, output_path: Path) -> Optional[str]:
        if not self.python_executable.is_file():
            return f"Project Python interpreter not found: {self.python_executable}"
        if not self.gen_launcher.exists():
            return f"text-to-cad gen launcher not found: {self.gen_launcher}"
        if self.gen_launcher.is_dir() and not (self.gen_launcher / "__main__.py").is_file():
            return f"text-to-cad gen launcher has no __main__.py: {self.gen_launcher}"
        if not source_path.is_file():
            return f"CAD source file not found: {source_path}"
        if source_path.suffix.lower() != ".py":
            return f"CAD source must be a Python file containing gen_step(): {source_path}"
        if output_path.suffix.lower() != ".step":
            return f"CAD output must use .step with text-to-cad scripts/gen: {output_path}"
        return None
````

## File: domain/skills/furniture-cad/scripts/furniture_workflow/workflow_orchestrator.py
````python
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
            workspace_root or Path(__file__).resolve().parents[5]
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
        """Create a revision from an edited serial planning-stage output."""
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
            if parse_stage(key) in STAGE_SEQUENCE
            and stage_index(parse_stage(key)) < stage_index(changed_stage)
        }
        revision.stage_outputs[WorkflowStage.DESIGN_INTENT.value] = (
            revision.intent.to_dict()
        )
        revision.stage_outputs[changed_stage.value] = deepcopy(output)
        if changed_stage == WorkflowStage.PANELS_PLANNED:
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
                    }:
                        continue
                    parameters[key] = value
        revision.approved_stages = [
            value
            for value in parent.approved_stages
            if parse_stage(value) in STAGE_SEQUENCE
            and stage_index(parse_stage(value)) < stage_index(changed_stage)
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
                revision.intent,
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
            revision.intent,
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
        """Run an explicit batch request through the serial furniture workflow."""
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
        if stage == WorkflowStage.PANELS_PLANNED:
            stage_input = panel_stage_input(revision.stage_inputs)
            output = plan_panel_stage(
                revision.intent,
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
            WorkflowStage.PANELS_PLANNED.value,
            WorkflowStage.MANUFACTURING_PLANNED.value,
        )
        if not all(key in revision.stage_outputs for key in required):
            return None
        return CabinetPipelineResult(
            spec=self._spec_from_revision(revision),
            structure=self._structure_from_revision(revision),
            placements=self._placements_from_revision(revision),
            panels=self._panels_from_revision(revision),
            bom=self._bom_from_revision(revision),
        )

    @staticmethod
    def _spec_from_revision(revision: Revision) -> FurnitureSpec:
        output = revision.stage_outputs[WorkflowStage.PANELS_PLANNED.value]
        return FurnitureSpec.from_dict(output["spec"])

    @staticmethod
    def _structure_from_revision(revision: Revision) -> CabinetStructure:
        output = revision.stage_outputs[WorkflowStage.PANELS_PLANNED.value]
        return CabinetStructure(**output["structure"])

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
            if stage == WorkflowStage.PANELS_PLANNED:
                return validate_panel_output(
                    revision.intent,
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
````

## File: domain/skills/furniture-cad/scripts/furniture_workflow/workflow_project.py
````python
"""Project and revision aggregate roots for traceable furniture work."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any
from uuid import uuid4

from furniture_delivery_validation.validation import ValidationReport
from furniture_design_intent.design_intent import DesignIntent
from furniture_panel_planning.panel_spec import migrate_legacy_panel_hinge_side

from .workflow_artifacts import ArtifactManifest
from .workflow_state import WorkflowStage, WorkflowState, parse_stage, utc_now


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


@dataclass
class Revision:
    number: int
    intent: DesignIntent
    stage_inputs: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: _id("rev"))
    parent_revision_id: str | None = None
    created_at: str = field(default_factory=utc_now)
    workflow: WorkflowState = field(default_factory=WorkflowState)
    validations: list[ValidationReport] = field(default_factory=list)
    manifest: ArtifactManifest | None = None
    feature_tree: dict[str, Any] | None = None
    stage_outputs: dict[str, Any] = field(default_factory=dict)
    stage_analyses: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    approved_stages: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.manifest is None:
            self.manifest = ArtifactManifest(source_revision_id=self.id)
        self.stage_outputs.setdefault(
            WorkflowStage.DESIGN_INTENT.value,
            self.intent.to_dict(),
        )
        if self.feature_tree is not None:
            self.stage_outputs.setdefault(
                WorkflowStage.FEATURE_TREE_PLANNED.value,
                self.feature_tree,
            )

    def is_stage_approved(self, stage: WorkflowStage) -> bool:
        return stage.value in self.approved_stages

    def approve_stage(self, stage: WorkflowStage) -> None:
        if stage.value not in self.approved_stages:
            self.approved_stages.append(stage.value)

    @property
    def intent_sha256(self) -> str:
        encoded = json.dumps(
            self.intent.to_dict(), ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
        return sha256(encoded).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "number": self.number,
            "parent_revision_id": self.parent_revision_id,
            "created_at": self.created_at,
            "intent_sha256": self.intent_sha256,
            "intent": self.intent.to_dict(),
            "stage_inputs": self.stage_inputs,
            "workflow": self.workflow.to_dict(),
            "validations": [report.to_dict() for report in self.validations],
            "manifest": self.manifest.to_dict() if self.manifest else None,
            "feature_tree": self.feature_tree,
            "stage_outputs": self.stage_outputs,
            "stage_analyses": self.stage_analyses,
            "approved_stages": self.approved_stages,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Revision":
        raw_intent = dict(data["intent"])
        stage_inputs = data.get("stage_inputs")
        if not isinstance(stage_inputs, dict):
            stage_inputs = _legacy_stage_inputs(raw_intent)
        else:
            stage_inputs = deepcopy(stage_inputs)
        stage_outputs = deepcopy(dict(data.get("stage_outputs", {})))
        panel_input = stage_inputs.get("panels")
        panel_parameters = (
            panel_input.get("parameters") if isinstance(panel_input, dict) else None
        )
        panel_output = stage_outputs.get(WorkflowStage.PANELS_PLANNED.value)
        migrate_legacy_panel_hinge_side(panel_parameters, panel_output)
        return cls(
            id=str(data["id"]),
            number=int(data["number"]),
            parent_revision_id=data.get("parent_revision_id"),
            created_at=str(data["created_at"]),
            intent=DesignIntent.from_dict(raw_intent),
            stage_inputs=stage_inputs,
            workflow=WorkflowState.from_dict(data["workflow"]),
            validations=[
                ValidationReport.from_dict(item) for item in data.get("validations", [])
            ],
            manifest=(
                ArtifactManifest.from_dict(data["manifest"])
                if data.get("manifest")
                else None
            ),
            feature_tree=data.get("feature_tree"),
            stage_outputs=stage_outputs,
            stage_analyses={
                str(stage): {
                    str(name): dict(record)
                    for name, record in dict(records).items()
                }
                for stage, records in dict(data.get("stage_analyses", {})).items()
            },
            approved_stages=[
                parse_stage(str(value)).value
                for value in data.get("approved_stages", [])
            ],
        )


@dataclass
class Project:
    name: str
    id: str = field(default_factory=lambda: _id("project"))
    created_at: str = field(default_factory=utc_now)
    revisions: list[Revision] = field(default_factory=list)

    @property
    def latest(self) -> Revision:
        if not self.revisions:
            raise ValueError("project has no revisions")
        return self.revisions[-1]

    def add_revision(
        self,
        intent: DesignIntent,
        stage_inputs: dict[str, Any] | None = None,
    ) -> Revision:
        parent = self.revisions[-1] if self.revisions else None
        if parent and parent.manifest:
            parent.manifest.mark_stale()
        revision = Revision(
            number=len(self.revisions) + 1,
            intent=intent,
            stage_inputs=dict(stage_inputs or {}),
            parent_revision_id=parent.id if parent else None,
        )
        self.revisions.append(revision)
        return revision

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "revisions": [revision.to_dict() for revision in self.revisions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            created_at=str(data["created_at"]),
            revisions=[Revision.from_dict(item) for item in data.get("revisions", [])],
        )


def _legacy_stage_inputs(raw_intent: dict[str, Any]) -> dict[str, Any]:
    """Move schema-v1 downstream fields out of DesignIntent when loading."""
    layout = dict(raw_intent.get("layout", {}))
    structure = dict(raw_intent.get("structure", {}))
    manufacturing_keys = {
        "options",
    }
    manufacturing = {
        key: structure.pop(key)
        for key in list(structure)
        if key in manufacturing_keys
    }
    room = layout.pop("room", None)
    placement = layout.pop("placement", None)
    for key in ("n_doors", "door_count"):
        if key in layout:
            structure[key] = layout.pop(key)
    result: dict[str, Any] = {
        "layout": {
            "room": room,
            "placement": placement,
        },
        "panels": {"parameters": structure},
        "manufacturing": {
            "parameters": manufacturing,
            "appearance": dict(raw_intent.get("appearance", {})),
        },
    }
    purpose = str(raw_intent.get("purpose", "")).strip()
    if purpose:
        result["layout"]["purpose"] = purpose
    if layout:
        result["layout"]["legacy_parameters"] = layout
    constraints = list(raw_intent.get("constraints", []))
    mappings = dict(raw_intent.get("constraint_mappings", {}))
    for constraint in constraints:
        target = str(mappings.get(constraint, "informational"))
        record = {"text": constraint, "target": target}
        if target.startswith("layout."):
            field = target.split(".", 1)[1]
            if field in {"n_doors", "door_count"}:
                result["panels"].setdefault("constraints", []).append(record)
            else:
                result["layout"].setdefault("constraints", []).append(record)
        elif target.startswith("structure."):
            result["panels"].setdefault("constraints", []).append(record)
        elif target == "informational":
            result.setdefault("informational_constraints", []).append(constraint)
        else:
            result.setdefault("envelope_constraints", []).append(record)
    return result
````

## File: domain/skills/furniture-cad/scripts/tests/test_back_groove_pipeline.py
````python
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_panel_planning.panel_spec import FurnitureSpec
from panel_fixtures import furniture_spec
from furniture_feature_tree.feature_tree_builder import panels_to_feature_tree
from furniture_feature_tree.feature_tree_emitter import write_build123d_source
from furniture_layout.layout_pipeline import plan_layout
from furniture_manufacturing.manufacturing_bom import plan_manufacturing
from furniture_manufacturing.validation import validate_manufacturing
from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.validation import validate_panels
from furniture_panel_planning.structure_planning import CabinetStructure


class BackGroovePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            shelf_count=0,
            n_doors=0,
        )
        self.layout = plan_layout(self.spec)
        self.structure = CabinetStructure.from_spec(self.spec)
        self.placements = plan_panels(self.spec, self.layout)
        self.manufacturing = plan_manufacturing(self.spec, self.placements)
        self.feature_tree = panels_to_feature_tree(
            self.manufacturing.panels,
            self.manufacturing.operations,
            furniture_type=self.spec.furniture_type,
        )

    def test_layout_defers_exact_regions_to_panel_structure(self) -> None:
        payload = asdict(self.layout)
        self.assertNotIn("internal_width", payload)
        self.assertNotIn("panels", payload)
        self.assertNotIn("placements", payload)
        self.assertIn("internal_width", asdict(self.structure))

    def test_panel_stage_owns_back_and_toe_kick_dimensions(self) -> None:
        panels = {panel.id: panel for panel in self.placements}
        back = panels["back_panel"]
        self.assertEqual((back.size_x, back.size_y, back.size_z), (776.0, 9.0, 926.0))
        self.assertEqual((back.pos_x, back.pos_y, back.pos_z), (12.0, 18.0, 62.0))
        supports = [panel for panel in self.placements if panel.id.startswith("toe_kick_support_")]
        self.assertEqual(len(supports), 1)
        self.assertEqual((supports[0].pos_x, supports[0].size_y), (391.0, 513.0))

    def test_manufacturing_stage_owns_four_target_specific_grooves(self) -> None:
        operations = {operation.id: operation for operation in self.manufacturing.operations}
        self.assertEqual(
            set(operations),
            {
                "left_side_back_groove",
                "right_side_back_groove",
                "top_back_groove",
                "bottom_back_groove",
            },
        )
        self.assertEqual(operations["left_side_back_groove"].size_y, 10.0)
        self.assertEqual(operations["left_side_back_groove"].size_x, 6.0)

    def test_feature_tree_preserves_groove_cut_operations(self) -> None:
        self.assertEqual(self.feature_tree["schema_version"], 2)
        self.assertEqual(len(self.feature_tree["operations"]), 4)
        self.assertTrue(
            all(operation["type"] == "cut_box" for operation in self.feature_tree["operations"])
        )

    def test_emitted_build123d_geometry_subtracts_groove_volume(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_path = Path(temporary_directory) / "grooved_cabinet.py"
            write_build123d_source(self.feature_tree, source_path)
            module_spec = importlib.util.spec_from_file_location(
                "generated_grooved_cabinet",
                source_path,
            )
            assert module_spec is not None and module_spec.loader is not None
            module = importlib.util.module_from_spec(module_spec)
            module_spec.loader.exec_module(module)
            shape = module.gen_step()

        uncut_volume = sum(
            panel.size_x * panel.size_y * panel.size_z
            for panel in self.manufacturing.panels
        )
        removed_volume = sum(
            operation.size_x * operation.size_y * operation.size_z
            for operation in self.manufacturing.operations
        )
        self.assertAlmostEqual(shape.volume, uncut_volume - removed_volume, places=3)

    def test_invalid_groove_and_support_inputs_fail_in_owning_stages(self) -> None:
        invalid_groove = furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            groove_clearance=600,
        )
        groove_layout = plan_layout(invalid_groove)
        groove_panels = plan_panels(invalid_groove, groove_layout)
        groove_report = validate_manufacturing(
            invalid_groove,
            plan_manufacturing(invalid_groove, groove_panels),
            groove_panels,
        )
        self.assertFalse(groove_report.passed)
        self.assertIn(
            "GROOVE_OUTSIDE_TARGET",
            {issue.code for issue in groove_report.issues},
        )

        invalid_supports = furniture_spec(
            furniture_type="floor_cabinet",
            width=100,
            depth=600,
            height=1000,
            board_thickness=18,
            toe_kick_support_count=4,
        )
        support_layout = plan_layout(invalid_supports)
        support_panels = plan_panels(invalid_supports, support_layout)
        support_report = validate_panels(
            invalid_supports,
            support_layout,
            support_panels,
        )
        self.assertFalse(support_report.passed)
        self.assertIn(
            "NON_POSITIVE_TOE_KICK_SUPPORT_SPACING",
            {issue.code for issue in support_report.issues},
        )

        with self.assertRaisesRegex(ValueError, "must be a non-negative integer"):
            invalid_serialized = asdict(self.spec)
            invalid_serialized["toe_kick_support_count"] = "two"
            FurnitureSpec.from_dict(invalid_serialized)


if __name__ == "__main__":
    unittest.main()
````

## File: domain/skills/furniture-cad/scripts/tests/test_cabinet_pipeline.py
````python
from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_panel_planning.panel_spec import FurnitureSpec
from panel_fixtures import furniture_spec
from furniture_workflow.cabinet_pipeline import plan_cabinet


class CabinetPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = plan_cabinet(
            furniture_spec(
                furniture_type="floor_cabinet",
                width=800,
                height=1000,
                depth=600,
                shelf_count=4,
                n_doors=2,
            )
        )

    def test_floor_cabinet_uses_expected_coordinate_convention(self) -> None:
        placements = {placement.id: placement for placement in self.result.placements}

        left = placements["left_side_panel"]
        self.assertEqual((left.pos_x, left.pos_y, left.pos_z), (0.0, 0.0, 0.0))

        right = placements["right_side_panel"]
        self.assertEqual(right.pos_x, 800.0 - 18.0)

        self.assertEqual(placements["back_panel"].pos_y, 18.0)
        self.assertEqual(placements["bottom_panel"].pos_z, 50.0)

    def test_floor_cabinet_produces_panels_and_bom(self) -> None:
        self.assertEqual(len(self.result.panels), len(self.result.placements))
        self.assertEqual(self.result.bom.panel_count, len(self.result.panels))
        self.assertEqual(self.result.bom.furniture_name, "落地柜")
        self.assertEqual(self.result.bom.dimensions, "800×1000×600mm")
        self.assertGreater(self.result.bom.total_area_m2, 0)
        self.assertEqual(self.result.bom.readiness, "preliminary")

    def test_rejects_non_cabinet_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "executable canonical type"):
            plan_cabinet(
                furniture_spec(
                    furniture_type="wardrobe",
                    width=1200,
                    height=2000,
                    depth=600,
                )
            )


if __name__ == "__main__":
    unittest.main()
````

## File: domain/skills/furniture-cad/scripts/tests/test_cad_bridge.py
````python
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
ADAPTER_PATH = SCRIPT_ROOT / "furniture_cad" / "cad_bridge.py"


def load_adapter_module():
    spec = importlib.util.spec_from_file_location("furniture_cad_bridge", ADAPTER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load CAD bridge module from {ADAPTER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CadBridgeTests(unittest.TestCase):
    def test_generates_step_and_topology_through_external_cli_contract(self) -> None:
        module = load_adapter_module()

        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            source_path = workspace / "generated" / "cabinet.step.py"
            output_path = workspace / "generated" / "cabinet.step"
            launcher_path = workspace / "fake_gen.py"
            source_path.parent.mkdir(parents=True)
            source_path.write_text("def gen_step():\n    return None\n", encoding="utf-8")
            launcher_path.write_text(
                "\n".join(
                    [
                        "import json",
                        "import sys",
                        "from pathlib import Path",
                        "assert '--json' in sys.argv",
                        "source = Path(sys.argv[1])",
                        "output = Path(sys.argv[sys.argv.index('--write') + 1])",
                        "output.parent.mkdir(parents=True, exist_ok=True)",
                        "output.write_text('STEP', encoding='utf-8')",
                        "package = source.parent / '__cadgen__' / 'models' / source.name",
                        "component = package / 'components' / 'fake.glb'",
                        "component.parent.mkdir(parents=True, exist_ok=True)",
                        "component.write_bytes(b'GLB')",
                        "(package / 'assembly.json').write_text(json.dumps({'components': {'fake': {'glb': 'components/fake.glb'}}}), encoding='utf-8')",
                        "print(json.dumps({'ok': True, 'packagePath': package.as_posix()}))",
                    ]
                ),
                encoding="utf-8",
            )

            bridge = module.CadBridge(
                workspace_root=workspace,
                external_repo_root=workspace / "external" / "text-to-cad",
                python_executable=sys.executable,
                gen_launcher=launcher_path,
            )
            result = bridge.generate_from_source(source_path, output_path)

            self.assertEqual(result.status, "ok")
            self.assertEqual(result.returncode, 0)
            self.assertTrue(output_path.is_file())
            package_path = source_path.parent / "__cadgen__" / "models" / source_path.name
            self.assertEqual(Path(result.viewer_package_path), package_path)
            self.assertEqual(Path(result.topology_path), package_path / "assembly.json")
            self.assertTrue((package_path / "components" / "fake.glb").is_file())

    def test_default_launcher_is_current_gen_entrypoint(self) -> None:
        module = load_adapter_module()
        bridge = module.CadBridge(workspace_root=WORKSPACE_ROOT)

        expected = (
            WORKSPACE_ROOT
            / "external"
            / "text-to-cad"
            / "skills"
            / "cad"
            / "scripts"
            / "gen"
        ).resolve()
        self.assertEqual(bridge.gen_launcher, expected)
        self.assertTrue((bridge.gen_launcher / "__main__.py").is_file())
        self.assertEqual(
            bridge._default_step_output(Path("cabinet.step.py")),
            Path("cabinet.step"),
        )

    def test_real_default_gen_entrypoint_generates_current_artifacts(self) -> None:
        module = load_adapter_module()
        cad_source_root = WORKSPACE_ROOT / "temp" / "cad-source"
        cad_source_root.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(
            prefix="cad-bridge-real-gen-",
            dir=cad_source_root,
        ) as temporary_directory:
            source_path = Path(temporary_directory) / "bridge-smoke.step.py"
            output_path = Path(temporary_directory) / "bridge-smoke.step"
            source_path.write_text(
                "\n".join(
                    [
                        "from build123d import Box",
                        "",
                        "def gen_step():",
                        "    return Box(10, 20, 30)",
                    ]
                ),
                encoding="utf-8",
            )

            bridge = module.CadBridge(
                workspace_root=WORKSPACE_ROOT,
                python_executable=sys.executable,
            )
            result = bridge.generate_from_source(
                source_path,
                output_path,
                force=True,
            )

            self.assertEqual(
                result.status,
                "ok",
                msg=f"stdout={result.stdout!r}\nstderr={result.stderr!r}",
            )
            self.assertEqual(result.returncode, 0)
            self.assertTrue(output_path.is_file())
            self.assertGreater(output_path.stat().st_size, 0)

            package_path = Path(result.viewer_package_path)
            descriptor_path = Path(result.topology_path)
            self.assertTrue(package_path.is_dir())
            self.assertEqual(descriptor_path, package_path / "assembly.json")
            descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
            components = descriptor.get("components")
            self.assertIsInstance(components, dict)
            self.assertTrue(components)
            for component in components.values():
                component_path = package_path / component["glb"]
                self.assertTrue(component_path.is_file())
                self.assertGreater(component_path.stat().st_size, 0)

    def test_rejects_missing_source_before_launch(self) -> None:
        module = load_adapter_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            launcher_path = workspace / "fake_gen.py"
            launcher_path.write_text("", encoding="utf-8")
            bridge = module.CadBridge(
                workspace_root=workspace,
                python_executable=sys.executable,
                gen_launcher=launcher_path,
            )

            result = bridge.generate_from_source("missing.py")

            self.assertEqual(result.status, "failed")
            self.assertIn("CAD source file not found", result.message)


if __name__ == "__main__":
    unittest.main()
````

## File: domain/skills/furniture-cad/scripts/tests/test_cli_entrypoint.py
````python
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

import generate_furniture
from furniture_cad.cad_bridge import CadBridge
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from panel_fixtures import cabinet_data


class CliEntrypointTests(unittest.TestCase):
    def test_cli_delegates_full_generation_to_injected_orchestrator(self) -> None:
        artifact_name = f"cli-test-{uuid4().hex}"
        source_dir = WORKSPACE_ROOT / "temp" / "cad-source" / artifact_name
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                temporary_root = Path(temporary_directory)
                spec_path = temporary_root / "cabinet.json"
                spec_path.write_text(
                    json.dumps(
                        cabinet_data("wall_cabinet")
                    ),
                    encoding="utf-8",
                )
                launcher_path = temporary_root / "fake_gen.py"
                launcher_path.write_text(
                    "\n".join(
                        [
                            "import json",
                            "import sys",
                            "from pathlib import Path",
                            "source = Path(sys.argv[1])",
                            "output = Path(sys.argv[sys.argv.index('--write') + 1])",
                            "output.parent.mkdir(parents=True, exist_ok=True)",
                            "output.write_text('STEP', encoding='utf-8')",
                            "package = source.parent / '__cadgen__' / 'models' / source.name",
                            "component = package / 'components' / 'fake.glb'",
                            "component.parent.mkdir(parents=True, exist_ok=True)",
                            "component.write_bytes(b'GLB')",
                            "(package / 'assembly.json').write_text(json.dumps({'components': {'fake': {'glb': 'components/fake.glb'}}}), encoding='utf-8')",
                            "print(json.dumps({'ok': True, 'packagePath': package.as_posix()}))",
                        ]
                    ),
                    encoding="utf-8",
                )
                bridge = CadBridge(
                    workspace_root=WORKSPACE_ROOT,
                    python_executable=sys.executable,
                    gen_launcher=launcher_path,
                )
                orchestrator = FurnitureOrchestrator(
                    workspace_root=WORKSPACE_ROOT,
                    cad_bridge=bridge,
                )

                with redirect_stdout(StringIO()):
                    exit_code = generate_furniture.main(
                        [
                            str(spec_path),
                            "--name",
                            artifact_name,
                            "--output-root",
                            str(temporary_root / "outputs"),
                        ],
                        orchestrator=orchestrator,
                    )

                artifact_dir = temporary_root / "outputs" / artifact_name
                self.assertEqual(exit_code, 0)
                self.assertTrue((artifact_dir / f"{artifact_name}.step").is_file())
                self.assertTrue(
                    (artifact_dir / f"{artifact_name}.feature-tree.json").is_file()
                )
                self.assertTrue(
                    (source_dir / f"{artifact_name}.step.py").is_file()
                )
        finally:
            shutil.rmtree(source_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
````

## File: domain/skills/furniture-cad/scripts/tests/test_entrypoint_architecture.py
````python
from __future__ import annotations

import ast
import unittest
from pathlib import Path


SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }


class EntrypointArchitectureTests(unittest.TestCase):
    def test_serial_entrypoints_only_import_the_application_orchestrator(self) -> None:
        for filename in ("generate_furniture.py",):
            modules = imported_modules(SCRIPTS_ROOT / filename)
            self.assertIn("furniture_workflow.workflow_orchestrator", modules)
            self.assertNotIn("furniture_layout.layout_pipeline", modules)
            self.assertNotIn("furniture_feature_tree.feature_tree_emitter", modules)
            self.assertNotIn("furniture_cad.cad_bridge", modules)

        server_modules = imported_modules(SCRIPTS_ROOT / "server.py")
        self.assertIn("furniture_workflow.workflow_orchestrator", server_modules)
        self.assertIn("furniture_layout.layout_pipeline", server_modules)
        self.assertNotIn("furniture_feature_tree.feature_tree_emitter", server_modules)
        self.assertNotIn("furniture_cad.cad_bridge", server_modules)

    def test_agent_routes_execution_through_the_orchestrator(self) -> None:
        agent_skill = (
            WORKSPACE_ROOT / ".agents" / "skills" / "furniture-agent" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("FurnitureOrchestrator", agent_skill)
        self.assertIn("不得从 Agent 直接调用 `plan_cabinet()`", agent_skill)


if __name__ == "__main__":
    unittest.main()
````

## File: domain/skills/furniture-cad/scripts/tests/test_furniture_pipeline.py
````python
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FurniturePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.planner = load_module(
            "test_furniture_planner",
            SCRIPT_ROOT / "furniture_workflow" / "planner.py",
        )

    def test_rejects_unsupported_furniture_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "supported:"):
            self.planner.plan_furniture(
                {"type": "bed", "width": 2000, "depth": 2200, "height": 500}
            )


if __name__ == "__main__":
    unittest.main()
````

## File: domain/skills/furniture-cad/scripts/tests/test_scientific_analysis_adapters.py
````python
from __future__ import annotations

from copy import deepcopy
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_delivery_validation.validation import validate_delivery
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_state import WorkflowStage
from furniture_workflow.workflow_store import JsonProjectStore
from panel_fixtures import cabinet_data


def cabinet_spec() -> dict[str, object]:
    return cabinet_data(shelf_count=2, n_doors=2)


class ScientificAnalysisAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.orchestrator = FurnitureOrchestrator(workspace_root=WORKSPACE_ROOT)

    def _project_through(self, stage: WorkflowStage):
        return self.orchestrator.execute_spec(
            "科学分析测试柜",
            cabinet_spec(),
            through_stage=stage,
        ).project

    def test_unit_audit_is_side_evidence_and_persists(self) -> None:
        project = self._project_through(WorkflowStage.PANELS_PLANNED)
        before = deepcopy(project.latest.stage_outputs)

        record = self.orchestrator.run_stage_analysis(
            project,
            "panel_unit_audit",
            {
                "uncertainties": {
                    "width": {
                        "uncertainty": 0.5,
                        "unit": "mm",
                        "kind": "limit",
                        "distribution": "rectangular",
                    },
                    "board_thickness": {
                        "uncertainty": 0.1,
                        "unit": "mm",
                        "kind": "standard",
                    },
                }
            },
        )

        self.assertEqual(record["method_skill"], "uncertainty-and-units")
        self.assertTrue(record["report"]["passed"])
        self.assertEqual(project.latest.stage_outputs, before)
        self.assertIn(
            "panel_unit_audit",
            project.latest.stage_analyses[WorkflowStage.PANELS_PLANNED.value],
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            store = JsonProjectStore(temporary_directory)
            store.save(project)
            loaded = store.load(project.id)
        loaded_record = loaded.latest.stage_analyses[
            WorkflowStage.PANELS_PLANNED.value
        ]["panel_unit_audit"]
        self.assertEqual(loaded_record["source_sha256"], record["source_sha256"])

    def test_pareto_candidate_requires_explicit_new_revision(self) -> None:
        project = self._project_through(WorkflowStage.MANUFACTURING_PLANNED)
        parent = project.latest
        source_output = deepcopy(
            parent.stage_outputs[WorkflowStage.PANELS_PLANNED.value]
        )

        record = self.orchestrator.run_stage_analysis(
            project,
            "panel_optimization",
            {
                "engine": "auto",
                "variables": {"board_thickness": [15.0, 18.0]},
                "objectives": [
                    "material_volume_m3",
                    "negative_internal_volume_m3",
                ],
            },
        )

        self.assertEqual(record["method_skill"], "pymoo")
        self.assertEqual(record["report"]["status"], "completed")
        self.assertEqual(
            parent.stage_outputs[WorkflowStage.PANELS_PLANNED.value],
            source_output,
        )
        self.assertGreaterEqual(len(record["report"]["candidates"]), 1)

        revised = self.orchestrator.apply_panel_optimization_candidate(project, 0)
        self.assertNotEqual(revised.id, parent.id)
        self.assertEqual(revised.parent_revision_id, parent.id)
        self.assertIn(WorkflowStage.PANELS_PLANNED.value, revised.stage_outputs)
        self.assertNotIn(
            WorkflowStage.MANUFACTURING_PLANNED.value,
            revised.stage_outputs,
        )
        self.assertEqual(revised.stage_analyses, {})

    def test_experiment_statistics_and_production_are_manufacturing_evidence(self) -> None:
        project = self._project_through(WorkflowStage.MANUFACTURING_PLANNED)
        before = deepcopy(project.latest.stage_outputs)

        experiment = self.orchestrator.run_stage_analysis(
            project,
            "prototype_experiment",
            {
                "factors": {
                    "edge_band_temperature_c": [180, 200],
                    "feed_rate_m_min": [8, 12],
                },
                "responses": ["bond_strength_n"],
                "independent_unit": "test_panel",
                "replicates": 2,
                "blocks": ["day-1", "day-2"],
                "seed": 17,
            },
        )
        self.assertEqual(experiment["method_skill"], "experimental-design")
        self.assertEqual(experiment["report"]["run_count"], 8)

        statistics = self.orchestrator.run_stage_analysis(
            project,
            "test_statistics",
            {
                "records": [
                    {"process": "A", "strength": 10.0},
                    {"process": "A", "strength": 11.0},
                    {"process": "A", "strength": 10.5},
                    {"process": "B", "strength": 13.0},
                    {"process": "B", "strength": 12.5},
                    {"process": "B", "strength": 13.5},
                ],
                "group_field": "process",
                "value_field": "strength",
            },
        )
        self.assertEqual(statistics["method_skill"], "statistical-analysis")
        self.assertIn(statistics["status"], {"completed", "descriptive_only"})
        self.assertEqual(statistics["report"]["descriptives"]["A"]["n"], 3)

        production = self.orchestrator.run_stage_analysis(
            project,
            "production_simulation",
            {
                "resources": {
                    "cutting": 1,
                    "edge_banding": 1,
                    "drilling": 1,
                    "assembly": 1,
                },
                "routes": {
                    "*": [
                        {"resource": "cutting", "duration_min": 2.0},
                        {"resource": "edge_banding", "duration_min": 1.0},
                        {"resource": "drilling", "duration_min": 0.5},
                    ]
                },
                "assembly": {"resource": "assembly", "duration_min": 10.0},
                "replications": 3,
                "duration_cv": 0.1,
                "seed": 23,
            },
        )
        self.assertEqual(production["method_skill"], "simpy")
        self.assertEqual(production["status"], "completed")
        self.assertGreater(production["report"]["summary"]["mean_makespan_min"], 0)
        self.assertEqual(project.latest.stage_outputs, before)

    def test_delivery_reports_stale_analysis_hash(self) -> None:
        project = self._project_through(WorkflowStage.PANELS_PLANNED)
        revision = project.latest
        self.orchestrator.run_stage_analysis(project, "panel_unit_audit")
        revision.stage_outputs[WorkflowStage.PANELS_PLANNED.value]["spec"][
            "board_thickness"
        ] = 19.0

        report = validate_delivery(
            revision.manifest,
            source_revision_id=revision.id,
            stage_outputs=revision.stage_outputs,
            approved_stages=revision.approved_stages,
            stage_validations=revision.validations,
            stage_analyses=revision.stage_analyses,
        )
        self.assertIn(
            "ANALYSIS_SOURCE_HASH_MISMATCH",
            {issue.code for issue in report.issues},
        )


if __name__ == "__main__":
    unittest.main()
````

## File: domain/skills/furniture-cad/scripts/tests/test_workspace_layout.py
````python
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from validate_workspace_layout import find_violations


class WorkspaceLayoutTests(unittest.TestCase):
    def test_live_workspace_uses_only_stage_skills_and_temp(self) -> None:
        self.assertEqual(find_violations(WORKSPACE_ROOT), [])

    def test_accepts_stage_owned_script_and_rejects_unrelated_skill_script(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            stage_scripts = root / "domain" / "skills" / "furniture-layout" / "scripts"
            stage_scripts.mkdir(parents=True)
            (stage_scripts / "layout.py").write_text("pass\n", encoding="utf-8")
            unrelated_scripts = root / "domain" / "skills" / "other-skill" / "scripts"
            unrelated_scripts.mkdir(parents=True)
            (unrelated_scripts / "tool.py").write_text("pass\n", encoding="utf-8")

            violations = find_violations(root)

        self.assertEqual(
            violations,
            ["script outside allowed locations: domain/skills/other-skill/scripts/tool.py"],
        )

    def test_rejects_root_code_tree_and_generated_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "scripts").mkdir()
            (root / "generated").mkdir()
            (root / "generated" / "model.py").write_text("pass\n", encoding="utf-8")

            violations = find_violations(root)

        self.assertIn("forbidden top-level code tree: scripts/", violations)
        self.assertIn(
            "script outside allowed locations: generated/model.py", violations
        )


if __name__ == "__main__":
    unittest.main()
````

## File: domain/skills/furniture-cad/scripts/generate_furniture.py
````python
"""端到端家具生成脚本：规划 → 拆单 → BOM → FeatureTree → 源码 → STEP/GLB

用法（从仓库根目录运行）:
  python domain/skills/furniture-cad/scripts/generate_furniture.py examples/cabinet_basic.json --name my_cabinet --force
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]

# skill 自带 furniture 运行包，不依赖仓库根目录的 packages/。
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator


def main(
    argv: list[str] | None = None,
    *,
    orchestrator: FurnitureOrchestrator | None = None,
) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="板式家具端到端生成：JSON spec → 拆单 → BOM → STEP/GLB"
    )
    parser.add_argument("spec", help="家具 JSON 规格文件路径")
    parser.add_argument("--name", help="输出名称（默认使用文件名）")
    parser.add_argument(
        "--output-root",
        default="generated",
        help="输出根目录（默认 generated）",
    )
    parser.add_argument("--force", action="store_true", help="强制重新生成 STEP")
    args = parser.parse_args(argv)

    # CLI 只负责协议适配；完整执行顺序统一由 FurnitureOrchestrator 控制。
    spec_path = _workspace_path(args.spec)
    spec_data = json.loads(spec_path.read_text(encoding="utf-8"))
    artifact_name = args.name or spec_path.stem

    try:
        application = orchestrator or FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT
        )
        orchestration = application.execute_spec(
            artifact_name,
            spec_data,
            output_root=args.output_root,
            artifact_name=artifact_name,
            generate_cad=True,
            force=args.force,
        )
    except (OSError, TypeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if orchestration.pipeline is None or orchestration.bridge is None:
        for report in orchestration.revision.validations:
            for issue in report.issues:
                print(f"Error [{issue.code}]: {issue.message}", file=sys.stderr)
        return 1

    pipeline = orchestration.pipeline
    fspec = pipeline.spec
    print(
        f" 规划家具: {fspec.furniture_type} "
        f"({fspec.width:.0f}×{fspec.height:.0f}×{fspec.depth:.0f}mm)"
    )
    print(f" 拆单完成: {pipeline.bom.panel_count} 块板件")
    print(f" 五金件: {pipeline.bom.hardware_item_count} 项")
    print(f" 总展开面积: {pipeline.bom.total_area_m2:.4f} m²")

    for kind, label in (
        ("design_intent", "设计意图"),
        ("feature_tree", "Feature Tree"),
        ("bom", "BOM 报告"),
        ("cad_source", "build123d 源码"),
    ):
        artifact = next(
            item
            for item in orchestration.revision.manifest.artifacts
            if item.kind == kind
        )
        print(f" {label} → {artifact.path}")

    bridge_result = orchestration.bridge

    print(f"\n{'='*60}")
    print(f"  CAD 生成结果: {bridge_result.status.upper()}")
    print(f"  {bridge_result.message}")
    if bridge_result.step_path:
        print(f"  STEP: {bridge_result.step_path}")
    if bridge_result.viewer_package_path:
        print(f"  Viewer 包: {bridge_result.viewer_package_path}")
    if bridge_result.topology_path:
        print(f"  Viewer 清单: {bridge_result.topology_path}")
    print(f"{'='*60}")

    return 0 if bridge_result.status == "ok" else 1


def _workspace_path(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = WORKSPACE_ROOT / candidate
    return candidate.resolve()


if __name__ == "__main__":
    raise SystemExit(main())
````

## File: domain/skills/furniture-cad/scripts/README.md
````markdown
# 家具跨阶段运行时

只保存 CAD 阶段及跨阶段应用层：

- `furniture_workflow/`：唯一 Orchestrator、状态、谱系、写入和持久化。
- `furniture_cad/`：CAD Bridge/校验；`generate_furniture.py`、`server.py`：CLI/API。
- `runtime_paths.py`：加载阶段包；`tests/`、`validate_workspace_layout.py`：集成测试/布局守卫。

其余阶段代码在所属 `domain/skills/furniture-*/scripts/`。CLI/API/Agent 均经 `FurnitureOrchestrator`；阶段包不得另建状态机或流水线。
````

## File: domain/skills/furniture-cad/scripts/runtime_paths.py
````python
"""Expose the seven stage-owned runtime packages to CLI, API, and tests."""

from __future__ import annotations

import sys
from pathlib import Path


STAGE_SKILL_NAMES = (
    "furniture-design-intent",
    "furniture-layout",
    "furniture-panel-planning",
    "furniture-manufacturing",
    "furniture-feature-tree",
    "furniture-cad",
    "furniture-delivery-validation",
)


def stage_script_roots(workspace_root: Path) -> tuple[Path, ...]:
    skills_root = workspace_root.resolve() / "domain" / "skills"
    return tuple(skills_root / name / "scripts" for name in STAGE_SKILL_NAMES)


def bootstrap_runtime_paths(workspace_root: Path | None = None) -> tuple[Path, ...]:
    root = (workspace_root or Path(__file__).resolve().parents[4]).resolve()
    script_roots = stage_script_roots(root)
    for script_root in reversed(script_roots):
        path = str(script_root)
        if path not in sys.path:
            sys.path.insert(0, path)
    return script_roots
````

## File: domain/skills/furniture-cad/scripts/validate_workspace_layout.py
````python
"""Enforce stage-owned skill scripts plus the disposable temp surface."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


SCRIPT_SUFFIXES = {
    ".bat",
    ".cmd",
    ".cjs",
    ".js",
    ".jsx",
    ".mjs",
    ".ps1",
    ".psm1",
    ".py",
    ".pyc",
    ".pyw",
    ".sh",
    ".ts",
    ".tsx",
}
STAGE_SKILL_NAMES = (
    "furniture-design-intent",
    "furniture-layout",
    "furniture-panel-planning",
    "furniture-manufacturing",
    "furniture-feature-tree",
    "furniture-cad",
    "furniture-delivery-validation",
)
ALLOWED_SCRIPT_ROOTS = tuple(
    Path("domain") / "skills" / skill_name / "scripts" for skill_name in STAGE_SKILL_NAMES
) + (Path("temp"),)
EXCLUDED_ROOTS = {".git", ".venv", "external"}
FORBIDDEN_TOP_LEVEL_CODE_TREES = {"packages", "scripts", "scratch", "tests", "tmp"}


def find_violations(workspace_root: Path) -> list[str]:
    workspace_root = workspace_root.resolve()
    violations: list[str] = []

    for name in sorted(FORBIDDEN_TOP_LEVEL_CODE_TREES):
        path = workspace_root / name
        if path.exists():
            violations.append(f"forbidden top-level code tree: {name}/")

    for current_root, directories, files in os.walk(workspace_root):
        current_path = Path(current_root)
        if current_path == workspace_root:
            directories[:] = [name for name in directories if name not in EXCLUDED_ROOTS]
        for filename in files:
            path = current_path / filename
            if path.suffix.lower() not in SCRIPT_SUFFIXES:
                continue
            relative = path.relative_to(workspace_root)
            if any(relative.is_relative_to(root) for root in ALLOWED_SCRIPT_ROOTS):
                continue
            violations.append(f"script outside allowed locations: {relative.as_posix()}")

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate that local scripts only exist in stage skills or temp/."
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    args = parser.parse_args()

    violations = find_violations(args.workspace_root)
    if violations:
        print("Workspace script layout is invalid:")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("Workspace script layout is valid: stage-owned domain/skills/*/scripts + temp only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## File: domain/skills/furniture-cad/SKILL.md
````markdown
---
name: furniture-cad
description: 用于 cad_generated 阶段和 CLI/API 批处理。当用户说"生成STEP""导出CAD""3D模型""生成六面钻文件""Viewer预览"时触发。根据已确认特征树生成 CAD、STEP 和 Viewer 拓扑，不做特征树规划或最终验证。
---

# 家具 CAD 执行

阶段：`cad_generated`

各阶段拥有运行时；`scripts/furniture_workflow/workflow_orchestrator.py` 统一编排，CAD 实现在 `scripts/furniture_cad/`。不得另建规划器接口、JSON 契约或流水线。

## 代码位置

- 阶段运行时放所属 `domain/skills/furniture-*/scripts/`；跨阶段 Orchestrator、CLI/API、布局守卫和集成测试放 `domain/skills/furniture-cad/scripts/`。
- 一次性检查、迁移、调试和 CAD 实验放已忽略的 `temp/<project-slug>/`；每个项目或任务独占一个目录，脚本与派生产物随目录整体识别和删除，任务结束即清理。禁止把不同项目平铺在 `temp/` 根层；也禁止根级 `scripts/`、`packages/`、`tests/`、`scratch/`、`tmp/`，以及在非家具 Skill 新建脚本面。
- 生成源码只进保留路径 `temp/cad-source/<artifact-name>/`，不得进 `generated/`。工作区目录或生成逻辑变更后运行：

```powershell
.\.venv\Scripts\python.exe domain\skills\furniture-cad\scripts\validate_workspace_layout.py
```

有违规即失败，交付前清零。

## 工作流

1. 声称支持、规范化 JSON、生成或报告产物前，读取 [运行时契约](references/runtime-contract.md) 并核对实时入口。
2. 要求 `feature_tree_planned` 已确认；用 `FurnitureOrchestrator.run_next()` 生成。
3. CLI/API/Agent 均经 Orchestrator；发射器和 CAD Bridge 仅由其调用，结果规则归 `scripts/furniture_cad/validation.py`。
4. 发射器将 Feature Tree `cut_box` 对目标板件做 build123d 布尔减料；不得用重叠板件冒充槽。
5. API 生成请求显式提交完整板件字段；`back_mount/back_rail_height` 等值只路由到板件阶段。有效背板模式由 `panels_planned` 准入并解析，API 返回制造备注、加工操作和 drilled-holes。
6. `workflow_artifact_writer.py` 写跨阶段快照；Orchestrator 不实现 JSON、BOM、孔位或 CAD 源码序列化。
7. 展示 `stage_outputs.cad_generated` 后暂停，不做交付验证。仅明确一次性 CLI/API 批处理可用 `execute_spec()` 或 `scripts/generate_furniture.py`。

## 返回内容

- 规范化输入、已确认特征树来源、CAD 命令结果和 `stage_outputs.cad_generated`。
- 实际存在的 STEP、Viewer 组件包及其 `assembly.json` 清单、drilled-holes、孔位 STEP 及逐板六面钻 XML 路径。
- 下一阶段：`domain/skills/furniture-delivery-validation/SKILL.md`；本阶段不宣称最终通过。
````

## File: domain/skills/furniture-layout/scripts/furniture_layout/layout_planning.py
````python
"""Customer-visible cabinet layout without construction geometry."""

from __future__ import annotations

from dataclasses import dataclass

from .layout_spec import LayoutSpec


@dataclass(frozen=True)
class CabinetLayout:
    """Stage-2 envelope and functional-count contract."""

    furniture_type: str
    width: float
    depth: float
    height: float
    door_count: int

    @classmethod
    def from_spec(cls, spec: LayoutSpec) -> "CabinetLayout":
        return cls(
            furniture_type=spec.furniture_type,
            width=spec.width,
            depth=spec.depth,
            height=spec.height,
            door_count=spec.door_count,
        )
````

## File: domain/skills/furniture-layout/scripts/furniture_layout/validation.py
````python
"""Validation owned by the layout-planning stage."""

from __future__ import annotations

from math import isfinite
from typing import Any, Mapping

from furniture_delivery_validation.validation import ValidationReport

from .layout_preview import render_layout_preview
from .layout_planning import CabinetLayout
from .layout_spec import LayoutSpec
from .layout_viewer import render_layout_viewer
from .room_planning import (
    EPSILON,
    PLACEMENT_MODES,
    WALLS,
    PlacementRequest,
    RoomPlacementPlan,
    build_room_placement,
    obstacle_collisions,
    opening_collisions,
    resolve_placement,
)


def validate_layout(
    spec: LayoutSpec | Any,
    layout: CabinetLayout,
) -> ValidationReport:
    report = ValidationReport(stage="layout_planned")
    if not isinstance(spec, LayoutSpec):
        spec = LayoutSpec(
            furniture_type=str(spec.furniture_type),
            width=float(spec.width),
            depth=float(spec.depth),
            height=float(spec.height),
            door_count=int(getattr(spec, "door_count", spec.n_doors)),
        )
    if (
        layout.furniture_type,
        layout.width,
        layout.depth,
        layout.height,
    ) != (
        spec.furniture_type,
        spec.width,
        spec.depth,
        spec.height,
    ):
        report.add_error(
            "LAYOUT_ENVELOPE_MISMATCH",
            "layout envelope does not match confirmed design intent",
        )
    for name, count in (
        ("door_count", layout.door_count),
    ):
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            report.add_error(
                "INVALID_LAYOUT_COUNT",
                f"{name} must be a non-negative integer",
                name,
            )
    if layout.door_count != spec.door_count:
        report.add_error(
            "LAYOUT_COUNT_MISMATCH",
            "layout counts must match the customer-visible layout request",
        )
    return report


def validate_layout_output(
    spec: LayoutSpec,
    output: Mapping[str, Any],
) -> ValidationReport:
    """Validate the complete stage output, including optional room placement."""
    report = ValidationReport(stage="layout_planned")
    raw_layout = output.get("layout")
    if not isinstance(raw_layout, Mapping):
        report.add_error(
            "MISSING_LAYOUT",
            "layout stage output requires a layout object",
            "layout",
        )
        return report

    try:
        layout = CabinetLayout(**raw_layout)
    except (TypeError, ValueError) as exc:
        report.add_error("INVALID_LAYOUT", str(exc), "layout")
        return report

    cabinet_report = validate_layout(spec, layout)
    report.issues.extend(cabinet_report.issues)

    raw_context = output.get("layout_context")
    if not isinstance(raw_context, Mapping):
        report.add_error(
            "MISSING_LAYOUT_CONTEXT",
            "layout stage output requires layout_context source markers",
            "layout_context",
        )
    else:
        for key, allowed in (
            ("room_source", {"provided", "default_bedroom"}),
            (
                "placement_source",
                {"provided", "default_north_wall_centered"},
            ),
        ):
            if raw_context.get(key) not in allowed:
                report.add_error(
                    "INVALID_LAYOUT_CONTEXT",
                    f"layout_context.{key} has an unsupported value",
                    f"layout_context.{key}",
                )

    has_room_placement = "room_placement" in output
    has_preview = "preview" in output
    has_viewer = "viewer" in output
    if not has_room_placement and not has_preview and not has_viewer:
        report.add_error(
            "MISSING_ROOM_LAYOUT_OUTPUT",
            "room placement, SVG preview, and interactive viewer are required",
            "room_placement",
        )
        return report
    if not (has_room_placement and has_preview and has_viewer):
        report.add_error(
            "INCOMPLETE_ROOM_LAYOUT_OUTPUT",
            "room placement, SVG preview, and interactive viewer must be emitted together",
            "room_placement",
        )
        return report

    try:
        raw_room_placement = output["room_placement"]
        if not isinstance(raw_room_placement, Mapping):
            raise ValueError("room_placement must be an object")
        plan = RoomPlacementPlan.from_dict(raw_room_placement)
    except (KeyError, TypeError, ValueError) as exc:
        report.add_error(
            "INVALID_ROOM_LAYOUT_OUTPUT",
            str(exc),
            "room_placement",
        )
        return report

    _validate_room(plan, report)
    if any(issue.code == "INVALID_ROOM_DIMENSION" for issue in report.issues):
        return report
    expected_plan = _validate_placement(plan, layout, report)
    if expected_plan is None:
        return report

    _validate_derived_room_output(plan, expected_plan, report)
    _validate_room_fit(plan, layout, report)

    raw_preview = output.get("preview")
    if not isinstance(raw_preview, Mapping):
        report.add_error(
            "INVALID_LAYOUT_PREVIEW",
            "preview must be an object",
            "preview",
        )
    elif dict(raw_preview) != render_layout_preview(expected_plan, layout):
        report.add_error(
            "LAYOUT_PREVIEW_MISMATCH",
            "SVG preview must match the current room and furniture placement",
            "preview",
        )
    raw_viewer = output.get("viewer")
    if not isinstance(raw_viewer, Mapping):
        report.add_error(
            "INVALID_LAYOUT_VIEWER",
            "viewer must be an object",
            "viewer",
        )
    elif dict(raw_viewer) != render_layout_viewer(expected_plan, layout):
        report.add_error(
            "LAYOUT_VIEWER_MISMATCH",
            "interactive viewer must match the current room and furniture placement",
            "viewer",
        )
    return report


def _validate_room(
    plan: RoomPlacementPlan,
    report: ValidationReport,
) -> None:
    room = plan.room
    for name, value in (
        ("width_mm", room.width_mm),
        ("depth_mm", room.depth_mm),
        ("height_mm", room.height_mm),
    ):
        if not isfinite(value) or value <= 0:
            report.add_error(
                "INVALID_ROOM_DIMENSION",
                f"room.{name} must be a positive finite number",
                f"room_placement.room.{name}",
            )

    for index, opening in enumerate(room.openings):
        path = f"room_placement.room.openings[{index}]"
        if opening.wall not in WALLS:
            report.add_error(
                "INVALID_OPENING_WALL",
                "opening.wall must be one of: " + ", ".join(sorted(WALLS)),
                f"{path}.wall",
            )
            continue
        wall_length = room.wall_length(opening.wall)
        if (
            not _all_finite(
                opening.offset_mm,
                opening.width_mm,
                opening.height_mm,
                opening.sill_height_mm,
            )
            or opening.offset_mm < 0
            or opening.width_mm <= 0
            or opening.offset_mm + opening.width_mm > wall_length + EPSILON
            or opening.sill_height_mm < 0
            or opening.height_mm <= 0
            or opening.sill_height_mm + opening.height_mm
            > room.height_mm + EPSILON
        ):
            report.add_error(
                "OPENING_OUTSIDE_ROOM",
                f"opening {opening.id!r} must fit on its wall and inside room height",
                path,
            )

    for index, obstacle in enumerate(room.obstacles):
        path = f"room_placement.room.obstacles[{index}]"
        if (
            not _all_finite(
                obstacle.x_mm,
                obstacle.y_mm,
                obstacle.z_mm,
                obstacle.width_mm,
                obstacle.depth_mm,
                obstacle.height_mm,
            )
            or obstacle.x_mm < 0
            or obstacle.y_mm < 0
            or obstacle.z_mm < 0
            or obstacle.width_mm <= 0
            or obstacle.depth_mm <= 0
            or obstacle.height_mm <= 0
            or obstacle.x_mm + obstacle.width_mm > room.width_mm + EPSILON
            or obstacle.y_mm + obstacle.depth_mm > room.depth_mm + EPSILON
            or obstacle.z_mm + obstacle.height_mm > room.height_mm + EPSILON
        ):
            report.add_error(
                "OBSTACLE_OUTSIDE_ROOM",
                f"obstacle {obstacle.id!r} must be a positive box inside the room",
                path,
            )


def _validate_placement(
    plan: RoomPlacementPlan,
    layout: CabinetLayout,
    report: ValidationReport,
) -> RoomPlacementPlan | None:
    placement = plan.placement
    if placement.mode not in PLACEMENT_MODES:
        report.add_error(
            "INVALID_PLACEMENT_MODE",
            "placement.mode must be one of: "
            + ", ".join(sorted(PLACEMENT_MODES)),
            "room_placement.placement.mode",
        )
        return None
    if not _all_finite(
        placement.origin_x_mm,
        placement.origin_y_mm,
        placement.origin_z_mm,
        placement.rotation_z_deg,
    ):
        report.add_error(
            "INVALID_PLACEMENT_TRANSFORM",
            "placement transform values must be finite",
            "room_placement.placement",
        )
        return None

    expected_placement = placement
    if placement.mode == "wall":
        if placement.host_wall not in WALLS or placement.offset_mm is None:
            report.add_error(
                "INVALID_WALL_PLACEMENT",
                "wall placement requires a known host_wall and offset_mm",
                "room_placement.placement",
            )
            return None
        try:
            expected_placement = resolve_placement(
                plan.room,
                PlacementRequest(
                    mode="wall",
                    host_wall=placement.host_wall,
                    offset_mm=placement.offset_mm,
                    origin_x_mm=None,
                    origin_y_mm=None,
                    origin_z_mm=placement.origin_z_mm,
                    rotation_z_deg=None,
                ),
            )
        except ValueError as exc:
            report.add_error(
                "INVALID_WALL_PLACEMENT",
                str(exc),
                "room_placement.placement",
            )
            return None
        if not _placements_close(placement, expected_placement):
            report.add_error(
                "WALL_PLACEMENT_TRANSFORM_MISMATCH",
                "wall placement origin and rotation must be derived from wall and offset",
                "room_placement.placement",
            )
    elif placement.host_wall is not None or placement.offset_mm is not None:
        report.add_error(
            "INVALID_FREE_PLACEMENT",
            "free placement cannot retain host_wall or offset_mm",
            "room_placement.placement",
        )

    return build_room_placement(
        layout,
        plan.room,
        expected_placement,
        furniture_label=plan.furniture_label,
    )


def _validate_derived_room_output(
    actual: RoomPlacementPlan,
    expected: RoomPlacementPlan,
    report: ValidationReport,
) -> None:
    if not _points_close(
        actual.furniture_footprint,
        expected.furniture_footprint,
    ):
        report.add_error(
            "FURNITURE_FOOTPRINT_MISMATCH",
            "furniture footprint must match its envelope and placement transform",
            "room_placement.furniture_footprint",
        )
    for direction, expected_value in expected.clearances_mm.items():
        actual_value = actual.clearances_mm.get(direction)
        if actual_value is None or abs(actual_value - expected_value) > EPSILON:
            report.add_error(
                "ROOM_CLEARANCE_MISMATCH",
                f"{direction} clearance does not match the furniture footprint",
                f"room_placement.clearances_mm.{direction}",
            )


def _validate_room_fit(
    plan: RoomPlacementPlan,
    layout: CabinetLayout,
    report: ValidationReport,
) -> None:
    room = plan.room
    if any(
        x < -EPSILON
        or x > room.width_mm + EPSILON
        or y < -EPSILON
        or y > room.depth_mm + EPSILON
        for x, y in plan.furniture_footprint
    ) or plan.placement.origin_z_mm < -EPSILON or (
        plan.placement.origin_z_mm + layout.height
        > room.height_mm + EPSILON
    ):
        report.add_error(
            "FURNITURE_OUTSIDE_ROOM",
            "furniture envelope must remain inside the room",
            "room_placement.placement",
        )

    for obstacle in obstacle_collisions(plan, layout):
        report.add_error(
            "FURNITURE_OBSTACLE_COLLISION",
            f"furniture collides with obstacle: {obstacle.id}",
            "room_placement.room.obstacles",
        )
    for opening in opening_collisions(plan, layout):
        report.add_error(
            "FURNITURE_OPENING_COLLISION",
            f"furniture blocks {opening.kind}: {opening.id}",
            "room_placement.room.openings",
        )

    if layout.furniture_type == "wall_cabinet" and plan.placement.origin_z_mm <= 0:
        report.add_warning(
            "WALL_CABINET_AT_FLOOR_LEVEL",
            "wall cabinet placement has no mounting elevation",
            "room_placement.placement.origin_z_mm",
        )


def _placements_close(first: Any, second: Any) -> bool:
    return (
        first.mode == second.mode
        and first.host_wall == second.host_wall
        and first.offset_mm == second.offset_mm
        and abs(first.origin_x_mm - second.origin_x_mm) <= EPSILON
        and abs(first.origin_y_mm - second.origin_y_mm) <= EPSILON
        and abs(first.origin_z_mm - second.origin_z_mm) <= EPSILON
        and abs(
            ((first.rotation_z_deg - second.rotation_z_deg + 180.0) % 360.0)
            - 180.0
        )
        <= EPSILON
    )


def _points_close(
    first: tuple[tuple[float, float], ...],
    second: tuple[tuple[float, float], ...],
) -> bool:
    return len(first) == len(second) and all(
        abs(first_point[0] - second_point[0]) <= EPSILON
        and abs(first_point[1] - second_point[1]) <= EPSILON
        for first_point, second_point in zip(first, second)
    )


def _all_finite(*values: float) -> bool:
    return all(isfinite(value) for value in values)
````

## File: domain/skills/furniture-manufacturing/scripts/furniture_manufacturing/connectors/__init__.py
````python
"""Hardware connectors — each connector packages its own matching, drilling, and machining logic."""

from .base import Connector, HoleSpec
from .trinity import TrinityConnector
from .hinge import HingeConnector
from .shelf import ShelfPinConnector, TwoInOneConnector
from .back_mount import BackMountConnector
from .drawer_slide import DrawerSlideConnector

__all__ = [
    "Connector",
    "HoleSpec",
    "TrinityConnector",
    "HingeConnector",
    "TwoInOneConnector",
    "ShelfPinConnector",
    "BackMountConnector",
    "DrawerSlideConnector",
]

ALL_CONNECTORS = [
    TrinityConnector,
    HingeConnector,
    TwoInOneConnector,
    ShelfPinConnector,
    BackMountConnector,
    DrawerSlideConnector,
]
````

## File: domain/skills/furniture-manufacturing/scripts/furniture_manufacturing/connectors/drawer_slide.py
````python
"""抽屉滑轨连接件 — 抽屉滑轨五金匹配与 BOM。

滑轨螺钉安装属组装现场工艺，不生成孔位（与 cover/groove 螺钉一致）。
滑轨长度由**抽屉自身深度**决定，承重由**抽屉宽度**决定——尺寸取自抽屉
板件，不依赖柜体面板猜测。

抽屉板件契约（详见 references/drawer-component-design.md）：
- panel_type 含 "drawer"（如 drawer_front / drawer_side / drawer_bottom）；
- label 形如 "drawer_<角色>_<实例后缀>"，实例 key = label 最后一个
  "_" 分段（沿用动态板件命名，如 shelf_z999 → z999）；
- 每抽左右各 1 副，数量 = 2 × 抽屉实例数。
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from furniture_manufacturing.connectors.base import Connector, HoleSpec
from furniture_manufacturing.manufacturing_models import (
    HardwareRecord,
    MachiningOperation,
    PanelRecord,
)


class DrawerSlideConnector(Connector):
    """抽屉滑轨连接件：按抽屉实例匹配滑轨型号与数量。

    单一默认滑轨类型（三节轨侧装，与铰链精简为单一默认同思路）；
    隐藏轨/品牌选择待抽屉组件落地后由确认选择（options）注入。
    """

    name = "抽屉滑轨"
    hole_type_for_json = "drawer_slide"
    catalog_entry = "drawer_slides"
    rules_section = None

    # 默认滑轨类型与品牌（显式默认，非静默取 brands[0]）
    slide_type = "三节轨"
    default_brand: str = "默认"

    @staticmethod
    def _is_drawer_panel(panel: PanelRecord) -> bool:
        return "drawer" in panel.panel_type

    @staticmethod
    def _instance_key(panel: PanelRecord) -> str:
        """抽屉实例标识 = label 最后一个 "_" 分段（位置后缀）。

        约定：drawer_side_z300 / drawer_front_z300 同属抽屉 z300。
        无后缀（如 drawer_side）时以 label 自身为 key。
        """
        parts = panel.label.split("_")
        return parts[-1] if len(parts) >= 2 else panel.label

    def match(self, panels: List[PanelRecord]) -> Dict[str, Any]:
        drawer_panels = [p for p in panels if self._is_drawer_panel(p)]
        by_instance: Dict[str, List[PanelRecord]] = {}
        for panel in drawer_panels:
            by_instance.setdefault(self._instance_key(panel), []).append(panel)
        return {
            "drawers": drawer_panels,
            "instances": by_instance,
        }

    def generate_holes(self, panel: PanelRecord) -> List[HoleSpec]:
        # 滑轨螺钉为组装现场工艺，不生成孔位
        return []

    def boms(
        self,
        panels: List[PanelRecord],
        *,
        options: Mapping[str, Any] | None = None,
    ) -> List[HardwareRecord]:
        matched = self.match(panels)
        instances = matched["instances"]
        if not instances:
            return []

        opts = (options or {}).get(self.catalog_entry, {})
        opts = dict(opts) if isinstance(opts, Mapping) else {}

        # 每个抽屉实例算一副（左右各 1）；不同规格（长度/承重）分条记录
        per_spec: Dict[tuple, int] = {}
        for instance_panels in instances.values():
            depth = max(p.size_y for p in instance_panels)
            width = max(p.size_x for p in instance_panels)
            slide = self._match_slide(depth, width, opts)
            if not slide:
                continue
            key = (
                slide["brand"],
                slide["model"],
                slide["length_mm"],
                slide["load_rating"],
            )
            per_spec[key] = per_spec.get(key, 0) + 2

        records: List[HardwareRecord] = []
        for (brand, model, length, load), quantity in sorted(per_spec.items()):
            records.append(HardwareRecord(
                name=self.name,
                spec=f"{brand} {model} {length}mm {load}",
                quantity=quantity,
                unit="副",
                brand=brand,
                model=model,
                note="每抽左右各 1，投产前确认",
            ))
        return records

    def _match_slide(
        self,
        depth_mm: float,
        width_mm: float,
        opts: Dict[str, Any],
    ) -> Dict[str, Any]:
        """按抽屉深度匹配标准长度、按宽度定承重、选品牌。"""
        catalog = self.catalog.get(self.catalog_entry, {})
        entry = catalog.get(opts.get("variant", self.slide_type)) if catalog else None
        if not entry:
            return {}

        # 滑轨长度 ≤ 抽屉深度 − 50mm（尾部间隙）
        standard_lengths = sorted(entry.get("standard_lengths_mm", []))
        if not standard_lengths:
            return {}
        target_length = depth_mm - 50
        match_length = next(
            (length for length in reversed(standard_lengths) if length <= target_length),
            standard_lengths[0],  # 兜底最小号
        )

        # 承重级别
        load_rating = "45kg" if width_mm > 600 else "30kg"
        brand = self._pick_brand(entry, opts.get("brand"))

        return {
            "slide_type": self.slide_type,
            "brand": brand["name"],
            "model": brand["model"],
            "length_mm": match_length,
            "load_rating": load_rating,
            "mounting": entry.get("mounting", "侧装"),
            "gap_requirement_mm": entry.get("gap_requirement_mm", 12.5),
        }

    def _pick_brand(
        self,
        entry: Dict[str, Any],
        selection: str | None = None,
    ) -> Dict[str, str]:
        """按确认选择/显式默认解析品牌；歧义时抛错，不静默取第一个。"""
        return self.resolve_brand(
            entry.get("brands", []),
            selection or self.default_brand,
        )

    def machining_operations(self, panel: PanelRecord) -> List[MachiningOperation]:
        # 滑轨无柜体加工指令
        return []
````

## File: domain/skills/furniture-manufacturing/scripts/furniture_manufacturing/drilled_holes_glb.py
````python
"""导出孔位预览的 GLB/STEP 文件。

STEP 文件用 Assembly 分组建模，支持在 Viewer 中独立开关板件和各类孔位。
GLB 文件为向后兼容保留，含板件+孔位的 Compound 合并体。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import build123d as bd

from .connectors import ALL_CONNECTORS

# ── 板件类型 → 颜色 ──────────────────────────────────────────────
PANEL_TYPE_COLORS: dict[str, bd.Color] = {
    "side":      bd.Color(0.80, 0.70, 0.55, 0.30),
    "top":       bd.Color(0.80, 0.70, 0.55, 0.30),
    "bottom":    bd.Color(0.80, 0.70, 0.55, 0.30),
    "fixed_shelf": bd.Color(0.82, 0.72, 0.58, 0.30),
    "back":      bd.Color(0.65, 0.60, 0.50, 0.25),
    "back_rail": bd.Color(0.80, 0.70, 0.55, 0.30),
    "toe_kick":  bd.Color(0.60, 0.55, 0.45, 0.30),
    "door":      bd.Color(0.85, 0.78, 0.65, 0.50),
}
FALLBACK_PANEL_COLOR = bd.Color(0.75, 0.68, 0.55, 0.30)

# ── 打孔方向 → Rotation ────────────────────────────────────────
_DIRECTION_ROT: dict[str, bd.RotationLike] = {
    "+x": (bd.Axis.Y, 90),
    "-x": (bd.Axis.Y, -90),
    "+y": (bd.Axis.X, 90),
    "-y": (bd.Axis.X, -90),
    "+z": None,
    "-z": (bd.Axis.X, 180),
}

# ── 孔位分类 → Assembly 子组名称（由各 Connector 的 glb_group 派生）──
def _build_hole_group_map() -> dict[str, str]:
    group_map: dict[str, str] = {}
    for connector_cls in ALL_CONNECTORS:
        for hole_type, meta in connector_cls.hole_legend.items():
            group_map[hole_type] = meta.get("glb_group", "其他孔位")
    return group_map


HOLE_GROUP_MAP = _build_hole_group_map()


def _panel_color(panel: dict[str, Any]) -> bd.Color:
    ptype = str(panel.get("panel_type", panel.get("name", ""))).lower()
    return PANEL_TYPE_COLORS.get(ptype, FALLBACK_PANEL_COLOR)


def export_drilled_holes_glb(
    drilled_holes: dict[str, Any],
    output_path: str | Path,
    *,
    marker_thickness: float = 2.0,
) -> Path:
    """导出板件 + 孔位标记到单个 GLB（向后兼容）。"""
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    geometry = _build_geometry(drilled_holes, marker_thickness)
    if not geometry:
        compound = bd.Compound()
    else:
        compound = bd.Compound(children=geometry)
        compound.label = "cabinet_with_holes"
    bd.export_gltf(compound, str(output_path), binary=True)
    return output_path


def export_drilled_holes_step(
    drilled_holes: dict[str, Any],
    output_path: str | Path,
    *,
    marker_thickness: float = 2.0,
) -> Path:
    """导出嵌套 Compound 结构的 STEP 文件，支持 Viewer 按组 toggle。

    build123d 的 export_step 保留 Compound 层级和子 Solid 标签名。
    Viewer 将嵌套 Compound 按组显示，可独立隐藏/显示。
    """
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    group_solids = _build_grouped_geometry(drilled_holes, marker_thickness)

    # 每组建一个 Compound，包进根 Compound
    children: list[bd.Compound] = []
    for group_name, solids in group_solids.items():
        comp = bd.Compound(children=solids, label=group_name)
        children.append(comp)

    root = bd.Compound(children=children, label="cabinet_assembly")

    try:
        bd.export_step(root, str(output_path))
        glb_sidecar = Path(str(output_path) + ".glb")
        bd.export_gltf(root, str(glb_sidecar), binary=True)
    except Exception as exc:
        raise RuntimeError(
            f"unable to export drilled-hole STEP assembly: {output_path}"
        ) from exc

    for artifact in (output_path, glb_sidecar):
        if not artifact.is_file() or artifact.stat().st_size == 0:
            raise RuntimeError(f"drilled-hole artifact is missing or empty: {artifact}")

    return output_path


def _panel_solid(panel: dict[str, Any]) -> bd.Solid | None:
    """Build one panel solid, independent of its dynamic label."""
    box_info = panel.get("box", {})
    if not box_info:
        return None
    sx = float(box_info.get("x", 0))
    sy = float(box_info.get("y", 0))
    sz = float(box_info.get("z", 0))
    if min(sx, sy, sz) <= 0:
        return None
    px = float(box_info.get("pos_x", 0))
    py = float(box_info.get("pos_y", 0))
    pz = float(box_info.get("pos_z", 0))
    box = bd.Box(sx, sy, sz)
    box.color = _panel_color(panel)
    box.label = str(panel.get("label", "panel"))
    box.move(
        bd.Location(
            (
                px + sx / 2.0,
                py + sy / 2.0,
                pz + sz / 2.0,
            )
        )
    )
    return box


def _hole_solids(
    panel: dict[str, Any],
    marker_thickness: float,
) -> list[bd.Solid]:
    """Build the visual solids for every hole on one panel."""
    solids: list[bd.Solid] = []
    for hole in panel.get("holes", []):
        diam = float(hole.get("diameter", 8))
        color_hex = hole.get("color", "#888888")
        direction = str(hole.get("direction", "+z"))
        hole_type = str(hole.get("hole_type", "hole"))
        x = float(hole.get("x", 0))
        y = float(hole.get("y", 0))
        z = float(hole.get("z", 0))

        cyl = bd.Cylinder(
            radius=diam / 2.0,
            height=marker_thickness,
            align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER),
        )
        cyl.color = _hex_to_color(color_hex)
        cyl.label = hole_type

        rot = _DIRECTION_ROT.get(direction)
        transform = bd.Location((x, y, z))
        if rot is not None:
            transform = transform * bd.Rotation(*rot)
        cyl.move(transform)
        solids.append(cyl)
    return solids


def _build_grouped_geometry(
    drilled_holes: dict[str, Any],
    marker_thickness: float,
) -> dict[str, list[bd.Solid]]:
    """Group panels by source role and holes by machining type."""
    groups: dict[str, list[bd.Solid]] = {}
    for panel in drilled_holes.get("panels", []):
        panel_solid = _panel_solid(panel)
        if panel_solid is not None:
            groups.setdefault("板件", []).append(panel_solid)
        for solid in _hole_solids(panel, marker_thickness):
            groups.setdefault(
                HOLE_GROUP_MAP.get(solid.label, "其他孔位"),
                [],
            ).append(solid)
    return groups


def _build_geometry(
    drilled_holes: dict[str, Any],
    marker_thickness: float,
) -> list[bd.Solid]:
    """构建所有板件和孔位 solid 列表。"""
    geometry: list[bd.Solid] = []

    for panel in drilled_holes.get("panels", []):
        panel_solid = _panel_solid(panel)
        if panel_solid is not None:
            geometry.append(panel_solid)
        geometry.extend(_hole_solids(panel, marker_thickness))

    return geometry


def load_drilled_holes_from_json(json_path: str | Path) -> dict[str, Any]:
    """从 JSON 文件加载钻孔数据。"""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _hex_to_color(hex_str: str) -> bd.Color:
    """十六进制颜色 -> build123d Color（alpha=0.9）。"""
    hex_str = hex_str.lstrip("#")
    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0
    return bd.Color(r, g, b, 0.9)
````

## File: domain/skills/furniture-manufacturing/scripts/furniture_manufacturing/hardware_rules.yaml
````yaml
# ============================================================================
# 打孔规则 — 三合一 + 铰链
# ============================================================================

# ── 三合一系统排钻 ──────────────────────────────────────
system_32_drilling:
  # 默认偏移
  first_hole_mm: 64       # 首孔距板边
  last_hole_mm: 64        # 末孔距板边
  max_spacing_mm: 512     # 孔间最大间距
  min_spacing_mm: 32      # 孔间最小间距（32mm 系统）
  # 孔位取整精度
  snap_to_mm: 0.5
  # 板材方向的孔位计算长度
  drill_length_by_type:
    side: height           # 侧板沿高度打孔
    divider: height        # 中立板沿高度打孔
    top: width             # 顶板沿宽度打孔
    bottom: width          # 底板沿宽度打孔
    fixed_shelf: width     # 固定层板沿宽度打孔

# ── 背板安装打孔（软件暂定，投产前确认）──────────────────
back_mount_drilling:
  insert:
    # 内嵌背板四边三合一连接点
    first_hole_mm: 64
    max_spacing_mm: 400

# ── 铰链打孔 ──────────────────────────────────────────
hinge_drilling:
  # ── 数量与偏移规则：按门板长度分档 ──
  # 每档独立定义 count / top_offset / bottom_offset
  count_by_door_height:
    - max_height_mm: 480
      count: 2
      top_offset_mm: 80
      bottom_offset_mm: 80
    - max_height_mm: 980
      count: 2
      top_offset_mm: 120
      bottom_offset_mm: 120
    - max_height_mm: 1500
      count: 3
      top_offset_mm: 120
      bottom_offset_mm: 120
    - max_height_mm: 2100
      count: 4
      top_offset_mm: 120
      bottom_offset_mm: 120
    - max_height_mm: 2750
      count: 5
      top_offset_mm: 120
      bottom_offset_mm: 120

  # ── 全局孔位参数 ──
  position:
    max_spacing_mm: 600      # 铰链之间最大间距，超过时自动增加铰链数量
    snap_to_mm: 0.5          # 孔位取整精度：0=不取整, 0.5=半毫米, 1.0=整毫米

  # ── 避让规则 ──
  conflict_avoidance:
    # 铰链孔位与系统排钻孔的最小间距 (mm)
    min_spacing_to_system_holes_mm: 50

    # 铰链孔位与层板位置的最小间距 (mm)
    min_spacing_to_shelf_mm: 80

    # 冲突时可微调的最大偏移范围 (mm)
    adjustment_max_shift_mm: 30

    # 避让优先级：shelf > system_holes（层板比系统孔更优先避开）
    priority: [shelf, system_holes]
````

## File: domain/skills/furniture-manufacturing/scripts/furniture_manufacturing/manufacturing_models.py
````python
"""Manufacturing-stage panel, hardware, and machining records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping


@dataclass
class PanelRecord:
    label: str
    name: str
    panel_type: str
    material: str
    thickness: float
    length_mm: float
    width_mm: float
    size_x: float
    size_y: float
    size_z: float
    quantity: int = 1
    drill_length: float = 0.0
    edge_banding: Dict[str, str] = field(default_factory=dict)
    note: str = ""
    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0
    depends_on: list[str] = field(default_factory=list)
    door_hinge_side: str | None = None
    door_overlay: str | None = None
    back_mount: str = ""
    inner_face: str = ""
    outer_face: str = ""
    cam_face: str | None = None
    joints: list = field(default_factory=list)  # list[PanelJoint], face-to-edge adjacencies
    movable_shelf_connector: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PanelRecord":
        """Restore serialized panel joints at the manufacturing boundary."""

        from furniture_panel_planning.joint_topology import PanelJoint

        values = dict(data)
        raw_joints = values.get("joints", [])
        if not isinstance(raw_joints, list):
            raise ValueError("manufacturing panel joints must be a list")
        values["joints"] = [
            item if isinstance(item, PanelJoint) else PanelJoint(**item)
            for item in raw_joints
        ]
        return cls(**values)

    @property
    def area_m2(self) -> float:
        return self.length_mm * self.width_mm * self.quantity / 1_000_000

    @property
    def volume_m3(self) -> float:
        return (
            self.length_mm * self.width_mm * self.thickness * self.quantity
            / 1_000_000_000
        )

    def edge_banding_summary(self) -> str:
        if not self.edge_banding:
            return "无"
        return ", ".join(
            f"{edge}:{material}" for edge, material in self.edge_banding.items()
        )

    # ── 几何接口（孔位定位 / 局部坐标化的地基）─────────────────────
    # 当前为轴对齐矩形实现；异形/姿态内核只需替换这几个方法的内部实现，
    # 下游 Connector / 校验 / 导出不再直接读 size_*/pos_*。

    def face_position(self, face_dir: str) -> float:
        """语义面在其法向轴上的世界坐标。

        face_dir 如 "+x" → 面板 x 最大值，"-x" → 面板 x 最小值。
        """
        axis = face_dir[1] if len(face_dir) >= 2 else ""
        origin = {"x": self.pos_x, "y": self.pos_y, "z": self.pos_z}.get(axis, 0.0)
        if face_dir.startswith("-"):
            return origin
        return origin + self.extent(axis)

    def extent(self, axis: str) -> float:
        """面板在指定轴（"x"/"y"/"z"）上的尺寸。"""
        return {"x": self.size_x, "y": self.size_y, "z": self.size_z}.get(axis, 0.0)

    def center_along(self, axis: str) -> float:
        """面板在指定轴上的中心世界坐标。"""
        origin = {"x": self.pos_x, "y": self.pos_y, "z": self.pos_z}.get(axis, 0.0)
        return origin + self.extent(axis) / 2.0

    def to_global(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        """局部坐标 → 世界坐标（当前轴对齐：仅平移）。"""
        return (self.pos_x + x, self.pos_y + y, self.pos_z + z)

    def to_local(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        """世界坐标 → 局部坐标（当前轴对齐：仅平移）。"""
        return (x - self.pos_x, y - self.pos_y, z - self.pos_z)


@dataclass(frozen=True)
class MachiningOperation:
    id: str
    operation_type: str
    target_panel: str
    size_x: float
    size_y: float
    size_z: float
    pos_x: float
    pos_y: float
    pos_z: float
    note: str = ""


@dataclass
class HardwareRecord:
    name: str
    spec: str
    quantity: int
    brand: str = "默认"
    model: str = ""
    unit: str = "个"
    note: str = ""
    drilling: list = None  # type: ignore[assignment]
````

## File: domain/skills/furniture-manufacturing/scripts/furniture_manufacturing/validation.py
````python
"""Validation owned by the manufacturing-planning stage."""

from __future__ import annotations

from furniture_delivery_validation.validation import ValidationReport
from furniture_panel_planning.panel_spec import FurnitureSpec, resolve_back_mount
from furniture_panel_planning.panel_models import PanelPlacement

from .connectors import ALL_CONNECTORS
from .hole_validator import (
    HoleValidationError,
    validate_hole_bounds,
    validate_hole_depth,
    validate_holes_no_interference,
)
from .manufacturing_bom import (
    BOMReport,
    VALID_MANUFACTURING_READINESS,
    emit_drilled_holes,
)


def validate_manufacturing(
    spec: FurnitureSpec,
    bom: BOMReport,
    placements: list[PanelPlacement],
) -> ValidationReport:
    report = ValidationReport(stage="manufacturing_planned")
    if bom.requested_options:
        report.add_warning(
            "REQUESTED_MANUFACTURING_OPTIONS_PENDING",
            "requested manufacturing options are recorded but remain preliminary",
            "requested_options",
        )
    if bom.appearance:
        report.add_warning(
            "REQUESTED_APPEARANCE_PENDING",
            "appearance preferences are recorded for manufacturing review",
            "appearance",
        )
    if bom.readiness not in VALID_MANUFACTURING_READINESS:
        report.add_error(
            "INVALID_MANUFACTURING_READINESS",
            "manufacturing readiness must be one of: "
            + ", ".join(sorted(VALID_MANUFACTURING_READINESS)),
            "readiness",
        )
    if bom.panel_count != len(placements):
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
    placement_by_id = {item.id: item for item in placements}
    placement_ids = set(placement_by_id)
    manufacturing_ids = {item.label for item in bom.panels}
    if placement_ids != manufacturing_ids:
        report.add_error(
            "MANUFACTURING_PANEL_ID_MISMATCH",
            "manufacturing records must preserve every confirmed panel id",
        )
    operation_ids: set[str] = set()
    for operation in bom.operations:
        if operation.id in operation_ids:
            report.add_error(
                "DUPLICATE_OPERATION_ID",
                f"duplicate machining operation: {operation.id}",
                operation.id,
            )
        operation_ids.add(operation.id)
        if operation.target_panel not in placement_ids:
            report.add_error(
                "UNKNOWN_OPERATION_TARGET",
                f"{operation.id} targets unknown panel {operation.target_panel}",
                operation.id,
            )
        else:
            target = placement_by_id[operation.target_panel]
            outside_target = False
            for axis, size, position, target_size, target_position in (
                ("x", operation.size_x, operation.pos_x, target.size_x, target.pos_x),
                ("y", operation.size_y, operation.pos_y, target.size_y, target.pos_y),
                ("z", operation.size_z, operation.pos_z, target.size_z, target.pos_z),
            ):
                if (
                    position < target_position - 1e-6
                    or position + size > target_position + target_size + 1e-6
                ):
                    report.add_error(
                        "OPERATION_OUTSIDE_TARGET",
                        f"{operation.id} exceeds {operation.target_panel} on {axis.upper()}",
                        operation.id,
                    )
                    outside_target = True
            if "back_groove" in operation.id and outside_target:
                report.add_error(
                    "GROOVE_OUTSIDE_TARGET",
                    f"{operation.id} must remain inside its target panel envelope",
                    operation.id,
                )
        if operation.operation_type != "cut_box":
            report.add_error(
                "UNSUPPORTED_OPERATION",
                f"unsupported machining operation: {operation.operation_type}",
                operation.id,
            )
        if min(operation.size_x, operation.size_y, operation.size_z) <= 0:
            report.add_error(
                "NON_POSITIVE_OPERATION_SIZE",
                f"{operation.id} must have positive cutter dimensions",
                operation.id,
            )
    expected_back_groove_ids = {
        "left_side_back_groove",
        "right_side_back_groove",
        "top_back_groove",
        "bottom_back_groove",
    }
    back_groove_operations = [
        operation
        for operation in bom.operations
        if "back_groove" in operation.id
    ]
    actual_back_groove_ids = {
        operation.id for operation in back_groove_operations
    }
    back_mount = resolve_back_mount(
        spec.back_mount,
        spec.back_thickness,
        spec.board_thickness,
    )
    if (
        back_mount == "groove"
        and actual_back_groove_ids != expected_back_groove_ids
    ):
        report.add_error(
            "INCOMPLETE_BACK_GROOVES",
            "grooved back strategy requires four target-specific groove cuts",
            "operations",
        )
    if back_mount == "groove":
        if spec.groove_depth <= 0:
            report.add_error(
                "INVALID_GROOVE_DEPTH",
                "groove_depth must be greater than zero",
                "groove_depth",
            )
        elif spec.groove_depth > spec.board_thickness:
            report.add_error(
                "GROOVE_DEPTH_EXCEEDS_PANEL_THICKNESS",
                "groove_depth cannot exceed board_thickness",
                "groove_depth",
            )
        if spec.groove_clearance < 0:
            report.add_error(
                "INVALID_GROOVE_CLEARANCE",
                "groove_clearance cannot be negative",
                "groove_clearance",
            )
        expected_groove_width = (
            spec.back_thickness + spec.groove_clearance
        )
        for operation in back_groove_operations:
            if abs(operation.size_y - expected_groove_width) > 1e-6:
                report.add_error(
                    "GROOVE_WIDTH_MISMATCH",
                    f"{operation.id} does not preserve the specified groove width",
                    operation.id,
                )
    elif back_mount != "groove" and back_groove_operations:
        report.add_error(
            "UNEXPECTED_BACK_GROOVES",
            f"{back_mount} back strategy must not contain groove cuts",
            "operations",
        )
    manufacturing_by_id = {item.label: item for item in bom.panels}
    recorded_mounts = {item.back_mount for item in bom.panels}
    if recorded_mounts != {back_mount}:
        report.add_error(
            "BACK_MOUNT_CONTEXT_MISMATCH",
            "every manufacturing panel must retain the resolved back_mount",
            "panels",
        )
    back_panel = manufacturing_by_id.get("back_panel")
    expected_back_edges = (
        {} if back_mount == "groove"
        else {"四边": "ABS 1.0mm同色"}
    )
    if back_panel is None or back_panel.edge_banding != expected_back_edges:
        report.add_error(
            "BACK_EDGE_BANDING_MISMATCH",
            f"{back_mount} back strategy has incorrect edge banding",
            "back_panel",
        )
    rails = [
        item for item in bom.panels if item.panel_type == "back_rail"
    ]
    if any(
        rail.edge_banding != {"四边": "ABS 1.0mm同色"}
        for rail in rails
    ):
        report.add_error(
            "BACK_RAIL_EDGE_BANDING_MISMATCH",
            "back rails must follow the repository four-edge rule",
            "back_rail",
        )

    # ── 孔位几何校验：边界/深度/干涉（hole_validator）──────────────
    hole_specs_by_panel: dict[str, list] = {}
    for connector_cls in ALL_CONNECTORS:
        connector = connector_cls()
        for hole in connector.generate_holes_for_panels(bom.panels):
            hole_specs_by_panel.setdefault(hole.panel_label, []).append(hole)
    panel_records_by_label = {item.label: item for item in bom.panels}
    for label, holes in hole_specs_by_panel.items():
        panel = panel_records_by_label.get(label)
        if panel is None:
            continue
        for hole in holes:
            try:
                validate_hole_bounds(hole, panel)
            except HoleValidationError as exc:
                report.add_error("HOLE_OUTSIDE_PANEL", str(exc), label)
            try:
                validate_hole_depth(hole, panel)
            except HoleValidationError as exc:
                report.add_error("HOLE_DEPTH_EXCEEDS_PANEL", str(exc), label)
        try:
            validate_holes_no_interference(holes, panel)
        except HoleValidationError as exc:
            report.add_error("HOLE_INTERFERENCE", str(exc), label)

    drilled = emit_drilled_holes(bom)
    # 五金专属校验：由各 Connector 自声明，新增五金不再改这里
    for connector_cls in ALL_CONNECTORS:
        connector_cls().validate(report, bom.panels, bom.hardware, drilled)
    return report
````

## File: domain/skills/furniture-panel-planning/references/cabinet-topologies/floor_cabinet.yaml
````yaml
# 落地柜板件拓扑 — 标准落地柜/储物柜的柜体结构定义
# 拓扑数据不包含任何坐标信息；坐标由 CabinetFrame + 空间求解器计算。

name: 落地柜
description: "标准落地柜（储物柜/底柜），前开门，背面靠墙，底部踢脚"
frame:
  front: "+y"
  top: "+z"

enclosure:
  left_side:
    type: panel
    semantic_face: left
    material: carcass
  right_side:
    type: panel
    semantic_face: right
    material: carcass
  top:
    type: panel
    semantic_face: top
    material: carcass
    cam_face: bottom      # 偏心轮从底板方向操作
  bottom:
    type: panel
    semantic_face: bottom
    material: carcass
    cam_face: bottom      # 偏心轮从底板方向操作
  back:
    type: back_panel
    semantic_face: back
    material: back
    mount_modes: [groove, insert, cover]
  front:
    type: opening
    semantic_face: front
    subtypes: [doors]

base:
  type: toe_kick
  height_field: toe_kick_height
  faces: [front, back]
  rear_offset_field: toe_kick_reveal_back
  front_offset_field: toe_kick_reveal_front
  support_count_field: toe_kick_support_count

internals:
  # 层板由 spec.shelves 驱动（从上到下、固定/活动混排），不再用 count_field
  drawers:
    type: full_height          # 整高抽屉区：抽屉占满内部净高与前开口
    count_field: drawer_count
    face_mode: none            # 无面板：前板即前脸
    # 净空、层缝和抽屉板厚均来自已准入的 FurnitureSpec；拓扑不持有方案默认值。
    # front_overlap（前板对盒体侧板的覆盖）按抽屉位置派生：
    #   顶/中间抽屉 0（顶板盖抽面、抽屉间无覆盖）；最底抽屉 18（全盖底板）。
    #   将来门+抽屉混合区按上方构造推导：共盖层板 9 / 顶板盖 0。
  dividers: []
````

## File: domain/skills/furniture-panel-planning/references/cabinet-topologies/wall_cabinet.yaml
````yaml
# 吊柜板件拓扑 — 壁挂式吊柜的柜体结构定义

name: 吊柜
description: "壁挂式吊柜，前开门，无踢脚，挂墙安装"
frame:
  front: "+y"
  top: "+z"

enclosure:
  left_side:
    type: panel
    semantic_face: left
    material: carcass
  right_side:
    type: panel
    semantic_face: right
    material: carcass
  top:
    type: panel
    semantic_face: top
    material: carcass
    cam_face: bottom
  bottom:
    type: panel
    semantic_face: bottom
    material: carcass
    cam_face: bottom
  back:
    type: back_panel
    semantic_face: back
    material: back
    mount_modes: [groove, insert, cover]
  front:
    type: opening
    semantic_face: front
    subtypes: [doors]

base:
  type: none   # 吊柜无踢脚

internals:
  # 层板由 spec.shelves 驱动（从上到下、固定/活动混排），不再用 count_field
  dividers: []
````

## File: domain/skills/furniture-panel-planning/references/panel-definition-rules.md
````markdown
# 板件定义规则

回答“有哪些实体家具部件？”；直接位于已确认设计意图后、制造/特征树前。板件是制造零件，不是 CAD 实体，独立房间布局不是前置条件。

## 记录

常见角色：左右侧板、顶/底/背板、层/隔板、门/抽屉面、横撑和踢脚板。每块记录稳定标识、角色、成品尺寸/厚度、材料、数量、朝向、位置和制造注释。

## 板件规则

- 柜型拓扑归本阶段 `references/cabinet-topologies/` 所有；设计意图只记录
  `furniture_type`，不得承载板件构成或板件面关系。
- 用角色及其与成品包络/区域的关系表达板件；位置用最小角点、包络、面或板件关系。
- 层板和隔板不得与选定的背板结构冲突。
- 门板和抽屉面板必须关联其开启策略及净空包络。
- 单门（`n_doors=1`）必须由提案显式提交 `door_hinge_side=left/right`，
  代码拒绝缺省；标准双门由代码确定性推导（左门左铰、右门右铰）并写入各门板；
  门数更多但开启策略未确认时保持为空，不由制造阶段猜测多门开启关系。
- 当前 `drawer_count>0` 的规范语义仅为整高抽屉区；必须同时提交
  空 `shelves` 与 `n_doors=0`。混合门、层板和抽屉分区先由 LLM 继续消歧，
  不得由代码按数量优先级静默丢弃任何区域。
- 抽屉每侧净空、层缝、底/背板厚和后部净空分别来自已准入的
  `drawer_side_clearance/drawer_layer_gap/drawer_bottom_thickness/`
  `drawer_back_thickness/drawer_back_clearance`。板件代码不得读取制造五金目录
  来猜测这些值；制造阶段只能选择与已确认几何兼容的滑轨。
- BOM 和五金记录应与 CAD 实体分离。
- 背板结构、精确净空和三种模式尺寸统一按 [背板结构规则](back-construction-rules.md)；本文件不复制解析公式。
- 入槽背拉条夹在左右侧板之间，数量按 `floor(internal_height / 500)` 计算，并使用 `back_rail_height` 等距布置；数量和净距必须由本阶段校验，净距不得小于等于 0。
- 本阶段只定背板/背拉条尺寸、位置、依赖；槽、封边、连接和孔位归制造阶段。
- 踢脚高度和前后退让在本阶段首次物化并形成精确区域；随后生成前后踢脚板和支撑板。提案显式提交 `toe_kick_support_count=null` 时才调用公式：`W < 600 → 0`，否则 `1 + floor((W-600)/300)`；显式整数直接使用。支撑净距为 `(internal_width - count×board_thickness)/(count+1)`，必须大于 0。

## 边界

- 不定义制造规则、封边/钻孔/五金、特征树/CAD/STEP、JSON、命令或工厂批准状态。
- 材料/公差/连接/封边/五金交给制造；建模依赖和 CAD 表达交给特征树。
````

## File: domain/skills/furniture-panel-planning/scripts/furniture_panel_planning/panel_planning.py
````python
"""Panels-planned stage entrypoint."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .cabinet_panel_planner import build_cabinet_panels
from .panel_models import PanelPlacement
from .panel_spec import FurnitureSpec
from .structure_planning import CabinetStructure


def plan_panels(
    spec: FurnitureSpec,
    layout: CabinetStructure | Any,
) -> list[PanelPlacement]:
    """Create physical panel roles, sizes, and placements."""
    if not isinstance(layout, CabinetStructure):
        # Compatibility for direct pre-refactor callers. The serial workflow
        # never requests or imports a room-layout result.
        spec = FurnitureSpec.from_dict(asdict(spec))
        expected = (
            spec.furniture_type,
            spec.width,
            spec.depth,
            spec.height,
            spec.n_doors,
        )
        received = (
            getattr(layout, "furniture_type", None),
            getattr(layout, "width", None),
            getattr(layout, "depth", None),
            getattr(layout, "height", None),
            getattr(layout, "door_count", None),
        )
        if received != expected:
            raise ValueError("legacy layout does not match the panel specification")
        layout = CabinetStructure.from_spec(spec)
    return build_cabinet_panels(spec, layout)
````

## File: domain/skills/furniture-panel-planning/scripts/furniture_panel_planning/structure_planning.py
````python
"""Exact cabinet construction geometry owned by panels_planned."""

from __future__ import annotations

from dataclasses import dataclass

from .panel_spec import FurnitureSpec


@dataclass(frozen=True)
class CabinetStructure:
    """Exact carcass, internal-clearance, back, and toe-kick geometry."""

    furniture_type: str
    width: float
    depth: float
    height: float
    side_depth: float
    carcass_y_start: float
    carcass_y_end: float
    internal_width: float
    internal_height: float
    internal_x_start: float
    internal_x_end: float
    internal_y_start: float
    internal_y_end: float
    internal_z_start: float
    internal_z_end: float
    back_plane_y: float
    back_mount: str
    toe_kick_height: float
    toe_kick_rear_y: float
    toe_kick_front_y: float
    door_count: int

    @classmethod
    def from_spec(cls, spec: FurnitureSpec) -> "CabinetStructure":
        board = spec.board_thickness
        carcass_y_end = spec.depth - spec.door_thickness - spec.door_hinge_gap
        if spec.back_mount == "cover":
            carcass_y_start = spec.back_thickness
            back_plane_y = 0.0
            internal_y_start = carcass_y_start
        else:
            carcass_y_start = 0.0
            back_plane_y = spec.back_offset
            internal_y_start = spec.back_offset + spec.back_thickness
        # Topology-specific legality was checked during proposal admission;
        # geometry consumes the admitted value without silently overriding it.
        toe_kick = spec.toe_kick_height
        return cls(
            furniture_type=spec.furniture_type,
            width=spec.width,
            depth=spec.depth,
            height=spec.height,
            side_depth=carcass_y_end - carcass_y_start,
            carcass_y_start=carcass_y_start,
            carcass_y_end=carcass_y_end,
            internal_width=spec.width - 2 * board,
            internal_height=spec.height - toe_kick - 2 * board,
            internal_x_start=board,
            internal_x_end=spec.width - board,
            internal_y_start=internal_y_start,
            internal_y_end=carcass_y_end,
            internal_z_start=toe_kick + board,
            internal_z_end=spec.height - board,
            back_plane_y=back_plane_y,
            back_mount=spec.back_mount,
            toe_kick_height=toe_kick,
            toe_kick_rear_y=carcass_y_start + spec.toe_kick_reveal_back,
            toe_kick_front_y=carcass_y_end - spec.toe_kick_reveal_front,
            door_count=spec.n_doors,
        )
````

## File: domain/skills/furniture-panel-planning/scripts/furniture_panel_planning/topology_solver.py
````python
"""Topology solver — convert cabinet topology data into panel placements.

Reads a cabinet topology YAML and a FurnitureSpec, then computes every panel's
3-D placement with correct semantic face directions (inner/outer/cam).

The solver is universal — it does not branch on furniture_type.  All
cabinet-specific knowledge lives in the topology YAML files under
references/cabinet-topologies/.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .cabinet_frame import CabinetFrame, _negate as negate_axis
from .joint_topology import compute_joints
from .panel_models import PanelPlacement
from .panel_spec import FurnitureSpec, resolve_shelf_gaps
from .panel_rules import (
    back_rail_clear_spacing,
    resolve_back_rail_count,
    resolve_door_hinge_side,
    resolve_toe_kick_support_count,
    toe_kick_support_clear_spacing,
)
from .structure_planning import CabinetStructure


def _load_topology(furniture_type: str) -> dict[str, Any]:
    """Load a topology YAML file for the given furniture type."""
    topo_dir = (
        Path(__file__).resolve().parents[2]
        / "references"
        / "cabinet-topologies"
    )
    path = topo_dir / f"{furniture_type}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"No topology defined for furniture_type='{furniture_type}'. "
            f"Expected: {path}"
        )
    with open(path, encoding="utf-8") as fp:
        return yaml.safe_load(fp) or {}


def _resolve_semantic_face(face_name: str, frame: CabinetFrame) -> str:
    """Map a semantic face name to a signed world axis.

    face_name is one of: front, back, top, bottom, left, right
    """
    return getattr(frame, face_name)


def solve_panel_placements(
    spec: FurnitureSpec,
    layout: CabinetStructure,
) -> list[PanelPlacement]:
    """Compute all panel placements from topology + spec + layout.

    Parameters
    ----------
    spec : FurnitureSpec
        Normalized cabinet dimensions and parameter choices.
    layout : CabinetStructure
        Panel-stage construction geometry and exact clear regions.

    Returns
    -------
    list[PanelPlacement]
        Every physical panel with size, position, and face semantics.
    """
    topology = _load_topology(spec.furniture_type)
    frame = CabinetFrame(**topology["frame"])

    placements: list[PanelPlacement] = []

    # ── Enclosure panels ──────────────────────────────────────────
    enclosure = topology.get("enclosure", {})
    board = spec.board_thickness

    for side_name, side_def in enclosure.items():
        sf_value = side_def.get("semantic_face", "")
        face_dir = _resolve_semantic_face(sf_value, frame)

        if side_def.get("type") == "opening":
            # Opening — generate door panels (managed separately below)
            continue

        if side_def.get("type") == "back_panel":
            placements.extend(_back_panel_variants(spec, layout, side_name, side_def, face_dir, frame))
            continue

        # Standard enclosure panel
        panel = _build_enclosure_panel(spec, layout, side_name, side_def, face_dir)
        placements.append(panel)

    # ── Doors ─────────────────────────────────────────────────────
    # 整高抽屉区下前开口被抽屉占满，不生成门
    front_side = enclosure.get("front", {})
    if front_side.get("type") == "opening" and spec.drawer_count <= 0:
        for subtype in front_side.get("subtypes", []):
            if subtype == "doors":
                placements.extend(_door_panels(spec, layout, frame))

    # ── Base (toe kick) ───────────────────────────────────────────
    base_def = topology.get("base", {})
    if base_def.get("type") == "toe_kick" and layout.toe_kick_height > 0:
        placements.extend(_toe_kick_panels(spec, layout, base_def, frame))

    # ── Internal shelves / drawers ────────────────────────────────
    internals = topology.get("internals", {})
    if spec.drawer_count > 0:
        # 整高抽屉区：抽屉占满内部净高，不生成固定层板
        drawers_def = internals.get("drawers", {})
        if drawers_def.get("type") == "full_height":
            placements.extend(_drawer_panels(spec, layout, drawers_def, frame))
    else:
        if spec.shelves:
            placements.extend(_shelves_from_spec(spec, layout, frame))

    # ── Connection topology ──────────────────────────────────────
    joints = compute_joints(placements)
    for panel in placements:
        panel.joints = [
            j for j in joints
            if j.female_id == panel.id or j.male_id == panel.id
        ]

    return placements


# ═══════════════════════════════════════════════════════════════════
# Panel builders
# ═══════════════════════════════════════════════════════════════════

def _build_enclosure_panel(
    spec: FurnitureSpec,
    layout: CabinetStructure,
    side_name: str,
    side_def: dict[str, Any],
    face_dir: str,
) -> PanelPlacement:
    """Build a single enclosure panel."""
    board = spec.board_thickness
    axis = frame_axis(face_dir)  # x, y, or z
    sign = frame_sign(face_dir)  # +1 or -1

    # Compute panel size and position based on which enclosure face this is
    if axis == "x":
        # Side panel (left or right) — broad face is Y-Z plane
        if sign > 0:
            # Right face: panel sits at x=width-board
            px = layout.width - board
            inner = "-x"    # inner face points left (toward cabinet center)
        else:
            # Left face: panel sits at x=0
            px = 0.0
            inner = "+x"    # inner face points right
        sx, sy, sz = board, layout.side_depth, layout.height
        py = layout.carcass_y_start
        pz = 0.0
        name_map = {"left_side": "左侧板", "right_side": "右侧板"}
        ptype = "side"

    elif axis == "z":
        # Horizontal panel (top or bottom) — broad face is X-Y plane
        sx = layout.internal_width
        sy = layout.side_depth
        sz = board
        px = layout.internal_x_start
        py = layout.carcass_y_start
        if sign > 0:
            pz = layout.height - board  # top
            inner = "-z"
        else:
            pz = layout.toe_kick_height  # bottom
            inner = "+z"
        name_map = {"top": "顶板", "bottom": "底板"}
        ptype = "top" if sign > 0 else "bottom"

    else:
        raise ValueError(
            f"enclosure panel '{side_name}' has unsupported face axis "
            f"'{face_dir}'; back and front openings use dedicated builders"
        )

    name = name_map.get(side_name, side_name)
    outer = face_dir
    cam = side_def.get("cam_face")
    if cam:
        cam = _resolve_semantic_face(cam, _frame_from_spec(spec))

    return PanelPlacement(
        id=f"{side_name}_panel",
        name=name,
        panel_type=ptype,
        size_x=sx, size_y=sy, size_z=sz,
        pos_x=px, pos_y=py, pos_z=pz,
        material_role="carcass",
        inner_face=inner,
        outer_face=outer,
        cam_face=cam,
        note=f"{name}，厚{board:.0f}mm",
    )


def _back_panel_variants(
    spec: FurnitureSpec,
    layout: CabinetStructure,
    side_name: str,
    side_def: dict[str, Any],
    face_dir: str,
    frame: CabinetFrame,
) -> list[PanelPlacement]:
    """Generate back panel and optional back rails for the selected mount mode."""
    board = spec.board_thickness
    back_mount = layout.back_mount
    back_y = layout.back_plane_y
    # 背板: 外表面=柜体背面, 内表面指向柜内=柜体前面
    outer = face_dir          # frame.back
    inner = negate_axis(outer)  # frame.front

    result: list[PanelPlacement] = []

    if back_mount == "groove":
        groove_d = spec.groove_depth
        bw = layout.internal_width + 2 * groove_d
        bh = layout.internal_height + 2 * groove_d
        result.append(PanelPlacement(
            id="back_panel", name="背板", panel_type="back",
            size_x=bw, size_y=spec.back_thickness, size_z=bh,
            pos_x=layout.internal_x_start - groove_d,
            pos_y=back_y,
            pos_z=layout.internal_z_start - groove_d,
            material_role="back",
            depends_on=["left_side_panel", "right_side_panel", "top_panel", "bottom_panel"],
            inner_face=inner, outer_face=outer, cam_face=None,
            note=f"四边入槽{groove_d:.0f}mm的成品背板",
        ))
        # back rails
        rail_h = spec.back_rail_height
        rail_count = resolve_back_rail_count(
            back_mount,
            layout.internal_height,
            rail_h,
        )
        if rail_h > 0 and rail_count > 0:
            step = back_rail_clear_spacing(
                layout.internal_height,
                rail_count,
                rail_h,
            )
            for i in range(rail_count):
                rz = layout.internal_z_start + step + i * (rail_h + step)
                result.append(PanelPlacement(
                    id=f"back_rail_{i + 1}", name=f"背拉条{i + 1}",
                    panel_type="back_rail",
                    size_x=layout.internal_width, size_y=board, size_z=rail_h,
                    pos_x=layout.internal_x_start, pos_y=layout.carcass_y_start, pos_z=rz,
                    material_role="carcass",
                    depends_on=["left_side_panel", "right_side_panel"],
                    inner_face="+y", outer_face="-y", cam_face=None,
                    note=f"背板拉条，{rail_h:.0f}×{board:.0f}mm",
                ))

    elif back_mount == "insert":
        result.append(PanelPlacement(
            id="back_panel", name="背板", panel_type="back",
            size_x=layout.internal_width, size_y=spec.back_thickness, size_z=layout.internal_height,
            pos_x=layout.internal_x_start, pos_y=back_y, pos_z=layout.internal_z_start,
            material_role="back",
            depends_on=["left_side_panel", "right_side_panel", "top_panel", "bottom_panel"],
            inner_face=inner, outer_face=outer, cam_face=None,
            note="内嵌背板，三合一连接",
        ))

    else:  # cover
        result.append(PanelPlacement(
            id="back_panel", name="背板", panel_type="back",
            size_x=layout.width, size_y=spec.back_thickness, size_z=layout.height,
            pos_x=0.0, pos_y=0.0, pos_z=0.0,
            material_role="back",
            depends_on=["left_side_panel", "right_side_panel", "top_panel", "bottom_panel"],
            inner_face=inner, outer_face=outer, cam_face=None,
            note="外盖背板，覆盖整个背面",
        ))

    return result


def _door_panels(
    spec: FurnitureSpec,
    layout: CabinetStructure,
    frame: CabinetFrame,
) -> list[PanelPlacement]:
    """Generate door panels on the front face of the cabinet."""
    count = layout.door_count
    if count <= 0:
        return []

    margin = spec.door_margin
    dw = (layout.width - margin * 2 * count) / count
    dh = layout.height - layout.toe_kick_height - margin * 2
    dy = layout.carcass_y_end + spec.door_hinge_gap

    # Door inner face points into the cabinet (= opposite of front)
    inner = frame.back   # back of cabinet = door inner face
    outer = frame.front  # front of cabinet = door outer face

    panels: list[PanelPlacement] = []
    for index in range(count):
        if count == 1:
            pid, pname = "single_door", "门板"
            x = layout.width / 2 - dw / 2
        elif count == 2:
            pid = "left_door" if index == 0 else "right_door"
            pname = "左门板" if index == 0 else "右门板"
            x = margin if index == 0 else layout.width - margin - dw
        else:
            pid = f"door_{index + 1}_door"
            pname = f"门板{index + 1}"
            x = margin * (2 * (index + 1) - 1) + dw * index
        hinge_side = resolve_door_hinge_side(
            count,
            index,
            spec.door_hinge_side,
        )

        panels.append(PanelPlacement(
            id=pid, name=pname, panel_type="door",
            size_x=dw, size_y=spec.door_thickness, size_z=dh,
            pos_x=x, pos_y=dy, pos_z=layout.toe_kick_height + margin,
            material_role="door",
            depends_on=["left_side_panel", "right_side_panel"],
            door_hinge_side=hinge_side,
            inner_face=inner, outer_face=outer, cam_face=None,
            note=f"门板，{dw:.0f}×{dh:.0f}×{spec.door_thickness:.0f}mm",
        ))
    return panels


def _toe_kick_panels(
    spec: FurnitureSpec,
    layout: CabinetStructure,
    base_def: dict[str, Any],
    frame: CabinetFrame,
) -> list[PanelPlacement]:
    """Generate toe kick panels (front and rear kickboards + optional supports)."""
    board = spec.board_thickness
    kw = layout.internal_width
    x = layout.internal_x_start

    # Toe kick panels — outer faces outward, inner faces toward cabinet interior
    rear = PanelPlacement(
        id="toe_kick_back", name="后踢脚板", panel_type="toe_kick",
        size_x=kw, size_y=board, size_z=layout.toe_kick_height,
        pos_x=x, pos_y=layout.toe_kick_rear_y,
        material_role="carcass",
        depends_on=["left_side_panel", "right_side_panel"],
        inner_face=frame.front, outer_face=frame.back, cam_face=None,
    )
    front = PanelPlacement(
        id="toe_kick_front", name="前踢脚板", panel_type="toe_kick",
        size_x=kw, size_y=board, size_z=layout.toe_kick_height,
        pos_x=x, pos_y=layout.toe_kick_front_y - board,
        material_role="carcass",
        depends_on=["left_side_panel", "right_side_panel"],
        inner_face=frame.back, outer_face=frame.front, cam_face=None,
    )
    panels = [rear, front]

    count = resolve_toe_kick_support_count(spec.toe_kick_support_count, layout.width)
    if count == 0:
        return panels

    sy = layout.toe_kick_rear_y + board
    sd = layout.toe_kick_front_y - board - sy
    gap = toe_kick_support_clear_spacing(kw, count, board)
    for i in range(count):
        panels.append(PanelPlacement(
            id=f"toe_kick_support_{i + 1}", name=f"踢脚支撑{i + 1}",
            panel_type="toe_kick",
            size_x=board, size_y=sd, size_z=layout.toe_kick_height,
            pos_x=x + gap + i * (board + gap), pos_y=sy,
            material_role="carcass",
            depends_on=["toe_kick_back", "toe_kick_front"],
            inner_face="", outer_face="", cam_face=None,  # small support, no meaningful face
        ))
    return panels


def _shelves_from_spec(
    spec: FurnitureSpec,
    layout: CabinetStructure,
    frame: CabinetFrame,
) -> list[PanelPlacement]:
    """按 spec.shelves（从上到下）生成固定/活动层板；解析 auto 净高。"""
    gaps = resolve_shelf_gaps(spec, layout.internal_height)
    board = spec.board_thickness
    sd = layout.internal_y_end - layout.internal_y_start
    inner = frame.bottom
    outer = frame.top
    panels: list[PanelPlacement] = []
    top_z = layout.internal_z_end - spec.top_gap_mm  # 最上层板顶面
    for shelf, gap in zip(spec.shelves, gaps):
        bottom_z = top_z - board          # 这块板底面
        cz = bottom_z + board / 2         # 这块板中心
        if shelf.shelf_type == "fixed":
            panel_type = "fixed_shelf"
            cam = frame.bottom
            name = f"层板({cz:.0f}mm)"
            note = "固定层板"
            panel_id = f"shelf_z{cz:.0f}"
        else:
            panel_type = "movable_shelf"
            cam = None
            name = f"活动层板({cz:.0f}mm)"
            note = "活动层板"
            panel_id = f"movable_shelf_z{cz:.0f}"
        panels.append(PanelPlacement(
            id=panel_id, name=name, panel_type=panel_type,
            size_x=layout.internal_width, size_y=sd, size_z=board,
            pos_x=layout.internal_x_start, pos_y=layout.internal_y_start,
            pos_z=bottom_z,
            material_role="carcass",
            depends_on=["left_side_panel", "right_side_panel"],
            inner_face=inner, outer_face=outer, cam_face=cam,
            note=note,
        ))
        top_z = bottom_z - gap           # 下一层板顶面
    return panels


def _drawer_panels(
    spec: FurnitureSpec,
    layout: CabinetStructure,
    drawers_def: dict[str, Any],
    frame: CabinetFrame,
) -> list[PanelPlacement]:
    """Generate full-height drawer box panels（首版：无面板，前板即前脸）。

    尺寸链（待确认，投产前核对）：
    - 每层净高 band_h = 内部净高 ÷ drawer_count
    - 前板：高 = band_h − layer_gap；宽 = 内部宽 − 2×door_margin；厚 = 板厚
    - 盒体宽 = 内部宽 − 2×已准入的抽屉每侧净空
    - 盒体深 = 内部深 − 前板厚 − back_clearance(≥0)
    - 盒体高 = 前板高 − 2×front_overlap（底抽 18 全盖底板，顶/中 0）
    板件 label 以 z 位置后缀结尾（drawer_*_z{pos}），与 DrawerSlideConnector
    实例 key 契约一致。
    """
    count = spec.drawer_count
    if count <= 0:
        return []
    board = spec.board_thickness
    slide_gap = spec.drawer_side_clearance
    layer_gap = spec.drawer_layer_gap
    bottom_t = spec.drawer_bottom_thickness
    back_t = spec.drawer_back_thickness
    back_clear = spec.drawer_back_clearance

    iw = layout.internal_width
    internal_depth = layout.internal_y_end - layout.internal_y_start
    band_h = layout.internal_height / count
    front_h = band_h - layer_gap
    front_w = iw - 2 * spec.door_margin
    box_w = iw - 2 * slide_gap
    box_d = internal_depth - board - back_clear
    box_back_y = layout.internal_y_start + back_clear

    # 底板 x/y 端面分别顶住侧板内面/前后面（三合一连接）；底板 y 向延伸到前板
    bottom_size_y = box_d - board
    if min(front_h, front_w, box_w, box_d, bottom_size_y) <= 0:
        raise ValueError("admitted drawer parameters leave non-positive geometry")

    panels: list[PanelPlacement] = []
    for i in range(count):
        front_z = (
            layout.internal_z_start + i * band_h + (layer_gap if i > 0 else 0.0)
        )
        # 底抽前板全盖底板（overlap=板厚）；顶/中间抽屉无覆盖
        overlap = board if i == 0 else 0.0
        box_h = front_h - 2 * overlap
        box_z = front_z + overlap
        z_suffix = f"z{front_z:.0f}"

        panels.append(PanelPlacement(
            id=f"drawer_front_{z_suffix}", name=f"抽屉前板({front_z:.0f}mm)",
            panel_type="drawer_front",
            size_x=front_w, size_y=board, size_z=front_h,
            pos_x=layout.internal_x_start + spec.door_margin,
            pos_y=layout.carcass_y_end - board,
            pos_z=front_z,
            material_role="carcass",
            inner_face=frame.back, outer_face=frame.front, cam_face=None,
            note=f"抽屉前板 {front_w:.0f}×{front_h:.0f}×{board:.0f}mm",
        ))
        panels.append(PanelPlacement(
            id=f"drawer_side_L_{z_suffix}", name=f"抽屉左板({front_z:.0f}mm)",
            panel_type="drawer_side",
            size_x=board, size_y=box_d, size_z=box_h,
            pos_x=layout.internal_x_start + slide_gap,
            pos_y=box_back_y,
            pos_z=box_z,
            material_role="carcass",
            inner_face=frame.right, outer_face=frame.left,
            cam_face=frame.left,  # 偏心轮在侧板外侧面（抽屉外部操作）
            note=f"抽屉左侧板 {box_d:.0f}×{box_h:.0f}×{board:.0f}mm",
        ))
        panels.append(PanelPlacement(
            id=f"drawer_side_R_{z_suffix}", name=f"抽屉右板({front_z:.0f}mm)",
            panel_type="drawer_side",
            size_x=board, size_y=box_d, size_z=box_h,
            pos_x=layout.internal_x_end - board - slide_gap,
            pos_y=box_back_y,
            pos_z=box_z,
            material_role="carcass",
            inner_face=frame.left, outer_face=frame.right,
            cam_face=frame.right,  # 偏心轮在侧板外侧面（抽屉外部操作）
            note=f"抽屉右侧板 {box_d:.0f}×{box_h:.0f}×{board:.0f}mm",
        ))
        panels.append(PanelPlacement(
            id=f"drawer_back_{z_suffix}", name=f"抽屉后板({front_z:.0f}mm)",
            panel_type="drawer_back",
            size_x=box_w - 2 * board, size_y=back_t, size_z=box_h - 2 * board,
            pos_x=layout.internal_x_start + slide_gap + board,
            pos_y=box_back_y,
            pos_z=box_z,  # 背板底边与底板齐平：底板后端的连接杆轴线才能落在背板内
            material_role="carcass",
            inner_face=frame.front, outer_face=frame.back,
            cam_face=frame.back,  # 偏心轮在背板外侧面（抽屉外部操作）
            note=f"抽屉后板 {box_w - 2 * board:.0f}×{box_h - 2 * board:.0f}×{back_t:.0f}mm",
        ))
        panels.append(PanelPlacement(
            id=f"drawer_bottom_{z_suffix}", name=f"抽屉底板({front_z:.0f}mm)",
            panel_type="drawer_bottom",
            size_x=box_w - 2 * board, size_y=bottom_size_y, size_z=bottom_t,
            pos_x=layout.internal_x_start + slide_gap + board,
            pos_y=box_back_y + board,
            pos_z=box_z,
            material_role="carcass",
            inner_face=frame.top, outer_face=frame.bottom,
            cam_face=frame.bottom,  # 偏心轮在底板下面（抽屉外部操作）
            note=f"抽屉底板 {box_w - 2 * board:.0f}×{bottom_size_y:.0f}×{bottom_t:.0f}mm",
        ))
    return panels


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def frame_axis(signed: str) -> str:
    """Return the axis letter from a signed axis: "+x" → "x"."""
    return signed[1]


def frame_sign(signed: str) -> int:
    """Return +1 or -1 from a signed axis."""
    return 1 if signed[0] == "+" else -1


def _frame_from_spec(spec: FurnitureSpec) -> CabinetFrame:
    """Build a CabinetFrame for the spec's furniture type."""
    topology = _load_topology(spec.furniture_type)
    return CabinetFrame(**topology["frame"])
````

## File: .agents/skills/furniture-agent/agents/openai.yaml
````yaml
interface:
  display_name: "家具智能体"
  short_description: "路由六阶段家具生成与独立房间布局"
  default_prompt: "使用 $furniture-agent 每次完成一个阶段，展示 stage_outputs 后等待确认；不得跳阶段生成 CAD。"
````

## File: domain/skills/furniture-cad/references/runtime-contract.md
````markdown
# 家具运行时契约

回答“当前工作区实际执行什么？”；声称支持、规范化输入、生成或报告产物前读取。这里只定义运行时契约、命令、路径和限制。

## 当前能力

唯一应用层入口：`domain/skills/furniture-cad/scripts/furniture_workflow/workflow_orchestrator.py`。它接受只含类别与成品外包络的已确认 `DesignIntent`；`execute_spec()` 接受 CLI/API 扁平 JSON，并把其他字段路由到 `Revision.stage_inputs` 的所属阶段。字段转换、阶段实现和校验归各 Skill，Orchestrator 只管理生命周期。

- `floor_cabinet`：固定模板，含背板、踢脚板、层板、门板。
- `wall_cabinet`：固定模板，含背板、层板、门板，无踢脚板。
- 均支持有效 `groove/insert/cover`；`auto` 仅解析模式。

它们不是任意家具配置器。承诺变体前检查 `planner.py` 和模板；其他类别未实现前只做意图/建模方案。

## 六阶段状态与确认

每个 Revision 记录：

1. `design_intent`
2. `panels_planned`
3. `manufacturing_planned`
4. `feature_tree_planned`
5. `cad_generated`
6. `delivery_validated`

输出在 `revision.stage_outputs[stage.value]`，待后续处理的参数在 `revision.stage_inputs`，确认在 `approved_stages`，历史在 `workflow.history`；`JsonProjectStore` 一并持久化。

交互调用：

```python
orchestrator.confirm_stage(project)
result = orchestrator.run_next(project)
```

进入 CAD 阶段须显式给出输出：

```python
result = orchestrator.run_next(
    project,
    output_root="generated",
    generate_cad=True,
)
```

`run_next()`/默认 `run_until()` 不越过未确认检查点。Agent 返回当前输出后等待确认，不用批处理代替确认。

- 意图变化：`revise(project, new_intent)`，从 `design_intent` 开始。
- `panels_planned`、`manufacturing_planned`、`feature_tree_planned` 变化：`revise_stage_output(project, stage, edited_output)`。
- 新 Revision 仅复制修改点前的已确认输出；修改阶段和下游重做。旧产物标为 stale，不手改 STEP、GLB、BOM 或源码。

`execute_spec()` 仅供明确 CLI/API 批处理，会自动确认校验通过的中间阶段；交互 Agent 禁用。

`furniture-layout` 不在 `STAGE_SEQUENCE` 中。只有明确请求房间摆放、碰撞检查、SVG 或 Viewer 时才单独运行 `/api/plan-layout`；其结果不写入 `approved_stages`，也不是板件、CAD 或交付的前置条件。

## 可执行 JSON

单位均为毫米；支持字段：

```json
{
  "type": "floor_cabinet", "width": 800, "depth": 600, "height": 2000,
  "board_thickness": 18, "back_thickness": 9, "door_thickness": 18,
  "toe_kick_height": 50, "back_offset": 18,
  "door_margin": 1.5, "door_hinge_gap": 2,
  "groove_depth": 6, "groove_clearance": 1,
  "toe_kick_reveal_front": 1, "toe_kick_reveal_back": 30,
  "toe_kick_support_count": null, "back_mount": "auto", "back_rail_height": 70,
  "drawer_count": 0, "drawer_side_clearance": 13, "drawer_layer_gap": 1.5,
  "drawer_bottom_thickness": 18, "drawer_back_thickness": 18,
  "drawer_back_clearance": 0, "shelves": [{"shelf_type": "fixed", "gap_below_mm": 200}], "top_gap_mm": 200, "n_doors": 2, "door_hinge_side": null
}
```

`width/depth/height` 必须在意图确认前明确提供；不再用类别预设替代客户确认的外包络。板件输入必须完整提交全部规范字段；代码不按柜型静默补默认方案。完整值经确定性准入后才写入 `panels_planned.spec`。

契约为扁平 JSON。适配器只把 `type/width/depth/height` 转成 `DesignIntent`，将包括 `door_hinge_side` 在内的板件规范字段路由到板件，将制造选项/外观路由到制造；`room/placement` 只供独立房间布局 API 使用。可选 `constraints` 必须有阶段映射；未分类约束在协议路由时拒绝。

持久化兼容只发生在读取旧 Project 时：旧单门规格缺少 `door_hinge_side`，仅当其唯一门板已显式保存 `left/right` 才恢复；否则加载停止。旧标准双门规格迁移为规范 `null`，门板缺省侧按确定性左右拓扑恢复；更多门保持 `null`。该迁移不用于新 JSON/API 请求，也不根据位置或柜型猜测单门偏好。

`back_mount` 接受 `auto/groove/insert/cover`，但不进入意图或布局输出。板件阶段在背板薄于柜体板时把 `auto` 解析为 `groove`，否则为 `insert`，并输出 requested/effective；`back_rail_height/groove_depth/groove_clearance` 仅对有效 `groove` 生效，`back_rail_height=0` 关闭背拉条。

仅总体尺寸为数值且变体匹配实时模板时执行；否则停在相应规划层并说明边界。

## API 契约

`server.py` 的 `POST /api/plan-cabinet` 只适配一次性批处理并调用 `FurnitureOrchestrator.execute_spec()`：

- 生成请求含完整板件字段。Pydantic 拒绝非法模式，Orchestrator 对缺字段、结构冲突或几何组合错误返回 `422`。
- 请求可含 `constraints/constraint_mappings`；协议层按目标阶段路由，不得写入 `DesignIntent` 或静默丢弃。
- 响应 `back_mount` 为有效模式；`readiness` 返回整份制造方案的 `preliminary/accepted/factory_ready` 状态；`panels` 保留备注/封边/模式，`hardware` 保留品牌/型号/暂定说明/孔数摘要。
- `operations` 仅为入槽模式返回目标切削；`drilled_holes` 按板件返回全局/local 孔位，`hole_color_legend` 返回孔型图例。

## 生成

根目录运行：

```powershell
.\.venv\Scripts\python.exe domain\skills\furniture-cad\scripts\generate_furniture.py <spec.json> --force
```

产物名不同于规格文件名时用 `--name <artifact-name>`；仅允许字母、数字、连字符、下划线。

写入 `generated/<artifact-name>/`：

- `<artifact-name>.design-intent.json`
- `<artifact-name>.panel-plan.json`
- `<artifact-name>.manufacturing-plan.json`
- `<artifact-name>.feature-tree.json`
- `<artifact-name>.bom.md`
- `<artifact-name>.drilled-holes.json`
- `<artifact-name>.drilled-holes.glb`
- `<artifact-name>.drilled-holes.step`
- `<artifact-name>.drilled-holes.step.glb`
- `六面钻文件/<panel-label>.xml`
- `<artifact-name>.step`
- `temp/cad-source/<artifact-name>/__cadgen__/models/<artifact-name>.step.py/assembly.json`
- 同一 Viewer 组件包内由 `assembly.json` 引用的 `components/*.glb`

build123d 入口源码以 `<artifact-name>.step.py`（交互模式为 `model.step.py`）只写入 `temp/cad-source/<artifact-name>/`。CAD Bridge 调用 text-to-cad 的 `scripts/gen <source> --write <output.step> --json`，STEP 写入交付目录，Viewer 组件包按上游约定与生成器入口同目录缓存。一次性 CLI 写上方目录；交互 Project/Revision 写 `<output-root>/<project-id>/revision-<n>/`。`workflow_artifact_writer.py` 写快照，`workflow_store.py` 将 Project/Revision、`stage_outputs`、`approved_stages` 存为 `project.json`。

运行时流水线为：

`CLI / API / Agent -> FurnitureOrchestrator -> 设计意图 -> 板件 -> 制造/BOM -> 特征树 -> CAD Bridge -> STEP + Viewer 组件包 -> 交付验证`

独立房间摆放为：`明确布局请求 -> furniture-layout -> 房间坐标/碰撞检查/SVG/互动 Viewer`。

Feature Tree v2 支持板件 `box` 和定向 `cut_box`；发射器先建板、再切削、最后装配加工后的板件。

不得将家具 JSON 直发 text-to-cad、用一次性 CAD 源码绕过规划器或修改外部子模块。

## 运行时板件与 BOM 路径

- `furniture_layout/layout_pipeline.py::plan_layout_stage()`：独立计算房间定位、碰撞和预览，不进入家具生成串联流程。
- `furniture_panel_planning/panel_pipeline.py::plan_panel_stage()`：从已确认意图直接首次物化功能数量、结构规格、精确净空、背板方案，并生成实体板件角色、尺寸和位置。
- `furniture_manufacturing/manufacturing_bom.py::plan_manufacturing()`：材料、封边、五金、BOM、槽；`emit_drilled_holes()` 输出配合孔。

`cabinet_pipeline.py::plan_cabinet()` 仅是无状态兼容门面；交互流程由 Orchestrator 分阶段调用，不合并检查点。

CLI 持久化 BOM Markdown，不生成裁切清单；命令未创建时不得报告裁切清单。
````

## File: domain/skills/furniture-cad/scripts/tests/test_api_entrypoint.py
````python
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

import server
from panel_fixtures import cabinet_data


class ApiEntrypointTests(unittest.TestCase):
    def test_request_exposes_back_mount_and_toe_kick_controls(self) -> None:
        request = server.CabinetRequest(
            **cabinet_data(
                back_mount="groove",
                back_rail_height=80,
                groove_depth=8,
                groove_clearance=0.5,
                toe_kick_reveal_front=2,
                toe_kick_reveal_back=25,
                toe_kick_support_count=2,
                constraints=["背板必须入槽"],
                constraint_mappings={"背板必须入槽": "structure.back_mount"},
            ),
        )

        payload = request.model_dump(exclude_none=True)
        self.assertEqual(payload["back_mount"], "groove")
        self.assertEqual(payload["back_rail_height"], 80)
        self.assertEqual(payload["groove_depth"], 8)
        self.assertEqual(payload["groove_clearance"], 0.5)
        self.assertEqual(payload["toe_kick_support_count"], 2)
        self.assertEqual(
            payload["constraint_mappings"]["背板必须入槽"],
            "structure.back_mount",
        )

        properties = server.CabinetRequest.model_json_schema()["properties"]
        self.assertIn("back_mount", properties)
        self.assertIn("back_rail_height", properties)
        self.assertIn("constraint_mappings", properties)
        openapi_schemas = server.app.openapi()["components"]["schemas"]
        self.assertIn(
            "back_mount",
            openapi_schemas["CabinetRequest"]["properties"],
        )
        for response_field in (
            "readiness",
            "back_mount",
            "hardware",
            "operations",
            "hole_color_legend",
            "drilled_holes",
        ):
            self.assertIn(
                response_field,
                openapi_schemas["BOMResponse"]["properties"],
            )

        with self.assertRaises(ValueError):
            server.CabinetRequest(
                type="floor_cabinet",
                width=800,
                depth=600,
                height=1000,
                back_mount="unsupported",
            )

    def test_plan_endpoint_runs_through_the_application_workflow(self) -> None:
        response = asyncio.run(
            server.plan_cabinet(
                server.CabinetRequest(
                    **cabinet_data("wall_cabinet"),
                )
            )
        )

        self.assertEqual(response.furniture_name, "吊柜")
        self.assertEqual(response.readiness, "preliminary")
        self.assertEqual(response.back_mount, "groove")
        self.assertGreater(response.panel_count, 0)

        auto_insert = asyncio.run(
            server.plan_cabinet(
                server.CabinetRequest(
                    **cabinet_data("wall_cabinet", back_thickness=18),
                )
            )
        )
        self.assertEqual(auto_insert.back_mount, "insert")

    def test_layout_endpoint_returns_room_position_and_svg_preview(self) -> None:
        request = server.CabinetRequest(
            type="floor_cabinet",
            width=1800,
            depth=600,
            height=2400,
            room=server.RoomRequest(
                id="bedroom",
                name="卧室",
                width_mm=4200,
                depth_mm=3600,
                height_mm=2800,
            ),
            placement=server.FurniturePlacementRequest(
                mode="wall",
                host_wall="west",
                offset_mm=300,
            ),
        )

        response = asyncio.run(server.plan_layout(request))

        self.assertEqual(response.room_placement["room"]["name"], "卧室")
        self.assertEqual(
            response.room_placement["placement"]["rotation_z_deg"],
            270,
        )
        self.assertEqual(response.preview["media_type"], "image/svg+xml")
        self.assertEqual(
            response.preview["view_kind"],
            "perspective_envelope",
        )
        self.assertIn("<svg", response.preview["svg"])
        self.assertEqual(response.viewer["media_type"], "text/html")
        self.assertEqual(
            response.viewer["view_kind"],
            "interactive_orbit_envelope",
        )

        svg_response = asyncio.run(server.plan_layout_preview(request))
        self.assertEqual(svg_response.media_type, "image/svg+xml")
        self.assertIn(b"<svg", svg_response.body)

        viewer_response = asyncio.run(server.plan_layout_viewer(request))
        self.assertEqual(viewer_response.media_type, "text/html")
        self.assertIn(b'<canvas id="scene"', viewer_response.body)
        self.assertIn(b'data-view="top"', viewer_response.body)

    def test_layout_endpoint_uses_default_bedroom_without_room_input(self) -> None:
        request = server.CabinetRequest(
            type="floor_cabinet",
            width=1600,
            depth=600,
            height=2400,
        )

        response = asyncio.run(server.plan_layout(request))

        self.assertEqual(
            response.layout_context,
            {
                "room_source": "default_bedroom",
                "placement_source": "default_north_wall_centered",
            },
        )
        self.assertEqual(
            response.room_placement["room"]["name"],
            "默认卧室（系统假设）",
        )
        self.assertEqual(
            response.room_placement["placement"]["origin_x_mm"],
            1300,
        )
        self.assertIn("<svg", response.preview["svg"])
        self.assertIn("pointermove", response.viewer["html"])

    def test_plan_endpoint_returns_each_back_mount_manufacturing_contract(
        self,
    ) -> None:
        # cover/groove 的螺钉为组装现场工艺：无螺钉五金、无螺钉孔
        contracts = {
            "groove": (9, None, set(), 4),
            "insert": (
                18,
                "三合一连接件（内嵌背板）",
                {
                    "back_insert_cam",
                    "back_insert_rod",
                    "back_insert_nut",
                },
                0,
            ),
            "cover": (9, None, set(), 0),
        }
        screw_names = {"沉头木螺钉（外盖背板）", "沉头木螺钉（背拉条）"}
        screw_hole_types = {
            "cover_back_clearance",
            "cover_back_pilot",
            "back_rail_side_clearance",
            "back_rail_pilot",
        }

        for back_mount, (
            back_thickness,
            hardware_name,
            required_holes,
            expected_operation_count,
        ) in contracts.items():
            with self.subTest(back_mount=back_mount):
                response = asyncio.run(
                    server.plan_cabinet(
                        server.CabinetRequest(
                            **cabinet_data(
                                back_mount=back_mount,
                                back_thickness=back_thickness,
                                back_rail_height=80,
                                shelf_count=1,
                                n_doors=2,
                            ),
                        )
                    )
                )

                self.assertEqual(response.back_mount, back_mount)
                self.assertEqual(
                    {panel.back_mount for panel in response.panels},
                    {back_mount},
                )
                back = next(
                    panel
                    for panel in response.panels
                    if panel.panel_type == "back"
                )
                self.assertEqual(
                    back.edge_banding,
                    {}
                    if back_mount == "groove"
                    else {"四边": "ABS 1.0mm同色"},
                )

                if hardware_name is None:
                    self.assertFalse(
                        any(
                            item.name in screw_names
                            for item in response.hardware
                        )
                    )
                else:
                    hardware = next(
                        item
                        for item in response.hardware
                        if item.name == hardware_name
                    )
                    self.assertGreater(hardware.quantity, 0)
                    self.assertIn("投产前确认", hardware.note)
                    self.assertTrue(hardware.drilling)

                hole_types = {
                    hole.hole_type
                    for panel in response.drilled_holes
                    for hole in panel.holes
                }
                self.assertTrue(required_holes.issubset(hole_types))
                self.assertFalse(screw_hole_types & hole_types)
                self.assertEqual(
                    len(response.operations),
                    expected_operation_count,
                )
                if back_mount == "groove":
                    rails = [
                        panel
                        for panel in response.panels
                        if panel.panel_type == "back_rail"
                    ]
                    self.assertTrue(rails)
                    self.assertTrue(
                        all(panel.size_z == 80 for panel in rails)
                    )


if __name__ == "__main__":
    unittest.main()
````

## File: domain/skills/furniture-cad/scripts/tests/test_recent_manufacturing_patches.py
````python
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree as ET


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_panel_planning.panel_spec import FurnitureSpec
from panel_fixtures import furniture_spec
from furniture_layout.layout_pipeline import plan_layout
from furniture_manufacturing.connectors.drawer_slide import DrawerSlideConnector
from furniture_manufacturing.connectors.hinge import HingeConnector
from furniture_manufacturing.connectors.trinity import TrinityConnector
from furniture_manufacturing.drilled_holes_glb import _build_grouped_geometry
from furniture_manufacturing.export_six_side_drill import (
    drill_json_to_xml_files,
)
from furniture_manufacturing.manufacturing_bom import (
    emit_drilled_holes,
    plan_manufacturing,
)
from furniture_manufacturing.manufacturing_models import PanelRecord
from furniture_manufacturing.validation import validate_manufacturing
from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.structure_planning import CabinetStructure
from furniture_panel_planning.validation import validate_panels


def panel_record(
    *,
    label: str,
    name: str,
    panel_type: str,
    size_x: float,
    size_y: float,
    size_z: float,
    pos_x: float = 0,
    pos_y: float = 0,
    pos_z: float = 0,
    inner_face: str = "",
    cam_face: str | None = None,
    door_hinge_side: str | None = None,
) -> PanelRecord:
    return PanelRecord(
        label=label,
        name=name,
        panel_type=panel_type,
        material="测试板",
        thickness=min(size_x, size_y, size_z),
        length_mm=max(size_x, size_y, size_z),
        width_mm=sorted((size_x, size_y, size_z))[-2],
        size_x=size_x,
        size_y=size_y,
        size_z=size_z,
        pos_x=pos_x,
        pos_y=pos_y,
        pos_z=pos_z,
        inner_face=inner_face,
        cam_face=cam_face,
        door_hinge_side=door_hinge_side,
    )


class PanelAndConnectorPatchTests(unittest.TestCase):
    def test_standard_doors_have_explicit_hinge_sides(self) -> None:
        spec = furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            n_doors=2,
        )
        placements = plan_panels(spec, plan_layout(spec))
        doors = {
            panel.id: panel
            for panel in placements
            if panel.panel_type == "door"
        }

        self.assertEqual(doors["left_door"].door_hinge_side, "left")
        self.assertEqual(doors["right_door"].door_hinge_side, "right")

    def test_single_door_requires_explicit_hinge_side(self) -> None:
        # 单门铰链侧是开放偏好，必须由提案显式提交，缺省不得由代码补默认值
        with self.assertRaises(ValueError):
            furniture_spec(n_doors=1)

        right_spec = furniture_spec(n_doors=1, door_hinge_side="right")
        placements = plan_panels(right_spec, plan_layout(right_spec))
        door = next(p for p in placements if p.panel_type == "door")
        self.assertEqual(door.door_hinge_side, "right")

        # 双门铰链侧由代码确定性推导，不接受显式标量覆盖
        with self.assertRaises(ValueError):
            furniture_spec(n_doors=2, door_hinge_side="left")

    def test_trinity_uses_two_depth_rows_and_explicit_hole_faces(self) -> None:
        connector = TrinityConnector()
        side = panel_record(
            label="left_side_panel",
            name="左侧板",
            panel_type="side",
            size_x=18,
            size_y=600,
            size_z=1000,
            inner_face="+x",
        )
        top = panel_record(
            label="top_panel",
            name="顶板",
            panel_type="top",
            size_x=764,
            size_y=600,
            size_z=18,
            pos_x=18,
            pos_z=982,
            cam_face="-z",
        )

        side_holes = connector.generate_holes(side)
        self.assertEqual({hole.y_local for hole in side_holes}, {64.0, 536.0})
        self.assertTrue(all(hole.is_face_hole for hole in side_holes))
        self.assertTrue(all(hole.direction == "-x" for hole in side_holes))

        top_holes = connector.generate_holes(top)
        rod_holes = [
            hole for hole in top_holes if hole.hole_type == "three_in_one_rod"
        ]
        cam_holes = [
            hole for hole in top_holes if hole.hole_type == "three_in_one_cam"
        ]
        self.assertEqual({hole.y_local for hole in rod_holes}, {64.0, 536.0})
        # 偏心轮 y 与连接杆同排；x 为端面 + cam_offset（= 插入深度 + 圆心到杆头端距离 = 33.5）
        self.assertEqual({hole.y_local for hole in cam_holes}, {64.0, 536.0})
        self.assertEqual({hole.x_local for hole in cam_holes}, {33.5, 764 - 33.5})
        self.assertTrue(all(not hole.is_face_hole for hole in rod_holes))
        self.assertTrue(all(hole.is_face_hole for hole in cam_holes))

    def test_trinity_machining_operation_ids_are_unique_per_end(self) -> None:
        """两端连接的三合一板，加工指令 id 必须含 x_local 以区分左右端。"""
        connector = TrinityConnector()
        top = panel_record(
            label="top_panel",
            name="顶板",
            panel_type="top",
            size_x=764,
            size_y=600,
            size_z=18,
            pos_x=18,
            pos_z=982,
            cam_face="-z",
        )
        ops = connector.machining_operations(top)
        ids = [op.id for op in ops]
        # 唯一性：旧实现 id 无 x_local 时，左右两端同 (z,y) 的孔 id 重复
        self.assertEqual(len(ids), len(set(ids)))
        # 同一深度排(y=64)的两个连接杆孔（左端 x=0 / 右端 x=764）id 必须不同
        male_front = [
            op for op in ops
            if "three_in_one_rod" in op.id and "_64_" in op.id
        ]
        self.assertEqual(len(male_front), 2)
        self.assertNotEqual(male_front[0].id, male_front[1].id)

    def test_trinity_rod_cam_count_mismatch_is_rejected(self) -> None:
        """删掉一个连接杆孔后，校验必须报 TRINITY_ROD_CAM_COUNT_MISMATCH。"""
        spec = furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            n_doors=2,
        )
        placements = plan_panels(spec, plan_layout(spec))
        manufacturing = plan_manufacturing(spec, placements)
        orig = TrinityConnector.generate_holes_for_panels

        def drop_one_male(self, panels):
            holes = orig(self, panels)
            dropped = False
            kept = []
            for hole in holes:
                if not dropped and hole.hole_type == "three_in_one_rod":
                    dropped = True
                    continue
                kept.append(hole)
            return kept

        with mock.patch.object(
            TrinityConnector, "generate_holes_for_panels", drop_one_male
        ):
            report = validate_manufacturing(spec, manufacturing, placements)

        self.assertFalse(report.passed)
        self.assertIn(
            "TRINITY_ROD_CAM_COUNT_MISMATCH",
            {issue.code for issue in report.issues},
        )

    def test_drawer_slide_connector_emits_per_drawer_bom(self) -> None:
        """每个抽屉实例一副滑轨（左右各 1）；不同深度各配各的长度。"""
        drawer_1 = [
            panel_record(
                label="drawer_side_L_z300", name="抽屉左板",
                panel_type="drawer_side", size_x=18, size_y=500, size_z=150,
                pos_x=0, pos_y=0, pos_z=300,
            ),
            panel_record(
                label="drawer_side_R_z300", name="抽屉右板",
                panel_type="drawer_side", size_x=18, size_y=500, size_z=150,
                pos_x=350, pos_y=0, pos_z=300,
            ),
            panel_record(
                label="drawer_front_z300", name="抽屉前板",
                panel_type="drawer_front", size_x=380, size_y=18, size_z=150,
                pos_x=0, pos_y=0, pos_z=300,
            ),
            panel_record(
                label="drawer_bottom_z300", name="抽屉底板",
                panel_type="drawer_bottom", size_x=380, size_y=500, size_z=12,
                pos_x=0, pos_y=0, pos_z=300,
            ),
        ]
        drawer_2 = [
            panel_record(
                label="drawer_side_L_z600", name="抽屉左板",
                panel_type="drawer_side", size_x=18, size_y=550, size_z=150,
                pos_x=0, pos_y=0, pos_z=600,
            ),
            panel_record(
                label="drawer_side_R_z600", name="抽屉右板",
                panel_type="drawer_side", size_x=18, size_y=550, size_z=150,
                pos_x=350, pos_y=0, pos_z=600,
            ),
            panel_record(
                label="drawer_front_z600", name="抽屉前板",
                panel_type="drawer_front", size_x=400, size_y=18, size_z=150,
                pos_x=0, pos_y=0, pos_z=600,
            ),
            panel_record(
                label="drawer_bottom_z600", name="抽屉底板",
                panel_type="drawer_bottom", size_x=400, size_y=550, size_z=12,
                pos_x=0, pos_y=0, pos_z=600,
            ),
        ]

        records = DrawerSlideConnector().boms(drawer_1 + drawer_2)

        self.assertEqual(len(records), 2)
        self.assertTrue(all(r.name == "抽屉滑轨" for r in records))
        self.assertTrue(all(r.unit == "副" for r in records))
        # 每抽一副（左右各 1）；深度 500→450mm、550→500mm
        self.assertEqual({r.quantity for r in records}, {2})
        self.assertEqual({r.model for r in records}, {"SJG-01"})
        self.assertEqual(
            {r.spec for r in records},
            {"默认 SJG-01 450mm 30kg", "默认 SJG-01 500mm 30kg"},
        )

    def test_drawer_slide_connector_absent_without_drawer_panels(self) -> None:
        """无抽屉板件时不产出滑轨 BOM（且全流水线 BOM 无滑轨行）。"""
        self.assertEqual(DrawerSlideConnector().boms([panel_record(
            label="left_side_panel", name="左侧板", panel_type="side",
            size_x=18, size_y=600, size_z=1000,
        )]), [])
        spec = furniture_spec(
            furniture_type="floor_cabinet",
            width=800, depth=600, height=1000, n_doors=2,
        )
        placements = plan_panels(spec, plan_layout(spec))
        bom = plan_manufacturing(spec, placements)
        self.assertNotIn("抽屉滑轨", [item.name for item in bom.hardware])

    def test_hinge_cup_uses_center_distance_and_inner_face(self) -> None:
        door = panel_record(
            label="left_door",
            name="左门板",
            panel_type="door",
            size_x=397,
            size_y=18,
            size_z=948,
            inner_face="-y",
            door_hinge_side="left",
        )

        holes = HingeConnector().generate_holes(door)

        self.assertTrue(holes)
        self.assertEqual({hole.x_local for hole in holes}, {22.5})
        # direction 统一为钻入方向：内侧面 "-y" → 往板内钻 "+y"
        self.assertTrue(all(hole.direction == "+y" for hole in holes))
        self.assertTrue(all(hole.is_face_hole for hole in holes))

    def test_manufacturing_validation_rejects_hinge_outside_door(self) -> None:
        spec = furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            n_doors=2,
        )
        placements = plan_panels(spec, plan_layout(spec))
        manufacturing = plan_manufacturing(spec, placements)
        left_door = next(
            panel
            for panel in manufacturing.panels
            if panel.label == "left_door"
        )
        left_door.size_x = 30

        report = validate_manufacturing(
            spec,
            manufacturing,
            placements,
        )

        self.assertFalse(report.passed)
        self.assertIn(
            "HINGE_HOLE_OUTSIDE_DOOR",
            {issue.code for issue in report.issues},
        )

    def test_emitted_panels_include_type_and_no_screw_holes(self) -> None:
        spec = furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            back_mount="cover",
            back_thickness=9,
            n_doors=2,
        )
        placements = plan_panels(spec, plan_layout(spec))
        drilled = emit_drilled_holes(plan_manufacturing(spec, placements))

        self.assertTrue(
            all(panel.get("panel_type") for panel in drilled["panels"])
        )
        # 螺钉孔为组装现场工艺，不应出现在柜体加工孔位中
        screw_holes = [
            hole
            for panel in drilled["panels"]
            for hole in panel["holes"]
            if hole["hole_type"] in {
                "cover_back_clearance",
                "cover_back_pilot",
                "back_rail_side_clearance",
                "back_rail_pilot",
            }
        ]
        self.assertEqual(screw_holes, [])

    def test_dynamic_panel_labels_stay_in_panel_step_group(self) -> None:
        groups = _build_grouped_geometry(
            {
                "panels": [
                    {
                        "label": "shelf_z999",
                        "panel_type": "fixed_shelf",
                        "box": {
                            "x": 600,
                            "y": 500,
                            "z": 18,
                            "pos_x": 0,
                            "pos_y": 0,
                            "pos_z": 999,
                        },
                        "holes": [],
                    }
                ]
            },
            marker_thickness=2,
        )

        self.assertEqual([solid.label for solid in groups["板件"]], ["shelf_z999"])
        self.assertNotIn("其他孔位", groups)


class DrawerZoneTests(unittest.TestCase):
    """整高抽屉区（档 B 首版）：drawer_count>0 → 抽屉板件，无门无层板。"""

    def _drawer_cabinet(
        self,
        drawer_count: int,
        n_doors: int = 0,
        shelf_count: int = 0,
    ):
        spec = furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            n_doors=n_doors,
            shelf_count=shelf_count,
            drawer_count=drawer_count,
        )
        placements = plan_panels(spec, plan_layout(spec))
        return spec, placements

    def test_full_height_drawer_zone_generates_five_panels_per_drawer(self) -> None:
        spec, placements = self._drawer_cabinet(3)
        types = {p.panel_type for p in placements}
        self.assertTrue(
            {"drawer_front", "drawer_side", "drawer_back", "drawer_bottom"}
            <= types
        )
        self.assertNotIn("door", types)
        self.assertNotIn("fixed_shelf", types)

        drawer_panels = [p for p in placements if "drawer" in p.panel_type]
        self.assertEqual(len(drawer_panels), 15)  # 3 抽屉 × 5 板
        # label 契约：drawer_<角色>_z{位置}（实例 key = z 后缀）
        for panel in drawer_panels:
            self.assertRegex(
                panel.id,
                r"^drawer_(front|side_L|side_R|back|bottom)_z\d+$",
            )
        # 3 个抽屉实例，每个 5 块板共享 z 后缀
        from collections import Counter

        instance_keys = Counter(
            panel.id.rsplit("_", 1)[1] for panel in drawer_panels
        )
        self.assertEqual(len(instance_keys), 3)
        self.assertTrue(all(count == 5 for count in instance_keys.values()))

    def test_bottom_drawer_front_covers_bottom_panel(self) -> None:
        """底抽前板全盖底板（front_overlap=18）：侧板高 = 前板高 − 36。"""
        _, placements = self._drawer_cabinet(3)
        drawer_panels = [p for p in placements if "drawer" in p.panel_type]
        fronts = sorted(
            (p for p in drawer_panels if p.panel_type == "drawer_front"),
            key=lambda p: p.pos_z,
        )
        sides = [
            p for p in drawer_panels if p.panel_type == "drawer_side"
        ]
        # 三个抽屉的前板高度相同（均分净高 − 层缝）
        front_h = fronts[0].size_z  # 未取整的实际前板高
        self.assertTrue(
            all(abs(p.size_z - front_h) < 1e-6 for p in fronts)
        )
        # 底抽（最小 front_z）：前板向下覆盖 18 → 侧板 pos_z = front_z + 18，高 = front_h − 36
        bottom_front_z = fronts[0].pos_z
        bottom_sides = [p for p in sides if p.pos_z == bottom_front_z + 18]
        self.assertEqual(len(bottom_sides), 2)
        self.assertTrue(all(abs(p.size_z - (front_h - 36)) < 1e-6 for p in bottom_sides))
        # 上两层抽屉：侧板 pos_z = 各自 front_z（无覆盖），高 = front_h
        for front in fronts[1:]:
            band_sides = [p for p in sides if p.pos_z == front.pos_z]
            self.assertEqual(len(band_sides), 2)
            self.assertTrue(all(abs(p.size_z - front_h) < 1e-6 for p in band_sides))

    def test_drawer_zone_bom_emits_slides_per_drawer(self) -> None:
        spec, placements = self._drawer_cabinet(3)
        manufacturing = plan_manufacturing(spec, placements)
        slides = [h for h in manufacturing.hardware if h.name == "抽屉滑轨"]
        self.assertEqual(len(slides), 1)  # 同深度 → 单条记录
        self.assertEqual(slides[0].quantity, 6)  # 3 抽屉 × 每抽 2
        # 抽屉深 = 内部深(553) − 前板厚(18) → 535 → 匹配 450mm 三节轨
        self.assertIn("450mm", slides[0].spec)

        report = validate_manufacturing(spec, manufacturing, placements)
        self.assertTrue(report.passed)

    def test_drawer_zone_rejects_conflicting_doors_or_shelves(self) -> None:
        with self.assertRaisesRegex(ValueError, "full-height drawers require"):
            self._drawer_cabinet(3, n_doors=2, shelf_count=4)

    def test_drawer_box_uses_trinity_by_default(self) -> None:
        """抽屉盒默认三合一（全屋定制主流）：杆/轮/螺母 1:1:1，底板 cam 在底面。"""
        spec, placements = self._drawer_cabinet(1)
        manufacturing = plan_manufacturing(spec, placements)
        holes = TrinityConnector().generate_holes_for_panels(manufacturing.panels)
        drawer_labels = {
            p.label for p in manufacturing.panels if "drawer" in p.panel_type
        }
        drawer_holes = [h for h in holes if h.panel_label in drawer_labels]
        types = [h.hole_type for h in drawer_holes]
        # 1:1:1 配对（每连接：1 杆 + 1 轮 + 1 螺母）
        self.assertGreater(types.count("three_in_one_rod"), 0)
        self.assertEqual(
            types.count("three_in_one_rod"),
            types.count("three_in_one_cam"),
        )
        self.assertEqual(
            types.count("three_in_one_cam"),
            types.count("three_in_one_nut"),
        )
        # 底板轮孔在底面（cam_face=-z → z_local=0，钻入方向 +z）
        bottom_cams = [
            h for h in holes
            if h.panel_label == "drawer_bottom_z68"
            and h.hole_type == "three_in_one_cam"
        ]
        self.assertEqual(len(bottom_cams), 8)  # 4 连接 × 2 排
        self.assertTrue(all(abs(h.z_local) < 1e-6 for h in bottom_cams))
        self.assertTrue(all(h.direction == "+z" for h in bottom_cams))
        # BOM 三合一数量 = 全部偏心轮孔数（柜体 + 抽屉，孔即真源）
        trinity = [h for h in manufacturing.hardware if h.name == "三合一连接件"]
        self.assertEqual(
            trinity[0].quantity,
            sum(1 for h in holes if h.hole_type == "three_in_one_cam"),
        )

    def test_no_drawer_keeps_doors_and_shelves(self) -> None:
        spec, placements = self._drawer_cabinet(0, n_doors=2, shelf_count=4)
        types = {p.panel_type for p in placements}
        self.assertIn("door", types)
        self.assertIn("fixed_shelf", types)
        self.assertTrue(all("drawer" not in p.panel_type for p in placements))


class SixSideDrillPatchTests(unittest.TestCase):
    def _sample_data(self, *, slots: list[dict] | None = None) -> dict:
        return {
            "panels": [
                {
                    "label": "top_panel",
                    "name": "顶板",
                    "panel_type": "top",
                    "box": {
                        "x": 764,
                        "y": 580,
                        "z": 18,
                        "pos_x": 10,
                        "pos_y": 20,
                        "pos_z": 30,
                    },
                    "holes": [
                        {
                            "hole_type": "three_in_one_cam",
                            "local_x": 100,
                            "local_y": 64,
                            "local_z": 18,
                            "diameter": 12,
                            "depth": 13.5,
                            "direction": "-z",
                            "is_face_hole": True,
                        },
                        {
                            "hole_type": "three_in_one_rod",
                            "x": 98,
                            "y": 97,
                            "z": 39,
                            "diameter": 8,
                            "depth": 33,
                            "direction": "+x",
                            "is_face_hole": False,
                        },
                    ],
                    "slots": slots or [],
                }
            ]
        }

    def test_xml_uses_machine_axes_localizes_legacy_holes_and_closes_once(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "drilled.json"
            source.write_text(
                json.dumps(self._sample_data(), ensure_ascii=False),
                encoding="utf-8",
            )

            [xml_path] = drill_json_to_xml_files(source, root / "xml")
            document = ET.fromstring(xml_path.read_text(encoding="utf-8"))

        self.assertEqual(document.findtext("./PANEL/PanelLength"), "580.0")
        self.assertEqual(document.findtext("./PANEL/PanelWidth"), "764.0")
        self.assertEqual(document.findtext("./PANEL/PanelThickness"), "18.0")

        vertices = [
            (
                float(vertex.findtext("X1", "0")),
                float(vertex.findtext("Y1", "0")),
            )
            for vertex in document.findall("./PANEL/PanelOutline/Vertex")
        ]
        self.assertEqual(
            vertices,
            [
                (0.0, 764.0),
                (0.0, 0.0),
                (580.0, 0.0),
                (580.0, 764.0),
                (0.0, 764.0),
            ],
        )

        face_hole, edge_hole = document.findall("./CAD")
        self.assertEqual(face_hole.findtext("TypeNo"), "1")
        self.assertEqual(face_hole.findtext("X1"), "64.0")
        self.assertEqual(face_hole.findtext("Y1"), "100.0")

        self.assertEqual(edge_hole.findtext("TypeNo"), "2")
        self.assertEqual(edge_hole.findtext("X1"), "77.0")
        self.assertEqual(edge_hole.findtext("Y1"), "88.0")
        self.assertEqual(edge_hole.findtext("Z1"), "9.00")
        self.assertEqual(edge_hole.findtext("Quadrant"), "3")

    def test_slot_input_is_rejected_instead_of_silently_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "drilled.json"
            source.write_text(
                json.dumps(
                    self._sample_data(slots=[{"type": "groove"}]),
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError,
                "slot export is not implemented",
            ):
                drill_json_to_xml_files(source, root / "xml")


if __name__ == "__main__":
    unittest.main()
````

## File: domain/skills/furniture-design-intent/references/intake/catalog.yaml
````yaml
# 分类轴 = 柜类家具的落位/安装方式：落地 → floor_cabinet，上墙 → wall_cabinet。
# 与功能、外观、所在房间无关；桌、椅、床等非柜类家具无法归类时产出 fallback 草稿
# （见 SKILL.md / references/intent-capture-rules.md）。
#
# `executable: true` 是代码准入契约：必须与
# furniture_design_intent.design_intent.SUPPORTED_TYPES 一致，
# 由 furniture-cad/scripts/tests/test_skill_architecture.py 断言。

families:
  floor_cabinet:
    executable: true

  wall_cabinet:
    executable: true
````

## File: domain/skills/furniture-design-intent/scripts/furniture_design_intent/design_intent.py
````python
"""Furniture category and finished-envelope intent.

DesignIntent is deliberately small: it records only the cabinet family and
the customer-confirmed finished envelope.  Functional layout, construction,
manufacturing, CAD, and artifact choices belong to later stage contracts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any


SUPPORTED_TYPES = frozenset({"floor_cabinet", "wall_cabinet"})
MOUNT_MODES = frozenset({"free_height", "flush_ceiling"})


@dataclass(frozen=True)
class OverallSize:
    """整体尺寸（草稿可空）。"""
    width_mm: float | None
    depth_mm: float | None
    height_mm: float | None

    def validate(self) -> list[str]:
        errors: list[str] = []
        for name, value in asdict(self).items():
            if value is None:
                errors.append(
                    f"overall_size.{name} must be provided before confirmation"
                )
            elif isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"overall_size.{name} must be numeric")
            elif value <= 0:
                errors.append(f"overall_size.{name} must be greater than zero")
        return errors


@dataclass(frozen=True)
class DesignIntent:
    """One revision's customer-confirmed finished-envelope source of truth."""

    furniture_type: str
    overall_size: OverallSize
    # 挂装方式：free_height（自由挂高，需 mounting_height_mm）/
    # flush_ceiling（贴顶到顶，无需数字）。仅吊柜有意义，地柜为 None。
    mount_mode: str | None = None
    # 自由挂高时吊柜底边离地高度；贴顶或地柜无此义，默认 None。
    mounting_height_mm: float | None = None
    confirmed: bool = False
    schema_version: int = 2

    def validate(self) -> list[str]:
        errors = self.overall_size.validate()
        errors.extend(
            _mounting_errors(
                self.furniture_type, self.mount_mode, self.mounting_height_mm
            )
        )
        if not self.furniture_type.strip():
            errors.append("furniture_type is required")
        if self.schema_version != 2:
            errors.append(f"unsupported DesignIntent schema_version: {self.schema_version}")
        return errors

    def confirm(self) -> "DesignIntent":
        errors = self.validate()
        if self.furniture_type not in SUPPORTED_TYPES:
            errors.append(
                "furniture_type must be an executable canonical type: "
                + ", ".join(sorted(SUPPORTED_TYPES))
            )
        if errors:
            raise ValueError("; ".join(errors))
        return replace(self, confirmed=True)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["overall_size"] = {
            "width_mm": _optional_float_value(self.overall_size.width_mm),
            "depth_mm": _optional_float_value(self.overall_size.depth_mm),
            "height_mm": _optional_float_value(self.overall_size.height_mm),
        }
        data["mounting_height_mm"] = _optional_float_value(self.mounting_height_mm)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DesignIntent":
        source_schema_version = int(data.get("schema_version", 2))
        legacy_schema = source_schema_version == 1
        downstream_fields = {
            "purpose",
            "layout",
            "appearance",
            "structure",
            "constraints",
            "constraint_mappings",
            "assumptions",
            "unresolved",
        }
        populated_downstream = sorted(
            key for key in downstream_fields if data.get(key)
        )
        if populated_downstream and not legacy_schema:
            raise ValueError(
                "DesignIntent only accepts furniture_type, overall_size, "
                "mount_mode, and mounting_height_mm; route later decisions "
                "through stage_inputs: "
                + ", ".join(populated_downstream)
            )
        size = data.get("overall_size", {})
        return cls(
            furniture_type=str(data.get("furniture_type", data.get("type", ""))).strip().lower(),
            overall_size=OverallSize(
                width_mm=_parse_optional_float(
                    size.get("width_mm", data.get("width")),
                    "overall_size.width_mm",
                ),
                depth_mm=_parse_optional_float(
                    size.get("depth_mm", data.get("depth")),
                    "overall_size.depth_mm",
                ),
                height_mm=_parse_optional_float(
                    size.get("height_mm", data.get("height")),
                    "overall_size.height_mm",
                ),
            ),
            mount_mode=data.get("mount_mode"),
            mounting_height_mm=_parse_optional_float(
                data.get("mounting_height_mm"),
                "mounting_height_mm",
            ),
            confirmed=bool(data.get("confirmed", False)),
            # Schema v1 carried downstream layout and construction fields.
            # Reading it into the current model intentionally drops those
            # fields; workflow project loading migrates them to stage_inputs.
            schema_version=(2 if legacy_schema else source_schema_version),
        )


def _mounting_errors(
    furniture_type: str,
    mount_mode: str | None,
    mounting_height_mm: float | None,
) -> list[str]:
    """Confirmation-time rules for a wall cabinet's mounting intent."""
    if furniture_type != "wall_cabinet":
        return []
    if mount_mode not in MOUNT_MODES:
        return [
            "mount_mode must be 'free_height' or 'flush_ceiling' "
            "for a wall cabinet"
        ]
    if mount_mode == "flush_ceiling":
        return []
    # free_height：必须给正数底边离地高度。
    if mounting_height_mm is None:
        return [
            "mounting_height_mm must be provided before confirmation "
            "for a free-height wall cabinet"
        ]
    if isinstance(mounting_height_mm, bool) or not isinstance(
        mounting_height_mm, (int, float)
    ):
        return ["mounting_height_mm must be numeric or null"]
    if mounting_height_mm <= 0:
        return [
            "mounting_height_mm must be greater than zero "
            "for a free-height wall cabinet"
        ]
    return []


def _optional_float_value(value: float | None) -> float | None:
    return None if value is None else float(value)


def _parse_optional_float(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric or null")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric or null") from exc
````

## File: domain/skills/furniture-manufacturing/references/connection-point-design.md
````markdown
# 连接点级实体需求（记录）

状态：**需求记录**（未立项、未实施）。来源于 2026-08 局部坐标化重构讨论。

## 背景

三合一（及背板 insert）的杆孔 / 轮孔配对目前是**几何隐式约定**，不是结构引用：

- 一个连接点 = 1 杆孔（端面）+ 1 轮孔（cam 面）+ 配合板 1 预埋螺母孔；
- 配对靠"同 y（深度排）、同 z（高度）、轮孔 x = 端面 ± `cam.hole.edge_offset_mm`"在几何上对齐；
- `HoleSpec` 之间没有 `connection_id` 之类的引用，孔位列表里没有"连接点"实体；
- 孔位永远是**整体重生成**（`generate_holes()` / `generate_holes_for_panels()` 从板件+连接拓扑从零计算），不存在"删单个孔"的增量编辑入口。

## 现状行为（回答"删一个孔，配对孔会怎样"）

| 操作 | 配对孔是否跟着删 | 校验是否拦截 |
|------|----------------|--------------|
| 删主柜体轮孔 | ❌ 不删，杆孔成孤儿 | 拦截：`TRINITY_HARDWARE_COUNT_MISMATCH`（偏心轮孔数 ≠ BOM 数） |
| 删主柜体杆孔 | ❌ 不删，轮孔成孤儿 | **不拦截**（无"杆孔数 == 轮孔数"检查，静默） |
| 删背板 insert 任一类孔 | ❌ 不删 | 拦截：`BACK_MOUNT_HOLE_COUNT_MISMATCH`（cam/rod/nut 三类数量必须相等） |

依据：`validation.py` L332-340（主柜体只校验轮孔数）、L354-388（背板 1:1:1 数量约束）；
BOM 数量只认轮孔（`TrinityConnector.boms()` quantity = `three_in_one_cam` 计数，孔即真源）。

## 需求

1. **连接点作为整体增删**：删除一个三合一连接点 → 它的杆孔 + 轮孔 + 配合板螺母孔一起消失；增加同理。背板连接点（cam + rod + nut）同样按连接点整体增删。
2. **校验按连接点对齐**：主柜体也校验 `杆孔数 == 轮孔数 == 连接点数`（或更强：按连接点标识逐点核对配对几何），消除"删杆孔静默孤儿"。
3. **配对显式化**：`HoleSpec` 增加连接点标识（如 `connection_id` / group 字段），或引入连接点级实体；连接拓扑（`PanelJoint` 的 male/female 配对）可作来源。
4. **顺带修正**：`machining_operations` 的 id 为 `{hole_type}_{panel}_{z:.0f}_{y:.0f}`，不含端面区分，横板左右两端同 (z,y) 的杆孔 id 重复——按连接点索引时该 id 方案必须含端面/方向区分。

## 实施建议（暂定，实施前需重新评审）

- 与 `coordinate-naming.md` 迁移策略同类，属"搭车改"：在有连接点实体的重写时一并落地字段命名，不单独动。
- 候选方案：以 `PanelJoint` 为连接点载体，制造阶段为每个 joint 生成带 `connection_id` 的三件套孔位；校验按 id 对齐。
- 验收建议：删除某连接点后其全部孔位与 BOM 数量同步减少且校验通过；模拟"手动删单孔"时校验能报出具体连接点。

## 关联

- 五金参数位置：`SKILL.md` 工作流第 3 步（`hardware_catalog.yaml` / `hardware_rules.yaml`）；连接件结构见 `references/runtime-map.md`（`connectors/` + `ALL_CONNECTORS` 注册）。
- 局部坐标化（局部为唯一真源）：`connectors/trinity.py`、`back_mount.py`、`shelf.py` 已落地，P3 触发条件已满足。
````

## File: domain/skills/furniture-manufacturing/references/runtime-map.md
````markdown
# 运行时映射（制造阶段）

本参考集中说明 `SKILL.md` 工作流背后的运行时结构与校验职责；LLM 走业务流时不必逐条记忆，核对实现或规划演进时再读。

## 五金连接件（`connectors/`）

- 基类 `Connector` 定义统一接口：`match()`、`generate_holes()`、`generate_holes_for_panels()`、`boms()`、`machining_operations()`。
- 具体连接件：`TrinityConnector`（三合一）、`HingeConnector`（铰链）、`TwoInOneConnector`（二合一）、`ShelfPinConnector`（隔板钉）、`BackMountConnector`（背板）、`DrawerSlideConnector`（滑轨）。
- 新增五金：实现对应 `Connector` 并注册进 `ALL_CONNECTORS`。
- 孔位用 `HoleSpec` 描述；`is_face_hole=True` 表示板面钻孔（导出 TypeNo=1 垂直孔），`False` 表示板边钻孔（TypeNo=2 水平孔）。
- 旧数据缺省 `door_hinge_side` 时，`HingeConnector` 按门板位置回退。

## 五金命名约定

- 五金按「套」组织：三合一（偏心轮+连接杆+预埋螺母）、二合一（偏心轮+连接杆，固定塑料件并入连接杆）、隔板钉（单钉）。
- 目录键（`hardware_catalog.yaml`）全英文：顶层按套 `three_in_one` / `two_in_one` / `shelf_pin`，套内规格组 `standard`，零件键 `cam` / `rod` / `nut` / `pin`；每个零件分 `part`（实物，BOM/采购）与 `hole`（打孔，钻孔）两层，配合余量直接写入 `hole` 数值，不做代码派生。
- 孔类型（`hole_type`）按 `<套名>_<零件>`：`three_in_one_cam` / `three_in_one_rod` / `three_in_one_nut`、`two_in_one_cam` / `two_in_one_rod`、`shelf_pin`、`back_insert_cam` / `back_insert_rod` / `back_insert_nut`；进入 `drilled-holes.json` / GLB 标签 / 校验计数。
- 活动层板连接方式由 `FurnitureSpec.movable_shelf_connector`（`two_in_one`/`shelf_pin`）显式选择，经制造阶段盖章到 `PanelRecord`；`TwoInOneConnector`/`ShelfPinConnector` 只处理选中自己的板件，避免两者同时出孔/BOM。

## 生成与产物

- 单板规则实现 `generate_holes()`；需要配合板时覆盖 `generate_holes_for_panels()` 生成成对孔。
- `estimate_hardware()` 与 `emit_drilled_holes()` 遍历 `ALL_CONNECTORS` 生成 BOM 与可序列化的全局/local 孔位数据。
- 实际 `.drilled-holes.json` / `.glb` 文件由 CAD 阶段 `workflow_artifact_writer.py` 写入；制造阶段只产出结构化孔位数据。

## 背板槽机制

- `groove` 为左右侧板、顶/底板生成 4 条目标明确的 `cut_box`；槽宽 = `back_thickness + groove_clearance`，槽深 = `groove_depth`。
- `insert` 输出四边三合一成对孔；cover 外盖螺钉与 groove 背拉条螺钉属组装现场工艺，不生成孔位与五金。

## 校验职责

- `validation.py`：BOM、每条槽是否落在目标板件包络内、铰链孔位置/进刀面/深度、背板五金和配合孔。
- `hole_validator.py`：孔位几何（边界/深度/干涉）。深度按打孔方向的板件尺寸判定（端面钻入的连接杆/预孔可大于板厚）；正交配合孔（三合一杆↔轮）不判干涉。

## 演进中需求（待评审）

- 连接点级实体（杆/轮/螺母按连接点整体增删、校验按连接点对齐）：`references/connection-point-design.md`。
- 背板三合一孔类型合并（已定方向，待连接点身份）：`back_insert_cam/rod/nut` → `three_in_one_cam/rod/nut`；`cover`（外盖）也改三合一（当前代码视为螺钉组装现场、不钻孔）。阻塞在连接点身份：柜体与背板的预埋螺母孔都落在侧板，需 `connection_id` 才能区分与校验。
- 完整抽屉组件（门+抽屉混合区、托底轨、有面板）：`references/drawer-component-design.md`。

## 相关契约

- 坐标命名约定：`references/coordinate-naming.md`
- 六面钻导出（仅用户要求出机床文件时）：`references/six-side-drill-export.md`
````

## File: domain/skills/furniture-manufacturing/scripts/furniture_manufacturing/manufacturing_bom.py
````python
"""Manufacturing policy, machining operations, hardware, and BOM output."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Mapping

from furniture_panel_planning.panel_spec import FurnitureSpec, resolve_back_mount
from furniture_panel_planning.panel_models import PanelPlacement

from .manufacturing_edge_banding import get_edge_banding
from .connectors import ALL_CONNECTORS
from .manufacturing_models import HardwareRecord, MachiningOperation, PanelRecord


FURNITURE_NAMES = {
    "floor_cabinet": "落地柜",
    "wall_cabinet": "吊柜",
}

VALID_MANUFACTURING_READINESS = frozenset(
    {
        "preliminary",
        "accepted",
        "factory_ready",
    }
)

MANUFACTURING_READINESS_LABELS = {
    "preliminary": "暂定，软件默认值待确认",
    "accepted": "方案已接受，仍需工厂工艺核对",
    "factory_ready": "工厂已确认可投产",
}

MANUFACTURING_OPTION_FIELDS = frozenset(
    {
        "options",
    }
)


@dataclass
class BOMReport:
    furniture_name: str
    dimensions: str
    panels: list[PanelRecord]
    hardware: list[HardwareRecord]
    operations: list[MachiningOperation]
    total_area_m2: float = 0.0
    readiness: str = "preliminary"
    requested_options: dict[str, Any] = field(default_factory=dict)
    appearance: dict[str, Any] = field(default_factory=dict)

    @property
    def panel_count(self) -> int:
        return len(self.panels)

    @property
    def hardware_item_count(self) -> int:
        return len(self.hardware)


def plan_manufacturing(
    spec: FurnitureSpec,
    placements: list[PanelPlacement],
    *,
    requested_options: Mapping[str, Any] | None = None,
    appearance: Mapping[str, Any] | None = None,
) -> BOMReport:
    """Stage 4: apply materials and emit explicit machining operations."""
    options = dict(requested_options or {})
    unknown = sorted(set(options) - MANUFACTURING_OPTION_FIELDS)
    if unknown:
        raise ValueError(
            "manufacturing stage does not support: " + ", ".join(unknown)
        )
    back_mount = resolve_back_mount(
        spec.back_mount, spec.back_thickness, spec.board_thickness
    )
    panels = [_manufacturing_panel(spec, back_mount, item) for item in placements]
    operations = _back_groove_operations(spec, back_mount, placements)
    dimensions = f"{spec.width:.0f}×{spec.height:.0f}×{spec.depth:.0f}mm"
    connector_options = options.get("options", {})
    if not isinstance(connector_options, Mapping):
        connector_options = {}
    return BOMReport(
        furniture_name=FURNITURE_NAMES.get(spec.furniture_type, spec.furniture_type),
        dimensions=dimensions,
        panels=panels,
        hardware=estimate_hardware(panels, options=connector_options),
        operations=operations,
        total_area_m2=sum(panel.area_m2 for panel in panels),
        readiness="preliminary",
        requested_options=options,
        appearance=dict(appearance or {}),
    )


def _manufacturing_panel(spec: FurnitureSpec, back_mount: str, placement: PanelPlacement) -> PanelRecord:
    if placement.material_role == "back":
        material = f"{spec.back_thickness:g}mm背板"
        thickness = spec.back_thickness
    elif placement.material_role == "door":
        material = f"{spec.door_thickness:g}mm门板"
        thickness = spec.door_thickness
    else:
        material = f"{spec.board_thickness:g}mm柜体板"
        thickness = spec.board_thickness
    drill_length = 0.0
    # 优先从连接拓扑推导排钻孔方向
    joints = placement.joints
    if joints:
        for j in joints:
            if j.female_id == placement.id:
                # female（侧板等）：inner_face 在 x/y 轴 → 高度方向排钻
                face_axis = j.face[1] if len(j.face) >= 2 else ""
                if face_axis in ("x", "y"):
                    drill_length = placement.size_z
                    break
            if j.male_id == placement.id:
                # male（横板等）：端面在 x 轴 → 宽度方向排钻
                if j.edge_axis == "x":
                    drill_length = placement.size_x
                    break
    # fallback：无连接拓扑时退回 panel_type 判断
    if drill_length == 0.0:
        if placement.panel_type in ("side", "divider"):
            drill_length = placement.size_z
        elif placement.panel_type in ("top", "bottom", "fixed_shelf", "movable_shelf"):
            drill_length = placement.size_x
        elif placement.panel_type == "door":
            drill_length = placement.size_z
    return PanelRecord(
        label=placement.id,
        name=placement.name,
        panel_type=placement.panel_type,
        material=material,
        thickness=thickness,
        length_mm=placement.size_x,
        width_mm=placement.size_y,
        size_x=placement.size_x,
        size_y=placement.size_y,
        size_z=placement.size_z,
        quantity=placement.quantity,
        drill_length=drill_length,
        edge_banding=_edge_banding_for(placement.panel_type, back_mount),
        note=placement.note,
        pos_x=placement.pos_x,
        pos_y=placement.pos_y,
        pos_z=placement.pos_z,
        depends_on=list(placement.depends_on),
        door_hinge_side=placement.door_hinge_side,
        door_overlay=placement.door_overlay,
        back_mount=back_mount,
        movable_shelf_connector=spec.movable_shelf_connector,
        inner_face=placement.inner_face,
        outer_face=placement.outer_face,
        cam_face=placement.cam_face,
        joints=list(placement.joints),
    )


def _edge_banding_for(panel_type: str, back_mount: str) -> dict[str, str]:
    if panel_type == "back" and back_mount == "groove":
        return {}
    return get_edge_banding(panel_type)


def _back_groove_operations(
    spec: FurnitureSpec,
    back_mount: str,
    placements: list[PanelPlacement],
) -> list[MachiningOperation]:
    if back_mount != "groove":
        return []
    by_id = {panel.id: panel for panel in placements}
    required = {"left_side_panel", "right_side_panel", "top_panel", "bottom_panel", "back_panel"}
    if not required.issubset(by_id):
        return []
    back = by_id["back_panel"]
    board = spec.board_thickness
    depth = spec.groove_depth
    groove_width = spec.back_thickness + spec.groove_clearance
    groove_y = spec.back_offset
    common = {"operation_type": "cut_box", "size_y": groove_width, "pos_y": groove_y}
    return [
        MachiningOperation(
            id="left_side_back_groove",
            target_panel="left_side_panel",
            size_x=depth,
            size_z=back.size_z,
            pos_x=board - depth,
            pos_z=back.pos_z,
            note="左侧板背板槽",
            **common,
        ),
        MachiningOperation(
            id="right_side_back_groove",
            target_panel="right_side_panel",
            size_x=depth,
            size_z=back.size_z,
            pos_x=spec.width - board,
            pos_z=back.pos_z,
            note="右侧板背板槽",
            **common,
        ),
        MachiningOperation(
            id="top_back_groove",
            target_panel="top_panel",
            size_x=spec.width - 2 * board,
            size_z=depth,
            pos_x=board,
            pos_z=spec.height - board,
            note="顶板背板槽",
            **common,
        ),
        MachiningOperation(
            id="bottom_back_groove",
            target_panel="bottom_panel",
            size_x=spec.width - 2 * board,
            size_z=depth,
            pos_x=board,
            pos_z=by_id["bottom_panel"].pos_z + board - depth,
            note="底板背板槽",
            **common,
        ),
    ]


def estimate_hardware(
    panels: List[PanelRecord],
    *,
    options: Mapping[str, Any] | None = None,
) -> List[HardwareRecord]:
    hardware: List[HardwareRecord] = []
    for connector_cls in ALL_CONNECTORS:
        connector = connector_cls()
        hardware.extend(connector.boms(panels, options=options))
    return hardware


def format_bom_markdown(report: BOMReport) -> str:
    lines = [
        f"## 拆单报告 - {report.furniture_name}",
        "",
        f"外形尺寸: **{report.dimensions}**",
        f"制造状态: **{report.readiness}** — "
        f"{MANUFACTURING_READINESS_LABELS.get(report.readiness, '未知状态')}",
        "",
        f"### 板件清单 ({report.panel_count} 块)",
        "",
        "| 序号 | 名称 | 类型 | 开料尺寸(mm) | 厚度 | 数量 | 封边 | 备注 |",
        "|------|------|------|-------------|------|------|------|------|",
    ]
    for index, panel in enumerate(report.panels, 1):
        lines.append(
            f"| {index} | {panel.name} | {panel.panel_type} | "
            f"{panel.length_mm:.0f}×{panel.width_mm:.0f} | "
            f"{panel.thickness:.0f} | {panel.quantity} | "
            f"{panel.edge_banding_summary()} | {panel.note} |"
        )
    lines.extend(["", f"**总展开面积**: {report.total_area_m2:.4f} m²"])
    if report.operations:
        lines.extend(["", f"### 加工操作 ({len(report.operations)} 项)", ""])
        for operation in report.operations:
            lines.append(
                f"- {operation.note}: {operation.target_panel}, "
                f"{operation.size_x:g}×{operation.size_y:g}×{operation.size_z:g}mm"
            )
    if report.hardware:
        lines.extend(["", f"### 五金清单 ({len(report.hardware)} 项)", ""])
        for item in report.hardware:
            note = f"；{item.note}" if item.note else ""
            lines.append(
                f"- {item.name} {item.spec} ×{item.quantity}{item.unit}{note}"
            )
    return "\n".join(lines)


def _build_color_legend() -> Dict[str, Dict[str, str]]:
    """孔型图例：由各 Connector 的 hole_legend 自声明派生。"""
    legend: Dict[str, Dict[str, str]] = {
        # 背板槽是 cut_box 加工操作，非五金孔，留在制造阶段（不随 Connector 下沉）
        "back_groove": {"color": "#FFD700", "label": "背板槽"},
    }
    for connector_cls in ALL_CONNECTORS:
        for hole_type, meta in connector_cls.hole_legend.items():
            legend[hole_type] = {"color": meta["color"], "label": meta["label"]}
    return legend


_COLOR_LEGEND = _build_color_legend()


def emit_drilled_holes(bom: BOMReport) -> dict:
    """Generate a per-panel hole summary for Viewer overlay.

    Uses Connectors to produce HoleSpec records with both global and local
    coordinates, then groups them by panel label.
    """
    panel_holes: dict[str, list[dict]] = {}

    for connector_cls in ALL_CONNECTORS:
        connector = connector_cls()
        for hole in connector.generate_holes_for_panels(bom.panels):
            panel_holes.setdefault(hole.panel_label, []).append({
                "hole_type": hole.hole_type,
                "color": _COLOR_LEGEND.get(hole.hole_type, {}).get("color", "#888888"),
                "x": round(hole.x_global, 2),
                "y": round(hole.y_global, 2),
                "z": round(hole.z_global, 2),
                "local_x": round(hole.x_local, 2),
                "local_y": round(hole.y_local, 2),
                "local_z": round(hole.z_local, 2),
                "diameter": hole.diameter,
                "depth": hole.depth,
                "direction": hole.direction,
                "is_face_hole": hole.is_face_hole,
                "note": hole.note,
            })

    panels_out = []
    for panel in bom.panels:
        entry: dict = {
            "label": panel.label,
            "name": panel.name,
            "panel_type": panel.panel_type,
            "box": {
                "x": panel.size_x, "y": panel.size_y, "z": panel.size_z,
                "pos_x": panel.pos_x, "pos_y": panel.pos_y, "pos_z": panel.pos_z,
            },
            "holes": panel_holes.get(panel.label, []),
        }
        panels_out.append(entry)

    return {
        "furniture_name": bom.furniture_name,
        "dimensions": bom.dimensions,
        "color_legend": _COLOR_LEGEND,
        "panels": panels_out,
    }
````

## File: domain/skills/furniture-panel-planning/scripts/furniture_panel_planning/panel_spec.py
````python
"""Structured contract admitted by the ``panels_planned`` stage."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

from furniture_design_intent.design_intent import DesignIntent, SUPPORTED_TYPES

from .panel_rules import resolve_door_hinge_side


VALID_BACK_MOUNTS = frozenset({"auto", "groove", "insert", "cover"})

# 活动层板连接方式：二选一。默认候选为 two_in_one，但必须是显式+待确认的提案值，
# 不得由代码静默补齐（见 furniture-panel-planning SKILL.md）。
VALID_MOVABLE_SHELF_CONNECTORS = frozenset({"two_in_one", "shelf_pin"})

VALID_SHELF_TYPES = frozenset({"fixed", "movable"})


@dataclass(frozen=True)
class ShelfSpec:
    """一层板（固定/活动）及其下方净高。

    gap_below_mm：本层板底面 到 下方紧邻一层顶面 的净高（mm）；
    None 表示「计算层」，由内净高反推、吸收剩余。
    """

    shelf_type: str                # "fixed" | "movable"
    gap_below_mm: float | None     # None = auto（计算层）


def _coerce_shelves(raw: Any) -> list[ShelfSpec]:
    """把 shelves 输入规范化为 ShelfSpec 列表（自动解析 gap_below_mm 的 auto）。"""
    if not isinstance(raw, (list, tuple)):
        raise ValueError("shelves must be a list")
    result: list[ShelfSpec] = []
    for item in raw:
        if isinstance(item, ShelfSpec):
            result.append(item)
            continue
        if not isinstance(item, Mapping):
            raise ValueError("each shelf entry must be an object")
        shelf_type = item.get("shelf_type", item.get("type"))
        if shelf_type not in VALID_SHELF_TYPES:
            raise ValueError(
                "shelf type must be one of: " + ", ".join(sorted(VALID_SHELF_TYPES))
            )
        gap = item.get("gap_below_mm")
        if gap is None or gap == "auto":
            gap_below: float | None = None
        else:
            gap_below = float(gap)
            if gap_below < 0:
                raise ValueError("gap_below_mm must be non-negative or 'auto'")
        result.append(ShelfSpec(shelf_type=shelf_type, gap_below_mm=gap_below))
    return result

# Every field is an LLM/user proposal decision. Runtime rejects omissions instead
# of selecting a cabinet profile or filling construction defaults.
PANEL_PARAMETER_FIELDS = frozenset(
    {
        "board_thickness", "back_thickness", "door_thickness",
        "toe_kick_height", "back_offset", "door_margin", "door_hinge_gap",
        "groove_depth", "groove_clearance", "toe_kick_reveal_front",
        "toe_kick_reveal_back", "toe_kick_support_count", "back_mount",
        "back_rail_height", "drawer_count", "drawer_side_clearance",
        "drawer_layer_gap", "drawer_bottom_thickness", "drawer_back_thickness",
        "drawer_back_clearance", "shelves", "top_gap_mm", "n_doors",
        "door_hinge_side", "movable_shelf_connector",
    }
)
PANEL_SPEC_FIELDS = PANEL_PARAMETER_FIELDS | {"door_count"}
_SERIALIZED_FIELDS = PANEL_PARAMETER_FIELDS | {
    "furniture_type", "width", "depth", "height",
}


@dataclass
class FurnitureSpec:
    """Complete, executable construction specification."""

    furniture_type: str
    width: float
    depth: float
    height: float
    board_thickness: float
    back_thickness: float
    door_thickness: float
    toe_kick_height: float
    back_offset: float
    door_margin: float
    door_hinge_gap: float
    shelves: list[ShelfSpec]
    top_gap_mm: float
    n_doors: int
    drawer_count: int
    groove_depth: float
    groove_clearance: float
    toe_kick_reveal_front: float
    toe_kick_reveal_back: float
    toe_kick_support_count: int | None
    back_mount: str
    back_rail_height: float
    drawer_side_clearance: float
    drawer_layer_gap: float
    drawer_bottom_thickness: float
    drawer_back_thickness: float
    drawer_back_clearance: float
    door_hinge_side: str | None
    movable_shelf_connector: str

    def __post_init__(self) -> None:
        if self.furniture_type not in SUPPORTED_TYPES:
            raise ValueError(
                f"furniture_type must be an executable canonical type: "
                f"{self.furniture_type}"
            )
        for name in (
            "width", "depth", "height", "board_thickness", "back_thickness",
            "door_thickness", "toe_kick_height", "back_offset", "door_margin",
            "door_hinge_gap", "groove_depth", "groove_clearance",
            "toe_kick_reveal_front", "toe_kick_reveal_back", "back_rail_height",
            "drawer_side_clearance", "drawer_layer_gap", "drawer_bottom_thickness",
            "drawer_back_thickness", "drawer_back_clearance",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
            ):
                raise ValueError(f"{name} must be numeric and finite")
        for name in ("n_doors", "drawer_count"):
            _require_count(getattr(self, name), name)
        if self.toe_kick_support_count is not None:
            _require_count(self.toe_kick_support_count, "toe_kick_support_count")
        self.back_mount = resolve_back_mount(
            self.back_mount, self.back_thickness, self.board_thickness
        )
        self.shelves = _coerce_shelves(self.shelves)
        _validate_objective_invariants(self)

    @classmethod
    def from_intent(
        cls,
        intent: DesignIntent,
        options: Mapping[str, Any] | None,
    ) -> "FurnitureSpec":
        """Admit a complete proposal against a confirmed finished envelope."""
        if not isinstance(intent, DesignIntent) or not intent.confirmed:
            raise ValueError("panel planning requires a confirmed DesignIntent")
        if not isinstance(options, Mapping):
            raise ValueError("panel proposal must be an object")
        values = dict(options)
        unknown = sorted(set(values) - PANEL_SPEC_FIELDS)
        if unknown:
            raise ValueError("panel stage does not support: " + ", ".join(unknown))
        if "door_count" in values:
            if "n_doors" in values and values["n_doors"] != values["door_count"]:
                raise ValueError("door_count and n_doors must match")
            values["n_doors"] = values.pop("door_count")
        missing = sorted(PANEL_PARAMETER_FIELDS - set(values))
        if missing:
            raise ValueError(
                "panel proposal is incomplete; missing: " + ", ".join(missing)
            )
        dimensions = (
            intent.overall_size.width_mm,
            intent.overall_size.depth_mm,
            intent.overall_size.height_mm,
        )
        if any(value is None for value in dimensions):
            raise ValueError("panel planning requires a confirmed finished envelope")
        return cls.from_dict(
            {
                "furniture_type": intent.furniture_type,
                "width": dimensions[0],
                "depth": dimensions[1],
                "height": dimensions[2],
                **values,
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FurnitureSpec":
        """Read a serialized complete spec without filling missing values."""
        values = dict(data)
        if "type" in values:
            if "furniture_type" in values and values["furniture_type"] != values["type"]:
                raise ValueError("type and furniture_type must match")
            values["furniture_type"] = values.pop("type")
        unknown = sorted(set(values) - _SERIALIZED_FIELDS)
        missing = sorted(_SERIALIZED_FIELDS - set(values))
        if unknown:
            raise ValueError(
                "serialized panel spec does not support: " + ", ".join(unknown)
            )
        if missing:
            raise ValueError(
                "serialized panel spec is incomplete; missing: " + ", ".join(missing)
            )
        if "shelves" in values:
            values["shelves"] = _coerce_shelves(values["shelves"])
        return cls(**values)


def resolve_back_mount(
    requested: str,
    back_thickness: float,
    board_thickness: float,
) -> str:
    """Resolve the explicitly requested strategy by a deterministic rule."""
    if requested not in VALID_BACK_MOUNTS:
        raise ValueError(
            f"back_mount must be one of: {', '.join(sorted(VALID_BACK_MOUNTS))}"
        )
    if requested != "auto":
        return requested
    return "insert" if back_thickness >= board_thickness else "groove"


def resolve_shelf_gaps(spec: FurnitureSpec, internal_height: float) -> list[float]:
    """返回每层板下方净高（从上到下），并解析 auto 层为「剩余」。

    auto = 内净高 − top_gap_mm − N×板厚 − 其余显式净高之和。
    """
    board = spec.board_thickness
    count = len(spec.shelves)
    explicit = [s.gap_below_mm for s in spec.shelves if s.gap_below_mm is not None]
    auto_count = count - len(explicit)
    if auto_count == 1:
        auto = internal_height - spec.top_gap_mm - count * board - sum(explicit)
        if auto < 0:
            raise ValueError("shelf gaps exceed the internal height")
        return [auto if s.gap_below_mm is None else s.gap_below_mm for s in spec.shelves]
    total = spec.top_gap_mm + count * board + sum(explicit)
    if abs(total - internal_height) > 0.5:
        raise ValueError(
            "explicit shelf gaps and top gap do not fill the internal height "
            f"(sum={total:g}, internal_height={internal_height:g})"
        )
    return list(explicit)


def migrate_legacy_panel_hinge_side(
    panel_parameters: dict[str, Any] | None,
    panel_output: dict[str, Any] | None,
) -> None:
    """Upgrade persisted pre-field panel data without guessing a preference."""
    output_side_available = False
    migrated_side: str | None = None
    if isinstance(panel_output, dict):
        spec = panel_output.get("spec")
        if isinstance(spec, dict):
            if "door_hinge_side" not in spec:
                door_count = _legacy_door_count(spec)
                doors = _legacy_doors(panel_output)
                if len(doors) != door_count:
                    raise ValueError(
                        "legacy panel output door count does not match its specification"
                    )
                if door_count == 1:
                    migrated_side = doors[0].get("door_hinge_side")
                    if migrated_side not in {"left", "right"}:
                        raise ValueError(
                            "legacy single-door output requires one explicit panel "
                            "door_hinge_side for migration"
                        )
                ordered_doors = sorted(
                    doors,
                    key=lambda panel: (
                        float(panel.get("pos_x", 0.0)),
                        str(panel.get("id", "")),
                    ),
                )
                for index, door in enumerate(ordered_doors):
                    expected_side = resolve_door_hinge_side(
                        door_count,
                        index,
                        migrated_side,
                    )
                    actual_side = door.get("door_hinge_side")
                    if door_count == 2 and actual_side is None:
                        door["door_hinge_side"] = expected_side
                    elif actual_side != expected_side:
                        raise ValueError(
                            "legacy panel output has inconsistent door_hinge_side values"
                        )
                spec["door_hinge_side"] = migrated_side
            else:
                migrated_side = spec["door_hinge_side"]
            output_side_available = True

    if not isinstance(panel_parameters, dict) or "door_hinge_side" in panel_parameters:
        return
    if output_side_available:
        panel_parameters["door_hinge_side"] = migrated_side
        return
    door_count = panel_parameters.get(
        "n_doors",
        panel_parameters.get("door_count"),
    )
    if (
        isinstance(door_count, int)
        and not isinstance(door_count, bool)
        and door_count >= 0
        and door_count != 1
    ):
        panel_parameters["door_hinge_side"] = None


def _legacy_door_count(spec: Mapping[str, Any]) -> int:
    value = spec.get("n_doors", spec.get("door_count"))
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("legacy panel spec requires a valid n_doors for migration")
    return value


def _legacy_doors(panel_output: Mapping[str, Any]) -> list[dict[str, Any]]:
    panels = panel_output.get("panels")
    if not isinstance(panels, list):
        return []
    return [
        panel
        for panel in panels
        if isinstance(panel, dict) and panel.get("panel_type") == "door"
    ]


def _require_count(value: Any, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _validate_objective_invariants(spec: FurnitureSpec) -> None:
    positive = (
        "width", "depth", "height", "board_thickness", "back_thickness",
        "door_thickness", "drawer_side_clearance", "drawer_bottom_thickness",
        "drawer_back_thickness",
    )
    non_negative = (
        "toe_kick_height", "back_offset", "door_margin", "door_hinge_gap",
        "groove_clearance", "toe_kick_reveal_front", "toe_kick_reveal_back",
        "back_rail_height", "drawer_layer_gap", "drawer_back_clearance",
        "top_gap_mm",
    )
    if any(getattr(spec, name) <= 0 for name in positive):
        raise ValueError("positive dimensions and thicknesses are required")
    if any(getattr(spec, name) < 0 for name in non_negative):
        raise ValueError("clearances, margins and offsets cannot be negative")
    if spec.back_mount == "groove" and spec.groove_depth <= 0:
        raise ValueError("groove_depth must be positive for groove back_mount")
    if spec.furniture_type == "wall_cabinet" and (
        spec.toe_kick_height != 0
        or spec.toe_kick_support_count not in {None, 0}
        or spec.drawer_count != 0
    ):
        raise ValueError(
            "wall_cabinet cannot contain a toe kick or full-height drawers"
        )
    if spec.toe_kick_height == 0 and spec.toe_kick_support_count not in {None, 0}:
        raise ValueError("toe-kick supports require a positive toe_kick_height")
    if spec.drawer_count and (spec.shelves or spec.n_doors):
        raise ValueError("full-height drawers require no shelves and n_doors=0")
    if spec.door_hinge_side not in {None, "left", "right"}:
        raise ValueError("door_hinge_side must be 'left', 'right', or null")
    if spec.n_doors == 1:
        if spec.door_hinge_side not in {"left", "right"}:
            raise ValueError(
                "a single door requires an explicit door_hinge_side 'left' or 'right'"
            )
    elif spec.door_hinge_side is not None:
        raise ValueError(
            "door_hinge_side only applies to a single door; use null otherwise"
        )
    if spec.movable_shelf_connector not in VALID_MOVABLE_SHELF_CONNECTORS:
        raise ValueError(
            "movable_shelf_connector must be one of: "
            + ", ".join(sorted(VALID_MOVABLE_SHELF_CONNECTORS))
        )
    if sum(1 for s in spec.shelves if s.gap_below_mm is None) > 1:
        raise ValueError("at most one shelf gap may be 'auto'")
````

## File: domain/skills/furniture-panel-planning/SKILL.md
````markdown
---
name: furniture-panel-planning
description: 用于 panels_planned 阶段。在已确认成品外包络上理解并提议门、层板、抽屉、板厚、背板、踢脚和净空方案，经结构化代码准入后生成可审查的实体板件；不负责房间摆放或制造策略。
---

# 家具板件规划

阶段：`panels_planned`

## 工作流

1. 只要求 `design_intent` 已确认；独立 `furniture-layout` 结果不是前置条件。
2. 由 LLM 根据完整上下文理解需求、消歧并推荐方案；展示未明确值的假设，不在脚本里做关键词识别、同义词映射或开放方案排序。
3. 把选定草稿的全部规范字段写入 `stage_inputs.panels.parameters`。缺字段不得由代码静默补齐；`toe_kick_support_count=null` 和 `back_mount=auto` 必须是显式结构化值。
4. 由 `FurnitureSpec.from_intent()` 校验意图确认状态、字段完整性/类型和客观结构冲突，首次物化完整规范。混合门/层板/整高抽屉语义无法由当前拓扑表达时先继续消歧，不得让运行时丢弃字段。
5. 依据 [背板结构规则](references/back-construction-rules.md) 对显式 `back_mount=auto` 做确定性解析，生成精确 `CabinetStructure`：柜体前后范围、内部 X/Y/Z 净空、背板基准和踢脚区域。
6. 按 [板件定义规则](references/panel-definition-rules.md) 与 `references/cabinet-topologies/` 柜型拓扑生成实体板件；仅入槽背板生成背拉条。抽屉几何只消费已准入的板件字段，不读取制造五金目录来选择净空。
7. `panel_rules.py` 统一计算显式请求自动计算的踢脚支撑、背拉条数量及净距；生成器和校验器必须共用。
8. 输出 `spec/structure/back_mount_resolution/panels`；校验结构规格、精确净空、板件标识/尺寸/位置/依赖和背板几何。展示后暂停，等待用户确认；未通过不得进入制造、BOM、特征树或 CAD。
9. 用户要求尺寸链、单位或公差审计时，先读 `../../external/scientific-agent-skills/skills/uncertainty-and-units/SKILL.md`，再用 `scripts/furniture_panel_planning/quantitative_audit.py` 对当前输出生成 `stage_analyses.panels_planned.panel_unit_audit`；不得据此静默改板件。
10. 用户要求在材料用量、内部空间和复杂度间优化时，先读 `../../external/scientific-agent-skills/skills/pymoo/SKILL.md`，由 LLM 明确目标与候选变量，再用 `design_optimization.py` 生成有来源摘要的 Pareto 候选。只有用户选中候选后才用 `revise_stage_output()`。

## 提案

- 完整参数包括层板列表 `shelves`（从上到下，每项 `{shelf_type: fixed|movable, gap_below_mm: 净高|null=auto}`）与顶格 `top_gap_mm`、数量 `n_doors/drawer_count`、单门铰链侧 `door_hinge_side`（`n_doors=1` 时必填 `left/right`，其余显式 `null`），活动层板连接方式 `movable_shelf_connector`（`two_in_one`/`shelf_pin`），主体厚度，背板模式/偏移/槽/背拉条，门缝与踢脚，以及五项抽屉净空/厚度；单位均为 mm。自然语言说明留在交互中。
- 常见提议起点可采用柜体/门板 18、背板 9、背板后移 18、门边缝 1.5、铰链深度缝 2、槽深 6、槽余量 1、背拉条高 70；抽屉每侧净空 13、层缝 1.5、底/背板厚 18、后净空 0。落地柜可从 50 高踢脚、4 层板/2 门起步，吊柜可从无踢脚、1 层板/2 门起步。它们只是 LLM 候选，须结合需求逐字段确认。
- `toe_kick_support_count=null` 是显式请求宽度公式，`back_mount=auto` 是显式请求厚度公式，均不是运行时缺省。混合门/抽屉、分区柜或多门开启关系超出当前拓扑时继续消歧。
- `movable_shelf_connector` 是活动层板连接方式的显式枚举（`two_in_one`=二合一、`shelf_pin`=隔板钉）；无偏好时提议 `two_in_one` 作为待确认默认，不得由代码静默补齐。
- `shelves` 按从上到下的视觉顺序排列；每项 `gap_below_mm` 是「本层板底面到下方紧邻一层顶面」的净高，最下层到底板顶面，顶格由 `top_gap_mm` 表示；恰好一项 `gap_below_mm` 可为 `null`/`auto`（计算层，吸收剩余）。均分由 LLM 算出具体值填入，运行时不做均分、不保留 `shelf_count`。

## 边界

- 运行时在 `scripts/furniture_panel_planning/`；`panel_spec.py` 只拥有规范 schema、完整性/客观不变量准入和背板模式解析，`structure_planning.py` 是精确净空的唯一所有者。代码不得按自然语言、柜型或内置 profile 选择方案。
- 板件须有稳定标识、角色、尺寸、位置和材料角色；本阶段输出是后续制造所用的已确认 `FurnitureSpec` 来源。
- 旧持久化 Project 缺少 `spec.door_hinge_side` 时只做有界 schema 迁移：单门仅从唯一门板已有的显式 `left/right` 恢复，缺失或冲突即停止；标准双门的规格迁移为 `null`，板件缺省侧按确定性左右拓扑恢复；更多门保持 `null`。新提案和扁平 API 契约仍必须显式提交该字段，迁移不得猜测新的单门偏好。
- 修改规划用 `revise_stage_output()`，使本阶段及下游失效。
- 不在此阶段确定连接件孔位、封边细节、最终 BOM 或 CAD 操作。
- 单位审计和优化报告属于可重跑的旁路证据；`panels_planned` 仍是唯一板件事实来源。
````

## File: AGENTS.md
````markdown
# 家具 Skill 开发约定

创建、修改或审查 `domain/skills/furniture-*`、家具工作流入口及其测试前，必须完整读取
[LLM 与运行时边界](.agents/skills/furniture-agent/references/llm-runtime-boundary.md)。

- 遵守“LLM 提案、代码准入”：自然语言理解和可确认的方案选择归 LLM；结构化契约、确定性计算、状态、验证与副作用归代码。
- 新增运行时代码前，按边界文档逐项判断；无法归入允许代码类别的逻辑，移到所属 Skill 的 `SKILL.md` 或 `references/`。
- 修改完成后执行边界审计，检查新增的分支、映射、默认值和解析器，并在交付说明中报告保留在代码中的理由及任何例外。
- 自动化测试只验证客观不变量与本约定可发现性，不用关键词扫描代替语义审计。
````

## File: domain/skills/furniture-cad/scripts/furniture_workflow/input_adapter.py
````python
"""Route flat protocol inputs to the stage that owns each decision."""

from __future__ import annotations

from typing import Any, Mapping

from furniture_design_intent.design_intent import DesignIntent
from furniture_panel_planning.panel_spec import PANEL_SPEC_FIELDS


PANEL_CONFIGURATION_FIELDS = frozenset({"n_doors", "door_count"})
LAYOUT_CONTEXT_FIELDS = frozenset({"room", "placement"})
MANUFACTURING_SPEC_FIELDS = frozenset(
    {
        "options",
    }
)
PROTOCOL_FIELDS = frozenset(
    {
        "type",
        "furniture_type",
        "width",
        "depth",
        "height",
        "overall_size",
        "mounting_height",
        "mounting_height_mm",
        "mount_mode",
        "purpose",
        "layout",
        "appearance",
        "structure",
        "manufacturing",
        "constraints",
        "constraint_mappings",
        "room",
        "placement",
        *PANEL_CONFIGURATION_FIELDS,
        *PANEL_SPEC_FIELDS,
        *MANUFACTURING_SPEC_FIELDS,
    }
)


def intent_from_spec(spec: Mapping[str, Any]) -> DesignIntent:
    """Translate only category and finished-envelope values to DesignIntent."""
    data = dict(spec)
    furniture_type = str(
        data.get("type", data.get("furniture_type", ""))
    ).strip().lower()
    size = data.get("overall_size", {})
    if not isinstance(size, Mapping):
        raise ValueError("overall_size must be an object")
    mount_mode = data.get("mount_mode")
    if mount_mode is not None:
        mount_mode = str(mount_mode).strip().lower()
    return DesignIntent.from_dict(
        {
            "furniture_type": furniture_type,
            "overall_size": {
                "width_mm": size.get("width_mm", data.get("width")),
                "depth_mm": size.get("depth_mm", data.get("depth")),
                "height_mm": size.get("height_mm", data.get("height")),
            },
            "mount_mode": mount_mode,
            "mounting_height_mm": data.get(
                "mounting_height_mm", data.get("mounting_height")
            ),
        }
    )


def stage_inputs_from_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Preserve downstream requests without treating them as confirmed intent."""
    data = dict(spec)
    unknown = sorted(set(data) - PROTOCOL_FIELDS)
    if unknown:
        raise ValueError("request field has no owning stage: " + ", ".join(unknown))
    raw_layout = data.get("layout", {})
    raw_structure = data.get("structure", {})
    raw_manufacturing = data.get("manufacturing", {})
    if not isinstance(raw_layout, Mapping):
        raise ValueError("layout must be an object")
    if not isinstance(raw_structure, Mapping):
        raise ValueError("structure must be an object")
    if not isinstance(raw_manufacturing, Mapping):
        raise ValueError("manufacturing must be an object")

    unknown_layout = sorted(
        set(raw_layout) - LAYOUT_CONTEXT_FIELDS - PANEL_CONFIGURATION_FIELDS
    )
    if unknown_layout:
        raise ValueError(
            "layout input only accepts independent room placement or panel counts: "
            + ", ".join(unknown_layout)
        )
    panel_parameters = dict(raw_structure)
    for key in PANEL_CONFIGURATION_FIELDS:
        if key in raw_layout:
            panel_parameters[key] = raw_layout[key]
    manufacturing_parameters = dict(raw_manufacturing)

    for key in PANEL_SPEC_FIELDS:
        if key in data:
            panel_parameters[key] = data[key]
    for key in MANUFACTURING_SPEC_FIELDS:
        if key in data:
            manufacturing_parameters[key] = data[key]

    room = data.get("room", raw_layout.get("room"))
    placement = data.get("placement", raw_layout.get("placement"))
    output: dict[str, Any] = {
        "layout": {
            "room": room,
            "placement": placement,
        },
        "panels": {"parameters": panel_parameters},
        "manufacturing": {
            "parameters": manufacturing_parameters,
            "appearance": dict(data.get("appearance", {})),
        },
    }
    purpose = str(data.get("purpose", "")).strip()
    if purpose:
        output["layout"]["purpose"] = purpose
    _route_constraints(data, output)
    return output


def _route_constraints(data: Mapping[str, Any], output: dict[str, Any]) -> None:
    constraints = data.get("constraints", [])
    mappings = data.get("constraint_mappings", {})
    if not isinstance(constraints, list):
        raise ValueError("constraints must be a list")
    if not isinstance(mappings, Mapping):
        raise ValueError("constraint_mappings must be an object")
    informational: list[str] = []
    envelope: list[dict[str, str]] = []
    for constraint in constraints:
        if not isinstance(constraint, str) or not constraint.strip():
            raise ValueError("constraints must contain non-empty strings")
        target = mappings.get(constraint)
        if target is None:
            raise ValueError(f"constraint has no stage mapping: {constraint}")
        target = str(target)
        if target == "informational":
            informational.append(constraint)
            continue
        record = {"text": constraint, "target": target}
        if target == "furniture_type" or target.startswith("overall_size."):
            if not _envelope_target_is_explicit(data, target):
                raise ValueError(f"constraint target is not explicit: {target}")
            envelope.append(record)
        elif target.startswith("layout."):
            field = target.split(".", 1)[1]
            if field in PANEL_CONFIGURATION_FIELDS:
                if field not in output["panels"].get("parameters", {}):
                    raise ValueError(f"constraint target is not explicit: {target}")
                output["panels"].setdefault("constraints", []).append(record)
            else:
                if field not in LAYOUT_CONTEXT_FIELDS or output["layout"].get(field) is None:
                    raise ValueError(f"constraint target is not explicit: {target}")
                output["layout"].setdefault("constraints", []).append(record)
        elif target.startswith(("structure.", "panels.")):
            field = target.split(".", 1)[1]
            if field not in output["panels"].get("parameters", {}):
                raise ValueError(f"constraint target is not explicit: {target}")
            output["panels"].setdefault("constraints", []).append(record)
        elif target.startswith("manufacturing."):
            field = target.split(".", 1)[1]
            if field not in output["manufacturing"].get("parameters", {}):
                raise ValueError(f"constraint target is not explicit: {target}")
            output["manufacturing"].setdefault("constraints", []).append(record)
        else:
            raise ValueError(f"constraint target has no owning stage: {target}")
    stale = sorted(set(mappings) - set(constraints))
    if stale:
        raise ValueError(
            "constraint mapping has no matching constraint: "
            + ", ".join(stale)
        )
    if informational:
        output["informational_constraints"] = informational
    if envelope:
        output["envelope_constraints"] = envelope


def _envelope_target_is_explicit(data: Mapping[str, Any], target: str) -> bool:
    if target == "furniture_type":
        return bool(data.get("type", data.get("furniture_type")))
    field = target.split(".", 1)[1]
    size = data.get("overall_size", {})
    flat_name = {
        "width_mm": "width",
        "depth_mm": "depth",
        "height_mm": "height",
    }.get(field)
    return (
        isinstance(size, Mapping)
        and size.get(field) is not None
    ) or (flat_name is not None and data.get(flat_name) is not None)


def layout_stage_input(stage_inputs: Mapping[str, Any]) -> dict[str, Any]:
    value = stage_inputs.get("layout", {})
    return dict(value) if isinstance(value, Mapping) else {}


def panel_stage_input(stage_inputs: Mapping[str, Any]) -> dict[str, Any]:
    value = stage_inputs.get("panels", {})
    return dict(value) if isinstance(value, Mapping) else {}


def manufacturing_stage_input(stage_inputs: Mapping[str, Any]) -> dict[str, Any]:
    value = stage_inputs.get("manufacturing", {})
    return dict(value) if isinstance(value, Mapping) else {}
````

## File: domain/skills/furniture-cad/scripts/tests/test_back_mount_modes.py
````python
from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_panel_planning.panel_spec import FurnitureSpec
from panel_fixtures import cabinet_data, furniture_spec
from furniture_layout.layout_pipeline import plan_layout
from furniture_layout.validation import validate_layout
from furniture_manufacturing.manufacturing_bom import (
    emit_drilled_holes,
    plan_manufacturing,
)
from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.structure_planning import CabinetStructure
from furniture_panel_planning.validation import validate_panels, validate_structure
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_state import WorkflowStage


class BackMountModeTests(unittest.TestCase):
    def _spec(self, back_mount: str) -> FurnitureSpec:
        return furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            back_mount=back_mount,
            back_thickness=18 if back_mount == "insert" else 9,
            shelf_count=1,
            n_doors=2,
        )

    def test_all_modes_preserve_the_finished_depth_envelope(self) -> None:
        expected_layouts = {
            "groove": (0.0, 580.0, 27.0),
            "insert": (0.0, 580.0, 36.0),
            "cover": (9.0, 580.0, 9.0),
        }

        for back_mount, expected in expected_layouts.items():
            with self.subTest(back_mount=back_mount):
                spec = self._spec(back_mount)
                layout = plan_layout(spec)
                structure = CabinetStructure.from_spec(spec)
                placements = plan_panels(spec, layout)
                panels = {panel.id: panel for panel in placements}
                carcass_y_start, carcass_y_end, internal_y_start = expected

                self.assertEqual(structure.carcass_y_start, carcass_y_start)
                self.assertEqual(structure.carcass_y_end, carcass_y_end)
                self.assertEqual(
                    structure.side_depth,
                    carcass_y_end - carcass_y_start,
                )
                self.assertEqual(structure.internal_y_start, internal_y_start)
                self.assertEqual(structure.internal_y_end, carcass_y_end)

                for panel_id in (
                    "left_side_panel",
                    "right_side_panel",
                    "top_panel",
                    "bottom_panel",
                ):
                    panel = panels[panel_id]
                    self.assertEqual(panel.pos_y, carcass_y_start)
                    self.assertEqual(panel.pos_y + panel.size_y, carcass_y_end)

                shelf = next(
                    panel
                    for panel in placements
                    if panel.panel_type == "fixed_shelf"
                )
                self.assertEqual(shelf.pos_y, internal_y_start)
                self.assertEqual(shelf.pos_y + shelf.size_y, carcass_y_end)

                doors = [
                    panel for panel in placements if panel.panel_type == "door"
                ]
                self.assertTrue(doors)
                self.assertTrue(
                    all(
                        door.pos_y + door.size_y == spec.depth
                        for door in doors
                    )
                )

                back = panels["back_panel"]
                if back_mount == "cover":
                    self.assertEqual(
                        (back.pos_y, back.size_y),
                        (0.0, spec.back_thickness),
                    )
                    self.assertEqual(
                        back.pos_y + back.size_y,
                        panels["left_side_panel"].pos_y,
                    )
                    self.assertEqual(structure.toe_kick_rear_y, 39.0)
                    self.assertEqual(structure.toe_kick_front_y, 579.0)
                else:
                    self.assertEqual(back.pos_y, spec.back_offset)

    def test_all_modes_pass_through_manufacturing_validation(self) -> None:
        orchestrator = FurnitureOrchestrator(workspace_root=WORKSPACE_ROOT)
        expected_groove_ids = {
            "left_side_back_groove",
            "right_side_back_groove",
            "top_back_groove",
            "bottom_back_groove",
        }

        for back_mount in ("groove", "insert", "cover"):
            with self.subTest(back_mount=back_mount):
                spec = self._spec(back_mount)
                result = orchestrator.execute_spec(
                    f"{back_mount}-back",
                    cabinet_data(
                        spec.furniture_type,
                        width=spec.width,
                        depth=spec.depth,
                        height=spec.height,
                        back_mount=spec.back_mount,
                        back_thickness=spec.back_thickness,
                        shelves=[{"shelf_type": s.shelf_type, "gap_below_mm": s.gap_below_mm} for s in spec.shelves],
                        top_gap_mm=spec.top_gap_mm,
                        n_doors=spec.n_doors,
                    ),
                    through_stage=WorkflowStage.MANUFACTURING_PLANNED,
                )

                self.assertEqual(
                    result.revision.workflow.current,
                    WorkflowStage.MANUFACTURING_PLANNED,
                )
                manufacturing_reports = [
                    report
                    for report in result.revision.validations
                    if report.stage == WorkflowStage.MANUFACTURING_PLANNED.value
                ]
                self.assertTrue(manufacturing_reports)
                self.assertTrue(
                    all(report.passed for report in manufacturing_reports)
                )

                operations = result.revision.stage_outputs[
                    WorkflowStage.MANUFACTURING_PLANNED.value
                ]["operations"]
                operation_ids = {operation["id"] for operation in operations}
                if back_mount == "groove":
                    self.assertEqual(operation_ids, expected_groove_ids)
                else:
                    self.assertEqual(operation_ids, set())

    def test_all_modes_emit_mount_specific_manufacturing_semantics(self) -> None:
        # insert 有三合一五金与成对孔；cover/groove 的螺钉为组装现场工艺，无五金无孔
        insert_contract = (
            "三合一连接件（内嵌背板）",
            ("back_insert_cam", "back_insert_rod", "back_insert_nut"),
        )
        screw_names = {"沉头木螺钉（外盖背板）", "沉头木螺钉（背拉条）"}
        screw_hole_types = {
            "cover_back_clearance",
            "cover_back_pilot",
            "back_rail_side_clearance",
            "back_rail_pilot",
        }

        for back_mount in ("insert", "cover", "groove"):
            with self.subTest(back_mount=back_mount):
                spec = self._spec(back_mount)
                layout = plan_layout(spec)
                placements = plan_panels(spec, layout)
                bom = plan_manufacturing(spec, placements)
                panels = {panel.label: panel for panel in bom.panels}

                self.assertEqual(
                    panels["back_panel"].edge_banding,
                    {}
                    if back_mount == "groove"
                    else {"四边": "ABS 1.0mm同色"},
                )
                self.assertEqual(
                    {panel.back_mount for panel in bom.panels},
                    {back_mount},
                )
                for rail in (
                    panel
                    for panel in bom.panels
                    if panel.panel_type == "back_rail"
                ):
                    self.assertEqual(
                        rail.edge_banding,
                        {"四边": "ABS 1.0mm同色"},
                    )

                drilled = emit_drilled_holes(bom)
                holes = [
                    hole
                    for panel in drilled["panels"]
                    for hole in panel["holes"]
                ]

                if back_mount == "insert":
                    hardware_name, required_holes = insert_contract
                    hardware = next(
                        item
                        for item in bom.hardware
                        if item.name == hardware_name
                    )
                    self.assertGreater(hardware.quantity, 0)
                    self.assertIn("投产前确认", hardware.note)
                    counts = {
                        hole_type: sum(
                            hole["hole_type"] == hole_type for hole in holes
                        )
                        for hole_type in required_holes
                    }
                    self.assertEqual(set(counts.values()), {hardware.quantity})
                else:
                    # cover/groove 的螺钉为组装现场工艺，不出五金、不出孔
                    self.assertFalse(
                        any(item.name in screw_names for item in bom.hardware)
                    )
                    self.assertFalse(
                        any(
                            hole["hole_type"] in screw_hole_types
                            for hole in holes
                        )
                    )

                for panel in drilled["panels"]:
                    box = panel["box"]
                    for hole in panel["holes"]:
                        for local_key, size_key in (
                            ("local_x", "x"),
                            ("local_y", "y"),
                            ("local_z", "z"),
                        ):
                            self.assertGreaterEqual(
                                hole[local_key],
                                -1e-6,
                            )
                            self.assertLessEqual(
                                hole[local_key],
                                box[size_key] + 1e-6,
                            )

    def test_mount_specific_validation_ignores_unused_groove_fields(self) -> None:
        for back_mount in ("insert", "cover"):
            with self.subTest(back_mount=back_mount):
                spec = self._spec(back_mount)
                spec.groove_depth = 100
                spec.groove_clearance = -10
                if back_mount == "cover":
                    spec.back_offset = -100
                plan_layout(spec)

        with self.assertRaisesRegex(ValueError, "back_mount"):
            invalid = self._spec("unsupported")
            plan_panels(invalid, plan_layout(invalid))

        cover_spec = furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=25,
            height=1000,
            back_mount="cover",
        )
        cover_layout = plan_layout(cover_spec)
        cover_report = validate_structure(
            cover_layout,
            cover_spec,
            CabinetStructure.from_spec(cover_spec),
        )
        self.assertFalse(cover_report.passed)
        self.assertIn(
            "NON_POSITIVE_INTERNAL_CLEARANCE",
            {issue.code for issue in cover_report.issues},
        )

        insert_spec = furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            back_mount="insert",
            back_thickness=18,
            back_offset=570,
        )
        insert_layout = plan_layout(insert_spec)
        insert_report = validate_structure(
            insert_layout,
            insert_spec,
            CabinetStructure.from_spec(insert_spec),
        )
        self.assertFalse(insert_report.passed)
        self.assertIn(
            "NON_POSITIVE_INTERNAL_CLEARANCE",
            {issue.code for issue in insert_report.issues},
        )

        rail_spec = furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            back_mount="groove",
            back_rail_height=1000,
        )
        rail_layout = plan_layout(rail_spec)
        rail_report = validate_panels(
            rail_spec,
            rail_layout,
            plan_panels(rail_spec, rail_layout),
        )
        self.assertFalse(rail_report.passed)
        self.assertIn(
            "NON_POSITIVE_BACK_RAIL_SPACING",
            {issue.code for issue in rail_report.issues},
        )

    def test_panel_validation_rejects_cover_overlap(self) -> None:
        spec = self._spec("cover")
        layout = plan_layout(spec)
        placements = plan_panels(spec, layout)

        self.assertTrue(validate_panels(spec, layout, placements).passed)

        overlapping = [
            replace(panel, pos_y=0.0)
            if panel.id == "left_side_panel"
            else panel
            for panel in placements
        ]
        report = validate_panels(spec, layout, overlapping)
        issue_codes = {issue.code for issue in report.issues}

        self.assertFalse(report.passed)
        self.assertIn("CARCASS_DEPTH_MISMATCH", issue_codes)
        self.assertIn("COVER_BACK_OVERLAP", issue_codes)


if __name__ == "__main__":
    unittest.main()
````

## File: domain/skills/furniture-layout/references/spatial-layout-rules.md
````markdown
# 空间布局规则

回答“家具在房间的哪个位置、是否越界或碰撞，以及摆放预览长什么样？”；这是独立按需能力，不位于家具生成串联阶段内，也不生成结构净空、板件或 CAD。

## 坐标约定

- 默认毫米，柜体局部 `W×D×H` 对应 X 左→右、Y 后→前、Z 向上。
- 柜体局部原点 `(0,0,0)` 为成品外包络左后下落地角；用范围/偏移描述区域，不转成 CAD 基元中心。
- 房间原点是平面图西北角的地面点；房间 X 向东、Y 向南、Z 向上。
- `room_placement.placement` 将柜体局部原点转换到房间坐标；`rotation_z_deg` 从房间 X 轴逆时针计算。

## 房间定位输入

成功的独立布局请求始终包含房间定位和 SVG 预览。用户未指定时使用以下可见默认假设：

- 房间：`4200×3600×2800 mm` 的矩形“默认卧室（系统假设）”，门窗和障碍物为空；
- 位置：沿北墙居中，落地柜标高为 `0`；
- 吊柜：沿北墙居中；若已确认意图提供了挂装方式，则按方式定位——`flush_ceiling` 贴顶（`origin_z_mm = 房高 − 柜高`），`free_height` 用挂高 `mounting_height_mm` 作 `origin_z_mm`；否则默认保留 `450 mm` 顶部净距；空间不足时降至不低于地面。

只提供 `layout.room` 或 `layout.placement` 时，仅补齐缺失项。`layout_context.room_source` 与 `layout_context.placement_source` 必须说明数据来自用户还是系统默认；默认场景不是现场实测数据，用户可在确认前修改。

`room`：

- `id/name`：房间标识与展示名。
- `width_mm/depth_mm/height_mm`：当前支持矩形房间。
- `openings[]`：门窗所在 `wall`、沿墙 `offset_mm`、宽高和窗台高。
- `obstacles[]`：柱、管井等轴对齐长方体的位置与尺寸。

沿墙偏移按房间边界顺时针定义：

- `north`：西 → 东；
- `east`：北 → 南；
- `south`：东 → 西；
- `west`：南 → 北。

`placement.mode=wall` 使用 `host_wall + offset_mm + origin_z_mm`，运行时自动推导原点和朝向，使柜体背面贴墙、正面朝向室内。`placement.mode=free` 使用 `origin_x_mm/origin_y_mm/origin_z_mm + rotation_z_deg`。

布局必须拒绝以下情况：柜体越出房间、超过层高、与障碍物发生正体积相交，或沿宿主墙遮挡垂直范围相交的门窗。边界接触不视为碰撞。

## 当前可执行决策

- 成品外包络可继承已确认 `DesignIntent`，也可来自独立请求中明确给出的同等字段；本能力不得改变尺寸口径。
- 房间与摆放位置属于布局输入；默认值必须在 `layout_context` 明示来源。

层板、门、抽屉、开放格、隔板分区、挂衣/设备/装饰区、滑门、盖门/嵌门、固定/可调层板差异都属于家具本体规划，不属于房间摆放。已支持的数量字段进入 `panels_planned`，不得要求用户先运行本能力。房间安装障碍只按本文件的长方体包络校验，不推断基层、管线或现场可施工性。

## 运行时输出

`CabinetLayout` 以 `furniture_type/width/depth/height` 作为摆放计算依据。当前序列化结构为兼容旧调用仍可含 `door_count`，但该字段不参与房间定位，也不向家具生成主流程提供数据。

完整 `layout_planned` 输出保持 `layout` 向后兼容，并增加：

- `layout_context`：房间和摆放位置的来源，明确标记系统默认假设；
- `room_placement.room`：标准化房间、门窗和障碍物；
- `room_placement.placement`：已解析的房间原点、标高、旋转及宿主墙；
- `room_placement.furniture_footprint`：房间平面坐标中的四角占地；
- `room_placement.clearances_mm`：西、东、南、北、地面和顶面的净距；
- `preview`：`image/svg+xml` 内联透视三维包络预览、视图类型、尺寸和替代文本。投影必须表现近大远小和空间边线汇聚；房间为透明六面体，家具为不透明成品包络，门窗和障碍物仍按房间坐标展示。
- `viewer`：`text/html` 自包含互动三维包络 Viewer，不依赖外网；支持鼠标/触摸拖拽环绕、滚轮缩放、透视/正视/左视/右视/俯视和重置。Viewer 必须由当前房间、家具包络、门窗及障碍物实时重建。

静态预览与 Viewer 必须由当前房间、柜体包络和定位实时重建；修改定位后不得沿用旧占地、旧 SVG 或旧 Viewer。

功能数量、板厚、背板模式、柜体前后范围、内部 `X/Y/Z` 净空和踢脚区域全部由板件阶段基于已确认意图首次计算；布局预览只表达成品外包络，不暗示内部结构已经确定。

## 类别指导

- 地柜：本能力只表达其成品外包络；踢脚和功能数量留给板件阶段。
- 吊柜：已确认意图的挂装方式决定 `origin_z_mm`（贴顶或自由挂高）；独立请求可显式提供 `origin_z_mm`，若为 0 则警告；挂墙结构和安装策略不进入 `CabinetLayout`。

## 边界

- 不定义板件记录、封边/钻孔/五金、特征树、CAD/STEP、命令或产物。
- 房间定位只影响场景展示和布局校验；主流程板件直接使用已确认意图与板件输入，不得把房间世界坐标混入板件尺寸。
- 独立布局结果不写入主流程 `STAGE_SEQUENCE`、`approved_stages` 或 CAD 交付清单，也不使任何家具生成阶段失效。
````

## File: domain/skills/furniture-layout/scripts/furniture_layout/layout_pipeline.py
````python
"""Layout-stage planning for supported cabinet families."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from .layout_preview import render_layout_preview
from .layout_planning import CabinetLayout
from .layout_spec import LayoutSpec
from .layout_viewer import render_layout_viewer
from .room_planning import RoomModel, plan_room_placement


DEFAULT_BEDROOM_WIDTH_MM = 4200.0
DEFAULT_BEDROOM_DEPTH_MM = 3600.0
DEFAULT_BEDROOM_HEIGHT_MM = 2800.0
DEFAULT_WALL_CABINET_CEILING_CLEARANCE_MM = 450.0


def plan_layout(spec: LayoutSpec | Any) -> CabinetLayout:
    """Normalize the envelope for an independent room-layout request."""
    if not isinstance(spec, LayoutSpec):
        spec = LayoutSpec(
            furniture_type=str(spec.furniture_type),
            width=float(spec.width),
            depth=float(spec.depth),
            height=float(spec.height),
            door_count=int(getattr(spec, "door_count", spec.n_doors)),
        )
    return CabinetLayout.from_spec(spec)


def plan_layout_stage(
    spec: LayoutSpec,
    *,
    room: Mapping[str, Any] | None = None,
    placement: Mapping[str, Any] | None = None,
    furniture_label: str = "",
) -> dict[str, Any]:
    """Build one complete serializable independent-layout output.

    Missing room context is filled with an explicit default bedroom and a
    centered north-wall placement so every successful request has a visible
    3D envelope preview. The output records which values were assumed.  No
    board thickness, back construction, or final internal clearance is
    introduced by this independent capability.
    """
    layout = plan_layout(spec)
    output: dict[str, Any] = {"layout": asdict(layout)}
    if room is not None and not isinstance(room, Mapping):
        raise ValueError("layout.room must be an object")
    if placement is not None and not isinstance(placement, Mapping):
        raise ValueError("layout.placement must be an object")

    room_source = "provided"
    placement_source = "provided"
    resolved_room = room
    if resolved_room is None:
        resolved_room = _default_bedroom()
        room_source = "default_bedroom"
    resolved_placement = placement
    if resolved_placement is None:
        resolved_placement = _default_placement(
            layout,
            resolved_room,
            mount_mode=spec.mount_mode,
            mounting_height_mm=spec.mounting_height_mm,
        )
        placement_source = "default_north_wall_centered"

    room_placement = plan_room_placement(
        layout,
        resolved_room,
        resolved_placement,
        furniture_label=furniture_label or spec.furniture_type,
    )
    output["layout_context"] = {
        "room_source": room_source,
        "placement_source": placement_source,
    }
    output["room_placement"] = room_placement.to_dict()
    output["preview"] = render_layout_preview(room_placement, layout)
    output["viewer"] = render_layout_viewer(room_placement, layout)
    return output


def _default_bedroom() -> dict[str, Any]:
    return {
        "id": "default_bedroom",
        "name": "默认卧室（系统假设）",
        "width_mm": DEFAULT_BEDROOM_WIDTH_MM,
        "depth_mm": DEFAULT_BEDROOM_DEPTH_MM,
        "height_mm": DEFAULT_BEDROOM_HEIGHT_MM,
        "openings": [],
        "obstacles": [],
    }


def _default_placement(
    layout: CabinetLayout,
    room: Mapping[str, Any],
    *,
    mount_mode: str | None = None,
    mounting_height_mm: float | None = None,
) -> dict[str, Any]:
    room_model = RoomModel.from_dict(room)
    origin_z_mm = 0.0
    if layout.furniture_type == "wall_cabinet":
        if mount_mode == "flush_ceiling":
            origin_z_mm = max(0.0, room_model.height_mm - layout.height)
        elif mount_mode == "free_height" and mounting_height_mm is not None:
            origin_z_mm = float(mounting_height_mm)
        else:
            origin_z_mm = max(
                0.0,
                room_model.height_mm
                - layout.height
                - DEFAULT_WALL_CABINET_CEILING_CLEARANCE_MM,
            )
    return {
        "mode": "wall",
        "host_wall": "north",
        "offset_mm": max((room_model.width_mm - layout.width) / 2.0, 0.0),
        "origin_z_mm": origin_z_mm,
    }
````

## File: domain/skills/furniture-layout/scripts/furniture_layout/layout_spec.py
````python
"""Envelope inputs for the independent room-placement capability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from furniture_design_intent.design_intent import DesignIntent, SUPPORTED_TYPES


LAYOUT_PRESETS: dict[str, dict[str, int]] = {
    "floor_cabinet": {"door_count": 2},
    "wall_cabinet": {"door_count": 2},
}


@dataclass(frozen=True)
class LayoutSpec:
    """Envelope plus legacy count fields; no construction inputs."""

    furniture_type: str
    width: float
    depth: float
    height: float
    door_count: int
    mount_mode: str | None = None
    mounting_height_mm: float | None = None

    @classmethod
    def from_intent(
        cls,
        intent: DesignIntent,
        options: Mapping[str, Any] | None = None,
    ) -> "LayoutSpec":
        values = dict(options or {})
        unknown = sorted(set(values) - {"n_doors", "door_count"})
        if unknown:
            raise ValueError(
                "independent layout does not support: " + ", ".join(unknown)
            )
        if intent.furniture_type not in SUPPORTED_TYPES:
            raise ValueError(f"unsupported furniture type: {intent.furniture_type}")
        dimensions = (
            intent.overall_size.width_mm,
            intent.overall_size.depth_mm,
            intent.overall_size.height_mm,
        )
        if any(value is None for value in dimensions):
            raise ValueError("layout requires a confirmed finished envelope")
        preset = LAYOUT_PRESETS[intent.furniture_type]
        door_count = _count(
            values.get("door_count", values.get("n_doors", preset["door_count"])),
            "door_count",
        )
        return cls(
            furniture_type=intent.furniture_type,
            width=float(dimensions[0]),
            depth=float(dimensions[1]),
            height=float(dimensions[2]),
            door_count=door_count,
            mount_mode=intent.mount_mode,
            mounting_height_mm=intent.mounting_height_mm,
        )


def _count(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value
````

## File: domain/skills/furniture-layout/SKILL.md
````markdown
---
name: furniture-layout
description: 独立的房间摆放与预览技能。当用户明确要求"放在房间哪个位置""靠墙还是居中""生成摆放图""检查门窗或障碍物碰撞"时触发。它不属于家具生成串联阶段，也不是板件、制造或 CAD 的前置条件。
---

# 家具布局规划

类型：独立按需步骤（兼容结果名：`layout_planned`）

## 工作流

1. 仅在用户明确要求房间摆放或摆放预览时运行；可读取已确认的家具类别与成品外包络（吊柜含挂装方式与挂高），也可接受独立请求中明确给出的同等输入。
2. 按 [空间布局规则](references/spatial-layout-rules.md) 生成用于摆放计算的 `CabinetLayout`，保留家具外包络；兼容字段中的 `door_count` 不参与房间定位，也不向主流程提供板件输入。
3. 解析房间、门窗、障碍物及沿墙/自由摆放位置；缺失时使用可见标注的默认卧室与沿北墙居中位置。
4. 生成房间坐标、家具占地、六向净距、静态 SVG 和自包含互动 Viewer；校验越界、门窗遮挡和障碍物碰撞。
5. 返回独立布局结果并暂停。客户可修改房间定位；结果不写入主流程 `STAGE_SEQUENCE`、`approved_stages` 或 CAD 交付清单。

## 边界

- 门数、层板数、抽屉数、隔板分区、开放格、滑门、挂衣区或设备区属于家具本体规划；其中已支持的 `n_doors/drawer_count` 进入 `panels_planned`，不得要求先生成房间摆放图。
- 局部原点为成品外包络左后下落地角；房间坐标通过 `room_placement.placement` 关联。
- 修改独立布局时重新运行本技能；不调用主流程 `revise_stage_output()`，也不使板件、制造、特征树或 CAD 失效。
- 精确柜体结构、功能数量、最终内部净空、背板和踢脚归 `panels_planned`；不输出制造或 CAD 信息。
````

## File: domain/skills/furniture-manufacturing/references/manufacturing-rules.md
````markdown
# 制造规则

回答“应如何制造？”；位于板件后，只负责材料、工艺和 BOM 策略。

## 需确定的策略

- 材料：类别、等级、厚度、纹理、可见面、饰面。
- 封边：边、厚度及余量状态；连接：螺钉、木榫、偏心件、槽/企口、胶合等。
- 五金：铰链、滑轨、拉手、层板托、固定、防倾倒及荷载。
- 公差/净空：门缝、安装/设备缝隙、地墙不平和安全余量。
- BOM：整份方案记录 `readiness`；`preliminary` 为软件暂定，`accepted` 表示用户/设计方接受方案但仍需工艺核对，`factory_ready` 只在工厂明确确认后使用。

## 三合一打孔规则

- 竖板（侧板/隔板）预埋螺母在高度方向按系统 32 排钻分布（首/末孔 64mm，间距≤512mm），深度方向前后双排（`[first_hole_mm, depth - last_hole_mm]`）。
- 横板（顶板/底板/固定层板）连接杆在深度方向前后双排；偏心轮深度方向与连接杆同排，沿连接杆方向（x）距端面 `cam.hole.edge_offset_mm`（33.5mm）——即偏心轮圆心到连接杆端面（接触端面）的距离。
- 所有孔位由 `Connector.generate_holes()` 生成 `HoleSpec`，标记 `is_face_hole=True`（板面钻孔）或 `False`（板边钻孔）。

## 铰链打孔规则

- 铰链数量按门板高度分 5 档（≤480→2, ≤980→2, ≤1500→3, ≤2100→4, ≤2750→5）。
- 铰链杯孔 Y1 = `hole.edge_offset_mm + hole.diameter_mm/2`，为杯孔中心到门边的距离（HJ-100：5+17.5=22.5mm）。
- 杯孔从门板内侧钻入，`direction` = 钻入方向（`panel.inner_face` 的反向，往板内）。
- 杯孔圆周必须完全位于门板面内，深度不得超过门厚；左/右铰链边须与 `door_hinge_side` 一致，孔数须与铰链 BOM 数量一致。

## 背板槽加工契约

- 入槽背板为左右侧板、顶/底板生成 4 条独立 `cut_box`；槽深 `groove_depth`，槽宽 `back_thickness + groove_clearance`。
- 每条含稳定 ID、目标、全局最小角点、正数尺寸和说明，且完全位于目标包络；本阶段不调用 CAD API。
- 制造校验是槽包络的主责任点；特征树随后只对同一操作做防御性复核。

## 背板安装制造契约

| 模式 | 背板封边 | 连接与孔位 | 五金 BOM |
|------|----------|------------|----------|
| `groove` | 不封边 | 四边槽（柜体加工）；背拉条螺钉连接为组装现场工艺，不生成孔位 | 无 |
| `insert` | 四边同色 | 背板四边布置三合一；每个连接点必须同时有背板偏心轮孔、连接杆通道和柜体预埋螺母孔 | 内嵌背板专用三合一套件 |
| `cover` | 四边同色 | 螺钉连接为组装现场工艺，不生成孔位 | 无 |

- 板件记录保留有效 `back_mount`，不得由厚度/备注反推。
- 成对孔由 `Connector.generate_holes_for_panels()` 基于完整装配生成，不伪装成单板规则；背拉条四边封边。
- cover 外盖螺钉与 groove 背拉条螺钉属于组装现场工艺，不生成孔位与五金；因此自动规划始终从 `readiness=preliminary` 开始。
- 五金数量等于主连接孔数量；同一连接的配合孔数量一致。

## 六面钻 XML 导出

机床加工文件（`KDTPanelFormat`）导出契约见 [six-side-drill-export.md](six-side-drill-export.md)，仅在用户要求出六面钻/机床加工文件时读取。

## 边界

- 不创建/修改板件、布局、特征树或 CAD/STEP，不定义命令和产物路径。
````

## File: domain/skills/furniture-manufacturing/scripts/furniture_manufacturing/connectors/back_mount.py
````python
"""背板安装连接件 — 内嵌背板四边三合一。

外盖(cover)与背拉条(groove)的螺钉连接属于组装现场工艺，
不在柜体加工范围内，不生成孔位与五金。
"""

from __future__ import annotations

from math import ceil
from typing import Any, Dict, List, Mapping

from furniture_manufacturing.connectors.base import Connector, HoleSpec
from furniture_manufacturing.manufacturing_models import (
    HardwareRecord,
    MachiningOperation,
    PanelRecord,
)


class BackMountConnector(Connector):
    """背板安装连接件。

    仅 insert 模式生成四边三合一（背板偏心轮孔 + 连接杆通道 + 柜体预埋螺母孔）。
    cover/groove 的螺钉孔与五金属于组装现场工艺，不加工、不出 BOM。
    """

    name = "背板安装连接件"
    hole_type_for_json = "back_mount"
    catalog_entry = "three_in_one"
    rules_section = "back_mount_drilling"
    hole_legend = {
        "back_insert_cam": {"color": "#8E44AD", "label": "内嵌背板偏心轮孔", "glb_group": "内嵌背板偏心轮孔"},
        "back_insert_rod": {"color": "#9B59B6", "label": "内嵌背板连接杆孔", "glb_group": "内嵌背板连接杆孔"},
        "back_insert_nut": {"color": "#6C3483", "label": "内嵌背板预埋螺母孔", "glb_group": "内嵌背板预埋螺母孔"},
    }

    def match(self, panels: List[PanelRecord]) -> Dict[str, Any]:
        return {
            "mode": self._mode(panels),
            "back": next(
                (panel for panel in panels if panel.panel_type == "back"),
                None,
            ),
            "rails": [
                panel for panel in panels if panel.panel_type == "back_rail"
            ],
            "panels": panels,
        }

    def generate_holes(self, panel: PanelRecord) -> List[HoleSpec]:
        # Back mounting requires the mating panel geometry. The bulk method
        # below is the supported entry point used by emit_drilled_holes().
        return []

    def generate_holes_for_panels(
        self,
        panels: List[PanelRecord],
    ) -> List[HoleSpec]:
        mode = self._mode(panels)
        if mode == "insert":
            return self._insert_holes(panels)
        return []

    def boms(
        self,
        panels: List[PanelRecord],
        *,
        options: Mapping[str, Any] | None = None,
    ) -> List[HardwareRecord]:
        mode = self._mode(panels)
        if mode != "insert":
            return []
        holes = self.generate_holes_for_panels(panels)
        quantity = self._hole_count(holes, "back_insert_cam")
        if quantity <= 0:
            return []
        spec = self.catalog.get("three_in_one", {}).get("standard", {})
        opts = (options or {}).get(self.catalog_entry, {})
        opts = dict(opts) if isinstance(opts, Mapping) else {}
        brand = self.resolve_brand(spec.get("brands", []), opts.get("brand"))
        return [
            HardwareRecord(
                name="三合一连接件（内嵌背板）",
                spec="偏心轮+连接杆+预埋螺母（实物规格待确认）",
                quantity=quantity,
                unit="套",
                brand=brand.get("name", "默认"),
                model=brand.get("model", "SJY-01"),
                note="按四边连接点估算，投产前确认连接点数量",
                drilling=[
                    {"hole_type": "back_insert_cam", "quantity": quantity},
                    {"hole_type": "back_insert_rod", "quantity": quantity},
                    {
                        "hole_type": "back_insert_nut",
                        "quantity": quantity,
                    },
                ],
            )
        ]

    def validate(
        self,
        report: Any,
        panels: List[PanelRecord],
        hardware: List[HardwareRecord],
        drilled: Dict[str, Any],
    ) -> None:
        """内嵌背板（insert）专属校验：三件套孔（轮/杆/螺母）数量一致且匹配 BOM。"""
        mode = self._mode(panels)
        hole_types = [
            hole["hole_type"]
            for panel in drilled["panels"]
            for hole in panel["holes"]
        ]
        hardware_by_name = {item.name: item for item in hardware}
        contract = {
            "insert": (
                "三合一连接件（内嵌背板）",
                ("back_insert_cam", "back_insert_rod", "back_insert_nut"),
            ),
        }.get(mode)
        if contract is None:
            return
        hardware_name, required_hole_types = contract
        hardware_item = hardware_by_name.get(hardware_name)
        counts = {
            hole_type: hole_types.count(hole_type)
            for hole_type in required_hole_types
        }
        if hardware_item is None or hardware_item.quantity <= 0:
            report.add_error(
                "MISSING_BACK_MOUNT_HARDWARE",
                f"{mode} back strategy is missing {hardware_name}",
                "hardware",
            )
        if any(count <= 0 for count in counts.values()):
            report.add_error(
                "MISSING_BACK_MOUNT_HOLES",
                f"{mode} back strategy is missing matched hole records",
                "drilled_holes",
            )
        elif len(set(counts.values())) != 1:
            report.add_error(
                "BACK_MOUNT_HOLE_COUNT_MISMATCH",
                f"{mode} mating hole counts do not match",
                "drilled_holes",
            )
        elif (
            hardware_item is not None
            and hardware_item.quantity != next(iter(counts.values()))
        ):
            report.add_error(
                "BACK_MOUNT_HARDWARE_COUNT_MISMATCH",
                f"{hardware_name} quantity does not match its hole pattern",
                "hardware",
            )

    def machining_operations(
        self,
        panel: PanelRecord,
    ) -> List[MachiningOperation]:
        # Round holes are emitted through HoleSpec and the drilled-holes
        # artifact; BOMReport.operations remains the box-cut contract.
        return []

    def _insert_holes(self, panels: List[PanelRecord]) -> List[HoleSpec]:
        """内嵌背板：四边三合一成对孔。

        连接点在背板局部坐标定义（背板为装配锚点，局部为唯一真源），
        配合板按"同一世界点 − 板件原点"折算到各自局部坐标，
        世界坐标统一由各板的 to_global 派生。
        """
        by_label = {panel.label: panel for panel in panels}
        back = by_label.get("back_panel")
        if back is None:
            return []
        targets = {
            "left": by_label.get("left_side_panel"),
            "right": by_label.get("right_side_panel"),
            "top": by_label.get("top_panel"),
            "bottom": by_label.get("bottom_panel"),
        }
        rules = self.rules.get("back_mount_drilling", {}).get("insert", {})
        first = float(rules.get("first_hole_mm", 64))
        max_spacing = float(rules.get("max_spacing_mm", 400))
        three_in_one = self.catalog.get("three_in_one", {}).get("standard", {})
        cam_spec = three_in_one.get("cam", {})
        rod_spec = three_in_one.get("rod", {})
        nut_spec = three_in_one.get("nut", {})
        cam_diameter = float(cam_spec.get("hole", {}).get("diameter_mm", 12))
        cam_depth = float(cam_spec.get("hole", {}).get("depth_mm", 13.5))
        cam_offset = float(cam_spec.get("hole", {}).get("edge_offset_mm", 33.5))
        rod_diameter = float(rod_spec.get("hole", {}).get("diameter_mm", 8))
        rod_depth = float(rod_spec.get("hole", {}).get("depth_mm", 33))
        nut_diameter = float(nut_spec.get("hole", {}).get("diameter_mm", 10))
        nut_depth = float(nut_spec.get("hole", {}).get("depth_mm", 11))
        y_center_local = back.size_y / 2
        y_face_local = back.size_y
        result: List[HoleSpec] = []

        def add_connection(
            target: PanelRecord | None,
            cam_x_local: float,
            cam_z_local: float,
            rod_x_local: float,
            rod_z_local: float,
            rod_direction: str,
            target_direction: str,
            edge_name: str,
        ) -> None:
            if target is None:
                return
            result.append(
                self._hole(
                    back,
                    "back_insert_cam",
                    cam_x_local,
                    y_face_local,
                    cam_z_local,
                    cam_diameter,
                    cam_depth,
                    "-y",
                    f"内嵌背板{edge_name}偏心轮孔",
                    is_face_hole=True,
                )
            )
            result.append(
                self._hole(
                    back,
                    "back_insert_rod",
                    rod_x_local,
                    y_center_local,
                    rod_z_local,
                    rod_diameter,
                    rod_depth,
                    rod_direction,
                    f"内嵌背板{edge_name}连接杆通道",
                    is_face_hole=False,
                )
            )
            # 配合板预埋螺母孔必须与背板连接杆落在同一世界点：
            # 以背板局部点为中间量折算到目标板局部坐标，再 to_global。
            point = (
                back.pos_x + rod_x_local,
                back.pos_y + y_center_local,
                back.pos_z + rod_z_local,
            )
            result.append(
                self._hole(
                    target,
                    "back_insert_nut",
                    point[0] - target.pos_x,
                    point[1] - target.pos_y,
                    point[2] - target.pos_z,
                    nut_diameter,
                    nut_depth,
                    target_direction,
                    f"{target.name}与内嵌背板的预埋螺母孔",
                    is_face_hole=True,
                )
            )

        for z_local in self._spaced_positions(
            back.size_z,
            first,
            max_spacing,
        ):
            add_connection(
                targets["left"],
                cam_offset,
                z_local,
                0.0,
                z_local,
                "+x",
                "-x",
                "左边",
            )
            add_connection(
                targets["right"],
                back.size_x - cam_offset,
                z_local,
                back.size_x,
                z_local,
                "-x",
                "+x",
                "右边",
            )
        for x_local in self._spaced_positions(
            back.size_x,
            first,
            max_spacing,
        ):
            add_connection(
                targets["bottom"],
                x_local,
                cam_offset,
                x_local,
                0.0,
                "+z",
                "-z",
                "下边",
            )
            add_connection(
                targets["top"],
                x_local,
                back.size_z - cam_offset,
                x_local,
                back.size_z,
                "-z",
                "+z",
                "上边",
            )
        return result

    @staticmethod
    def _mode(panels: List[PanelRecord]) -> str:
        """从面板列表中提取统一的背板安装模式。"""
        modes = {panel.back_mount for panel in panels if panel.back_mount}
        return next(iter(modes)) if len(modes) == 1 else ""

    @staticmethod
    def _hole_count(holes: List[HoleSpec], hole_type: str) -> int:
        """统计某类孔的数量。"""
        return sum(hole.hole_type == hole_type for hole in holes)

    @staticmethod
    def _spaced_positions(
        length: float,
        edge_offset: float,
        max_spacing: float,
    ) -> List[float]:
        """沿指定长度均匀分布连接点，首末距边 edge_offset。"""
        if length <= 0:
            return []
        if length <= 2 * edge_offset:
            return [length / 2]
        usable = length - 2 * edge_offset
        intervals = max(1, ceil(usable / max(max_spacing, 1)))
        return [
            edge_offset + usable * index / intervals
            for index in range(intervals + 1)
        ]

    @staticmethod
    def _hole(
        panel: PanelRecord,
        hole_type: str,
        x_local: float,
        y_local: float,
        z_local: float,
        diameter: float,
        depth: float,
        direction: str,
        note: str,
        is_face_hole: bool = True,
    ) -> HoleSpec:
        """在指定板上生成孔位：局部坐标定义（唯一真源），世界由 to_global 派生。"""
        x_global, y_global, z_global = panel.to_global(
            x_local, y_local, z_local
        )
        return HoleSpec(
            hole_type=hole_type,
            panel_label=panel.label,
            x_global=x_global,
            y_global=y_global,
            z_global=z_global,
            x_local=x_local,
            y_local=y_local,
            z_local=z_local,
            diameter=diameter,
            depth=depth,
            direction=direction,
            is_face_hole=is_face_hole,
            note=note,
        )
````

## File: domain/skills/furniture-manufacturing/scripts/furniture_manufacturing/connectors/base.py
````python
"""五金连接件抽象基类。

提供所有连接件的公共接口：孔位描述、规则加载、BOM 生成。
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping
import yaml
from furniture_manufacturing.manufacturing_models import HardwareRecord, MachiningOperation, PanelRecord


def _opposite(axis: str) -> str:
    """反转带符号轴方向："+x"→"-x"，"-y"→"+y"。"""
    if not axis or axis[0] not in ("+", "-"):
        return "-x"
    return f"{'+' if axis[0] == '-' else '-'}{axis[1]}"


@dataclass
class HoleSpec:
    hole_type: str = ""
    panel_label: str = ""
    x_global: float = 0.0
    y_global: float = 0.0
    z_global: float = 0.0
    x_local: float = 0.0
    y_local: float = 0.0
    z_local: float = 0.0
    diameter: float = 0.0
    depth: float = 0.0
    direction: str = "+y"
    is_face_hole: bool = True  # True=板面钻孔(TypeNo=1), False=板边钻孔(TypeNo=2)
    note: str = ""


class Connector:
    name: str = ""
    hole_type_for_json: str = ""
    catalog_entry: str = ""
    rules_section: str | None = None
    # hole_type → {color, label, glb_group}；Viewer/GLB 图例由各 Connector 自声明派生
    hole_legend: Dict[str, Dict[str, str]] = {}
    _catalog_cache: Dict[str, Any] | None = None
    _rules_cache: Dict[str, Any] | None = None

    @staticmethod
    def _load_catalog() -> Dict[str, Any]:
        if Connector._catalog_cache is None:
            p = Path(__file__).resolve().parent.parent / "hardware_catalog.yaml"
            with open(p, encoding="utf-8") as f:
                Connector._catalog_cache = yaml.safe_load(f) or {}
        return Connector._catalog_cache

    @staticmethod
    def _load_rules() -> Dict[str, Any]:
        if Connector._rules_cache is None:
            p = Path(__file__).resolve().parent.parent / "hardware_rules.yaml"
            with open(p, encoding="utf-8") as f:
                Connector._rules_cache = yaml.safe_load(f) or {}
        return Connector._rules_cache

    @property
    def catalog(self) -> Dict[str, Any]:
        return self._load_catalog()

    @property
    def rules(self) -> Dict[str, Any]:
        return self._load_rules()

    def match(self, panels: List[PanelRecord]) -> Dict[str, Any]:
        raise NotImplementedError

    def generate_holes(self, panel: PanelRecord) -> List[HoleSpec]:
        raise NotImplementedError

    def generate_holes_for_panels(
        self,
        panels: List[PanelRecord],
    ) -> List[HoleSpec]:
        """Generate holes with the full assembly available when needed.

        Ordinary connectors remain panel-local. Assembly-aware connectors can
        override this method to emit matched holes on both mating panels.
        """
        return [
            hole
            for panel in panels
            for hole in self.generate_holes(panel)
        ]

    def boms(
        self,
        panels: List[PanelRecord],
        *,
        options: Mapping[str, Any] | None = None,
    ) -> List[HardwareRecord]:
        raise NotImplementedError

    def validate(
        self,
        report: Any,
        panels: List[PanelRecord],
        hardware: List[HardwareRecord],
        drilled: Dict[str, Any],
    ) -> None:
        """五金专属校验；默认 no-op，由各 Connector 覆盖。"""
        return None

    @staticmethod
    def resolve_brand(
        brands: List[Dict[str, Any]] | None,
        selection: str | None = None,
    ) -> Dict[str, Any]:
        """返回唯一/已确认的品牌；歧义时抛错，不静默取第一个。

        selection 为确认的品牌名；未提供时，目录恰好一个品牌才返回，
        多个品牌则要求显式选择（失败安全，避免代码替用户拍板）。
        """
        candidates = [b for b in (brands or []) if isinstance(b, dict)]
        if not candidates:
            return {"name": "默认", "model": "N/A"}
        if selection is not None:
            for brand in candidates:
                if brand.get("name") == selection:
                    return brand
            raise ValueError(
                f"selected brand {selection!r} is not in the catalog"
            )
        if len(candidates) == 1:
            return candidates[0]
        raise ValueError(
            "multiple brands are available; an explicit selection is required"
        )

    def machining_operations(self, panel: PanelRecord) -> List[MachiningOperation]:
        raise NotImplementedError
````

## File: domain/skills/furniture-cad/scripts/tests/panel_fixtures.py
````python
from __future__ import annotations

from typing import Any

from furniture_panel_planning.panel_spec import FurnitureSpec


def _even_shelves(count: int, *, height: float, board: float, toe_kick: float):
    """均分 count 层固定层板：所有格子（含顶格、底格）净高相等。"""
    internal_height = height - toe_kick - 2 * board
    gap = (internal_height - count * board) / (count + 1)
    shelves = [{"shelf_type": "fixed", "gap_below_mm": gap} for _ in range(count)]
    return shelves, gap


def panel_parameters(furniture_type: str = "floor_cabinet", **overrides: Any) -> dict[str, Any]:
    """Return a complete proposal owned only by the test suite."""
    wall = furniture_type == "wall_cabinet"
    values = {
        "board_thickness": 18.0, "back_thickness": 9.0, "door_thickness": 18.0,
        "toe_kick_height": 0.0 if wall else 50.0, "back_offset": 18.0,
        "door_margin": 1.5, "door_hinge_gap": 2.0,
        "groove_depth": 6.0, "groove_clearance": 1.0,
        "toe_kick_reveal_front": 0.0 if wall else 1.0,
        "toe_kick_reveal_back": 0.0 if wall else 30.0,
        "toe_kick_support_count": None, "back_mount": "auto", "back_rail_height": 70.0,
        "drawer_count": 0, "drawer_side_clearance": 13.0, "drawer_layer_gap": 1.5,
        "drawer_bottom_thickness": 18.0, "drawer_back_thickness": 18.0,
        "drawer_back_clearance": 0.0, "n_doors": 2,
        "door_hinge_side": None,
        "movable_shelf_connector": "two_in_one",
        "shelves": [], "top_gap_mm": 0.0,
    }
    values.update(overrides)
    return values


def _fill_shelves(overrides: dict[str, Any], *, wall: bool, height: float) -> None:
    """把 shelf_count 兼容地转成 shelves + top_gap_mm（测试夹具便利）。"""
    if "shelves" in overrides or "top_gap_mm" in overrides:
        return
    count = overrides.pop("shelf_count", 1 if wall else 4)
    if count <= 0:
        return
    params = panel_parameters("wall_cabinet" if wall else "floor_cabinet")
    board = overrides.get("board_thickness", params["board_thickness"])
    toe_kick = overrides.get("toe_kick_height", params["toe_kick_height"])
    shelves, top_gap = _even_shelves(count, height=height, board=board, toe_kick=toe_kick)
    overrides["shelves"] = shelves
    overrides["top_gap_mm"] = top_gap


def cabinet_data(furniture_type: str = "floor_cabinet", **overrides: Any) -> dict[str, Any]:
    wall = furniture_type == "wall_cabinet"
    overrides = dict(overrides)
    height = overrides.get("height", 900 if wall else 1000)
    _fill_shelves(overrides, wall=wall, height=height)
    values = {
        "type": furniture_type, "width": 800, "depth": 350 if wall else 600,
        "height": height, **panel_parameters(furniture_type),
    }
    if wall:
        values["mount_mode"] = "free_height"
        values["mounting_height"] = 2000
    values.update(overrides)
    return values


def furniture_spec(
    *, furniture_type: str = "floor_cabinet", width: float = 800,
    depth: float = 600, height: float = 1000, **overrides: Any,
) -> FurnitureSpec:
    wall = furniture_type == "wall_cabinet"
    overrides = dict(overrides)
    _fill_shelves(overrides, wall=wall, height=height)
    return FurnitureSpec(
        furniture_type=furniture_type, width=width, depth=depth, height=height,
        **panel_parameters(furniture_type, **overrides),
    )
````

## File: domain/skills/furniture-cad/scripts/tests/test_furniture_orchestrator.py
````python
from __future__ import annotations

from copy import deepcopy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_cad.cad_bridge import CadBridge
from furniture_delivery_validation.validation import validate_delivery
from furniture_design_intent.design_intent import DesignIntent, OverallSize
from furniture_workflow.input_adapter import stage_inputs_from_spec
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_project import Project
from furniture_workflow.workflow_state import STAGE_SEQUENCE, WorkflowStage
from furniture_workflow.workflow_store import JsonProjectStore
from furniture_panel_planning.panel_pipeline import plan_panel_stage
from panel_fixtures import cabinet_data, panel_parameters


def cabinet_intent(*, furniture_type: str = "floor_cabinet") -> DesignIntent:
    return DesignIntent(
        furniture_type=furniture_type,
        overall_size=OverallSize(width_mm=800, depth_mm=600, height_mm=1000),
    )


def fake_orchestrator(temporary_root: Path) -> FurnitureOrchestrator:
    launcher_path = temporary_root / "fake_gen.py"
    launcher_path.write_text(
        "\n".join(
            [
                "import json",
                "import sys",
                "from pathlib import Path",
                "source = Path(sys.argv[1])",
                "output = Path(sys.argv[sys.argv.index('--write') + 1])",
                "output.parent.mkdir(parents=True, exist_ok=True)",
                "output.write_text('STEP', encoding='utf-8')",
                "package = source.parent / '__cadgen__' / 'models' / source.name",
                "component = package / 'components' / 'fake.glb'",
                "component.parent.mkdir(parents=True, exist_ok=True)",
                "component.write_bytes(b'GLB')",
                "(package / 'assembly.json').write_text(json.dumps({'components': {'fake': {'glb': 'components/fake.glb'}}}), encoding='utf-8')",
                "print(json.dumps({'ok': True, 'packagePath': package.as_posix()}))",
            ]
        ),
        encoding="utf-8",
    )
    bridge = CadBridge(
        workspace_root=WORKSPACE_ROOT,
        python_executable=sys.executable,
        gen_launcher=launcher_path,
    )
    return FurnitureOrchestrator(
        workspace_root=WORKSPACE_ROOT,
        cad_bridge=bridge,
    )


class FurnitureOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.orchestrator = FurnitureOrchestrator(workspace_root=WORKSPACE_ROOT)

    def test_interactive_workflow_pauses_at_every_stage(self) -> None:
        project = self.orchestrator.create_project(
            "玄关柜",
            cabinet_intent(),
            stage_inputs=stage_inputs_from_spec(
                panel_parameters()
            ),
        )
        revision = project.latest

        self.assertEqual(revision.workflow.current, WorkflowStage.DESIGN_INTENT)
        self.assertEqual(
            set(revision.stage_outputs),
            {WorkflowStage.DESIGN_INTENT.value},
        )

        self.orchestrator.confirm_intent(project)
        for expected in STAGE_SEQUENCE[1:4]:
            result = self.orchestrator.run_next(project)
            self.assertEqual(result.revision.workflow.current, expected)
            self.assertIn(expected.value, result.revision.stage_outputs)
            self.assertFalse(result.revision.is_stage_approved(expected))

            paused = self.orchestrator.run_next(project)
            self.assertEqual(paused.revision.workflow.current, expected)

            self.orchestrator.confirm_stage(project, expected)

        self.assertEqual(
            project.latest.workflow.current,
            WorkflowStage.FEATURE_TREE_PLANNED,
        )
        self.assertEqual(
            set(project.latest.stage_outputs),
            {stage.value for stage in STAGE_SEQUENCE[:4]},
        )

    def test_revising_panels_invalidates_and_regenerates_downstream(self) -> None:
        result = self.orchestrator.execute_spec(
            "可修改柜体",
            cabinet_data(shelf_count=2, n_doors=2),
            through_stage=WorkflowStage.FEATURE_TREE_PLANNED,
        )
        project = result.project
        parent = project.latest
        old_panel_output = deepcopy(
            parent.stage_outputs[WorkflowStage.PANELS_PLANNED.value]
        )
        edited_panels = plan_panel_stage(
            parent.intent,
            panel_parameters(
                shelves=[{"shelf_type": "fixed", "gap_below_mm": None}],
                top_gap_mm=300,
                n_doors=2,
            ),
        )

        revised = self.orchestrator.revise_stage_output(
            project,
            WorkflowStage.PANELS_PLANNED,
            edited_panels,
        )

        self.assertEqual(revised.parent_revision_id, parent.id)
        self.assertEqual(
            set(revised.stage_outputs),
            {
                WorkflowStage.DESIGN_INTENT.value,
                WorkflowStage.PANELS_PLANNED.value,
            },
        )
        self.assertNotIn(
            WorkflowStage.FEATURE_TREE_PLANNED.value,
            revised.stage_outputs,
        )
        self.assertEqual(
            revised.approved_stages,
            [WorkflowStage.DESIGN_INTENT.value],
        )

        self.orchestrator.confirm_stage(project, WorkflowStage.PANELS_PLANNED)
        regenerated = self.orchestrator.run_until(
            project,
            WorkflowStage.FEATURE_TREE_PLANNED,
            auto_confirm=True,
        )

        new_panel_output = regenerated.revision.stage_outputs[
            WorkflowStage.PANELS_PLANNED.value
        ]
        self.assertNotEqual(new_panel_output, old_panel_output)
        self.assertIn(
            WorkflowStage.FEATURE_TREE_PLANNED.value,
            regenerated.revision.stage_outputs,
        )

    def test_revised_single_door_hinge_side_must_match_spec(self) -> None:
        result = self.orchestrator.execute_spec(
            "右铰单门柜",
            cabinet_data(n_doors=1, door_hinge_side="right"),
            through_stage=WorkflowStage.PANELS_PLANNED,
        )
        edited = deepcopy(
            result.revision.stage_outputs[WorkflowStage.PANELS_PLANNED.value]
        )
        door = next(
            panel for panel in edited["panels"] if panel["panel_type"] == "door"
        )
        door["door_hinge_side"] = "left"

        revision = self.orchestrator.revise_stage_output(
            result.project,
            WorkflowStage.PANELS_PLANNED,
            edited,
        )
        self.orchestrator.confirm_stage(
            result.project,
            WorkflowStage.PANELS_PLANNED,
        )

        self.assertEqual(revision.workflow.current, WorkflowStage.FAILED)
        self.assertIn(
            "DOOR_HINGE_SIDE_MISMATCH",
            {issue.code for issue in revision.validations[-1].issues},
        )

    def test_named_batch_generation_records_all_six_serial_stages(self) -> None:
        artifact_name = f"orchestrator-test-{uuid4().hex}"
        source_dir = WORKSPACE_ROOT / "temp" / "cad-source" / artifact_name
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                temporary_root = Path(temporary_directory)
                orchestrator = fake_orchestrator(temporary_root)
                result = orchestrator.execute_spec(
                    artifact_name,
                    cabinet_data("wall_cabinet"),
                    output_root=temporary_root / "outputs",
                    artifact_name=artifact_name,
                    generate_cad=True,
                )

                self.assertEqual(
                    result.revision.workflow.current,
                    WorkflowStage.DELIVERY_VALIDATED,
                )
                self.assertEqual(
                    set(result.revision.stage_outputs),
                    {stage.value for stage in STAGE_SEQUENCE},
                )
                self.assertEqual(
                    result.revision.approved_stages,
                    [stage.value for stage in STAGE_SEQUENCE],
                )
                self.assertTrue(all(report.passed for report in result.revision.validations))
                self.assertEqual(
                    [report.stage for report in result.revision.validations],
                    [stage.value for stage in STAGE_SEQUENCE],
                )
                artifact_kinds = {
                    artifact.kind for artifact in result.revision.manifest.artifacts
                }
                self.assertEqual(
                    artifact_kinds,
                    {
                        "design_intent",
                        "panel_plan",
                        "manufacturing_plan",
                        "feature_tree",
                        "bom",
                        "drilled_holes",
                        "drilled_holes_glb",
                        "drilled_holes_step",
                        "drilled_holes_step_glb",
                        "six_side_drill_xml",
                        "cad_source",
                        "step",
                        "viewer_topology",
                    },
                )
                self.assertIsNotNone(result.pipeline)
                self.assertEqual(result.bridge.status, "ok")
                delivery_output = result.revision.stage_outputs[
                    WorkflowStage.DELIVERY_VALIDATED.value
                ]
                self.assertTrue(delivery_output["passed"])
                self.assertIn(
                    "MANUFACTURING_PRELIMINARY",
                    {
                        issue["code"]
                        for issue in delivery_output["issues"]
                    },
                )
                readiness_by_kind = {
                    artifact.kind: artifact.metadata.get("readiness")
                    for artifact in result.revision.manifest.artifacts
                    if artifact.kind in {"manufacturing_plan", "bom"}
                }
                self.assertEqual(
                    readiness_by_kind,
                    {
                        "manufacturing_plan": "preliminary",
                        "bom": "preliminary",
                    },
                )
                six_side_artifacts = [
                    artifact
                    for artifact in result.revision.manifest.artifacts
                    if artifact.kind == "six_side_drill_xml"
                ]
                self.assertEqual(
                    len(six_side_artifacts),
                    len(result.pipeline.panels),
                )
                self.assertTrue(
                    all(
                        artifact.metadata.get("panel_label")
                        and artifact.metadata.get("readiness") == "preliminary"
                        for artifact in six_side_artifacts
                    )
                )

                incomplete_lineage = validate_delivery(
                    result.revision.manifest,
                    source_revision_id=result.revision.id,
                    stage_outputs=result.revision.stage_outputs,
                    approved_stages=[],
                    stage_validations=[],
                )
                self.assertFalse(incomplete_lineage.passed)
                incomplete_codes = {
                    issue.code for issue in incomplete_lineage.issues
                }
                self.assertIn(
                    "UNAPPROVED_DELIVERY_SOURCE_STAGE",
                    incomplete_codes,
                )
                self.assertIn(
                    "MISSING_STAGE_VALIDATION",
                    incomplete_codes,
                )

                design_artifact = next(
                    artifact
                    for artifact in result.revision.manifest.artifacts
                    if artifact.kind == "design_intent"
                )
                Path(design_artifact.path).write_text(
                    '{"tampered": true}',
                    encoding="utf-8",
                )
                tampered_report = validate_delivery(
                    result.revision.manifest,
                    source_revision_id=result.revision.id,
                )
                self.assertFalse(tampered_report.passed)
                self.assertIn(
                    "ARTIFACT_HASH_MISMATCH",
                    {issue.code for issue in tampered_report.issues},
                )
        finally:
            shutil.rmtree(source_dir, ignore_errors=True)

    def test_revised_manufacturing_operation_must_remain_inside_target_panel(self) -> None:
        result = self.orchestrator.execute_spec(
            "加工验证",
            cabinet_data(),
            through_stage=WorkflowStage.MANUFACTURING_PLANNED,
        )
        edited = deepcopy(
            result.revision.stage_outputs[WorkflowStage.MANUFACTURING_PLANNED.value]
        )
        edited["operations"][0]["pos_x"] = -1
        revision = self.orchestrator.revise_stage_output(
            result.project,
            WorkflowStage.MANUFACTURING_PLANNED,
            edited,
        )

        self.orchestrator.confirm_stage(
            result.project,
            WorkflowStage.MANUFACTURING_PLANNED,
        )

        self.assertEqual(revision.workflow.current, WorkflowStage.FAILED)
        self.assertIn(
            "OPERATION_OUTSIDE_TARGET",
            {issue.code for issue in revision.validations[-1].issues},
        )

    def test_manufacturing_readiness_must_use_known_state(self) -> None:
        result = self.orchestrator.execute_spec(
            "制造状态验证",
            cabinet_data(),
            through_stage=WorkflowStage.MANUFACTURING_PLANNED,
        )
        edited = deepcopy(
            result.revision.stage_outputs[
                WorkflowStage.MANUFACTURING_PLANNED.value
            ]
        )
        edited["readiness"] = "claimed_ready"
        revision = self.orchestrator.revise_stage_output(
            result.project,
            WorkflowStage.MANUFACTURING_PLANNED,
            edited,
        )

        self.orchestrator.confirm_stage(
            result.project,
            WorkflowStage.MANUFACTURING_PLANNED,
        )

        self.assertEqual(revision.workflow.current, WorkflowStage.FAILED)
        self.assertIn(
            "INVALID_MANUFACTURING_READINESS",
            {issue.code for issue in revision.validations[-1].issues},
        )

    def test_new_intent_revision_marks_parent_artifacts_stale(self) -> None:
        artifact_name = f"revision-test-{uuid4().hex}"
        source_dir = WORKSPACE_ROOT / "temp" / "cad-source" / artifact_name
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                temporary_root = Path(temporary_directory)
                orchestrator = fake_orchestrator(temporary_root)
                result = orchestrator.execute_spec(
                    artifact_name,
                    cabinet_data("wall_cabinet"),
                    output_root=temporary_root / "outputs",
                    artifact_name=artifact_name,
                    generate_cad=True,
                )
                parent = result.revision

                revised = orchestrator.revise(
                    result.project,
                    DesignIntent(
                        furniture_type="wall_cabinet",
                        overall_size=OverallSize(900, 350, 900),
                        mount_mode="free_height",
                        mounting_height_mm=2000,
                    ),
                )

                self.assertEqual(revised.parent_revision_id, parent.id)
                self.assertTrue(all(item.stale for item in parent.manifest.artifacts))
                self.assertEqual(
                    set(revised.stage_outputs),
                    {WorkflowStage.DESIGN_INTENT.value},
                )
        finally:
            shutil.rmtree(source_dir, ignore_errors=True)

    def test_unconfirmed_intent_pauses_without_executing_panels(self) -> None:
        project = self.orchestrator.create_project("未确认", cabinet_intent())
        result = self.orchestrator.run_until(
            project,
            WorkflowStage.FEATURE_TREE_PLANNED,
        )

        self.assertIsNone(result.pipeline)
        self.assertEqual(
            result.revision.workflow.current,
            WorkflowStage.DESIGN_INTENT,
        )
        self.assertNotIn(
            WorkflowStage.PANELS_PLANNED.value,
            result.revision.stage_outputs,
        )
        self.assertNotIn("layout_planned", result.revision.stage_outputs)

    def test_serial_workflow_skips_room_layout_even_when_context_is_supplied(self) -> None:
        result = self.orchestrator.execute_spec(
            "带房间信息的柜体",
            cabinet_data(
                room={
                    "width_mm": 4200,
                    "depth_mm": 3600,
                    "height_mm": 2800,
                },
                placement={
                    "mode": "wall",
                    "host_wall": "north",
                    "offset_mm": 500,
                },
            ),
            through_stage=WorkflowStage.PANELS_PLANNED,
        )

        self.assertEqual(
            result.revision.workflow.current,
            WorkflowStage.PANELS_PLANNED,
        )
        self.assertNotIn("layout_planned", result.revision.stage_outputs)
        self.assertIn("panels_planned", result.revision.stage_outputs)

    def test_draft_intent_preserves_null_dimensions_and_cannot_confirm(self) -> None:
        intent = DesignIntent.from_dict(
            {
                "furniture_type": "floor_cabinet",
                "overall_size": {
                    "width_mm": 800,
                    "depth_mm": None,
                    "height_mm": 1000,
                },
            }
        )
        project = self.orchestrator.create_project("未完整柜体", intent)

        self.assertIsNone(
            project.latest.stage_outputs["design_intent"]["overall_size"]["depth_mm"]
        )
        revision = self.orchestrator.confirm_intent(project)

        self.assertEqual(revision.workflow.current, WorkflowStage.FAILED)
        issue_codes = {issue.code for issue in revision.validations[-1].issues}
        self.assertIn("INVALID_INTENT", issue_codes)

    def test_runtime_requires_llm_to_normalize_natural_language_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "executable canonical type"):
            cabinet_intent(furniture_type="地柜").confirm()

    def test_unsupported_layout_decision_is_rejected_by_independent_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "layout input only accepts"):
            stage_inputs_from_spec(
                {"layout": {"unsupported_layout_option": 2}}
            )

    def test_unsupported_structure_decision_fails_at_panel_stage(self) -> None:
        project = self.orchestrator.create_project(
            "未知连接柜体",
            cabinet_intent(),
            stage_inputs=stage_inputs_from_spec(
                {"structure": {"mystery_joint": "unknown"}}
            ),
        )
        self.orchestrator.confirm_intent(project)
        revision = self.orchestrator.run_next(project).revision

        self.assertEqual(revision.workflow.current, WorkflowStage.FAILED)
        self.assertIn("panel stage does not support", revision.validations[-1].issues[0].message)

    def test_unclassified_constraint_is_rejected_by_protocol_routing(self) -> None:
        with self.assertRaisesRegex(ValueError, "has no stage mapping"):
            stage_inputs_from_spec({"constraints": ["必须提供防倾倒固定"]})

    def test_constraints_require_explicit_executable_or_informational_destinations(
        self,
    ) -> None:
        inputs = stage_inputs_from_spec(
            {
                "back_mount": "cover",
                "constraints": ["背板必须外盖", "仅供卧室方案比较"],
                "constraint_mappings": {
                    "背板必须外盖": "structure.back_mount",
                    "仅供卧室方案比较": "informational",
                },
            }
        )
        self.assertEqual(
            inputs["panels"]["constraints"][0]["target"],
            "structure.back_mount",
        )
        self.assertEqual(inputs["informational_constraints"], ["仅供卧室方案比较"])

    def test_malformed_dormant_parameters_fail_structured_admission(self) -> None:
        result = self.orchestrator.execute_spec(
            "外盖背板柜体",
            cabinet_data(
                back_mount="cover",
                groove_depth="unused",
                groove_clearance="unused",
                back_rail_height="unused",
            ),
            through_stage=WorkflowStage.PANELS_PLANNED,
        )
        self.assertEqual(result.revision.workflow.current, WorkflowStage.FAILED)
        self.assertIn(
            "must be numeric",
            result.revision.validations[-1].issues[0].message,
        )

    def test_active_groove_parameters_are_validated_at_panel_stage(self) -> None:
        result = self.orchestrator.execute_spec(
            "错误入槽参数柜体",
            cabinet_data(back_mount="groove", groove_depth="invalid"),
            through_stage=WorkflowStage.PANELS_PLANNED,
        )
        self.assertEqual(result.revision.workflow.current, WorkflowStage.FAILED)
        self.assertIn(
            "must be numeric",
            result.revision.validations[-1].issues[0].message,
        )

    def test_unsupported_family_fails_at_design_intent_confirmation(self) -> None:
        project = self.orchestrator.create_project(
            "床", cabinet_intent(furniture_type="bed")
        )
        revision = self.orchestrator.confirm_intent(project)

        self.assertEqual(revision.workflow.current, WorkflowStage.FAILED)
        self.assertFalse(revision.validations[-1].passed)
        self.assertEqual(
            revision.validations[-1].issues[0].code,
            "UNSUPPORTED_FURNITURE_TYPE",
        )

    def test_project_store_round_trips_stage_outputs_and_approvals(self) -> None:
        result = self.orchestrator.execute_spec(
            "可恢复项目",
            cabinet_data(),
            through_stage=WorkflowStage.FEATURE_TREE_PLANNED,
        )
        project = result.project

        with tempfile.TemporaryDirectory() as temporary_directory:
            store = JsonProjectStore(temporary_directory)
            store.save(project)
            restored = store.load(project.id)

        self.assertEqual(restored.id, project.id)
        self.assertEqual(restored.latest.stage_inputs, project.latest.stage_inputs)
        self.assertEqual(restored.latest.stage_outputs, project.latest.stage_outputs)
        self.assertEqual(restored.latest.approved_stages, project.latest.approved_stages)
        self.assertEqual(
            restored.latest.workflow.current,
            WorkflowStage.FEATURE_TREE_PLANNED,
        )

    def test_legacy_projects_migrate_only_recoverable_hinge_sides(self) -> None:
        payloads: list[tuple[dict, str | None]] = []
        for door_count, hinge_side in ((1, "right"), (2, None)):
            result = self.orchestrator.execute_spec(
                f"旧项目-{door_count}",
                cabinet_data(
                    n_doors=door_count,
                    door_hinge_side=hinge_side,
                ),
                through_stage=WorkflowStage.PANELS_PLANNED,
            )
            payload = deepcopy(result.project.to_dict())
            raw_revision = payload["revisions"][-1]
            raw_revision["stage_outputs"]["panels_planned"]["spec"].pop(
                "door_hinge_side"
            )
            raw_revision["stage_inputs"]["panels"]["parameters"].pop(
                "door_hinge_side"
            )
            if door_count == 2:
                for panel in raw_revision["stage_outputs"]["panels_planned"][
                    "panels"
                ]:
                    if panel["panel_type"] == "door":
                        panel.pop("door_hinge_side")
            payloads.append((payload, hinge_side))

        for payload, expected_side in payloads:
            with self.subTest(expected_side=expected_side):
                restored = Project.from_dict(payload)
                revision = restored.latest
                self.assertEqual(
                    revision.stage_outputs["panels_planned"]["spec"][
                        "door_hinge_side"
                    ],
                    expected_side,
                )
                self.assertEqual(
                    revision.stage_inputs["panels"]["parameters"][
                        "door_hinge_side"
                    ],
                    expected_side,
                )
                if expected_side is None:
                    migrated_doors = sorted(
                        (
                            panel
                            for panel in revision.stage_outputs["panels_planned"][
                                "panels"
                            ]
                            if panel["panel_type"] == "door"
                        ),
                        key=lambda panel: panel["pos_x"],
                    )
                    self.assertEqual(
                        [panel["door_hinge_side"] for panel in migrated_doors],
                        ["left", "right"],
                    )
                continued = self.orchestrator.run_next(restored)
                self.assertEqual(
                    continued.revision.workflow.current,
                    WorkflowStage.MANUFACTURING_PLANNED,
                )
                self.assertTrue(continued.revision.validations[-1].passed)

        invalid_single = deepcopy(payloads[0][0])
        invalid_door = next(
            panel
            for panel in invalid_single["revisions"][-1]["stage_outputs"][
                "panels_planned"
            ]["panels"]
            if panel["panel_type"] == "door"
        )
        invalid_door["door_hinge_side"] = None
        with self.assertRaisesRegex(ValueError, "explicit panel door_hinge_side"):
            Project.from_dict(invalid_single)

    def test_intent_from_spec_contains_only_category_and_envelope(self) -> None:
        request = {
            "type": "wall_cabinet",
            "width": 800,
            "depth": 350,
            "height": 900,
            "shelves": [{"shelf_type": "fixed", "gap_below_mm": None}],
            "top_gap_mm": 300,
            "back_mount": "cover",
        }
        intent = self.orchestrator.intent_from_spec(request)
        self.assertEqual(intent.overall_size.width_mm, 800)
        self.assertEqual(intent.overall_size.depth_mm, 350)
        self.assertEqual(intent.overall_size.height_mm, 900)
        self.assertEqual(
            set(intent.to_dict()),
            {
                "furniture_type",
                "overall_size",
                "mount_mode",
                "mounting_height_mm",
                "confirmed",
                "schema_version",
            },
        )
        inputs = stage_inputs_from_spec(request)
        self.assertEqual(
            inputs["panels"]["parameters"]["shelves"],
            [{"shelf_type": "fixed", "gap_below_mm": None}],
        )
        self.assertEqual(inputs["panels"]["parameters"]["top_gap_mm"], 300)
        self.assertEqual(inputs["panels"]["parameters"]["back_mount"], "cover")

    def test_design_intent_rejects_new_downstream_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "route later decisions"):
            DesignIntent.from_dict(
                {
                    "furniture_type": "floor_cabinet",
                    "overall_size": {
                        "width_mm": 800,
                        "depth_mm": 600,
                        "height_mm": 1000,
                    },
                    "structure": {"back_mount": "cover"},
                }
            )

    def test_wall_cabinet_intent_requires_mount_mode_before_confirmation(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "mount_mode"):
            DesignIntent(
                furniture_type="wall_cabinet",
                overall_size=OverallSize(800, 350, 900),
            ).confirm()

        with self.assertRaisesRegex(ValueError, "mounting_height_mm"):
            DesignIntent(
                furniture_type="wall_cabinet",
                overall_size=OverallSize(800, 350, 900),
                mount_mode="free_height",
            ).confirm()

        free = DesignIntent(
            furniture_type="wall_cabinet",
            overall_size=OverallSize(800, 350, 900),
            mount_mode="free_height",
            mounting_height_mm=1800,
        ).confirm()
        self.assertTrue(free.confirmed)
        self.assertEqual(free.to_dict()["mounting_height_mm"], 1800)

        flush = DesignIntent(
            furniture_type="wall_cabinet",
            overall_size=OverallSize(800, 350, 900),
            mount_mode="flush_ceiling",
        ).confirm()
        self.assertTrue(flush.confirmed)
        self.assertIsNone(flush.mounting_height_mm)

        floor = DesignIntent(
            furniture_type="floor_cabinet",
            overall_size=OverallSize(800, 600, 1000),
        ).confirm()
        self.assertTrue(floor.confirmed)
        self.assertIsNone(floor.to_dict()["mounting_height_mm"])

    def test_panel_stage_admits_complete_structured_parameters(self) -> None:
        project = self.orchestrator.create_project(
            "直接意图柜体",
            cabinet_intent(),
            stage_inputs=stage_inputs_from_spec(
                panel_parameters()
            ),
        )

        revision = self.orchestrator.confirm_intent(project)
        self.assertNotIn("structure", revision.stage_outputs["design_intent"])
        with self.assertRaisesRegex(ValueError, "panel proposal is incomplete"):
            plan_panel_stage(revision.intent, {})
        result = self.orchestrator.run_next(project)
        panel_output = result.revision.stage_outputs["panels_planned"]
        self.assertEqual(panel_output["spec"]["board_thickness"], 18.0)
        self.assertEqual(panel_output["structure"]["back_mount"], "groove")


if __name__ == "__main__":
    unittest.main()
````

## File: domain/skills/furniture-cad/scripts/tests/test_room_layout_preview.py
````python
from __future__ import annotations

from copy import deepcopy
from math import hypot
import sys
import unittest
from pathlib import Path
from xml.etree import ElementTree


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_workflow.input_adapter import (
    layout_stage_input,
    panel_stage_input,
    stage_inputs_from_spec,
)
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_state import STAGE_SEQUENCE, WorkflowStage
from furniture_layout.layout_pipeline import plan_layout_stage
from furniture_layout.layout_preview import _build_projector
from furniture_layout.layout_spec import LayoutSpec
from furniture_layout.validation import validate_layout_output


def wardrobe_spec(
    *,
    wall: str = "south",
    offset_mm: float = 500,
) -> dict:
    return {
        "type": "floor_cabinet",
        "width": 1800,
        "depth": 600,
        "height": 2400,
        "room": {
            "id": "bedroom",
            "name": "主卧",
            "width_mm": 4200,
            "depth_mm": 3600,
            "height_mm": 2800,
            "openings": [
                {
                    "id": "bedroom_door",
                    "kind": "door",
                    "wall": "south",
                    "offset_mm": 3000,
                    "width_mm": 900,
                    "height_mm": 2100,
                }
            ],
            "obstacles": [
                {
                    "id": "column",
                    "kind": "column",
                    "x_mm": 3700,
                    "y_mm": 2900,
                    "z_mm": 0,
                    "width_mm": 300,
                    "depth_mm": 400,
                    "height_mm": 2800,
                }
            ],
        },
        "placement": {
            "mode": "wall",
            "host_wall": wall,
            "offset_mm": offset_mm,
            "origin_z_mm": 0,
        },
    }


def run_independent_layout(name: str, spec: dict):
    orchestrator = FurnitureOrchestrator(workspace_root=WORKSPACE_ROOT)
    intent = orchestrator.intent_from_spec(spec).confirm()
    stage_inputs = stage_inputs_from_spec(spec)
    panel_parameters = panel_stage_input(stage_inputs).get("parameters", {})
    options = {
        key: panel_parameters[key]
        for key in ("n_doors", "door_count")
        if key in panel_parameters
    }
    context = layout_stage_input(stage_inputs)
    layout_spec = LayoutSpec.from_intent(intent, options)
    output = plan_layout_stage(
        layout_spec,
        room=context.get("room"),
        placement=context.get("placement"),
        furniture_label=name,
    )
    return layout_spec, output, validate_layout_output(layout_spec, output)


class RoomLayoutPreviewTests(unittest.TestCase):
    def test_preview_projection_makes_near_geometry_larger(self) -> None:
        project = _build_projector(4200, 3600, 2800)

        near_bottom = project((4200, 0, 0))
        near_top = project((4200, 0, 1000))
        far_bottom = project((0, 3600, 0))
        far_top = project((0, 3600, 1000))
        near_height = hypot(
            near_top[0] - near_bottom[0],
            near_top[1] - near_bottom[1],
        )
        far_height = hypot(
            far_top[0] - far_bottom[0],
            far_top[1] - far_bottom[1],
        )

        self.assertGreater(near_height, far_height * 1.5)

    def test_missing_room_context_uses_visible_default_bedroom(self) -> None:
        _, output, report = run_independent_layout(
            "1600衣柜",
            {
                "type": "floor_cabinet",
                "width": 1600,
                "depth": 600,
                "height": 2400,
            },
        )

        self.assertEqual(
            output["layout_context"],
            {
                "room_source": "default_bedroom",
                "placement_source": "default_north_wall_centered",
            },
        )
        self.assertEqual(
            output["room_placement"]["room"],
            {
                "id": "default_bedroom",
                "name": "默认卧室（系统假设）",
                "width_mm": 4200.0,
                "depth_mm": 3600.0,
                "height_mm": 2800.0,
                "openings": [],
                "obstacles": [],
            },
        )
        self.assertEqual(
            output["room_placement"]["placement"]["origin_x_mm"],
            1300,
        )
        self.assertEqual(
            output["room_placement"]["placement"]["host_wall"],
            "north",
        )
        self.assertEqual(
            output["preview"]["view_kind"],
            "perspective_envelope",
        )
        self.assertEqual(output["viewer"]["media_type"], "text/html")
        self.assertEqual(
            output["viewer"]["view_kind"],
            "interactive_orbit_envelope",
        )
        self.assertIn("drag_orbit", output["viewer"]["controls"])
        self.assertIn('data-view="top"', output["viewer"]["html"])
        self.assertIn('addEventListener("pointermove"', output["viewer"]["html"])
        self.assertIn('addEventListener("wheel"', output["viewer"]["html"])
        self.assertIn("透明为房间", output["preview"]["svg"])
        self.assertIn("默认卧室（系统假设）", output["preview"]["svg"])
        self.assertTrue(report.passed)

    def test_missing_placement_centers_furniture_in_provided_room(self) -> None:
        spec = wardrobe_spec()
        del spec["placement"]
        _, output, report = run_independent_layout(
            "主卧衣柜",
            spec,
        )

        self.assertTrue(report.passed)
        self.assertEqual(output["layout_context"]["room_source"], "provided")
        self.assertEqual(
            output["layout_context"]["placement_source"],
            "default_north_wall_centered",
        )
        self.assertEqual(
            output["room_placement"]["placement"]["origin_x_mm"],
            1200,
        )

    def test_wall_cabinet_default_placement_uses_confirmed_mounting_height(
        self,
    ) -> None:
        _, output, report = run_independent_layout(
            "吊柜",
            {
                "type": "wall_cabinet",
                "width": 800,
                "depth": 350,
                "height": 900,
                "mount_mode": "free_height",
                "mounting_height": 1800,
            },
        )

        self.assertTrue(report.passed)
        self.assertEqual(
            output["room_placement"]["placement"]["origin_z_mm"],
            1800,
        )
        self.assertEqual(
            output["room_placement"]["clearances_mm"]["floor"],
            1800,
        )

    def test_wall_cabinet_flush_ceiling_placement_uses_room_height(self) -> None:
        _, output, report = run_independent_layout(
            "到顶吊柜",
            {
                "type": "wall_cabinet",
                "width": 800,
                "depth": 350,
                "height": 900,
                "mount_mode": "flush_ceiling",
            },
        )

        self.assertTrue(report.passed)
        # 默认卧室层高 2800，贴顶 → 底边 = 2800 - 900 = 1900
        self.assertEqual(
            output["room_placement"]["placement"]["origin_z_mm"],
            1900,
        )

    def test_independent_layout_emits_room_position_footprint_and_svg(self) -> None:
        _, output, report = run_independent_layout(
            "主卧衣柜",
            wardrobe_spec(),
        )

        self.assertNotIn(WorkflowStage.LAYOUT_PLANNED, STAGE_SEQUENCE)
        room_placement = output["room_placement"]
        placement = room_placement["placement"]
        self.assertEqual(placement["host_wall"], "south")
        self.assertEqual(placement["origin_x_mm"], 3700)
        self.assertEqual(placement["origin_y_mm"], 3600)
        self.assertEqual(placement["rotation_z_deg"], 180)
        self.assertEqual(
            room_placement["furniture_footprint"],
            [
                {"x_mm": 3700.0, "y_mm": 3600.0},
                {"x_mm": 1900.0, "y_mm": 3600.0},
                {"x_mm": 1900.0, "y_mm": 3000.0},
                {"x_mm": 3700.0, "y_mm": 3000.0},
            ],
        )
        self.assertEqual(room_placement["clearances_mm"]["north"], 3000)
        self.assertEqual(output["preview"]["media_type"], "image/svg+xml")
        self.assertEqual(
            output["preview"]["view_kind"],
            "perspective_envelope",
        )
        self.assertIn("<svg", output["preview"]["svg"])
        self.assertIn("三维包络预览", output["preview"]["svg"])
        self.assertIn("主卧衣柜", output["preview"]["svg"])
        self.assertEqual(
            ElementTree.fromstring(output["preview"]["svg"]).tag,
            "{http://www.w3.org/2000/svg}svg",
        )
        self.assertTrue(report.passed)

    def test_north_wall_position_derives_room_transform(self) -> None:
        spec = wardrobe_spec(wall="north", offset_mm=400)
        spec["room"]["obstacles"] = []
        _, output, report = run_independent_layout(
            "北墙衣柜",
            spec,
        )

        self.assertTrue(report.passed)
        placement = output["room_placement"]["placement"]
        self.assertEqual(placement["origin_x_mm"], 400)
        self.assertEqual(placement["origin_y_mm"], 0)
        self.assertEqual(placement["rotation_z_deg"], 0)
        self.assertEqual(
            output["room_placement"]["clearances_mm"]["north"],
            0,
        )

    def test_free_position_supports_rotation(self) -> None:
        spec = wardrobe_spec()
        spec["placement"] = {
            "mode": "free",
            "origin_x_mm": 1000,
            "origin_y_mm": 1000,
            "origin_z_mm": 0,
            "rotation_z_deg": 90,
        }
        _, output, report = run_independent_layout(
            "自由摆放衣柜",
            spec,
        )

        self.assertTrue(report.passed)
        footprint = output["room_placement"]["furniture_footprint"]
        self.assertEqual(
            footprint,
            [
                {"x_mm": 1000.0, "y_mm": 1000.0},
                {"x_mm": 1000.0, "y_mm": 2800.0},
                {"x_mm": 400.0, "y_mm": 2800.0},
                {"x_mm": 400.0, "y_mm": 1000.0},
            ],
        )
    def test_layout_rejects_furniture_outside_room(self) -> None:
        _, _, report = run_independent_layout(
            "越界衣柜",
            wardrobe_spec(offset_mm=3000),
        )

        self.assertFalse(report.passed)
        self.assertIn(
            "FURNITURE_OUTSIDE_ROOM",
            {issue.code for issue in report.issues},
        )

    def test_layout_rejects_opening_and_obstacle_collisions(self) -> None:
        door_spec = wardrobe_spec(offset_mm=2200)
        _, _, door_report = run_independent_layout(
            "遮门衣柜",
            door_spec,
        )
        self.assertIn(
            "FURNITURE_OPENING_COLLISION",
            {issue.code for issue in door_report.issues},
        )

        free_door_spec = wardrobe_spec()
        free_door_spec["placement"] = {
            "mode": "free",
            "origin_x_mm": 0,
            "origin_y_mm": 3000,
            "origin_z_mm": 0,
            "rotation_z_deg": 0,
        }
        _, _, free_door_report = run_independent_layout(
            "自由摆放遮门衣柜",
            free_door_spec,
        )
        self.assertIn(
            "FURNITURE_OPENING_COLLISION",
            {
                issue.code for issue in free_door_report.issues
            },
        )

        obstacle_spec = wardrobe_spec()
        obstacle_spec["room"]["obstacles"] = [
            {
                "id": "low_column",
                "kind": "column",
                "x_mm": 2000,
                "y_mm": 3200,
                "z_mm": 0,
                "width_mm": 300,
                "depth_mm": 300,
                "height_mm": 2800,
            }
        ]
        _, _, obstacle_report = run_independent_layout(
            "撞柱衣柜",
            obstacle_spec,
        )
        self.assertIn(
            "FURNITURE_OBSTACLE_COLLISION",
            {
                issue.code for issue in obstacle_report.issues
            },
        )

    def test_revised_position_must_refresh_transform_and_preview(self) -> None:
        layout_spec, output, report = run_independent_layout(
            "可修改衣柜位置",
            wardrobe_spec(),
        )
        self.assertTrue(report.passed)
        edited = deepcopy(output)
        edited["room_placement"]["placement"]["offset_mm"] = 700
        edited_report = validate_layout_output(layout_spec, edited)

        self.assertFalse(edited_report.passed)
        issue_codes = {issue.code for issue in edited_report.issues}
        self.assertIn("WALL_PLACEMENT_TRANSFORM_MISMATCH", issue_codes)
        self.assertIn("LAYOUT_PREVIEW_MISMATCH", issue_codes)
        self.assertIn("LAYOUT_VIEWER_MISMATCH", issue_codes)


if __name__ == "__main__":
    unittest.main()
````

## File: domain/skills/furniture-cad/scripts/tests/test_skill_architecture.py
````python
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

import yaml


WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
SKILLS_ROOT = WORKSPACE_ROOT / "domain" / "skills"

INTENT_SCRIPTS_ROOT = SKILLS_ROOT / "furniture-design-intent" / "scripts"
if str(INTENT_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(INTENT_SCRIPTS_ROOT))

from furniture_design_intent.design_intent import SUPPORTED_TYPES

STAGE_SKILLS = {
    "design_intent": "furniture-design-intent",
    "panels_planned": "furniture-panel-planning",
    "manufacturing_planned": "furniture-manufacturing",
    "feature_tree_planned": "furniture-feature-tree",
    "cad_generated": "furniture-cad",
    "delivery_validated": "furniture-delivery-validation",
}

STAGE_REFERENCES = {
    "furniture-design-intent": (
        "references/intent-capture-rules.md",
        "references/intake/catalog.yaml",
    ),
    "furniture-layout": ("references/spatial-layout-rules.md",),
    "furniture-panel-planning": (
        "references/panel-definition-rules.md",
    ),
    "furniture-manufacturing": ("references/manufacturing-rules.md",),
    "furniture-feature-tree": ("references/feature-tree-rules.md",),
    "furniture-cad": ("references/runtime-contract.md",),
    "furniture-delivery-validation": ("references/delivery-checklist.md",),
}

STAGE_RUNTIME_PACKAGES = {
    "furniture-design-intent": "furniture_design_intent",
    "furniture-layout": "furniture_layout",
    "furniture-panel-planning": "furniture_panel_planning",
    "furniture-manufacturing": "furniture_manufacturing",
    "furniture-feature-tree": "furniture_feature_tree",
    "furniture-cad": "furniture_cad",
    "furniture-delivery-validation": "furniture_delivery_validation",
}


class SkillArchitectureTests(unittest.TestCase):
    def test_llm_runtime_boundary_policy_is_discoverable(self) -> None:
        policy_relative_path = (
            ".agents/skills/furniture-agent/references/"
            "llm-runtime-boundary.md"
        )
        policy_path = WORKSPACE_ROOT / policy_relative_path
        self.assertTrue(policy_path.is_file(), policy_path)

        router_path = (
            WORKSPACE_ROOT / ".agents" / "skills" / "furniture-agent" / "SKILL.md"
        )
        router = router_path.read_text(encoding="utf-8")
        self.assertIn("references/llm-runtime-boundary.md", router, router_path)

        repository_instructions = (WORKSPACE_ROOT / "AGENTS.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(policy_relative_path, repository_instructions)

    def test_six_serial_stages_have_one_skill_each(self) -> None:
        claimed_stages: dict[str, str] = {}

        for stage, skill_name in STAGE_SKILLS.items():
            skill_root = SKILLS_ROOT / skill_name
            skill_file = skill_root / "SKILL.md"
            agent_file = skill_root / "agents" / "openai.yaml"
            self.assertTrue(skill_file.is_file(), skill_file)
            self.assertTrue(agent_file.is_file(), agent_file)

            skill_text = skill_file.read_text(encoding="utf-8")
            match = re.search(r"^阶段：`([^\`]+)`$", skill_text, re.MULTILINE)
            self.assertIsNotNone(match, skill_file)
            claimed_stage = match.group(1)
            self.assertEqual(claimed_stage, stage, skill_file)
            self.assertNotIn(claimed_stage, claimed_stages)
            claimed_stages[claimed_stage] = skill_name

        self.assertEqual(claimed_stages, STAGE_SKILLS)
        layout_skill = (SKILLS_ROOT / "furniture-layout" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("独立按需步骤", layout_skill)
        self.assertNotRegex(layout_skill, re.compile(r"^阶段：`", re.MULTILINE))

    def test_router_uses_explicit_stage_skill_paths(self) -> None:
        router = (
            WORKSPACE_ROOT / ".agents" / "skills" / "furniture-agent" / "SKILL.md"
        ).read_text(encoding="utf-8")

        for stage, skill_name in STAGE_SKILLS.items():
            self.assertIn(
                f"`{stage}`：`domain/skills/{skill_name}/SKILL.md`",
                router,
            )
        self.assertIn(
            "独立能力（不在上述串联阶段内）",
            router,
        )
        self.assertIn("`domain/skills/furniture-layout/SKILL.md`", router)

    def test_scientific_skills_are_routed_on_demand_to_stage_owned_adapters(
        self,
    ) -> None:
        router_path = (
            WORKSPACE_ROOT / ".agents" / "skills" / "furniture-agent" / "SKILL.md"
        )
        router = router_path.read_text(encoding="utf-8")
        for skill_name in (
            "uncertainty-and-units",
            "pymoo",
            "experimental-design",
            "statistical-analysis",
            "simpy",
        ):
            self.assertIn(f"{skill_name}/SKILL.md", router, router_path)

        owned_adapters = (
            (
                "furniture-panel-planning",
                "furniture_panel_planning/quantitative_audit.py",
            ),
            (
                "furniture-panel-planning",
                "furniture_panel_planning/design_optimization.py",
            ),
            (
                "furniture-manufacturing",
                "furniture_manufacturing/prototype_experiment.py",
            ),
            (
                "furniture-manufacturing",
                "furniture_manufacturing/test_statistics.py",
            ),
            (
                "furniture-manufacturing",
                "furniture_manufacturing/production_simulation.py",
            ),
        )
        for skill_name, relative_path in owned_adapters:
            path = SKILLS_ROOT / skill_name / "scripts" / relative_path
            self.assertTrue(path.is_file(), path)

        self.assertFalse(
            (
                WORKSPACE_ROOT
                / ".agents"
                / "skills"
                / "scientific-agent-skills"
            ).exists()
        )

    def test_stage_references_live_with_their_owning_skill(self) -> None:
        for skill_name, references in STAGE_REFERENCES.items():
            skill_root = SKILLS_ROOT / skill_name
            for relative_path in references:
                self.assertTrue((skill_root / relative_path).is_file())

        cad_references = SKILLS_ROOT / "furniture-cad" / "references"
        for moved_reference in (
            "intent-capture-rules.md",
            "spatial-layout-rules.md",
            "panel-definition-rules.md",
            "manufacturing-rules.md",
            "feature-tree-rules.md",
            "delivery-checklist.md",
        ):
            self.assertFalse((cad_references / moved_reference).exists())

        topology_root = (
            SKILLS_ROOT
            / "furniture-panel-planning"
            / "references"
            / "cabinet-topologies"
        )
        self.assertTrue((topology_root / "floor_cabinet.yaml").is_file())
        self.assertTrue((topology_root / "wall_cabinet.yaml").is_file())
        self.assertFalse(
            (
                SKILLS_ROOT
                / "furniture-design-intent"
                / "references"
                / "cabinet_topologies"
            ).exists()
        )

    def test_intent_catalog_executable_families_match_runtime_supported_types(
        self,
    ) -> None:
        catalog_path = (
            SKILLS_ROOT
            / "furniture-design-intent"
            / "references"
            / "intake"
            / "catalog.yaml"
        )
        catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
        executable_families = {
            name
            for name, family in catalog.get("families", {}).items()
            if family.get("executable") is True
        }
        self.assertEqual(
            executable_families,
            set(SUPPORTED_TYPES),
            "catalog.yaml `executable: true` families must match SUPPORTED_TYPES",
        )

    def test_each_stage_skill_owns_its_runtime_package(self) -> None:
        for skill_name, package_name in STAGE_RUNTIME_PACKAGES.items():
            package_root = SKILLS_ROOT / skill_name / "scripts" / package_name
            self.assertTrue(package_root.is_dir(), package_root)
            self.assertTrue((package_root / "__init__.py").is_file(), package_root)

        workflow_package = (
            SKILLS_ROOT / "furniture-cad" / "scripts" / "furniture_workflow"
        )
        self.assertTrue((workflow_package / "workflow_orchestrator.py").is_file())

    def test_stage_validation_rules_do_not_live_in_the_orchestrator(self) -> None:
        validators = {
            "furniture-design-intent": "furniture_design_intent/validation.py",
            "furniture-layout": "furniture_layout/validation.py",
            "furniture-panel-planning": "furniture_panel_planning/validation.py",
            "furniture-manufacturing": "furniture_manufacturing/validation.py",
            "furniture-feature-tree": "furniture_feature_tree/validation.py",
            "furniture-cad": "furniture_cad/validation.py",
            "furniture-delivery-validation": (
                "furniture_delivery_validation/validation.py"
            ),
        }
        for skill_name, relative_path in validators.items():
            self.assertTrue(
                (SKILLS_ROOT / skill_name / "scripts" / relative_path).is_file()
            )

        orchestrator = (
            SKILLS_ROOT
            / "furniture-cad"
            / "scripts"
            / "furniture_workflow"
            / "workflow_orchestrator.py"
        ).read_text(encoding="utf-8")
        for forbidden_definition in (
            "def _validate_intent(",
            "def _validate_layout(",
            "def _validate_panels(",
            "def _validate_manufacturing(",
            "def _validate_feature_tree(",
            "def _validate_cad(",
            "def _validate_artifacts(",
            "def _write_artifacts(",
        ):
            self.assertNotIn(forbidden_definition, orchestrator)
        self.assertIn("def _validate_stage_output(", orchestrator)
        self.assertIn("from .workflow_artifact_writer import", orchestrator)

        delivery_validation = (
            SKILLS_ROOT
            / "furniture-delivery-validation"
            / "scripts"
            / "furniture_delivery_validation"
            / "validation.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("furniture_workflow", delivery_validation)

    def test_layout_does_not_own_panel_or_manufacturing_runtime(self) -> None:
        layout_package = (
            SKILLS_ROOT
            / "furniture-layout"
            / "scripts"
            / "furniture_layout"
        )
        layout_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in layout_package.glob("*.py")
        )
        self.assertNotIn("PanelPlacement", layout_source)
        self.assertNotIn("cut_box", layout_source)
        self.assertFalse((layout_package / "layout_template.py").exists())

        panel_package = (
            SKILLS_ROOT
            / "furniture-panel-planning"
            / "scripts"
            / "furniture_panel_planning"
        )
        manufacturing_package = (
            SKILLS_ROOT
            / "furniture-manufacturing"
            / "scripts"
            / "furniture_manufacturing"
        )
        self.assertTrue((panel_package / "cabinet_panel_planner.py").is_file())
        self.assertFalse((panel_package / "manufacturing_edge_banding.py").exists())
        self.assertTrue((manufacturing_package / "manufacturing_edge_banding.py").is_file())

    def test_geometric_rules_live_in_their_owning_stages(self) -> None:
        intent_package = (
            SKILLS_ROOT
            / "furniture-design-intent"
            / "scripts"
            / "furniture_design_intent"
        )
        panel_package = (
            SKILLS_ROOT
            / "furniture-panel-planning"
            / "scripts"
            / "furniture_panel_planning"
        )
        self.assertFalse((intent_package / "design_spec.py").exists())
        self.assertFalse((intent_package / "translation.py").exists())

        input_adapter = (
            SKILLS_ROOT
            / "furniture-cad"
            / "scripts"
            / "furniture_workflow"
            / "input_adapter.py"
        )
        self.assertTrue(input_adapter.is_file())

        layout_validation = (
            SKILLS_ROOT
            / "furniture-layout"
            / "scripts"
            / "furniture_layout"
            / "validation.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("NON_POSITIVE_INTERNAL_CLEARANCE", layout_validation)
        self.assertNotIn("INTERNAL_CLEARANCE_MISMATCH", layout_validation)

        panel_validation = (
            SKILLS_ROOT
            / "furniture-panel-planning"
            / "scripts"
            / "furniture_panel_planning"
            / "validation.py"
        ).read_text(encoding="utf-8")
        panel_spec = (panel_package / "panel_spec.py").read_text(encoding="utf-8")
        self.assertIn("def resolve_back_mount(", panel_spec)
        self.assertIn("NON_POSITIVE_INTERNAL_CLEARANCE", panel_validation)
        self.assertIn("STRUCTURE_GEOMETRY_MISMATCH", panel_validation)
        self.assertIn(
            "NON_POSITIVE_TOE_KICK_SUPPORT_SPACING",
            panel_validation,
        )
        self.assertIn("BACK_RAIL_COUNT_MISMATCH", panel_validation)

        manufacturing_validation = (
            SKILLS_ROOT
            / "furniture-manufacturing"
            / "scripts"
            / "furniture_manufacturing"
            / "validation.py"
        ).read_text(encoding="utf-8")
        self.assertIn("GROOVE_OUTSIDE_TARGET", manufacturing_validation)
        # 五金专属几何规则随各 Connector 自洽（仍属制造阶段运行时）
        hinge_connector = (
            SKILLS_ROOT
            / "furniture-manufacturing"
            / "scripts"
            / "furniture_manufacturing"
            / "connectors"
            / "hinge.py"
        ).read_text(encoding="utf-8")
        self.assertIn("HINGE_HOLE_OUTSIDE_DOOR", hinge_connector)

        feature_tree_emitter = (
            SKILLS_ROOT
            / "furniture-feature-tree"
            / "scripts"
            / "furniture_feature_tree"
            / "feature_tree_emitter.py"
        ).read_text(encoding="utf-8")
        self.assertIn("_validate_operation_bounds", feature_tree_emitter)

    def test_back_mount_contract_is_synchronized_across_stage_skills(
        self,
    ) -> None:
        expected_terms = {
            ".agents/skills/furniture-agent/SKILL.md": (
                "back_mount",
                "从板件阶段开始",
            ),
            "domain/skills/furniture-panel-planning/SKILL.md": (
                "back_mount",
                "背拉条",
            ),
            "domain/skills/furniture-manufacturing/SKILL.md": (
                "groove",
                "背拉条",
            ),
            "domain/skills/furniture-manufacturing/references/runtime-map.md": (
                "BackMountConnector",
                "generate_holes_for_panels",
            ),
            "domain/skills/furniture-feature-tree/SKILL.md": (
                "insert/cover",
                "drilled-holes",
            ),
            "domain/skills/furniture-cad/SKILL.md": (
                "back_mount/back_rail_height",
                "drilled-holes",
            ),
            (
                "domain/skills/furniture-delivery-validation/"
                "references/delivery-checklist.md"
            ): (
                "back_mount",
                "五金数量与主孔、配合孔数量一致",
            ),
        }

        for relative_path, terms in expected_terms.items():
            path = WORKSPACE_ROOT / relative_path
            text = path.read_text(encoding="utf-8")
            for term in terms:
                self.assertIn(term, text, path)

        for relative_path in (
            "domain/skills/furniture-design-intent/SKILL.md",
            "domain/skills/furniture-layout/SKILL.md",
        ):
            text = (WORKSPACE_ROOT / relative_path).read_text(encoding="utf-8")
            self.assertNotIn("auto/groove/insert/cover", text)

    def test_corrected_stage_boundaries_match_runtime_ownership(self) -> None:
        expected_terms = {
            "domain/skills/furniture-design-intent/SKILL.md": (
                "草稿尺寸可为 `null`",
                "furniture_type",
                "成品外包络",
            ),
            "domain/skills/furniture-layout/SKILL.md": (
                "door_count",
                "不参与房间定位",
                "左后下落地角",
            ),
            "domain/skills/furniture-manufacturing/SKILL.md": (
                "readiness=preliminary/accepted/factory_ready",
                "FurnitureOrchestrator.run_next()",
                "references/runtime-map.md",
            ),
            "domain/skills/furniture-delivery-validation/SKILL.md": (
                "前五个串联阶段",
                "不解析 STEP 几何",
                "未执行",
            ),
        }
        for relative_path, terms in expected_terms.items():
            path = WORKSPACE_ROOT / relative_path
            text = path.read_text(encoding="utf-8")
            for term in terms:
                self.assertIn(term, text, path)


if __name__ == "__main__":
    unittest.main()
````

## File: domain/skills/furniture-manufacturing/scripts/furniture_manufacturing/connectors/hinge.py
````python
"""铰链连接件 — 门板杯孔打孔。

铰链杯孔从门板内侧面钻入，`direction` 存钻入方向（往板内，
= inner_face 的反向）。内侧面方向由 panel.inner_face 提供，
不再硬编码 "+y"。
"""

from typing import Any, Dict, List, Mapping
from furniture_manufacturing.connectors.base import Connector, HoleSpec, _opposite
from furniture_manufacturing.manufacturing_models import HardwareRecord, MachiningOperation, PanelRecord


class HingeConnector(Connector):
    """铰链连接件：在门板内侧面钻铰链杯孔。"""

    name = "液压缓冲铰链"
    hole_type_for_json = "hinge"
    catalog_entry = "hinges"
    rules_section = "hinge_drilling"
    hole_legend = {
        "hinge": {"color": "#4A90D9", "label": "铰链杯孔 35mm", "glb_group": "铰链孔位"},
    }

    def match(self, panels: List[PanelRecord]) -> Dict[str, Any]:
        """匹配所有门板及相关规则。"""
        doors = [p for p in panels if p.panel_type == "door"]
        rules = self.rules.get(self.rules_section, {}) if self.rules_section else {}
        catalog = self.catalog.get(self.catalog_entry, {})
        return {"doors": doors, "rules": rules, "catalog": catalog}

    def generate_holes(self, panel: PanelRecord) -> List[HoleSpec]:
        """在一块门板上生成铰链杯孔。

        杯孔沿门板高度方向分布，从内侧面钻入；direction 为钻入方向
        （inner_face 的反向）。
        """
        result: List[HoleSpec] = []
        if panel.panel_type != "door":
            return result
        rules = self.rules.get(self.rules_section, {}) if self.rules_section else {}
        entry = self._resolve_entry(self.catalog.get(self.catalog_entry, {}), {})
        count, top_offset, bottom_offset = self._hinge_count(panel.size_z, rules)
        positions = self._distribute(panel.size_z, count, top_offset, bottom_offset)
        hole = entry.get("hole", {}) or {}
        edge_offset = float(hole.get("edge_offset_mm", 5))
        cup_diameter = float(hole.get("diameter_mm", 35))
        cup_depth = float(hole.get("depth_mm", 13))
        # 杯孔中心距门边 = 边距 + 杯孔半径
        cup_center_from_edge = edge_offset + cup_diameter / 2
        inner = panel.inner_face or "+y"  # default for backward compat

        # 铰链侧：优先使用显式字段，否则根据 X 位置推断
        hinge_side = panel.door_hinge_side
        if hinge_side == "left":
            x_local = cup_center_from_edge
        elif hinge_side == "right":
            x_local = panel.size_x - cup_center_from_edge
        elif panel.pos_x < panel.size_x:
            x_local = cup_center_from_edge  # 兜底：X 位置靠左 → 左铰链
        else:
            x_local = panel.size_x - cup_center_from_edge  # 兜底：X 位置靠右 → 右铰链

        # Drill direction = 钻入方向（往板内）：杯孔从内侧面钻入，
        # 钻入方向 = inner_face 的反向（direction 语义统一约定，见 coordinate-naming.md）。
        cup_dir = _opposite(inner)

        for y_local in positions:
            hole = self._make_hole(
                panel=panel,
                x_local=x_local,
                y_local=0.0,
                z_local=y_local,
                diameter=cup_diameter,
                depth=cup_depth,
                direction=cup_dir,
                note="从门板内侧面钻入的铰链杯孔",
            )
            result.append(hole)

        return result

    def _make_hole(
        self,
        panel: PanelRecord,
        x_local: float,
        y_local: float,
        z_local: float,
        diameter: float,
        depth: float,
        direction: str,
        note: str,
    ) -> HoleSpec:
        """在面板 inner_face 上打杯孔。

        孔位先在面板局部坐标定义（局部为唯一真源），
        再由 to_global 派生世界坐标（当前轴对齐：仅平移）。
        """
        inner = panel.inner_face or "+y"
        face_axis = inner[1] if len(inner) >= 2 else "y"

        # 孔中心落在 inner_face 上：该轴局部坐标 = 面位置(0 或该轴尺寸)
        origin = {"x": panel.pos_x, "y": panel.pos_y, "z": panel.pos_z}[face_axis]
        face_local = panel.face_position(inner) - origin

        local = {"x": x_local, "y": y_local, "z": z_local}
        local[face_axis] = face_local

        x_global, y_global, z_global = panel.to_global(
            local["x"], local["y"], local["z"]
        )

        return HoleSpec(
            hole_type="hinge",
            panel_label=panel.label,
            x_global=x_global,
            y_global=y_global,
            z_global=z_global,
            x_local=local["x"],
            y_local=local["y"],
            z_local=local["z"],
            diameter=diameter,
            depth=depth,
            direction=direction,
            is_face_hole=True,
            note=note,
        )

    def _hinge_count(self, door_h: float, rules: Dict[str, Any]) -> tuple:
        """根据门板高度确定铰链数量和上下边距。"""
        for entry in rules.get("count_by_door_height", []):
            if door_h <= entry["max_height_mm"]:
                return entry.get("count", 2), entry.get("top_offset_mm", 100), entry.get("bottom_offset_mm", 100)
        return 2, 100, 100

    def _distribute(self, total: float, count: int, top: float, bottom: float) -> List[float]:
        """在总长度内均匀分布 count 个位置。"""
        if count <= 1:
            return [total / 2]
        usable = total - top - bottom
        spacing = usable / (count - 1)
        return [top + i * spacing for i in range(count)]

    def boms(
        self,
        panels: List[PanelRecord],
        *,
        options: Mapping[str, Any] | None = None,
    ) -> List[HardwareRecord]:
        """生成铰链 BOM 清单。

        条目与品牌由确认选择（options[本 catalog_entry]）决定；未选择时
        仅当目录唯一才返回，否则抛错——不再按固定规格静默挑选。
        """
        doors = [p for p in panels if p.panel_type == "door"]
        if not doors:
            return []
        catalog = self.catalog.get(self.catalog_entry, {})
        opts = self._connector_options(options)
        entry = self._resolve_entry(catalog, opts)
        brand = self.resolve_brand(entry.get("brands", []), opts.get("brand"))
        records: List[HardwareRecord] = []
        for door in doors:
            count, _, _ = self._hinge_count(
                door.size_z, self.rules.get(self.rules_section, {})
            )
            records.append(HardwareRecord(
                name=self.name,
                spec=f"{brand['name']} {brand['model']} {entry.get('angle', 100)}°",
                quantity=count, brand=brand.get("name", "默认"), model=brand.get("model", ""),
                note=f"门板: {door.name}"))
        return records

    def _connector_options(self, options: Mapping[str, Any] | None) -> Dict[str, Any]:
        opts = (options or {}).get(self.catalog_entry, {})
        return dict(opts) if isinstance(opts, Mapping) else {}

    def _resolve_entry(
        self,
        catalog: Dict[str, Any],
        opts: Dict[str, Any],
    ) -> Dict[str, Any]:
        """返回唯一铰链条目；歧义时抛错，不按固定规格静默筛选。"""
        entries = list(catalog.items())
        if not entries:
            raise ValueError("hinge catalog is empty")
        filters = {k: opts[k] for k in ("angle",) if k in opts}
        if filters:
            entries = [
                (name, spec) for name, spec in entries
                if all(spec.get(k) == v for k, v in filters.items())
            ]
            if not entries:
                raise ValueError(f"no hinge entry matches {filters!r}")
        if len(entries) == 1:
            return entries[0][1]
        raise ValueError("multiple hinge entries require an explicit selection")

    def validate(
        self,
        report: Any,
        panels: List[PanelRecord],
        hardware: List[HardwareRecord],
        drilled: Dict[str, Any],
    ) -> None:
        """铰链专属校验：杯孔在门包络内、从内侧面钻入、深度≤门厚、侧别正确、孔数=BOM 数。"""
        drilled_by_panel = {
            panel["label"]: panel["holes"] for panel in drilled["panels"]
        }
        door_panels = [p for p in panels if p.panel_type == "door"]
        # 门厚适用范围校验：door_thickness_mm = [min, max]，仅目录唯一条目时适用
        entries = list(self.catalog.get(self.catalog_entry, {}).values())
        if len(entries) == 1:
            door_range = entries[0].get("door_thickness_mm")
            if isinstance(door_range, (list, tuple)) and len(door_range) == 2:
                lo, hi = float(door_range[0]), float(door_range[1])
                for panel in door_panels:
                    if panel.thickness < lo - 1e-6 or panel.thickness > hi + 1e-6:
                        report.add_error(
                            "HINGE_DOOR_THICKNESS_OUT_OF_RANGE",
                            f"{panel.label} door thickness {panel.thickness:g}mm is outside hinge range [{lo:g}, {hi:g}]mm",
                            panel.label,
                        )
        expected_hinge_count = sum(
            item.quantity for item in hardware if item.name == self.name
        )
        hinge_holes = [
            (panel, hole)
            for panel in door_panels
            for hole in drilled_by_panel.get(panel.label, [])
            if hole["hole_type"] == "hinge"
        ]
        for panel in door_panels:
            panel_hinges = [
                hole for hole in drilled_by_panel.get(panel.label, [])
                if hole["hole_type"] == "hinge"
            ]
            if not panel_hinges:
                report.add_error(
                    "MISSING_HINGE_HOLES",
                    f"{panel.label} requires hinge cup holes",
                    panel.label,
                )
            for hole in panel_hinges:
                radius = hole["diameter"] / 2
                if (
                    hole["diameter"] <= 0
                    or hole["local_x"] - radius < -1e-6
                    or hole["local_x"] + radius > panel.size_x + 1e-6
                    or hole["local_z"] - radius < -1e-6
                    or hole["local_z"] + radius > panel.size_z + 1e-6
                ):
                    report.add_error(
                        "HINGE_HOLE_OUTSIDE_DOOR",
                        f"hinge cup on {panel.label} exceeds the door envelope",
                        panel.label,
                    )
                expected_face_coordinate = (
                    panel.size_y if panel.inner_face == "+y" else 0.0
                )
                if (
                    panel.inner_face not in {"+y", "-y"}
                    or abs(hole["local_y"] - expected_face_coordinate) > 1e-6
                    or hole["direction"] != _opposite(panel.inner_face)
                    or not hole["is_face_hole"]
                ):
                    report.add_error(
                        "HINGE_HOLE_FACE_MISMATCH",
                        f"hinge cup on {panel.label} must enter from its inner face",
                        panel.label,
                    )
                if hole["depth"] <= 0 or hole["depth"] > panel.size_y + 1e-6:
                    report.add_error(
                        "INVALID_HINGE_HOLE_DEPTH",
                        f"hinge cup depth on {panel.label} exceeds door thickness",
                        panel.label,
                    )
                if (
                    panel.door_hinge_side == "left"
                    and hole["local_x"] >= panel.size_x / 2
                ) or (
                    panel.door_hinge_side == "right"
                    and hole["local_x"] <= panel.size_x / 2
                ):
                    report.add_error(
                        "HINGE_SIDE_MISMATCH",
                        f"hinge cup on {panel.label} is on the wrong door edge",
                        panel.label,
                    )
        if len(hinge_holes) != expected_hinge_count:
            report.add_error(
                "HINGE_HARDWARE_COUNT_MISMATCH",
                "hinge cup count must match hinge hardware quantity",
                "hardware",
            )

    def machining_operations(self, panel: PanelRecord) -> List[MachiningOperation]:
        """生成铰链杯孔的 cut_box 加工指令。

        根据钻入方向将 cut_box 放置在孔位入口处，使其沿钻入方向
        展开，而不是跑到板件后方（direction 已是钻入方向语义）。
        """
        ops: List[MachiningOperation] = []
        for hole in self.generate_holes(panel):
            d = hole.diameter
            # 将 cut_box 放在孔位入口处，沿打孔方向展开
            if hole.direction == "+y":
                pos_y = hole.y_global
            elif hole.direction == "-y":
                pos_y = hole.y_global - hole.depth
            else:
                pos_y = hole.y_global - hole.depth
            ops.append(MachiningOperation(
                id=f"hinge_{panel.label}_{hole.z_local:.0f}",
                operation_type="cut_box", target_panel=panel.label,
                size_x=d, size_y=hole.depth, size_z=d,
                pos_x=hole.x_global - d / 2, pos_y=pos_y,
                pos_z=hole.z_global - d / 2,
                note=f"铰链杯孔 φ{d:g}"))
        return ops
````

## File: domain/skills/furniture-manufacturing/scripts/furniture_manufacturing/connectors/shelf.py
````python
"""活动层板连接件：二合一与隔板钉。

两者都服务 movable_shelf（活动层板），用于层板可拆卸 / 小范围调整：
- 二合一（TwoInOneConnector）：偏心轮装在层板底面、连接杆打在侧板，有固定作用；
- 隔板钉（ShelfPinConnector）：单钉打在侧板，单纯架住层板。

活动层板由 spec.shelves 里 `shelf_type="movable"` 的层板生成；连接方式由
`movable_shelf_connector` 选择（two_in_one / shelf_pin）。下列几何定位
（前后排、高度对齐、层板侧边投影）为软件暂定，投产前确认。
"""

from typing import Any, Dict, List, Mapping

from furniture_manufacturing.connectors.base import Connector, HoleSpec, _opposite
from furniture_manufacturing.manufacturing_models import HardwareRecord, MachiningOperation, PanelRecord


def _shelf_positions(length: float) -> List[float]:
    """沿层板深度（前→后）分布连接点，返回相对前边的距离列表。"""
    if length <= 192:
        return [32.0, length - 32.0]
    if length <= 550:
        return [64.0, length - 64.0]
    holes = [64.0, length / 2, length - 64.0]
    if length > 1100:
        usable = length - 128
        extra = int((length - 1100) / 550) + 1
        spacing = usable / (extra + 1)
        for i in range(1, extra + 1):
            holes.append(64.0 + i * spacing)
    return sorted(set(holes))


def _movable_shelves(panels: List[PanelRecord]) -> List[PanelRecord]:
    return [p for p in panels if p.panel_type == "movable_shelf"]


def _selected_shelves(panels: List[PanelRecord], connector_key: str) -> List[PanelRecord]:
    """只取选中该连接方式的活动层板（movable_shelf_connector == connector_key）。"""
    return [p for p in _movable_shelves(panels) if p.movable_shelf_connector == connector_key]


def _side_faces(panels: List[PanelRecord]) -> List[tuple]:
    """侧板内侧面定位：返回 (side, inner_face, x_local, 钻入方向)。"""
    out = []
    for side in [p for p in panels if p.panel_type == "side"]:
        inner = side.inner_face or ""
        x_local = side.size_x if inner in ("+x", "") else 0.0
        out.append((side, inner, x_local, _opposite(inner) if inner else "-x"))
    return out


class TwoInOneConnector(Connector):
    """二合一连接件：一套 = 偏心轮 + 连接杆（固定塑料件并入连接杆）。

    偏心轮孔打在层板底面（从下往上钻 +z），圆心距层板朝向侧板的侧边 edge_offset_mm；
    连接杆孔打在侧板内侧面，与偏心轮孔同排同位。
    """

    name = "二合一连接件"
    hole_type_for_json = "two_in_one"
    catalog_entry = "two_in_one"
    rules_section = None
    hole_legend = {
        "two_in_one_cam": {"color": "#27AE60", "label": "二合一偏心轮孔 12mm", "glb_group": "二合一偏心轮孔"},
        "two_in_one_rod": {"color": "#2E86C1", "label": "二合一连接杆孔 5mm", "glb_group": "二合一连接杆孔"},
    }

    def match(self, panels: List[PanelRecord]) -> Dict[str, Any]:
        return {"shelves": _movable_shelves(panels), "sides": [s for s, *_ in _side_faces(panels)]}

    def generate_holes(self, panel: PanelRecord) -> List[HoleSpec]:
        return []

    def generate_holes_for_panels(self, panels: List[PanelRecord]) -> List[HoleSpec]:
        spec = self.catalog.get(self.catalog_entry, {}).get("standard", {})
        cam_spec = spec.get("cam", {})
        cam_hole = cam_spec.get("hole", {})
        rod_hole = spec.get("rod", {}).get("hole", {})
        cam_d = float(cam_hole.get("diameter_mm", 12))
        cam_depth = float(cam_hole.get("depth_mm", 13.5))
        cam_edge = float(cam_hole.get("edge_offset_mm", 4.5))
        rod_d = float(rod_hole.get("diameter_mm", 5))
        rod_depth = float(rod_hole.get("depth_mm", 10))
        rod_axis_offset = float(cam_spec.get("rod_axis_to_cam_face_mm", 9))

        result: List[HoleSpec] = []
        for shelf in _selected_shelves(panels, self.catalog_entry):
            for side, inner, side_x, rod_dir in _side_faces(panels):
                for depth in _shelf_positions(shelf.drill_length):
                    y_local = side.size_y - depth
                    # 连接杆孔：侧板内侧面水平钻入；杆轴 = 层板底面 + rod_axis_to_cam_face_mm
                    z_local = (shelf.pos_z + rod_axis_offset) - side.pos_z
                    sx, sy, sz = side.to_global(side_x, y_local, z_local)
                    result.append(HoleSpec(
                        hole_type="two_in_one_rod", panel_label=side.label,
                        x_global=sx, y_global=sy, z_global=sz,
                        x_local=side_x, y_local=y_local, z_local=z_local,
                        diameter=rod_d, depth=rod_depth, direction=rod_dir,
                        is_face_hole=True, note=f"二合一连接杆孔({shelf.name})"))

                    # 偏心轮孔：层板底面从下往上钻；圆心距朝向侧板的侧边 cam_edge（待确认）
                    cam_x = cam_edge if inner in ("+x", "") else shelf.size_x - cam_edge
                    cam_y = depth
                    cam_z = 0.0
                    cx, cy, cz = shelf.to_global(cam_x, cam_y, cam_z)
                    result.append(HoleSpec(
                        hole_type="two_in_one_cam", panel_label=shelf.label,
                        x_global=cx, y_global=cy, z_global=cz,
                        x_local=cam_x, y_local=cam_y, z_local=cam_z,
                        diameter=cam_d, depth=cam_depth, direction="+z",
                        is_face_hole=True, note=f"二合一偏心轮孔({shelf.name})"))
        return result

    def boms(
        self,
        panels: List[PanelRecord],
        *,
        options: Mapping[str, Any] | None = None,
    ) -> List[HardwareRecord]:
        shelves = _selected_shelves(panels, self.catalog_entry)
        if not shelves:
            return []
        spec = self.catalog.get(self.catalog_entry, {}).get("standard", {})
        opts = (options or {}).get(self.catalog_entry, {})
        opts = dict(opts) if isinstance(opts, Mapping) else {}
        brand = self.resolve_brand(spec.get("brands", []), opts.get("brand"))
        total = sum(len(_shelf_positions(p.drill_length)) * 2 for p in shelves)
        return [HardwareRecord(
            name=self.name,
            spec="偏心轮+连接杆（实物规格待确认）",
            quantity=total, unit="套",
            brand=brand.get("name", "默认"), model=brand.get("model", "EYJ-01"))]

    def machining_operations(self, panel: PanelRecord) -> List[MachiningOperation]:
        return []


class ShelfPinConnector(Connector):
    """隔板钉：单钉打在侧板，单纯架住层板。

    钉孔打在侧板内侧面（水平钻入），钉孔中心比层板底面低 shelf_bottom_offset_mm
    （= 钉半径 2.5mm），层板架在钉上。
    """

    name = "隔板钉"
    hole_type_for_json = "shelf_pin"
    catalog_entry = "shelf_pin"
    rules_section = None
    hole_legend = {
        "shelf_pin": {"color": "#00A86B", "label": "隔板钉孔 5mm", "glb_group": "隔板钉孔"},
    }

    def match(self, panels: List[PanelRecord]) -> Dict[str, Any]:
        return {"shelves": _movable_shelves(panels), "sides": [s for s, *_ in _side_faces(panels)]}

    def generate_holes(self, panel: PanelRecord) -> List[HoleSpec]:
        return []

    def generate_holes_for_panels(self, panels: List[PanelRecord]) -> List[HoleSpec]:
        spec = self.catalog.get(self.catalog_entry, {}).get("standard", {})
        pin = spec.get("pin", {})
        pin_hole = pin.get("hole", {})
        pin_d = float(pin_hole.get("diameter_mm", 5))
        pin_depth = float(pin_hole.get("depth_mm", 9))
        bottom_offset = float(pin.get("shelf_bottom_offset_mm", 2.5))

        result: List[HoleSpec] = []
        for shelf in _selected_shelves(panels, self.catalog_entry):
            for side, _inner, side_x, drill_dir in _side_faces(panels):
                # 钉孔中心 = 层板底面 - bottom_offset（层板架在钉上）
                z_local = (shelf.pos_z - bottom_offset) - side.pos_z
                for depth in _shelf_positions(shelf.drill_length):
                    y_local = side.size_y - depth
                    sx, sy, sz = side.to_global(side_x, y_local, z_local)
                    result.append(HoleSpec(
                        hole_type="shelf_pin", panel_label=side.label,
                        x_global=sx, y_global=sy, z_global=sz,
                        x_local=side_x, y_local=y_local, z_local=z_local,
                        diameter=pin_d, depth=pin_depth, direction=drill_dir,
                        is_face_hole=True, note=f"隔板钉孔({shelf.name})"))
        return result

    def boms(
        self,
        panels: List[PanelRecord],
        *,
        options: Mapping[str, Any] | None = None,
    ) -> List[HardwareRecord]:
        shelves = _selected_shelves(panels, self.catalog_entry)
        if not shelves:
            return []
        spec = self.catalog.get(self.catalog_entry, {}).get("standard", {})
        opts = (options or {}).get(self.catalog_entry, {})
        opts = dict(opts) if isinstance(opts, Mapping) else {}
        brand = self.resolve_brand(spec.get("brands", []), opts.get("brand"))
        total = sum(len(_shelf_positions(p.drill_length)) * 2 for p in shelves)
        return [HardwareRecord(
            name=self.name,
            spec="钉（实物规格待确认）",
            quantity=total, unit="个",
            brand=brand.get("name", "默认"), model=brand.get("model", "GBD-01"))]

    def machining_operations(self, panel: PanelRecord) -> List[MachiningOperation]:
        return []
````

## File: domain/skills/furniture-manufacturing/scripts/furniture_manufacturing/connectors/trinity.py
````python
"""三合一连接件（偏心轮 + 连接杆 + 预埋螺母）。

不再按 panel_type 名称判断角色。改用连接拓扑（PanelJoint）：
- female（面接触方）→ 预埋螺母孔，打在板面上
- male  （边接触方）→ 连接杆孔 + 偏心轮孔

每块板的 joints 字段由 topology_solver 在求解阶段填充。
"""

from typing import Any, Dict, List, Mapping, Set

from furniture_manufacturing.connectors.base import Connector, HoleSpec, _opposite
from furniture_manufacturing.manufacturing_models import HardwareRecord, MachiningOperation, PanelRecord


# ── Joint helpers ──────────────────────────────────────────────────

def _joints_of(panel: PanelRecord) -> list:
    """面板参与的所有连接（PanelJoint 列表）。"""
    return list(panel.joints) if panel.joints else []


def _is_female(panel: PanelRecord) -> bool:
    """该板是否有面被其他板的端面顶着（面接触方 → 预埋螺母）。"""
    return any(j.female_id == panel.label for j in _joints_of(panel))


def _is_male(panel: PanelRecord) -> bool:
    """该板是否有端面顶着其他板的面（边接触方 → 连接杆+偏心轮）。"""
    return any(j.male_id == panel.label for j in _joints_of(panel))


def _trinity_female(panel: PanelRecord) -> bool:
    """x 轴方向、带 cam 的面接触方（侧板/隔板）。

    优先从连接拓扑推导；无连接拓扑时退回 panel_type 判断。
    male_has_cam 必须为真（与 _trinity_male/_female_holes 一致）：
    否则抽屉侧板等无 cam 的板件会被误判为三合一母件。
    """
    if panel.joints:
        return any(
            j.female_id == panel.label and j.face[1] == "x" and j.male_has_cam
            for j in _joints_of(panel)
        )
    # fallback: no joint topology available
    return panel.panel_type in ("side", "divider")


def _trinity_male(panel: PanelRecord) -> bool:
    """x 轴方向的边接触方（横板），端面在 x 轴且 male_has_cam。

    优先从连接拓扑推导；无连接拓扑时退回 panel_type 判断。
    """
    if panel.joints:
        return any(
            j.male_id == panel.label and j.edge_axis == "x" and j.male_has_cam
            for j in _joints_of(panel)
        )
    # fallback: no joint topology available
    return panel.panel_type in ("top", "bottom", "fixed_shelf")


def _gather_joints(panels: list[PanelRecord]) -> list:
    """收集所有面板的连接拓扑（去重）。"""
    seen: Set[tuple] = set()
    result = []
    for p in panels:
        for j in _joints_of(p):
            key = (j.female_id, j.male_id)
            if key not in seen:
                seen.add(key)
                result.append(j)
    return result


def _trinity_joints(panels: list[PanelRecord]) -> list:
    """筛选三合一相关的连接（x 轴方向，male_has_cam）。"""
    return [
        j for j in _gather_joints(panels)
        if j.face[1] == "x" and j.edge_axis == "x" and j.male_has_cam
    ]


def _male_edge_signs(panel: PanelRecord) -> Set[int]:
    """male 面板的 x 轴端面连接方向（-1=左，+1=右）。

    优先从连接拓扑推导；无连接拓扑时返回两端。
    """
    if panel.joints:
        signs = {
            j.edge_sign for j in _joints_of(panel)
            if j.male_id == panel.label and j.edge_axis == "x"
        }
        if signs:
            return signs
    # fallback: no joint topology → assume both ends
    return {-1, 1}


def _other_axis(a: str, t: str) -> str:
    """连接平面内除边轴 a 与 cam 面轴 t 之外的第三轴。"""
    for axis in ("x", "y", "z"):
        if axis != a and axis != t:
            return axis
    return "y"


def _is_trinity_joint(joint: Any, by_label: Dict[str, PanelRecord]) -> bool:
    """某 joint 是否是三合一连接。

    抽屉盒是滑动子装配，内部 x/y 轴接触均为连接（前/后/底↔侧）；
    柜体结构连接仅 x 轴（侧板↔横板）——背板等 y 向接触（如层板后
    端面搁在背板前面）是接触不是连接，不生成三合一。
    """
    if not joint.male_has_cam:
        return False
    female = by_label[joint.female_id]
    if "drawer" in female.panel_type:
        return joint.edge_axis in ("x", "y")
    return joint.edge_axis == "x"


class TrinityConnector(Connector):
    """三合一连接件。

    偏心轮位于“边接触方”板件的板面（cam_face），从可操作面钻入。
    连接杆从“边接触方”板件的端面穿入，指向“面接触方”板件的预埋螺母。
    预埋螺母在“面接触方”板件的板面上，朝柜内方向钻入。

    深度方向：前后双排，分别距前/后边 first_hole_mm（默认 64mm）。
    偏心轮：沿连接杆方向(x)距端面 cam.hole.edge_offset_mm（33.5mm），深度方向与连接杆同排。
    """

    name = "三合一连接件"
    hole_type_for_json = "three_in_one"
    catalog_entry = "three_in_one"
    rules_section = "system_32_drilling"
    hole_legend = {
        "three_in_one_cam": {"color": "#FF6B35", "label": "三合一偏心轮孔 12mm", "glb_group": "偏心轮孔"},
        "three_in_one_rod": {"color": "#FF4500", "label": "三合一连接杆端孔 8mm", "glb_group": "连接杆孔"},
        "three_in_one_nut": {"color": "#D95F02", "label": "三合一预埋螺母孔 10mm", "glb_group": "预埋螺母孔"},
    }

    def match(self, panels: List[PanelRecord]) -> Dict[str, Any]:
        """匹配 — 用连接拓扑而非 panel_type 名称。"""
        entry = self.catalog.get(self.catalog_entry, {})
        first_key = next(iter(entry)) if entry else None
        spec = entry.get(first_key, {}) if first_key else {}
        rules = self.rules.get(self.rules_section, {}) if self.rules_section else {}

        female_panels = [p for p in panels if _trinity_female(p)]
        male_panels = [p for p in panels if _trinity_male(p)]

        return {
            "panels": female_panels + male_panels,
            "female": female_panels,
            "male": male_panels,
            "spec": spec,
            "rules": rules,
        }

    # ── single-panel holes ──────────────────────────────────────

    def generate_holes(self, panel: PanelRecord) -> List[HoleSpec]:
        """在一块板件上生成三合一孔位。

        female（面接触方）→ 预埋螺母孔
        male  （边接触方）→ 连接杆孔（端面）+ 偏心轮孔（cam_face）
        """
        result: List[HoleSpec] = []
        matched = self.match([panel])
        rules = matched.get("rules", {})
        spec = matched.get("spec", {})
        cam_spec = spec.get("cam", {})
        rod_spec = spec.get("rod", {})
        nut_spec = spec.get("nut", {})
        z_positions = self._system_32_positions(panel, rules)
        nut_first = float(rules.get("first_hole_mm", 64))
        nut_last  = float(rules.get("last_hole_mm", 64))
        cam_offset = float(cam_spec.get("hole", {}).get("edge_offset_mm", 33.5))

        if _trinity_female(panel):
            result.extend(self._female_holes(
                panel, z_positions, nut_first, nut_last, nut_spec, cam_spec))
        if _trinity_male(panel):
            result.extend(self._male_holes(
                panel, nut_first, nut_last, rod_spec, cam_spec, cam_offset))

        return result

    def _female_holes(
        self, panel: PanelRecord, z_positions: List[float],
        nut_first: float, nut_last: float, nut_spec: Dict[str, Any],
        cam_spec: Dict[str, Any],
    ) -> List[HoleSpec]:
        """竖板（面接触方）→ 预埋螺母打在 inner_face 上。

        本路径仅服务无连接拓扑的旧数据：系统-32 全高排钻（1:1:1 的
        轴无关成对孔由 generate_holes_for_panels 的连接驱动逻辑处理）。

        孔位先在面板局部坐标定义（局部为唯一真源），世界坐标由 to_global 派生。
        """
        result: List[HoleSpec] = []
        n_diam = float(nut_spec.get("hole", {}).get("diameter_mm", 10))
        n_depth = float(nut_spec.get("hole", {}).get("depth_mm", 11))
        inner = panel.inner_face or ""
        nut_dir = _opposite(inner)

        # 螺母孔打在 inner_face 上：用几何接口 face_position 定位（面在 x 轴），
        # 折算成板件局部坐标（局部为真源，世界由 to_global 派生）。
        face = inner if inner in ("+x", "-x") else "+x"
        x_local = panel.face_position(face) - panel.pos_x

        # 本路径仅服务无连接拓扑的旧数据（有拓扑的连接由 generate_holes_for_panels
        # 的连接驱动逻辑处理）：系统-32 全高排钻（z_positions 已是局部坐标）。
        z_locals = list(z_positions)

        for z_local in z_locals:
            for y_local in [nut_first, panel.size_y - nut_last]:
                x_global, y_global, z_global = panel.to_global(
                    x_local, y_local, z_local
                )
                result.append(HoleSpec(
                    hole_type="three_in_one_nut", panel_label=panel.label,
                    x_global=x_global,
                    y_global=y_global,
                    z_global=z_global,
                    x_local=x_local, y_local=y_local,
                    z_local=z_local,
                    diameter=n_diam, depth=n_depth, direction=nut_dir,
                    is_face_hole=True, note="预埋螺母孔"))
        return result

    def _male_holes(
        self, panel: PanelRecord, nut_first: float, nut_last: float,
        rod_spec: Dict[str, Any], cam_spec: Dict[str, Any], cam_offset: float,
    ) -> List[HoleSpec]:
        """横板（边接触方）→ 连接杆孔 + 偏心轮孔。

        根据 panel.joints 确定哪些端面有连接：
        edge_sign == -1 → 左端，+1 → 右端。只在实际有连接的端面生成孔位。

        孔位先在面板局部坐标定义（局部为唯一真源），世界坐标由 to_global 派生。
        """
        result: List[HoleSpec] = []
        r_diam = float(rod_spec.get("hole", {}).get("diameter_mm", 8))
        r_depth = float(rod_spec.get("hole", {}).get("depth_mm", 33))
        w_diam = float(cam_spec.get("hole", {}).get("diameter_mm", 12))
        w_depth = float(cam_spec.get("hole", {}).get("depth_mm", 13.5))
        # 连接杆轴线高度 = cam_face ± 偏心距(五金固定参数)，与板厚无关。
        rod_axis_offset = float(cam_spec.get("rod_axis_to_cam_face_mm", 9))
        cam = panel.cam_face or ""

        # cam_face 是偏心轮的可操作面：孔应落在该面所在的局部坐标。
        # cam == "+z" → 顶面(z_local = size_z)；cam == "-z" → 底面(z_local = 0)。
        if cam == "+z":
            cam_zl = panel.size_z
            rod_zl = panel.size_z - rod_axis_offset
        elif cam == "-z":
            cam_zl = 0.0
            rod_zl = rod_axis_offset
        else:
            cam_zl = panel.size_z
            cam = "+z"
            rod_zl = panel.size_z - rod_axis_offset

        # direction 统一为钻入方向（往板内）：轮孔从 cam_face 钻入，
        # 钻入方向 = cam_face 的反向（direction 语义统一约定，见 coordinate-naming.md）。
        cam_dir = _opposite(cam)

        rod_y_offsets = [nut_first, panel.size_y - nut_last]

        edge_signs = _male_edge_signs(panel)
        for sign in edge_signs:
            if sign == -1:
                x_local = 0.0
                rod_sign = "+x"
                # 偏心轮圆心距端面 cam_offset，沿连接杆伸入方向(向板内)
                cam_x_local = cam_offset
            else:
                x_local = panel.size_x
                rod_sign = "-x"
                cam_x_local = panel.size_x - cam_offset

            # 与旧实现保持相同的发射顺序：先全部连接杆孔，再全部偏心轮孔
            for y_offset in rod_y_offsets:
                rod_x, rod_y, rod_z = panel.to_global(x_local, y_offset, rod_zl)
                result.append(HoleSpec(
                    hole_type="three_in_one_rod", panel_label=panel.label,
                    x_global=rod_x,
                    y_global=rod_y,
                    z_global=rod_z,
                    x_local=x_local, y_local=y_offset, z_local=rod_zl,
                    diameter=r_diam, depth=r_depth, direction=rod_sign,
                    is_face_hole=False, note="连接杆孔"))

            for y_offset in rod_y_offsets:   # 偏心轮 y 与连接杆 y 一致
                cam_x, cam_y, cam_z = panel.to_global(cam_x_local, y_offset, cam_zl)
                result.append(HoleSpec(
                    hole_type="three_in_one_cam", panel_label=panel.label,
                    x_global=cam_x,
                    y_global=cam_y,
                    z_global=cam_z,
                    x_local=cam_x_local, y_local=y_offset, z_local=cam_zl,
                    diameter=w_diam, depth=w_depth, direction=cam_dir,
                    is_face_hole=True, note="偏心轮孔"))

        return result

    # ── assembly-aware（连接驱动，轴无关）──────────────────────────

    def generate_holes_for_panels(
        self,
        panels: List[PanelRecord],
    ) -> List[HoleSpec]:
        """生成所有三合一孔位。

        对每个带 cam 的连接（male_has_cam 的 joint，边轴 x 或 y）成对生成：
        - female 面 → 预埋螺母孔（位置对齐 male 的连接杆轴线与连接排）
        - male 边   → 连接杆孔（端面）
        - male cam 面 → 偏心轮孔
        连接排沿"连接平面内除边轴与 cam 面轴之外的第三轴"分布；
        无连接拓扑的旧数据走 generate_holes() 的 system-32 回退。
        """
        matched = self.match(panels)
        spec = matched.get("spec", {})
        cam_spec = spec.get("cam", {})
        rod_spec = spec.get("rod", {})
        nut_spec = spec.get("nut", {})
        rules = matched.get("rules", {})
        row_first = float(rules.get("first_hole_mm", 64))
        row_last = float(rules.get("last_hole_mm", 64))
        cam_offset = float(cam_spec.get("hole", {}).get("edge_offset_mm", 33.5))
        rod_axis_offset = float(cam_spec.get("rod_axis_to_cam_face_mm", 9))

        by_label = {panel.label: panel for panel in panels}
        result: List[HoleSpec] = []
        for panel in panels:
            fem_joints = [
                j for j in (panel.joints or [])
                if j.female_id == panel.label
                and _is_trinity_joint(j, by_label)
            ]
            mal_joints = [
                j for j in (panel.joints or [])
                if j.male_id == panel.label
                and _is_trinity_joint(j, by_label)
            ]
            if not panel.joints:
                # 无连接拓扑的旧数据：system-32 回退
                result.extend(self.generate_holes(panel))
                continue
            # 螺母孔先发（按连接杆轴线位置排序，保持旧顺序），再杆、再轮
            for joint in sorted(
                fem_joints,
                key=lambda j: self._rod_axis_world(
                    j, by_label[j.male_id], rod_axis_offset
                ),
            ):
                result.extend(self._nut_holes(
                    panel, joint, by_label[joint.male_id], nut_spec, cam_spec,
                    row_first, row_last, rod_axis_offset,
                ))
            for joint in sorted(mal_joints, key=lambda j: j.edge_sign):
                result.extend(self._rod_holes(
                    panel, joint, rod_spec, cam_spec, cam_offset,
                    row_first, row_last, rod_axis_offset,
                ))
            for joint in sorted(mal_joints, key=lambda j: j.edge_sign):
                result.extend(self._cam_holes(
                    panel, joint, cam_spec, cam_offset,
                    row_first, row_last, rod_axis_offset,
                ))
        return result

    @staticmethod
    def _rod_axis_world(
        joint: Any, male: PanelRecord, rod_axis_offset: float
    ) -> float:
        """male 连接杆轴线在 cam 面法向轴上的世界坐标（取整到 0.001）。"""
        cam_face = getattr(joint, "male_cam_face", None) or "+z"
        t = cam_face[1]
        size_t = getattr(male, f"size_{t}", 0.0)
        pos_t = getattr(male, f"pos_{t}", 0.0)
        if size_t <= 0:
            # 旧 joint 数据缺 male 尺寸：退回 male_z（旧行为，仅 z 轴有效）
            return joint.male_z
        rod_t = (
            size_t - rod_axis_offset if cam_face[0] == "+" else rod_axis_offset
        )
        return round(pos_t + rod_t, 3)

    def _nut_holes(
        self, panel: PanelRecord, joint: Any, male: PanelRecord,
        nut_spec: Dict[str, Any], cam_spec: Dict[str, Any],
        row_first: float, row_last: float, rod_axis_offset: float,
    ) -> List[HoleSpec]:
        """female 面板上的预埋螺母孔：与 male 的连接杆/轮同排同位。"""
        result: List[HoleSpec] = []
        n_diam = float(nut_spec.get("hole", {}).get("diameter_mm", 10))
        n_depth = float(nut_spec.get("hole", {}).get("depth_mm", 11))
        face = joint.face
        f = face[1]
        a = joint.edge_axis
        cam_face = getattr(joint, "male_cam_face", None) or "+z"
        t = cam_face[1]
        s2 = _other_axis(a, t)
        face_local = panel.face_position(face) - getattr(panel, f"pos_{f}")
        t_rod_world = self._rod_axis_world(joint, male, rod_axis_offset)
        # 连接排沿 s2 以 male 的跨度为基准（世界坐标，螺母与杆/轮严格同排）
        rows_world = [
            getattr(male, f"pos_{s2}") + row_first,
            getattr(male, f"pos_{s2}") + getattr(male, f"size_{s2}") - row_last,
        ]
        nut_dir = _opposite(face)
        for row_world in rows_world:
            local = {
                f: face_local,
                t: t_rod_world - getattr(panel, f"pos_{t}"),
                s2: row_world - getattr(panel, f"pos_{s2}"),
            }
            x_global, y_global, z_global = panel.to_global(
                local["x"], local["y"], local["z"]
            )
            result.append(HoleSpec(
                hole_type="three_in_one_nut", panel_label=panel.label,
                x_global=x_global, y_global=y_global, z_global=z_global,
                x_local=local["x"], y_local=local["y"], z_local=local["z"],
                diameter=n_diam, depth=n_depth, direction=nut_dir,
                is_face_hole=True, note="预埋螺母孔"))
        return result

    def _rod_holes(
        self, panel: PanelRecord, joint: Any,
        rod_spec: Dict[str, Any], cam_spec: Dict[str, Any], cam_offset: float,
        row_first: float, row_last: float, rod_axis_offset: float,
    ) -> List[HoleSpec]:
        """male 面板端面的连接杆孔（轴无关）。"""
        result: List[HoleSpec] = []
        r_diam = float(rod_spec.get("hole", {}).get("diameter_mm", 8))
        r_depth = float(rod_spec.get("hole", {}).get("depth_mm", 33))
        a = joint.edge_axis
        cam_face = getattr(joint, "male_cam_face", None) or "+z"
        t = cam_face[1]
        s2 = _other_axis(a, t)
        rows = [row_first, getattr(panel, f"size_{s2}") - row_last]
        edge_local = (
            0.0 if joint.edge_sign == -1 else getattr(panel, f"size_{a}")
        )
        rod_dir = f"{'+' if joint.edge_sign == -1 else '-'}{a}"
        size_t = getattr(panel, f"size_{t}")
        t_rod = (
            size_t - rod_axis_offset if cam_face[0] == "+" else rod_axis_offset
        )
        for row in rows:
            local = {a: edge_local, s2: row, t: t_rod}
            x_global, y_global, z_global = panel.to_global(
                local["x"], local["y"], local["z"]
            )
            result.append(HoleSpec(
                hole_type="three_in_one_rod", panel_label=panel.label,
                x_global=x_global, y_global=y_global, z_global=z_global,
                x_local=local["x"], y_local=local["y"], z_local=local["z"],
                diameter=r_diam, depth=r_depth, direction=rod_dir,
                is_face_hole=False, note="连接杆孔"))
        return result

    def _cam_holes(
        self, panel: PanelRecord, joint: Any,
        cam_spec: Dict[str, Any], cam_offset: float,
        row_first: float, row_last: float, rod_axis_offset: float,
    ) -> List[HoleSpec]:
        """male 面板 cam 面上的偏心轮孔（轴无关）。"""
        result: List[HoleSpec] = []
        w_diam = float(cam_spec.get("hole", {}).get("diameter_mm", 12))
        w_depth = float(cam_spec.get("hole", {}).get("depth_mm", 13.5))
        a = joint.edge_axis
        cam_face = getattr(joint, "male_cam_face", None) or "+z"
        t = cam_face[1]
        s2 = _other_axis(a, t)
        rows = [row_first, getattr(panel, f"size_{s2}") - row_last]
        cam_a = (
            cam_offset
            if joint.edge_sign == -1
            else getattr(panel, f"size_{a}") - cam_offset
        )
        cam_t = (
            0.0 if cam_face[0] == "-" else getattr(panel, f"size_{t}")
        )
        cam_dir = _opposite(cam_face)
        for row in rows:
            local = {a: cam_a, s2: row, t: cam_t}
            x_global, y_global, z_global = panel.to_global(
                local["x"], local["y"], local["z"]
            )
            result.append(HoleSpec(
                hole_type="three_in_one_cam", panel_label=panel.label,
                x_global=x_global, y_global=y_global, z_global=z_global,
                x_local=local["x"], y_local=local["y"], z_local=local["z"],
                diameter=w_diam, depth=w_depth, direction=cam_dir,
                is_face_hole=True, note="偏心轮孔"))
        return result

    def _system_32_positions(self, panel: PanelRecord, rules: Dict[str, Any]) -> List[float]:
        """按系统 32 排钻规则计算孔位 Z 坐标列表。"""
        first = float(rules.get("first_hole_mm", 64))
        last = float(rules.get("last_hole_mm", 64))
        max_spacing = float(rules.get("max_spacing_mm", 512))
        min_spacing = float(rules.get("min_spacing_mm", 32))
        snap = float(rules.get("snap_to_mm", 0.5))
        usable = panel.drill_length - first - last
        if usable <= 0:
            return [panel.drill_length / 2]
        spacings = [512, 480, 448, 416, 384, 352, 320, 288, 256, 224, 192, 160, 128, 96, 64]
        best = 320.0
        for sp in spacings:
            if sp <= max_spacing and int(usable / sp) >= 1:
                best = sp
                break
        count = max(1, int(usable / best))
        actual = usable / count
        holes = [first] + [first + (i + 1) * actual for i in range(count - 1)] + [panel.drill_length - last]
        holes = sorted(set(holes))
        merged = [holes[0]]
        for h in holes[1:]:
            if h - merged[-1] >= min_spacing:
                merged.append(h)
        if snap > 0:
            merged = [round(h / snap) * snap for h in merged]
        return merged

    def boms(
        self,
        panels: List[PanelRecord],
        *,
        options: Mapping[str, Any] | None = None,
    ) -> List[HardwareRecord]:
        """生成三合一 BOM 清单。

        数量 = 实际生成的偏心轮孔数（孔即真源）。
        一套三合一 = 1 偏心轮 + 1 连接杆 + 1 预埋螺母。
        品牌由确认选择（options）决定；未选择时目录唯一才返回。
        """
        matched = self.match(panels)
        spec = matched["spec"]
        opts = (options or {}).get(self.catalog_entry, {})
        opts = dict(opts) if isinstance(opts, Mapping) else {}
        brand = self.resolve_brand(spec.get("brands", []), opts.get("brand"))
        holes = self.generate_holes_for_panels(panels)
        quantity = sum(1 for h in holes if h.hole_type == "three_in_one_cam")
        return [HardwareRecord(
            name=self.name,
            spec="偏心轮+连接杆+预埋螺母（实物规格待确认）",
            quantity=quantity,
            unit="套", brand=brand.get("name", "默认"), model=brand.get("model", "SJY-01"))]

    def validate(
        self,
        report: Any,
        panels: List[PanelRecord],
        hardware: List[HardwareRecord],
        drilled: Dict[str, Any],
    ) -> None:
        """三合一专属校验：偏心轮孔数 = BOM 数，连接杆孔数 = 偏心轮孔数（1:1 配对）。"""
        hole_types = [
            hole["hole_type"]
            for panel in drilled["panels"]
            for hole in panel["holes"]
        ]
        hardware_by_name = {item.name: item for item in hardware}
        trinity_hardware = hardware_by_name.get(self.name)
        trinity_cam_count = hole_types.count("three_in_one_cam")
        if trinity_hardware is not None and trinity_hardware.quantity != trinity_cam_count:
            report.add_error(
                "TRINITY_HARDWARE_COUNT_MISMATCH",
                f"三合一连接件数量 {trinity_hardware.quantity} 与偏心轮孔数 {trinity_cam_count} 不一致",
                "hardware",
            )
        trinity_rod_count = hole_types.count("three_in_one_rod")
        if trinity_rod_count != trinity_cam_count:
            report.add_error(
                "TRINITY_ROD_CAM_COUNT_MISMATCH",
                f"连接杆孔数 {trinity_rod_count} 与偏心轮孔数 {trinity_cam_count} 不一致（1:1 配对）",
                "drilled_holes",
            )

    def machining_operations(self, panel: PanelRecord) -> List[MachiningOperation]:
        """生成三合一孔位的 cut_box 加工指令。"""
        ops: List[MachiningOperation] = []
        for hole in self.generate_holes(panel):
            d = hole.diameter
            # id 含 x_local：区分左右两端同 (z,y) 的孔，避免 DUPLICATE_OPERATION_ID
            ops.append(MachiningOperation(
                id=(
                    f"{hole.hole_type}_{panel.label}_"
                    f"{hole.z_local:.0f}_{hole.y_local:.0f}_{hole.x_local:.0f}"
                ),
                operation_type="cut_box", target_panel=panel.label,
                size_x=hole.depth if hole.direction in ("+x", "-x") else d,
                size_y=hole.depth if hole.direction in ("+y", "-y") else d,
                size_z=hole.depth if hole.direction in ("+z", "-z") else d,
                pos_x=hole.x_global - d / 2, pos_y=hole.y_global - d / 2,
                pos_z=hole.z_global - d / 2,
                note=f"{self.name} {hole.note}"))
        return ops
````

## File: domain/skills/furniture-manufacturing/scripts/furniture_manufacturing/hardware_catalog.yaml
````yaml
# ============================================================================
# 硬件规格库 — 三合一 + 铰链
# ============================================================================
# 规格组决定工程参数（打孔），品牌决定 BOM 输出
# ============================================================================

# ── 三合一：一套 = 偏心轮 + 连接杆 + 预埋螺母 ────────────
three_in_one:
  standard:
    cam:                              # 偏心轮
      part: { outer_diameter_mm: 待定, thickness_mm: 待定 }   # 实物 → BOM/采购
      hole: { diameter_mm: 12, depth_mm: 13.5, edge_offset_mm: 33.5 }   # 打孔（圆心到横板端面）
      rod_axis_to_cam_face_mm: 9      # 连接杆轴中心线到偏心轮安装面的距离（五金固定参数；投产前确认）
    rod:                              # 连接杆
      part: { diameter_mm: 待定, length_mm: 待定 }            # 实物（总长 44 待确认）
      hole: { diameter_mm: 8, depth_mm: 33 }                  # 打孔
    nut:                              # 预埋螺母
      part: { outer_diameter_mm: 待定, thickness_mm: 待定 }   # 实物（外径/厚度待确认）
      hole: { diameter_mm: 10, depth_mm: 11 }                 # 打孔
    brands:
      - name: 默认
        model: SJY-01

# ── 二合一：一套 = 偏心轮 + 连接杆（固定塑料件并入连接杆，不单列）──
two_in_one:
  standard:
    cam:                              # 偏心轮
      part: { outer_diameter_mm: 待定, thickness_mm: 待定 }   # 实物 → BOM/采购
      hole: { diameter_mm: 12, depth_mm: 13.5, edge_offset_mm: 4.5 }   # 打孔（层板底面，圆心到朝向侧板的侧边）
      rod_axis_to_cam_face_mm: 9      # 连接杆轴中心线到层板底面（偏心轮安装面）的距离（五金固定参数）
    rod:                              # 连接杆（特殊螺丝，打在侧板）
      part: { diameter_mm: 待定, length_mm: 待定 }            # 实物
      hole: { diameter_mm: 5, depth_mm: 10 }                  # 打孔
    note: 活动层板标准连接件
    brands:
      - name: 默认
        model: EYJ-01

# ── 隔板钉：一套 = 单钉 ──────────────────────────────────
shelf_pin:
  standard:
    pin:                              # 钉
      part: { diameter_mm: 待定, length_mm: 待定 }            # 实物
      hole: { diameter_mm: 5, depth_mm: 9 }                   # 打孔（侧板孔）
      shelf_bottom_offset_mm: 2.5     # 层板底面比钉孔中心高（= 钉半径）
    note: 轻载层板，安装简便
    brands:
      - name: 默认
        model: GBD-01

# ── 抽屉滑轨 ──────────────────────────────────────────
drawer_slides:
  三节轨:
    mounting: 侧装
    gap_requirement_mm: 13.0        # 每侧间隙（修正 12.5→13.0，投产前确认）
    extension: 100%                 # 全拉出
    standard_lengths_mm: [250, 300, 350, 400, 450, 500, 550, 600]
    brands:
      - name: 默认
        model: SJG-01
      - name: DTC
        model: DTC-3S
      - name: 悍高
        model: HG-3S

  隐藏轨:
    mounting: 底装
    gap_requirement_mm: 12.7        # 每侧间隙
    extension: 100%
    standard_lengths_mm: [270, 300, 350, 400, 450, 500, 550]
    brands:
      - name: 默认
        model: YCG-01
      - name: Blum
        model: 760H

# ── 铰链 ──────────────────────────────────────────────
hinges:
  HJ-100:
    angle: 100                          # 开门角度（产品规格）
    part: { cup_diameter_mm: 待定 }     # 实物（铰链杯外径，待确认）
    hole: { diameter_mm: 35, depth_mm: 13, edge_offset_mm: 5 }   # 杯孔打孔（直径/深度/边距）
    door_thickness_mm: [14, 22]         # 适用门厚范围 [min, max]，超出由校验拦截
    brands:
      - name: 默认
        model: HJ-100
````

## File: domain/skills/furniture-cad/scripts/server.py
````python
"""Furniture Agent 服务 — FastAPI 入口

启动: ./.venv/Scripts/python.exe domain/skills/furniture-cad/scripts/server.py
打开: http://localhost:8000/docs 查看 Swagger API 文档
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Literal

# skill 自带运行包，服务入口与它位于同一个 scripts 目录。
SCRIPT_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
OUTPUT_ROOT = WORKSPACE_ROOT / "generated"
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.input_adapter import (
    layout_stage_input,
    panel_stage_input,
    stage_inputs_from_spec,
)
from furniture_layout.layout_pipeline import plan_layout_stage
from furniture_layout.layout_spec import LayoutSpec
from furniture_layout.validation import validate_layout_output

API_VERSION = "0.6.0"

app = FastAPI(
    title="Furniture Agent — 板式家具拆单服务",
    version=API_VERSION,
    description=(
        "板式家具参数化拆单 API：房间定位与 SVG 预览、"
        "落地柜/吊柜规划、三种背板安装、BOM、加工与孔位输出"
    ),
)
ORCHESTRATOR = FurnitureOrchestrator(workspace_root=WORKSPACE_ROOT)

# 静态文件服务 — 挂载 generated 目录，供访问 STEP/GLB 文件
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/generated", StaticFiles(directory=str(OUTPUT_ROOT)), name="generated")


# ── 请求/响应模型 ──
class RoomOpeningRequest(BaseModel):
    id: str = Field(default="", description="门窗标识")
    kind: str = Field(default="opening", description="opening / door / window")
    wall: Literal["south", "east", "north", "west"]
    offset_mm: float = Field(default=0, ge=0, description="沿墙顺时针起点的偏移")
    width_mm: float = Field(..., gt=0)
    height_mm: float = Field(..., gt=0)
    sill_height_mm: float = Field(default=0, ge=0)


class RoomObstacleRequest(BaseModel):
    id: str = Field(default="", description="障碍物标识")
    kind: str = Field(default="obstacle", description="column / pipe / obstacle")
    x_mm: float = Field(default=0, ge=0)
    y_mm: float = Field(default=0, ge=0)
    z_mm: float = Field(default=0, ge=0)
    width_mm: float = Field(..., gt=0)
    depth_mm: float = Field(..., gt=0)
    height_mm: float = Field(..., gt=0)


class RoomRequest(BaseModel):
    id: str = Field(default="room")
    name: str = Field(default="房间")
    width_mm: float = Field(..., gt=0)
    depth_mm: float = Field(..., gt=0)
    height_mm: float = Field(..., gt=0)
    openings: list[RoomOpeningRequest] = Field(default_factory=list)
    obstacles: list[RoomObstacleRequest] = Field(default_factory=list)


class FurniturePlacementRequest(BaseModel):
    mode: Literal["wall", "free"] = Field(default="wall")
    host_wall: Literal["south", "east", "north", "west"] | None = None
    offset_mm: float | None = Field(default=None, ge=0)
    origin_x_mm: float | None = None
    origin_y_mm: float | None = None
    origin_z_mm: float = Field(default=0, ge=0)
    rotation_z_deg: float | None = None


class CabinetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(..., description="家具类型: floor_cabinet / wall_cabinet")
    width: float = Field(..., gt=0, description="总宽 mm (X)")
    depth: float = Field(..., gt=0, description="总深 mm (Y)")
    height: float = Field(..., gt=0, description="总高 mm (Z)")
    mounting_height: float | None = Field(
        default=None,
        gt=0,
        description="吊柜底边离地高度（挂高）mm；地柜无需提供",
    )
    mount_mode: Literal["free_height", "flush_ceiling"] | None = Field(
        default=None,
        description="吊柜挂装方式：free_height（自由挂高）/ flush_ceiling（贴顶到顶）",
    )
    board_thickness: float | None = Field(default=None, gt=0, description="柜体板厚 mm")
    back_thickness: float | None = Field(default=None, gt=0, description="背板厚 mm")
    door_thickness: float | None = Field(default=None, gt=0, description="门板厚 mm")
    toe_kick_height: float | None = Field(default=None, ge=0, description="踢脚线高 mm")
    back_offset: float | None = Field(default=None, ge=0, description="背板后移 mm")
    door_margin: float | None = Field(default=None, ge=0, description="门板四周间隙 mm")
    door_hinge_gap: float | None = Field(default=None, ge=0, description="门铰深度间隙 mm")
    shelves: list[dict[str, Any]] | None = Field(
        default=None,
        description="层板列表（从上到下）：[{shelf_type: fixed|movable, gap_below_mm: 净高mm|null=auto}]",
    )
    top_gap_mm: float | None = Field(default=None, ge=0, description="顶格净高 mm（最上层板顶面到顶板底面）")
    n_doors: int | None = Field(default=None, ge=0, description="门板数量")
    door_hinge_side: Literal["left", "right"] | None = Field(
        default=None,
        description="单门铰链侧；仅 n_doors=1 时有效，双门由代码确定性推导",
    )
    drawer_count: int | None = Field(default=None, ge=0, description="整高抽屉数量")
    movable_shelf_connector: Literal["two_in_one", "shelf_pin"] | None = Field(
        default=None,
        description="活动层板连接方式：two_in_one（二合一）/ shelf_pin（隔板钉）",
    )
    groove_depth: float | None = Field(default=None, gt=0, description="背板入槽深度 mm")
    groove_clearance: float | None = Field(default=None, ge=0, description="槽宽相对背板厚度的余量 mm")
    back_mount: Literal["auto", "groove", "insert", "cover"] | None = Field(
        default=None,
        description=(
            "板件阶段的背板安装方式；auto 按背板厚度解析为 groove 或 insert"
        ),
    )
    back_rail_height: float | None = Field(
        default=None,
        ge=0,
        description="入槽模式背拉条高度 mm；0 表示不生成背拉条",
    )
    toe_kick_reveal_front: float | None = Field(default=None, ge=0, description="前踢脚板后缩 mm")
    toe_kick_reveal_back: float | None = Field(default=None, ge=0, description="后踢脚板前移 mm")
    toe_kick_support_count: int | None = Field(default=None, ge=0, description="踢脚支撑板数量；空值为自动")
    drawer_side_clearance: float | None = Field(default=None, gt=0, description="抽屉每侧净空 mm")
    drawer_layer_gap: float | None = Field(default=None, ge=0, description="抽屉层间缝 mm")
    drawer_bottom_thickness: float | None = Field(default=None, gt=0, description="抽屉底板厚 mm")
    drawer_back_thickness: float | None = Field(default=None, gt=0, description="抽屉背板厚 mm")
    drawer_back_clearance: float | None = Field(default=None, ge=0, description="抽屉后部净空 mm")
    appearance: dict[str, Any] = Field(
        default_factory=dict,
        description="制造阶段使用的饰面和外观偏好",
    )
    room: RoomRequest | None = Field(
        default=None,
        description="独立房间布局使用的房间模型",
    )
    placement: FurniturePlacementRequest | None = Field(
        default=None,
        description="家具在房间中的沿墙或自由摆放位置",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="需要映射到所属阶段或明确标为 informational 的约束",
    )
    constraint_mappings: dict[str, str] = Field(
        default_factory=dict,
        description="约束到 layout/structure/manufacturing/外包络字段或 informational 的映射",
    )


class PanelResponse(BaseModel):
    label: str
    name: str
    panel_type: str
    size_x: float
    size_y: float
    size_z: float
    pos_x: float
    pos_y: float
    pos_z: float
    material: str
    thickness: float
    length_mm: float
    width_mm: float
    edge_banding: dict
    note: str
    back_mount: Literal["groove", "insert", "cover"]


class HardwareDrillingResponse(BaseModel):
    hole_type: str
    quantity: int


class HardwareResponse(BaseModel):
    name: str
    spec: str
    quantity: int
    unit: str
    brand: str
    model: str
    note: str
    drilling: list[HardwareDrillingResponse]


class MachiningOperationResponse(BaseModel):
    id: str
    operation_type: str
    target_panel: str
    size_x: float
    size_y: float
    size_z: float
    pos_x: float
    pos_y: float
    pos_z: float
    note: str


class HoleResponse(BaseModel):
    hole_type: str
    color: str
    x: float
    y: float
    z: float
    local_x: float
    local_y: float
    local_z: float
    diameter: float
    depth: float
    direction: str
    note: str


class PanelDrillingResponse(BaseModel):
    label: str
    name: str
    box: dict[str, float]
    holes: list[HoleResponse]


class BOMResponse(BaseModel):
    furniture_name: str
    dimensions: str
    readiness: Literal["preliminary", "accepted", "factory_ready"]
    back_mount: Literal["groove", "insert", "cover"]
    panel_count: int
    total_area_m2: float
    panels: list[PanelResponse]
    hardware: list[HardwareResponse]
    operations: list[MachiningOperationResponse]
    hole_color_legend: dict[str, dict[str, str]]
    drilled_holes: list[PanelDrillingResponse]


class LayoutPlanResponse(BaseModel):
    layout: dict[str, Any]
    layout_context: dict[str, str] | None = None
    room_placement: dict[str, Any] | None = None
    preview: dict[str, Any] | None = None
    viewer: dict[str, Any] | None = None


# ── 路由 ──
@app.get("/health")
async def health():
    return {"status": "ok", "version": API_VERSION}


@app.get("/", response_class=HTMLResponse)
async def root():
    """API 入口页面"""
    return """
    <html><body style="font-family:sans-serif;padding:40px;">
    <h1>Furniture Agent API</h1>
    <p><a href="/docs">API 文档 (Swagger)</a></p>
    </body></html>
    """


@app.post("/api/plan-cabinet", response_model=BOMResponse)
async def plan_cabinet(req: CabinetRequest):
    """规划柜体、拆单、返回 BOM"""
    # Preserve an explicitly submitted null (for example the deterministic
    # toe-kick support formula) while omitting fields the caller never sent.
    spec = req.model_dump(exclude_unset=True)
    try:
        orchestration = ORCHESTRATOR.execute_spec(
            f"api-{req.type}",
            spec,
        )
    except (OSError, TypeError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))

    if orchestration.pipeline is None:
        errors = [
            issue.message
            for validation in orchestration.revision.validations
            for issue in validation.issues
        ]
        raise HTTPException(
            status_code=400,
            detail="; ".join(errors) or "furniture orchestration failed",
        )

    report = orchestration.pipeline.bom
    drilled_holes = orchestration.drilled_holes or {
        "color_legend": {},
        "panels": [],
    }

    return BOMResponse(
        furniture_name=report.furniture_name,
        dimensions=report.dimensions,
        readiness=report.readiness,
        back_mount=orchestration.pipeline.spec.back_mount,
        panel_count=report.panel_count,
        total_area_m2=report.total_area_m2,
        panels=[
            PanelResponse(
                label=p.label,
                name=p.name,
                panel_type=p.panel_type,
                size_x=p.size_x,
                size_y=p.size_y,
                size_z=p.size_z,
                pos_x=p.pos_x,
                pos_y=p.pos_y,
                pos_z=p.pos_z,
                material=p.material,
                thickness=p.thickness,
                length_mm=p.length_mm,
                width_mm=p.width_mm,
                edge_banding=p.edge_banding,
                note=p.note,
                back_mount=p.back_mount,
            )
            for p in report.panels
        ],
        hardware=[
            HardwareResponse(
                name=h.name,
                spec=h.spec,
                quantity=h.quantity,
                unit=h.unit,
                brand=h.brand,
                model=h.model,
                note=h.note,
                drilling=h.drilling or [],
            )
            for h in report.hardware
        ],
        operations=[
            MachiningOperationResponse(
                id=operation.id,
                operation_type=operation.operation_type,
                target_panel=operation.target_panel,
                size_x=operation.size_x,
                size_y=operation.size_y,
                size_z=operation.size_z,
                pos_x=operation.pos_x,
                pos_y=operation.pos_y,
                pos_z=operation.pos_z,
                note=operation.note,
            )
            for operation in report.operations
        ],
        hole_color_legend=drilled_holes["color_legend"],
        drilled_holes=drilled_holes["panels"],
    )


@app.post("/api/plan-layout", response_model=LayoutPlanResponse)
async def plan_layout(req: CabinetRequest):
    """独立规划房间摆放；不进入家具生成的串联阶段。"""
    payload = req.model_dump(exclude_none=True)
    try:
        intent = ORCHESTRATOR.intent_from_spec(payload).confirm()
        stage_inputs = stage_inputs_from_spec(payload)
        panel_parameters = panel_stage_input(stage_inputs).get("parameters", {})
        layout_options = {
            key: panel_parameters[key]
            for key in ("n_doors", "door_count")
            if key in panel_parameters
        }
        context = layout_stage_input(stage_inputs)
        spec = LayoutSpec.from_intent(intent, layout_options)
        output = plan_layout_stage(
            spec,
            room=context.get("room"),
            placement=context.get("placement"),
            furniture_label=f"layout-{req.type}",
        )
        report = validate_layout_output(spec, output)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    if not report.passed:
        raise HTTPException(
            status_code=422,
            detail="; ".join(issue.message for issue in report.issues),
        )
    return LayoutPlanResponse(**output)


@app.post(
    "/api/plan-layout/preview",
    response_class=Response,
    responses={200: {"content": {"image/svg+xml": {}}}},
)
async def plan_layout_preview(req: CabinetRequest) -> Response:
    """返回可直接在浏览器中显示的独立 SVG 房间摆放预览。"""
    result = await plan_layout(req)
    if result.preview is None:
        raise HTTPException(
            status_code=422,
            detail="layout preview was not generated",
        )
    return Response(
        content=str(result.preview["svg"]),
        media_type="image/svg+xml",
    )


@app.post(
    "/api/plan-layout/viewer",
    response_class=HTMLResponse,
    responses={200: {"content": {"text/html": {}}}},
)
async def plan_layout_viewer(req: CabinetRequest) -> HTMLResponse:
    """返回可拖拽旋转、缩放和切换标准视角的独立 Viewer。"""
    result = await plan_layout(req)
    if result.viewer is None:
        raise HTTPException(
            status_code=422,
            detail="interactive layout viewer was not generated",
        )
    return HTMLResponse(content=str(result.viewer["html"]))


# ── 启动入口 ──
def main() -> None:
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
````

## File: domain/skills/furniture-design-intent/SKILL.md
````markdown
---
name: furniture-design-intent
description: 用于 design_intent 阶段，也是家具流水线的入口。当用户提出"设计一个柜子"、描述想要的家具类型和大致尺寸时触发。只确认家具类别与成品外包络，不提前确认布局、结构、材料或制造细节；非柜类家具只产出 fallback 草稿。
---

# 家具设计意图

阶段：`design_intent`

**本阶段只回答一个问题：做哪类家具、占多大外部空间（外包络）？** 产物是一份待确认的 `DesignIntent` 草稿；布局、结构、材料、制造都不在此阶段，由后续阶段接管。

## 工作流

1. **归一化类别**：读 [家具目录](references/intake/catalog.yaml)，按完整语义把描述归到 `families` 中的规范 `furniture_type`。拿不准就只出 fallback 草稿，不确认、不进可执行流水线。
2. **生成草稿**：字段只有 `furniture_type`、成品外包络 `overall_size`、吊柜挂装方式 `mount_mode` 与挂高 `mounting_height_mm`、以及工作流元数据。
3. **预校验**：草稿尺寸可为 `null`；确认前只查——类别已归一化、宽/深/高均为正数、`mount_mode` 完整（`free_height` 时挂高为正数）。
4. **展示并等确认**：只展示外包络与挂装方式。

## 本阶段不做什么

- 布局（门/层板/抽屉…）→ 布局阶段
- 结构（板厚/背板/踢脚…）→ 板件阶段
- 制造（材料/饰面/五金…）→ 制造阶段

归一化判据、挂装方式取值与挂高基准、以及不在本阶段捕获的完整清单，见 [意图采集规则](references/intent-capture-rules.md)。

## 边界

- 运行时仅含 `DesignIntent`（含吊柜挂装方式 `mount_mode` 与挂高 `mounting_height_mm`）、`OverallSize`、目录中的可执行规范类别和外包络校验；不得导入或定义下游 `FurnitureSpec`。
- CLI/API 完整请求由 `furniture_workflow/input_adapter.py` 拆成 `DesignIntent` 与 `stage_inputs`；扁平字段 `type/width/depth/height/mount_mode/mounting_height` 与下游参数都留在对应阶段输入，不进入 `DesignIntent`。
- 意图变化用 `FurnitureOrchestrator.revise()` 新建 Revision；不得另建规格、状态机或入口。
- 本阶段的阻塞项只允许是类别、外包络尺寸或吊柜挂装方式。
````

## File: domain/skills/furniture-design-intent/references/intent-capture-rules.md
````markdown
# 设计意图采集规则

回答“要制作哪类、占多大外部空间的家具？”；本阶段只建立客户可确认的成品外包络。

## 捕获内容

- `furniture_type`：由 LLM 根据完整语义按**落位/安装方式**归一化为 [家具目录](intake/catalog.yaml) 中 `executable: true` 的规范类别——柜类家具中，落地的归 `floor_cabinet`、上墙的归 `wall_cabinet`；与功能、外观、所在房间无关。“靠墙/贴墙摆放”是房间里的摆放位置，不是挂墙（上墙），不得据此归入 `wall_cabinet`。归一化是语义判断，不要求字面命中；运行时只验证归一化结果是否属于可执行类别，不实现自然语言别名匹配。
- `overall_size.width_mm/depth_mm/height_mm`：成品外包络；草稿未知值可为 `null`，确认前必须全部为正数。
- `mount_mode`：吊柜**挂装方式**，二选一——`free_height`（自由挂高，需挂高）或 `flush_ceiling`（贴顶/到顶，无需数字）。客户说“做到顶 / 贴顶 / 到顶”归一到 `flush_ceiling`；说“挂多高 / 离地多少 / 底边距地面多少”归一到 `free_height`。
- `mounting_height_mm`：仅 `free_height` 时有效，吊柜**底边离地高度**；测量基准是柜底，不是柜顶、也不是台面。地柜与 `flush_ceiling` 无需此值。
- 坐标口径为 X 左→右、Y 后→前、Z 向上；未标注的三个尺寸按 `W×D×H` 解释并向客户展示。

## 不在本阶段捕获

- 功能布局：门、层板、抽屉、隔间、开放格、房间和摆放位置。
- 结构设计：板厚、背板安装、踢脚、门缝、内部净空、背拉条和板件构成。
- 制造设计：材料、饰面、封边、连接、五金、公差、槽和孔位。

完整 CLI/API 请求可一次提交上述后续参数；拆分与写入 `stage_inputs` 的契约见 SKILL.md 边界，本阶段不得在意图确认时物化下游默认值。

## 边界

- 目录只列可执行类别，不列同义表达；无法可靠归一化时停在 fallback 草稿（确认与流水线门禁见 SKILL.md 工作流）。
- 在外包络确认后停止；不计算布局、净空、板件、制造策略、特征树或 CAD。
````

## File: README.md
````markdown
# furniture-agent-workspace

板式家具参数化规划、拆单、BOM 与 CAD 输出的本地开发工作区。

## 架构

```text
CLI / FastAPI / Agent Skill
            |
            v
FurnitureOrchestrator
            |
            +-- 设计意图 -> 板件 -> 制造/BOM -> 特征树
            +-- 按需科学分析 -> stage_analyses（不改阶段检查点）
            +-- CadBridge -> external/text-to-cad
            +-- 验证、Project/Revision、产物清单

独立 furniture-layout -> 房间摆放 / 碰撞检查 / SVG / Viewer
```

`domain/skills/furniture-cad/scripts/furniture_workflow/workflow_orchestrator.py` 是家具生成的唯一应用层入口。六个串联阶段实现由各自 Skill 的 `scripts/` 拥有；CLI、API 与 Agent 不直接拼装规划器、发射器或 CAD Bridge。`furniture-layout` 是明确请求时才调用的独立房间摆放能力，不是家具生成前置步骤。

## 六阶段交互

交互式 Agent 每次只运行一个阶段：`confirm_stage()` 确认当前阶段，`run_next()` 进入下一阶段。阶段完成后，用户检查 Revision 中对应的 `stage_outputs`；未确认时再次调用不会越过当前检查点。

```text
1. design_intent
2. panels_planned
3. manufacturing_planned
4. feature_tree_planned
5. cad_generated
6. delivery_validated
```

阶段确认顺序遵循客户决策：`design_intent` 只确认家具类别与宽深高成品外包络；`panels_planned` 首次确认门数、层板数、抽屉数、板厚、背板、踢脚、精确净空和实体板件；`manufacturing_planned` 再确定材料、封边、连接、五金与加工。

只有明确调用独立 `furniture-layout` 或 `/api/plan-layout` 时才接收房间和家具位置并生成摆放图。未提供时使用 `4200×3600×2800 mm` 的“默认卧室（系统假设）”，并将柜体沿北墙居中摆放；只提供一项时补齐另一项。独立结果包含 `layout_context` 来源标记、房间坐标、家具四角占地、六向净距、内联 SVG 透视图和自包含 HTML 互动 Viewer。普通家具生成不会运行这一步，也不会生成 `layout-plan.json`：

```json
{
  "type": "floor_cabinet",
  "width": 1800,
  "depth": 600,
  "height": 2400,
  "room": {
    "id": "bedroom",
    "name": "主卧",
    "width_mm": 4200,
    "depth_mm": 3600,
    "height_mm": 2800,
    "openings": [],
    "obstacles": []
  },
  "placement": {
    "mode": "wall",
    "host_wall": "north",
    "offset_mm": 500,
    "origin_z_mm": 0
  }
}
```

设计意图变化使用 `revise()` 从第 1 阶段建立新 Revision。修改 `panels_planned`、`manufacturing_planned` 或 `feature_tree_planned` 时使用 `revise_stage_output()`：新 Revision 只保留修改点之前已确认的结果，修改点及全部下游重新确认或生成。独立房间布局直接重新运行，不建立或使主流程 Revision 失效。完整批处理请求中的后续参数保存在 `stage_inputs`，不会污染 `DesignIntent`；`stage_inputs`、`stage_outputs`、`approved_stages` 和工作流历史会随 Project JSON 一起保存。

`generate_furniture.py` 和 `execute_spec()` 是明确的一次性批处理入口，可以自动确认已通过验证的中间阶段；它们不用于交互式逐步设计。

## 按需科学分析

`external/scientific-agent-skills` 保持上游子模块，不复制进家具 Skill。路由器只在任务需要时读取相应方法说明，家具数据适配器仍由板件或制造阶段拥有：

| 分析名 | 来源阶段 | 方法 Skill | 家具适配器 |
| --- | --- | --- | --- |
| `panel_unit_audit` | `panels_planned` | `uncertainty-and-units` | `quantitative_audit.py` |
| `panel_optimization` | `panels_planned` | `pymoo` | `design_optimization.py` |
| `prototype_experiment` | `manufacturing_planned` | `experimental-design` | `prototype_experiment.py` |
| `test_statistics` | `manufacturing_planned` | `statistical-analysis` | `test_statistics.py` |
| `production_simulation` | `manufacturing_planned` | `simpy` | `production_simulation.py` |

可选数值依赖统一安装：

```powershell
uv sync --extra furniture-analysis
```

调用统一入口：

```python
record = orchestrator.run_stage_analysis(
    project,
    "panel_optimization",
    {
        "variables": {"board_thickness": [15.0, 18.0, 21.0]},
        "objectives": ["material_volume_m3", "negative_internal_volume_m3"],
    },
)

# 用户审查 Pareto 候选并明确选择后，才生成新 Revision：
revision = orchestrator.apply_panel_optimization_candidate(project, 0)
```

每条结果保存在当前 Revision 的 `stage_analyses`，包含来源阶段、Revision ID 和来源输出 SHA-256。分析不会改写 `stage_outputs`；来源家具方案变化后，交付验证会把旧分析标记为谱系错误。缺少可选依赖时，适配器会返回 `unavailable`，或使用报告中明确注明限制的有界回退。

## 入口

```powershell
# CLI：明确的一次性批处理，规划并生成 CAD
.\.venv\Scripts\python.exe domain\skills\furniture-cad\scripts\generate_furniture.py <spec.json> --force

# API：只负责 HTTP 协议，内部同样调用 FurnitureOrchestrator
.\.venv\Scripts\python.exe domain\skills\furniture-cad\scripts\server.py
```

`POST /api/plan-layout` 返回独立房间布局 JSON；`POST /api/plan-layout/preview` 直接返回 `image/svg+xml` 静态预览；`POST /api/plan-layout/viewer` 返回可直接打开的 `text/html` 互动 Viewer。

可复用阶段代码放在对应的 `domain/skills/furniture-*/scripts/`；统一 Orchestrator、CLI/API 和集成测试放在 `domain/skills/furniture-cad/scripts/`；一次性脚本和派生 CAD 源码放在 `temp/`；最终产物放在 `generated/`。
````

## File: .agents/skills/furniture-agent/SKILL.md
````markdown
---
name: furniture-agent
description: 路由本仓库六阶段家具生成主流程、独立房间摆放布局与所需 CAD 技能。适用于设计意图、板件、制造/BOM、特征树、CAD/STEP、交付验证，以及按需的房间摆放预览和 Viewer 交接。
---

# 家具智能体

家具工作的薄路由入口；路径均相对仓库根目录。

## 路由

家具生成主流程只读取当前阶段，不提前加载下游：

   - `design_intent`：`domain/skills/furniture-design-intent/SKILL.md`
   - `panels_planned`：`domain/skills/furniture-panel-planning/SKILL.md`
   - `manufacturing_planned`：`domain/skills/furniture-manufacturing/SKILL.md`
   - `feature_tree_planned`：`domain/skills/furniture-feature-tree/SKILL.md`
   - `cad_generated`：`domain/skills/furniture-cad/SKILL.md`
   - `delivery_validated`：`domain/skills/furniture-delivery-validation/SKILL.md`

独立能力（不在上述串联阶段内）：

   - 房间摆放、碰撞检查、SVG/互动 Viewer：`domain/skills/furniture-layout/SKILL.md`

规则：

- 创建、修改或审查家具 Skill 及其运行时代码前，必须读取 [LLM 与运行时边界](references/llm-runtime-boundary.md)，并在完成前执行其中的边界审计；无法归入确定性代码类别的逻辑不得进入 `scripts/`。
- 讨论或推理停在所属阶段；实现由该 Skill 的 `scripts/` 拥有，串联阶段顺序统一由 `FurnitureOrchestrator` 管理。
- 交互式家具生成 Agent 只用 `confirm_stage()`、`run_next()`：确认当前阶段、生成下一阶段、展示其 `stage_outputs`，然后等待“继续”。不得用 `execute_spec()` 越过确认；不得从 Agent 直接调用 `plan_cabinet()`、特征树发射器或 `CadBridge` 另建流水线。
- 修改设计意图用 `revise()`；修改 `panels_planned`、`manufacturing_planned` 或 `feature_tree_planned` 用 `revise_stage_output()`。新 Revision 只继承修改点之前的已确认输出；修改阶段及下游重新确认/生成。
- 只有用户明确要求房间摆放、靠墙/居中、门窗或障碍物碰撞、摆放图或房间 Viewer 时才调用 `furniture-layout`；它不写入主流程 `STAGE_SEQUENCE`，也不是 `panels_planned` 的前置条件。
- `shelf_count/n_doors` 属于板件规划输入；`back_mount` 也从板件阶段开始。板件阶段首次物化这些家具本体与结构规格、解析有效背板模式并生成背板/背拉条；制造阶段只消费已确认板件方案，生成封边、连接、BOM 和孔位。意图和独立房间布局不得提前携带或解析背板结构。
- 外部技能只从 `external/text-to-cad/skills/` 按需加载：CAD/STEP/几何/快照用 `cad/SKILL.md`，审查/链接用 `cad-viewer/SKILL.md`，命名采购件用 `step-parts/SKILL.md`；忽略生成副本 `external/text-to-cad/plugins/cad/skills/`。
- 科学分析只从 `external/scientific-agent-skills/skills/` 按当前阶段按需加载，不把整个集合注册为家具技能：板件尺寸链/公差审计读 `uncertainty-and-units/SKILL.md`，板件多目标候选读 `pymoo/SKILL.md`；制造样件试验读 `experimental-design/SKILL.md`，已有试验数据读 `statistical-analysis/SKILL.md`，板件流转/工位排队读 `simpy/SKILL.md`。
- 科学分析是 `stage_analyses` 旁路证据，不是新的检查点，也不得直接覆盖 `stage_outputs`。候选方案经用户接受后，按字段所有者调用 `revise()` 或 `revise_stage_output()` 建立新 Revision，再重新确认受影响阶段及下游。
- 仅明确的一次性家具生成批处理可用 `domain/skills/furniture-cad/scripts/generate_furniture.py` 或 `execute_spec()`；`server.py` 的家具生成端点只适配协议并调用 Orchestrator，独立 `/api/plan-layout` 端点调用 `furniture-layout` 自有运行时。
- 声称可执行前检查实时代码、测试和入口；缺失则如实说明。

## 边界

- 已确认意图只定义家具类别和成品外包络；板件结构和制造方案分别以各自已确认的阶段输出为事实来源。六个串联 Skill 对应六个用户可见检查点，生成 CAD 前须确认 `design_intent`、`panels_planned`、`manufacturing_planned` 与 `feature_tree_planned`。房间布局是独立结果，不参与交付检查点谱系。
- `domain/skills/furniture-cad/scripts/furniture_workflow/` 是唯一应用层入口；CLI/API/Agent 仅适配协议。阶段规则归各 Skill，Orchestrator 只编排、记录状态/验证/产物谱系。
- 可复用脚本和运行时模块放在所属阶段 Skill 的 `scripts/`；跨阶段入口与集成测试放在 `domain/skills/furniture-cad/scripts/`。一次性检查、迁移、调试和实验统一放在已忽略的 `temp/<project-slug>/`，每个项目或任务独占一个目录，使脚本与派生产物可按目录整体识别和删除；任务结束即清理。生成 CAD 源码使用保留路径 `temp/cad-source/<artifact-name>/`。
- 禁止根级 `scripts/`、`packages/`、`tests/`、`scratch/`、`tmp/`；生成源码不得进入 `generated/`。工作区目录变更后运行 `domain/skills/furniture-cad/scripts/validate_workspace_layout.py` 并清零违规。
- 不修改 `external/text-to-cad` 实现家具逻辑；有上游意图/源码时不手改派生 STEP、GLB、BOM、裁切清单或 Python。
- 不修改或复制 `external/scientific-agent-skills` 来实现家具逻辑；家具输入适配、结果约束和可复用执行代码归对应家具阶段的 `scripts/`。科学技能缺少可选依赖时必须报告 `unavailable` 或使用明确标注的有界回退，不得伪装成已运行上游引擎。
- 只报告实际运行过的验证和实际存在的产物。
````

## File: CHANGELOG.md
````markdown
# 更新日志

## 20260901.2 — 层板高度化：`shelf_count` 移除，`shelves` 列表 + `top_gap_mm`，活动层板落地

层板规格从「数量 + 自动均分」改为「自上而下的逐层清单」，并真正生成活动层板（二合一/隔板钉按 `movable_shelf_connector` 选型出孔/BOM）。

### 契约（`FurnitureSpec`）

- 删除 `shelf_count`（无向后兼容迁移，测试夹具 `_fill_shelves` 仅为测试便利转换）。
- 新增 `shelves: list[ShelfSpec]`，自上而下（视觉顺序）逐层描述，每层 `{shelf_type: fixed|movable, gap_below_mm: 净高|null}`。
- 新增 `top_gap_mm: float`：最上层板顶面到顶板底面的净高。
- `gap_below_mm` = 本层板底面到下方紧邻一层顶面的净高；最末层为到底板顶面。`null`(=auto) 表示由代码吸收剩余高度，**恰好一个** auto（或 0 个且各净高之和正好铺满内高）。
- 抽屉校验改为 `drawer_count and (shelves or n_doors)`：有抽屉时层板清单必须为空。

### 代码

- `panel_spec.py`：`ShelfSpec` 冻结数据类、`_coerce_shelves()` 校验与 `resolve_shelf_gaps()` 确定性算高（auto = 内高 − top_gap_mm − N×板厚 − Σ显式净高）。
- `topology_solver.py`：`_shelves_from_spec()` 自上而下累加定位，fixed→`fixed_shelf`（cam_face=底板 `frame.bottom`，id=`shelf_z{cz}`），movable→`movable_shelf`（cam_face=None，id=`movable_shelf_z{cz}`）。
- 板件规划/布局/工作流/服务端（`server.py` `CabinetRequest`）同步删除 `shelf_count`，改传 `shelves` + `top_gap_mm`；布局阶段保留 `door_count`。

### 验证

- `spec.shelves=[movable(200), fixed(auto)] top_gap=150` 端到端生成 `fixed_shelf` 与 `movable_shelf`；`TwoInOneConnector` 出 `two_in_one_cam/rod`，`ShelfPinConnector` 因选型为 two_in_one 返回空。
- 目标回归 30 项通过（`test_cabinet_pipeline` / `test_api_entrypoint` / `test_back_mount_modes` / `test_recent_manufacturing_patches.PanelAndConnectorPatchTests` / `.DrawerZoneTests`）；仅环境性 `%TEMP%` 写权限失败与本次改动无关。

## 20260901.1 — 五金命名统一（part/hole 分层）+ 二合一/隔板钉拆分 + 活动层板选型

将三套五金（三合一/二合一/隔板钉）与铰链的名称、参数和目录统一，并把「零件实物规格」与「打孔规格」分离为 `part`/`hole` 两层；活动层板连接方式（二合一 vs 隔板钉）改为显式选型。

### 目录（hardware_catalog.yaml）

- 顶层按套命名：`three_in_one` / `two_in_one` / `shelf_pin`；铰链 `hinges.*` 条目同样按 `part`/`hole` 分层。
- 每个打孔件拆 `part`（实物 → BOM/采购，暂标「待定」）与 `hole`（打孔 → 钻孔）；定位类固定参数（`rod_axis_to_cam_face_mm`、`shelf_bottom_offset_mm`）留在零件顶层。
- 参数直接存、不做代码派生：三合一轮孔边距 `cam.hole.edge_offset_mm=33.5`（原为 `insertion_depth+0.5` 派生）；`rod_axis_offset_mm` → `cam.rod_axis_to_cam_face_mm=9`；`pre_embedded_nut` → `nut`；删除 `base.cam_offset_from` / `base.rod_length_from`。
- 二合一偏心轮 `cam.hole.edge_offset_mm=4.5`、`cam.rod_axis_to_cam_face_mm=9`；隔板钉 `pin.hole=5×9`、`pin.shelf_bottom_offset_mm=2.5`（层板底面比钉孔中心高 2.5）。

### 孔类型标识（hole_type，进 drilled-holes.json / GLB 标签 / 校验）

- `system_32_female/male/pre_nut` → `three_in_one_cam` / `three_in_one_rod` / `three_in_one_nut`（修正原 female/male 与板件公母语义相反）。
- `back_insert_pre_nut` → `back_insert_nut`。
- 新增 `two_in_one_cam` / `two_in_one_rod`、`shelf_pin`。

### 代码

- `ShelfConnector`（混搭「层板托」与「二合一」）拆为 `TwoInOneConnector`（二合一：偏心轮+连接杆）与 `ShelfPinConnector`（隔板钉：单钉），均读目录 `hole`、不再硬编码；无活动层板时 BOM 返回空（修复「二合一连接件 ×0套」挂空行）。
- 铰链 `HingeConnector` 打孔读取由 `cup`/`edge_offset_mm` 改为 `hole.diameter_mm/depth_mm/edge_offset_mm`。
- 三合一/背板/铰链/二合一/隔板钉的打孔尺寸全部来自目录 `hole`，无字面量硬编码。

### 活动层板选型

- `FurnitureSpec` 新增必填枚举 `movable_shelf_connector`（`two_in_one` / `shelf_pin`，无软默认、非法值拦截）；`CabinetRequest` 同步暴露；制造阶段盖章到 `PanelRecord`，两个连接件按值过滤，避免同时出孔/BOM。
- 默认候选 `two_in_one` 仅在 LLM 提案层体现（`furniture-panel-planning/SKILL.md`），代码不静默补值。

### 备注

- `movable_shelf` 面板当前未由板件规划生成，二合一/隔板钉连接件为休眠占位；其几何定位（前后排、杆轴对齐、层板侧边投影）标「软件暂定，投产前确认」。
- 各五金 `part`（实物规格）标「待定」，待提供后 BOM 规格串改为读 `part`。

### 验证

- 三合一/背板/抽屉/铰链/API 相关测试通过；`test_api_entrypoint` 5 项 OK；非法枚举被拒；选型过滤正确。

## 20260825.1 — 房间布局从家具生成主流程拆分

- 家具生成主流程由七阶段改为六阶段：`design_intent → panels_planned → manufacturing_planned → feature_tree_planned → cad_generated → delivery_validated`。
- `furniture-layout` 改为明确请求房间摆放、碰撞检查、SVG 或互动 Viewer 时才运行的独立能力；普通家具生成不再创建默认卧室或摆放图。
- `shelf_count/n_doors/door_count` 改由 `panels_planned` 直接从 `stage_inputs.panels.parameters` 物化，板件阶段只依赖已确认 `DesignIntent`。
- CAD 交付不再生成或要求 `layout-plan.json`；独立布局结果不进入 `STAGE_SEQUENCE`、`approved_stages` 或交付谱系。
- `/api/plan-layout` 保留为独立端点，房间越界、门窗/障碍物碰撞和 SVG/Viewer 行为不变。

### 验证

- 家具 CAD 集成测试 91 项通过。
- 工作区目录布局校验通过。

## 20260822.8 — 抽屉盒默认三合一 + TrinityConnector 泛化（轴无关）

全屋定制抽屉盒主流用三合一连接（木销+胶为少数），改为默认；连接布置按确认方案。

### 连接布置（每抽 8 连接 × 2 排 = 16 套三合一）

- 底板 ↔ 侧板（x 轴，2 侧）：male=底板，cam_face=`-z`（偏心轮在底板下面，抽屉外部操作）。
- 底板前端 ↔ 前板 / 底板后端 ↔ 背板（y 轴）：male=底板（cam 仍在 `-z`），female=前板/背板。
- 前板 ↔ 侧板（y 轴）：female=前板，male=侧板，cam_face=`±x`（侧板外侧面）。
- 背板 ↔ 侧板（x 轴）：female=侧板，male=背板，cam_face=`-y`（背板外侧面）。

### 改动点

- `TrinityConnector.generate_holes_for_panels` 重写为**连接驱动、轴无关**：螺母/杆/轮按 joint 的
  边轴（x/y）+ cam 面轴 + 第三轴推导，替代原"x 轴 + 横板 male（cam ±z）"假设；`_nut_holes`/
  `_rod_holes`/`_cam_holes` 新 builder；`generate_holes` 保留为无拓扑旧数据回退。
- 连接判定 `_is_trinity_joint`：抽屉子装配内部 x/y 轴接触均为连接；柜体仅 x 轴（层板后 y 端面
  搁背板前面是接触不是连接，不再误生成螺母孔）。
- `joint_topology.compute_joints`：排除抽屉↔柜体跨装配接触（抽屉是滑动子装配）。
- `_drawer_panels`：侧板按滑轨间隙内缩（`slide_gap`）；底板 y 向延伸到前板；背板底边与底板齐平
  （底板后端连接杆轴线才能落在背板内）；各板 `cam_face` 按布置赋值。
- **顺带修正**：柜体层板连接"螺母/杆前排错位 27mm"（螺母原按自身跨度、现按 male 跨度对齐，
  层板前排螺母 world y 64→91）；侧板螺母数不变。

### 验证

- 57 项测试通过（抽屉默认三合一新测试替代原"无三合一"断言）。
- 抽屉柜 1:1:1（杆=轮=螺母=24/抽含柜体）；底板 8 轮孔全在底面（z_local=0、方向 +z）。
- 柜体（drawer_count=0）侧板 12 螺母、层板 8 孔、背板 0——仅层板前排螺母对齐修正 4 处。

## 20260822.7 — 修复抽屉侧板被误判为三合一母件

抽屉盒体不用三合一（现实工艺为木榫+胶/螺丝）；但 `_trinity_female` 的拓扑判定
只查 `face[1]=="x"`、未校验 `male_has_cam`，导致抽屉侧板（与抽屉底板/背板存在
x 面邻接）被误判为三合一母件，走 fallback 全高排钻打出系统 32 预埋螺母孔
（且仅左侧板出现，不对称）。

### 修复

- `connectors/trinity.py`：`_trinity_female` joint 判定补 `j.male_has_cam` 条件
  （与 `_trinity_male`/`_female_holes` 一致）；抽屉板件 `cam_face=None` → 不再误判。
- 测试：`test_drawer_panels_have_no_trinity_holes`（抽屉板件零三合一孔，carcass 孔位不变）。

### 验证

- 57 项测试通过；抽屉 15 板零孔；carcass 孔位不变（bottom 8 / 侧板各 4 / top 8）。

## 20260822.6 — 抽屉区首版落地（档 B：整高抽屉区 + 无面板 + 三节轨）

`drawer_count` 驱动的整高抽屉区打通板件规划→制造全链路。

### 改动点

- `FurnitureSpec` 新增 `drawer_count`（默认 0，向后兼容）+ `PANEL_SPEC_FIELDS` 白名单 + `from_dict` 解析（走 options 路径，layout 不感知）。
- `floor_cabinet.yaml` 新增 `internals.drawers` profile（type=full_height、slide_type、face_mode=none、layer_gap 1.5、底/背板厚 18、back_clearance≥0）；滑轨间隙**单一真源** = catalog `gap_requirement_mm`（按文件路径读取，不 import 制造模块）。
- `topology_solver._drawer_panels`：每抽屉 5 板（前/左/右/后/底），label 契约 `drawer_*_z{pos}`；底抽前板全盖底板（overlap=18）、顶/中 0；抽屉优先——`drawer_count>0` 时不生成门与固定层板。
- 板件校验：`drawer_count>0` 且 `n_doors>0`/`shelf_count>0` 时发 warning（`DRAWER_ZONE_SUPERSEDES_*`），不静默。
- `hardware_catalog.yaml`：三节轨 `gap_requirement_mm` 12.5→**13.0**（投产前确认）。
- 封边：`DEFAULT_EDGE_RULES` 补 `drawer_*` 四边 ABS 同色。
- 清理：layout 测试中"未知字段"样例由 `drawer_count` 换为 `unsupported_layout_option`（drawer_count 已是合法面板输入）。
- 测试：新增 `DrawerZoneTests` 5 条（5 板/抽、底抽覆盖、BOM 滑轨 ×6、warning、向后兼容）。

### 验证

- 56 项测试通过（51 + 5 新增）。
- `drawer_count=0` 全回归不变；滑轨 BOM：3 抽 → 数量 6、长度按抽屉深 535→450mm。

## 20260822.5 — 记录抽屉组件级实体需求（待评审提案）

抽屉本质是子装配组件（板件集合+盒体拓扑+滑轨/拉手五金），当前板件规划不生成抽屉板件。

### 内容

- 新增 `domain/skills/furniture-manufacturing/references/drawer-component-design.md`：背景、现状、**契约 3 条**（panel_type 含 `drawer`、尺寸取自抽屉板件自身、实例 key = label 位置后缀且每抽 1 副）、需求（抽屉组件物化、layout `drawer_count` 启用或清理、滑轨长度校验、五金变体注入）、实施建议。
- `SKILL.md` 步骤 4 与连接点需求并列加指引，标注"实施前需评审"。

## 20260822.4 — 抽屉滑轨 Connector 化（档 A：纯重构）

`DrawerSlideConnector` 落地，抽屉滑轨从"特例函数"迁入标准 Connector 路径，消灭死代码。

### 改动点

- 新增 `connectors/drawer_slide.py`：`DrawerSlideConnector`（`catalog_entry="drawer_slides"`），按抽屉实例匹配长度/承重/品牌；滑轨螺钉为组装现场工艺，不生成孔位。
- 修复潜在 bug：滑轨数量从"整柜固定 2"改为"每抽一副（左右各 1）× 抽屉实例数"，不同规格分条记录。
- `connectors/__init__.py`：注册 `ALL_CONNECTORS`；`manufacturing_bom.py`：删除滑轨特例块与 import。
- 删除死模块 `manufacturing_hardware.py`（`match_drawer_slides` 原所在，无其他引用）。
- 测试：新增 2 条——按抽屉实例出 BOM（数量/长度/品牌）、无抽屉板件时不产出滑轨。

### 验证

- 51 项测试通过（49 + 2 新增）。
- 无抽屉柜型 BOM 零变化（DrawerSlideConnector 空输出）。
- 契约面向"抽屉组件"（见 20260822.5），档 B 抽屉板件落地时滑轨自动生效。

## 20260822.3 — direction 语义统一为钻入方向

`HoleSpec.direction` 统一为"钻入方向（往板内）"（`coordinate-naming.md` 约定），
消除"杯孔/偏心轮存面朝向、螺母/杆存钻入方向"的混合语义。

### 改动点

- `connectors/hinge.py`：杯孔 direction 从 `inner_face`（面朝向）改为 `_opposite(inner_face)`（钻入方向），新增 `_opposite` 助手。
- `connectors/trinity.py`：偏心轮孔 direction 从 `cam_face` 改为 `_opposite(cam_face)`。
- `furniture_panel_planning/panel_face.py`：`cup_direction`/`cam_direction` 语义同步改为钻入方向（该辅助当前无调用方，纯语义定义修正）。
- `validation.py`：铰链方向校验改为 `hole["direction"] != _opposite(panel.inner_face)`。
- 测试：`test_recent_manufacturing_patches.py` 铰链方向断言 `-y → +y`（1 处）。
- 文档：`coordinate-naming.md` ⚠"待落地"→✅"已统一"、`manufacturing-rules.md`、`SKILL.md` 方向措辞同步。

### 验证

- 3 柜型（地柜 cover/insert + 吊柜）JSON diff 仅 direction 翻转（cam `-z→+z`、铰链 `-y→+y`），其余字段逐字相同。
- GLB 孔位标记网格顶点多重集逐点相等——几何零变化，产物差异仅为旋转表示。
- 六面钻 XML/Quadrant 零影响（Quadrant 仅用于边孔，边孔方向本就为钻入方向）。
- 47 项测试通过。

### 遗留

- 前端 Viewer 是否消费 `drilled-holes.json` 的 `direction` 字段待确认（GUI 代码不在本仓库）。

## 20260822.2 — 记录连接点级实体需求（待评审提案）

记录"连接点作为整体增删"的需求，**未立项、未实施**。

### 内容

- 新增 `domain/skills/furniture-manufacturing/references/connection-point-design.md`：背景（杆/轮/螺母配对为几何隐式约定）、现状行为表（删轮孔被拦、删杆孔静默孤儿、背板 1:1:1 拦截）、需求 4 条（整体增删、按连接点校验、配对显式化、machining id 去重）、实施建议与验收标准。
- `SKILL.md` connectors 步骤加指引行，标注"实施前需评审"。

## 20260822.1 — 三合一/背板/层板孔位局部坐标化

孔位先在面板局部坐标定义（局部为唯一真源），世界坐标统一由 `to_global` 派生
（当前轴对齐：仅平移）。不涉及字段改名（按"搭车改、不单独改"）。

### 改动点

- `connectors/trinity.py`：`_female_holes` 螺母孔 Z 先算局部（joint 高度 − `panel.pos_z`），删除 `x_local = x_global - panel.pos_x` 反推；`_male_holes` 世界坐标全部由 `to_global` 派生，删掉手工并行计算；保留旧发射顺序（先全部杆孔再全部轮孔）。
- `connectors/back_mount.py`：连接点以背板局部坐标为锚，配合板按同一世界点折算到各自局部坐标；`_hole` 改为收局部坐标、内部统一 `to_global`。
- `connectors/shelf.py`：层板托孔局部优先，世界由 `to_global` 派生。

### 验证

- 4 柜型（地柜 cover/insert/groove + 吊柜）改前/改后孔位 JSON 快照**字节级一致**（244578 字节）。
- 所有孔位满足 `world == to_global(local)`。
- 41 项测试通过。

### 遗留

- 字段改名（`x_local → hole_x` 等）：`coordinate-naming.md` P3 触发条件现已满足，仍按"搭车改、不单独改"等待下游需求。

## 20260819.2 — 铰链死接口清理（五金类目决策：路线 B）

经五金类目讨论拍板，采纳路线 B（整体移除）：`hinge_brand / hinge_variant / hinge_overlay / hinge_angle` 四个参数自 20260817.1 精简目录后已成死接口（API/适配器接受并回显，`HingeConnector` 不消费），删除以消除"收了不生效"的静默失效风险。决策依据见 `temp/hardware-category-decision/PROPOSAL.md`。

### 移除点

- `server.py`：删除 `CabinetRequest` 四个铰链偏好字段（`hinge_brand/hinge_variant/hinge_overlay/hinge_angle`）。
- `input_adapter.py`：`MANUFACTURING_SPEC_FIELDS` 仅保留 `options`。
- `workflow_project.py`：`_legacy_stage_inputs` 制造搬运白名单仅保留 `options`。
- `manufacturing_bom.py`：`MANUFACTURING_OPTION_FIELDS` 仅保留 `options`。
- `hardware_rules.yaml`：删除 `bore_distance_mm` 注释残留（杯孔边距由 `edge_offset_mm + cup_diameter/2` 现算，无消费方）。
- `test_furniture_orchestrator.py`：删除 `test_input_adapter_routes_hinge_preferences_to_manufacturing`（只测回显、语义已死）。

### 影响

- 孔位/BOM/六面钻 XML 零变化（死字段本就无消费；探针已验证磁盘产物与代码一致）。
- 铰链仍为单一默认 `35mm杯全盖 100° full`（`hardware_catalog.yaml` 不变）。
- 未来如需多盖法/品牌：按经验层设计（`temp/experience-layer-design/DESIGN.md` §6.3 候选-拍板）以真参数形态回归，品牌经 `factory_profile.yaml` 厂规注入。

### 遗留（完整总账见 `temp/hardware-category-decision/PENDING.md`）

- 路线 B 改动**未提交**（7 文件在工作树，待 review 后 commit）。
- 四边盖值模型（铰链边+三边）讨论中：已共识"铰链边为主、默认联动、先做第 1 层"；宽度口径/对开门中缝/铰链型号映射/特殊角度排除 4 点待拆单员拍板。
- 经验层 `temp/experience-layer-design/` DESIGN.md 待评审 + 5 个开放问题 + EXPERIENCE-CHECKLIST 8 类厂规待填。
- `direction` 语义统一与坐标字段改名：按策略 P3 搭车改，不单独动。

## 20260817.1 — 三合一几何正确性修复 + 孔即真源 + 铰链局部坐标化

### 三合一孔位几何修正（connectors/trinity.py, joint_topology.py, hardware_catalog.yaml）

- 偏心轮孔 cam_face 坐标映射反转修复：`cam_face="+z"` 落在顶面、`"-z"` 落在底面（原先写反）。
- 连接杆孔/预埋螺母孔高度从"板厚中心"改为"偏心距驱动"：新增 `rod_axis_offset_mm: 9`（连接杆轴线到偏心轮安装面的距离），25mm 板下不再错位。
- 偏心轮圆心修正：沿连接杆方向(x)距端面 `center_offset_from_edge_mm`(33.5)，深度方向(y)与连接杆同排（原先 33.5 被误用在深度方向）。
- `PanelJoint` 新增 `male_cam_face`/`male_size_z`，供制造阶段由 cam_face + 偏心距反推连接杆轴线高度。

### 孔即真源（connectors/trinity.py, validation.py）

- 三合一 BOM 数量从"系统 32 排钻估算"改为"统计实际生成的偏心轮孔数"，消灭数量≠孔数。
- 新增校验：三合一数量必须等于偏心轮孔数。

### 几何接口地基（manufacturing_models.py）

- `PanelRecord` 新增 `face_position`/`extent`/`center_along`/`to_global`/`to_local`，为局部坐标化与异形内核铺路。

### 铰链目录精简（hardware_catalog.yaml, hardware_rules.yaml, hinge.py）

- 铰链规格从 13 种（国内/进口 × 全盖/半盖/内嵌，共 11 品牌）精简为 1 个默认 `35mm杯全盖 100°`。
- `cup_by_variant_group` 同步精简为单个 `35mm杯全盖`。

### 铰链局部坐标化（connectors/hinge.py）

- 杯孔生成从"先算全局、再反推局部"反转为"先在局部定义、`to_global` 派生"，局部坐标成为唯一真源。

### 文档与测试

- `manufacturing-rules.md` 三合一偏心轮规则与铰链"国产全盖"措辞同步。
- `test_recent_manufacturing_patches.py` 三合一偏心轮 x/y 断言更新。

### 背板螺钉删除（组装现场工艺，不加工）

- cover 外盖螺钉与 groove 背拉条螺钉的孔位（clearance 通孔 + pilot 预孔）与五金 BOM 全部删除——它们是组装现场工艺，非柜体加工。
- `BackMountConnector` 只保留 insert 内嵌背板四边三合一；catalog 删除 `back_fasteners`，rules 删除 cover/back_rail 打孔规则。

### 坐标命名约定（references/coordinate-naming.md）

- 新增命名约定文档：三层坐标 panel/cabinet/world，`对象_参考系_轴` 命名规则，
  `hole_x`/`hole_cabinet_x`/`panel_cabinet_x`/`panel_world_x`/`cabinet_world_x` 五层量，
  以及圆心=入口面圆心、direction=钻入方向、废弃 `global` 等约定。
- 现有代码字段未动，按"搭车改、不单独改"策略，待 P3 局部坐标化/direction 统一/2.5D 时落地。

### 遗留（待五金类目讨论）

- `hinge_brand/hinge_variant/hinge_overlay/hinge_angle` 参数成为死接口（catalog 已精简，连接件不消费）。
- `bore_distance_mm` 仍为死配置。

---

## 20260814.1 — 房间坐标 Y 轴约定统一

- 房间坐标 Y 轴从"向北"调整为"向南"（俯视朝下），原点从"西南角"改为"西北角"。
- 标准柜体默认贴北墙、门朝南，此时柜体局部坐标与世界坐标完全一致（零旋转）。
- 默认摆放从"沿南墙居中"改为"沿北墙居中"，`placement_source` 标记改为 `default_north_wall_centered`。
- 沿墙偏移方向纠正为顺时针：`north` 西→东、`east` 北→南、`south` 东→西、`west` 南→北。
- 同步修正 `room_planning` 的旋转/原点/净距/门窗跨度计算，以及 SVG/Viewer 的门窗渲染坐标。

---


## 20260731.3 — 默认卧室与三维包络预览

- 未提供房间时，第 2 阶段使用 `4200×3600×2800 mm` 的“默认卧室（系统假设）”。
- 未提供摆放位置时，柜体默认沿南墙居中；只提供房间或位置时补齐缺失项。
- `layout_planned` 增加 `layout_context` 来源标记，成功输出必须包含房间定位和 SVG 预览。
- SVG 从俯视平面图改为近大远小的透视三维包络：房间透明，家具为不透明长方体，门窗和障碍物保留空间标识。
- `layout_planned` 增加自包含 HTML 互动 Viewer，支持拖拽环绕、滚轮缩放及透视/正视/左视/右视/俯视切换。
- FastAPI 版本更新至 `0.5.0`，无房间输入也可直接取得布局预览，并增加 `/api/plan-layout/viewer`。

---

## 20260731.2 — 房间定位与第 2 阶段 SVG 预览

- `furniture-layout` 增加矩形房间、门窗和长方体障碍物模型。
- 支持按南/东/北/西墙与沿墙偏移自动定位，也支持自由坐标和旋转定位。
- `layout_planned` 增加标准化房间变换、四角占地、六向净距和内联 SVG 平面预览。
- 布局校验增加房间越界、层高、门窗遮挡、障碍物碰撞及预览谱系检查。
- FastAPI 增加 `/api/plan-layout` 和 `/api/plan-layout/preview`。

---

## 20260731.1 — 最近制造/六面钻更新的稳定性补丁

- 柜型拓扑移回 `furniture-panel-planning/references/cabinet-topologies/`，
  避免设计意图阶段承载板件构成。
- 单门和标准双门显式写入铰链侧；铰链杯孔继续使用杯心距边与门板内侧面。
- `drilled-holes.json` 补齐 `panel_type`，三合一前后双排、板面孔/板边孔和
  4.5mm 螺钉直通孔增加回归测试。
- 六面钻 XML 统一使用板件局部坐标，并将水平孔方向从世界轴转换到机床轴；
  修复 Z1、Quadrant、重复闭合顶点和缺失局部坐标的问题。
- 槽位尚无设备契约时明确拒绝导出，不再静默漏加工。
- 孔位 STEP 导出不再吞异常或覆盖普通 GLB；动态板件按来源角色分组。
- 孔位 STEP/Viewer 侧车与逐板六面钻 XML 全部登记进 Manifest 和交付必需项。

---

## 20260729.2 — 六面钻 XML 导出修正 + 三合一打孔逻辑修复

### 六面钻 XML 导出 (export_six_side_drill.py)

**修正 1：TypeNo 判定基准修正**
- 原因: 原先用世界坐标 ±z 区分垂直/水平孔 (TypeNo=1/2)，但板件在机床上的放置方向可能使 ±x 方向变为垂直孔
- 修复: 引入 `is_face_hole` 属性到 `HoleSpec`，由连接件生成孔时直接标记面孔/边孔，XML 导出层直接读取
- 涉及文件: `connectors/base.py` (新增字段), `connectors/trinity.py`, `connectors/hinge.py`, `connectors/back_mount.py`, `connectors/shelf.py`, `manufacturing_bom.py`, `export_six_side_drill.py`

**修正 2：PanelOutline 顶点 X/Y 写反（板子转了 90°）**
- 原因: `_make_panel_xml` 中 outline 用 `(width_2d, length)` 当作 X/Y，实际 PanelLength 是 X 轴
- 修复: 变量改为六面钻语义 `sixd_x`(机床X轴), `sixd_y`(机床Y轴), `sixd_z`(板厚)，outline 顶点改为 `(sixd_x, sixd_y)` 顺序

**修正 3：语义重命名**
- `hardware_catalog.yaml` 和 `devices/six_side_drill_guigui.yaml` 全部增加中文注释
- YAML key: `length_from_box` → `sixd_x_from_box`, `width_from_box` → `sixd_y_from_box`
- Python 变量: `length` → `sixd_x`, `width_2d` → `sixd_y`, `thickness` → `sixd_z`

### 三合一打孔逻辑修复 (connectors/trinity.py)

**修正 4：深度方向单排→双排**
- 原因: 原先每个高度层只打 1 个预埋螺母 (Y 固定在 depth-33.5)，三合一应该是前后各一个
- 修复: 预埋螺母/连接杆 Y 位置改为 `[first_hole_mm, depth - last_hole_mm]` 双排（默认 [64, depth-64]）
- 偏心轮 Y 位置改为 `[center_offset_from_edge, depth - center_offset_from_edge]` 双排

**修正 5：交叉补充预埋螺母也改为双排**
- `generate_holes_for_panels` 的去重逻辑从 1D (仅 Z) 改为 2D (Z + y_local)，每处补两个

### 铰链孔位修正 (connectors/hinge.py)

**修正 6：铰链 Y1 用杯心距边**
- 原因: 原先 Y1=edge_offset=5mm（铰链臂侧边距），柜柜 Y1=22.5mm
- 修复: Y1 = `edge_offset + cup_diameter/2 = 5 + 17.5 = 22.5`，杯孔中心到门边的真实距离

### 五金规则检查

全面校验了 3 个 YAML 文件中所有 21 个规则值，全部正确：
- `system_32_drilling`: first/last 64mm, max 512mm, min 32mm ✅
- `hinge_drilling`: edge_offset 5mm, cup φ35×13 (国产全盖) ✅
- `back_mount_drilling`: insert/cover/back_rail 三模式正确 ✅
- `catalog/three_in_one`: φ12 偏心轮, φ8 连接杆, φ10 预埋螺母 ✅
- `devices/six_side_drill_guigui`: side/horizontal/door/toe_kick/default 面板放置正确 ✅

### 与柜柜的差异分析（仅记录，本次未修改）

| 差异 | 原因 | 说明 |
|---|---|---|
| 背板安装模式 | `resolve_back_mount()` auto→groove | 柜柜用 insert |
| 背拉条连接件 | groove 模式用螺钉 | 柜柜用三合一 |
| 踢脚板无三合一 | TrinityConnector 不匹配 toe_kick | 规则值正确，代码匹配范围可扩展 |
| 背板槽未导出 | export_six_side_drill 不处理 TypeNo=3 | 未来可加 |

### SKILL 文档更新

- `SKILL.md`: 更新连接件和六面钻导出描述
- `references/manufacturing-rules.md`: 更新孔位生成规则说明

---

## 20260729.1 — 拓扑驱动重构 + 方向错误修复

### 架构变更：拓扑数据 + 通用求解器

引入三层新抽象，将柜体结构从硬编码改为数据驱动：

1. **`CabinetFrame`** (`cabinet_frame.py`) — 柜体方向模型
   - 用 `front` + `top` 两个方向定义柜体朝向，右手定则自动推导其余四面
   - 落地柜: `front="+y", top="+z"`；未来榻榻米: `front="+z", top="-y"`

2. **`PanelFace`** (`panel_face.py`) — 板件面语义模型
   - 每块板件携带 `inner_face`（朝柜内面）、`outer_face`（朝柜外面）、`cam_face`（偏心轮可操作面）
   - 连接件不再硬编码钻孔方向，改为通过面语义推导

3. **`topology_solver.py`** — 通用空间求解器
   - 读取 YAML 拓扑数据 + FurnitureSpec + CabinetLayout → 计算 PanelPlacement[]
   - 不按柜体类型分支，新增柜型只需增加一份 YAML 拓扑文件

4. **拓扑数据文件**
   - `cabinet_topologies/floor_cabinet.yaml` — 落地柜拓扑
   - `cabinet_topologies/wall_cabinet.yaml` — 吊柜拓扑

### 方向错误修复

**修复 1：右侧板预埋螺母孔打反了**
- 原因: `trinity.py` 对所有竖板写死 `x_global = pos_x + size_x`, `direction="-x"`
- 左侧板 (pos_x=0) → x_global=18, 方向"-x" ✅ 正确
- 右侧板 (pos_x=582) → x_global=600, 方向"-x" ❌ 打到外侧面去了
- 修复: 左侧板 inner_face="+x" → 螺母方向="-x"；右侧板 inner_face="-x" → 螺母方向="+x"

**修复 2：顶板/底板/固定层板偏心轮方向全统一"+z"**
- 原因: `trinity.py` 偏心轮写死 `direction="+z"`（从顶面钻入）
- 实际: 偏心轮应从可操作面钻入（通常为底面 "-z"），安装后顶面被相邻板挡住
- 修复: 偏心轮方向 = `panel.cam_face`，顶板/底板/层板的 cam_face 设为 "-z"

**修复 3：铰链杯孔方向硬编码 "+y"**
- 原因: `hinge.py` 写死 `direction="+y"`
- 修复: 杯孔方向 = `panel.inner_face`，门板内侧面由拓扑规划器标记

**修复 4：层板托孔打在了层板自身上**
- 原因: `shelf.py` 对 movable_shelf 自身打孔
- 修复: 层板托孔改打侧板内侧面（这是受力支撑点）

### 数据模型扩展

- `PanelPlacement` 新增 `inner_face: str`, `outer_face: str`, `cam_face: str | None`
- `PanelRecord` 新增同样三个字段
- `_manufacturing_panel()` 传递 face 字段到 PanelRecord

---

## 当前程序存在问题清单

### 🔴 已知 Bug（方向/坐标错误）

| # | 问题 | 位置 | 状态 |
|---|------|------|------|
| 1 | 右侧板预埋螺母孔打到外侧面 | trinity.py | ✅ 本版已修复 |
| 2 | 顶板/底板/层板偏心轮方向硬编码"+z"，不可操作 | trinity.py | ✅ 本版已修复 |
| 3 | 层板托孔打在层板自身，应在侧板内侧面 | shelf.py | ✅ 本版已修复 |

### 🟡 架构问题（缺失抽象）

| # | 问题 | 位置 | 状态 |
|---|------|------|------|
| 4 | 面板方向由位置隐式推断（pos_x+size_x 猜内侧面），右侧板猜错 | trinity.py, hinge.py | ✅ 本版引入 PanelFace 解决 |
| 5 | 柜体结构硬编码在 cabinet_panel_planner.py 中，无法扩展 | cabinet_panel_planner.py | ✅ 本版引入拓扑 YAML + 求解器解决 |
| 6 | 世界坐标系硬编码在 feature_tree_builder.py | feature_tree_builder.py | ⚠️ 仍硬编码，需改为从 CabinetFrame 生成 |

### 🟠 功能缺失

| # | 问题 | 位置 | 状态 |
|---|------|------|------|
| 7 | 活动层板 (movable_shelf) 根本不生成 | cabinet_panel_planner → topology_solver | ⚠️ 拓扑 YAML 未定义 movable_shelf |
| 8 | 抽屉完全不生成（面板、滑轨） | 整个 pipeline | ⚠️ 未实现 |
| 9 | 木榫完全不生成 | 五金层 | ⚠️ 未实现 |
| 10 | 拉手/拉直器完全不生成 | 五金层 | ⚠️ 未实现 |
| 11 | 铰链选型硬编码"国内35mm杯全盖 100°"，catalog 有 14 种只用 1 种 | hinge.py | ⚠️ 未实现 |
| 12 | hole_type 硬编码 "hinge"，与 hinge_brand/hinge_variant/hinge_overlay/hinge_angle 字段脱节 | hinge.py, FurnitureSpec | ⚠️ 字段定义了但未使用 |

### 🔵 规则未执行

| # | 问题 | 位置 | 状态 |
|---|------|------|------|
| 13 | 冲突检测规则定义了但从未执行 | hardware_rules.yaml §conflict_avoidance | ⚠️ 规则有，代码无 |
| 14 | drill_length_by_type 在 YAML 定义了，代码用另一套 if-elif | hardware_rules.yaml + manufacturing_bom.py | ⚠️ 两处不一致 |
| 15 | 排钻起步面未定义（drill_length 只定义长度，不定义从哪个边开始） | trinity.py _system_32_positions | ⚠️ 靠 first_hole_mm=64 隐式假定 |
| 16 | hinge_brand / hinge_variant / hinge_overlay / hinge_angle 在 FurnitureSpec 定义了但连接件不读取 | FurnitureSpec → hinge.py | ⚠️ 字段空置 |

### ⚪ 间隙规则缺失

| # | 问题 | 位置 | 状态 |
|---|------|------|------|
| 17 | 活动层板减尺量未定义（宽度应比内空小 2-4mm） | 未建模 | ⚠️ 需在拓扑或 spec 中定义 |
| 18 | 门板上下间隙应有别于左右间隙（上紧下松） | 未建模 | ⚠️ 目前 door_margin 四周统一 |
| 19 | 抽屉面板减尺未定义 | 未建模 | ⚠️ 依赖抽屉整体功能 |

### 其他

| # | 问题 | 位置 | 状态 |
|---|------|------|------|
| 20 | 榻榻米/床箱等水平柜体完全不支持 | 整体架构 | ⚠️ 拓扑数据 + CabinetFrame 已铺路，需增加 tatami_base.yaml 拓扑 |
| 21 | 转角柜不支撑 | 整体架构 | ⚠️ 拓扑需扩展多翼（multi-wing）描述 |

---

## 20260715.1

### 封边规则修正
- 所有柜体板件（侧板/顶板/底板/固定层板/活动层板/中竖板/踢脚板/门板）统一四边封边 ABS 1.0mm 同色
- 背板插槽模式不封边，内嵌/外盖模式四边同色

### 背板槽位置修正
- `groove_y = back_offset`，槽后壁对齐背板后面，间隙全放前面

### 三种背板安装方式 (back_mount)
- `FurnitureSpec` 新增 `back_mount: str = "auto"` 字段 + `resolve_back_mount()` 推导函数
- `"auto"` → `back_thickness >= board_thickness` 时 `"insert"`，否则 `"groove"`
- `"groove"` / `"insert"` / `"cover"` 可显式指定
- `CabinetLayout` 新增 `back_mount` 字段，`from_spec()` 按模式分流 side_depth / back_plane_y / internal_y_start
- `build_cabinet_panels()` 按三种模式生成不同尺寸/位置的背板
- `_edge_banding_for()` 控制背板封边；`_back_groove_operations()` 只在 groove 返回 4 条槽

| 模式 | side_depth | back_plane_y | 背板尺寸 | 槽 | 封边 |
|------|-----------|-------------|---------|-----|------|
| groove | d - door - hinge | back_offset(18) | int + 2×groove | 4条 | 无 |
| insert | d - door - hinge | back_offset(18) | int_w × int_h | 0 | 四边同色 |
| cover | d - door - hinge - back | 0 | width × height | 0 | 四边同色 |

### 背板拉条 (groove 模式)
- `FurnitureSpec` 新增 `back_rail_height: float = 70.0`
- 数量 = `internal_height // 500`，均分间隙
- 拉条类型 `back_rail`，Y 方向占 0~board_thickness，夹在左右侧板之间

### 封边规则修正
- 所有柜体板件（侧板/顶板/底板/固定层板/活动层板/中竖板/踢脚板/门板）统一四边封边 ABS 1.0mm 同色
- 背板插槽模式不封边，内嵌/外盖模式四边同色

### 背板槽位置修正
- `groove_y = back_offset`，槽后壁对齐背板后面，间隙全放前面

### 三种背板安装方式 (back_mount)
- `FurnitureSpec` 新增 `back_mount: str = "auto"` 字段 + `resolve_back_mount()` 推导函数
- `"auto"` → `back_thickness >= board_thickness` 时 `"insert"`，否则 `"groove"`
- `"groove"` / `"insert"` / `"cover"` 可显式指定
- `CabinetLayout` 新增 `back_mount` 字段，`from_spec()` 按模式分流 side_depth / back_plane_y / internal_y_start
- `build_cabinet_panels()` 按三种模式生成不同尺寸/位置的背板
- `_edge_banding_for()` 控制背板封边；`_back_groove_operations()` 只在 groove 返回 4 条槽

| 模式 | side_depth | back_plane_y | 背板尺寸 | 槽 | 封边 |
|------|-----------|-------------|---------|-----|------|
| groove | d - door - hinge | back_offset(18) | int + 2×groove | 4条 | 无 |
| insert | d - door - hinge | back_offset(18) | int_w × int_h | 0 | 四边同色 |
| cover | d - door - hinge - back | 0 | width × height | 0 | 四边同色 |

### 背板拉条 (groove 模式)
- `FurnitureSpec` 新增 `back_rail_height: float = 70.0`
- 数量 = `internal_height // 500`，均分间隙
- 拉条类型 `back_rail`，Y 方向占 0~board_thickness，夹在左右侧板之间
````
