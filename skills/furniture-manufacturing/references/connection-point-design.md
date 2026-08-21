# 连接点级实体需求（记录）

状态：**需求记录**（未立项、未实施）。来源于 2026-08 局部坐标化重构讨论。

## 背景

三合一（及背板 insert）的杆孔 / 轮孔配对目前是**几何隐式约定**，不是结构引用：

- 一个连接点 = 1 杆孔（端面）+ 1 轮孔（cam 面）+ 配合板 1 预埋螺母孔；
- 配对靠"同 y（深度排）、同 z（高度）、轮孔 x = 端面 ± `center_offset_from_edge_mm`"在几何上对齐；
- `HoleSpec` 之间没有 `connection_id` 之类的引用，孔位列表里没有"连接点"实体；
- 孔位永远是**整体重生成**（`generate_holes()` / `generate_holes_for_panels()` 从板件+连接拓扑从零计算），不存在"删单个孔"的增量编辑入口。

## 现状行为（回答"删一个孔，配对孔会怎样"）

| 操作 | 配对孔是否跟着删 | 校验是否拦截 |
|------|----------------|--------------|
| 删主柜体轮孔 | ❌ 不删，杆孔成孤儿 | 拦截：`TRINITY_HARDWARE_COUNT_MISMATCH`（偏心轮孔数 ≠ BOM 数） |
| 删主柜体杆孔 | ❌ 不删，轮孔成孤儿 | **不拦截**（无"杆孔数 == 轮孔数"检查，静默） |
| 删背板 insert 任一类孔 | ❌ 不删 | 拦截：`BACK_MOUNT_HOLE_COUNT_MISMATCH`（cam/rod/pre_nut 三类数量必须相等） |

依据：`validation.py` L332-340（主柜体只校验轮孔数）、L354-388（背板 1:1:1 数量约束）；
BOM 数量只认轮孔（`TrinityConnector.boms()` quantity = `system_32_female` 计数，孔即真源）。

## 需求

1. **连接点作为整体增删**：删除一个三合一连接点 → 它的杆孔 + 轮孔 + 配合板螺母孔一起消失；增加同理。背板连接点（cam + rod + pre_nut）同样按连接点整体增删。
2. **校验按连接点对齐**：主柜体也校验 `杆孔数 == 轮孔数 == 连接点数`（或更强：按连接点标识逐点核对配对几何），消除"删杆孔静默孤儿"。
3. **配对显式化**：`HoleSpec` 增加连接点标识（如 `connection_id` / group 字段），或引入连接点级实体；连接拓扑（`PanelJoint` 的 male/female 配对）可作来源。
4. **顺带修正**：`machining_operations` 的 id 为 `{hole_type}_{panel}_{z:.0f}_{y:.0f}`，不含端面区分，横板左右两端同 (z,y) 的杆孔 id 重复——按连接点索引时该 id 方案必须含端面/方向区分。

## 实施建议（暂定，实施前需重新评审）

- 与 `coordinate-naming.md` 迁移策略同类，属"搭车改"：在有连接点实体的重写时一并落地字段命名，不单独动。
- 候选方案：以 `PanelJoint` 为连接点载体，制造阶段为每个 joint 生成带 `connection_id` 的三件套孔位；校验按 id 对齐。
- 验收建议：删除某连接点后其全部孔位与 BOM 数量同步减少且校验通过；模拟"手动删单孔"时校验能报出具体连接点。

## 关联

- 五金参数位置：`SKILL.md`（`hardware_catalog.yaml` / `hardware_rules.yaml` / `connectors/` + `ALL_CONNECTORS` 注册）。
- 局部坐标化（局部为唯一真源）：`connectors/trinity.py`、`back_mount.py`、`shelf.py` 已落地，P3 触发条件已满足。
