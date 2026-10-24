# 项目模块导航

维护入口。领域规则仍以各阶段 Skill 为准；交互协议与保存格式见 [运行时契约](runtime-contract.md)。

## 总体数据流

```text
HTTP / function calling / AI 对话
              ↓
       FurnitureOrchestrator
              ↓
布局 → 板件 → 制造 → 特征树 → CAD → 交付验证
              ↓
 Project / Revision / attempts / 冻结文件 / manifest
```

六阶段各自拥有领域计算；工作流拥有确认、重试、继承、版本与持久化。公共校验类型与内容哈希归 `furniture_contracts`，各阶段不为使用这些类型而依赖交付或工作流。旁路分析只写 `stage_analyses`。UI、AI 接入与 HTTP 不另建生成流程。

## 依赖与变更约束

下表是开发与审查约束，不是一个已覆盖所有导入和字段写入的自动门禁。执行时的确认、冻结、摘要与失效范围由 [运行时契约](runtime-contract.md) 维护；领域字段与准入规则由下文各阶段入口维护。

| 调用方 | 可以依赖什么 | 不得承担什么 |
| --- | --- | --- |
| 布局领域模型、序列化及几何校验 | 本阶段数据与计算、公共校验类型 | 不导入网页、AI 或工作流来生成 `to_dict()`、摘要或完成几何确认；展示适配入口不属于这一纯计算层 |
| 板件规划与属性编辑 | 布局交来的规范柜体包络、本阶段结构规则 | 不读取房间摆放来补构造；不决定制造连接；`panel_edit` 不操作 Project、租约、确认或文件 |
| 制造规划与修订 | 已确认板件的字典交接、本阶段材料与加工规则 | 不导入板件 Python 类型、不重跑板件、不修改冻结板件；制造类型恢复及 BOM 派生留在制造包 |
| 特征树转换 | 已确认制造记录的规范字段、本阶段树规则 | 不重新选择材料、连接、孔位、背板模式或槽参数，不回写制造结果 |
| 工作流、存储与 HTTP 门面 | 阶段公开入口及交接读取函数；阶段路由、逐柜组装和状态管理 | 不复制门序、铰链、料厚或加工公式；不在恢复类型时另列一份制造字段；不以展示内容作为领域事实 |
| Web 与可选助手 | 展示投影、规范编辑操作、宿主提供的应用入口 | 不直接改冻结文件或确认列表，不复制阶段默认值；助手只提案，写入仍经过原有阶段和工作流入口 |
| `furniture_contracts` | 标准库、阶段无关的数据类型与确定性计算 | 不导入任何阶段、工作流、网页或 AI 实现 |

按调用职责区分层次，不按目录名一刀切：`layout_figures`、`room_http`、`open_preview` 等适配入口可以连接展示或宿主，但不得因此让布局核心序列化反向依赖它们。跨阶段使用规范交接和所属阶段的入口，不通过私有计算函数补做另一阶段业务。

维护同一字段时，只在所有者处定义选择、默认、物化和校验口径。消费者可按自身交接需要复制规范值、验证类型与加工不变量，不得借适配器重新决定该值；缺少受支持的输入时，按所属阶段契约报错或追问。更改交接语义时同时列出生产者、消费者及工作流/测试，不能只改一端再靠默认值补齐另一端。

## 六阶段归属

所有下列 Python 包位于对应阶段的 `scripts/` 下。

