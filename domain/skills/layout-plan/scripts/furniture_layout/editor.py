"""Generate an editable room-scene view.

点选一件家具后拖动：靠墙件沿墙滑动（发 `offset_mm`），自由件平面移动（发
`origin_x_mm`/`origin_y_mm`）。选中后家具上方有两个手柄——橙色圆点拖了是旋转
（发 `rotation_z_deg`），蓝色圆点拖了改离地高度（发 `origin_z_mm`）；墙摆的
旋转由 `host_wall` 派生，所以旋转墙摆会在同一个 op 里改成自由摆放。靠墙件往
房间内拖过阈值也会转成自由摆放。

画面、转视角、缩放和点选由 three.js 负责。房间坐标仍是 X 东、Y 南、Z 上。
相机接近水平（pitch 很小）时地面射线求交会退化，所以那种视角下拖动改成在「水平轴 +
高度」这个竖直平面里走，上下拖就是改高度。

选中件的四向净距（到最近的家具/障碍物/墙）直接画在图上：先找同一高度带、垂直
方向有重叠的最近邻，找不到才退到墙。

拖动与旋转**本地就按服务端的摆放检查求解**（见 placement_check.py：底面正面积
重叠且高度重叠才算干涉，贴边接触放行；另查越界和遮挡门窗洞口）。过不去就停在
接触处，不会先穿过再回弹。求解在**整数毫米**上进行，
和服务端落盘取整口径一致，预览即落盘值。

拖动期间只做本地预览，松手才发**一个** edit op，由后端重算并校验——失败会显示
原因，不回退本地已画的形状。

项目预览复用同一块画布，但是只读：不发 edit op，按版本号换上新的包络。
"""

from __future__ import annotations

from html import escape
import json
from typing import Any

from .scene import RoomScene


EDITOR_WIDTH_PX = 960
EDITOR_HEIGHT_PX = 600


def editor_scene_payload(scene: RoomScene) -> dict[str, Any]:
    """Scene JSON the canvas already draws. Same shape after a reload."""
    return {
        "room": scene.room.to_dict(),
        # 与服务端 PlacedItem.to_dict() 同构：编辑后用同一形状替换，不引入第二种结构。
        "items": [item.to_dict() for item in scene.items],
        "obstacles": [
            {
                "label": obstacle.kind,
                "footprint": [list(point) for point in obstacle.footprint],
                "z_start": obstacle.z_mm,
                "z_end": obstacle.z_mm + obstacle.height_mm,
            }
            for obstacle in scene.room.obstacles
        ],
        "openings": [opening.to_dict() for opening in scene.room.openings],
    }


def _json_for_script(payload: object) -> str:
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


_EDITOR_TIPS = (
    "拖动时干涉、越界或遮挡门窗洞口会停在接触处<br>"
    "选中件：紫线是四向净距，灰线是本体宽/深/高<br>"
    "橙点或旋转环拖了调朝向（Shift 1°）· 蓝点调离地高度<br>"
    "前/后/左/右视里上下拖 = 改高度<br>"
    "右侧的距离 / 朝向 / 离地可输入，也可用 − / ＋ 走整数档<br>"
    "空白处拖拽转视角 · 右键/中键/Shift+左键拖拽平移 · 滚轮缩放 · Esc 取消选中<br>"
    "双击画面吸到最近的正视图，再双击回到自由视角"
)

_PREVIEW_TIPS = (
    "只读预览，位置由对话更新。<br>"
    "空白处拖拽转视角 · 右键/中键/Shift+左键拖拽平移 · 滚轮缩放<br>"
    "双击画面吸到最近的正视图，再双击回到自由视角<br>"
    "有多间房时点上方房间名切换，地址栏 ?room= 直接指向某间房<br>"
    "退出会停掉后台预览服务，然后再关闭这个标签页"
)
_SHARE_TIPS = (
    "这是只读分享链接：只看不改，位置由房主那边更新。<br>"
    "空白处拖拽转视角 · 右键/中键/Shift+左键拖拽平移 · 滚轮缩放<br>"
    "双击画面吸到最近的正视图，再双击回到自由视角<br>"
    "有多间房时点上方房间名切换，地址栏 ?room= 直接指向某间房"
)
#: 可编辑的项目页（本机来源）——提示语要说清"什么时候要审、什么时候算数"。
_PROJECT_EDITOR_TIPS = (
    "拖动改位置（与别的家具或障碍物干涉、越出房间或遮挡门窗洞口时停在接触处）<br>"
    "选中件：橙点或旋转环改朝向 · 蓝点改离地高度 · 右侧也能直接输入<br>"
    "还没跑下游时，改动就落在**这一版**上（版号不变）；改到哪一间，哪一间就要重看一眼<br>"
    "空白处拖拽转视角 · 双击吸到最近的正视图 · 滚轮缩放<br>"
    "多间房时点上方房间名切换，地址栏 ?room= 直接指向某间房"
)
_SHUTDOWN_BUTTON = (
    '<button type="button" id="shutdown-preview">退出</button>'
)
# 页面身份的牌子：一眼说清「这一页能不能改、改了算不算数」。
# 预览页=只读投影，草稿页=可改但不进项目；两者都不写项目，写项目只走对话或确认流程。
# 分享形态（预览页带 ?mode=view）另加一块牌子：这页是给外人看的，转发链接即可。
# 注意：`?mode=view` 只是"表达"，不是权限——地址栏谁都能改，真正的门在服务端
# （`server.access_scope()`，见 runtime-contract「写权限」段）。
_PREVIEW_BADGE = "只读预览 · 由对话更新"
_DRAFT_BADGE = "草稿 · 不影响项目"
_SHARE_BADGE = "只读分享 · 链接可转发"
_PROJECT_EDIT_BADGE = "可直接拖动 · 无下游产物时改的是同一版"


def _render_canvas_html(
    *,
    scene_id: str,
    scene_payload: dict[str, Any],
    rooms: list[dict[str, Any]],
    version: str,
    read_only: bool,
    poll_url: str,
    heading_suffix: str,
    tips: str,
    app_label: str,
    mode_badge: str,
    shutdown_button: str,
    share_form: bool = False,
    edit_url: str = "",
    undo_url: str = "",
) -> str:
    room_name = str(scene_payload["room"]["name"])
    heading = f"{room_name} · {heading_suffix}"
    body_class = " ".join(
        name for name in ("readonly" if read_only else "", "share" if share_form else "") if name
    )
    return (
        _EDITOR_HTML.replace("__SCENE_JSON__", _json_for_script(scene_payload))
        .replace("__SCENE_ID__", escape(scene_id, quote=True))
        .replace("__HEADING__", escape(heading, quote=True))
        .replace("__HEADING_SUFFIX__", _json_for_script(heading_suffix))
        .replace("__MODE_BADGE__", escape(mode_badge, quote=True))
        .replace("__READ_ONLY__", "true" if read_only else "false")
        .replace("__SHARE_FORM__", "true" if share_form else "false")
        .replace("__POLL_URL__", _json_for_script(poll_url))
        .replace("__EDIT_URL__", _json_for_script(edit_url))
        .replace("__UNDO_URL__", _json_for_script(undo_url))
        .replace("__ROOMS_JSON__", _json_for_script(rooms))
        .replace("__VERSION_JSON__", _json_for_script(version))
        .replace("__BODY_CLASS__", body_class)
        .replace("__APP_LABEL__", escape(app_label, quote=True))
        .replace("__TIPS__", tips)
        .replace("__SHUTDOWN_BUTTON__", shutdown_button)
    )


def render_editor(scene_id: str, scene: RoomScene) -> dict[str, object]:
    """Return self-contained HTML that edits one saved room scene."""
    payload = editor_scene_payload(scene)
    html = _render_canvas_html(
        scene_id=scene_id,
        scene_payload=payload,
        rooms=[],
        version="",
        read_only=False,
        poll_url="",
        heading_suffix="布局编辑",
        tips=_EDITOR_TIPS,
        app_label="可编辑家具布局",
        mode_badge=_DRAFT_BADGE,
        shutdown_button="",
    )
    return {
        "media_type": "text/html",
        "view_kind": "editable_envelope",
        "scene_id": scene_id,
        "width_px": EDITOR_WIDTH_PX,
        "height_px": EDITOR_HEIGHT_PX,
        "controls": [
            "select_item",
            "drag_item",
            "drag_rotate_handle",
            "drag_height_handle",
            "front_orientation",
            "manual_distance_input",
            "manual_rotation_input",
            "view_transition",
            "dimension_readout",
            "item_size_readout",
            "view_elevation",
            "orthographic_view_select",
            "double_click_snap",
            "drag_orbit",
            "drag_pan",
            "wheel_zoom",
            "placement_stop",
        ],
        "alt_text": (
            f"{scene.room.name}的可编辑外形尺寸视图；点击家具外形尺寸任意位置可选中，"
            "拖动改位置（与别的家具或障碍物干涉、越出房间或遮挡门窗洞口时停在接触处），"
            "拖橙点或旋转环改朝向、拖蓝点改离地高度；"
            "每件的正面用绿色描边标出（约定：局部 +Y 为正面），选中件还有指向正面的箭头；"
            "选中件四周显示到最近邻的净距，并沿自身局部轴标出宽/深/高；"
            "净距、朝向、离地高度都能在右侧直接输入；"
            "视角从下拉里选正视图（俯视/仰视/前/后/左/右），「复位」回默认视角，"
            "双击画面吸到最近的正视图、再双击回到自由视角；"
            "空白处拖动转视角、右键或 Shift+左键拖动平移、滚轮缩放"
        ),
        "html": html,
    }


def render_project_preview(
    project_id: str,
    document: dict[str, Any],
    *,
    mode: str | None = None,
    read_only: bool = True,
) -> str:
    """Canvas for one project. The page polls `document` replacements.

    `read_only` 由**服务端按权限**决定（本机来源可编辑；其余只读），`mode="view"` 再强制只读。
    之所以不靠 URL 参数判权限：参数谁都能改（见 runtime-contract「写权限」段）。
    可编辑时页面还要自己拿到**编辑租约**才算真的能写——那是页面的事，见 workflow_lease.py。
    """
    rooms = list(document["rooms"])
    if not rooms:
        raise ValueError("project layout has no rooms")
    first = rooms[0]["scene"]
    if not isinstance(first, dict):
        raise ValueError("project room scene must be an object")
    share_form = mode == "view"
    if share_form:
        read_only = True
    return _render_canvas_html(
        scene_id=project_id,
        scene_payload=first,
        rooms=rooms,
        version=str(document["version"]),
        read_only=read_only,
        poll_url=f"/api/project/{project_id}/layout",
        edit_url=f"/api/project/{project_id}/layout/edit",
        undo_url=f"/api/project/{project_id}/layout/undo",
        heading_suffix="布局预览",
        tips=_SHARE_TIPS if share_form else (
            _PREVIEW_TIPS if read_only else _PROJECT_EDITOR_TIPS
        ),
        app_label="只读布局分享" if share_form else (
            "只读布局预览" if read_only else "可编辑家具布局"
        ),
        mode_badge=(
            _SHARE_BADGE if share_form
            else _PREVIEW_BADGE if read_only
            else _PROJECT_EDIT_BADGE
        ),
        shutdown_button="" if share_form else _SHUTDOWN_BUTTON,
        share_form=share_form,
    )


