// 浏览器编辑租约及事件连接生命周期；权限准入由服务端执行。

export function createRoomLease({
  config, syncStore, leaseSignal, layoutPersistence, setStatus,
  refreshProjectDocument,
}) {
  const {scene_id:SCENE_ID,layout_url:LAYOUT_URL,edit_url:PROJECT_EDIT_URL,read_only:READ_ONLY,share_form:SHARE_FORM}=config;
  const LEASE_URL=LAYOUT_URL?LAYOUT_URL.replace(/\/layout$/,"/edit-lease"):"";
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
    lastInteraction:Date.now(),
    idleYielded:false,
    idleTimer:0,
    phase:"loading",
    pending:null,
    closing:false,
  };
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
  function start(){
    if(LAYOUT_URL&&(!PROJECT_EDIT_URL||READ_ONLY))watchLayout();
    if(PROJECT_EDIT_URL&&!READ_ONLY){
      acquireLease().then(lease=>{
        if(lease)setStatus("可以直接拖动：还没有下游产物时，改动落在同一版上；改到哪一间，哪一间就要重看一眼");
      });
      refreshProjectDocument();
    }
  }

  return {applyLease, ownsLease, leaseMessage, start, get token(){return leaseStore.token}};
}
