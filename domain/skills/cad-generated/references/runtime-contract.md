# 家具运行时契约

改编排、产物路径、扁平协议或 store 布局时读本文。做家具或改某一阶段规则时不要读；用当前阶段 Skill。这里只定义运行时契约、命令、路径和限制。

## 当前能力

唯一应用层入口：`domain/skills/cad-generated/scripts/furniture_workflow/workflow_orchestrator.py`。它接受已规划的全屋 `layout_plan`（按房间组织的家具包络 CAD 单元）。板件/制造字段经 `create_project(..., stage_inputs=)` 或 `run_next`/`retry_stage` 的 `stage_input` 进入所属阶段。字段转换、阶段实现和校验归各 Skill，Orchestrator 只管理生命周期。没有一次性自动确认的批处理入口。

- `floor_cabinet` / `wall_cabinet`：layout 只确认柜类、外形尺寸和房间门窗（`openings[]`）。柜门、层板、槽背板/背板安装、踢脚在 `panel_plan` 才准入。

它们不是任意家具配置器。承诺变体前检查板件拓扑模板；其他类别未实现前只做意图/建模方案。

## 六阶段状态与确认

每个 Revision 记录：

1. `layout_plan`
2. `panel_plan`
3. `manufacture_plan`
4. `feature_tree_planned`
5. `cad_generated`
6. `delivery_validated`

输出在 `revision.stage_outputs[stage.value]`，待后续处理的参数在 `revision.stage_inputs`，确认在 `approved_stages`，规划尝试在 `stage_attempts`，历史在 `workflow.history`。`JsonProjectStore` 把 Project 写到 `store/<project-id>/project.json`，确认意图时额外写出冻结文件，每次规划尝试写出独立 attempt 目录。

交互调用（Python）：

```python
orchestrator.confirm_stage(project)          # 确认当前检查点；意图确认后冻结 JSON
result = orchestrator.run_next(project, stage_input={...})  # 生成下一阶段的第一次尝试
orchestrator.retry_stage(project, "panel_plan", stage_input={"parameters": ...})
orchestrator.select_stage_attempt(project, "panel_plan", 1)
```

任意 function-calling 宿主不要直调上述 Python 对象，应注册 `furniture_workflow/agent_tools.py` 的 `openai_tools()`，经 `FurnitureToolSession.call` 传入 `project_id`。工具列表、错误码与快照字段见 [交互工具面](agent-tool-contract.md)。

进入 CAD 阶段须显式给出输出：

```python
result = orchestrator.run_next(
    project,
    output_root="generated",
    generate_cad=True,
)
```

`run_next()`/`run_until()` 不越过未确认检查点。返回当前输出后等待确认。

- 布局确认：`confirm_stage(project, "layout_plan")` 把确认后的布局冻成 `store/<project-id>/layouts/<layout-sha256>.json`。之后板件只读这份冻结布局里的可执行 CAD 单元。
- **房间级确认**：布局检查点是"**每间都审过**"的派生值——`confirm_room(project, room_id)` 审一间，`pending_room_ids()` 说还差哪几间，全部审过时布局才 `confirmed` 并进 `approved_stages`（下游仍只认这一个闸门，panel / 制造 / CAD 的契约没改）。`confirm_stage(layout_plan)` 保留"一次确认全部"的老语义，等价于把剩下的房间一次审完。**没动过的房间，确认跟着走**：新 Revision 里某间房的内容与父修订**逐字节相同**且父修订审过它，就自动记入 `approved_rooms` 并在 `inherited_rooms[room_id] = {sha256, from_revision}` 留痕；若这样凑齐了每一间，布局检查点当场成立（不必再让人点一次头）。所以"改一间只审一间"成立，而"改的是没审过的那间"仍要人看。老项目文件没有 `approved_rooms`：`confirmed: true` 等价于"每间都审过"。
- 内容指纹只有一个实现：`furniture_workflow/workflow_digest.py::stable_digest`——对 `json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",",":"))` 取 sha256。`layout_sha256`、`panel_sha256`、`source_sha256`、`stage_output_sha256` 都走它；**别再各写一份**，否则同一份内容在两个模块里算出两个指纹，冻结文件会互相认不出。交付验证的 `validation._stable_digest` 是同一套算法在独立包里的副本，有测试盯着两者一致。
- 板件确认：`confirm_stage(project, "panel_plan")` 把已确认板件冻成 `store/<project-id>/panels/<panel-sha256>.json`，并记下 `confirmed_panel_sha256`。有 Store 时制造、板件旁路分析、CAD `panel-plan.json` 和交付分析哈希都按该哈希读冻结文件，文件缺失则失败；无 Store 时读内存中已确认输出。`retry_stage(project, "manufacture_plan")` 不重跑板件。
- 同一冻结上游再试规划：`retry_stage(project, stage, stage_input=...)`。适用于未确认或需作废下游的 `panel_plan`、`manufacture_plan`、`feature_tree_planned`。失败只记录该次 attempt，不把 Revision 标为 `FAILED`。
- 选用某次通过的尝试：`select_stage_attempt(project, stage, number)`，再 `confirm_stage()`。
- 布局变化：`revise(project, new_layout)`，从 `layout_plan` 开始，下游尝试作废。
- 直接改已有规划结果：`revise_stage_output(project, stage, edited_output)`。
- 新 Revision 仅复制修改点前的已确认输出；修改阶段和下游重做。旧产物标为 stale，不手改 STEP、GLB、BOM 或源码。

