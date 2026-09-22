# 运行时映射（制造阶段）

本参考集中说明 `SKILL.md` 工作流背后的运行时结构与校验职责；LLM 走业务流时不必逐条记忆，核对实现或规划演进时再读。

## 交接

板件几何来自已确认冻结文件，不重跑 `panel-plan`。Orchestrator 用 `confirmed_panel_sha256` 读 `store/<project-id>/panels/<sha256>.json`。本阶段用 `confirmed_panels.py` 只抄加工要用的字段：柜类、外包络、料厚、已经解析好的背板模式和槽参数，以及每块板的尺寸、位置、语义面和接触几何。不引用板件阶段的 Python 类型。多出来的板件字段忽略。接触上若带有历史 `connection`，读入时丢掉，连不连由本阶段重算。本阶段已经保存的接触若缺 `connection`，按旧档视为 `on`。板件 id 仍是 `{cabinet_id}__{role}`；旧制造记录缺 `role` 或 `parent_id` 时从这段 id 还原，没有柜体前缀时父级用 `cabinet_1`。本阶段自己的提案在 `stage_inputs.manufacturing`。无 Store 或尚未记下确认哈希时读内存 `stage_outputs.panel_plan`。

## 五金连接件（`connectors/`）

- 基类 `Connector` 定义统一接口：`match()`、`generate_holes()`、`generate_holes_for_panels()`、`boms()`、`machining_operations()`。
- 具体连接件：`TrinityConnector`（三合一）、`HingeConnector`（铰链）、`TwoInOneConnector`（二合一）、`ShelfPinConnector`（隔板钉）、`BackMountConnector`（背板）、`DrawerSlideConnector`（滑轨）。
- 新增五金：实现对应 `Connector` 并注册进 `ALL_CONNECTORS`。
- 孔位用 `HoleSpec` 描述；`is_face_hole=True` 表示板面钻孔（导出 TypeNo=1 垂直孔），`False` 表示板边钻孔（TypeNo=2 水平孔）。
- 铰链侧 `door_hinge_side` 由制造层派生：单门从 `requested_options` 输入（`left`/`right`），双门按门板 X 位置派生；`HingeConnector` 读 `PanelRecord.door_hinge_side`，缺省时按门板位置回退。

## 五金命名约定

- 五金按「套」组织：三合一（偏心轮+连接杆+预埋螺母）、二合一（偏心轮+连接杆，固定塑料件并入连接杆）、隔板钉（单钉）。
- 目录键（`hardware_catalog.yaml`）全英文：顶层按套 `three_in_one` / `two_in_one` / `shelf_pin`，套内规格组 `standard`，零件键 `cam` / `rod` / `nut` / `pin`；每个零件分 `part`（实物，BOM/采购）与 `hole`（打孔，钻孔）两层，配合余量直接写入 `hole` 数值，不做代码派生。
- 孔类型（`hole_type`）按 `<套名>_<零件>`：`three_in_one_cam` / `three_in_one_rod` / `three_in_one_nut`、`two_in_one_cam` / `two_in_one_rod`、`shelf_pin`；进入 `drilled-holes.json` / GLB 标签 / 校验计数。内嵌背板三合一与柜体三合一统一为 `three_in_one_*`，靠 `HoleSpec.connection_id`（`<female>→<male>#<排次>`，确定性、非随机）区分来源。
- 活动层板连接方式由制造阶段输入 `movable_shelf_connector`（`two_in_one`/`shelf_pin`）显式选择，经 `plan_manufacturing` 盖章到 `PanelRecord`；`TwoInOneConnector`/`ShelfPinConnector` 只处理选中自己的板件，避免两者同时出孔/BOM。有活动层板却未提供时运行时拒绝。
- 连不连写在制造接触 `Contact.connection` 上，由 `plan_manufacturing` 按面板类型重解析（`default_joint_connection`）。默认口径见 [连接与接触默认规则](connection-contact-defaults.md)。`off` 的接触不进入三合一打孔。轴方向和制造层派生的 `cam_face` 只用于选择三合一五金。

## 材料目录与 appearance 物化

- 材质单一真源 `materials_catalog.yaml`：`substrate`（基材）+ `surface`（表面）两个独立维度；键=稳定代号（全小写、段间 `__`、段内 `_`），`name`=可读全名。键唯一由公共 `catalog_loader.py` 的重复键检测兜底。
- `surface` 键 = `颜色__表面处理__纹理`；`finish`（soft_touch/gloss/double_faced）与 `grain`（plain/grain）的组合当前显式枚举；颜色增多后按规则派生（yaml 顶部 TODO）。
- `appearance` 输入按材质角色选型：`{carcass|door|back: {substrate, surface}}`，键值必须命中目录（查表准入）；角色键只能是三个、缺角色/多余角色报错，不做静默默认。空 appearance 不物化（向后兼容）。
- 物化：`plan_manufacturing` 按 `placement.material_role` 把 substrate/surface 键写进 `PanelRecord.substrate/surface`；`material` 字符串仍表达「料厚+角色」。
- `validation.py`：appearance 非空时每块板 substrate/surface 必须非空（`APPEARANCE_NOT_MATERIALIZED`）。
- 语义：`BOMReport.appearance` 是选型输入记录，`PanelRecord.substrate/surface` 是物化真相；revise 直接编辑输出后两者可不同步。

## 封边皮

