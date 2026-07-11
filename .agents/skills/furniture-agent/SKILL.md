---
name: furniture-agent
description: 将家具工作路由到本仓库正确的本地域技能和 CAD 技能。适用于家具需求、设计意图、板件结构、BOM 或裁切清单、特征树、CAD 生成、STEP 检查、产物验证，以及 CAD Viewer 交接。
---

# 家具智能体

将本技能作为家具工作的入口。所有路径从仓库根目录解析，本入口只负责路由。

## 请求路由

1. 每个家具请求都先读取 `skills/furniture-cad/SKILL.md`，并遵循其中按阶段划分的参考文档。
2. 讨论、设计意图、家具结构、板件拆分、BOM 或制造推理，除非明确要求 CAD，否则留在家具技能及 `skills/furniture-cad/scripts/` 运行时内。
3. 从权威目录 `external/text-to-cad/skills/` 中只加载所需的最小技能：
   - CAD 生成、修改、STEP 检查、几何验证或快照：`cad/SKILL.md`。
   - 可视化审查或产物链接：`cad-viewer/SKILL.md`。
   - 有名称的可采购部件：`step-parts/SKILL.md`。
   - 只有明确请求对应输出时，才加载其他引擎技能。
4. 忽略 `external/text-to-cad/plugins/cad/skills/`，它是生成的生产副本。
5. 声称具备可执行支持前，检查实时代码、测试和入口命令；源码缺失时如实报告。

## 边界

- 以已确认的家具意图为事实来源。
- `skills/furniture-cad/scripts/` 负责家具规划；外部引擎负责通用 CAD 生成、检查、快照和查看。
- 可复用脚本、运行时模块和测试放在 `skills/furniture-cad/scripts/`；一次性脚本放在 `temp/`。
- 禁止创建根级 `scripts/`、`packages/`、`tests/`、`scratch/` 或 `tmp/` 代码树；禁止把生成源码写入 `generated/`。
- 代码布局变更后运行 `skills/furniture-cad/scripts/validate_workspace_layout.py` 并修复全部违规项。
- 不得通过修改 `external/text-to-cad` 实现家具领域行为。
- 存在上游意图或源文件时，不得手工修改派生 STEP、GLB、BOM、裁切清单或生成的 Python。
- 不要加载整棵外部技能树，只选择最小相关集合。
- 只报告实际运行过的验证和实际存在的产物。
