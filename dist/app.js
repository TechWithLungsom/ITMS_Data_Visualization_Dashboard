'use strict';
const $=id=>document.getElementById(id),v=$('video'),canvas=$('overlay'),ctx=canvas.getContext('2d'),capture=document.createElement('canvas');
const S={ready:false,classes:[],names:[],session:null,generation:0,running:false,busy:false,done:false,time:0,last:-1,url:null,result:null,rows:[],samples:[],observedTypes:new Set(),file:''};
const labels={two_wheeler:'Two-wheelers',autorickshaw:'Auto-rickshaws',car:'Cars',bus_truck:'Buses & trucks',bicycle:'Bicycles',motorcycle:'Motorcycles',bus:'Buses',truck:'Trucks'};
const symbols={two_wheeler:'◉',autorickshaw:'◇',car:'▰',bus_truck:'▤',bicycle:'◉',motorcycle:'◉',bus:'▤',truck:'▤'};
const pretty=name=>labels[name]||name.replaceAll('_',' ');
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const time=t=>`${String(Math.floor(t/60)).padStart(2,'0')}:${String(Math.floor(t%60)).padStart(2,'0')}`;
function notify(message,error=false){$('notice').textContent=message;$('notice').classList.toggle('error',error);}
async function api(path,options={}){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),300000);try{const r=await fetch(path,{...options,credentials:'same-origin',signal:controller.signal});if(r.status===405)throw Error('The dashboard and service versions do not match. Restart TrafficFlow and refresh this page.');const data=await r.json();if(!r.ok){const error=Error(typeof data.detail==='string'?data.detail:'The analysis service could not complete this request.');error.status=r.status;throw error;}return data;}finally{clearTimeout(timer);}}
function renderTypes(counts={}){const current={};for(const d of S.result?.detections||[])current[d.class]=(current[d.class]||0)+1;$('types').innerHTML=S.names.map(name=>`<div class="type-row"><span class="vehicle-symbol">${symbols[name]||'◈'}</span><div><strong>${esc(pretty(name))}</strong><small>${current[name]||0} in view now</small></div><b>${counts[name]||((S.observedTypes?.has(name))?'—':0)}</b></div>`).join('')||'<div class="type-empty">Vehicle categories appear when the model is ready.</div>';}
async function connect(){try{const d=await api('/api/health');S.names=Object.values(d.classes);S.classes=Object.keys(d.classes).map(Number);S.ready=true;$('connection').textContent=`${d.model} · ready`;$('connectionDot').classList.add('ready');renderTypes();return true;}catch(e){S.ready=false;$('connection').textContent='Service unavailable';notify('The analysis service is unavailable. Please refresh this page shortly.',true);return false;}}
function releaseSession(session){if(session)fetch('/api/cancel',{method:'POST',headers:{'X-Session':session},credentials:'same-origin',keepalive:true}).catch(()=>{});}
window.addEventListener('pagehide',()=>releaseSession(S.session));
function reset(){releaseSession(S.session);S.session=null;S.duration=0;S.done=false;S.time=0;S.last=-1;S.result=null;S.rows=[];S.samples=[];S.observedTypes=new Set();$('totalSub').textContent='Estimated unique vehicles in this video';$('total').textContent='—';$('typeCount').textContent='—';$('density').textContent='—';$('green').textContent='—';$('inView').textContent='—';$('densitySub').textContent='Based on vehicles visible in the video';$('greenSub').textContent='Updates with the visible traffic load';$('summary').textContent='Analyzing your video…';$('progress').style.width='0';$('export').disabled=true;ctx.clearRect(0,0,canvas.width,canvas.height);renderTypes();}
function draw(detections){ctx.clearRect(0,0,canvas.width,canvas.height);const w=canvas.width,h=canvas.height;for(const d of detections){let [a,b,c,e]=d.box;ctx.strokeStyle='#b5ee83';ctx.lineWidth=Math.max(2,w/600);ctx.strokeRect(a*w,b*h,(c-a)*w,(e-b)*h);const label=pretty(d.class);ctx.font=`600 ${Math.max(12,w/85)}px sans-serif`;const tw=ctx.measureText(label).width;const y=Math.max(22,b*h);ctx.fillStyle='#b5ee83';ctx.fillRect(a*w,y-22,tw+12,22);ctx.fillStyle='#183018';ctx.fillText(label,a*w+6,y-6);}}
function update(d){S.result=d;S.last=d.timestamp;S.time=d.timestamp;const counts=d.unique_by_class||{};S.samples.push({time:d.timestamp,count:d.detections.length});S.samples=S.samples.filter(x=>x.time>=d.timestamp-10);const insight=TrafficInsights.summarize(S.samples);for(const box of d.detections)S.observedTypes.add(box.class);const types=S.observedTypes.size;$('total').textContent=d.unique|| (types?'—':0);$('totalSub').textContent=!d.unique&&types?'Detected vehicles await confirmed tracking IDs':'Estimated unique vehicles in this video';$('typeCount').textContent=types;$('inView').textContent=d.detections.length;$('density').textContent=insight.density;$('densitySub').textContent=`${insight.average.toFixed(1)} vehicles in view on average · last 10s`;$('green').innerHTML=`${insight.green} <small>sec</small>`;$('greenSub').textContent='Suggested duration · traffic-load estimate';$('time').textContent=`${time(S.time)} / ${time((S.duration||v.duration))}`;$('progress').style.width=`${S.time/(S.duration||v.duration)*100}%`;$('progressLabel').textContent=`${Math.min(99,Math.floor(S.time/(S.duration||v.duration)*100))}% analyzed`;$('summary').textContent=insight.average===0?'No vehicles detected in the recent video frames.':`${insight.density} traffic load, with about ${insight.average.toFixed(1)} vehicles visible on average. Suggested green time: ${insight.green} seconds.`;renderTypes(counts);draw(d.detections);S.rows.push({time:d.timestamp,total:d.unique,current:d.detections.length,counts:{...counts},types,...insight});$('export').disabled=false;}
async function showFrame(data,gen){
 const frame=$('processed');frame.src=data.image;
 await frame.decode();
 if(gen!==S.generation)return;
 v.style.display='none';frame.style.display='block';update(data);
}
async function run(){
 if(S.busy||S.done)return;
 if(!S.ready&&!(await connect()))return;
 S.running=true;S.busy=true;const gen=S.generation;
 $('play').disabled=false;$('play').textContent='Ⅱ Pause';$('mode').textContent='ANALYZING';
 try{
  if(!S.session){
   notify('Preparing the original video for full-frame analysis…');
   let d;
   while(gen===S.generation){
    try{d=await api('/api/video',{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:S.fileObject});break;}
    catch(e){if(e.status!==429)throw e;notify('Another video is finishing. Your video will start automatically when the server is available.');$('mode').textContent='WAITING';await new Promise(r=>setTimeout(r,3000));}
   }
   if(gen!==S.generation){if(d)releaseSession(d.session);return;}
   $('mode').textContent='ANALYZING';
   S.session=d.session;S.fps=d.fps;S.duration=d.duration;
   canvas.width=d.width;canvas.height=d.height;$('stage').style.aspectRatio=`${d.width}/${d.height}`;
   notify('Analyzing every original frame with the Kaggle confidence and overlap settings.');
  }
  while(S.running&&gen===S.generation){
   const started=performance.now();
   const d=await api('/api/next',{method:'POST',headers:{'X-Session':S.session}});
   if(gen!==S.generation)break;
   if(d.complete){
    S.done=true;S.running=false;$('mode').textContent='COMPLETE';$('play').textContent='✓ Complete';$('play').disabled=true;
    $('progress').style.width='100%';$('progressLabel').textContent=`${d.frames_processed} frames analyzed`;
    $('time').textContent=`${time(S.duration)} / ${time(S.duration)}`;
    $('windowNote').textContent='Density and timing describe the final 10 seconds. Vehicle totals cover the entire video.';
    notify('Analysis complete. Every decoded video frame was analyzed. Your results are ready.');break;
   }
   await showFrame(d,gen);
   await new Promise(r=>setTimeout(r,Math.max(0,1000/S.fps-(performance.now()-started))));
  }
 }catch(e){
  if(gen===S.generation){S.running=false;releaseSession(S.session);S.session=null;S.done=true;$('mode').textContent='STOPPED';$('play').disabled=true;notify(`Analysis stopped: ${e.message} Upload the video again to retry.`,true);}
 }finally{
  if(gen===S.generation){S.busy=false;if(!S.done){$('play').disabled=false;$('play').textContent=S.running?'Ⅱ Pause':'▶ Resume';if(!S.running)$('mode').textContent='PAUSED';}}
 }
}
async function load(file){if(!file)return;if(file.size>100*1024**2){notify('Please choose a video smaller than 100 MB.',true);return;}if(!file.type.startsWith('video/')){notify('Please choose a video file.',true);return;}S.generation++;S.running=false;S.busy=false;if(S.url)URL.revokeObjectURL(S.url);reset();S.file=file.name;S.fileObject=file;$('processed').style.display='none';S.url=URL.createObjectURL(file);v.src=S.url;v.style.display='block';$('empty').hidden=true;$('empty').style.display='none';$('fileName').textContent=file.name;$('mode').textContent='LOADING';$('play').disabled=true;$('windowNote').textContent='Density and timing use the most recent 10 seconds of video.';notify('Video received. Analysis will start automatically.');}
v.addEventListener('loadeddata',()=>{canvas.width=v.videoWidth;canvas.height=v.videoHeight;$('stage').style.aspectRatio=`${v.videoWidth}/${v.videoHeight}`;if(!Number.isFinite((S.duration||v.duration))||(S.duration||v.duration)<=0){notify('Please upload a video with a readable duration.',true);return;}run();});v.addEventListener('error',()=>{S.running=false;S.generation++;$('mode').textContent='UNSUPPORTED';$('play').disabled=true;notify('This browser cannot play that video. Try an H.264 MP4 or WebM.',true);});
$('play').onclick=()=>{if(S.running){S.running=false;$('play').disabled=true;$('play').textContent='Pausing…';}else run();};
for(const id of ['upload','choose'])$(id).onclick=()=>{$('file').value='';$('file').click();};$('file').onchange=e=>load(e.target.files[0]);$('stage').ondragover=e=>e.preventDefault();$('stage').ondrop=e=>{e.preventDefault();load(e.dataTransfer.files[0]);};
$('export').onclick=()=>{const q=x=>'"'+String(x).replaceAll('"','""')+'"';const rows=[['video_seconds','estimated_unique_vehicles','vehicles_in_view','types_captured',...S.names.map(pretty),'average_visible_vehicles_last_10s','density_estimate','suggested_green_seconds'],...S.rows.map(r=>[r.time.toFixed(2),r.total,r.current,r.types,...S.names.map(n=>r.counts[n]||0),r.average.toFixed(2),r.density,r.green])];const url=URL.createObjectURL(new Blob([rows.map(r=>r.map(q).join(',')).join('\n')],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='TrafficFlow-report.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
connect();