冻结意图、冻结板件与 attempt 文件：

```text
store/<project-id>/
  project.json
  layouts/<layout-sha256>.json
  panels/<panel-sha256>.json
  revisions/<revision-id>/attempts/panel_plan/001/input.json
  revisions/<revision-id>/attempts/panel_plan/001/output.json
  revisions/<revision-id>/attempts/panel_plan/001/status.json
```

未传入 `project_store` 时只更新内存中的 Revision；交互服务默认使用仓库根目录下已忽略的 `store/`。

`layout_plan` 是 `STAGE_SEQUENCE` 的第一阶段。确认后写入 `approved_stages`，板件只读冻结布局中的可执行 CAD 单元。房间编辑器仍可经 `/api/room-scene/...` 读写 Project 里的房间草稿。

## 可执行 JSON

单位均为毫米；支持字段：

```json
{
  "furniture_category": "floor_cabinet", "width": 800, "depth": 600, "height": 2000,
  "board_thickness": 18, "back_thickness": 9, "door_thickness": 18,
  "toe_kick_height": 50, "back_offset": 18,
  "front_face_margin": 1.5, "front_gap": 2,
  "groove_depth": 6, "groove_clearance": 1,
  "toe_kick_reveal_front": 1, "toe_kick_reveal_back": 30,
  "toe_kick_support_count": 1, "back_mount": "groove", "back_rail_height": 70,
  "drawer_count": 0, "drawer_side_clearance": 13, "drawer_layer_gap": 1.5,
  "drawer_bottom_thickness": 18, "drawer_back_thickness": 18,
  "drawer_back_clearance": 0, "shelves": [{"shelf_type": "fixed", "gap_below_mm": 200}], "top_gap_mm": 200, "n_doors": 2, "door_hinge_side": null
}
```

`width/depth/height` 必须在意图确认前明确提供；不再用类别预设替代客户确认的外形尺寸。板件必填字段必须完整提交；料档字段（`board_thickness` / `back_thickness` / `door_thickness` / `drawer_bottom_thickness` / `drawer_back_thickness`）可省略，由车间工艺卡展开（柜体板 18、9 厘背板 9、门与抽屉盒同柜体板）。代码不按柜型静默补其他默认方案。完整值经确定性准入后才写入 `panel_plan.cabinets[].spec`。

契约为扁平 JSON。规范字段使用 `furniture_category/width/depth/height` 或 `rooms[]`；适配器把单件快捷写法展开成一间工作室房间 + 一个 CAD 单元，把板件规范字段路由到 `stage_inputs.panels`，把制造选项（含 `door_hinge_side`、`movable_shelf_connector`、`edge_banding`）和外观路由到 `stage_inputs.manufacturing`。扁平请求不接受历史名 `type`、`furniture_type`、`overall_size`、`hanging_height`、`mounting_height`、`mounting_height_mm`、`mount_mode`。吊柜离地用 `origin_z_mm` 或 `hanging_height_mm`，贴顶用 `hanging_mode=flush_ceiling`。可选 `constraints` 必须有阶段映射；未分类约束在协议路由时拒绝。扁平示例里的 `door_hinge_side` 是制造选项，不是板件规范字段。

