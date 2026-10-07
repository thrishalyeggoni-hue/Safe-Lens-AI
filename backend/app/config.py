import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "SafeLens AI"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./safelens.db")
    
    # Security & Session
    SECRET_KEY: str = os.getenv("SECRET_KEY", "safelens-secure-secret-key-32-chars-min-change-prod")
    SESSION_COOKIE_NAME: str = "safelens_session"
    SESSION_MAX_AGE_SECONDS: int = 86400 * 7 # 7 days
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    
    # External Threat Intelligence
    SAFE_BROWSING_API_KEY: str = os.getenv("SAFE_BROWSING_API_KEY", "")
    SAFE_BROWSING_NONCOMMERCIAL: bool = os.getenv("SAFE_BROWSING_NONCOMMERCIAL", "true").lower() == "true"
    
    # Local & Remote AI Settings
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
    FALLBACK_LOCAL_RULES: bool = True
    
    # Limits & Storage
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024 # 50 MB
    MAX_PDF_PAGES: int = 30
    MAX_VIDEO_SECONDS: int = 180
    RETENTION_HOURS: int = 24
    STORAGE_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage")
    
    model_config = SettingsConfigDict(env_file=".env", extra="allow")

settings = Settings()

# Ensure transient storage directory exists
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
