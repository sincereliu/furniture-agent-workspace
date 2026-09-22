# furniture-agent-workspace

板式家具参数化规划、拆单、BOM 与 CAD 输出的本地开发工作区。

编码助手不要读本文件；约定见 `AGENTS.md`，阶段入口见 `.agents/skills/furniture-agent/SKILL.md`。

## 架构

```text
家具项目从 layout-plan 进入：房间、家具包络、摆放检查
            |
            v
确认布局 -> 板件 -> 制造/BOM -> 特征树 -> CAD -> 交付验证
            |
            +-- 按需科学分析 -> stage_analyses（不改阶段检查点）
            +-- CadBridge -> external/text-to-cad

同一套摆放内核另有独立房间场景（HTTP）。它不进入阶段检查点。
```

家具生成走 `furniture_*` 工具，编排在 `domain/skills/cad-generated/scripts/furniture_workflow/`。各阶段规则与实现在 `domain/skills/`。全屋布局确认后，下游只读冻成的柜体外包络。交互协议见 `domain/skills/cad-generated/references/agent-tool-contract.md`。

## 入口

家具生成只走 `furniture_*` 工具。独立房间布局：

```powershell
.\.venv\Scripts\python.exe domain\skills\cad-generated\scripts\server.py
```

独立房间场景：`POST /api/plan-room` 返回摆放 JSON，`/api/plan-room/preview` 返回 SVG，`/api/plan-room/viewer` 返回 HTML，`/api/plan-room/cad` 追加房间包络 CAD。场景状态另有一组端点（保存、读取、列出、单次编辑、可编辑视图），完整清单见 [运行时契约](domain/skills/cad-generated/references/runtime-contract.md)。

可复用阶段代码在 `domain/skills/*/scripts/`；Orchestrator、布局 API 和集成测试在 `domain/skills/cad-generated/scripts/`；一次性脚本和派生 CAD 源码在 `temp/`；最终产物在 `generated/`。

从零建 `.venv`、用 uv 对齐 `external/text-to-cad` 的 cadgen pin（fnm 只在改 Viewer / bundle 时需要）：见 [开发环境](.agents/skills/furniture-agent/references/dev-environment.md)。

可选数值依赖：

```powershell
uv sync --extra furniture-analysis
```
