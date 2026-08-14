# furniture-manufacturing 拆分设计文档

> 状态：待评审（本文档不包含任何代码改动）
> 范围：`skills/furniture-manufacturing` → 拆分为 3 个 skill
> 日期：2026-08-13

## 1. 结论摘要（TL;DR）

`furniture-manufacturing` 目前把 5 类关注点塞进同一个 skill（44 文件 / ~346KB，含 `__pycache__`）。
依赖分析表明其中有 2 群是**零内部依赖**的，可无痛独立；剩下 1 群强耦合，必须整体保留：

| # | 拆分目标 | 内容 | 可拆性 |
|---|---------|------|--------|
| ① | `furniture-manufacturing`（保留） | BOM / 材料 / 封边 / 五金连接 / 孔位 / 校验 + 共享数据模型 | 强耦合，保持不变 |
| ② | `furniture-drilling`（新） | 六面钻 XML、孔位 GLB/STEP、机床坐标变换 | ✅ 零内部依赖 |
| ③ | `furniture-manufacturing-analysis`（新） | 样件试验 / 统计分析 / 生产仿真 | ✅ 零内部依赖 |

拆分后 `furniture-manufacturing` 仍是 `manufacturing_planned` 阶段唯一事实来源；②③ 是**能力型 skill**（非流水线检查点），由其他阶段按需调用，与现有"科学分析是 `stage_analyses` 旁路证据"定位一致。

## 2. 现状结构与问题

### 2.1 文件清单（`scripts/furniture_manufacturing/`）

| 文件 | 大小 | 内部依赖 |
|------|------|----------|
| `manufacturing_models.py` | 2.6KB | 无（仅惰性 import panel_planning 的 `PanelJoint`） |
| `manufacturing_edge_banding.py` | 0.8KB | 无 |
| `manufacturing_hardware.py` | 2.7KB | `manufacturing_models`、`hardware_catalog.yaml` |
| `hardware_catalog.yaml` / `hardware_rules.yaml` | 8.0KB / 4.2KB | 数据，被 `connectors/base.py` 与 `manufacturing_hardware.py` 读取 |
| `connectors/base.py` | 2.8KB | `manufacturing_models` + 两个 yaml |
| `connectors/{trinity,hinge,shelf,back_mount}.py` | 9.1~20.3KB | `connectors.base`、`manufacturing_models` |
| `manufacturing_bom.py` | 13.7KB | `edge_banding`、`manufacturing_hardware`、`connectors`、`manufacturing_models` |
| `hole_validator.py` | 5.6KB | `connectors.base.HoleSpec`、`manufacturing_models` |
| `validation.py` | 14.7KB | `manufacturing_bom`、`hole_validator`、`manufacturing_models` |
| `drilled_holes_glb.py` | 7.7KB | 无（仅 json/pathlib/build123d） |
| `export_six_side_drill.py` | 11.7KB | 无（仅 json/yaml/xml） |
| `devices/six_side_drill_guigui.yaml` | 1.7KB | 被 `export_six_side_drill.py` 读取 |
| `coordinate_system.py` | 5.9KB | `transform` |
| `transform.py` | 4.8KB | 无（仅 numpy） |
| `prototype_experiment.py` | 4.2KB | 无（仅 stdlib） |
| `test_statistics.py` | 8.1KB | 无（仅 math/statistics） |
| `production_simulation.py` | 13.3KB | 无（仅 stdlib + simpy） |

### 2.2 关注点归类（为什么"重"）

1. **核心制造规划**：材料 / 封边 / 五金连接 / 孔位 / BOM / 槽 / 校验（`manufacturing_bom.py`、`manufacturing_models.py`、`manufacturing_edge_banding.py`、`manufacturing_hardware.py`、`validation.py`、`hole_validator.py`、`connectors/`、`hardware_*.yaml`）。
2. **打孔导出**：六面钻 XML + 孔位 GLB/STEP + 机床坐标（`export_six_side_drill.py`、`drilled_holes_glb.py`、`devices/`、`coordinate_system.py`、`transform.py`）。
3. **科学分析旁路**：样件试验 / 统计 / 生产仿真（`prototype_experiment.py`、`test_statistics.py`、`production_simulation.py`）。

