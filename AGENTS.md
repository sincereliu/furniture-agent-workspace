# 仓库约定

- 做家具或查找阶段入口时，读 [家具智能体](.agents/skills/furniture-agent/SKILL.md)。
- 创建、修改或审查 `domain/skills/` 下家具阶段包、CAD 执行工具、家具工作流入口及其测试前，必须完整读取 [LLM 与运行时边界](.agents/skills/furniture-agent/references/llm-runtime-boundary.md)，并按该文档完成边界审计。
- 测试只检查算得对不对、状态对不对、以及约定文件和链接还在不在。不要靠在代码里搜关键词，来判断「这段该不该进 Python」；那种判断改完后仍要自己看代码。
- 不要自动写更新日志。只有用户明确要求写更新日志时，才在 `changelog/` 下为这一次更新新建一个 Markdown 文件；不要追加到已有文件，也不要维护根目录 `CHANGELOG.md`。文件名用 `YYYYMMDD.N.md`（同一天已有文件则 `N` 递增）。
