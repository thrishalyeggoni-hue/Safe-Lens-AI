import uuid
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

class EvidenceItem(BaseModel):
    id: str = Field(default_factory=lambda: f"ev_{uuid.uuid4().hex[:8]}")
    snippet: str
    source_type: str # text, ocr, qr, pdf_page, audio_transcript, metadata
    page_number: Optional[int] = None
    text_offset: Optional[Dict[str, int]] = None # {"start": 0, "end": 15}
    bounding_box: Optional[Dict[str, float]] = None # {"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.3}
    timestamp_range: Optional[Dict[str, float]] = None # {"start": 1.2, "end": 4.5}
    detail: Optional[str] = None

class FindingItem(BaseModel):
    id: str = Field(default_factory=lambda: f"find_{uuid.uuid4().hex[:8]}")
    source: str # e.g. "DNS Verification", "Heuristic Rules", "Contextual NLP"
    observation: str
    interpretation: str
    action: str
    risk_level: str = "Caution" # Low Risk, Caution, High Risk, Informational

class CheckItem(BaseModel):
    name: str
    status: str # "passed", "flagged", "inconclusive", "unavailable"
    detail: str

class AssessmentCreateRequest(BaseModel):
    module_type: str # link, message, screenshot, qr, document, media, offer
    content_text: Optional[str] = None
    target_url: Optional[str] = None

class AssessmentResponse(BaseModel):
    id: str
    created_at: str
    module_type: str
    input_summary: str
    risk_category: str # Low Risk, Caution, High Risk, Unable to Assess
    explanation: str
    findings: List[FindingItem] = []
    evidence: List[EvidenceItem] = []
    checks_performed: List[CheckItem] = []
    unavailable_checks: List[CheckItem] = []
    recommended_actions: List[str] = []
    provider_info: Dict[str, Any] = {}
    score: Optional[int] = None
    retention_expiry: str

class JobStatusResponse(BaseModel):
    job_id: str
    status: str # "queued", "processing", "completed", "failed", "cancelled"
    current_stage: str
    stages: List[str] = []
    assessment_id: Optional[str] = None
    error: Optional[str] = None

class DashboardSummary(BaseModel):
    total_assessments: int
    caution_count: int
    high_risk_count: int
    low_risk_count: int
    unable_count: int
    recent_assessments: List[Dict[str, Any]] = []

class CapabilitiesResponse(BaseModel):
    supported_modules: List[str]
    max_upload_size_mb: int
    ocr_available: bool
    qr_decoder_available: bool
    clamav_available: bool
    whisper_available: bool
    safe_browsing_configured: bool
    local_llm_available: bool
    version: str
