"""Single-worker dashboard using the original-video Ultralytics tracker."""
import asyncio
import hashlib
import hmac
from contextlib import asynccontextmanager
import base64
import math
import os
import secrets
import tempfile
import threading
import time
from pathlib import Path
from typing import Annotated

import cv2
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from ultralytics import YOLO
from ultralytics.utils import DEFAULT_CFG

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = Path(os.environ.get('MODEL_PATH', str(Path.home() / 'Downloads/best (1).pt'))).expanduser()
TOKEN = os.environ.get('ITMS_TOKEN') or secrets.token_urlsafe(32)
PUBLIC_URL = os.environ.get('RENDER_EXTERNAL_URL', os.environ.get('PUBLIC_BASE_URL', '')).rstrip('/')
MAX_UPLOAD = 100 * 1024**2
IDLE_SECONDS = 300
DEVICE = os.environ.get('ITMS_DEVICE', 'cpu')
model = YOLO(str(MODEL_PATH))
VEHICLE_LABELS = {'bicycle','car','motorcycle','bus','truck','two_wheeler','autorickshaw','bus_truck'}
vehicle_classes = {i:name for i,name in model.names.items() if name in VEHICLE_LABELS}
origins = [PUBLIC_URL,'http://127.0.0.1:8765','http://localhost:8765',*filter(None,os.environ.get('ITMS_ORIGINS','').split(','))]
lock = threading.Lock()
state = {'id':None,'iterator':None,'path':None,'tracks':{},'index':0,'fps':0,'frames':0,'complete':False,'owner':None,'touched':0,'uploading':False}
@asynccontextmanager
async def lifespan(app):
    async def cleanup():
        while True:
            await asyncio.sleep(30)
            await run_in_threadpool(expire_source)
    task = asyncio.create_task(cleanup())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    with lock:
        release_source()

app = FastAPI(title='TrafficFlow original-video YOLO inference', lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=['GET','POST'],allow_headers=['Authorization','Content-Type','X-Session'])

def visitor_cookie():
    value = secrets.token_urlsafe(24) + '.' + str(int(time.time()))
    signature = hmac.new(TOKEN.encode(), value.encode(), hashlib.sha256).hexdigest()
    return value + '.' + signature

def auth(request, value=None):
    origin = request.headers.get('origin')
    if origin and origin not in origins:
        raise HTTPException(403, 'Origin not allowed.')
    cookie = request.cookies.get('itms_session', '')
    try:
        visitor, issued, signature = cookie.split('.')
        expected = hmac.new(TOKEN.encode(), (visitor+'.'+issued).encode(), hashlib.sha256).hexdigest()
        if not secrets.compare_digest(signature, expected) or not 0 <= time.time()-int(issued) < 86400:
            raise ValueError()
        return visitor
    except (ValueError, TypeError):
        raise HTTPException(401, 'Refresh the dashboard to reconnect.')

@app.get('/healthz')
def healthz():
    return {'ready': True}

