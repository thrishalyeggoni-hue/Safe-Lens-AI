"""Offer orchestration over existing Message, Link and Document services."""
import re
from .message_service import analyze_message
from .message_extraction import context_for,span,validate_text
from .document_service import analyze_document_bytes
from .screenshot_grounding import map_evidence

TYPES={'job':r'\b(?:job|employment|salary|recruitment|interview|hiring)\b|नौकरी|ఉద్యోగ','shopping':r'\b(?:shopping|product|buy|checkout|discount|sale)\b|खरीद|కొనుగోలు','investment':r'\b(?:invest\w*|returns?|profit|portfolio)\b|निवेश|పెట్టుబడి','service':r'\b(?:service|consulting|booking|payment request|invoice)\b','promotion':r'\b(?:promotion|promotional|coupon|reward|prize)\b'}
PATTERNS=[('advance_payment',r'\b(?:registration|interview|processing|activation|joining|training|release|refundable|equipment)\s+(?:fee|charge|deposit|payment)\b|\bsecurity\s+deposit\b|\b(?:advance|booking)\s+payment\b|\btax\s+payment\s+before\b|पंजीकरण\s+शुल्क|रजिस्ट्रेशन\s+फीस|నమోదు\s+ఫీజు'),('guaranteed_return',r'\b(?:guaranteed|assured)\s+(?:profits?|returns?|income)\b|\b(?:zero risk|risk[- ]free|double your money|fixed daily income)\b|गारंटी.{0,15}(?:रिटर्न|लाभ)|హామీ.{0,20}రాబడి'),('large_discount',r'\b(?:[89]\d|100)\s*%\s*(?:off|discount)\b'),('pressure',r'\b(?:act now|today only|limited time|pay immediately|last chance|do not tell anyone|no interview required|immediate selection)\b'),('credential_request',r'\b(?:send|share|give|provide|tell)\s+(?:(?:me|us|your|the)\s+){0,2}(?:seed phrase|private key|recovery code|banking credentials|card number)\b'),('off_platform',r'\b(?:pay|payment)\s+outside\s+(?:checkout|the platform)\b'),('regulatory_claim',r'\b(?:SEBI|RBI|government|regulator)[- ](?:approved|registered|licensed)\b')]


def classify(text):
    matches={kind:[span(text,*m.span(),'offer_type_cue') for m in re.finditer(pattern,text,re.I)] for kind,pattern in TYPES.items()}
    populated=[k for k,v in matches.items() if v]
    return {'offer_type':populated[0] if len(populated)==1 else 'unknown','method':'Keyword observations, not certified classification','candidates':populated,'evidence':[e for v in matches.values() for e in v]}


def extract_offer(text):
    validate_text(text);items=[]
    for category,pattern in PATTERNS:
        for m in re.finditer(pattern,text,re.I):
            items.append(span(text,*m.span(),category,source='offer_deterministic',context=context_for(text,*m.span()),interpretation={'advance_payment':'Observed fee/deposit wording; verify whether this is an active request and whether payment is justified.','guaranteed_return':'The offer claims guaranteed or low-risk returns; performance and regulatory status were not verified.','large_discount':'The offer claims a very large discount; no real market price comparison was performed.','regulatory_claim':'A regulatory approval claim is present; regulatory status was not independently verified.'}.get(category,'Observed offer request or pressure indicator; it is not confirmed fraud.')))
    organisations=[]
    for m in re.finditer(r'\b(?:Microsoft|Google|Amazon|Apple|Infosys|TCS|Wipro|SBI|HDFC|ICICI)\b',text,re.I):organisations.append(span(text,*m.span(),'organisation_mention'))
    for m in re.finditer(r'\b(?:company|organisation|organization|employer)\s*:\s*([A-Za-z][A-Za-z &.-]{1,60})',text,re.I):organisations.append(span(text,*m.span(1),'organisation_claim'))
    return items,organisations


