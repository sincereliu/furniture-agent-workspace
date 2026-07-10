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

`skills/furniture-cad/scripts/furniture/workflow_orchestrator.py` 是应用层的单一编排入口。它只
维护工作流、验证和产物血缘，不重新实现家具尺寸、板件、BOM 或 CAD
算法。

## 边界

家具领域运行时代码统一放在 `skills/furniture-cad/scripts/furniture`，文件名按技能阶段组织：

- `design_*`：Design Intent 和可执行尺寸规格；
- `layout_*`：柜体布局、面约束和共享布局管线；
- `panel_*`：板件语义、定位和生产记录；
- `manufacturing_*`：材料、封边、钻孔、五金和 BOM；
- `feature_tree_*`：当前 box-based Feature Tree v1 和 CAD 源码；
- `cad_bridge.py`：隔离外部 CAD CLI；
- `workflow_*`：Project、Revision、验证、产物血缘和编排。

- `skills/furniture-cad/scripts/furniture`：拥有家具领域规划和工作流实现。
- `external/text-to-cad`：通用 CAD 生成、STEP 和 Viewer topology。
- `skills/furniture-cad`：同时保存 LLM 路由、阶段说明，以及 skill 私有的
  `scripts/` 运行代码；仓库根目录不再维护重复的 Python 包和入口。

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
