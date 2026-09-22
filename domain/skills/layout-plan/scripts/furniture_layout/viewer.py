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
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
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
<script>
(()=>{
"use strict";
const scene=JSON.parse(document.getElementById("scene-data").textContent);
const canvas=document.getElementById("scene"),ctx=canvas.getContext("2d"),status=document.getElementById("status");
const W=canvas.width,H=canvas.height,room=scene.room;
const target=[room.width_mm/2,room.depth_mm/2,room.height_mm*.42];
const diagonal=Math.hypot(room.width_mm,room.depth_mm,room.height_mm);
// 默认视角：正南偏东 15°（yaw=75°），北墙几乎正对；俯仰 0.35 rad（≈20°）。
const DEFAULT_YAW=Math.PI*5/12,DEFAULT_PITCH=.35,DEFAULT_DISTANCE=diagonal*1.75;
const defaults={yaw:DEFAULT_YAW,pitch:DEFAULT_PITCH,distance:DEFAULT_DISTANCE};
const state={...defaults,dragging:false,lastX:0,lastY:0,active:"default_view",freeView:null};
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const sub=(a,b)=>[a[0]-b[0],a[1]-b[1],a[2]-b[2]];
const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const norm=a=>{const n=Math.hypot(...a)||1;return a.map(v=>v/n)};
const midpoint=pts=>pts[0].map((_,i)=>pts.reduce((s,p)=>s+p[i],0)/pts.length);
function camera(){
  const cp=Math.cos(state.pitch),sp=Math.sin(state.pitch),cy=Math.cos(state.yaw),sy=Math.sin(state.yaw);
  const position=[target[0]+state.distance*cp*cy,target[1]+state.distance*cp*sy,target[2]+state.distance*sp];
  // 房间坐标系是 X 东 / Y 南 / Z 上（左手系），右向量必须取 cross(up, forward)；
  // 反过来会得到「左」向量，整幅画面左右镜像（正视会把东墙画到左边）。
  const forward=norm(sub(target,position)),right=norm(cross([0,0,1],forward)),up=norm(cross(forward,right));
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
  const entries=[...scene.obstacles.map(box=>({box,kind:"obstacle"})),...(scene.items||[]).map(box=>({box,kind:"furniture"}))],faces=[];
  for(const entry of entries)faces.push(...solidFaces(entry.box,entry.kind,project,cam));
  faces.sort((a,b)=>b.depth-a.depth);for(const face of faces){path(face.points);ctx.fillStyle=face.fill;ctx.fill();ctx.strokeStyle=face.stroke;ctx.lineWidth=2;ctx.stroke()}
  ctx.font="700 16px Microsoft YaHei, sans-serif";ctx.textAlign="center";ctx.textBaseline="middle";
  for(const f of scene.items||[]){const c=[f.footprint.reduce((s,p)=>s+p[0],0)/4,f.footprint.reduce((s,p)=>s+p[1],0)/4,(f.z_start+f.z_end)/2],p=project(c);ctx.lineWidth=4;ctx.strokeStyle="rgba(30,58,138,.9)";ctx.strokeText(f.label,p.x,p.y);ctx.fillStyle="#fff";ctx.fillText(f.label,p.x,p.y)}
}
/* ---------- 房间原点与 X/Y/Z 轴：轴长就是房间的总宽 / 总深 / 总高 ---------- */
// 与可编辑/预览页同一套：原点在西北角地面，三根轴画在房间外侧，箭头指向 +X（东）/ +Y（南）/ +Z（上）。
// 正对相机被压成一点、或者跑到相机后面的那根就不画。
function drawOriginAxes(project){
  const origin=project([0,0,0]);
  if(!(origin.depth>0))return;
  const gap=Math.max(120,Math.min(room.width_mm,room.depth_mm)*.04);
  const centre=project([room.width_mm/2,room.depth_mm/2,0]);
  const arms=[
    {from:[0,-gap,0],tip:[room.width_mm,-gap,0],witness:[[0,0,0],[0,-gap,0]],color:"#dc2626",
      label:`X 东 · 总宽 ${Math.round(room.width_mm)}`},
    {from:[-gap,0,0],tip:[-gap,room.depth_mm,0],witness:[[0,0,0],[-gap,0,0]],color:"#047857",
      label:`Y 南 · 总深 ${Math.round(room.depth_mm)}`},
    {from:[-gap,-gap,0],tip:[-gap,-gap,room.height_mm],color:"#2563eb",
      label:`Z 上 · 总高 ${Math.round(room.height_mm)}`},
  ];
  ctx.save();
  ctx.font='700 13px "Microsoft YaHei",system-ui,sans-serif';
  ctx.textAlign="center";ctx.textBaseline="middle";
  for(const arm of arms){
    const a=project(arm.from),b=project(arm.tip);
    if(!(a.depth>0)||!(b.depth>0))continue;
    if(Math.hypot(b.x-a.x,b.y-a.y)<26)continue;
    if(arm.witness){
      const [w0,w1]=arm.witness.map(project);
      ctx.save();ctx.setLineDash([4,4]);ctx.strokeStyle=arm.color;ctx.lineWidth=1;
      ctx.beginPath();ctx.moveTo(w0.x,w0.y);ctx.lineTo(w1.x,w1.y);ctx.stroke();ctx.restore();
    }
    const angle=Math.atan2(b.y-a.y,b.x-a.x);
    ctx.strokeStyle=arm.color;ctx.lineWidth=2;ctx.lineCap="round";
    ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
    const head=10;
    ctx.beginPath();ctx.moveTo(b.x,b.y);
    ctx.lineTo(b.x-head*Math.cos(angle-.42),b.y-head*Math.sin(angle-.42));
    ctx.lineTo(b.x-head*Math.cos(angle+.42),b.y-head*Math.sin(angle+.42));
    ctx.closePath();ctx.fillStyle=arm.color;ctx.fill();
    // 标签朝房间外侧让开，免得压在家具上。
    const mx=(a.x+b.x)/2,my=(a.y+b.y)/2;
    let ox=mx-centre.x,oy=my-centre.y;
    const length=Math.hypot(ox,oy)||1;
    ox=mx+ox/length*15;oy=my+oy/length*15;
    ctx.lineWidth=4;ctx.strokeStyle="rgba(255,255,255,.92)";
    ctx.strokeText(arm.label,ox,oy);
    ctx.fillStyle=arm.color;ctx.fillText(arm.label,ox,oy);
  }
  ctx.beginPath();ctx.arc(origin.x,origin.y,3.4,0,Math.PI*2);ctx.fillStyle="#0f172a";ctx.fill();
  let rx=origin.x-centre.x,ry=origin.y-centre.y;
  const radius=Math.hypot(rx,ry)||1;
  rx=origin.x+rx/radius*16;ry=origin.y+ry/radius*16;
  ctx.font='700 12px "Microsoft YaHei",system-ui,sans-serif';
  ctx.lineWidth=4;ctx.strokeStyle="rgba(255,255,255,.92)";
  ctx.strokeText("O (0,0,0)",rx,ry);
  ctx.fillStyle="#0f172a";ctx.fillText("O (0,0,0)",rx,ry);
  ctx.restore();
}
function focalLength(){return H/(2*Math.tan(48*Math.PI/360))}
function screenPoint(event){const rect=canvas.getBoundingClientRect();return [(event.clientX-rect.left)*(W/rect.width),(event.clientY-rect.top)*(H/rect.height)]}
function unprojectToGround(sx,sy){
  const cam=camera(),f=focalLength();
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
const ELEVATION_MAX_PITCH=.12;
function isElevation(){return state.pitch<ELEVATION_MAX_PITCH}
// 光标落点的房间坐标。相机贴地（立面视图）时地面射线求交会退化，宁可不显示也不显示假坐标。
function updateCoordReadout(event){
  const box=document.getElementById("coord");
  if(!box)return;
  const margin=Math.max(room.width_mm,room.depth_mm);
  const [sx,sy]=screenPoint(event);
  const ground=isElevation()?null:unprojectToGround(sx,sy);
  if(!ground){box.hidden=true;return}
  const x=Math.round(ground[0]),y=Math.round(ground[1]);
  if(x<-margin||y<-margin||x>room.width_mm+margin||y>room.depth_mm+margin){box.hidden=true;return}
  const outside=x<0||y<0||x>room.width_mm||y>room.depth_mm;
  box.hidden=false;
  box.textContent=`X ${x} · Y ${y} · Z 0 mm　距西墙 ${x} · 距北墙 ${y}${outside?"（房间外）":""}`;
}
function render(){ctx.clearRect(0,0,W,H);const gradient=ctx.createRadialGradient(W*.5,H*.38,20,W*.5,H*.42,W*.72);gradient.addColorStop(0,"#fff");gradient.addColorStop(1,"#e8eef5");ctx.fillStyle=gradient;ctx.fillRect(0,0,W,H);const cam=camera(),project=projector(cam);drawRoom(project,cam);drawSolids(project,cam);drawOriginAxes(project)}
// 视图预设：default_view 是「复位」回到的那一眼，不是"正交/透视"之分——这张画布永远是透视投影。
const VIEWS={
  default_view:{yaw:DEFAULT_YAW,pitch:DEFAULT_PITCH,distance:DEFAULT_DISTANCE},
  top:{yaw:Math.PI/2,pitch:1.48,distance:diagonal*1.82},
  bottom:{yaw:Math.PI/2,pitch:-1.48,distance:diagonal*1.82},
  front:{yaw:Math.PI/2,pitch:0,distance:diagonal*1.72},
  back:{yaw:-Math.PI/2,pitch:0,distance:diagonal*1.72},
  right:{yaw:0,pitch:0,distance:diagonal*1.72},
  left:{yaw:Math.PI,pitch:0,distance:diagonal*1.72},
};
const ORTHO_VIEWS=["top","bottom","front","back","left","right"];
const isOrthoView=name=>ORTHO_VIEWS.includes(name);
// 旧链接（#view=perspective）继续能用。
const VIEW_ALIASES={perspective:"default_view"};
const VIEW_LABELS={default_view:"默认视角",top:"俯视图",bottom:"仰视图",front:"前视图",back:"后视图",left:"左视图",right:"右视图"};
// 视角标识：下拉回答「在哪个正视图」，复位按钮回答「在不在默认位」。
function syncViewControls(){
  const select=document.getElementById("view-select");
  if(select)select.value=isOrthoView(state.active)?state.active:"free";
  const button=document.querySelector('[data-view="default_view"]');
  if(button)button.setAttribute("aria-pressed",String(state.active==="default_view"));
  status.textContent=VIEW_LABELS[state.active]||"自由视角";
}
function markFree(){state.active="free";syncViewControls()}
function nearAngle(gap){return Math.abs(((gap+Math.PI)%(2*Math.PI)+2*Math.PI)%(2*Math.PI)-Math.PI)}
// 双击时吸到最近的正视图：先看俯仰够不够陡，否则按方位角取最近的立面。
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
function setView(name){
  const key=VIEW_ALIASES[name]||name,preset=VIEWS[key];
  if(!preset)return;
  // 从自由/默认位切进正视图时先记下这一眼，双击时回到它。
  if(isOrthoView(key)&&!isOrthoView(state.active)){
    state.freeView={yaw:state.yaw,pitch:state.pitch,distance:state.distance};
  }
  Object.assign(state,{yaw:preset.yaw,pitch:preset.pitch,distance:preset.distance});
  state.active=key;
  syncViewControls();
  render();
}
// 回到「进正视图之前那一眼」；没记过就回默认视角。
function restoreFreeView(){
  const remembered=state.freeView;
  if(!remembered){setView("default_view");return}
  Object.assign(state,{yaw:remembered.yaw,pitch:remembered.pitch,distance:remembered.distance});
  state.active=(Math.abs(state.yaw-VIEWS.default_view.yaw)<1e-3&&
    Math.abs(state.pitch-VIEWS.default_view.pitch)<1e-3)?"default_view":"free";
  syncViewControls();
  render();
}
canvas.addEventListener("pointerdown",e=>{state.dragging=true;state.lastX=e.clientX;state.lastY=e.clientY;canvas.setPointerCapture(e.pointerId);canvas.classList.add("dragging")});
canvas.addEventListener("pointermove",e=>{if(!state.dragging)return;const dx=e.clientX-state.lastX,dy=e.clientY-state.lastY;state.lastX=e.clientX;state.lastY=e.clientY;
  // 转视角跟手：往右拖，靠近自己的那一边就往右走；下限 -1.48 才落得到仰视。
  state.yaw+=dx*.008;state.pitch=clamp(state.pitch+dy*.006,-1.48,1.48);markFree();render()});
canvas.addEventListener("pointerup",e=>{state.dragging=false;canvas.releasePointerCapture(e.pointerId);canvas.classList.remove("dragging")});
canvas.addEventListener("pointercancel",()=>{state.dragging=false;canvas.classList.remove("dragging")});
canvas.addEventListener("wheel",e=>{e.preventDefault();state.distance=clamp(state.distance*Math.exp(e.deltaY*.001),diagonal*.72,diagonal*3.4);markFree();render()},{passive:false});
canvas.addEventListener("pointermove",updateCoordReadout);
canvas.addEventListener("pointerleave",()=>{const box=document.getElementById("coord");if(box)box.hidden=true});
// 双击：自由/默认位 → 吸到最近的正视图；已经在正视图上 → 回到进它之前那一眼。
canvas.addEventListener("dblclick",()=>{
  if(isOrthoView(state.active)){restoreFreeView();return}
  state.freeView={yaw:state.yaw,pitch:state.pitch,distance:state.distance};
  setView(nearestOrthoView());
});
document.querySelectorAll("[data-view]").forEach(button=>button.addEventListener("click",()=>setView(button.dataset.view)));
const viewSelect=document.getElementById("view-select");
if(viewSelect)viewSelect.addEventListener("change",()=>{
  const name=viewSelect.value;
  if(!VIEWS[name]){syncViewControls();return}
  setView(name);
});
window.addEventListener("keydown",e=>{if(e.key.toLowerCase()==="r")setView("default_view")});
// 深链：#view=top 之类直接开某个视角（#view=perspective 走别名）。
if(typeof location!=="undefined"&&location.hash.length>1){
  const wanted=new URLSearchParams(location.hash.slice(1)).get("view");
  const key=wanted?(VIEW_ALIASES[wanted]||wanted):null;
  if(key&&VIEWS[key])setView(key);
}
render();
syncViewControls();
})();
</script>
</body>
</html>
"""
