---
name: furniture-delivery-validation
description: 验证家具阶段谱系、STEP、Viewer 拓扑和实际交付产物。适用于 delivery_validated 阶段的跨层一致性、文件存在性、几何检查和诚实交付报告。
---

# 家具交付验证

阶段：`delivery_validated`

## 工作流

1. 要求 `cad_generated` 已确认且产物来自当前 Revision。
2. 读取 [验证关卡](references/validation.md)。
3. 检查 `../furniture-cad/references/workspace-pipeline.md` 指向的实时入口和产物契约。
4. 通过 `FurnitureOrchestrator.run_next()` 调用 `scripts/furniture_delivery_validation/validation.py`，检查必需产物、文件存在性、大小、SHA-256、stale 状态和 Revision 谱系，展示结果后暂停。

## 边界

- 本阶段运行时代码位于 `scripts/furniture_delivery_validation/`。
- 通用 `ValidationReport` 和最终交付规则在本包中实现；Orchestrator 只负责触发验证、保存报告和推进状态。
- STEP 检查、几何测量或快照委托 `external/text-to-cad/skills/cad/SKILL.md`。
- 可视化审查和链接按需委托 `external/text-to-cad/skills/cad-viewer/SKILL.md`。
- 只报告实际运行过的验证和实际存在的产物，不手工修改派生文件。
