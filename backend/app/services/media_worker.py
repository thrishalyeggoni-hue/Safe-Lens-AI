"""Bounded, fixed-argument local decoding and CPU Whisper worker. No downloads."""
import argparse,hashlib,json,math,os,re,resource,shutil,subprocess,wave
from pathlib import Path
import io
from fractions import Fraction
from PIL import Image,ImageOps


def run(args,timeout=20):
    p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    if len(p.stdout)>2*1024*1024 or len(p.stderr)>2*1024*1024:raise ValueError('Decoder output limit')
    if p.returncode:raise ValueError('Decoder failed')
    return p


def decode(path,folder):
    raw=path.read_bytes();frames=[]
    if raw.startswith((b'\x89PNG\r\n\x1a\n',b'\xff\xd8\xff')) or raw[:4]==b'RIFF' and raw[8:12]==b'WEBP':
        with Image.open(io.BytesIO(raw)) as image:
            fmt=image.format;w,h=image.size
            if fmt not in ('PNG','JPEG','WEBP') or getattr(image,'n_frames',1)!=1 or min(w,h)<16 or max(w,h)>6000 or w*h>12000000:raise ValueError('Image dimension/format limit')
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            exif={str(k):str(v)[:500] for k,v in image.getexif().items() if k in (271,272,274,305,306,36867)}
            oriented=ImageOps.exif_transpose(image)
            if oriented.mode in ('RGBA','LA') or 'transparency' in oriented.info:
                rgba=oriented.convert('RGBA');im=Image.new('RGB',rgba.size,'white');im.paste(rgba,mask=rgba.getchannel('A'))
            else:im=oriented.convert('RGB')
            original_width,original_height=im.size;im.thumbnail((1600,1600));im.save(folder/'frame_001.png')
        return {'media_type':'image','container':fmt,'duration_seconds':None,'width':original_width,'height':original_height,'ocr_coordinate_space':'EXIF-oriented image fitted inside 1600x1600; frame dimensions identify polygon coordinates','metadata':exif,'streams':[], 'frames':[{'frame_id':'frame_001','timestamp_seconds':None,'frame_number':None,'file':'frame_001.png','width':im.width,'height':im.height}], 'audio':{'status':'not_applicable'},'sampling_policy':'Actual image, EXIF orientation applied; no authenticity inference'}
    # Only bounded supported local containers; network/playlist files never enter a demuxer.
    container=(raw[4:8]==b'ftyp' and len(raw)>12) or raw.startswith((b'RIFF',b'\x1aE\xdf\xa3',b'ID3',b'\xff\xfb',b'\xff\xf3',b'\xff\xf2',b'\xff\xf1',b'\xff\xf9'))
    if not container:raise ValueError('Unsupported media signature')
    probe=run([shutil.which('ffprobe'),'-v','error','-protocol_whitelist','file,pipe','-max_alloc','67108864','-probesize','5000000','-analyzeduration','5000000','-show_entries','format=format_name,duration,start_time,bit_rate:format_tags=creation_time,encoder:stream=index,codec_type,codec_name,width,height,avg_frame_rate,sample_rate,channels,start_time,duration:stream_tags=creation_time,encoder','-of','json',str(path)],10)
    metadata=json.loads(probe.stdout)
    fmt=metadata.get('format',{}).get('format_name','')
    if not any(c in fmt.split(',') for c in ('mov','mp4','matroska','webm','wav','mp3','aac')):raise ValueError('Unsupported container')
    streams=metadata.get('streams',[])
    videos=[s for s in streams if s.get('codec_type')=='video'];audios=[s for s in streams if s.get('codec_type')=='audio']
    if len(videos)>1 or len(audios)>1 or not (videos or audios):raise ValueError('Only one video and one audio stream supported')
    if any(s.get('codec_name') not in ('h264','hevc','vp8','vp9','av1','mpeg4','aac','mp3','opus','vorbis','pcm_s16le','pcm_s24le','pcm_s32le','pcm_f32le') for s in videos+audios):raise ValueError('Unsupported codec')
    duration=float(metadata.get('format',{}).get('duration') or max(float(s.get('duration') or 0) for s in streams))
    if not math.isfinite(duration) or not 0<duration<=120:raise ValueError('Duration must be positive and at most 120 seconds')
    v=videos[0] if videos else {};w=v.get('width');h=v.get('height')
    if videos and (not w or not h or max(w,h)>4096 or w*h>8294400):raise ValueError('Video resolution limit')
    ff=shutil.which('ffmpeg');base=[ff,'-nostdin','-hide_banner','-y','-max_alloc','67108864','-protocol_whitelist','file,pipe','-threads','1','-filter_threads','1']
    if videos:
        video_duration=min(duration,float(v.get('duration') or duration))
        fps=float(Fraction(v.get('avg_frame_rate') or '0/1'))
        if not math.isfinite(fps) or fps<=0 or fps>120:raise ValueError('Frame rate unsupported or unavailable')
        last=max(0,round(video_duration-1/fps-.001,6))
        times=sorted(set([0,round(video_duration/2,3),last])) if video_duration>.2 else [0]
        for index,t in enumerate(times):
            filename=f'frame_{index+1:03d}.png'
            try:
                p=run(base+['-copyts','-ss',str(t),'-i',str(path),'-map','0:v:0','-an','-vf',"scale='min(1280,iw)':-2,showinfo",'-frames:v','1','-threads','1',str(folder/filename)],20)
                pts=re.findall(rb'pts_time:([\d.eE+\-]+)',p.stderr)
                if not pts or not (folder/filename).is_file():raise ValueError('No decoded frame timestamp')
                with Image.open(folder/filename) as im:fw,fh=im.size
                timestamp=float(pts[0])-float(metadata.get('format',{}).get('start_time') or 0)
                frames.append({'frame_id':f'frame_{index+1:03d}','requested_timestamp_seconds':t,'timestamp_seconds':max(0,round(timestamp,6)),'frame_number':None,'file':filename,'width':fw,'height':fh})
            except (ValueError,subprocess.TimeoutExpired):
                frames.append({'frame_id':f'frame_{index+1:03d}','requested_timestamp_seconds':t,'status':'failed','error':'Frame could not be decoded with bounded resources'})
    audio={'status':'absent'}
    if audios:
        run(base+['-v','error','-i',str(path),'-map','0:a:0','-vn','-t','60','-ac','1','-ar','16000','-c:a','pcm_s16le','-threads','1',str(folder/'audio.wav')],25)
        with wave.open(str(folder/'audio.wav')) as wav:
            samples=wav.readframes(wav.getnframes());seconds=wav.getnframes()/wav.getframerate()
        import numpy as np
        data=np.frombuffer(samples,dtype='<i2').astype('float32')/32768
        rms=float(np.sqrt(np.mean(data**2))) if data.size else 0
        audio={'status':'extracted','file':'audio.wav','timeline_origin_seconds':max(0,float(audios[0].get('start_time') or 0)-float(metadata.get('format',{}).get('start_time') or 0)),'duration_seconds':seconds,'sample_rate':16000,'channels':1,'rms':rms,'silent_at_threshold':rms<.0001,'silence_threshold_rms':.0001,'coverage':'first 60 seconds maximum; audio presence does not establish speech'}
    return {'media_type':'video' if videos else 'audio','container':metadata.get('format',{}).get('format_name'),'duration_seconds':duration,'width':w,'height':h,'metadata':metadata,'streams':streams,'frames':frames,'audio':audio,'sampling_policy':'Beginning, midpoint and last-frame interval computed from video duration/frame rate; actual decoded PTS minus stream start. No scene-change or whole-video visual coverage; absolute frame numbers unavailable.'}


