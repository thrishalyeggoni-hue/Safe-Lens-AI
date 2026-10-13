"""Real, bounded QR decoding. Parsed identities are self-declared."""
import asyncio
from importlib.metadata import version, PackageNotFoundError
import json
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlsplit, parse_qsl, unquote
from .screenshot_image import decode_image
from .url_service import analyze_link
from .message_service import analyze_message

QR_LOCK=asyncio.Lock()
MAX_CODES=32
MAX_PAYLOAD=12000


def capability():
    try: binding=version('zxing-cpp')
    except PackageNotFoundError: binding=None
    return {'engine':'ZXing-C++','binding':'zxing-cpp','version':binding,'available':bool(binding),'decode_timeout_seconds':15,'max_codes':MAX_CODES,'max_payload_characters':MAX_PAYLOAD,'formats':['QR_CODE'],'multiple_codes':True}


def escaped_fields(text,delimiter=';'):
    # Escape-aware WIFI/MECARD grammar; values never enter logs/history.
    fields=[]; current=''; escaped=False
    for char in text:
        if escaped: current+=char; escaped=False
        elif char=='\\': escaped=True
        elif char==delimiter: fields.append(current); current=''
        else: current+=char
    if escaped: current+='\\'
    fields.append(current)
    result={}
    for field in fields:
        if ':' in field:
            key,value=field.split(':',1); result.setdefault(key.upper(),[]).append(value)
    return result


def classify_qr_payload(raw):
    text=raw.strip(); lower=text.lower(); fields={}; urls=[]; errors=[]
    kind='PLAIN_TEXT'
    if lower.startswith(('http://','https://')):
        kind='URL'; urls=[text]; fields={'original_url':text}
    elif lower.startswith('upi:'):
        kind='UPI_PAYMENT'
        parsed=urlsplit(text)
        pairs=parse_qsl(parsed.query,keep_blank_values=True,max_num_fields=100)
        params={}
        for k,v in pairs: params.setdefault(k,[]).append(v)
        fields={'parameters':params,'unknown_parameters':{k:v for k,v in params.items() if k not in ('pa','pn','am','cu','tn','tr')},'identity_verified':False}
        for key,label in [('pa','payee_address'),('pn','payee_name'),('am','amount'),('cu','currency'),('tn','transaction_note'),('tr','transaction_reference')]:
            fields[label]=params.get(key,[])
        if parsed.scheme.lower()!='upi' or parsed.netloc.lower()!='pay' or parsed.path not in ('','/') or not params.get('pa') or not all(params['pa']): errors.append('Unsupported or incomplete UPI payment URI')
        if any(len(v)>1 for v in params.values()): errors.append('Repeated payment parameters require independent review')
        if params.get('am') and not all(re.fullmatch(r'\d+(?:\.\d{1,2})?',v) and float(v)>0 for v in params['am']): errors.append('Invalid or nonpositive amount')
    elif text.upper().startswith('WIFI:'):
        kind='WIFI_CONFIG'; params=escaped_fields(text[5:])
        fields={'ssid':params.get('S',[]),'authentication':params.get('T',[]),'hidden':params.get('H',[]),'password':params.get('P',[]),'temporary_credentials':True,'identity_verified':False}
        if not params.get('S'): errors.append('SSID is missing')
    elif text.upper().startswith(('BEGIN:VCARD','MECARD:')):
        kind='CONTACT'; params={}
        if text.upper().startswith('MECARD:'): params=escaped_fields(text[7:])
        else:
            unfolded=re.sub(r'\r?\n[ \t]','',text)
            for line in unfolded.splitlines():
                if ':' in line:
                    key,value=line.split(':',1); key=key.split(';',1)[0].upper(); params.setdefault(key,[]).append(value)
            if 'END:VCARD' not in text.upper(): errors.append('Incomplete vCard')
        fields={'name':params.get('FN',params.get('N',[])),'phone':params.get('TEL',[]),'email':params.get('EMAIL',[]),'organization':params.get('ORG',[]),'url':params.get('URL',[]),'identity_verified':False}
        urls=[v for v in fields['url'] if v.lower().startswith(('http://','https://'))]
        if len(urls)!=len(fields['url']): errors.append('Unsupported contact URL scheme')
    elif lower.startswith(('tel:','mailto:','sms:','smsto:')):
        kind='PHONE' if lower.startswith('tel:') else 'EMAIL' if lower.startswith('mailto:') else 'SMS'
        scheme,rest=text.split(':',1)
        fields={'scheme':scheme.lower(),'value':unquote(rest),'identity_verified':False}
    elif re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',text):
        kind='UNSUPPORTED_STRUCTURED'; fields={'scheme':text.split(':',1)[0]}; errors.append('Unsupported structured payment payload' if lower.startswith(('bitcoin:','ethereum:','lightning:','pay:')) else 'Unsupported structured payload')
    return {'type':kind,'parsed_fields':fields,'urls':urls,'parse_warnings':errors}


