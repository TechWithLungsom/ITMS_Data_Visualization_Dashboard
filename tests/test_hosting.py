"""Public visitor isolation and real-video analysis smoke test."""
import importlib.util
import os
from pathlib import Path
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1]
os.environ['MODEL_PATH']=str(ROOT/'backend/models/best.pt')
os.environ['PUBLIC_BASE_URL']='https://trafficflow.example'
spec=importlib.util.spec_from_file_location('trafficflow',ROOT/'backend/app.py')
app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)

def run(video):
    with TestClient(app.app,base_url='https://trafficflow.example') as a:
        b=TestClient(app.app,base_url='https://trafficflow.example')
        assert a.get('/healthz').status_code==200
        assert a.get('/api/health').status_code==401
        r=a.get('/');assert 'Secure' in r.headers['set-cookie']
        b.get('/')
        assert a.cookies.get('itms_session')!=b.cookies.get('itms_session')
        assert a.get('/api/health').status_code==200
        assert a.get('/api/health',headers={'Origin':'https://evil.example'}).status_code==403
        data=Path(video).read_bytes()
        r=a.post('/api/video',content=data);assert r.status_code==200,r.text
        session=r.json()['session'];path=app.state['path']
        assert b.post('/api/video',content=data).status_code==429
        assert b.post('/api/next',headers={'X-Session':session}).status_code==409
        frames=0
        while True:
            r=a.post('/api/next',headers={'X-Session':session});assert r.status_code==200,r.text
            if r.json()['complete']:break
            frames+=1
        assert frames==30,frames
        assert not path.exists()
        r=b.post('/api/video',content=data);assert r.status_code==200
        path=app.state['path'];app.state['touched']-=301;app.expire_source()
        assert not path.exists() and app.state['owner'] is None
        assert b.post('/api/video',content=b'bad video').status_code==400
        assert app.state['owner'] is None and not app.state['uploading']
        r=a.post('/api/video',content=data);sid=r.json()['session'];path=app.state['path']
        b.post('/api/cancel',headers={'X-Session':sid})
        assert path.exists(), 'Other visitors must not cancel analysis'
        a.post('/api/cancel',headers={'X-Session':sid})
        assert not path.exists() and app.state['owner'] is None
        assert b.post('/api/video',content=data).status_code==200
        print('PASS: owner cancellation releases slot immediately; cross-visitor cancellation denied.')
        assert a.get('/backend/models/best.pt').status_code==404
        print('PASS: signed HTTPS cookies, cross-origin rejection, visitor isolation, busy handling, all 30 original frames, completion and idle cleanup, invalid upload recovery, private model.')
if __name__=='__main__':
    import sys
    run(sys.argv[1])
