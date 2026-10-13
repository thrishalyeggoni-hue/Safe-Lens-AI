import asyncio
import io
import json
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
from PIL import Image
from backend.app.services.screenshot_image import decode_image, safe_filename
from backend.app.services.screenshot_grounding import valid_regions, merge_reading_order, map_evidence
from backend.app.services import ocr_service, paddle_service
from backend.app.config import settings
from tests.test_link_api import client


def image_bytes(fmt='PNG', size=(200,100)):
    out=io.BytesIO(); Image.new('RGB',size,'white').save(out,format=fmt); return out.getvalue()


def region(text,score=.99):
    return {'text':text,'confidence':score,'bounding_box':{'points':[[5,5],[190,5],[190,30],[5,30]]},'language_model':'en','model':'test-only'}

@pytest.mark.parametrize('fmt,mime',[('PNG','image/png'),('JPEG','image/jpeg'),('WEBP','image/webp')])
def test_true_content_type_not_filename(fmt,mime):
    image,meta=decode_image(image_bytes(fmt),'../../wrong.exe')
    assert meta['validated_mime']==mime and meta['original_filename']=='wrong.exe'
    assert meta['sha256'] and image.size==(200,100)
    image.close()

@pytest.mark.parametrize('raw',[b'not an image',b'',image_bytes('GIF'),image_bytes(size=(10,100)),image_bytes(size=(6001,20))])
def test_corrupt_unsupported_oversized_images_rejected(raw):
    with pytest.raises(ValueError): decode_image(raw,'image.png')


def test_pixel_limit_and_size_limit(monkeypatch):
    monkeypatch.setattr(settings,'SCREENSHOT_MAX_PIXELS',100)
    with pytest.raises(ValueError): decode_image(image_bytes(),'image.png')
    monkeypatch.setattr(settings,'SCREENSHOT_MAX_BYTES',10)
    with pytest.raises(ValueError): decode_image(image_bytes(),'image.png')


def test_exif_coordinates_match_oriented_preview():
    image=Image.new('RGB',(300,100),'white'); exif=Image.Exif();exif[274]=6
    out=io.BytesIO();image.save(out,format='JPEG',exif=exif)
    decoded,meta=decode_image(out.getvalue(),'rotation.jpg')
    assert decoded.size==(100,300) and meta['exif_orientation']==6
    decoded.close()


def test_exact_region_mapping_and_rejection():
    items=[region('Send me your OTP')]
    items.append({'text':'invented','confidence':1.2,'bounding_box':{'points':[[0,0],[1,0],[1,1],[0,1]]}})
    valid,rejected=valid_regions(items,200,100)
    assert rejected==1
    text,regions=merge_reading_order(valid)
    mapped=map_evidence({'start':0,'end':len(text),'text':text,'category':'credential_request'},text,regions)
    assert mapped['region_ids']==['ocr_1'] and mapped['bounding_boxes']==[items[0]['bounding_box']]
    assert not map_evidence({'start':0,'end':4,'text':'fake'},text,regions)

@pytest.mark.asyncio
@pytest.mark.parametrize('score,risk',[(.99,'High Risk'),(.3,'Caution')])
async def test_ocr_uncertainty_affects_verdict(monkeypatch,score,risk):
    monkeypatch.setattr(ocr_service,'run_paddle',AsyncMock(return_value={'status':'completed','regions':[region('Send me your OTP now.',score)],'runs':[],'package_version':'test-only'}))
    monkeypatch.setattr(settings,'MESSAGE_AI_ENABLED',False)
    result=await ocr_service.analyze_screenshot_bytes(image_bytes(),'test.png')
    assert result['risk_category']==risk
    assert result['grounded_findings'][0]['ocr_confidences']==[score]
    assert result['score'] is None

@pytest.mark.asyncio
async def test_unavailable_ocr_never_invents_text(monkeypatch):
    monkeypatch.setattr(ocr_service,'run_paddle',AsyncMock(return_value={'status':'unavailable','regions':[],'runs':[],'error':'Test missing engine'}))
    result=await ocr_service.analyze_screenshot_bytes(image_bytes(),'test.png')
    assert result['risk_category']=='Unable to Assess' and result['extracted_text']==''
    assert result['grounded_findings']==[] and result['message_analysis'] is None

@pytest.mark.asyncio
async def test_uncertain_url_is_not_contacted(monkeypatch):
    monkeypatch.setattr(ocr_service,'run_paddle',AsyncMock(return_value={'status':'completed','regions':[region('Visit https://example.com',.3)],'runs':[]}))
    from backend.app.services import message_service
    check=AsyncMock()
    monkeypatch.setattr(message_service,'analyze_link',check)
    monkeypatch.setattr(settings,'MESSAGE_AI_ENABLED',False)
    result=await ocr_service.analyze_screenshot_bytes(image_bytes(),'test.png')
    assert check.await_count==0
    assert result['url_assessments'][0]['analysis']['risk_category']=='Unable to Assess'
    assert result['risk_category']!='Low Risk'


def test_upload_endpoint_content_validation_and_private_history(client,monkeypatch):
    monkeypatch.setattr(ocr_service,'run_paddle',AsyncMock(return_value={'status':'unavailable','regions':[],'runs':[],'error':'Test missing engine'}))
    response=client.post('/api/check/screenshot',files={'file':('../../secret-password.png',image_bytes(),'text/plain')})
    assert response.status_code==200 and response.headers['cache-control']=='no-store'
    result=response.json()
    assert result['image']['validated_mime']=='image/png' and result['original_filename']=='secret-password.png'
    assert result['risk_category']=='Unable to Assess'
    history=client.get('/api/assessments/'+result['id']).json()
    assert history['content_saved'] is False and history['evidence']==[]
    assert 'secret-password' not in json.dumps(history) and 'ocr_regions' not in history
    client.cookies.set('safelens_session','another-session-value',domain='testserver.local',path='/')
    assert client.get('/api/assessments/'+result['id']).status_code==403


