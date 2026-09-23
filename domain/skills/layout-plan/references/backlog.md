# 布局阶段未落地需求

日常改房间摆放、摆放检查、编辑器或 Viewer 不必读本文。核对实现或规划演进时再打开。

## 待评审

### 摆放级改动不该重跑柜体（跨阶段需求，登记在编排层）

改摆放 / 改房间会开新 Revision 并从本阶段重来，但柜体内容其实一个字都没变（板件只读 `id / furniture_category / width / depth / height`）。柜体没变时下游全部重做、还要人重新确认，代价偏大。证据、缺口与候选方向登记在 [编排与生命周期未落地需求](../../cad-generated/references/backlog.md)，机制与判据见 [修订继承设计](../../cad-generated/references/revision-inheritance-design.md)。本阶段要注意的是依赖面与 `fill` 例外（见 [运行时映射](runtime-map.md)）。

### 门窗的增删改，以及"锁定"

现状：门窗只能在建房时写进 `rooms[].openings[]` 或场景源；编辑器里只画不编辑（`openingPoints`）；没有"锁定"概念，家具和洞口都能被拖走。

要做：edit 下增删洞口、改宽高 / 离墙偏移 / 窗台高；家具与洞口可"锁定"（拖不动，可解锁）。

约束：洞口同时参与摆放检查（遮挡门窗洞口）、`fill` 空段扣除、房间 CAD 的 `cut_box`，以及编辑器 / Viewer / SVG 三处绘制；改完必须能重建预览 —— `validate_room_scene` 会核对预览是否由当前几何重建。

### 预览页与草稿页的互相切换

现状：两个页面之间没有入口。预览页链接由对话给出；草稿页必须先存一份场景才有链接。

要做：预览页右栏给"在草稿页打开这一间"（服务端已有 `POST /api/room-scene/save` 与 `GET /api/room-scene/{id}/editor`）；草稿页给"回到项目预览"。

前提：草稿是**单间**、项目是**多间**，需要定映射规则（房间 id ↔ `scene_id`），并说明草稿写回时的合并方式 —— 现有做法是整屋一次性提交：草稿那间按草稿、其余房间按项目现状原样带上。

### Viewer 与 Editor 能否共用部分代码（待决定）

现状：两份模板各带一套相机 / 投影 / 拖拽 / 绘制（`viewer.py` 约 270 行、`editor.py` 约 2000 行），一致性靠"改两遍"维持 —— 本轮的相机镜像修正、视图控件、坐标层都是改两遍。

选项：① 抽一段公共 JS（在 Python 侧拼进两份模板）；② 只共享数据与契约，代码保持两份（现状）；③ 合并成一个页面、两种模式。

约束：模板是纯 Python 字符串，没有构建步骤；页面 CSP 目前是 `script-src 'unsafe-inline'`，抽成静态文件要放开 `'self'`，并改"模板自包含"这条约定。

### 房间能否合并（待决定）

现状：`rooms[]` 是矩形列表，各自算边界、各自做摆放检查；洞口只能开在房间自己的墙上。

要决定：先只做"相邻房间之间开一个门洞"（低成本），还是真的支持非矩形 / 复合房间轮廓。

影响面：`placement_check.py`（越界按单矩形判定）、`placement.py`（`fill` 空段）、`cad.py`（地面与墙的生成）、编辑器 / Viewer 的绘制与命中判定。

### 视图代码是否需要分割（待决定）

现状：`editor.py` 一个文件里同时装着 Python 渲染入口 + HTML/CSS + 一大段画布 JS（相机、投影、摆放检查的 JS 镜像、绘制、交互），接近 2000 行；`viewer.py` 是精简的第二份。

要决定：是否把画布 JS 拆成静态文件（例如 `scripts/furniture_layout/static/editor-canvas.js`）由服务端读入拼接。好处：能被编辑器与测试直接加载、diff 更可读、便于与 Viewer 共用。代价：CSP 要放开 `'self'`、"自包含 HTML"约定要改、`editor.py` 里的占位替换要跟着动。

先决定上一条"能否共用代码"，再决定怎么切。

## 已决定不做（留档）

- 视角接近正上方（极点）时的水平转速 / 俯仰上限调整：实测手感可接受，不做。极区行为保持现状 —— `pitch` 夹在 ±1.48，靠近正上方时水平拖动仍是绕竖轴旋转。

## 已落地（留档）

- 页面写项目（P3）：`POST /api/project/{id}/layout/edit` —— 页面上改一件的摆放，落成一个新 Revision（未确认）。几何复用房间场景编辑那套 op 词表与重算/准入（新增 `project_edit.py`：`RoomScene` ↔ 场景源往返 + `plan_scene`），版本与生命周期归 `furniture_workflow/project_layout_edit.py` 门面；三道门（本机来源 / 灰度开关 / `expected_version`）任一不过都不落盘。`fill` 件拒绝摆放类 op（宽与偏移由墙上空段派生）。设计见 [页面写项目设计](../../cad-generated/references/project-layout-edit-design.md)；预览页**尚未**接上这个 op（属单页内核收敛）。
- 页面身份与房间导航：两页页眉各挂一块身份牌（预览「只读预览 · 由对话更新」 / 草稿「草稿 · 不影响项目」）；多间房的切换从下拉改成页眉药丸按钮（只有一间房时整条藏掉），当前房间写进地址栏 `?room=<id>`，切房间时 `history.replaceState` 跟着改，链接可分享；深链按房间 → 视角 → 选中件依次生效。
- 只读分享形态：预览页带 `?mode=view`（`preview_url(id, mode="view")` / `open_project_preview(id, share=True)`）时牌子换「只读分享 · 链接可转发」、提示语换成"只看不改"、**不生成「退出」按钮**。它只是表达，不承担权限；写权限的门在服务端（见 [访问模式与外网分享](../../cad-generated/references/preview-access-design.md)）。
- 内容指纹收敛到一个实现：`workflow_digest.stable_digest`（key 排序 + 紧凑分隔符的规范化 JSON 上取 sha256），`workflow_constants` / `workflow_project` 都改用它，`project_preview` 的 `version` 从「修订号」改成内容版本 `layout_sha256:确认位`。
- 只读预览页去掉"编辑痕迹"：右栏**不生成**输入框与 − / ＋ 按钮（只留纯文字读数，提示语换成"只读预览：位置由对话更新；要自己拖，用草稿页"）；画布上**不画橙色旋转手柄、旋转环与刻度、蓝色离地手柄**（保留"正面朝哪"的绿箭头与「前」）；图例里"旋转环与手柄（橙）""离地高度手柄（蓝）"两行在只读页隐藏。落点：`detailMarkup()` 与 `drawRotateHandle()` / `drawHeightHandle()` 里按 `READ_ONLY` 分支，绿箭头抽成 `drawFrontArrow()` 两页共用；图例行标 `data-edit-only` + 一条 `body.readonly` 的 CSS。可编辑页一个字没动。
- 视图控件与坐标层：两页统一为"正视图下拉 + 复位"，预设键 `default_view`（旧的 `#view=perspective` 走别名），补 `仰视`，双击吸附 / 再双击回到进它之前那一眼，转视角后标识变「自由视角」；默认视角正南偏东 15°、俯仰 0.35。
- 相机左右镜像修正：房间坐标系是 X 东 / Y 南（左手系），右向量必须取 `cross(up, forward)`；转视角的拖动符号要一起翻。两页都改了。
- 原点三轴与光标坐标读数：两页一致（轴长就是总宽 / 总深 / 总高，带 `O (0,0,0)`）；Viewer 原先右下角那个固定不动的小图标已删除。
