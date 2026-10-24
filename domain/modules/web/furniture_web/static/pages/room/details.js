// 家具列表、属性输入和微调；摆放约束仍由布局求解器计算。
import {detailValues,distancesOf,footprintCenter,heightProbe,normalizeAngle,placementStop,resolveInteger,setItemHeight,solvePlanarDrag,solveRotation} from "/layout-view/layout_solver.js";
import {escapeHtml} from "./markup.js";
import {fillsWall} from "./item_hints.js";

export function createRoomDetails({
  config, scene, state, uiStore, displayScene,
  isDragging, canEditLayout, commitCandidate, persist, render,
  setStatus, selectItem,
}) {
  let panelSignature=null,detailItemId;
  const {read_only:READ_ONLY,share_form:SHARE_FORM,panel_url_base:PANEL_URL_BASE}=config;
  function plansPanels(item){
    return !!item && item.manufacture!==false
      && (item.furniture_category==="floor_cabinet" || item.furniture_category==="wall_cabinet");
  }
  function syncPanel(){
    const items=displayScene().items;
    const signature=items.map(item=>`${item.id}:${item.label}:${item.placement.mode}`).join("|")+"#"+state.selectedId;
    const list=document.getElementById("item-list");
    if(list&&signature!==panelSignature){
      panelSignature=signature;
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
      if(detailItemId!==null){
        detailItemId=null;
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
    if(detailItemId!==item.id){
      detailItemId=item.id;
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
  function nudgeHeight(item,delta){
    if(isDragging()||!canEditLayout())return;
    const before=item;item=structuredClone(item);
    const base=Math.round(item.placement.origin_z_mm||0);
    const solved=resolveInteger(base,base+delta,heightProbe(scene,item,item.footprint));
    if(solved.value===base){setStatus(`离地高度已经是 ${base} mm，${delta>0?"再高":"再低"}${placementStop(solved.blocker)}`,"warn");return}
    setItemHeight(item,solved.value);
    render();
    commitCandidate(item,before);
  }
  function setGap(item,direction,value){
    if(isDragging()||!canEditLayout())return;
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
    if(isDragging()||!canEditLayout())return;
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
    if(isDragging()||!canEditLayout())return;
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
    if(isDragging()||!canEditLayout())return;
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
  function applyLocalDrag(item,dx,dy,startOrigin){
    const origin=startOrigin||[item.placement.origin_x_mm||0,item.placement.origin_y_mm||0];
    const blocker=solvePlanarDrag(scene,item,origin,dx,dy);
    return blocker;
  }

  return {syncPanel, syncDetail, nudgeHeight, reset(){panelSignature=null;detailItemId=undefined}};
}
