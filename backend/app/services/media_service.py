"""Real media orchestration; no detector/score substitution."""
import asyncio,hashlib,importlib.util,io,json,os,shutil,sys,tempfile
from pathlib import Path
from PIL import Image
from .ocr_service import analyze_screenshot_bytes
from .message_service import analyze_message
from .screenshot_image import safe_filename

MAX_BYTES=50*1024*1024
MEDIA_LOCK=asyncio.Lock()
CHECKPOINT=Path.home()/'.cache/whisper/tiny.pt'
AUTHENTICITY={'status':'unavailable','assessment':'Unable to Assess','detector':None,'candidate_detector':'DeepfakeBench Xception (not installed/configured)','checkpoint':None,'required_candidate_checkpoint':'DeepfakeBench training/weights/xception_best.pth (not downloaded)','scope':'Candidate: face manipulation in suitable face crops only','raw_score':None,'calibrated':False,'measured_evaluation':None,'reason':'No configured detector checkpoint, face preprocessing integration or held-out evaluation. Apple M2 has no CUDA; this framework integration has not been validated on MPS/CPU.','audio_authenticity':'unavailable; Whisper does not detect cloned voices','source':'https://github.com/sever46/DeepfakeBench','source_license':'CC BY-NC 4.0; checkpoint/data terms need separate verification'}


def capability():
    return {'ffmpeg_available':bool(shutil.which('ffmpeg')),'ffprobe_available':bool(shutil.which('ffprobe')),'whisper_installed':importlib.util.find_spec('whisper') is not None,'whisper_model':'tiny','checkpoint_available':CHECKPOINT.is_file(),'automatic_downloads':False,'authenticity':AUTHENTICITY,'limits':{'bytes':MAX_BYTES,'duration_seconds':120,'audio_seconds':60,'sampled_frames':3,'job_seconds':600,'threads':1},'languages':['en','hi','te','mixed'],'language_accuracy':'Not comprehensive; real controlled tests reported separately'}


