// 工作副本记录与助手假设面板；写入使用统一队列。
import {LayoutWriteError} from "./layout_persistence.js";
import {escapeHtml} from "./markup.js";

export function createRoomActivity({
  config, workingSignal, pendingDecisionsSignal, layoutPersistence, canEditLayout,
  setStatus, reportWriteFailure,
}) {
  const {layout_url:LAYOUT_URL,edit_url:PROJECT_EDIT_URL,read_only:READ_ONLY,share_form:SHARE_FORM}=config;
  const DECISIONS_URL=LAYOUT_URL?LAYOUT_URL.replace(/\/layout$/,"/decisions"):"";
  let pendingDecisions=[];
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
    panel.innerHTML=pendingDecisions.map(entry=>{
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
    pendingDecisions=(payload&&payload.decisions&&payload.decisions.pending)||[];
    pendingDecisionsSignal.set(pendingDecisions);
    if(!pendingDecisions.length){
      badge.hidden=true;badge.removeAttribute("title");badge.setAttribute("aria-expanded","false");
      if(panel)panel.hidden=true;
      return;
    }
    badge.hidden=false;
    badge.textContent=`助手假设 ${pendingDecisions.length} 条 · 点开确认`;
    badge.title=pendingDecisions.map(entry=>`${entry.utterance} → ${entry.interpretation}`).join("\n");
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

  return {applyWorking, applyDecisions};
}
