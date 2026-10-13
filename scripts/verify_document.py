"""Explicit actual controlled-document API checks; never used as app fixtures."""
import asyncio
import json
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]
CASES=['normal','url','provider_test','mismatch','job_offer','changed_invoice','legitimate_invoice','scanned','mixed_pages','hindi','telugu','mixed_language','encrypted','corrupt','many_pages','blank','malware_test','prompt_injection','active_actions','normal_docx','job_docx']


async def main():
    results=[]
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8000',timeout=310) as client:
        ready=await client.get('/api/check/document/capabilities');ready.raise_for_status()
        for name in CASES:
            path=ROOT/'tests/document-fixtures'/(name+('.docx' if name.endswith('docx') else '.pdf'))
            language='hi' if name=='hindi' else 'te' if name=='telugu' else 'mixed' if name=='mixed_language' else 'en'
            response=await client.post('/api/check/document',files={'file':(path.name,path.read_bytes(),'application/octet-stream')},data={'language':language})
            result=response.json()
            # Keep actual text/regions/results; inert preview bytes are saved separately in browser proof.
            for page in result.get('pages',[]):page.pop('preview_png',None)
            results.append({'case':name,'http_status':response.status_code,'result':result})
            (ROOT/'docs/document-verification.json').write_text(json.dumps({'notice':'Actual controlled upload runs in progress; preview bytes omitted.','cases':results},ensure_ascii=False,indent=2)+'\n')
            print(name,response.status_code,result.get('risk_category'),result.get('malware',{}).get('status'),result.get('coverage',{}).get('pages_ocr_processed'),flush=True)
        response=await client.post('/api/check/document',content=b'x'*(22*1024*1024),headers={'Content-Type':'multipart/form-data; boundary=controlled'})
        results.append({'case':'oversized','http_status':response.status_code,'result':response.json()})
    (ROOT/'docs/document-verification.json').write_text(json.dumps({'notice':'Actual controlled agent-authored document uploads; no application use as canned responses. Rendered preview bytes omitted. EICAR fixture is the harmless standard AV test string embedded as an attachment, never executed.','cases':results},ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':asyncio.run(main())
