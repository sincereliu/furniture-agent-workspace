"""Generate a self-contained orbit viewer for independent room placement."""

from __future__ import annotations

from html import escape
import json

from .scene import RoomScene


VIEWER_WIDTH_PX = 960
VIEWER_HEIGHT_PX = 720


def render_viewer(scene: RoomScene) -> dict[str, object]:
    """Return deterministic HTML that renders the current layout interactively."""
    item_summary = "、".join(item.label for item in scene.items) or "家具"
    payload = {
        "room": scene.room.to_dict(),
        "items": [
            {
                "label": item.label,
                "footprint": [list(point) for point in item.footprint],
                "z_start": item.placement.origin_z_mm,
                "z_end": item.z_end,
                "dimensions": [item.width, item.depth, item.height],
            }
            for item in scene.items
        ],
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
    scene_json = (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    html = (
        _VIEWER_HTML.replace("__SCENE_JSON__", scene_json)
        .replace("__ROOM_NAME__", escape(scene.room.name, quote=True))
        .replace("__FURNITURE_LABEL__", escape(item_summary, quote=True))
    )
    return {
        "media_type": "text/html",
        "view_kind": "interactive_orbit_envelope",
        "width_px": VIEWER_WIDTH_PX,
        "height_px": VIEWER_HEIGHT_PX,
        "controls": [
            "drag_orbit",
            "wheel_zoom",
            "perspective",
            "front",
            "left",
            "right",
            "top",
            "reset",
        ],
        "alt_text": (
            f"{item_summary}在{scene.room.name}中的可旋转三维外形尺寸；"
            "拖拽旋转、滚轮缩放，并可选择正视、左右视图和俯视"
        ),
        "html": html,
    }


_VIEWER_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'self' 'unsafe-inline'">
<title>__ROOM_NAME__ · __FURNITURE_LABEL__ · 互动布局预览</title>
<style>
:root{font-family:Inter,"Microsoft YaHei",system-ui,sans-serif;color:#0f172a;background:#eef2f7}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;padding:16px}
.viewer{width:min(960px,100%);background:#f8fafc;border:1px solid #cbd5e1;border-radius:18px;box-shadow:0 18px 50px rgba(15,23,42,.16);overflow:hidden}
header{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:16px 18px 12px;background:#fff;border-bottom:1px solid #e2e8f0}
h1{font-size:18px;margin:0 0 4px}.hint{font-size:12px;color:#64748b;margin:0}
.toolbar{display:flex;flex-wrap:wrap;justify-content:flex-end;align-items:center;gap:7px}
button{appearance:none;border:1px solid #cbd5e1;background:#fff;color:#334155;border-radius:9px;padding:7px 10px;font:inherit;font-size:12px;font-weight:600;cursor:pointer}
button:hover,button:focus-visible{border-color:#2563eb;color:#1d4ed8;outline:none}
button[aria-pressed="true"]{background:#2563eb;border-color:#2563eb;color:#fff}
.view-switch select{border:1px solid #cbd5e1;border-radius:9px;background:#fff;color:#334155;font:inherit;font-size:12px;font-weight:600;padding:7px 8px}
.stage{position:relative;background:radial-gradient(circle at 50% 38%,#fff 0,#f1f5f9 58%,#e2e8f0 100%)}
canvas{display:block;width:100%;height:auto;touch-action:none;cursor:grab}
canvas.dragging{cursor:grabbing}
.badge{position:absolute;left:16px;bottom:14px;padding:7px 10px;border-radius:9px;background:rgba(255,255,255,.88);border:1px solid rgba(203,213,225,.9);font-size:12px;color:#475569;backdrop-filter:blur(6px)}
.badge.coord{left:auto;right:16px;font-variant-numeric:tabular-nums;pointer-events:none}
footer{display:flex;justify-content:space-between;gap:16px;padding:10px 18px 13px;background:#fff;border-top:1px solid #e2e8f0;font-size:12px;color:#64748b}
@media(max-width:760px){header{align-items:flex-start;flex-direction:column}.toolbar{justify-content:flex-start}button{padding:8px 11px}}
</style>
</head>
<body>
<main class="viewer" aria-label="可旋转家具布局预览">
  <header>
    <div><h1>__ROOM_NAME__ · __FURNITURE_LABEL__</h1><p class="hint">拖拽旋转 · 滚轮缩放 · 双击吸到最近的正视图，再双击回到自由视角</p></div>
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
    </nav>
  </header>
  <section class="stage">
    <canvas id="scene" width="960" height="600" aria-label="透明房间与不透明家具外形尺寸"></canvas>
    <div class="badge" id="status">默认视角</div>
    <div class="badge coord" id="coord" hidden></div>
  </section>
  <footer><span>透明线框：房间</span><span>蓝色实体：家具外形尺寸</span><span>红色实体：障碍物</span></footer>
</main>
<script id="scene-data" type="application/json">__SCENE_JSON__</script>
<script type="importmap">
{"imports":{"three":"/vendor/three/three.module.js"}}
</script>
<script type="module">
import { mountLayout } from "/vendor/three/layout_scene.js";
const scene=JSON.parse(document.getElementById("scene-data").textContent);
const canvas=document.getElementById("scene"),status=document.getElementById("status");
const view=mountLayout(canvas);
const room=scene.room;
const target=[room.width_mm/2,room.depth_mm/2,room.height_mm*.42];
const diagonal=Math.hypot(room.width_mm,room.depth_mm,room.height_mm);
const DEFAULT_YAW=Math.PI*5/12,DEFAULT_PITCH=.35;
const VIEWS={
  default_view:{yaw:DEFAULT_YAW,pitch:DEFAULT_PITCH},
  top:{yaw:Math.PI/2,pitch:1.48},
  bottom:{yaw:Math.PI/2,pitch:-1.48},
  front:{yaw:Math.PI/2,pitch:0},
  back:{yaw:-Math.PI/2,pitch:0},
  right:{yaw:0,pitch:0},
  left:{yaw:Math.PI,pitch:0},
};
const ORTHO=["top","bottom","front","back","left","right"];
let active="default_view",freeView=null,placing=false;
function fitDistance(pitch){
  const aspect=(canvas.clientWidth||960)/Math.max(canvas.clientHeight||600,1);
  const vFov=48*Math.PI/180;
  const limit=Math.min(vFov,2*Math.atan(Math.tan(vFov/2)*aspect));
  return diagonal*0.5/Math.sin(limit/2)*(pitch<0.12?1.15:1.25);
}
function show(name){
  const preset=VIEWS[name];
  if(!preset)return;
  placing=true;
  view.setView(preset.yaw,preset.pitch,fitDistance(preset.pitch),target);
  placing=false;
  view.sync(scene,{selectedId:null,dims:false,readOnly:true,blockedId:null});
  active=name;
  const select=document.getElementById("view-select");
  if(select)select.value=ORTHO.includes(name)?name:"free";
  const button=document.querySelector('[data-view="default_view"]');
  if(button)button.setAttribute("aria-pressed",String(name==="default_view"));
  status.textContent=name==="default_view"?"默认视角":"正视图";
}
view.resize();
show("default_view");
view.controls.addEventListener("change",()=>{if(!placing)view.draw()});
view.controls.addEventListener("end",()=>{
  if(!VIEWS[active])return;
  const pose=view.readView();
  if(Math.abs(pose.yaw-VIEWS[active].yaw)>0.02||Math.abs(pose.pitch-VIEWS[active].pitch)>0.02){
    active="free";
    const select=document.getElementById("view-select");
    if(select)select.value="free";
    status.textContent="自由视角";
  }
});
document.querySelectorAll("[data-view]").forEach(button=>button.addEventListener("click",()=>show(button.dataset.view)));
const viewSelect=document.getElementById("view-select");
if(viewSelect)viewSelect.addEventListener("change",()=>{if(VIEWS[viewSelect.value])show(viewSelect.value)});
canvas.addEventListener("dblclick",()=>{
  if(ORTHO.includes(active)&&freeView){
    const back=freeView;
    freeView=null;
    placing=true;
    view.setView(back.yaw,back.pitch,back.distance,target);
    placing=false;
    view.sync(scene,{selectedId:null,dims:false,readOnly:true,blockedId:null});
    active="free";
    const select=document.getElementById("view-select");
    if(select)select.value="free";
    status.textContent="自由视角";
    return;
  }
  freeView=view.readView();
  const pose=freeView;
  show(pose.pitch>0.35?"top":pose.pitch<-0.35?"bottom":"front");
});
window.addEventListener("resize",()=>{view.resize();show(active)});
canvas.addEventListener("pointermove",event=>{
  const box=document.getElementById("coord");
  if(!box)return;
  const ground=view.ground(event.clientX,event.clientY);
  if(!ground){box.hidden=true;return}
  box.hidden=false;
  box.textContent=`X ${Math.round(ground[0])} · Y ${Math.round(ground[1])} mm`;
});
canvas.addEventListener("contextmenu",event=>event.preventDefault());
</script>
</body>
</html>
"""
