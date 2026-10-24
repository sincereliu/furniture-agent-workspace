# 仓库约定

## 指令文件分工

- 本文件维护全仓库的读取范围、归属、修改协作和验收要求。
- `.agents/skills/furniture-agent/SKILL.md` 是发现各阶段的薄路由；阶段业务规则维护在所属 `domain/stages/<stage>/SKILL.md`，CAD 执行入口为 `cad-generated/TOOL.md`。
- 各入口的 `references/` 按任务加载，维护本阶段详细契约与规则；其他阶段引用所有者的文件，不复制一套规则。未完成设计留在 `backlog/`。
- `agents/openai.yaml` 只维护 Skill 的显示信息和调用提示，不是独立子智能体，也不另定义阶段顺序、默认值或确认规则。行为变更写回所属 Skill/契约，调用提示保持简短。
- 共享实现和测试虽存放在 `cad-generated/scripts/`，也按下表区分职责；不能因目录位置把它们都当作 CAD 业务。

## 按需读取

- 做家具或查找阶段入口，先读 [家具智能体](.agents/skills/furniture-agent/SKILL.md)；改代码再按对应阶段 Skill/TOOL 的导航读具体文件。
- 修改 Web 三维画面、家具预览或描边代码前，先读 [三维预览视觉规范](domain/modules/web/references/visual-style.md)，沿用已确认的「卡通手办风」及其参考图。修复或重构须保留视觉风格；用户明确要求改变风格时再调整规范。
- 默认只在 `domain/`、`.agents/` 搜索和列目录。`store/`、`generated/`、`temp/`、`changelog/`、`external/`、`vendor/` 及根 `README.md`、`domain/stages/cad-generated/references/runtime-contract.md`，仅在当前任务、阶段技能或工具结果点名后读取，且只读点名范围。
- `external/` 是上游子模块：仅在用户点名 CAD/科学分析 Skill，或阶段触发表指向它时读该 Skill，不浏览其余内容；升级只移动子模块指针。
- `vendor/` 是版本钉死的构建文件（当前 `vendor/three/0.186.0/`，预览挂同名 URL）：仅核对点名文件，不读其余库源码；升级替换构建文件。

## 职责与修改范围

阶段路径均位于 `domain/stages/`：

| 改什么 | 所属路径或入口 |
| --- | --- |
| 布局、房间门窗 `openings[]` | `layout-plan/` |
| 门、层板、抽屉、背板、踢脚、料厚、门缝、铰链侧及结构净空 | `panel-plan/` |
| 材质选型、封边、连接、五金、BOM、孔 | `manufacture-plan/` |
| 特征树 | `feature-tree/` |
| 确认、重试、冻结、状态机、交互工具 | `cad-generated/scripts/furniture_workflow/`、`cad-generated/references/agent-tool-contract.md` |
| CAD/STEP | `cad-generated/TOOL.md`、`cad-generated/scripts/furniture_cad/` |
| 交付 | `delivery-validated/` |
| 阶段无关校验类型、规范内容哈希 | `cad-generated/scripts/furniture_contracts/` |
| 宿主接入、路径加载、整库回归与跨阶段测试 | `cad-generated/scripts/` 中的入口脚本、`tests/`；详见 [模块导航](domain/stages/cad-generated/references/module-map.md) |

独立应用模块：AI 模型接入、网页助手、设置与登录归 `domain/modules/ai/`；页面展示归 `domain/modules/web/`，各自拥有代码、界面、测试和维护文档。摆放求解、拖动换算、板件结构投影仍归对应阶段。

维护阶段 Skill 只改本阶段目录（含 Skill/TOOL、references、scripts、agents）。必须跨阶段时，先列出阶段、文件和原因，等开发者看过再改。用户已点名文件或明确要求跨阶段调整指令、说明时，可按该范围直接改文档；不包含其他阶段的 `scripts/`。

单阶段修改先区分「本阶段规则」和「阶段间契约」：只改本阶段计算或说明、交接字段与语义不变时，下游继续消费原契约，不顺手改下游。需要改变交接字段、含义、确认/冻结或失效行为时，把生产者、消费者及共享工作流/测试列入跨阶段范围。发现其他阶段的问题先报告，不在本阶段补默认值或绕过校验。

多个任务同时修改不同阶段时，先核对工作区现有差异；共享工作流、公共契约、入口和整库测试不属于任意阶段的独占文件，须明确由哪个任务修改，其他任务避免同时编辑。阶段分目录不能消除共享文件的冲突，也不能覆盖已有未提交改动。

## 实现与验收

- 新增或搬移阶段 `scripts/`、AI/Web 模块中的分支、映射、默认值或解析器前，完整读取 [LLM 与运行时边界](.agents/skills/furniture-agent/references/llm-runtime-boundary.md)，完成分工和完成度审计。只改文案、references、测试数据或已有确定性计算时，不必先读。
- **正式文件只接纳已完成能力**：未完成方案留在 `backlog/`，实现留在开发分支或隔离工作区；不得预埋未来接口与机制。分期须独立可用，具体判据见上述边界文档的「正式文件准入」。
- 测试检查计算、状态、文件和链接；代码归属与完成度由审查判断，不靠关键词、固定文案或测试全绿代替。
- 改板件、制造等影响产物的结构性代码前，先跑 `domain/stages/cad-generated/scripts/tests/test_panel_output_baseline.py`。意外变化改代码，不改基线；故意变化按测试文件头部步骤重建基线，并在提交信息写清「什么变了、为什么变」。

## 同步与维护

- 同步先 fetch、审查新提交，再合并或推送；未完成实现不得因无冲突、测试通过而合入。已进入历史的问题先报告，不擅自回滚他人提交。
- 实现待办前，先跑 `domain/stages/cad-generated/scripts/backlog_reconcile.py`；Open/Done 按 `backlog_landed.py` 的落地版本核对，已落地项转 Done。完成一项时，同次改动更新其落地版本。
- 只有用户明确要求写更新日志时，才在 `changelog/` 新建本次更新的 `YYYYMMDD.N.md`，同日序号递增；不追加旧文件，不维护根 `CHANGELOG.md`。

## Web 预览

启动 `open_projects.py` / `server.py` 供浏览器访问时，必须用 `BypassSandbox: true`、`IsDaemon: true` 在后台启动，确认 `/health` 为 200 后再给链接。Windows 沙箱网络拦截会使 `socket.socketpair()` 挂起、浏览器无法访问端口；真实 HTTP/异步测试（如 `test_project_preview.py`）也须避开沙箱内无超时等待。

