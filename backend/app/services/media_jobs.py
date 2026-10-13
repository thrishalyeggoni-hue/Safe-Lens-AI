"""Use the project's persisted JobModel; transient results never enter SQLite."""
import asyncio,time,uuid
from contextlib import suppress
from ..database import JobModel,SessionLocal
from .message_storage import persist_message_metadata

JOBS={}


def update(job_id,**fields):
    with SessionLocal() as db:
        row=db.get(JobModel,job_id)
        for k,v in fields.items():setattr(row,k,v)
        db.commit()


def start_job(session_id,analyze):
    job_id='job_'+uuid.uuid4().hex[:12];state={'owner':session_id,'queue':asyncio.Queue(),'result':None,'created':time.monotonic()}
    with SessionLocal() as db:
        db.add(JobModel(job_id=job_id,session_id=session_id,status='queued',current_stage='Queued'));db.commit()
    def stage(s):
        update(job_id,status='queued' if s.startswith('Queued') else 'processing',current_stage=s[:64])
        state['queue'].put_nowait({'type':'stage','stage':s,'job_id':job_id})
    async def run():
        try:
            async with asyncio.timeout(600):result=await analyze(stage)
            with SessionLocal() as db:result=persist_message_metadata(result,session_id,db)
            result['job_id']=job_id;state['result']=result
            update(job_id,status='completed',current_stage='Assessment complete',assessment_id=result['id'])
            state['queue'].put_nowait({'type':'result','data':result})
        except asyncio.CancelledError:
            update(job_id,status='cancelled',current_stage='Cancelled');state['queue'].put_nowait({'type':'error','detail':'Analysis cancelled','job_id':job_id});raise
        except Exception as e:
            error=f'Media processing failed ({type(e).__name__}); no safety verdict inferred.'
            update(job_id,status='failed',current_stage='Failed',error=error)
            state['queue'].put_nowait({'type':'error','detail':error,'job_id':job_id})
        finally:
            asyncio.get_running_loop().call_later(900,JOBS.pop,job_id,None)
    JOBS[job_id]=state;state['task']=asyncio.create_task(run());return job_id,state


async def cancel(job_id):
    state=JOBS.get(job_id)
    if state and not state['task'].done():
        state['task'].cancel()
        with suppress(asyncio.CancelledError):await state['task']
        if state['task'].cancelled():update(job_id,status='cancelled',current_stage='Cancelled')


def recover_interrupted_jobs():
    with SessionLocal() as db:
        for row in db.query(JobModel).filter(JobModel.status.in_(['queued','processing'])):
            row.status='failed';row.current_stage='Interrupted by server shutdown';row.error='Processing did not complete; reupload the original media.'
        db.commit()


async def shutdown_jobs():
    for job_id in list(JOBS):await cancel(job_id)
    JOBS.clear()
