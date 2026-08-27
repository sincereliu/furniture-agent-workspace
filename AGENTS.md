# 家具 Skill 开发约定

创建、修改或审查 `domain/skills/furniture-*`、家具工作流入口及其测试前，必须完整读取
[LLM 与运行时边界](.agents/skills/furniture-agent/references/llm-runtime-boundary.md)。

- 遵守“LLM 提案、代码准入”：自然语言理解和可确认的方案选择归 LLM；结构化契约、确定性计算、状态、验证与副作用归代码。
- 新增运行时代码前，按边界文档逐项判断；无法归入允许代码类别的逻辑，移到所属 Skill 的 `SKILL.md` 或 `references/`。
- 修改完成后执行边界审计，检查新增的分支、映射、默认值和解析器，并在交付说明中报告保留在代码中的理由及任何例外。
- 自动化测试只验证客观不变量与本约定可发现性，不用关键词扫描代替语义审计。

