# 交互工具面

回答“任意 function-calling 宿主如何驱动家具生成，而不必读取本仓库 Skill？”  
实现：`domain/skills/cad-generated/scripts/furniture_workflow/agent_tools.py`。

这是交互协议适配器，不是新的规划器。生命周期仍由 `FurnitureOrchestrator` 执行。没有一次性批处理入口，工具面不得自动确认。

## 注册

```python
from furniture_workflow.agent_tools import FurnitureToolSession, openai_tools
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_store import JsonProjectStore

orchestrator = FurnitureOrchestrator(
    workspace_root=workspace,
    project_store=JsonProjectStore(workspace / "store"),
)
session = FurnitureToolSession(orchestrator)
tools = openai_tools()          # OpenAI / 兼容的 function 列表
result = session.call(name, arguments)  # arguments 为对象或 JSON 字符串
```

把 `openai_tools()` 原样交给宿主的 tool/function calling API。Anthropic / Gemini 等把同一份 `function.name` + `parameters` JSON Schema 映射到各自字段即可。

## 工具

| 工具 | 作用 |
| --- | --- |
| `furniture_create_project` | 用规范意图字段开工，停在未确认的 `design_intent` |
| `furniture_get_project` | 读当前 Revision 快照 |
| `furniture_confirm_stage` | 确认当前检查点；意图/板件确认时冻结 JSON |
| `furniture_run_next` | 在已确认检查点上生成下一阶段的第一次 attempt |
| `furniture_retry_stage` | 对同一冻结上游再试 `panel_plan` / `manufacture_plan` / `feature_tree_planned` |
| `furniture_select_stage_attempt` | 选用某次通过的 attempt，再确认 |
| `furniture_revise_intent` | 新 Revision，从 `design_intent` 重来 |

不提供：`CadBridge`、特征树发射器、一次性自动确认、压扁检查点的入口。房间 `layout-plan` 仍是独立 API，不在这组工具里。

## 调用规则（代码强制）

- 未确认当前阶段时，`furniture_run_next` 返回 `STAGE_NOT_CONFIRMED`。
- 下一阶段已有 attempt 时，必须 `furniture_retry_stage`，否则 `USE_RETRY_STAGE`。
- 进入 `cad_generated` 必须 `generate_cad=true`；省略 `output_root` 时使用工作区约定路径 `generated`。
- 未知字段、历史别名（`furniture_type` / `type` / `overall_size`）返回 `UNKNOWN_ARGUMENT`。
- 失败 Revision 只能 `furniture_revise_intent`。
- 每次成功调用后展示 `project.current_output`，按 `waiting_for` / `allowed_actions` 停，不要连跳。

## 快照字段

`project` 只含协议状态，不是完整 `project.json`：

- `id` / `revision_id` / `current_stage` / `approved_stages` / `next_stage`
- `allowed_actions`、`waiting_for`、`cad_generation_required`
- `attempts`（编号、是否通过、错误；不含整份输出）
- `current_output`（当前阶段输出；`include_output=false` 可省略）
- `intent` 与冻结哈希

`allowed_actions` 是状态机合法转移，不是方案推荐。

## 意图与阶段输入

`furniture_create_project` / `furniture_revise_intent` 只接受：

- `furniture_category`
- `width_mm` / `depth_mm` / `height_mm` 或 `finished_envelope.{width_mm,depth_mm,height_mm}`
- 吊柜：`hanging_mode`（`free_hanging_height` / `flush_ceiling`）与自由挂高时的 `hanging_height_mm`

门、层板、抽屉、料厚、背板、踢脚、五金不得进入意图。它们属于 `stage_input`：

- 第一次板件/制造：`furniture_run_next` 的 `stage_input`
- 再试：`furniture_retry_stage` 的 `stage_input`

工具面不补构造默认值。料档字段可省略，由车间工艺卡展开。缺字段或非法组合由阶段运行时拒绝，并记为失败 attempt。

## 与 Skill 的关系

本仓库的阶段 Skill 仍供本宿主做领域提案（选门数、解释假设）。其他 LLM 宿主可以只注册上述工具；提案质量取决于模型，准入与状态由代码保证。
