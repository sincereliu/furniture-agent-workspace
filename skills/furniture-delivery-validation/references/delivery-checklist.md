# 交付验证清单

回答“当前 Revision 的交付文件是否完整且可追溯？”；区分内置自动验证、上游阶段验证和外部几何审查。

## 内置自动硬关卡

1. 当前 Revision 必须包含并确认 `design_intent` 到 `cad_generated` 六个前置阶段，且每阶段最近一份 `ValidationReport` 通过。
2. Manifest 与每个 Artifact 的 `source_revision_id` 必须等于当前 Revision；任何 `stale` 产物均失败。
3. 必需产物种类齐全，文件存在、非空，实时大小与 SHA-256 和 Manifest 一致。
4. `manufacturing_plan` 与 `bom` 的 Manifest `readiness` 必须等于 `manufacturing_planned.readiness`。
5. `readiness=preliminary` 只产生警告：文件可以完整交付，但不得称为工厂已确认或可直接投产。

## 已由上游阶段负责的语义关卡

- 意图完整性和可执行类别归 `design_intent` 验证。
- 包络、净空、背板模式和区域边界归 `layout_planned` 验证。
- 板件标识、尺寸、位置、依赖和背板几何归 `panels_planned` 验证。
- BOM、封边、解析后的 `back_mount`、`groove` 四条槽以及“背板五金数量与主孔、配合孔数量一致”归 `manufacturing_planned` 验证。
- Feature Tree 标识、依赖、目标和切削包络归 `feature_tree_planned` 验证。
- STEP 与 Viewer 拓扑是否由 CAD Bridge 成功生成归 `cad_generated` 验证。

交付阶段核对这些验证属于当前 Revision 且已通过，不复制或重写各阶段算法。

## 不属于内置通过条件

- `validate_delivery()` 不导入 STEP、不测量几何、不生成快照，也不执行 Viewer 人工审查。
- 需要 STEP 导入、几何尺寸、快照证据时，实际调用 `external/text-to-cad/skills/cad/SKILL.md`。
- 需要可视化审查或链接时，实际调用 `external/text-to-cad/skills/cad-viewer/SKILL.md`。
- 未执行上述外部步骤时，只能报告“未验证”，不得从文件存在或哈希一致推断几何正确。

## 报告边界

- 只报告实际运行/存在的命令、验证和产物。
- `delivery_validated.passed=true` 表示检查点谱系与文件完整性通过，不自动表示几何审查通过或制造状态达到 `factory_ready`。
- 未达到 `factory_ready` 前，不得称 BOM、封边、五金或裁切清单可直接投产。