@app.middleware('http')
async def prevent_stale_dashboard(request: Request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.post('/api/start')
@app.post('/api/infer')
def outdated_dashboard():
    raise HTTPException(409, 'This tab is using an older dashboard. Refresh this page, then upload your video.')

@app.get('/api/health')
def health(request:Request,authorization:Annotated[str|None,Header()]=None):
    auth(request,authorization)
    return {'model':MODEL_PATH.name,'classes':vehicle_classes,'device':DEVICE,'ready':True,
            'pipeline':{'confidence':.30,'iou':.45,'tracker':DEFAULT_CFG.tracker,'imgsz':640,'vid_stride':1,'source':'original video'}}

def release_source():
    iterator=state.get('iterator')
    if iterator is not None:
        iterator.close()
        state['iterator']=None
    predictor=model.predictor
    if predictor is not None:
        capture=getattr(getattr(predictor,'dataset',None),'cap',None)
        if capture is not None: capture.release()
    path=state.get('path')
    if path is not None:
        Path(path).unlink(missing_ok=True)
        state['path']=None

def expire_source():
    with lock:
        if not state['uploading'] and state['owner'] and time.monotonic()-state['touched'] > IDLE_SECONDS:
            release_source()
            state.update(owner=None, id=None, tracks={})

def begin(path, owner):
    probe=cv2.VideoCapture(str(path))
    try:
        fps=probe.get(cv2.CAP_PROP_FPS)
        frames=int(probe.get(cv2.CAP_PROP_FRAME_COUNT))
        width=int(probe.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(probe.get(cv2.CAP_PROP_FRAME_HEIGHT))
        ok,_=probe.read()
        if not ok or not math.isfinite(fps) or fps<=0 or frames<=0:
            raise HTTPException(400,'The video cannot be decoded. Try an H.264 MP4 file.')
    finally:
        probe.release()
    with lock:
        release_source()
        # Fresh predictor and tracker for each new video.
        model.predictor=None
        session=secrets.token_urlsafe(16)
        iterator=model.track(source=str(path),stream=True,conf=.30,iou=.45,
                             imgsz=640,vid_stride=1,device=DEVICE,save=False,verbose=False)
        state.update(owner=owner,touched=time.monotonic(),id=session,iterator=iterator,path=path,tracks={},index=0,fps=fps,frames=frames,complete=False)
        return {'session':session,'fps':fps,'frames':frames,'width':width,'height':height,'duration':frames/fps}

@app.post('/api/video')
async def upload(request:Request,authorization:Annotated[str|None,Header()]=None):
    owner = auth(request,authorization)
    await run_in_threadpool(expire_source)
    with lock:
        if state['uploading'] or (state['owner'] not in (None,owner) and not state['complete']):
            raise HTTPException(429, 'Another video is being analyzed. Please try again shortly.')
        state.update(owner=owner, uploading=True, touched=time.monotonic())
    # Reserve the single analysis slot before accepting a temporary video.
    path=None
    try:
        fd,name=tempfile.mkstemp(prefix='trafficflow-',suffix='.mp4')
        path=Path(name)
        size=0
        with os.fdopen(fd,'wb') as f:
            async for chunk in limited_stream(request):
                size+=len(chunk)
                if size>MAX_UPLOAD: raise HTTPException(413,'Please use a video smaller than 100 MB.')
                f.write(chunk)
        if not size: raise HTTPException(400,'The uploaded video is empty.')
        return await run_in_threadpool(begin,path,owner)
    except BaseException:
        if path is not None: path.unlink(missing_ok=True)
        with lock:
            release_source()
            state.update(owner=None,id=None)
        raise
    finally:
        with lock:
            state['uploading']=False
            state['touched']=time.monotonic()

async def limited_stream(request):
    async with asyncio.timeout(120):
        async for chunk in request.stream():
            yield chunk

def next_frame(session, owner):
    with lock:
        if not session or session!=state['id'] or owner!=state['owner'] or state['uploading']:
            raise HTTPException(409,'This video session has ended. Upload your video again.')
        state['touched']=time.monotonic()
        if state['complete']:
            return {'complete':True,'frames_processed':state['index']}
        try:
            started=time.perf_counter()
            result=next(state['iterator'])
        except StopIteration:
            state['complete']=True
            release_source()
            return {'complete':True,'frames_processed':state['index']}
        except Exception:
            state['complete']=True
            release_source()
            raise HTTPException(500,'The model could not process this video. Please upload it again.')
        h,w=result.orig_shape
        detections=[]
        for box in result.boxes:
            cls=int(box.cls[0])
            # Run inference on all classes like Kaggle, but count road vehicles only.
            if cls not in vehicle_classes: continue
            track=int(box.id[0]) if box.id is not None else None
            x1,y1,x2,y2=box.xyxy[0].tolist()
            if track is not None: state['tracks'].setdefault(track,model.names[cls])
            detections.append({'box':[x1/w,y1/h,x2/w,y2/h],'class':model.names[cls],
                               'confidence':round(float(box.conf[0]),3),'id':track})
        index=state['index'];state['index']+=1
        counts={name:0 for name in vehicle_classes.values()}
        for name in state['tracks'].values(): counts[name]+=1
        # Display encoding occurs AFTER detection, so it cannot affect inference.
        ok,jpeg=cv2.imencode('.jpg',result.orig_img,[cv2.IMWRITE_JPEG_QUALITY,85])
        if not ok: raise HTTPException(500,'Unable to display the processed frame.')
        return {'complete':False,'detections':detections,'unique':len(state['tracks']),'unique_by_class':counts,
                'timestamp':index/state['fps'],'frame':index,'fps':state['fps'],'frames':state['frames'],
                'inference_ms':round((time.perf_counter()-started)*1000,1),
                'image':'data:image/jpeg;base64,'+base64.b64encode(jpeg).decode('ascii')}

@app.post('/api/next')
async def next_result(request:Request,authorization:Annotated[str|None,Header()]=None,
                      x_session:Annotated[str|None,Header()]=None):
    owner=auth(request,authorization)
    return await run_in_threadpool(next_frame,x_session,owner)

@app.post('/api/cancel')
async def cancel(request:Request, x_session:Annotated[str|None,Header()]=None):
    owner=auth(request)
    def stop():
        with lock:
            if x_session and owner==state['owner'] and x_session==state['id'] and not state['uploading']:
                release_source()
                state.update(owner=None,id=None,tracks={},complete=True)
        return {'released':True}
    return await run_in_threadpool(stop)

@app.get('/')
def dashboard(request:Request):
    response=FileResponse(ROOT/'dist'/'index.html')
    try:
        auth(request)
    except HTTPException:
        response.set_cookie('itms_session',visitor_cookie(),httponly=True,samesite='strict',
                            secure=PUBLIC_URL.startswith('https://'),max_age=86400)
    response.headers['Cache-Control']='no-store'
    return response

app.mount('/',StaticFiles(directory=ROOT/'dist',html=True),name='dashboard')
if __name__=='__main__':
    import uvicorn
    print('\nTrafficFlow ready. Open http://127.0.0.1:8765/ and upload your video.\n',flush=True)
    uvicorn.run(app,host=os.environ.get('HOST','127.0.0.1'),port=int(os.environ.get('PORT','8765')),log_level='warning')
