# 料档与工艺卡

回答“板件厚度从哪来，提案要不要写，运行时如何准入？”；本文件是料厚目录、工艺卡和角色绑定的唯一规则中心。

## 车间进料

只有两种板：

- **料板**：目录 `{18, 22}` mm。工艺卡默认 `18`。
- **卷后背板**：常量 `9` mm。

门板不是第三种板，只用料板。多数跟柜体料；用户明示时门可单独为 `18` 或 `22`。

## 角色绑定

| 零件 | 料档 |
| --- | --- |
| 侧板、顶底板、层板、踢脚板、踢脚支撑、背拉条 | 料板 `board_thickness` |
| 抽屉前板、抽屉侧板、抽屉后板、抽屉底板 | 料板 `board_thickness` |
| 后背板（`groove` / `cover`） | 卷后背板 `back_thickness = 9` |
| 后背板（`insert`） | 料板 `board_thickness`（内嵌背板要打三合一，不能用 9 mm 卷板） |
| 门板 | 料板 `door_thickness`，省略则等于 `board_thickness` |

当前拓扑没有独立的抽屉面板。若以后增加，按门板料走，不按抽屉盒另开一档。

`board_thickness` 的规范语义是料板厚，不是「每块板各自的厚度」。踢脚条高是 `toe_kick_height`，背拉条高是 `back_rail_height`，厚度都走料板。

## 提案

- `board_thickness`、`back_thickness`、`door_thickness`、`drawer_bottom_thickness`、`drawer_back_thickness` 可省略。
- 省略由本工艺卡展开后再写入已准入 spec；冻结 JSON 与下游仍带具体毫米，不得缺字段。
- 写出的值必须落在目录内。`groove/cover` 背板写出时必须是 `9`；`insert` 背板写出时必须等于料板厚。抽屉底/背写出时必须等于已准入料板厚。
- 裸 CLI/API 没有 LLM 时同样允许省略料档；这是结构化协议，不是按柜型猜方案，也不是自然语言默认值。
- 「厚一点」等开放说法归 LLM，改写成目录成员后再写入；代码不解释这句话。

## 工艺卡展开

1. 未给 `board_thickness` → `18`；给了则必须是 `18` 或 `22`。
2. 未给 `back_thickness`：`groove/cover` → `9`，`insert` → 已准入料板厚。给了则必须等于该模式对应料档。
3. 未给 `door_thickness` → 等于已准入料板厚；给了则必须是 `18` 或 `22`。
4. 未给 `drawer_bottom_thickness` / `drawer_back_thickness` → 等于已准入料板厚；给了则必须等于料板厚。

用户没提板厚时，展示一行「料档按工艺卡：料板 18 / 卷后背板 9 / 门同料板」，不把五条厚度列入假设清单。只有覆盖了目录值时才展示改过的那一档。
