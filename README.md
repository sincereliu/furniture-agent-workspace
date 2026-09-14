# furniture-agent-workspace

板式家具参数化规划、拆单、BOM 与 CAD 输出的本地开发工作区。

编码助手不要读本文件；约定见 `AGENTS.md`，阶段入口见 `.agents/skills/furniture-agent/SKILL.md`。

## 架构

```text
Agent tools (furniture_*) / FastAPI layout
            |
            v
FurnitureOrchestrator  |  layout-plan runtime
            |
            +-- 设计意图 -> 板件 -> 制造/BOM -> 特征树
            +-- 按需科学分析 -> stage_analyses（不改阶段检查点）
            +-- CadBridge -> external/text-to-cad
            +-- 验证、Project/Revision、产物清单

独立 layout-plan -> 房间摆放 / 碰撞检查 / SVG / Viewer
```

家具生成入口是 `domain/skills/cad-generated/scripts/furniture_workflow/`。各阶段规则与实现在 `domain/skills/`。房间摆放是独立能力，不是主流程前置。交互协议见 `domain/skills/cad-generated/references/agent-tool-contract.md`。

## 入口

家具生成只走 `furniture_*` 工具。独立房间布局：

```powershell
.\.venv\Scripts\python.exe domain\skills\cad-generated\scripts\server.py
```

`POST /api/plan-layout` 返回布局 JSON；`/preview` 返回 SVG；`/viewer` 返回 HTML。

可复用阶段代码在 `domain/skills/*/scripts/`；Orchestrator、布局 API 和集成测试在 `domain/skills/cad-generated/scripts/`；一次性脚本和派生 CAD 源码在 `temp/`；最终产物在 `generated/`。

可选数值依赖：

```powershell
uv sync --extra furniture-analysis
```
