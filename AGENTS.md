# 仓库约定

- 做家具或查找阶段入口时，读 [家具智能体](.agents/skills/furniture-agent/SKILL.md)。
- 搜索与列目录默认只针对 `domain/` 与 `.agents/`。`store/`、`generated/`、`temp/`、`changelog/`、`external/`、`vendor/` 只在当前任务、阶段技能或工具结果点名该路径时打开，并且只打开点名的文件或目录。`README.md` 和 `domain/stages/cad-generated/references/runtime-contract.md` 同样：没有点名就不要打开；点名了就读被点到的部分。
- `external/` 是用子模块跟踪的上游整仓。用户点名某一个 CAD 桥或科学分析 Skill，或当前阶段技能的触发表写了该文件时，只打开那一个 Skill，不浏览子模块的其余部分。升级是移动子模块指针。
- `vendor/` 是本仓库自己提供、版本钉死的第三方构建文件。现在是 `vendor/three/0.186.0/`，预览服务按同名 URL 挂出。升级是替换这些文件。默认不读里面的库源码；要核对某个已点名的构建文件时，只打开那个文件。
- 改代码先打开对应阶段包，再按该 Skill 的参考导航打开具体文件：
  - 布局、房间门窗（`openings[]`）→ `domain/stages/layout-plan/`
  - 柜门、层板、抽屉、背板、踢脚、料厚 → `domain/stages/panel-plan/`
  - 材料、封边、连接、五金、BOM、孔 → `domain/stages/manufacture-plan/`
  - 特征树 → `domain/stages/feature-tree/`
  - 确认、重试、冻结、状态机、交互工具 → `domain/stages/cad-generated/scripts/furniture_workflow/` 与 `references/agent-tool-contract.md`
  - CAD/STEP → `domain/stages/cad-generated/TOOL.md` 与 `scripts/furniture_cad/`
  - 交付 → `domain/stages/delivery-validated/`
  - AI 模型接入、网页助手、模型设置与登录 → `domain/modules/ai/`；这是独立应用模块，不属于 CAD 或其他家具阶段，代码、界面、测试和维护文档归该模块。
  - 网页展示（房间页、项目名单、板件页画面）→ `domain/modules/web/`；这也是独立应用模块。摆放求解、拖动换算和板件结构投影仍留在对应阶段。

- 维护某一个阶段的 Skill 时，只改该阶段自己的目录。六个阶段目录是 `domain/stages/` 下的 `layout-plan/`、`panel-plan/`、`manufacture-plan/`、`feature-tree/`、`cad-generated/`、`delivery-validated/`（含各自的 `SKILL.md` 或 `TOOL.md`、`references/`、`scripts/`、`agents/`）。改动必须落到另一个阶段时，先列出要改哪些阶段、哪些文件、为什么不能只留在当前阶段，等开发者看过再改那些文件。用户这次已经点名这些文件，或明确要求跨阶段调整指令和说明时，按该范围改指令和说明，不必再等一次；这个授权不包含改其他阶段的 `scripts/`。
- 新增或搬移阶段 `scripts/` 或独立模块 `domain/modules/ai/`、`domain/modules/web/` 中的分支、映射、默认值或解析器前，必须完整读取 [LLM 与运行时边界](.agents/skills/furniture-agent/references/llm-runtime-boundary.md)，并按该文档完成边界审计。只改 Skill 文案、`references/`、测试数据或已有确定性计算时，不必先读该文档。
- 测试只检查算得对不对、状态对不对，以及约定文件和链接还在不在。新增或搬移上述运行时逻辑时，「这段该不该进 Python」只按该边界文档里的边界审计判断。
- **动结构性代码前先确认回归基线**：改板件、制造这类会改变产物内容的代码之前，先跑 `domain/stages/cad-generated/scripts/tests/test_panel_output_baseline.py`。它红了先判断是不是**意外**变化——意外就改代码，**不要改基线**；确认是故意的才按该文件头部步骤重新生成，并在提交信息里写清「什么变了、为什么变」。
- 不要自动写更新日志。只有用户明确要求写更新日志时，才在 `changelog/` 下为这一次更新新建一个 Markdown 文件；不要追加到已有文件，也不要维护根目录 `CHANGELOG.md`。文件名用 `YYYYMMDD.N.md`（同一天已有文件则 `N` 递增）。
- 实现 `backlog/` 里的条目前，先跑 `domain/stages/cad-generated/scripts/backlog_reconcile.py`。它用 `backlog_landed.py` 里的已落地版本核对待办文件。版本已经落地的条目改到 Done，不再留在 Open。做完一条时，同一次改动里把该条目的已落地版本改成待办里的版本。