`back_mount` 接受 `groove/insert/cover`，但不进入意图或布局输出。板件阶段不从板厚推断模式；`back_rail_height/groove_depth/groove_clearance` 仅对 `groove` 生效，`back_rail_height=0` 关闭背拉条。

仅总体尺寸为数值且变体匹配实时模板时执行；否则停在相应规划层并说明边界。

## API 契约

`server.py` 提供独立房间场景，以及只读的项目布局预览。房间场景请求体为 `room + items[]`；除 `GET` 外都是 JSON body。完整端点：

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| POST | `/api/plan-room` | 规划摆放，返回房间、包络、预览与 Viewer |
| POST | `/api/plan-room/preview` | 同上，只返回 SVG |
| POST | `/api/plan-room/viewer` | 同上，只返回 Viewer HTML |
| POST | `/api/plan-room/cad` | 同上，并追加房间包络 CAD（写 · 本机） |
| POST | `/api/room-scene/save` | 保存场景**源**，返回 `scene_id`（写 · 本机） |
| GET | `/api/room-scene/{scene_id}` | 读源并重算摆放/预览/Viewer |
| GET | `/api/room-scenes` | 列出已保存的 `scene_ids` |
| POST | `/api/room-scene/{scene_id}/edit` | 应用**一次**编辑 op（写 · 本机） |
| GET | `/api/room-scene/{scene_id}/editor` | 可编辑视图（自包含 HTML） |
| GET | `/api/project/{project_id}/layout` | 读项目最新布局：房间与已摆放包络 |
| POST | `/api/project/{project_id}/layout/edit` | 页面上改一件的摆放：工作副本原地改，否则落成新 Revision（写 · 本机 · 灰度） |
| POST | `/api/project/{project_id}/layout/undo` | 撤销工作副本上的最后 N 步（写 · 本机 · 灰度） |
| POST | `/api/project/{project_id}/edit-lease` | 申请 / 续租编辑权（写 · 本机） |
| DELETE | `/api/project/{project_id}/edit-lease` | 归还编辑权（写 · 本机） |
| POST | `/api/project/{project_id}/edit-lease/takeover` | 强制收回编辑权（写 · 本机） |
| GET | `/api/project/{project_id}/preview` | 只读布局页，按版本号自行刷新 |
| POST | `/api/preview/shutdown` | 本机请求后让预览服务干净退出（写 · 本机） |

另有 `GET /health` 与 `GET /`（Swagger 入口），不是场景契约的一部分。缺场景或项目返回 404，参数或校验不通过返回 422。`project_id` 只允许英文字母、数字、`-` 和 `_`。

写权限（`may_edit`）：**有副作用的端点只对本机来源开放**——停进程（`/api/preview/shutdown`）、保存场景（`/api/room-scene/save`）、编辑场景（`/api/room-scene/{scene_id}/edit`）、出房间 CAD（`/api/plan-room/cad`，会写源文件与 STEP）、改项目布局（`/api/project/{project_id}/layout/edit`）、编辑租约三个端点。非本机来源一律 403，且在动手之前就拒（不能先写一半再报错）。判据只有 `server.access_scope()` 一处，只看 `request.client.host`；**URL 参数不是权限**——`?mode=view` 这类只是页面表达，地址栏谁都能改，门必须在服务端。将来要给外人只读分享，在这一处多认一种凭证（新增 `shared` 来源），各端点不用动。读端点不受限（服务本来只监听 `127.0.0.1`）。外网分享的 token 形态与开门顺序见 [访问模式与外网分享](preview-access-design.md)。

