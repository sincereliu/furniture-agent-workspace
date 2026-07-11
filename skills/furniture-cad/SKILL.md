---
name: furniture-cad
description: 通过本工作区，把任何家具类别的请求转化为可确认的设计意图、布局规划、板件规划、制造策略、特征树规划和经过验证的 CAD。适用于家具尺寸或布局、结构、板件语义、制造推理、STEP 生成，以及当前家具流水线能力范围相关问题。
---

# 家具 CAD

将本技能作为轻量路由器。用户意图、空间组织、制造零件、制造规则、CAD 建模语义、运行时执行和验证应保持为独立领域层。运行时代码决定可执行行为；本技能中的参考文档说明如何使用这些行为。

概念工作流：

`设计意图 -> 布局规划 -> 板件规划 -> 制造策略 -> 特征树 -> CAD -> STEP`

这些是文档和推理层。当前运行时仍由本技能 `scripts/` 下已有的规划器实现规划；本技能不定义新的规划器接口、可执行 JSON 结构或运行时步骤。

## 强制代码放置规则

工作区只保留两个本地脚本位置：

1. 可复用的家具运行时模块、命令、验证辅助工具及其测试，放在 `skills/furniture-cad/scripts/` 下。
2. 一次性的检查、迁移、调试和 CAD 实验脚本，放在已忽略的 `temp/` 目录下，并在任务结束时删除。

禁止创建根级 `scripts/`、`packages/`、`tests/`、`scratch/` 或 `tmp/` 代码树。禁止在 `generated/` 下放置 `.py`、`.pyc`、PowerShell、shell、JavaScript 或其他生成的源文件；生成的 CAD 源码应放在 `temp/cad-source/`。不得为了方便创建第三个脚本位置。完成任何代码布局或 CAD 生成变更前，运行：

```powershell
.\.venv\Scripts\python.exe skills\furniture-cad\scripts\validate_workspace_layout.py
```

任何报告的违规项都视为验证失败；报告完成前必须移动或删除违规文件。

## 按任务路由

1. 读取[家具目录](references/intake/catalog.yaml)，将用户请求匹配到一个类别；无匹配时使用目录的回退规则。默认尺寸和参数位于 `scripts/furniture/design_spec.py`（数据类默认值及 `CABINET_PRESETS`）。
2. 对于用户需求、尺寸、风格、约束或早期设计讨论，读取 [references/design-intent.md](references/design-intent.md)。返回一份可确认的设计意图；除非用户要求后续阶段，否则到此停止。
3. 对于布局、板件语义、制造策略、特征树推理或验证，加载所选目录项适用的 `planning_references`。
4. 在声称支持、规范化可执行 JSON、运行生成或报告产物前，读取 [references/workspace-pipeline.md](references/workspace-pipeline.md)；若能力可能已变化，还要检查其中指向的实时入口。
5. 对不受支持的家具类别，先完成有价值的意图或建模方案工作，再明确说明执行边界；不得在技能内虚构新的运行时路径。

## 领域参考文档

- [设计意图](references/design-intent.md)：要制作什么家具。
- [布局规划](references/layout-planning.md)：家具如何组织。
- [板件规划](references/panel-planning.md)：有哪些实体部件。
- [制造策略](references/manufacturing-policy.md)：应如何制造。
- [特征树](references/feature-tree.md)：部件应如何建模。
- [工作区流水线](references/workspace-pipeline.md)：当前运行时实际执行什么。
- [验证](references/validation.md)：报告成功前必须通过哪些关卡。

## 分阶段工作

1. 捕获并确认设计意图：要制作什么家具。
2. 解决布局规划：主要布局和家具类别选择。
3. 解决板件规划：存在哪些实体家具部件。
4. 解决制造策略：材料、公差、连接方式和 BOM 假设。
5. 在 CAD 几何细节前生成特征树建模语义。
6. 在受支持时，依次运行技能自有的规划器、发射器和 CAD 桥接器。
7. 报告成功前验证相关层和产物。

若用户明确要求端到端运行，并为受支持类型提供了足够信息，则无需额外批准即可继续。只有继续操作会导致适配、安全、结构或制造出现实质错误时，才询问一个聚焦问题。

## 返回内容

- 意图工作：设计意图、假设、未解决决策，以及至多一个阻塞性的确认问题。
- 规划工作：规范化规格、布局决策、板件规划语义、制造策略假设和特征树影响。
- 生成工作：规范化输入、命令结果、已执行的验证，以及实际存在的产物路径。
