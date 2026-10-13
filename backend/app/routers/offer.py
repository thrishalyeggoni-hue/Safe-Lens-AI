import asyncio,json,uuid
from contextlib import suppress
from fastapi import APIRouter,Request,Response,HTTPException,Depends
from fastapi.responses import StreamingResponse
from starlette.datastructures import UploadFile
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..services.offer_service import analyze_offer_input
from ..services.message_extraction import validate_text
from ..services.document_service import validate_document,MAX_BYTES
from ..services.message_storage import persist_message_metadata

router=APIRouter(prefix='/api',tags=['Real Offer Check'])


@router.post('/check/offer')
async def check_offer(request:Request,response:Response,stream:bool=False,db:Session=Depends(get_db)):
    raw=None;filename=None;language='en'
    if 'application/json' in request.headers.get('content-type',''):
        body=await request.body()
        if len(body)>128*1024:raise HTTPException(413,detail='Offer request too large')
        try:text=json.loads(body).get('offer','')
        except (ValueError,AttributeError):raise HTTPException(422,detail='Offer JSON must contain text') from None
    else:
        async with request.form(max_files=1,max_fields=3) as form:
            text=form.get('offer','');language=form.get('language','en');file=form.get('file')
            if isinstance(file,UploadFile):raw=await file.read(MAX_BYTES+1);filename=file.filename
    try:
        validate_text(text)
        if language not in ('en','hi','te','mixed'):raise ValueError('Choose English/Hindi/Telugu/mixed')
        if raw is not None:
            validate_document(raw,filename)
            if text.strip():raise ValueError('Submit text or one offer document separately')
        elif not text.strip():raise ValueError('Paste offer text or upload a supported document')
    except ValueError as e:raise HTTPException(422,detail=str(e)) from None
    owner=request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not owner or len(owner)<16:
        owner=str(uuid.uuid4());response.set_cookie(settings.SESSION_COOKIE_NAME,owner,max_age=settings.SESSION_MAX_AGE_SECONDS,httponly=True,samesite='lax')
    async def analyze(stage=None):
        async with asyncio.timeout(360):return await analyze_offer_input(text,raw,filename,language,stage)
    response.headers['Cache-Control']='no-store'
    if not stream:return persist_message_metadata(await analyze(),owner,db)
    async def events():
        queue=asyncio.Queue()
        async def run():
            try:
                queue.put_nowait({'type':'stage','stage':'Submission received · actual offer'})
                result=await analyze(lambda s:queue.put_nowait({'type':'stage','stage':s}))
                queue.put_nowait({'type':'result','data':persist_message_metadata(result,owner,db)})
            except Exception as e:
                db.rollback();queue.put_nowait({'type':'error','detail':f'Offer analysis failed ({type(e).__name__}); no verdict inferred.'})
        task=asyncio.create_task(run())
        try:
            while True:
                event=await queue.get();yield json.dumps(event,ensure_ascii=False)+'\n'
                if event['type'] in ('result','error'):break
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):await task
    out=StreamingResponse(events(),media_type='application/x-ndjson',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})
    for n,v in response.raw_headers:
        if n.lower()==b'set-cookie':out.raw_headers.append((n,v))
    return out
