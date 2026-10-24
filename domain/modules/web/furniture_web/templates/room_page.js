import { mountLayout } from "/layout-view/layout_scene.js";
import { normalizeItems } from "/layout-view/layout_payload.js";
import { createLayoutPersistence, LayoutWriteError } from "/layout-view/layout_persistence.js";
import { createDragTransaction, poseOperation } from "/layout-view/layout_interaction.js";
import {
  contactStop, detailValues, distancesOf, footprintCenter, heightProbe,
  normalizeAngle, placementStop, resolveInteger,
  setItemHeight, solvePlanarDrag,
  solveRotation, syncPlacementGeometry, wallLabel, wallNormal,
} from "/layout-view/layout_solver.js";
import {
  ELEVATION_MAX_PITCH, baseFit, fitDistance, horizontalAxis,
  isOrthoView, nearAngle, rotationSign, verticalPlaneScale,
} from "/layout-view/layout_camera.js";
import {
  Component, Injectable, signal, computed, effect, bootstrapApplication,
} from "/layout-view/layout_angular.js";

const pageConfigEl=document.getElementById("page-config");
const PAGE_CONFIG=pageConfigEl?JSON.parse(pageConfigEl.textContent||"{}"):{};
const SCENE_ID="__SCENE_ID__";
const READ_ONLY=__READ_ONLY__;
const SHARE_FORM=__SHARE_FORM__;
const PROJECT_EDIT_URL=__EDIT_URL__;
const PROJECT_UNDO_URL=__UNDO_URL__;
const PANEL_URL_BASE=__PANEL_URL_BASE__;
const LAYOUT_URL=__LAYOUT_URL__;
let rooms=__ROOMS_JSON__;
const initialLayoutVersion=__VERSION_JSON__;

// Angular Reactive Signals 与职责清晰的 Store
const selectedIdSignal=signal(null);
const activeViewSignal=signal("default_view");
const dimsModeSignal=signal("selected");
const statusToastSignal=signal({text:"点击一件家具开始",kind:""});
const roomIndexSignal=signal(0);
const leaseSignal=signal(null);
const workingSignal=signal(null);
const pendingDecisionsSignal=signal([]);

const syncStore={
  events:null,
  leaseQuery:"",
  roomIndex:0,
};
const pullStore={now:1,from:1,end:1};
const uiStore={
  placing:false,
  scale:1,
  panelSignature:null,
  detailItemId:undefined,
  viewAnimation:0,
  resizing:0,
};

function plansPanels(item){
  return !!item && item.manufacture!==false
    && (item.furniture_category==="floor_cabinet" || item.furniture_category==="wall_cabinet");
}
function loadCanvasItems(raw){
  return normalizeItems(raw||[]);
}

const scene=JSON.parse(document.getElementById("scene-data").textContent);
scene.items=loadCanvasItems(scene.items);
scene.obstacles=scene.obstacles||[];
scene.openings=scene.openings||[];
const canvas=document.getElementById("scene"),status=document.getElementById("status");
const view=mountLayout(canvas);
const layoutPersistence=createLayoutPersistence({
  readUrl:LAYOUT_URL||`/api/room-scene/${encodeURIComponent(SCENE_ID)}`,
  editUrl:PROJECT_EDIT_URL||`/api/room-scene/${encodeURIComponent(SCENE_ID)}/edit`,
  version:initialLayoutVersion,versioned:Boolean(PROJECT_EDIT_URL),
  getLeaseToken:()=>leaseStore.token,
  isInteracting:()=>Boolean(drag||state.orbiting||state.panning),
  onMetadata:applyDocumentMetadata,
  onDocument:showDocument,
});
let room=scene.room;
let HOME_TARGET=[room.width_mm/2,room.depth_mm/2,room.height_mm*.3];
const target=[...HOME_TARGET];
let diagonal=Math.hypot(room.width_mm,room.depth_mm,room.height_mm);

function bindRoom(){
  room=scene.room;
  HOME_TARGET=[room.width_mm/2,room.depth_mm/2,room.height_mm*.3];
  diagonal=Math.hypot(room.width_mm,room.depth_mm,room.height_mm);
  const roomMeta=document.getElementById("room-meta");
  if(roomMeta){
    roomMeta.textContent=[`${Math.round(room.width_mm)} × ${Math.round(room.depth_mm)} × ${Math.round(room.height_mm)} mm`,
      `${scene.items.length} 件家具`].join(" · ");
  }
  const heading=document.getElementById("heading");
  if(heading){
    heading.textContent=(room.name||"房间")+" · "+(PAGE_CONFIG.heading_suffix||__HEADING_SUFFIX__);
    document.title=heading.textContent;
  }
}

/* ---------- 1. 视角预设与相机过渡 ---------- */
const DEFAULT_YAW=Math.PI*5/12,DEFAULT_PITCH=.72;
const VIEWS={
  default_view:{yaw:DEFAULT_YAW,pitch:DEFAULT_PITCH},
  top:{yaw:Math.PI/2,pitch:1.48},
  bottom:{yaw:Math.PI/2,pitch:-1.48},
  front:{yaw:Math.PI/2,pitch:0},
  back:{yaw:-Math.PI/2,pitch:0},
  right:{yaw:0,pitch:0},
  left:{yaw:Math.PI,pitch:0},
};
function fitCanvas(){view.resize();uiStore.scale=1}
const px=css=>css*uiStore.scale;
function camera(){return view.basis()}
function projector(){return point=>view.project(point[0],point[1],point[2]||0)}
function unprojectToGround(sx,sy){
  const rect=canvas.getBoundingClientRect();
  return view.ground(rect.left+sx,rect.top+sy);
}
function screenPoint(event){
  const rect=canvas.getBoundingClientRect();
  return [event.clientX-rect.left,event.clientY-rect.top];
}
function setPullProgress(k){pullStore.now=pullStore.from+(pullStore.end-pullStore.from)*k}

function render(){
  uiStore.placing=true;
  const fit=baseFit(canvas,diagonal);
  state.distance=fit*pullStore.now;
  view.setFovForZoom(state.zoom*pullStore.now);
  view.setView(state.yaw,state.pitch,state.distance,target);
  uiStore.placing=false;
  window.__state={active:state.active,yaw:state.yaw,pitch:state.pitch,
    distance:state.distance,zoom:state.zoom,
    freeView:state.freeView?{...state.freeView}:null,
    pullFrom:pullStore.from,pullEnd:pullStore.end,pullNow:pullStore.now,
    animating:uiStore.viewAnimation!==0};
  view.sync(displayScene(),{selectedId:state.selectedId,dims:state.dims,readOnly:READ_ONLY,blockedId:state.blocked});
  syncPanel();
}

function setStatus(text,kind){
  statusToastSignal.set({text,kind:kind||""});
  status.textContent=text;
  status.classList.toggle("warn",kind==="warn");
  status.classList.toggle("error",kind==="error");
}
function isElevation(){return state.pitch<ELEVATION_MAX_PITCH}

/* ---------- 2. 拖拽、旋转与摆放求解桥接 ---------- */
function applyLocalDrag(item,dx,dy,startOrigin){
  const origin=startOrigin||[item.placement.origin_x_mm||0,item.placement.origin_y_mm||0];
  const blocker=solvePlanarDrag(scene,item,origin,dx,dy);
  return blocker;
}

