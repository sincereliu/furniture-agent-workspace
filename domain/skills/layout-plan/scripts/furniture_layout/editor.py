"""Generate an editable room-scene view.

点选一件家具后拖动：靠墙件沿墙滑动（发 `offset_mm`），自由件平面移动（发
`origin_x_mm`/`origin_y_mm`）。选中后家具上方有两个手柄——橙色圆点拖了是旋转
（发 `rotation_z_deg`），蓝色圆点拖了改离地高度（发 `origin_z_mm`）；墙摆的
旋转由 `host_wall` 派生，所以旋转墙摆会在同一个 op 里改成自由摆放。靠墙件往
房间内拖过阈值也会转成自由摆放。

相机是同一套轨道相机，除了透视/俯视，还有前/后/左/右四个立面视图。相机接近
水平（pitch 很小）时地面射线求交会退化，所以那种视角下拖动改成在「水平轴 +
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
    "空白处拖拽转视角 · 右键/中键/Shift+左键拖拽平移 · 滚轮缩放 · Esc 取消选中"
)

_PREVIEW_TIPS = (
    "只读预览，位置由对话更新。<br>"
    "空白处拖拽转视角 · 右键/中键/Shift+左键拖拽平移 · 滚轮缩放<br>"
    "有多间房时在上方切换，默认第一间<br>"
    "退出会停掉后台预览服务，然后再关闭这个标签页"
)
_SHUTDOWN_BUTTON = (
    '<button type="button" id="shutdown-preview">退出</button>'
)


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
    shutdown_button: str,
) -> str:
    room_name = str(scene_payload["room"]["name"])
    heading = f"{room_name} · {heading_suffix}"
    return (
        _EDITOR_HTML.replace("__SCENE_JSON__", _json_for_script(scene_payload))
        .replace("__SCENE_ID__", escape(scene_id, quote=True))
        .replace("__HEADING__", escape(heading, quote=True))
        .replace("__HEADING_SUFFIX__", _json_for_script(heading_suffix))
        .replace("__READ_ONLY__", "true" if read_only else "false")
        .replace("__POLL_URL__", _json_for_script(poll_url))
        .replace("__ROOMS_JSON__", _json_for_script(rooms))
        .replace("__VERSION_JSON__", _json_for_script(version))
        .replace("__BODY_CLASS__", "readonly" if read_only else "")
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
            "视角可选透视/俯视/前/后/左/右（切换带过渡），"
            "空白处拖动转视角、右键或 Shift+左键拖动平移、滚轮缩放"
        ),
        "html": html,
    }


def render_project_preview(
    project_id: str,
    document: dict[str, Any],
) -> str:
    """Read-only canvas for one project. The page polls `document` replacements."""
    rooms = list(document["rooms"])
    if not rooms:
        raise ValueError("project layout has no rooms")
    first = rooms[0]["scene"]
    if not isinstance(first, dict):
        raise ValueError("project room scene must be an object")
    return _render_canvas_html(
        scene_id=project_id,
        scene_payload=first,
        rooms=rooms,
        version=str(document["version"]),
        read_only=True,
        poll_url=f"/api/project/{project_id}/layout",
        heading_suffix="布局预览",
        tips=_PREVIEW_TIPS,
        app_label="布局预览",
        shutdown_button=_SHUTDOWN_BUTTON,
    )


_EDITOR_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'">
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
.room-switch:not([hidden]){display:flex;align-items:center;gap:8px;font-size:12.5px;font-weight:600;color:var(--muted)}
.room-switch select{border:1px solid var(--line);border-radius:8px;background:#fff;color:var(--ink);font:inherit;font-weight:600;padding:6px 8px}
body.readonly .detail input.num,body.readonly .detail .step{pointer-events:none;opacity:.72}
.workspace{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:14px;min-height:0}
.stage{position:relative;height:100%;min-height:340px;border-radius:16px;overflow:hidden;background:var(--canvas);border:1px solid var(--line);box-shadow:0 1px 2px rgba(15,23,42,.05),0 18px 40px -26px rgba(15,23,42,.42)}
canvas{display:block;width:100%;height:100%;touch-action:none;cursor:default}
canvas.orbiting{cursor:grabbing}
canvas.moving{cursor:move}
canvas.panning{cursor:grabbing}
.toast{position:absolute;left:14px;bottom:14px;max-width:calc(100% - 28px);padding:8px 12px;border-radius:10px;background:rgba(255,255,255,.94);border:1px solid var(--line-strong);font-size:12.5px;color:#334155;box-shadow:0 4px 14px -6px rgba(15,23,42,.28);backdrop-filter:blur(8px);transition:border-color .12s,color .12s}
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
    </div>
    <label class="room-switch" id="room-switch-wrap" hidden>房间
      <select id="room-switch" aria-label="房间"></select>
    </label>
    <nav class="toolbar" aria-label="视角选择">
      <button type="button" data-view="perspective" aria-pressed="true">透视</button>
      <button type="button" data-view="top" aria-pressed="false">俯视</button>
      <button type="button" data-view="front" aria-pressed="false">前视</button>
      <button type="button" data-view="back" aria-pressed="false">后视</button>
      <button type="button" data-view="left" aria-pressed="false">左视</button>
      <button type="button" data-view="right" aria-pressed="false">右视</button>
      <button type="button" data-view="reset" aria-pressed="false">复位</button>
      <button type="button" id="toggle-dims" aria-pressed="true">标注</button>
      __SHUTDOWN_BUTTON__
    </nav>
  </header>
  <div class="workspace">
    <section class="stage">
      <canvas id="scene" width="960" height="600" aria-label="房间与家具外形尺寸；点选家具后可拖动移动、拖橙点旋转、拖蓝点改离地高度"></canvas>
      <div class="toast" id="status">点击一件家具开始</div>
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
          <li><i class="chip selected"></i>选中 / 旋转环与手柄（橙）</li>
          <li><i class="chip height"></i>离地高度手柄（蓝）</li>
          <li><i class="chip dim"></i>净距标注线（紫）</li>
          <li><i class="chip size"></i>本体尺寸 宽/深/高（深灰）</li>
          <li><i class="chip front"></i>正面（绿边）</li>
          <li><i class="chip obstacle"></i>障碍物</li>
          <li><i class="chip opening"></i>门窗</li>
        </ul>
        <p class="tips">__TIPS__</p>
      </section>
    </aside>
  </div>
</main>
<script id="scene-data" type="application/json">__SCENE_JSON__</script>
<script>
(()=>{
"use strict";
const SCENE_ID="__SCENE_ID__";
const READ_ONLY=__READ_ONLY__;
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
const canvas=document.getElementById("scene"),ctx=canvas.getContext("2d"),status=document.getElementById("status");
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
const DEFAULT_YAW=-Math.PI/4,DEFAULT_PITCH=.95;
// 立面视图把相机放到水平（pitch 0）并从四个方向看；前视=站在南边往北看，依此类推。
const VIEWS={
  perspective:{yaw:DEFAULT_YAW,pitch:DEFAULT_PITCH},
  top:{yaw:-Math.PI/2,pitch:1.48},
  front:{yaw:Math.PI/2,pitch:0},
  back:{yaw:-Math.PI/2,pitch:0},
  right:{yaw:0,pitch:0},
  left:{yaw:Math.PI,pitch:0},
};
// 相机几乎与地面齐平时，地面射线求交会退化（交点跑到几万毫米外），
// 所以这个角度以下改成在竖直平面里拖：横向 = 该视图的水平轴，纵向 = 高度。
const ELEVATION_MAX_PITCH=.12;
let W=960,H=600,uiScale=1;
// 画布按设备像素比放大，线更锐利；阈值仍按 CSS 像素定义，用 px() 换算。
function fitCanvas(){
  const rect=canvas.getBoundingClientRect();
  const cssWidth=rect.width||960,cssHeight=rect.height||600;
  const ratio=Math.min(2,window.devicePixelRatio||1);
  W=Math.max(320,Math.round(cssWidth*ratio));
  H=Math.max(200,Math.round(cssHeight*ratio));
  canvas.width=W;canvas.height=H;
  uiScale=W/cssWidth;
}
const px=css=>css*uiScale;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const sub=(a,b)=>[a[0]-b[0],a[1]-b[1],a[2]-b[2]];
const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const norm=a=>{const n=Math.hypot(...a)||1;return a.map(v=>v/n)};
const midpoint=pts=>pts[0].map((_,i)=>pts.reduce((s,p)=>s+p[i],0)/pts.length);
const focal=()=>H/(2*Math.tan(48*Math.PI/360));
function camera(distance,pitch,yaw){
  const p=pitch===undefined?state.pitch:pitch,y=yaw===undefined?state.yaw:yaw;
  const d=distance===undefined?state.distance:distance;
  const cp=Math.cos(p),sp=Math.sin(p),cy=Math.cos(y),sy=Math.sin(y);
  const position=[target[0]+d*cp*cy,target[1]+d*cp*sy,target[2]+d*sp];
  const forward=norm(sub(target,position)),right=norm(cross(forward,[0,0,1])),up=norm(cross(right,forward));
  return{position,forward,right,up};
}
function projector(cam){
  const f=focal();
  return point=>{const rel=sub(point,cam.position),depth=dot(rel,cam.forward);return{x:W/2+dot(rel,cam.right)/depth*f,y:H/2-dot(rel,cam.up)/depth*f,depth}};
}
function unprojectToGround(sx,sy){
  const cam=camera(),f=focal();
  const ax=(sx-W/2)/f,ay=-(sy-H/2)/f;
  const dir=norm([
    cam.forward[0]+cam.right[0]*ax+cam.up[0]*ay,
    cam.forward[1]+cam.right[1]*ax+cam.up[1]*ay,
    cam.forward[2]+cam.right[2]*ax+cam.up[2]*ay,
  ]);
  if(Math.abs(dir[2])<1e-6)return null;
  const t=-cam.position[2]/dir[2];
  if(!(t>0))return null;
  return [cam.position[0]+dir[0]*t,cam.position[1]+dir[1]*t];
}
// 竖直平面拖动：屏幕位移按该点的透视尺度换算成毫米。
// 屏幕 y 变小 = 往上 = z 变大，所以取负号。
function verticalPlaneScale(point){
  const depth=projector(camera())(point).depth;
  return depth/focal();
}
function screenPoint(event){
  const rect=canvas.getBoundingClientRect();
  return [(event.clientX-rect.left)*(W/rect.width),(event.clientY-rect.top)*(H/rect.height)];
}
// 平视时按屏幕像素换算成毫米，拖动才和画面 1:1。
// 中心沿相机的右/上方向走，所以任何视角下都是「往哪拖、画面往哪走」。
function panBy(dxCss,dyCss){
  const cam=camera(),per=uiScale*state.distance/focal();
  for(let i=0;i<3;i++)target[i]+=(-cam.right[i]*dxCss+cam.up[i]*dyCss)*per;
}
// 取景要按房间中心算，否则平移过之后会把房间框到画外。
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

function boxVertices(box){const b=box.footprint.map(p=>[p[0],p[1],box.z_start]),t=box.footprint.map(p=>[p[0],p[1],box.z_end]);return[...b,...t]}
const boxFaces=[[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]];
const boxFaceAlpha=[.55,.95,.82,.72,.88,.76];
const roomFaces=[[0,1,2,3],[4,7,6,5],[0,4,5,1],[1,5,6,2],[2,6,7,3],[3,7,4,0]];
const roomEdges=[[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
const FURNITURE="#7d9ae0",OBSTACLE="#dd8f8f";
function visible(face,verts,cam){const a=verts[face[0]],b=verts[face[1]],c=verts[face[2]],normal=cross(sub(b,a),sub(c,b));return dot(normal,sub(cam.position,midpoint(face.map(i=>verts[i]))))>0}
function path(points){ctx.beginPath();ctx.moveTo(points[0].x,points[0].y);for(const p of points.slice(1))ctx.lineTo(p.x,p.y);ctx.closePath()}
function roomVertices(){const w=room.width_mm,d=room.depth_mm,h=room.height_mm;return[[0,0,0],[w,0,0],[w,d,0],[0,d,0],[0,0,h],[w,0,h],[w,d,h],[0,d,h]]}
// 取景：二分出把整个房间装进画面（留 20% 余量，给手柄和墙面留空间）的最小距离，
// 窗口尺寸/房间比例/视角都不用手调。深度 <= 0 表示角点跑到相机后面，投影会翻号
// 变垃圾值，必须直接判为「装不下」，否则二分会被这种假的小跨度骗到相机贴脸。
function roomFits(distance,pitch,yaw){
  const cam=camera(distance,pitch,yaw),project=projector(cam),verts=roomVertices();
  let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;
  for(const vertex of verts){
    const rel=sub(vertex,cam.position);
    if(dot(rel,cam.forward)<=1)return false;
    const p=project(vertex);
    minX=Math.min(minX,p.x);maxX=Math.max(maxX,p.x);
    minY=Math.min(minY,p.y);maxY=Math.max(maxY,p.y);
  }
  return (maxX-minX)/W<=.8&&(maxY-minY)/H<=.8;
}
function fitDistance(pitch,yaw){
  let low=diagonal*.4,high=diagonal*3;
  for(let i=0;i<44;i++){
    const mid=(low+high)/2;
    if(roomFits(mid,pitch,yaw))high=mid;else low=mid;
  }
  return high;
}
function openingPoints(o){const s=o.offset_mm,e=s+o.width_mm,z0=o.sill_height_mm,z1=z0+o.height_mm,w=room.width_mm,d=room.depth_mm;if(o.wall==="north")return[[s,0,z0],[e,0,z0],[e,0,z1],[s,0,z1]];if(o.wall==="east")return[[w,s,z0],[w,e,z0],[w,e,z1],[w,s,z1]];if(o.wall==="south")return[[w-s,d,z0],[w-e,d,z0],[w-e,d,z1],[w-s,d,z1]];return[[0,d-s,z0],[0,d-e,z0],[0,d-e,z1],[0,d-s,z1]]}
function gridStep(){
  const longest=Math.max(room.width_mm,room.depth_mm);
  for(const step of [200,250,500,1000,2000])if(longest/step<=14)return step;
  return 5000;
}
function drawBackdrop(){
  const gradient=ctx.createLinearGradient(0,0,0,H);
  gradient.addColorStop(0,"#f9fbfd");gradient.addColorStop(1,"#e7ecf3");
  ctx.fillStyle=gradient;ctx.fillRect(0,0,W,H);
}
function drawFloor(project){
  const w=room.width_mm,d=room.depth_mm;
  const quad=()=>path([[0,0],[w,0],[w,d],[0,d]].map(point=>project([point[0],point[1],0])));
  quad();
  const gradient=ctx.createLinearGradient(0,H*.12,0,H*.96);
  gradient.addColorStop(0,"#ffffff");gradient.addColorStop(1,"#eef2f7");
  ctx.fillStyle=gradient;ctx.fill();
  ctx.save();quad();ctx.clip();
  const step=gridStep();
  ctx.strokeStyle="rgba(148,163,184,.45)";ctx.lineWidth=1;
  for(let x=step;x<w;x+=step){const a=project([x,0,0]),b=project([x,d,0]);ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke()}
  for(let y=step;y<d;y+=step){const a=project([0,y,0]),b=project([w,y,0]);ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke()}
  ctx.restore();
  quad();
  ctx.strokeStyle="rgba(100,116,139,.50)";ctx.lineWidth=px(1.4);ctx.stroke();
}
// roomFaces[2..5] 依次是北/东/南/西墙，法线朝房间内。透视视角下只画远端那两面，
// 免得近墙在家具前面盖一层灰罩；立面视图里相机在房间外侧水平看，改画「正对相机」
// 那一面（也就是能看到内表面的那面墙），房间才立得起来。
const wallFaces={north:2,east:3,south:4,west:5};
function drawWalls(project,cam){
  const verts=roomVertices();
  const elevation=isElevation();
  const shown=Object.entries(wallFaces).filter(([,i])=>visible(roomFaces[i],verts,cam)).map(([name])=>name);
  const farWalls=new Set(shown);
  const faces=roomFaces.slice(2).filter(face=>visible(face,verts,cam))
    .map(face=>({face,depth:face.reduce((s,i)=>s+project(verts[i]).depth,0)/face.length}))
    .sort((a,b)=>b.depth-a.depth);
  for(const entry of faces){
    path(entry.face.map(index=>project(verts[index])));
    ctx.fillStyle="rgba(148,163,184,.16)";ctx.fill();
  }
  for(const opening of scene.openings){
    const corners=openingPoints(opening);
    if(!farWalls.has(opening.wall)){
      // 近端/侧向的门窗画成墙脚的粗虚线 + 名目，像平面图的洞口标注：看得见，又不盖住家具。
      const a=project(corners[0]),b=project(corners[1]);
      ctx.setLineDash([px(7),px(5)]);
      ctx.strokeStyle="rgba(2,132,199,.75)";ctx.lineWidth=px(3);
      ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
      ctx.setLineDash([]);
      ctx.font=`700 ${Math.round(px(12))}px "Microsoft YaHei",system-ui,sans-serif`;
      ctx.textAlign="center";ctx.textBaseline="middle";
      ctx.lineWidth=px(3.5);ctx.strokeStyle="rgba(255,255,255,.92)";
      ctx.strokeText(openingLabel(opening.kind),(a.x+b.x)/2,(a.y+b.y)/2);
      ctx.fillStyle="#0369a1";
      ctx.fillText(openingLabel(opening.kind),(a.x+b.x)/2,(a.y+b.y)/2);
    }else{
      path(corners.map(project));
      ctx.fillStyle="rgba(125,211,252,.34)";ctx.fill();
      ctx.strokeStyle="rgba(2,132,199,.7)";ctx.lineWidth=px(1.5);ctx.stroke();
    }
  }
  ctx.strokeStyle="rgba(100,116,139,.45)";ctx.lineWidth=px(1.3);
  for(const edge of roomEdges){
    const a=project(verts[edge[0]]),b=project(verts[edge[1]]);
    ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
  }
  if(elevation){
    // 立面视图没有地面网格可参照，给个地脚线，房间才不像悬空。
    const floor=[[0,0,0],[room.width_mm,0,0],[room.width_mm,room.depth_mm,0],[0,room.depth_mm,0]].map(v=>project(v));
    path(floor);
    ctx.strokeStyle="rgba(100,116,139,.6)";ctx.lineWidth=px(1.8);ctx.stroke();
  }
}
function drawShadows(project){
  if(isElevation())return;
  for(const box of scene.items){
    path(box.footprint.map(point=>project([point[0],point[1],0])));
    ctx.fillStyle=box.id===state.selectedId?"rgba(180,83,9,.16)":"rgba(15,23,42,.10)";
    ctx.fill();
  }
}
function drawSolids(project,cam){
  const faces=[];
  const push=(box,base,selected,blocked,markFront)=>{
    const verts=boxVertices(box);
    boxFaces.forEach((face,index)=>{
      if(!visible(face,verts,cam))return;
      // boxFaces[4] = [2,3,7,6]，两边正是 footprint[2]→[3]，
      // 也就是局部 +Y 那条边——正面。给家具的正面换个描边色。
      const front=markFront&&index===4;
      faces.push({
        points:face.map(i=>project(verts[i])),
        depth:face.reduce((s,i)=>s+project(verts[i]).depth,0)/face.length,
        fill:base,alpha:boxFaceAlpha[index],
        stroke:blocked?"#dc2626":front?"#047857":(selected?"#b45309":"rgba(30,41,79,.55)"),
        width:blocked?px(2.4):front?px(2.6):(selected?px(2.4):px(1.2)),
      });
    });
  };
  for(const obstacle of scene.obstacles)push(obstacle,OBSTACLE,false,false,false);
  for(const box of scene.items)push(box,FURNITURE,box.id===state.selectedId,box.id===state.blocked,true);
  faces.sort((a,b)=>b.depth-a.depth);
  for(const face of faces){
    path(face.points);
    ctx.globalAlpha=face.alpha;ctx.fillStyle=face.fill;ctx.fill();ctx.globalAlpha=1;
    ctx.strokeStyle=face.stroke;ctx.lineWidth=face.width;ctx.stroke();
  }
  // 正面也可能背对相机：再在正面那侧的墙脚补一条绿线，任何角度都看得出正面对哪。
  ctx.strokeStyle="#047857";ctx.lineWidth=px(2.4);ctx.lineCap="round";
  for(const box of scene.items){
    const a=project([box.footprint[2][0],box.footprint[2][1],box.z_start]);
    const b=project([box.footprint[3][0],box.footprint[3][1],box.z_start]);
    ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
  }
  ctx.lineCap="butt";
  ctx.font=`700 ${Math.round(px(15))}px "Microsoft YaHei",system-ui,sans-serif`;
  ctx.textAlign="center";ctx.textBaseline="middle";
  for(const f of scene.items){
    const center=footprintCenter(f),p=project([center[0],center[1],(f.z_start+f.z_end)/2]);
    ctx.lineWidth=px(4);ctx.strokeStyle="rgba(15,23,42,.72)";ctx.strokeText(f.label,p.x,p.y);
    ctx.fillStyle="#fff";ctx.fillText(f.label,p.x,p.y);
  }
}
/* ---------- 净距：到最近邻（或墙）的四向标注 ---------- */
// 先在同一高度带里、垂直方向有重叠的邻居中找最近的一件；没有才退到墙。
// 与房间净距（clearances）同一套矩形口径，标注线才好读。
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
function drawDimensions(project){
  if(!state.dims)return;
  const item=scene.items.find(candidate=>candidate.id===state.selectedId);
  if(!item)return;
  const gaps=distancesOf(item),box=boxOf(item.footprint);
  const midX=(box.x0+box.x1)/2,midY=(box.y0+box.y1)/2;
  const specs=[
    [box.x0,midY,box.x0-gaps.west.gap,midY,true],
    [box.x1,midY,box.x1+gaps.east.gap,midY,true],
    [midX,box.y0,midX,box.y0-gaps.north.gap,false],
    [midX,box.y1,midX,box.y1+gaps.south.gap,false],
  ];
  const values=[gaps.west,gaps.east,gaps.north,gaps.south];
  ctx.font=`700 ${Math.round(px(11.5))}px "Microsoft YaHei",system-ui,sans-serif`;
  ctx.textAlign="center";ctx.textBaseline="middle";
  specs.forEach((spec,index)=>{
    const a=project([spec[0],spec[1],0]),b=project([spec[2],spec[3],0]);
    const vertical=spec[4];
    ctx.strokeStyle="rgba(124,58,237,.85)";ctx.lineWidth=px(1.4);
    ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
    const tick=px(4.5);
    for(const p of [a,b]){
      ctx.beginPath();
      if(vertical){ctx.moveTo(p.x,p.y-tick);ctx.lineTo(p.x,p.y+tick)}
      else{ctx.moveTo(p.x-tick,p.y);ctx.lineTo(p.x+tick,p.y)}
      ctx.stroke();
    }
    const label=String(Math.round(values[index].gap));
    const lx=(a.x+b.x)/2,ly=(a.y+b.y)/2-px(10);
    ctx.lineWidth=px(3.5);ctx.strokeStyle="rgba(255,255,255,.95)";
    ctx.strokeText(label,lx,ly);
    ctx.fillStyle="#6d28d9";
    ctx.fillText(label,lx,ly);
  });
  drawItemDimensions(project,item);
}
// 家具本体的尺寸线：宽 / 深 / 高。都沿局部轴量，所以跟着朝向走，不是量 AABB。
// 宽深两条朝包络中心让开一段，免得和外圈净距线、本体轮廓叠在一起。
// 三条都从原点角（局部 0,0）出发，正好成一组坐标框。
function itemDimensionSpecs(item){
  const fp=item.footprint,centre=footprintCenter(item);
  const smaller=Math.min(item.width,item.depth);
  const inset=Math.min(Math.max(60,Math.min(180,smaller*0.2)),smaller*0.35);
  const pull=(a,b)=>{
    const mx=(a[0]+b[0])/2,my=(a[1]+b[1])/2;
    const length=Math.hypot(centre[0]-mx,centre[1]-my)||1;
    const ux=(centre[0]-mx)/length,uy=(centre[1]-my)/length;
    return [[a[0]+ux*inset,a[1]+uy*inset,0],[b[0]+ux*inset,b[1]+uy*inset,0]];
  };
  const corner=[fp[0][0],fp[0][1]];
  return [
    {label:`宽 ${Math.round(item.width)}`,ends:pull(fp[0],fp[1])},
    {label:`深 ${Math.round(item.depth)}`,ends:pull(fp[0],fp[3])},
    {label:`高 ${Math.round(item.height)}`,
      ends:[[corner[0],corner[1],item.z_start],[corner[0],corner[1],item.z_end]]},
  ];
}
function drawItemDimensions(project,item){
  ctx.font=`700 ${Math.round(px(11))}px "Microsoft YaHei",system-ui,sans-serif`;
  ctx.textAlign="center";ctx.textBaseline="middle";
  const centre=footprintCenter(item);
  const centreScreen=project([centre[0],centre[1],(item.z_start+item.z_end)/2]);
  for(const spec of itemDimensionSpecs(item)){
    const a=project(spec.ends[0]),b=project(spec.ends[1]);
    const dx=b.x-a.x,dy=b.y-a.y,length=Math.hypot(dx,dy)||1;
    const nx=-dy/length,ny=dx/length,tick=px(4.5);
    ctx.strokeStyle="rgba(51,65,85,.9)";ctx.lineWidth=px(1.4);
    ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(a.x-nx*tick,a.y-ny*tick);ctx.lineTo(a.x+nx*tick,a.y+ny*tick);
    ctx.moveTo(b.x-nx*tick,b.y-ny*tick);ctx.lineTo(b.x+nx*tick,b.y+ny*tick);
    ctx.stroke();
    // 标签往外放（背离本体中心），免得挤在家具名和其他数字上。
    const mx=(a.x+b.x)/2,my=(a.y+b.y)/2;
    let ox=mx-centreScreen.x,oy=my-centreScreen.y;
    const span=Math.hypot(ox,oy)||1;
    const lx=mx+ox/span*px(11),ly=my+oy/span*px(11);
    ctx.lineWidth=px(3.5);ctx.strokeStyle="rgba(255,255,255,.95)";ctx.strokeText(spec.label,lx,ly);
    ctx.fillStyle="#334155";ctx.fillText(spec.label,lx,ly);
  }
}
// 正面方向。约定见 spatial-layout-rules：件局部 X 左→右、Y 后→前，原点在左后下角，
// 所以局部 +Y 那一侧就是正面（靠墙件背面贴墙、正面朝室内）。转到世界是 (−sinθ, cosθ)。
function frontVector(item){
  const rad=(item.placement.rotation_z_deg||0)*Math.PI/180;
  return [-Math.sin(rad),Math.cos(rad)];
}
// 正面朝哪一边，说成人话。方向词的顺序是先东西后南北（西南、东南、东北、西北）。
function frontCompass(item){
  const vector=frontVector(item),parts=[];
  if(vector[0]>0.38)parts.push("东");else if(vector[0]<-0.38)parts.push("西");
  if(vector[1]>0.38)parts.push("南");else if(vector[1]<-0.38)parts.push("北");
  return parts.join("")||"—";
}
// 正面方向在屏幕上的角度，用来画朝向箭头。
function headingScreenAngle(item,project,center,height){
  const vector=frontVector(item);
  const reach=Math.max(200,room.width_mm*.08);
  const pivot=project([center[0],center[1],height]);
  const tip=project([center[0]+vector[0]*reach,center[1]+vector[1]*reach,height]);
  return Math.atan2(tip.y-pivot.y,tip.x-pivot.x);
}
function drawRotateHandle(project){
  const item=scene.items.find(candidate=>candidate.id===state.selectedId);
  if(!item){state.handle=null;state.rotateRing=null;return}
  const center=footprintCenter(item),height=(item.z_start+item.z_end)/2;
  const pivot=project([center[0],center[1],height]);
  const top=project([center[0],center[1],item.z_end]);
  const handle={x:clamp(top.x+px(32),px(20),W-px(20)),y:clamp(top.y-px(48),px(20),H-px(20))};
  state.handle=handle;
  // 旋转环：把转轴、刻度和当前朝向都画出来，整圈都是可抓区域。
  const radius=px(74);
  state.rotateRing={x:pivot.x,y:pivot.y,radius};
  ctx.save();
  ctx.setLineDash([px(3),px(5)]);
  ctx.strokeStyle="rgba(180,83,9,.34)";ctx.lineWidth=px(1.2);
  ctx.beginPath();ctx.arc(pivot.x,pivot.y,radius,0,Math.PI*2);ctx.stroke();
  ctx.setLineDash([]);
  for(let deg=0;deg<360;deg+=15){
    const a=deg*Math.PI/180,major=deg%45===0;
    const inner=radius-(major?px(7):px(4));
    ctx.strokeStyle=major?"rgba(180,83,9,.5)":"rgba(180,83,9,.26)";
    ctx.lineWidth=px(1.4);
    ctx.beginPath();
    ctx.moveTo(pivot.x+Math.cos(a)*inner,pivot.y+Math.sin(a)*inner);
    ctx.lineTo(pivot.x+Math.cos(a)*radius,pivot.y+Math.sin(a)*radius);
    ctx.stroke();
  }
  const heading=headingScreenAngle(item,project,center,height);
  // 朝向箭头指向「正面」，箭头外再标个「前」。
  const tipX=pivot.x+Math.cos(heading)*radius,tipY=pivot.y+Math.sin(heading)*radius;
  ctx.strokeStyle="#047857";ctx.lineWidth=px(2.4);
  ctx.beginPath();ctx.moveTo(pivot.x,pivot.y);ctx.lineTo(tipX,tipY);ctx.stroke();
  const back=heading+Math.PI;
  ctx.beginPath();
  ctx.moveTo(tipX+Math.cos(back-0.42)*px(10),tipY+Math.sin(back-0.42)*px(10));
  ctx.lineTo(tipX,tipY);
  ctx.lineTo(tipX+Math.cos(back+0.42)*px(10),tipY+Math.sin(back+0.42)*px(10));
  ctx.stroke();
  ctx.restore();
  const labelX=clamp(tipX+Math.cos(heading)*px(14),px(14),W-px(14));
  const labelY=clamp(tipY+Math.sin(heading)*px(14),px(14),H-px(14));
  ctx.font=`700 ${Math.round(px(12.5))}px "Microsoft YaHei",system-ui,sans-serif`;
  ctx.textAlign="center";ctx.textBaseline="middle";
  ctx.lineWidth=px(3.5);ctx.strokeStyle="rgba(255,255,255,.95)";ctx.strokeText("前",labelX,labelY);
  ctx.fillStyle="#047857";ctx.fillText("前",labelX,labelY);
  ctx.strokeStyle="rgba(180,83,9,.5)";ctx.lineWidth=px(1.6);
  ctx.setLineDash([px(4),px(4)]);
  ctx.beginPath();ctx.moveTo(top.x,top.y);ctx.lineTo(handle.x,handle.y);ctx.stroke();
  ctx.setLineDash([]);
  ctx.beginPath();ctx.arc(handle.x,handle.y,px(14),0,Math.PI*2);
  ctx.fillStyle="#f59e0b";ctx.fill();
  ctx.strokeStyle="#b45309";ctx.lineWidth=px(2);ctx.stroke();
  ctx.beginPath();ctx.arc(handle.x,handle.y,px(6.5),-Math.PI*.75,Math.PI*.55);
  ctx.strokeStyle="#fff";ctx.lineWidth=px(2.2);ctx.stroke();
  if(drag&&drag.kind==="rotate"){
    // 拖动时就地显示角度，不用去猜吸附到哪了。
    const label=`${Math.round(normalizeAngle(item.placement.rotation_z_deg||0))}°`;
    ctx.font=`700 ${Math.round(px(13))}px "Microsoft YaHei",system-ui,sans-serif`;
    ctx.textAlign="center";ctx.textBaseline="middle";
    const lx=clamp(handle.x+px(28),px(26),W-px(26)),ly=handle.y-px(16);
    ctx.lineWidth=px(4);ctx.strokeStyle="rgba(255,255,255,.95)";ctx.strokeText(label,lx,ly);
    ctx.fillStyle="#b45309";ctx.fillText(label,lx,ly);
  }
}
function drawHeightHandle(project){
  const item=scene.items.find(candidate=>candidate.id===state.selectedId);
  if(!item){state.heightHandle=null;return}
  const center=footprintCenter(item),top=project([center[0],center[1],item.z_end]);
  const handle={x:clamp(top.x-px(30),px(20),W-px(20)),y:clamp(top.y-px(46),px(20),H-px(20))};
  state.heightHandle=handle;
  ctx.strokeStyle="rgba(29,78,216,.5)";ctx.lineWidth=px(1.6);
  ctx.setLineDash([px(4),px(4)]);
  ctx.beginPath();ctx.moveTo(top.x,top.y);ctx.lineTo(handle.x,handle.y);ctx.stroke();
  ctx.setLineDash([]);
  ctx.beginPath();ctx.arc(handle.x,handle.y,px(12),0,Math.PI*2);
  ctx.fillStyle="#3b82f6";ctx.fill();
  ctx.strokeStyle="#1d4ed8";ctx.lineWidth=px(2);ctx.stroke();
  ctx.strokeStyle="#fff";ctx.lineWidth=px(1.8);
  ctx.beginPath();
  ctx.moveTo(handle.x,handle.y-px(6));ctx.lineTo(handle.x,handle.y+px(6));
  ctx.moveTo(handle.x-px(3.6),handle.y-px(2.4));ctx.lineTo(handle.x,handle.y-px(6));ctx.lineTo(handle.x+px(3.6),handle.y-px(2.4));
  ctx.moveTo(handle.x-px(3.6),handle.y+px(2.4));ctx.lineTo(handle.x,handle.y+px(6));ctx.lineTo(handle.x+px(3.6),handle.y+px(2.4));
  ctx.stroke();
}
function render(){
  ctx.setTransform(1,0,0,1,0,0);
  const cam=camera(),project=projector(cam);
  drawBackdrop();
  drawFloor(project);
  drawWalls(project,cam);
  drawShadows(project);
  drawSolids(project,cam);
  drawDimensions(project);
  drawRotateHandle(project);
  drawHeightHandle(project);
  syncPanel();
}
function pointInPolygon(points,sx,sy){
  let inside=false;
  for(let i=0,j=points.length-1;i<points.length;j=i++){
    const a=points[i],b=points[j];
    if((a.y>sy)!==(b.y>sy)&&sx<(b.x-a.x)*(sy-a.y)/(b.y-a.y)+a.x)inside=!inside;
  }
  return inside;
}
function distanceToSegment(sx,sy,a,b){
  const dx=b.x-a.x,dy=b.y-a.y;
  const lengthSquared=dx*dx+dy*dy;
  const t=lengthSquared?clamp(((sx-a.x)*dx+(sy-a.y)*dy)/lengthSquared,0,1):0;
  return Math.hypot(sx-(a.x+t*dx),sy-(a.y+t*dy));
}
// 轮廓线上的点落在多边形边界上，射线法在那里数值上是不确定的；给一圈容差，
// 否则点家具的描边会穿透去转视角。
function distanceToPolygon(points,sx,sy){
  if(pointInPolygon(points,sx,sy))return 0;
  let best=Infinity;
  for(let i=0,j=points.length-1;i<points.length;j=i++){
    best=Math.min(best,distanceToSegment(sx,sy,points[j],points[i]));
  }
  return best;
}
// 点选整个包络：凸盒 6 个面的投影并集就是轮廓。先取点中实体的，再取点在容差边上的，
// 同类里取最靠前的那个面。
function hitTest(sx,sy){
  const project=projector(camera());
  let best=null,bestRank=Infinity,bestDepth=Infinity;
  for(const item of scene.items){
    const verts=boxVertices(item);let depth=Infinity,rank=Infinity;
    for(const face of boxFaces){
      const points=face.map(index=>project(verts[index]));
      const distance=distanceToPolygon(points,sx,sy);
      if(distance>px(5))continue;
      const faceDepth=points.reduce((sum,point)=>sum+point.depth,0)/points.length;
      if(faceDepth<depth){depth=faceDepth;rank=distance>0?1:0}
    }
    if(depth===Infinity)continue;
    if(rank<bestRank||(rank===bestRank&&depth<bestDepth)){best=item;bestRank=rank;bestDepth=depth}
  }
  return best;
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
function handleAt(sx,sy,handle){
  if(!handle)return null;
  if(Math.hypot(handle.x-sx,handle.y-sy)>px(22))return null;
  return scene.items.find(item=>item.id===state.selectedId)||null;
}
// 旋转环也整圈可抓：比一个小圆点好点太多。
function ringAt(sx,sy){
  const ring=state.rotateRing;
  if(!ring)return null;
  const distance=Math.hypot(sx-ring.x,sy-ring.y);
  if(Math.abs(distance-ring.radius)>px(14))return null;
  return scene.items.find(item=>item.id===state.selectedId)||null;
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
  const gapRow=(label,key)=>`<dt>${label}</dt><dd><button type="button" class="step" data-gap-step="${key}" data-delta="-10" aria-label="${label}减 10">−</button><input class="num" type="number" step="1" data-gap="${key}" aria-label="${label}"><button type="button" class="step" data-gap-step="${key}" data-delta="10" aria-label="${label}加 10">＋</button><span class="who" data-who="${key}"></span></dd>`;
  return `<dl class="detail">
    <dt>名称</dt><dd>${escapeHtml(item.label)}</dd>
    <dt>尺寸</dt><dd>${round(item.width)}×${round(item.depth)}×${round(item.height)}</dd>
    <dt>摆放</dt><dd data-field="mode"></dd>
    <dt>位置</dt><dd data-field="position"></dd>
    <dt>朝向</dt><dd><button type="button" class="step" data-rotation-step data-delta="-15" aria-label="逆时针 15°">−</button><input class="num" type="number" step="1" data-rotation data-field="rotation" aria-label="朝向角度"><button type="button" class="step" data-rotation-step data-delta="15" aria-label="顺时针 15°">＋</button><span class="who">°</span><span class="who" data-front></span></dd>
    <dt>离地</dt><dd><button type="button" class="step" data-height="-50" aria-label="降低 50">−</button><input class="num" type="number" step="1" data-height-input data-field="height" aria-label="离地高度"><button type="button" class="step" data-height="50" aria-label="升高 50">＋</button><span class="who">mm</span></dd>
    <dt>离顶</dt><dd><span data-field="ceiling"></span> mm</dd>
    ${gapRow("西距","west")}${gapRow("东距","east")}${gapRow("北距","north")}${gapRow("南距","south")}
  </dl>
  <p class="hint-inline">可以直接输入任意毫米值，回车生效。输入框的上下箭头走 1；旁边的 − / ＋ 走整数档（净距 10 · 离地 50 · 朝向 15）。到不了就只挪到能到的地方，并在左下角说明是越界、干涉还是遮挡门窗洞口。</p>`;
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
// 平移视图：右键 / 中键拖，或空白处 Shift+左键拖。只动视图中心，不发任何 op。
function startPan(event){
  state.panning=true;state.adjusted=true;
  state.lastX=event.clientX;state.lastY=event.clientY;
  canvas.classList.add("panning");
  canvas.setPointerCapture(event.pointerId);
}
canvas.addEventListener("pointerdown",event=>{
  const [sx,sy]=screenPoint(event);
  // 右键 / 中键一律平移（多数三维软件的习惯），不看下面压着什么。
  if(event.button===1||event.button===2){startPan(event);return}
  if(READ_ONLY){
    const readonlyHit=hitTest(sx,sy);
    if(readonlyHit){selectItem(readonlyHit.id);return}
    if(event.shiftKey){startPan(event);return}
    state.selectedId=null;state.blocked=null;
    state.orbiting=true;state.lastX=event.clientX;state.lastY=event.clientY;
    canvas.classList.add("orbiting");canvas.setPointerCapture(event.pointerId);
    render();
    return;
  }
  const heightItem=handleAt(sx,sy,state.heightHandle);
  if(heightItem){
    drag={kind:"height",item:heightItem,startScreen:[sx,sy],moved:false,
      startZ:heightItem.placement.origin_z_mm||0};
    canvas.classList.add("moving");
    setStatus(`离地高度 ${Math.round(heightItem.z_start)} mm`);
    canvas.setPointerCapture(event.pointerId);
    return;
  }
  const rotateItem=ringAt(sx,sy)||handleAt(sx,sy,state.handle);
  if(rotateItem){
    const center=footprintCenter(rotateItem),height=(rotateItem.z_start+rotateItem.z_end)/2;
    const origin=projector(camera())([center[0],center[1],height]);
    const startAngle=Math.atan2(sy-origin.y,sx-origin.x)*180/Math.PI;
    drag={kind:"rotate",item:rotateItem,center,height,origin,startAngle,lastAngle:startAngle,
      accumulated:0,moved:false,startScreen:[sx,sy],
      startRotation:rotateItem.placement.rotation_z_deg||0,startMode:rotateItem.placement.mode,
      sign:rotationSign(center,height)};
    canvas.classList.add("moving");
    setStatus(`旋转 ${rotateItem.label}…`);
    canvas.setPointerCapture(event.pointerId);
    return;
  }
  const ground=unprojectToGround(sx,sy);
  const hit=hitTest(sx,sy);
  if(hit&&(ground||isElevation())){
    const placement=hit.placement;
    state.selectedId=hit.id;state.blocked=null;
    drag={kind:"move",item:hit,ground,startScreen:[sx,sy],moved:false,
      startOrigin:[placement.origin_x_mm||0,placement.origin_y_mm||0],
      startOffset:placement.offset_mm||0,startZ:placement.origin_z_mm||0,
      horizontal:horizontalAxis(),elevation:isElevation(),
      startFootprint:hit.footprint.map(point=>[...point])};
    if(placement.mode==="wall"&&!drag.elevation){
      const normal=wallNormal(placement.host_wall),project=projector(camera()),center=footprintCenter(hit);
      if(normal){
        const from=project([center[0],center[1],0]);
        const to=project([center[0]+normal[0]*300,center[1]+normal[1]*300,0]);
        const length=Math.hypot(to.x-from.x,to.y-from.y)||1;
        drag.perpScreen={x:(to.x-from.x)/length,y:(to.y-from.y)/length};
      }
    }
    canvas.classList.add("moving");
    setStatus(selectHint(hit));
    render();
    canvas.setPointerCapture(event.pointerId);
    return;
  }
  // 空白处 Shift+左键 = 平移；普通左键仍是转视角。家具/手柄优先，所以放在它们之后。
  if(event.shiftKey){startPan(event);return}
  state.selectedId=null;state.blocked=null;
  state.orbiting=true;state.lastX=event.clientX;state.lastY=event.clientY;
  canvas.classList.add("orbiting");canvas.setPointerCapture(event.pointerId);
  render();
});
canvas.addEventListener("pointermove",event=>{
  if(state.panning){
    const dx=event.clientX-state.lastX,dy=event.clientY-state.lastY;
    state.lastX=event.clientX;state.lastY=event.clientY;
    panBy(dx,dy);render();
    return;
  }
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
  if(!state.orbiting)return;
  const dx=event.clientX-state.lastX,dy=event.clientY-state.lastY;state.lastX=event.clientX;state.lastY=event.clientY;
  state.yaw-=dx*.008;state.pitch=clamp(state.pitch+dy*.006,-1.42,1.48);render();
});
async function reload(){
  try{
    const response=await fetch(`/api/room-scene/${encodeURIComponent(SCENE_ID)}`);
    if(!response.ok)return;
    const next=await response.json();
    scene.items=normalizeItems(next.items||[]);
  }catch(error){/* 回退失败时保留画面，状态栏已有提示 */}
}
async function persist(item,kind){
  if(READ_ONLY)return false;
  const placement=item.placement,op={op:kind==="rotate"?"rotate":"move",item_id:item.id};
  if(kind==="rotate")op.rotation_z_deg=Math.round(normalizeAngle(placement.rotation_z_deg)*10)/10;
  if(placement.mode==="wall"){op.offset_mm=Math.round(placement.offset_mm)}
  else{op.mode="free";op.origin_x_mm=Math.round(placement.origin_x_mm);op.origin_y_mm=Math.round(placement.origin_y_mm)}
  // origin_z_mm 是 move 的共享字段，平面移动时顺带带上也不会互相干扰。
  if(kind!=="rotate")op.origin_z_mm=Math.round(placement.origin_z_mm||0);
  try{
    const response=await fetch(`/api/room-scene/${encodeURIComponent(SCENE_ID)}/edit`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(op)});
    if(!response.ok){
      const detail=await response.json().catch(()=>({}));
      setStatus("改动被拒绝，已回到原位："+(detail.detail||response.status),"error");
      await reload();
      return false;
    }
    const next=await response.json();
    scene.items=normalizeItems(next.items||[]);
    setStatus(`已保存 ${item.label}`);
    return true;
  }catch(error){
    setStatus("保存失败："+error,"error");
    await reload();
    return false;
  }
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
    canvas.releasePointerCapture(event.pointerId);
    if(moved&&!unchanged){persist(item,kind).then(()=>{render()})}
    else{setStatus(selectHint(item));render()}
    return;
  }
  if(state.orbiting){state.orbiting=false;canvas.classList.remove("orbiting");canvas.releasePointerCapture(event.pointerId)}
});
canvas.addEventListener("pointercancel",()=>{drag=null;state.blocked=null;state.panning=false;canvas.classList.remove("moving","orbiting","panning")});
// 右键要用来平移，别弹系统菜单。
canvas.addEventListener("contextmenu",event=>event.preventDefault());
canvas.addEventListener("wheel",event=>{event.preventDefault();cancelFrame(viewAnimation);viewAnimation=0;state.adjusted=true;state.distance=clamp(state.distance*Math.exp(event.deltaY*.001),diagonal*.4,diagonal*3.4);render()},{passive:false});
window.addEventListener("keydown",event=>{
  if(event.key==="Escape")selectItem(null);
  const item=scene.items.find(candidate=>candidate.id===state.selectedId);
  if(!item)return;
  if(event.key==="PageUp"){event.preventDefault();nudgeHeight(item,50)}
  if(event.key==="PageDown"){event.preventDefault();nudgeHeight(item,-50)}
});
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
function setView(name){
  const key=name==="reset"?"perspective":name;
  const preset=VIEWS[key];
  if(!preset)return;
  state.adjusted=false;
  document.querySelectorAll("[data-view]").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.view===name)));
  // 取景按房间中心算，然后连中心一起动画回去——平移过的视角也能干净复位。
  const distance=withHomeCentre(()=>fitDistance(preset.pitch,preset.yaw))*
    (preset.pitch<ELEVATION_MAX_PITCH?1.04:1);
  animateView({yaw:preset.yaw,pitch:preset.pitch,distance,target:HOME_TARGET},500);
}
document.querySelectorAll("[data-view]").forEach(button=>button.addEventListener("click",()=>setView(button.dataset.view)));
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
const state={...defaults,orbiting:false,panning:false,lastX:0,lastY:0,active:"perspective",selectedId:null,
  handle:null,heightHandle:null,rotateRing:null,blocked:null,adjusted:false,dims:true};
render();
// 深链：#view=front&item=desk 直接打开某个视角并选中某件，方便分享/复现。
if(typeof location!=="undefined"&&location.hash.length>1){
  const params=new URLSearchParams(location.hash.slice(1));
  const view=params.get("view");
  if(view&&VIEWS[view])setView(view);
  const wanted=params.get("item");
  if(wanted&&scene.items.some(candidate=>candidate.id===wanted))selectItem(wanted);
}
function syncRoomSwitch(){
  const wrap=document.getElementById("room-switch-wrap");
  const select=document.getElementById("room-switch");
  if(!wrap||!select)return;
  if(!rooms||rooms.length<2){wrap.hidden=true;return}
  wrap.hidden=false;
  const signature=rooms.map(entry=>`${entry.id}:${entry.name}`).join("|");
  if(select.dataset.signature!==signature){
    select.dataset.signature=signature;
    select.innerHTML=rooms.map((entry,index)=>`<option value="${index}">${escapeHtml(entry.name||entry.id)}</option>`).join("");
  }
  select.value=String(roomIndex);
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
    state.active="perspective";
    document.querySelectorAll("[data-view]").forEach(button=>button.setAttribute("aria-pressed",String(button.dataset.view==="perspective")));
  }
  if(state.selectedId&&!scene.items.some(item=>item.id===state.selectedId)){
    state.selectedId=null;state.blocked=null;
  }
  panelSignature=null;
  detailItemId=undefined;
  syncRoomSwitch();
  render();
}
function layoutVersionOf(payload){
  return String(payload.version||"");
}
async function pollLayout(){
  if(!POLL_URL)return;
  if(drag||state.orbiting||state.panning)return;
  try{
    const response=await fetch(POLL_URL,{cache:"no-store",headers:{Accept:"application/json"}});
    if(!response.ok)return;
    const payload=await response.json();
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
const roomSwitch=document.getElementById("room-switch");
if(roomSwitch){
  roomSwitch.addEventListener("change",()=>{
    const index=Number(roomSwitch.value);
    if(!Number.isInteger(index)||!rooms[index])return;
    showRoom(index,false);
  });
}
syncRoomSwitch();
let pollTimer=0;
if(POLL_URL)pollTimer=setInterval(pollLayout,1000);
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
})();
</script>
</body>
</html>
"""
