# CAD 执行工具

本目录不是 Agent Skill。不要添加 `SKILL.md`。

阶段：`cad_generated`

Agent 在 `feature_tree_planned` 已确认后调用 Orchestrator tool。function-calling 宿主使用：

```python
session.call("furniture_run_next", {
    "project_id": project_id,
    "generate_cad": True,
})
```

等价 Python：

```python
orchestrator.run_next(project, output_root="generated", generate_cad=True)
```

不要直调发射器或 `CadBridge`。CLI/API 批处理仍走 `execute_spec()` 或 `scripts/generate_furniture.py`。交互工具面见 [交互工具面](references/agent-tool-contract.md)。

契约见 [运行时契约](references/runtime-contract.md)。实现在 `scripts/furniture_cad/` 与 `scripts/furniture_workflow/`。展示 `stage_outputs.cad_generated` 后暂停；交付验证归 `domain/skills/delivery-validated/SKILL.md`。
