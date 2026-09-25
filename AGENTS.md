# 仓库约定

- 做家具或查找阶段入口时，读 [家具智能体](.agents/skills/furniture-agent/SKILL.md)。
- 搜索与列目录默认只针对 `domain/` 与 `.agents/`。不要扫 `store/`、`generated/`、`temp/`、`changelog/`、`external/`、`vendor/`。不要先读 `README.md` 或整份 `domain/skills/cad-generated/references/runtime-contract.md`。
- `external/` 是用子模块跟踪的上游整仓。只有用户点名 CAD 桥或科学分析时，才打开里面对应的那一个 Skill。升级是移动子模块指针。
- `vendor/` 是本仓库自己提供、版本钉死的第三方构建文件。现在是 `vendor/three/0.186.0/`，预览服务按同名 URL 挂出。升级是替换这些文件。默认不读里面的库源码。
- 改代码先打开对应阶段包，再按该 Skill 的参考导航打开具体文件：
  - 布局、房间门窗（`openings[]`）→ `domain/skills/layout-plan/`
  - 柜门、层板、抽屉、背板、踢脚、料厚 → `domain/skills/panel-plan/`
  - 材料、封边、连接、五金、BOM、孔 → `domain/skills/manufacture-plan/`
  - 特征树 → `domain/skills/feature-tree/`
  - 确认、重试、冻结、状态机、交互工具 → `domain/skills/cad-generated/scripts/furniture_workflow/` 与 `references/agent-tool-contract.md`
  - CAD/STEP → `domain/skills/cad-generated/TOOL.md` 与 `scripts/furniture_cad/`
  - 交付 → `domain/skills/delivery-validated/`

- 新增或搬移 `scripts/` 中的分支、映射、默认值或解析器前，必须完整读取 [LLM 与运行时边界](.agents/skills/furniture-agent/references/llm-runtime-boundary.md)，并按该文档完成边界审计。只改 Skill 文案、`references/`、测试数据或已有确定性计算时，不必先读该文档。
- 测试只检查算得对不对、状态对不对、以及约定文件和链接还在不在。不要靠在代码里搜关键词，来判断「这段该不该进 Python」；那种判断改完后仍要自己看代码。
- 不要自动写更新日志。只有用户明确要求写更新日志时，才在 `changelog/` 下为这一次更新新建一个 Markdown 文件；不要追加到已有文件，也不要维护根目录 `CHANGELOG.md`。文件名用 `YYYYMMDD.N.md`（同一天已有文件则 `N` 递增）。