def transcribe(path,checkpoint,language):
    import torch,whisper,numpy as np
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    expected=whisper._MODELS['tiny'].split('/')[-2]
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=expected:raise ValueError('Whisper checkpoint checksum mismatch')
    model=whisper.load_model(str(checkpoint),device='cpu')
    with wave.open(str(path)) as wav:audio=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').astype('float32')/32768
    result=model.transcribe(audio,fp16=False,language=None if language=='mixed' else language,task='transcribe',temperature=0,beam_size=1,best_of=1,condition_on_previous_text=False,verbose=None)
    segments=[{k:s[k] for k in ('id','start','end','text','avg_logprob','no_speech_prob','compression_ratio') if k in s} for s in result['segments']]
    return {'status':'completed','model':'tiny','checkpoint_sha256':expected,'device':'CPU','threads':1,'task':'transcribe','language':result.get('language'),'selected_language':language,'language_accuracy_verified':False,'language_limitation':'Tiny performed poorly in controlled Hindi/Telugu tests; mixed decoding can omit later languages. Inspect original speech.','segments':segments,'text':result.get('text',''),'limitation':'Speech recognition only, not voice authenticity or speaker identity. Tiny multilingual accuracy is limited; inspect original audio.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['decode','transcribe'],required=True);p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--checkpoint');p.add_argument('--language',default='en');a=p.parse_args()
    try:
        resource.setrlimit(resource.RLIMIT_CPU,(120,120))
        data=decode(Path(a.input),Path(a.output).parent) if a.mode=='decode' else transcribe(Path(a.input),Path(a.checkpoint),a.language)
    except Exception as e:data={'status':'failed','error':str(e) if isinstance(e,ValueError) else f'Media worker failed ({type(e).__name__})'}
    Path(a.output).write_text(json.dumps(data,ensure_ascii=False))
