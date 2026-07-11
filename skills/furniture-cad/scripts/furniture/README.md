# 家具技能运行时

这是 `furniture-cad` 技能的私有运行时包。把它放在技能旁边，可以避免将同一工作流拆散到根目录的 `packages/`、`scripts/` 和 `tests/` 中：

1. `design_*` —— 设计意图与可执行尺寸。
2. `layout_*` —— 布局规划与柜体定位。
3. `panel_*` —— 板件语义与生产记录。
4. `manufacturing_*` —— 封边、钻孔、五金和 BOM 策略。
5. `feature_tree_*` —— 特征树构建与 CAD 源码发射。
6. `cad_bridge.py` —— 调用并验证外部 STEP 生成。
7. `workflow_*` —— 编排、修订、验证和产物谱系。

`planner.py` 是边界明确的无状态规划门面。家具 JSON 必须先经过规划和特征树生成，之后 `cad_bridge.py` 才能调用外部 `text-to-cad` 引擎。
