# 编排与生命周期未落地需求

日常做家具、改某一阶段规则不必读本文。核对实现或规划演进时再打开。

## 待评审

### 页面写项目：多窗口提示、撤销按钮（工作副本与租约已落地）

**现状**：`POST /api/project/{id}/layout/edit`、`/layout/undo` 已落地。**工作副本（方案 H）已落地**：还没有下游产物时改动**原地生效**（版号不变、内容摘要变），撤销日志记旧值、下游一产出就关门；有下游产物时追加新 Revision。**房间级确认、编辑租约、页面接入**都已落地（预览页按权限渲染成可编辑/只读/分享三态，页面自己申请租约、心跳、闲置让出）。

**待决定**：① 撤销要不要露到页面上（接口与日志已就位、有测试）；② "另一窗口正在编辑"的提示要不要做细；③ 外网只读分享的 token 形态（见下一条）。

### 外网只读分享（token 形态，尚未实现）

**现状**：写权限已收成一道服务端门（`access_scope()` / `may_edit()`，五个有副作用的端点：停进程、保存场景、编辑场景、出房间 CAD、改项目布局），`?mode=view` 只是页面表达（换牌子、去掉「退出」按钮），不承担权限。

**要做**：给不在本机的人看。按 token 形态铺——`GET /share/<token>` + 凭证（可撤销、可过期）落在 `store/<project-id>/shares/`，`access_scope()` 多认一种 `shared` 来源（`may_edit("shared")` 恒假，四个端点不用改）。**通道是主要成本**：今天服务只监听 `127.0.0.1`，开隧道或放开监听之前必须先确认门在位，否则等于把写接口公开。

**明确不做**：外人在页面上改（并发、冲突、审计属"页面写项目"那条线）。

**设计方案**：[预览页的访问模式与外网分享](preview-access-design.md)。

### 摆放级 / 房间级改动不该重跑柜体（方向 1+2 已落地；方向 3 待定）

**现状（已改）**：方向 1「摘要重用」与方向 2「`revise()` 保留 `stage_inputs`」都已实现。现在改摆放或改房间后跑板件，若内容与更早某版**已确认**的板件逐字节相同，系统直接承认那次确认（不再要人点头），并记 `Revision.inherited` 回指到真正点头的那一版；`revise()` 不再丢 `stage_inputs`。判据、逐字节不变式、`fill` 例外与三条承认规则见 [修订继承设计](revision-inheritance-design.md)（落地顺序 1–5 已完成）。

**仍未做**：方向 3「产物按内容寻址复用」——`generated/<project-id>/revision-<n>/` 现在仍按修订号出目录，所以 CAD / STEP **还是会重跑**（哪怕几何一模一样）。要改就得动血缘：`delivery_validated` 的谱系校验、`manifest` 的 stale 标记，以及逐柜复用的混合来源。建议等 CAD 真的成为瓶颈再评估。

**现象（原始记录）**：客户改一个柜子的摆放、或房间进深，`revise_layout()` 会开新 Revision 并从 `layout_plan` 重来。柜体本身没变，但下游（板件 → 制造 → 特征树 → CAD → 交付）全部作废重做，而且每一格都要人重新确认。

**根本原因**：`revise()` 一律作废，不做内容比对。抽屉式契约其实早就分开了 —— 布局交给板件的只有 `id / furniture_category / width / depth / height`（`furniture_panel_planning/cabinet_envelope.py` 开头明确写着 "Layout rooms, placement, origin, and rotation are not part of this contract"），所以摆放改动**理论上不可能**影响柜体。

**实测证据**（临时项目实跑，跑完已删；同一份板件参数，每次走 改布局 → 确认 → 重跑板件 → 确认板件）：

| 改动 | `panel_plan` 内容 | `panel_sha256` |
| --- | --- | --- |
| 柜子沿北墙 100mm → 1200mm | 完全相同 | 相同（`7929fd22…`） |
| 房间进深 3000 → 4200 | 完全相同 | 相同 |
| 柜宽 800 → 900 | 变了 | 变了 |

`plan_panel_stage()` 是纯 Python、无 LLM、无 IO，重跑本身毫秒级。真正付代价的是两处：

1. ~~**要人重新确认。** 板件内容与摘要都一样、冻结文件就是硬盘上那一份，但新 Revision 的 `confirmed_panel_sha256` 是 `None`，系统仍要求再确认一次板件。~~ **已解决**：内容逐字节相同时直接承认上一版的确认（`Revision.inherited`）。
2. **CAD 白跑。** `generated/` 按 `revision-<n>` 命名，所以必出新目录、必再跑一次 build123d 出 STEP，哪怕几何一模一样。**仍未解决**（方向 3）。

**候选方向（按性价比）**

