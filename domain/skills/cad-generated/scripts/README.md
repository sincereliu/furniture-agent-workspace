# 家具跨阶段运行时

模块职责、六阶段数据流和维护入口见 [项目模块导航](../references/module-map.md)。

只保存 CAD 执行工具及跨阶段应用层：

- `furniture_workflow/`：唯一 Orchestrator、状态、谱系、写入和持久化。
- `furniture_contracts/`：阶段无关的校验结果类型与规范 JSON 内容哈希；只依赖标准库。
- `furniture_chat/`：可选网页助手的 HTTP、会话、界面与静态资源；`furniture_ai/`：无家具领域依赖的模型连接。启动前设 `FURNITURE_WEB_CHAT=0` 并重启预览服务可完全移除页面 AI 接入，详见 [维护与禁用说明](../references/ai-integration.md)。
- `furniture_cad/`：CAD Bridge/校验；`server.py`：本机运行时进程。房间场景路由、预览文档和手动打开项目名单都在 `layout-plan`。`agent_tools.py`：交互工具面。
- `runtime_paths.py`：加载阶段包；`run_tests.py`：唯一测试入口；`tests/`、`validate_workspace_layout.py`：集成测试/布局守卫。

其余阶段代码在所属 `domain/skills/{layout-plan,panel-plan,manufacture-plan,feature-tree,delivery-validated}/scripts/`。家具生成经 `FurnitureOrchestrator` 与 `furniture_workflow/agent_tools.py`。阶段包不得另建状态机或流水线。没有一次性自动确认入口。