function fillsWall(item){return !!(item&&item.placement&&item.placement.fill)}
function selectHint(item){
  if(READ_ONLY)return `已选中 ${item.label}`;
  if(fillsWall(item))return `已选中 ${item.label}：铺满这面墙，可改离地高度`;
  return item.placement.mode==="wall"
    ?`已选中 ${item.label}：靠墙贴合，向外拖可离开墙面`
    :`已选中 ${item.label}：拖动可移动`;
}

/* ---------- 3. 右侧面板与数值微调 ---------- */
const escapeHtml=value=>String(value).replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
function syncPanel(){
  const items=displayScene().items;
  const signature=items.map(item=>`${item.id}:${item.label}:${item.placement.mode}`).join("|")+"#"+state.selectedId;
  const list=document.getElementById("item-list");
  if(list&&signature!==uiStore.panelSignature){
    uiStore.panelSignature=signature;
    list.innerHTML=items.map(item=>`<li><button type="button" class="item-row${item.id===state.selectedId?" active":""}" data-item="${escapeHtml(item.id)}">
      <span class="dot"></span><span class="name">${escapeHtml(item.label)}</span>
      <span class="mode">${item.placement.mode==="wall"?"靠墙":"自由"}</span></button></li>`).join("");
  }
  const countEl=document.getElementById("item-count");
  if(countEl)countEl.textContent=`${scene.items.length}`;
  syncDetail();
}

function detailMarkup(item){
  const round=n=>Math.round(n);
  const fills=fillsWall(item);
  const gapRow=(label,key)=>(READ_ONLY||fills)
    ? `<dt>${label}</dt><dd><span data-gap="${key}"></span> mm<span class="who" data-who="${key}"></span></dd>`
    : `<dt>${label}</dt><dd class="gap-row"><button type="button" class="step" data-gap-step="${key}" data-delta="-10" aria-label="${label}减 10">−</button><input class="num" type="number" step="1" data-gap="${key}" aria-label="${label}"><button type="button" class="step" data-gap-step="${key}" data-delta="10" aria-label="${label}加 10">＋</button><span class="who" data-who="${key}"></span></dd>`;
  const rotationRow=(READ_ONLY||fills)
    ? `<span data-field="rotation"></span>°<span class="who" data-front></span>`
    : `<button type="button" class="step" data-rotation-step data-delta="-15" aria-label="逆时针 15°">−</button><input class="num" type="number" step="1" data-rotation data-field="rotation" aria-label="朝向角度"><button type="button" class="step" data-rotation-step data-delta="15" aria-label="顺时针 15°">＋</button><span class="who">°</span><span class="who" data-front></span>`;
  const heightRow=READ_ONLY
    ? `<span data-field="height"></span> mm`
    : `<button type="button" class="step" data-height="-50" aria-label="降低 50">−</button><input class="num" type="number" step="1" data-height-input data-field="height" aria-label="离地高度"><button type="button" class="step" data-height="50" aria-label="升高 50">＋</button><span class="who">mm</span>`;
  const hint=READ_ONLY
    ? `<p class="hint-inline">${SHARE_FORM
        ? "只读分享：这一页只能看，位置由房主那边更新。"
        : "只读预览：位置由对话更新；要自己拖，用草稿页。"}</p>`
    : fills
      ? `<p class="hint-inline">这一台铺满剩下的空墙。沿墙位置、朝向和净距不在这里改。离地高度可以改。</p>`
      : `<p class="hint-inline">可以直接输入任意毫米值，回车生效。宽、深、高改的是这一件的外形，保存后给板件用；改过的这间要再看一眼。输入框的上下箭头走 1；旁边的 − / ＋ 走整数档（净距 10 · 离地 50 · 朝向 15）。到不了就只挪到能到的地方，并在左下角说明是越界、干涉还是遮挡门窗洞口。</p>`;
  const sizeReadout=`<dt>尺寸</dt><dd>${round(item.width)}×${round(item.depth)}×${round(item.height)}</dd>`;
  const sizeRow=READ_ONLY
    ? sizeReadout
    : fills
      ? `<dt>尺寸</dt><dd>${round(item.width)}×${round(item.depth)}×${round(item.height)} · 沿墙铺满，宽度由墙算出</dd>`
      : `<dt>尺寸</dt><dd class="size-edit"><input class="num size" type="number" step="1" min="1" data-size="width" aria-label="宽"><span class="who">×</span><input class="num size" type="number" step="1" min="1" data-size="depth" aria-label="深"><span class="who">×</span><input class="num size" type="number" step="1" min="1" data-size="height" aria-label="高"><span class="who">mm</span></dd>`;
  return `<div class="detail-container">
    <div class="selected-hero">
      <div class="selected-hero-top">
        <div class="selected-title-wrap">
          <span class="selected-dot"></span>
          <h3 class="selected-title">${escapeHtml(item.label)}</h3>
        </div>
        <div class="selected-badges">
          <span class="badge-mode" data-field="mode"></span>
          <span class="badge-front" data-front></span>
        </div>
      </div>
    </div>
    <dl class="detail">
      <dt class="row-name">名称</dt><dd class="row-name">${escapeHtml(item.label)}</dd>
      ${sizeRow}
      <dt>摆放</dt><dd data-field="mode"></dd>
      <dt>位置</dt><dd data-field="position"></dd>
      <dt>坐标</dt><dd data-field="coord" class="coord-val"></dd>
      <dt>朝向</dt><dd class="rotation-dd">${rotationRow}</dd>
      <dt>离地</dt><dd class="height-dd">${heightRow}</dd>
      <dt>离顶</dt><dd><span data-field="ceiling"></span> mm</dd>
      ${gapRow("西距","west")}${gapRow("东距","east")}${gapRow("北距","north")}${gapRow("南距","south")}
    </dl>
    ${panelPlanBlock(item)}
    <details class="hint-accordion" open>
      <summary class="hint-summary">
        <span class="hint-summary-title">💡 微调指南</span>
        <span class="hint-chevron">›</span>
      </summary>
      <div class="hint-content">${hint}</div>
    </details>
  </div>`;
}
function panelPlanBlock(item){
  if(!PANEL_URL_BASE)return "";
  if(item.manufacture===false)return `<p class="hint-inline">这件只占位置</p>`;
  if(!plansPanels(item))return "";
  return `<p class="panel-entry"><button type="button" class="btn-panel-plan" data-panel-plan>板件规划</button></p><p class="panel-note" data-panel-note hidden>先保存外形</p>`;
}
function sizeInputsDirty(item){
  const detail=document.getElementById("detail");
  if(!detail)return false;
  const saved={width:Math.round(item.width),depth:Math.round(item.depth),height:Math.round(item.height)};
  for(const key of ["width","depth","height"]){
    const input=detail.querySelector(`[data-size="${key}"]`);
    if(!input)continue;
    const typed=Number(input.value);
    if(!Number.isFinite(typed)||Math.round(typed)!==saved[key])return true;
  }
  return false;
}
function syncPanelPlan(item){
  const button=document.querySelector("#detail [data-panel-plan]");
  const note=document.querySelector("#detail [data-panel-note]");
  if(!button)return;
  const dirty=sizeInputsDirty(item);
  button.disabled=dirty;
  if(note)note.hidden=!dirty;
}
function openPanelPlan(item){
  if(!PANEL_URL_BASE||!plansPanels(item)||sizeInputsDirty(item)){
    setStatus("先保存外形","warn");
    return;
  }
  const params=new URLSearchParams();
  if(scene.room&&scene.room.id)params.set("room",scene.room.id);
  if(SHARE_FORM)params.set("mode","view");
  const query=params.toString();
  location.assign(`${PANEL_URL_BASE}/${encodeURIComponent(item.id)}/panels${query?`?${query}`:""}`);
}

