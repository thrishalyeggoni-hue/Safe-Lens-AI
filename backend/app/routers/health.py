import os
import shutil
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..database import get_db
from ..config import settings
from ..services.ai_service import check_ollama_health

router = APIRouter(prefix="/api", tags=["Health & Readiness"])

@router.get("/health/ready")
async def health_ready(db: Session = Depends(get_db)):
    # 1. Database check
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    # 2. OCR engine check
    tesseract_ok = shutil.which("tesseract") is not None or os.path.exists("/opt/homebrew/bin/tesseract")

    # 3. FFmpeg check
    ffmpeg_ok = shutil.which("ffmpeg") is not None or os.path.exists("/opt/homebrew/bin/ffmpeg")

    # 4. Ollama server check
    ollama_status = await check_ollama_health()

    # 5. Google Safe Browsing configured check
    gsb_configured = bool(settings.SAFE_BROWSING_API_KEY)

    return {
        "status": "ready" if db_ok else "degraded",
        "database": {"ready": db_ok, "type": "sqlite" if "sqlite" in settings.DATABASE_URL else "postgresql"},
        "ocr_engine": {"ready": tesseract_ok, "engine": "Tesseract 5.5"},
        "media_processor": {"ready": ffmpeg_ok, "binary": "ffmpeg"},
        "local_model_server": ollama_status,
        "threat_intel_service": {
            "google_safe_browsing": {
                "configured": gsb_configured,
                "mode": "live_api" if gsb_configured else "unconfigured_opt_in"
            }
        }
    }

@router.get("/capabilities")
async def get_capabilities():
    tesseract_ok = shutil.which("tesseract") is not None or os.path.exists("/opt/homebrew/bin/tesseract")
    ffmpeg_ok = shutil.which("ffmpeg") is not None or os.path.exists("/opt/homebrew/bin/ffmpeg")
    ollama_status = await check_ollama_health()

    return {
        "supported_modules": [
            "link",
            "message",
            "screenshot",
            "qr",
            "document",
            "media",
            "offer"
        ],
        "max_upload_size_mb": round(settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)),
        "ocr_available": tesseract_ok,
        "qr_decoder_available": True,
        "clamav_available": False,
        "whisper_available": False,
        "ffmpeg_available": ffmpeg_ok,
        "safe_browsing_configured": bool(settings.SAFE_BROWSING_API_KEY),
        "local_llm_available": ollama_status.get("running", False),
        "version": settings.VERSION
    }
