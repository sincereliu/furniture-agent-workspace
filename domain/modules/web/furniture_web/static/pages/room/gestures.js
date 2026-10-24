// 指针与键盘到布局事务的桥接；拖动候选仅在此控制器持有。
import {createDragTransaction} from "/layout-view/layout_interaction.js";
import {contactStop,footprintCenter,wallNormal} from "/layout-view/layout_solver.js";
import {horizontalAxis,rotationSign,verticalPlaneScale} from "../../render/room/layout_camera.js";
import {fillsWall,selectHint} from "./item_hints.js";

export function createRoomGestures({
  config, scene, canvas, view, state,
  uiStore, selectedIdSignal, camera, projector, unprojectToGround,
  screenPoint, isElevation, render, setStatus, selectItem,
  canEditLayout, commitCandidate, flushLayoutNotice, nudgeHeight,
}) {
  const READ_ONLY=config.read_only;
  const px=css=>css*uiStore.scale;
  let drag=null;
  function displayScene(){return drag?drag.preview(scene):scene}
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
      rotationSign:rotationSign(projector(),scene.room.width_mm,center,height),
      threshold:px(4),detachThreshold:px(26)});
    view.setEnabled(false);canvas.classList.add("moving");
    canvas.setPointerCapture(event.pointerId);
    setStatus(selectHint(item,READ_ONLY));render();
  },true);
  canvas.addEventListener("pointermove",event=>{
    if(!drag||event.pointerId!==drag.pointerId)return;
    const result=drag.update(screenPoint(event),{fine:event.shiftKey});
    if(!result.moved)return;
    state.blocked=result.blocker?result.blocker.id:null;
    setStatus(result.blocker?contactStop(result.blocker):`调整 ${drag.item.label}…`,result.blocker?"warn":"");
    render();
  });

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
    else{setStatus(selectHint(result.item,READ_ONLY));render();flushLayoutNotice()}
  });

  function updateCoordReadout(event){
    const box=document.getElementById("coord");
    if(!box)return;
    const [sx,sy]=screenPoint(event);
    const margin=Math.max(scene.room.width_mm,scene.room.depth_mm);
    const ground=isElevation()?null:unprojectToGround(sx,sy);
    if(!ground){box.hidden=true;return}
    const x=Math.round(ground[0]),y=Math.round(ground[1]);
    if(x<-margin||y<-margin||x>scene.room.width_mm+margin||y>scene.room.depth_mm+margin){box.hidden=true;return}
    const outside=x<0||y<0||x>scene.room.width_mm||y>scene.room.depth_mm;
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

  return {displayScene, cancelDrag, isDragging:()=>Boolean(drag)};
}