- 封边皮单一真源 `edge_banding_catalog.yaml`：`material`（abs/pvc/laser）+ `thickness`（t0_8/t1_0/t2_0）两个独立维度；键唯一由公共 `catalog_loader.py` 的重复键检测兜底。
- 封边选型 `{material, thickness}` 经 `requested_options.edge_banding` 输入，默认 `abs/t1_0`（= 历史「ABS 1.0mm」）；查表准入。
- 两个派生属性（不进目录、代码确定性计算）：宽度 = 板件厚度；颜色 = 同色，取 surface 键的 color 段（`white__soft_touch__plain` → `white`）。
- `EdgeBandFeature` 承载结构化封边：`material`（键）+ `thickness_mm` + `width_mm` + `color`；`from_edge_banding` 兼容旧字符串格式。
- 封哪些边：四边规则保留（`manufacturing_edge_banding.py` 的 `FOUR_EDGE_TYPES`）；入槽背板不封边；「见光边」依赖见光面建模，列未来。

## 生成与产物

- 单板规则实现 `generate_holes()`；需要配合板时覆盖 `generate_holes_for_panels()` 生成成对孔。
- `estimate_hardware()` 与 `emit_drilled_holes()` 遍历 `ALL_CONNECTORS` 生成 BOM 与可序列化的全局/local 孔位数据。
- `estimate_materials()` 从板件派生材料 BOM（`MaterialRecord` 三类）：基材（substrate，按基材+厚度汇总 m²）、饰面（surface，按表面汇总 m²）、封边皮（edge_banding，按材质/厚度/宽度/颜色汇总米数，四边周长 2×(长+宽)）；与五金 BOM 对称，写入 `BOMReport.materials`。
- 实际 `.drilled-holes.json` / `.glb` 文件由 CAD 阶段 `workflow_artifact_writer.py` 写入；制造阶段只产出结构化孔位数据。

## 背板槽机制

- `groove` 为左右侧板、顶/底板生成 4 条目标明确的 `cut_box`；槽宽 = `back_thickness + groove_clearance`，槽深 = `groove_depth`。
- `insert` 输出四边三合一成对孔；cover 外盖螺钉与 groove 背拉条螺钉属组装现场工艺，不生成孔位与五金。

## 校验职责

- `validation.py`：BOM、每条槽是否落在目标板件包络内、铰链孔位置/进刀面/深度、背板五金和配合孔。
- `hole_validator.py`：孔位几何（边界/深度/干涉）。深度按打孔方向的板件尺寸判定（端面钻入的连接杆/预孔可大于板厚）；正交配合孔（三合一杆↔轮）不判干涉。

未落地与待议需求见 [backlog](backlog.md)，日常改孔位/BOM 不必读。

## 改 X 去哪改

跨阶段定位表：想改某个制造相关结果，从这张表找到拥有它的文件。表中 `domain/` 开头的路径由 `tests/test_skill_architecture.py` 断言存在，改文件名或搬目录必须同步改这里。

| 想改什么 | 去哪改 |
|---|---|
| 门宽 / 门高 | `domain/skills/panel-plan/scripts/furniture_panel_planning/topology_solver.py`（`_door_panels` 的 `dw`/`dh` 公式） |
| 铰链侧（左/右） | `domain/skills/manufacture-plan/scripts/furniture_manufacturing/manufacturing_bom.py`（`_derive_door_hinge_sides`；单门来自 `stage_inputs.manufacturing` 的 `door_hinge_side`） |
| 铰链数量（按门高分档） | `domain/skills/manufacture-plan/scripts/furniture_manufacturing/hardware_rules.yaml`（`hinge_drilling.count_by_door_height`） |
| 杯孔直径 / 深度 | 同上（`hinge_drilling.cup_by_variant_group`） |
| 杯孔到门边距离 | 同上（`hinge_drilling.position.edge_offset_mm`） |
| 铰链钻孔几何 | `domain/skills/manufacture-plan/scripts/furniture_manufacturing/connectors/hinge.py` |
| 三合一孔位与类型 | `domain/skills/manufacture-plan/scripts/furniture_manufacturing/connectors/trinity.py` |
| 钻孔方向语义 | `domain/skills/manufacture-plan/references/coordinate-naming.md` |
| 背板槽尺寸与四种目标槽 | `domain/skills/manufacture-plan/scripts/furniture_manufacturing/connectors/back_mount.py` |
| 封边皮宽度与颜色派生 | `domain/skills/manufacture-plan/scripts/furniture_manufacturing/manufacturing_edge_banding.py` |
| 材质目录键 | `domain/skills/manufacture-plan/scripts/furniture_manufacturing/materials_catalog.yaml` |
| 封边皮目录键 | `domain/skills/manufacture-plan/scripts/furniture_manufacturing/edge_banding_catalog.py` |
| 六面钻机床轴映射 | `domain/skills/manufacture-plan/scripts/furniture_manufacturing/devices/six_side_drill_guigui.yaml` |
| 六面钻 XML 输出 | `domain/skills/manufacture-plan/scripts/furniture_manufacturing/export_six_side_drill.py` |
| 料厚（板/背板/门/抽屉） | `domain/skills/panel-plan/scripts/furniture_panel_planning/panel_spec.py`（`thickness_for_material_role`） |

门厚、门缝、铰链缝、料档等**输入参数**归板件阶段提案契约，见 [板件提案契约](../../panel-plan/references/panel-proposal-contract.md)；本表只回答「结果由哪个文件算出来」。

## 相关契约

- 坐标命名约定：`references/coordinate-naming.md`
- 六面钻导出（仅用户要求出机床文件时）：`references/six-side-drill-export.md`
