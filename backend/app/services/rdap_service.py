from datetime import datetime, timezone

from .dns_service import now
from .redirect_service import fetch_public_json

BOOTSTRAP_URL = 'https://data.iana.org/rdap/dns.json'
_bootstrap = None
_bootstrap_time = 0


async def lookup_rdap(domain: str | None) -> dict:
    global _bootstrap, _bootstrap_time
    result = {'provider': 'IANA RDAP bootstrap / registry RDAP', 'lookup_time': now(), 'status': 'unavailable',
              'registered_domain': domain, 'bootstrap_source': BOOTSTRAP_URL}
    if not domain:
        return {**result, 'error': 'No registered domain; RDAP domain lookup is not applicable'}
    try:
        import time
        if _bootstrap is None or time.monotonic() - _bootstrap_time > 86400:
            _bootstrap, _ = await fetch_public_json(BOOTSTRAP_URL)
            _bootstrap_time = time.monotonic()
        tld = domain.rsplit('.', 1)[-1]
        bases = next((urls for tlds, urls in _bootstrap['services'] if tld in tlds), [])
        if not bases:
            return {**result, 'error': 'No RDAP service in the IANA bootstrap for this TLD'}
        base = next((url for url in bases if url.startswith('https://')), bases[0])
        data, source = await fetch_public_json(base.rstrip('/') + '/domain/' + domain)
        if data.get('objectClassName') != 'domain' or data.get('ldhName', '').lower().rstrip('.') != domain:
            raise ValueError('RDAP response does not identify the requested domain')
        events = {event['eventAction']: event['eventDate'] for event in data.get('events', []) if event.get('eventAction') and event.get('eventDate')}
        registrar = None
        for entity in data.get('entities', []):
            if 'registrar' in entity.get('roles', []):
                card = entity.get('vcardArray', [None, []])
                registrar = next((item[3] for item in card[1] if len(item) > 3 and item[0] == 'fn'), None)
                break
        result.update(status='available', source_url=source, registration_date=events.get('registration'), expiry_date=events.get('expiration'),
                      registrar=registrar, nameservers=[ns['ldhName'] for ns in data.get('nameservers', []) if ns.get('ldhName')],
                      domain_status=data.get('status', []))
        if result['registration_date']:
            try:
                registered = datetime.fromisoformat(result['registration_date'].replace('Z', '+00:00'))
                age = (datetime.now(timezone.utc) - registered).days
                if age >= 0:
                    result['age_days'] = age
            except (ValueError, TypeError):
                pass
    except Exception as exc:
        result['error'] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
    return result
