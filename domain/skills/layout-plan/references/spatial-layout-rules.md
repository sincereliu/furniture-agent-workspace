# 空间布局规则

回答“这些家具在房间里怎么放、是否越界、干涉或遮挡门窗洞口，以及房间 CAD 包络长什么样？”  
家具流水线第一阶段。回答房间里家具怎么摆；可执行柜体作为 CAD 单元交给板件。不生成柜体板件或柜体 STEP。

人给摆放意图，代码换毫米并做摆放检查；各文件干什么见 [运行时映射](runtime-map.md)。

## 坐标约定

- 默认毫米。件局部 `W×D×H` 对应 X 宽方向、Y 深方向、Z 向上。
- 件局部原点 `(0,0,0)` 为外形尺寸的左后下角。“左后下”是局部坐标的固定名称，不随观察视角变化；吊柜的这个角也可以离地。
- 房间原点是平面图西北角的地面点；房间 X 向东、Y 向南、Z 向上。
- **正面 = 局部 `Y=D` 那一侧，朝向局部 +Y；背面 = 局部 `Y=0` 那一侧。** 靠墙件的背面贴墙、正面朝室内。预览用绿线标识正面。

### 原点和足迹点序

包络盒子没有天然的原点、左右或正面。系统通过外形尺寸、局部点序和 `placement` 指定它们，不从画面外观识别。局部包络占据 `[0,W] × [0,D] × [0,H]`，底面四点固定为：

| 点 | 局部坐标 | 含义 |
| --- | --- | --- |
| P0 | `(0,0,0)` | 局部原点，后侧起点 |
| P1 | `(W,0,0)` | 沿局部 +X 的底角 |
| P2 | `(W,D,0)` | 底面对角 |
| P3 | `(0,D,0)` | 沿局部 +Y 的底角 |

`P0→P1` 是宽边，`P0→P3` 是深边，`P0→P1` 所在的 `Y=0` 一侧是背面，`P3→P2` 所在的 `Y=D` 一侧是正面。每个底角沿局部 +Z 移动 H 得到对应顶角。

输出 `footprint` 是这四点变换后的**房间平面坐标**，仍按 `[P0,P1,P2,P3]` 排列；点内的 `x_mm/y_mm` 是房间 X/Y。底面高度统一为 `placement.origin_z_mm`，顶面高度为 `origin_z_mm + height`。房间轴和家具局部轴分别命名，不把旋转后的房间 X 跨度当作家具宽度。

生成、序列化、读取和预览应保留点序，不按房间坐标大小重排，也不把包围框的最小角重新认作 P0。正方形或立方体也保留这个约定：同一占用空间可以具有不同的局部原点和正面，不能凭形状或宽深相等消除其朝向信息。

### 局部坐标到房间坐标

`placement.origin_x_mm/origin_y_mm/origin_z_mm` 是家具局部原点在房间中的位置，不是家具中心。`rotation_z_deg` 是局部 +X 相对房间 +X 的转角；正方向从房间 +X 转向房间 +Y。0° 时局部 +X 向东、+Y 向南；90° 时局部 +X 向南、+Y 向西。屏幕坐标的 Y 向下，因此不以画面的顺/逆时针定义这个转角。

令局部点为 `(x_local,y_local,z_local)`，原点位置为 `(ox,oy,oz)`，θ 为 `rotation_z_deg` 换成弧度后的值，变换固定为：

```text
x_room = ox + x_local × cosθ − y_local × sinθ
y_room = oy + x_local × sinθ + y_local × cosθ
z_room = oz + z_local
```

例如 `W=1200,D=500,H=1700`，原点在房间 `(1000,800,300)`，转角 90°，房间中的底角依次为 `(1000,800,300)`、`(1000,2000,300)`、`(500,2000,300)`、`(500,800,300)`；正面在房间西侧，顶部高度为 2000 mm。

靠墙摆放先把宿主墙和贴合起点换成同一份原点和转角，再使用上面的变换。设房间总宽、总深为 `RW/RD`，贴合起点为 s（由包络贴合算出，不是输入）：

| 宿主墙 | 房间原点 X/Y | 转角 | 正面朝向 |
| --- | --- | --- | --- |
| north | `(s,0)` | 0° | 南 / 房间 +Y |
| east | `(RW,s)` | 90° | 西 / 房间 −X |
| south | `(RW−s,RD)` | 180° | 北 / 房间 −Y |
| west | `(0,RD−s)` | 270° | 东 / 房间 +X |

