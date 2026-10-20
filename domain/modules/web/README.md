# 网页展示模块

独立应用模块，不属于六阶段家具流程。房间页、项目名单和板件页的画面集中在这里。

```text
domain/modules/web/
  furniture_web/    页面组装、模板和三维画面
  references/       这一模块拿什么、留什么
```

`furniture_web` 只把已经算好的数据填进页面。摆放检查、拖动换算、板件结构投影、保存和编辑租约仍在原阶段。预览进程把本模块和布局阶段剩下的两份脚本一起挂在 `/layout-view`。

宿主的 `runtime_paths.bootstrap_runtime_paths()` 加载本模块路径。打开项目的命令不变。

- [页面边界](references/web-preview.md)

页面行为仍由现有预览测试覆盖：

```powershell
.\.venv\Scripts\python.exe domain/stages/cad-generated/scripts/run_tests.py -p test_project_preview.py
.\.venv\Scripts\python.exe domain/stages/cad-generated/scripts/run_tests.py -p test_cabinet_panel_page.py
```
