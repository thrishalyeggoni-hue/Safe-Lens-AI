"""Screenshot extraction and orchestration; real PaddleOCR + existing Message/Link."""
import asyncio
import io
from pathlib import Path
from ..config import settings
from .dns_service import now
from .screenshot_image import decode_image
from .paddle_service import run_paddle
from .screenshot_grounding import valid_regions, merge_reading_order, map_evidence, payment_observations, uncertain_urls
from .message_service import analyze_message


async def decode_qr(image):
    """Independent actual ZXing decoder. It does not generate OCR evidence."""
    try:
        import zxingcpp
        result=zxingcpp.read_barcodes(image)
        return {'status':'completed','source':'ZXing-C++ QR/barcode decoder','payloads':[{'text':r.text,'format':str(r.format),
            'bounding_box':{'points':[[r.position.top_left.x,r.position.top_left.y],[r.position.top_right.x,r.position.top_right.y],
                                     [r.position.bottom_right.x,r.position.bottom_right.y],[r.position.bottom_left.x,r.position.bottom_left.y]]}} for r in result],
            'limitation':'QR payloads are separate from OCR text. No payment ownership verification; QR-only destination safety is not evaluated by this screenshot flow.'}
    except ImportError:
        return {'status':'unavailable','payloads':[],'error':'Local QR decoder is not installed'}
    except Exception as exc:
        return {'status':'unavailable','payloads':[],'error':type(exc).__name__}


