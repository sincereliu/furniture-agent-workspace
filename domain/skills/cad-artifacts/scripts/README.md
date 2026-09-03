# 家具跨阶段运行时

只保存 CAD 阶段及跨阶段应用层：

- `furniture_workflow/`：唯一 Orchestrator、状态、谱系、写入和持久化。
- `furniture_cad/`：CAD Bridge/校验；`generate_furniture.py`、`server.py`：CLI/API。
- `runtime_paths.py`：加载阶段包；`tests/`、`validate_workspace_layout.py`：集成测试/布局守卫。

其余阶段代码在所属 `domain/skills/furniture-*/scripts/`。CLI/API/Agent 均经 `FurnitureOrchestrator`；阶段包不得另建状态机或流水线。
