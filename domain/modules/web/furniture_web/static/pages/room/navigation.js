// 房间集合、深链与文档安装；不拥有相机或属性面板缓存。
import {normalizeItems} from "./layout_payload.js";
import {escapeHtml} from "./markup.js";
import {DEFAULT_YAW,DEFAULT_PITCH,VIEWS} from "./camera.js";
import {fitDistance} from "../../render/room/layout_camera.js";

export function createRoomNavigation({
  config, scene, state, resetDetails, pullStore,
  target, view, canvas, roomIndexSignal, selectedIdSignal,
  layoutPersistence, updateRoomBounds, homeTarget, diagonal, cancelAnimation,
  syncViewControls, setView, selectItem, render, setStatus,
}) {
  let rooms=config.rooms;
  let roomIndex=0;
  function bindRoom(){
    const room=scene.room;
    updateRoomBounds(room);
    const roomMeta=document.getElementById("room-meta");
    if(roomMeta){
      roomMeta.textContent=[`${Math.round(room.width_mm)} × ${Math.round(room.depth_mm)} × ${Math.round(room.height_mm)} mm`,
        `${scene.items.length} 件家具`].join(" · ");
    }
    const heading=document.getElementById("heading");
    if(heading){
      heading.textContent=(room.name||"房间")+" · "+(config.heading_suffix);
      document.title=heading.textContent;
    }
  }

  function deepLinkParams(){
    const params=new URLSearchParams(typeof location!=="undefined"?location.search:"");
    if(typeof location!=="undefined"&&location.hash.length>1){
      new URLSearchParams(location.hash.slice(1)).forEach((value,key)=>{
        if(!params.has(key))params.set(key,value);
      });
    }
    return params;
  }
  function syncRoomUrl(){
    if(!rooms||rooms.length<2)return;
    const entry=rooms[roomIndex];
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
        const pressed=index===roomIndex?' aria-pressed="true"':' aria-pressed="false"';
        const mark=entry.approved===false?' data-pending="true"':"";
        return `<button type="button" data-room-index="${index}"${pressed}${mark}>${escapeHtml(entry.name||entry.id)}${pending}</button>`;
      }).join("");
      return;
    }
    Array.from(band.querySelectorAll("button")).forEach(button=>{
      button.setAttribute("aria-pressed",Number(button.dataset.roomIndex)===roomIndex?"true":"false");
    });
  }
  function showRoom(index,keepCamera){
    if(!rooms||!rooms[index])return;
    roomIndex=index;
    roomIndexSignal.set(index);
    const next=rooms[index].scene;
    scene.room=next.room;
    scene.items=normalizeItems(next.items||[]);
    scene.obstacles=next.obstacles||[];
    scene.openings=next.openings||[];
    bindRoom();
    if(!keepCamera){
      cancelAnimation();
      pullStore.now=pullStore.from=pullStore.end=1;state.zoom=1;state.freeView=null;
      target[0]=homeTarget()[0];target[1]=homeTarget()[1];target[2]=homeTarget()[2];
      state.yaw=DEFAULT_YAW;state.pitch=DEFAULT_PITCH;
      state.distance=fitDistance(canvas,diagonal(),view,"default_view");
      state.active="default_view";
      syncViewControls();
    }
    if(state.selectedId&&!scene.items.some(item=>item.id===state.selectedId)){
      state.selectedId=null;state.blocked=null;
      selectedIdSignal.set(null);
    }
    resetDetails();
    syncRoomBand();
    syncRoomUrl();
    render();
  }

  const roomBand=document.getElementById("room-band");
  if(roomBand){
    roomBand.addEventListener("click",event=>{
      const button=event.target&&event.target.closest?event.target.closest("button[data-room-index]"):null;
      if(!button)return;
      const index=Number(button.dataset.roomIndex);
      if(!Number.isInteger(index)||!rooms||!rooms[index]||index===roomIndex)return;
      if(layoutPersistence.busy){setStatus("布局正在操作或保存，完成后再切换房间","warn");return}
      showRoom(index,false);
    });
  }
  function showDocument(payload){
    if(!payload.rooms){scene.items=normalizeItems(payload.items||[]);render();return}
    rooms=payload.rooms;
    let index=rooms.findIndex(entry=>entry.id===scene.room.id);
    showRoom(index<0?0:index,true);
  }
  function start(){
    bindRoom();
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
    syncRoomBand();
    syncRoomUrl();
  }

  return {showDocument, start};
}