**编辑租约（谁在写）**：写权限回答"这台机器上能不能写"，租约回答"**此刻轮到谁写**"。同一个项目的页面（拖动）与助手（对话）都能改，两边同时改就会互相覆盖——`expected_version` 只能事后发现（409），租约事前就分开。它落在 `<store>/<project-id>/edit-lease.json`（tmp + replace 原子写），**因为写者不在同一个进程里**：页面走 HTTP 服务进程、助手直接调 orchestrator，内存里的锁互相看不见。规矩三条：① `LEASE_TTL_SECONDS=45` 没续租就失效（页面每 5 秒心跳，助手每步续一次；关标签页、崩溃、断网都不用管）；② 被别人持有就是 `LeaseHeld`，**不静默接管**——人把活交给助手 = 授权让出，由 `handover_to_agent()` 显式转移并让页面显示「助手正在处理」，页面拿到的是 **423**（带 `holder` / `label` / `expires_in`）；③ `transfer()` 让人**随时抢得回来**（页面的「收回编辑权」按钮走 `/edit-lease/takeover`）——租约不是用来把主人关在门外的。写请求带 `X-Edit-Lease: <token>`；租约空闲或持在调用方手里才放行。状态码分工：**403** 不许写 · **409** 信息过期 · **422** 改动不合法 · **423** 编辑权在别人手里。

项目预览读 `store/<project-id>/project.json` 的最新 Revision，不写 `stage_outputs`，也不写 `generated/room-scenes/`。`layout` 返回 `revision_id`、`revision_number`、`layout_confirmed`、`version` 和每间房的已摆放包络，不含预览 HTML。`version` 是**内容版本**，不是修订号：它是 `layout_sha256:确认位`（如 `5d28c9b6…:0`），同一份布局换个修订号不会让它变，页面刷新靠它判断"要不要重画"。别把它当成给人看的版本号（给人看的是 `revision_number`），也别把 `revision_id` 编进去——那会让每次重读都像变了。`preview` 打开时带上当前第一间房，之后每秒再读 `layout`：`version` 没变不重画；变了且没有正在转视角或平移，就换上新包络并保持相机角度。多间房在页上按**药丸按钮**切换（只有一间房时整条藏掉），默认第一间；当前那间写进地址栏 `?room=<id>`，切房间时用 `history.replaceState` 跟着改，所以链接能分享、能复现。页眉挂一块**身份牌**（预览页「只读预览 · 由对话更新」，草稿页「草稿 · 不影响项目」）——一眼说清这一页能不能改、改了算不算数。预览页带 `?mode=view` 时出**分享形态**：牌子换「只读分享 · 链接可转发」（琥珀色），提示语改成"只看不改"，且**不生成「退出」按钮**（那按钮能停掉本机预览服务，不该给拿到链接的人）；写链接用 `project_preview.preview_url(id, mode="view")` 或 `open_project_preview(id, share=True)`。这一页不把拖动写回项目。页上的「退出」向 `POST /api/preview/shutdown` 发本机请求，服务发完响应后结束进程。只关浏览器标签不会停服务。项目文件仍留在 `store/`。非本机来源返回 403。

页面写项目（`POST /api/project/{project_id}/layout/edit`）：改**一件**家具的摆放，一次请求只改一处。body = `{op, item_id, expected_version, …op 字段}`；op 词表与字段白名单**复用房间场景编辑**（`scene_edit.apply_edit`，只有 `move` / `rotate` / `resize`），这里不另写一份判断。三道门按顺序，任何一道不过都**不落盘**：① 本机来源（`may_edit`）→ 403；② 灰度开关 `FURNITURE_PROJECT_LAYOUT_EDIT=1`（不设就是关，`true` / `yes` / 空一律当关）→ 403，理由里点名变量；③ `expected_version` 必须等于页面最近一次看到的 `version` → 不符回 409，detail 里带 `current_version`，页面刷新后重试。

成功之后落在哪里，取决于**这一版还没有下游产物**（工作副本，方案 H）：

- **还没有下游产物 → 原地改这一版**：`revision_number` 不变、`version`（内容摘要）变，改动进 `revision.working_ops`（记**改动前的旧值**，供撤销；**不是审计**）。改到哪一间，**那一间的确认作废**（移出 `approved_rooms`；因此不再"每间都审过"时，`layout.confirmed` 与 `approved_stages` 里的 `layout_plan` 一并撤回——不能让"已确认"挂在一份改过的内容上）。
- **已经有下游产物 → 追加新 Revision**：已经有东西依赖这一版，再改就不是同一版。新版从空日志开始（触发它的那次改动也记一条），父修订的 `stage_inputs` **原样带走**——摆放变了，柜体构造意图（门数、层板、背板安装…）没变，不带走会让下一次 `run_next()` 报 `panel proposal is incomplete`。
- 下游阶段一产出，工作副本就**关门**（`Revision.close_working_copy()`：清空日志 + 一条 `workflow` 事件）；页面牌子一直显示「草稿中 · 同一版 · 已调整 N 次」或「这一版已有下游产物：改动会落成新一版」，别让人以为版号变了。

