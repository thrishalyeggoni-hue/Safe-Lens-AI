import asyncio
import httpx
from ..config import settings
from .dns_service import now

ENDPOINT = 'https://webrisk.googleapis.com/v1/uris:search'
THREATS = ('MALWARE', 'SOCIAL_ENGINEERING', 'UNWANTED_SOFTWARE')


async def lookup_reputation(url: str) -> dict:
    result = {'provider': 'Google Web Risk Lookup API', 'source_url': ENDPOINT, 'lookup_time': now(), 'status': 'unavailable', 'threats': []}
    key = settings.GOOGLE_WEB_RISK_API_KEY
    if not key:
        return {**result, 'error': 'GOOGLE_WEB_RISK_API_KEY is not configured'}
    params = [('uri', url), *[('threatTypes', threat) for threat in THREATS]]
    try:
        async with asyncio.timeout(6), httpx.AsyncClient(timeout=4, trust_env=False, follow_redirects=False) as client:
            # Key stays in backend request headers, not URLs/logs or browser code.
            async with client.stream('GET', ENDPOINT, params=params, headers={'X-Goog-Api-Key': key, 'Accept-Encoding': 'identity'}) as response:
                result['http_status'] = response.status_code
                if response.status_code != 200:
                    return {**result, 'error': f'Google Web Risk HTTP {response.status_code}'}
                body = b''
                async for chunk in response.aiter_raw():
                    if len(body) + len(chunk) > 65536:
                        raise ValueError('Provider response exceeded 64 KiB')
                    body += chunk
        import json
        data = json.loads(body)
        if not isinstance(data, dict) or (data and 'threat' not in data) or ('threat' in data and not isinstance(data['threat'], dict)):
            raise ValueError('Unexpected provider response')
        threats = data.get('threat', {}).get('threatTypes', [])
        if not isinstance(threats, list) or any(threat not in THREATS for threat in threats) or ('threat' in data and not threats):
            raise ValueError('Unexpected provider threat information')
        result.update(status='listed' if threats else 'not_listed', threats=threats, expire_time=data.get('threat', {}).get('expireTime'),
                      detail='Listed threat reported by this reputation provider' if threats else 'Not listed by this reputation provider')
    except Exception as exc:
        # Do not serialize exception URLs/headers; they can contain credentials.
        result['error'] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
    return result
