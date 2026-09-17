# 家具运行时契约

改编排、产物路径、扁平协议或 store 布局时读本文。做家具或改某一阶段规则时不要读；用当前阶段 Skill。这里只定义运行时契约、命令、路径和限制。

## 当前能力

唯一应用层入口：`domain/skills/cad-generated/scripts/furniture_workflow/workflow_orchestrator.py`。它接受已规划的全屋 `layout_plan`（按房间组织的家具包络 CAD 单元）。板件/制造字段经 `create_project(..., stage_inputs=)` 或 `run_next`/`retry_stage` 的 `stage_input` 进入所属阶段。字段转换、阶段实现和校验归各 Skill，Orchestrator 只管理生命周期。没有一次性自动确认的批处理入口。

- `floor_cabinet`：固定模板，含背板、踢脚板、层板、门板。
- `wall_cabinet`：固定模板，含背板、层板、门板，无踢脚板。
- 均支持显式 `groove/insert/cover`。

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

`width/depth/height` 必须在意图确认前明确提供；不再用类别预设替代客户确认的外包络。板件必填字段必须完整提交；料档字段（`board_thickness` / `back_thickness` / `door_thickness` / `drawer_bottom_thickness` / `drawer_back_thickness`）可省略，由车间工艺卡展开（料板 18、卷后背板 9、门与抽屉盒同料板）。代码不按柜型静默补其他默认方案。完整值经确定性准入后才写入 `panel_plan.cabinets[].spec`。

契约为扁平 JSON。规范字段使用 `furniture_category/width/depth/height` 或 `rooms[]`；适配器把单件快捷写法展开成一间工作室房间 + 一个 CAD 单元，把板件规范字段路由到 `stage_inputs.panels`，把制造选项（含 `door_hinge_side`、`movable_shelf_connector`、`edge_banding`）和外观路由到 `stage_inputs.manufacturing`。扁平请求不再接受历史 `type`，该字段仅在旧序列化 spec 加载时恢复。历史 `furniture_type`/`overall_size`/`mounting_height` 仍可映射到规范名。可选 `constraints` 必须有阶段映射；未分类约束在协议路由时拒绝。扁平示例里的 `door_hinge_side` 是制造选项，不是板件规范字段。

`back_mount` 接受 `groove/insert/cover`，但不进入意图或布局输出。板件阶段不从板厚推断模式；`back_rail_height/groove_depth/groove_clearance` 仅对 `groove` 生效，`back_rail_height=0` 关闭背拉条。

仅总体尺寸为数值且变体匹配实时模板时执行；否则停在相应规划层并说明边界。

## API 契约

`server.py` 只提供独立房间场景：`POST /api/plan-room`、`/api/plan-room/preview`、`/api/plan-room/viewer`、`/api/plan-room/cad`。请求体为 `room + items[]`。

场景状态（供交互编辑）：`POST /api/room-scene/save` 保存场景的**源**（房间定义 + 多件包络及其摆放请求），`GET /api/room-scene/{scene_id}` 读取源并重算摆放/预览/Viewer，`GET /api/room-scenes` 列出已保存场景，`POST /api/room-scene/{scene_id}/edit` 应用**一次**编辑。只存源、**不存派生结果**（摆放坐标、footprint、净距、预览都在读取时重算）；存储独立于家具主流程，不写 `stage_outputs`。

编辑是**单 op、原子**：`move`（按当前 `mode` 二选一——`wall` 收 `host_wall`/`offset_mm`，`free` 收 `origin_x_mm`/`origin_y_mm`；**混给即拒**，换模式必须显式给 `mode` 并给出目标模式的坐标）、`rotate`（`rotation_z_deg`）、`resize`（`width`/`depth`/`height` 任意子集，至少一个）。每个 op 只接受自己的字段，白名单外即拒；**重算与校验通过才落盘**，失败整体拒绝，不留半成品。批量 op 留待多选拖动或场景级操作出现时再加。

`rotate` 只对 `free` 摆放有定义：`wall` 的原点与 `rotation_z_deg` 都由 `host_wall` 派生（见 `placement.py`），直接转会被拒。所以 rotate 可以带 `mode: "free"` + `origin_x_mm`/`origin_y_mm`，在**同一个 op 里**把墙摆改成自由摆放并给出绕中心旋转后的原点；带 `host_wall`/`offset_mm` 的 rotate 一律拒绝（否则 `rotation_z_deg: 0` 会伪装成一次沿墙移动）。

