"""Link + Message + Screenshot API: OCR is isolated in short-lived CPU workers."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import init_db
from .routers import link, dashboard, message, screenshot, qr, document, media, offer
from .services.screenshot_upload_limit import ScreenshotUploadLimit


@asynccontextmanager
async def lifespan(app):
    init_db()
    from .services.media_jobs import recover_interrupted_jobs
    recover_interrupted_jobs()
    try:
        yield
    finally:
        from .services.media_jobs import shutdown_jobs
        await shutdown_jobs()
        from .services.document_scan import stop_scanner
        await stop_scanner()


app = FastAPI(title='SafeLens Link Check', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
app.add_middleware(ScreenshotUploadLimit)
app.include_router(link.router)
app.include_router(dashboard.router)
app.include_router(message.router)
app.include_router(screenshot.router)
app.include_router(qr.router)
app.include_router(document.router)
app.include_router(media.router)
app.include_router(offer.router)


@app.get('/api/health/ready')
def health():
    return {'status': 'ready', 'mode': 'link-message-screenshot', 'ai_loaded': False, 'ocr_loaded': False, 'web_risk_configured': bool(settings.GOOGLE_WEB_RISK_API_KEY), 'message_model': settings.MESSAGE_OLLAMA_MODEL}
