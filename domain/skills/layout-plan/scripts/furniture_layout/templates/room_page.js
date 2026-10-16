import { mountLayout } from "/layout-view/layout_scene.js";
import { normalizeItems } from "/layout-view/layout_payload.js";
import { groundDragDelta, wallSnap } from "/layout-view/layout_drag.js";
import {
  contactStop, detailValues, distancesOf, footprintCenter, heightProbe,
  localFootprint, normalizeAngle, placementStop, resolveInteger,
  setItemHeight, snapAngle, solveElevationDrag, solvePlanarDrag,
  solveRotation, wallLabel, wallNormal,
} from "/layout-view/layout_solver.js";
import {
  ELEVATION_MAX_PITCH, baseFit, fitDistance, horizontalAxis,
  isOrthoView, nearAngle, rotationSign, verticalPlaneScale,
} from "/layout-view/layout_camera.js";

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
let layoutVersion=__VERSION_JSON__;

// 收敛散落的顶层可变状态为四个职责清晰的 Store
const syncStore={
  dirty:false,
  epoch:0,
  fetchEpoch:-1,
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
};

const scene=JSON.parse(document.getElementById("scene-data").textContent);
scene.items=normalizeItems(scene.items);
scene.obstacles=scene.obstacles||[];
scene.openings=scene.openings||[];
const canvas=document.getElementById("scene"),status=document.getElementById("status");
const view=mountLayout(canvas);
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
  view.sync(scene,{selectedId:state.selectedId,dims:state.dims,readOnly:READ_ONLY,blockedId:state.blocked});
  syncPanel();
}

function setStatus(text,kind){
  status.textContent=text;
  status.classList.toggle("warn",kind==="warn");
  status.classList.toggle("error",kind==="error");
}
function isElevation(){return state.pitch<ELEVATION_MAX_PITCH}

/* ---------- 2. 拖拽、旋转与摆放求解桥接 ---------- */
function applyLocalDrag(item,dx,dy,startOrigin){
  const origin=startOrigin||[item.placement.origin_x_mm||0,item.placement.origin_y_mm||0];
  const blocker=solvePlanarDrag(scene,item,origin,dx,dy);
  if(item.placement.mode!=="wall"){
    const snap=wallSnap({footprint:item.footprint,rotation:item.placement.rotation_z_deg||0,
      room:{width_mm:room.width_mm,depth_mm:room.depth_mm}});
    if(snap){
      item.placement.mode="wall";item.placement.host_wall=snap.host_wall;
    }
  }
  return blocker;
}

function detachToFree(activeDrag){
  const placement=activeDrag.item.placement;
  placement.mode="free";placement.host_wall=null;
  placement.origin_x_mm=Math.round(activeDrag.startOrigin[0]);
  placement.origin_y_mm=Math.round(activeDrag.startOrigin[1]);
  placement.rotation_z_deg=placement.rotation_z_deg||0;
  activeDrag.item.footprint=localFootprint(activeDrag.item,placement.origin_x_mm,placement.origin_y_mm,placement.rotation_z_deg);
  setStatus(`${activeDrag.item.label} 已离开墙面，改为自由摆放`,"warn");
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
  const signature=scene.items.map(item=>`${item.id}:${item.label}:${item.placement.mode}`).join("|")+"#"+state.selectedId;
  const list=document.getElementById("item-list");
  if(list&&signature!==uiStore.panelSignature){
    uiStore.panelSignature=signature;
    list.innerHTML=scene.items.map(item=>`<li><button type="button" class="item-row${item.id===state.selectedId?" active":""}" data-item="${escapeHtml(item.id)}">
      <span class="dot"></span><span class="name">${escapeHtml(item.label)}</span>
      <span class="mode">${item.placement.mode==="wall"?"靠墙":"自由"}</span></button></li>`).join("");
  }
  syncDetail();
}

