"""Real document ingestion, page grounding and existing Link/Message reuse."""
import asyncio
import base64
import hashlib
from importlib.metadata import version,PackageNotFoundError
import io
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
from urllib.parse import urlsplit
import zipfile
from PIL import Image
from ..config import settings
from .screenshot_image import safe_filename
from .document_scan import scan_document
from .paddle_service import run_paddle,capability as ocr_capability
from .screenshot_grounding import valid_regions,merge_reading_order,map_evidence,uncertain_urls
from .message_extraction import URL_REGEX
from .url_service import analyze_link
from .message_service import analyze_message

DOCUMENT_LOCK=asyncio.Lock()
MAX_BYTES=20*1024*1024
MAX_OCR_PAGES=3
MAX_LINKS=16
MAX_CONTENT_BLOCKS=30


def validate_document(raw,filename):
    if not raw or len(raw)>MAX_BYTES: raise ValueError('Document must be nonempty and at most 20 MiB')
    if re.match(rb'%PDF-\d\.\d',raw[:8]): fmt='PDF';mime='application/pdf'
    elif raw.startswith(b'PK\x03\x04'):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zipped:
                items=zipped.infolist(); names=set(zipped.namelist())
                if len(items)>500 or sum(i.file_size for i in items)>32*1024*1024 or any(i.file_size>8*1024*1024 or i.file_size>max(1,i.compress_size)*200 for i in items): raise ValueError('DOCX archive exceeds safe expansion limits')
                if any(i.flag_bits&1 for i in items): raise ValueError('Encrypted DOCX archives are unsupported')
                if not {'[Content_Types].xml','word/document.xml'}.issubset(names): raise ValueError('Unsupported ZIP; upload a real DOCX document')
                content=zipped.read('[Content_Types].xml')
                if b'macroEnabled' in content or any('vbaProject' in name for name in names): raise ValueError('Macro-enabled Office documents are unsupported')
                if b'wordprocessingml.document.main+xml' not in content: raise ValueError('Unsupported Office document type')
        except (zipfile.BadZipFile,OSError,RuntimeError): raise ValueError('DOCX archive could not be safely decoded') from None
        fmt='DOCX';mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    else: raise ValueError('Unsupported document contents; use PDF or DOCX')
    return {'original_filename':safe_filename(filename),'validated_type':fmt,'validated_mime':mime,'file_size_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'authenticity':'Filename, metadata and signatures do not verify issuer identity or document authenticity'}


def capability():
    def installed(name):
        try: return version(name)
        except PackageNotFoundError: return None
    return {'formats':['PDF','DOCX'],'pypdf':installed('pypdf'),'pdfplumber':installed('pdfplumber'),'pypdfium2':installed('pypdfium2'),'python_docx':installed('python-docx'),'clamav_installed':bool(shutil.which('clamscan')),'ocr':ocr_capability(),'limits':{'upload_bytes':MAX_BYTES,'pdf_pages':30,'ocr_pages':MAX_OCR_PAGES,'render_pixels':4_000_000,'rendered_pages_including_preview':3,'parse_seconds':30,'analysis_seconds':300,'urls':MAX_LINKS,'content_blocks':MAX_CONTENT_BLOCKS}}


async def parse_real(path,folder,fmt):
    process=await asyncio.create_subprocess_exec(sys.executable,'-m','backend.app.services.document_worker',str(path),str(folder),fmt,cwd=str(Path(__file__).resolve().parents[3]),stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
    try:
        await asyncio.wait_for(process.wait(),30)
        out=Path(folder)/'parsed.json'
        if not out.exists() or out.stat().st_size>8*1024*1024: raise ValueError('Parser output unavailable or oversized')
        parsed=json.loads(out.read_text())
        if not isinstance(parsed,dict) or not isinstance(parsed.get('pages'),list): raise ValueError('Invalid parser output')
        return parsed
    except (TimeoutError,OSError,ValueError): return {'parse_status':'failed','error':'Document parser failed or reached its time/memory/output limit','pages':[],'links':[],'total_pages':None,'encrypted':False,'metadata':{},'structure_observations':[],'parse_failures':[],'pages_skipped':[]}
    finally:
        if process.returncode is None: process.kill(); await process.wait()


async def analyze_document_bytes(raw,filename,language='en',on_stage=None):
    def stage(value):
        if on_stage: on_stage(value)
    stage('Validating actual document contents')
    metadata=validate_document(raw,filename)
    async with DOCUMENT_LOCK:
        with tempfile.TemporaryDirectory(prefix='safelens-document-') as folder:
            folder=Path(folder);path=folder/('upload.pdf' if metadata['validated_type']=='PDF' else 'upload.docx');path.write_bytes(raw)
            stage('Malware scanning · actual upload · ClamAV')
            malware=await scan_document(path)
            if malware['status']=='infected':
                parsed={'parse_status':'skipped_infected','pages':[],'links':[],'metadata':{},'total_pages':None,'encrypted':None,'structure_observations':[],'pages_skipped':[],'parse_failures':[],'error':'Parsing skipped because ClamAV matched a malware signature'}
            else:
                stage('Parsing document in isolated worker · actual text, annotations and page structure')
                parsed=await parse_real(path,folder,metadata['validated_type'])
            pages=parsed['pages']; findings=[];evidence=[];grounded=[];checks=[];unavailable=[];urls=list(parsed.get('links',[]));ocr_count=0;message_count=0;risks=[]
            stage('Detecting scanned pages and extracting page-linked URLs')
            for page in pages:
                page['ocr']=None;page['message_analysis']=None;page['uncertain_url_candidates']=[]
                render=page.pop('rendered_image',None)
                if render:
                    render_path=folder/render
                    if render_path.is_file() and render_path.stat().st_size<=3*1024*1024:
                        if not any(p.get('preview_png') for p in pages): page['preview_png']='data:image/png;base64,'+base64.b64encode(render_path.read_bytes()).decode()
                if page.get('ocr_needed'):
                    if render and ocr_count<MAX_OCR_PAGES:
                        stage(f"Running real PaddleOCR · {page['reference']} · {language} · CPU one thread")
                        with Image.open(folder/render) as image:
                            ocr=await run_paddle(image,language,on_stage)
                            valid,rejected=valid_regions(ocr['regions'],image.width,image.height)
                        text,regions=merge_reading_order(valid);page.update(text=text,source='ocr',ocr={**ocr,'regions':regions,'rejected_regions':rejected},status='completed' if text and ocr['status']=='completed' else 'unreadable')
                        page['uncertain_url_candidates']=uncertain_urls(text,regions);ocr_count+=1
                    else: page.update(status='unreadable',source='ocr',text='',ocr={'status':'unavailable','error':page.get('render_error','OCR/render limit reached'),'regions':[]})
                text=page['text']
                if not text.strip(): page['status']='unreadable'
                for match in URL_REGEX.finditer(text):
                    value=match.group().rstrip('.,;!?)')
                    occurrence={'page':page.get('page'),'reference':page['reference'],'source':'ocr_visible_url' if page['source']=='ocr' else 'visible_url_text','url':value,'offset':{'start':match.start(),'end':match.start()+len(value)}}
                    if page['source']=='ocr':
                        mapped=map_evidence({'text':value,'start':match.start(),'end':match.start()+len(value)},text,page['ocr']['regions'])
                        occurrence['ocr_evidence']=mapped;occurrence['readable']=bool(mapped and mapped['ocr_certainty']=='readable')
                    else: occurrence['readable']=True
                    urls.append(occurrence)
            url_cache={};url_results=[]
            async def check_url(url):
                if url not in url_cache:
                    if len(url_cache)>=MAX_LINKS: return {'risk_category':'Unable to Assess','explanation':'Document URL limit reached; destination was not contacted','findings':[],'checks_performed':[],'unavailable_checks':[{'name':'Document URL coverage','status':'unavailable','detail':'Only the first 16 distinct destinations are inspected'}]}
                    stage('Checking actual destination · existing protected Link Check')
                    try: url_cache[url]=await analyze_link(url)
                    except Exception as exc: url_cache[url]={'risk_category':'Unable to Assess','explanation':f'Link Check unavailable ({type(exc).__name__})','findings':[],'checks_performed':[],'unavailable_checks':[{'name':'Link Check','status':'unavailable','detail':'Malformed or unsupported destination'}]}
                return url_cache[url]
            for item in urls:
                supported=item['url'].lower().startswith(('http://','https://','www.')) and not item.get('destination_truncated')
                if supported and item.get('readable',True): result=await check_url(item['url'])
                else: result={'risk_category':'Unable to Assess','explanation':'Unsupported destination or uncertain OCR URL; not contacted','findings':[],'checks_performed':[],'unavailable_checks':[{'name':'Document link inspection','status':'unavailable','detail':'Unsupported/truncated destination or uncertain OCR URL'}]}
                url_results.append({**item,'analysis':result});risks.append(result['risk_category'])
                unavailable.extend(result.get('unavailable_checks',[]));checks.extend(result.get('checks_performed',[]))
                for finding in result.get('findings',[]): findings.append({**finding,'page_number':item.get('page'),'reference':item.get('reference',f"Page {item.get('page')}"),'source':f"Document Link Check · {finding.get('source','')}",'url_source':item['source']})
                if item.get('displayed_text'):
                    displayed=URL_REGEX.search(item['displayed_text'])
                    if displayed:
                        try:
                            display_host=urlsplit(displayed.group().rstrip('.,;')).hostname;target_host=urlsplit(item['url']).hostname
                            mismatch=bool(display_host and target_host and display_host.lower()!=target_host.lower())
                        except ValueError: mismatch=False
                        if mismatch:
                            finding={'source':'PDF/DOCX hyperlink structure','observation':f"Displayed {displayed.group()} points to {item['url']}",'interpretation':'Visible and embedded destination domains differ. This is an observation, not proof of fraud.','action':'Verify the embedded destination independently before opening.','risk_level':'Caution','page_number':item.get('page'),'reference':item.get('reference',f"Page {item.get('page')}"),'rectangle_points':item.get('rectangle_points')}
                            findings.append(finding);risks.append('Caution');evidence.append({'source_type':'embedded_link_mismatch','snippet':finding['observation'],'page_number':item.get('page'),'detail':finding['interpretation']})
            for page in pages:
                text=page['text']
                if not text.strip(): continue
                if message_count>=MAX_CONTENT_BLOCKS or len(text)>settings.MESSAGE_MAX_CHARACTERS:
                    page['content_analysis_skipped']='Page/block count or exact text length exceeds Message Check limits';continue
                stage(f"Analysing actual content · {page['reference']} · existing Message Check")
                def readable_url(url):
                    if page['source']!='ocr': return True
                    return any(item['url']==url and item.get('readable') for item in urls if item.get('reference')==page['reference'])
                message=await analyze_message(text,url_filter=readable_url,link_checker=check_url,document_context={'page_number':page.get('page'),'reference':page['reference']})
                message_count+=1;page['message_analysis']=message
                checks.extend([{**c,'name':f"{page['reference']} · {c['name']}"} for c in message['checks_performed']])
                page_grounded=[]
                for item in message['deterministic_findings']+message['ai_interpretations']:
                    start,end=item.get('start'),item.get('end')
                    if not isinstance(start,int) or not isinstance(end,int) or not 0<=start<end<=len(text) or text[start:end]!=item['text']: continue
                    mapped=map_evidence(item,text,page['ocr']['regions']) if page['source']=='ocr' else item
                    if not mapped: continue
                    entry={**mapped,'page_number':page.get('page'),'reference':page['reference'],'text_source':page['source']};page_grounded.append(entry);grounded.append(entry)
                    level='Informational' if item.get('context')!='direct_or_uncertain' else 'High Risk' if item['category']=='credential_request' and item['source']=='deterministic' and entry.get('ocr_certainty','readable')=='readable' else 'Caution'
                    findings.append({'source':f"Document {item['source']} · {item['category']}",'observation':item['text'],'interpretation':item['interpretation'],'action':item.get('recommended_action','Verify the request independently.'),'risk_level':level,'page_number':page.get('page'),'reference':page['reference'],'text_offset':{'start':start,'end':end},'bounding_boxes':entry.get('bounding_boxes')})
                    evidence.append({'source_type':page['source'],'snippet':item['text'],'page_number':page.get('page'),'reference':page['reference'],'text_offset':{'start':start,'end':end},'bounding_boxes':entry.get('bounding_boxes'),'detail':f"Exact grounded page evidence · {item['category']}"})
                risk=message['risk_category']
                if page['source']=='ocr' and any(item.get('ocr_certainty')=='uncertain' for item in page_grounded) and risk=='High Risk': risk='Caution'
                risks.append(risk);unavailable.extend([{**c,'name':f"{page['reference']} · {c['name']}"} for c in message['unavailable_checks']])
                page['content_risk']=risk
                # Document-specific observations keep exact spans, source and context.
                for match in re.finditer(r'\b(?:changed? (?:bank|account|payment) details|new bank account|guaranteed (?:returns|profits)|refundable security deposit)\b',text,re.I):
                    phrase=match.group();context=text[max(0,match.start()-45):match.start()].lower();educational=any(w in context for w in ('beware','do not','never','example','avoid'))
                    mapped=map_evidence({'text':phrase,'start':match.start(),'end':match.end()},text,page['ocr']['regions']) if page['source']=='ocr' else {'text':phrase,'start':match.start(),'end':match.end()}
                    if mapped:
                        findings.append({'source':'Document deterministic wording observation','observation':phrase,'interpretation':'Observed wording requires context and independent verification; account ownership or historical change is not verified.','action':'Verify payment instructions through independently obtained contact details.','risk_level':'Informational' if educational else 'Caution','page_number':page.get('page'),'reference':page['reference']})
                        evidence.append({'source_type':page['source'],'snippet':phrase,'page_number':page.get('page'),'reference':page['reference'],'text_offset':{'start':match.start(),'end':match.end()},'bounding_boxes':mapped.get('bounding_boxes'),'detail':'Actual document wording, not issuer/payment verification'})
                        if not educational: risks.append('Caution')
            for observation in parsed.get('structure_observations',[]):
                findings.append({'source':observation['source'],'observation':observation['action'],'interpretation':observation['interpretation'],'action':'Review through a trusted inert viewer; do not execute embedded actions.','risk_level':'Caution','page_number':observation['location'] if isinstance(observation['location'],int) else None,'reference':str(observation['location'])});risks.append('Caution')
            failed=[p['page'] if p.get('page') is not None else p['reference'] for p in pages if p['status']!='completed']
            partial=parsed['parse_status']!='completed' or bool(parsed.get('pages_skipped') or parsed.get('blocks_skipped') or parsed.get('unprocessed_parts') or failed) or any(p.get('text_truncated') or p.get('content_analysis_skipped') or p.get('uncertain_url_candidates') or p.get('ocr') and (p['ocr']['status']!='completed' or any((r.get('confidence') or 0)<settings.SCREENSHOT_MIN_CONFIDENCE for r in p['ocr']['regions'])) for p in pages) or len({u['url'] for u in urls})>MAX_LINKS
            coverage={'total_pages':parsed.get('total_pages'),'pages_parsed':len(pages) if metadata['validated_type']=='PDF' else None,'logical_blocks_parsed':len(pages) if metadata['validated_type']=='DOCX' else None,'pages_ocr_processed':ocr_count,'pages_failed':failed,'pages_skipped':parsed.get('pages_skipped',[]),'content_blocks_analysed':message_count,'parse_coverage_complete':not partial,'analysis_complete':not partial and malware['status']=='clean' and not unavailable and bool(pages),'pagination_limitation':parsed.get('pagination_limitation'),'unprocessed_parts':parsed.get('unprocessed_parts',[]),'limits':capability()['limits']}
            if malware['status']!='clean': unavailable.append({'name':'ClamAV scan coverage','status':'unavailable','detail':malware['detail']})
            if partial or not pages: unavailable.append({'name':'Document content coverage','status':'unavailable','detail':parsed.get('error','Unreadable/skipped/truncated pages, OCR uncertainty or configured limits prevent complete coverage')})
            checks=[{'name':'Content-based file validation','status':'passed','detail':metadata['validated_type']},{'name':'ClamAV malware scan','status':'flagged' if malware['status']=='infected' else 'passed' if malware['status']=='clean' else 'inconclusive','detail':malware['detail']},{'name':'Isolated document parser','status':'passed' if parsed['parse_status']=='completed' else 'inconclusive','detail':parsed['parse_status']},{'name':'Page/content coverage','status':'inconclusive' if partial or not pages else 'passed','detail':f"{len(pages)} actual pages/blocks; {ocr_count} OCR runs; {len(failed)} unreadable; {len(parsed.get('pages_skipped',[]))} skipped"},*checks]
            stage('Combining malware, page evidence, external findings and coverage')
            content_risk='High Risk' if 'High Risk' in risks else 'Caution' if 'Caution' in risks else 'Unable to Assess' if not coverage['analysis_complete'] or not risks or 'Unable to Assess' in risks else 'Low Risk'
            risk='High Risk' if malware['status']=='infected' else content_risk
            if malware['status']=='infected': findings.append({'source':'ClamAV signature database','observation':malware['signature_match'],'interpretation':'Actual malware signature match; parser was not run.','action':'Do not open or execute this document.','risk_level':'High Risk'})
            explanation=parsed.get('error') or f"Processed {len(pages)} actual page(s)/logical block(s). Malware: {malware['status']}. Content risk: {content_risk}. Metadata, signatures, issuer identity, bank ownership and invoice authenticity are not independently verified."
            return {'module_type':'document','original_filename':metadata['original_filename'],'input_summary':'Document content not retained','file':metadata,'document':{k:v for k,v in parsed.items() if k not in ('pages','links')},'pages':pages,'malware':malware,'content_risk':content_risk,'url_assessments':url_results,'grounded_findings':grounded,'coverage':coverage,'risk_category':risk,'explanation':explanation,'score':None,'findings':findings,'evidence':evidence,'checks_performed':checks,'unavailable_checks':unavailable,'recommended_actions':['Verify issuer and payment instructions using independently obtained contact details.','Do not execute document scripts, macros or attachments.','A clean malware scan does not establish safety or authenticity.','Review exact page evidence and missing coverage before acting.'],'provider_info':{'engine':'SafeLens real Document Check','raw_content_retained':False,'parsers':capability()}}


async def analyze_document(file_path,original_filename):
    return await analyze_document_bytes(Path(file_path).read_bytes(),original_filename)
