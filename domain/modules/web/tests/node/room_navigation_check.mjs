import assert from "node:assert/strict";
import {createRoomNavigation} from "../../furniture_web/static/pages/room/navigation.js";

const handlers={};
const band={
  dataset:{}, hidden:true, innerHTML:"",
  addEventListener(name,callback){handlers[name]=callback},
  querySelectorAll(){return []},
};
globalThis.document={getElementById:id=>id==="room-band"?band:null};
globalThis.location=new URL("http://localhost/preview?room=second&item=cab_second&view=front");
globalThis.history={replaceState(_state,_title,url){globalThis.location=new URL(url)}};
const item=id=>({id,placement:{origin_z_mm:0},height:100,footprint:[]});
const rooms=["first","second"].map(id=>({id,name:id,scene:{
  room:{id,width_mm:4000,depth_mm:3000,height_mm:2800},items:[item("cab_"+id)],
}}));
const scene=structuredClone(rooms[0].scene);
const state={selectedId:null,blocked:null};
const persistence={busy:false};
const selected=[];
const statuses=[];
let resets=0;
const navigation=createRoomNavigation({
  config:{rooms,heading_suffix:"检查"},scene,state,
  resetDetails:()=>resets++,pullStore:{},target:[0,0,0],view:{},canvas:{},
  roomIndexSignal:{set(){}},selectedIdSignal:{set:value=>selected.push(value)},
  layoutPersistence:persistence,updateRoomBounds(){},
  homeTarget:()=>[2000,1500,840],diagonal:()=>6000,
  cancelAnimation(){},syncViewControls(){},
  setView:name=>{state.active=name},selectItem:id=>{state.selectedId=id},
  render(){},setStatus:message=>statuses.push(message),
});

assert.equal(location.search,"?room=second&item=cab_second&view=front",
  "construction must not overwrite the deep link before it is read");
navigation.start();
assert.equal(scene.room.id,"second");
assert.equal(state.selectedId,"cab_second");
assert.equal(state.active,"front");
assert.equal(new URL(location).searchParams.get("room"),"second");

navigation.showDocument({rooms:structuredClone(rooms)});
assert.equal(scene.room.id,"second","document refresh preserves the current room");
assert.equal(state.selectedId,"cab_second");

const click=index=>handlers.click({target:{closest:()=>({dataset:{roomIndex:String(index)}})}});
const before=resets;
persistence.busy=true;
click(0);
assert.equal(scene.room.id,"second","pending writes prevent room changes");
assert.equal(resets,before);
assert.equal(statuses.length,1);
persistence.busy=false;
click(0);
assert.equal(scene.room.id,"first");
assert.equal(state.active,"default_view");
assert.equal(state.selectedId,null,"selection from another room must be cleared");
assert.deepEqual(selected,[null]);
assert.equal(new URL(location).searchParams.get("room"),"first");
assert.equal(resets,before+1);
console.log("Room/item/view deep links, document refresh and busy room switching pass.");