| 阶段与入口 | 包 | 内部职责 |
| --- | --- | --- |
| [布局](../../layout-plan/SKILL.md) | `furniture_layout` | `scene` / `input_fields` 定义结构化输入；`scene_planning` / `placement` / `placement_check` 计算摆放；`validation` / `layout_figures` 校验几何与图；`project_layout` 保存全屋布局 |
| [板件](../../panel-plan/SKILL.md) | `furniture_panel_planning` | `cabinet_envelope` / `panel_spec` 准入；`structure_planning` / `interior_structure` / `panel_rules` / `construction_geometry` 算尺寸；`topology_solver` / `assembly_tree` / `joint_topology` 产出装配和接触；`validation*` 校验；`panel_pipeline` 是阶段入口 |
| [制造](../../manufacture-plan/SKILL.md) | `furniture_manufacturing` | `confirmed_panels` 接收冻结几何；`manufacturing_bom` 编制计划；`materials_catalog` / `edge_banding_catalog` / `catalog_loader` 准入目录；`connectors` / `connection_points` / `features` 算连接和加工；`manufacturing_models` 定义结果；`validation` / `hole_validator` 校验 |
| [特征树](../../feature-tree/SKILL.md) | `furniture_feature_tree` | `feature_tree_builder` 把制造结果转换为特征树；`feature_tree_emitter` 发射模型源码；`validation` 校验树结构 |
| [CAD](../TOOL.md) | `furniture_cad` | `cad_bridge` 调外部 CAD 进程；`validation` 校验桥接结果。逐柜生成 STEP 与 Viewer 包 |
| [交付](../../delivery-validated/SKILL.md) | `furniture_delivery_validation` | `validation` 核对阶段检查点、逐柜覆盖、文件、大小、摘要及谱系；不重算制造，也不解析 STEP 几何 |

布局计算在 `furniture_layout`：`room_page.room_page_payload` 给出页面要画的字典；`room_svg` 配展示用的图；`open_preview` 准备预览数据并打开页面；`scene_edit` / `project_edit` 管几何编辑；`scene_store` 管独立场景；`layout_events` 管变更通知；`room_http` 暴露独立房间接口；`room_shell` 只导出房间外壳。房间页、项目名单和三维画面在 [网页展示模块](../../../modules/web/README.md)。三维脚本的分工见 [布局运行时映射](../../layout-plan/references/runtime-map.md)。

板件结构投影在 `cabinet_panel_page.panel_structure_view`，顺纹规则在 `grain_rules`。板件页 HTML 在网页模块。`panel_review` 是确认审查。身份与交接在 `cabinet_identity` / `panel_models`。板件审计、优化与制造试验、统计、仿真是旁路分析。制造的 `drilled_holes_glb` / `export_six_side_drill` 负责文件格式转换，实际生成目录与 manifest 由工作流写入。具体规则见 [板件映射](../../panel-plan/references/runtime-map.md)、[制造映射](../../manufacture-plan/references/runtime-map.md)。

## 工作流包

目录：`cad-generated/scripts/furniture_workflow/`。

| 模块 | 唯一职责 |
| --- | --- |
| `workflow_orchestrator` | 应用入口，装配服务、创建项目、委托校验与持久化 |
| `workflow_stage_runner` | 执行一个阶段，登记 attempt、推进状态、应用内容相同的确认继承 |
| `workflow_stage_planning` | 无状态的逐柜制造及特征树转换，不接管确认和落盘 |
| `workflow_stage_validation` | 统一调度各阶段校验，核对逐柜身份、完整覆盖及顺序，汇总逐柜问题；通过传入的读取函数访问冻结板件与 BOM，不依赖 Orchestrator |
| `workflow_revision_ops` | 确认、冻结、重试、选 attempt、修订及下游失效 |
| `workflow_state` / `workflow_constants` | 阶段顺序、规范枚举、状态转换、结果类型与阶段归属表 |
| `workflow_project` | Project、Revision、StageAttempt 及保存格式 |
| `workflow_store` | 项目与冻结内容的持久化；不决定家具构造 |
| `workflow_reconstruction` | 从现有输出与冻结文件恢复结果视图；制造类型委托 `BOMReport.from_dict` 恢复，不重新规划 |
| `workflow_digest` / `workflow_inheritance` | 公共内容哈希的兼容入口与跨修订确认继承 |
| `input_adapter` | 明确的结构化阶段输入路由；不理解自然语言 |
| `workflow_cabinets` / `cabinet_pipeline` | 逐柜输出读取与只读结果容器 |
| `workflow_artifact_writer` / `workflow_artifacts` | 写出产物并记录文件摘要、柜体归属和修订谱系 |
| `workflow_analyses` | 调用旁路分析，记录证据与来源摘要 |
| `workflow_decisions` | 只追加的决策台账与假设撤回 |
| `workflow_lease` | 页面和助手的编辑租约 |
| `project_layout_edit` | 页面编辑门面：版本、租约、几何变更和工作副本协作 |
| `agent_tool_schema` / `agent_tools` | 工具定义、结构化协议准入和快照；业务动作交给 Orchestrator |

