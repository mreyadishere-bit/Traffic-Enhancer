"use strict";
// Operator key lives in memory only. This is a single-operator dev MVP.
const el=id=>document.getElementById(id);
let key="",items=[],selected=null,mediaUrl=null,currentFile=null,poll=null,toastTimer=null;
const date=s=>s?new Date(s).toLocaleString():"—";
const mb=n=>(Number(n)/1024/1024).toFixed(1)+" MB";
el("today").textContent=new Date().toLocaleDateString("en-US",{month:"short",day:"2-digit",year:"numeric"}).toUpperCase();
function toast(message){el("toast").textContent=message;el("toast").classList.add("show");clearTimeout(toastTimer);toastTimer=setTimeout(()=>el("toast").classList.remove("show"),5000)}
async function api(path,opts={}){
 const res=await fetch("/api/v1"+path,{...opts,headers:{Authorization:"Bearer "+key,...(opts.headers||{})}});
 if(!res.ok){let msg="Request failed ("+res.status+")";try{let x=await res.json();if(typeof x.detail==="string")msg=x.detail}catch{}throw Error(msg)}
 return res;
}
el("loginForm").addEventListener("submit",async e=>{
 e.preventDefault();key=el("key").value;el("loginError").textContent="";
 try{const r=await api("/incidents");items=(await r.json()).items;el("overlay").classList.add("hidden");el("key").value="";render();refreshLoop()}catch(error){key="";el("loginError").textContent=error.message}
});
el("disconnect").addEventListener("click",()=>{key="";items=[];selected=null;if(poll)clearInterval(poll);clearMedia();render();el("overlay").classList.remove("hidden")});
function refreshLoop(){if(poll)clearInterval(poll);poll=setInterval(()=>{if(items.some(x=>["queued","processing"].includes(x.status)))refresh()},3000)}
async function refresh(){if(!key)return;try{items=(await(await api("/incidents")).json()).items;if(selected){selected=items.find(x=>x.id===selected.id)||selected;showAnalysis(selected)}render()}catch(e){toast("Refresh failed: "+e.message)}}
el("refresh").addEventListener("click",refresh);
el("newIncident").addEventListener("click",()=>{el("studio").scrollIntoView({behavior:"smooth"});el("video").click()});
const drop=el("drop"),upload=el("video");
drop.addEventListener("click",()=>upload.click());
drop.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();upload.click()}});
["dragenter","dragover"].forEach(t=>drop.addEventListener(t,e=>{e.preventDefault();drop.classList.add("over")}));
["dragleave","drop"].forEach(t=>drop.addEventListener(t,e=>{e.preventDefault();drop.classList.remove("over")}));
drop.addEventListener("drop",e=>{if(e.dataTransfer.files[0])choose(e.dataTransfer.files[0])});
upload.addEventListener("change",()=>{if(upload.files[0])choose(upload.files[0])});
function choose(file){const ext=file.name.split(".").pop().toLowerCase();if(!["mp4","mov","mkv"].includes(ext)){toast("Supported formats: MP4, MOV, MKV");return}if(file.size>150*1024*1024){toast("Video exceeds 150 MB");return}currentFile=file;el("filename").textContent=file.name;el("upload").disabled=false;el("uploadStatus").textContent=mb(file.size)+" · Ready to upload"}
el("upload").addEventListener("click",()=>{
 if(!currentFile||!key)return;
 const xhr=new XMLHttpRequest();xhr.open("POST","/api/v1/incidents");xhr.setRequestHeader("Authorization","Bearer "+key);
 const data=new FormData();data.append("video",currentFile,currentFile.name);
 el("upload").disabled=true;el("progress").hidden=false;el("progressBar").style.width="0%";el("uploadStatus").textContent="Uploading original footage…";
 xhr.upload.onprogress=e=>{if(e.lengthComputable)el("progressBar").style.width=Math.round(100*e.loaded/e.total)+"%"};
 xhr.onload=async()=>{
  let body={};try{body=JSON.parse(xhr.responseText)}catch{}
  if(xhr.status===202){
   toast("Original evidence accepted and hashed.");
   currentFile=null;upload.value="";el("filename").textContent="Drop dashcam footage here";
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
 el("selected").textContent=x.id.slice(0,12).toUpperCase()+" / "+x.status.toUpperCase();
 el("play").disabled=x.status!=="ready";el("pdf").disabled=x.status!=="ready";
 const a=x.analysis||{}, stages=el("stages");stages.replaceChildren(
   stateRow("VEHICLE DETECTION",a.vehicle_detection?.status||x.status),
   stateRow("SPEECH TRANSCRIPTION",a.transcription?.status||x.status),
   stateRow("VIOLATION ASSESSMENT",a.violation_assessment?.status||"not_implemented")
 );
 if(a.vehicle_detection?.detections?.length)stages.append(stateRow("VEHICLES IN ONE FRAME",String(a.vehicle_detection.detections.length)));
 const extras = [
  ["QWEN2.5-VL VIDEO ANALYSIS",a.visual_reasoning?.status||"not_configured"],
  ["VEHICLE TRACKING",a.object_tracking?.status||"not_configured"],
  ["EGYPTIAN PLATE OCR",a.plate_recognition?.status||"not_configured"],
  ["DRIVER VOICE DESCRIPTION",a.driver_claim?.status||"unavailable"],
  ["TARGET VEHICLE MATCH",a.target_matching?.status||"unavailable"]
 ];
 extras.forEach(pair=>stages.append(stateRow(pair[0],pair[1])));
 const summary=a.visual_reasoning?.observations?.scene_summary;
 if(summary){const p=document.createElement("p");p.className="small-center";p.textContent="Qwen visual assessment (UNVERIFIED): "+summary;stages.append(p)}
 if(a.driver_claim?.verbatim){const p=document.createElement("p");p.className="small-center";p.textContent="Driver's claim: "+a.driver_claim.verbatim;stages.append(p)}
 const candidates=a.violation_assessment?.candidates||[];
 for(const candidate of candidates.slice(0,6)){const p=document.createElement("p");p.className="small-center";p.textContent="Review candidate: "+candidate.category.replaceAll("_"," ")+" — "+candidate.visual_evidence+" at "+(candidate.time_seconds??"?")+"s";stages.append(p)}
 if(a.object_tracking?.tracks?.length){const p=document.createElement("p");p.className="small-center";p.textContent=a.object_tracking.tracks.length+" provisional vehicle track IDs. Identity not established.";stages.append(p)}
 if(a.plate_recognition?.candidates?.length){const p=document.createElement("p");p.className="small-center";p.textContent=a.plate_recognition.candidates.length+" plate OCR candidate readings; none verified.";stages.append(p)}
 if(x.status==="failed"){const note=document.createElement("p");note.className="small-center";note.textContent=x.error||"Processing failed";const retry=document.createElement("button");retry.className="button mini";retry.textContent="Retry analysis ↻";retry.onclick=async()=>{try{await api("/incidents/"+x.id+"/reanalyze",{method:"POST"});toast("Reanalysis queued");await refresh()}catch(e){toast(e.message)}};stages.append(note,retry)}
}
async function selectIncident(x){
 if(!x)return;selected=x;showAnalysis(x);clearMedia();el("studio").scrollIntoView({behavior:"smooth"});
 if(x.status!=="ready")return;
 try{const res=await api("/incidents/"+x.id+"/thumbnail");if(selected.id!==x.id)return;mediaUrl=URL.createObjectURL(await res.blob());const img=document.createElement("img");img.src=mediaUrl;img.alt="Actual frame extracted from uploaded footage";const chip=document.createElement("div");chip.className="image-chip";chip.textContent="ORIGINAL FRAME AT "+(x.analysis?.evidence?.keyframe_second??"—")+"s";el("frame").replaceChildren(img,chip)}catch(e){el("frame").textContent="Preview unavailable: "+e.message}
}
async function asset(path,name,videoMode=false){
 if(!selected)return;
 try{const response=await api(path);const blob=await response.blob();if(videoMode){clearMedia();mediaUrl=URL.createObjectURL(blob);const player=document.createElement("video");player.controls=true;player.playsInline=true;player.src=mediaUrl;el("frame").replaceChildren(player);player.play().catch(()=>{})}
 else{const url=URL.createObjectURL(blob);const anchor=document.createElement("a");anchor.href=url;anchor.download=name;document.body.append(anchor);anchor.click();anchor.remove();setTimeout(()=>URL.revokeObjectURL(url),2000)}}catch(e){toast(e.message)}
}
el("play").onclick=()=>{if(selected)asset("/incidents/"+selected.id+"/video",null,true)};
el("pdf").onclick=()=>{if(selected)asset("/incidents/"+selected.id+"/report.pdf","traffic-report-"+selected.id+".pdf")};
