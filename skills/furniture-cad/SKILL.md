---
name: furniture-cad
description: 根据已确认特征树生成家具 CAD，并核对当前运行时能力。适用于 cad_generated 阶段、CLI/API 批处理、STEP 生成和 Viewer 拓扑生成；不负责特征树规划或最终交付验证。
---

# 家具 CAD 执行

阶段：`cad_generated`

每个阶段 Skill 拥有自己的 `scripts/` 运行时代码；七个阶段仍统一由 `FurnitureOrchestrator` 执行。

概念工作流：

`设计意图 -> 布局规划 -> 板件规划 -> 制造策略 -> 特征树 -> CAD 生成 -> 验证交付`

当前运行时由 `scripts/furniture_workflow/workflow_orchestrator.py` 统一编排，并调用各阶段 Skill 的运行时包；CAD 阶段实现位于 `scripts/furniture_cad/`。本技能不定义新的规划器接口、可执行 JSON 结构或平行运行时步骤。

## 强制代码放置规则

工作区只允许两类本地脚本位置：

1. 可复用的阶段运行时模块放在对应的 `skills/furniture-*/scripts/`；跨阶段 Orchestrator、CLI/API、布局校验器和集成测试放在 `skills/furniture-cad/scripts/`。
2. 一次性的检查、迁移、调试和 CAD 实验脚本，放在已忽略的 `temp/` 目录下，并在任务结束时删除。

禁止创建根级 `scripts/`、`packages/`、`tests/`、`scratch/` 或 `tmp/` 代码树。禁止在非家具阶段 Skill 中创建新的脚本面。禁止在 `generated/` 下放置 `.py`、`.pyc`、PowerShell、shell、JavaScript 或其他生成的源文件；生成的 CAD 源码应放在 `temp/cad-source/`。完成任何代码布局或 CAD 生成变更前，运行：

```powershell
.\.venv\Scripts\python.exe skills\furniture-cad\scripts\validate_workspace_layout.py
```

任何报告的违规项都视为验证失败；报告完成前必须移动或删除违规文件。

## 按任务路由

1. 在声称支持、规范化可执行 JSON、生成或报告产物前，读取 [工作区流水线](references/workspace-pipeline.md) 并检查其中指向的实时入口。
2. 要求 `feature_tree_planned` 已确认；通过 `FurnitureOrchestrator.run_next()` 生成 CAD。
3. CLI、API 和 Agent 必须统一经过 `FurnitureOrchestrator`；发射器和 CAD Bridge 只由 Orchestrator 调用。
4. Feature Tree `cut_box` 由发射器对指定板件执行 build123d 布尔减料；不得用板件重叠冒充开槽。
5. API 必须接受 `back_mount/back_rail_height`，并返回解析后的模式、制造备注、加工操作和 drilled-holes；不得在协议层重新实现背板推导。
6. 展示 `stage_outputs.cad_generated` 后停止，不得同时完成交付验证。
7. 只有明确的一次性 CLI/API 批处理才使用 `execute_spec()` 或 `scripts/generate_furniture.py`。

## 领域参考文档

- [工作区流水线](references/workspace-pipeline.md)：当前运行时实际执行什么。

## 返回内容

- 规范化输入和已确认的特征树来源。
- CAD 命令结果以及 `stage_outputs.cad_generated`。
- 实际存在的 STEP、Viewer 拓扑、drilled-holes 和产物路径。
- 下一阶段使用 `skills/furniture-delivery-validation/SKILL.md`，本阶段不报告最终交付通过。