可编辑视图：`GET /api/room-scene/{scene_id}/editor` 返回自包含 HTML。**点包络任意位置**都能选中（命中判定用凸盒 6 个面投影的并集，外加 5px 容差，免得点描边穿透去转视角）。选中后家具上方出现两个手柄：**橙色圆点**拖了旋转（角度绕包络中心算，默认吸附 15°、按住 Shift 精细到 1°，`wall` 家具会在同一次 op 里转成 `free`），**蓝色圆点**拖了改**离地高度**（发 `origin_z_mm`，范围 0 到「层高 − 自身高」，同样按碰撞求解）。选中件还会画一圈**旋转环**（15° 刻度 + 朝向指针），**整圈都是可抓区域**，拖动时就地显示当前角度——比去点一个小圆点好抓得多。拖动改位置：靠墙件沿墙滑动（发 `offset_mm`），往房间内拖过 26px 阈值就转成自由摆放（发 `mode: "free"` + 自由坐标）；自由件平面移动（发 `origin_x_mm`/`origin_y_mm`）。**4px 死区**——纯点击只选中、不发 op。空白处拖拽转视角，Esc 取消选中，PageUp/PageDown 按 50mm 调离地高度。

视角：透视、俯视，以及**前/后/左/右四个立面**（相机 pitch=0，前视=站在南边往北看）。相机接近水平（pitch < 0.12）时地面射线求交会退化，所以那种角度下拖动**在竖直平面里走**：横向 = 该视图的水平轴（由相机右向量决定正负号），纵向 = 高度。也就是在前/后视里上下拖就是改高度。**视图可以平移**：右键 / 中键拖动，或空白处 Shift+左键拖动（普通左键仍是转视角）。平移只改视图中心（相机的一切都相对它算），沿相机的右/上方向按屏幕像素换算成毫米，所以任何视角下都是「往哪拖、画面往哪走」且 1:1 跟手；它**不改** yaw/pitch/distance，也不发任何 op。切换视角时中心会一起动画回房间中心——取景也必须按房间中心算（`withHomeCentre`），否则平移过之后会把房间框到画外。整个切换带 500ms 插值过渡——只插值 `yaw`/`pitch`/`distance` 和视图中心，跑完即停，不留常驻动画循环，所以只有切换那一瞬间在重画；系统开了 `prefers-reduced-motion` 就直接跳到位。深链 `#view=front&item=desk` 可以直接打开某个视角并选中某件。

净距标注：选中件四周画出**到最近邻**的四向距离（同一高度带、垂直方向有重叠才算邻居，找不到才退到墙），数值画在图上、来源写在右侧栏（如「900 衣柜」）。同时沿选中件**自身的局部轴**画出本体尺寸：宽（局部 +X）、深（局部 +Y）、高（竖直），三条都从原点角出发，量的是 `width`/`depth`/`height` 本身——所以转了角度也跟着转，**不是量世界包围盒**。宽深两条朝包络内让开一段，免得和外圈净距线撞在一起。右侧栏另有尺寸/摆放/位置/朝向/离地/离顶。可用工具栏「标注」开关。

正面：每件家具的**正面**（局部 +Y 那一侧，见 `spatial-layout-rules.md`）描成绿色，墙脚再补一条绿线，所以正面背对相机时也看得出朝哪；选中件另外画一根指向正面的绿箭头，箭头外标「前」。右侧栏的朝向一行同时写出「前朝南/西南/…」（方向词按先东西后南北）。靠墙件的正面应当朝向室内，画出来就能一眼核对。

**净距、朝向、离地高度都能在右侧栏直接输入。** 输入走的是和拖动**同一套求解器**（`withDragContext` 临时装一个 drag 上下文复用 `applyLocalDrag`），所以到不了就只挪到能到的地方，并在状态栏说明被谁挡住——不会出现「输入能到、拖动不能到」。详情面板**按选中件重建一次**，之后一律 `applyDetailValues` 就地改值：正在打字的那个框不动，其余（含东距/西距这种此消彼长的）立刻跟着变。别改成「焦点在面板里就整块不刷新」——按钮拿到焦点后数字就不动了，这是个踩过的坑。

