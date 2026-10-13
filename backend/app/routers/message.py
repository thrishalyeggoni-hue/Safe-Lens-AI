import asyncio
import json
import uuid
from contextlib import suppress

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..services.message_extraction import extract_message
from ..services.message_service import analyze_message
from ..services.message_storage import persist_message_metadata

router = APIRouter(prefix='/api', tags=['Real Message Check'])


class MessageRequest(BaseModel):
    message: str = Field(max_length=12000)


@router.post('/check/message')
async def check_message(body: MessageRequest, request: Request, response: Response, stream: bool = False, db: Session = Depends(get_db)):
    try:
        extract_message(body.message)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from None
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_id or len(session_id) < 16:
        session_id = str(uuid.uuid4())
        response.set_cookie(settings.SESSION_COOKIE_NAME, session_id, max_age=settings.SESSION_MAX_AGE_SECONDS, httponly=True, samesite='lax')
    if not stream:
        response.headers['Cache-Control'] = 'no-store'
        return persist_message_metadata(await analyze_message(body.message), session_id, db)

    async def events():
        queue = asyncio.Queue()
        async def run():
            try:
                result = await analyze_message(body.message, on_stage=lambda stage: queue.put_nowait({'type': 'stage', 'stage': stage}))
                queue.put_nowait({'type': 'result', 'data': persist_message_metadata(result, session_id, db)})
            except Exception as exc:
                db.rollback()
                # Exception type only: no raw message, quotes, request URLs, or model responses in logs/errors.
                queue.put_nowait({'type': 'error', 'detail': f'Message analysis could not complete ({type(exc).__name__}).'})
        task = asyncio.create_task(run())
        try:
            while True:
                event = await queue.get()
                yield json.dumps(event, ensure_ascii=False) + '\n'
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
