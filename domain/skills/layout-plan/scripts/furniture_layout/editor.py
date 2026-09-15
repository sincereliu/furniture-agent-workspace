"""Generate an editable room-scene view.

点选一件家具后拖动：靠墙件沿墙滑动（发 `offset_mm`），自由件平面移动（发
`origin_x_mm`/`origin_y_mm`）。选中后家具上方有一个橙色圆点，拖它就是旋转
（发 `rotation_z_deg`）；墙摆的旋转由 `host_wall` 派生，所以旋转墙摆会在同一
个 op 里改成自由摆放。靠墙件往房间内拖过阈值也会转成自由摆放。

拖动期间只做本地预览，松手才发**一个** edit op，由后端重算并校验——失败会显示
原因，不回退本地已画的形状。
"""

from __future__ import annotations

from html import escape
import json
from typing import Any

from .scene import RoomScene


EDITOR_WIDTH_PX = 960
EDITOR_HEIGHT_PX = 720


def render_editor(scene_id: str, scene: RoomScene) -> dict[str, object]:
    """Return self-contained HTML that edits one saved room scene."""
    payload: dict[str, Any] = {
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
    scene_json = (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    html = (
        _EDITOR_HTML.replace("__SCENE_JSON__", scene_json)
        .replace("__SCENE_ID__", escape(scene_id, quote=True))
        .replace("__ROOM_NAME__", escape(scene.room.name, quote=True))
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
            "drag_orbit",
            "wheel_zoom",
        ],
        "alt_text": (
            f"{scene.room.name}的可编辑包络视图；点击家具包络任意位置可选中，"
            "拖动改位置（靠墙件沿墙滑动，拖离墙面或拖橙色圆点会转成自由摆放），"
            "拖橙色圆点旋转；空白处拖动旋转视角"
        ),
        "html": html,
    }


_EDITOR_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'">
<title>__ROOM_NAME__ · 布局编辑</title>
<style>
:root{font-family:Inter,"Microsoft YaHei",system-ui,sans-serif;color:#0f172a;background:#eef2f7}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;padding:16px}
.editor{width:min(960px,100%);background:#f8fafc;border:1px solid #cbd5e1;border-radius:18px;box-shadow:0 18px 50px rgba(15,23,42,.16);overflow:hidden}
header{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:16px 18px 12px;background:#fff;border-bottom:1px solid #e2e8f0}
h1{font-size:18px;margin:0 0 4px}.hint{font-size:12px;color:#64748b;margin:0}
.toolbar{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:7px}
button{appearance:none;border:1px solid #cbd5e1;background:#fff;color:#334155;border-radius:9px;padding:7px 10px;font:inherit;font-size:12px;font-weight:600;cursor:pointer}
button:hover,button:focus-visible{border-color:#2563eb;color:#1d4ed8;outline:none}
button[aria-pressed="true"]{background:#2563eb;border-color:#2563eb;color:#fff}
.stage{position:relative;background:radial-gradient(circle at 50% 38%,#fff 0,#f1f5f9 58%,#e2e8f0 100%)}
canvas{display:block;width:100%;height:auto;touch-action:none;cursor:default}
canvas.orbiting{cursor:grabbing}
canvas.moving{cursor:move}
.badge{position:absolute;left:16px;bottom:14px;padding:7px 10px;border-radius:9px;background:rgba(255,255,255,.9);border:1px solid rgba(203,213,225,.9);font-size:12px;color:#475569;backdrop-filter:blur(6px);max-width:70%}
.badge.error{color:#b91c1c;border-color:#fecaca;background:rgba(254,242,242,.94)}
footer{display:flex;justify-content:space-between;gap:16px;padding:10px 18px 13px;background:#fff;border-top:1px solid #e2e8f0;font-size:12px;color:#64748b}
</style>
</head>
<body>
<main class="editor" aria-label="可编辑家具布局">
  <header>
    <div><h1>__ROOM_NAME__ · 布局编辑</h1><p class="hint">点击选中家具 · 拖动移动 · 空白处拖拽转视角 · 滚轮缩放</p></div>
    <nav class="toolbar" aria-label="视角选择">
      <button type="button" data-view="perspective" aria-pressed="true">透视</button>
      <button type="button" data-view="top" aria-pressed="false">俯视</button>
      <button type="button" data-view="reset" aria-pressed="false">重置视角</button>
    </nav>
  </header>
  <section class="stage">
    <canvas id="scene" width="960" height="600" aria-label="房间与家具包络；点选家具后可拖动移动、拖橙色圆点旋转"></canvas>
    <div class="badge" id="status">点击一件家具开始</div>
  </section>
  <footer><span>透明线框：房间</span><span>蓝色实体：家具包络（可拖动移动）</span><span>橙色圆点：旋转，按住 Shift 精细到 1°</span><span>红色实体：障碍物</span></footer>
</main>
<script id="scene-data" type="application/json">__SCENE_JSON__</script>
<script>
(()=>{
"use strict";
const SCENE_ID="__SCENE_ID__";
const scene=JSON.parse(document.getElementById("scene-data").textContent);
const normalizeItems=items=>items.map(item=>{
  const placement=item.placement||{};
  const zStart=item.z_start!==undefined?item.z_start:(placement.origin_z_mm||0);
  return {...item,placement,z_start:zStart,z_end:item.z_end!==undefined?item.z_end:zStart+(item.height||0),footprint:(item.footprint||[]).map(p=>Array.isArray(p)?[p[0],p[1]]:[p.x_mm,p.y_mm])};
});
scene.items=normalizeItems(scene.items||[]);
const canvas=document.getElementById("scene"),ctx=canvas.getContext("2d"),status=document.getElementById("status");
const W=canvas.width,H=canvas.height,room=scene.room;
const target=[room.width_mm/2,room.depth_mm/2,room.height_mm*.42];
const diagonal=Math.hypot(room.width_mm,room.depth_mm,room.height_mm);
const defaults={yaw:-Math.PI/4,pitch:.95,distance:diagonal*1.28};
const state={...defaults,orbiting:false,lastX:0,lastY:0,active:"perspective",selectedId:null,handle:null};
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const sub=(a,b)=>[a[0]-b[0],a[1]-b[1],a[2]-b[2]];
const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const norm=a=>{const n=Math.hypot(...a)||1;return a.map(v=>v/n)};
const midpoint=pts=>pts[0].map((_,i)=>pts.reduce((s,p)=>s+p[i],0)/pts.length);
const focal=()=>H/(2*Math.tan(48*Math.PI/360));
function camera(){
  const cp=Math.cos(state.pitch),sp=Math.sin(state.pitch),cy=Math.cos(state.yaw),sy=Math.sin(state.yaw);
  const position=[target[0]+state.distance*cp*cy,target[1]+state.distance*cp*sy,target[2]+state.distance*sp];
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
function screenPoint(event){
  const rect=canvas.getBoundingClientRect();
  return [(event.clientX-rect.left)*(W/rect.width),(event.clientY-rect.top)*(H/rect.height)];
}
function boxVertices(box){const b=box.footprint.map(p=>[p[0],p[1],box.z_start]),t=box.footprint.map(p=>[p[0],p[1],box.z_end]);return[...b,...t]}
const boxFaces=[[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]];
const roomFaces=[[0,1,2,3],[4,7,6,5],[0,4,5,1],[1,5,6,2],[2,6,7,3],[3,7,4,0]];
const roomEdges=[[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
function visible(face,verts,cam){const a=verts[face[0]],b=verts[face[1]],c=verts[face[2]],normal=cross(sub(b,a),sub(c,b));return dot(normal,sub(cam.position,midpoint(face.map(i=>verts[i]))))>0}
function path(points){ctx.beginPath();ctx.moveTo(points[0].x,points[0].y);for(const p of points.slice(1))ctx.lineTo(p.x,p.y);ctx.closePath()}
function roomVertices(){const w=room.width_mm,d=room.depth_mm,h=room.height_mm;return[[0,0,0],[w,0,0],[w,d,0],[0,d,0],[0,0,h],[w,0,h],[w,d,h],[0,d,h]]}
function openingPoints(o){const s=o.offset_mm,e=s+o.width_mm,z0=o.sill_height_mm,z1=z0+o.height_mm,w=room.width_mm,d=room.depth_mm;if(o.wall==="north")return[[s,0,z0],[e,0,z0],[e,0,z1],[s,0,z1]];if(o.wall==="east")return[[w,s,z0],[w,e,z0],[w,e,z1],[w,s,z1]];if(o.wall==="south")return[[w-s,d,z0],[w-e,d,z0],[w-e,d,z1],[w-s,d,z1]];return[[0,d-s,z0],[0,d-e,z0],[0,d-e,z1],[0,d-s,z1]]}
function drawRoom(project,cam){
  const verts=roomVertices(),faces=roomFaces.map(face=>({face,depth:face.reduce((s,i)=>s+project(verts[i]).depth,0)/face.length})).sort((a,b)=>b.depth-a.depth);
  for(const item of faces){const pts=item.face.map(i=>project(verts[i]));path(pts);ctx.fillStyle="rgba(186,230,253,.055)";ctx.fill()}
  for(const opening of scene.openings){const pts=openingPoints(opening).map(project);path(pts);ctx.fillStyle="rgba(34,211,238,.34)";ctx.fill();ctx.strokeStyle="rgba(8,145,178,.8)";ctx.lineWidth=2;ctx.stroke()}
  ctx.strokeStyle="rgba(71,85,105,.72)";ctx.lineWidth=1.6;for(const edge of roomEdges){const a=project(verts[edge[0]]),b=project(verts[edge[1]]);ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke()}
}
function drawSolids(project,cam){
  const faces=[];
  for(const obstacle of scene.obstacles){
    const verts=boxVertices(obstacle);
    for(const face of boxFaces)if(visible(face,verts,cam))faces.push({points:face.map(i=>project(verts[i])),depth:face.reduce((s,i)=>s+project(verts[i]).depth,0)/face.length,fill:"#dc2626",stroke:"#7f1d1d"});
  }
  for(const box of scene.items){
    const verts=boxVertices(box),selected=box.id===state.selectedId;
    for(const face of boxFaces)if(visible(face,verts,cam))faces.push({points:face.map(i=>project(verts[i])),depth:face.reduce((s,i)=>s+project(verts[i]).depth,0)/face.length,fill:selected?"#f59e0b":"#2563eb",stroke:selected?"#92400e":"#172554"});
  }
  faces.sort((a,b)=>b.depth-a.depth);
  for(const face of faces){path(face.points);ctx.fillStyle=face.fill;ctx.fill();ctx.strokeStyle=face.stroke;ctx.lineWidth=2;ctx.stroke()}
  ctx.font="700 16px Microsoft YaHei, sans-serif";ctx.textAlign="center";ctx.textBaseline="middle";
  for(const f of scene.items){
    const c=[f.footprint.reduce((s,p)=>s+p[0],0)/4,f.footprint.reduce((s,p)=>s+p[1],0)/4,(f.z_start+f.z_end)/2],p=project(c);
    ctx.lineWidth=4;ctx.strokeStyle="rgba(15,23,42,.9)";ctx.strokeText(f.label,p.x,p.y);ctx.fillStyle="#fff";ctx.fillText(f.label,p.x,p.y);
  }
}
function drawHandle(project){
  const item=scene.items.find(candidate=>candidate.id===state.selectedId);
  if(!item){state.handle=null;return}
  const center=footprintCenter(item),top=project([center[0],center[1],item.z_end]);
  const handle={x:clamp(top.x,18,W-18),y:clamp(top.y-44,18,H-18)};
  state.handle=handle;
  ctx.strokeStyle="rgba(245,158,11,.85)";ctx.lineWidth=2;
  ctx.beginPath();ctx.moveTo(top.x,top.y);ctx.lineTo(handle.x,handle.y);ctx.stroke();
  ctx.beginPath();ctx.arc(handle.x,handle.y,10,0,Math.PI*2);ctx.fillStyle="#f59e0b";ctx.fill();
  ctx.strokeStyle="#92400e";ctx.lineWidth=2;ctx.stroke();
  ctx.beginPath();ctx.arc(handle.x,handle.y,4,0,Math.PI*2);ctx.fillStyle="#fff";ctx.fill();
}
function render(){
  ctx.clearRect(0,0,W,H);
  const gradient=ctx.createRadialGradient(W*.5,H*.38,20,W*.5,H*.42,W*.72);gradient.addColorStop(0,"#fff");gradient.addColorStop(1,"#e8eef5");ctx.fillStyle=gradient;ctx.fillRect(0,0,W,H);
  const cam=camera(),project=projector(cam);drawRoom(project,cam);drawSolids(project,cam);drawHandle(project);
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
      if(distance>HIT_TOLERANCE_PX)continue;
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
// 旋转会让包络扫出墙体（贴着墙的长柜尤甚）；和拖动一样，平移到最小位移把包络收回房间内。
function keepInsideRoom(item){
  const xs=item.footprint.map(point=>point[0]),ys=item.footprint.map(point=>point[1]);
  const shiftX=clamp(0,-Math.min(...xs),room.width_mm-Math.max(...xs));
  const shiftY=clamp(0,-Math.min(...ys),room.depth_mm-Math.max(...ys));
  if(!shiftX&&!shiftY)return;
  item.placement.origin_x_mm+=shiftX;item.placement.origin_y_mm+=shiftY;
  item.footprint=item.footprint.map(point=>[point[0]+shiftX,point[1]+shiftY]);
}
function reanchorRotation(item,center,rotationDeg){
  // 墙摆转到原角度就还是墙摆：别因为一点点拖动被吸附回原角，就悄悄脱离墙面。
  const current=item.placement;
  if(current.mode==="wall"&&normalizeAngle(rotationDeg)===normalizeAngle(current.rotation_z_deg||0))return;
  const angle=rotationDeg*Math.PI/180,cosine=Math.cos(angle),sine=Math.sin(angle);
  const halfWidth=item.width/2,halfDepth=item.depth/2;
  const originX=center[0]-(halfWidth*cosine-halfDepth*sine);
  const originY=center[1]-(halfWidth*sine+halfDepth*cosine);
  const placement=item.placement;
  // 墙面的旋转由 host_wall 派生，转不动；要旋转就同一次 op 里改成自由摆放。
  placement.mode="free";placement.host_wall=null;placement.offset_mm=null;
  placement.origin_x_mm=originX;placement.origin_y_mm=originY;placement.rotation_z_deg=rotationDeg;
  item.footprint=localFootprint(item,originX,originY,rotationDeg);
  keepInsideRoom(item);
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
function setStatus(text,isError){status.textContent=text;status.classList.toggle("error",Boolean(isError))}
const DRAG_THRESHOLD_PX=4;
const HANDLE_HIT_PX=18;
const WALL_DETACH_PX=26;
const HIT_TOLERANCE_PX=5;
function wallLength(wall){return wall==="north"||wall==="south"?room.width_mm:(wall==="east"||wall==="west"?room.depth_mm:0)}
function footprintSpan(item,axis){const values=item.footprint.map(point=>axis==="x"?point[0]:point[1]);return Math.max(...values)-Math.min(...values)}
function clampShift(item,dx,dy){
  const xs=item.footprint.map(point=>point[0]),ys=item.footprint.map(point=>point[1]);
  return [
    clamp(dx,-Math.min(...xs),room.width_mm-Math.max(...xs)),
    clamp(dy,-Math.min(...ys),room.depth_mm-Math.max(...ys)),
  ];
}
function applyLocalDrag(item,dx,dy){
  const placement=item.placement;
  item.footprint=drag.startFootprint.map(point=>[...point]);
  if(placement.mode==="wall"){
    const sign=wallSign(placement.host_wall);
    if(!sign)return;
    const along=sign[0]==="x"?dx:dy;
    const startOffset=drag.startOffset||0;
    const maxOffset=Math.max(0,wallLength(placement.host_wall)-footprintSpan(item,sign[0]));
    const nextOffset=clamp(startOffset+along*sign[1],0,maxOffset);
    const delta=(nextOffset-startOffset)*sign[1];
    const axis=sign[0]==="x"?0:1;
    placement.offset_mm=nextOffset;
    item.footprint.forEach(point=>{point[axis]+=delta});
    return;
  }
  const [safeX,safeY]=clampShift(item,dx,dy);
  placement.origin_x_mm=drag.startOrigin[0]+safeX;
  placement.origin_y_mm=drag.startOrigin[1]+safeY;
  item.footprint.forEach(point=>{point[0]+=safeX;point[1]+=safeY});
}
// 墙摆只有一个自由度（沿墙 offset）；把家具往房间内拖够远就转成自由摆放，
// 用当前派生原点当自由原点，位置不跳。
function detachToFree(activeDrag){
  const placement=activeDrag.item.placement;
  placement.mode="free";placement.host_wall=null;placement.offset_mm=null;
  placement.origin_x_mm=activeDrag.startOrigin[0];
  placement.origin_y_mm=activeDrag.startOrigin[1];
  placement.rotation_z_deg=placement.rotation_z_deg||0;
  activeDrag.item.footprint=activeDrag.startFootprint.map(point=>[...point]);
  setStatus(`${activeDrag.item.label} 已离开墙面，改为自由摆放`);
}
function selectHint(item){
  return item.placement.mode==="wall"
    ?`已选中 ${item.label}：沿墙拖动，向外拖可离开墙面，拖圆点可旋转`
    :`已选中 ${item.label}：拖动可移动，拖圆点可旋转`;
}
function handleAt(sx,sy){
  const handle=state.handle;
  if(!handle)return null;
  if(Math.hypot(handle.x-sx,handle.y-sy)>HANDLE_HIT_PX)return null;
  return scene.items.find(item=>item.id===state.selectedId)||null;
}
let drag=null;
canvas.addEventListener("pointerdown",event=>{
  const [sx,sy]=screenPoint(event),ground=unprojectToGround(sx,sy);
  const handleItem=handleAt(sx,sy);
  if(handleItem){
    const center=footprintCenter(handleItem),height=(handleItem.z_start+handleItem.z_end)/2;
    const origin=projector(camera())([center[0],center[1],height]);
    const startAngle=Math.atan2(sy-origin.y,sx-origin.x)*180/Math.PI;
    drag={kind:"rotate",item:handleItem,center,height,origin,startAngle,lastAngle:startAngle,
      accumulated:0,moved:false,startScreen:[sx,sy],
      startRotation:handleItem.placement.rotation_z_deg||0,startMode:handleItem.placement.mode,
      sign:rotationSign(center,height)};
    canvas.classList.add("moving");
    setStatus(`旋转 ${handleItem.label}…`);
    canvas.setPointerCapture(event.pointerId);
    return;
  }
  const hit=hitTest(sx,sy);
  if(hit&&ground){
    const placement=hit.placement;
    state.selectedId=hit.id;
    drag={kind:"move",item:hit,ground,startScreen:[sx,sy],moved:false,
      startOrigin:[placement.origin_x_mm||0,placement.origin_y_mm||0],
      startOffset:placement.offset_mm,
      startFootprint:hit.footprint.map(point=>[...point])};
    if(placement.mode==="wall"){
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
  state.selectedId=null;
  state.orbiting=true;state.lastX=event.clientX;state.lastY=event.clientY;
  canvas.classList.add("orbiting");canvas.setPointerCapture(event.pointerId);
  render();
});
canvas.addEventListener("pointermove",event=>{
  if(drag){
    const [sx,sy]=screenPoint(event);
    if(!drag.moved){
      if(Math.hypot(sx-drag.startScreen[0],sy-drag.startScreen[1])<DRAG_THRESHOLD_PX)return;
      drag.moved=true;
    }
    if(drag.kind==="rotate"){
      const angle=Math.atan2(sy-drag.origin.y,sx-drag.origin.x)*180/Math.PI;
      let delta=angle-drag.lastAngle;
      if(delta>180)delta-=360;
      if(delta<-180)delta+=360;
      drag.accumulated+=delta;drag.lastAngle=angle;
      const next=snapAngle(drag.startRotation+drag.sign*drag.accumulated,event.shiftKey?1:15);
      reanchorRotation(drag.item,drag.center,next);
      setStatus(`旋转 ${drag.item.label}：${Math.round(normalizeAngle(next))}°${event.shiftKey?"（精细）":""}`);
      render();
      return;
    }
    if(drag.item.placement.mode==="wall"&&drag.perpScreen){
      const away=(sx-drag.startScreen[0])*drag.perpScreen.x+(sy-drag.startScreen[1])*drag.perpScreen.y;
      if(away>WALL_DETACH_PX)detachToFree(drag);
    }
    const ground=unprojectToGround(sx,sy);
    if(!ground)return;
    const moveX=ground[0]-drag.ground[0],moveY=ground[1]-drag.ground[1];
    applyLocalDrag(drag.item,moveX,moveY);
    setStatus(`拖动 ${drag.item.label}… 位移 ${Math.hypot(moveX,moveY).toFixed(0)}mm`);
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
  const placement=item.placement,op={op:kind==="rotate"?"rotate":"move",item_id:item.id};
  if(kind==="rotate")op.rotation_z_deg=Math.round(normalizeAngle(placement.rotation_z_deg)*10)/10;
  if(placement.mode==="wall"){op.offset_mm=Math.round(placement.offset_mm)}
  else{op.mode="free";op.origin_x_mm=Math.round(placement.origin_x_mm);op.origin_y_mm=Math.round(placement.origin_y_mm)}
  try{
    const response=await fetch(`/api/room-scene/${encodeURIComponent(SCENE_ID)}/edit`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(op)});
    if(!response.ok){
      const detail=await response.json().catch(()=>({}));
      setStatus("改动被拒绝，已回到原位："+(detail.detail||response.status),true);
      await reload();
      return false;
    }
    const next=await response.json();
    scene.items=normalizeItems(next.items||[]);
    setStatus(`已保存 ${item.label}`);
    return true;
  }catch(error){
    setStatus("保存失败："+error,true);
    await reload();
    return false;
  }
}
canvas.addEventListener("pointerup",event=>{
  if(drag){
    const item=drag.item,moved=drag.moved,kind=drag.kind;
    // 吸附回原角度的旋转不产生 op：否则会把墙摆包成 mode=free + offset_mm 的非法 op。
    const unchanged=kind==="rotate"
      &&item.placement.rotation_z_deg===drag.startRotation
      &&item.placement.mode===drag.startMode;
    drag=null;canvas.classList.remove("moving");
    canvas.releasePointerCapture(event.pointerId);
    if(moved&&!unchanged){persist(item,kind).then(()=>{render()})}
    else{setStatus(selectHint(item));render()}
    return;
  }
  if(state.orbiting){state.orbiting=false;canvas.classList.remove("orbiting");canvas.releasePointerCapture(event.pointerId)}
});
canvas.addEventListener("pointercancel",()=>{drag=null;state.orbiting=false;canvas.classList.remove("moving","orbiting")});
canvas.addEventListener("wheel",event=>{event.preventDefault();state.distance=clamp(state.distance*Math.exp(event.deltaY*.001),diagonal*.72,diagonal*3.4);render()},{passive:false});
function setView(name){
  if(name==="reset"||name==="perspective")Object.assign(state,defaults);
  if(name==="top")Object.assign(state,{yaw:-Math.PI/2,pitch:1.48,distance:diagonal*1.82});
  document.querySelectorAll("[data-view]").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.view===name)));
  render();
}
document.querySelectorAll("[data-view]").forEach(button=>button.addEventListener("click",()=>setView(button.dataset.view)));
render();
})();
</script>
</body>
</html>
"""