### 2.3 跨 skill 消费者（精确清单）

| 消费者文件 | 当前 import 的 `furniture_manufacturing` 符号 |
|-----------|---------------------------------------------|
| `skills/furniture-cad/scripts/furniture_workflow/workflow_orchestrator.py` | `manufacturing_bom.{BOMReport, emit_drilled_holes, plan_manufacturing, format_bom_markdown}`、`manufacturing_models.{HardwareRecord, MachiningOperation, PanelRecord}`、`production_simulation.simulate_production`、`prototype_experiment.design_prototype_experiment`、`test_statistics.analyze_prototype_results`、`validation.validate_manufacturing` |
| `skills/furniture-cad/scripts/furniture_workflow/workflow_artifact_writer.py` | `drilled_holes_glb.{export_drilled_holes_glb, export_drilled_holes_step}`、`export_six_side_drill.drill_json_to_xml_files`、`manufacturing_bom.{emit_drilled_holes, format_bom_markdown}` |
| `skills/furniture-cad/scripts/furniture_workflow/cabinet_pipeline.py` | `manufacturing_bom.{BOMReport, plan_manufacturing}`、`manufacturing_models.PanelRecord` |
| `skills/furniture-feature-tree/scripts/furniture_feature_tree/feature_tree_builder.py` | `manufacturing_models.{MachiningOperation, PanelRecord}` |
| `skills/furniture-cad/scripts/tests/test_recent_manufacturing_patches.py` | `connectors.hinge.HingeConnector`、`connectors.trinity.TrinityConnector`、`drilled_holes_glb._build_grouped_geometry`、`export_six_side_drill.drill_json_to_xml_files`、`manufacturing_bom.{emit_drilled_holes, plan_manufacturing}`、`manufacturing_models.PanelRecord`、`validation.validate_manufacturing` |
| `skills/furniture-cad/scripts/tests/test_skill_architecture.py` | 多处**结构断言**（详见 §7） |

## 3. 依赖分析关键结论

1. **打孔导出群零内部依赖**：`drilled_holes_glb.py`、`export_six_side_drill.py` 只依赖标准库 + 第三方（build123d / yaml / xml），通过**读取 `drilled-holes.json` 产物**工作，不 import 任何 `furniture_manufacturing` 模块。✅ 可直接搬走。
2. **科学分析群零内部依赖**：`prototype_experiment.py`、`test_statistics.py`、`production_simulation.py` 只依赖 stdlib + simpy，函数签名是 `(manufacturing_output: Mapping, config: Mapping) -> dict`，纯函数。✅ 可直接搬走。
3. **核心群强耦合，不可再拆**：`manufacturing_bom.py ↔ connectors/ ↔ validation.py ↔ hole_validator.py ↔ manufacturing_models.py` 互相依赖（BOM 遍历 `ALL_CONNECTORS` 生成孔位和五金；校验器复用 `emit_drilled_holes` 和 `HoleSpec`）。把 `connectors/` 单独拆出去会制造假边界，且 `manufacturing_models.PanelRecord` 被 `feature-tree` 跨阶段引用，模型必须留在一个稳定位置。⚠️ 不建议拆。
4. **`coordinate_system.py` + `transform.py` 是孤儿模块**：全仓库只有 `coordinate_system.py` import `transform`；没有任何生产模块 import `coordinate_system`（`feature_tree_builder.py` 里的 `coordinate_system` 只是数据字段名）。二者实现"柜体全局→板件局部→六面钻机床坐标"变换，概念上属六面钻导出域，建议随打孔导出搬走（或作为遗留工具保留，见 §11 决策点 3）。

## 4. 目标架构

### 4.1 `furniture-manufacturing`（保留 — 阶段 skill）

- **包**：`furniture_manufacturing`（不变）
- **阶段**：`manufacturing_planned`
- **保留文件**：`manufacturing_models.py`、`manufacturing_bom.py`、`manufacturing_edge_banding.py`、`manufacturing_hardware.py`、`validation.py`、`hole_validator.py`、`connectors/`（base/trinity/hinge/shelf/back_mount）、`hardware_catalog.yaml`、`hardware_rules.yaml`、`__init__.py`
- **SKILL.md**：删除第 6 条（六面钻 XML，移给 furniture-drilling）和第 11–13 条（试验/统计/仿真，移给 furniture-manufacturing-analysis），其余不变；`references/manufacturing-rules.md` 同步删除"六面钻 XML 导出"章节。
- **frontmatter description**：聚焦"材料/封边/连接/五金/BOM"，把导出类触发词移出。

