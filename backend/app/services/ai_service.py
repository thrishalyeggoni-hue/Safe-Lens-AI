import json
import httpx
from typing import Dict, Any, Optional
from ..config import settings

async def query_ollama_qwen(prompt: str, system_prompt: str, schema: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Query local Ollama instance for Qwen structured output if running."""
    try:
        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
        payload = {
            "model": settings.OLLAMA_MODEL,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9
            }
        }
        if schema:
            payload["format"] = "json"

        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                raw_response = data.get("response", "")
                if schema or raw_response.strip().startswith("{"):
                    try:
                        return json.loads(raw_response)
                    except json.JSONDecodeError:
                        return {"text": raw_response}
                return {"text": raw_response}
    except Exception:
        # Ollama not running or model not pulled; graceful fallback
        return None
    return None

async def check_ollama_health() -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags")
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                return {
                    "running": True,
                    "models": models,
                    "target_model_ready": any(settings.OLLAMA_MODEL in m for m in models)
                }
    except Exception:
        pass
    return {"running": False, "models": [], "target_model_ready": False}