function detailMarkup(item){
  const round=n=>Math.round(n);
  const fills=fillsWall(item);
  const gapRow=(label,key)=>(READ_ONLY||fills)
    ? `<dt>${label}</dt><dd><span data-gap="${key}"></span> mm<span class="who" data-who="${key}"></span></dd>`
    : `<dt>${label}</dt><dd><button type="button" class="step" data-gap-step="${key}" data-delta="-10" aria-label="${label}减 10">−</button><input class="num" type="number" step="1" data-gap="${key}" aria-label="${label}"><button type="button" class="step" data-gap-step="${key}" data-delta="10" aria-label="${label}加 10">＋</button><span class="who" data-who="${key}"></span></dd>`;
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
  return `<dl class="detail">
    <dt>名称</dt><dd>${escapeHtml(item.label)}</dd>
    ${sizeRow}
    <dt>摆放</dt><dd data-field="mode"></dd>
    <dt>位置</dt><dd data-field="position"></dd>
    <dt>坐标</dt><dd data-field="coord"></dd>
    <dt>朝向</dt><dd>${rotationRow}</dd>
    <dt>离地</dt><dd>${heightRow}</dd>
    <dt>离顶</dt><dd><span data-field="ceiling"></span> mm</dd>
    ${gapRow("西距","west")}${gapRow("东距","east")}${gapRow("北距","north")}${gapRow("南距","south")}
  </dl>
  ${panelPlanBlock(item)}
  ${hint}`;
}
function plansPanels(item){
  return !!item && item.manufacture!==false
    && (item.furniture_category==="floor_cabinet" || item.furniture_category==="wall_cabinet");
}
function panelPlanBlock(item){
  if(!PANEL_URL_BASE)return "";
  if(item.manufacture===false)return `<p class="hint-inline">这件只占位置</p>`;
  if(!plansPanels(item))return "";
  return `<p class="panel-entry"><button type="button" data-panel-plan>板件规划</button></p><p class="hint-inline" data-panel-note hidden>先保存外形</p>`;
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
  const item=scene.items.find(candidate=>candidate.id===state.selectedId);
  if(!item){
    if(uiStore.detailItemId!==null){uiStore.detailItemId=null;detail.innerHTML='<p class="empty">未选中任何家具</p>'}
    return;
  }
  if(uiStore.detailItemId!==item.id){
    uiStore.detailItemId=item.id;
    detail.innerHTML=detailMarkup(item);
  }
  applyDetailValues(detail,item,force);
}
function applyDetailValues(detail,item,force){
  if(!detail.querySelector)return;
  const values=detailValues(scene,item);
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
  const item=scene.items.find(candidate=>candidate.id===id);
  setStatus(item?selectHint(item):"点击一件家具开始");
  render();
}
function nudgeHeight(item,delta){
  if(READ_ONLY)return;
  const base=Math.round(item.placement.origin_z_mm||0);
  const solved=resolveInteger(base,base+delta,heightProbe(scene,item,item.footprint));
  if(solved.value===base){setStatus(`离地高度已经是 ${base} mm，${delta>0?"再高":"再低"}${placementStop(solved.blocker)}`,"warn");return}
  setItemHeight(item,solved.value);
  render();
  persist(item,"move").then(()=>{render()});
}
function setGap(item,direction,value){
  if(READ_ONLY)return;
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
  persist(item,"move").then(()=>{render()});
}
function setRotationValue(item,degrees){
  if(READ_ONLY)return;
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
  persist(item,"rotate").then(()=>{render()});
}
function setHeightValue(item,value){
  if(READ_ONLY)return;
  const base=Math.round(item.placement.origin_z_mm||0),target=Math.round(value);
  const solved=resolveInteger(base,target,heightProbe(scene,item,item.footprint));
  setItemHeight(item,solved.value);
  render();
  if(solved.value===base){
    if(solved.value!==target)setStatus(`改不了：${placementStop(solved.blocker)}`,"warn");
    return;
  }
  if(solved.value!==target)setStatus(`只到 ${solved.value} mm：${placementStop(solved.blocker)}`,"warn");
  persist(item,"move").then(()=>{render()});
}
function setSize(item,key,value){
  if(READ_ONLY)return;
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
  persist(item,"resize",sizes).then(()=>{
    render();
    if(state.selectedId===item.id)syncDetail(true);
  });
}

