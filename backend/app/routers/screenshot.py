import asyncio
from contextlib import suppress
import json
import uuid
from fastapi import APIRouter, Request, Response, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..services.screenshot_image import decode_image
from ..services.ocr_service import analyze_screenshot_bytes
from ..services.paddle_service import capability
from ..services.message_storage import persist_message_metadata

router=APIRouter(prefix='/api',tags=['Real Screenshot Check'])


@router.get('/check/screenshot/capabilities')
def capabilities():
    return capability()


@router.post('/check/screenshot')
async def check_screenshot(request:Request,response:Response,file:UploadFile=File(...),language:str=Form('en'),
                           stream:bool=False,db:Session=Depends(get_db)):
    if language not in ('en','hi','te','mixed'):
        await file.close()
        raise HTTPException(422,detail='Choose English, Hindi, Telugu or mixed OCR')
    try:
        raw=await file.read(settings.SCREENSHOT_MAX_BYTES+1)
        filename=file.filename
    finally:
        await file.close()
    try:
        image,_=await asyncio.to_thread(decode_image,raw,filename)
        image.close()
    except ValueError as exc:
        raise HTTPException(422,detail=str(exc)) from None
    session_id=request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_id or len(session_id)<16:
        session_id=str(uuid.uuid4())
        response.set_cookie(settings.SESSION_COOKIE_NAME,session_id,max_age=settings.SESSION_MAX_AGE_SECONDS,httponly=True,samesite='lax')
    async def analyze(on_stage=None):
        async with asyncio.timeout(240):
            return await analyze_screenshot_bytes(raw,filename,language,on_stage)
    response.headers['Cache-Control']='no-store'
    if not stream:
        try:
            return persist_message_metadata(await analyze(),session_id,db)
        except TimeoutError:
            raise HTTPException(504,detail='Screenshot analysis timed out; no safety verdict was inferred') from None
    async def events():
        queue=asyncio.Queue()
        queue.put_nowait({'type':'stage','stage':'Upload received · actual screenshot validated'})
        async def run():
            try:
                result=await analyze(lambda stage:queue.put_nowait({'type':'stage','stage':stage}))
                result=persist_message_metadata(result,session_id,db)
                queue.put_nowait({'type':'stage','stage':'Assessment complete'})
                queue.put_nowait({'type':'result','data':result})
            except Exception as exc:
                db.rollback()
                queue.put_nowait({'type':'error','detail':f'Screenshot processing failed ({type(exc).__name__}); no safety verdict was inferred.'})
        task=asyncio.create_task(run())
        try:
            while True:
                event=await queue.get()
                yield json.dumps(event,ensure_ascii=False)+'\n'
                if event['type'] in ('result','error'): break
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError): await task
    output=StreamingResponse(events(),media_type='application/x-ndjson',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})
    for name,value in response.raw_headers:
        if name.lower()==b'set-cookie': output.raw_headers.append((name,value))
    return output
