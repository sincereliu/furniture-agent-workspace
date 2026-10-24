# 网页展示模块

独立应用模块，不属于六阶段家具流程。房间页、项目名单和板件页的画面集中在这里。

```text
domain/modules/web/
  furniture_web/    页面组装、模板和三维画面
  references/       这一模块拿什么、留什么
```

`furniture_web` 只把已经算好的数据填进页面。摆放检查、拖动换算、板件结构投影、保存和编辑租约仍在原阶段。预览进程把本模块和布局阶段的求解、换算和交互事务脚本一起挂在 `/layout-view`。

浏览器里的布局写入与响应同步统一由 `static/layout_persistence.js` 管理。页面模板提交规范操作、显示状态和安装已确认的文档；控制器拥有请求队列、版本和同步状态。后端的几何准入、落盘与租约仍由原阶段负责。改这一链路先跑 `node domain/modules/web/furniture_web/static/layout_persistence_check.mjs`，再跑下列相关页面测试。

宿主的 `runtime_paths.bootstrap_runtime_paths()` 加载本模块路径。打开项目的命令不变。

- [页面边界](references/web-preview.md)
- [三维预览视觉规范与参考图](references/visual-style.md)：修改三维展示前必读，保持已确认的卡通手办风。

修改描边后，在仓库根目录运行统一检查（使用现有 Node、`.venv` 中的 Playwright 和已安装的 Chromium）：

```powershell
.\.venv\Scripts\python.exe domain/modules/web/scripts/check_outline.py
```

命令运行八组 Node 检查（含沙发尺寸边界与软包曲面）和真实 WebGL 像素检查，并在 `temp/outline-checks/` 保存 `results.json` 和 11 张固定场景截图。可用 `--output temp/outline-before` / `--output temp/outline-after` 分别保存改动前后结果供比较。任何脚本、浏览器断言、页面运行错误或依赖缺失都会返回非零退出码；不会把未运行的浏览器检查当作通过。它自行启动并清理临时本机静态服务，不读写项目，不要求已有预览服务。真实 HTTP/Chromium 检查应在沙箱外执行。

职责与检查范围见 [视觉规范](references/visual-style.md)。截图仍须人工核对卡通手办风，像素断言不能替代审美判断。

页面行为仍由现有预览测试覆盖：

```powershell
.\.venv\Scripts\python.exe domain/stages/cad-generated/scripts/run_tests.py -p test_project_preview.py
.\.venv\Scripts\python.exe domain/stages/cad-generated/scripts/run_tests.py -p test_cabinet_panel_page.py
```
