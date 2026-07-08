# 更新日志

## 20260708.1

### 概要

将家具 skill 的参考文档重构为 DDD（领域驱动设计）风格的分层结构。
每个 reference 文件只负责一个领域责任，方便协作者区分用户意图、空间布局、
板件语义、制造工艺、CAD 建模语义、runtime 行为和校验规则。

### 变更内容

- 将 `skills/furniture-cad/references/` 拆分为以下责任层：
  - `design-intent.md`：用户需求，回答“要做什么家具？”
  - `layout-planning.md`：空间布局，回答“家具内部怎么组织？”
  - `panel-planning.md`：板件语义，回答“有哪些物理部件？”
  - `manufacturing-policy.md`：材料、五金、公差、封边和 BOM 规则，回答“应该怎么制造？”
  - `feature-tree.md`：CAD 建模语义，回答“这些部件应该怎么建模？”
  - `workspace-pipeline.md`：当前 runtime contract，回答“当前工作区实际执行什么？”
  - `validation.md`：跨层校验规则。
- 删除旧的 `panel-cabinetry.md` reference，并将其中内容拆分到新的 DDD reference 文件中。
- 更新 `skills/furniture-cad/SKILL.md`，将概念流程描述为：

  `Design Intent -> Layout Planning -> Panel Planning -> Manufacturing Policy -> Feature Tree -> CAD -> STEP`

- 更新 `skills/furniture-cad/references/intake/catalog.yaml`，让柜类家具指向新的 planning references。

### 未改变

- 没有修改 runtime planner 行为。
- 没有修改 planner 接口。
- 没有修改 executable JSON contract。
- 没有修改 CAD emitter 行为。
- 没有修改测试。
- 没有修改生成的 STEP、BOM、cut-list 或其他 artifact。
- 没有声明新增任何实际 runtime 支持的家具能力。

### 校验

- `git diff --check` 通过。
- `quick_validate.py skills\furniture-cad` 通过。
- 重构后没有残留 `panel-cabinetry.md` 的旧引用。