### 4.2 `furniture-drilling`（新 — 能力 skill）

- **目录**：`skills/furniture-drilling/`，含 `SKILL.md`、`agents/openai.yaml`、`scripts/furniture_drilling/`
- **包**：`furniture_drilling`
- **文件**：`drilled_holes_glb.py`、`export_six_side_drill.py`、`coordinate_system.py`、`transform.py`、`devices/six_side_drill_guigui.yaml`、`__init__.py`
  - 注意：`coordinate_system.py` 内 `from furniture_manufacturing.transform import OrthoRotation` 需改为 `from furniture_drilling.transform import OrthoRotation`。
- **职责**：把 `drilled-holes.json`（由 `emit_drilled_holes()` 产出）转换为六面钻 XML（KDTPanelFormat）与孔位 GLB/STEP 预览。
- **触发**：用户说"生成六面钻文件 / 六面钻 XML / 孔位 STEP / 孔位 GLB"。
- **frontmatter 示例**：
  ```
  name: furniture-drilling
  description: 能力技能，由 cad_generated 阶段的 workflow_artifact_writer 调用。将 drilled-holes.json 导出为六面钻 XML、孔位 GLB/STEP 预览；不做制造规划、不打孔决策、不校验 BOM。
  ```
- **agents/openai.yaml**：`display_name: 家具打孔导出` / `short_description: 六面钻 XML 与孔位 GLB/STEP 导出`。

### 4.3 `furniture-manufacturing-analysis`（新 — 能力 skill）

- **目录**：`skills/furniture-manufacturing-analysis/`，含 `SKILL.md`、`agents/openai.yaml`、`scripts/furniture_manufacturing_analysis/`
- **包**：`furniture_manufacturing_analysis`
- **文件**：`prototype_experiment.py`、`test_statistics.py`、`production_simulation.py`、`__init__.py`
- **职责**：制造阶段的样件试验设计、已采集数据的统计、板件级生产仿真。三者继续写 `stage_analyses.manufacturing_planned`，仍是旁路证据，不自动提升 `readiness`。
- **触发**：用户说"对比样件 / 承重试验 / 涂装对比 / 分析试验数据 / 交期仿真 / 工位排队"。
- **frontmatter 示例**：
  ```
  name: furniture-manufacturing-analysis
  description: 能力技能，由 manufacturing_planned 阶段按需调用。规划样件/承重/涂装对比试验、分析已采集试验数据、仿真板件流转与交期；结果写入 stage_analyses.manufacturing_planned，是旁路证据，不自动提升 readiness。
  ```

## 5. 模块搬迁映射表

| 现状路径（`skills/furniture-manufacturing/scripts/furniture_manufacturing/`） | 目标路径 |
|---|---|
| `drilled_holes_glb.py` | `skills/furniture-drilling/scripts/furniture_drilling/drilled_holes_glb.py` |
| `export_six_side_drill.py` | `skills/furniture-drilling/scripts/furniture_drilling/export_six_side_drill.py` |
| `coordinate_system.py` | `skills/furniture-drilling/scripts/furniture_drilling/coordinate_system.py` |
| `transform.py` | `skills/furniture-drilling/scripts/furniture_drilling/transform.py` |
| `devices/six_side_drill_guigui.yaml` | `skills/furniture-drilling/scripts/furniture_drilling/devices/six_side_drill_guigui.yaml` |
| `prototype_experiment.py` | `skills/furniture-manufacturing-analysis/scripts/furniture_manufacturing_analysis/prototype_experiment.py` |
| `test_statistics.py` | `skills/furniture-manufacturing-analysis/scripts/furniture_manufacturing_analysis/test_statistics.py` |
| `production_simulation.py` | `skills/furniture-manufacturing-analysis/scripts/furniture_manufacturing_analysis/production_simulation.py` |
| 其余全部（models/bom/edge_banding/hardware/validation/hole_validator/connectors/hardware_*.yaml） | 原地不动 |