function syncDetail(force=false){
  const detail=document.getElementById("detail");
  if(!detail)return;
  const item=displayScene().items.find(candidate=>candidate.id===state.selectedId);
  if(!item){
    if(uiStore.detailItemId!==null){
      uiStore.detailItemId=null;
      detail.innerHTML=`<div class="empty-state">
        <div class="empty-icon-wrap">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
            <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
            <line x1="12" y1="22.08" x2="12" y2="12"/>
          </svg>
        </div>
        <p class="empty-title">未选中任何家具</p>
        <p class="empty-subtitle">点击画布中的家具或上方列表即可微调尺寸、朝向与四向净距</p>
        <p class="empty" hidden>未选中任何家具</p>
      </div>`;
    }
    return;
  }
  if(uiStore.detailItemId!==item.id){
    uiStore.detailItemId=item.id;
    detail.innerHTML=detailMarkup(item);
  }
  applyDetailValues(detail,item,force);
}
function applyDetailValues(detail,item,force){
  if(!detail.querySelectorAll)return;
  const values=detailValues(displayScene(),item);
  const active=document.activeElement;
  const set=(selector,value)=>{
    for(const element of detail.querySelectorAll(selector)){
      if(element===active&&!force)continue;
      if(element.tagName==="INPUT")element.value=String(value);
      else element.textContent=String(value);
    }
  };
  set('[data-field="mode"]',values.mode);
  set('[data-field="position"]',values.position);
  set('[data-field="coord"]',values.coord);
  set('[data-field="rotation"]',values.rotation);
  set('[data-front]',values.front);
  set('[data-field="height"]',values.height);
  set('[data-size="width"]',values.width);
  set('[data-size="depth"]',values.depth);
  set('[data-size="height"]',values.boxHeight);
  set('[data-field="ceiling"]',values.ceiling);
  for(const key of ["west","east","north","south"]){
    set(`[data-gap="${key}"]`,values.gaps[key]);
    set(`[data-who="${key}"]`,values.who[key]);
  }
  syncPanelPlan(item);
}
function selectItem(id){
  state.selectedId=id;state.blocked=null;
  selectedIdSignal.set(id);
  const item=scene.items.find(candidate=>candidate.id===id);
  setStatus(item?selectHint(item):"点击一件家具开始");
  render();
}
function nudgeHeight(item,delta){
  if(drag||!canEditLayout())return;
  const before=item;item=structuredClone(item);
  const base=Math.round(item.placement.origin_z_mm||0);
  const solved=resolveInteger(base,base+delta,heightProbe(scene,item,item.footprint));
  if(solved.value===base){setStatus(`离地高度已经是 ${base} mm，${delta>0?"再高":"再低"}${placementStop(solved.blocker)}`,"warn");return}
  setItemHeight(item,solved.value);
  render();
  commitCandidate(item,before);
}
function setGap(item,direction,value){
  if(drag||!canEditLayout())return;
  const before=item;item=structuredClone(item);
  if(fillsWall(item)){
    setStatus("沿墙铺满的位置由空段算出，这一页不改净距","warn");
    return;
  }
  const gap=distancesOf(scene,item)[direction];
  const horizontal=direction==="west"||direction==="east";
  const sign=(direction==="west"||direction==="north")?1:-1;
  const delta=Math.round(sign*(value-gap.gap));
  if(!delta)return;
  if(item.placement.mode==="wall"){
    setStatus("靠墙位置由包络贴合算出，这一页不改沿墙距离","warn");
    return;
  }
  const blocker=applyLocalDrag(item,horizontal?delta:0,horizontal?0:delta);
  render();
  const reached=Math.round(distancesOf(scene,item)[direction].gap);
  if(blocker&&reached!==Math.round(value)){
    setStatus(`只挪到 ${reached} mm：${placementStop(blocker)}`,"warn");
  }
  commitCandidate(item,before);
}
function setRotationValue(item,degrees){
  if(drag||!canEditLayout())return;
  const before=item;item=structuredClone(item);
  if(fillsWall(item)){
    setStatus("沿墙铺满的朝向由这面墙决定，这一页不改","warn");
    return;
  }
  const result=solveRotation(scene,item,footprintCenter(item),degrees);
  render();
  if(!result.applied){
    if(result.blocker)setStatus(`转不过去：${placementStop(result.blocker)}`,"warn");
    return;
  }
  commitCandidate(item,before);
}
function setHeightValue(item,value){
  if(drag||!canEditLayout())return;
  const before=item;item=structuredClone(item);
  const base=Math.round(item.placement.origin_z_mm||0),target=Math.round(value);
  const solved=resolveInteger(base,target,heightProbe(scene,item,item.footprint));
  setItemHeight(item,solved.value);
  render();
  if(solved.value===base){
    if(solved.value!==target)setStatus(`改不了：${placementStop(solved.blocker)}`,"warn");
    return;
  }
  if(solved.value!==target)setStatus(`只到 ${solved.value} mm：${placementStop(solved.blocker)}`,"warn");
  commitCandidate(item,before);
}
function setSize(item,key,value){
  if(drag||!canEditLayout())return;
  if(fillsWall(item)){
    setStatus("沿墙铺满的宽度由这面墙剩下的空段算出，这一页不手改","warn");
    return;
  }
  const next=Math.round(value);
  if(!Number.isFinite(next)||next<=0){
    setStatus("宽、深、高都要大于 0","warn");
    return;
  }
  if(Math.round(item[key])===next)return;
  const sizes={};sizes[key]=next;
  uiStore.resizing+=1;
  persist(item,"resize",sizes).then(()=>{
    render();
    if(state.selectedId===item.id)syncDetail(true);
  }).finally(()=>{uiStore.resizing-=1});
}

