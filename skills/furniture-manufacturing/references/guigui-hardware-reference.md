# 柜柜（Guigui3）五金与加工参照资料

> ⚠️ **存档资料，暂不纳入当前计划。**
> 仅在对话中明确提到「对照柜柜进行对照」时，才读取本资料并启动对照工作。

来源：`D:\Program Files\guigui3`（柜柜 5.0.0.4）。

## 一、五金/连接件全集（`caches\libraries\tdat\connector\`，51 个 .jd）

| 类别 | 连接件 |
|------|--------|
| 三合一 | TrinityConnector、TrinityWithDowel(+Helper)、CCompConnector、CustomConnector、CustomConnectorComponent、CustomConnectorImpl、CustomConnectorComponentGenerator、CustomConnectorLayout |
| 铰链 | DefaultHinge、CCompHinge、Hinge、HingeHelper、FrameDoorHinge、NoneHinge |
| 二合一 | Con2In1Lock、Invisible2In1(+Helper) |
| 隐藏连接件 | QRInvisible、MDYInvisible、HKInvisible、LKInvisible、GuiRenYiInvisible、InvisiblePartV2(Style1/2 + Helper) |
| 木榫 | Dowel |
| 滑轨 | Slide、SlideHelper、KJLSliderHole |
| 拉米诺 Lamello | LamelloParts、LamelloPartsStyle1~5、LamelloPartsHelper |
| 钉 | Nail、PlateNail、GlassLaminateNail |
| 槽/孔生成 | ConSlot、SlotGenerator、HoleGenerator、ConHandleSideSlot |
| 锁孔 | DrawerLockHole、DoorLockHole、LockHole、LockHolePrivate、LockHoleHelper |

## 二、生产/组件对象全集（`caches\libraries\tdat\production\`，27 个 .jd）

- 柜体：PanelProduction、PlankProduction、SingleDoorProduction、SlideDoorProduction、DrawerProduction、SlideProduction
- 功能五金：HandleProduction、FreeHandleProduction、FootPlateProduction(踢脚板)、ClothesHookProduction(挂衣钩)、HangerProduction(挂衣架)、PantsRackProduction(裤架)、PierGlassProduction(穿衣镜)、RebounderProduction(反弹器)、RomaProduction(罗马柱)、RailingProduction(栏杆)、WLineBottomProduction、WtopLineProduction(顶/底线)
- 玻璃/定制：GlassProduction、GlassLaminateProduction、CustomHardwareProduction、CircularCornerProduction(圆角)、CCompProduction、MatPanelProduction

## 三、加工语义词汇表（`caches\clients\BFZ\technology\MachineDictionary.json`）

柜柜用「位置 + 动作 + 条件」描述加工，词汇如下：

- **位置类**：`margin_back`(距后)、`margin_front`(距前)、`margin_up`(距上)、`margin_down`(距下)、`margin_left`(距左)、`margin_right`(距右)、`margin_side`(距边=距前或后)、`spacing`(间隔)、`move_front/back/up/down/left/right`(向前/后/上/下/左/右运动)
- **动作类**：`length_slot`(拉槽长)、`depth_hole`(打孔深)、`knife_change`(换刀)、`knife_lift`(提刀)、`count`(放一个)
- **条件类**：`depth_lessThan`(深度<)、`depth_greaterThan`(深度>)

## 四、形状定义格式（`caches\clients\BFZ\materials\shapes\*.js`）

JSON 顶点轮廓：`{b, x, y}` 描述 2D 轮廓（`b` 为贝塞尔/圆弧标志），`props` 存尺寸参数，`vertex`/`extras` 存主轮廓与凹槽轮廓。是截面造型，非打孔逻辑。

## 五、报告模板字段（`base\reports\打印标签.xml`）

客户、订单、板件、房间、板号、材质、成品尺寸、**侧孔信息**，带条形码。

## 六、无法读取的部分

`.jd` 文件为二进制（read 报 binary file，hex 查看受沙箱限制），核心打孔生成逻辑（孔位/直径/深度/配合关系）在 .jd 内，无法直接读取。

## 启动条件

仅在明确提到「对照柜柜进行对照」时启动，读取本资料并开展五金类目/打孔规则的对照工作。
