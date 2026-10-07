from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session
from ..database import get_db, AssessmentModel
from ..config import settings

router = APIRouter(prefix="/api", tags=["Dashboard & History"])

@router.get("/dashboard/summary")
async def get_dashboard_summary(request: Request, db: Session = Depends(get_db)):
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_id:
        return {
            "total_assessments": 0,
            "caution_count": 0,
            "high_risk_count": 0,
            "low_risk_count": 0,
            "unable_count": 0,
            "recent_assessments": []
        }

    records = db.query(AssessmentModel).filter(
        AssessmentModel.session_id == session_id
    ).order_by(AssessmentModel.created_at.desc()).all()

    total = len(records)
    caution = sum(1 for r in records if r.risk_category == "Caution")
    high_risk = sum(1 for r in records if r.risk_category == "High Risk")
    low_risk = sum(1 for r in records if r.risk_category == "Low Risk")
    unable = sum(1 for r in records if r.risk_category == "Unable to Assess")

    recent = [r.to_dict() for r in records[:4]]

    return {
        "total_assessments": total,
        "caution_count": caution,
        "high_risk_count": high_risk,
        "low_risk_count": low_risk,
        "unable_count": unable,
        "recent_assessments": recent
    }

@router.get("/history")
async def get_history(request: Request, db: Session = Depends(get_db)):
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_id:
        return []

    records = db.query(AssessmentModel).filter(
        AssessmentModel.session_id == session_id
    ).order_by(AssessmentModel.created_at.desc()).all()

    return [r.to_dict() for r in records]

@router.delete("/history")
async def clear_history(request: Request, db: Session = Depends(get_db)):
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_id:
        return {"cleared": 0}

    deleted_count = db.query(AssessmentModel).filter(
        AssessmentModel.session_id == session_id
    ).delete()
    db.commit()

    return {"cleared": deleted_count}