/* ---------- 4. 画布指针与键盘交互 ---------- */
let drag=null;
function displayScene(){return drag?drag.preview(scene):scene}
async function commitCandidate(item,before,operation=poseOperation(item)){
  syncPlacementGeometry(scene.room,item);
  scene.items=scene.items.map(entry=>entry.id===item.id?item:entry);
  render();
  const saved=await persist(item,"move",null,operation);
  if(!saved)scene.items=scene.items.map(entry=>entry===item?before:entry);
  render();flushLayoutNotice();
  return saved;
}
function canEditLayout(){
  if(READ_ONLY)return false;
  if(uiStore.resizing){setStatus("正在保存外形，完成后再调整位置","warn");return false}
  if(PROJECT_EDIT_URL&&!ownsLease()){
    setStatus(leaseMessage(),"warn");
    return false;
  }
  return true;
}
function projectedWallNormal(wall,item){
  const normal=wallNormal(wall),project=projector(),center=footprintCenter(item);
  if(!normal)return null;
  const from=project([center[0],center[1],0]);
  const to=project([center[0]+normal[0]*300,center[1]+normal[1]*300,0]);
  const length=Math.hypot(to.x-from.x,to.y-from.y)||1;
  return {x:(to.x-from.x)/length,y:(to.y-from.y)/length};
}
function cancelDrag(){
  if(!drag)return;
  const pointerId=drag.pointerId;
  drag.cancel();drag=null;state.blocked=null;
  view.setEnabled(true);
  canvas.classList.remove("moving");
  if(canvas.hasPointerCapture(pointerId))canvas.releasePointerCapture(pointerId);
  render();flushLayoutNotice();
}
canvas.addEventListener("pointerdown",event=>{
  if(event.button===1||event.button===2)return;
  if(drag){cancelDrag();return}
  const picked=view.pick(event.clientX,event.clientY);
  const item=picked?scene.items.find(entry=>entry.id===picked.itemId):null;
  if(!item)return;
  if(READ_ONLY){selectItem(item.id);return}
  if(!canEditLayout())return;
  const kind=picked.kind==="height"?"height"
    :picked.kind==="rotate"||picked.kind==="ring"?"rotate"
    :picked.kind==="item"?"move":null;
  if(!kind)return;
  if(fillsWall(item)&&kind!=="height"){selectItem(item.id);return}
  const screen=screenPoint(event),basis=camera(),elevation=isElevation();
  if(kind==="move"&&!unprojectToGround(...screen)&&!elevation)return;
  state.selectedId=item.id;selectedIdSignal.set(item.id);state.blocked=null;
  const center=footprintCenter(item),height=kind==="move"&&!elevation
    ?item.z_start:(item.z_start+item.z_end)/2;
  const origin=projector()([center[0],center[1],height]);
  drag=createDragTransaction({scene,item,kind,screen,pointerId:event.pointerId,basis,
    scale:verticalPlaneScale(canvas,basis,[...center,height]),
    elevation,horizontal:horizontalAxis(basis),
    wallScreenNormal:projectedWallNormal(item.placement.host_wall,item),
    projectWallNormal:projectedWallNormal,rotationOrigin:origin,
    rotationSign:rotationSign(projector(),room.width_mm,center,height),
    threshold:px(4),detachThreshold:px(26)});
  view.setEnabled(false);canvas.classList.add("moving");
  canvas.setPointerCapture(event.pointerId);
  setStatus(selectHint(item));render();
},true);
canvas.addEventListener("pointermove",event=>{
  if(!drag||event.pointerId!==drag.pointerId)return;
  const result=drag.update(screenPoint(event),{fine:event.shiftKey});
  if(!result.moved)return;
  state.blocked=result.blocker?result.blocker.id:null;
  setStatus(result.blocker?contactStop(result.blocker):`调整 ${drag.item.label}…`,result.blocker?"warn":"");
  render();
});

/* ---------- 5. 落盘保存与房间文档同步 ---------- */
function refreshProjectDocument(){return layoutPersistence.refresh()}
function applyDocumentMetadata(payload){
  if(payload.lease!==undefined)applyLease(payload.lease||null);
  if(payload.working)applyWorking(payload);
  if(payload.decisions)applyDecisions(payload);
}
function showDocument(payload){
  if(!payload.rooms){
    scene.items=loadCanvasItems(payload.items);
    render();
    return;
  }
  rooms=payload.rooms;
  const currentId=scene.room&&scene.room.id;
  let index=rooms.findIndex(entry=>entry.id===currentId);
  if(index<0)index=0;
  showRoom(index,true);
}
async function persist(item,kind,sizes,operation){
  if(READ_ONLY)return false;
  if(PROJECT_EDIT_URL&&!ownsLease()){
    setStatus(leaseMessage(),"warn");
    return false;
  }
  let op=operation;
  if(!op){
    op=kind==="resize"?{op:"resize",item_id:item.id,...sizes}:poseOperation(item);
  }
  try{
    const next=await layoutPersistence.write(op);
    if(PROJECT_EDIT_URL){
      if(kind==="resize"){
        setStatus(`已保存 ${item.label}。这一版布局给板件用。改过的这间要再看一眼，看过才算确认。`);
        return true;
      }
      const working=next.working||{};
      const retired=(next.withdrawn_decisions||[]).length;
      const suffix=retired?` · 顺带作废了 ${retired} 条助手假设（你改的与它不一致）`:"";
      setStatus((working.open===false
        ? `已保存 ${item.label}（这一版已有下游产物，改动落成了新一版）`
        : `已保存 ${item.label}（同一版，草稿中${working.ops?` · 已调整 ${working.ops} 次`:""}）`)+suffix);
      return true;
    }
    setStatus(`已保存 ${item.label}`);
    return true;
  }catch(error){
    if(error instanceof LayoutWriteError)reportWriteFailure(error.status,error.detail,error.expectedVersion);
    else setStatus("保存失败："+error,"error");
    return false;
  }
}
function reportWriteFailure(status,detail,expectedVersion){
  const raw=detail&&detail.detail!==undefined?detail.detail:detail;
  const message=typeof raw==="string"?raw:JSON.stringify(raw||status);
  if(status===423){
    if(raw&&raw.holder)applyLease(raw);
    setStatus("这次改动没有保存；"+leaseMessage(),"warn");
    return;
  }
  if(status===409){
    const current=(raw&&raw.current_version)||"";
    const mineMoved=current&&expectedVersion&&current.split(":")[0]!==expectedVersion.split(":")[0];
    setStatus(mineMoved
      ? "布局已在别处更新（画面已为你刷新），刚才那次拖动没有保存"
      : "这一版刚被确认过，画面没变，请再拖一次","warn");
    return;
  }
  if(status===403){setStatus("这一页没有写权限（分享或只读）","error");return}
  setStatus(`改动被拒绝，已回到原位：${message}`,"error");
}

canvas.addEventListener("pointerup",event=>{
  if(state.panning){
    state.panning=false;canvas.classList.remove("panning");
    if(canvas.hasPointerCapture(event.pointerId))canvas.releasePointerCapture(event.pointerId);
    return;
  }
  if(!drag||event.pointerId!==drag.pointerId)return;
  const transaction=drag;
  if(!canEditLayout()){cancelDrag();return}
  const result=transaction.finish();
  drag=null;state.blocked=null;
  view.setEnabled(true);canvas.classList.remove("moving");
  if(canvas.hasPointerCapture(event.pointerId))canvas.releasePointerCapture(event.pointerId);
  if(result.changed)commitCandidate(result.item,result.before,result.operation);
  else{setStatus(selectHint(result.item));render();flushLayoutNotice()}
});

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
canvas.addEventListener("pointercancel",event=>{
  if(drag&&event.pointerId===drag.pointerId)cancelDrag();
  state.orbiting=false;state.panning=false;
  canvas.classList.remove("orbiting","panning");
  view.setEnabled(true);flushLayoutNotice();
});
canvas.addEventListener("lostpointercapture",event=>{
  if(drag&&event.pointerId===drag.pointerId)cancelDrag();
});
canvas.addEventListener("contextmenu",event=>event.preventDefault());
window.addEventListener("keydown",event=>{
  if(event.key==="Shift")view.setShiftPan(true);
  if(event.key==="Escape"){cancelDrag();selectItem(null);return}
  if(drag)return;
  const item=scene.items.find(candidate=>candidate.id===state.selectedId);
  if(!item)return;
  if(event.key==="PageUp"){event.preventDefault();nudgeHeight(item,50)}
  if(event.key==="PageDown"){event.preventDefault();nudgeHeight(item,-50)}
});
window.addEventListener("keyup",event=>{if(event.key==="Shift")view.setShiftPan(false)});