数值输入框一律 **`step="1"`**：原生上下微调按钮在 `step=10`、基准 0 时会把 192 吸附成 200（HTML 规范里 step up 的算法），既不是我们取整、也不省事——`setGap` 收的是整数毫米，直接输 202 本来就落 202。粗调交给旁边的 − / ＋ 按钮，各自走整数档：净距 10 · 离地 50 · 朝向 15。

拖动与旋转**在本地就按 `collision.py` 的同一套规则求解**（凸多边形 SAT，**正体积相交才算撞、贴边接触放行**；另加房间边界、障碍物、其他家具、门窗跨度）：撞上就**停在接触处**，不会先穿过去再等后端拒绝回弹。求解在**整数毫米**上进行——落盘本来就取整，所以**预览坐标就是落盘坐标**，不会出现「预览没撞、取整后撞上」。旋转会扫出墙体时按最小位移收回房间，改完仍撞着邻居的那一帧不落地（停在上一格）并在状态栏说明原因。松手才发一个 op，后端仍是权威，拒绝时显示原因并**回退到服务端状态**（所见即真实）。

界面：画布按设备像素比放大，线更锐利；相机按房间自动取景（二分出装得下整个房间的距离）。透视下只画远端两面墙，免得近墙在家具前盖一层灰罩；立面视图下改画正对相机的那几面墙，房间才立得起来。近端/侧向的门窗画成墙脚粗虚线加「门/窗」标注。

⚠️ 编辑器把 SAT 判定在 JS 里镜像了一份（`polygonsOverlap`、`blockerAt`）。**改 `collision.py` 的判定必须同步改编辑器**，否则本地预览会与服务端校验不一致（预览放行、落盘被拒）。

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

build123d 入口源码以 `<artifact-name>.step.py`（交互模式为 `model.step.py`）只写入 `temp/cad-source/<artifact-name>/`。CAD Bridge 按 text-to-cad / cadgen 0.6.3 用项目 `.venv` 直接运行该模型：`python <source.py> --json`（可加 `--force`），不调用已删除的 `skills/cad/scripts/gen`，也不把 `external/text-to-cad` 源码插到 `PYTHONPATH`。STEP 按模型 `@step(out=...)` 写入交付目录；Viewer 视图从 cadgen store 导出到源码旁 `__cadgen__/models/<source>/assembly.json`。交互 Project/Revision 写 `<output-root>/<project-id>/revision-<n>/`。`workflow_artifact_writer.py` 写快照，`workflow_store.py` 将 Project/Revision、`stage_outputs`、`approved_stages` 存为 `project.json`。环境安装见 [开发环境](../../../../.agents/skills/furniture-agent/references/dev-environment.md)。

运行时流水线为：

`Agent tools -> FurnitureOrchestrator -> 房间布局 -> 板件 -> 制造/BOM -> 特征树 -> CAD Bridge -> STEP + Viewer 组件包 -> 交付验证`

Feature Tree v2 支持板件 `box` 和定向 `cut_box`；发射器先建板、再切削、最后装配加工后的板件。

不得将家具 JSON 直发 text-to-cad、用一次性 CAD 源码绕过规划器或修改外部子模块。

## 运行时板件与 BOM 路径

- `furniture_layout/pipeline.py::plan_project_layout()`：计算多房间定位、碰撞和预览，产出可执行 CAD 单元；`generate_room_cad()` 发射房屋与包络 CAD。
- `furniture_panel_planning/panel_pipeline.py::plan_panel_stage()`：从已确认布局的可执行单元物化功能数量、结构规格、精确净空、背板方案，并生成实体板件角色、尺寸和位置。
- `furniture_manufacturing/manufacturing_bom.py::plan_manufacturing()`：材料、封边、五金、BOM、槽；`emit_drilled_holes()` 输出配合孔。

`cabinet_pipeline.py::CabinetPipelineResult` 只是已确认板件+制造结果的快照，供 CAD 写入使用。Orchestrator 按阶段调用各 Skill，不合并检查点。

CAD 阶段可持久化 BOM Markdown，不生成裁切清单；未创建时不得报告裁切清单。