async def analyze_screenshot_bytes(raw, filename, language='en', on_stage=None):
    def stage(value):
        if on_stage: on_stage(value)
    stage('Validating actual uploaded image contents and dimensions')
    image,metadata=await asyncio.to_thread(decode_image,raw,filename)
    stage('Preparing image · EXIF orientation and RGB conversion')
    ocr=await run_paddle(image,language,on_stage)
    regions,rejected=valid_regions(ocr['regions'],image.width,image.height)
    text,regions=merge_reading_order(regions)
    url_candidates=uncertain_urls(text,regions)
    ocr.pop('regions',None)
    # Runs contain original actual output but no redundant per-run copies in the response.
    ocr['runs']=[{k:v for k,v in run.items() if k!='regions'} for run in ocr.get('runs',[])]
    ocr.update(region_count=len(regions),rejected_regions=rejected,
               reading_order='Spatial rows ordered top-to-bottom, left-to-right. Adjacent same-line pieces joined with spaces; distant columns separated. Complex chat blocks/columns may be ambiguous.',
               preprocessing_limitation='No blind thresholding or forced rescaling. Arbitrary rotation and layout authenticity are not inferred.')
    if rejected: ocr['status']='partial'
    stage('Extracting grounded text and links from actual OCR regions')
    message=None; error=None; mapped=[]; payments=[]; rejected_findings=0
    if text and len(text)<=settings.MESSAGE_MAX_CHARACTERS:
        def confident_url(url):
            if any(url in item['original_ocr_text'] for item in url_candidates): return False
            starts=[]; pos=0
            while (pos:=text.find(url,pos))>=0:
                item=map_evidence({'text':url,'start':pos,'end':pos+len(url)},text,regions)
                starts.append(bool(item and item['ocr_certainty']=='readable'))
                pos+=len(url)
            return bool(starts) and all(starts)
        stage('Analysing OCR message · reusing real Message Check and Link Check')
        try:
            message=await analyze_message(text,on_stage=on_stage,url_filter=confident_url)
            for item in message['deterministic_findings']+message['ai_interpretations']:
                grounded=map_evidence(item,text,regions)
                if grounded: mapped.append(grounded)
                else: rejected_findings+=1
            for link in message['url_assessments']:
                if link['analysis']['risk_category'] in ('High Risk','Caution'):
                    for occurrence in link['occurrences']:
                        grounded=map_evidence({**occurrence,'source':'external_link_observation','context':'direct_or_uncertain',
                                               'interpretation':link['analysis']['explanation'],'risk_level':link['analysis']['risk_category']},text,regions)
                        if grounded: mapped.append(grounded)
            payments=payment_observations(text,regions,message['extracted_entities'])
        except Exception as exc:
            error=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
    elif text:
        error='OCR text exceeded the Message Check limit; no content was silently truncated'
    else:
        error='Insufficient readable text; OCR absence does not imply safety'
    stage('Checking QR/barcode evidence separately from OCR')
    qr=await decode_qr(image)
    stage('Combining grounded OCR evidence and actual analysis coverage')
    uncertain=[r for r in regions if r.get('confidence') is None or r['confidence']<settings.SCREENSHOT_MIN_CONFIDENCE]
    risk='Unable to Assess'; explanation=error or 'OCR is unavailable or insufficient; screenshot content could not be reliably assessed.'
    if message:
        risk=message['risk_category']; explanation=message['explanation']
        direct=[x for x in mapped if x.get('context')=='direct_or_uncertain']
        authoritative=any(link['analysis'].get('reputation',{}).get('status')=='listed' for link in message['url_assessments'])
        clear_otp=any(x['category']=='credential_request' and x['source']=='deterministic' and x['ocr_certainty']=='readable' for x in direct)
        if risk=='High Risk' and not authoritative and not clear_otp and (not direct or any(x['ocr_certainty']!='readable' for x in direct)):
            risk='Caution'; explanation='Potentially concerning wording was recognized with uncertain OCR; its exact wording needs a clearer screenshot.'
        if risk=='Low Risk' and (ocr['status']!='completed' or uncertain or rejected_findings or qr.get('payloads') or language=='mixed' or url_candidates):
            risk='Unable to Assess'; explanation='Incomplete OCR, mixed-language/layout uncertainty or unevaluated QR content prevents a reliable Low Risk assessment.'
        explanation+=' Screenshot text cannot verify sender identity, payment authenticity or image manipulation.'
    checks=[{'name':'Image content validation','status':'passed','detail':f"{metadata['validated_format']} · {image.width}×{image.height} pixels"},
            {'name':'PaddleOCR','status':'passed' if ocr['status']=='completed' and regions else 'inconclusive','detail':f"{len(regions)} real regions; {len(uncertain)} uncertain regions"},
            {'name':'OCR evidence grounding','status':'passed' if not rejected_findings else 'inconclusive','detail':f'{len(mapped)} mapped findings; {rejected_findings} rejected unsupported findings'},
            {'name':'Independent QR decoding','status':'passed' if qr['status']=='completed' else 'inconclusive','detail':f"{len(qr['payloads'])} actual payload(s); separate evidence source"}]
    unavailable=[]
    if ocr['status']!='completed' or not regions:
        unavailable.append({'name':'OCR coverage','status':'unavailable','detail':ocr.get('error') or 'No readable text regions were recognized'})
    if uncertain: unavailable.append({'name':'OCR readability','status':'unavailable','detail':'Some recognized text is uncertain. Upload a clearer screenshot; confidence values are model output, not a safety percentage.'})
    if url_candidates: unavailable.append({'name':'OCR URL reconstruction','status':'unavailable','detail':'URL-like text is damaged or split across regions. Inferred candidates were recorded but not contacted; verify the original URL manually.'})
    if error: unavailable.append({'name':'Message Check','status':'unavailable','detail':error})
    if message:
        checks.extend(message['checks_performed']); unavailable.extend(message['unavailable_checks'])
    if qr['status']!='completed' or qr['payloads']:
        unavailable.append({'name':'QR destination/payment verification','status':'unavailable','detail':qr.get('error',qr.get('limitation'))})
    findings=[{'source':f"{x['source']} · {x['category']}",'observation':x['text'],
               'interpretation':x.get('interpretation','Observed OCR text')+f" OCR: {x['ocr_certainty']}; context: {x.get('context','unverified')}.",
               'action':x.get('recommended_action','Verify independently; upload a clearer screenshot if uncertain.'),
               'risk_level':x.get('risk_level') or ('Informational' if x.get('context')!='direct_or_uncertain' else 'High Risk' if x['category']=='credential_request' and x['ocr_certainty']=='readable' else 'Caution'),
               'region_ids':x['region_ids'],'bounding_boxes':x['bounding_boxes']} for x in mapped]
    evidence=[{'source_type':x['source'],'snippet':x['text'],'detail':f"{x['category']} · {x['ocr_certainty']}",'region_ids':x['region_ids'],
               'bounding_boxes':x['bounding_boxes'],'ocr_confidences':x['ocr_confidences'],'text_offset':{'start':x['start'],'end':x['end']}} for x in mapped]
    urls=[]
    if message:
        for link in message['url_assessments']:
            occurrences=[map_evidence(item,text,regions) for item in link['occurrences']]
            urls.append({**link,'occurrences':[x for x in occurrences if x]})
    image.close()
    return {'module_type':'screenshot','original_filename':metadata['original_filename'],'input_summary':'Screenshot content not retained',
            'image':metadata,'ocr':ocr,'extracted_text':text,'ocr_regions':regions,'grounded_findings':mapped,
            'url_assessments':urls,'uncertain_url_candidates':url_candidates,'payment_observations':payments,'qr':qr,'message_analysis':message,
            'risk_category':risk,'explanation':explanation,'findings':findings,'evidence':evidence,
            'checks_performed':checks,'unavailable_checks':unavailable,'score':None,'content_saved':False,'checked_at':now(),
            'processing_coverage':{'ocr':ocr['status'],'readable_regions':len(regions)-len(uncertain),'uncertain_regions':len(uncertain),
                                   'message':bool(message),'qr':qr['status'],'image_authenticity':'not verified','rejected_evidence':rejected_findings,
                                   'url_repair':'No inferred domains. URLs split across regions are not silently joined; check them manually.'},
            'recommended_actions':message['recommended_actions'] if message else ['Upload a clear screenshot in the correct language and orientation.','Verify requests independently before paying or sharing credentials.'],
            'provider_info':{'engine':'SafeLens PaddleOCR screenshot orchestration','raw_image_retained':False,'ocr_version':ocr.get('package_version')}}


async def analyze_screenshot(image_path, original_filename, on_stage=None):
    raw=await asyncio.to_thread(Path(image_path).read_bytes)
    return await analyze_screenshot_bytes(raw,original_filename,on_stage=on_stage)
