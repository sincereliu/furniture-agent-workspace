# 架构

该仓库被组织为一个用于家具 CAD 生成的分层系统。

## 各层职责

- Workspace：协调所有模块的顶层工程项目。
- external/text-to-cad：用于几何生成的外部 CAD 引擎。
- packages/cad_bridge：隔离外部依赖并暴露稳定接口的适配层。
- packages/furniture_schema：家具参数和输入契约的规范 schema。
- packages/furniture_planner：将结构化规格转换为结构规划。
- packages/furniture_pipeline：复用规划、拆单和 BOM 生成用例。
- validation：检查约束、验证计划并应用修复策略。
- services/furniture-agent：HTTP 输入输出和服务启动入口。
- apps/web 和 apps/cli：面向用户的交互界面。
- skills/furniture-cad：用于家具生成的可复用 LLM 规则和领域知识。

## 推荐执行流程

1. 用户通过 Web 应用或 CLI 发出请求。
2. Agent 解析请求并生成结构化规格。
3. 规划器根据规格创建特征树。
4. 验证层检查特征树并修复无效或不完整的部分。
5. 执行层调用 CAD 桥接层，而后者再与外部 CAD 引擎通信。
6. 最终的 CAD 工件返回给用户。
