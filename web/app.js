"use strict";
// Operator key lives in memory only. This is a single-operator dev MVP.
const el=id=>document.getElementById(id);
let key="",accessReady=false,localAccess=false,items=[],selected=null,mediaUrl=null,currentFile=null,poll=null,toastTimer=null;
let previewObjectUrl=null,trimDuration=null,trimStart=0,trimEnd=0,trimReady=false;
const trimFormat=s=>{const seconds=Math.floor(Number(s)||0);return Math.floor(seconds/60)+":"+String(seconds%60).padStart(2,"0")};
const MAX_SEGMENT=180;
const date=s=>s?new Date(s).toLocaleString():"—";
const mb=n=>(Number(n)/1024/1024).toFixed(1)+" MB";
el("today").textContent=new Date().toLocaleDateString("en-US",{month:"short",day:"2-digit",year:"numeric"}).toUpperCase();
function toast(message){el("toast").textContent=message;el("toast").classList.add("show");clearTimeout(toastTimer);toastTimer=setTimeout(()=>el("toast").classList.remove("show"),5000)}
async function api(path,opts={}){
 const res=await fetch("/api/v1"+path,{...opts,headers:{...(key?{Authorization:"Bearer "+key}:{}),...(opts.headers||{})}});
 if(!res.ok){let msg="Request failed ("+res.status+")";try{let x=await res.json();if(typeof x.detail==="string")msg=x.detail}catch{}throw Error(msg)}
 return res;
}
el("loginForm").addEventListener("submit",async e=>{
 e.preventDefault();key=el("key").value;el("loginError").textContent="";
 try{const r=await api("/incidents");items=(await r.json()).items;accessReady=true;el("overlay").classList.add("hidden");el("key").value="";render();refreshLoop();const caps=(await(await api("/capabilities")).json());if(!caps.qwen.configured)toast("Qwen2.5-VL is not configured on this backend. See docs/AI_RUNTIME.md.");}catch(error){key="";accessReady=false;el("loginError").textContent=error.message==="Invalid operator key"?"Invalid key for this running server. Use the operator key configured as TE_API_KEY.":error.message}
});
el("disconnect").addEventListener("click",()=>{if(localAccess)return;key="";accessReady=false;items=[];selected=null;if(poll)clearInterval(poll);clearMedia();render();el("overlay").classList.remove("hidden")});
function refreshLoop(){if(poll)clearInterval(poll);poll=setInterval(()=>{if(items.some(x=>["queued","processing"].includes(x.status)))refresh()},3000)}
async function refresh(){
 if(!accessReady)return;
 try{
   const previousStatus=selected?.status;
   items=(await(await api("/incidents")).json()).items;
   if(selected){selected=items.find(x=>x.id===selected.id)||selected;}
   render();
   if(selected){
     showAnalysis(selected);
     // The upload selected this job before it finished. Populate the actual
     // evidence preview when processing transitions from queued to ready.
     if(previousStatus!=="ready"&&selected.status==="ready")await selectIncident(selected,false);
   }
 }catch(e){toast("Refresh failed: "+e.message)}
}
// Direct Windows localhost access starts immediately without a login screen.
// Any hosted URL (including private GitHub Codespaces) retains its operator key.
async function bootLocalWorkspace(){
 try{
  const resp=await fetch("/api/v1/session",{cache:"no-store"});
  if(!resp.ok)return;
  const session=await resp.json();
  if(session.login_required!==false)return;
  localAccess=true;
  const data=await(await api("/incidents")).json();
  items=data.items;
  accessReady=true;
  el("overlay").classList.add("hidden");
  el("disconnect").hidden=true;
  render();
  refreshLoop();
 }catch(error){console.warn("Automatic local workspace setup failed:",error)}
}
bootLocalWorkspace();

