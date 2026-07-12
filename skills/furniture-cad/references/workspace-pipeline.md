# 工作区家具流水线

在声称具备可执行支持、规范化输入、运行生成或报告运行时产物前，读取本文档。工作区流水线回答：“当前工作区实际执行什么？”

本文件负责运行时契约、命令、生成产物路径和当前执行限制。它不负责用户意图、布局规划、板件语义、制造策略、特征树设计规则或验证关卡。

## 当前能力

唯一应用层入口是 `skills/furniture-cad/scripts/furniture/workflow_orchestrator.py`。它接受已确认的 `DesignIntent`，也通过 `execute_spec()` 接受 CLI/API 使用的扁平规格 JSON。它当前委托的领域规划器支持：

- `floor_cabinet`：固定柜体模板，包含背板、踢脚板、层板和门板。
- `wall_cabinet`：固定柜体模板，包含背板、层板和门板，不含踢脚板。

这些是边界明确的模板，不是任意家具配置器。承诺布局变体前，必须检查 `planner.py` 及相应模板。其他家具类别在实现前只支持意图或建模方案。

## 七阶段状态与确认

`FurnitureOrchestrator` 在每个 Revision 中记录以下七个真实运行阶段：

1. `design_intent`
2. `layout_planned`
3. `panels_planned`
4. `manufacturing_planned`
5. `feature_tree_planned`
6. `cad_generated`
7. `delivery_validated`

每个阶段的可审查结果保存在 `revision.stage_outputs[stage.value]`，用户确认记录保存在 `revision.approved_stages`，转换历史保存在 `revision.workflow.history`。`JsonProjectStore` 序列化 Project 时会同时保存这些字段。

交互式调用顺序为：

```python
orchestrator.confirm_stage(project)  # 确认当前阶段
result = orchestrator.run_next(project)  # 只生成下一阶段并暂停
```

从已确认的 `feature_tree_planned` 进入第 6 阶段时，必须显式提供 CAD 输出位置：

```python
result = orchestrator.run_next(
    project,
    output_root="generated",
    generate_cad=True,
)
```

未确认当前阶段时，`run_next()` 和默认的 `run_until()` 不会越过当前检查点。Agent 必须返回当前阶段输出并等待用户确认，不得调用批处理入口代替阶段确认。

上游修改规则：

- 设计意图变化：`revise(project, new_intent)`，新 Revision 从 `design_intent` 开始。
- 第 2～5 阶段变化：`revise_stage_output(project, stage, edited_output)`。
- 新 Revision 只复制修改阶段之前已经确认的输出和确认记录。
- 被修改阶段不自动确认；该阶段及全部下游重新确认或生成。
- 旧 Revision 的产物清单标记为 stale，不手工修改旧 STEP、GLB、BOM 或派生源码。

`execute_spec()` 是 CLI/API 明确批处理使用的便利入口，会自动确认通过验证的中间阶段；交互式 Agent 不使用它。

## 可执行 JSON

所有数值单位均为毫米。每个受支持类型都需要：

```json
{
  "type": "floor_cabinet",
  "width": 800,
  "depth": 600,
  "height": 2000,
  "board_thickness": 18,
  "back_thickness": 9,
  "door_thickness": 18,
  "toe_kick_height": 50,
  "back_offset": 18,
  "door_margin": 1.5,
  "door_hinge_gap": 2,
  "shelf_count": 4,
  "n_doors": 2
}
```

`wall_cabinet` 的默认尺寸较小：`width` 800、`height` 900、`depth` 350、`toe_kick_height` 0、`shelf_count` 1。

默认尺寸和参数位于 `skills/furniture-cad/scripts/furniture/design_spec.py`：`CABINET_PRESETS` 保存各类型默认值，数据类字段保存全局常量。除非用户要求覆盖或设计必须覆盖，否则不要要求用户逐项填写。

可执行契约是扁平 JSON。

只有总体尺寸为数值且请求的变体与实时模板匹配时，才进入执行。否则停在合适的 DDD 规划层，并说明不支持的边界。

## 生成

在工作区根目录运行：

```powershell
.\.venv\Scripts\python.exe skills\furniture-cad\scripts\generate_furniture.py <spec.json> --force
```

当期望的产物名称与规格文件名不同时，使用 `--name <artifact-name>`。名称只能包含字母、数字、连字符和下划线。

命令写入 `generated/<artifact-name>/`：

- `<artifact-name>.design-intent.json`
- `<artifact-name>.layout-plan.json`
- `<artifact-name>.panel-plan.json`
- `<artifact-name>.manufacturing-plan.json`
- `<artifact-name>.feature-tree.json`
- `<artifact-name>.bom.md`
- `<artifact-name>.step`
- CAD 桥接器生成的相邻隐藏 Viewer 拓扑 GLB

派生的 build123d Python 源码是临时文件，只写入 `temp/cad-source/<artifact-name>/`，绝不能持久化到 `generated/`。

CLI、API 与 Agent 均委托 `skills/furniture-cad/scripts/furniture/workflow_orchestrator.py`。Orchestrator 负责 Project/Revision、七阶段输出、逐阶段确认、验证、产物清单和可选 CAD 桥接。命名的一次性 CLI 运行写入 `generated/<artifact-name>/`；交互式 Project/Revision 工作流写入 `<output-root>/<project-id>/revision-<n>/`。派生 CAD 源码统一写入 `temp/cad-source/`。`skills/furniture-cad/scripts/furniture/workflow_store.py` 可将 Project/Revision、`stage_outputs` 和 `approved_stages` 持久化为 `project.json`。

运行时流水线为：

`CLI / API / Agent -> FurnitureOrchestrator -> 设计意图 -> 布局 -> 板件 -> 制造/BOM -> 特征树 -> CAD Bridge -> STEP + Viewer 拓扑 -> 交付验证`

概念板件方案由现有规划器流程表达。它不增加新的运行时命令、规划器接口、可执行 JSON 结构、特征树操作集或 STEP 实体模型。

不要把家具 JSON 直接发送给 text-to-cad。普通家具生成不得用一次性 CAD 源码绕过规划器，也不得修改外部子模块。

## 运行时板件与 BOM 路径

`skills/furniture-cad/scripts/furniture/layout_pipeline.py` 为两种柜体类型公开三个独立阶段函数：

- `plan_layout()`：生成布局与板件定位记录。
- `plan_panels()`：把布局转换成制造板件记录。
- `plan_manufacturing()`：应用材料、五金和 BOM 策略。

`plan_cabinet()` 保留为组合这些领域函数的无状态兼容门面；交互式工作流由 Orchestrator 分阶段调用三个函数，不通过 `plan_cabinet()` 把检查点合并掉。

主生成 CLI 会持久化 BOM Markdown 报告，但不会持久化裁切清单产物。除非某个命令确实创建了裁切清单，否则不得报告存在裁切清单。
