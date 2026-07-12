# 家具跨阶段运行时

此目录只保存 CAD 阶段和跨阶段应用层：

- `furniture_workflow/`：唯一 Orchestrator、Project/Revision、阶段状态、产物谱系和持久化。
- `furniture_cad/`：CAD Bridge。
- `generate_furniture.py`、`server.py`：CLI/API 协议入口。
- `runtime_paths.py`：加载七个阶段 Skill 的运行时包。
- `tests/`、`validate_workspace_layout.py`：跨阶段集成测试和仓库布局守卫。

设计意图、布局、板件、制造、特征树和交付验证代码分别位于对应 `skills/furniture-*/scripts/`。`FurnitureOrchestrator` 仍是唯一应用层入口：CLI、API 与 Agent 都通过它执行，各阶段包不得建立平行状态机或第二条流水线。
