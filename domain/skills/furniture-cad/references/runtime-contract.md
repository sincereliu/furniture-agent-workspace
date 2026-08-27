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
  "drawer_back_clearance": 0, "shelf_count": 4, "n_doors": 2, "door_hinge_side": null
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
