import asyncio
import json
import uuid
from contextlib import suppress
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..database import AssessmentModel, get_db
from ..services.url_normalizer import normalize_url
from ..services.url_service import analyze_link

router = APIRouter(prefix='/api', tags=['Real Link Check'])


class LinkRequest(BaseModel):
    url: str = Field(min_length=1, max_length=4096)


def persist(result, session_id, db):
    record = AssessmentModel(
        id=f'asmt_{uuid.uuid4().hex[:12]}', session_id=session_id, created_at=datetime.now(timezone.utc),
        module_type='link', input_summary=result['input_summary'], risk_category=result['risk_category'], explanation=result['explanation'],
        findings_json=json.dumps(result['findings']), evidence_json=json.dumps(result['evidence']), checks_json=json.dumps(result['checks_performed']),
        unavailable_checks_json=json.dumps(result['unavailable_checks']), recommended_actions_json=json.dumps(result['recommended_actions']),
        provider_info_json=json.dumps(result['provider_info']), score=None,
        retention_expiry=datetime.now(timezone.utc) + timedelta(hours=settings.RETENTION_HOURS))
    db.add(record)
    db.commit()
    return record.to_dict()


@router.post('/check/link')
async def check_link(body: LinkRequest, request: Request, response: Response, stream: bool = False, db: Session = Depends(get_db)):
    try:
        normalize_url(body.url)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from None
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_id or len(session_id) < 16:
        session_id = str(uuid.uuid4())
        response.set_cookie(settings.SESSION_COOKIE_NAME, session_id, max_age=settings.SESSION_MAX_AGE_SECONDS, httponly=True, samesite='lax')
    if not stream:
        return persist(await analyze_link(body.url), session_id, db)

    async def events():
        queue = asyncio.Queue()
        async def run():
            try:
                result = await analyze_link(body.url, on_stage=lambda stage: queue.put_nowait({'type': 'stage', 'stage': stage}))
                queue.put_nowait({'type': 'result', 'data': persist(result, session_id, db)})
            except Exception:
                db.rollback()
                queue.put_nowait({'type': 'error', 'detail': 'Link analysis could not complete. Please retry.'})
        task = asyncio.create_task(run())
        try:
            while True:
                event = await queue.get()
                yield json.dumps(event) + '\n'
                if event['type'] in ('result', 'error'):
                    break
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
    streaming = StreamingResponse(events(), media_type='application/x-ndjson', headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})
    for name, value in response.raw_headers:
        if name.lower() == b'set-cookie':
            streaming.raw_headers.append((name, value))
    return streaming


@router.get('/assessments/{assessment_id}')
def read_link_assessment(assessment_id: str, request: Request, db: Session = Depends(get_db)):
    record = db.get(AssessmentModel, assessment_id)
    if not record:
        raise HTTPException(404, detail='Assessment not found')
    if record.session_id != request.cookies.get(settings.SESSION_COOKIE_NAME):
        raise HTTPException(403, detail='Access denied to this assessment')
    return record.to_dict()
