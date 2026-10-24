# Web 检查方法

在仓库根目录使用现有 Node、`.venv` 的 Python、Playwright 和 Chromium。真实 HTTP/浏览器检查须在 Windows 沙箱外执行；自行建立临时服务并清理，不读写用户项目。失败、运行错误和依赖缺失均视为失败。

## 按改动选择检查

下列命令均为 `.venv/Scripts/python.exe domain/modules/web/scripts/<命令>`：

| 改动 | 命令 | 主要覆盖 |
| --- | --- | --- |
| 模块路径、通用计算 | `check_node.py` | 自动执行 `tests/node/*_check.mjs` 全部行为检查 |
| 板件页模块装配、材质、取景、属性与保存 | `check_panels.py` | 真实规划并确认冻结板件，浏览器加载、顺纹/铰链预览、HTTP 保存重冻、重载与分享只读 |
| 描边、接触、深度 | `check_outline.py` | 8 组 Node、WebGL 最终像素和真实房间入口 |
| 墙体、门窗、淡出 | `check_openings.py` | 几何方向/边界、玻璃、四墙淡出、布局入口和释放 |
| 照明、天空、庭院 | `check_lighting.py` | 窗光/顶灯贡献、真实阴影、隐藏墙顶、天空解码/署名、落地和释放 |
| 输入、属性、同步 | `check_drag.py` | 指针 → HTTP 保存 → 重开一致，取消、失败、迟到响应、外形互斥、against/fill |
| 租约、事件连接 | `check_edit_lease.py` | 双窗口收回并保存、关闭/助手归还恢复、闲置、网络/HTTP 失败、403、并发申请 |

可单独运行 `node domain/modules/web/tests/node/<文件名>`。新增行为检查放在该目录，采用 `*_check.mjs`，全部检查入口自动执行。专项命令只执行相关子集。

宿主 Python 页面与服务检查：

```powershell
.venv/Scripts/python.exe domain/stages/cad-generated/scripts/run_tests.py -p test_project_preview.py
.venv/Scripts/python.exe domain/stages/cad-generated/scripts/run_tests.py -p test_cabinet_panel_page.py
.venv/Scripts/python.exe domain/stages/cad-generated/scripts/run_tests.py -p test_room_layout_preview.py
.venv/Scripts/python.exe domain/stages/cad-generated/scripts/run_tests.py -p test_skill_architecture.py
.venv/Scripts/python.exe domain/stages/cad-generated/scripts/run_tests.py -p test_api_entrypoint.py
.venv/Scripts/python.exe domain/stages/cad-generated/scripts/run_tests.py -p test_decision_log.py
.venv/Scripts/python.exe domain/stages/cad-generated/scripts/run_tests.py -p test_layout_input_contract.py
.venv/Scripts/python.exe domain/stages/cad-generated/scripts/run_tests.py -p test_room_scene_editor.py
```

位置协议改动还需布局阶段 `static/interaction_check.mjs` 与 `test_drag_transaction_roundtrip.py`。阶段求解检查留在原阶段。

## 画面与证据

描边、门窗、照明和板件命令均支持 `--output <目录>`，默认分别写入 `temp/outline-checks/`、`temp/opening-checks/`、`temp/lighting-checks/`、`temp/panel-checks/`，输出 JSON 和截图。拖动命令支持 `--output <截图路径>`。前后比较用不同目录，不自动改已确认参考图。

描边覆盖同件接缝、不同家具交界、选中/碰撞色、透明/不透明墙、远近线宽、左右视角、正交/透视、DPR 1/2、画布大小、贴墙/接地及 2/80 mm 移离恢复。Node 还检查代理复用、移除、清理与渲染异常后的状态恢复。不能只检查消线，而漏掉可见部分的整圈基础外框。

浏览器夹具在 `tests/browser/`，由 `scripts/browser_support.py` 临时以 `/web-checks/` 提供，正式预览不提供这些页面。探针仅注入测试响应，正式页面不向检查脚本暴露私有租约或拖动事务。

板件检查使用 `tests/browser/panel_project.py` 的显式提案，经正式规划/确认流程生成测试项目，不依赖宿主测试类或 `temp/` 中的脚本。`scripts/project_browser_support.py` 为板件、拖动和租约检查提供独立临时目录与实际 HTTP 服务；检查结束后清理。模块加载错误、页面异常、保存失败或新冻结事实未反映到重载页面，均使 `check_panels.py` 返回非零退出码。此入口与 Python 板件测试配合使用，源码断言不能代替真实浏览器回归。

仍须按 [视觉规范](visual-style.md) 人工比较截图。通过已有检查不能证明没有未覆盖问题；已复现的两项描边缺陷与缺失用例仍在 [Web 待办](../../../../backlog/web.md)，不能据此标为完成。