async def decode_real(image):
    info=capability()
    if not info['available']: return {**info,'status':'unavailable','codes':[],'error':'ZXing-C++ binding is unavailable'}
    async with QR_LOCK:
        with tempfile.TemporaryDirectory(prefix='safelens-qr-') as folder:
            src=Path(folder)/'image.png'; out=Path(folder)/'result.json'; image.save(src)
            process=await asyncio.create_subprocess_exec(sys.executable,'-m','backend.app.services.qr_worker',str(src),str(out),cwd=str(Path(__file__).resolve().parents[3]),stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
            try:
                await asyncio.wait_for(process.wait(),15)
                if not out.exists() or out.stat().st_size>2*1024*1024: raise ValueError('Invalid decoder output')
                result=json.loads(out.read_text())
                if result.get('error'): raise ValueError('Decoder failed')
                if len(result['codes'])>MAX_CODES: raise ValueError('Too many QR codes')
                return {**info,'status':'completed','codes':result['codes']}
            except TimeoutError: return {**info,'status':'unavailable','codes':[],'error':'Unable to decode QR within time limit'}
            except (OSError,ValueError,KeyError,TypeError): return {**info,'status':'unavailable','codes':[],'error':'Unable to decode QR'}
            finally:
                if process.returncode is None: process.kill(); await process.wait()


async def analyze_qr_bytes(raw,filename,on_stage=None):
    def stage(value):
        if on_stage: on_stage(value)
    stage('Validating image')
    image,metadata=await asyncio.to_thread(decode_image,raw,filename)
    try:
        stage('Detecting and decoding QR codes · ZXing-C++')
        decoded=await decode_real(image)
    finally: image.close()
    codes=[]; findings=[]; evidence=[]; unavailable=[]; checks=[{'name':'Content-validated image','status':'passed','detail':metadata['validated_format']},{'name':'Real QR decoding','status':'passed' if decoded['codes'] else 'inconclusive','detail':f"{len(decoded['codes'])} readable QR codes; {decoded['status']}"}]
    stage('Classifying actual decoded payloads')
    url_cache={}
    for index,code in enumerate(decoded['codes'],1):
        item={**code,'id':index,'source':'QR decoder observation','link_results':[],'message_result':None}
        if len(code['payload'])>MAX_PAYLOAD:
            classification={'type':'UNSUPPORTED_STRUCTURED','parsed_fields':{},'urls':[],'parse_warnings':['Decoded payload exceeds the analysis length limit']}
        else:
            try: classification=classify_qr_payload(code['payload'])
            except (ValueError,OverflowError): classification={'type':'UNSUPPORTED_STRUCTURED','parsed_fields':{},'urls':[],'parse_warnings':['Malformed structured payload']}
        item.update(classification)
        risks=[]
        for url in classification['urls'][:8]:
            stage(f'Checking destination · QR {index} · existing Link Check')
            if url not in url_cache:
                try: url_cache[url]=await analyze_link(url)
                except Exception as exc: url_cache[url]={'risk_category':'Unable to Assess','explanation':f'Destination check unavailable ({type(exc).__name__})','findings':[],'checks_performed':[],'unavailable_checks':[{'name':'Link Check','status':'unavailable','detail':'Malformed or unavailable destination'}]}
            result=url_cache[url]; item['link_results'].append({'original_url':url,'result':result}); risks.append(result['risk_category'])
            findings.extend([{**f,'source':f"Link Check · QR {index} · {f.get('source','')}",'qr_id':index} for f in result.get('findings',[])])
            checks.extend([{**c,'name':f"QR {index} Link · {c['name']}"} for c in result.get('checks_performed',[])])
            unavailable.extend([{**c,'name':f"QR {index} Link · {c['name']}"} for c in result.get('unavailable_checks',[])])
        if len(classification['urls'])>8: classification['parse_warnings'].append('Only the first eight contact URLs were checked')
        if classification['type']=='PLAIN_TEXT' and code['payload'].strip() and len(code['payload'])<=MAX_PAYLOAD:
            stage(f'Reviewing decoded text · QR {index} · existing Message Check')
            item['message_result']=await analyze_message(code['payload'])
            result=item['message_result']; risks.append(result['risk_category'])
            findings.extend([{**f,'source':f"Message Check · QR {index} · {f.get('source','')}",'qr_id':index} for f in result.get('findings',[])])
            unavailable.extend(result.get('unavailable_checks',[])); checks.extend(result.get('checks_performed',[]))
        if classification['type']=='UPI_PAYMENT':
            risks.append('Caution' if classification['parse_warnings'] else 'Unable to Assess')
            unavailable.append({'name':f'QR {index} payment ownership','status':'unavailable','detail':'Payment parameters are self-declared. Payee ownership, legitimacy and authorization are not verified.'})
        elif classification['type'] in ('CONTACT','WIFI_CONFIG','PHONE','EMAIL','SMS'):
            risks.append('Unable to Assess'); unavailable.append({'name':f'QR {index} identity/network verification','status':'unavailable','detail':'Parsed contact details or network credentials are self-declared and unverified.'})
        if classification['parse_warnings']:
            risks.append('Unable to Assess'); unavailable.append({'name':f'QR {index} structured parsing','status':'unavailable','detail':'; '.join(classification['parse_warnings'])})
        item['risk_category']='High Risk' if 'High Risk' in risks else 'Caution' if 'Caution' in risks else 'Unable to Assess' if not risks or 'Unable to Assess' in risks else 'Low Risk'
        codes.append(item)
        evidence.append({'snippet':code['payload'],'source_type':'qr','detail':f"Actual ZXing-C++ decoded payload · QR {index} · {classification['type']}"})
        checks.append({'name':f'QR {index} payload classification','status':'inconclusive' if classification['parse_warnings'] else 'passed','detail':classification['type']})
    stage('Combining observed evidence')
    risks=[c['risk_category'] for c in codes]
    risk='High Risk' if 'High Risk' in risks else 'Caution' if 'Caution' in risks else 'Unable to Assess' if not risks or 'Unable to Assess' in risks else 'Low Risk'
    explanation=decoded.get('error','No readable QR code found') if not codes else f"Decoded {len(codes)} actual QR code(s). Decoding establishes readability only; review each payload and the external checks. Self-declared identities and payment authorization remain unverified."
    return {'module_type':'qr','input_summary':'QR content not retained','original_filename':metadata['original_filename'],'image':metadata,'decoder':{k:v for k,v in decoded.items() if k!='codes'},'qr_count':len(codes),'codes':codes,'risk_category':risk,'explanation':explanation,'score':None,'findings':findings,'evidence':evidence,'checks_performed':checks,'unavailable_checks':unavailable,'recommended_actions':['Review the original decoded payload before acting.','Verify the source and payee independently.','No destination, payment, contact or Wi-Fi action is executed automatically.'],'provider_info':{'engine':'ZXing-C++ QR orchestration','raw_content_retained':False}}


async def analyze_qr_image(image_path,original_filename):
    return await analyze_qr_bytes(Path(image_path).read_bytes(),original_filename)
