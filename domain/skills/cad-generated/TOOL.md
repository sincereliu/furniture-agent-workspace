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

**多柜（2026-10-02 起逐柜）**：制造、特征树、**CAD 与交付清单都已逐柜**——布局里有几台柜，就出几套柜级产物（`bom.<cabinet_id>.md`、`<cabinet_id>.step`、`<cabinet_id>.drilled-holes.*`、`六面钻文件/{cabinet_id}__{role}.xml`），manifest 的柜级记录带 `cabinet_id`，交付验证会拦住"规划了三台、只有一台有文件"。产物形状是 `{"cabinets": [{"id", "bom"|"tree"|"bridge"}]}`，与板件 `cabinets[]` 一一对应。

**成本口径（实测 + 推算）**：桥是**一个源文件起一个进程**，实测约 **5 秒/次**，所以 CAD 阶段是 **N 台 ≈ N × 5 秒**（2 台 ~10 秒、3 台 ~15 秒、6 台 ~29 秒，正好压到下面那条"单次 >30 秒"的唤醒线）。要压这个成本只有两条路：**一个进程里连做几台**，或**按柜内容寻址复用**（没变的那台不重跑）——后者是[编排与生命周期未落地需求](references/backlog.md) 的「方向 3」，**动之前先看那一条**。

**已知的一次白跑（2026-09-24 决定暂缓）**：CAD 每次重跑实测 **4.8–5.6 秒**，几乎全是固定开销（起进程 + 导入 build123d）；内容**逐字节相同**的第二版照样重跑，STEP 也逐字节相同。要不要改成按内容寻址、逐柜复用，取决于"孔位与多柜让单次重算涨到多贵"——唤醒条件与实测数据在[编排与生命周期未落地需求](references/backlog.md) 的「方向 3」。
