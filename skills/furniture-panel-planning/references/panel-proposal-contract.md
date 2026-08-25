# 板件方案提案与准入契约

回答“LLM 应怎样把用户语言整理为板件方案，运行时又准入什么？”本文件只指导提案，规范字段和数值不变量仍由 `panel_spec.py` 执行。

## 语义层：由 LLM 负责

- 综合用户原话、已确认外包络和当前对话，判断门、层板、整高抽屉区、背板、踢脚及净空诉求；不要按关键词、同义词表或单句正则分类。
- 多个方案都合理时给出候选与取舍，推荐其中一个，并把未由用户明确给出的值列为假设。不要把假设伪装成用户要求。
- 混合门/抽屉、分区柜体、多门开启关系或其他当前拓扑不能完整表达的需求必须继续消歧；不得把它压缩成会丢失语义的 `drawer_count` 或 `n_doors`。
- 交给运行时的 `parameters` 只含规范字段和值，不携带自然语言说明。说明、假设和追问保留在用户交互中。

## 结构化提案

提案有两种合法形态：

1. 显式选择一个 `panel_profile`，并只覆盖用户已选择或 LLM 明确提议的字段。
2. 不使用 profile，完整提交下列全部字段；缺少任一字段都会停止准入。

规范字段：

- 功能数量：`shelf_count/n_doors/drawer_count`，均为非负整数。
- 主体：`board_thickness/back_thickness/door_thickness`。
- 背板：`back_mount/back_offset/groove_depth/groove_clearance/back_rail_height`。
- 门与踢脚：`door_margin/door_hinge_gap/toe_kick_height/toe_kick_reveal_front/toe_kick_reveal_back/toe_kick_support_count`。
- 抽屉几何：`drawer_side_clearance/drawer_layer_gap/drawer_bottom_thickness/drawer_back_thickness/drawer_back_clearance`。

数值单位均为 mm。`toe_kick_support_count=null` 是显式请求宽度公式计算，不等于缺失；`back_mount=auto` 是显式请求厚度公式解析，也不等于缺失。`door_count` 仅是结构化协议兼容字段，新提案使用 `n_doors`。

## 可选标准 profile

profile 是方便确认的、版本化的完整结构化方案，不是运行时按柜型猜出的默认值。LLM 只有在认为适合当前需求时才推荐；运行时只按显式名称展开并检查柜型兼容性。

| profile | 适用柜型 | 主要提议 |
|---|---|---|
| `floor_cabinet_standard_v1` | `floor_cabinet` | 18 mm 柜体/门、9 mm 背板、4 层板、2 门、50 mm 踢脚、显式 `auto` 背板；无抽屉 |
| `wall_cabinet_standard_v1` | `wall_cabinet` | 18 mm 柜体/门、9 mm 背板、1 层板、2 门、无踢脚、显式 `auto` 背板；无抽屉 |

完整数值由 `panel_spec.py/PANEL_PROFILES` 作为结构化协议单一真源；本表只帮助 LLM 选择，不复制全部参数。

## 停止条件

- `DesignIntent` 未确认、提案不完整、字段不是规范类型、profile 与柜型不匹配：停止，不生成板件。
- 当前拓扑中的 `drawer_count>0` 表示整高抽屉区，因此必须同时为 `shelf_count=0/n_doors=0`；混合分区先继续设计，不由代码静默忽略门或层板。
- 吊柜当前不支持抽屉，且 `toe_kick_height` 必须为 0。
- 代码准入后仍须通过结构、净空和板件不变量校验；`proposal_admission.spec_sha256` 不匹配时不得确认，更不得进入 BOM、制造、特征树或 CAD。