function handleViewportResize(){
  cancelDrag();
  fitCanvas();
  if(!uiStore.viewAnimation)state.distance=fitDistance(canvas,diagonal,view,state.active);
  render();
}
window.addEventListener("resize",handleViewportResize);
if(typeof ResizeObserver==="function"){
  const stageRo=new ResizeObserver(()=>handleViewportResize());
  stageRo.observe(canvas.parentElement||canvas);
}
const nextFrame=typeof requestAnimationFrame==="function"
  ?requestAnimationFrame
  :callback=>setTimeout(()=>callback(Date.now()),16);
const cancelFrame=typeof cancelAnimationFrame==="function"?cancelAnimationFrame:clearTimeout;
function animateView(goal,duration){
  cancelFrame(uiStore.viewAnimation);uiStore.viewAnimation=0;
  const reduce=typeof matchMedia==="function"&&matchMedia("(prefers-reduced-motion: reduce)").matches;
  const from={yaw:state.yaw,pitch:state.pitch,zoom:state.zoom,
    centre:[target[0],target[1],target[2]]};
  const to=goal.target||from.centre;
  const toZoom=goal.zoom===undefined?from.zoom:goal.zoom;
  const done=typeof goal.onDone==="function"?goal.onDone:null;
  if(reduce||duration<=0){
    state.yaw=goal.yaw;state.pitch=goal.pitch;
    state.zoom=toZoom;
    for(let i=0;i<3;i++)target[i]=to[i];
    pullStore.from=pullStore.end=isOrthoView(goal.active)?view.elevationPull():1;
    pullStore.now=pullStore.end;
    state.distance=baseFit(canvas,diagonal)*pullStore.now;
    render();
    if(done)done();
    return;
  }
  pullStore.from=pullStore.now;
  pullStore.end=isOrthoView(goal.active)?view.elevationPull():1;
  pullStore.now=pullStore.from;
  let deltaYaw=goal.yaw-from.yaw;
  while(deltaYaw>Math.PI)deltaYaw-=Math.PI*2;
  while(deltaYaw<-Math.PI)deltaYaw+=Math.PI*2;
  const started=Date.now();
  const ease=t=>t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
  const step=()=>{
    const t=Math.max(0,Math.min(1,(Date.now()-started)/duration)),k=ease(t);
    setPullProgress(k);
    state.yaw=from.yaw+deltaYaw*k;
    state.pitch=from.pitch+(goal.pitch-from.pitch)*k;
    state.zoom=from.zoom+(toZoom-from.zoom)*k;
    for(let i=0;i<3;i++)target[i]=from.centre[i]+(to[i]-from.centre[i])*k;
    render();
    if(t<1){uiStore.viewAnimation=nextFrame(step);return}
    uiStore.viewAnimation=0;
    if(done)done();
  };
  uiStore.viewAnimation=nextFrame(step);
}
function syncViewControls(){
  activeViewSignal.set(state.active);
  const select=document.getElementById("view-select");
  if(select)select.value=isOrthoView(state.active)?state.active:"free";
  const button=document.querySelector('[data-view="default_view"]');
  if(button)button.setAttribute("aria-pressed",String(state.active==="default_view"));
}
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
function updateActiveAfterRestore(pose){
  state.active=(nearAngle(pose.yaw-VIEWS.default_view.yaw)<1e-3&&
    Math.abs(pose.pitch-VIEWS.default_view.pitch)<1e-3)?"default_view":"free";
}
function restoreFreeView(){
  const remembered=state.freeView;
  if(!remembered){setView("default_view");return}
  updateActiveAfterRestore(remembered);
  syncViewControls();
  animateView({
    yaw:remembered.yaw,pitch:remembered.pitch,
    target:[...remembered.target],
    active:state.active,
  },500);
}
function setView(name){
  const preset=VIEWS[name];
  if(!preset)return;
  if(isOrthoView(name)&&!isOrthoView(state.active)){
    state.freeView={yaw:state.yaw,pitch:state.pitch,distance:state.distance,target:[...target]};
  }
  state.active=name;
  syncViewControls();
  const reset=name==="default_view";
  animateView({yaw:preset.yaw,pitch:preset.pitch,
    target:reset?HOME_TARGET:[...target],zoom:reset?1:state.zoom,
    active:name},500);
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
canvas.addEventListener("dblclick",()=>{
  if(isOrthoView(state.active)){restoreFreeView();return}
  const nearest=nearestOrthoView();
  state.freeView={yaw:state.yaw,pitch:state.pitch,distance:state.distance,target:[...target]};
  setView(nearest);
});
const dimsButton=document.getElementById("toggle-dims");
const DIMS_CYCLE=[["selected","标注·选中"],["all","标注·全部"],["off","标注·关"]];
function syncDimsButton(){
  dimsModeSignal.set(state.dims);
  if(!dimsButton)return;
  const found=DIMS_CYCLE.find(([value])=>value===state.dims);
  dimsButton.textContent=found?found[1]:"标注";
  dimsButton.setAttribute("aria-pressed",String(state.dims!=="off"));
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
    if(button.dataset.panelPlan!==undefined){openPanelPlan(item);return}
    if(button.dataset.height!==undefined)nudgeHeight(item,Number(button.dataset.height));
    else if(button.dataset.gapStep)setGap(item,button.dataset.gapStep,
      distancesOf(scene,item)[button.dataset.gapStep].gap+Number(button.dataset.delta));
    else if(button.dataset.rotationStep!==undefined)setRotationValue(item,
      Math.round(normalizeAngle(item.placement.rotation_z_deg||0))+Number(button.dataset.delta));
    else return;
    applyDetailValues(detailBox,displayScene().items.find(candidate=>candidate.id===item.id)||item,true);
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
    else if(input.dataset.size)setSize(item,input.dataset.size,value);
    else return;
    applyDetailValues(detailBox,displayScene().items.find(candidate=>candidate.id===item.id)||item,true);
  });
  detailBox.addEventListener("input",event=>{
    const input=event.target;
    if(!input||!input.dataset||!input.dataset.size)return;
    const item=scene.items.find(candidate=>candidate.id===state.selectedId);
    if(item)syncPanelPlan(item);
  });
}
bindRoom();
fitCanvas();
const defaults={yaw:DEFAULT_YAW,pitch:DEFAULT_PITCH,distance:fitDistance(canvas,diagonal,view,"default_view")};
const state={...defaults,orbiting:false,panning:false,active:"default_view",selectedId:null,
  freeView:null,zoom:1,blocked:null,dims:"selected"};