撤销（`POST /api/project/{project_id}/layout/undo`，body `{expected_version, steps}`）：只在工作副本还开着时可用，**逐条恢复旧值**（失败整体拒绝），并留一条 `undo N step(s)` 事件——撤销会让"已经跟人说过"的内容变样，必须看得出来。窗口的边界是**下游产物**，不是时间：没有下游产物时随时可以撤，有了就不能（再往回走是"修订"的事：明确、留痕、下游跟着作废）。

响应就是 `GET /layout` 那份文档（含 `working: {open, ops, can_undo}`），页面可直接换上新包络。几何校验不过（越界、与别的件或障碍物干涉、遮挡门窗洞口）回 422，**什么都不改**。`fill` 件的宽与偏移由墙上的空段算出，所以拒绝摆放类 op（改了也会被重算覆盖，与其静默丢掉不如明说）。判断、取舍与尚未做的部分见 [页面写项目设计](project-layout-edit-design.md)。

页面能不能编辑由**服务端按权限渲染**：本机来源（`may_edit`）给可编辑页，其余给只读页；`?mode=view`（分享形态）在本机也强制只读。可编辑页还要自己拿到**编辑租约**才算真的能写（申请 / 5 秒心跳 / 闲置 5 分钟自动让出 / 离开页面归还）。

`/api/room-scene/save`、`/api/room-scene/{scene_id}`、`/api/room-scenes`、`/api/room-scene/{scene_id}/edit`、`/api/room-scene/{scene_id}/editor` 组成场景状态（供交互编辑）：只存源（房间定义 + 多件包络及其摆放请求），**不存派生结果**——摆放坐标、footprint、净距、预览都在读取时重算；存储独立于家具主流程，不写 `stage_outputs`。

编辑是**单 op、原子**：`move`（按当前 `mode` 二选一——`wall` 收 `host_wall`/`offset_mm`，`free` 收 `origin_x_mm`/`origin_y_mm`；**混给即拒**，换模式必须显式给 `mode` 并给出目标模式的坐标）、`rotate`（`rotation_z_deg`）、`resize`（`width`/`depth`/`height` 任意子集，至少一个）。每个 op 只接受自己的字段，白名单外即拒；**重算与校验通过才落盘**，失败整体拒绝，不留半成品。批量 op 留待多选拖动或场景级操作出现时再加。

`rotate` 只对 `free` 摆放有定义：`wall` 的原点与 `rotation_z_deg` 都由 `host_wall` 派生（见 `placement.py`），直接转会被拒。所以 rotate 可以带 `mode: "free"` + `origin_x_mm`/`origin_y_mm`，在**同一个 op 里**把墙摆改成自由摆放并给出绕中心旋转后的原点；带 `host_wall`/`offset_mm` 的 rotate 一律拒绝（否则 `rotation_z_deg: 0` 会伪装成一次沿墙移动）。

可编辑视图：`GET /api/room-scene/{scene_id}/editor` 返回自包含 HTML。**点包络任意位置**都能选中（命中判定用凸盒 6 个面投影的并集，外加 5px 容差，免得点描边穿透去转视角）。选中后家具上方出现两个手柄：**橙色圆点**拖了旋转（角度绕包络中心算，默认吸附 15°、按住 Shift 精细到 1°，`wall` 家具会在同一次 op 里转成 `free`），**蓝色圆点**拖了改**离地高度**（发 `origin_z_mm`，范围 0 到「层高 − 自身高」，同样按摆放检查求解）。选中件还会画一圈**旋转环**（15° 刻度 + 朝向指针），**整圈都是可抓区域**，拖动时就地显示当前角度——比去点一个小圆点好抓得多。拖动改位置：靠墙件沿墙滑动（发 `offset_mm`），往房间内拖过 26px 阈值就转成自由摆放（发 `mode: "free"` + 自由坐标）；自由件平面移动（发 `origin_x_mm`/`origin_y_mm`）。**只读的项目预览页不画这两个手柄，也不画旋转环**（保留"正面朝哪"的绿箭头与「前」）：只读时它们拖不动，画出来只会让人以为能拖。**4px 死区**——纯点击只选中、不发 op。空白处拖拽转视角，Esc 取消选中，PageUp/PageDown 按 50mm 调离地高度。

