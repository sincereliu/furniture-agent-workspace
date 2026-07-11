# furniture-agent-workspace

板式家具参数化规划、拆单、BOM 与 CAD 输出的本地开发工作区。

## 架构

```text
CLI / FastAPI / Agent Skill
            |
            v
FurnitureOrchestrator
            |
            +-- 家具规划、板件、制造/BOM、特征树
            +-- CadBridge -> external/text-to-cad
            +-- 验证、Project/Revision、产物清单
```

`skills/furniture-cad/scripts/furniture/workflow_orchestrator.py` 是唯一应用层入口。CLI、API 与 Agent 不直接拼装规划器、发射器或 CAD Bridge。

## 入口

```powershell
# CLI：规划并生成 CAD
.\.venv\Scripts\python.exe skills\furniture-cad\scripts\generate_furniture.py <spec.json> --force

# API：只负责 HTTP 协议，内部同样调用 FurnitureOrchestrator
.\.venv\Scripts\python.exe skills\furniture-cad\scripts\server.py
```

可复用代码只放在 `skills/furniture-cad/scripts/`；一次性脚本和派生 CAD 源码放在 `temp/`；最终产物放在 `generated/`。
