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

不要直调发射器或 `CadBridge`。没有一次性批处理入口；必须确认 `feature_tree_planned` 后再生成 CAD。交互工具面见 [交互工具面](references/agent-tool-contract.md)。

契约见 [运行时契约](references/runtime-contract.md)。实现在 `scripts/furniture_cad/` 与 `scripts/furniture_workflow/`。展示 `stage_outputs.cad_generated` 后暂停；交付验证归 `domain/skills/delivery-validated/SKILL.md`。

**已知的一次白跑（2026-09-24 决定暂缓）**：CAD 每次重跑实测 **4.8–5.6 秒**，几乎全是固定开销（起进程 + 导入 build123d），与柜子数量无关；内容**逐字节相同**的第二版照样重跑，STEP 也逐字节相同。另外制造 / 特征树 / CAD 目前只用 `require_primary_handoff()` 读**主柜**。要不要改成按内容寻址、逐柜复用，取决于"孔位与多柜让单次重算涨到多贵"——唤醒条件与实测数据在 [编排与生命周期未落地需求](references/backlog.md) 的「方向 3」，**动 CAD 之前先看那一条**。