视角：工具栏一个**正视图下拉**（俯视 / 仰视 / 前视 / 后视 / 左视 / 右视）加一个**「复位」按钮**（回默认视角，同时把平移和缩放复位；内部预设名 `default_view`，旧的 `#view=perspective` 链接仍兼容——视角名与动作名分开，别把 reset 焊进预设名）。默认视角是**正南偏东 15°**（`yaw=5π/12`，北墙几乎正对、仍留一点纵深）、俯仰压低（`pitch=0.35` ≈ 20°，站在门口往里看的角度；再低就接近 `ELEVATION_MAX_PITCH=0.12`，会变成"平视/立面"）。独立房间 Viewer（`/api/plan-room/viewer`）用同一套控件与预设、同一组键名，也带同一套原点三轴（总宽/总深/总高）与光标坐标读数，只是它的取景距离按对角线固定倍数算、没有标注开关。仰视 `pitch=-1.48`，与俯视对称；俯视按平面图习惯**北在上、东在右**；四个立面 `pitch=0`，前视=站在南边往北看，东在右手边。相机不在任何正视图上时下拉显示**「自由视角」**（转过视角之后标识就变成它，不会还挂着上一个正视图）；平移和缩放不算离开正视图，只有绕竖轴的转动算。**双击画面**：自由/复位位时吸到最近的正视图（`|pitch| > 0.35` 取俯视/仰视，否则按方位角取最近的立面）；已经站在正视图上时，回到进它之前那一眼的自由视角。画面左右与真实方位一致：房间坐标系是 X 东 / Y 南 / Z 上，相机右向量取 `cross(up, forward)`；取反会让整幅画面左右镜像，转视角的符号也必须跟着翻。空白处拖拽转视角是**跟手**的：往右拖，画面里靠近你的那一侧就往右走（相机绕竖轴朝反方向转）；往下拖，近端往下走（相机抬高、更俯视）。相机接近水平（pitch < 0.12）时地面射线求交会退化，所以那种角度下拖动**在竖直平面里走**：横向 = 该视图的水平轴（由相机右向量决定正负号），纵向 = 高度。也就是在前/后视里上下拖就是改高度。**视图可以平移**：右键 / 中键拖动，或空白处 Shift+左键拖动（普通左键仍是转视角）。平移只改视图中心（相机的一切都相对它算），沿相机的右/上方向按屏幕像素换算成毫米，所以任何视角下都是「往哪拖、画面往哪走」且 1:1 跟手；它**不改** yaw/pitch/distance，也不发任何 op。切换视角时中心会一起动画回房间中心——取景也必须按房间中心算（`withHomeCentre`），否则平移过之后会把房间框到画外。整个切换带 500ms 插值过渡——只插值 `yaw`/`pitch`/`distance` 和视图中心，跑完即停，不留常驻动画循环，所以只有切换那一瞬间在重画；系统开了 `prefers-reduced-motion` 就直接跳到位。深链 `#view=front&item=desk` 可以直接打开某个视角并选中某件；`?room=<id>`（写成 `#room=<id>` 也认）直接打开某间房；三者叠在一条链接里也认，先落房间、再定视角、最后选中件。只改 `#` 后面的部分浏览器不重载页面，于是深链不会重新生效——要发深链就用整条新地址。

净距标注：选中件四周画出**到最近邻**的四向距离（同一高度带、垂直方向有重叠才算邻居，找不到才退到墙），数值画在图上、来源写在右侧栏（如「900 衣柜」）。同时沿选中件**自身的局部轴**画出本体尺寸：宽（局部 +X）、深（局部 +Y）、高（竖直），三条都从原点角出发，量的是 `width`/`depth`/`height` 本身——所以转了角度也跟着转，**不是量世界包围盒**。宽深两条朝包络内让开一段，免得和外圈净距线撞在一起。右侧栏另有尺寸/摆放/位置/朝向/离地/离顶。可用工具栏「标注」开关。**只读的项目预览页只显示这些读数，不生成输入框与 − / ＋ 按钮**（要改就去草稿页，或让助手改）；读数钩子挂在 `<span>` 上，值照旧刷新。

