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
| `furniture_create_project` | 用明确的房间布局开工，停在未确认的 `layout_plan`。成功后在本机打开该项目的预览页（环境变量 `FURNITURE_PREVIEW_BROWSER=0` 时不开） |
| `furniture_get_project` | 读当前 Revision 快照 |
| `furniture_confirm_stage` | 确认当前检查点；布局/板件确认时冻结 JSON。带 `room_id` 时只审那一间房（仅 `layout_plan`）：每间都审过，布局检查点才成立 |
| `furniture_run_next` | 在已确认检查点上生成下一阶段的第一次 attempt |
| `furniture_retry_stage` | 对同一冻结上游再试 `panel_plan` / `manufacture_plan` / `feature_tree_planned` |
| `furniture_select_stage_attempt` | 选用某次通过的 attempt，再确认 |
| `furniture_revise_layout` | 新 Revision，从 `layout_plan` 重来 |
| `furniture_record_decision` | 只把客户说的话记进**决策台账**（追加）：不动布局、不动阶段，`progressed=false`。客户后来说了一句、但还不用改布局时用它 |

不提供：`CadBridge`、特征树发射器、一次性自动确认、压扁检查点的入口。房间编辑器仍可走 `layout-plan` HTTP，真源是 Project 的 `layout_plan`。

## 调用规则（代码强制）

- 未确认当前阶段时，`furniture_run_next` 返回 `STAGE_NOT_CONFIRMED`。
- 下一阶段已有 attempt 时，必须 `furniture_retry_stage`，否则 `USE_RETRY_STAGE`。
- 进入 `cad_generated` 必须 `generate_cad=true`；省略 `output_root` 时使用工作区约定路径 `generated`。
- 未知字段、历史别名（`furniture_type` / `type` / `overall_size` / `mounting_height` / `mounting_height_mm` / `hanging_height` / `mount_mode`）返回 `UNKNOWN_ARGUMENT`。
- **决策台账**：`furniture_create_project` / `furniture_revise_layout` 可带 `decisions`（可选，只这两个工具收），
  `furniture_record_decision` 则**必须**带（它就是为"只记一句话"存在的）；
  每条是 `{utterance, interpretation, speaker?, status?, targets?, applies_to?}`：`utterance` 是**客户原话**
  （`speaker` 为 `customer`/`relay` 时必填——**助手自己的假设不要编引语**），`interpretation` 是我们把它落成了什么。
  缺省 `speaker=agent`、`status=assumption`——**只有客户真说了才写
  `speaker=customer`，只有客户认了才写 `status=confirmed`（且只有 `customer`/`relay` 能确认，助手不能自己点头）**。
  只追加：改主意是加一条并用 `targets` 指回被改的那几条，绝不改写旧条目。校验在动项目之前完成，
  不合法整批拒绝、不留半成品。口径见 [决策台账设计](decision-log-design.md)。
- 失败 Revision 只能 `furniture_revise_layout`。
- 每次成功调用后展示 `project.current_view`，按 `required_tool` / `allowed_tools` 停，不要连跳。`panel_plan` 展示审查清单的 `markdown` 或板件/接触表，不要把冻结 `cabinets[]` 树当确认界面。

## 调用结果

外层：`ok`、`tool`、`error`、`progressed`、`project`。`progressed` 表示这次调用是否把流程往前推进（新建、确认、生成下一步、改布局为真；只查状态或只换已有尝试为假）。

## 快照字段

`project` 只含协议状态，不是完整 `project.json`：

