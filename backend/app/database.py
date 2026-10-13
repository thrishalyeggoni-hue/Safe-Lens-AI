import json
from datetime import datetime, timedelta, timezone
from typing import Generator
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from .config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class AssessmentModel(Base):
    __tablename__ = "assessments"

    id = Column(String(64), primary_key=True, index=True)
    session_id = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    module_type = Column(String(32), nullable=False)
    input_summary = Column(String(256), nullable=False)
    risk_category = Column(String(32), nullable=False)
    explanation = Column(Text, nullable=False)
    findings_json = Column(Text, default="[]")
    evidence_json = Column(Text, default="[]")
    checks_json = Column(Text, default="[]")
    unavailable_checks_json = Column(Text, default="[]")
    recommended_actions_json = Column(Text, default="[]")
    provider_info_json = Column(Text, default="{}")
    score = Column(Integer, nullable=True)
    retention_expiry = Column(DateTime, nullable=False)

    def to_dict(self):
        output = {
            "id": self.id,
            "created_at": self.created_at.strftime("%d %b, %H:%M") if self.created_at else "",
            "created_at_iso": self.created_at.isoformat() if self.created_at else "",
            "module_type": self.module_type,
            "input_summary": self.input_summary,
            "risk_category": self.risk_category,
            "explanation": self.explanation,
            "findings": json.loads(self.findings_json or "[]"),
            "evidence": json.loads(self.evidence_json or "[]"),
            "checks_performed": json.loads(self.checks_json or "[]"),
            "unavailable_checks": json.loads(self.unavailable_checks_json or "[]"),
            "recommended_actions": json.loads(self.recommended_actions_json or "[]"),
            "provider_info": json.loads(self.provider_info_json or "{}"),
            "score": self.score,
            "retention_expiry": self.retention_expiry.isoformat() if self.retention_expiry else ""
        }
        if self.module_type == 'link':
            output.update(output['provider_info'].get('link_analysis', {}))
        if self.module_type in ('link', 'message', 'screenshot', 'qr', 'document', 'media', 'offer'):
            output['created_at'] = self.created_at.replace(tzinfo=timezone.utc).isoformat()
            output['created_at_iso'] = output['created_at']
        if self.module_type == 'message':
            output['content_saved'] = False
            output['message_details_retained'] = False
        if self.module_type in ('screenshot','qr','document','media','offer'):
            output['content_saved'] = False
            output[f'{self.module_type}_details_retained'] = False
        return output

class JobModel(Base):
    __tablename__ = "jobs"

    job_id = Column(String(64), primary_key=True, index=True)
    session_id = Column(String(64), index=True, nullable=False)
    status = Column(String(32), default="processing") # queued, processing, completed, failed, cancelled
    current_stage = Column(String(64), default="Initialising validation...")
    stages_json = Column(Text, default="[]")
    assessment_id = Column(String(64), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "job_id": self.job_id,
            "status": self.status,
            "current_stage": self.current_stage,
            "stages": json.loads(self.stages_json or "[]"),
            "assessment_id": self.assessment_id,
            "error": self.error
        }

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
