# 修订继承：内容没变的下游产物不必重做

日常做家具、改某一阶段规则不必读本文。改编排、Revision 生命周期、产物写入或交付校验时读。

问题陈述、实测证据与候选方向的登记在 [编排与生命周期未落地需求](backlog.md)（「摆放级 / 房间级改动不该重跑柜体」）。本文只写**机制**：判据、承认语义、必重算清单、边界与测试要求。

## 1. 依赖面只有五个字段

契约原文在 `furniture_panel_planning/cabinet_envelope.py` 开头：布局交给板件的只有柜 `id`、`furniture_category` 与 `width` / `depth` / `height`；**房间、摆放、原点、旋转不属于这个契约**（`input_adapter.panel_envelopes_from_layout()` 就是照这个投影的）。

推论：摆放变化与房间变化**在数学上不可能**影响柜体内容；柜的尺寸或类别一变，内容必变。判据可以写死，不需要模型判断，也不该有"大概没变"这种档位。

## 2. 判据：`envelope_set`

```
envelope_set(layout) = { unit.id: (unit.furniture_category, unit.width, unit.depth, unit.height)
                         for unit in layout.executable_units() }
```

- **按 id 建映射**（id 在项目内唯一），比较时与顺序无关；同时给出差异分类：`same / added / removed / resized / recategorized`，用于"这次只重做了哪几件"的说明。
- **不要**直接比 `layout_sha256`：它含房间、摆放、原点、旋转，那些变了也应允许复用。
- **数值先归一**：比较前按落盘精度取整（避免 `599.9999` 与 `600` 被当成不同）。
- `executable_units()` 已经过滤掉 `manufacture: false` 与无柜类的包络，判据直接用它的结果（即"不制造的件不参与下游"，与现状一致）。

判据命中 = **所有下游阶段都可继承**；未命中 = 按柜粒度决定谁必须重算（见第 5 节）。

## 3. 承认语义（三条规则）

**R1 承认，而不是重做。** 新 Revision 的某阶段，若其输出内容与**已有的内容寻址文件**同名，则直接**承认**该内容：

| 阶段 | 判据 | 命中对象 |
| --- | --- | --- |
| `panel_plan` | `envelope_set` 未变（或变化的柜都被重算） | `store/<id>/panels/<panel_sha256>.json`（现成，按内容命名） |
| `manufacture_plan` / `feature_tree_planned` | 上游冻结哈希 + `requested_options` / `appearance` 未变 | 无内容寻址文件；**仍重算**（纯 Python、毫秒级），只是**免掉再确认** |
| `cad_generated` | 特征树 + 板件摘要未变 | `generated/...` 目前按 `revision-<n>` 命名，**不命中**；要免掉 build123d 重跑需内容寻址（见第 6 节，另行评估） |

要点：**"重算"和"重新确认"是两件事**。板件/制造重算的代价是毫秒，真正的代价是让人再点一次头 + 重放那 18 个构造字段。R1 先免掉后者。

**R2 承认要留痕，且区分"内容"与"人"。** 建议在 Revision 上记：

```json
"inherited": {
  "panel_plan": {"sha256": "7929fd22…", "from_revision": "rev_…", "from_stage": "panel_plan"}
}
```

并在 `workflow.history` 追一条事件。`approved_stages` 的语义明确为**「这份内容已被确认过」**，不是"人在这一版又点了一次头"；审计时靠 `inherited.from_revision` 回指到真正点头的那一版。这条必须写进契约，否则"内容等同是否等于确认"会一直含糊（对方 backlog 已点到这个取舍）。

**R3 让人看得见。** 工具面/页面快照里标出沿用与重算（如 `panel_plan.inherited_from = rev-2`），确认提示改成"沿用 rev-2 的板件（内容相同），是否继续"，不要让"系统悄悄少做了一步"。

## 4. 必重算清单（钉进测试）

| 变了什么 | 柜体（板件 / 五金 / BOM / 特征树 / 柜体 STEP） | 房间 CAD / 摆放 / 净距 / 预览 | 交付清单与 manifest |
| --- | --- | --- | --- |
| 房间宽深高 | 可继承 | 必重算 | 重算（引用要更新） |
| 摆放（位置 / 朝向 / 离地） | 可继承 | 必重算 | 重算 |
| 柜的宽 / 深 / 高 | **该柜必重算** | 必重算 | 重算 |
| 柜的类别（落地 ↔ 吊柜） | **该柜必重算** | 必重算 | 重算 |
| 柜的增删或 id 变化 | 变化者必重算 | 必重算 | 重算 |
| 门窗 / 障碍物 | 可继承 | 必重算（可能影响放得下 / 被遮挡） | 重算 |
| `manufacture: false` 的件 | 不参与（不入单元） | 必重算（包络仍在房间里挡人） | 重算 |