原点高度仍由 `origin_z_mm` 给出。屏幕投影和 Three.js 的 Y 向上约定属于预览层，只通过 `roomToThree/threeToRoom` 转换，不改变家具的局部原点、点序或正面。

## 输入

必须提供：

- `room`：`id`、`width_mm`/`depth_mm`/`height_mm`（矩形），可选 `name`、`openings[]`、`obstacles[]`。`openings[]` 是墙上的房间门洞/窗洞（`kind=door|window`），用来挡柜、扣 fill 空段；不是柜门 `n_doors`。
- `items[]`：每件 `id`、`category`、`depth`/`height`、`placement`；固定宽度的件还要给 `width`，`fill=true` 可省略 `width`。不猜默认卧室，不猜默认家具。
  **`id` 的形状有要求**：必须是合法 Python 标识符（字母/数字/下划线，不能以数字开头）、且不含 `__`——板件阶段拿它拼板件编号（`{cabinet_id}__{role}`）。`cabinet-1`、`1cabinet`、`a__b` 这类 id **在布局入口就被拒**（`scene.parse_item_specs`），不会等到板件阶段才炸；省略时自动补 `item_<序号>`。房间 `id` 不受这条约束（它只进 URL 与房间级确认）。

结构化接口只接受这里列出的规范字段和精确枚举，未知字段直接拒绝。房间、门窗和障碍物尺寸带 `_mm`；家具尺寸用 `width/depth/height`。`placement.mode` 必须明确提供，不从 `host_wall` 或坐标猜测。门窗 `kind` 必须为 `door` 或 `window`。数值必须有限，`fill` 和 `manufacture` 必须是布尔值。历史字段名不再转换。

沿墙方向按房间边界顺时针。门窗的 `offset_mm` 用这个方向；靠墙包络贴合后的起点也用这个方向：

- `north`：西 → 东
- `east`：北 → 南
- `south`：东 → 西
- `west`：南 → 北

`placement.mode=wall` 使用 `host_wall + origin_z_mm`，可选 `fill` 和 `against`。背面贴墙、正面朝向室内。墙摆的原点与 `rotation_z_deg` 都由 `host_wall` 和贴合结果派生，不接受自由坐标，也不接受沿墙偏移，也转不动——要旋转或要离开墙面，就改成 `mode=free`。从自由摆放改回靠墙时，原来的转角不进入下一次计算，朝向仍由宿主墙决定，沿墙位置重新贴合。  
`placement.mode=free` 使用 `origin_x_mm/origin_y_mm/origin_z_mm + rotation_z_deg`。自由摆不写 `against`。

`placement.against` 写靠墙柜子沿墙的两头。方向用 `east` / `south` / `west` / `north`，每一头的目标显式区分墙和家具：

```json
{"against": {"west": {"kind": "wall"}, "east": {"kind": "item", "id": "cabinet_b"}}}
```

- `{kind: wall}`：这一头贴到侧面那面墙，只允许 `kind` 字段。
- `{kind: item, id: cabinet_b}`：这一头贴着指定家具，必须有合法家具 `id`，只允许 `kind` 和 `id` 字段。家具可以叫 `wall`，用 `{kind: item, id: wall}` 引用。
- 输入、已摆放输出、`to_source()` 和编辑请求都使用显式对象。字符串目标直接拒绝，包括读取保存的布局；不转换旧格式。
- 缺失或未知 `kind`、缺失或非法家具 `id`、目标上的额外字段直接拒绝。方向值为 `null` 表示未声明这一头。

LLM 负责选择贴墙还是贴哪件家具，运行时只验证显式目标并计算坐标。背面仍由 `host_wall` 表示，所以每面墙只许写它的两头：北墙 `west`/`east`，东墙 `north`/`south`，南墙 `east`/`west`，西墙 `south`/`north`。

固定宽度里写了 `against` 的先摆，占住它声明的那一头。它点名的固定柜子如果自己没写 `against`，按当时的最早空段先摆好。其余没写 `against` 的固定柜子再按清单顺序，占该高度上最早一段放得下的空墙。因此排在前面的普通柜子不会抢走已经声明贴墙的那一头。同一个角上，高度重叠的柜子只能有一台指定墙为目标；落地柜和吊柜高度不重叠时可以各写一次。空段要扣掉同高度的门窗、贴墙障碍和已经摆下的包络。放不下就失败。

