"""Generate a self-contained orbit viewer for independent room placement."""

from __future__ import annotations

from html import escape
import json

from .layout_planning import CabinetLayout
from .room_planning import RoomPlacementPlan


VIEWER_WIDTH_PX = 960
VIEWER_HEIGHT_PX = 720


def render_layout_viewer(
    plan: RoomPlacementPlan,
    layout: CabinetLayout,
) -> dict[str, object]:
    """Return deterministic HTML that renders the current layout interactively."""
    scene = {
        "room": plan.room.to_dict(),
        "furniture": {
            "label": plan.furniture_label,
            "footprint": [list(point) for point in plan.furniture_footprint],
            "z_start": plan.placement.origin_z_mm,
            "z_end": plan.placement.origin_z_mm + layout.height,
            "dimensions": [layout.width, layout.depth, layout.height],
        },
        "obstacles": [
            {
                "label": obstacle.kind,
                "footprint": [list(point) for point in obstacle.footprint],
                "z_start": obstacle.z_mm,
                "z_end": obstacle.z_mm + obstacle.height_mm,
            }
            for obstacle in plan.room.obstacles
        ],
        "openings": [opening.to_dict() for opening in plan.room.openings],
    }
    scene_json = (
        json.dumps(scene, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    html = (
        _VIEWER_HTML.replace("__SCENE_JSON__", scene_json)
        .replace("__ROOM_NAME__", escape(plan.room.name, quote=True))
        .replace("__FURNITURE_LABEL__", escape(plan.furniture_label, quote=True))
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
            f"{plan.furniture_label}在{plan.room.name}中的可旋转三维包络；"
            "拖拽旋转、滚轮缩放，并可选择正视、左右视图和俯视"
        ),
        "html": html,
    }


_VIEWER_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<title>__ROOM_NAME__ · __FURNITURE_LABEL__ · 互动布局预览</title>
<style>
:root{font-family:Inter,"Microsoft YaHei",system-ui,sans-serif;color:#0f172a;background:#eef2f7}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;padding:16px}
.viewer{width:min(960px,100%);background:#f8fafc;border:1px solid #cbd5e1;border-radius:18px;box-shadow:0 18px 50px rgba(15,23,42,.16);overflow:hidden}
header{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:16px 18px 12px;background:#fff;border-bottom:1px solid #e2e8f0}
h1{font-size:18px;margin:0 0 4px}.hint{font-size:12px;color:#64748b;margin:0}
.toolbar{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:7px}
button{appearance:none;border:1px solid #cbd5e1;background:#fff;color:#334155;border-radius:9px;padding:7px 10px;font:inherit;font-size:12px;font-weight:600;cursor:pointer}
button:hover,button:focus-visible{border-color:#2563eb;color:#1d4ed8;outline:none}
button[aria-pressed="true"]{background:#2563eb;border-color:#2563eb;color:#fff}
.stage{position:relative;background:radial-gradient(circle at 50% 38%,#fff 0,#f1f5f9 58%,#e2e8f0 100%)}
canvas{display:block;width:100%;height:auto;touch-action:none;cursor:grab}
canvas.dragging{cursor:grabbing}
.badge{position:absolute;left:16px;bottom:14px;padding:7px 10px;border-radius:9px;background:rgba(255,255,255,.88);border:1px solid rgba(203,213,225,.9);font-size:12px;color:#475569;backdrop-filter:blur(6px)}
footer{display:flex;justify-content:space-between;gap:16px;padding:10px 18px 13px;background:#fff;border-top:1px solid #e2e8f0;font-size:12px;color:#64748b}
@media(max-width:760px){header{align-items:flex-start;flex-direction:column}.toolbar{justify-content:flex-start}button{padding:8px 11px}}
</style>
</head>
<body>
<main class="viewer" aria-label="可旋转家具布局预览">
  <header>
    <div><h1>__ROOM_NAME__ · __FURNITURE_LABEL__</h1><p class="hint">拖拽旋转 · 滚轮缩放 · 选择标准视角</p></div>
    <nav class="toolbar" aria-label="视角选择">
      <button type="button" data-view="perspective" aria-pressed="true">透视</button>
      <button type="button" data-view="front" aria-pressed="false">正视</button>
      <button type="button" data-view="left" aria-pressed="false">左视</button>
      <button type="button" data-view="right" aria-pressed="false">右视</button>
      <button type="button" data-view="top" aria-pressed="false">俯视</button>
      <button type="button" data-view="reset" aria-pressed="false">重置</button>
    </nav>
  </header>
  <section class="stage">
    <canvas id="scene" width="960" height="600" aria-label="透明房间与不透明家具包络"></canvas>
    <div class="badge" id="status">透视视角</div>
  </section>
  <footer><span>透明线框：房间</span><span>蓝色实体：家具包络</span><span>红色实体：障碍物</span></footer>
</main>
<script id="scene-data" type="application/json">__SCENE_JSON__</script>
<script>
(()=>{
"use strict";
const scene=JSON.parse(document.getElementById("scene-data").textContent);
const canvas=document.getElementById("scene"),ctx=canvas.getContext("2d"),status=document.getElementById("status");
const W=canvas.width,H=canvas.height,room=scene.room;
const target=[room.width_mm/2,room.depth_mm/2,room.height_mm*.42];
const diagonal=Math.hypot(room.width_mm,room.depth_mm,room.height_mm);
const defaults={yaw:-Math.PI/4,pitch:.48,distance:diagonal*1.65};
const state={...defaults,dragging:false,lastX:0,lastY:0,active:"perspective"};
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const sub=(a,b)=>[a[0]-b[0],a[1]-b[1],a[2]-b[2]];
const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const norm=a=>{const n=Math.hypot(...a)||1;return a.map(v=>v/n)};
const midpoint=pts=>pts[0].map((_,i)=>pts.reduce((s,p)=>s+p[i],0)/pts.length);
function camera(){
  const cp=Math.cos(state.pitch),sp=Math.sin(state.pitch),cy=Math.cos(state.yaw),sy=Math.sin(state.yaw);
  const position=[target[0]+state.distance*cp*cy,target[1]+state.distance*cp*sy,target[2]+state.distance*sp];
  const forward=norm(sub(target,position)),right=norm(cross(forward,[0,0,1])),up=norm(cross(right,forward));
  return{position,forward,right,up};
}
function projector(cam){
  const focal=H/(2*Math.tan(48*Math.PI/360));
  return point=>{const rel=sub(point,cam.position),depth=dot(rel,cam.forward);return{x:W/2+dot(rel,cam.right)/depth*focal,y:H/2-dot(rel,cam.up)/depth*focal,depth}};
}
function roomVertices(){const w=room.width_mm,d=room.depth_mm,h=room.height_mm;return[[0,0,0],[w,0,0],[w,d,0],[0,d,0],[0,0,h],[w,0,h],[w,d,h],[0,d,h]]}
function boxVertices(box){const b=box.footprint.map(p=>[p[0],p[1],box.z_start]),t=box.footprint.map(p=>[p[0],p[1],box.z_end]);return[...b,...t]}
const boxFaces=[[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]];
const roomFaces=[[0,1,2,3],[4,7,6,5],[0,4,5,1],[1,5,6,2],[2,6,7,3],[3,7,4,0]];
const roomEdges=[[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
function visible(face,verts,cam){const a=verts[face[0]],b=verts[face[1]],c=verts[face[2]],normal=cross(sub(b,a),sub(c,b));return dot(normal,sub(cam.position,midpoint(face.map(i=>verts[i]))))>0}
function path(points){ctx.beginPath();ctx.moveTo(points[0].x,points[0].y);for(const p of points.slice(1))ctx.lineTo(p.x,p.y);ctx.closePath()}
function openingPoints(o){const s=o.offset_mm,e=s+o.width_mm,z0=o.sill_height_mm,z1=z0+o.height_mm,w=room.width_mm,d=room.depth_mm;if(o.wall==="north")return[[s,0,z0],[e,0,z0],[e,0,z1],[s,0,z1]];if(o.wall==="east")return[[w,s,z0],[w,e,z0],[w,e,z1],[w,s,z1]];if(o.wall==="south")return[[w-s,d,z0],[w-e,d,z0],[w-e,d,z1],[w-s,d,z1]];return[[0,d-s,z0],[0,d-e,z0],[0,d-e,z1],[0,d-s,z1]]}
function drawRoom(project,cam){
  const verts=roomVertices(),faces=roomFaces.map(face=>({face,depth:face.reduce((s,i)=>s+project(verts[i]).depth,0)/face.length})).sort((a,b)=>b.depth-a.depth);
  for(const item of faces){const pts=item.face.map(i=>project(verts[i]));path(pts);ctx.fillStyle="rgba(186,230,253,.055)";ctx.fill()}
  for(const opening of scene.openings){const pts=openingPoints(opening).map(project);path(pts);ctx.fillStyle="rgba(34,211,238,.34)";ctx.fill();ctx.strokeStyle="rgba(8,145,178,.8)";ctx.lineWidth=2;ctx.stroke()}
  ctx.strokeStyle="rgba(71,85,105,.72)";ctx.lineWidth=1.6;for(const edge of roomEdges){const a=project(verts[edge[0]]),b=project(verts[edge[1]]);ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke()}
}
function solidFaces(box,kind,project,cam){
  const verts=boxVertices(box),palette=kind==="furniture"?["#1e40af","#60a5fa","#1d4ed8","#2563eb","#1e3a8a","#3b82f6"]:["#991b1b","#fca5a5","#b91c1c","#dc2626","#7f1d1d","#ef4444"];
  return boxFaces.filter(face=>visible(face,verts,cam)).map((face,index)=>({points:face.map(i=>project(verts[i])),depth:face.reduce((s,i)=>s+project(verts[i]).depth,0)/face.length,fill:palette[boxFaces.indexOf(face)],stroke:kind==="furniture"?"#172554":"#7f1d1d"}))
}
function drawSolids(project,cam){
  const entries=[...scene.obstacles.map(box=>({box,kind:"obstacle"})),{box:scene.furniture,kind:"furniture"}],faces=[];
  for(const entry of entries)faces.push(...solidFaces(entry.box,entry.kind,project,cam));
  faces.sort((a,b)=>b.depth-a.depth);for(const face of faces){path(face.points);ctx.fillStyle=face.fill;ctx.fill();ctx.strokeStyle=face.stroke;ctx.lineWidth=2;ctx.stroke()}
  const f=scene.furniture,c=[f.footprint.reduce((s,p)=>s+p[0],0)/4,f.footprint.reduce((s,p)=>s+p[1],0)/4,(f.z_start+f.z_end)/2],p=project(c);ctx.font="700 16px Microsoft YaHei, sans-serif";ctx.textAlign="center";ctx.textBaseline="middle";ctx.lineWidth=4;ctx.strokeStyle="rgba(30,58,138,.9)";ctx.strokeText(f.label,p.x,p.y);ctx.fillStyle="#fff";ctx.fillText(f.label,p.x,p.y)
}
function drawAxis(){const x=W-88,y=H-58,axes=[[36,12,"#dc2626","X"],[-31,12,"#16a34a","Y"],[0,-39,"#2563eb","Z"]];ctx.lineWidth=3;ctx.font="700 12px sans-serif";for(const [dx,dy,color,label] of axes){ctx.strokeStyle=color;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+dx,y+dy);ctx.stroke();ctx.fillStyle=color;ctx.beginPath();ctx.arc(x+dx,y+dy,4,0,Math.PI*2);ctx.fill();ctx.fillText(label,x+dx+8,y+dy+4)}}
function render(){ctx.clearRect(0,0,W,H);const gradient=ctx.createRadialGradient(W*.5,H*.38,20,W*.5,H*.42,W*.72);gradient.addColorStop(0,"#fff");gradient.addColorStop(1,"#e8eef5");ctx.fillStyle=gradient;ctx.fillRect(0,0,W,H);const cam=camera(),project=projector(cam);drawRoom(project,cam);drawSolids(project,cam);drawAxis()}
function activate(name){state.active=name;document.querySelectorAll("[data-view]").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.view===name)));const labels={perspective:"透视视角",front:"正视图",left:"左视图",right:"右视图",top:"俯视图",reset:"透视视角"};status.textContent=labels[name]||"自由视角"}
function setView(name){if(name==="reset"||name==="perspective")Object.assign(state,defaults);if(name==="front")Object.assign(state,{yaw:-Math.PI/2,pitch:.04,distance:diagonal*1.72});if(name==="left")Object.assign(state,{yaw:Math.PI,pitch:.08,distance:diagonal*1.72});if(name==="right")Object.assign(state,{yaw:0,pitch:.08,distance:diagonal*1.72});if(name==="top")Object.assign(state,{yaw:-Math.PI/2,pitch:1.48,distance:diagonal*1.82});activate(name==="reset"?"perspective":name);render()}
canvas.addEventListener("pointerdown",e=>{state.dragging=true;state.lastX=e.clientX;state.lastY=e.clientY;canvas.setPointerCapture(e.pointerId);canvas.classList.add("dragging")});
canvas.addEventListener("pointermove",e=>{if(!state.dragging)return;const dx=e.clientX-state.lastX,dy=e.clientY-state.lastY;state.lastX=e.clientX;state.lastY=e.clientY;state.yaw-=dx*.008;state.pitch=clamp(state.pitch+dy*.006,-1.42,1.48);activate("free");status.textContent="自由视角";render()});
canvas.addEventListener("pointerup",e=>{state.dragging=false;canvas.releasePointerCapture(e.pointerId);canvas.classList.remove("dragging")});
canvas.addEventListener("pointercancel",()=>{state.dragging=false;canvas.classList.remove("dragging")});
canvas.addEventListener("wheel",e=>{e.preventDefault();state.distance=clamp(state.distance*Math.exp(e.deltaY*.001),diagonal*.72,diagonal*3.4);activate("free");status.textContent="自由视角";render()},{passive:false});
document.querySelectorAll("[data-view]").forEach(button=>button.addEventListener("click",()=>setView(button.dataset.view)));
window.addEventListener("keydown",e=>{if(e.key.toLowerCase()==="r")setView("reset")});
render();
})();
</script>
</body>
</html>
"""