**`fill` 例外（必须写清）**：`fill: true` 的件宽度**由该墙净长派生**（扣门窗、贴墙障碍、已摆家具）。所以**改房间会改它的 `width`**，判据自然判为"变了"，那件必须重算。这不是判据失灵，而是它正确工作的证据；反过来说也提醒：不要用"房间变了 ⇒ 柜体一定可继承"这种粗略规则。

## 5. 部分复用（进阶，逐柜）

多柜项目里可以做到"卧室柜沿用、客厅柜重算"：板件/制造产物本来就按柜组织（`panel_plan.cabinets[]`、`plan_panel_cabinets()`），逐柜比对 `envelope_set` 即可。

代价是要给产物加**柜级来源**标注（哪个柜来自哪一版），并让交付校验与 manifest 接受**混合来源**。建议先做整版（R1–R3），逐柜留到真实的"多柜 + 频繁改一间"需求出现时再上。

## 6. 前置条件与边界

- **前置 1**：`revise()` 必须保留 `stage_inputs`（对方 backlog「已知缺口」第 1 条：现状会清空，导致"只改摆放"的重放直接缺 18 个字段而失败）。不修这条，继承机制没有输入可比。
- **前置 2**：新版布局必须先通过规划准入（越界 / 干涉 / 遮挡）。"房间变小后柜子还放得下吗"是 layout 阶段的事，继承机制不兜这个底。
- **边界 1**：只在内容**逐字节相同**时继承；哈希不同就重算。不做"近似复用"，也不做容差比较。
- **边界 2（最大风险）**：**隐藏依赖**。若某阶段其实偷读了布局的其它字段（不只是那五个），判据会误判成"没变"。防法不是看代码，而是**用测试锁死**：
  - 改摆放 / 改房间 → 板件与制造的输出哈希**必须逐字节不变**；
  - 改柜宽 / 柜类 / 柜数 → 哈希**必变**；
  - 改房间 → `fill` 件的 `width` **必变**。
- **边界 3**：`generated/<project-id>/revision-<n>/` 的目录命名与"内容寻址"是两件事。R1 免掉的是"重新确认"；要让 CAD **不重跑**（build123d 那一步）必须改成按内容寻址输出，那会动血缘（`delivery_validated` 的谱系校验、manifest 的 stale 标记），按对方 backlog 的方向 3 单独评估。

## 7. 落地顺序

1. ✅ **判据 + 测试**：`workflow_inheritance.py::envelope_set()/envelope_diff()`（投影直接建在 `panel_envelopes_from_layout()` 上，判据与板件读的字段不可能分家），差异分类 `same / added / removed / resized / recategorized`。逐字节不变式钉在 `tests/test_revision_inheritance.py`（改摆放/改房间 → 板件输出哈希不变；改宽/类/数 → 必变；改房间 → `fill` 件宽度必变）。
2. ✅ **`revise()` 保留 `stage_inputs`**：做页面写项目（P3）时一并修掉。
3. ✅ **R1 承认**：`workflow_stage_runner._inherit_settled_stage()`——阶段产出落定后，若更早的 Revision 上该阶段已确认且内容摘要逐字节相同，就地把本阶段记为已确认（板件同时写 `confirmed_panel_sha256`）。**不跳过重算**：重算毫秒级，短路会把隐藏依赖的风险引进来。
4. ✅ **R2 留痕 + 契约措辞**：`Revision.approved_digests`（人当年点的哪份内容，`confirm_stage()` 写入）、`Revision.inherited`（`{sha256, from_revision, from_stage}`）、`workflow` 事件；契约在 [运行时契约](runtime-contract.md)「继承不变式」段，明确 `approved_stages` = "这份内容已被确认过"。
5. ✅ **R3 让人看得见（工具面 + 页面）**：`project_snapshot()` 出 `inherited` / `inherited_stages`，`project_layout_document()` 也带 `inherited`；确认提示里说"沿用 rev-2 的板件（内容相同）"是下一步文案工作。
6. ⬜ 制造 / 特征树接上同一条路（机制已经通用了，缺的是"这类内容值得免确认"的确认）；CAD 的内容寻址与逐柜复用另议（边界 3）。