async def analyze_offer(offer_text,on_stage=None,base_analysis=None,document_context=None,url_filter=None):
    text=offer_text;indicators,organisations=extract_offer(text)
    if on_stage:on_stage('Extracting offer details · actual text and offsets')
    classification=classify(text)
    message=base_analysis or await analyze_message(text,on_stage=on_stage,document_context=document_context,url_filter=url_filter,offer_context=True)
    entities=message['extracted_entities']+organisations
    contacts=[e for e in entities if e['category'] in ('email','phone')]
    # Lexical inconsistency only; these comparisons do not establish official domains or ownership.
    if organisations:
        for contact in contacts:
            if contact['category']!='email':continue
            domain=contact['text'].rsplit('@',1)[1].lower()
            names=[re.sub(r'[^a-z0-9]','',o['text'].lower()) for o in organisations]
            if not any(name and name in domain.replace('-','').replace('.','') for name in names):
                indicators.append({**contact,'category':'identity_conflict','source':'offer_deterministic','context':context_for(text,contact['start'],contact['end']),'interpretation':'Claimed organisation wording and contact domain appear lexically inconsistent. No official domain, sender ownership or impersonation was independently verified.'})
    direct=[i for i in indicators if i['context']=='direct_or_uncertain']
    categories={i['category'] for i in direct}
    adequate=sum(c.isalnum() for c in text)>=12
    risk=message['risk_category']
    if not adequate:risk='Unable to Assess'
    elif 'credential_request' in categories or {'guaranteed_return','pressure'}<=categories and any(e['category']=='payment_method' and re.search('crypto|bitcoin|USDT',e['text'],re.I) for e in entities):risk='High Risk'
    elif direct and risk not in ('High Risk','Caution'):risk='Caution'
    findings=list(message['findings']);evidence=list(message['evidence'])
    for i in indicators:
        level='Informational' if i['context']!='direct_or_uncertain' else 'High Risk' if i['category']=='credential_request' else 'Caution'
        findings.append({'source':'Offer deterministic · '+i['category'],'observation':i['text'],'interpretation':i['interpretation']+' Context: '+i['context'],'action':'Verify the issuer and claims independently before payment or sharing credentials.','risk_level':level,'text_offset':{'start':i['start'],'end':i['end']}})
        evidence.append({'source_type':'offer_deterministic','snippet':i['text'],'text_offset':{'start':i['start'],'end':i['end']},'detail':i['category']+' · '+i['context']})
    return {'module_type':'offer','input_summary':'Offer content not retained','submitted_text':text,'input_source':'text','offset_unit':'unicode_codepoints','offer_type':classification['offer_type'],'classification':classification,'extracted_entities':entities,'contacts':contacts,'organisations':organisations,'payment_amounts':[e for e in entities if e['category']=='amount'],'payment_instructions':[i for i in indicators+message['deterministic_findings'] if i['category'] in ('advance_payment','unusual_payment','off_platform')],'deterministic_findings':message['deterministic_findings']+indicators,'url_assessments':message['url_assessments'],'ai':message['ai'],'ai_interpretations':message['ai_interpretations'],'findings':findings,'evidence':evidence,'risk_category':risk,'score':None,'explanation':f'Offer content risk: {risk}. Observed claims and requests are indicators, not independent proof of fraud or legitimacy. Regulatory status, market prices, employer identity and contact ownership were not independently verified.','checks_performed':message['checks_performed']+[{'name':'Offer classification and contextual deterministic indicators','status':'flagged' if direct else 'passed','detail':f"{classification['offer_type']} · {len(indicators)} exact spans; quoted/negated wording distinguished"}],'unavailable_checks':message['unavailable_checks']+[{'name':'Organisation, regulatory, price and contact verification','status':'unavailable','detail':'No independent registry, regulator, price, phone or bank ownership source connected'}],'recommended_actions':['Verify the offer through independently obtained organisation contact details.','Do not disclose credentials or pay advance fees solely on an unsolicited promise.','A suspicious indicator does not prove an organisation is fake.'],'provider_info':{'engine':'SafeLens Offer orchestration over Message/Link/Document','model_used':message['ai'].get('model_used'),'raw_content_retained':False},'coverage':{'contextual_ai':message['ai']['status'],'all_urls_checked':len(message['url_assessments']),'external_claims_verified':False}}