canvas.addEventListener("wheel",event=>{
  event.preventDefault();
  cancelFrame(uiStore.viewAnimation);uiStore.viewAnimation=0;
  const pose=view.readView();
  state.yaw=pose.yaw;state.pitch=pose.pitch;
  for(let i=0;i<3;i++)target[i]=pose.target[i];
  const pixels=event.deltaY*(event.deltaMode===1?16:event.deltaMode===2?canvas.clientHeight:1);
  state.zoom=Math.max(.15,Math.min(12,state.zoom*Math.exp(-pixels*.002)));
  render();
},{passive:false});
if(dimsButton){
  dimsButton.addEventListener("click",()=>{
    const index=DIMS_CYCLE.findIndex(([value])=>value===state.dims);
    state.dims=DIMS_CYCLE[(index+1)%DIMS_CYCLE.length][0];
    syncDimsButton();
    render();
  });
  syncDimsButton();
}
view.controls.addEventListener("start",()=>{
  cancelFrame(uiStore.viewAnimation);uiStore.viewAnimation=0;
  state.orbiting=true;
  state._pose=view.readView();
  canvas.classList.add("orbiting");
});
view.controls.addEventListener("change",()=>{if(!uiStore.placing)view.draw()});
view.controls.addEventListener("end",()=>{
  const pose=view.readView();
  const before=state._pose;
  state.yaw=pose.yaw;state.pitch=pose.pitch;state.distance=pose.distance;
  target[0]=pose.target[0];target[1]=pose.target[1];target[2]=pose.target[2];
  state.orbiting=false;state.panning=false;
  canvas.classList.remove("orbiting","panning");
  flushLayoutNotice();
  if(before&&(Math.abs(pose.yaw-before.yaw)>0.01||Math.abs(pose.pitch-before.pitch)>0.01)){
    state.active="free";syncViewControls();
  }
});
render();
syncViewControls();

/* ---------- 6. 多房间切换与深链 ---------- */
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
if(deepLinkView&&VIEWS[deepLinkView])setView(deepLinkView);
const deepLinkItem=deepLink.get("item");
if(deepLinkItem&&scene.items.some(candidate=>candidate.id===deepLinkItem))selectItem(deepLinkItem);
function syncRoomUrl(){
  if(!rooms||rooms.length<2)return;
  const entry=rooms[syncStore.roomIndex];
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
      const pending=entry.approved===false?" · 待审":"";
      const pressed=index===syncStore.roomIndex?' aria-pressed="true"':' aria-pressed="false"';
      const mark=entry.approved===false?' data-pending="true"':"";
      return `<button type="button" data-room-index="${index}"${pressed}${mark}>${escapeHtml(entry.name||entry.id)}${pending}</button>`;
    }).join("");
    return;
  }
  Array.from(band.querySelectorAll("button")).forEach(button=>{
    button.setAttribute("aria-pressed",Number(button.dataset.roomIndex)===syncStore.roomIndex?"true":"false");
  });
}
function showRoom(index,keepCamera){
  if(!rooms||!rooms[index])return;
  syncStore.roomIndex=index;
  roomIndexSignal.set(index);
  const next=rooms[index].scene;
  scene.room=next.room;
  scene.items=loadCanvasItems(next.items);
  scene.obstacles=next.obstacles||[];
  scene.openings=next.openings||[];
  bindRoom();
  if(!keepCamera){
    cancelFrame(uiStore.viewAnimation);uiStore.viewAnimation=0;
    pullStore.now=pullStore.from=pullStore.end=1;state.zoom=1;state.freeView=null;
    target[0]=HOME_TARGET[0];target[1]=HOME_TARGET[1];target[2]=HOME_TARGET[2];
    state.yaw=DEFAULT_YAW;state.pitch=DEFAULT_PITCH;
    state.distance=fitDistance(canvas,diagonal,view,"default_view");
    state.active="default_view";
    syncViewControls();
  }
  if(state.selectedId&&!scene.items.some(item=>item.id===state.selectedId)){
    state.selectedId=null;state.blocked=null;
    selectedIdSignal.set(null);
  }
  uiStore.panelSignature=null;
  uiStore.detailItemId=undefined;
  syncRoomBand();
  syncRoomUrl();
  render();
}

