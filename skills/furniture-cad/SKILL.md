---
name: furniture-cad
description: 用于 cad_generated 阶段和 CLI/API 批处理；根据已确认特征树生成 CAD、STEP 和 Viewer 拓扑，不做特征树规划或最终验证。
---

# 家具 CAD 执行

阶段：`cad_generated`

各阶段拥有运行时；`scripts/furniture_workflow/workflow_orchestrator.py` 统一编排，CAD 实现在 `scripts/furniture_cad/`。不得另建规划器接口、JSON 契约或流水线。

## 代码位置

- 阶段运行时放所属 `skills/furniture-*/scripts/`；跨阶段 Orchestrator、CLI/API、布局守卫和集成测试放 `skills/furniture-cad/scripts/`。
- 一次性检查/迁移/调试/CAD 实验放已忽略的 `temp/`，任务结束删除。禁止根级 `scripts/`、`packages/`、`tests/`、`scratch/`、`tmp/`，也不得在非家具 Skill 新建脚本面。
- 生成源码只进 `temp/cad-source/`，不得进 `generated/`。布局或生成变更后运行：

```powershell
.\.venv\Scripts\python.exe skills\furniture-cad\scripts\validate_workspace_layout.py
```

有违规即失败，交付前清零。

## 工作流

1. 声称支持、规范化 JSON、生成或报告产物前，读取 [工作区流水线](references/workspace-pipeline.md) 并核对实时入口。
2. 要求 `feature_tree_planned` 已确认；用 `FurnitureOrchestrator.run_next()` 生成。
3. CLI/API/Agent 均经 Orchestrator；发射器和 CAD Bridge 仅由其调用，结果规则归 `scripts/furniture_cad/validation.py`。
4. 发射器将 Feature Tree `cut_box` 对目标板件做 build123d 布尔减料；不得用重叠板件冒充槽。
5. API 接受 `back_mount/back_rail_height`，返回有效模式、制造备注、加工操作和 drilled-holes；协议层不重做背板推导。
6. `workflow_artifact_writer.py` 写跨阶段快照；Orchestrator 不实现 JSON、BOM、孔位或 CAD 源码序列化。
7. 展示 `stage_outputs.cad_generated` 后暂停，不做交付验证。仅明确一次性 CLI/API 批处理可用 `execute_spec()` 或 `scripts/generate_furniture.py`。

## 返回内容

- 规范化输入、已确认特征树来源、CAD 命令结果和 `stage_outputs.cad_generated`。
- 实际存在的 STEP、Viewer 拓扑、drilled-holes 及路径。
- 下一阶段：`skills/furniture-delivery-validation/SKILL.md`；本阶段不宣称最终通过。