房间坐标：原点画在西北角地面，带 X（东）/ Y（南）/ Z（上）三根轴和 `O (0,0,0)`；三根轴就画在房间外侧，长度分别是房间的**总宽 / 总深 / 总高**，轴上直接标出这三个数（`X 东 · 总宽 3000` 这类）；正对相机被压成一点的那根不画。光标在画布上移动时，右下角显示落点的房间坐标（`X 1234 · Y 800 · Z 0 mm`）以及「距西墙 / 距北墙」的说法，落在房间外面会标出来；选中件的右侧栏另有一行同样的坐标。立面视图下地面射线求交会退化，读数自动隐藏（光标指到房间很远以外也一样）。预览页与编辑页共用这套画布，两边都有。

正面：每件家具的**正面**（局部 +Y 那一侧，见 `spatial-layout-rules.md`）描成绿色，墙脚再补一条绿线，所以正面背对相机时也看得出朝哪；选中件另外画一根指向正面的绿箭头，箭头外标「前」。右侧栏的朝向一行同时写出「前朝南/西南/…」（方向词按先东西后南北）。靠墙件的正面应当朝向室内，画出来就能一眼核对。

**净距、朝向、离地高度都能在右侧栏直接输入。** 输入走的是和拖动**同一套求解器**（`withDragContext` 临时装一个 drag 上下文复用 `applyLocalDrag`），所以到不了就只挪到能到的地方，并在状态栏按原因说明是越界、干涉还是遮挡门窗洞口——不会出现「输入能到、拖动不能到」。详情面板**按选中件重建一次**，之后一律 `applyDetailValues` 就地改值：正在打字的那个框不动，其余（含东距/西距这种此消彼长的）立刻跟着变。别改成「焦点在面板里就整块不刷新」——按钮拿到焦点后数字就不动了，这是个踩过的坑。

数值输入框一律 **`step="1"`**：原生上下微调按钮在 `step=10`、基准 0 时会把 192 吸附成 200（HTML 规范里 step up 的算法），既不是我们取整、也不省事——`setGap` 收的是整数毫米，直接输 202 本来就落 202。粗调交给旁边的 − / ＋ 按钮，各自走整数档：净距 10 · 离地 50 · 朝向 15。

拖动与旋转**在本地就按 `placement_check.py` 的同一套规则求解**（凸多边形 SAT，**底面正面积重叠且高度重叠才算干涉、贴边接触放行**；另查越出房间和遮挡门窗洞口）：过不去就**停在接触处**，不会先穿过去再等后端拒绝回弹。求解在**整数毫米**上进行——落盘本来就取整，所以**预览坐标就是落盘坐标**。旋转会扫出墙体时按最小位移收回房间，改完仍干涉邻居或遮挡洞口的那一帧不落地（停在上一格）并在状态栏说明原因。松手才发一个 op，后端仍是权威，拒绝时显示原因并**回退到服务端状态**（所见即真实）。

界面：画布按设备像素比放大，线更锐利；相机按房间自动取景（二分出装得下整个房间的距离）。透视下只画远端两面墙，免得近墙在家具前盖一层灰罩；立面视图下改画正对相机的那几面墙，房间才立得起来。近端/侧向的门窗画成墙脚粗虚线加「门/窗」标注。

⚠️ 编辑器把 SAT 判定在 JS 里镜像了一份（`polygonsOverlap`、`blockerAt`）。**改 `placement_check.py` 的判定必须同步改编辑器**，否则本地预览会与服务端校验不一致（预览放行、落盘被拒）。

家具生成不走 HTTP 批处理，只走 [交互工具面](agent-tool-contract.md)。

## 生成

交互确认后的 CAD 写入 `generated/<project-id>/revision-<n>/`（或调用时给出的 `output_root`）：

- `<artifact-name>.layout-plan.json`
- `<artifact-name>.panel-plan.json`
- `<artifact-name>.manufacture-plan.json`
- `<artifact-name>.feature-tree.json`
- `<artifact-name>.bom.md`
- `<artifact-name>.drilled-holes.json`
- `<artifact-name>.drilled-holes.glb`
- `<artifact-name>.drilled-holes.step`
- `<artifact-name>.drilled-holes.step.glb`
- `六面钻文件/<panel-label>.xml`
- `<artifact-name>.step`
- `temp/cad-source/<artifact-name>/__cadgen__/models/<artifact-name>.step.py/assembly.json`
- 同一 Viewer 组件包内由 `assembly.json` 引用的 `components/*.glb`