`fill=true` 仅用于 `mode=wall`。可以不写 `width`。固定宽度的柜子都贴完之后才铺满。没写 `against` 时，这一台占剩下最长的一段空墙。写了 `against` 时，占贴着那一头的空段，不改拿更长的另一段。客户同时给了 width 与 fill 时，以这段空墙为准。

铺满得到**一台**柜子：id 不变，宽度就是这段空墙，`fill` 仍为 true。不按门宽、门扇数或内部分格再拆成几台。柜门、层板和抽屉归板件阶段。沿墙留空、从墙头挪开一截，不在这一阶段。两头都写了但固定宽度对不上这段距离、点名的柜子挨不到这一头、固定柜子去贴一台铺满柜、或者几台互相只写对方而没有一头贴墙，摆放失败。

编辑已经摆好的房间时，靠墙请求不带走算出的起点，但会留下 `against`，下次仍按它重贴。铺满件的编辑只改 `origin_z_mm`。换墙或改成自由摆放时，原来的 `against` 不再沿用。撤销这次换墙，或从自由摆放改回原来的墙时，`against` 按改之前的那一份写回。

## 拒绝条件

- 件越出房间或超过层高
- 与障碍物或另一件家具正体积相交
- 沿宿主墙遮挡垂直范围相交的门窗

边界接触不算干涉。可编辑视图的拖动按同一套摆放检查求解，干涉、越界或遮挡洞口就停在接触处（JS 侧镜像的判定在 `templates/room_page.js`，改 `placement_check.py` 要同步改它）。项目布局在创建待确认 Revision 前校验；缺房间尺寸或 fill 没有空段均失败。独立房间场景接口还要求非空 `items[]`。

## 输出

- 项目布局：`rooms[]` 中每间房含标准化 `room`、已解析的 `items[]`，有家具时还含 `preview`（透视 SVG）和 `viewer`（互动 HTML）；顶层 `cad.units` 是可执行柜体包络，不是 STEP。
- 独立房间场景：直接返回 `room`、`items[]`、`preview`、`viewer`；请求生成房间 CAD 时另有 `cad`，含源码、STEP 和 Viewer 路径。
- `items[]` 中有 placement、footprint 和六向净距；fill 后的 width 为沿墙实宽。

预览、Viewer 和房间 CAD 必须由当前房间和全部包络重建。

保存布局的 `rooms[]` 每项固定为 `{room, items, preview?, viewer?}`，必须带当前 `schema_version`。不接受旧的扁平房间输出或缺失版本。Viewer 与实时房间页共用模板；视角链接只使用 `default_view/top/bottom/front/back/left/right`。

## 房间 CAD

房屋：地面薄板 + 四面墙薄板（墙厚 100 mm）。门窗为墙上 `cut_box`。障碍物与每件家具为外形尺寸盒子，带原点与 `rotation_z_deg`。房间不做成封闭实心体。

- 源码：`temp/cad-source/layout-<artifact-name>/model.step.py`
- STEP：`generated/layout/<artifact-name>/room.step`

显式 `artifact_id` 仅允许英文字母、数字、`-` 和 `_`；非法值在创建目录或写文件前失败。未提供时，安全的房间 `id` 原样作为 `artifact-name`，否则由房间 `id` 的 SHA-256 生成稳定的 `room-<16 位十六进制>` 名称。所有源码和 STEP 路径在写入前都必须确认仍位于各自的输出根目录内。

这不是家具主流程的 `cad_generated`。不要调用 `furniture_run_next(..., generate_cad=True)`，也不要直调 `CadBridge`。

## 边界

- 不定义板件、封边、钻孔、五金、特征树或柜体 STEP。
- 房间坐标不混入板件尺寸。
- 项目布局写入 `stage_outputs["layout_plan"]`；`layout_plan` 是 `STAGE_SEQUENCE` 的首阶段，确认后进入 `approved_stages`，可执行柜体作为下游 CAD 单元。独立房间场景的预览和房间 CAD 不进入项目阶段输出或家具 CAD 交付清单。
