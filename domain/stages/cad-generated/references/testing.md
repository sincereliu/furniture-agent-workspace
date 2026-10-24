# 按改动选择测试

测试范围由维护者根据实际差异、字段所有者与调用关系判断；入口只执行明确选中的文件和用例，不自动推断依赖。共享目录中的测试按行为归属选择，不因目录位置把它们全部算进 CAD 或当前阶段。

## 选择范围

1. 先确定本次改了什么行为，选已有的直接覆盖测试；修复缺陷时补能复现该缺陷的行为测试。
2. 局部修复可选单个测试类或方法，正常路径和相关拒绝/失败路径一并覆盖。改动影响整个文件时跑该文件，不为减少数量任意删掉受影响分支。
3. 改了交接字段、规范值含义、确认/冻结、持久化或下游失效，再加受影响消费者与工作流测试。仅导入某阶段不等于该测试受本次修改影响。
4. 板件、制造等影响产物的结构性改动，按仓库约定在修改前跑板件产物基线，修改后与相关行为测试一起验证。此要求不扩展到纯页面、AI、测试入口或文案修改。
5. 纯文案检查实际涉及的文件和链接，不启动业务回归。定向验证通过后，除非有新改动、失败或未解决风险，不扩大或重复测试。

整库 Python 回归只用于明确的整库验收，或公共启动/导入、公共契约等改动经依赖审查确实波及全库。执行前说明原因。单阶段结构调整、增加一项测试或准备提交本身都不自动触发整库回归。`--all` 不包含独立 Node 和浏览器专项检查。

## 入口用法

以下命令在仓库根目录执行，均使用 `.venv/Scripts/python.exe domain/stages/cad-generated/scripts/run_tests.py`：

| 参数 | 行为 |
| --- | --- |
| `-p test_door_hinge_side.py` | 只导入、发现并执行匹配的测试文件 |
| `-p test_door_hinge_side.py -p test_panel_output_baseline.py` | 合并多个文件选择；重叠匹配的用例只执行一次 |
| `-p test_shared_contracts.py -k SharedDigestTests` | 在所选文件中只执行该类的用例 |
| `-p test_shared_contracts.py -k test_empty_object_keeps_the_existing_canonical_hash` | 选单个方法 |
| `-p test_shared_contracts.py -k SharedDigestTests -k SharedValidationTests` | 多个 `-k` 取并集；`-p` 与 `-k` 取交集 |
| `-p test_panel_*.py --list` | 先列测试 ID 与总数，不执行用例，也不核对/改写待办 |
| `--all` | 显式运行整库 Python 测试；不能与 `-p` 合用 |

`-k` 大小写敏感，匹配完整测试 ID：不含 `*` 时按子串匹配；含 `*` 时按 glob 匹配。无范围参数、匹配零项或测试模块导入失败，均以非零退出码结束。`--list` 仍会导入所选测试模块，不代表用例已通过。

## 找到对应测试

下表是查找入口，不是一行改动必须执行的固定大包。先读相关文件中的测试类与方法，再按本次行为缩小选择；新增行为按所有者补相应测试，不维护另一份自动文件映射。

| 改动行为 | 测试入口或指南 |
| --- | --- |
| 布局几何、门窗、拖动、房间编辑 | [布局运行时映射的选测表](../../layout-plan/references/runtime-map.md#维护时跑哪几个测试) |
| Web 画面、交互、页面装配 | [Web 检查方法](../../../modules/web/references/testing.md)，选择相关 Node、浏览器专项与宿主测试 |
| 门扇、铰链、抽屉、隔板、背板 | `test_panel_multi_door.py`、`test_door_hinge_side.py`、`test_drawer_zone.py` / `test_drawer_variants.py`、`test_panel_divider.py`、`test_back_mount_modes.py` 中对应行为；结构产物变化另加 `test_panel_output_baseline.py` |
| 材料目录、封边、连接、孔 | `test_materials_catalog.py` / `test_materials_bom.py`、`test_edge_banding.py`、`test_connection_point_contract.py` / `test_connector_patches.py`、`test_six_side_drill_patches.py` 中对应行为 |
| 制造特征与特征树转换 | 特征记录查 `test_feature_contract.py`，制造交接和树转换查 `test_manufacture_stage_boundary.py`，槽加工到树/源码查 `test_back_groove_pipeline.py`；改变阶段交接时补 `test_stage_boundary_regressions.py` 中相关类 |
| 确认、冻结、准入 | `test_furniture_orchestrator_freeze.py`、`test_furniture_orchestrator_admission.py` 中相关类 |
| 修订继承、租约、工具面 | 分别查 `test_revision_inheritance.py`、`test_edit_lease.py`、`test_agent_tools.py`；不因改动经过 Orchestrator 就全跑 |
| CAD 桥接 | `test_cad_bridge.py` 中对应测试；实际 CAD 生成受环境要求约束 |
| 公共校验与哈希 | `test_shared_contracts.py`，以及确实受影响的保存/冻结/继承测试 |
| AI 提供方、登录隔离、网页会话 | [AI 接入维护](../../../modules/ai/references/ai-integration.md)，按提供方、隔离、会话或页面挂载选择文件 |
| 测试入口、路径发现 | `test_test_runner.py`；`test_stage_boundary_regressions.py -k StageTestDiscoveryTests`；入口说明变动可选 `test_skill_architecture.py -k test_test_entry_point_is_discoverable` |

真实 HTTP、异步服务和浏览器测试须按 [开发环境](../../../../.agents/skills/furniture-agent/references/dev-environment.md) 及仓库的沙箱要求运行。汇报实际执行的范围、数量、结果与未覆盖项；选测通过只说明这些行为通过。