def validate_media(raw,filename):
    if not raw or len(raw)>MAX_BYTES:raise ValueError('Media must be nonempty and at most 50 MiB')
    supported=raw.startswith((b'\x89PNG\r\n\x1a\n',b'\xff\xd8\xff',b'RIFF',b'\x1aE\xdf\xa3',b'ID3',b'\xff\xfb',b'\xff\xf3',b'\xff\xf2',b'\xff\xf1',b'\xff\xf9')) or raw[4:8]==b'ftyp'
    if not supported:raise ValueError('Unsupported media signature; choose PNG/JPEG/WEBP, MP4/MOV/WEBM or WAV/MP3/M4A/AAC')
    return {'original_filename':safe_filename(filename),'file_size_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


async def worker(mode,path,folder,language='en'):
    output=folder/(mode+'.json')
    env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
    args=[sys.executable,'-m','backend.app.services.media_worker','--mode',mode,'--input',str(path),'--output',str(output),'--language',language]
    if mode=='transcribe':args+=['--checkpoint',str(CHECKPOINT)]
    p=await asyncio.create_subprocess_exec(*args,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL,env=env,start_new_session=True)
    try:
        await asyncio.wait_for(p.wait(),150 if mode=='transcribe' else 100)
        if not output.is_file() or output.stat().st_size>4*1024*1024:return {'status':'failed','error':'Worker produced no bounded output'}
        return json.loads(output.read_text())
    except TimeoutError:return {'status':'failed','error':'Media worker timed out'}
    finally:
        if p.returncode is None:
            import signal
            try:os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            await p.wait()


async def analyze_media_bytes(raw,filename,language='en',on_stage=None):
    file=validate_media(raw,filename)
    def stage(s):
        if on_stage:on_stage(s)
    stage('Queued · waiting for one local media job')
    async with MEDIA_LOCK:
      with tempfile.TemporaryDirectory(prefix='safelens-media-') as tmp:
        folder=Path(tmp);path=folder/'upload';path.write_bytes(raw)
        stage('Inspecting metadata · extracting bounded frames/audio · actual FFmpeg')
        decoded=await worker('decode',path,folder)
        findings=[];evidence=[];checks=[];unavailable=[];frames=[];frame_cache={};transcript={'status':'not_applicable','segments':[]}
        checks.append({'name':'Content signature and size validation','status':'passed','detail':f'{len(raw)} actual bytes; SHA-256 matched upload'})
        if decoded.get('status')=='failed':
            unavailable.append({'name':'Media decoding','status':'failed','detail':decoded['error']})
        else:
            file.update(validated_type=decoded['media_type'],container=decoded['container'])
            checks.append({'name':'Actual FFmpeg/Pillow decoding','status':'passed','detail':f"{decoded['media_type']} · {decoded['container']}"})
            for frame in decoded.get('frames',[]):
                if not frame.get('file'):
                    frames.append(frame);unavailable.append({'name':frame['frame_id'],'status':'failed','detail':frame['error']});continue
                stage(f"Running OCR · {frame['frame_id']} · actual extracted image")
                frame_bytes=(folder/frame['file']).read_bytes();frame_hash=hashlib.sha256(frame_bytes).hexdigest();reused=frame_hash in frame_cache
                if reused:result=frame_cache[frame_hash]
                else:
                    result=await analyze_screenshot_bytes(frame_bytes,frame['frame_id']+'.png',language,on_stage=on_stage);frame_cache[frame_hash]=result
                context={'frame_id':frame['frame_id'],'timestamp_seconds':frame['timestamp_seconds'],'text_source':'ocr'}
                frames.append({**{k:v for k,v in frame.items() if k!='file'},'decoded_frame_sha256':frame_hash,'ocr_reused_identical_frame':reused,'ocr':result['ocr'],'text':result['extracted_text'],'ocr_regions':result['ocr_regions'],'message_analysis':result['message_analysis'],'url_assessments':result['url_assessments'],'risk_category':result['risk_category']})
                findings.extend({**f,**context} for f in result['findings']);evidence.extend({**e,**context} for e in result['evidence'])
                checks.extend({**c,'name':frame['frame_id']+' · '+c['name']} for c in result['checks_performed'])
                unavailable.extend({**c,'name':frame['frame_id']+' · '+c['name']} for c in result['unavailable_checks'])
            audio=decoded.get('audio',{})
            if audio.get('status')=='extracted':
                stage('Extracted audio · actual 16 kHz mono WAV')
                if audio['silent_at_threshold']:transcript={'status':'silent_at_threshold','segments':[],'limitation':'Measured RMS below threshold; does not prove absence of quiet speech'}
                elif not capability()['whisper_installed'] or not CHECKPOINT.is_file():
                    transcript={'status':'unavailable','segments':[],'error':'Whisper tiny package or cached checkpoint missing; uploads do not download models'}
                else:
                    stage('Transcribing speech · real Whisper tiny · CPU one thread')
                    transcript=await worker('transcribe',folder/'audio.wav',folder,language)
                    transcript.setdefault('segments',[])
                    segments=transcript['segments']
                    for s in segments:
                        if isinstance(s.get('start'),(int,float)) and isinstance(s.get('end'),(int,float)):
                            s['audio_relative_start']=s['start'];s['audio_relative_end']=s['end'];s['start']+=audio.get('timeline_origin_seconds',0);s['end']+=audio.get('timeline_origin_seconds',0)
                    if language!='en':unavailable.append({'name':'Speech language accuracy','status':'inconclusive','detail':'Whisper tiny Hindi/Telugu/mixed controlled tests showed poor accuracy; uncertain transcription is not a verified request or URL.'})
                    if len(segments)>40:
                        transcript['segments']=segments[:40];transcript['coverage_limited']=True
                        unavailable.append({'name':'Transcript content coverage','status':'partial','detail':'First 40 segments analysed'})
                    for segment in transcript['segments']:
                        text=segment.get('text','');start=segment.get('start');end=segment.get('end')
                        if not isinstance(start,(float,int)) or not isinstance(end,(float,int)) or not 0<=start<end<=audio['duration_seconds']+audio.get('timeline_origin_seconds',0)+.5:continue
                        uncertain=language!='en' or segment.get('avg_logprob',-2)<-1 or segment.get('no_speech_prob',1)>.6
                        segment['uncertain']=uncertain
                        if not text.strip():continue
                        stage('Analysing transcript · shared Message/Link Check')
                        result=await analyze_message(text,on_stage=on_stage,url_filter=(lambda _:False) if uncertain else None)
                        segment['message_analysis']=result
                        for item in result['deterministic_findings']+result['ai_interpretations']:
                            if text[item['start']:item['end']]!=item['text']:continue
                            risk='Informational' if item.get('context')!='direct_or_uncertain' else 'High Risk' if item['category']=='credential_request' and not uncertain else 'Caution'
                            context={'timestamp_seconds':start,'start_seconds':start,'end_seconds':end,'segment_id':segment['id'],'text_offset':{'start':item['start'],'end':item['end']},'text_source':'whisper_transcript','uncertain_transcription':uncertain}
                            findings.append({'source':'Whisper transcript · '+item['category'],'observation':item['text'],'interpretation':item['interpretation']+' Speech recognition is not voice authenticity.','risk_level':risk,'action':'Verify the request independently.',**context})
                            evidence.append({'source_type':'whisper_transcript','snippet':item['text'],**context})
                        for link in result['url_assessments']:
                            if link['analysis']['risk_category'] in ('High Risk','Caution'):
                                findings.append({'source':'Transcript Link Check','observation':link['url'],'interpretation':link['analysis']['explanation'],'risk_level':link['analysis']['risk_category'],'start_seconds':start,'end_seconds':end,'timestamp_seconds':start,'action':'Verify the destination independently.'})
                        checks.extend({**c,'name':f"Speech {start:.2f}s · "+c['name']} for c in result['checks_performed']);unavailable.extend(result['unavailable_checks'])
                if transcript['status']!='completed' or not transcript['segments']:
                    unavailable.append({'name':'Speech transcription coverage','status':'inconclusive','detail':transcript.get('error',transcript.get('limitation','No speech segments recognised'))})
                if decoded['duration_seconds']>audio['duration_seconds']+.5:unavailable.append({'name':'Audio coverage','status':'partial','detail':'Only first 60 seconds extracted and transcribed'})
        stage('Authenticity capability check · no configured detector')
        unavailable.append({'name':'Deepfake authenticity analysis','status':'unavailable','detail':AUTHENTICITY['reason']})
        risk='High Risk' if any(f['risk_level']=='High Risk' for f in findings) else 'Caution' if any(f['risk_level']=='Caution' for f in findings) else 'Unable to Assess'
        stage('Combining actual evidence and limitations')
        urls=[{'source':'ocr','frame_id':f['frame_id'],'timestamp_seconds':f.get('timestamp_seconds'),**u} for f in frames for u in f.get('url_assessments',[])]+[{'source':'transcript','start_seconds':s.get('start'),'end_seconds':s.get('end'),**u} for s in transcript['segments'] for u in s.get('message_analysis',{}).get('url_assessments',[])]
        public_decoded={k:v for k,v in decoded.items() if k not in ('frames','audio')}
        audio={k:v for k,v in decoded.get('audio',{}).items() if k!='file'}
        return {'module_type':'media','input_summary':'Media content not retained','file':file,'media':public_decoded,'frames':frames,'audio_extraction':audio,'transcript':transcript,'url_assessments':urls,'authenticity':AUTHENTICITY,'content_risk':risk,'risk_category':risk,'score':None,'explanation':f'Content risk: {risk}. Authenticity: Unable to Assess. Sampled visual coverage and speech recognition do not establish authenticity.','findings':findings,'evidence':evidence,'checks_performed':checks,'unavailable_checks':unavailable,'coverage':{'frames_sampled':len(frames),'actual_ocr_executions':len(frame_cache),'frames_ocr_completed':sum(f.get('ocr',{}).get('status')=='completed' for f in frames),'total_duration_seconds':decoded.get('duration_seconds'),'audio_seconds_extracted':audio.get('duration_seconds'),'whole_video_visual_analysis':False,'analysis_complete':False},'recommended_actions':['Review original media at the evidence timestamps.','Never share credentials or pay solely because a clip requests it.','Verify provenance independently; authenticity analysis is unavailable.'],'provider_info':{'engine':'SafeLens real bounded Media Check','raw_content_retained':False,'capabilities':capability()}}


async def analyze_media(file_path,original_filename):
    with open(file_path,'rb') as f:raw=f.read(MAX_BYTES+1)
    return await analyze_media_bytes(raw,original_filename)
