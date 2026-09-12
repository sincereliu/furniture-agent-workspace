# furniture-agent-workspace

板式家具参数化规划、拆单、BOM 与 CAD 输出的本地开发工作区。

## 架构

```text
CLI / FastAPI / Agent tools (furniture_*)
            |
            v
FurnitureOrchestrator
            |
            +-- 设计意图 -> 板件 -> 制造/BOM -> 特征树
            +-- 按需科学分析 -> stage_analyses（不改阶段检查点）
            +-- CadBridge -> external/text-to-cad
            +-- 验证、Project/Revision、产物清单

独立 layout-plan -> 房间摆放 / 碰撞检查 / SVG / Viewer
```

`domain/skills/cad-generated/scripts/furniture_workflow/workflow_orchestrator.py` 是家具生成的唯一应用层入口。规划阶段实现由各自 Skill 的 `scripts/` 拥有；`cad_generated` 是 Orchestrator tool（`run_next(..., generate_cad=True)`），不是 Agent Skill。交互式 function-calling 经 `furniture_workflow/agent_tools.py` 的 `FurnitureToolSession` 调用 Orchestrator，不直接拼装规划器、发射器或 CAD Bridge。CLI/API 批处理仍走 `execute_spec()`。`layout-plan` 是明确请求时才调用的独立房间摆放能力，不是家具生成前置步骤。

## 六阶段交互

交互式 Agent 每次只运行一个阶段：`furniture_confirm_stage` 确认当前阶段，`furniture_run_next` 进入下一阶段。意图确认后冻成 JSON；对同一份冻结意图可用 `furniture_retry_stage` 再试板件等规划阶段，用 `furniture_select_stage_attempt` 选用某次尝试。阶段完成后，用户检查快照中的 `current_output`；未确认时不能越过当前检查点。工具契约见 `domain/skills/cad-generated/references/agent-tool-contract.md`。

```text
1. design_intent
2. panel_plan
3. manufacture_plan
4. feature_tree_planned
5. cad_generated
6. delivery_validated
```

阶段确认顺序遵循客户决策：`design_intent` 只确认家具类别与宽深高成品外包络；`panel_plan` 首次确认门数、层板数、抽屉数、板厚、背板、踢脚、精确净空和实体板件；`manufacture_plan` 再确定材料、封边、连接、五金与加工。

只有明确调用独立 `layout-plan` 或 `/api/plan-layout` 时才接收房间和家具位置并生成摆放图。未提供时使用 `4200×3600×2800 mm` 的“默认卧室（系统假设）”，并将柜体沿北墙居中摆放；只提供一项时补齐另一项。独立结果包含 `layout_context` 来源标记、房间坐标、家具四角占地、六向净距、内联 SVG 透视图和自包含 HTML 互动 Viewer。普通家具生成不会运行这一步，也不会生成 `layout-plan.json`：

```json
{
  "type": "floor_cabinet",
  "width": 1800,
  "depth": 600,
  "height": 2400,
  "room": {
    "id": "bedroom",
    "name": "主卧",
    "width_mm": 4200,
    "depth_mm": 3600,
    "height_mm": 2800,
    "openings": [],
    "obstacles": []
  },
  "placement": {
    "mode": "wall",
    "host_wall": "north",
    "offset_mm": 500,
    "origin_z_mm": 0
  }
}
```

设计意图变化使用 `revise()` 从第 1 阶段建立新 Revision。同一冻结意图上再试规划使用 `retry_stage()`；已确认板件冻成独立 JSON，对同一份板件再试制造不必重跑 `panel-plan`。直接改已有 `panel_plan`、`manufacture_plan` 或 `feature_tree_planned` 结果时使用 `revise_stage_output()`：新 Revision 只保留修改点之前已确认的结果，修改点及全部下游重新确认或生成。独立房间布局直接重新运行，不建立或使主流程 Revision 失效。完整批处理请求中的后续参数保存在 `stage_inputs`，不会污染 `DesignIntent`；`stage_inputs`、`stage_outputs`、`stage_attempts`、`approved_stages` 和工作流历史会随 Project JSON 一起保存，冻结意图、冻结板件与各次 attempt 另有独立 JSON 文件。

`generate_furniture.py` 和 `execute_spec()` 是明确的一次性批处理入口，可以自动确认已通过验证的中间阶段；它们不用于交互式逐步设计。

## 按需科学分析

`external/scientific-agent-skills` 保持上游子模块，不复制进家具 Skill。路由器只在任务需要时读取相应方法说明，家具数据适配器仍由板件或制造阶段拥有：

| 分析名 | 来源阶段 | 方法 Skill | 家具适配器 |
| --- | --- | --- | --- |
| `panel_unit_audit` | `panel_plan` | `uncertainty-and-units` | `quantitative_audit.py` |
| `panel_optimization` | `panel_plan` | `pymoo` | `design_optimization.py` |
| `prototype_experiment` | `manufacture_plan` | `experimental-design` | `prototype_experiment.py` |
| `test_statistics` | `manufacture_plan` | `statistical-analysis` | `test_statistics.py` |
| `production_simulation` | `manufacture_plan` | `simpy` | `production_simulation.py` |

可选数值依赖统一安装：

```powershell
uv sync --extra furniture-analysis
```

调用统一入口：

```python
record = orchestrator.run_stage_analysis(
    project,
    "panel_optimization",
    {
        "variables": {"board_thickness": [18.0, 22.0]},
        "objectives": ["material_volume_m3", "negative_internal_volume_m3"],
    },
)

# 用户审查 Pareto 候选并明确选择后，才生成新 Revision：
revision = orchestrator.apply_panel_optimization_candidate(project, 0)
```

每条结果保存在当前 Revision 的 `stage_analyses`，包含来源阶段、Revision ID 和来源输出 SHA-256。分析不会改写 `stage_outputs`；来源家具方案变化后，交付验证会把旧分析标记为谱系错误。缺少可选依赖时，适配器会返回 `unavailable`，或使用报告中明确注明限制的有界回退。

## 入口

```powershell
# CLI：明确的一次性批处理，规划并生成 CAD
.\.venv\Scripts\python.exe domain\skills\cad-generated\scripts\generate_furniture.py <spec.json> --force

# API：只负责 HTTP 协议，内部同样调用 FurnitureOrchestrator
.\.venv\Scripts\python.exe domain\skills\cad-generated\scripts\server.py
```

`POST /api/plan-layout` 返回独立房间布局 JSON；`POST /api/plan-layout/preview` 直接返回 `image/svg+xml` 静态预览；`POST /api/plan-layout/viewer` 返回可直接打开的 `text/html` 互动 Viewer。

可复用阶段代码放在对应的 `domain/skills/*/scripts/`；统一 Orchestrator、CLI/API 和集成测试放在 `domain/skills/cad-generated/scripts/`；一次性脚本和派生 CAD 源码放在 `temp/`；最终产物放在 `generated/`。

