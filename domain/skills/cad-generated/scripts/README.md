# 家具跨阶段运行时

只保存 CAD 执行工具及跨阶段应用层：

- `furniture_workflow/`：唯一 Orchestrator、状态、谱系、写入和持久化。
- `furniture_cad/`：CAD Bridge/校验；`server.py`：独立房间布局 API。`agent_tools.py`：交互工具面。
- `runtime_paths.py`：加载阶段包；`tests/`、`validate_workspace_layout.py`：集成测试/布局守卫。

其余阶段代码在所属 `domain/skills/{design-intent,layout-plan,panel-plan,manufacture-plan,feature-tree,delivery-validated}/scripts/`。家具生成经 `FurnitureOrchestrator` 与 `furniture_workflow/agent_tools.py`；房间布局 API 走 `layout-plan` 自有运行时。阶段包不得另建状态机或流水线。没有一次性自动确认入口。