_EDITOR_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'">
<title>__HEADING__</title>
<style>
:root{
  --ink:#0f172a;--muted:#64748b;--line:#e2e8f0;--line-strong:#cbd5e1;
  --accent:#4f46e5;--accent-soft:#eef2ff;--amber:#f59e0b;--amber-ink:#b45309;
  --danger:#dc2626;--surface:#ffffff;--canvas:#eef1f6;
  font-family:Inter,"Microsoft YaHei",system-ui,-apple-system,"Segoe UI",sans-serif;
  color:var(--ink);
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:linear-gradient(180deg,#f7f9fc 0,#eef1f6 100%);padding:18px;display:flex;justify-content:center}
.app{width:min(1320px,100%);height:100%;display:grid;grid-template-rows:auto minmax(0,1fr);gap:14px}
.topbar{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;flex-wrap:wrap}
.titles h1{margin:0;font-size:21px;font-weight:700;letter-spacing:-.01em}
.titles p{margin:4px 0 0;font-size:12.5px;color:var(--muted);font-variant-numeric:tabular-nums}
.toolbar{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:6px;background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:4px;box-shadow:0 1px 2px rgba(15,23,42,.05)}
.toolbar button{appearance:none;border:0;background:transparent;color:var(--muted);border-radius:8px;padding:7px 11px;font:inherit;font-size:12.5px;font-weight:600;cursor:pointer;transition:background .12s,color .12s}
.toolbar button:hover{background:#f1f5f9;color:var(--ink)}
.toolbar button[aria-pressed="true"]{background:var(--accent);color:#fff;box-shadow:0 1px 3px rgba(79,70,229,.35)}
#shutdown-preview{margin-left:4px;color:#b91c1c}
#shutdown-preview:hover{background:#fef2f2;color:#b91c1c}
/* 房间切换：多间房时按一排小药丸，当前那间高亮；只有一间房时整条藏掉。 */
.room-band:not([hidden]){display:flex;align-items:center;flex-wrap:wrap;gap:4px;background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:4px;box-shadow:0 1px 2px rgba(15,23,42,.05)}
.room-band button{appearance:none;border:1px solid transparent;background:transparent;color:var(--muted);border-radius:8px;padding:7px 11px;font:inherit;font-size:12.5px;font-weight:600;cursor:pointer;transition:background .12s,color .12s,border-color .12s}
.room-band button:hover{background:#f1f5f9;color:var(--ink)}
.room-band button[aria-pressed="true"]{background:var(--accent-soft);border-color:#c7d2fe;color:#3730a3}
/* 还没审过的房间在药丸上带一个记号——"改一间只审一间"要看得见还差哪间。 */
.room-band button[data-pending="true"]{color:#b45309}
.room-band button[aria-pressed="true"][data-pending="true"]{color:#92400e;background:#fffbeb;border-color:#fcd34d}
/* 身份牌：这页是只读预览还是草稿，写在标题底下。 */
.mode-badge{margin:7px 0 0;display:inline-block;font-size:11.5px;font-weight:600;color:#475569;background:#f1f5f9;border:1px solid var(--line);border-radius:999px;padding:3px 10px}
body.readonly .mode-badge{color:#1d4ed8;background:#eff6ff;border-color:#bfdbfe}
/* 分享形态另给一种颜色：拿到链接的人一眼能看出这不是他自己那台机器上的页面。 */
body.share .mode-badge{color:#b45309;background:#fffbeb;border-color:#fcd34d}
/* 编辑租约：谁此刻在写这个项目（助手正在处理 / 另一窗口在编辑）。 */
.lease-badge{margin:6px 0 0;display:inline-block;font-size:11.5px;font-weight:600;color:#92400e;background:#fffbeb;border:1px solid #fcd34d;border-radius:999px;padding:3px 10px}
.lease-badge.mine{color:#065f46;background:#ecfdf5;border-color:#a7f3d0}
/* 工作副本状态：还没下游产物时改的是同一版（版号不变），这一点必须一直看得见。 */
.working-badge{margin:6px 0 0;display:inline-block;font-size:11.5px;font-weight:600;color:#5b21b6;background:#f5f3ff;border:1px solid #ddd6fe;border-radius:999px;padding:3px 10px}
.working-badge.closed{color:#475569;background:#f1f5f9;border-color:var(--line)}
#take-lease{color:#b45309}
.view-switch{display:flex;align-items:center;gap:8px;font-size:12.5px;font-weight:600;color:var(--muted)}
.view-switch select{border:1px solid var(--line);border-radius:8px;background:#fff;color:var(--ink);font:inherit;font-weight:600;padding:6px 8px}
/* 只读页没有编辑手柄，图例里对应的两行也藏掉——留着就是假广告。 */
body.readonly .legend [data-edit-only]{display:none}
.workspace{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:14px;min-height:0}
.stage{position:relative;height:100%;min-height:340px;border-radius:16px;overflow:hidden;background:var(--canvas);border:1px solid var(--line);box-shadow:0 1px 2px rgba(15,23,42,.05),0 18px 40px -26px rgba(15,23,42,.42)}
canvas{display:block;width:100%;height:100%;touch-action:none;cursor:default}
canvas.orbiting{cursor:grabbing}
canvas.moving{cursor:move}
canvas.panning{cursor:grabbing}
.toast{position:absolute;left:14px;bottom:14px;max-width:calc(100% - 28px);padding:8px 12px;border-radius:10px;background:rgba(255,255,255,.94);border:1px solid var(--line-strong);font-size:12.5px;color:#334155;box-shadow:0 4px 14px -6px rgba(15,23,42,.28);backdrop-filter:blur(8px);transition:border-color .12s,color .12s}
/* 光标坐标读数：贴着右下角，只读，不吃指针事件（免得挡住画布的拖拽命中）。 */
.coord{position:absolute;right:14px;bottom:14px;max-width:calc(100% - 28px);padding:8px 12px;border-radius:10px;background:rgba(255,255,255,.94);border:1px solid var(--line-strong);font-size:12.5px;color:#334155;box-shadow:0 4px 14px -6px rgba(15,23,42,.28);backdrop-filter:blur(8px);font-variant-numeric:tabular-nums;pointer-events:none}
.toast.warn{color:var(--amber-ink);border-color:#fcd34d;background:rgba(255,251,235,.96)}
.toast.error{color:#b91c1c;border-color:#fecaca;background:rgba(254,242,242,.96)}
.sidebar{display:flex;flex-direction:column;gap:12px;min-height:0;overflow:auto}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:13px 14px;box-shadow:0 1px 2px rgba(15,23,42,.04)}
.card h2{margin:0 0 10px;font-size:11px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:#94a3b8}
.list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:3px}
.item-row{width:100%;display:flex;align-items:center;gap:9px;appearance:none;border:1px solid transparent;background:transparent;border-radius:9px;padding:7px 9px;font:inherit;font-size:13px;color:#334155;cursor:pointer;text-align:left;transition:background .12s,border-color .12s}
.item-row:hover{background:#f8fafc}
.item-row.active{background:var(--accent-soft);border-color:#c7d2fe;color:#3730a3;font-weight:600}
.item-row .dot{width:9px;height:9px;border-radius:3px;background:#8ea9e8;box-shadow:inset 0 0 0 1px rgba(15,23,42,.14);flex:none}
.item-row.active .dot{background:var(--amber)}
.item-row .name{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.item-row .mode{font-size:10.5px;font-weight:600;color:#94a3b8;border:1px solid var(--line);border-radius:999px;padding:1px 7px;flex:none}
.item-row.active .mode{color:#6366f1;border-color:#c7d2fe;background:#fff}
.detail{margin:0;display:grid;grid-template-columns:auto 1fr;gap:6px 12px;font-size:12.5px;align-items:center}
.detail dt{color:var(--muted)}
.detail dd{margin:0;display:flex;align-items:center;justify-content:flex-end;gap:6px;text-align:right;font-variant-numeric:tabular-nums;font-weight:600}
.detail .who{color:#94a3b8;font-weight:500;font-size:11px}
.detail input.num{width:62px;border:1px solid var(--line);border-radius:7px;padding:3px 6px;font:inherit;font-size:12.5px;font-weight:600;text-align:right;color:var(--ink);font-variant-numeric:tabular-nums;background:#fff}
.detail input.num:hover{border-color:var(--line-strong)}
.detail input.num:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.stepper{display:inline-flex;align-items:center;justify-content:flex-end;gap:6px}
.step{appearance:none;border:1px solid var(--line);background:#fff;border-radius:6px;width:21px;height:21px;padding:0;font:inherit;font-size:13px;font-weight:700;line-height:1;color:#475569;cursor:pointer}
.step:hover{border-color:var(--accent);color:var(--accent);background:var(--accent-soft)}
.empty{margin:0;font-size:12.5px;color:#94a3b8}
.legend{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:7px;font-size:12.5px;color:#475569}
.legend li{display:flex;align-items:center;gap:9px}
.chip{width:14px;height:10px;border-radius:3px;flex:none;box-shadow:inset 0 0 0 1px rgba(15,23,42,.16)}
.chip.furniture{background:#8ea9e8}
.chip.selected{background:var(--amber)}
.chip.height{background:#3b82f6}
.chip.dim{background:#a78bfa}
.chip.size{background:#334155}
.chip.front{background:#047857}
.chip.obstacle{background:#e79a9a}
.chip.opening{background:#7dd3fc}
.chip.axes{background:#0f172a}
.tips{margin:11px 0 0;padding-top:10px;border-top:1px dashed var(--line);font-size:11.5px;line-height:1.7;color:#94a3b8}
.hint-inline{margin:8px 0 0;font-size:11.5px;color:#94a3b8;line-height:1.6}
@media (max-width:980px){.workspace{grid-template-columns:minmax(0,1fr)}.stage{min-height:420px}.app{height:auto}}
</style>
</head>
<body class="__BODY_CLASS__">
<main class="app" aria-label="__APP_LABEL__">
  <header class="topbar">
    <div class="titles">
      <h1 id="heading">__HEADING__</h1>
      <p id="room-meta"></p>
      <p class="mode-badge" id="mode-badge">__MODE_BADGE__</p>
      <p class="working-badge" id="working-badge" hidden></p>
      <p class="lease-badge" id="lease-badge" hidden></p>
    </div>
    <nav class="room-band" id="room-band" aria-label="房间切换" hidden></nav>
    <nav class="toolbar" aria-label="视角选择">
      <label class="view-switch">
        <select id="view-select" aria-label="正视图">
          <option value="free" disabled>自由视角</option>
          <option value="top">俯视</option>
          <option value="bottom">仰视</option>
          <option value="front">前视</option>
          <option value="back">后视</option>
          <option value="left">左视</option>
          <option value="right">右视</option>
        </select>
      </label>
      <button type="button" data-view="default_view" aria-pressed="true">复位</button>
      <button type="button" id="toggle-dims" aria-pressed="true">标注</button>
      <button type="button" id="take-lease" hidden>收回编辑权</button>
      __SHUTDOWN_BUTTON__
    </nav>
  </header>
  <div class="workspace">
    <section class="stage">
      <canvas id="scene" width="960" height="600" aria-label="房间与家具外形尺寸；点选家具后可拖动移动、拖橙点旋转、拖蓝点改离地高度"></canvas>
      <div class="toast" id="status">点击一件家具开始</div>
      <div class="coord" id="coord" hidden></div>
    </section>
    <aside class="sidebar">
      <section class="card">
        <h2>家具</h2>
        <ul class="list" id="item-list"></ul>
      </section>
      <section class="card">
        <h2>选中</h2>
        <div id="detail"><p class="empty">未选中任何家具</p></div>
      </section>
      <section class="card">
        <h2>图例</h2>
        <ul class="legend">
          <li><i class="chip furniture"></i>家具外形尺寸</li>
          <li data-edit-only><i class="chip selected"></i>选中 / 旋转环与手柄（橙）</li>
          <li data-edit-only><i class="chip height"></i>离地高度手柄（蓝）</li>
          <li><i class="chip dim"></i>净距标注线（紫）</li>
          <li><i class="chip size"></i>本体尺寸 宽/深/高（深灰）</li>
          <li><i class="chip front"></i>正面（绿边）</li>
          <li><i class="chip obstacle"></i>障碍物</li>
          <li><i class="chip opening"></i>门窗</li>
          <li><i class="chip axes"></i>房间原点与 X/Y/Z 轴（X 东 · Y 南 · Z 上）</li>
        </ul>
        <p class="tips">__TIPS__</p>
      </section>
    </aside>
  </div>
</main>
<script id="scene-data" type="application/json">__SCENE_JSON__</script>
<script type="importmap">
{"imports":{"three":"/vendor/three/0.186.0/three.module.js"}}
</script>
<script type="module">
import { mountLayout } from "/layout-view/layout_scene.js";
const SCENE_ID="__SCENE_ID__";
const READ_ONLY=__READ_ONLY__;
// 分享形态（预览页 ?mode=view）：只影响文案，不改权限。
const SHARE_FORM=__SHARE_FORM__;
// 项目页（服务端按权限渲染成可编辑）用这两个地址写回；草稿页写场景源，两者都空。
const PROJECT_EDIT_URL=__EDIT_URL__;
const PROJECT_UNDO_URL=__UNDO_URL__;
const POLL_URL=__POLL_URL__;
let rooms=__ROOMS_JSON__;
let layoutVersion=__VERSION_JSON__;
let roomIndex=0;
const scene=JSON.parse(document.getElementById("scene-data").textContent);
const normalizeItems=items=>items.map(item=>{
  const placement=item.placement||{};
  const zStart=item.z_start!==undefined?item.z_start:(placement.origin_z_mm||0);
  return {...item,placement,z_start:zStart,z_end:item.z_end!==undefined?item.z_end:zStart+(item.height||0),footprint:(item.footprint||[]).map(p=>Array.isArray(p)?[p[0],p[1]]:[p.x_mm,p.y_mm])};
});
scene.items=normalizeItems(scene.items||[]);
scene.obstacles=scene.obstacles||[];
scene.openings=scene.openings||[];
const canvas=document.getElementById("scene"),status=document.getElementById("status");
const view=mountLayout(canvas);
let placing=false;
let room=scene.room;
// 视图中心。平移是就地改它（相机的一切都相对它算）；切视角时动画回 HOME_TARGET。
let HOME_TARGET=[room.width_mm/2,room.depth_mm/2,room.height_mm*.42];
const target=[...HOME_TARGET];
let diagonal=Math.hypot(room.width_mm,room.depth_mm,room.height_mm);
function bindRoom(){
  room=scene.room;
  HOME_TARGET=[room.width_mm/2,room.depth_mm/2,room.height_mm*.42];
  diagonal=Math.hypot(room.width_mm,room.depth_mm,room.height_mm);
  const roomMeta=document.getElementById("room-meta");
  if(roomMeta){
    roomMeta.textContent=[`${Math.round(room.width_mm)} × ${Math.round(room.depth_mm)} × ${Math.round(room.height_mm)} mm`,
      `${scene.items.length} 件家具`].join(" · ");
  }
  const heading=document.getElementById("heading");
  if(heading){
    heading.textContent=(room.name||"房间")+" · "+__HEADING_SUFFIX__;
    document.title=heading.textContent;
  }
}
// 默认视角：正南偏东 15°（yaw=75°）看向北偏西，北墙几乎正对、仍留一点纵深；俯仰 0.35 rad（≈20°）。
const DEFAULT_YAW=Math.PI*5/12,DEFAULT_PITCH=.35;
// 立面视图把相机放到水平（pitch 0）并从四个方向看；前视=站在南边往北看，依此类推。
// 正视图预设：四个立面（pitch 0）+ 俯视/仰视（对称的 ±1.48，避开正好 90° 的退化）。
// default_view 是「复位」回到的那一眼，不是"正交/透视"之分——这张画布永远是透视投影。
const VIEWS={
  default_view:{yaw:DEFAULT_YAW,pitch:DEFAULT_PITCH},
  top:{yaw:Math.PI/2,pitch:1.48},
  bottom:{yaw:Math.PI/2,pitch:-1.48},
  front:{yaw:Math.PI/2,pitch:0},
  back:{yaw:-Math.PI/2,pitch:0},
  right:{yaw:0,pitch:0},
  left:{yaw:Math.PI,pitch:0},
};
const ORTHO_VIEWS=["top","bottom","front","back","left","right"];
const isOrthoView=name=>ORTHO_VIEWS.includes(name);
// 旧链接（书签、聊天记录里的 #view=perspective）继续能用。
const VIEW_ALIASES={perspective:"default_view"};
// 相机几乎与地面齐平时，地面射线求交会退化（交点跑到几万毫米外），
// 所以这个角度以下改成在竖直平面里拖：横向 = 该视图的水平轴，纵向 = 高度。
const ELEVATION_MAX_PITCH=.12;
let uiScale=1;
function fitCanvas(){view.resize();uiScale=1}
const px=css=>css*uiScale;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
function camera(){return view.basis()}
function projector(){
  return point=>view.project(point[0],point[1],point[2]||0);
}
function unprojectToGround(sx,sy){
  const rect=canvas.getBoundingClientRect();
  return view.ground(rect.left+sx,rect.top+sy);
}
function verticalPlaneScale(point){
  const cam=camera();
  const rel=[point[0]-cam.position[0],point[1]-cam.position[1],(point[2]||0)-cam.position[2]];
  const depth=rel[0]*cam.forward[0]+rel[1]*cam.forward[1]+rel[2]*cam.forward[2];
  const fov=48*Math.PI/180;
  return 2*Math.tan(fov/2)*Math.max(depth,1)/(canvas.clientHeight||600);
}
function screenPoint(event){
  const rect=canvas.getBoundingClientRect();
  return [event.clientX-rect.left,event.clientY-rect.top];
}
function withHomeCentre(run){
  const saved=[target[0],target[1],target[2]];
  target[0]=HOME_TARGET[0];target[1]=HOME_TARGET[1];target[2]=HOME_TARGET[2];
  try{return run()}finally{target[0]=saved[0];target[1]=saved[1];target[2]=saved[2]}
}

/* ---------- 摆放检查：与 placement_check.py / placement.py 逐条对应 ---------- */
const EPSILON_MM=1e-6;
// ranges_overlap
function rangesOverlap(a0,a1,b0,b1){return Math.min(a1,b1)>Math.max(a0,b0)+EPSILON_MM}
// polygons_overlap：SAT，底面正面积重叠，贴边接触放行。干涉还要再加上高度重叠。
function polygonsOverlap(first,second){
  for(const polygon of [first,second]){
    for(let index=0;index<polygon.length;index++){
      const point=polygon[index],next=polygon[(index+1)%polygon.length];
      const axis=[-(next[1]-point[1]),next[0]-point[0]];
      let minA=Infinity,maxA=-Infinity,minB=Infinity,maxB=-Infinity;
      for(const candidate of first){const value=candidate[0]*axis[0]+candidate[1]*axis[1];if(value<minA)minA=value;if(value>maxA)maxA=value}
      for(const candidate of second){const value=candidate[0]*axis[0]+candidate[1]*axis[1];if(value<minB)minB=value;if(value>maxB)maxB=value}
      if(maxA<=minB+EPSILON_MM||maxB<=minA+EPSILON_MM)return false;
    }
  }
  return true;
}
// footprint_span_on_wall：只有包络真的贴在那面墙上才算有跨度。
function spanOnWall(wall,footprint){
  const xs=footprint.map(point=>point[0]),ys=footprint.map(point=>point[1]);
  if(wall==="north"&&Math.min(...ys)<=EPSILON_MM)return[Math.min(...xs),Math.max(...xs)];
  if(wall==="east"&&Math.max(...xs)>=room.width_mm-EPSILON_MM)return[Math.min(...ys),Math.max(...ys)];
  if(wall==="south"&&Math.max(...ys)>=room.depth_mm-EPSILON_MM)return[room.width_mm-Math.max(...xs),room.width_mm-Math.min(...xs)];
  if(wall==="west"&&Math.min(...xs)<=EPSILON_MM)return[room.depth_mm-Math.max(...ys),room.depth_mm-Math.min(...ys)];
  return null;
}
// item_outside_room + obstacle_interferences + item_interferences + blocked_openings。
// 返回挡住这次移动的对象（用来提示和描边），放得下则返回 null。reason 决定状态栏用词。
function blockerAt(footprint,zStart,zEnd,ignoreId){
  const xs=footprint.map(point=>point[0]),ys=footprint.map(point=>point[1]);
  if(Math.min(...xs)<-EPSILON_MM||Math.max(...xs)>room.width_mm+EPSILON_MM
    ||Math.min(...ys)<-EPSILON_MM||Math.max(...ys)>room.depth_mm+EPSILON_MM){
    return{label:"房间边界",id:null,reason:"outside_room"};
  }
  for(const obstacle of scene.obstacles){
    if(rangesOverlap(zStart,zEnd,obstacle.z_start,obstacle.z_end)&&polygonsOverlap(footprint,obstacle.footprint)){
      return{label:obstacle.label||"障碍物",id:null,reason:"interference"};
    }
  }
  for(const other of scene.items){
    if(other.id===ignoreId)continue;
    if(rangesOverlap(zStart,zEnd,other.z_start,other.z_end)&&polygonsOverlap(footprint,other.footprint)){
      return{label:other.label,id:other.id,reason:"interference"};
    }
  }
  for(const opening of scene.openings){
    const span=spanOnWall(opening.wall,footprint);
    if(!span)continue;
    if(rangesOverlap(span[0],span[1],opening.offset_mm,opening.offset_mm+opening.width_mm)
      &&rangesOverlap(zStart,zEnd,opening.sill_height_mm,opening.sill_height_mm+opening.height_mm)){
      return{label:"门窗",id:null,reason:"blocked_opening"};
    }
  }
  return null;
}
function placementStop(blocker){
  if(!blocker)return "超出可放范围";
  if(blocker.reason==="outside_room")return "会越出房间";
  if(blocker.reason==="blocked_opening")return "会遮挡门窗洞口";
  return `会与 ${blocker.label} 干涉`;
}
function contactStop(blocker){
  if(blocker.reason==="outside_room")return "已停在房间边界";
  if(blocker.reason==="blocked_opening")return "再过去会遮挡门窗洞口";
  return `已与 ${blocker.label} 贴到接触，再过去会干涉`;
}
// 从 from（必须可用）朝 to 走，二分找最远的可用整数位置：过不去就停在接触处。
function resolveInteger(from,to,probe){
  const startBlocker=probe(from);
  if(startBlocker)return{value:from,blocker:startBlocker};
  if(from===to)return{value:from,blocker:null};
  const step=to>from?1:-1;
  const endBlocker=probe(to);
  if(!endBlocker)return{value:to,blocker:null};
  let low=from,high=to,blocker=endBlocker;
  while(Math.abs(high-low)>1){
    const middle=low+step*Math.floor(Math.abs(high-low)/2);
    const hit=probe(middle);
    if(hit){high=middle;blocker=hit}else{low=middle}
  }
  return{value:low,blocker};
}

function fitDistance(pitch,yaw){
  const aspect=(canvas.clientWidth||960)/Math.max(canvas.clientHeight||600,1);
  const vFov=48*Math.PI/180;
  const limit=Math.min(vFov,2*Math.atan(Math.tan(vFov/2)*aspect));
  const margin=pitch<ELEVATION_MAX_PITCH?1.15:1.25;
  return diagonal*0.5/Math.sin(limit/2)*margin;
}
function render(){
  placing=true;
  view.setView(state.yaw,state.pitch,state.distance,target);
  placing=false;
  view.sync(scene,{selectedId:state.selectedId,dims:state.dims,readOnly:READ_ONLY,blockedId:state.blocked});
  syncPanel();
}

function boxOf(footprint){
  const xs=footprint.map(point=>point[0]),ys=footprint.map(point=>point[1]);
  return{x0:Math.min(...xs),x1:Math.max(...xs),y0:Math.min(...ys),y1:Math.max(...ys)};
}
function distancesOf(item){
  const box=boxOf(item.footprint);
  const neighbours=[];
  for(const other of scene.items){
    if(other.id===item.id)continue;
    neighbours.push({label:other.label,box:boxOf(other.footprint),z0:other.z_start,z1:other.z_end});
  }
  for(const obstacle of scene.obstacles){
    neighbours.push({label:obstacle.label||"障碍物",box:boxOf(obstacle.footprint),z0:obstacle.z_start,z1:obstacle.z_end});
  }
  const result={};
  for(const dir of ["west","east","north","south"]){
    const horizontal=dir==="west"||dir==="east";
    let best=null;
    for(const other of neighbours){
      if(!rangesOverlap(item.z_start,item.z_end,other.z0,other.z1))continue;
      if(horizontal){
        if(!rangesOverlap(box.y0,box.y1,other.box.y0,other.box.y1))continue;
      }else{
        if(!rangesOverlap(box.x0,box.x1,other.box.x0,other.box.x1))continue;
      }
      let gap;
      if(dir==="west"){if(other.box.x1>box.x0+EPSILON_MM)continue;gap=box.x0-other.box.x1}
      else if(dir==="east"){if(other.box.x0<box.x1-EPSILON_MM)continue;gap=other.box.x0-box.x1}
      else if(dir==="north"){if(other.box.y1>box.y0+EPSILON_MM)continue;gap=box.y0-other.box.y1}
      else{if(other.box.y0<box.y1-EPSILON_MM)continue;gap=other.box.y0-box.y1}
      if(!best||gap<best.gap)best={gap,label:other.label};
    }
    const wallGap=dir==="west"?box.x0
      :dir==="east"?room.width_mm-box.x1
      :dir==="north"?box.y0
      :room.depth_mm-box.y1;
    result[dir]=best&&best.gap<=wallGap+EPSILON_MM?{gap:best.gap,label:best.label}
      :{gap:wallGap,label:"墙"};
  }
  return result;
}
function frontVector(item){
  const rad=(item.placement.rotation_z_deg||0)*Math.PI/180;
  return [-Math.sin(rad),Math.cos(rad)];
}
function frontCompass(item){
  const vector=frontVector(item),parts=[];
  if(vector[0]>0.38)parts.push("东");else if(vector[0]<-0.38)parts.push("西");
  if(vector[1]>0.38)parts.push("南");else if(vector[1]<-0.38)parts.push("北");
  return parts.join("")||"—";
}
function footprintCenter(item){
  const count=item.footprint.length||1;
  return [item.footprint.reduce((s,p)=>s+p[0],0)/count,item.footprint.reduce((s,p)=>s+p[1],0)/count];
}
// 与服务端 furniture_footprint 同一套定义：局部 (0,0)-(w,d) 经原点与 rotation_z_deg 变换。
function localFootprint(item,originX,originY,rotationDeg){
  const angle=rotationDeg*Math.PI/180,cosine=Math.cos(angle),sine=Math.sin(angle);
  return [[0,0],[item.width,0],[item.width,item.depth],[0,item.depth]].map(
    ([x,y])=>[originX+x*cosine-y*sine,originY+x*sine+y*cosine]
  );
}
// 屏幕角度增大时世界 rotation_z_deg 是增还是减，取决于相机朝向，开机时用一次数值探测定符号。
function rotationSign(center,height){
  const project=projector(camera()),probe=10*Math.PI/180,radius=Math.max(200,room.width_mm*.1);
  const origin=project([center[0],center[1],height]);
  const base=project([center[0]+radius,center[1],height]);
  const turned=project([center[0]+radius*Math.cos(probe),center[1]+radius*Math.sin(probe),height]);
  const a0=Math.atan2(base.y-origin.y,base.x-origin.x);
  const a1=Math.atan2(turned.y-origin.y,turned.x-origin.x);
  return a1>a0?1:-1;
}
function snapAngle(deg,step){return Math.round(deg/step)*step}
function normalizeAngle(deg){return ((deg%360)+360)%360}
function wallSign(wall){return {north:["x",1],east:["y",1],south:["x",-1],west:["y",-1]}[wall]||null}
function wallNormal(wall){return {north:[0,1],east:[-1,0],south:[0,-1],west:[1,0]}[wall]||null}
function wallLabel(wall){return {north:"北",east:"东",south:"南",west:"西"}[wall]||wall}
function openingLabel(kind){return {door:"门",window:"窗"}[kind]||kind}
function setStatus(text,kind){
  status.textContent=text;
  status.classList.toggle("warn",kind==="warn");
  status.classList.toggle("error",kind==="error");
}
function isElevation(){return state.pitch<ELEVATION_MAX_PITCH}
// 立面视图里屏幕横向对应哪个房间轴（由相机右向量决定），以及正负号。
function horizontalAxis(){
  const right=camera().right;
  const axis=Math.abs(right[0])>=Math.abs(right[1])?0:1;
  return{axis,sign:right[axis]>=0?1:-1};
}
function wallLength(wall){return wall==="north"||wall==="south"?room.width_mm:(wall==="east"||wall==="west"?room.depth_mm:0)}
function spanOf(footprint,axis){const values=footprint.map(point=>axis==="x"?point[0]:point[1]);return Math.max(...values)-Math.min(...values)}
// 落盘取整到整数毫米，所以拖动也在整数毫米上求解：预览 == 落盘值。
function anchorWallOffset(offset,probe){
  if(!probe(offset))return offset;
  for(const step of [1,-1,2,-2])if(!probe(offset+step))return offset+step;
  return null;
}
function anchorFreeCell(x,y,probe){
  if(!probe(x,y))return[x,y];
  for(const [dx,dy] of [[1,0],[-1,0],[0,1],[0,-1],[1,1],[-1,-1],[1,-1],[-1,1]]){
    if(!probe(x+dx,y+dy))return[x+dx,y+dy];
  }
  return null;
}
// 高度：0 到「层高 - 自身高度」之间，且不能和其他外形干涉。
function heightProbe(item,footprint){
  return z=>(z<0||z+item.height>room.height_mm+EPSILON_MM)
    ?{label:"层高",id:null,reason:"outside_room"}
    :blockerAt(footprint,z,z+item.height,item.id);
}
function setItemHeight(item,z){
  item.placement.origin_z_mm=z;
  item.z_start=z;item.z_end=z+item.height;
}
function applyLocalDrag(item,dx,dy){
  const placement=item.placement;
  if(placement.mode==="wall"){
    const sign=wallSign(placement.host_wall);
    if(!sign)return null;
    const axis=sign[0]==="x"?0:1;
    const maxOffset=Math.max(0,wallLength(placement.host_wall)-spanOf(drag.startFootprint,sign[0]));
    const at=offset=>drag.startFootprint.map(point=>{
      const next=[point[0],point[1]];
      next[axis]+=(offset-drag.startOffset)*sign[1];
      return next;
    });
    const probe=offset=>offset<0||offset>maxOffset
      ?{label:"墙尽头",id:null}
      :blockerAt(at(offset),item.z_start,item.z_end,item.id);
    const start=anchorWallOffset(Math.round(drag.startOffset),probe);
    if(start===null)return{label:"无处可移",id:null};
    const along=Math.round(axis===0?dx:dy)*sign[1];
    const target=clamp(start+along,0,maxOffset);
    const solved=resolveInteger(start,target,probe);
    placement.offset_mm=solved.value;
    item.footprint=at(solved.value);
    return solved.blocker;
  }
  const rotation=placement.rotation_z_deg||0;
  const at=(x,y)=>localFootprint(item,x,y,rotation);
  const probe=(x,y)=>blockerAt(at(x,y),item.z_start,item.z_end,item.id);
  const anchor=anchorFreeCell(Math.round(drag.startOrigin[0]),Math.round(drag.startOrigin[1]),probe);
  if(!anchor)return{label:"无处可移",id:null};
  const solvedX=resolveInteger(anchor[0],anchor[0]+Math.round(dx),(x)=>probe(x,anchor[1]));
  const solvedY=resolveInteger(anchor[1],anchor[1]+Math.round(dy),(y)=>probe(solvedX.value,y));
  placement.origin_x_mm=solvedX.value;placement.origin_y_mm=solvedY.value;
  item.footprint=at(solvedX.value,solvedY.value);
  return solvedX.blocker||solvedY.blocker;
}
// 立面视图的拖动：横向走该视图的水平轴，纵向走高度。求解顺序仍是先水平后高度。
function applyElevationDrag(item,dHoriz,dVert){
  const placement=item.placement,rotation=placement.rotation_z_deg||0;
  const baseZ=Math.round(drag.startZ);
  let blocker=null;
  if(placement.mode==="wall"){
    const sign=wallSign(placement.host_wall);
    const wallAxis=sign?(sign[0]==="x"?0:1):-1;
    if(sign&&wallAxis===drag.horizontal.axis){
      const maxOffset=Math.max(0,wallLength(placement.host_wall)-spanOf(drag.startFootprint,sign[0]));
      const at=offset=>drag.startFootprint.map(point=>{
        const next=[point[0],point[1]];
        next[wallAxis]+=(offset-drag.startOffset)*sign[1];
        return next;
      });
      const probe=offset=>offset<0||offset>maxOffset
        ?{label:"墙尽头",id:null}
        :heightProbe(item,at(offset))(baseZ);
      const start=anchorWallOffset(Math.round(drag.startOffset),probe);
      if(start!==null){
        const solved=resolveInteger(start,clamp(start+Math.round(dHoriz*drag.horizontal.sign)*sign[1],0,maxOffset),probe);
        placement.offset_mm=solved.value;
        item.footprint=at(solved.value);
        blocker=solved.blocker;
      }
    }
  }else{
    const at=(x,y)=>localFootprint(item,x,y,rotation);
    const probe=(x,y)=>heightProbe(item,at(x,y))(baseZ);
    const anchor=anchorFreeCell(Math.round(drag.startOrigin[0]),Math.round(drag.startOrigin[1]),probe);
    if(anchor){
      const want=Math.round(dHoriz*drag.horizontal.sign);
      const solved=drag.horizontal.axis===0
        ?resolveInteger(anchor[0],anchor[0]+want,x=>probe(x,anchor[1]))
        :resolveInteger(anchor[1],anchor[1]+want,y=>probe(anchor[0],y));
      const nx=drag.horizontal.axis===0?solved.value:anchor[0];
      const ny=drag.horizontal.axis===1?solved.value:anchor[1];
      placement.origin_x_mm=nx;placement.origin_y_mm=ny;
      item.footprint=at(nx,ny);
      blocker=solved.blocker;
    }
  }
  const zSolved=resolveInteger(baseZ,baseZ+Math.round(dVert),heightProbe(item,item.footprint));
  setItemHeight(item,zSolved.value);
  return blocker||zSolved.blocker;
}
// 旋转同样先算出候选包络，过不去就整帧不落地（停在上一格），不会穿过去再回弹。
function applyRotation(item,center,rotationDeg){
  const current=item.placement;
  const target=Math.round(normalizeAngle(rotationDeg)*10)/10;
  // 墙摆转到原角度就还是墙摆：别因为一点点拖动被吸附回原角，就悄悄脱离墙面。
  if(current.mode==="wall"&&normalizeAngle(target)===normalizeAngle(current.rotation_z_deg||0)){
    return{applied:false,blocker:null};
  }
  const angle=target*Math.PI/180,cosine=Math.cos(angle),sine=Math.sin(angle);
  const halfWidth=item.width/2,halfDepth=item.depth/2;
  let originX=Math.round(center[0]-(halfWidth*cosine-halfDepth*sine));
  let originY=Math.round(center[1]-(halfWidth*sine+halfDepth*cosine));
  let footprint=localFootprint(item,originX,originY,target);
  // 旋转会让包络扫出墙体（贴着墙的长柜尤甚）：按最小位移收回房间内，向外取整免得又出界。
  const xs=footprint.map(point=>point[0]),ys=footprint.map(point=>point[1]);
  const shiftX=clamp(0,-Math.min(...xs),room.width_mm-Math.max(...xs));
  const shiftY=clamp(0,-Math.min(...ys),room.depth_mm-Math.max(...ys));
  if(shiftX||shiftY){
    originX+=shiftX>0?Math.ceil(shiftX):Math.floor(shiftX);
    originY+=shiftY>0?Math.ceil(shiftY):Math.floor(shiftY);
    footprint=localFootprint(item,originX,originY,target);
  }
  const blocker=blockerAt(footprint,item.z_start,item.z_end,item.id);
  if(blocker)return{applied:false,blocker};
  const placement=item.placement;
  // 墙面的旋转由 host_wall 派生，转不动；要旋转就同一次 op 里改成自由摆放。
  placement.mode="free";placement.host_wall=null;placement.offset_mm=null;
  placement.origin_x_mm=originX;placement.origin_y_mm=originY;placement.rotation_z_deg=target;
  item.footprint=footprint;
  return{applied:true,blocker:null};
}
// 墙摆只有一个自由度（沿墙 offset）；把家具往房间内拖够远就转成自由摆放，
// 用当前派生原点当自由原点，位置不跳。
function detachToFree(activeDrag){
  const placement=activeDrag.item.placement;
  placement.mode="free";placement.host_wall=null;placement.offset_mm=null;
  placement.origin_x_mm=Math.round(activeDrag.startOrigin[0]);
  placement.origin_y_mm=Math.round(activeDrag.startOrigin[1]);
  placement.rotation_z_deg=placement.rotation_z_deg||0;
  activeDrag.item.footprint=localFootprint(activeDrag.item,placement.origin_x_mm,placement.origin_y_mm,placement.rotation_z_deg);
  setStatus(`${activeDrag.item.label} 已离开墙面，改为自由摆放`,"warn");
}
function selectHint(item){
  if(READ_ONLY)return `已选中 ${item.label}`;
  return item.placement.mode==="wall"
    ?`已选中 ${item.label}：沿墙拖动，向外拖可离开墙面`
    :`已选中 ${item.label}：拖动可移动`;
}
const escapeHtml=value=>String(value).replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
// 侧栏列表只在结构变化时重建。
let panelSignature=null;
function syncPanel(){
  const signature=scene.items.map(item=>`${item.id}:${item.label}:${item.placement.mode}`).join("|")+"#"+state.selectedId;
  const list=document.getElementById("item-list");
  if(list&&signature!==panelSignature){
    panelSignature=signature;
    list.innerHTML=scene.items.map(item=>`<li><button type="button" class="item-row${item.id===state.selectedId?" active":""}" data-item="${escapeHtml(item.id)}">
      <span class="dot"></span><span class="name">${escapeHtml(item.label)}</span>
      <span class="mode">${item.placement.mode==="wall"?"靠墙":"自由"}</span></button></li>`).join("");
  }
  syncDetail();
}
// 详情面板要显示的数值。单独拆出来，好让它能被直接测（DOM 那层只是把值填进去）。
// 坐标行：房间原点在西北角地面，X 向东、Y 向南。给这件家具占地的范围，
// 以及最靠西、最靠北那两条边到墙的距离——报数字改布局时两种说法都用得上。
function coordText(item){
  const xs=item.footprint.map(point=>point[0]),ys=item.footprint.map(point=>point[1]);
  const x0=Math.round(Math.min(...xs)),x1=Math.round(Math.max(...xs));
  const y0=Math.round(Math.min(...ys)),y1=Math.round(Math.max(...ys));
  return `X ${x0}~${x1} · Y ${y0}~${y1} mm（距西墙 ${x0} · 距北墙 ${y0}）`;
}
function detailValues(item){
  const gaps=distancesOf(item);
  const round=n=>Math.round(n);
  return {
    mode:item.placement.mode==="wall"?"靠墙":"自由",
    position:item.placement.mode==="wall"
      ?`沿${wallLabel(item.placement.host_wall)}墙 ${round(item.placement.offset_mm)} mm`
      :`X ${round(item.placement.origin_x_mm)} · Y ${round(item.placement.origin_y_mm)} mm`,
    rotation:round(normalizeAngle(item.placement.rotation_z_deg||0)),
    front:`前朝${frontCompass(item)}`,
    height:round(item.z_start),
    ceiling:round(room.height_mm-item.z_end),
    coord:coordText(item),
    gaps:{west:round(gaps.west.gap),east:round(gaps.east.gap),
      north:round(gaps.north.gap),south:round(gaps.south.gap)},
    who:{west:gaps.west.label,east:gaps.east.label,
      north:gaps.north.label,south:gaps.south.label},
  };
}
function detailMarkup(item){
  const round=n=>Math.round(n);
  // 输入框一律 step=1：原生上下箭头按 1 走，不会「先吸附到 10 的整数倍」——
  // 那是 HTML 规范里 type=number 微调按钮的行为（基准 0、step=10 时 192 → 200）。
  // 粗调用旁边的 − / ＋：净距 10、离地 50、朝向 15，点一下就是正好加这么多。
  // 只读页（项目预览）**不生成**这些控件：灰着留在那儿只会让人点一下发现没反应、又不说明原因。
  // 读数照样刷新——钩子挂在 <span> 上，applyDetailValues() 已按 tagName==="INPUT" 分支处理。
  const gapRow=(label,key)=>READ_ONLY
    ? `<dt>${label}</dt><dd><span data-gap="${key}"></span> mm<span class="who" data-who="${key}"></span></dd>`
    : `<dt>${label}</dt><dd><button type="button" class="step" data-gap-step="${key}" data-delta="-10" aria-label="${label}减 10">−</button><input class="num" type="number" step="1" data-gap="${key}" aria-label="${label}"><button type="button" class="step" data-gap-step="${key}" data-delta="10" aria-label="${label}加 10">＋</button><span class="who" data-who="${key}"></span></dd>`;
  const rotationRow=READ_ONLY
    ? `<span data-field="rotation"></span>°<span class="who" data-front></span>`
    : `<button type="button" class="step" data-rotation-step data-delta="-15" aria-label="逆时针 15°">−</button><input class="num" type="number" step="1" data-rotation data-field="rotation" aria-label="朝向角度"><button type="button" class="step" data-rotation-step data-delta="15" aria-label="顺时针 15°">＋</button><span class="who">°</span><span class="who" data-front></span>`;
  const heightRow=READ_ONLY
    ? `<span data-field="height"></span> mm`
    : `<button type="button" class="step" data-height="-50" aria-label="降低 50">−</button><input class="num" type="number" step="1" data-height-input data-field="height" aria-label="离地高度"><button type="button" class="step" data-height="50" aria-label="升高 50">＋</button><span class="who">mm</span>`;
  const hint=READ_ONLY
    ? `<p class="hint-inline">${SHARE_FORM
        ? "只读分享：这一页只能看，位置由房主那边更新。"
        : "只读预览：位置由对话更新；要自己拖，用草稿页。"}</p>`
    : `<p class="hint-inline">可以直接输入任意毫米值，回车生效。输入框的上下箭头走 1；旁边的 − / ＋ 走整数档（净距 10 · 离地 50 · 朝向 15）。到不了就只挪到能到的地方，并在左下角说明是越界、干涉还是遮挡门窗洞口。</p>`;
  return `<dl class="detail">
    <dt>名称</dt><dd>${escapeHtml(item.label)}</dd>
    <dt>尺寸</dt><dd>${round(item.width)}×${round(item.depth)}×${round(item.height)}</dd>
    <dt>摆放</dt><dd data-field="mode"></dd>
    <dt>位置</dt><dd data-field="position"></dd>
    <dt>坐标</dt><dd data-field="coord"></dd>
    <dt>朝向</dt><dd>${rotationRow}</dd>
    <dt>离地</dt><dd>${heightRow}</dd>
    <dt>离顶</dt><dd><span data-field="ceiling"></span> mm</dd>
    ${gapRow("西距","west")}${gapRow("东距","east")}${gapRow("北距","north")}${gapRow("南距","south")}
  </dl>
  ${hint}`;
}
// 只在换选中件时才重建 DOM，之后一律就地改值。
// 早先的做法是「焦点在面板里就整块不刷新」，结果点了 −/＋ 之后数字不跟着动，
// 改一边的净距另一边也不动——都是同一个毛病。
let detailItemId;
function syncDetail(){
  const detail=document.getElementById("detail");
  if(!detail)return;
  const item=scene.items.find(candidate=>candidate.id===state.selectedId);
  if(!item){
    if(detailItemId!==null){detailItemId=null;detail.innerHTML='<p class="empty">未选中任何家具</p>'}
    return;
  }
  if(detailItemId!==item.id){
    detailItemId=item.id;
    detail.innerHTML=detailMarkup(item);
  }
  applyDetailValues(detail,item,false);
}
// 就地刷新数值：正在输入的框不动（免得打断打字），其余（含东距/西距这种此消彼长的）
// 立刻跟着变。force=true 用于一次输入落定之后，把输入框校正成实际达到的值。
function applyDetailValues(detail,item,force){
  if(!detail.querySelector)return;
  const values=detailValues(item);
  const active=document.activeElement;
  const set=(selector,value)=>{
    const element=detail.querySelector(selector);
    if(!element)return;
    if(element===active&&!force)return;
    if(element.tagName==="INPUT")element.value=String(value);
    else element.textContent=String(value);
  };
  set('[data-field="mode"]',values.mode);
  set('[data-field="position"]',values.position);
  set('[data-field="coord"]',values.coord);
  set('[data-field="rotation"]',values.rotation);
  set('[data-front]',values.front);
  set('[data-field="height"]',values.height);
  set('[data-field="ceiling"]',values.ceiling);
  for(const key of ["west","east","north","south"]){
    set(`[data-gap="${key}"]`,values.gaps[key]);
    set(`[data-who="${key}"]`,values.who[key]);
  }
}
function selectItem(id){
  state.selectedId=id;state.blocked=null;
  const item=scene.items.find(candidate=>candidate.id===id);
  setStatus(item?selectHint(item):"点击一件家具开始");
  render();
}
function nudgeHeight(item,delta){
  if(READ_ONLY)return;
  const base=Math.round(item.placement.origin_z_mm||0);
  const solved=resolveInteger(base,base+delta,heightProbe(item,item.footprint));
  if(solved.value===base){setStatus(`离地高度已经是 ${base} mm，${delta>0?"再高":"再低"}${placementStop(solved.blocker)}`,"warn");return}
  setItemHeight(item,solved.value);
  render();
  persist(item,"move").then(()=>{render()});
}
// 借用拖动那套求解器：临时装一个 drag 上下文，求解完还原。
// 手动输入和拖动因此走的是同一条路径，不会出现「输入能到、拖动不能到」。
function withDragContext(item,run){
  const saved=drag;
  drag={item,startOrigin:[item.placement.origin_x_mm||0,item.placement.origin_y_mm||0],
    startOffset:item.placement.offset_mm||0,startZ:item.placement.origin_z_mm||0,
    startFootprint:item.footprint.map(point=>[...point])};
  try{return run()}finally{drag=saved}
}
// 手动填某一边的净距：把包络移到「相邻那面 + 输入值」，照样过摆放检查，
// 所以只会停在到得了的地方，不会把家具塞进邻居里。
function setGap(item,direction,value){
  if(READ_ONLY)return;
  const gap=distancesOf(item)[direction];
  const horizontal=direction==="west"||direction==="east";
  const sign=(direction==="west"||direction==="north")?1:-1;
  const delta=Math.round(sign*(value-gap.gap));
  if(!delta)return;
  if(item.placement.mode==="wall"){
    const wsign=wallSign(item.placement.host_wall);
    const wallAxis=wsign?(wsign[0]==="x"?0:1):-1;
    if((horizontal?0:1)!==wallAxis){
      setStatus("靠墙件只能改沿墙方向的距离；要改进深方向请先把它拖离墙面","warn");
      return;
    }
  }
  const blocker=withDragContext(item,()=>applyLocalDrag(item,horizontal?delta:0,horizontal?0:delta));
  render();
  const reached=Math.round(distancesOf(item)[direction].gap);
  if(blocker&&reached!==Math.round(value)){
    setStatus(`只挪到 ${reached} mm：${placementStop(blocker)}`,"warn");
  }
  persist(item,"move").then(()=>{render()});
}
function setRotationValue(item,degrees){
  if(READ_ONLY)return;
  const result=applyRotation(item,footprintCenter(item),degrees);
  render();
  if(!result.applied){
    if(result.blocker)setStatus(`转不过去：${placementStop(result.blocker)}`,"warn");
    return;
  }
  persist(item,"rotate").then(()=>{render()});
}
function setHeightValue(item,value){
  if(READ_ONLY)return;
  const base=Math.round(item.placement.origin_z_mm||0),target=Math.round(value);
  const solved=resolveInteger(base,target,heightProbe(item,item.footprint));
  setItemHeight(item,solved.value);
  render();
  if(solved.value===base){
    if(solved.value!==target)setStatus(`改不了：${placementStop(solved.blocker)}`,"warn");
    return;
  }
  if(solved.value!==target)setStatus(`只到 ${solved.value} mm：${placementStop(solved.blocker)}`,"warn");
  persist(item,"move").then(()=>{render()});
}
let drag=null;
canvas.addEventListener("pointerdown",event=>{
  const [sx,sy]=screenPoint(event);
  if(event.button===1||event.button===2)return;
  const picked=view.pick(event.clientX,event.clientY);
  const pickedItem=picked?scene.items.find(item=>item.id===picked.itemId):null;
  if(READ_ONLY){
    if(pickedItem){selectItem(pickedItem.id);return}
    state.selectedId=null;state.blocked=null;
    render();
    return;
  }
  if(picked&&picked.kind==="height"&&pickedItem){
    view.setEnabled(false);
    drag={kind:"height",item:pickedItem,startScreen:[sx,sy],moved:false,
      startZ:pickedItem.placement.origin_z_mm||0};
    canvas.classList.add("moving");
    setStatus(`离地高度 ${Math.round(pickedItem.z_start)} mm`);
    canvas.setPointerCapture(event.pointerId);
    return;
  }
  if(picked&&(picked.kind==="rotate"||picked.kind==="ring")&&pickedItem){
    view.setEnabled(false);
    const center=footprintCenter(pickedItem),height=(pickedItem.z_start+pickedItem.z_end)/2;
    const origin=projector()([center[0],center[1],height]);
    const startAngle=Math.atan2(sy-origin.y,sx-origin.x)*180/Math.PI;
    drag={kind:"rotate",item:pickedItem,center,height,origin,startAngle,lastAngle:startAngle,
      accumulated:0,moved:false,startScreen:[sx,sy],
      startRotation:pickedItem.placement.rotation_z_deg||0,startMode:pickedItem.placement.mode,
      sign:rotationSign(center,height)};
    canvas.classList.add("moving");
    setStatus(`旋转 ${pickedItem.label}…`);
    canvas.setPointerCapture(event.pointerId);
    return;
  }
  const ground=unprojectToGround(sx,sy);
  if(pickedItem&&picked.kind==="item"&&(ground||isElevation())){
    view.setEnabled(false);
    const placement=pickedItem.placement;
    state.selectedId=pickedItem.id;state.blocked=null;
    drag={kind:"move",item:pickedItem,ground,startScreen:[sx,sy],moved:false,
      startOrigin:[placement.origin_x_mm||0,placement.origin_y_mm||0],
      startOffset:placement.offset_mm||0,startZ:placement.origin_z_mm||0,
      horizontal:horizontalAxis(),elevation:isElevation(),
      startFootprint:pickedItem.footprint.map(point=>[...point])};
    if(placement.mode==="wall"&&!drag.elevation){
      const normal=wallNormal(placement.host_wall),project=projector(),center=footprintCenter(pickedItem);
      if(normal){
        const from=project([center[0],center[1],0]);
        const to=project([center[0]+normal[0]*300,center[1]+normal[1]*300,0]);
        const length=Math.hypot(to.x-from.x,to.y-from.y)||1;
        drag.perpScreen={x:(to.x-from.x)/length,y:(to.y-from.y)/length};
      }
    }
    canvas.classList.add("moving");
    setStatus(selectHint(pickedItem));
    render();
    canvas.setPointerCapture(event.pointerId);
    return;
  }
  state.selectedId=null;state.blocked=null;
  render();
},true);
canvas.addEventListener("pointermove",event=>{
  if(drag){
    const [sx,sy]=screenPoint(event);
    if(!drag.moved){
      if(Math.hypot(sx-drag.startScreen[0],sy-drag.startScreen[1])<px(4))return;
      drag.moved=true;
    }
    if(drag.kind==="height"){
      const scale=verticalPlaneScale([...footprintCenter(drag.item),(drag.item.z_start+drag.item.z_end)/2]);
      const wanted=Math.round(-(sy-drag.startScreen[1])*scale/(camera().up[2]||1));
      const base=Math.round(drag.startZ);
      const solved=resolveInteger(base,base+wanted,heightProbe(drag.item,drag.item.footprint));
      setItemHeight(drag.item,solved.value);
      setStatus(solved.blocker&&solved.value!==base
        ?`离地高度 ${solved.value} mm（已抵住 ${solved.blocker.label}）`
        :`离地高度 ${solved.value} mm`);
      render();
      return;
    }
    if(drag.kind==="rotate"){
      const angle=Math.atan2(sy-drag.origin.y,sx-drag.origin.x)*180/Math.PI;
      let delta=angle-drag.lastAngle;
      if(delta>180)delta-=360;
      if(delta<-180)delta+=360;
      drag.accumulated+=delta;drag.lastAngle=angle;
      const next=snapAngle(drag.startRotation+drag.sign*drag.accumulated,event.shiftKey?1:15);
      const result=applyRotation(drag.item,drag.center,next);
      if(result.applied){
        state.blocked=null;
        setStatus(`旋转 ${drag.item.label}：${Math.round(normalizeAngle(drag.item.placement.rotation_z_deg))}°${event.shiftKey?"（精细 1°）":""}`);
      }else if(result.blocker){
        state.blocked=result.blocker.id;
        setStatus(`转不过去：${placementStop(result.blocker)}`,"warn");
      }
      render();
      return;
    }
    if(drag.elevation){
      const scale=verticalPlaneScale([...footprintCenter(drag.item),(drag.item.z_start+drag.item.z_end)/2]);
      const blocker=applyElevationDrag(drag.item,(sx-drag.startScreen[0])*scale,-(sy-drag.startScreen[1])*scale);
      state.blocked=blocker?blocker.id:null;
      setStatus(blocker
        ?contactStop(blocker)
        :`${drag.item.label}：离地 ${Math.round(drag.item.z_start)} mm`);
      render();
      return;
    }
    if(drag.item.placement.mode==="wall"&&drag.perpScreen){
      const away=(sx-drag.startScreen[0])*drag.perpScreen.x+(sy-drag.startScreen[1])*drag.perpScreen.y;
      if(away>px(26))detachToFree(drag);
    }
    const ground=unprojectToGround(sx,sy);
    if(!ground)return;
    const moveX=ground[0]-drag.ground[0],moveY=ground[1]-drag.ground[1];
    const blocker=applyLocalDrag(drag.item,moveX,moveY);
    state.blocked=blocker?blocker.id:null;
    if(blocker)setStatus(contactStop(blocker),"warn");
    else setStatus(`拖动 ${drag.item.label}… 位移 ${Math.round(Math.hypot(moveX,moveY))} mm`);
    render();
    return;
  }
});
async function reload(){
  if(PROJECT_EDIT_URL){await refreshProjectDocument();return}
  try{
    const response=await fetch(`/api/room-scene/${encodeURIComponent(SCENE_ID)}`);
    if(!response.ok)return;
    const next=await response.json();
    scene.items=normalizeItems(next.items||[]);
  }catch(error){/* 回退失败时保留画面，状态栏已有提示 */}
}
// 项目页：把服务端文档换到画布上（保持相机与当前房间）。
function applyDocument(payload){
  if(payload.version!==undefined)layoutVersion=String(payload.version);
  if(payload.lease!==undefined)applyLease(payload.lease||null);
  if(payload.working)applyWorking(payload);
  if(!payload.rooms)return;
  rooms=payload.rooms;
  const currentId=scene.room&&scene.room.id;
  let index=rooms.findIndex(entry=>entry.id===currentId);
  if(index<0)index=0;
  showRoom(index,true);
}
async function refreshProjectDocument(){
  try{
    const response=await fetch(POLL_URL,{cache:"no-store",headers:{Accept:"application/json"}});
    if(!response.ok)return false;
    applyDocument(await response.json());
    return true;
  }catch(error){return false}
}
async function persist(item,kind){
  if(READ_ONLY)return false;
  if(PROJECT_EDIT_URL&&!leaseToken){
    setStatus("这一页现在只能看：编辑权不在你手上（点「收回编辑权」或等助手做完）","warn");
    return false;
  }
  const placement=item.placement,op={op:kind==="rotate"?"rotate":"move",item_id:item.id};
  if(kind==="rotate")op.rotation_z_deg=Math.round(normalizeAngle(placement.rotation_z_deg)*10)/10;
  if(placement.mode==="wall"){op.offset_mm=Math.round(placement.offset_mm)}
  else{op.mode="free";op.origin_x_mm=Math.round(placement.origin_x_mm);op.origin_y_mm=Math.round(placement.origin_y_mm)}
  // origin_z_mm 是 move 的共享字段，平面移动时顺带带上也不会互相干扰。
  if(kind!=="rotate")op.origin_z_mm=Math.round(placement.origin_z_mm||0);
  const url=PROJECT_EDIT_URL||`/api/room-scene/${encodeURIComponent(SCENE_ID)}/edit`;
  const headers={"Content-Type":"application/json"};
  if(leaseToken)headers["X-Edit-Lease"]=leaseToken;
  if(PROJECT_EDIT_URL)op.expected_version=layoutVersion;
  try{
    const response=await fetch(url,{method:"POST",headers,body:JSON.stringify(op)});
    if(!response.ok){
      const detail=await response.json().catch(()=>({}));
      await reportWriteFailure(response.status,detail,item);
      return false;
    }
    const next=await response.json();
    if(PROJECT_EDIT_URL){
      applyDocument(next);
      const working=next.working||{};
      setStatus(working.open===false
        ? `已保存 ${item.label}（这一版已有下游产物，改动落成了新一版）`
        : `已保存 ${item.label}（同一版，草稿中${working.ops?` · 已调整 ${working.ops} 次`:""}）`);
      return true;
    }
    scene.items=normalizeItems(next.items||[]);
    setStatus(`已保存 ${item.label}`);
    return true;
  }catch(error){
    setStatus("保存失败："+error,"error");
    await reload();
    return false;
  }
}
// 写失败要说清是哪一种：不许写 / 编辑权在别人手里 / 画面过期 / 这次改动本身不合法。
async function reportWriteFailure(status,detail,item){
  const raw=detail&&detail.detail!==undefined?detail.detail:detail;
  const message=typeof raw==="string"?raw:JSON.stringify(raw||status);
  if(status===423){
    setStatus("助手正在处理这个项目，你的这次改动没有保存；它做完就还给你","warn");
    await refreshProjectDocument();
    return;
  }
  if(status===409){
    const current=(raw&&raw.current_version)||"";
    const mineMoved=current&&layoutVersion&&current.split(":")[0]!==layoutVersion.split(":")[0];
    setStatus(mineMoved
      ? "布局已在别处更新（画面已为你刷新），刚才那次拖动没有保存"
      : "这一版刚被确认过，画面没变，请再拖一次","warn");
    await refreshProjectDocument();
    return;
  }
  if(status===403){setStatus("这一页没有写权限（分享或只读）","error");return}
  setStatus(`改动被拒绝，已回到原位：${message}`,"error");
  await reload();
}
canvas.addEventListener("pointerup",event=>{
  if(state.panning){
    state.panning=false;canvas.classList.remove("panning");
    canvas.releasePointerCapture(event.pointerId);
    return;
  }
  if(drag){
    const item=drag.item,moved=drag.moved,kind=drag.kind;
    // 没实际改动就不产生 op：吸附回原角度的旋转、没动过的高度都不要发。
    const unchanged=kind==="rotate"
      ?(item.placement.rotation_z_deg===drag.startRotation&&item.placement.mode===drag.startMode)
      :kind==="height"?Math.round(item.placement.origin_z_mm||0)===Math.round(drag.startZ)
      :false;
    drag=null;state.blocked=null;canvas.classList.remove("moving");
    view.setEnabled(true);
    canvas.releasePointerCapture(event.pointerId);
    if(moved&&!unchanged){persist(item,kind).then(()=>{render()})}
    else{setStatus(selectHint(item));render()}
    return;
  }
  view.setEnabled(true);
});
// 光标落点的房间坐标。原点在西北角地面、X 向东、Y 向南。
// 相机贴地（立面视图）时地面射线求交会退化，交点能跑到几万毫米外；拖动那边同样躲开这个角度，
// 这里就把读数藏起来，宁可不显示也不显示假坐标。指到房间很远以外也一样藏。
function updateCoordReadout(event){
  const box=document.getElementById("coord");
  if(!box)return;
  const [sx,sy]=screenPoint(event);
  const margin=Math.max(room.width_mm,room.depth_mm);
  const ground=isElevation()?null:unprojectToGround(sx,sy);
  if(!ground){box.hidden=true;return}
  const x=Math.round(ground[0]),y=Math.round(ground[1]);
  if(x<-margin||y<-margin||x>room.width_mm+margin||y>room.depth_mm+margin){box.hidden=true;return}
  const outside=x<0||y<0||x>room.width_mm||y>room.depth_mm;
  box.hidden=false;
  box.textContent=`X ${x} · Y ${y} · Z 0 mm　距西墙 ${x} · 距北墙 ${y}${outside?"（房间外）":""}`;
}
canvas.addEventListener("pointermove",updateCoordReadout);
canvas.addEventListener("pointerleave",()=>{
  const box=document.getElementById("coord");
  if(box)box.hidden=true;
});
canvas.addEventListener("pointercancel",()=>{drag=null;state.blocked=null;state.panning=false;canvas.classList.remove("moving","orbiting","panning")});
// 右键要用来平移，别弹系统菜单。
canvas.addEventListener("contextmenu",event=>event.preventDefault());
window.addEventListener("keydown",event=>{
  if(event.key==="Shift")view.setShiftPan(true);
  if(event.key==="Escape")selectItem(null);
  const item=scene.items.find(candidate=>candidate.id===state.selectedId);
  if(!item)return;
  if(event.key==="PageUp"){event.preventDefault();nudgeHeight(item,50)}
  if(event.key==="PageDown"){event.preventDefault();nudgeHeight(item,-50)}
});
window.addEventListener("keyup",event=>{if(event.key==="Shift")view.setShiftPan(false)});

window.addEventListener("resize",()=>{
  fitCanvas();
  if(!viewAnimation&&!state.adjusted)state.distance=fitDistance(state.pitch,state.yaw);
  render();
});
const nextFrame=typeof requestAnimationFrame==="function"
  ?requestAnimationFrame
  :callback=>setTimeout(()=>callback(Date.now()),16);
const cancelFrame=typeof cancelAnimationFrame==="function"?cancelAnimationFrame:clearTimeout;
let viewAnimation=0;
// 切视角做个短过渡：只插值 yaw/pitch/distance 和视图中心，500ms 内跑完就停，
// 不留常驻动画循环，所以只有切换那一瞬间在重画。系统开了「减少动态效果」就直接跳到位。
function animateView(goal,duration){
  cancelFrame(viewAnimation);viewAnimation=0;
  const reduce=typeof matchMedia==="function"&&matchMedia("(prefers-reduced-motion: reduce)").matches;
  const from={yaw:state.yaw,pitch:state.pitch,distance:state.distance,
    centre:[target[0],target[1],target[2]]};
  const to=goal.target||from.centre;
  if(reduce||duration<=0){
    state.yaw=goal.yaw;state.pitch=goal.pitch;state.distance=goal.distance;
    for(let i=0;i<3;i++)target[i]=to[i];
    render();return;
  }
  let deltaYaw=goal.yaw-from.yaw;
  while(deltaYaw>Math.PI)deltaYaw-=Math.PI*2;
  while(deltaYaw<-Math.PI)deltaYaw+=Math.PI*2;
  const started=Date.now();
  const ease=t=>t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
  const step=()=>{
    const t=Math.min(1,(Date.now()-started)/duration),k=ease(t);
    state.yaw=from.yaw+deltaYaw*k;
    state.pitch=from.pitch+(goal.pitch-from.pitch)*k;
    state.distance=from.distance+(goal.distance-from.distance)*k;
    for(let i=0;i<3;i++)target[i]=from.centre[i]+(to[i]-from.centre[i])*k;
    render();
    viewAnimation=t<1?nextFrame(step):0;
  };
  viewAnimation=nextFrame(step);
}
// 视角标识：下拉回答「在哪个正视图」，透视按钮回答「在不在默认透视位」。
// 转过角度之后既不是正视也不是默认位，下拉就显示「自由视角」——不能还挂着上一个正视图。
function syncViewControls(){
  const select=document.getElementById("view-select");
  if(select)select.value=isOrthoView(state.active)?state.active:"free";
  const button=document.querySelector('[data-view="default_view"]');
  if(button)button.setAttribute("aria-pressed",String(state.active==="default_view"));
}
function nearAngle(gap){
  return Math.abs(((gap+Math.PI)%(2*Math.PI)+2*Math.PI)%(2*Math.PI)-Math.PI);
}
// 双击时吸到最近的正视图：先看俯仰够不够陡（够陡就是俯视/仰视），否则按方位角取最近的立面。
function nearestOrthoView(){
  const threshold=.35;
  if(state.pitch>threshold)return"top";
  if(state.pitch<-threshold)return"bottom";
  let best="front",bestGap=Infinity;
  for(const name of ["front","back","left","right"]){
    const gap=nearAngle(state.yaw-VIEWS[name].yaw);
    if(gap<bestGap){bestGap=gap;best=name}
  }
  return best;
}
function updateActiveAfterRestore(){
  state.active=(Math.abs(state.yaw-VIEWS.default_view.yaw)<1e-3&&
    Math.abs(state.pitch-VIEWS.default_view.pitch)<1e-3)?"default_view":"free";
}
// 回到「进正视图之前那一眼」的相机；没记过就回默认透视。
function restoreFreeView(){
  const remembered=state.freeView;
  if(!remembered){setView("default_view");return}
  state.adjusted=false;
  animateView({
    yaw:remembered.yaw,pitch:remembered.pitch,distance:remembered.distance,
    target:[...remembered.target],
  },500);
  // animateView 会把相机挪回去，动画结束后才谈得上判断落在哪个标识上。
  window.setTimeout(()=>{updateActiveAfterRestore();syncViewControls()},520);
}
function setView(name){
  const preset=VIEWS[name];
  if(!preset)return;
  // 从自由/透视切进正视图时，先把当前这一眼记下来，双击时回到它。
  if(isOrthoView(name)&&!isOrthoView(state.active)){
    state.freeView={yaw:state.yaw,pitch:state.pitch,distance:state.distance,target:[...target]};
  }
  state.adjusted=false;
  state.active=name;
  // 取景按房间中心算，然后连中心一起动画回去——平移过的视角也能干净复位。
  const distance=withHomeCentre(()=>fitDistance(preset.pitch,preset.yaw))*
    (preset.pitch<ELEVATION_MAX_PITCH?1.04:1);
  animateView({yaw:preset.yaw,pitch:preset.pitch,distance,target:HOME_TARGET},500);
  syncViewControls();
}
document.querySelectorAll("[data-view]").forEach(button=>button.addEventListener("click",()=>setView(button.dataset.view)));
const viewSelect=document.getElementById("view-select");
if(viewSelect){
  viewSelect.addEventListener("change",()=>{
    const name=viewSelect.value;
    if(!VIEWS[name]){syncViewControls();return}
    setView(name);
  });
}
// 双击：自由/透视 → 吸到最近的正视图；已经在正视图上 → 回到进它之前那一眼。
canvas.addEventListener("dblclick",()=>{
  if(isOrthoView(state.active)){restoreFreeView();return}
  const nearest=nearestOrthoView();
  state.freeView={yaw:state.yaw,pitch:state.pitch,distance:state.distance,target:[...target]};
  setView(nearest);
});
const dimsButton=document.getElementById("toggle-dims");
if(dimsButton){
  dimsButton.addEventListener("click",()=>{
    state.dims=!state.dims;
    dimsButton.setAttribute("aria-pressed",String(state.dims));
    render();
  });
}
const itemList=document.getElementById("item-list");
if(itemList&&itemList.addEventListener){
  itemList.addEventListener("click",event=>{
    const target=event.target;
    const button=target&&target.closest?target.closest("[data-item]"):null;
    if(button)selectItem(button.dataset.item);
  });
}
const detailBox=document.getElementById("detail");
if(detailBox&&detailBox.addEventListener){
  detailBox.addEventListener("click",event=>{
    const target=event.target;
    const button=target&&target.closest?target.closest("button"):null;
    if(!button)return;
    const item=scene.items.find(candidate=>candidate.id===state.selectedId);
    if(!item)return;
    if(button.dataset.height!==undefined)nudgeHeight(item,Number(button.dataset.height));
    else if(button.dataset.gapStep)setGap(item,button.dataset.gapStep,
      distancesOf(item)[button.dataset.gapStep].gap+Number(button.dataset.delta));
    else if(button.dataset.rotationStep!==undefined)setRotationValue(item,
      Math.round(normalizeAngle(item.placement.rotation_z_deg||0))+Number(button.dataset.delta));
    else return;
    applyDetailValues(detailBox,item,true);
  });
  detailBox.addEventListener("change",event=>{
    const input=event.target;
    if(!input||!input.dataset)return;
    const item=scene.items.find(candidate=>candidate.id===state.selectedId);
    if(!item)return;
    const value=Number(input.value);
    if(!Number.isFinite(value))return;
    if(input.dataset.gap)setGap(item,input.dataset.gap,value);
    else if(input.dataset.rotation!==undefined)setRotationValue(item,value);
    else if(input.dataset.heightInput!==undefined)setHeightValue(item,value);
    else return;
    // 落定后把输入框校正到实际达到的值（可能因为被挡住而不等于输入）
    applyDetailValues(detailBox,item,true);
  });
}
bindRoom();
fitCanvas();
const defaults={yaw:DEFAULT_YAW,pitch:DEFAULT_PITCH,distance:fitDistance(DEFAULT_PITCH,DEFAULT_YAW)};
const state={...defaults,orbiting:false,panning:false,lastX:0,lastY:0,active:"default_view",selectedId:null,
  freeView:null,viewMoved:false,
  handle:null,heightHandle:null,rotateRing:null,blocked:null,adjusted:false,dims:true};
view.controls.addEventListener("start",()=>{
  state.orbiting=true;
  state._pose=view.readView();
  canvas.classList.add("orbiting");
});
view.controls.addEventListener("change",()=>{if(!placing)view.draw()});
view.controls.addEventListener("end",()=>{
  const pose=view.readView();
  const before=state._pose;
  state.yaw=pose.yaw;state.pitch=pose.pitch;state.distance=pose.distance;
  target[0]=pose.target[0];target[1]=pose.target[1];target[2]=pose.target[2];
  state.orbiting=false;state.panning=false;
  canvas.classList.remove("orbiting","panning");
  if(before&&(Math.abs(pose.yaw-before.yaw)>0.01||Math.abs(pose.pitch-before.pitch)>0.01)){
    state.active="free";syncViewControls();
  }
});
render();
// 一进来就把视角标识摆对：默认是透视位，下拉显示「自由视角」、透视按钮高亮。
syncViewControls();
// 深链：#view=front&item=desk 直接打开某个视角并选中某件；?room=<id>（写成 #room=<id> 也认）
// 直接打开某间房。链接可分享、可复现，所以切房间时也把地址栏里的 ?room= 跟着改。
function deepLinkParams(){
  const params=new URLSearchParams(typeof location!=="undefined"?location.search:"");
  if(typeof location!=="undefined"&&location.hash.length>1){
    new URLSearchParams(location.hash.slice(1)).forEach((value,key)=>{
      if(!params.has(key))params.set(key,value);
    });
  }
  return params;
}
const deepLink=deepLinkParams();
const deepLinkRoom=deepLink.get("room");
if(deepLinkRoom&&rooms){
  const wanted=rooms.findIndex(entry=>entry.id===deepLinkRoom);
  if(wanted>0)showRoom(wanted,false);
}
const deepLinkView=deepLink.get("view");
const deepLinkTarget=deepLinkView?(VIEW_ALIASES[deepLinkView]||deepLinkView):null;
if(deepLinkTarget&&VIEWS[deepLinkTarget])setView(deepLinkTarget);
const deepLinkItem=deepLink.get("item");
if(deepLinkItem&&scene.items.some(candidate=>candidate.id===deepLinkItem))selectItem(deepLinkItem);
function syncRoomUrl(){
  if(!rooms||rooms.length<2)return;
  const entry=rooms[roomIndex];
  if(!entry||!entry.id||typeof history==="undefined")return;
  try{
    const url=new URL(location.href);
    url.searchParams.set("room",entry.id);
    history.replaceState(null,"",url.toString());
  }catch(error){}
}
function syncRoomBand(){
  const band=document.getElementById("room-band");
  if(!band)return;
  if(!rooms||rooms.length<2){band.hidden=true;return}
  band.hidden=false;
  const signature=rooms.map(entry=>`${entry.id}:${entry.name}`).join("|");
  if(band.dataset.signature!==signature){
    band.dataset.signature=signature;
    band.innerHTML=rooms.map((entry,index)=>{
      // 逐间确认：还没审过的那间在药丸上标出来（"改一间只审一间"要看得见差哪间）。
      const pending=entry.approved===false?" · 待审":"";
      const pressed=index===roomIndex?' aria-pressed="true"':' aria-pressed="false"';
      const mark=entry.approved===false?' data-pending="true"':"";
      return `<button type="button" data-room-index="${index}"${pressed}${mark}>${escapeHtml(entry.name||entry.id)}${pending}</button>`;
    }).join("");
    return;
  }
  Array.from(band.querySelectorAll("button")).forEach(button=>{
    button.setAttribute("aria-pressed",Number(button.dataset.roomIndex)===roomIndex?"true":"false");
  });
}
function showRoom(index,keepCamera){
  if(!rooms||!rooms[index])return;
  roomIndex=index;
  const next=rooms[index].scene;
  scene.room=next.room;
  scene.items=normalizeItems(next.items||[]);
  scene.obstacles=next.obstacles||[];
  scene.openings=next.openings||[];
  bindRoom();
  if(!keepCamera){
    target[0]=HOME_TARGET[0];target[1]=HOME_TARGET[1];target[2]=HOME_TARGET[2];
    state.adjusted=false;
    state.yaw=DEFAULT_YAW;state.pitch=DEFAULT_PITCH;
    state.distance=fitDistance(DEFAULT_PITCH,DEFAULT_YAW);
    state.active="default_view";
    syncViewControls();
  }
  if(state.selectedId&&!scene.items.some(item=>item.id===state.selectedId)){
    state.selectedId=null;state.blocked=null;
  }
  panelSignature=null;
  detailItemId=undefined;
  syncRoomBand();
  syncRoomUrl();
  render();
}
function layoutVersionOf(payload){
  return String(payload.version||"");
}
// 编辑租约：同一时刻只有一个写者能动这个项目。页面这一侧只做两件事——
// **看得见**（谁在写）与**抢回来**（人永远抢得回来）。裁定在服务端，
// 见 references/runtime-contract.md「编辑租约」段。
const LEASE_URL=POLL_URL?POLL_URL.replace(/\/layout$/,"/edit-lease"):"";
const LEASE_TOKEN_KEY="dsh-edit-lease:"+SCENE_ID;
const LEASE_ID_KEY=LEASE_TOKEN_KEY+":id";
const LEASE_LABEL_KEY=LEASE_TOKEN_KEY+":label";
let leaseToken=sessionStorage.getItem(LEASE_TOKEN_KEY)||"";
let leaseId=sessionStorage.getItem(LEASE_ID_KEY)||"";
if(!sessionStorage.getItem(LEASE_LABEL_KEY)){
  sessionStorage.setItem(LEASE_LABEL_KEY,"窗口 "+Math.random().toString(16).slice(2,6));
}
const leaseLabel=sessionStorage.getItem(LEASE_LABEL_KEY);
// 工作副本：没有下游产物时改动原地生效（版号不变）——这句必须一直挂着，别让人以为版号变了。
function applyWorking(payload){
  const badge=document.getElementById("working-badge");
  if(!badge)return;
  const working=payload&&payload.working;
  if(!PROJECT_EDIT_URL||!working){badge.hidden=true;return}
  const revision=payload.revision_number?`第 ${payload.revision_number} 版 · `:"";
  badge.hidden=false;
  badge.classList.toggle("closed",working.open===false);
  badge.textContent=working.open===false
    ?`${revision}已有下游产物：改动会落成新一版`
    :`${revision}草稿中 · 同一版${working.ops?` · 已调整 ${working.ops} 次`:""}${READ_ONLY?"（只读）":""}`;
}
function applyLease(lease){
  const badge=document.getElementById("lease-badge");
  const button=document.getElementById("take-lease");
  if(!badge||!button)return;
  const mine=Boolean(lease&&leaseToken&&lease.id===leaseId);
  if(!lease){
    badge.hidden=true;badge.classList.remove("mine");button.hidden=true;return;
  }
  const who=lease.holder==="agent"?"助手正在处理":(mine?"编辑权在你手上":"另一窗口正在编辑");
  badge.textContent=`${who} · ${Math.round(lease.expires_in||0)} 秒后自动释放`;
  badge.hidden=false;
  badge.classList.toggle("mine",mine);
  // 助手拿着时给一个出口；自己拿着不用抢，分享形态不给外人这个按钮。
  button.hidden=SHARE_FORM||lease.holder!=="agent";
}
async function leasePost(path,body){
  const headers={"Content-Type":"application/json"};
  if(leaseToken)headers["X-Edit-Lease"]=leaseToken;
  return fetch(path,{method:"POST",cache:"no-store",headers,body:JSON.stringify(body)});
}
const takeLeaseButton=document.getElementById("take-lease");
if(takeLeaseButton){
  takeLeaseButton.addEventListener("click",async()=>{
    takeLeaseButton.disabled=true;
    try{
      const response=await fetch(LEASE_URL+"/takeover",{
        method:"POST",cache:"no-store",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({holder:"page",label:leaseLabel}),
      });
      if(!response.ok)throw new Error(response.status);
      const lease=await response.json();
      leaseToken=lease.token;leaseId=lease.id;
      sessionStorage.setItem(LEASE_TOKEN_KEY,leaseToken);
      sessionStorage.setItem(LEASE_ID_KEY,leaseId);
      applyLease(lease);
      setStatus("已收回编辑权：助手下次写入会被挡下");
    }catch(error){
      setStatus("收回失败："+error,"error");
    }finally{
      takeLeaseButton.disabled=false;
    }
  });
}
function heartbeatLease(){
  if(!leaseToken||!LEASE_URL)return;
  leasePost(LEASE_URL,{holder:"page",label:leaseLabel,token:leaseToken})
    .then(response=>(response&&response.ok?response.json():null))
    .then(lease=>{
      if(!lease)return;
      leaseId=lease.id;
      sessionStorage.setItem(LEASE_ID_KEY,leaseId);
      applyLease(lease);
    })
    .catch(()=>{});
}
if(LEASE_URL)setInterval(heartbeatLease,5000);
// 关页面就还回去；带 keepalive 让请求在卸载后仍能发出。
window.addEventListener("pagehide",()=>{
  if(!leaseToken||!LEASE_URL)return;
  try{
    fetch(LEASE_URL,{
      method:"DELETE",cache:"no-store",keepalive:true,
      headers:{"X-Edit-Lease":leaseToken},
    });
  }catch(error){}
});
async function pollLayout(){
  if(!POLL_URL)return;
  if(drag||state.orbiting||state.panning)return;
  try{
    const response=await fetch(POLL_URL,{cache:"no-store",headers:{Accept:"application/json"}});
    if(!response.ok)return;
    const payload=await response.json();
    // 租约与版本无关：助手接管或让出时布局一个字没变，也必须立刻显示出来。
    applyLease(payload.lease||null);
    applyWorking(payload);
    if(layoutVersionOf(payload)===layoutVersion)return;
    if(drag||state.orbiting||state.panning)return;
    layoutVersion=layoutVersionOf(payload);
    rooms=payload.rooms||[];
    const currentId=scene.room&&scene.room.id;
    let index=rooms.findIndex(entry=>entry.id===currentId);
    let keepCamera=true;
    if(index<0){index=0;keepCamera=false}
    showRoom(index,keepCamera);
  }catch(error){}
}
const roomBand=document.getElementById("room-band");
if(roomBand){
  roomBand.addEventListener("click",event=>{
    const button=event.target&&event.target.closest?event.target.closest("button[data-room-index]"):null;
    if(!button)return;
    const index=Number(button.dataset.roomIndex);
    if(!Number.isInteger(index)||!rooms||!rooms[index]||index===roomIndex)return;
    showRoom(index,false);
  });
}
syncRoomBand();
syncRoomUrl();
let pollTimer=0;
if(POLL_URL)pollTimer=setInterval(pollLayout,1000);
// ---------------------------------------------------------------- 项目页的编辑权
// 服务端按权限把这一页渲染成可编辑；能不能**真的写**由编辑租约说话（同一时刻只有一个写者）。
// 页面只负责：申请、心跳、闲置让出、被抢走/被收回时跟着变。
const IDLE_YIELD_SECONDS=300;
let lastInteraction=Date.now();
let idleYielded=false;
function markInteraction(){
  lastInteraction=Date.now();
  if(idleYielded&&PROJECT_EDIT_URL&&!READ_ONLY&&!leaseToken)acquireLease();
}
["pointerdown","keydown","wheel","pointermove"].forEach(name=>{
  window.addEventListener(name,markInteraction,{passive:true});
});
async function acquireLease(){
  if(!PROJECT_EDIT_URL||READ_ONLY||SHARE_FORM)return null;
  try{
    const response=await leasePost(LEASE_URL,{holder:"page",label:leaseLabel,token:leaseToken||undefined});
    if(response.status===423){
      const detail=await response.json().catch(()=>({}));
      applyLease(detail.detail&&detail.detail.holder?detail.detail:(detail.detail||null));
      idleYielded=false;
      return null;
    }
    if(!response.ok)return null;
    const lease=await response.json();
    leaseToken=lease.token;leaseId=lease.id;idleYielded=false;
    sessionStorage.setItem(LEASE_TOKEN_KEY,leaseToken);
    sessionStorage.setItem(LEASE_ID_KEY,leaseId);
    applyLease(lease);
    return lease;
  }catch(error){return null}
}
function idleGuard(){
  if(!PROJECT_EDIT_URL||READ_ONLY||SHARE_FORM)return;
  if(!leaseToken)return;
  if(Date.now()-lastInteraction<IDLE_YIELD_SECONDS*1000)return;
  // 闲置太久：把编辑权还回去，别让一个开着的标签页把项目占一整天。
  fetch(LEASE_URL,{method:"DELETE",cache:"no-store",headers:{"X-Edit-Lease":leaseToken}})
    .catch(()=>{});
  leaseToken="";idleYielded=true;
  sessionStorage.removeItem(LEASE_TOKEN_KEY);
  applyLease(null);
  setStatus("闲置太久，已让出编辑权 · 点一下就能拿回来");
}
if(PROJECT_EDIT_URL)setInterval(idleGuard,30000);
if(PROJECT_EDIT_URL&&!READ_ONLY){
  acquireLease().then(lease=>{
    if(lease)setStatus("可以直接拖动：还没有下游产物时，改动落在同一版上；改到哪一间，哪一间就要重看一眼");
  });
  refreshProjectDocument();
}
const shutdownButton=document.getElementById("shutdown-preview");
if(shutdownButton){
  shutdownButton.addEventListener("click",async()=>{
    shutdownButton.disabled=true;
    if(pollTimer)clearInterval(pollTimer);
    try{
      await fetch("/api/preview/shutdown",{method:"POST",cache:"no-store"});
      setStatus("预览服务已退出，可以关闭这个标签页");
      window.close();
    }catch(error){
      shutdownButton.disabled=false;
      setStatus("退出失败："+error,"error");
    }
  });
}
</script>
</body>
</html>
"""
