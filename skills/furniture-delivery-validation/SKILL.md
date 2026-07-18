---
name: furniture-delivery-validation
description: 用于 delivery_validated 阶段；验证阶段谱系、STEP、Viewer 拓扑、跨层一致性、文件存在性、几何检查和交付报告。
---

# 家具交付验证

阶段：`delivery_validated`

## 工作流

1. 要求 `cad_generated` 已确认且产物来自当前 Revision。
2. 读取 [交付验证清单](references/delivery-checklist.md) 和 `../furniture-cad/references/runtime-contract.md`。
3. 用 `FurnitureOrchestrator.run_next()` 调用 `scripts/furniture_delivery_validation/validation.py`，检查必需产物、存在性、大小、SHA-256、stale 状态和 Revision 谱系；展示后暂停。

## 边界

- 运行时在 `scripts/furniture_delivery_validation/`；`ValidationReport` 与交付规则归本包，Orchestrator 只触发、保存和推进状态。
- STEP 检查、几何测量或快照委托 `external/text-to-cad/skills/cad/SKILL.md`。
- 可视化审查和链接按需委托 `external/text-to-cad/skills/cad-viewer/SKILL.md`。
- 只报告实测验证和实存产物，不手改派生文件。
