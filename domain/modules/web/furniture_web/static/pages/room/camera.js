// 房间页相机、视角过渡和画布事件；几何换算调用渲染模块。
import {ELEVATION_MAX_PITCH,baseFit,fitDistance,isOrthoView,nearAngle} from "../../render/room/layout_camera.js";
export const DEFAULT_YAW=Math.PI*5/12,DEFAULT_PITCH=.72;
export const VIEWS={
  default_view:{yaw:DEFAULT_YAW,pitch:DEFAULT_PITCH},
  top:{yaw:Math.PI/2,pitch:1.48},
  bottom:{yaw:Math.PI/2,pitch:-1.48},
  front:{yaw:Math.PI/2,pitch:0},
  back:{yaw:-Math.PI/2,pitch:0},
  right:{yaw:0,pitch:0},
  left:{yaw:Math.PI,pitch:0},
};

export function createRoomCamera({
  canvas, view, state, target, uiStore,
  pullStore, getRoom, getDiagonal, getHomeTarget, activeViewSignal,
  dimsModeSignal, render, cancelDrag, flushLayoutNotice,
}) {
  function fitCanvas(){view.resize();uiStore.scale=1}
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

  function isElevation(){return state.pitch<ELEVATION_MAX_PITCH}
  function handleViewportResize(){
    cancelDrag();
    fitCanvas();
    if(!uiStore.viewAnimation)state.distance=fitDistance(canvas,getDiagonal(),view,state.active);
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
      state.distance=baseFit(canvas,getDiagonal())*pullStore.now;
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
      target:reset?getHomeTarget():[...target],zoom:reset?1:state.zoom,
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

  return {fitCanvas, camera, projector, unprojectToGround, screenPoint, isElevation, setView, syncViewControls, cancelAnimation(){cancelFrame(uiStore.viewAnimation);uiStore.viewAnimation=0}};
}