1. **摘要重用。** ~~新 Revision 算出板件后，若 `panel_sha256` 与已有冻结文件同名，直接认定已确认（记 `confirmed_panel_sha256 =` 该摘要），跳过"再确认一次"。~~ **已做**：判据不是"冻结文件同名"，而是"更早某版该阶段已确认、且确认的内容摘要逐字节相同"，记在 `approved_digests` / `inherited` 上（更准，也不依赖 store 是否落盘）。`approved_stages` 的语义就此定为**「这份内容已被确认过」**，不是"人在这一版又点了一次头"，审计靠 `inherited.from_revision` 回指真正点头的那一版。
2. **布局修订时保留 `stage_inputs`。** 见下方「已知缺口」第 1 条。**已做（P3）**。
3. **产物按内容寻址复用**（`generated/` 改成按 特征树 + 板件摘要 命名，内容没变就指回旧目录）。收益最大但动血缘：`delivery_validated` 的谱系校验、`manifest` 的 stale 标记都要跟着改。建议等 CAD 真的成为瓶颈再说。

**方向 3 的实测代价（2026-09-24 实测，真实 build123d / `external/text-to-cad`）**

| 阶段 | 耗时 | 说明 |
| --- | --- | --- |
| layout → `panel_plan` | 0.01 s | 纯 Python |
| panel → `manufacture_plan` | 0.05 s | 纯 Python |
| manufacture → `feature_tree` | 0.03 s | 纯 Python |
| feature_tree → **CAD** | **4.8 – 5.6 s** | 出 `model.step`（≈200 KB）+ `drilled-holes.{json,glb,step,step.glb}` + `bom.md` + 六面钻 XML |

- **内容逐字节相同的第二版照样重跑 5.37 s**，产出的 STEP 与第一版**逐字节相同**（`e63ff928dfdaecba` 两次一致）→ 这次重跑纯属白跑。
- **耗时与柜数无关**：1 件 4.75 s、3 件 4.80 s、6 件 4.90 s；STEP 大小也几乎不变（200 / 200 / 200 KB，小柜 184 KB）。→ 这 4.8 秒基本是**固定开销**（起 Python 进程 + 导入 build123d + 初始化发射器），不是几何计算。
- **前置缺口**：`require_primary_handoff()` 只取 `cabinets[0]`，所以制造 / 特征树 / CAD **目前只处理主柜**（见 [板件运行时映射](../../panel-plan/references/runtime-map.md)第 13 行与"交互主流程一份意图一台柜"）。这解释了上面的形状数据，也意味着：**"逐柜复用"的前提是"逐柜 CAD"**——多柜下游没做之前，内容寻址只能省下"整份没变还要重跑"的 4.8 秒。
- **结论（2026-09-24 决定：暂缓，等时机）**：4.8 秒/次不值得为它动血缘（谱系校验 + stale 标记 + 混合来源）。**但有明确的唤醒条件——满足任一条就回来重估方向 3**：
  1. **孔位/加工计算变重之后**：现在每次 4.8 秒几乎全是固定开销（起进程 + 导入 build123d），几何几乎不计时。孔位建模一旦细化（每块板的孔都要真实建模、多柜要各出 STEP），单次会明显上涨——**重算越贵，内容寻址越值**。
  2. **多柜下游落地之后**（制造/特征树/CAD 覆盖每件柜子，见下条前置缺口）：那时"改一件只重跑一件"才有地方可省。
  3. **单次 CAD 实测 > 30 秒**，或真实项目里出现"同一内容被反复白跑"。
  复现脚本：`temp/measure_cad.py`、`temp/measure_cad_shape.py`（临时目录，不入库）。**动 CAD 相关代码前先看一眼这几条。**

**取舍**：现在"改任何上游都开新 Revision、下游全作废"是一条极清晰的血缘规则，审计时无歧义。方向 1+2 保留这条规则、只免掉"内容没变还要重新排队确认"；方向 3 会削弱它。做之前先决定愿意付多少复杂度换多少等待时间。
**设计方案**：[修订继承设计](revision-inheritance-design.md) —— 判据（`envelope_set` 比对与差异分类）、承认语义（R1 承认 / R2 留痕 / R3 让人看得见）、必重算清单、`fill` 例外、逐柜复用、前置条件与测试要求。

## 已知缺口（实测踩到；已修的留档）

1. ~~**`revise()` 会清空 `stage_inputs`。**~~ **已修（P3）**：`revise()`/`revise_layout()` 现在带走父修订的 `stage_inputs`（与 `revise_stage_output()` 一致）。页面写项目让它变成硬需求——改摆放不该顺带丢掉柜体构造参数。落点：`workflow_revision_ops.py::revise()`，测试 `tests/test_project_layout_edit.py::test_new_revision_keeps_the_cabinet_stage_inputs`。
2. **板件参数无法凭记忆重建。** 层板间距必须严格填满内部净空（实测报 `explicit shelf gaps and top gap do not fill the internal height (sum=1982, internal_height=1964)`），内部净空又是从外形尺寸推出来的。所以"重跑板件"不能假设参数可原样搬运，必须完整重放上一版输入。
3. **`store/` 里 79/84 份 revision 是旧格式**（`stage_outputs` 用 `design_intent` / `panels_planned` / `manufacturing_planned`）。实测加载报 `ValueError: revision requires layout`（`Revision.from_dict` 第一步就要求顶层 `layout` 键）。属历史残留，当前代码读不了；`store/` 已忽略，不必清理，但翻 store 排查时先确认格式。