/* ---------- 7. 编辑租约、工作副本与决策台账 ---------- */
const LEASE_URL=LAYOUT_URL?LAYOUT_URL.replace(/\/layout$/,"/edit-lease"):"";
// 对一条待确认的说法表态（确认 / 划掉）：与布局编辑同一套门。
const DECISIONS_URL=LAYOUT_URL?LAYOUT_URL.replace(/\/layout$/,"/decisions"):"";
const LEASE_TOKEN_KEY="dsh-edit-lease:"+SCENE_ID;
const LEASE_ID_KEY=LEASE_TOKEN_KEY+":id";
const LEASE_LABEL_KEY=LEASE_TOKEN_KEY+":label";
if(PROJECT_EDIT_URL&&!sessionStorage.getItem(LEASE_LABEL_KEY)){
  sessionStorage.setItem(LEASE_LABEL_KEY,"窗口 "+Math.random().toString(16).slice(2,6));
}
const leaseStore={
  token:PROJECT_EDIT_URL?(sessionStorage.getItem(LEASE_TOKEN_KEY)||""):"",
  id:PROJECT_EDIT_URL?(sessionStorage.getItem(LEASE_ID_KEY)||""):"",
  label:PROJECT_EDIT_URL?sessionStorage.getItem(LEASE_LABEL_KEY):"",
  shown:null,
  painted:"",
  pendingDecisions:[],
  lastInteraction:Date.now(),
  idleYielded:false,
  idleTimer:0,
  phase:"loading",
  pending:null,
  closing:false,
};
const round1=value=>Math.round(value);
function localTime(iso){
  const date=new Date(iso);
  if(!iso||Number.isNaN(date.getTime()))return String(iso||"").replace("T"," ").slice(0,16);
  const pad=value=>String(value).padStart(2,"0");
  return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())} `
    +`${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
function describeOp(op,itemId){
  const entry=op||{};
  if(entry.op==="set_pose")return `X ${round1(entry.origin_x_mm)} · Y ${round1(entry.origin_y_mm)} · 离地 ${round1(entry.origin_z_mm)} mm · 朝向 ${round1(entry.rotation_z_deg)}°`;
  if(entry.op==="resize")return "改了外形尺寸";
  if(entry.op==="undo")return "撤销一步";
  return `${entry.op||"改动"} ${itemId||""}`.trim();
}
function describeActor(actor){
  const holder=actor&&actor.holder;
  if(holder==="page")return `页面 ${(actor.label||"").trim()}`.trim();
  if(holder==="agent")return "助手";
  return "不知道谁";
}
function renderWorkingPanel(){
  const panel=document.getElementById("working-panel");
  if(!panel)return;
  const recent=(window.__workingRecent)||[];
  if(!recent.length){panel.innerHTML="";return}
  panel.innerHTML="<ol>"+recent.slice().reverse().map(entry=>
    `<li>${escapeHtml(localTime(entry.at))} · `
    +`<span class="who">${escapeHtml(describeActor(entry.actor))}</span> · `
    +`${escapeHtml(describeOp(entry.op,entry.item_id))}</li>`).join("")+"</ol>";
}
function toggleWorkingPanel(){
  const badge=document.getElementById("working-badge");
  const panel=document.getElementById("working-panel");
  if(!badge||!panel||badge.hidden)return;
  const recent=(window.__workingRecent)||[];
  if(!recent.length)return;
  if(panel.hidden)renderWorkingPanel();
  panel.hidden=!panel.hidden;
}
function applyWorking(payload){
  const badge=document.getElementById("working-badge");
  if(!badge)return;
  const working=payload&&payload.working;
  workingSignal.set(working||null);
  if(!PROJECT_EDIT_URL||!working){badge.hidden=true;return}
  const revision=payload.revision_number?`第 ${payload.revision_number} 版 · `:"";
  badge.hidden=false;
  badge.classList.toggle("closed",working.open===false);
  badge.textContent=working.open===false
    ?`${revision}已有下游产物：改动会落成新一版`
    :`${revision}草稿中 · 同一版${working.ops?` · 已调整 ${working.ops} 次`:""}${READ_ONLY?"（只读）":""}`;
  const recent=(working&&working.recent)||[];
  window.__workingRecent=recent;
  badge.title=recent.slice().reverse().map(entry=>
    `${localTime(entry.at)} · ${describeActor(entry.actor)} · ${describeOp(entry.op,entry.item_id)}`
  ).join("\n");
  const panel=document.getElementById("working-panel");
  if(panel&&!panel.hidden)renderWorkingPanel();
}
function basisCanDecide(){
  return Boolean(PROJECT_EDIT_URL)&&!READ_ONLY&&!SHARE_FORM;
}
function renderBasisPanel(){
  const panel=document.getElementById("basis-panel");
  const badge=document.getElementById("basis-badge");
  if(!panel||!badge)return;
  const canDecide=basisCanDecide();
  panel.innerHTML=leaseStore.pendingDecisions.map(entry=>{
    const quote=entry.utterance?`<p class="quote">「${escapeHtml(entry.utterance)}」</p>`:"";
    const who=entry.speaker==="relay"?"（别人转达的客户话）":(entry.speaker==="customer"?"":"（助手记的）");
    const actions=canDecide
      ?`<div class="basis-actions">
          <button type="button" data-basis="confirm" data-target="${escapeHtml(entry.id)}">确认</button>
          <button type="button" data-basis="withdraw" data-target="${escapeHtml(entry.id)}">划掉</button>
        </div>`
      :"";
    return `<div class="basis-item">${quote}
      <p class="reading">${escapeHtml(entry.interpretation)}${who}</p>${actions}</div>`;
  }).join("")+(canDecide?"":`<p class="basis-note">这一页不能改：确认 / 划掉要在可编辑的页面上按。</p>`);
}
function applyDecisions(payload){
  const badge=document.getElementById("basis-badge");
  const panel=document.getElementById("basis-panel");
  if(!badge)return;
  leaseStore.pendingDecisions=(payload&&payload.decisions&&payload.decisions.pending)||[];
  pendingDecisionsSignal.set(leaseStore.pendingDecisions);
  if(!leaseStore.pendingDecisions.length){
    badge.hidden=true;badge.removeAttribute("title");badge.setAttribute("aria-expanded","false");
    if(panel)panel.hidden=true;
    return;
  }
  badge.hidden=false;
  badge.textContent=`助手假设 ${leaseStore.pendingDecisions.length} 条 · 点开确认`;
  badge.title=leaseStore.pendingDecisions.map(entry=>`${entry.utterance} → ${entry.interpretation}`).join("\n");
  renderBasisPanel();
}
function toggleBasisPanel(){
  const badge=document.getElementById("basis-badge");
  const panel=document.getElementById("basis-panel");
  if(!badge||!panel||badge.hidden)return;
  panel.hidden=!panel.hidden;
  badge.setAttribute("aria-expanded",String(!panel.hidden));
}
async function decideBasis(target,action){
  if(!DECISIONS_URL||!canEditLayout())return;
  try{
    await layoutPersistence.write({action,target},DECISIONS_URL);
    setStatus(action==="confirm"?"已记下：客户确认了这条":"已记下：客户划掉了这条");
  }catch(error){
    if(error instanceof LayoutWriteError)reportWriteFailure(error.status,error.detail,error.expectedVersion);
    else setStatus("没记上："+error,"error");
  }
}
function applyLease(lease){
  leaseStore.shown=lease||null;
  if(PROJECT_EDIT_URL&&!READ_ONLY&&!leaseStore.pending&&!leaseStore.closing&&leaseStore.phase!=="denied"){
    if(lease&&lease.id!==leaseStore.id){
      forgetLease();
      leaseStore.phase="blocked";
    }else if(!lease&&!leaseStore.idleYielded&&["ready","blocked"].includes(leaseStore.phase)){
      forgetLease();
      acquireLease();
    }
  }
  leaseSignal.set(leaseStore.shown);
  leaseStore.painted="";
  paintLease();
}
function ownsLease(){
  return leaseStore.phase==="ready"&&Boolean(leaseStore.token&&leaseStore.shown
    &&leaseStore.shown.holder==="page"&&leaseStore.shown.id===leaseStore.id);
}
function forgetLease(){
  leaseStore.token="";leaseStore.id="";
  clearTimeout(leaseStore.idleTimer);
  sessionStorage.removeItem(LEASE_TOKEN_KEY);
  sessionStorage.removeItem(LEASE_ID_KEY);
}
function leaseMessage(){
  if(leaseStore.phase==="loading")return "正在申请编辑权，请稍等";
  if(leaseStore.phase==="error")return "编辑权申请失败，请点「重试编辑权」";
  if(leaseStore.phase==="denied")return "当前页面没有编辑权限，请从本机项目列表打开";
  if(leaseStore.shown&&leaseStore.shown.holder==="agent")return "助手正在处理，可点「收回编辑权」";
  if(leaseStore.shown)return "另一窗口正在编辑，可点「收回编辑权」";
  return "编辑权已空闲，点「取得编辑权」后再操作";
}
function paintLease(){
  const badge=document.getElementById("lease-badge");
  const button=document.getElementById("take-lease");
  if(!badge||!button)return;
  const lease=leaseStore.shown;
  const editable=Boolean(PROJECT_EDIT_URL&&!READ_ONLY&&!SHARE_FORM);
  const mine=ownsLease();
  if(!lease&&!editable){
    if(leaseStore.painted==="none")return;
    leaseStore.painted="none";
    badge.hidden=true;badge.classList.remove("mine");button.hidden=true;return;
  }
  const who=mine?"编辑权在你手上":(!editable&&lease
    ?(lease.holder==="agent"?"助手正在处理":"另一窗口正在编辑"):leaseMessage());
  const signature=`${who}|${mine}|${leaseStore.phase}`;
  if(signature===leaseStore.painted)return;
  leaseStore.painted=signature;
  badge.textContent=who;
  badge.hidden=false;
  badge.classList.toggle("mine",mine);
  button.hidden=!editable||mine||["loading","denied"].includes(leaseStore.phase);
  button.textContent=leaseStore.phase==="error"?"重试编辑权":(lease?"收回编辑权":"取得编辑权");
}
async function leasePost(path,body){
  const headers={"Content-Type":"application/json"};
  if(leaseStore.token)headers["X-Edit-Lease"]=leaseStore.token;
  return fetch(path,{method:"POST",cache:"no-store",headers,body:JSON.stringify(body),signal:AbortSignal.timeout(10000)});
}
const takeLeaseButton=document.getElementById("take-lease");
const workingBadge=document.getElementById("working-badge");
if(workingBadge)workingBadge.addEventListener("click",toggleWorkingPanel);
const basisBadge=document.getElementById("basis-badge");
if(basisBadge){
  basisBadge.addEventListener("click",toggleBasisPanel);
  basisBadge.addEventListener("keydown",event=>{
    if(event.key==="Enter"||event.key===" "){event.preventDefault();toggleBasisPanel()}
  });
}
const basisPanel=document.getElementById("basis-panel");
if(basisPanel){
  basisPanel.addEventListener("click",event=>{
    const button=event.target&&event.target.closest?event.target.closest("button[data-basis]"):null;
    if(!button)return;
    button.disabled=true;
    decideBasis(button.dataset.target,button.dataset.basis).finally(()=>{button.disabled=false});
  });
}
if(takeLeaseButton){
  takeLeaseButton.addEventListener("click",async()=>{
    if(leaseStore.pending)return;
    takeLeaseButton.disabled=true;
    try{
      const takeover=Boolean(leaseStore.shown&&!ownsLease());
      const lease=await acquireLease(takeover);
      if(lease)setStatus(takeover?"已收回编辑权，可以继续编辑":"已取得编辑权，可以继续编辑");
    }finally{
      takeLeaseButton.disabled=false;
    }
  });
}
window.addEventListener("pagehide",()=>{
  leaseStore.closing=true;
  clearTimeout(leaseStore.idleTimer);
  if(syncStore.events)syncStore.events.close();
  if(!leaseStore.token||!LEASE_URL)return;
  try{
    fetch(LEASE_URL,{
      method:"DELETE",cache:"no-store",keepalive:true,
      headers:{"X-Edit-Lease":leaseStore.token},
    });
  }catch(error){}
});
window.addEventListener("pageshow",event=>{
  if(!event.persisted)return;
  leaseStore.closing=false;
  syncStore.events=null;
  if(PROJECT_EDIT_URL&&!READ_ONLY)acquireLease();
  else watchLayout();
});
function applyLayoutNotice(notice){
  layoutPersistence.notice(notice);
}
function flushLayoutNotice(){
  layoutPersistence.flush();
}
function watchLayout(){
  if(!LAYOUT_URL)return;
  const query=leaseStore.id?("?lease_id="+encodeURIComponent(leaseStore.id)):"";
  if(syncStore.events&&query===syncStore.leaseQuery)return;
  if(syncStore.events)syncStore.events.close();
  syncStore.leaseQuery=query;
  const source=new EventSource(LAYOUT_URL+"/events"+query);
  source.onmessage=event=>{
    if(source!==syncStore.events)return;
    try{applyLayoutNotice(JSON.parse(event.data))}catch(error){}
  };
  syncStore.events=source;
}
const roomBand=document.getElementById("room-band");
if(roomBand){
  roomBand.addEventListener("click",event=>{
    const button=event.target&&event.target.closest?event.target.closest("button[data-room-index]"):null;
    if(!button)return;
    const index=Number(button.dataset.roomIndex);
    if(!Number.isInteger(index)||!rooms||!rooms[index]||index===syncStore.roomIndex)return;
    if(layoutPersistence.busy){setStatus("布局正在操作或保存，完成后再切换房间","warn");return}
    showRoom(index,false);
  });
}
syncRoomBand();
syncRoomUrl();
// 可编辑页先申请，再用取得的锁号订阅，避免续租覆盖连接刚钉住的到期时间。
if(LAYOUT_URL&&(!PROJECT_EDIT_URL||READ_ONLY))watchLayout();

const IDLE_YIELD_SECONDS=300;
function armIdle(){
  if(!PROJECT_EDIT_URL||READ_ONLY||SHARE_FORM||!ownsLease())return;
  clearTimeout(leaseStore.idleTimer);
  leaseStore.idleTimer=setTimeout(yieldIdleLease,IDLE_YIELD_SECONDS*1000);
}
function markInteraction(){
  leaseStore.lastInteraction=Date.now();
  if(leaseStore.token)armIdle();
  if(leaseStore.idleYielded&&PROJECT_EDIT_URL&&!READ_ONLY&&!leaseStore.token)acquireLease();
}
["pointerdown","keydown","wheel","pointermove"].forEach(name=>{
  window.addEventListener(name,markInteraction,{passive:true});
});
function acquireLease(takeover=false){
  if(!PROJECT_EDIT_URL||READ_ONLY||SHARE_FORM||leaseStore.closing)return Promise.resolve(null);
  if(leaseStore.pending)return leaseStore.pending;
  leaseStore.phase="loading";
  paintLease();
  leaseStore.pending=requestLease(takeover).finally(()=>{
    leaseStore.pending=null;
    if(!leaseStore.closing&&!syncStore.events)watchLayout();
    paintLease();
  });
  return leaseStore.pending;
}
async function requestLease(takeover){
  try{
    const response=await leasePost(LEASE_URL+(takeover?"/takeover":""),{
      holder:"page",label:leaseStore.label,token:leaseStore.token||undefined,
    });
    if(response.status===423){
      const detail=await response.json().catch(()=>({}));
      forgetLease();
      leaseStore.phase="blocked";
      leaseStore.idleYielded=false;
      applyLease(detail.detail&&detail.detail.holder?detail.detail:null);
      setStatus(leaseMessage(),"warn");
      return null;
    }
    if(!response.ok){
      forgetLease();
      leaseStore.phase=response.status===403?"denied":"error";
      setStatus(leaseMessage()+`（HTTP ${response.status}）`,"error");
      return null;
    }
    const lease=await response.json();
    if(!lease.token||!lease.id||lease.holder!=="page")throw new Error("invalid edit lease response");
    leaseStore.token=lease.token;leaseStore.id=lease.id;leaseStore.idleYielded=false;
    leaseStore.phase="ready";
    sessionStorage.setItem(LEASE_TOKEN_KEY,leaseStore.token);
    sessionStorage.setItem(LEASE_ID_KEY,leaseStore.id);
    applyLease(lease);
    watchLayout();
    armIdle();
    return lease;
  }catch(error){
    forgetLease();
    leaseStore.phase="error";
    setStatus("无法取得编辑权，请检查预览服务或网络后点「重试编辑权」","error");
    return null;
  }
}
function yieldIdleLease(){
  if(!PROJECT_EDIT_URL||READ_ONLY||SHARE_FORM||!leaseStore.token)return;
  if(Date.now()-leaseStore.lastInteraction<IDLE_YIELD_SECONDS*1000){
    armIdle();
    return;
  }
  fetch(LEASE_URL,{method:"DELETE",cache:"no-store",headers:{"X-Edit-Lease":leaseStore.token}})
    .catch(()=>{});
  forgetLease();leaseStore.idleYielded=true;leaseStore.phase="idle";
  applyLease(null);
  setStatus("闲置太久，已让出编辑权 · 点一下就能拿回来");
}
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
    if(syncStore.events){syncStore.events.close();syncStore.events=null}
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

/* ---------- 8. Angular 根组件引导 (Standalone Component + Signals) ---------- */
const LayoutWorkspaceAppComponent=Component({
  selector:"main.app",
  standalone:true,
})(class LayoutWorkspaceAppComponent{
  constructor(){
    this.selectedId=selectedIdSignal;
    this.activeView=activeViewSignal;
    this.dimsMode=dimsModeSignal;
    this.statusToast=statusToastSignal;
    this.roomIndex=roomIndexSignal;
    this.lease=leaseSignal;
    this.working=workingSignal;
    this.pendingDecisions=pendingDecisionsSignal;
  }

});
bootstrapApplication(LayoutWorkspaceAppComponent);



// Trusted optional page code receives only these two layout integration hooks.
const pageHost=Object.freeze({
  onProjectUpdated:()=>refreshProjectDocument(),
  onStatusToast:(message,kind)=>setStatus(message,kind),
});
__PAGE_EXTENSION_SCRIPT__
