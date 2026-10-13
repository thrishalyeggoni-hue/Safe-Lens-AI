import os
import uuid
import json
import shutil
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, Response
from starlette.datastructures import UploadFile as StarletteUploadFile
from sqlalchemy.orm import Session
from ..database import get_db, AssessmentModel, JobModel
from ..config import settings
from ..schemas import AssessmentResponse, JobStatusResponse
from ..services.url_service import analyze_link
from ..services.message_service import analyze_message
from ..services.message_storage import persist_message_metadata
from ..services.ocr_service import analyze_screenshot_bytes
from ..services.qr_service import analyze_qr_bytes
from ..services.document_service import analyze_document, analyze_document_bytes
from ..services.media_service import analyze_media_bytes
from ..services.offer_service import analyze_offer_input

router = APIRouter(prefix="/api", tags=["Assessments"])

def get_or_create_session(request: Request, response: Response) -> str:
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_id or len(session_id) < 16:
        session_id = str(uuid.uuid4())
        response.set_cookie(
            key=settings.SESSION_COOKIE_NAME,
            value=session_id,
            max_age=settings.SESSION_MAX_AGE_SECONDS,
            httponly=True,
            samesite="lax"
        )
    return session_id

@router.post("/assessments")
async def create_assessment(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    session_id = get_or_create_session(request, response)
    assessment_id = f"asmt_{uuid.uuid4().hex[:12]}"
    retention_expiry = datetime.now(timezone.utc) + timedelta(hours=settings.RETENTION_HOURS)

    content_type = request.headers.get("content-type", "").lower()
    file = None
    module_type = None
    content_text = None
    target_url = None

    if "application/json" in content_type:
        body = await request.json()
        module_type = body.get("module_type")
        content_text = body.get("content_text")
        target_url = body.get("target_url")
    else:
        form = await request.form()
        module_type = form.get("module_type")
        content_text = form.get("content_text")
        target_url = form.get("target_url")
        raw_file = form.get("file")
        if isinstance(raw_file, StarletteUploadFile):
            file = raw_file

    if not module_type:
        raise HTTPException(status_code=400, detail="module_type is required")

    # 1. Dispatch to real backend processing based on module_type
    try:
        if module_type == "link":
            raw_target = target_url or content_text or ""
            if not raw_target.strip():
                raise HTTPException(status_code=400, detail="URL cannot be empty for link check")
            result = await analyze_link(raw_target)

        elif module_type == "message":
            text = content_text or target_url or ""
            result = await analyze_message(text)

        elif module_type == "screenshot":
            if not file:
                raise HTTPException(status_code=400, detail="Image screenshot file is required")
            try:
                raw = await file.read(settings.SCREENSHOT_MAX_BYTES + 1)
                result = await analyze_screenshot_bytes(raw, file.filename)
            finally:
                await file.close()

        elif module_type == "qr":
            if not file:
                raise HTTPException(status_code=400, detail="QR image file is required")
            raw = await file.read(settings.SCREENSHOT_MAX_BYTES + 1)
            try:
                result = await analyze_qr_bytes(raw, file.filename)
            except ValueError as exc:
                raise HTTPException(422, detail=str(exc)) from None
            finally:
                await file.close()

        elif module_type == "document":
            if not file:
                raise HTTPException(status_code=400, detail="PDF document file is required")
            raw = await file.read(20 * 1024 * 1024 + 1)
            try:
                result = await analyze_document_bytes(raw, file.filename)
            finally:
                await file.close()

        elif module_type == "media":
            if not file:
                raise HTTPException(status_code=400, detail="Media file is required")
            try:
                raw = await file.read(50 * 1024 * 1024 + 1)
                result = await analyze_media_bytes(raw, file.filename)
            finally:
                await file.close()

        elif module_type == "offer":
            raw = None
            if file:
                try: raw = await file.read(20 * 1024 * 1024 + 1)
                finally: await file.close()
            result = await analyze_offer_input(content_text or '', raw, file.filename if file else None)

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported threat module type: {module_type}")

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assessment processing failed: {str(e)}")

    # 2. Persist real assessment to database for this session
    if module_type in ('message', 'screenshot', 'qr', 'document', 'media', 'offer'):
        return persist_message_metadata(result, session_id, db)
    record = AssessmentModel(
        id=assessment_id,
        session_id=session_id,
        created_at=datetime.now(timezone.utc),
        module_type=module_type,
        input_summary=result.get("input_summary", "Submitted content"),
        risk_category=result.get("risk_category", "Caution"),
        explanation=result.get("explanation", ""),
        findings_json=json.dumps(result.get("findings", [])),
        evidence_json=json.dumps(result.get("evidence", [])),
        checks_json=json.dumps(result.get("checks_performed", [])),
        unavailable_checks_json=json.dumps(result.get("unavailable_checks", [])),
        recommended_actions_json=json.dumps(result.get("recommended_actions", [])),
        provider_info_json=json.dumps(result.get("provider_info", {})),
        score=result.get("score", 50),
        retention_expiry=retention_expiry
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    output = record.to_dict()
    return output

@router.get("/assessments/{assessment_id}")
async def get_assessment(
    assessment_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    record = db.query(AssessmentModel).filter(AssessmentModel.id == assessment_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    # Strict ownership verification: assessment IDs alone must never grant access
    if not session_id or record.session_id != session_id:
        raise HTTPException(status_code=403, detail="Access denied to this assessment")

    return record.to_dict()
