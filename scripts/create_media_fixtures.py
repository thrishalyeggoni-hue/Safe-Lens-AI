"""Author controlled clips from local macOS TTS and existing controlled screenshot images."""
from pathlib import Path
import subprocess,shutil
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'tests/media-fixtures';OUT.mkdir(exist_ok=True)
ff=shutil.which('ffmpeg')
def run(args):subprocess.run([ff,'-v','error','-y','-threads','1','-filter_threads','1',*map(str,args)],check=True)
for name in ['english','hindi','telugu','ordinary','injection']:
 run(['-i',OUT/(name+'.aiff'),'-ac','1','-ar','16000',OUT/(name+'.wav')])
run(['-i',OUT/'english.wav','-i',OUT/'hindi.wav','-i',OUT/'telugu.wav','-filter_complex','[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]','-map','[out]',OUT/'mixed.wav'])
Image.new('RGB',(640,360),(170,210,200)).save(OUT/'ordinary.png')
shutil.copy(ROOT/'tests/screenshot-fixtures/otp.png',OUT/'text.png')
for name,image,audio in [('speech','ordinary.png','ordinary.wav'),('otp','text.png','english.wav'),('payment','text.png','english.wav'),('injection','text.png','injection.wav')]:
 run(['-loop','1','-i',OUT/image,'-i',OUT/audio,'-c:v','libx264','-threads','1','-pix_fmt','yuv420p','-vf','scale=960:-2','-r','5','-c:a','aac','-shortest',OUT/(name+'.mp4')])
for name,duration in [('silent',2),('short',.1),('long',121)]:
 run(['-f','lavfi','-i',f'color=c=green:s=320x240:r=5:d={duration}','-c:v','libx264','-threads','1',OUT/(name+'.mp4')])
run(['-i',OUT/'otp.mp4','-c:v','libx264','-threads','1','-crf','40','-c:a','aac',OUT/'compressed.mp4'])
run(['-f','lavfi','-i','color=c=blue:s=320x240:r=5:d=1','-c:v','ffv1','-threads','1',OUT/'unsupported.avi'])
run(['-i',OUT/'english.wav','-c:a','libmp3lame',OUT/'english.mp3'])
run(['-i',OUT/'english.wav','-c:a','aac',OUT/'english.m4a'])
run(['-i',OUT/'silent.mp4','-c:v','libvpx-vp9','-threads','1',OUT/'silent.webm'])
run(['-i',OUT/'silent.mp4','-c','copy',OUT/'silent.mov'])
(OUT/'corrupt.mp4').write_bytes(b'\x00\x00\x00\x18ftypmp42CORRUPT')
print('Controlled real fixtures created; no application canned media.')
