from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import init_db
from .routers import assessments, dashboard, health, link, message, screenshot, qr, document, media, offer
from .services.screenshot_upload_limit import ScreenshotUploadLimit

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite/PostgreSQL schema
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

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Real Security Backend for SafeLens AI",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assessments.router)
app.include_router(dashboard.router)
app.include_router(health.router)
app.include_router(link.router)
app.include_router(message.router)
app.include_router(screenshot.router)
app.include_router(qr.router)
app.include_router(document.router)
app.include_router(media.router)
app.include_router(offer.router)
app.add_middleware(ScreenshotUploadLimit)

import os
from fastapi.staticfiles import StaticFiles

# If production frontend build exists in dist, serve it under root origin
dist_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "dist")
if os.path.exists(dist_dir):
    app.mount("/", StaticFiles(directory=dist_dir, html=True), name="static")
else:
    @app.get("/")
    def root():
        return {
            "app": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "status": "operational",
            "api_docs": "/docs"
        }
