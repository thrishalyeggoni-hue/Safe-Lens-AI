import json,time
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/media-verification.json';cases=[]
with httpx.Client(base_url='http://127.0.0.1:8000',timeout=650) as client:
 for filename,language in [('ordinary.png','en'),('text.png','en'),('otp.mp4','en'),('speech.mp4','en'),('silent.mp4','en'),('short.mp4','en'),('long.mp4','en'),('corrupt.mp4','en'),('unsupported.avi','en'),('hindi.wav','hi'),('telugu.wav','te'),('mixed.wav','mixed'),('english.mp3','en'),('english.m4a','en'),('compressed.mp4','en'),('injection.mp4','en'),('silent.webm','en'),('silent.mov','en')]:
  start=time.monotonic();path=ROOT/'tests/media-fixtures'/filename
  with path.open('rb') as f:r=client.post('/api/check/media',files={'file':(filename,f)},data={'language':language})
  result=r.json();cases.append({'filename':filename,'language':language,'http_status':r.status_code,'elapsed_seconds':round(time.monotonic()-start,2),'result':result});OUT.write_text(json.dumps({'notice':'Actual controlled uploads, synthetic local TTS used to test speech extraction, not detector evaluation; no fabricated model results.','cases':cases},ensure_ascii=False,indent=2))
  print(filename,r.status_code,result.get('risk_category'),result.get('transcript',{}).get('status'),result.get('transcript',{}).get('text'),flush=True)