def test_upload_errors_and_limits(client):
    assert client.post('/api/check/screenshot',files={'file':('broken.png',b'bad','image/png')}).status_code==422
    assert client.post('/api/check/screenshot',files={'file':('wrong.gif',image_bytes('GIF'),'image/png')}).status_code==422
    assert client.post('/api/check/screenshot',files={'file':('ok.png',image_bytes(),'image/png')},data={'language':'unsupported'}).status_code==422
    assert client.post('/api/check/screenshot',content=b'x',headers={'content-length':str(11*1024*1024),'content-type':'multipart/form-data; boundary=x'}).status_code==413


def test_real_stream_stages(client,monkeypatch):
    monkeypatch.setattr(ocr_service,'run_paddle',AsyncMock(return_value={'status':'unavailable','regions':[],'runs':[],'error':'Test: unavailable'}))
    response=client.post('/api/check/screenshot?stream=true',files={'file':('image.png',image_bytes(),'image/png')})
    events=[json.loads(line) for line in response.text.splitlines()]
    assert events[0]['stage'].startswith('Upload received') and events[-1]['type']=='result'
    assert events[-1]['data']['risk_category']=='Unable to Assess'
    assert not any('percent' in json.dumps(event).lower() for event in events)

@pytest.mark.asyncio
async def test_worker_is_killed_and_tempfile_cleaned_on_cancel(monkeypatch):
    monkeypatch.setattr(paddle_service,'capability',lambda:{'package_version':'test','runtime_version':'test','detector_available':True,'languages':{'en':{'available':True}}})
    started=asyncio.Event()
    class Process:
        returncode=None
        killed=False
        async def wait(self):
            if not self.killed: await asyncio.Future()
            self.returncode=-9
        def kill(self): self.killed=True
    process=Process(); paths=[]
    async def create(*args,**kwargs):
        paths.append(Path(args[args.index('--input')+1]));started.set();return process
    monkeypatch.setattr(asyncio,'create_subprocess_exec',create)
    image=Image.new('RGB',(100,100),'white')
    task=asyncio.create_task(paddle_service.run_paddle(image,'en'))
    await started.wait();task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    assert process.killed and not paths[0].exists()


def test_damaged_and_split_url_candidates_are_explicit_and_uncontacted():
    from backend.app.services.screenshot_grounding import uncertain_urls
    text,regions=merge_reading_order([region('Visit https:/example.com',.99)])
    candidate=uncertain_urls(text,regions)[0]
    assert candidate['original_ocr_text']=='https:/example.com'
    assert candidate['normalized_candidate']=='https://example.com'
    assert candidate['status']=='not_contacted' and candidate['region_ids']==['ocr_1']
    top=region('https://exam'); bottom=region('ple.com')
    bottom['bounding_box']['points']=[[5,35],[190,35],[190,60],[5,60]]
    text,regions=merge_reading_order([top,bottom])
    candidate=uncertain_urls(text,regions)[0]
    assert candidate['normalized_candidate']=='https://example.com' and candidate['region_ids']==['ocr_1','ocr_2']


def test_actual_recorded_multilingual_ocr_regressions():
    path=Path('docs/screenshot-ocr-verification.json')
    if not path.exists(): pytest.skip('Run the explicit real OCR verification script first')
    cases=json.loads(path.read_text())['cases']
    for name,quote in [('hindi','अपना ओटीपी भेजें'),('telugu','మీ ఓటీపీ పంపండి'),('mixed','Never share your OTP.')]:
        assert quote in cases[name]['reconstructed_text']
        assert all(region['model'].endswith('_rec') for region in cases[name]['ocr_regions'])
    assert not cases['blurred']['ocr_regions'] and not cases['no_text']['ocr_regions']
    assert cases['warning']['message_analysis']['risk_category']!='High Risk'
    assert cases['injection']['message_analysis']['risk_category']=='High Risk'


def test_same_line_fragments_keep_spatial_order_and_exact_box_mapping():
    right=region('OTP.')
    right['bounding_box']['points']=[[120,5],[190,5],[190,30],[120,30]]
    left=region('Share your')
    left['bounding_box']['points']=[[5,7],[115,7],[115,28],[5,28]]
    text,regions=merge_reading_order([right,left])
    assert text=='Share your OTP.'
    mapped=map_evidence({'text':text,'start':0,'end':len(text)},text,regions)
    assert mapped['region_ids']==['ocr_1','ocr_2']
    assert mapped['bounding_boxes']==[left['bounding_box'],right['bounding_box']]

@pytest.mark.asyncio
async def test_independent_real_qr_payload_is_not_ocr_text():
    import cv2
    matrix=cv2.QRCodeEncoder_create().encode('upi://pay?pa=test@okhdfcbank&am=2500')
    image=Image.fromarray(matrix).resize((400,400),Image.Resampling.NEAREST)
    decoded=await ocr_service.decode_qr(image)
    assert decoded['status']=='completed'
    assert decoded['payloads'][0]['text']=='upi://pay?pa=test@okhdfcbank&am=2500'
    assert decoded['source']=='ZXing-C++ QR/barcode decoder'
    assert len(decoded['payloads'][0]['bounding_box']['points'])==4
