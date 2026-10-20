# 家具跨阶段运行时

模块职责、六阶段数据流和维护入口见 [项目模块导航](../references/module-map.md)。

只保存 CAD 执行工具及跨阶段应用层：

- `furniture_workflow/`：唯一 Orchestrator、状态、谱系、写入和持久化。
- `furniture_contracts/`：阶段无关的校验结果类型与规范 JSON 内容哈希；只依赖标准库。
- AI 助手已独立到 [domain/modules/ai](../../../modules/ai/README.md)：`furniture_chat/` 管网页助手，`furniture_ai/` 管模型连接，专属测试和维护文档也在模块内。启动前设 `FURNITURE_WEB_CHAT=0` 并重启预览服务可禁用网页 AI 接入。
- 网页展示已独立到 [domain/modules/web](../../../modules/web/README.md)：房间页、项目名单和板件页的画面在 `furniture_web/`。摆放求解和拖动换算仍在布局阶段，由同一个 `/layout-view` 挂出。
- `furniture_cad/`：CAD Bridge/校验；`server.py`：本机运行时进程。房间场景路由、预览文档和手动打开项目名单都在 `layout-plan`。`agent_tools.py`：交互工具面。
- `runtime_paths.py`：加载阶段包与独立模块；`run_tests.py`：统一发现阶段和 AI 模块测试；`tests/`、`validate_workspace_layout.py`：集成测试/布局守卫。网页模块的页面行为由这些预览测试覆盖。

其余阶段代码在所属 `domain/stages/{layout-plan,panel-plan,manufacture-plan,feature-tree,delivery-validated}/scripts/`。家具生成经 `FurnitureOrchestrator` 与 `furniture_workflow/agent_tools.py`。阶段包不得另建状态机或流水线。没有一次性自动确认入口。