> `export_six_side_drill.py` 内 `Path(__file__).parent / "devices" / "six_side_drill_guigui.yaml"` 是相对路径，搬移后无需改；`coordinate_system.py` 的 `transform` import 需要改包名。

## 6. 影响面改动清单

### 6.1 运行时路径注册（关键）

| 文件 | 改动 |
|------|------|
| `skills/furniture-cad/scripts/runtime_paths.py` | `STAGE_SKILL_NAMES` 增加 `"furniture-drilling"`、`"furniture-manufacturing-analysis"`（否则新包无法 import） |
| `skills/furniture-cad/scripts/validate_workspace_layout.py` | 同名 `STAGE_SKILL_NAMES` 同步增加两个条目（否则新 skill 的 `scripts/` 被判为"script outside allowed locations"） |

> 语义提醒：这两个列表名为 `STAGE_SKILL_NAMES`，但新增的两个不是"阶段"。建议在实现时一并加注释或改名，避免误导（见 §11 决策点 2）。

### 6.2 import 路径更新（精确）

| 文件 | 改动（旧 → 新） |
|------|----------------|
| `workflow_orchestrator.py` | `from furniture_manufacturing.production_simulation import simulate_production` → `from furniture_manufacturing_analysis.production_simulation import ...`；`prototype_experiment` / `test_statistics` 同理 |
| `workflow_artifact_writer.py` | `from furniture_manufacturing.drilled_holes_glb import ...` → `from furniture_drilling.drilled_holes_glb import ...`；`from furniture_manufacturing.export_six_side_drill import drill_json_to_xml_files` → `from furniture_drilling.export_six_side_drill import ...`；`manufacturing_bom` 部分不动 |
| `tests/test_recent_manufacturing_patches.py` | `drilled_holes_glb`、`export_six_side_drill` 的 import 改 `furniture_drilling`；`connectors` / `manufacturing_bom` / `manufacturing_models` / `validation` 不动 |
| `cabinet_pipeline.py` / `feature_tree_builder.py` | 无改动（只依赖 `manufacturing_bom` / `manufacturing_models`，均保留） |

### 6.3 文档 / 路由

| 文件 | 改动 |
|------|------|
| `skills/furniture-manufacturing/SKILL.md` | 删第 6、11–13 条，指向两个新 skill |
| `skills/furniture-manufacturing/references/manufacturing-rules.md` | 删"六面钻 XML 导出"章节 |
| `.agents/skills/furniture-agent/SKILL.md`（router） | 在"规则"里新增两个按需路由条目（指向 `skills/furniture-*/SKILL.md`）；`manufacturing_planned` → `furniture-manufacturing` 的映射不变 |
| 新 skill 各自 `SKILL.md` + `agents/openai.yaml` | 新建 |

## 7. 架构测试影响（`test_skill_architecture.py`）

该测试把当前 7 阶段架构和制造包文件位置**硬编码**了，拆分必须同步更新，否则 CI 红：

| 测试 | 断点 | 处理 |
|------|------|------|
| `test_scientific_skills_are_routed_on_demand_to_stage_owned_adapters` | 断言 `prototype_experiment.py` / `test_statistics.py` / `production_simulation.py` 位于 `furniture-manufacturing/scripts/furniture_manufacturing/` | 改为断言位于 `furniture-manufacturing-analysis/scripts/furniture_manufacturing_analysis/` |
| `test_each_stage_skill_owns_its_runtime_package` | 遍历 `STAGE_RUNTIME_PACKAGES`（7 项） | 新增两个 skill 不在该表，需决定是否扩展为含"能力包"的映射（见 §11 决策点 1） |
| `test_corrected_stage_boundaries_match_runtime_ownership` | 断言 `furniture-manufacturing/SKILL.md` 含 `workflow_artifact_writer.py` | 该词随六面钻条目迁走；改为断言 `furniture-drilling/SKILL.md` 含 `workflow_artifact_writer.py` |
| `test_back_mount_contract_is_synchronized...` | 断言 manufacturing SKILL.md 含 `BackMountConnector` / `generate_holes_for_panels` | ✅ 不受影响（connectors 保留在 manufacturing） |
| `test_seven_stages_have_one_skill_each` / `test_router_uses_explicit_stage_skill_paths` | 7 阶段映射 | ✅ 不受影响（manufacturing 仍是阶段，新增 skill 非阶段，不被遍历） |
| `test_stage_validation_rules_do_not_live_in_the_orchestrator` | `furniture_manufacturing/validation.py` 路径 | ✅ 不受影响 |

