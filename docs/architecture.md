# 家具 Agent 架构

当前目标不是同时支持所有家具，而是先让 `floor_cabinet` 和
`wall_cabinet` 成为可追溯、可恢复、可验证的完整纵向切片。

## 运行时主链

```text
DesignIntent
  -> Project / Revision
  -> FurnitureOrchestrator
  -> cabinet planner
  -> panelizer / BOM
  -> Feature Tree v1
  -> furniture CAD emitter
  -> cad_bridge
  -> external/text-to-cad
  -> STEP / Viewer topology
```

`packages/furniture_agent/orchestrator.py` 是应用层的单一编排入口。它只
维护工作流、验证和产物血缘，不重新实现家具尺寸、板件、BOM 或 CAD
算法。

## 边界

- `packages/furniture_schema`：DesignIntent、Project、Revision、
  WorkflowState、ValidationReport 和 ArtifactManifest 等稳定契约。
- `packages/furniture_agent`：单一 Orchestrator 和 JSON ProjectStore。
- `packages/furniture_planner`：柜体尺寸与板件位置推导。
- `packages/furniture_panelizer`：生产元数据、五金估算和 BOM。
- `packages/furniture_cad_emitter`：把板件转换为当前 box-based Feature
  Tree v1 和 CAD 源码。
- `packages/cad_bridge`：隔离外部 CAD CLI。
- `external/text-to-cad`：通用 CAD 生成、STEP 和 Viewer topology。
- `skills/furniture-cad`：仅保存 LLM 路由、阶段说明和领域使用规则；不
  拥有运行时 schema 或业务算法。

## Revision 规则

- DesignIntent 是每个 Revision 的上游真相。
- 用户修改意图时创建新 Revision，不覆盖旧 Revision。
- 新 Revision 会把上一 Revision 的已登记产物标记为 `stale`。
- Manifest 记录产物路径、内容哈希、大小和来源 Revision。
- ProjectStore 使用原子替换保存 `project.json`，进程重启后可以恢复。

## 当前诚实边界

- 只有地柜和吊柜进入运行时执行；其他品类停在意图或建模计划层。
- 当前 Feature Tree 仍只执行 `box` 特征和 `compound` 根节点。
- Layout Plan 和 Manufacturing Policy 仍是概念层，尚未伪装成独立的
  运行时阶段。
- BOM 是预估产物，未经制造策略确认时不称为制造就绪。
