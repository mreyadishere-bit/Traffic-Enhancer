"use strict";
/* Traffic Enhancer evidence studio — real API data, no simulated cases. */
const $ = id => document.getElementById(id);
let operatorKey = "", cases = [], selected = null, activeTrackId = null;
let mediaUrl = null, importUrl = null, chosen = null, sourceDuration = null;
let refreshTimer = null, toastTimer = null, activePreviewId = null, connecting = false;
const video = $("caseVideo"), canvas = $("trackCanvas");
const clamp = (x,min,max) => Math.min(max,Math.max(min,x));
const statusText = x => (x || "unavailable").replaceAll("_"," ");
const timecode = x => {
  const s = Math.max(0,Math.floor(Number(x)||0));
  return String(Math.floor(s/60)).padStart(2,"0")+":"+String(s%60).padStart(2,"0");
};
const fmtDate = x => x ? new Date(x).toLocaleString() : "—";
const idShort = x => x ? x.slice(0,12).toUpperCase() : "—";
const make = (tag,cls,text) => {
  const item=document.createElement(tag);
  if(cls)item.className=cls;
  if(text!==undefined)item.textContent=String(text);
  return item;
};
$("today").textContent=new Date().toLocaleDateString("en-US",{day:"numeric",month:"short",year:"numeric"});
function notice(message) {
  const toast=$("toast");
  toast.textContent=message;toast.classList.add("active");
  clearTimeout(toastTimer);toastTimer=setTimeout(()=>toast.classList.remove("active"),6500);
}
async function request(path, options={}) {
  const response=await fetch("/api/v1"+path,{
    ...options,headers:{Authorization:"Bearer "+operatorKey,...(options.headers||{})}
  });
  if(!response.ok) {
    let message="Request failed ("+response.status+")";
    try{const value=await response.json();if(typeof value.detail==="string")message=value.detail}catch{}
    throw new Error(message);
  }
  return response;
}
$("loginForm").addEventListener("submit",async event=>{
  event.preventDefault();
  if(connecting)return;
  connecting=true;
  $("loginError").textContent="";
  operatorKey=$("key").value;
  try{
    cases=(await(await request("/incidents")).json()).items;
    $("key").value="";
    $("authScreen").hidden=true;
    renderLibrary();renderCounts();await loadCapabilities();
    refreshLoop();
    if(cases.length)await openCase(cases[0],false);
  }catch(error){
    operatorKey="";
    $("loginError").textContent=error.message;
  }finally{connecting=false}
});
$("disconnect").addEventListener("click",()=>{
  operatorKey="";cases=[];selected=null;activeTrackId=null;activePreviewId=null;
  if(refreshTimer)clearInterval(refreshTimer);
  releaseVideo();renderCounts();renderLibrary();
  $("authScreen").hidden=false;$("key").focus();
});
function refreshLoop(){
  if(refreshTimer)clearInterval(refreshTimer);
  refreshTimer=setInterval(()=>{
    if(operatorKey)refresh(false);
  },4000);
}
async function refresh(showToast=false){
  if(!operatorKey)return;
  try {
    const prev=selected;
    cases=(await(await request("/incidents")).json()).items;
    renderCounts();renderLibrary();
    if(prev){
      const latest=cases.find(x=>x.id===prev.id);
      if(latest){
        selected=latest;
        renderSelected(false);
        if(prev.status!=="ready"&&latest.status==="ready")await preparePlayer(latest);
      }
    }
    if(showToast)notice("Case library is up to date.");
  }catch(error){notice("Unable to refresh: "+error.message)}
}
$("refresh").addEventListener("click",()=>refresh(true));
function renderCounts(){
  $("nCases").textContent=cases.length;
  $("nReady").textContent=cases.filter(x=>x.status==="ready").length;
  $("nPending").textContent=cases.filter(x=>["queued","processing"].includes(x.status)).length;
  $("nFailed").textContent=cases.filter(x=>x.status==="failed").length;
}
function renderLibrary(){
  const q=$("search").value.trim().toLowerCase(),f=$("statusFilter").value;
  const visible=cases.filter(x=>(f==="all"||x.status===f)
    &&(x.filename.toLowerCase().includes(q)||x.id.toLowerCase().includes(q)));
  const container=$("caseList");container.replaceChildren();
  if(!visible.length){
    container.append(make("p","placeholder",
      cases.length?"No recordings match the current filters.":"No recordings yet. Import a video to begin."));
    return;
  }
  visible.forEach(item=>{
    const row=make("div","case-row");
    const name=make("div");
    name.append(make("strong","case-name",item.filename),
      make("small","",idShort(item.id)+" · "+Number(item.duration).toFixed(1)+"s clip"));
    const when=make("div","case-meta",fmtDate(item.created_at));
    const tag=make("span","case-label "+item.status,item.status);
    const button=make("button","inspect-btn","Inspect ↗");
    button.addEventListener("click",()=>openCase(item));
    row.append(name,when,tag,button);container.append(row);
  });
}
$("search").addEventListener("input",renderLibrary);
$("statusFilter").addEventListener("change",renderLibrary);
async function loadCapabilities(){
  try{
    const caps=(await(await request("/capabilities")).json());
    const summary=[
      ["Qwen2.5-VL",caps.qwen?.configured,"Multimodal reasoning",caps.qwen?.model],
      ["Vehicle tracking",caps.vehicle_tracking?.configured,"YOLO + tracker",""],
      ["Speech transcription",caps.speech?.configured,"Faster-Whisper",""],
      ["Egyptian plate OCR",caps.plate_ocr?.configured,"Specialized detector required",""],
      ["Traffic-offense verification",false,"Human review required",""],
      ["Direct dashcam transfer",false,"Physical device validation needed",""]
    ];
    const parent=$("capabilities");parent.replaceChildren();
    summary.forEach(([name,on,desc,model])=>{
      const card=make("article","capability");
      card.append(make("strong","",name),make("span","",on?"CONFIGURED · NOT VALIDATED":"NOT AVAILABLE / CONFIGURED"),
          make("p","",desc+(model?" · "+model:"")));
      parent.append(card);
    });
  }catch(e){$("capabilities").textContent="Capabilities unavailable: "+e.message}
}
const importSection=$("intake"), importPreview=$("trimVideo");
function showIntake(show=true){
  importSection.hidden=!show;
  if(show)importSection.scrollIntoView({behavior:"smooth",block:"start"});
}
$("newCase").onclick=()=>showIntake(true);
$("closeIntake").onclick=()=>showIntake(false);
const drop=$("drop"),file=$("file");
drop.onclick=()=>file.click();
drop.onkeydown=e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();file.click()}};
drop.ondragover=e=>{e.preventDefault();drop.classList.add("over")};
drop.ondragleave=e=>{e.preventDefault();drop.classList.remove("over")};
drop.ondrop=e=>{e.preventDefault();drop.classList.remove("over");if(e.dataTransfer.files[0])chooseFile(e.dataTransfer.files[0])};
file.onchange=()=>{if(file.files[0])chooseFile(file.files[0])};
function chooseFile(picked){
  if(!/\.(mp4|mov|mkv)$/i.test(picked.name)){notice("Choose an MP4, MOV or MKV file.");return}
  if(picked.size>512*1024*1024){notice("Source video exceeds 512 MB.");return}
  chosen=picked;sourceDuration=null;
  if(importUrl)URL.revokeObjectURL(importUrl);
  importUrl=URL.createObjectURL(picked);importPreview.src=importUrl;
  $("filename").textContent=picked.name;
  $("trimHelp").textContent="Reading video metadata…";
  $("upload").disabled=true;
}
importPreview.onloadedmetadata=()=>{
  sourceDuration=importPreview.duration;
  if(!Number.isFinite(sourceDuration)||sourceDuration<1){sourceDuration=null;return}
  $("startSec").value=0;
  // MP4 browsers can report a rounded timeline slightly longer than FFprobe.
  // Leave a small safety margin; server will still verify the actual source.
  const last=Math.min(20,Math.max(1,Math.floor((sourceDuration-.35)*10)/10));
  $("endSec").value=String(last);
  $("trimSeek").max=String(sourceDuration);
  $("trimHelp").textContent="Source: "+timecode(sourceDuration)+
    ". Select up to three minutes for analysis. The full original is retained.";
  validateTrim();
};
importPreview.onerror=()=>{
  if(chosen){$("trimHelp").textContent="This codec cannot be previewed in the browser. You may still enter segment times.";validateTrim()}
};
importPreview.ontimeupdate=()=>{$("trimSeek").value=String(importPreview.currentTime)};
$("trimSeek").oninput=e=>{try{importPreview.currentTime=Number(e.target.value)}catch{}};
$("startSec").oninput=validateTrim;$("endSec").oninput=validateTrim;
function validateTrim(){
  if(!chosen){$("upload").disabled=true;return false}
  const start=Number($("startSec").value),end=Number($("endSec").value);
  const valid=Number.isFinite(start)&&Number.isFinite(end)&&start>=0&&end-start>=1
    &&end-start<=180&&end<=7200&&(sourceDuration===null||end<=sourceDuration+.1);
  $("upload").disabled=!valid;
  if(!valid)$("uploadStatus").textContent="Select a valid 1–180 second segment.";
  else $("uploadStatus").textContent="Selected "+(end-start).toFixed(1)+"s · Original recording preserved.";
  return valid;
}
$("upload").onclick=()=>{
  if(!operatorKey||!validateTrim())return;
  const form=new FormData();form.append("video",chosen,chosen.name);
  const s=Number($("startSec").value),e=Number($("endSec").value);
  const full=sourceDuration!==null&&s===0&&Math.abs(e-sourceDuration)<.1;
  if(!full){form.append("start_seconds",String(s));form.append("end_seconds",String(e))}
  const description=$("uploadClaim").value.trim();
  if(description)form.append("driver_description",description);
  const xhr=new XMLHttpRequest();
  xhr.open("POST","/api/v1/incidents");
  xhr.setRequestHeader("Authorization","Bearer "+operatorKey);
  $("upload").disabled=true;$("progress").hidden=false;
  $("uploadStatus").textContent="Uploading original evidence…";
  xhr.upload.onprogress=ev=>{
    if(ev.lengthComputable)$("progressBar").style.width=(100*ev.loaded/ev.total).toFixed(0)+"%";
  };
  xhr.onload=async()=>{
    let data={};try{data=JSON.parse(xhr.responseText)}catch{}
    $("progress").hidden=true;
    if(xhr.status===202){
      chosen=null;file.value="";$("filename").textContent="Choose a recording";
      if(importUrl){URL.revokeObjectURL(importUrl);importUrl=null}
      importPreview.removeAttribute("src");importPreview.load();
      $("uploadStatus").textContent="Recording accepted. Watch its real processing stages below.";
      await refresh();
      const job=cases.find(x=>x.id===data.id);
      if(job)await openCase(job);
    }else{
      $("upload").disabled=false;
      $("uploadStatus").textContent=typeof data.detail==="string"?data.detail:"Upload failed.";
      notice("Upload rejected: "+$("uploadStatus").textContent);
    }
  };
  xhr.onerror=()=>{
    $("upload").disabled=false;$("progress").hidden=true;
    notice("Network interruption. Check the library before re-uploading.");
  };
  xhr.send(form);
};
function releaseVideo(){
  video.pause();
  video.removeAttribute("src");video.load();
  if(mediaUrl){URL.revokeObjectURL(mediaUrl);mediaUrl=null}
  activePreviewId=null;
  video.hidden=true;
  $("playerEmpty").hidden=false;$("videoPill").hidden=true;
  $("play").disabled=$("back").disabled=$("forward").disabled=true;
  $("seek").disabled=true;drawOverlay();
}
async function openCase(item,scroll=true){
  if(!item)return;
  const changed=selected?.id!==item.id;
  selected=item;
  activeTrackId=item.review?.selected_track_id??null;
  renderSelected(changed);
  if(changed||activePreviewId!==item.id)await preparePlayer(item);
  if(scroll)$("studio").scrollIntoView({behavior:"smooth",block:"start"});
}
function renderSelected(replaceForm){
  const x=selected;if(!x)return;
  const a=x.analysis||{}, review=x.review||{};
  $("selectedId").textContent=idShort(x.id)+" · "+statusText(x.stage||x.status).toUpperCase();
  $("currentCaseTitle").textContent=x.filename;
  $("caseState").textContent=x.status==="ready"?"REVIEW AVAILABLE":statusText(x.status).toUpperCase();
  $("caseHeading").textContent=x.status==="ready"?"What does the evidence show?":"Analysis "+statusText(x.status);
  $("caseIntro").textContent=x.status==="ready"?
    "Only verified observations from your uploaded footage belong in the report. AI suggestions remain preliminary.":
    (x.error||"The recording is being processed. The model stages will appear when available.");
  $("report").disabled=x.status!=="ready";
  $("reanalyze").disabled=!["ready","failed"].includes(x.status);
  $("saveReview").disabled=!["ready","failed"].includes(x.status);
  $("evidenceSource").disabled=!["ready","failed"].includes(x.status);
  if(replaceForm){
    $("reviewClaim").value=review.manual_description || a.driver_claim?.verbatim || "";
    $("reviewNote").value=review.review_note || "";
    $("reviewEventSecond").value=review.reviewed_event_second??"";
    $("reviewStatus").value=review.status || "unreviewed";
  }
  showStages(x);renderTracks(x);renderEvents(x);renderMarkers(x);
  drawOverlay();
}
function showStages(x){
  const a=x.analysis||{};
  const stages=[
    ["Speech",a.transcription],
    ["Driver description",a.driver_claim],
    ["Vehicle tracking",a.object_tracking],
    ["Qwen2.5-VL",a.visual_reasoning],
    ["Egyptian plate OCR",a.plate_recognition],
    ["Event assessment",a.violation_assessment],
    ["Vehicle association",a.target_matching]
  ];
  const parent=$("stageList");parent.replaceChildren();
  if(x.status==="processing"||x.status==="queued"){
    parent.append(make("p","placeholder","Currently: "+statusText(x.stage||x.status)));
  }
  stages.forEach(([name,stage])=>{
    const status=stage?.status||"unavailable";
    const row=make("div","stage-item");
    const label=make("span","",name);
    const b=make("b",["failed","unparseable"].includes(status)?"fail":
      ["not_configured","requires_review","candidate_for_review"].includes(status)?"warn":"",statusText(status));
    row.append(label,b);
    if(stage?.status==="failed"||stage?.status==="not_configured"||stage?.status==="unparseable"){
      row.append(make("small","",stage.note||"This model is not available."));
    }
    parent.append(row);
  });
}
function renderTracks(x){
  const items=x.analysis?.object_tracking?.tracks||[];
  const parent=$("trackList");parent.replaceChildren();
  if(!items.length){
    parent.append(make("p","placeholder","No tracked vehicles available. Enable and test your vehicle detector."));
    return;
  }
  items.forEach(track=>{
    if(track.track_id===undefined||track.track_id===null)return;
    const b=make("button","track-chip"+(activeTrackId===track.track_id?" selected":""));
    b.append(make("span","",track.label+" · #"+track.track_id),
      make("small","",(track.observations?.length||0)+" sampled observations"));
    b.onclick=()=>{
      activeTrackId=track.track_id;
      renderTracks(x);drawOverlay();
      const first=track.observations?.find(o=>Number.isFinite(o.second));
      if(first && !video.hidden)video.currentTime=first.second;
      notice("Track #"+track.track_id+" selected for review. Save to retain the selection.");
    };
    parent.append(b);
  });
}
function renderEvents(x){
  const a=x.analysis||{};
  const parent=$("eventList");parent.replaceChildren();
  const observations=a.visual_reasoning?.observations||{};
  if(observations.scene_summary){
    const scene=make("article","event-card");
    scene.append(make("div","event-head","Visual scene summary · unverified"),
      make("p","",observations.scene_summary));
    parent.append(scene);
  }
  const events=a.violation_assessment?.candidates||[];
  if(!events.length){
    const note=a.visual_reasoning?.status==="completed"?
      "No supported potential event was produced. This does not prove that no incident occurred.":
      "No visual event assessment is available. Qwen requires an operational model and appropriate footage.";
    parent.append(make("p","placeholder",note));
    return;
  }
  events.forEach(event=>{
    const card=make("article","event-card"), head=make("div","event-head");
    head.append(make("strong","",statusText(event.category)));
    if(Number.isFinite(event.time_seconds)){
      const jump=make("button","","Go to "+timecode(event.time_seconds)+" ↗");
      jump.onclick=()=>{if(!video.hidden)video.currentTime=event.time_seconds};
      head.append(jump);
    }
    card.append(head,make("p","",event.visual_evidence||"Visual model did not provide supporting details."),
      make("small","","MODEL SUGGESTION · "+(event.uncertainty||"unverified")+" · HUMAN REVIEW REQUIRED"));
    parent.append(card);
  });
}
function renderMarkers(x){
  const parent=$("markers");parent.replaceChildren();
  const duration=Number(x.duration)||0;
  if(!duration)return;
  const times=[
    ...(x.analysis?.violation_assessment?.candidates||[]).map(item=>item.time_seconds),
    x.review?.reviewed_event_second,
    ...(x.analysis?.transcription?.segments||[]).map(s=>s.start)
  ];
  times.filter(t=>typeof t==="number"&&t>=0&&t<=duration).slice(0,70).forEach(t=>{
    const mark=make("i");mark.style.left=(t/duration*100)+"%";parent.append(mark);
  });
}
function drawOverlay(){
  const parent=$("playerContainer");
  const width=parent.clientWidth,height=parent.clientHeight;
  if(width<=0||height<=0)return;
  const density=Math.min(window.devicePixelRatio||1,2);
  canvas.width=Math.round(width*density);canvas.height=Math.round(height*density);
  const ctx=canvas.getContext("2d");ctx.scale(density,density);ctx.clearRect(0,0,width,height);
  if(!selected||video.hidden||video.readyState===0||!$("overlayToggle").checked)return;
  const w=video.videoWidth||selected.video?.width,h=video.videoHeight||selected.video?.height;
  if(!w||!h)return;
  const scale=Math.min(width/w,height/h),imageW=w*scale,imageH=h*scale;
  const offsetX=(width-imageW)/2,offsetY=(height-imageH)/2;
  const tracks=selected.analysis?.object_tracking?.tracks||[];
  const debug=$("debugToggle").checked;
  const visible=debug?tracks:tracks.filter(t=>t.track_id===activeTrackId);
  const fps=Number(selected.video?.frame_rate)||30;
  const stride=Number(selected.analysis?.object_tracking?.stride)||5;
  const windowSeconds=Math.min(.7,Math.max(.23,1.4*stride/fps));
  for(const track of visible){
    const observations=(track.observations||[]).filter(o=>Number.isFinite(o.second)&&Array.isArray(o.box_xyxy));
    if(!observations.length)continue;
    let match=null,dt=Infinity;
    for(const o of observations){
      const diff=Math.abs(o.second-video.currentTime);
      if(diff<dt){match=o;dt=diff}
    }
    if(!match||dt>windowSeconds)continue;
    const [left,top,right,bottom]=match.box_xyxy;
    const x=offsetX+left*scale,y=offsetY+top*scale;
    const boxW=(right-left)*scale,boxH=(bottom-top)*scale;
    if(boxW<=1||boxH<=1)continue;
    ctx.strokeStyle=debug&&track.track_id!==activeTrackId?"rgba(210,230,228,.60)":"#bceee2";
    ctx.lineWidth=debug?1.4:2.5;
    ctx.strokeRect(x,y,boxW,boxH);
    const label="TRACK "+track.track_id+" · "+track.label;
    ctx.font="700 11px DM Sans, sans-serif";
    const labelW=ctx.measureText(label).width+16;
    ctx.fillStyle="#162d32e8";ctx.fillRect(x,Math.max(0,y-24),labelW,22);
    ctx.fillStyle="#e5faf4";ctx.fillText(label,x+8,Math.max(14,y-9));
  }
}
window.addEventListener("resize",drawOverlay);
$("overlayToggle").onchange=drawOverlay;
$("debugToggle").onchange=()=>{if($("debugToggle").checked)$("overlayToggle").checked=true;drawOverlay()};
async function preparePlayer(x){
  releaseVideo();
  if(x.status!=="ready")return;
  try{
    const response=await request("/incidents/"+x.id+"/video");
    const blob=await response.blob();
    if(selected?.id!==x.id)return;
    mediaUrl=URL.createObjectURL(blob);
    video.src=mediaUrl;video.hidden=false;
    $("playerEmpty").hidden=true;$("videoPill").hidden=false;
    activePreviewId=x.id;
    $("play").disabled=$("back").disabled=$("forward").disabled=false;
    $("seek").disabled=false;
    video.load();
  }catch(e){$("playerEmpty").textContent="Cannot load source video: "+e.message}
}
video.onloadedmetadata=()=>{syncTime();drawOverlay()};
video.ontimeupdate=()=>{syncTime();drawOverlay()};
video.onseeked=drawOverlay;
video.onplay=()=>{$("play").textContent="Ⅱ"};
video.onpause=()=>{$("play").textContent="▶"};
function syncTime(){
  const d=video.duration||selected?.duration||0;
  $("timecode").textContent=timecode(video.currentTime)+" / "+timecode(d);
  if(d>0)$("seek").value=String(Math.floor(video.currentTime/d*1000));
  const origin=Number(selected?.video?.selection?.start_seconds||0);
  $("sourceTime").textContent="Source T+"+timecode(origin+video.currentTime)+" · Clip T+"+timecode(video.currentTime);
}
$("seek").oninput=e=>{if(Number.isFinite(video.duration)&&video.duration>0)video.currentTime=Number(e.target.value)/1000*video.duration};
$("play").onclick=()=>{if(video.paused)video.play().catch(e=>notice(e.message));else video.pause()};
$("back").onclick=()=>{video.currentTime=Math.max(0,video.currentTime-1/(selected?.video?.frame_rate||30))};
$("forward").onclick=()=>{video.currentTime=Math.min(video.duration||1,video.currentTime+1/(selected?.video?.frame_rate||30))};
async function download(path,name){
  if(!selected)return;
  try{
    const blob=await(await request(path)).blob(), url=URL.createObjectURL(blob);
    const a=make("a");a.href=url;a.download=name;
    document.body.append(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),2000);
  }catch(e){notice("Download failed: "+e.message)}
}
$("evidenceSource").onclick=()=>{if(selected)download("/incidents/"+selected.id+"/source",selected.filename)};
$("report").onclick=()=>{if(selected)download("/incidents/"+selected.id+"/report.pdf","traffic-report-"+selected.id+".pdf")};
$("saveReview").onclick=async()=>{
  if(!selected)return;
  const eventRaw=$("reviewEventSecond").value.trim();
  const eventSecond=eventRaw?Number(eventRaw):null;
  if(eventSecond!==null&&(!Number.isFinite(eventSecond)||eventSecond<0||eventSecond>selected.duration)){
    notice("Event time must be inside the selected clip.");return;
  }
  const payload={
    status:$("reviewStatus").value,
    manual_description:$("reviewClaim").value.trim(),
    selected_track_id:activeTrackId,
    reviewed_event_second:eventSecond,
    review_note:$("reviewNote").value.trim()
  };
  $("saveReview").disabled=true;
  try{
    const r=(await(await request("/incidents/"+selected.id+"/review",{
      method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)
    })).json());
    selected.review=r.review;
    cases=cases.map(x=>x.id===selected.id?selected:x);
    renderEvents(selected);renderMarkers(selected);
    notice(r.reanalyze_recommended?
      "Review saved. Re-analyze to use the updated description in the AI pipeline.":
      "Reviewer notes saved. No official violation has been declared.");
  }catch(e){notice("Cannot save review: "+e.message)}
  finally{$("saveReview").disabled=false}
};
$("reanalyze").onclick=async()=>{
  if(!selected)return;
  const id=selected.id;
  $("reanalyze").disabled=true;
  try{
    await request("/incidents/"+id+"/reanalyze",{method:"POST"});
    notice("Re-analysis started. It will use the current model configuration and saved driver description.");
    await refresh();
  }catch(e){notice("Re-analysis error: "+e.message);$("reanalyze").disabled=false}
};