## 8. 风险与权衡

- **循环 import 风险：低**。打孔导出读 JSON 产物而非 `HoleSpec`/`PanelRecord`，科学分析纯函数，都不回指核心包。
- **共享模型归属**：`manufacturing_models.py` 留在 `furniture-manufacturing`（被 feature-tree/orchestrator 跨阶段引用）。若未来 feature-tree 也想独立，才考虑把它提升为共享库——本次不动。
- **"阶段" vs "能力" 的语义**：两个新 skill 不是检查点，不产生 `stage_outputs`；需在 SKILL.md 与 router 里写清"能力型，按需加载，不推进阶段"，避免被误当流水线阶段。
- **`runtime_paths.py` / `validate_workspace_layout.py` 的命名漂移**：把非阶段 skill 放进 `STAGE_SKILL_NAMES` 是当前最省事的做法，但名字会误导，建议改名/加注释。
- **测试耦合**：架构测试对文件位置敏感，拆分需与测试更新同 commit 落地，避免中间态。

## 9. 实施步骤（顺序 + 每步验证）

1. 新建两个 skill 目录骨架（`SKILL.md` + `agents/openai.yaml` + `scripts/<pkg>/__init__.py`）。
2. `git mv` 搬迁 8 个模块 + 1 个 devices yaml（§5 映射表），改 `coordinate_system.py` 的 `transform` import。
3. 更新 `runtime_paths.py`、`validate_workspace_layout.py` 的两个 `STAGE_SKILL_NAMES`。
4. 更新 `workflow_orchestrator.py`、`workflow_artifact_writer.py`、`test_recent_manufacturing_patches.py` 的 import。
5. 更新三份 SKILL.md、`manufacturing-rules.md`、router `.agents/skills/furniture-agent/SKILL.md`。
6. 更新 `test_skill_architecture.py`（§7）。
7. 验证：
   - `.\\.venv\\Scripts\\python.exe skills\\furniture-cad\\scripts\\validate_workspace_layout.py`
   - 跑 `skills/furniture-cad/scripts/tests/`，重点 `test_skill_architecture.py`、`test_recent_manufacturing_patches.py`。
   - 走一遍 CLI/API 生成流程，确认 `drilled-holes.json/.glb/.step` 与六面钻 XML 仍正常产出。

## 10. 备选方案对比

| 方案 | 内容 | 优点 | 缺点 |
|------|------|------|------|
| **A（推荐）3-way** | 见本文档 | 依赖边界清晰，改动量适中 | 需更新架构测试 + 2 个路径注册 |
| B（2-way，最小） | 只把科学分析三件套拆出 | 改动最小、最安全 | 打孔导出仍留制造，SKILL 仍偏重 |
| C（4-way） | 再拆 `furniture-hardware`（connectors） | 制造更薄 | connectors↔bom↔validation↔models 强耦合，需额外处理共享模型，假边界风险高 |

## 11. 待评审决策点

1. **新 skill 是否纳入架构测试的包映射**：`test_each_stage_skill_owns_its_runtime_package` 目前只认 7 个阶段包。是扩展测试覆盖两个能力包，还是保持 7 阶段语义、另写能力包断言？
2. **`STAGE_SKILL_NAMES` 命名**：是否随本次改名（如 `SKILL_SCRIPT_ROOTS` / `SKILL_NAMES_WITH_SCRIPTS`）并同步两处 + 测试，还是保持现状只加条目？
3. **`coordinate_system.py` / `transform.py` 的去留**：当前为孤儿模块，确认随 `furniture-drilling` 搬走（推荐），还是作为遗留工具留在 manufacturing？
4. **新 skill 命名**：`furniture-drilling` vs `furniture-machining-export`；`furniture-manufacturing-analysis` vs `furniture-manufacturing-science`。请拍板。