- `id` / `revision_id` / `current_stage` / `approved_stages` / `next_stage`
- `approved_rooms` / `pending_rooms` / `inherited_rooms`：布局的房间级确认。**每间都审过，布局检查点才成立**；`furniture_confirm_stage` 带 `room_id`（只对 `layout_plan`，一次审一间）或整份确认都行。没动过的房间，确认自动沿用父修订（`inherited_rooms` 回指真正点头的那一版）——所以 `pending_rooms` 就是"还差人看的哪几间"
- `lease`：编辑租约（谁此刻在写这个项目，含 `holder` / `label` / `expires_in`，**不含 token**）。写动作前工具面会**自动接管**租约，并把 `handover`（`taken_over` + 一句 `message`）放进结果里——模型要把那句话转告人："页面已切成只读，我做完还给你"
- `decisions` / `pending_decisions`：决策台账全量条目与**还没人确认**的那些 id。
  客户说的话、我们翻译成什么、谁确认过都在这里；`pending_decisions` 就是"还差哪几条要问客户"。
  **改布局会顺带作废被动摇的假设**：`furniture_revise_layout` 比对改动前后，把"针对真正变了的字段、还待确认、引用精确到 `对象.字段`"的条目自动记成 `withdrawn`——所以助手改完布局后，`pending_decisions` 里不该再留着已经被改掉的那几条。
  见 [决策台账设计](decision-log-design.md)
- `inherited`（哪些阶段沿用了更早那一版的内容，附 `sha256` 与 `from_revision`）与 `inherited_stages`。摆动摆放或改房间后板件内容没变时，系统会**承认**上一版的确认而不是让人再点一次头——快照必须把它显示出来，别让"少做了一步"变得看不见（见 [修订继承设计](revision-inheritance-design.md)）
- `allowed_tools`、`required_tool`、`cad_generation_required`
- `attempts`（编号、是否通过、错误；不含整份输出）
- `current_view`（当前阶段给人看的内容；`include_view=false` 可省略）。`panel_plan` 是确认审查清单（净空、板件一行一条、接触去重、`markdown`），不是冻结 `cabinets[]` 树；冻结板件仍在 Store。`manufacture_plan` 与 `feature_tree_planned` 是**逐柜**产物（`{"cabinets": [{"id", "bom"|"tree"}]}`，与板件 `cabinets[]` 一一对应），所以视图会随柜数变长——只关心一台时读 `cabinets[0]`。其他阶段一般就是该阶段结果本身。
- `layout` 与冻结哈希

`allowed_tools` 是当前合法的 `furniture_*` 工具名，不是方案推荐。`required_tool` 是下一步必须调用的那个工具。

## 布局与阶段输入

`furniture_create_project` / `furniture_revise_layout` 只接受：

- 必填的非空 `rooms[]`，每间房明确提供 `id`、`width_mm`、`depth_mm`、`height_mm`；家具包络和摆放放在所属房间的 `items[]`。
- 创建时另传 `name`，修改时另传 `project_id`。即使只有一件家具，也使用同一份房间契约；房间尺寸缺失时先询问客户。

柜门（`n_doors`）、层板、抽屉、料厚、背板、踢脚、五金不得进入布局，它们属于 `stage_input`。房间门窗写在 `rooms[].openings[]`（`kind=door|window`），这是 layout 输入，不是柜门。

板件/制造构造走：

- 第一次板件/制造：`furniture_run_next` 的 `stage_input`
- 再试：`furniture_retry_stage` 的 `stage_input`

板件与制造都接受 `{parameters: {...}}`，或扁平 parameters 对象（运行时会包一层）。制造的 `appearance` 与 `parameters` 平级，不要写进 `parameters`。封边选型 `edge_banding` 写在制造 `parameters` 里。

**逐柜参数**用同一个 `stage_input` 里的兄弟键 `cabinets`：

```json
{"stage_input": {"parameters": {…共享…}, "cabinets": {"cabinet_2": {…这台的覆盖…}}}}
```

板件的覆盖是**构造字段**（逐字段合并），制造的覆盖形如 `{"parameters": {…}, "appearance": {…}}`；身份与几何（柜类、宽深高）只来自布局，覆盖里写了会被拒；陌生柜名直接拒。**一组柜要不一样时（这台双门、那台单门）就靠它**——不要用一份共享参数假装也一样。形状见[板件提案契约](../../panel-plan/references/panel-proposal-contract.md)「逐柜参数」。

工具面不补构造默认值。料档字段可省略，由车间工艺卡展开。缺字段或非法组合由阶段运行时拒绝，并记为失败 attempt。

## 与 Skill 的关系

本仓库的阶段 Skill 仍供本宿主做领域提案（选门数、解释假设）。其他 LLM 宿主可以只注册上述工具；提案质量取决于模型，准入与状态由代码保证。