/* ---------- 4. 画布指针与键盘交互 ---------- */
let drag=null;
canvas.addEventListener("pointerdown",event=>{
  const [sx,sy]=screenPoint(event);
  if(event.button===1||event.button===2)return;
  const picked=view.pick(event.clientX,event.clientY);
  const pickedItem=picked?scene.items.find(item=>item.id===picked.itemId):null;
  if(READ_ONLY){
    if(pickedItem){selectItem(pickedItem.id);return}
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
    if(fillsWall(pickedItem)){selectItem(pickedItem.id);return}
    view.setEnabled(false);
    const center=footprintCenter(pickedItem),height=(pickedItem.z_start+pickedItem.z_end)/2;
    const origin=projector()([center[0],center[1],height]);
    const startAngle=Math.atan2(sy-origin.y,sx-origin.x)*180/Math.PI;
    drag={kind:"rotate",item:pickedItem,center,height,origin,startAngle,lastAngle:startAngle,
      accumulated:0,moved:false,startScreen:[sx,sy],
      startRotation:pickedItem.placement.rotation_z_deg||0,startMode:pickedItem.placement.mode,
      sign:rotationSign(projector(),room.width_mm,center,height)};
    canvas.classList.add("moving");
    setStatus(`旋转 ${pickedItem.label}…`);
    canvas.setPointerCapture(event.pointerId);
    return;
  }
  const ground=unprojectToGround(sx,sy);
  if(pickedItem&&picked.kind==="item"&&(ground||isElevation())){
    if(fillsWall(pickedItem)){selectItem(pickedItem.id);return}
    view.setEnabled(false);
    const placement=pickedItem.placement;
    state.selectedId=pickedItem.id;state.blocked=null;
    drag={kind:"move",item:pickedItem,startScreen:[sx,sy],moved:false,
      startOrigin:[placement.origin_x_mm||0,placement.origin_y_mm||0],
      startZ:placement.origin_z_mm||0,startMode:placement.mode,startWall:placement.host_wall,
      horizontal:horizontalAxis(camera()),elevation:isElevation(),
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
},true);

canvas.addEventListener("pointermove",event=>{
  if(drag){
    const [sx,sy]=screenPoint(event);
    if(!drag.moved){
      if(Math.hypot(sx-drag.startScreen[0],sy-drag.startScreen[1])<px(4))return;
      drag.moved=true;
    }
    const cam=camera();
    if(drag.kind==="height"){
      const scale=verticalPlaneScale(canvas,cam,[...footprintCenter(drag.item),(drag.item.z_start+drag.item.z_end)/2]);
      const wanted=Math.round(-(sy-drag.startScreen[1])*scale/(cam.up[2]||1));
      const base=Math.round(drag.startZ);
      const solved=resolveInteger(base,base+wanted,heightProbe(scene,drag.item,drag.item.footprint));
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
      const result=solveRotation(scene,drag.item,drag.center,next);
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
      const scale=verticalPlaneScale(canvas,cam,[...footprintCenter(drag.item),(drag.item.z_start+drag.item.z_end)/2]);
      const blocker=solveElevationDrag(scene,drag.item,drag.startOrigin,drag.startZ,drag.horizontal,(sx-drag.startScreen[0])*scale,-(sy-drag.startScreen[1])*scale);
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
    const scale=verticalPlaneScale(canvas,cam,[...footprintCenter(drag.item),drag.item.z_start||0]);
    const delta=groundDragDelta({dx:sx-drag.startScreen[0],dy:sy-drag.startScreen[1],scale,
      right:cam.right,forward:cam.forward});
    const modeBefore=drag.item.placement.mode;
    const blocker=applyLocalDrag(drag.item,delta[0],delta[1],drag.startOrigin);
    if(modeBefore==="free"&&drag.item.placement.mode==="wall")drag.startScreen=[sx,sy];
    state.blocked=blocker?blocker.id:null;
    if(blocker)setStatus(contactStop(blocker),"warn");
    else setStatus(`拖动 ${drag.item.label}… 位移 ${Math.round(Math.hypot(delta[0],delta[1]))} mm`);
    render();
    return;
  }
});

/* ---------- 5. 落盘保存与房间文档同步 ---------- */
async function reload(){
  if(PROJECT_EDIT_URL){await refreshProjectDocument();return}
  try{
    const response=await fetch(`/api/room-scene/${encodeURIComponent(SCENE_ID)}`);
    if(!response.ok)return;
    const next=await response.json();
    scene.items=normalizeItems(next.items||[]);
  }catch(error){}
}
function applyDocument(payload){
  if(payload.version!==undefined)layoutVersion=String(payload.version);
  if(payload.lease!==undefined)applyLease(payload.lease||null);
  if(payload.working)applyWorking(payload);
  if(payload.decisions)applyDecisions(payload);
  if(!payload.rooms)return;
  rooms=payload.rooms;
  const currentId=scene.room&&scene.room.id;
  let index=rooms.findIndex(entry=>entry.id===currentId);
  if(index<0)index=0;
  showRoom(index,true);
}
async function refreshProjectDocument(){
  const epoch=syncStore.epoch;
  try{
    const response=await fetch(LAYOUT_URL,{cache:"no-store",headers:{Accept:"application/json"}});
    if(!response.ok)return false;
    const payload=await response.json();
    if(epoch!==syncStore.epoch)return false;
    applyDocument(payload);
    syncStore.dirty=false;
    return true;
  }catch(error){return false}
}
async function persist(item,kind,sizes){
  if(READ_ONLY)return false;
  if(PROJECT_EDIT_URL&&!leaseStore.token){
    setStatus("这一页现在只能看：编辑权不在你手上（点「收回编辑权」或等助手做完）","warn");
    return false;
  }
  let op;
  if(fillsWall(item)){
    if(kind!=="move"&&kind!=="height"){
      setStatus("沿墙铺满不改沿墙位置和朝向","warn");
      return false;
    }
    op={op:"move",item_id:item.id,origin_z_mm:Math.round(item.placement.origin_z_mm||0)};
  }else if(kind==="resize"){
    op={op:"resize",item_id:item.id};
    if(sizes)Object.assign(op,sizes);
  }else{
    const placement=item.placement;
    op={op:kind==="rotate"?"rotate":"move",item_id:item.id};
    if(kind==="rotate")op.rotation_z_deg=Math.round(normalizeAngle(placement.rotation_z_deg)*10)/10;
    if(placement.mode==="wall"){
      op.mode="wall";op.host_wall=placement.host_wall;
    }else{
      op.mode="free";op.origin_x_mm=Math.round(placement.origin_x_mm);op.origin_y_mm=Math.round(placement.origin_y_mm);
    }
    if(kind!=="rotate")op.origin_z_mm=Math.round(placement.origin_z_mm||0);
  }
  const url=PROJECT_EDIT_URL||`/api/room-scene/${encodeURIComponent(SCENE_ID)}/edit`;
  const headers={"Content-Type":"application/json"};
  if(leaseStore.token)headers["X-Edit-Lease"]=leaseStore.token;
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
    scene.items=normalizeItems(next.items||[]);
    setStatus(`已保存 ${item.label}`);
    return true;
  }catch(error){
    setStatus("保存失败："+error,"error");
    await reload();
    return false;
  }
}
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
    const unchanged=kind==="rotate"
      ?(item.placement.rotation_z_deg===drag.startRotation&&item.placement.mode===drag.startMode)
      :kind==="height"?Math.round(item.placement.origin_z_mm||0)===Math.round(drag.startZ)
      :kind==="move"&&drag.startMode==="wall"&&item.placement.mode==="wall"
        &&item.placement.host_wall===drag.startWall
        &&Math.round(item.placement.origin_z_mm||0)===Math.round(drag.startZ);
    drag=null;state.blocked=null;canvas.classList.remove("moving");
    view.setEnabled(true);
    canvas.releasePointerCapture(event.pointerId);
    if(moved&&!unchanged){persist(item,kind).then(()=>{render();flushLayoutNotice()})}
    else{setStatus(selectHint(item));render();flushLayoutNotice()}
    return;
  }
  view.setEnabled(true);
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
canvas.addEventListener("pointercancel",()=>{
  drag=null;state.blocked=null;state.orbiting=false;state.panning=false;
  canvas.classList.remove("moving","orbiting","panning");
  flushLayoutNotice();
});
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
  if(!uiStore.viewAnimation)state.distance=fitDistance(canvas,diagonal,view,state.active);
  render();
});
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
    else if(input.dataset.size)setSize(item,input.dataset.size,value);
    else return;
    applyDetailValues(detailBox,item,true);
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
  const next=rooms[index].scene;
  scene.room=next.room;
  scene.items=normalizeItems(next.items||[]);
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
  }
  uiStore.panelSignature=null;
  uiStore.detailItemId=undefined;
  syncRoomBand();
  syncRoomUrl();
  render();
}
function layoutVersionOf(payload){return String(payload.version||"")}

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
  if(entry.op==="move"&&entry.host_wall)return `靠${wallLabel(entry.host_wall)}墙`;
  if(entry.op==="move"&&entry.origin_z_mm!==undefined)return `离地 ${round1(entry.origin_z_mm)} mm`;
  if(entry.op==="move"&&entry.origin_x_mm!==undefined)
    return `挪到 X ${round1(entry.origin_x_mm)} · Y ${round1(entry.origin_y_mm)} mm`;
  if(entry.op==="resize")return "改了外形尺寸";
  if(entry.op==="rotate")return `转到 ${round1(entry.rotation_z_deg||0)}°`;
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
  if(!DECISIONS_URL)return;
  const answer=await leasePost(DECISIONS_URL,{expected_version:layoutVersion,action,target});
  if(answer.status===423){
    const detail=await answer.json().catch(()=>({}));
    applyLease((detail&&detail.detail)||null);
    setStatus("编辑权在别人手里 · 先点「收回编辑权」再确认","warn");
    return;
  }
  if(answer.status===409){
    setStatus("页面上的内容已经过期 · 刷新后再确认","warn");
    return;
  }
  if(!answer.ok){
    const detail=await answer.json().catch(()=>({}));
    setStatus("没记上："+((detail&&detail.detail)||answer.status),"error");
    return;
  }
  const document=await answer.json();
  if(document.version!==undefined)layoutVersion=String(document.version);
  applyDecisions(document);
  setStatus(action==="confirm"?"已记下：客户确认了这条":"已记下：客户划掉了这条");
}
function applyLease(lease){
  leaseStore.shown=lease||null;
  leaseStore.painted="";
  paintLease();
}
function paintLease(){
  const badge=document.getElementById("lease-badge");
  const button=document.getElementById("take-lease");
  if(!badge||!button)return;
  const lease=leaseStore.shown;
  const mine=Boolean(lease&&leaseStore.token&&lease.id===leaseStore.id);
  if(!lease){
    if(leaseStore.painted==="none")return;
    leaseStore.painted="none";
    badge.hidden=true;badge.classList.remove("mine");button.hidden=true;return;
  }
  const who=lease.holder==="agent"?"助手正在处理":(mine?"编辑权在你手上":"另一窗口正在编辑");
  const signature=`${who}|${mine}|${lease.holder}`;
  if(signature===leaseStore.painted)return;
  leaseStore.painted=signature;
  badge.textContent=who;
  badge.hidden=false;
  badge.classList.toggle("mine",mine);
  button.hidden=SHARE_FORM||lease.holder!=="agent";
}
async function leasePost(path,body){
  const headers={"Content-Type":"application/json"};
  if(leaseStore.token)headers["X-Edit-Lease"]=leaseStore.token;
  return fetch(path,{method:"POST",cache:"no-store",headers,body:JSON.stringify(body)});
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
    takeLeaseButton.disabled=true;
    try{
      const response=await fetch(LEASE_URL+"/takeover",{
        method:"POST",cache:"no-store",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({holder:"page",label:leaseStore.label}),
      });
      if(!response.ok)throw new Error(response.status);
      const lease=await response.json();
      leaseStore.token=lease.token;leaseStore.id=lease.id;
      sessionStorage.setItem(LEASE_TOKEN_KEY,leaseStore.token);
      sessionStorage.setItem(LEASE_ID_KEY,leaseStore.id);
      applyLease(lease);
      watchLayout();
      setStatus("已收回编辑权：助手下次写入会被挡下");
    }catch(error){
      setStatus("收回失败："+error,"error");
    }finally{
      takeLeaseButton.disabled=false;
    }
  });
}
window.addEventListener("pagehide",()=>{
  if(syncStore.events)syncStore.events.close();
  if(!leaseStore.token||!LEASE_URL)return;
  try{
    fetch(LEASE_URL,{
      method:"DELETE",cache:"no-store",keepalive:true,
      headers:{"X-Edit-Lease":leaseStore.token},
    });
  }catch(error){}
});
function sceneBusy(){
  return Boolean(drag||state.orbiting||state.panning);
}
function applyLayoutNotice(notice){
  if(!notice||typeof notice!=="object")return;
  if(Object.prototype.hasOwnProperty.call(notice,"lease"))applyLease(notice.lease||null);
  if(notice.working)applyWorking(notice);
  if(notice.decisions)applyDecisions(notice);
  if(notice.version===undefined)return;
  if(layoutVersionOf(notice)===layoutVersion){syncStore.dirty=false;return}
  syncStore.epoch+=1;
  syncStore.dirty=true;
  if(!sceneBusy())flushLayoutNotice();
}
function flushLayoutNotice(){
  if(!syncStore.dirty||sceneBusy()||!LAYOUT_URL)return;
  if(syncStore.fetchEpoch===syncStore.epoch)return;
  const epoch=syncStore.epoch;
  syncStore.fetchEpoch=epoch;
  refreshProjectDocument().then(ok=>{
    if(!ok&&syncStore.fetchEpoch===epoch)syncStore.fetchEpoch=-1;
  });
}
function watchLayout(){
  if(!LAYOUT_URL)return;
  const query=leaseStore.id?("?lease_id="+encodeURIComponent(leaseStore.id)):"";
  if(syncStore.events&&query===syncStore.leaseQuery)return;
  if(syncStore.events)syncStore.events.close();
  syncStore.leaseQuery=query;
  const source=new EventSource(LAYOUT_URL+"/events"+query);
  source.onmessage=event=>{
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
    showRoom(index,false);
  });
}
syncRoomBand();
syncRoomUrl();
if(LAYOUT_URL)watchLayout();

