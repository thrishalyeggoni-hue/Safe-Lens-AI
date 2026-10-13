from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException
from ..config import settings


class ScreenshotUploadLimit:
    """Enforce multipart request limits before spooled file parsing, including chunked requests."""
    def __init__(self,app): self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope.get('path') not in ('/api/check/screenshot','/api/check/qr','/api/check/document','/api/check/media','/api/check/offer') or scope.get('method')!='POST':
            return await self.app(scope,receive,send)
        document=scope.get('path') in ('/api/check/document','/api/check/offer')
        media=scope.get('path')=='/api/check/media'
        limit=50*1024*1024 if media else 20*1024*1024 if document else settings.SCREENSHOT_MAX_BYTES
        maximum=limit+128*1024
        length=dict(scope.get('headers',[])).get(b'content-length')
        if length:
            try: oversized=int(length)>maximum
            except ValueError: oversized=True
            if oversized:
                return await JSONResponse({'detail':f'Upload exceeds the {limit//(1024*1024)} MiB limit'},status_code=413)(scope,receive,send)
        consumed=0
        async def bounded_receive():
            nonlocal consumed
            event=await receive()
            consumed+=len(event.get('body',b''))
            if consumed>maximum:
                raise HTTPException(413,detail=f'Upload exceeds the {limit//(1024*1024)} MiB limit')
            return event
        await self.app(scope,bounded_receive,send)