## 接入与启动

| 模块 | 职责 |
| --- | --- |
| `furniture_contracts/validation` / `digest` | 六阶段共用的校验结果与规范 JSON 内容哈希，仅依赖标准库 |
| `server.py` | FastAPI 进程、本机访问检查、项目 HTTP 接口、挂载阶段路由和网页模块 |
| `furniture_chat/conversation` / `http` | 可选页面助手的会话、模型上下文、工具循环和 HTTP 接入；开关与维护见 [AI 接入层维护](../../../modules/ai/references/ai-integration.md) |
| `furniture_chat/integration` / `page` / `templates` / `static` | 助手挂载、可选界面与前端资源；布局阶段只提供空插槽和两个展示回调 |
| `furniture_ai/contracts` / `service` | 模型接入契约与统一分发 |
| `furniture_ai/settings` / `discovery` | 本机配置与提供方发现 |
| `furniture_ai/openai_compatible` | OpenAI 兼容 HTTP 协议适配 |
| `furniture_ai/codex` / `agy` / `cli_protocol` / `isolation` | 本机 CLI 协议、进程调用与隔离配置 |
| `runtime_paths.py` | 为宿主入口加载六阶段包和独立 AI 模块路径 |
| `run_tests.py` / `tests/` | 唯一整库回归入口与共享测试样例 |
| `validate_workspace_layout.py` | 校验脚本归属目录 |
| `backlog_reconcile.py` / `backlog_landed.py` | 待办版本与已落地版本核对 |

上表的 `furniture_ai`、`furniture_chat` 及其专属测试和维护文档位于 [独立 AI 模块](../../../modules/ai/README.md)，不属于 `cad-generated`。CAD 目录中的服务器只负责条件接入。房间页、项目名单和板件页画面位于 [网页展示模块](../../../modules/web/README.md)，服务器负责挂载。

公共包位于 `cad-generated/scripts/furniture_contracts/`，沿用现有 `runtime_paths` 加载，无需增加启动步骤。它只定义阶段无关的数据契约和确定性计算，不导入阶段实现或工作流。新增调用使用 `furniture_contracts.validation` 的 `ValidationReport` / `ValidationIssue` / `ValidationSeverity` 及 `furniture_contracts.digest.stable_digest`；旧的交付类型导入和 `workflow_digest` 导入保持兼容。公共校验报告的 JSON 字段、错误等级与哈希算法不变；布局摘要只取领域数据，具体范围由运行时契约维护。

## 修改与验证

- 改尺寸和加工公式：改拥有该公式的阶段包。工作流只传递规范输入和结果。
- 改确认、重试和保存次数：改工作流生命周期；检查失败 attempt、冻结来源、下游失效和修订继承。
- 改模型提供方：改 `furniture_ai`；项目会话与工具循环归 `furniture_chat/conversation`，网页 HTTP 接入归 `furniture_chat/http`。
- 改页面样子：改 [网页展示模块](../../../modules/web/README.md)。改摆放求解或拖动换算仍改布局阶段。页面写项目仍走 `project_layout_edit`。
- 修改公共结构前先确认跨阶段范围，在 `furniture_contracts` 维护唯一实现，并验证各阶段保存格式、冻结哈希与兼容入口。

验证按 [测试选择指南](testing.md) 选择改动直接涉及的行为与受影响交接。板件、制造等影响产物的结构性改动先跑板件基线，之后只补本次相关测试，不能为让重构通过而更新基线：

```powershell
.\.venv\Scripts\python.exe domain/stages/cad-generated/scripts/run_tests.py -p test_panel_output_baseline.py
```

整库 Python 回归使用 `run_tests.py --all`，仅在明确需要整库覆盖时执行，不作为每次修改的固定收尾。

测试使用明确输入与固定断言，不依赖本机历史项目。临时文件和外部 CAD 的环境要求见 [开发环境](../../../../.agents/skills/furniture-agent/references/dev-environment.md)。
