# 空间布局规则

回答“这些家具在房间里怎么放、是否越界或碰撞，以及房间 CAD 包络长什么样？”  
独立按需能力，不位于家具生成串联阶段内，不生成板件或柜体 STEP。

## 坐标约定

- 默认毫米。件局部 `W×D×H` 对应 X 左→右、Y 后→前、Z 向上。
- 件局部原点 `(0,0,0)` 为外包络左后下落地角。
- 房间原点是平面图西北角的地面点；房间 X 向东、Y 向南、Z 向上。
- `placement` 将局部原点转换到房间坐标；`rotation_z_deg` 从房间 X 轴逆时针计算。

## 输入

必须提供：

- `room`：`id`、`width_mm`/`depth_mm`/`height_mm`（矩形），可选 `name`、`openings[]`、`obstacles[]`。
- `items[]`：每件 `id`、`category`、`width`/`depth`/`height`、`placement`。缺一则失败，不猜默认卧室，不猜默认家具。

沿墙偏移按房间边界顺时针：

- `north`：西 → 东
- `east`：北 → 南
- `south`：东 → 西
- `west`：南 → 北

`placement.mode=wall` 使用 `host_wall + offset_mm + origin_z_mm`，可选 `fill`。背面贴墙、正面朝向室内。墙摆的原点与 `rotation_z_deg` 都由 `host_wall` 派生，不接受自由坐标，也转不动——要旋转或要离开墙面，就改成 `mode=free`。  
`placement.mode=free` 使用 `origin_x_mm/origin_y_mm/origin_z_mm + rotation_z_deg`。

`fill=true` 仅用于 `mode=wall`。代码用该墙净长（扣除与该件高度相交的门窗、贴墙障碍、已摆家具）写入沿墙 `width` 和 `offset_mm`。未给 `offset_mm` 时取最长空段；给了则从该偏移铺到该空段终点。客户同时给了 width 与 fill 时，以墙净长为准。

## 拒绝条件

- 件越出房间或超过层高
- 与障碍物或另一件家具正体积相交
- 沿宿主墙遮挡垂直范围相交的门窗

边界接触不视为碰撞。缺房间尺寸、缺 `items`、fill 没有空段，均失败。

## 输出

- `room`：标准化房间、门窗、障碍物
- `items[]`：已解析 placement、footprint、六向净距；fill 后的 width 为沿墙实宽
- `preview`：透视 SVG，房间透明，家具为不透明包络
- `viewer`：自包含互动 HTML
- `cad`：仅请求生成时出现，含 cadgen 源码、STEP、Viewer 路径

预览、Viewer、CAD 必须由当前房间和全部包络实时重建。

## 房间 CAD

房屋：地面薄板 + 四面墙薄板（墙厚 100 mm）。门窗为墙上 `cut_box`。障碍物与每件家具为外包络盒，带原点与 `rotation_z_deg`。房间不做成封闭实心体。

源码：`temp/cad-source/layout-<id>/model.step.py`  
STEP：`generated/layout/<id>/room.step`

这不是家具主流程的 `cad_generated`。不要调用 `furniture_run_next(..., generate_cad=True)`，也不要直调 `CadBridge`。

## 边界

- 不定义板件、封边、钻孔、五金、特征树或柜体 STEP。
- 房间坐标不混入板件尺寸。
- 结果不写入 `STAGE_SEQUENCE`、`approved_stages` 或家具 CAD 交付清单。
