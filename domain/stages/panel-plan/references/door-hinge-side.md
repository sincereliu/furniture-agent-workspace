# 门板铰链侧

回答"门往哪边开、这个值谁给、制造怎么读"。一句话：**它是设计决定，板件阶段给，制造只消费。**

## 为什么归板件阶段

铰链侧决定的不只是打孔位置，它还决定**人从哪边伸手**、拉手装哪一侧、开门会不会撞墙或撞旁边的门。

以前这条由制造阶段按门序猜（`_derive_door_hinge_sides`：单门必须显式给，双门左=left 右=right）。两个问题：

1. **它是设计决定，被塞进了工艺阶段**——制造只该按它选铰链、排孔位；
2. **只能处理 ≤2 扇**：一排放 5 扇就抛 `supports at most 2 doors`。

所以现在改由板件阶段给出，随门板一起进冻结文件；制造读它，不再推。

## 提案怎么写

`door_hinges` 是**可选**字段，从左到右每扇门一项：

```json
"door_hinges": ["left", "right", "left"]
```

长度必须等于 `n_doors`，取值只能是 `left` / `right`。

## 口径：只说铰链在哪条边

**左开 = 铰链在门的左侧；右开 = 铰链在门的右侧。** 这里的"左/右"就是人站在柜子正面
看到的左右。别把它翻译成"往哪边开"——那两种说法方向词正好相反，混着说必然吵（踩过）。
也不在页面上解释"拉手在哪"，越解释越绕。

数据里的对应关系：柜体坐标 X 是宽；**低 X ＝ 屏幕左侧**（3D 页面把 x 镜像过来渲染，
见 `layout-plan/references/preview-ops.md`）。所以 `left` ＝ 铰链在门的**低 X** 那条边。

## 三条规则

| 情况 | 谁定 | 写法 |
| --- | --- | --- |
| **对开腔**（一个腔两扇门） | 几何逼死：左扇挂左、右扇挂右 | 可以不写（自动推）；写了必须是 `left, right`，写反直接拒 |
| **单开腔**（一个腔一扇门） | 设计决定：往走道开还是往墙开，几何里没有答案 | 必须写；不写就停 |
| **一个腔三扇以上** | 本拓扑表达不了 | 一律留空，等门型（联动 / 推拉）补上再说 |

**留空 ≠ 随便，但也不硬停**：留空的门不能开门、也排不了铰链孔。板件阶段会报一条
**警告** `DOOR_HINGE_SIDE_UNKNOWN` 点名单开腔那几扇门——**不拦确认**，因为拦了板件页
就没有这台柜，客户连"点一下左开/右开"的机会都没有。补上的两条路：

1. **页面上点**：板件页选中那扇门，右侧「铰链侧」给两个按钮（左开 / 右开），选完点
   「保存并冻结」——落一个新 Revision、重新冻结，警告随之消失。走
   `POST /api/project/{id}/cabinets/{id}/panels`（`hinges: {门板 id: left|right}`）。
2. **提案里给**：`door_hinges` 补齐再重跑板件阶段。

**真正的闸门在制造**：没有铰链侧的门排不了铰链孔，`manufacturing_bom` 会点名叫出
还没定的那几扇（`door hinge side is not decided yet: …`），不会按门序猜。

整排都是对开腔（比如 800 宽双门柜）时，`door_hinges` **完全可以不写**——几何已经把答案定死，再让人填一遍就是让人说废话。

## 落到哪

- 提案字段：`door_hinges`（`panel_spec.PANEL_OPTIONAL_PARAMETER_FIELDS`）。
- 冻结文件：每块门板上的 `door_hinge_side`。**空值不落盘**，所以老工程产出不变。
- 推导与核对：`construction_geometry.door_hinge_sides()`——对开腔自动推、单开腔读提案、写反就拒。
- 校验：`validation_panels._validate_doors()` 的 `DOOR_HINGE_SIDE_MISMATCH` / `DOOR_HINGE_SIDE_UNKNOWN`（后者是**警告**）。
- 页面改：`POST /api/project/{id}/cabinets/{id}/panels` —— `project_layout_edit.save_cabinet_panel_edits()` 同时更新 `spec.door_hinges` 与每块门板的 `door_hinge_side`，再用 `door_hinge_sides()` 复核；对开腔被单独改会被拒。
- 制造：`manufacturing_bom._resolve_door_hinge_sides()` **优先读门板上的值**；只有老冻结文件没带时才回退到按门序推导（`_legacy_door_hinge_sides`，仍限 ≤2 扇）。铰链孔位规则仍在制造（`connectors/hinge.py`），不搬。
- 页面：板件页的「开门」按这个值绕门的一条竖边旋转——`left` 绕门左边转开；空值的门不动，详情里写"还没定"。

## 边界

- 这个字段只说**哪条边**。几个铰链、上下端距多少、什么型号，都是按门高与五金算的工艺，留在制造阶段。
- 上翻 / 折叠 / 推拉 / 联动是**门型**，不是铰链侧；那些还没有拓扑，等做门排或多门型时再单列。

入口：[板件提案契约](panel-proposal-contract.md)、[板件定义规则](panel-definition-rules.md)、[柜内结构契约](interior-structure-contract.md)。