async def analyze_offer_input(text='',raw=None,filename=None,language='en',on_stage=None):
    if raw is None:return await analyze_offer(text,on_stage)
    if text.strip():raise ValueError('Submit offer text or one offer document, separately, so every evidence offset has one source')
    doc=await analyze_document_bytes(raw,filename,language,on_stage)
    analyses=[];findings=[];evidence=[];entities=[];urls=list(doc.get('url_assessments',[]));checks=list(doc['checks_performed']);unavailable=list(doc['unavailable_checks'])
    # Reuse the Document pipeline's actual per-page Message/Link results, including grounded AI.
    for page in doc.get('pages',[]):
        if not page.get('text'):continue
        result=await analyze_offer(page['text'],on_stage,base_analysis=page.get('message_analysis'),document_context={'page_number':page.get('page'),'reference':page['reference']},url_filter=lambda _:False)
        context={'page_number':page.get('page'),'reference':page['reference'],'text_source':page['source']}
        analyses.append({'reference':page['reference'],'page_number':page.get('page'),'analysis':result})
        entities.extend({**x,**context} for x in result['extracted_entities']);urls.extend({**u,**context} for u in result['url_assessments'])
        for f in result['findings']:
            item={**f,**context}
            if page.get('ocr'):
                offset=f.get('text_offset') or next((e['text_offset'] for e in result['evidence'] if e['snippet']==f['observation']),None)
                mapped=map_evidence({'text':f['observation'],**(offset or {})},page['text'],page['ocr'].get('regions',[]))
                if not mapped:continue
                item.update(region_ids=mapped['region_ids'],bounding_boxes=mapped['bounding_boxes'],ocr_certainty=mapped['ocr_certainty'])
                if mapped['ocr_certainty']=='uncertain' and item['risk_level']=='High Risk':item['risk_level']='Caution'
            findings.append(item)
        for e in result['evidence']:
            item={**e,**context}
            if page.get('ocr'):
                mapped=map_evidence({'text':e['snippet'],**e['text_offset']},page['text'],page['ocr'].get('regions',[]))
                if not mapped:continue
                item.update(region_ids=mapped['region_ids'],bounding_boxes=mapped['bounding_boxes'])
            evidence.append(item)
        checks.extend(result['checks_performed']);unavailable.extend(result['unavailable_checks'])
    # Preserve structural/malware/link findings even when text is unreadable.
    risk=doc['risk_category']
    if any(f['risk_level']=='High Risk' for f in findings):risk='High Risk'
    elif any(f['risk_level']=='Caution' for f in findings) and risk!='High Risk':risk='Caution'
    types={a['analysis']['offer_type'] for a in analyses if a['analysis']['offer_type']!='unknown'}
    return {'module_type':'offer','input_summary':'Offer document content not retained','input_source':'document','offer_type':next(iter(types)) if len(types)==1 else 'unknown','file':doc['file'],'document_analysis':doc,'page_analyses':analyses,'extracted_entities':entities,'url_assessments':urls,'findings':doc['findings']+findings,'evidence':doc['evidence']+evidence,'risk_category':risk,'score':None,'explanation':f'Offer document: {risk}. Actual document evidence and coverage retained; issuer, regulatory status and market prices are unverified.','checks_performed':checks,'unavailable_checks':unavailable,'coverage':doc['coverage'],'recommended_actions':doc['recommended_actions'],'provider_info':{'engine':'SafeLens Offer + existing Document/Message/Link','raw_content_retained':False}}
