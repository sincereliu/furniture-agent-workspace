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

布局预览在 `furniture_layout`：`room_page` / `room_svg` / `project_list` / `open_preview` 管展示；`scene_edit` / `project_edit` 管几何编辑；`scene_store` 管独立场景；`layout_events` 管变更通知；`room_http` 暴露独立房间接口；`room_shell` 只导出房间外壳。三维前端的细分见 [布局运行时映射](../../layout-plan/references/runtime-map.md)。

板件展示由 `panel_review` / `cabinet_panel_page` / `grain_rules` 负责；身份与交接在 `cabinet_identity` / `panel_models`。板件审计、优化与制造试验、统计、仿真是旁路分析。制造的 `drilled_holes_glb` / `export_six_side_drill` 负责文件格式转换，实际生成目录与 manifest 由工作流写入。具体规则见 [板件映射](../../panel-plan/references/runtime-map.md)、[制造映射](../../manufacture-plan/references/runtime-map.md)。

## 工作流包

目录：`cad-generated/scripts/furniture_workflow/`。

| 模块 | 唯一职责 |
| --- | --- |
| `workflow_orchestrator` | 应用入口，装配服务、创建项目、委托校验与持久化 |
| `workflow_stage_runner` | 执行一个阶段，登记 attempt、推进状态、应用内容相同的确认继承 |
| `workflow_stage_planning` | 无状态的逐柜制造及特征树转换；校验逐柜覆盖，不接管确认和落盘 |
| `workflow_stage_validation` | 统一调度各阶段校验、汇总逐柜问题；通过传入的读取函数访问冻结板件与 BOM，不依赖 Orchestrator |
| `workflow_revision_ops` | 确认、冻结、重试、选 attempt、修订及下游失效 |
| `workflow_state` / `workflow_constants` | 阶段顺序、规范枚举、状态转换、结果类型与阶段归属表 |
| `workflow_project` | Project、Revision、StageAttempt 及保存格式 |
| `workflow_store` | 项目与冻结内容的持久化；不决定家具构造 |
| `workflow_reconstruction` | 从现有输出与冻结文件恢复类型和结果视图；不重新规划 |
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
| `server.py` | FastAPI 进程、本机访问检查、项目 HTTP 接口、挂载阶段路由和静态资源 |
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

上表的 `furniture_ai`、`furniture_chat` 及其专属测试和维护文档位于 [独立 AI 模块](../../../modules/ai/README.md)，不属于 `cad-generated`。CAD 目录中的服务器只负责条件接入。

公共包位于 `cad-generated/scripts/furniture_contracts/`，沿用现有 `runtime_paths` 加载，无需增加启动步骤。它只定义阶段无关的数据契约和确定性计算，不导入阶段实现或工作流。新增调用使用 `furniture_contracts.validation` 的 `ValidationReport` / `ValidationIssue` / `ValidationSeverity` 及 `furniture_contracts.digest.stable_digest`；旧的交付类型导入和 `workflow_digest` 导入保持兼容。保存的 JSON 字段、错误等级与哈希算法不变。

## 修改与验证

- 改尺寸和加工公式：改拥有该公式的阶段包。工作流只传递规范输入和结果。
- 改确认、重试和保存次数：改工作流生命周期；检查失败 attempt、冻结来源、下游失效和修订继承。
- 改模型提供方：改 `furniture_ai`；项目会话与工具循环归 `furniture_chat/conversation`，网页 HTTP 接入归 `furniture_chat/http`。
- 改页面：在所属阶段维护渲染与几何编辑，通过 `project_layout_edit` 写项目。
- 修改公共结构前先确认跨阶段范围，在 `furniture_contracts` 维护唯一实现，并验证各阶段保存格式、冻结哈希与兼容入口。

结构性改动先跑板件基线，不能为让重构通过而更新基线：

```powershell
.\.venv\Scripts\python.exe domain/stages/cad-generated/scripts/run_tests.py -p test_panel_output_baseline.py
.\.venv\Scripts\python.exe domain/stages/cad-generated/scripts/run_tests.py
```

测试使用明确输入与固定断言，不依赖本机历史项目。临时文件和外部 CAD 的环境要求见 [开发环境](../../../../.agents/skills/furniture-agent/references/dev-environment.md)。
