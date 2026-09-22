---
name: delivery-validated
description: 用于 delivery_validated 阶段。当用户说"检查一下产物""验证完整性""校验文件""确认交付"时触发。验证当前 Revision 的前置检查点、产物谱系、文件存在性、大小和 SHA-256，并区分外部几何审查。
---

# 家具交付验证

阶段：`delivery_validated`

**这一阶段只回答一件事：当前这一版修订的检查点、谱系和文件是否齐。** 交出去的是一份验证结果。它证明文件在、哈希对、上游检查点属于这一版。它不重新计算前面各阶段的业务，也不解析 STEP 几何。

## 人要交什么

`cad_generated` 已确认，而且产物来自当前 Revision。房间场景不属于交付前置检查点。

核对时读 [交付验证清单](references/delivery-checklist.md) 和 `../cad-generated/references/runtime-contract.md`。

## 一步一步做什么

1. **确认 CAD 已经确认，且产物属于当前 Revision。**
2. **调用 `FurnitureOrchestrator.run_next()`。** 它走到 `scripts/furniture_delivery_validation/validation.py`。前五个串联阶段都要在当前 Revision 里有输出、已确认，并且最近一次验证通过。然后再查必需产物是否存在、非空、大小、SHA-256、是否 stale，以及 Revision 谱系。
3. **核对制造接受程度。** `manufacture_plan.readiness` 必须与 manufacture-plan 的 BOM 清单元数据一致。仍为 `preliminary` 时报告警告。交付完整不等于可以直接投产。
4. **若这一版有 `stage_analyses`，逐条核对。** 每条记录要带上 Revision、来源阶段和 `source_sha256`。`unavailable` / `descriptive_only` 只作警告。旁路分析不是必需交付物。
5. **展示后停。** 把 `stage_outputs.delivery_validated` 给客户看。没有实际跑过的 STEP 几何测量、快照或 Viewer 人工审查，写成未验证。

## 本阶段不做什么

- 不重算前面阶段的业务语义，不解析 STEP 几何。内置验证只证明检查点谱系和文件完整性。
- STEP 导入、几何测量或快照，只有实际调用了 `external/text-to-cad/skills/cad/SKILL.md` 之后才单独报告。
- 可视化审查和链接，只有实际调用了 `external/text-to-cad/skills/cad-viewer/SKILL.md` 之后才单独报告。
- 只报告实测验证和实存产物，不手改派生文件。

## 参考导航

- 查什么、怎样算过： [交付验证清单](references/delivery-checklist.md)
- 运行时在 `scripts/furniture_delivery_validation/`。`ValidationReport` 与交付规则归本包。Orchestrator 只触发、保存和推进状态。
