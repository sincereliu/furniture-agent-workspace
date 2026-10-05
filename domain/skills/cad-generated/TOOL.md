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

**成本口径（2026-10-02 实测）**：桥是**一个源文件起一个进程**，实测约 **4.2 秒/台**，所以 CAD 阶段是 **N 台 ≈ N × 4.2 秒**（2 台 9.3 秒、3 台 12.4 秒、6 台约 25 秒）。拆开看：**导入 build123d 约 2.4 秒**、建模约 0.25–0.7 秒、**viewer 拓扑导出约 1.4 秒**。

**试过并否掉的方案：一个进程连做几台。** 实测**更慢**——两台柜 **20.1 秒 vs 9.3 秒**（三台：4.0 秒只够跑模型脚本，加上 viewer 导出就反超）。原因：**viewer 拓扑导出必须待在刚建完模型的那个进程里**——长进程里导出同样三台要 **6.7 秒/台**，在模型自己的进程里只要约 1.4 秒（CAD 内核与网格状态是热的）。所以"把桥的整段配方搬进一个进程"这条今天不划算；要复活它，前提是**让模型脚本自己产出 viewer 包**（上游 cadgen 的事），那时一个进程才能真连做几台。

**下一件要做的（2026-10-02 起暂停）**：**按柜内容寻址复用**——没变的那台直接沿用上一版的 STEP 与 viewer 包（**0 秒**）；内容逐字节相同的第二版今天照样白跑 4.2 秒/台。先例是冻结板件（按 sha256 存 `store/<project-id>/panels/<sha256>.json`）。**暂停原因：客户定了边界——代码更新只到 `panel_plan`，制造起往后即将重写**（见[未落地需求](references/backlog.md) 的边界说明）。重写时必须保住两条不变式：**逐柜**、**交付齐全检查**。

**已知的一次白跑（2026-09-24 决定暂缓）**：CAD 每次重跑实测 **4.8–5.6 秒**，几乎全是固定开销（起进程 + 导入 build123d）；内容**逐字节相同**的第二版照样重跑，STEP 也逐字节相同。要不要改成按内容寻址、逐柜复用，取决于"孔位与多柜让单次重算涨到多贵"——唤醒条件与实测数据在[编排与生命周期未落地需求](references/backlog.md) 的「方向 3」。