build123d 入口源码以 `<artifact-name>.step.py`（交互模式为 `model.step.py`）只写入 `temp/cad-source/<artifact-name>/`。CAD Bridge 按子模块 `external/text-to-cad/VERSION` 所指的 text-to-cad / cadgen 版本，用项目 `.venv` 直接运行该模型：`python <source.py> --json`（可加 `--force`），不调用已删除的 `skills/cad/scripts/gen`，也不把 `external/text-to-cad` 源码插到 `PYTHONPATH`。STEP 按模型 `@step(out=...)` 写入交付目录；Viewer 视图从 cadgen store 导出到源码旁 `__cadgen__/models/<source>/assembly.json`。交互 Project/Revision 写 `<output-root>/<project-id>/revision-<n>/`。`workflow_artifact_writer.py` 写快照，`workflow_store.py` 将 Project/Revision、`stage_outputs`、`approved_stages` 存为 `project.json`。环境安装见 [开发环境](../../../../.agents/skills/furniture-agent/references/dev-environment.md)。

运行时流水线为：

`Agent tools -> FurnitureOrchestrator -> 房间布局 -> 板件 -> 制造/BOM -> 特征树 -> CAD Bridge -> STEP + Viewer 组件包 -> 交付验证`

Feature Tree v2 支持板件 `box` 和定向 `cut_box`；发射器先建板、再切削、最后装配加工后的板件。

不得将家具 JSON 直发 text-to-cad、用一次性 CAD 源码绕过规划器或修改外部子模块。

## 运行时板件与 BOM 路径

- `furniture_layout/pipeline.py::plan_project_layout()`：计算多房间定位、摆放检查和预览，产出可执行 CAD 单元；`generate_room_cad()` 发射房屋与包络 CAD。
- `furniture_panel_planning/panel_pipeline.py::plan_panel_stage()`：从已确认 CAD 单元投影出的柜体外形尺寸物化功能数量、结构规格、精确净空、背板方案，并生成实体板件角色、尺寸和位置。
- `furniture_manufacturing/manufacturing_bom.py::plan_manufacturing()`：材料、封边、五金、BOM、槽；`emit_drilled_holes()` 输出配合孔。

`cabinet_pipeline.py::CabinetPipelineResult` 只是已确认板件+制造结果的快照，供 CAD 写入使用。Orchestrator 按阶段调用各 Skill，不合并检查点。

**继承不变式**：下游只依赖布局可执行单元的那五个字段（`id` / `furniture_category` / `width` / `depth` / `height`）。这五个字段不变时，板件、制造、特征树的内容**逐字节不变**，因此内容相同的下游产物可以**跨 Revision 继承**，不必让人重新确认（`approved_stages` 的语义是"这份内容已被确认过"，不是"人在这一版又点了头"）。机制、判据、必重算清单与 `fill` 例外见 [修订继承设计](revision-inheritance-design.md)。

继承怎么落地（已实现）：判据与证据在 `furniture_workflow/workflow_inheritance.py`，承认发生在 `workflow_stage_runner._inherit_settled_stage()`——阶段产出落定后，若**更早的某个 Revision 上该阶段已确认、且确认的内容摘要与本版逐字节相同**，就把本阶段就地记为已确认，并在 `Revision.inherited[阶段] = {sha256, from_revision, from_stage}` 留痕、追一条 `workflow` 事件。`Revision.approved_digests[阶段]` 记的是"人当年点的哪份内容"（`confirm_stage()` 写入，板件另有历史字段 `confirmed_panel_sha256`，下游按它读冻结板件）。两条边界：**只在逐字节相同时继承**（不近似、不容差，哈希不同就重算）；**判据只用来解释、不用来跳过重算**——`envelope_diff()` 给出 `same/added/removed/resized/recategorized` 供人看，是否继承由内容摘要比对决定，免得把隐藏依赖的风险引进来。快照与页面文档都带 `inherited` / `inherited_stages`，别让"少做了一步"变得看不见。

CAD 阶段可持久化 BOM Markdown，不生成裁切清单；未创建时不得报告裁切清单。
