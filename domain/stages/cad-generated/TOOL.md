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

契约见 [运行时契约](references/runtime-contract.md)。几何执行在 `scripts/furniture_cad/`；阶段调度、文件写出和 manifest 归 `scripts/furniture_workflow/`。修改 CAD 桥接不接管上游板件、制造或特征树规则。展示 `stage_outputs.cad_generated`；客户接受后用 `furniture_confirm_stage` 确认。客户要做交付验证且 `cad_generated` 已确认时，再打开 [交付阶段](../delivery-validated/SKILL.md)。

维护模块边界、定位实现与测试时，先看 [项目模块导航](references/module-map.md)。

**逐柜产物**：每台已确认且参与制造的柜体各出一套产物（`bom.<cabinet_id>.md`、`<cabinet_id>.step`、`<cabinet_id>.drilled-holes.*`、`六面钻文件/{cabinet_id}__{role}.xml`），manifest 的柜级记录带 `cabinet_id`。制造、特征树和 CAD 的 `cabinets[]` 与冻结板件一一对应；交付阶段负责核对逐柜产物是否齐全。

**当前限制**：按柜内容寻址复用尚未实现。性能实测、已否决方案和暂停记录集中在 [CAD 待办](../../../backlog/cad-generated.md) 的 `content-addressed-reuse`，需要做该优化时再读；本入口只描述现有执行行为。
