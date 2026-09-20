# 空间布局规则

回答“这些家具在房间里怎么放、是否越界或碰撞，以及房间 CAD 包络长什么样？”  
家具流水线第一阶段。回答房间里家具怎么摆；可执行柜体作为 CAD 单元交给板件。不生成柜体板件或柜体 STEP。

人给摆放意图，代码换毫米并做碰撞准入；模块入口与两条产品线见 [运行时映射](runtime-map.md)。

## 坐标约定

- 默认毫米。件局部 `W×D×H` 对应 X 左→右、Y 后→前、Z 向上。
- 件局部原点 `(0,0,0)` 为外包络左后下落地角。
- 房间原点是平面图西北角的地面点；房间 X 向东、Y 向南、Z 向上。
- `placement` 将局部原点转换到房间坐标；`rotation_z_deg` 从房间 X 轴逆时针计算。
- **正面 = 局部 +Y 那一侧**（原点在左后下角，所以 `y=depth` 那条边是正面）。靠墙件「背面贴墙、正面朝室内」说的就是这条。可编辑视图把正面描成绿边，并在选中件上画一根指向正面的箭头。

## 输入

必须提供：

- `room`：`id`、`width_mm`/`depth_mm`/`height_mm`（矩形），可选 `name`、`openings[]`、`obstacles[]`。`openings[]` 是墙上的房间门洞/窗洞（`kind=door|window`），用来挡柜、扣 fill 空段；不是柜门 `n_doors`。
- `items[]`：每件 `id`、`category`、`depth`/`height`、`placement`；固定宽度的件还要给 `width`，`fill=true` 可省略 `width`。不猜默认卧室，不猜默认家具。

沿墙偏移按房间边界顺时针：

- `north`：西 → 东
- `east`：北 → 南
- `south`：东 → 西
- `west`：南 → 北

`placement.mode=wall` 使用 `host_wall + offset_mm + origin_z_mm`，可选 `fill`。背面贴墙、正面朝向室内。墙摆的原点与 `rotation_z_deg` 都由 `host_wall` 派生，不接受自由坐标，也转不动——要旋转或要离开墙面，就改成 `mode=free`。  
`placement.mode=free` 使用 `origin_x_mm/origin_y_mm/origin_z_mm + rotation_z_deg`。

`fill=true` 仅用于 `mode=wall`。无需提供 `width`；代码用该墙净长（扣除与该件高度相交的门窗、贴墙障碍、已摆家具）写入沿墙 `width` 和 `offset_mm`。未给 `offset_mm` 时取最长空段；给了则从该偏移铺到该空段终点。客户同时给了 width 与 fill 时，以墙净长为准。

## 拒绝条件

- 件越出房间或超过层高
- 与障碍物或另一件家具正体积相交
- 沿宿主墙遮挡垂直范围相交的门窗

边界接触不视为碰撞——可编辑视图的拖动也按同一条规则求解，撞上就停在接触处（JS 侧镜像的判定在 `editor.py`，改这里要同步改它）。项目布局在创建待确认 Revision 前校验；缺房间尺寸或 fill 没有空段均失败。独立房间场景接口还要求非空 `items[]`。

## 输出

- 项目布局：`rooms[]` 中每间房含标准化 `room`、已解析的 `items[]`，有家具时还含 `preview`（透视 SVG）和 `viewer`（互动 HTML）；顶层 `cad.units` 是可执行柜体包络，不是 STEP。
- 独立房间场景：直接返回 `room`、`items[]`、`preview`、`viewer`；请求生成房间 CAD 时另有 `cad`，含源码、STEP 和 Viewer 路径。
- `items[]` 中有 placement、footprint 和六向净距；fill 后的 width 为沿墙实宽。

预览、Viewer 和房间 CAD 必须由当前房间和全部包络重建。

## 房间 CAD

房屋：地面薄板 + 四面墙薄板（墙厚 100 mm）。门窗为墙上 `cut_box`。障碍物与每件家具为外包络盒，带原点与 `rotation_z_deg`。房间不做成封闭实心体。

- 源码：`temp/cad-source/layout-<artifact-name>/model.step.py`
- STEP：`generated/layout/<artifact-name>/room.step`

显式 `artifact_id` 仅允许英文字母、数字、`-` 和 `_`；非法值在创建目录或写文件前失败。未提供时，安全的房间 `id` 原样作为 `artifact-name`，否则由房间 `id` 的 SHA-256 生成稳定的 `room-<16 位十六进制>` 名称。所有源码和 STEP 路径在写入前都必须确认仍位于各自的输出根目录内。

这不是家具主流程的 `cad_generated`。不要调用 `furniture_run_next(..., generate_cad=True)`，也不要直调 `CadBridge`。

## 边界

- 不定义板件、封边、钻孔、五金、特征树或柜体 STEP。
- 房间坐标不混入板件尺寸。
- 项目布局写入 `stage_outputs["layout_plan"]`；`layout_plan` 是 `STAGE_SEQUENCE` 的首阶段，确认后进入 `approved_stages`，可执行柜体作为下游 CAD 单元。独立房间场景的预览和房间 CAD 不进入项目阶段输出或家具 CAD 交付清单。
