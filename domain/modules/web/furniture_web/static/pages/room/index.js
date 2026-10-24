// 房间页组装与唯一的渲染/写入桥接；控制器持有各自内部状态。
import {mountLayout} from "../../render/room/layout_scene.js";
import {normalizeItems} from "./layout_payload.js";
import {createLayoutPersistence,LayoutWriteError} from "./layout_persistence.js";
import {poseOperation} from "/layout-view/layout_interaction.js";
import {syncPlacementGeometry} from "/layout-view/layout_solver.js";
import {baseFit,fitDistance} from "../../render/room/layout_camera.js";
import {Component,signal,bootstrapApplication} from "../../shared/reactivity.js";
import {createRoomCamera,DEFAULT_YAW,DEFAULT_PITCH} from "./camera.js";
import {createRoomDetails} from "./details.js";
import {createRoomGestures} from "./gestures.js";
import {createRoomActivity} from "./activity.js";
import {createRoomLease} from "./lease.js";
import {createRoomNavigation} from "./navigation.js";
import {selectHint} from "./item_hints.js";

export function mountRoomPage(config,scene){
  const {scene_id:SCENE_ID,read_only:READ_ONLY,edit_url:PROJECT_EDIT_URL,layout_url:LAYOUT_URL,version:initialLayoutVersion}=config;
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
  };
  const pullStore={now:1,from:1,end:1};
  const uiStore={
    placing:false,
    scale:1,
    viewAnimation:0,
    resizing:0,
  };

  scene.items=normalizeItems(scene.items||[]);
  scene.obstacles=scene.obstacles||[];scene.openings=scene.openings||[];
  const canvas=document.getElementById("scene"),status=document.getElementById("status");
  const view=mountLayout(canvas);
  let HOME_TARGET,diagonal;
  function updateRoomBounds(room){
    HOME_TARGET=[room.width_mm/2,room.depth_mm/2,room.height_mm*.3];
    diagonal=Math.hypot(room.width_mm,room.depth_mm,room.height_mm);
  }
  updateRoomBounds(scene.room);
  const target=[...HOME_TARGET];
  const state={yaw:DEFAULT_YAW,pitch:DEFAULT_PITCH,distance:fitDistance(canvas,diagonal,view,"default_view"),
    orbiting:false,panning:false,active:"default_view",selectedId:null,freeView:null,zoom:1,blocked:null,dims:"selected"};
  const layoutPersistence=createLayoutPersistence({
    readUrl:LAYOUT_URL||`/api/room-scene/${encodeURIComponent(SCENE_ID)}`,
    editUrl:PROJECT_EDIT_URL||`/api/room-scene/${encodeURIComponent(SCENE_ID)}/edit`,
    version:initialLayoutVersion,versioned:Boolean(PROJECT_EDIT_URL),
    getLeaseToken:()=>lease.token,
    isInteracting:()=>Boolean(input.isDragging()||state.orbiting||state.panning),
    onMetadata:payload=>{
      if(payload.lease!==undefined)lease.applyLease(payload.lease||null);
      if(payload.working)activity.applyWorking(payload);
      if(payload.decisions)activity.applyDecisions(payload);
    },
    onDocument:payload=>navigation.showDocument(payload),
  });
  const cameraController=createRoomCamera({canvas,view,state,target,uiStore,pullStore,
    getRoom:()=>scene.room,getDiagonal:()=>diagonal,getHomeTarget:()=>HOME_TARGET,
    activeViewSignal,dimsModeSignal,render,cancelDrag:()=>input.cancelDrag(),flushLayoutNotice});
  const details=createRoomDetails({config,scene,state,uiStore,displayScene,
    isDragging:()=>input.isDragging(),canEditLayout,commitCandidate,persist,render,setStatus,selectItem});
  const input=createRoomGestures({config,scene,canvas,view,state,uiStore,selectedIdSignal,
    camera:cameraController.camera,projector:cameraController.projector,
    unprojectToGround:cameraController.unprojectToGround,screenPoint:cameraController.screenPoint,
    isElevation:cameraController.isElevation,render,setStatus,selectItem,canEditLayout,commitCandidate,flushLayoutNotice,
    nudgeHeight:(item,delta)=>details.nudgeHeight(item,delta)});
  const activity=createRoomActivity({config,workingSignal,pendingDecisionsSignal,
    layoutPersistence,canEditLayout,setStatus,reportWriteFailure});
  const lease=createRoomLease({config,syncStore,leaseSignal,layoutPersistence,setStatus,refreshProjectDocument});
  const navigation=createRoomNavigation({config,scene,state,resetDetails:()=>details.reset(),pullStore,target,view,canvas,
    roomIndexSignal,selectedIdSignal,layoutPersistence,updateRoomBounds,homeTarget:()=>HOME_TARGET,
    diagonal:()=>diagonal,cancelAnimation:()=>cameraController.cancelAnimation(),
    syncViewControls:()=>cameraController.syncViewControls(),setView:name=>cameraController.setView(name),
    selectItem,render,setStatus});
  function displayScene(){return input.displayScene()}
  function refreshProjectDocument(){return layoutPersistence.refresh()}
  function flushLayoutNotice(){layoutPersistence.flush()}
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
    details.syncPanel();
  }

  function setStatus(text,kind){
    statusToastSignal.set({text,kind:kind||""});
    status.textContent=text;
    status.classList.toggle("warn",kind==="warn");
    status.classList.toggle("error",kind==="error");
  }
  function selectItem(id){
    state.selectedId=id;state.blocked=null;
    selectedIdSignal.set(id);
    const item=scene.items.find(candidate=>candidate.id===id);
    setStatus(item?selectHint(item,READ_ONLY):"点击一件家具开始");
    render();
  }
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
    if(PROJECT_EDIT_URL&&!lease.ownsLease()){
      setStatus(lease.leaseMessage(),"warn");
      return false;
    }
    return true;
  }
  async function persist(item,kind,sizes,operation){
    if(READ_ONLY)return false;
    if(PROJECT_EDIT_URL&&!lease.ownsLease()){
      setStatus(lease.leaseMessage(),"warn");
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
      if(raw&&raw.holder)lease.applyLease(raw);
      setStatus("这次改动没有保存；"+lease.leaseMessage(),"warn");
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

  cameraController.fitCanvas();navigation.start();
  render();cameraController.syncViewControls();lease.start();
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

  return Object.freeze({onProjectUpdated:refreshProjectDocument,onStatusToast:setStatus});
}
