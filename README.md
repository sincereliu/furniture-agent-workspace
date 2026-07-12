# furniture-agent-workspace

板式家具参数化规划、拆单、BOM 与 CAD 输出的本地开发工作区。

## 架构

```text
CLI / FastAPI / Agent Skill
            |
            v
FurnitureOrchestrator
            |
            +-- 设计意图 -> 布局 -> 板件 -> 制造/BOM -> 特征树
            +-- CadBridge -> external/text-to-cad
            +-- 验证、Project/Revision、产物清单
```

`skills/furniture-cad/scripts/furniture_workflow/workflow_orchestrator.py` 是唯一应用层入口。七个阶段实现由各自 Skill 的 `scripts/` 拥有；CLI、API 与 Agent 不直接拼装规划器、发射器或 CAD Bridge。

## 七阶段交互

交互式 Agent 每次只运行一个阶段：`confirm_stage()` 确认当前阶段，`run_next()` 进入下一阶段。阶段完成后，用户检查 Revision 中对应的 `stage_outputs`；未确认时再次调用不会越过当前检查点。

```text
1. design_intent
2. layout_planned
3. panels_planned
4. manufacturing_planned
5. feature_tree_planned
6. cad_generated
7. delivery_validated
```

设计意图变化使用 `revise()` 从第 1 阶段建立新 Revision。修改第 2～5 阶段时使用 `revise_stage_output()`：新 Revision 只保留修改点之前已确认的结果，修改点及全部下游重新确认或生成。`stage_outputs`、`approved_stages` 和工作流历史会随 Project JSON 一起保存。

`generate_furniture.py` 和 `execute_spec()` 是明确的一次性批处理入口，可以自动确认已通过验证的中间阶段；它们不用于交互式逐步设计。

## 入口

```powershell
# CLI：明确的一次性批处理，规划并生成 CAD
.\.venv\Scripts\python.exe skills\furniture-cad\scripts\generate_furniture.py <spec.json> --force

# API：只负责 HTTP 协议，内部同样调用 FurnitureOrchestrator
.\.venv\Scripts\python.exe skills\furniture-cad\scripts\server.py
```

可复用阶段代码放在对应的 `skills/furniture-*/scripts/`；统一 Orchestrator、CLI/API 和集成测试放在 `skills/furniture-cad/scripts/`；一次性脚本和派生 CAD 源码放在 `temp/`；最终产物放在 `generated/`。