el("refresh").addEventListener("click",refresh);
el("newIncident").addEventListener("click",()=>{el("studio").scrollIntoView({behavior:"smooth"});el("video").click()});
const drop=el("drop"),upload=el("video");
drop.addEventListener("click",()=>upload.click());
drop.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();upload.click()}});
["dragenter","dragover"].forEach(t=>drop.addEventListener(t,e=>{e.preventDefault();drop.classList.add("over")}));
["dragleave","drop"].forEach(t=>drop.addEventListener(t,e=>{e.preventDefault();drop.classList.remove("over")}));
drop.addEventListener("drop",e=>{if(e.dataTransfer.files[0])choose(e.dataTransfer.files[0])});
upload.addEventListener("change",()=>{if(upload.files[0])choose(upload.files[0])});
function removeTrimPreview(){
 if(previewObjectUrl){URL.revokeObjectURL(previewObjectUrl);previewObjectUrl=null}
 el("trimPreview").pause();el("trimPreview").removeAttribute("src");el("trimPreview").load();
 el("trimPanel").hidden=true;trimDuration=null;trimReady=false;
}
function renderTrim(){
 const known=Number.isFinite(trimDuration)&&trimDuration>0;
 if(known){
   el("trimStart").disabled=false;el("trimEnd").disabled=false;
   el("trimStart").max=String(trimDuration);
   el("trimEnd").max=String(trimDuration);
   el("trimStart").value=String(trimStart);el("trimEnd").value=String(trimEnd);
   el("sourceLength").textContent="Source length: "+trimFormat(trimDuration);
 }else{
   el("trimStart").disabled=true;el("trimEnd").disabled=true;
   el("sourceLength").textContent="Duration not readable in browser — use second inputs";
 }
 el("startLabel").textContent=trimFormat(trimStart);
 el("endLabel").textContent=trimFormat(trimEnd);
 el("trimStartNumber").value=String(Math.round(trimStart*10)/10);
 el("trimEndNumber").value=String(Math.round(trimEnd*10)/10);
 const length=trimEnd-trimStart;
 const valid=Number.isFinite(length)&&length>=1&&length<=MAX_SEGMENT&&trimStart>=0
     &&(!known||trimEnd<=trimDuration+0.01);
 el("trimLength").textContent=valid?"Selected: "+trimFormat(length)+" ("+length.toFixed(1)+"s)":"Select 1–180 seconds";
 el("upload").disabled=!currentFile||!valid||!trimReady;
 el("playTrim").disabled=!known||!valid;
 el("trimHint").textContent=valid?
   (known&&Math.abs(trimStart)<0.01&&Math.abs(trimEnd-trimDuration)<0.11
    ? "Whole video selected; original will be analyzed as-is."
    : "The server will re-encode this segment accurately; it keeps the original file and hashes both copies.")
   : "Choose a clip of at least 1 second and at most 180 seconds.";
}
function setTrimBounds(which,raw){
 let value=Number(raw);
 if(!Number.isFinite(value))value=which==="start"?trimStart:trimEnd;
 const maximum=trimDuration??7200;
 if(which==="start"){
   trimStart=Math.max(0,Math.min(value,maximum-1));
   if(trimEnd<=trimStart+1)trimEnd=Math.min(maximum,trimStart+20);
   if(trimEnd-trimStart>MAX_SEGMENT)trimEnd=Math.min(maximum,trimStart+MAX_SEGMENT);
 }else{
   trimEnd=Math.max(1,Math.min(value,maximum));
   if(trimStart>=trimEnd-1)trimStart=Math.max(0,trimEnd-20);
   if(trimEnd-trimStart>MAX_SEGMENT)trimStart=Math.max(0,trimEnd-MAX_SEGMENT);
 }
 const player=el("trimPreview");
 if(trimDuration!==null&&player.readyState>=1){try{player.currentTime=trimStart}catch{}}
 renderTrim();
}
function choose(file){
 const ext=file.name.split(".").pop().toLowerCase();
 if(!["mp4","mov","mkv"].includes(ext)){toast("Supported formats: MP4, MOV, MKV");return}
 if(file.size>512*1024*1024){toast("Source exceeds 512 MB. Please reduce file size.");return}
 removeTrimPreview();
 currentFile=file;trimStart=0;trimEnd=20;
 el("filename").textContent=file.name;
 el("trimPanel").hidden=false;
 el("uploadStatus").textContent=mb(file.size)+" · Loading video preview…";
 trimReady=false;
 previewObjectUrl=URL.createObjectURL(file);
 el("trimPreview").src=previewObjectUrl;
 el("trimFallback").hidden=true;
 renderTrim();
}
el("trimPreview").addEventListener("loadedmetadata",()=>{
 const duration=el("trimPreview").duration;
 if(!Number.isFinite(duration)||duration<1){el("trimFallback").hidden=false;return}
 trimDuration=duration;trimReady=true;trimStart=0;trimEnd=duration<=MAX_SEGMENT?duration:Math.min(20,duration);
 el("uploadStatus").textContent=duration>MAX_SEGMENT?
   "Long video detected: select your 1–180 second segment below.":
   "Video ready. You can trim it before analysis.";
 renderTrim();
});
el("trimPreview").addEventListener("error",()=>{
 if(!currentFile)return;
 trimReady=true;
 el("trimFallback").hidden=false;
 el("uploadStatus").textContent="Cannot preview the codec in your browser. Enter segment seconds to trim.";
 renderTrim();
});
el("trimPreview").addEventListener("timeupdate",()=>{
 if(el("trimPreview").currentTime>trimEnd+0.08&&trimEnd>trimStart){
   el("trimPreview").pause();
   el("trimPreview").currentTime=trimStart;
 }
});
el("playTrim").addEventListener("click",()=>{
 const player=el("trimPreview");
 if(!Number.isFinite(trimDuration))return;
 player.currentTime=trimStart;player.play().catch(()=>toast("Preview not supported; server can still trim."));
});
el("trimStart").addEventListener("input",e=>setTrimBounds("start",e.target.value));
el("trimEnd").addEventListener("input",e=>setTrimBounds("end",e.target.value));
el("trimStartNumber").addEventListener("change",e=>setTrimBounds("start",e.target.value));
el("trimEndNumber").addEventListener("change",e=>setTrimBounds("end",e.target.value));
el("upload").addEventListener("click",()=>{
 if(!currentFile||!accessReady)return;
 const xhr=new XMLHttpRequest();xhr.open("POST","/api/v1/incidents");if(key)xhr.setRequestHeader("Authorization","Bearer "+key);
 const data=new FormData();data.append("video",currentFile,currentFile.name);
 const full=Number.isFinite(trimDuration)&&Math.abs(trimStart)<0.01&&Math.abs(trimEnd-trimDuration)<0.11;
 if(!full){data.append("start_seconds",String(trimStart));data.append("end_seconds",String(trimEnd))}
 el("upload").disabled=true;el("progress").hidden=false;el("progressBar").style.width="0%";el("uploadStatus").textContent="Uploading original footage…";
 xhr.upload.onprogress=e=>{if(e.lengthComputable)el("progressBar").style.width=Math.round(100*e.loaded/e.total)+"%"};
 xhr.onload=async()=>{
  let body={};try{body=JSON.parse(xhr.responseText)}catch{}
  if(xhr.status===202){
   toast("Original evidence accepted and hashed.");
   currentFile=null;upload.value="";el("filename").textContent="Drop dashcam footage here";removeTrimPreview();
   el("uploadStatus").textContent="Analyzing actual footage. Status will update…";
   await refresh();const match=items.find(x=>x.id===body.id);if(match)selectIncident(match);
   let tries=0;const track=setInterval(async()=>{tries++;await refresh();let x=items.find(i=>i.id===body.id);if((x&&!["queued","processing"].includes(x.status))||tries>40){clearInterval(track);el("progress").hidden=true;el("uploadStatus").textContent=x?.status==="ready"?"Preliminary report ready.":"View the incident library for job status."}},2000);
  }else{el("progress").hidden=true;el("uploadStatus").textContent=body.detail||"Upload failed.";toast("Upload rejected: "+(body.detail||xhr.status))}
  el("upload").disabled=!currentFile;
 };
 xhr.onerror=()=>{el("upload").disabled=false;el("progress").hidden=true;el("uploadStatus").textContent="Network interrupted. Check library before retrying."};
 xhr.send(data);
});
el("search").addEventListener("input",render);el("filter").addEventListener("change",render);
function td(text,cls=""){const c=document.createElement("td");if(cls)c.className=cls;c.textContent=text;return c}
function render(){
 el("nTotal").textContent=items.length;
 el("nReady").textContent=items.filter(x=>x.status==="ready").length;
 el("nPending").textContent=items.filter(x=>["queued","processing"].includes(x.status)).length;
 el("nFailed").textContent=items.filter(x=>x.status==="failed").length;
 el("count").textContent=items.length;
 const q=el("search").value.toLowerCase(),filter=el("filter").value;
 const rows=items.filter(x=>(filter==="all"||x.status===filter)&&(x.filename.toLowerCase().includes(q)||x.id.includes(q)));
 const tbody=el("rows");tbody.replaceChildren();
 if(!rows.length){const tr=document.createElement("tr");const cell=td("No incidents match these filters. Upload real dashcam footage to begin.","no-data");cell.colSpan=5;tr.append(cell);tbody.append(tr);return}
 rows.forEach(x=>{
  const tr=document.createElement("tr");const filename=td("");const strong=document.createElement("span");strong.className="name";strong.textContent=x.filename;const minor=document.createElement("span");minor.className="file-id";minor.textContent=x.id.slice(0,14)+"… · "+mb(x.bytes);filename.append(strong,minor);
  const status=td("");const tag=document.createElement("span");tag.className="tag "+x.status;tag.textContent=x.status;status.append(tag);
  const action=td("");const btn=document.createElement("button");btn.className="inspect";btn.textContent="Inspect ↗";btn.addEventListener("click",()=>selectIncident(x));action.append(btn);
  tr.append(filename,td(date(x.created_at)),td(Number(x.duration).toFixed(1)+" sec"),status,action);tbody.append(tr);
 });
}
function clearMedia(){if(mediaUrl){URL.revokeObjectURL(mediaUrl);mediaUrl=null}const root=el("frame");root.replaceChildren();const empty=document.createElement("div");empty.className="empty-frame";empty.textContent="Select a ready incident to inspect original evidence.";root.append(empty)}
function stateRow(label,value){const wrap=document.createElement("div"),a=document.createElement("span"),b=document.createElement("b");a.textContent=label;b.textContent=(value||"no data").replaceAll("_"," ").toUpperCase();if(["not_configured","failed"].includes(value))b.className="warn";else if(value!=="completed")b.className="muted";wrap.append(a,b);return wrap}
function showAnalysis(x){
 el("selected").textContent=x.id.slice(0,12).toUpperCase()+" / "+x.status.toUpperCase()+" / "+(x.stage||"").replaceAll("_"," ").toUpperCase();
 el("play").disabled=x.status!=="ready";el("pdf").disabled=x.status!=="ready";el("source").disabled=x.status!=="ready";el("recheck").disabled=!["ready","failed"].includes(x.status);
 const a=x.analysis||{}, stages=el("stages");stages.replaceChildren(
   stateRow("VEHICLE DETECTION",a.vehicle_detection?.status||x.status),
   stateRow("SPEECH TRANSCRIPTION",a.transcription?.status||x.status),
   stateRow("VIOLATION ASSESSMENT",a.violation_assessment?.status||"not_implemented")
 );
 if(a.vehicle_detection?.detections?.length){
   stages.append(stateRow("SAMPLED-FRAME DETECTIONS (CAPPED AT 250)",
     String(a.vehicle_detection.detections.length)
     +(a.vehicle_detection.detections.length>=250?" + (limit)":"")));
 }
 if(a.object_tracking?.sampled_frames){
   stages.append(stateRow("VIDEO FRAMES SAMPLED",String(a.object_tracking.sampled_frames)));
 }
 const extras = [
  ["QWEN2.5-VL VIDEO ANALYSIS",a.visual_reasoning?.status||"not_configured"],
  ["VEHICLE TRACKING",a.object_tracking?.status||"not_configured"],
  ["EGYPTIAN PLATE OCR",a.plate_recognition?.status||"not_configured"],
  ["DRIVER VOICE DESCRIPTION",a.driver_claim?.status||"unavailable"],
  ["TARGET VEHICLE MATCH",a.target_matching?.status||"unavailable"]
 ];
 extras.forEach(pair=>stages.append(stateRow(pair[0],pair[1])));
 // A completed incident can still contain individually failed AI stages.
 // Surface the stored error instead of implying every model succeeded.
 for(const [label,part] of [
   ["Speech transcription",a.transcription],
   ["YOLO/BoT-SORT",a.object_tracking],
   ["Qwen2.5-VL",a.visual_reasoning],
   ["Egyptian plate OCR",a.plate_recognition]
 ]){
   if(part?.status==="failed" || part?.status==="unparseable"){
     const error=document.createElement("p");
     error.className="small-center";
     error.style.textAlign="left";
     error.style.color="#f6bc96";
     error.textContent=label+" error: "+(part.note||"Inspect the model runtime logs.");
     stages.append(error);
   }
 }

 const summary=a.visual_reasoning?.observations?.scene_summary;
 if(summary){const p=document.createElement("p");p.className="small-center";p.textContent="Qwen visual assessment (UNVERIFIED): "+summary;stages.append(p)}
 if(a.driver_claim?.verbatim){const p=document.createElement("p");p.className="small-center";p.textContent="Driver's claim: "+a.driver_claim.verbatim;stages.append(p)}
 const candidates=a.violation_assessment?.candidates||[];
 for(const candidate of candidates.slice(0,6)){const p=document.createElement("p");p.className="small-center";p.textContent="Review candidate: "+candidate.category.replaceAll("_"," ")+" — "+candidate.visual_evidence+" at "+(candidate.time_seconds??"?")+"s";stages.append(p)}
 if(a.object_tracking?.tracks?.length){const p=document.createElement("p");p.className="small-center";p.textContent=a.object_tracking.tracks.length+" provisional tracking IDs across sampled frames. These are NOT necessarily distinct vehicles; IDs can change.";stages.append(p)}
 if(a.plate_recognition?.candidates?.length){const p=document.createElement("p");p.className="small-center";p.textContent=a.plate_recognition.candidates.length+" plate OCR candidate readings; none verified.";stages.append(p)}
 if(x.status==="failed"){const note=document.createElement("p");note.className="small-center";note.textContent=x.error||"Processing failed";const retry=document.createElement("button");retry.className="button mini";retry.textContent="Retry analysis ↻";retry.onclick=async()=>{try{await api("/incidents/"+x.id+"/reanalyze",{method:"POST"});toast("Reanalysis queued");await refresh()}catch(e){toast(e.message)}};stages.append(note,retry)}
}
async function selectIncident(x,scroll=true){
 if(!x)return;selected=x;showAnalysis(x);clearMedia();if(scroll)el("studio").scrollIntoView({behavior:"smooth"});
 if(x.status!=="ready")return;
 try{const res=await api("/incidents/"+x.id+"/thumbnail");if(selected.id!==x.id)return;mediaUrl=URL.createObjectURL(await res.blob());const img=document.createElement("img");img.src=mediaUrl;img.alt="Actual frame extracted from uploaded footage";const chip=document.createElement("div");chip.className="image-chip";chip.textContent="SOURCE FRAME AT "+(Number(x.video?.selection?.start_seconds||0)+Number(x.analysis?.evidence?.keyframe_second||0)).toFixed(1)+"s";el("frame").replaceChildren(img,chip)}catch(e){el("frame").textContent="Preview unavailable: "+e.message}
}
async function asset(path,name,videoMode=false){
 if(!selected)return;
 try{const response=await api(path);const blob=await response.blob();if(videoMode){clearMedia();mediaUrl=URL.createObjectURL(blob);const player=document.createElement("video");player.controls=true;player.playsInline=true;player.src=mediaUrl;el("frame").replaceChildren(player);player.play().catch(()=>{})}
 else{const url=URL.createObjectURL(blob);const anchor=document.createElement("a");anchor.href=url;anchor.download=name;document.body.append(anchor);anchor.click();anchor.remove();setTimeout(()=>URL.revokeObjectURL(url),2000)}}catch(e){toast(e.message)}
}
el("play").onclick=()=>{if(selected)asset("/incidents/"+selected.id+"/video",null,true)};
el("pdf").onclick=()=>{if(selected)asset("/incidents/"+selected.id+"/report.pdf","traffic-report-"+selected.id+".pdf")};
el("source").onclick=()=>{if(selected)asset("/incidents/"+selected.id+"/source",selected.filename)};

el("recheck").onclick=async()=>{
 if(!selected || !["ready","failed"].includes(selected.status))return;
 const id=selected.id;
 el("recheck").disabled=true;
 try{
   await api("/incidents/"+id+"/reanalyze",{method:"POST"});
   toast("Analysis requested using current configured models.");
   await refresh();
 }catch(error){toast("Could not restart analysis: "+error.message);el("recheck").disabled=false}
};
