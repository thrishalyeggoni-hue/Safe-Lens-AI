import json,uuid
from fastapi import APIRouter,Request,Response,UploadFile,File,Form,HTTPException,Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db,JobModel
from ..services.media_service import capability,validate_media,analyze_media_bytes,MAX_BYTES
from ..services.media_jobs import start_job,cancel,JOBS

router=APIRouter(prefix='/api',tags=['Real Media Check'])


@router.get('/check/media/capabilities')
def capabilities():return capability()


@router.post('/check/media')
async def check_media(request:Request,response:Response,file:UploadFile=File(...),language:str=Form('en'),stream:bool=False,queued:bool=False):
    try:raw=await file.read(MAX_BYTES+1);filename=file.filename
    finally:await file.close()
    if language not in ('en','hi','te','mixed'):raise HTTPException(422,detail='Choose English/Hindi/Telugu/mixed')
    try:validate_media(raw,filename)
    except ValueError as e:raise HTTPException(422,detail=str(e)) from None
    owner=request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not owner or len(owner)<16:
        owner=str(uuid.uuid4());response.set_cookie(settings.SESSION_COOKIE_NAME,owner,max_age=settings.SESSION_MAX_AGE_SECONDS,httponly=True,samesite='lax')
    job_id,state=start_job(owner,lambda stage:analyze_media_bytes(raw,filename,language,stage))
    response.headers['Cache-Control']='no-store'
    if queued:return {'job_id':job_id,'status':'queued'}
    if not stream:
        await state['task']
        if not state['result']:raise HTTPException(500,detail='Media job failed; no safety verdict inferred')
        return state['result']
    async def events():
        try:
            yield json.dumps({'type':'stage','stage':'Upload received · queued','job_id':job_id})+'\n'
            while True:
                event=await state['queue'].get();yield json.dumps(event,ensure_ascii=False)+'\n'
                if event['type'] in ('result','error'):break
        finally:await cancel(job_id)
    out=StreamingResponse(events(),media_type='application/x-ndjson',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})
    for n,v in response.raw_headers:
        if n.lower()==b'set-cookie':out.raw_headers.append((n,v))
    return out


def owned(job_id,request,db):
    row=db.get(JobModel,job_id)
    if not row or row.session_id!=request.cookies.get(settings.SESSION_COOKIE_NAME):raise HTTPException(404,detail='Job not found')
    return row


@router.get('/jobs/{job_id}')
def status(job_id:str,request:Request,response:Response,db:Session=Depends(get_db)):
    response.headers['Cache-Control']='no-store';return owned(job_id,request,db).to_dict()


@router.get('/jobs/{job_id}/result')
def result(job_id:str,request:Request,response:Response,db:Session=Depends(get_db)):
    row=owned(job_id,request,db);state=JOBS.get(job_id)
    if not state or state['result'] is None:raise HTTPException(410 if row.status=='completed' else 409,detail='Result is transient or not ready; reupload when expired')
    response.headers['Cache-Control']='no-store';return state['result']


@router.post('/jobs/{job_id}/cancel')
async def cancel_job(job_id:str,request:Request,db:Session=Depends(get_db)):
    owned(job_id,request,db);await cancel(job_id);db.expire_all();return owned(job_id,request,db).to_dict()
