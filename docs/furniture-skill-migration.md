# 家具技能迁移

## 决策

将 skills/furniture-cad 作为一个轻量级的 Agent 入口点保留。把可复用的家具知识迁移到渐进式参考资料中，并将可执行行为放在工作区包中。不要把早期的“一体化技能目录”直接复制到这个工作区。

## 源到目标映射

| 早期 furniture 内容 | 本工作区中的目标 | 动作 |
|---|---|---|
| SKILL.md 工作流和默认值 | skills/furniture-cad/SKILL.md 以及参考资料 | 按阶段提炼并路由 |
| references/cabinet-structures.md | references/panel-cabinetry.md | 迁移结构语义 |
| references/panel-placement.md | planner 规则和测试 | 保留后到前的 Y 方向并验证范围 |
| configs/*.yaml | 未来版本化的领域策略包 | 不要在技能说明里重复 |
| templates/*.py | 未来的 planner 策略 | 移植行为，而不是移植源码布局 |
| core/panel.py | 未来的家具 schema/领域包 | 从记录中移除 CAD 实体所有权 |
| core/generator.py | planner 与 emitter 包 | 将规划与几何输出拆分 |
| core/assembly_adapter.py | packages/cad-bridge | 使用现有桥接层 |
| 订单脚本和输出布局 | service 或 CLI 层 | 保留在技能之外 |
| 生成缓存和历史对比文件 | 无 | 不迁移 |

## 为什么直接复制不安全

- 早期包混合了 LLM 指令、业务规则、CAD 对象、模板、订单存储和导出命令。
- 其“后到前”的 Y 方向约定是有效的，并且现在与本工作区一致，但旧公式在复用前仍需经过语义 planner 测试。
- 它直接导出 STEP，绕过了当前的 planner、emitter 和 CAD bridge。
- Python 和 YAML 中重复定义了默认值，容易产生漂移。
- 其技能描述承诺了柜子生成和 BOM 输出，但当前工作区尚未实现或验证这些能力。

## 实施顺序

1. 为意图、语义部件、材料和制造注释稳定一个与 CAD 解耦的家具 schema。
2. 增加基于范围坐标测试的 panel-cabinet planner 策略。
3. 扩展 emitter，使其消费语义 panel 特征，而不嵌入业务默认值。
4. 增加基于同一审批后的 Feature Tree 的 BOM 和封边输出。
5. 增加 floor-cabinet、wall-cabinet 和 wardrobe 的端到端夹具。
6. 只有在上述步骤完成后，才将技能能力声明从“仅规划”改为“可执行柜子生成”。