const IDLE_YIELD_SECONDS=300;
function armIdle(){
  if(!PROJECT_EDIT_URL||READ_ONLY||SHARE_FORM||!leaseStore.token)return;
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
async function acquireLease(){
  if(!PROJECT_EDIT_URL||READ_ONLY||SHARE_FORM)return null;
  try{
    const response=await leasePost(LEASE_URL,{holder:"page",label:leaseStore.label,token:leaseStore.token||undefined});
    if(response.status===423){
      const detail=await response.json().catch(()=>({}));
      applyLease(detail.detail&&detail.detail.holder?detail.detail:(detail.detail||null));
      leaseStore.idleYielded=false;
      return null;
    }
    if(!response.ok)return null;
    const lease=await response.json();
    leaseStore.token=lease.token;leaseStore.id=lease.id;leaseStore.idleYielded=false;
    sessionStorage.setItem(LEASE_TOKEN_KEY,leaseStore.token);
    sessionStorage.setItem(LEASE_ID_KEY,leaseStore.id);
    applyLease(lease);
    watchLayout();
    armIdle();
    return lease;
  }catch(error){return null}
}
function yieldIdleLease(){
  if(!PROJECT_EDIT_URL||READ_ONLY||SHARE_FORM||!leaseStore.token)return;
  if(Date.now()-leaseStore.lastInteraction<IDLE_YIELD_SECONDS*1000){
    armIdle();
    return;
  }
  fetch(LEASE_URL,{method:"DELETE",cache:"no-store",headers:{"X-Edit-Lease":leaseStore.token}})
    .catch(()=>{});
  leaseStore.token="";leaseStore.idleYielded=true;
  sessionStorage.removeItem(LEASE_TOKEN_KEY);
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
