"""Map reconstructed text back to actual engine polygons; never invent regions."""
import math
import re
from .message_extraction import span
from ..config import settings


def bounds(item):
    p = item['bounding_box']['points']
    return min(x for x,y in p), min(y for x,y in p), max(x for x,y in p), max(y for x,y in p)


def overlap(a,b):
    ax,ay,ar,ab=bounds(a); bx,by,br,bb=bounds(b)
    intersection=max(0,min(ar,br)-max(ax,bx))*max(0,min(ab,bb)-max(ay,by))
    union=(ar-ax)*(ab-ay)+(br-bx)*(bb-by)-intersection
    return intersection/union if union else 0


def valid_regions(items, width, height):
    valid, rejected = [], 0
    for item in items:
        try:
            points=item['bounding_box']['points']
            score=item.get('confidence')
            if not isinstance(item['text'],str) or len(item['text'])>12000 or not item['text'].strip() or len(points)!=4:
                raise ValueError()
            if any(len(p)!=2 or any(not math.isfinite(float(v)) for v in p) or not (-1<=p[0]<=width+1 and -1<=p[1]<=height+1) for p in points):
                raise ValueError()
            if score is not None and (not math.isfinite(score) or not 0<=score<=1): raise ValueError()
            valid.append(item)
        except (KeyError, TypeError, ValueError): rejected+=1
    return valid,rejected


def merge_reading_order(items):
    groups=[]
    for item in items:
        existing=next((group for group in groups if overlap(group[0],item)>.65),None)
        if existing is not None: existing.append(item)
        else: groups.append([item])
    chosen=[]
    for group in groups:
        # Native-script candidate preference only when the actual recognized script matches the recognizer.
        def rank(item):
            native=(item.get('language_model')=='hi' and re.search(r'[\u0900-\u097f]',item['text'])) or (item.get('language_model')=='te' and re.search(r'[\u0c00-\u0c7f]',item['text']))
            return (bool(native and (item.get('confidence') or 0)>=.8), item.get('confidence') or 0)
        item=dict(max(group,key=rank))
        if len(group)>1:
            item['recognition_alternatives']=[{'text':x['text'],'confidence':x.get('confidence'),'model':x.get('model')} for x in group]
        chosen.append(item)
    chosen.sort(key=lambda item:(bounds(item)[1],bounds(item)[0]))
    rows=[]
    for item in chosen:
        x,y,r,b=bounds(item)
        def same_row(row):
            _,ry,_,rb=bounds(row[0])
            return max(0,min(b,rb)-max(y,ry))>=.5*min(b-y,rb-ry)
        row=next((row for row in rows if same_row(row)),None)
        if row is None: rows.append([item])
        else: row.append(item)
    chosen=[]
    for row in rows:
        row.sort(key=lambda item:bounds(item)[0])
        for index,item in enumerate(row):
            item=dict(item)
            separator='\n'
            if index:
                px,py,pr,pb=bounds(row[index-1]);x,y,r,b=bounds(item)
                # Adjacent pieces of one line get a space; distant columns stay separated.
                separator=' ' if x-pr<=1.5*max(pb-py,b-y) else '\n\n'
            item['reading_separator']=separator
            chosen.append(item)
    text=''
    for i,item in enumerate(chosen):
        if text: text+=item['reading_separator']
        item.update(region_id=f'ocr_{i+1}',start=len(text),end=len(text)+len(item['text']))
        text+=item['text']
    return text,chosen


def map_evidence(item, text, regions):
    start,end=item.get('start'),item.get('end')
    if not isinstance(start,int) or not isinstance(end,int) or not 0<=start<end<=len(text) or text[start:end]!=item.get('text'):
        return None
    matching=[region for region in regions if region['start']<end and start<region['end']]
    if not matching: return None
    # Every non-whitespace character must belong to a known region, not an inferred join.
    if any(not text[i].isspace() and not any(r['start']<=i<r['end'] for r in matching) for i in range(start,end)):
        return None
    scores=[r.get('confidence') for r in matching]
    readable=all(score is not None and score>=settings.SCREENSHOT_MIN_CONFIDENCE for score in scores)
    return {**item,'region_ids':[r['region_id'] for r in matching],'bounding_boxes':[r['bounding_box'] for r in matching],
            'ocr_confidences':scores,'ocr_certainty':'readable' if readable else 'uncertain',
            'source':item.get('source','ocr_entity')}


def payment_observations(text,regions,entities):
    observations=[]
    for item in entities:
        if item['category'] in ('amount','payment_method'):
            mapped=map_evidence(item,text,regions)
            if mapped: observations.append(mapped)
    patterns=[('upi_identifier',r'\b[\w.-]{2,256}@(?:ok\w+|paytm|ybl|ibl|axl|sbi|icici|hdfc)\b'),
              ('bank_account_reference',r'\b(?:bank account|account number|a/c)\s*[:#-]?\s*\d[\d -]{5,22}'),
              ('payment_instruction',r'\b(?:registration fee|processing fee|scan.{0,30}(?:pay|payment))\b'),
              ('crypto_address_candidate',r'\b(?:0x[a-fA-F0-9]{40}|bc1[ac-hj-np-z02-9]{25,62})\b')]
    for category,pattern in patterns:
        for match in re.finditer(pattern,text,re.I):
            mapped=map_evidence(span(text,*match.span(),category,source='ocr_payment_observation'),text,regions)
            if mapped: observations.append(mapped)
    return [{**item,'interpretation':'Observed OCR payment content only; payee identity, ownership, transaction authenticity and legality are not verified.'} for item in observations]


def uncertain_urls(text,regions):
    candidates=[]
    for match in re.finditer(r'https?:/(?!/)[^\s<>]+',text,re.I):
        mapped=map_evidence(span(text,*match.span(),'uncertain_url',source='ocr_candidate'),text,regions)
        if mapped:
            candidates.append({**mapped,'original_ocr_text':match.group(),'normalized_candidate':re.sub(r'^(https?):/',r'\1://',match.group(),flags=re.I),
                               'normalization_reason':'Possible missing scheme slash in OCR; candidate is inferred, not silently substituted.', 'status':'not_contacted'})
    for left,right in zip(regions,regions[1:]):
        match=re.search(r'(?:https?://|www\.)[^\s]*$',left['text'],re.I)
        continuation=re.match(r'^[a-z0-9][a-z0-9./?=&_%#-]{1,150}$',right['text'])
        if not match or not continuation: continue
        prefix=match.group();host=prefix.removeprefix('https://').removeprefix('http://').split('/')[0]
        if '.' in host and not host.endswith(('.', '-')): continue
        lx,ly,lr,lb=bounds(left);rx,ry,rr,rb=bounds(right)
        if ry-lb>max(lb-ly,rb-ry)*2 or abs(lx-rx)>max(40,(lr-lx)*.2): continue
        original=text[left['start']+match.start():right['end']]
        mapped=map_evidence({'text':original,'start':left['start']+match.start(),'end':right['end'],'category':'uncertain_url','source':'ocr_candidate'},text,regions)
        if mapped:
            candidates.append({**mapped,'original_ocr_text':original,'normalized_candidate':prefix+right['text'],
                               'normalization_reason':'URL-like text spans adjacent regions; joining is uncertain and requires manual confirmation.', 'status':'not_contacted'})
    return candidates
