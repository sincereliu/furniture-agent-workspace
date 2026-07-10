# 家具技能迁移

## 决策

将 skills/furniture-cad 作为 Agent 入口点保留。把可复用知识放在渐进式参考资料中，并将 skill 专用的可执行行为统一放在 `skills/furniture-cad/scripts/`。一次性脚本只放 `temp/`。

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
| core/assembly_adapter.py | skills/furniture-cad/scripts/furniture/cad_bridge.py | 使用 skill 私有包中的桥接模块 |
| 订单脚本和输出布局 | service 或 CLI 层 | 保留在技能之外 |
| 生成缓存和历史对比文件 | 无 | 不迁移 |

旧版 `references/cabinet-structures.md`、`references/panel-placement.md` 和
wardrobe 专用嵌套执行 schema 不作为现行 skill 资源保留。结构语义已经提炼到
`panel-cabinetry.md`，定位公式由 planner 与测试拥有，所有可执行品类共用
`workspace-pipeline.md` 记录的扁平 JSON 契约。品类默认值统一在
`skills/furniture-cad/scripts/furniture/design_spec.py` 中定义（`CABINET_PRESETS`
字典 + dataclass fallback），不分散在多个 YAML 文件中。

## 为什么直接复制不安全

- 早期包混合了 LLM 指令、业务规则、CAD 对象、模板、订单存储和导出命令。
- 其"后到前"的 Y 方向约定是有效的，并且现在与本工作区一致，但旧公式在复用前仍需经过语义 planner 测试。
- 它直接导出 STEP，绕过了当前的 planner、emitter 和 CAD bridge。
- Python 和 YAML 中重复定义了默认值，容易产生漂移。
- 历史技能描述把柜子生成、BOM、加工标准和 CAD 导出混成一个能力声明，无法区分
  "代码能生成"与"结果已达到制造级"。

## 当前状态

1. `floor_cabinet` 和 `wall_cabinet` 已接入统一 planner 与 box Feature Tree；
   table 和 wardrobe 已移除，其功能由通用柜体参数化方案替代。
2. skill 内统一的 `scripts/furniture` 包可以生成板件记录和估算 BOM；主生成 CLI
   会落盘 BOM，但不生成 cut-list。
3. 两种柜体仍是固定模板；品类名可执行不代表任意结构变体都已实现。
4. STEP 与 Viewer topology 仍须经过 CAD bridge 实跑并检查工件后才能宣称成功。
