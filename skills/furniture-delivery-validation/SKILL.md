---
name: furniture-delivery-validation
description: 用于 delivery_validated 阶段；验证当前 Revision 的前置检查点、产物谱系、文件存在性、大小和 SHA-256，并区分外部几何审查。
---

# 家具交付验证

阶段：`delivery_validated`

## 工作流

1. 要求 `cad_generated` 已确认且产物来自当前 Revision。
2. 读取 [交付验证清单](references/delivery-checklist.md) 和 `../furniture-cad/references/runtime-contract.md`。
3. 用 `FurnitureOrchestrator.run_next()` 调用 `scripts/furniture_delivery_validation/validation.py`，要求前六阶段在当前 Revision 中均有输出、已确认且最近验证通过，再检查必需产物、存在性、非空、大小、SHA-256、stale 状态和 Revision 谱系。
4. `manufacturing_planned.readiness` 必须与 manufacturing-plan/BOM 清单元数据一致；仍为 `preliminary` 时报告警告，交付完整不等于可直接投产。
5. 展示 `stage_outputs.delivery_validated` 后暂停；不得把未执行的 STEP 几何测量、快照或 Viewer 人工审查写成已通过。

## 边界

- 运行时在 `scripts/furniture_delivery_validation/`；`ValidationReport` 与交付规则归本包，Orchestrator 只触发、保存和推进状态。
- 内置 `delivery_validated` 只证明检查点谱系和文件完整性，不重新计算前五阶段业务语义，也不解析 STEP 几何。
- STEP 导入、几何测量或快照仅在实际调用 `external/text-to-cad/skills/cad/SKILL.md` 后单独报告。
- 可视化审查和链接仅在实际调用 `external/text-to-cad/skills/cad-viewer/SKILL.md` 后单独报告。
- 只报告实测验证和实存产物，不手改派生文件。
